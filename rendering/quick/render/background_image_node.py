"""Retained Qt scenegraph owner for steady background images and custom transitions."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage
from PySide6.QtQuick import (
    QQuickWindow,
    QSGImageNode,
    QSGNode,
    QSGOpacityNode,
    QSGTexture,
)

from ..image_state import PresentationImage
from ..transitions.state import TransitionRun
from .background_node import BackgroundRenderNode, SlideProofState
from .telemetry import RenderNodeTelemetry


class RetainedBackgroundSceneNode(QSGNode):
    """Retain native steady content and a blocked custom transition branch.

    Production steady-state presentation uses ``QSGImageNode`` so an unchanged
    wallpaper remains retained by Qt's scenegraph and executes no Python render
    callback per frame.  The legacy/custom ``BackgroundRenderNode`` remains
    alive behind an opacity node and is enabled only for authored transitions,
    proof rendering, and pixel-oracle harnesses.  Keeping the custom node alive
    avoids recompiling transition programs merely because a transition ended.
    """

    def __init__(
        self,
        *,
        window: QQuickWindow | None,
        telemetry: RenderNodeTelemetry,
        screen_index: int,
        frame_trace,
    ) -> None:
        super().__init__()
        self._window = window
        self._telemetry = telemetry
        self._screen_index = int(screen_index)
        self._frame_trace = frame_trace

        self._image_opacity = QSGOpacityNode()
        self._image_opacity.setOpacity(0.0)
        self.appendChildNode(self._image_opacity)

        self._custom_opacity = QSGOpacityNode()
        self._custom_opacity.setOpacity(0.0)
        self.appendChildNode(self._custom_opacity)

        self._image_node: QSGImageNode | None = None
        self._image_identity: str | None = None
        self._image_byte_count = 0
        self._custom_node = BackgroundRenderNode(
            telemetry,
            screen_index=self._screen_index,
            frame_trace=self._frame_trace,
        )
        self._custom_opacity.appendChildNode(self._custom_node)
        self._custom_active = False
        self._released = False

    @property
    def image_identity(self) -> str | None:
        return self._image_identity

    @property
    def custom_active(self) -> bool:
        return self._custom_active

    def synchronize(
        self,
        *,
        logical_size: tuple[float, float],
        device_pixel_ratio: float,
        state: SlideProofState,
        presentation_image: PresentationImage | None,
        transition_run: TransitionRun | None,
        custom_required: bool,
    ) -> None:
        """Synchronize one immutable background state on the render thread."""

        if self._released:
            raise RuntimeError("retained background scene node reused after release")

        width = max(0.0, float(logical_size[0]))
        height = max(0.0, float(logical_size[1]))
        logical_size = (width, height)

        # The native branch is intentionally omitted from pixel-oracle/proof
        # paths; those diagnostics must continue exercising the exact custom GL
        # renderer they were written to validate.
        if presentation_image is not None and not self._telemetry.capture_pixels_enabled:
            self._synchronize_native_image(
                presentation_image,
                logical_size=logical_size,
            )
        elif self._image_node is not None:
            self._image_node.setRect(QRectF(0.0, 0.0, width, height))

        if custom_required:
            self._set_native_visible(False)
            self._custom_opacity.setOpacity(1.0)
            self._custom_active = True
            self._telemetry.note_custom_background_active()
            self._custom_node.synchronize(
                logical_size=logical_size,
                device_pixel_ratio=device_pixel_ratio,
                state=state,
                presentation_image=presentation_image,
                transition_run=transition_run,
            )
            return

        # Steady production path: Qt traverses the retained image branch while
        # opacity=0 prevents traversal/rendering of the custom QSGRenderNode.
        # If a transition just ended, retire only its presentation textures;
        # shader/program/VAO resources remain warm for the next transition.
        if self._custom_active:
            self._custom_opacity.setOpacity(0.0)
            self._custom_active = False
            self._custom_node.release_presentation_textures()
        else:
            self._custom_opacity.setOpacity(0.0)

        self._set_native_visible(self._image_node is not None)
        self._telemetry.note_sync(
            logical_size=logical_size,
            device_pixel_ratio=float(device_pixel_ratio),
        )

    def release_resources(self) -> None:
        """Retire custom GL resources and mirror native texture lifetime once."""

        if self._released:
            return
        self._released = True
        self._custom_node.releaseResources()
        self._note_native_released()
        # The QSGImageNode owns its QSGTexture.  Qt deletes both with this
        # subtree; do not manually delete the texture and risk double-free.

    def _synchronize_native_image(
        self,
        image: PresentationImage,
        *,
        logical_size: tuple[float, float],
    ) -> None:
        width, height = image.pixel_size
        logical_width, logical_height = logical_size

        if self._window is None:
            raise RuntimeError("retained Quick background image has no window")

        new_image_node = False
        if self._image_node is None:
            image_node = self._window.createImageNode()
            if image_node is None:
                raise RuntimeError("Qt Quick did not create a retained background image node")
            image_node.setOwnsTexture(True)
            image_node.setFiltering(QSGTexture.Filtering.Linear)
            self._image_node = image_node
            new_image_node = True

        if self._image_identity != image.identity:
            # Wallpaper pixels are opaque (composited over black at processing;
            # the texture is created TextureIsOpaque). Straight and premultiplied
            # RGBA are byte-identical for opaque pixels, and the premultiplied label
            # spares Qt a full straight->premultiplied conversion before every
            # upload (PR-04: 8.1 -> 0.15 ms blocking at 4K).
            qimage = QImage(
                image.rgba8,
                width,
                height,
                image.row_stride,
                QImage.Format.Format_RGBA8888_Premultiplied,
            ).copy()
            if qimage.isNull():
                raise RuntimeError("Qt Quick retained background QImage conversion failed")
            qimage.setDevicePixelRatio(float(image.device_pixel_ratio))

            texture = self._window.createTextureFromImage(
                qimage,
                QQuickWindow.CreateTextureOption.TextureIsOpaque,
            )
            if texture is None:
                raise RuntimeError("Qt Quick did not create a retained background texture")

            previous_identity = self._image_identity
            previous_byte_count = self._image_byte_count
            self._image_node.setTexture(texture)
            self._image_identity = image.identity
            self._image_byte_count = image.byte_count

            if previous_identity is not None:
                self._telemetry.note_native_background_released(
                    identity=previous_identity,
                    byte_count=previous_byte_count,
                )
            self._telemetry.note_native_background_admitted(
                identity=image.identity,
                byte_count=image.byte_count,
            )

        if new_image_node:
            # QSGImageNode must have a texture before it enters the scene graph.
            self._image_opacity.appendChildNode(self._image_node)

        self._image_node.setSourceRect(
            QRectF(0.0, 0.0, float(width), float(height))
        )
        self._image_node.setRect(
            QRectF(0.0, 0.0, logical_width, logical_height)
        )

    def _set_native_visible(self, visible: bool) -> None:
        visible = bool(visible and self._image_node is not None)
        self._image_opacity.setOpacity(1.0 if visible else 0.0)
        self._telemetry.note_native_background_visibility(
            identity=self._image_identity,
            visible=visible,
        )

    def _note_native_released(self) -> None:
        identity = self._image_identity
        if identity is None:
            return
        byte_count = self._image_byte_count
        self._image_identity = None
        self._image_byte_count = 0
        self._telemetry.note_native_background_released(
            identity=identity,
            byte_count=byte_count,
        )
