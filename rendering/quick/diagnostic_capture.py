"""Development-only explicit key-edge capture; never a render-loop observer.

Qt/QScreen readback is performed synchronously on the owning GUI thread only
when requested. A detached QImage is saved in a disposable daemon writer so
PNG compression does not stall the Qt rendering thread. The writer retains no
runtime/QObject, cannot hold a lifecycle owner, and creates no recurring work.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from threading import Lock, Thread
from time import time_ns

from PySide6.QtCore import QPointF
from PySide6.QtGui import QCursor

from core.build_profile import is_compiled_runtime, is_diagnostic_build
from core.diagnostic_capture_contract import capture_filename, crop_pixels
from core.logging.logger import get_logger

logger = get_logger(__name__)
_capture_busy = Lock()  # One explicit screenshot at a time, no idle worker.


def capture_allowed() -> bool:
    return not is_compiled_runtime() or is_diagnostic_build()


def capture_cursor_position():
    return QCursor.pos()


def capture_directory() -> Path:
    if is_compiled_runtime():
        return Path(sys.executable).resolve().parent / "captures"
    return Path(__file__).resolve().parents[2] / "captures"


def _save_detached(image, destination: Path) -> None:
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not image.save(str(destination), "PNG"):
            raise OSError(f"QImage.save failed for {destination}")
        logger.info("[DIAGNOSTIC_CAPTURE] Written %s", destination)
    except Exception:
        logger.exception("[DIAGNOSTIC_CAPTURE] Cannot save %s", destination)


def _write_and_release(image, destination: Path) -> None:
    try:
        _save_detached(image, destination)
    finally:
        _capture_busy.release()


def capture_key_edge(*, window, scene, screen_index: int) -> Path | None:
    """One screenshot of the hovered widget, otherwise the owning physical display.

    Called only after admission and release-build checks. Hover uses a single
    instantaneous cursor point, not a pointer listener or periodic hit-test.
    """
    if not capture_allowed() or window is None or scene is None or not window.isVisible():
        return None
    screen = window.screen()
    if screen is None or not _capture_busy.acquire(blocking=False):
        return None
    scheduled = False
    try:
        cursor = capture_cursor_position()
        # Only use a widget crop when the pointer is actually on this display.
        bounds = screen.geometry()
        target = None
        if bounds.contains(cursor):
            local = window.mapFromGlobal(cursor)
            target = scene.diagnostic_capture_target_at(QPointF(local))
        pixmap = screen.grabWindow(0)
        if pixmap.isNull():
            logger.warning("[DIAGNOSTIC_CAPTURE] QScreen capture returned an empty image")
            return None
        frame = pixmap.toImage().copy()  # Detach before releasing Qt GUI-thread pixmap.
        del pixmap
        rect = crop_pixels(
            None if target is None else target[1],
            (bounds.x(), bounds.y()), (bounds.width(), bounds.height()),
            (frame.width(), frame.height()),
        )
        if rect is not None:
            frame = frame.copy(rect.x, rect.y, rect.width, rect.height)
        label = "display" if target is None or rect is None else target[0]
        destination = capture_directory() / capture_filename(
            moment=datetime.now(), screen_index=screen_index,
            region=label, suffix=time_ns() & 0xffffffff,
        )
        Thread(target=_write_and_release, args=(frame, destination), daemon=True,
               name="SRPSSCapturePNG").start()
        scheduled = True
        return destination
    except Exception:
        logger.exception("[DIAGNOSTIC_CAPTURE] Capture request failed")
        return None
    finally:
        if not scheduled:
            _capture_busy.release()
