"""Focused real-GL proof for the inline Quick visualizer clip and Spectrum."""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
import threading
import time
from typing import Any

from rendering.quick.bootstrap import (
    configure_quick_environment,
    configure_quick_graphics,
)


configure_quick_environment()

from OpenGL import GL as gl  # noqa: E402
from PySide6.QtCore import (  # noqa: E402
    QObject,
    QMetaObject,
    QRect,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QGuiApplication, QOpenGLContext  # noqa: E402
from PySide6.QtQuick import (  # noqa: E402
    QQuickItem,
    QQuickWindow,
    QSGRenderNode,
    QSGRendererInterface,
)

from core.settings.visualizer_mode_registry import (  # noqa: E402
    VisualizerClipPolicy,
    VisualizerModePresentationPolicy,
    VisualizerShellPolicy,
    get_visualizer_presentation_policy,
)
from rendering.quick.render.gl_resources import compile_program  # noqa: E402
from rendering.quick.visualizer import (  # noqa: E402
    VisualizerClipFrame,
    VisualizerClipHost,
    VisualizerRenderItem,
    VisualizerRenderNode,
    VisualizerRenderNodeTelemetry,
)
from widgets.spotify_visualizer.presentation_geometry import (  # noqa: E402
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.render_bridge import (  # noqa: E402
    VisualizerRenderIdentity,
    VisualizerSnapshotBridge,
)
from widgets.spotify_visualizer.render_state import (  # noqa: E402
    SpectrumFrame,
    VisualizerCommonState,
    VisualizerLogicalFrame,
    compose_visualizer_render_snapshot,
    freeze_render_fields,
)
from widgets.spotify_visualizer.spectrum_frame_runtime import (  # noqa: E402
    SpectrumFrameRuntime,
)


_WINDOW_SIZE = (320, 240)
_OUTER_RECT = (60.0, 50.0, 180.0, 140.0)
_BACKGROUND = QColor(18, 42, 96)
_DRAW_COLOR = (236, 48, 36)
_SPECTRUM_WINDOW_SIZE = (760, 600)
_SPECTRUM_ORIGIN = (80.0, 60.0)

_VERTEX_SOURCE = """#version 410 core
layout(location = 0) in vec2 aPosition;
uniform mat4 uMatrix;
uniform vec2 uItemSize;
void main() {
    vec2 itemPosition = aPosition * uItemSize;
    gl_Position = uMatrix * vec4(itemPosition, 0.0, 1.0);
}
"""

_FRAGMENT_SOURCE = """#version 410 core
out vec4 fragColor;
void main() {
    fragColor = vec4(0.92549, 0.18824, 0.14118, 1.0);
}
"""

_SAMPLE_POINTS = {
    "center": (150.0, 120.0),
    "rounded_edge_left": (74.0, 120.0),
    "rounded_edge_right": (226.0, 120.0),
    "rounded_edge_top": (150.0, 64.0),
    "rounded_edge_bottom": (150.0, 176.0),
    "rounded_corner_out_tl": (74.0, 64.0),
    "rounded_corner_out_tr": (226.0, 64.0),
    "rounded_corner_out_bl": (74.0, 176.0),
    "rounded_corner_out_br": (226.0, 176.0),
    "rounded_corner_in_tl": (81.0, 71.0),
    "rounded_corner_in_tr": (219.0, 71.0),
    "rounded_corner_in_bl": (81.0, 169.0),
    "rounded_corner_in_br": (219.0, 169.0),
    "card_border_left": (65.0, 120.0),
    "card_border_right": (235.0, 120.0),
    "card_border_top": (150.0, 55.0),
    "card_border_bottom": (150.0, 185.0),
    "rect_inside_left": (61.0, 120.0),
    "rect_inside_right": (239.0, 120.0),
    "rect_inside_top": (150.0, 51.0),
    "rect_inside_bottom": (150.0, 189.0),
    "rect_outside_left": (55.0, 120.0),
    "rect_outside_right": (245.0, 120.0),
    "rect_outside_top": (150.0, 45.0),
    "rect_outside_bottom": (150.0, 195.0),
}


def _int_state(name: int) -> int:
    value = gl.glGetIntegerv(name)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(value[0])


def _bool_state(name: int) -> bool:
    value = gl.glGetBooleanv(name)
    try:
        return bool(value[0])
    except (IndexError, TypeError):
        return bool(value)


def _set_enabled(capability: int, enabled: bool) -> None:
    if enabled:
        gl.glEnable(capability)
    else:
        gl.glDisable(capability)


def _direct_gl_state() -> dict[str, Any]:
    return {
        "viewport": [int(value) for value in gl.glGetIntegerv(gl.GL_VIEWPORT)],
        "program": _int_state(gl.GL_CURRENT_PROGRAM),
        "vao": _int_state(gl.GL_VERTEX_ARRAY_BINDING),
        "array_buffer": _int_state(gl.GL_ARRAY_BUFFER_BINDING),
        "blend_enabled": bool(gl.glIsEnabled(gl.GL_BLEND)),
        "cull_enabled": bool(gl.glIsEnabled(gl.GL_CULL_FACE)),
        "depth_enabled": bool(gl.glIsEnabled(gl.GL_DEPTH_TEST)),
        "depth_write": _bool_state(gl.GL_DEPTH_WRITEMASK),
        "color_mask": [
            bool(value) for value in gl.glGetBooleanv(gl.GL_COLOR_WRITEMASK)
        ],
        "scissor_enabled": bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST)),
        "scissor_box": [
            int(value) for value in gl.glGetIntegerv(gl.GL_SCISSOR_BOX)
        ],
        "stencil_enabled": bool(gl.glIsEnabled(gl.GL_STENCIL_TEST)),
        "stencil_func": _int_state(gl.GL_STENCIL_FUNC),
        "stencil_ref": _int_state(gl.GL_STENCIL_REF),
        "stencil_value_mask": _int_state(gl.GL_STENCIL_VALUE_MASK),
        "stencil_write_mask": _int_state(gl.GL_STENCIL_WRITEMASK),
        "stencil_fail": _int_state(gl.GL_STENCIL_FAIL),
        "stencil_depth_fail": _int_state(gl.GL_STENCIL_PASS_DEPTH_FAIL),
        "stencil_depth_pass": _int_state(gl.GL_STENCIL_PASS_DEPTH_PASS),
        "stencil_back_func": _int_state(gl.GL_STENCIL_BACK_FUNC),
        "stencil_back_ref": _int_state(gl.GL_STENCIL_BACK_REF),
        "stencil_back_value_mask": _int_state(gl.GL_STENCIL_BACK_VALUE_MASK),
        "stencil_back_write_mask": _int_state(gl.GL_STENCIL_BACK_WRITEMASK),
        "stencil_back_fail": _int_state(gl.GL_STENCIL_BACK_FAIL),
        "stencil_back_depth_fail": _int_state(
            gl.GL_STENCIL_BACK_PASS_DEPTH_FAIL
        ),
        "stencil_back_depth_pass": _int_state(
            gl.GL_STENCIL_BACK_PASS_DEPTH_PASS
        ),
    }


