"""Always-on Qt/QML diagnostic capture.

Qt and QML own a diagnostic plane that is separate from Python ``logging``.
Binding errors, QML warnings, signal/slot complaints, shader/component failures
and other Qt messages normally go through Qt's process message handler and are
therefore easy to miss when an investigation looks only at ``screensaver*.log``.

This module installs one process-scoped ``qInstallMessageHandler`` callback and
writes those messages synchronously to ``screensaver_qml.log``.  The sidecar is
small, bounded, eagerly created every run, and deliberately independent of the
ordinary asynchronous logging queue: a QML/Qt error storm must not disappear
because the normal queue is saturated or already closing.

The sidecar is additive.  A pre-existing Qt message handler is preserved and
called after capture; when Qt had no custom handler, a compact equivalent is
echoed to the original stderr so script/debug console behaviour remains useful.

This is *not* a process-level stderr redirect.  Native libraries or other code
that writes directly to file descriptor 2 without using Qt remain outside this
capture.  See ``Docs/Qt_QML_Observability.md`` before adding an OS-level stderr
tee: fd-level redirection has materially different subprocess/crash semantics.
"""
from __future__ import annotations

import atexit
from collections import Counter
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os
import sys
import threading
import time
import uuid
from typing import Any, Callable, Optional

_MAIN_LOGGER = logging.getLogger("qt")
_QT_LOGGER = logging.getLogger("srpss.qml")

QT_MESSAGE_LOG_NAME = "screensaver_qml.log"

# Small but deep enough for repeated QML warning storms. The file is direct and
# synchronous, so keep the active chunk modest and rotate rather than growing
# one giant file.
_MAX_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 3

_state_lock = threading.RLock()
_installed = False
_handler: Optional[RotatingFileHandler] = None
_capture_path: Optional[Path] = None
_qt_handler: Optional[Callable[..., None]] = None
_previous_qt_handler: Optional[Callable[..., None]] = None
_atexit_registered = False
_session_id: str | None = None
_session_started_monotonic: float | None = None
_message_count = 0
_counts_by_level: Counter[str] = Counter()
_counts_by_category: Counter[str] = Counter()
_write_errors = 0
_last_metrics: dict[str, Any] = {}


class _CaptureRotatingFileHandler(RotatingFileHandler):
    """Rotating handler that exposes sidecar write failures as telemetry."""

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802 - logging API
        global _write_errors
        with _state_lock:
            _write_errors += 1
        # Do not call the normal logging pipeline from a Qt message callback.
        # Best-effort stderr is the only emergency notification here.
        try:
            stream = getattr(sys, "__stderr__", None) or sys.stderr
            if stream is not None:
                stream.write("[QT_CAPTURE] sidecar write failed\n")
                stream.flush()
        except Exception:
            pass
        # Intentionally do not call super().handleError(): in development it can
        # print a traceback to stderr for every failed record and create a second
        # diagnostic storm while Qt itself may already be failing.


def _level_for(mode: object) -> int:
    """Map a QtMsgType-like value to one Python logging level."""

    name = getattr(mode, "name", str(mode))
    if "Debug" in name:
        return logging.DEBUG
    if "Info" in name:
        return logging.INFO
    if "Warning" in name:
        return logging.WARNING
    if "Fatal" in name:
        return logging.CRITICAL
    if "Critical" in name:
        return logging.ERROR
    return logging.WARNING


def _level_name(level: int) -> str:
    return logging.getLevelName(level).upper()


def _clean(value: object | None, *, fallback: str = "-") -> str:
    if value is None:
        return fallback
    try:
        text = str(value).strip()
    except Exception:
        return fallback
    if not text:
        return fallback
    return text.replace("\r", " ").replace("\n", " ")


def _source_text(file: str | None, line: int, function: str | None) -> str:
    path = _clean(file)
    fn = _clean(function)
    try:
        line_number = max(0, int(line or 0))
    except (TypeError, ValueError):
        line_number = 0
    if path == "-" and fn == "-":
        return "-"
    if line_number:
        path = f"{path}:{line_number}"
    if fn != "-":
        return f"{path}::{fn}"
    return path


def _format_payload(
    *,
    sequence: int,
    category: str | None,
    file: str | None,
    line: int,
    function: str | None,
    message: str,
) -> str:
    return (
        f"seq={sequence} "
        f"category={_clean(category, fallback='default')} "
        f"source={_source_text(file, line, function)} "
        f"message={_clean(message, fallback='')}"
    )


