"""Single render-node-local clip path for inline visualizer GL.

PySide 6.9.1 does not provide a reliable scene-graph clip-node to Python
render-node state handoff on the pinned Windows/OpenGL runtime. This host
therefore owns the one admitted fallback: a rounded-rectangle SDF writes a
temporary nested stencil value, mode GL draws against it, and the host redraws
the same mask to restore the inherited stencil contents before returning to Qt.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass

from OpenGL import GL as gl
from PySide6.QtGui import QOpenGLContext
from PySide6.QtQuick import QSGRenderNode

from rendering.quick.render.gl_resources import compile_program
from widgets.spotify_visualizer.render_state import ResolvedVisualizerPresentation


_VERTEX_SOURCE = """#version 410 core
layout(location = 0) in vec2 aPosition;
uniform mat4 uMatrix;
uniform vec2 uItemSize;
out vec2 vLocalPosition;
void main() {
    vLocalPosition = aPosition * uItemSize;
    gl_Position = uMatrix * vec4(vLocalPosition, 0.0, 1.0);
}
"""

_FRAGMENT_SOURCE = """#version 410 core
in vec2 vLocalPosition;
uniform vec4 uClipRect;
uniform float uRadius;
out vec4 fragColor;
void main() {
    vec2 halfSize = uClipRect.zw * 0.5;
    vec2 center = uClipRect.xy + halfSize;
    float radius = min(uRadius, min(halfSize.x, halfSize.y));
    vec2 q = abs(vLocalPosition - center) - (halfSize - vec2(radius));
    float distanceToEdge = length(max(q, vec2(0.0)))
        + min(max(q.x, q.y), 0.0) - radius;
    if (distanceToEdge > 0.0)
        discard;
    fragColor = vec4(0.0);
}
"""


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


@dataclass(frozen=True, slots=True)
class VisualizerClipFrame:
    logical_size: tuple[float, float]
    local_content_rect: tuple[float, float, float, float]
    inner_corner_radius: float
    matrix_values: tuple[float, ...]
    viewport: tuple[int, int, int, int]

    @classmethod
    def from_presentation(
        cls,
        presentation: ResolvedVisualizerPresentation,
        *,
        matrix_values: tuple[float, ...],
        viewport: tuple[int, int, int, int],
    ) -> "VisualizerClipFrame":
        outer_x, outer_y, outer_width, outer_height = presentation.outer_rect
        content_x, content_y, content_width, content_height = (
            presentation.content_rect
        )
        if len(matrix_values) != 16:
            raise ValueError("visualizer clip matrix must contain 16 values")
        if len(viewport) != 4 or viewport[2] <= 0 or viewport[3] <= 0:
            raise ValueError("visualizer clip viewport must have positive extent")
        return cls(
            logical_size=(outer_width, outer_height),
            local_content_rect=(
                content_x - outer_x,
                content_y - outer_y,
                content_width,
                content_height,
            ),
            inner_corner_radius=float(
                presentation.shell_style.get("inner_corner_radius", 0.0)
            ),
            matrix_values=tuple(float(value) for value in matrix_values),
            viewport=tuple(int(value) for value in viewport),
        )


@dataclass(frozen=True, slots=True)
class _InheritedClipState:
    scissor_enabled: bool
    scissor_box: tuple[int, int, int, int]
    stencil_enabled: bool
    stencil_func: int
    stencil_ref: int
    stencil_value_mask: int
    stencil_write_mask: int
    stencil_fail: int
    stencil_depth_fail: int
    stencil_depth_pass: int
    stencil_back_func: int
    stencil_back_ref: int
    stencil_back_value_mask: int
    stencil_back_write_mask: int
    stencil_back_fail: int
    stencil_back_depth_fail: int
    stencil_back_depth_pass: int

    @classmethod
    def capture(cls) -> "_InheritedClipState":
        return cls(
            scissor_enabled=bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST)),
            scissor_box=tuple(
                int(value) for value in gl.glGetIntegerv(gl.GL_SCISSOR_BOX)
            ),
            stencil_enabled=bool(gl.glIsEnabled(gl.GL_STENCIL_TEST)),
            stencil_func=_int_state(gl.GL_STENCIL_FUNC),
            stencil_ref=_int_state(gl.GL_STENCIL_REF),
            stencil_value_mask=_int_state(gl.GL_STENCIL_VALUE_MASK),
            stencil_write_mask=_int_state(gl.GL_STENCIL_WRITEMASK),
            stencil_fail=_int_state(gl.GL_STENCIL_FAIL),
            stencil_depth_fail=_int_state(gl.GL_STENCIL_PASS_DEPTH_FAIL),
            stencil_depth_pass=_int_state(gl.GL_STENCIL_PASS_DEPTH_PASS),
            stencil_back_func=_int_state(gl.GL_STENCIL_BACK_FUNC),
            stencil_back_ref=_int_state(gl.GL_STENCIL_BACK_REF),
            stencil_back_value_mask=_int_state(gl.GL_STENCIL_BACK_VALUE_MASK),
            stencil_back_write_mask=_int_state(gl.GL_STENCIL_BACK_WRITEMASK),
            stencil_back_fail=_int_state(gl.GL_STENCIL_BACK_FAIL),
            stencil_back_depth_fail=_int_state(
                gl.GL_STENCIL_BACK_PASS_DEPTH_FAIL
            ),
            stencil_back_depth_pass=_int_state(
                gl.GL_STENCIL_BACK_PASS_DEPTH_PASS
            ),
        )

    def restore(self) -> None:
        gl.glScissor(*self.scissor_box)
        _set_enabled(gl.GL_SCISSOR_TEST, self.scissor_enabled)
        gl.glStencilFuncSeparate(
            gl.GL_FRONT,
            self.stencil_func,
            self.stencil_ref,
            self.stencil_value_mask,
        )
        gl.glStencilFuncSeparate(
            gl.GL_BACK,
            self.stencil_back_func,
            self.stencil_back_ref,
            self.stencil_back_value_mask,
        )
        gl.glStencilOpSeparate(
            gl.GL_FRONT,
            self.stencil_fail,
            self.stencil_depth_fail,
            self.stencil_depth_pass,
        )
        gl.glStencilOpSeparate(
            gl.GL_BACK,
            self.stencil_back_fail,
            self.stencil_back_depth_fail,
            self.stencil_back_depth_pass,
        )
        gl.glStencilMaskSeparate(gl.GL_FRONT, self.stencil_write_mask)
        gl.glStencilMaskSeparate(gl.GL_BACK, self.stencil_back_write_mask)
        _set_enabled(gl.GL_STENCIL_TEST, self.stencil_enabled)


@dataclass(frozen=True, slots=True)
class VisualizerClipRun:
    frame: VisualizerClipFrame
    inherited: _InheritedClipState
    base_stencil_value: int
    local_stencil_value: int
    stencil_mask: int
    incoming_scissor: tuple[int, int, int, int] | None


class VisualizerClipHost:
    """Own and restore one temporary SDF/stencil clip around a mode draw."""

    def __init__(self) -> None:
        self._program = 0
        self._vao = 0
        self._vbo = 0
        self._matrix_location = -1
        self._item_size_location = -1
        self._clip_rect_location = -1
        self._radius_location = -1
        self._active_run: VisualizerClipRun | None = None

    @property
    def has_resources(self) -> bool:
        return bool(self._program or self._vao or self._vbo)

    def begin(
        self,
        frame: VisualizerClipFrame,
        render_state: QSGRenderNode.RenderState,
    ) -> VisualizerClipRun:
        if self._active_run is not None:
            raise RuntimeError("visualizer clip host is already active")
        self._ensure_resources()
        inherited = _InheritedClipState.capture()
        run: VisualizerClipRun | None = None
        try:
            incoming_scissor = self._apply_incoming_scissor(render_state)
            context = QOpenGLContext.currentContext()
            if context is None:
                raise RuntimeError("visualizer clip has no current GL context")
            stencil_bits = int(context.format().stencilBufferSize())
            if stencil_bits <= 0:
                raise RuntimeError("Quick render target has no stencil attachment")
            stencil_mask = (1 << min(stencil_bits, 8)) - 1
            base_value = (
                int(render_state.stencilValue())
                if render_state.stencilEnabled()
                else 0
            )
            local_value = base_value + 1
            if local_value > stencil_mask:
                raise RuntimeError("incoming Quick stencil nesting is exhausted")
            run = VisualizerClipRun(
                frame=frame,
                inherited=inherited,
                base_stencil_value=base_value,
                local_stencil_value=local_value,
                stencil_mask=stencil_mask,
                incoming_scissor=incoming_scissor,
            )
            self._active_run = run

            gl.glEnable(gl.GL_STENCIL_TEST)
            gl.glStencilMask(stencil_mask)
            gl.glStencilFunc(gl.GL_EQUAL, base_value, stencil_mask)
            gl.glStencilOp(gl.GL_KEEP, gl.GL_KEEP, gl.GL_INCR)
            self._draw_mask(frame)

            gl.glStencilMask(0x00)
            gl.glStencilFunc(gl.GL_EQUAL, local_value, stencil_mask)
            gl.glStencilOp(gl.GL_KEEP, gl.GL_KEEP, gl.GL_KEEP)
            return run
        except Exception as exc:
            if run is None:
                inherited.restore()
            else:
                try:
                    self.end(run)
                except Exception as cleanup_exc:
                    raise RuntimeError(
                        "visualizer clip setup and stencil rollback both failed: "
                        f"{type(cleanup_exc).__name__}: {cleanup_exc}"
                    ) from exc
            raise

    def end(self, run: VisualizerClipRun) -> None:
        if run is not self._active_run:
            raise RuntimeError("visualizer clip run is not current")
        try:
            self._apply_resolved_scissor(run.incoming_scissor)
            gl.glEnable(gl.GL_STENCIL_TEST)
            gl.glStencilMask(run.stencil_mask)
            gl.glStencilFunc(
                gl.GL_EQUAL,
                run.local_stencil_value,
                run.stencil_mask,
            )
            gl.glStencilOp(gl.GL_KEEP, gl.GL_KEEP, gl.GL_DECR)
            self._draw_mask(run.frame)
        finally:
            self._active_run = None
            run.inherited.restore()

    def release_resources(self) -> None:
        if not self.has_resources:
            return
        if self._active_run is not None:
            raise RuntimeError("cannot release an active visualizer clip run")
        if QOpenGLContext.currentContext() is None:
            raise RuntimeError(
                "visualizer clip resources released without a current GL context"
            )
        if self._program:
            gl.glDeleteProgram(self._program)
        if self._vbo:
            gl.glDeleteBuffers(1, [self._vbo])
        if self._vao:
            gl.glDeleteVertexArrays(1, [self._vao])
        self._program = 0
        self._vbo = 0
        self._vao = 0

    @staticmethod
    def _apply_incoming_scissor(
        render_state: QSGRenderNode.RenderState,
    ) -> tuple[int, int, int, int] | None:
        if not render_state.scissorEnabled():
            gl.glDisable(gl.GL_SCISSOR_TEST)
            return None
        rect = render_state.scissorRect()
        values = tuple(int(value) for value in rect.getRect())
        if values[0] < 0 or values[1] < 0 or values[2] <= 0 or values[3] <= 0:
            inherited_enabled = bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
            inherited_box = tuple(
                int(value) for value in gl.glGetIntegerv(gl.GL_SCISSOR_BOX)
            )
            raise RuntimeError(
                "incoming Quick scissor is unusable: "
                f"{values}; inherited={inherited_enabled}:{inherited_box}"
            )
        gl.glEnable(gl.GL_SCISSOR_TEST)
        gl.glScissor(*values)
        return values

    @staticmethod
    def _apply_resolved_scissor(
        scissor: tuple[int, int, int, int] | None,
    ) -> None:
        if scissor is None:
            gl.glDisable(gl.GL_SCISSOR_TEST)
            return
        gl.glEnable(gl.GL_SCISSOR_TEST)
        gl.glScissor(*scissor)

    def _ensure_resources(self) -> None:
        if self._program:
            return
        if QOpenGLContext.currentContext() is None:
            raise RuntimeError("visualizer clip initialized without a current GL context")
        prior_vao = _int_state(gl.GL_VERTEX_ARRAY_BINDING)
        prior_array_buffer = _int_state(gl.GL_ARRAY_BUFFER_BINDING)
        try:
            self._program = compile_program(
                _VERTEX_SOURCE,
                _FRAGMENT_SOURCE,
                label="Quick visualizer clip",
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
            self._matrix_location = int(
                gl.glGetUniformLocation(self._program, "uMatrix")
            )
            self._item_size_location = int(
                gl.glGetUniformLocation(self._program, "uItemSize")
            )
            self._clip_rect_location = int(
                gl.glGetUniformLocation(self._program, "uClipRect")
            )
            self._radius_location = int(
                gl.glGetUniformLocation(self._program, "uRadius")
            )
            if min(
                self._matrix_location,
                self._item_size_location,
                self._clip_rect_location,
                self._radius_location,
            ) < 0:
                raise RuntimeError("visualizer clip uniforms are incomplete")
        except Exception:
            if self._program:
                gl.glDeleteProgram(self._program)
            if self._vbo:
                gl.glDeleteBuffers(1, [self._vbo])
            if self._vao:
                gl.glDeleteVertexArrays(1, [self._vao])
            self._program = 0
            self._vbo = 0
            self._vao = 0
            raise
        finally:
            gl.glBindVertexArray(prior_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, prior_array_buffer)

    def _draw_mask(self, frame: VisualizerClipFrame) -> None:
        prior_viewport = tuple(
            int(value) for value in gl.glGetIntegerv(gl.GL_VIEWPORT)
        )
        prior_program = _int_state(gl.GL_CURRENT_PROGRAM)
        prior_vao = _int_state(gl.GL_VERTEX_ARRAY_BINDING)
        prior_array_buffer = _int_state(gl.GL_ARRAY_BUFFER_BINDING)
        prior_blend = bool(gl.glIsEnabled(gl.GL_BLEND))
        prior_cull = bool(gl.glIsEnabled(gl.GL_CULL_FACE))
        prior_depth = bool(gl.glIsEnabled(gl.GL_DEPTH_TEST))
        prior_depth_mask = _bool_state(gl.GL_DEPTH_WRITEMASK)
        prior_color_mask = tuple(
            bool(value) for value in gl.glGetBooleanv(gl.GL_COLOR_WRITEMASK)
        )
        try:
            gl.glDisable(gl.GL_BLEND)
            gl.glDisable(gl.GL_CULL_FACE)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glDepthMask(gl.GL_FALSE)
            gl.glColorMask(gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE)
            gl.glViewport(*frame.viewport)
            gl.glUseProgram(self._program)
            gl.glBindVertexArray(self._vao)
            gl.glUniformMatrix4fv(
                self._matrix_location,
                1,
                gl.GL_FALSE,
                frame.matrix_values,
            )
            gl.glUniform2f(self._item_size_location, *frame.logical_size)
            gl.glUniform4f(self._clip_rect_location, *frame.local_content_rect)
            gl.glUniform1f(self._radius_location, frame.inner_corner_radius)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        finally:
            gl.glViewport(*prior_viewport)
            gl.glBindVertexArray(prior_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, prior_array_buffer)
            gl.glUseProgram(prior_program)
            gl.glDepthMask(gl.GL_TRUE if prior_depth_mask else gl.GL_FALSE)
            gl.glColorMask(*prior_color_mask)
            _set_enabled(gl.GL_BLEND, prior_blend)
            _set_enabled(gl.GL_CULL_FACE, prior_cull)
            _set_enabled(gl.GL_DEPTH_TEST, prior_depth)


__all__ = [
    "VisualizerClipFrame",
    "VisualizerClipHost",
    "VisualizerClipRun",
]