def _framebuffer_diagnostics() -> dict[str, Any]:
    context = QOpenGLContext.currentContext()
    framebuffer = _int_state(gl.GL_DRAW_FRAMEBUFFER_BINDING)
    result: dict[str, Any] = {
        "draw_framebuffer": framebuffer,
        "status": int(gl.glCheckFramebufferStatus(gl.GL_DRAW_FRAMEBUFFER)),
        "viewport": [int(value) for value in gl.glGetIntegerv(gl.GL_VIEWPORT)],
        "context_depth_bits": (
            -1 if context is None else int(context.format().depthBufferSize())
        ),
        "context_stencil_bits": (
            -1 if context is None else int(context.format().stencilBufferSize())
        ),
    }
    if framebuffer:
        for name, attachment in (
            ("depth", gl.GL_DEPTH_ATTACHMENT),
            ("stencil", gl.GL_STENCIL_ATTACHMENT),
        ):
            try:
                result[f"{name}_object_type"] = int(
                    gl.glGetFramebufferAttachmentParameteriv(
                        gl.GL_DRAW_FRAMEBUFFER,
                        attachment,
                        gl.GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE,
                    )
                )
                result[f"{name}_size"] = int(
                    gl.glGetFramebufferAttachmentParameteriv(
                        gl.GL_DRAW_FRAMEBUFFER,
                        attachment,
                        (
                            gl.GL_FRAMEBUFFER_ATTACHMENT_DEPTH_SIZE
                            if name == "depth"
                            else gl.GL_FRAMEBUFFER_ATTACHMENT_STENCIL_SIZE
                        ),
                    )
                )
            except Exception as exc:
                result[f"{name}_query_error"] = f"{type(exc).__name__}: {exc}"
    return result


class _SharedProbe:
    def __init__(self, policy: str) -> None:
        self.lock = threading.Lock()
        self.policy = policy
        self.captures: dict[str, dict[str, Any]] = {}
        self.error: str | None = None
        self.release_context_current = False

    def set_error(self, exc: BaseException) -> None:
        with self.lock:
            if self.error is None:
                self.error = f"{type(exc).__name__}: {exc}"

    def fail(self, message: object) -> None:
        with self.lock:
            if self.error is None:
                self.error = str(message)

    def capture(self, policy: str, value: dict[str, Any]) -> None:
        with self.lock:
            self.captures.setdefault(policy, value)

    def snapshot(self) -> tuple[dict[str, dict[str, Any]], str | None]:
        with self.lock:
            return dict(self.captures), self.error


class _NestedRenderState:
    """Focused valid incoming clip state layered over Qt's real state."""

    def __init__(
        self,
        base: QSGRenderNode.RenderState,
        *,
        scissor_rect: QRect,
        stencil_value: int,
    ) -> None:
        self._base = base
        self._scissor_rect = scissor_rect
        self._stencil_value = int(stencil_value)

    def scissorEnabled(self) -> bool:
        return True

    def scissorRect(self) -> QRect:
        return self._scissor_rect

    def stencilEnabled(self) -> bool:
        return True

    def stencilValue(self) -> int:
        return self._stencil_value

    def __getattr__(self, name: str):
        return getattr(self._base, name)


