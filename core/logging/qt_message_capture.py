"""Capture Qt/QML engine messages into a bounded, rotating sidecar log.

Qt and the QML engine emit their own diagnostics (binding `TypeError`s, missing
properties, shader/component errors) through Qt's C++ message handler, which by
default writes straight to the process **stderr**. That channel is completely
separate from this app's Python ``logging`` pipeline, so those messages never
reach any ``screensaver*.log`` file — they exist only on the console. That blind
spot hid the Clock retirement null-model storm (``ClockAnalogueFace.qml: Cannot
read property '...' of null``) from every log scan.

``install_qt_message_capture`` installs a Qt message handler that routes those
messages into a dedicated ``screensaver_qml.log`` written by a
``RotatingFileHandler`` (size-capped, rotated), independent of the async main-log
queue so a storm is captured reliably rather than dropped. Console parity is
preserved: each message is still echoed to the original stderr, so anyone
watching the console sees exactly what they saw before — the file is purely
additive. Genuine Qt errors/fatals are additionally surfaced into the main log.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from typing import Optional

_MAIN_LOGGER = logging.getLogger("qt")
_QML_LOGGER = logging.getLogger("srpss.qml")

# Reasonable bounded footprint: 2 MB per file, 3 rotations -> 8 MB ceiling.
_MAX_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 3

_installed = False
_handler: Optional[RotatingFileHandler] = None
_capture_path: Optional[Path] = None


def _level_for(mode: object) -> int:
    """Map a QtMsgType to a Python logging level without importing Qt eagerly."""

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


def _log_qt_message(
    mode: object,
    *,
    category: str | None,
    file: str | None,
    line: int,
    message: str,
) -> None:
    """Record one Qt/QML message. Separated from the Qt handler for testability."""

    level = _level_for(mode)
    text = str(message)
    normalized_category = (category or "").strip()
    if normalized_category and normalized_category != "default":
        text = f"[{normalized_category}] {text}"
    if file and ".qml" not in text and str(file) not in text:
        # QML messages usually already embed file:line; only append when absent.
        text = f"{text} ({file}:{line})"

    try:
        _QML_LOGGER.log(level, text)
    except Exception:
        pass

    # Preserve the pre-existing console behaviour: Qt's default handler wrote
    # these to stderr, and operators watch the console for them.
    try:
        original = getattr(sys, "__stderr__", None) or sys.stderr
        if original is not None:
            original.write(text + "\n")
    except Exception:
        pass

    # A real Qt/QML error or fatal is worth surfacing in the main log too.
    if level >= logging.ERROR:
        try:
            _MAIN_LOGGER.log(level, "[QT] %s", text)
        except Exception:
            pass


def install_qt_message_capture(log_dir: Path) -> Optional[Path]:
    """Install the Qt message handler and its rotating sidecar. Idempotent.

    Returns the sidecar path on success, or ``None`` if capture could not be set
    up (in which case Qt's default stderr behaviour is left untouched).
    """

    global _installed, _handler, _capture_path
    if _installed:
        return _capture_path

    try:
        from PySide6.QtCore import qInstallMessageHandler
    except Exception:
        return None

    try:
        directory = Path(log_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "screensaver_qml.log"
        handler = RotatingFileHandler(
            path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
            delay=True,
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s %(message)s",
                "%Y-%m-%d %H:%M:%S",
            )
        )
    except Exception:
        return None

    _QML_LOGGER.setLevel(logging.DEBUG)
    _QML_LOGGER.propagate = False
    # Replace any prior handler on re-init (e.g. a forced log-dir switch).
    for existing in list(_QML_LOGGER.handlers):
        _QML_LOGGER.removeHandler(existing)
    _QML_LOGGER.addHandler(handler)
    _handler = handler
    _capture_path = path

    def _qt_handler(mode, context, message) -> None:  # pragma: no cover - Qt cb
        try:
            _log_qt_message(
                mode,
                category=getattr(context, "category", None),
                file=getattr(context, "file", None),
                line=int(getattr(context, "line", 0) or 0),
                message=message,
            )
        except Exception:
            # A message handler must never raise back into Qt.
            pass

    try:
        qInstallMessageHandler(_qt_handler)
    except Exception:
        return None

    _installed = True
    return _capture_path


def uninstall_qt_message_capture() -> None:
    """Restore Qt's default handler and detach the sidecar (best-effort)."""

    global _installed, _handler
    try:
        from PySide6.QtCore import qInstallMessageHandler

        qInstallMessageHandler(None)
    except Exception:
        pass
    if _handler is not None:
        try:
            _QML_LOGGER.removeHandler(_handler)
            _handler.close()
        except Exception:
            pass
    _handler = None
    _installed = False


__all__ = [
    "install_qt_message_capture",
    "uninstall_qt_message_capture",
]
