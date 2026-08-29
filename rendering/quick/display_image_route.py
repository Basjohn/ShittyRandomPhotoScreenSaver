"""GUI-thread image routing from the legacy pipeline into a Quick runtime (H).

The image pipeline produces a processed ``QPixmap`` per display on the Qt GUI
thread. This seam captures that pixmap into immutable :class:`PresentationImage`
state (a tightly packed RGBA deep copy) and publishes it into the display's
:class:`~rendering.quick.runtime.QuickDisplayRuntime` through its explicit
``set_presentation_image`` API - no compositor/private-widget poke, no live
QPixmap crossing into the render thread.

It is deliberately tiny and presentation-neutral: it owns no lifecycle, no
processing policy and no image accounting; the display orchestrator calls it on
the GUI thread with an already-processed pixmap.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QPixmap

from .image_boundary import capture_qpixmap
from .image_state import PresentationImage


def presentation_image_from_processed_pixmap(
    pixmap: QPixmap,
    *,
    image_path: str = "",
) -> PresentationImage:
    """Capture a processed pipeline QPixmap into immutable presentation state.

    The pixmap's own device pixel ratio is preserved. Must run on the Qt GUI
    thread (enforced by :func:`capture_qpixmap`). The image identity is derived
    from the source path and the pixmap's pixel dimensions so a re-processed
    image at a new size is a distinct identity.
    """

    identity = f"{image_path}@{pixmap.width()}x{pixmap.height()}"
    return capture_qpixmap(pixmap, identity=identity, source_path=image_path)


def present_processed_pixmap(
    runtime: Any,
    pixmap: QPixmap,
    *,
    image_path: str = "",
) -> PresentationImage:
    """Route one processed pipeline pixmap into a Quick display generation.

    Captures the pixmap on the GUI thread and publishes the resulting immutable
    base-image state through the runtime's explicit API. Returns the captured
    :class:`PresentationImage` for caller proof/accounting. Raises if the runtime
    cannot currently accept a base image (retiring, or mid-transition).
    """

    image = presentation_image_from_processed_pixmap(pixmap, image_path=image_path)
    runtime.set_presentation_image(image)
    return image


__all__ = [
    "present_processed_pixmap",
    "presentation_image_from_processed_pixmap",
]