class _ProbeRenderNode(QSGRenderNode):
    def __init__(
        self,
        telemetry: VisualizerRenderNodeTelemetry,
        shared: _SharedProbe,
        window: QQuickWindow,
    ) -> None:
        super().__init__()
        self._telemetry = telemetry
        self._shared = shared
        self._window = window
        self._logical_size = (0.0, 0.0)
        self._presentation = None
        self._clip_host = VisualizerClipHost()
        self._parent_clip_host = VisualizerClipHost()
        self._released = False
        self._program = 0
        self._vao = 0
        self._vbo = 0
        self._matrix_location = -1
        self._size_location = -1

    def synchronize(
        self,
        *,
        identity,
        snapshot,
        logical_size: tuple[float, float],
        device_pixel_ratio: float,
        clear_snapshot: bool = False,
    ) -> None:
        del identity, snapshot, device_pixel_ratio, clear_snapshot
        self._logical_size = (
            max(0.0, float(logical_size[0])),
            max(0.0, float(logical_size[1])),
        )
        self._telemetry.note_sync()

    def set_presentation(self, presentation) -> None:
        self._presentation = presentation

    def rect(self) -> QRectF:
        return QRectF(0.0, 0.0, *self._logical_size)

    def flags(self) -> QSGRenderNode.RenderingFlag:
        # The proof quad deliberately exceeds the item. The clip, not a false
        # bounded-render declaration, must contain those pixels.
        return QSGRenderNode.RenderingFlag(0)

    def changedStates(self) -> QSGRenderNode.StateFlag:
        return (
            QSGRenderNode.StateFlag.BlendState
            | QSGRenderNode.StateFlag.CullState
            | QSGRenderNode.StateFlag.DepthState
        )

    def render(self, state: QSGRenderNode.RenderState) -> None:
        try:
            if not self._program:
                self._initialize_gl()
            presentation = self._presentation
            if presentation is None:
                raise RuntimeError("clip probe has no presentation")
            target = self.renderTarget()
            if target is None:
                raise RuntimeError("clip probe has no render target")
            size = target.pixelSize()
            target_size = (int(size.width()), int(size.height()))
            if target_size[0] <= 0 or target_size[1] <= 0:
                raise RuntimeError(f"invalid clip probe target: {target_size}")

            framebuffer_diagnostics = _framebuffer_diagnostics()
            outer_inherited_gl = _direct_gl_state()
            matrix_values = tuple(
                float(value)
                for value in (self.projectionMatrix() * self.matrix()).data()
            )
            clip_frame = VisualizerClipFrame.from_presentation(
                presentation,
                matrix_values=matrix_values,
                viewport=(0, 0, *target_size),
            )
            with self._shared.lock:
                policy = self._shared.policy
            parent_run = None
            effective_state = state
            if policy == "nested":
                parent_frame = VisualizerClipFrame(
                    logical_size=clip_frame.logical_size,
                    local_content_rect=(0.0, 0.0, *clip_frame.logical_size),
                    inner_corner_radius=0.0,
                    matrix_values=matrix_values,
                    viewport=clip_frame.viewport,
                )
                parent_run = self._parent_clip_host.begin(parent_frame, state)
                scale_x = target_size[0] / float(self._window.width())
                scale_y = target_size[1] / float(self._window.height())
                clip_left = int(round(_OUTER_RECT[0] * scale_x))
                clip_bottom = int(
                    round(
                        (
                            self._window.height()
                            - _OUTER_RECT[1]
                            - _OUTER_RECT[3]
                        )
                        * scale_y
                    )
                )
                effective_state = _NestedRenderState(
                    state,
                    scissor_rect=QRect(
                        clip_left,
                        clip_bottom,
                        int(round(100.0 * scale_x)),
                        int(round(_OUTER_RECT[3] * scale_y)),
                    ),
                    stencil_value=parent_run.local_stencil_value,
                )
            try:
                (
                    colors,
                    stencil_samples,
                    restored_stencil_samples,
                    inherited_gl,
                    restored_gl,
                ) = self._render_local_clip(
                    effective_state,
                    clip_frame=clip_frame,
                    matrix_values=matrix_values,
                    target_size=target_size,
                )
            finally:
                if parent_run is not None:
                    self._parent_clip_host.end(parent_run)
            final_stencil_samples = self._sample_stencil(target_size)
            final_gl = _direct_gl_state()
            self._shared.capture(
                policy,
                {
                    "colors": colors,
                    "stencil_samples": stencil_samples,
                    "restored_stencil_samples": restored_stencil_samples,
                    "restored_gl": restored_gl,
                    "final_stencil_samples": final_stencil_samples,
                    "final_gl": final_gl,
                    "outer_inherited_gl": outer_inherited_gl,
                    "render_thread_id": threading.get_ident(),
                    "target_size": list(target_size),
                    "framebuffer": framebuffer_diagnostics,
                    "clip_frame": {
                        "logical_size": list(clip_frame.logical_size),
                        "content_rect": list(clip_frame.local_content_rect),
                        "corner_radius": clip_frame.inner_corner_radius,
                        "matrix": list(clip_frame.matrix_values),
                        "viewport": list(clip_frame.viewport),
                    },
                    "render_state": {
                        "scissor_enabled": bool(effective_state.scissorEnabled()),
                        "scissor_rect": list(
                            effective_state.scissorRect().getRect()
                        ),
                        "stencil_enabled": bool(effective_state.stencilEnabled()),
                        "stencil_value": int(effective_state.stencilValue()),
                    },
                    "inherited_gl": inherited_gl,
                },
            )
            self._telemetry.note_render(
                scissor_enabled=bool(effective_state.scissorEnabled()),
                scissor_rect=tuple(
                    int(value) for value in effective_state.scissorRect().getRect()
                ),
                stencil_enabled=bool(effective_state.stencilEnabled()),
                stencil_value=int(effective_state.stencilValue()),
            )
        except Exception as exc:
            self._shared.set_error(exc)

    def _render_local_clip(
        self,
        state,
        *,
        clip_frame: VisualizerClipFrame,
        matrix_values: tuple[float, ...],
        target_size: tuple[int, int],
    ) -> tuple[
        dict[str, list[int]],
        dict[str, int],
        dict[str, int],
        dict[str, Any],
        dict[str, Any],
    ]:
        inherited_gl = _direct_gl_state()
        clip_run = self._clip_host.begin(clip_frame, state)
        try:
            prior_viewport = tuple(
                int(value) for value in gl.glGetIntegerv(gl.GL_VIEWPORT)
            )
            prior_program = _int_state(gl.GL_CURRENT_PROGRAM)
            prior_vao = _int_state(gl.GL_VERTEX_ARRAY_BINDING)
            prior_array_buffer = _int_state(gl.GL_ARRAY_BUFFER_BINDING)
            prior_blend = bool(gl.glIsEnabled(gl.GL_BLEND))
            prior_cull = bool(gl.glIsEnabled(gl.GL_CULL_FACE))
            prior_depth = bool(gl.glIsEnabled(gl.GL_DEPTH_TEST))
            prior_color_mask = tuple(
                bool(value) for value in gl.glGetBooleanv(gl.GL_COLOR_WRITEMASK)
            )
            try:
                gl.glDisable(gl.GL_BLEND)
                gl.glDisable(gl.GL_CULL_FACE)
                gl.glDisable(gl.GL_DEPTH_TEST)
                gl.glColorMask(
                    gl.GL_TRUE,
                    gl.GL_TRUE,
                    gl.GL_TRUE,
                    gl.GL_TRUE,
                )
                gl.glViewport(0, 0, *target_size)
                gl.glUseProgram(self._program)
                gl.glBindVertexArray(self._vao)
                gl.glUniformMatrix4fv(
                    self._matrix_location,
                    1,
                    gl.GL_FALSE,
                    matrix_values,
                )
                rect = self.rect()
                gl.glUniform2f(
                    self._size_location,
                    float(rect.width()),
                    float(rect.height()),
                )
                gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
                colors = self._sample_pixels(target_size)
                stencil_samples = self._sample_stencil(target_size)
            finally:
                gl.glBindVertexArray(prior_vao)
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, prior_array_buffer)
                gl.glUseProgram(prior_program)
                gl.glViewport(*prior_viewport)
                _set_enabled(gl.GL_BLEND, prior_blend)
                _set_enabled(gl.GL_CULL_FACE, prior_cull)
                _set_enabled(gl.GL_DEPTH_TEST, prior_depth)
                gl.glColorMask(*prior_color_mask)
        finally:
            self._clip_host.end(clip_run)
        return (
            colors,
            stencil_samples,
            self._sample_stencil(target_size),
            inherited_gl,
            _direct_gl_state(),
        )

    def releaseResources(self) -> None:
        if (
            self._program
            or self._vao
            or self._vbo
            or self._clip_host.has_resources
            or self._parent_clip_host.has_resources
        ):
            context = QOpenGLContext.currentContext()
            self._shared.release_context_current = context is not None
            if context is None:
                self._shared.set_error(
                    RuntimeError("clip probe released GL without a current context")
                )
            else:
                self._clip_host.release_resources()
                self._parent_clip_host.release_resources()
                if self._program:
                    gl.glDeleteProgram(self._program)
                if self._vbo:
                    gl.glDeleteBuffers(1, [self._vbo])
                if self._vao:
                    gl.glDeleteVertexArrays(1, [self._vao])
                self._program = 0
                self._vbo = 0
                self._vao = 0
        if not self._released:
            self._released = True
            self._telemetry.note_release()

    def _initialize_gl(self) -> None:
        if QOpenGLContext.currentContext() is None:
            raise RuntimeError("clip probe initialized without a current GL context")
        self._program = compile_program(
            _VERTEX_SOURCE,
            _FRAGMENT_SOURCE,
            label="Quick visualizer clip proof",
        )
        # Oversized normalized quad: every clip edge is tested against pixels
        # this render node would otherwise paint.
        vertices = (ctypes.c_float * 8)(
            -0.25,
            -0.25,
            1.25,
            -0.25,
            -0.25,
            1.25,
            1.25,
            1.25,
        )
        self._vao = int(gl.glGenVertexArrays(1))
        self._vbo = int(gl.glGenBuffers(1))
        gl.glBindVertexArray(self._vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._vbo)
        gl.glBufferData(
            gl.GL_ARRAY_BUFFER,
            ctypes.sizeof(vertices),
            vertices,
            gl.GL_STATIC_DRAW,
        )
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(
            0,
            2,
            gl.GL_FLOAT,
            False,
            2 * ctypes.sizeof(ctypes.c_float),
            ctypes.c_void_p(0),
        )
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)
        self._matrix_location = int(gl.glGetUniformLocation(self._program, "uMatrix"))
        self._size_location = int(gl.glGetUniformLocation(self._program, "uItemSize"))
        if min(self._matrix_location, self._size_location) < 0:
            raise RuntimeError("clip probe uniforms are incomplete")

    def _sample_pixels(
        self,
        target_size: tuple[int, int],
    ) -> dict[str, list[int]]:
        scale_x = target_size[0] / float(self._window.width())
        scale_y = target_size[1] / float(self._window.height())
        colors: dict[str, list[int]] = {}
        for name, (logical_x, logical_y) in _SAMPLE_POINTS.items():
            pixel_x = max(
                0,
                min(target_size[0] - 1, int(round(logical_x * scale_x))),
            )
            pixel_y = max(
                0,
                min(
                    target_size[1] - 1,
                    target_size[1] - 1 - int(round(logical_y * scale_y)),
                ),
            )
            rgba = bytes(
                gl.glReadPixels(
                    pixel_x,
                    pixel_y,
                    1,
                    1,
                    gl.GL_RGBA,
                    gl.GL_UNSIGNED_BYTE,
                )
            )
            colors[name] = list(rgba[:4])
        return colors

    def _sample_stencil(
        self,
        target_size: tuple[int, int],
    ) -> dict[str, int]:
        scale_x = target_size[0] / float(self._window.width())
        scale_y = target_size[1] / float(self._window.height())
        samples: dict[str, int] = {}
        for name in (
            "center",
            "rect_outside_left",
            "rounded_corner_out_tl",
            "rounded_edge_right",
        ):
            logical_x, logical_y = _SAMPLE_POINTS[name]
            pixel_x = max(
                0,
                min(target_size[0] - 1, int(round(logical_x * scale_x))),
            )
            pixel_y = max(
                0,
                min(
                    target_size[1] - 1,
                    target_size[1] - 1 - int(round(logical_y * scale_y)),
                ),
            )
            raw = bytes(
                gl.glReadPixels(
                    pixel_x,
                    pixel_y,
                    1,
                    1,
                    gl.GL_STENCIL_INDEX,
                    gl.GL_UNSIGNED_BYTE,
                )
            )
            samples[name] = int(raw[0]) if raw else -1
        return samples


