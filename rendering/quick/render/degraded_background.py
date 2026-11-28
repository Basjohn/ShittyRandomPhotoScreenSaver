"""The degraded display (Current_Plan.md N5.2h, the switch's point 5): no native core loaded on either API.

The photos show through Qt's own image node (``QQuickWindow.createImageNode`` with a texture Qt uploads from the item's
``PresentationImage``), placed by the presenter's one owner (``rendering.quick.background_placement``). It is not a
second renderer: no program, no GL, no transitions; a new photo replaces the old one as a hard cut (the runtime
publishes the run's destination at its end). The reason is logged once by the backend owner
(``rendering.quick.bootstrap.degraded_reason``).
"""
from __future__ import annotations

import shiboken6
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickWindow, QSGNode

from ..background_placement import background_placement
from ..image_state import PresentationImage


class DegradedBackgroundNode(QSGNode):
    """One image node showing the item's current photo; GUI-free (synchronised from ``updatePaintNode``)."""

    def __init__(self, window: QQuickWindow) -> None:
        super().__init__()
        self._window = window
        self._image_node = None
        self._image: PresentationImage | None = None   # kept while Qt may read its bytes (no-copy QImage)

    @property
    def image(self) -> PresentationImage | None:
        return self._image

    def synchronize(self, image: PresentationImage, logical_size: tuple[float, float]) -> None:
        if self._image is None or image.identity != self._image.identity:
            width, height = image.pixel_size
            qimage = QImage(image.rgba8, width, height, image.row_stride,
                            QImage.Format.Format_RGBA8888_Premultiplied)   # opaque pixels: byte-identical
            texture = self._window.createTextureFromImage(qimage, QQuickWindow.CreateTextureOption.TextureIsOpaque)
            if texture is None:
                raise RuntimeError("Qt Quick did not create the degraded background's texture")
            if self._image_node is None:
                self._image_node = self._window.createImageNode()
                self._image_node.setOwnsTexture(True)
                self._image_node.setTexture(texture)
                self.appendChildNode(self._image_node)
            else:
                self._image_node.setTexture(texture)     # owns it: the previous texture goes (a hard cut)
            # PySide parents the texture's wrapper to the window; the node owns the C++ texture now, so the wrapper
            # is detached and invalidated (never one kept per photo, never a Python-side delete).
            texture.setParent(None)
            shiboken6.invalidate(texture)
            self._image = image
        placement = background_placement(self._image.pixel_size, logical_size)
        self._image_node.setSourceRect(QRectF(*placement.source_rect))
        self._image_node.setRect(QRectF(*placement.target_rect))


__all__ = ["DegradedBackgroundNode"]