def _record_marker(event: str, **fields: object) -> None:
    """Write one direct capture-lifecycle marker to the Qt/QML sidecar."""

    parts = [f"event={_clean(event, fallback='unknown')}"]
    parts.extend(
        f"{_clean(key)}={_clean(value)}" for key, value in sorted(fields.items())
    )
    try:
        _QT_LOGGER.info("[QT_CAPTURE] %s", " ".join(parts))
    except Exception:
        pass


def _echo_to_prior_route(mode: object, context: object, message: str, text: str) -> None:
    """Preserve a pre-existing Qt handler or default stderr-like behaviour."""

    previous = _previous_qt_handler
    current = _qt_handler
    if callable(previous) and previous is not current:
        try:
            previous(mode, context, message)
            return
        except Exception:
            # Preserve capture even when someone else's handler is broken.
            pass

    try:
        stream = getattr(sys, "__stderr__", None) or sys.stderr
        if stream is not None:
            stream.write(text + "\n")
            stream.flush()
    except Exception:
        pass


def _log_qt_message(
    mode: object,
    *,
    context: object | None = None,
    category: str | None,
    file: str | None,
    line: int,
    function: str | None = None,
    message: str,
    echo: bool = True,
) -> None:
    """Record one Qt/QML message. Kept separate from the Qt callback for tests."""

    global _message_count

    level = _level_for(mode)
    normalized_category = _clean(category, fallback="default")
    with _state_lock:
        _message_count += 1
        sequence = _message_count
        _counts_by_level[_level_name(level)] += 1
        _counts_by_category[normalized_category] += 1

    payload = _format_payload(
        sequence=sequence,
        category=normalized_category,
        file=file,
        line=line,
        function=function,
        message=message,
    )

    # RotatingFileHandler / StreamHandler flushes every emitted record. That is
    # intentional: this channel exists specifically for errors that may precede
    # an abrupt Qt/native termination.
    try:
        _QT_LOGGER.log(level, payload)
    except Exception:
        # A Qt message callback may never raise into Qt.
        pass

    if echo:
        _echo_to_prior_route(mode, context, str(message), payload)

    # ERROR/FATAL remains visible in the ordinary log as a high-level spine when
    # that pipeline is still alive. WARNING stays sidecar-only to avoid turning
    # routine QML warnings into duplicate main-log traffic.
    if level >= logging.ERROR:
        try:
            _MAIN_LOGGER.log(level, "[QT] %s", payload)
        except Exception:
            pass


def _new_handler(path: Path) -> RotatingFileHandler:
    handler = _CaptureRotatingFileHandler(
        path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
        # Eager open is deliberate: every successful install creates the file,
        # even when the run is perfectly clean and Qt emits zero messages.
        delay=False,
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)-8s "
            "pid=%(process)d thread=%(threadName)s(%(thread)d) %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
    )
    return handler


def _configure_sidecar(path: Path) -> RotatingFileHandler:
    handler = _new_handler(path)
    _QT_LOGGER.setLevel(logging.DEBUG)
    _QT_LOGGER.propagate = False
    for existing in list(_QT_LOGGER.handlers):
        _QT_LOGGER.removeHandler(existing)
        try:
            existing.close()
        except Exception:
            pass
    _QT_LOGGER.addHandler(handler)
    return handler


