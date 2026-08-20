"""Inline OpenGL background node for the display's sole Quick scene."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import threading

from OpenGL import GL as gl
from PySide6.QtCore import QRectF
from PySide6.QtGui import QOpenGLContext
from PySide6.QtQuick import QSGRenderNode

from core.logging.logger import get_logger
from .gl_resources import compile_program
from .telemetry import RenderNodeTelemetry


logger = get_logger(__name__)


_VERTEX_SOURCE = """#version 410 core
layout(location = 0) in vec2 aPosition;

uniform mat4 uMatrix;
uniform vec2 uItemSize;

out vec2 vUv;

void main() {
    vUv = aPosition;
    gl_Position = uMatrix * vec4(aPosition * uItemSize, 0.0, 1.0);
}
"""


_FRAGMENT_SOURCE = """#version 410 core
in vec2 vUv;
out vec4 fragColor;

uniform float uProgress;

vec3 oldPalette(float band) {
    if (band < 1.0) return vec3(0.055, 0.180, 0.420);
    if (band < 2.0) return vec3(0.070, 0.340, 0.620);
    if (band < 3.0) return vec3(0.090, 0.520, 0.710);
    if (band < 4.0) return vec3(0.170, 0.650, 0.620);
    if (band < 5.0) return vec3(0.360, 0.720, 0.500);
    return vec3(0.620, 0.760, 0.340);
}

vec3 newPalette(float band) {
    if (band < 1.0) return vec3(0.950, 0.310, 0.190);
    if (band < 2.0) return vec3(0.950, 0.500, 0.160);
    if (band < 3.0) return vec3(0.930, 0.690, 0.170);
    if (band < 4.0) return vec3(0.760, 0.760, 0.200);
    if (band < 5.0) return vec3(0.620, 0.610, 0.260);
    return vec3(0.780, 0.390, 0.300);
}

