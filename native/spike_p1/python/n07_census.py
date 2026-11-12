"""Process census for handle and thread attribution (N0.7, harness only; Windows).

What this process holds, read from inside it: its handles by kernel object type (NtQuerySystemInformation with
SystemExtendedHandleInformation, the type names from NtQueryObject's ObjectTypeInformation on our own handle values)
and its threads with each one's start address resolved to a module (NtQueryInformationThread,
ThreadQuerySetWin32StartAddress) and its description (GetThreadDescription; Qt names its QThreads with it). Two
censuses diffed name what a step left behind: "+1 Thread, +1 Event, ... and a new thread starting in ntdll.dll" is
a thread-pool worker, a new thread in nvoglv64.dll is the driver's, in Qt6Core.dll a QThread.

The census opens and closes thread handles while it runs; read handle counts before calling it.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
SYSTEM_EXTENDED_HANDLE_INFORMATION = 64
OBJECT_TYPE_INFORMATION = 2
THREAD_QUERY_SET_WIN32_START_ADDRESS = 9
THREAD_QUERY_INFORMATION = 0x0040
THREAD_QUERY_LIMITED_INFORMATION = 0x0800
GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS = 0x4
GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT = 0x2

_ntdll = ctypes.WinDLL("ntdll")
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_ntdll.NtQuerySystemInformation.restype = ctypes.c_long
_ntdll.NtQuerySystemInformation.argtypes = [ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
                                            ctypes.POINTER(ctypes.c_ulong)]
_ntdll.NtQueryObject.restype = ctypes.c_long
_ntdll.NtQueryObject.argtypes = [wintypes.HANDLE, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
                                 ctypes.POINTER(ctypes.c_ulong)]
_ntdll.NtQueryInformationThread.restype = ctypes.c_long
_ntdll.NtQueryInformationThread.argtypes = [wintypes.HANDLE, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
                                            ctypes.POINTER(ctypes.c_ulong)]
_kernel32.OpenThread.restype = wintypes.HANDLE
_kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.GetModuleHandleExW.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.HMODULE)]
_kernel32.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
_kernel32.LocalFree.argtypes = [ctypes.c_void_p]
_GetThreadDescription = getattr(_kernel32, "GetThreadDescription", None)
if _GetThreadDescription is not None:
    _GetThreadDescription.restype = ctypes.c_long
    _GetThreadDescription.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]

_TYPE_NAMES: dict[int, str] = {}


class _UnicodeString(ctypes.Structure):
    _fields_ = [("Length", ctypes.c_ushort), ("MaximumLength", ctypes.c_ushort), ("Buffer", ctypes.c_void_p)]


def _own_handles() -> list[tuple[int, int]]:
    """[(handle value, object type index)] of this process."""
    import numpy as np

    size = 1 << 22
    while True:
        buf = ctypes.create_string_buffer(size)
        needed = ctypes.c_ulong(0)
        status = _ntdll.NtQuerySystemInformation(SYSTEM_EXTENDED_HANDLE_INFORMATION, buf, size, ctypes.byref(needed))
        if (status & 0xFFFFFFFF) == STATUS_INFO_LENGTH_MISMATCH:
            size = max(size * 2, needed.value + (1 << 20))
            continue
        if status != 0:
            raise OSError(f"NtQuerySystemInformation: NTSTATUS 0x{status & 0xFFFFFFFF:08X}")
        break
    count = int.from_bytes(buf.raw[:8], "little")
    entry = np.dtype([("object", "<u8"), ("pid", "<u8"), ("handle", "<u8"), ("access", "<u4"), ("backtrace", "<u2"),
                      ("type", "<u2"), ("attributes", "<u4"), ("reserved", "<u4")])
    table = np.frombuffer(buf.raw, dtype=entry, count=count, offset=16)
    own = table[table["pid"] == os.getpid()]
    return [(int(h), int(t)) for h, t in zip(own["handle"], own["type"])]


def _type_name(handle: int, index: int) -> str:
    if index in _TYPE_NAMES:
        return _TYPE_NAMES[index]
    buf = ctypes.create_string_buffer(1024)
    status = _ntdll.NtQueryObject(wintypes.HANDLE(handle), OBJECT_TYPE_INFORMATION, buf, 1024, None)
    name = f"type_{index}"
    if status == 0:
        us = _UnicodeString.from_buffer(buf)
        if us.Buffer and us.Length:
            name = ctypes.wstring_at(us.Buffer, us.Length // 2)
    _TYPE_NAMES[index] = name
    return name


def _module_of(address: int) -> tuple[str, int]:
    module = wintypes.HMODULE()
    if not address or not _kernel32.GetModuleHandleExW(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            ctypes.c_void_p(address), ctypes.byref(module)):
        return "?", address
    path = ctypes.create_unicode_buffer(1024)
    _kernel32.GetModuleFileNameW(module, path, 1024)
    base = ctypes.cast(module, ctypes.c_void_p).value or 0
    return os.path.basename(path.value) or "?", address - base


def _thread_record(tid: int) -> dict:
    record: dict = {"tid": tid}
    handle = _kernel32.OpenThread(THREAD_QUERY_INFORMATION | THREAD_QUERY_LIMITED_INFORMATION, False, tid)
    if not handle:
        record["error"] = "OpenThread failed"
        return record
    try:
        start = ctypes.c_void_p(0)
        if _ntdll.NtQueryInformationThread(handle, THREAD_QUERY_SET_WIN32_START_ADDRESS, ctypes.byref(start),
                                           ctypes.sizeof(start), None) == 0:
            module, offset = _module_of(start.value or 0)
            record["start_module"] = module
            record["start_offset"] = hex(offset)
        if _GetThreadDescription is not None:
            text = ctypes.c_void_p(0)
            if _GetThreadDescription(handle, ctypes.byref(text)) >= 0 and text.value:
                record["description"] = ctypes.wstring_at(text.value)
                _kernel32.LocalFree(text)
    finally:
        _kernel32.CloseHandle(handle)
    return record


def census() -> dict:
    """This process's handles by object type and its threads (start module, description)."""
    import psutil

    result: dict = {}
    try:
        handles = _own_handles()
        by_type: dict[str, int] = {}
        for value, index in handles:
            name = _type_name(value, index)
            by_type[name] = by_type.get(name, 0) + 1
        result["handles_total"] = len(handles)
        result["handles_by_type"] = dict(sorted(by_type.items()))
    except Exception as exc:  # noqa: BLE001 - the census informs, it never fails a run
        result["handles_error"] = str(exc)
    try:
        result["threads"] = [_thread_record(t.id) for t in psutil.Process().threads()]
    except Exception as exc:  # noqa: BLE001
        result["threads_error"] = str(exc)
    return result


def diff(before: dict, after: dict) -> dict:
    """What changed between two censuses: handle counts per type, threads that appeared or went."""
    a, b = before.get("handles_by_type", {}), after.get("handles_by_type", {})
    types = {k: b.get(k, 0) - a.get(k, 0) for k in sorted(set(a) | set(b)) if b.get(k, 0) != a.get(k, 0)}
    old = {t["tid"]: t for t in before.get("threads", [])}
    new = {t["tid"]: t for t in after.get("threads", [])}
    return {"handles_total": after.get("handles_total", 0) - before.get("handles_total", 0),
            "handles_by_type": types,
            "threads_new": [new[t] for t in new if t not in old],
            "threads_gone": [old[t] for t in old if t not in new]}