def install_qt_message_capture(log_dir: Path) -> Optional[Path]:
    """Install the process-wide Qt message capture. Idempotent and relocatable.

    The handler is installed before ``QApplication`` / ``QQmlEngine`` creation in
    the normal entry point.  A successful install eagerly creates
    ``screensaver_qml.log`` and writes a ``session_start`` marker, so the absence
    of the file can no longer be confused with "Qt emitted no warnings".
    """

    global _installed, _handler, _capture_path, _qt_handler
    global _previous_qt_handler, _atexit_registered, _session_id
    global _session_started_monotonic, _message_count, _write_errors

    try:
        from PySide6.QtCore import qInstallMessageHandler
    except Exception:
        return None

    try:
        directory = Path(log_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / QT_MESSAGE_LOG_NAME
    except Exception:
        return None

    with _state_lock:
        if _installed:
            if _capture_path == path and _handler is not None:
                return _capture_path
            # A log-directory switch is rare but supported. Keep the already
            # installed Qt callback and move only the direct sink.
            try:
                new_handler = _configure_sidecar(path)
            except Exception:
                return _capture_path
            _handler = new_handler
            _capture_path = path
            _record_marker(
                "sink_relocated",
                session=_session_id or "-",
                path=path,
            )
            return _capture_path

        try:
            handler = _configure_sidecar(path)
        except Exception:
            return None

        def _qt_callback(mode, context, message) -> None:  # pragma: no cover - Qt callback
            try:
                _log_qt_message(
                    mode,
                    context=context,
                    category=getattr(context, "category", None),
                    file=getattr(context, "file", None),
                    line=int(getattr(context, "line", 0) or 0),
                    function=getattr(context, "function", None),
                    message=str(message),
                    echo=True,
                )
            except Exception:
                # Nothing from this callback may unwind into Qt.
                pass

        try:
            previous = qInstallMessageHandler(_qt_callback)
        except Exception:
            _QT_LOGGER.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
            return None

        _handler = handler
        _capture_path = path
        _qt_handler = _qt_callback
        _previous_qt_handler = previous if callable(previous) else None
        _installed = True
        _session_id = uuid.uuid4().hex[:12]
        _session_started_monotonic = time.monotonic()
        _message_count = 0
        _counts_by_level.clear()
        _counts_by_category.clear()
        _write_errors = 0

        _record_marker(
            "session_start",
            session=_session_id,
            path=path,
            pid=os.getpid(),
            max_bytes=_MAX_BYTES,
            backups=_BACKUP_COUNT,
        )
        try:
            handler.flush()
        except Exception:
            pass

        if not _atexit_registered:
            atexit.register(uninstall_qt_message_capture)
            _atexit_registered = True

        return _capture_path


def flush_qt_message_capture() -> bool:
    """Flush the direct Qt/QML sidecar without uninstalling capture."""

    with _state_lock:
        handler = _handler
    if handler is None:
        return True
    try:
        handler.flush()
        return True
    except Exception:
        return False


def get_qt_message_capture_metrics() -> dict[str, Any]:
    """Return a passive snapshot of the process-wide Qt/QML capture."""

    with _state_lock:
        duration_ms = 0.0
        if _session_started_monotonic is not None:
            duration_ms = max(
                0.0,
                (time.monotonic() - _session_started_monotonic) * 1000.0,
            )
        return {
            "installed": bool(_installed),
            "path": str(_capture_path) if _capture_path is not None else None,
            "session_id": _session_id,
            "message_count": int(_message_count),
            "counts_by_level": dict(_counts_by_level),
            "counts_by_category": dict(_counts_by_category),
            "write_errors": int(_write_errors),
            "duration_ms": float(duration_ms),
        }


def uninstall_qt_message_capture() -> None:
    """Restore the prior Qt handler and close the sidecar exactly once."""

    global _installed, _handler, _capture_path, _qt_handler
    global _previous_qt_handler, _session_id, _session_started_monotonic
    global _last_metrics

    with _state_lock:
        if not _installed and _handler is None:
            return

        metrics = get_qt_message_capture_metrics()
        _last_metrics = dict(metrics)
        _record_marker(
            "session_end",
            session=metrics.get("session_id") or "-",
            messages=metrics.get("message_count", 0),
            levels=metrics.get("counts_by_level", {}),
            categories=metrics.get("counts_by_category", {}),
            write_errors=metrics.get("write_errors", 0),
            duration_ms=f"{float(metrics.get('duration_ms', 0.0)):.1f}",
        )
        try:
            if _handler is not None:
                _handler.flush()
        except Exception:
            pass

        try:
            from PySide6.QtCore import qInstallMessageHandler

            qInstallMessageHandler(_previous_qt_handler)
        except Exception:
            pass

        handler = _handler
        if handler is not None:
            try:
                _QT_LOGGER.removeHandler(handler)
            except Exception:
                pass
            try:
                handler.close()
            except Exception:
                pass

        _handler = None
        _capture_path = None
        _qt_handler = None
        _previous_qt_handler = None
        _installed = False
        _session_id = None
        _session_started_monotonic = None


def get_last_qt_message_capture_metrics() -> dict[str, Any]:
    """Return the most recent completed-session metrics (mainly for tests)."""

    with _state_lock:
        return dict(_last_metrics)


__all__ = [
    "QT_MESSAGE_LOG_NAME",
    "flush_qt_message_capture",
    "get_last_qt_message_capture_metrics",
    "get_qt_message_capture_metrics",
    "install_qt_message_capture",
    "uninstall_qt_message_capture",
]