class _ProbeItem(QQuickItem):
    def __init__(
        self,
        parent: QQuickItem,
        *,
        shared: _SharedProbe,
        window: QQuickWindow,
        telemetry: VisualizerRenderNodeTelemetry,
    ) -> None:
        super().__init__(parent)
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)
        self._shared = shared
        self._window = window
        self._telemetry = telemetry
        self._presentation = None
        self._render_node: _ProbeRenderNode | None = None
        window.sceneGraphInvalidated.connect(
            self._invalidate,
            Qt.ConnectionType.DirectConnection,
        )

    def set_presentation(self, presentation) -> None:
        self._presentation = presentation
        self.setWidth(presentation.outer_rect[2])
        self.setHeight(presentation.outer_rect[3])
        self.update()

    def updatePaintNode(self, old_node, _update_data):
        render_node = (
            old_node
            if isinstance(old_node, _ProbeRenderNode)
            else _ProbeRenderNode(
                self._telemetry,
                self._shared,
                self._window,
            )
        )
        presentation = self._presentation
        logical_size = (
            presentation.outer_rect[2],
            presentation.outer_rect[3],
        )
        render_node.set_presentation(presentation)
        render_node.synchronize(
            identity=None,
            snapshot=None,
            logical_size=logical_size,
            device_pixel_ratio=presentation.dpr,
            clear_snapshot=True,
        )
        self._render_node = render_node
        return render_node

    def _invalidate(self) -> None:
        node, self._render_node = self._render_node, None
        self._telemetry.note_invalidation()
        if node is not None:
            node.releaseResources()


