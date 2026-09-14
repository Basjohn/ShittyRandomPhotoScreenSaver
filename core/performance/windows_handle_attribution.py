"""Out-of-process Windows handle-type attribution for ``--usage`` diagnostics.

R-84 needs to distinguish a real main-process handle leak from observer-owned
PDH churn. Querying every live handle from inside SRPSS would itself perturb the
process being measured, so this diagnostic runs in a tiny child process and
writes ``screensaver_handles.log`` directly. The main process contributes only
a stable child-process owner handle; the child PID is excluded from ``--usage``
app aggregates.

The sidecar takes a system extended-handle snapshot, filters it to the target
PID, groups by object type index, then duplicates at most a few representative
handles per index into the sidecar to resolve the kernel object type name. It
never duplicates handles back into the target process and never touches
``--perf``.
"""
from __future__ import annotations

import ctypes
import json
import multiprocessing as mp
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from ctypes import wintypes

SYSTEM_EXTENDED_HANDLE_INFORMATION = 64
OBJECT_TYPE_INFORMATION = 2
PROCESS_DUP_HANDLE = 0x0040
SYNCHRONIZE = 0x00100000
DUPLICATE_SAME_ACCESS = 0x00000002
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102

_STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
_STATUS_BUFFER_OVERFLOW = 0x80000005
_STATUS_BUFFER_TOO_SMALL = 0xC0000023
_MAX_SYSTEM_HANDLE_BUFFER = 256 * 1024 * 1024
_DEFAULT_SAMPLE_INTERVAL_S = 60.0


class _SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX(ctypes.Structure):
    _fields_ = [
        ("Object", ctypes.c_void_p),
        ("UniqueProcessId", ctypes.c_size_t),
        ("HandleValue", ctypes.c_size_t),
        ("GrantedAccess", wintypes.ULONG),
        ("CreatorBackTraceIndex", wintypes.USHORT),
        ("ObjectTypeIndex", wintypes.USHORT),
        ("HandleAttributes", wintypes.ULONG),
        ("Reserved", wintypes.ULONG),
    ]


class _UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", ctypes.c_void_p),
    ]


class _OBJECT_TYPE_INFORMATION_PREFIX(ctypes.Structure):
    _fields_ = [("TypeName", _UNICODE_STRING)]


def _status_code(status: int) -> int:
    return int(status) & 0xFFFFFFFF


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _write_json_line(stream, payload: dict[str, object]) -> None:
    stream.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    stream.flush()


def _windows_apis():
    if os.name != "nt":
        raise OSError("Windows handle attribution is Windows-only")

    ntdll = ctypes.WinDLL("ntdll")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    ntdll.NtQuerySystemInformation.argtypes = [
        wintypes.ULONG,
        ctypes.c_void_p,
        wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG),
    ]
    ntdll.NtQuerySystemInformation.restype = wintypes.LONG
    ntdll.NtQueryObject.argtypes = [
        wintypes.HANDLE,
        wintypes.ULONG,
        ctypes.c_void_p,
        wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG),
    ]
    ntdll.NtQueryObject.restype = wintypes.LONG

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.DuplicateHandle.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.DuplicateHandle.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return ntdll, kernel32


