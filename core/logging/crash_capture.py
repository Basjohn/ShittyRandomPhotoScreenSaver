"""Native-fault capture plus diagnostic-build lifecycle breadcrumbs.

Debug/verbose and dedicated diagnostic runs retain faulthandler output in a
companion file so recoverable Windows SEH/COM faults are not visible only in the
console. The diagnostic build additionally records bounded lifecycle stages and
uncaught Python exceptions. Hang/stall diagnostics must never retarget the
global faulthandler stream away from this authority.
"""
from __future__ import annotations

import atexit
import faulthandler
import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import TextIO

from core.build_profile import is_diagnostic_build


CRASH_LOG_NAME = "diagnostic_crash.log"
NATIVE_FAULT_LOG_NAME = "native_faults.log"
CRASH_LOG_MAX_BYTES = 1 * 1024 * 1024
CRASH_LOG_BACKUP_COUNT = 5

_stream: TextIO | None = None
_capture_path: Path | None = None
_capture_enabled = False
_atexit_registered = False
_faulthandler_was_enabled = False
_owns_faulthandler = False
_previous_sys_excepthook = None
_previous_threading_excepthook = None
_installed_sys_excepthook = None
_installed_threading_excepthook = None
_capture_lock = threading.RLock()


def _trim_oversized_crash_log(path: Path) -> None:
    """Bound a raw fatal dump before it becomes a retained backup."""

    try:
        size = path.stat().st_size
    except OSError:
        return
    if size <= CRASH_LOG_MAX_BYTES:
        return

    marker = b"[older diagnostic crash output trimmed]\n"
    keep_bytes = max(0, CRASH_LOG_MAX_BYTES - len(marker))
    temp_path = path.with_name(f".{path.name}.trim")
    try:
        with path.open("rb") as source:
            source.seek(-keep_bytes, os.SEEK_END)
            tail = source.read(keep_bytes)
        temp_path.write_bytes(marker + tail)
        temp_path.replace(path)
    except OSError:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _rotate_crash_log(path: Path, *, force: bool = False) -> None:
    """Rotate an oversized crash companion before opening the next session."""

    try:
        if (
            not path.is_file()
            or (not force and path.stat().st_size < CRASH_LOG_MAX_BYTES)
        ):
            return
    except OSError:
        return

    try:
        _trim_oversized_crash_log(path)
        oldest = path.with_name(f"{path.name}.{CRASH_LOG_BACKUP_COUNT}")
        oldest.unlink(missing_ok=True)
        for index in range(CRASH_LOG_BACKUP_COUNT - 1, 0, -1):
            source = path.with_name(f"{path.name}.{index}")
            destination = path.with_name(f"{path.name}.{index + 1}")
            if source.exists():
                source.replace(destination)
        path.replace(path.with_name(f"{path.name}.1"))
    except OSError:
        # Failure to rotate must not stop the diagnostic runtime from opening.
        return


def _safe_field(value: object) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    return text[:256]


def _reopen_after_rollover() -> bool:
    """Rotate/reopen the companion while preserving owned faulthandler output."""

    global _stream
    if _capture_path is None:
        return False
    old_stream = _stream
    try:
        if _owns_faulthandler and faulthandler.is_enabled():
            faulthandler.disable()
        if old_stream is not None:
            old_stream.flush()
            old_stream.close()
        _rotate_crash_log(_capture_path, force=True)
        _stream = _capture_path.open("a", encoding="utf-8", buffering=1)
        if _owns_faulthandler:
            faulthandler.enable(file=_stream, all_threads=True)
        return True
    except (OSError, RuntimeError, ValueError):
        _stream = None
        return False


def _ensure_capacity(additional_bytes: int) -> bool:
    """Keep ordinary breadcrumbs within the configured active-file limit."""

    if _stream is None:
        return False
    try:
        current_size = _stream.tell()
    except (OSError, ValueError):
        try:
            current_size = _capture_path.stat().st_size if _capture_path else 0
        except OSError:
            current_size = 0
    if current_size + max(0, int(additional_bytes)) <= CRASH_LOG_MAX_BYTES:
        return True
    return _reopen_after_rollover()


