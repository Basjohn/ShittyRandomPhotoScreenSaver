"""Image routing from processed Qt images into detached Quick state (H).

Normal async image rotation captures its already-processed ``QImage`` into an
immutable :class:`PresentationImage` inside the compute task, so the GUI thread
only admits/publishes detached state.  The legacy/startup ``QPixmap`` seam
remains for paths that genuinely originate on Qt's GUI thread.

This module owns no lifecycle, processing policy, or image accounting; it only
normalizes processed pixels into the render thread's immutable value contract.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QImage, QPixmap

from .image_boundary import capture_qimage, capture_qpixmap
from .image_state import PresentationImage




def presentation_image_from_processed_qimage(
    image: QImage,
    *,
    image_path: str = "",
) -> PresentationImage:
    """Capture a processed QImage into immutable presentation state.

    Unlike the legacy QPixmap seam this operation is GUI-independent, so the
    image pipeline can perform the necessary RGBA deep copy in its compute
    task and hand the UI thread an already-detached presentation value.
    Identity/DPR semantics intentionally match the QPixmap route.
    """

    identity = f"{image_path}@{image.width()}x{image.height()}"
    return capture_qimage(image, identity=identity, source_path=image_path)


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
    "presentation_image_from_processed_qimage",
    "presentation_image_from_processed_pixmap",
]