def _spectrum_case_geometry(case: str) -> tuple[tuple[float, float], float]:
    if case == "scaled":
        return (420.0, 280.0), 0.65
    if case == "wide":
        return (560.0, 280.0), 1.0
    if case == "tall":
        return (420.0, 420.0), 1.0
    return (420.0, 280.0), 1.0


def _spectrum_snapshot(case: str, presentation):
    runtime = SpectrumFrameRuntime()
    if case == "idle":
        resolved = runtime.resolve(
            [0.0] * 16,
            bar_count=16,
            now_ts=1.0,
            runtime_generation=1,
            engine_generation=2,
            activation_id=3,
            source_generation=-1,
            source_activation_id=-1,
            playing=False,
            first_frame=True,
            smoothing_enabled=True,
            smoothing_strength=0.5,
            single_piece=True,
            segments=53,
            ghosting_enabled=True,
            ghost_decay=0.4,
            animation_enabled=False,
        )
        playing = False
        source_generation = -1
        source_activation = -1
    else:
        bars = (
            (0.18,) * 16
            if case == "ghost"
            else tuple(
                0.18 + 0.70 * abs(((index / 15.0) * 2.0) - 1.0)
                for index in range(16)
            )
        )
        peaks = (
            (0.92,) * 16
            if case == "ghost"
            else bars
        )
        resolved = type(
            "_ResolvedSpectrum",
            (),
            {
                "bars": bars,
                "peaks": peaks,
                "ghost_bars": peaks,
                "animation_time": 0.25,
            },
        )()
        playing = True
        source_generation = 2
        source_activation = 3
    logical = VisualizerLogicalFrame(
        runtime_generation=1,
        engine_generation=2,
        activation_id=3,
        source_generation=source_generation,
        source_activation_id=source_activation,
        mode_id="spectrum",
        playing=playing,
        logical_timestamp=1.0,
        source_timestamp=None,
        changed=True,
        present_frame=True,
        mode_reveal_ready=True,
        common=VisualizerCommonState(
            bars=tuple(resolved.bars),
            bar_count=16,
            style=freeze_render_fields(
                {
                    "fill_color": (18, 220, 92, 255),
                    "border_color": (245, 250, 255, 255),
                    "single_piece": True,
                    "border_radius": 4.0,
                }
            ),
        ),
        mode_state=SpectrumFrame(
            peaks=tuple(resolved.peaks),
            ghost_bars=tuple(resolved.ghost_bars),
            animation_time=float(resolved.animation_time),
            parameters=freeze_render_fields(
                {
                    "rainbow_enabled": False,
                    "rainbow_per_bar": False,
                    "spectrum_ghosting_enabled": case == "ghost",
                    "spectrum_ghost_alpha": 0.85,
                    "spectrum_glow_enabled": True,
                    "spectrum_glow_intensity": 0.55,
                    "spectrum_glow_color": (120, 255, 180, 255),
                }
            ),
        ),
    )
    return compose_visualizer_render_snapshot(
        logical,
        presentation,
        logical_revision=1,
    )