def _write_bounded_text(payload: str) -> None:
    """Write diagnostic Python text without allowing repeated growth."""

    if not payload:
        return
    encoded = payload.encode("utf-8", errors="replace")
    max_payload = max(256, CRASH_LOG_MAX_BYTES - 512)
    if len(encoded) > max_payload:
        marker = b"\n...[diagnostic traceback truncated]...\n"
        head_size = max(0, (max_payload - len(marker)) // 2)
        tail_size = max(0, max_payload - len(marker) - head_size)
        encoded = encoded[:head_size] + marker + encoded[-tail_size:]
    with _capture_lock:
        if not _ensure_capacity(len(encoded)) or _stream is None:
            return
        try:
            _stream.write(encoded.decode("utf-8", errors="replace"))
            _stream.flush()
        except (OSError, ValueError):
            return


def record_diagnostic_stage(stage: str, **fields: object) -> None:
    """Write and flush one privacy-safe diagnostic lifecycle boundary."""

    if not is_diagnostic_build() or _stream is None:
        return
    timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
    parts = [
        timestamp,
        f"pid={os.getpid()}",
        f"thread={threading.get_ident()}",
        f"stage={_safe_field(stage)}",
    ]
    parts.extend(f"{key}={_safe_field(value)}" for key, value in sorted(fields.items()))
    _write_bounded_text(" ".join(parts) + "\n")


def enable_diagnostic_crash_capture(
    log_dir: Path, *, allow_runtime_capture: bool = False
) -> Path | None:
    """Enable persistent native-fault capture for diagnostic or debug runs.

    ``allow_runtime_capture`` is granted by startup for source/developer runs or
    an explicit ``--debug``/``--verbose`` profile. Diagnostic builds retain
    lifecycle and uncaught-Python breadcrumbs in ``diagnostic_crash.log``; other
    admitted runs use the clearer ``native_faults.log`` companion.
    """

    global _stream, _capture_path, _capture_enabled, _atexit_registered
    global _faulthandler_was_enabled, _owns_faulthandler
    global _previous_sys_excepthook, _previous_threading_excepthook
    global _installed_sys_excepthook, _installed_threading_excepthook

    diagnostic_build = is_diagnostic_build()
    if not diagnostic_build and not allow_runtime_capture:
        return None
    if _capture_enabled and _stream is not None:
        return Path(_stream.name)

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / (CRASH_LOG_NAME if diagnostic_build else NATIVE_FAULT_LOG_NAME)
        _rotate_crash_log(path)
        _capture_path = path
        _stream = path.open("a", encoding="utf-8", buffering=1)
    except OSError:
        _stream = None
        return None

    _faulthandler_was_enabled = faulthandler.is_enabled()
    # This module is the sole persistent native-fault stream authority while
    # active. Even an environment-enabled faulthandler is redirected to the
    # companion so a recoverable Windows fault cannot remain console-only.
    try:
        if _faulthandler_was_enabled:
            faulthandler.disable()
        faulthandler.enable(file=_stream, all_threads=True)
        _owns_faulthandler = True
    except (OSError, RuntimeError, ValueError):
        # Opening the companion file is not success: if faulthandler cannot own
        # it, report capture as unavailable rather than leaving a false-positive
        # path in startup logs. Restore the caller's prior stderr ownership when
        # possible and close our unused stream.
        _owns_faulthandler = False
        stream = _stream
        _stream = None
        _capture_path = None
        if stream is not None:
            try:
                stream.flush()
                stream.close()
            except OSError:
                pass
        if _faulthandler_was_enabled:
            try:
                faulthandler.enable(file=sys.stderr, all_threads=True)
            except (OSError, RuntimeError, ValueError):
                pass
        _faulthandler_was_enabled = False
        return None

    if diagnostic_build:
        _previous_sys_excepthook = sys.excepthook

        def _sys_excepthook(exc_type, exc_value, exc_traceback) -> None:
            record_diagnostic_stage("python_unhandled_exception", exception=exc_type.__name__)
            _write_bounded_text(
                "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            )
            previous = _previous_sys_excepthook
            if callable(previous):
                previous(exc_type, exc_value, exc_traceback)

        _installed_sys_excepthook = _sys_excepthook
        sys.excepthook = _installed_sys_excepthook

        if hasattr(threading, "excepthook"):
            _previous_threading_excepthook = threading.excepthook

            def _threading_excepthook(args) -> None:
                exception_type = getattr(args, "exc_type", None)
                record_diagnostic_stage(
                    "thread_unhandled_exception",
                    exception=getattr(exception_type, "__name__", "unknown"),
                    thread=getattr(getattr(args, "thread", None), "name", "unknown"),
                )
                _write_bounded_text(
                    "".join(
                        traceback.format_exception(
                            exception_type,
                            getattr(args, "exc_value", None),
                            getattr(args, "exc_traceback", None),
                        )
                    )
                )
                previous = _previous_threading_excepthook
                if callable(previous):
                    previous(args)

            _installed_threading_excepthook = _threading_excepthook
            threading.excepthook = _installed_threading_excepthook

    _capture_enabled = True
    if diagnostic_build:
        record_diagnostic_stage(
            "crash_capture_enabled",
            executable=Path(getattr(sys, "executable", "") or "").name or "unknown",
        )
    else:
        _write_bounded_text(
            f"{datetime.now().astimezone().isoformat(timespec='milliseconds')} "
            f"native fault capture enabled pid={os.getpid()} "
            f"thread={threading.get_ident()}\n"
        )
    if not _atexit_registered:
        atexit.register(close_diagnostic_crash_capture)
        _atexit_registered = True
    return path

def close_diagnostic_crash_capture() -> None:
    """Flush/release native-fault capture and restore any prior faulthandler state."""

    global _stream, _capture_path, _capture_enabled, _owns_faulthandler
    global _faulthandler_was_enabled
    global _previous_sys_excepthook, _previous_threading_excepthook
    global _installed_sys_excepthook, _installed_threading_excepthook

    if not _capture_enabled:
        return
    if is_diagnostic_build():
        record_diagnostic_stage("orderly_process_exit")
    else:
        _write_bounded_text(
            f"{datetime.now().astimezone().isoformat(timespec='milliseconds')} "
            f"native fault capture closed pid={os.getpid()} "
            f"thread={threading.get_ident()}\n"
        )
    if sys.excepthook is _installed_sys_excepthook and callable(_previous_sys_excepthook):
        sys.excepthook = _previous_sys_excepthook
    if (
        hasattr(threading, "excepthook")
        and threading.excepthook is _installed_threading_excepthook
        and callable(_previous_threading_excepthook)
    ):
        threading.excepthook = _previous_threading_excepthook
    if _owns_faulthandler and faulthandler.is_enabled():
        try:
            faulthandler.disable()
        except RuntimeError:
            pass
    if _faulthandler_was_enabled:
        try:
            faulthandler.enable(file=sys.stderr, all_threads=True)
        except (OSError, RuntimeError, ValueError):
            pass
    stream = _stream
    _stream = None
    _capture_path = None
    _capture_enabled = False
    _owns_faulthandler = False
    _faulthandler_was_enabled = False
    _previous_sys_excepthook = None
    _previous_threading_excepthook = None
    _installed_sys_excepthook = None
    _installed_threading_excepthook = None
    if stream is not None:
        try:
            stream.flush()
            stream.close()
        except OSError:
            pass

