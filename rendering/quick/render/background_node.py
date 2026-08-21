"""Inline OpenGL background node for the display's sole Quick scene."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import threading
import time

from OpenGL import GL as gl
from PySide6.QtCore import QRectF
from PySide6.QtGui import QOpenGLContext
from PySide6.QtQuick import QSGRenderNode

from core.logging.logger import get_logger
from ..image_state import PresentationImage
from ..transitions.render_contract import QuickTransitionRenderFrame
from ..transitions.render_host import QuickTransitionRenderHost
from ..transitions.state import TransitionRun, TransitionSample
from .gl_resources import compile_program
from .image_textures import PresentationTextureHost
from .telemetry import RenderNodeTelemetry


logger = get_logger(__name__)


# Diagnostic pixel-readback grids, used only when telemetry pixel capture is
# enabled (tests/harnesses); capture_pixels defaults to False so there is no
# production cost. The sparse 5x5 grid is the long-standing shared grid that the
# geometry-precise transition oracles (slide/wipe/warp/block_flip/block_spins)
# are tuned to; it must not change. The dense grid is an ADDITIONAL midpoint-only
# readback that reliably samples thin authored effect regions (burn fire front,
# crumble cracks, particle displacement) so the Phase-C effect oracles are not
# decided by sampling luck. The smoke harness mirrors both constants so its
# sample coordinates stay in lock-step with the readback.
TRANSITION_DENSE_SAMPLE_AXIS_COUNT = 15


def transition_sample_offsets(extent: int) -> tuple[int, ...]:
    """The original shared 5-point-per-axis diagnostic offsets."""

    return (
        max(0, extent // 12),
        max(0, extent // 4),
        max(0, extent // 2),
        max(0, (extent * 3) // 4),
        max(0, (extent * 11) // 12),
    )


def transition_dense_sample_offsets(extent: int) -> tuple[int, ...]:
    """Evenly spaced dense pixel offsets across ``extent`` (effect oracles)."""

    limit = max(0, int(extent) - 1)
    return tuple(
        min(limit, max(0, round((index + 0.5) / TRANSITION_DENSE_SAMPLE_AXIS_COUNT * extent)))
        for index in range(TRANSITION_DENSE_SAMPLE_AXIS_COUNT)
    )


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
uniform bool uHasImage;
uniform sampler2D uImage;

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
    if (uHasImage) {
        fragColor = texture(uImage, vUv);
        return;
    }
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
        self._presentation_image: PresentationImage | None = None
        self._transition_run: TransitionRun | None = None
        self._image_textures = PresentationTextureHost(self._telemetry)
        self._transition_renderer = QuickTransitionRenderHost()
        self._program = 0
        self._vao = 0
        self._vbo = 0
        self._matrix_location = -1
        self._item_size_location = -1
        self._progress_location = -1
        self._has_image_location = -1
        self._image_location = -1

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
        presentation_image: PresentationImage | None,
        transition_run: TransitionRun | None,
    ) -> None:
        """Accept immutable values during the Quick sync/updatePaintNode phase."""

        self._logical_size = (
            max(0.0, float(logical_size[0])),
            max(0.0, float(logical_size[1])),
        )
        self._device_pixel_ratio = max(0.01, float(device_pixel_ratio))
        self._state = state.normalized()
        self._presentation_image = presentation_image
        self._transition_run = transition_run
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
            run = self._transition_run
            sample = None
            if run is not None:
                sample = run.sample(time.monotonic_ns())
                self._telemetry.note_transition_sample(
                    run=run,
                    sample=sample,
                )
            self._draw(run=run, sample=sample)
        except Exception as exc:
            self._telemetry.note_error(f"{type(exc).__name__}: {exc}")
            logger.exception("[QUICK] Background render node failed: %s", exc)

    def releaseResources(self) -> None:
        """Delete node-owned GL names on Qt Quick's legal render/context owner."""

        if not (
            self._program
            or self._vao
            or self._vbo
            or self._image_textures.has_resources
            or self._transition_renderer.has_resources
        ):
            return
        context = QOpenGLContext.currentContext()
        if context is None:
            error = "Quick background resources released without a current GL context"
            self._telemetry.note_error(error)
            logger.error("[QUICK] %s", error)
            return

        try:
            self._transition_renderer.release_resources()
            self._image_textures.release()
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
        self._has_image_location = int(
            gl.glGetUniformLocation(self._program, "uHasImage")
        )
        self._image_location = int(
            gl.glGetUniformLocation(self._program, "uImage")
        )
        if min(
            self._matrix_location,
            self._item_size_location,
            self._progress_location,
            self._has_image_location,
            self._image_location,
        ) < 0:
            raise RuntimeError("Quick background uniforms are incomplete")

        self._telemetry.note_initialized(
            render_thread_id=threading.get_ident(),
            gl_version=_gl_string(gl.GL_VERSION),
        )

    def _draw(
        self,
        *,
        run: TransitionRun | None,
        sample: TransitionSample | None,
    ) -> None:
        textures = self._image_textures.synchronize(
            self._presentation_image,
            run,
        )
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
        matrix = self.projectionMatrix() * self.matrix()
        matrix_values = tuple(float(value) for value in matrix.data())

        if run is not None:
            if sample is None or not textures.has_transition_pair:
                raise RuntimeError("Quick transition render state is incomplete")
            renderer_id = self._transition_renderer.render(
                QuickTransitionRenderFrame(
                    run=run,
                    sample=sample,
                    viewport=viewport,
                    logical_size=self._logical_size,
                    matrix_values=matrix_values,
                    quad_vao=self._vao,
                    source_texture_id=textures.source_texture_id,
                    destination_texture_id=textures.destination_texture_id,
                )
            )
            self._telemetry.note_transition_drawn(transition_id=renderer_id)
        else:
            self._draw_base(
                texture_id=textures.base_texture_id,
                viewport=viewport,
                matrix_values=matrix_values,
            )

        self._sample_pixels(viewport, sample=sample)
        self._telemetry.note_render(
            render_thread_id=threading.get_ident(),
            viewport=viewport,
            render_target_size=render_target_size,
        )

    def _draw_base(
        self,
        *,
        texture_id: int,
        viewport: tuple[int, int, int, int],
        matrix_values: tuple[float, ...],
    ) -> None:
        prior_viewport_value = gl.glGetIntegerv(gl.GL_VIEWPORT)
        prior_viewport = tuple(int(value) for value in prior_viewport_value)
        if len(prior_viewport) != 4:
            raise RuntimeError(f"invalid inherited Quick GL viewport: {prior_viewport}")

        prior_program = _int_state(gl.GL_CURRENT_PROGRAM)
        prior_vao = _int_state(gl.GL_VERTEX_ARRAY_BINDING)
        prior_array_buffer = _int_state(gl.GL_ARRAY_BUFFER_BINDING)
        prior_active_texture = _int_state(gl.GL_ACTIVE_TEXTURE)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        prior_texture = _int_state(gl.GL_TEXTURE_BINDING_2D)
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
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)

            gl.glUniformMatrix4fv(
                self._matrix_location,
                1,
                gl.GL_FALSE,
                matrix_values,
            )
            gl.glUniform2f(
                self._item_size_location,
                float(self._logical_size[0]),
                float(self._logical_size[1]),
            )
            gl.glUniform1f(self._progress_location, float(self._state.progress))
            gl.glUniform1i(self._has_image_location, 1 if texture_id else 0)
            gl.glUniform1i(self._image_location, 0)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, prior_texture)
            gl.glActiveTexture(prior_active_texture)
            gl.glBindVertexArray(prior_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, prior_array_buffer)
            gl.glUseProgram(prior_program)
            gl.glViewport(*prior_viewport)
            _set_enabled(gl.GL_BLEND, prior_blend)
            _set_enabled(gl.GL_CULL_FACE, prior_cull)
            _set_enabled(gl.GL_DEPTH_TEST, prior_depth)
            _set_enabled(gl.GL_STENCIL_TEST, prior_stencil)

    def _sample_pixels(
        self,
        viewport: tuple[int, int, int, int],
        *,
        sample: TransitionSample | None,
    ) -> None:
        wants_sync_sample = self._telemetry.wants_pixel_sample()
        wants_midpoint = bool(
            sample is not None
            and self._telemetry.wants_transition_midpoint_sample(sample)
        )
        wants_transition_probe = bool(
            sample is not None
            and self._telemetry.wants_transition_probe_sample(sample)
        )
        if not wants_sync_sample and not wants_midpoint and not wants_transition_probe:
            return
        physical_width = max(
            1,
            round(self._logical_size[0] * self._device_pixel_ratio),
        )
        physical_height = max(
            1,
            round(self._logical_size[1] * self._device_pixel_ratio),
        )
        def _read_grid(x_offsets: tuple[int, ...], y_offsets: tuple[int, ...]):
            sample_xs = tuple(viewport[0] + offset for offset in x_offsets)
            sample_ys = tuple(viewport[1] + offset for offset in y_offsets)
            return tuple(
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
                for sample_y in sample_ys
                for sample_x in sample_xs
            )

        colors = _read_grid(
            transition_sample_offsets(physical_width),
            transition_sample_offsets(physical_height),
        )
        if wants_sync_sample:
            self._telemetry.note_pixel_sample(colors)
        if wants_midpoint and sample is not None:
            # Additionally read a dense grid so the Phase-C effect oracles can
            # reliably see thin authored effect regions. Sparse ``colors`` stay
            # the shared midpoint sample the geometry oracles depend on.
            dense_colors = _read_grid(
                transition_dense_sample_offsets(physical_width),
                transition_dense_sample_offsets(physical_height),
            )
            self._telemetry.note_transition_midpoint_sample(
                sample=sample,
                colors=colors,
                dense_colors=dense_colors,
            )
        if wants_transition_probe and sample is not None:
            self._telemetry.note_transition_probe_sample(
                sample=sample,
                colors=colors,
            )
