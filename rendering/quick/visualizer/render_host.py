"""Common GL fence, quad, and lazy visualizer renderer ownership."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from time import perf_counter_ns as _perf_counter_ns

from OpenGL import GL as gl
from PySide6.QtGui import QOpenGLContext

from core.diagnostics import visualizer_attribution as _viz_attr

from .implementation_registry import resolve_quick_visualizer_renderer
from .render_contract import QuickVisualizerRenderFrame, QuickVisualizerRenderer
from .telemetry import (
    VisualizerRenderHostLifecycleSnapshot,
    VisualizerRenderHostLifecycleTelemetry,
)


def create_lifecycle_telemetry_if_admitted() -> (
    VisualizerRenderHostLifecycleTelemetry | None
):
    """Allocate render-host lifecycle telemetry only when opt-in admitted.

    The switch/resource ownership telemetry (P1) is a diagnostic experiment, not
    a runtime feature: without ``--viz-switch-telemetry`` or ``--abc-drive`` the
    process admission is disabled and this returns ``None``, so Standard/MC
    runtime allocates no telemetry object, takes no new lock, and keeps no new
    bookkeeping. Tests/tools inject a telemetry object directly instead of
    depending on process argv.
    """
    from core.diagnostics.experiment_flags import (
        visualizer_switch_telemetry_admitted,
    )

    if visualizer_switch_telemetry_admitted():
        return VisualizerRenderHostLifecycleTelemetry()
    return None


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
class _InheritedGlState:
    viewport: tuple[int, int, int, int]
    program: int
    vao: int
    array_buffer: int
    blend: bool
    blend_src_rgb: int
    blend_dst_rgb: int
    blend_src_alpha: int
    blend_dst_alpha: int
    blend_equation_rgb: int
    blend_equation_alpha: int
    cull: bool
    depth: bool
    depth_write: bool

    @classmethod
    def capture(cls) -> "_InheritedGlState":
        viewport = tuple(int(value) for value in gl.glGetIntegerv(gl.GL_VIEWPORT))
        if len(viewport) != 4:
            raise RuntimeError(f"invalid inherited Quick GL viewport: {viewport}")
        return cls(
            viewport=viewport,
            program=_int_state(gl.GL_CURRENT_PROGRAM),
            vao=_int_state(gl.GL_VERTEX_ARRAY_BINDING),
            array_buffer=_int_state(gl.GL_ARRAY_BUFFER_BINDING),
            blend=bool(gl.glIsEnabled(gl.GL_BLEND)),
            blend_src_rgb=_int_state(gl.GL_BLEND_SRC_RGB),
            blend_dst_rgb=_int_state(gl.GL_BLEND_DST_RGB),
            blend_src_alpha=_int_state(gl.GL_BLEND_SRC_ALPHA),
            blend_dst_alpha=_int_state(gl.GL_BLEND_DST_ALPHA),
            blend_equation_rgb=_int_state(gl.GL_BLEND_EQUATION_RGB),
            blend_equation_alpha=_int_state(gl.GL_BLEND_EQUATION_ALPHA),
            cull=bool(gl.glIsEnabled(gl.GL_CULL_FACE)),
            depth=bool(gl.glIsEnabled(gl.GL_DEPTH_TEST)),
            depth_write=_bool_state(gl.GL_DEPTH_WRITEMASK),
        )

    def restore(self) -> None:
        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.array_buffer)
        gl.glUseProgram(self.program)
        gl.glViewport(*self.viewport)
        gl.glBlendEquationSeparate(
            self.blend_equation_rgb,
            self.blend_equation_alpha,
        )
        gl.glBlendFuncSeparate(
            self.blend_src_rgb,
            self.blend_dst_rgb,
            self.blend_src_alpha,
            self.blend_dst_alpha,
        )
        gl.glDepthMask(gl.GL_TRUE if self.depth_write else gl.GL_FALSE)
        _set_enabled(gl.GL_BLEND, self.blend)
        _set_enabled(gl.GL_CULL_FACE, self.cull)
        _set_enabled(gl.GL_DEPTH_TEST, self.depth)


class QuickVisualizerRenderHost:
    """Own one shared quad and resolve only the current mode implementation."""

    def __init__(
        self,
        *,
        lifecycle_telemetry: VisualizerRenderHostLifecycleTelemetry | None = None,
    ) -> None:
        self._quad_vao = 0
        self._quad_vbo = 0
        self._implementations: dict[str, QuickVisualizerRenderer] = {}
        self._last_render_mode_id: str | None = None
        # Opt-in only: injected telemetry (tests/tools) wins; otherwise consult
        # the process experiment admission. ``None`` == disabled == no new
        # allocation/lock/bookkeeping for ordinary Standard/MC runtime.
        self._lifecycle: VisualizerRenderHostLifecycleTelemetry | None = (
            lifecycle_telemetry
            if lifecycle_telemetry is not None
            else create_lifecycle_telemetry_if_admitted()
        )

    @property
    def lifecycle_telemetry_enabled(self) -> bool:
        """True only when opt-in switch/resource telemetry is admitted."""
        return self._lifecycle is not None

    def lifecycle_snapshot(self) -> VisualizerRenderHostLifecycleSnapshot | None:
        """Boundary-only ownership facts, or ``None`` when telemetry is disabled.

        Reading mutates/renders/releases nothing. ``None`` means the opt-in
        telemetry was never admitted, so no snapshot exists to surface.
        """
        if self._lifecycle is None:
            return None
        return self._lifecycle.snapshot()

    def _record_ownership(self) -> None:
        """Capture already-owned ownership facts at an existing boundary.

        No ``glGet*`` queries: the quad booleans and per-implementation
        ``has_resources`` are host-side facts already tracked in Python. A no-op
        when telemetry is disabled.
        """
        if self._lifecycle is None:
            return
        self._lifecycle.note_ownership(
            resolved_mode_ids=tuple(sorted(self._implementations)),
            resolved_has_resources=tuple(
                (mode_id, bool(implementation.has_resources))
                for mode_id, implementation in sorted(self._implementations.items())
            ),
            quad_vao_owned=bool(self._quad_vao),
            quad_vbo_owned=bool(self._quad_vbo),
        )

    @property
    def has_resources(self) -> bool:
        return bool(
            self._quad_vao
            or self._quad_vbo
            or any(
                implementation.has_resources
                for implementation in self._implementations.values()
            )
        )

    @property
    def resolved_mode_ids(self) -> frozenset[str]:
        return frozenset(self._implementations)

    def render(
        self,
        *,
        snapshot,
        viewport: tuple[int, int, int, int],
        logical_size: tuple[float, float],
        matrix_values: tuple[float, ...],
    ) -> str:
        mode_id = snapshot.logical.mode_id
        # A mode switch is observed on the render thread, where the GL context
        # is legal.  Retire every previously resolved inactive implementation
        # before lazily resolving the new one.  Lifecycle telemetry advances only
        # on this real boundary, never on ordinary same-mode frames.
        # ``mode_changed`` already gates the existing retirement path; guarding
        # the telemetry note behind it (short-circuit) adds no per-frame branch,
        # only a boundary-time None check when a switch actually happens.
        mode_changed = mode_id != self._last_render_mode_id
        if mode_changed and self._lifecycle is not None:
            self._lifecycle.note_mode_boundary(mode_id)
        if mode_changed or len(self._implementations) > 1:
            self.release_inactive_implementations(mode_id)
        implementation = self._implementations.get(mode_id)
        if implementation is None:
            implementation = resolve_quick_visualizer_renderer(mode_id)
            if implementation is None:
                raise RuntimeError(
                    f"Quick visualizer renderer is not registered: {mode_id}"
                )
            self._implementations[mode_id] = implementation
            if self._lifecycle is not None:
                self._lifecycle.note_resolve(mode_id)
        self._ensure_quad()
        if mode_changed:
            self._record_ownership()
        frame = QuickVisualizerRenderFrame(
            snapshot=snapshot,
            viewport=viewport,
            logical_size=logical_size,
            matrix_values=matrix_values,
            quad_vao=self._quad_vao,
        )
        # Opt-in P4 fence-cost measurement (render thread). When the experiment is
        # not admitted this is None and no timing calls run; the GL work below is
        # NEVER added to or removed from — only the existing capture()/restore() are
        # wrapped with time.perf_counter_ns() to measure their duration distribution.
        _fence = _viz_attr.fence_timing()
        if _fence is None:
            inherited = _InheritedGlState.capture()
        else:
            _c0 = _perf_counter_ns()
            inherited = _InheritedGlState.capture()
            _fence.note_capture(_perf_counter_ns() - _c0)
        try:
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendEquationSeparate(gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
            gl.glBlendFuncSeparate(
                gl.GL_SRC_ALPHA,
                gl.GL_ONE_MINUS_SRC_ALPHA,
                gl.GL_ONE,
                gl.GL_ONE_MINUS_SRC_ALPHA,
            )
            gl.glDisable(gl.GL_CULL_FACE)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glDepthMask(gl.GL_FALSE)
            gl.glViewport(*viewport)
            implementation.render(frame)
        finally:
            if _fence is None:
                inherited.restore()
            else:
                _r0 = _perf_counter_ns()
                inherited.restore()
                _fence.note_restore(_perf_counter_ns() - _r0)
        self._last_render_mode_id = mode_id
        return mode_id

    def release_inactive_implementations(self, active_mode_id: str | None) -> None:
        """Release cached renderers that cannot draw the current snapshot.

        This method is intentionally render-thread-only.  A failed renderer
        cleanup remains cached so a later legal render or explicit teardown can
        retry it; successfully released implementations are removed immediately.
        The shared quad belongs to the host and remains available for the active
        mode.
        """

        active = (
            None
            if active_mode_id is None
            else str(active_mode_id).strip().lower()
        )
        inactive = tuple(
            (mode_id, implementation)
            for mode_id, implementation in self._implementations.items()
            if mode_id != active
        )
        if not inactive:
            return
        if QOpenGLContext.currentContext() is None:
            raise RuntimeError(
                "visualizer inactive render resources released without a current GL context"
            )
        errors: list[str] = []
        successes = 0
        for mode_id, implementation in inactive:
            try:
                implementation.release_resources()
            except Exception as exc:
                errors.append(f"{mode_id}:{type(exc).__name__}:{exc}")
                continue
            if not implementation.has_resources:
                self._implementations.pop(mode_id, None)
                successes += 1
        # A failed release stays accounted as a failure and a retained renderer;
        # it is never silently dropped from the ownership snapshot.
        if self._lifecycle is not None:
            self._lifecycle.note_inactive_release(
                attempts=len(inactive),
                successes=successes,
                failures=len(errors),
                error=(" | ".join(errors) if errors else None),
            )
        self._record_ownership()
        if errors:
            raise RuntimeError(
                "Quick visualizer inactive cleanup incomplete: "
                + " | ".join(errors)
            )

    def release_resources(self) -> None:
        if not self.has_resources:
            return
        if QOpenGLContext.currentContext() is None:
            raise RuntimeError(
                "visualizer render resources released without a current GL context"
            )
        errors: list[str] = []
        for mode_id, implementation in tuple(self._implementations.items()):
            try:
                implementation.release_resources()
            except Exception as exc:
                errors.append(f"{mode_id}:{type(exc).__name__}:{exc}")
                continue
            if not implementation.has_resources:
                del self._implementations[mode_id]
        if self._quad_vbo:
            gl.glDeleteBuffers(1, [self._quad_vbo])
            self._quad_vbo = 0
        if self._quad_vao:
            gl.glDeleteVertexArrays(1, [self._quad_vao])
        self._quad_vao = 0
        self._last_render_mode_id = None
        if self._lifecycle is not None:
            self._lifecycle.note_full_release(
                error=(" | ".join(errors) if errors else None)
            )
        self._record_ownership()
        if errors:
            raise RuntimeError(
                "Quick visualizer cleanup incomplete: " + " | ".join(errors)
            )

    def _ensure_quad(self) -> None:
        if self._quad_vao and self._quad_vbo:
            return
        if QOpenGLContext.currentContext() is None:
            raise RuntimeError("visualizer render host has no current GL context")
        prior_vao = _int_state(gl.GL_VERTEX_ARRAY_BINDING)
        prior_buffer = _int_state(gl.GL_ARRAY_BUFFER_BINDING)
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
        try:
            self._quad_vao = int(gl.glGenVertexArrays(1))
            self._quad_vbo = int(gl.glGenBuffers(1))
            if not self._quad_vao or not self._quad_vbo:
                raise RuntimeError("visualizer shared quad creation failed")
            gl.glBindVertexArray(self._quad_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._quad_vbo)
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
        except Exception:
            if self._quad_vbo:
                gl.glDeleteBuffers(1, [self._quad_vbo])
            if self._quad_vao:
                gl.glDeleteVertexArrays(1, [self._quad_vao])
            self._quad_vbo = 0
            self._quad_vao = 0
            raise
        finally:
            gl.glBindVertexArray(prior_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, prior_buffer)


__all__ = ["QuickVisualizerRenderHost"]