void main() {
    float progress = clamp(uProgress, 0.0, 1.0);
    bool newRegion = vUv.x < progress;
    float sourceX = newRegion
        ? vUv.x + (1.0 - progress)
        : vUv.x - progress;
    float band = floor(clamp(sourceX, 0.0, 0.9999) * 6.0);
    vec3 color = newRegion ? newPalette(band) : oldPalette(band);

    float accent = step(0.485, vUv.y) * step(vUv.y, 0.515);
    color = mix(color, vec3(0.96), accent * 0.75);
    fragColor = vec4(color, 1.0);
}
"""


@dataclass(frozen=True)
class SlideProofState:
    """Immutable deterministic content synchronized into the render node."""

    progress: float = 0.35

    def normalized(self) -> "SlideProofState":
        return SlideProofState(progress=max(0.0, min(1.0, float(self.progress))))


def _gl_string(name: int) -> str:
    value = gl.glGetString(name)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _int_state(name: int) -> int:
    value = gl.glGetIntegerv(name)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(value[0])


def _set_enabled(capability: int, enabled: bool) -> None:
    if enabled:
        gl.glEnable(capability)
    else:
        gl.glDisable(capability)


def _pixel_hex(value: object) -> str:
    raw = bytes(value)
    if len(raw) < 4:
        raise RuntimeError(f"incomplete GL pixel sample: {len(raw)} bytes")
    return f"#{raw[3]:02x}{raw[0]:02x}{raw[1]:02x}{raw[2]:02x}"


class BackgroundRenderNode(QSGRenderNode):
    """Render-thread GL resource owner for the full-screen background item."""

    def __init__(self, telemetry: RenderNodeTelemetry | None = None) -> None:
        super().__init__()
        self._telemetry = telemetry or RenderNodeTelemetry()
        self._logical_size = (0.0, 0.0)
        self._device_pixel_ratio = 1.0
        self._state = SlideProofState()
        self._program = 0
        self._vao = 0
        self._vbo = 0
        self._matrix_location = -1
        self._item_size_location = -1
        self._progress_location = -1

    def __del__(self) -> None:
        # Some scene-graph backends may skip the virtual releaseResources()
        # callback. Qt guarantees a current GL context while destroying a
        # render node; the explicit invalidation owner normally makes this a
        # no-op and this remains the required final safety net.
        try:
            self.releaseResources()
        except Exception:
            return

    def synchronize(
        self,
        *,
        logical_size: tuple[float, float],
        device_pixel_ratio: float,
        state: SlideProofState,
    ) -> None:
        """Accept immutable values during the Quick sync/updatePaintNode phase."""

        self._logical_size = (
            max(0.0, float(logical_size[0])),
            max(0.0, float(logical_size[1])),
        )
        self._device_pixel_ratio = max(0.01, float(device_pixel_ratio))
        self._state = state.normalized()
        self._telemetry.note_sync(
            logical_size=self._logical_size,
            device_pixel_ratio=self._device_pixel_ratio,
        )

    def rect(self) -> QRectF:
        return QRectF(0.0, 0.0, *self._logical_size)

    def flags(self) -> QSGRenderNode.RenderingFlag:
        return (
            QSGRenderNode.RenderingFlag.BoundedRectRendering
            | QSGRenderNode.RenderingFlag.OpaqueRendering
        )

    def changedStates(self) -> QSGRenderNode.StateFlag:
        return (
            QSGRenderNode.StateFlag.BlendState
            | QSGRenderNode.StateFlag.CullState
            | QSGRenderNode.StateFlag.DepthState
            | QSGRenderNode.StateFlag.StencilState
        )

    def render(self, _state: QSGRenderNode.RenderState) -> None:
        try:
            if self._logical_size[0] <= 0.0 or self._logical_size[1] <= 0.0:
                return
            if not self._program:
                self._initialize_gl()
            self._draw()
        except Exception as exc:
            self._telemetry.note_error(f"{type(exc).__name__}: {exc}")
            logger.exception("[QUICK] Background render node failed: %s", exc)

    def releaseResources(self) -> None:
        """Delete node-owned GL names on Qt Quick's legal render/context owner."""

        if not (self._program or self._vao or self._vbo):
            return
        context = QOpenGLContext.currentContext()
        if context is None:
            error = "Quick background resources released without a current GL context"
            self._telemetry.note_error(error)
            logger.error("[QUICK] %s", error)
            return

        try:
            if self._program:
                gl.glDeleteProgram(self._program)
            if self._vbo:
                gl.glDeleteBuffers(1, [self._vbo])
            if self._vao:
                gl.glDeleteVertexArrays(1, [self._vao])
            self._program = 0
            self._vbo = 0
            self._vao = 0
            self._telemetry.note_released(release_thread_id=threading.get_ident())
        except Exception as exc:
            self._telemetry.note_error(
                f"resource release failed: {type(exc).__name__}: {exc}"
            )
            logger.exception("[QUICK] Background render resource release failed: %s", exc)

    def _initialize_gl(self) -> None:
        context = QOpenGLContext.currentContext()
        if context is None:
            raise RuntimeError("QSGRenderNode has no current OpenGL context")

        self._program = compile_program(
            _VERTEX_SOURCE,
            _FRAGMENT_SOURCE,
            label="Quick Slide proof",
        )
        vertices = (ctypes.c_float * 8)(
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
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
        self._item_size_location = int(
            gl.glGetUniformLocation(self._program, "uItemSize")
        )
        self._progress_location = int(
            gl.glGetUniformLocation(self._program, "uProgress")
        )
        if min(
            self._matrix_location,
            self._item_size_location,
            self._progress_location,
        ) < 0:
            raise RuntimeError("Quick Slide proof uniforms are incomplete")

        self._telemetry.note_initialized(
            render_thread_id=threading.get_ident(),
            gl_version=_gl_string(gl.GL_VERSION),
        )

    def _draw(self) -> None:
        prior_viewport_value = gl.glGetIntegerv(gl.GL_VIEWPORT)
        prior_viewport = tuple(int(value) for value in prior_viewport_value)
        if len(prior_viewport) != 4:
            raise RuntimeError(f"invalid inherited Quick GL viewport: {prior_viewport}")
        render_target = self.renderTarget()
        if render_target is None:
            raise RuntimeError("Quick render node has no active render target")
        target_size = render_target.pixelSize()
        render_target_size = (int(target_size.width()), int(target_size.height()))
        if render_target_size[0] <= 0 or render_target_size[1] <= 0:
            raise RuntimeError(
                f"Quick render node has invalid render target: {render_target_size}"
            )
        viewport = (0, 0, *render_target_size)

        prior_program = _int_state(gl.GL_CURRENT_PROGRAM)
        prior_vao = _int_state(gl.GL_VERTEX_ARRAY_BINDING)
        prior_array_buffer = _int_state(gl.GL_ARRAY_BUFFER_BINDING)
        prior_blend = bool(gl.glIsEnabled(gl.GL_BLEND))
        prior_cull = bool(gl.glIsEnabled(gl.GL_CULL_FACE))
        prior_depth = bool(gl.glIsEnabled(gl.GL_DEPTH_TEST))
        prior_stencil = bool(gl.glIsEnabled(gl.GL_STENCIL_TEST))

        try:
            gl.glDisable(gl.GL_BLEND)
            gl.glDisable(gl.GL_CULL_FACE)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glDisable(gl.GL_STENCIL_TEST)
            gl.glViewport(*viewport)
            gl.glUseProgram(self._program)
            gl.glBindVertexArray(self._vao)

            matrix = self.projectionMatrix() * self.matrix()
            gl.glUniformMatrix4fv(
                self._matrix_location,
                1,
                gl.GL_FALSE,
                list(matrix.data()),
            )
            gl.glUniform2f(
                self._item_size_location,
                float(self._logical_size[0]),
                float(self._logical_size[1]),
            )
            gl.glUniform1f(self._progress_location, float(self._state.progress))
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            if self._telemetry.wants_pixel_sample():
                physical_width = max(
                    1,
                    round(self._logical_size[0] * self._device_pixel_ratio),
                )
                physical_height = max(
                    1,
                    round(self._logical_size[1] * self._device_pixel_ratio),
                )
                sample_y = viewport[1] + max(0, physical_height // 4)
                sample_xs = (
                    viewport[0] + max(0, physical_width // 12),
                    viewport[0] + max(0, physical_width // 4),
                    viewport[0] + max(0, physical_width // 2),
                    viewport[0] + max(0, (physical_width * 3) // 4),
                    viewport[0] + max(0, (physical_width * 11) // 12),
                )
                colors = tuple(
                    _pixel_hex(
                        gl.glReadPixels(
                            min(viewport[0] + viewport[2] - 1, sample_x),
                            min(viewport[1] + viewport[3] - 1, sample_y),
                            1,
                            1,
                            gl.GL_RGBA,
                            gl.GL_UNSIGNED_BYTE,
                        )
                    )
                    for sample_x in sample_xs
                )
                self._telemetry.note_pixel_sample(colors)
        finally:
            gl.glBindVertexArray(prior_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, prior_array_buffer)
            gl.glUseProgram(prior_program)
            gl.glViewport(*prior_viewport)
            _set_enabled(gl.GL_BLEND, prior_blend)
            _set_enabled(gl.GL_CULL_FACE, prior_cull)
            _set_enabled(gl.GL_DEPTH_TEST, prior_depth)
            _set_enabled(gl.GL_STENCIL_TEST, prior_stencil)

        self._telemetry.note_render(
            render_thread_id=threading.get_ident(),
            viewport=viewport,
            render_target_size=render_target_size,
        )