class _SpectrumSamplingNode(VisualizerRenderNode):
    def __init__(
        self,
        telemetry: VisualizerRenderNodeTelemetry,
        *,
        shared: _SharedProbe,
        window: QQuickWindow,
        case: str,
        presentation,
    ) -> None:
        super().__init__(telemetry)
        self._shared = shared
        self._window = window
        self._case = case
        self._presentation = presentation

    def render(self, state: QSGRenderNode.RenderState) -> None:
        super().render(state)
        telemetry = self.telemetry.snapshot()
        if telemetry.error is not None:
            self._shared.fail(telemetry.error)
            return
        if telemetry.draw_count < 1:
            return
        with self._shared.lock:
            if self._case in self._shared.captures:
                return
        try:
            target = self.renderTarget()
            if target is None:
                raise RuntimeError("Spectrum smoke has no render target")
            target_size = target.pixelSize()
            target_width = int(target_size.width())
            target_height = int(target_size.height())
            window_width = max(1.0, float(self._window.width()))
            window_height = max(1.0, float(self._window.height()))
            scale_x = target_width / window_width
            scale_y = target_height / window_height
            outer_x, outer_y, outer_width, outer_height = (
                self._presentation.outer_rect
            )
            pixel_x = max(0, round(outer_x * scale_x))
            pixel_y = max(
                0,
                target_height - round((outer_y + outer_height) * scale_y),
            )
            pixel_width = min(
                target_width - pixel_x,
                max(1, round(outer_width * scale_x)),
            )
            pixel_height = min(
                target_height - pixel_y,
                max(1, round(outer_height * scale_y)),
            )
            raw = bytes(
                gl.glReadPixels(
                    pixel_x,
                    pixel_y,
                    pixel_width,
                    pixel_height,
                    gl.GL_RGBA,
                    gl.GL_UNSIGNED_BYTE,
                )
            )
            expected = _BACKGROUND.getRgb()[:3]
            lit_points: list[tuple[int, int]] = []
            for row in range(pixel_height):
                for column in range(pixel_width):
                    offset = ((row * pixel_width) + column) * 4
                    red, green, blue = raw[offset : offset + 3]
                    if max(
                        abs(red - expected[0]),
                        abs(green - expected[1]),
                        abs(blue - expected[2]),
                    ) >= 20:
                        lit_points.append((column, row))
            columns = {column for column, _row in lit_points}
            rows = {row for _column, row in lit_points}
            capture = {
                "target_size": [target_width, target_height],
                "outer_pixel_size": [pixel_width, pixel_height],
                "lit_pixel_count": len(lit_points),
                "lit_column_count": len(columns),
                "lit_row_count": len(rows),
                "lit_bounds": (
                    None
                    if not lit_points
                    else [
                        min(columns),
                        min(rows),
                        max(columns),
                        max(rows),
                    ]
                ),
                "gl_error": int(gl.glGetError()),
            }
            self._shared.capture(self._case, capture)
        except Exception as exc:
            self._shared.fail(f"{type(exc).__name__}: {exc}")

    def releaseResources(self) -> None:
        self._shared.release_context_current = (
            QOpenGLContext.currentContext() is not None
        )
        super().releaseResources()