def _query_target_handles(ntdll, target_pid: int) -> list[tuple[int, int]]:
    """Return ``(object_type_index, handle_value)`` pairs for one PID."""

    size = 4 * 1024 * 1024
    while size <= _MAX_SYSTEM_HANDLE_BUFFER:
        buffer = ctypes.create_string_buffer(size)
        required = wintypes.ULONG(0)
        status = ntdll.NtQuerySystemInformation(
            SYSTEM_EXTENDED_HANDLE_INFORMATION,
            buffer,
            size,
            ctypes.byref(required),
        )
        code = _status_code(status)
        if code == 0:
            break
        if code != _STATUS_INFO_LENGTH_MISMATCH:
            raise OSError(f"NtQuerySystemInformation failed: 0x{code:08X}")
        requested = int(required.value) + (256 * 1024)
        size = max(size * 2, requested)
    else:
        raise MemoryError("System handle snapshot exceeded diagnostic safety cap")

    header_size = ctypes.sizeof(ctypes.c_size_t) * 2
    entry_size = ctypes.sizeof(_SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX)
    count = int(ctypes.c_size_t.from_buffer(buffer, 0).value)
    available = max(0, (len(buffer) - header_size) // entry_size)
    count = min(count, available)
    base = ctypes.addressof(buffer) + header_size

    target: list[tuple[int, int]] = []
    for index in range(count):
        entry = _SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX.from_address(base + (index * entry_size))
        if int(entry.UniqueProcessId) != target_pid:
            continue
        target.append((int(entry.ObjectTypeIndex), int(entry.HandleValue)))
    return target


def _query_type_name(ntdll, duplicated_handle: wintypes.HANDLE) -> str | None:
    size = 1024
    for _attempt in range(3):
        buffer = ctypes.create_string_buffer(size)
        required = wintypes.ULONG(0)
        status = ntdll.NtQueryObject(
            duplicated_handle,
            OBJECT_TYPE_INFORMATION,
            buffer,
            size,
            ctypes.byref(required),
        )
        code = _status_code(status)
        if code == 0:
            prefix = _OBJECT_TYPE_INFORMATION_PREFIX.from_buffer(buffer)
            length = int(prefix.TypeName.Length)
            pointer = int(prefix.TypeName.Buffer or 0)
            if length <= 0 or pointer <= 0:
                return None
            return ctypes.wstring_at(pointer, length // ctypes.sizeof(ctypes.c_wchar))
        if code not in {
            _STATUS_INFO_LENGTH_MISMATCH,
            _STATUS_BUFFER_OVERFLOW,
            _STATUS_BUFFER_TOO_SMALL,
        }:
            return None
        size = max(size * 2, int(required.value) + 256)
    return None


def _resolve_type_names(
    ntdll,
    kernel32,
    target_process: wintypes.HANDLE,
    handles_by_type: dict[int, list[int]],
    cache: dict[int, str],
) -> dict[int, str]:
    current_process = kernel32.GetCurrentProcess()
    for type_index, handle_values in handles_by_type.items():
        if type_index in cache:
            continue
        resolved: str | None = None
        for handle_value in handle_values[:8]:
            duplicate = wintypes.HANDLE()
            ok = kernel32.DuplicateHandle(
                target_process,
                wintypes.HANDLE(handle_value),
                current_process,
                ctypes.byref(duplicate),
                0,
                False,
                DUPLICATE_SAME_ACCESS,
            )
            if not ok:
                continue
            try:
                resolved = _query_type_name(ntdll, duplicate)
            finally:
                kernel32.CloseHandle(duplicate)
            if resolved:
                break
        if resolved:
            cache[type_index] = resolved
    return cache


def summarize_handle_types(
    handle_pairs: Iterable[tuple[int, int]],
    type_names: dict[int, str],
) -> tuple[dict[str, int], dict[str, str]]:
    """Pure summarizer used by the sidecar and tests."""

    counts = Counter(int(type_index) for type_index, _handle in handle_pairs)
    named: Counter[str] = Counter()
    index_names: dict[str, str] = {}
    for type_index, count in counts.items():
        name = type_names.get(type_index) or f"type_{type_index}"
        named[name] += count
        index_names[str(type_index)] = name
    return dict(sorted(named.items())), dict(sorted(index_names.items(), key=lambda item: int(item[0])))


def run_handle_attribution_sidecar(
    target_pid: int,
    log_path: str,
    interval_s: float = _DEFAULT_SAMPLE_INTERVAL_S,
) -> None:
    """Child-process entry point. Never import or call this from normal runtime."""

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    interval_s = max(30.0, float(interval_s))
    target_pid = int(target_pid)

    with path.open("a", encoding="utf-8", buffering=1) as stream:
        try:
            ntdll, kernel32 = _windows_apis()
            target_process = kernel32.OpenProcess(
                PROCESS_DUP_HANDLE | SYNCHRONIZE,
                False,
                target_pid,
            )
            if not target_process:
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception as exc:
            _write_json_line(
                stream,
                {
                    "event": "startup_error",
                    "utc": _utc_now(),
                    "target_pid": target_pid,
                    "error": repr(exc),
                },
            )
            return

        type_names: dict[int, str] = {}
        started = time.monotonic()
        sequence = 0
        try:
            _write_json_line(
                stream,
                {
                    "event": "session_start",
                    "utc": _utc_now(),
                    "target_pid": target_pid,
                    "sidecar_pid": os.getpid(),
                    "interval_s": interval_s,
                },
            )
            while True:
                sequence += 1
                sample_started = time.perf_counter()
                try:
                    pairs = _query_target_handles(ntdll, target_pid)
                    by_type: dict[int, list[int]] = defaultdict(list)
                    for type_index, handle_value in pairs:
                        by_type[type_index].append(handle_value)
                    _resolve_type_names(
                        ntdll,
                        kernel32,
                        target_process,
                        by_type,
                        type_names,
                    )
                    type_counts, index_names = summarize_handle_types(pairs, type_names)
                    _write_json_line(
                        stream,
                        {
                            "event": "sample",
                            "utc": _utc_now(),
                            "elapsed_s": round(time.monotonic() - started, 3),
                            "sequence": sequence,
                            "target_pid": target_pid,
                            "snapshot_handles": len(pairs),
                            "collect_ms": round((time.perf_counter() - sample_started) * 1000.0, 3),
                            "type_counts": type_counts,
                            "type_indices": index_names,
                        },
                    )
                except Exception as exc:
                    _write_json_line(
                        stream,
                        {
                            "event": "sample_error",
                            "utc": _utc_now(),
                            "elapsed_s": round(time.monotonic() - started, 3),
                            "sequence": sequence,
                            "target_pid": target_pid,
                            "error": repr(exc),
                        },
                    )

                wait_ms = min(0xFFFFFFFE, int(interval_s * 1000.0))
                wait_result = int(kernel32.WaitForSingleObject(target_process, wait_ms))
                if wait_result == WAIT_OBJECT_0:
                    break
                if wait_result != WAIT_TIMEOUT:
                    _write_json_line(
                        stream,
                        {
                            "event": "wait_error",
                            "utc": _utc_now(),
                            "target_pid": target_pid,
                            "wait_result": wait_result,
                        },
                    )
                    break
        finally:
            _write_json_line(
                stream,
                {
                    "event": "session_stop",
                    "utc": _utc_now(),
                    "target_pid": target_pid,
                    "sequence": sequence,
                },
            )
            kernel32.CloseHandle(target_process)


class WindowsHandleAttributionSidecar:
    """Own the R-84 helper process for one ``--usage`` session."""

    def __init__(self, log_dir: Path, *, interval_s: float = _DEFAULT_SAMPLE_INTERVAL_S) -> None:
        self._log_path = Path(log_dir) / "screensaver_handles.log"
        self._interval_s = max(30.0, float(interval_s))
        self._process: mp.Process | None = None

    @property
    def log_path(self) -> Path:
        return self._log_path

    @property
    def pid(self) -> int | None:
        process = self._process
        return None if process is None else process.pid

    def start(self, target_pid: int) -> int | None:
        if os.name != "nt":
            return None
        process = self._process
        if process is not None and process.is_alive():
            return process.pid
        # Normal diagnostic fresh-start handling clears the log directory, but
        # direct/manual --usage launches are allowed too. Start a new attribution
        # session with a fresh file so an old run cannot masquerade as current
        # handle growth. Failure to truncate is non-fatal; session_start still
        # provides a hard analysis boundary in an append-only fallback.
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_path.write_text("", encoding="utf-8")
        except OSError:
            pass
        process = mp.Process(
            target=run_handle_attribution_sidecar,
            args=(int(target_pid), str(self._log_path), self._interval_s),
            name="SRPSS_usage_handle_attribution",
            daemon=True,
        )
        process.start()
        self._process = process
        return process.pid

    def stop(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        pid = process.pid
        forced = False
        exitcode: int | None = None
        try:
            if process.is_alive():
                # The helper is diagnostics-only and flushes every JSON line.
                # Terminating it here avoids making application shutdown wait up
                # to the 60 s sample interval. A controller_stop record is
                # appended after join so abrupt child termination is explicit.
                forced = True
                process.terminate()
            process.join(timeout=2.0)
            if process.is_alive():
                forced = True
                process.kill()
                process.join(timeout=1.0)
            exitcode = process.exitcode
        finally:
            try:
                process.close()
            except (ValueError, OSError):
                pass
            try:
                self._log_path.parent.mkdir(parents=True, exist_ok=True)
                with self._log_path.open("a", encoding="utf-8", buffering=1) as stream:
                    _write_json_line(
                        stream,
                        {
                            "event": "controller_stop",
                            "utc": _utc_now(),
                            "sidecar_pid": pid,
                            "exitcode": exitcode,
                            "forced": forced,
                        },
                    )
            except OSError:
                pass


__all__ = [
    "WindowsHandleAttributionSidecar",
    "run_handle_attribution_sidecar",
    "summarize_handle_types",
]
