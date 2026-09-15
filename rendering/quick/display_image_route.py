"""QImage -> immutable Qt Quick presentation routing.

Steady-state wallpaper rotation admits only processed ``QImage`` values and
immediately detaches them into :class:`PresentationImage`.  There is deliberately
no generic pixmap route or synchronous compatibility fallback in this module.
The one unavoidable QScreen screenshot pixmap is isolated in
``startup_desktop_capture`` and cannot be used by runtime image rotation.
"""

from __future__ import annotations

from PySide6.QtGui import QImage

from .image_boundary import capture_qimage
from .image_state import PresentationImage


def presentation_image_from_processed_qimage(
    image: QImage,
    *,
    image_path: str = "",
) -> PresentationImage:
    """Deep-copy a processed QImage into immutable presentation state."""

    identity = f"{image_path}@{image.width()}x{image.height()}"
    return capture_qimage(image, identity=identity, source_path=image_path)


__all__ = ["presentation_image_from_processed_qimage"]