class _SpectrumItem(VisualizerRenderItem):
    def __init__(
        self,
        parent: QQuickItem,
        *,
        shared: _SharedProbe,
        window: QQuickWindow,
        telemetry: VisualizerRenderNodeTelemetry,
        case: str,
        presentation,
    ) -> None:
        self._spectrum_shared = shared
        self._spectrum_window = window
        self._spectrum_case = case
        self._spectrum_presentation = presentation
        super().__init__(parent, telemetry=telemetry)

    def _create_render_node(self) -> VisualizerRenderNode:
        return _SpectrumSamplingNode(
            self.telemetry,
            shared=self._spectrum_shared,
            window=self._spectrum_window,
            case=self._spectrum_case,
            presentation=self._spectrum_presentation,
        )


class _SpectrumRunner(QObject):
    def __init__(self, app: QGuiApplication, case: str) -> None:
        super().__init__()
        self._app = app
        self._case = case
        self._started_at = time.monotonic()
        self._shared = _SharedProbe(case)
        self._telemetry = VisualizerRenderNodeTelemetry()
        self._window = QQuickWindow()
        self._window.setColor(_BACKGROUND)
        self._window.resize(*_SPECTRUM_WINDOW_SIZE)
        self._window.setPersistentGraphics(False)
        self._window.setPersistentSceneGraph(False)
        extent, scale = _spectrum_case_geometry(case)
        self._presentation = resolve_visualizer_presentation(
            policy=get_visualizer_presentation_policy("spectrum"),
            display_size=_SPECTRUM_WINDOW_SIZE,
            outer_origin=_SPECTRUM_ORIGIN,
            viewport_extent=extent,
            uniform_visual_scale=scale,
            border_width=4.0,
            corner_radius=12.0,
            shadow_enabled=False,
        )
        outer_x, outer_y, outer_width, outer_height = (
            self._presentation.outer_rect
        )
        self._host = QQuickItem(self._window.contentItem())
        self._host.setX(outer_x)
        self._host.setY(outer_y)
        self._host.setWidth(outer_width)
        self._host.setHeight(outer_height)
        self._item = _SpectrumItem(
            self._host,
            shared=self._shared,
            window=self._window,
            telemetry=self._telemetry,
            case=case,
            presentation=self._presentation,
        )
        self._item.set_presentation(self._presentation)
        self._bridge = VisualizerSnapshotBridge()
        self._identity = VisualizerRenderIdentity(
            runtime_generation=1,
            engine_generation=2,
            activation_id=3,
            mode_id="spectrum",
        )
        self._bridge.begin_activation(
            runtime_generation=1,
            engine_generation=2,
            activation_id=3,
            mode_id="spectrum",
        )
        if not self._bridge.publish(
            _spectrum_snapshot(case, self._presentation)
        ):
            raise RuntimeError("Spectrum smoke snapshot was rejected")
        self._item.bind_render_source(self._bridge, self._identity)
        self._frame_swap_count = 0
        self._window.frameSwapped.connect(self._on_frame_swapped)
        self._closing = False

    def _on_frame_swapped(self) -> None:
        self._frame_swap_count += 1

    def start(self) -> None:
        self._window.show()
        self._window.update()
        QTimer.singleShot(20, self._poll)

    def _poll(self) -> None:
        captures, error = self._shared.snapshot()
        if error is not None:
            self._finish(valid=False, error=error)
            return
        if time.monotonic() - self._started_at > 8.0:
            self._finish(valid=False, error="Spectrum proof timed out")
            return
        if self._case not in captures or self._frame_swap_count < 1:
            QTimer.singleShot(20, self._poll)
            return
        if not self._closing:
            self._closing = True
            for method in ("hide", "releaseResources", "close"):
                QMetaObject.invokeMethod(
                    self._window,
                    method,
                    Qt.ConnectionType.QueuedConnection,
                )
            QTimer.singleShot(20, self._poll)
            return
        telemetry = self._telemetry.snapshot()
        if telemetry.invalidation_count < 1 or telemetry.release_count < 1:
            QTimer.singleShot(20, self._poll)
            return
        self._finish(valid=True, error=None)

    def _finish(self, *, valid: bool, error: str | None) -> None:
        captures, shared_error = self._shared.snapshot()
        telemetry = self._telemetry.snapshot()
        report = {
            "valid": bool(valid and shared_error is None),
            "error": error or shared_error,
            "case": self._case,
            "captures": captures,
            "telemetry": {
                "sync_count": telemetry.sync_count,
                "render_count": telemetry.render_count,
                "draw_count": telemetry.draw_count,
                "drawn_mode_id": telemetry.drawn_mode_id,
                "release_count": telemetry.release_count,
                "invalidation_count": telemetry.invalidation_count,
                "render_thread_id": telemetry.render_thread_id,
                "release_thread_id": telemetry.release_thread_id,
                "error": telemetry.error,
            },
            "release_context_current": self._shared.release_context_current,
        }
        print(json.dumps(report, sort_keys=True), flush=True)
        self._app.exit(0 if report["valid"] else 1)


