"""Explicit startup-only QScreen screenshot boundary for Qt Quick.

``QScreen.grabWindow()`` is a Qt API that necessarily returns ``QPixmap``.  That
native GUI object is allowed only here and is immediately converted/captured to
detached ``PresentationImage`` state.  No steady-state image route accepts a
QPixmap and this helper must never be used for wallpaper rotation/fallback.
"""

from __future__ import annotations

from PySide6.QtCore import QThread
from PySide6.QtGui import QGuiApplication, QPixmap

from .image_boundary import capture_qimage
from .image_state import PresentationImage


def capture_startup_desktop_pixmap(
    pixmap: QPixmap,
    *,
    screen_index: int,
) -> PresentationImage:
    app = QGuiApplication.instance()
    if app is None or QThread.currentThread() is not app.thread():
        raise RuntimeError("startup desktop QPixmap capture must run on the Qt GUI thread")
    if not isinstance(pixmap, QPixmap) or pixmap.isNull():
        raise ValueError("startup desktop capture requires a non-null QPixmap")
    identity = f"__startup_desktop_screen_{int(screen_index)}__@{pixmap.width()}x{pixmap.height()}"
    # QPixmap is not retained beyond this call. The QImage is immediately deep
    # copied into the immutable Quick presentation value contract.
    return capture_qimage(
        pixmap.toImage(),
        identity=identity,
        source_path=f"__startup_desktop_screen_{int(screen_index)}__",
        device_pixel_ratio=float(pixmap.devicePixelRatio()),
    )


__all__ = ["capture_startup_desktop_pixmap"]