class _Runner(QObject):
    def __init__(self, app: QGuiApplication, policy: str) -> None:
        super().__init__()
        self._app = app
        self._started_at = time.monotonic()
        self._policy = policy
        self._shared = _SharedProbe(policy)
        self._telemetry = VisualizerRenderNodeTelemetry()
        self._window = QQuickWindow()
        self._window.setColor(_BACKGROUND)
        self._window.resize(*_WINDOW_SIZE)
        self._window.setPersistentGraphics(False)
        self._window.setPersistentSceneGraph(False)
        self._frame_swap_count = 0
        self._window.frameSwapped.connect(self._on_frame_swapped)
        self._host = QQuickItem(self._window.contentItem())
        self._host.setX(_OUTER_RECT[0])
        self._host.setY(_OUTER_RECT[1])
        self._host.setWidth(_OUTER_RECT[2])
        self._host.setHeight(_OUTER_RECT[3])
        self._item = _ProbeItem(
            self._host,
            shared=self._shared,
            window=self._window,
            telemetry=self._telemetry,
        )
        self._closing = False

    def _on_frame_swapped(self) -> None:
        self._frame_swap_count += 1

    def start(self) -> None:
        self._apply_policy(self._policy)
        self._window.show()
        self._window.update()
        QTimer.singleShot(20, self._poll)

    def _apply_policy(self, policy: str) -> None:
        with self._shared.lock:
            self._shared.policy = policy
        if policy in {"rounded", "nested"}:
            presentation_policy = get_visualizer_presentation_policy("spectrum")
            border_width = 12.0
            corner_radius = 36.0
        else:
            presentation_policy = VisualizerModePresentationPolicy(
                shell_policy=VisualizerShellPolicy.FRAMELESS,
                clip_policy=VisualizerClipPolicy.VIEWPORT_RECT,
                viewport_resize_capable=True,
            )
            border_width = 0.0
            corner_radius = 0.0
        presentation = resolve_visualizer_presentation(
            policy=presentation_policy,
            display_size=_WINDOW_SIZE,
            outer_origin=_OUTER_RECT[:2],
            viewport_extent=_OUTER_RECT[2:],
            border_width=border_width,
            corner_radius=corner_radius,
            shadow_enabled=False,
        )
        self._item.set_presentation(presentation)
        self._item.update()
        self._window.update()

    def _poll(self) -> None:
        captures, error = self._shared.snapshot()
        if error is not None:
            self._finish(valid=False, error=error)
            return
        if time.monotonic() - self._started_at > 8.0:
            self._finish(valid=False, error="clip proof timed out")
            return
        if self._policy not in captures:
            QTimer.singleShot(20, self._poll)
            return
        if self._frame_swap_count < 1:
            QTimer.singleShot(20, self._poll)
            return
        if not self._closing:
            self._closing = True
            for method in ("hide", "releaseResources", "close"):
                QMetaObject.invokeMethod(
                    self._window,
                    method,
                    Qt.ConnectionType.QueuedConnection,
                )
            QTimer.singleShot(20, self._poll)
            return
        telemetry = self._telemetry.snapshot()
        if telemetry.invalidation_count < 1 or telemetry.release_count < 1:
            QTimer.singleShot(20, self._poll)
            return
        self._finish(valid=True, error=None)

    def _finish(self, *, valid: bool, error: str | None) -> None:
        captures, shared_error = self._shared.snapshot()
        telemetry = self._telemetry.snapshot()
        report = {
            "valid": bool(valid and shared_error is None),
            "error": error or shared_error,
            "gui_thread_id": threading.get_ident(),
            "background_rgb": list(_BACKGROUND.getRgb()[:3]),
            "draw_rgb": list(_DRAW_COLOR),
            "policy": self._policy,
            "captures": captures,
            "telemetry": {
                "sync_count": telemetry.sync_count,
                "render_count": telemetry.render_count,
                "release_count": telemetry.release_count,
                "invalidation_count": telemetry.invalidation_count,
                "render_thread_id": telemetry.render_thread_id,
                "release_thread_id": telemetry.release_thread_id,
                "error": telemetry.error,
            },
            "release_context_current": self._shared.release_context_current,
        }
        print(json.dumps(report, sort_keys=True), flush=True)
        self._app.exit(0 if report["valid"] else 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        choices=("rounded", "rect", "nested", "spectrum"),
        required=True,
    )
    parser.add_argument(
        "--spectrum-case",
        choices=("canonical", "scaled", "wide", "tall", "idle", "ghost"),
        default="canonical",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    configure_quick_graphics(reason="visualizer-clip-smoke")
    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("SRPSSQuickVisualizerClipSmoke")
    app.setQuitOnLastWindowClosed(False)
    if QQuickWindow.graphicsApi() != QSGRendererInterface.GraphicsApi.OpenGL:
        print(json.dumps({"valid": False, "error": "Quick is not using OpenGL"}))
        return 1
    runner = (
        _SpectrumRunner(app, args.spectrum_case)
        if args.policy == "spectrum"
        else _Runner(app, args.policy)
    )
    QTimer.singleShot(0, runner.start)
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
