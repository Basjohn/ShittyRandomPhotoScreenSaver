"""Common GL fence, quad, and lazy visualizer renderer ownership."""

from __future__ import annotations

import ctypes
import time
from typing import TYPE_CHECKING, Callable

from OpenGL import GL as gl
from PySide6.QtGui import QOpenGLContext

from core.logging.logger import get_logger
from core.performance.frame_trace import FrameTraceEvent, logical_timestamp_ns

from rendering.quick import gl_query

from .gl_state import InheritedGlState
from .implementation_registry import resolve_quick_visualizer_renderer
from .render_contract import (
    QuickVisualizerRenderFrame,
    QuickVisualizerRenderer,
    VisualizerModeTraceContext,
)
from .telemetry import (
    VisualizerRenderHostLifecycleSnapshot,
    VisualizerRenderHostLifecycleTelemetry,
)

if TYPE_CHECKING:
    from core.performance.frame_trace import FrameTraceSink

logger = get_logger(__name__)



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




class VisualizerRenderCarryover:
    """A mode's render-thread history carried across a display move (1C.2): one box per move, made by the scene
    transfer, filled once on the source window's render thread and emptied once on the target's.

    Only history goes in (Extruded Bubble's drift state: storage buffers integrated on the GPU); everything else a
    renderer owns is rebuilt in the target's context. The display windows' contexts share one share group
    (``AA_ShareOpenGLContexts``, set before Qt starts), so a buffer named in one is valid in the other; the depositor
    fences its last use and the taker waits on the fence. ``take`` refuses (and logs) a payload from a context that
    does not share with the taker's: the history then restarts there, as a lifecycle event. Thread-safe; no GL here.
    """

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self._payloads: dict[str, object] = {}
        self._context = None
        self._closed = False

    @property
    def closed(self) -> bool:
        """The source has deposited whatever it had (or had nothing): the target may take it now."""
        with self._lock:
            return self._closed

    def deposit(self, mode_id: str, payload: object) -> None:
        """Source render thread, its context current: one mode's history."""
        with self._lock:
            if self._closed:
                raise RuntimeError("visualizer render carryover already closed")
            self._payloads[str(mode_id)] = payload
            self._context = QOpenGLContext.currentContext()

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def take(self, mode_id: str) -> object | None:
        """Target render thread, its context current: the history for ``mode_id`` (once), or None."""
        with self._lock:
            if not self._closed:
                return None
            payload = self._payloads.pop(str(mode_id), None)
            source = self._context
        if payload is None:
            return None
        current = QOpenGLContext.currentContext()
        if source is None or current is None or not QOpenGLContext.areSharing(source, current):
            logger.error("[QUICK] Visualizer %s history crossed to a window whose context does not share with its "
                         "source; the history restarts there", mode_id)
            return None
        return payload

    def take_all(self) -> dict[str, object]:
        """Whatever was never taken (a move abandoned after the deposit), for discarding in a sharing context."""
        with self._lock:
            payloads, self._payloads = self._payloads, {}
            source = self._context
        current = QOpenGLContext.currentContext()
        if not payloads or source is None or current is None or not QOpenGLContext.areSharing(source, current):
            return {}
        return payloads


# Hidden frames (content fade 0, as during a mode or preset reveal's waiting phase) let a renderer
# that offers ``prepare_step`` compile or allocate one unit, at least this far apart, so no two
# nearby frames of the window both carry a compile. Measured at the first visible frame before
# this existed: Shockwave Grid 22 ms with a warm driver shader cache. Truly cold (a new build's
# executable path, an edited shader) one unit is a whole driver link: Neon Lake's basin 5-6 s (R-180).
PREPARE_SPACING_S = 0.03


class QuickVisualizerRenderHost:
    """Own one shared quad and resolve only the current mode implementation."""

    def __init__(
        self,
        *,
        lifecycle_telemetry: VisualizerRenderHostLifecycleTelemetry | None = None,
        renderer_factory: Callable[[str], QuickVisualizerRenderer | None] | None = None,
    ) -> None:
        self._quad_vao = 0
        self._quad_vbo = 0
        self._implementations: dict[str, QuickVisualizerRenderer] = {}
        # Scoped lab/test construction seam. The canonical resolver still owns
        # registry admission and protocol validation; consulted only on a miss.
        self._renderer_factory = renderer_factory
        self._last_render_mode_id: str | None = None
        # (mode id, activation id) whose renderer has everything its visible frames need. Written
        # here on the render thread, read by the GUI-side reveal (one reference, no lock needed).
        self._prepared: tuple[str, int] | None = None
        # ((mode id, activation id), preparation units completed for it): the render thread's liveness for an
        # unrevealed activation. One unit can be a multi-second driver link (Neon Lake's basin program with a cold
        # shader cache, R-180); the GUI side tells a slow-but-alive target from a silent one by this count advancing.
        # Written only on preparation edges (never per steady frame), read by the GUI (one reference, no lock).
        self._preparation: tuple[tuple[str, int], int] | None = None
        self._next_prepare_at = 0.0
        # A display move's carried history, expected by this (target) host until its source has deposited it (1C.2).
        self._carryover: VisualizerRenderCarryover | None = None
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

    @property
    def prepared_activation(self) -> tuple[str, int] | None:
        """(mode id, activation id) whose renderer is ready to draw without compiling."""
        return self._prepared

    def preparation_progress(self, mode_id: str, activation_id: int) -> int:
        """Preparation units the render thread has completed for this activation (0 for any other)."""
        preparation = self._preparation
        if preparation is None or preparation[0] != (mode_id, int(activation_id)):
            return 0
        return preparation[1]

    def _note_preparation(self, activation: tuple[str, int]) -> None:
        preparation = self._preparation
        count = preparation[1] if preparation is not None and preparation[0] == activation else 0
        self._preparation = (activation, count + 1)

    def render(
        self,
        *,
        snapshot,
        viewport: tuple[int, int, int, int],
        logical_size: tuple[float, float],
        matrix_values: tuple[float, ...],
        frame_trace: "FrameTraceSink | None" = None,
        screen_index: int = -1,
        inherited_gl_state: InheritedGlState | None = None,
        mode_trace_context: VisualizerModeTraceContext | None = None,
    ) -> str:
        mode_id = snapshot.logical.mode_id
        # A mode switch is observed on the render thread, where the GL context
        # is legal.  The active mode draws first; every previously resolved
        # inactive implementation is retired after it, on this boundary frame
        # only (``_retire_inactive_at_boundary``), so a failing release can never
        # black out the active mode.  Lifecycle telemetry advances only on this
        # real boundary, never on ordinary same-mode frames.
        mode_changed = mode_id != self._last_render_mode_id
        if mode_changed and self._lifecycle is not None:
            self._lifecycle.note_mode_boundary(mode_id)
        implementation = self._implementations.get(mode_id)
        if implementation is None:
            implementation = (
                resolve_quick_visualizer_renderer(mode_id)
                if self._renderer_factory is None
                else resolve_quick_visualizer_renderer(mode_id, renderer_factory=self._renderer_factory)
            )
            if implementation is None:
                raise RuntimeError(
                    f"Quick visualizer renderer is not registered: {mode_id}"
                )
            self._implementations[mode_id] = implementation
            if self._lifecycle is not None:
                self._lifecycle.note_resolve(mode_id)
        self._ensure_quad()
        carryover = self._carryover
        if carryover is not None and carryover.closed:
            # A display move's history (1C.2), taken once its source deposited it, before this mode draws again.
            self._carryover = None
            payload = carryover.take(mode_id)
            if payload is not None:
                self._adopt_carryover(mode_id, implementation, payload)
        if mode_changed:
            self._record_ownership()
        frame = QuickVisualizerRenderFrame(
            snapshot=snapshot,
            viewport=viewport,
            logical_size=logical_size,
            matrix_values=matrix_values,
            quad_vao=self._quad_vao,
            trace_context=mode_trace_context,
        )
        inherited = (
            inherited_gl_state
            if inherited_gl_state is not None
            else InheritedGlState.capture_render_host()
        )
        if frame_trace is not None:
            frame_trace.record(
                FrameTraceEvent.RENDER_GL_STATE_READY,
                screen_index=int(screen_index),
                revision=snapshot.logical_revision,
                logical_timestamp_ns=logical_timestamp_ns(
                    snapshot.logical.logical_timestamp
                ),
                auxiliary=int(snapshot.logical.runtime_generation),
            )
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
            if frame_trace is not None:
                frame_trace.record(
                    FrameTraceEvent.RENDER_MODE_BEGIN,
                    screen_index=int(screen_index),
                    revision=snapshot.logical_revision,
                    logical_timestamp_ns=logical_timestamp_ns(
                        snapshot.logical.logical_timestamp
                    ),
                    auxiliary=int(snapshot.logical.runtime_generation),
                )
            prepare = getattr(implementation, "prepare_step", None)
            activation = (mode_id, int(snapshot.logical.activation_id))
            if prepare is not None and snapshot.presentation.content_fade <= 0.0:
                # Hidden: nothing would be drawn, so prepare instead (spaced, one unit).
                if self._prepared != activation:
                    now = time.monotonic()
                    if now >= self._next_prepare_at:
                        self._next_prepare_at = now + PREPARE_SPACING_S
                        if prepare(frame):
                            self._prepared = activation
                        self._note_preparation(activation)
            else:
                implementation.render(frame)
                if self._prepared != activation:
                    self._prepared = activation      # it has drawn: whatever it needed exists
                    self._note_preparation(activation)
            if frame_trace is not None:
                frame_trace.record(
                    FrameTraceEvent.RENDER_MODE_READY,
                    screen_index=int(screen_index),
                    revision=snapshot.logical_revision,
                    logical_timestamp_ns=logical_timestamp_ns(
                        snapshot.logical.logical_timestamp
                    ),
                    auxiliary=int(snapshot.logical.runtime_generation),
                )
            if mode_changed and len(self._implementations) > 1:
                self._retire_inactive_at_boundary(mode_id)
        finally:
            inherited.restore_render_host()
        self._last_render_mode_id = mode_id
        return mode_id

    def _retire_inactive_at_boundary(self, active_mode_id: str) -> None:
        """Release the inactive renderers once, after the active mode has drawn.

        A failure is recorded once (lifecycle note inside
        ``release_inactive_implementations``, one log line here) and never
        re-raised into the frame: the failed renderer stays cached and accounted,
        and its release is retried only at the next mode boundary or at
        ``release_resources``, never per frame.
        """
        try:
            self.release_inactive_implementations(active_mode_id)
        except Exception:
            logger.exception(
                "[QUICK] Visualizer inactive renderer release failed at the %s boundary; "
                "retrying at the next mode boundary or teardown",
                active_mode_id,
            )

    @staticmethod
    def _adopt_carryover(mode_id: str, implementation, payload) -> None:
        """Hand a taken history to the renderer that continues it. The host owns the payload from ``take`` until the
        renderer has adopted it: a renderer that cannot adopt it, or whose adoption raises, never leaves it without
        an owner; it is discarded here (in this context, which shares the source's), then the error is raised.
        ``discard`` is idempotent, so a renderer that already discarded it costs nothing."""
        adopt = getattr(implementation, "adopt_carryover", None)
        discard = getattr(payload, "discard", None)
        if not callable(adopt):
            logger.error("[QUICK] Visualizer %s cannot adopt a carried history; it is released", mode_id)
            if callable(discard):
                discard()
            return
        try:
            adopt(payload)
        except BaseException:
            if callable(discard):
                discard()
            raise

    def expect_carryover(self, carryover: VisualizerRenderCarryover | None) -> None:
        """Render thread (at sync): this host is a display move's target; take the source's history when it lands."""
        self._carryover = carryover

    def release_inactive_implementations(
        self,
        active_mode_id: str | None,
        carryover: VisualizerRenderCarryover | None = None,
    ) -> None:
        """Release cached renderers that cannot draw the current snapshot.

        This method is intentionally render-thread-only.  A failed renderer
        cleanup remains cached so the next mode boundary or explicit teardown can
        retry it (``render`` never retries per frame); successfully released
        implementations are removed immediately.
        The shared quad belongs to the host and remains available for the active
        mode.

        ``carryover``: this host's display just moved away (1C.2). A renderer that keeps history
        (``export_carryover``) hands it over before it releases the rest; the box closes either way.
        """

        try:
            self._release_inactive(active_mode_id, carryover)
        finally:
            if carryover is not None:
                carryover.close()

    def _release_inactive(self, active_mode_id: str | None, carryover: VisualizerRenderCarryover | None) -> None:
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
                export = getattr(implementation, "export_carryover", None)
                if carryover is not None and callable(export):
                    payload = export()
                    if payload is not None:
                        carryover.deposit(mode_id, payload)
                implementation.release_resources()
            except Exception as exc:
                errors.append(f"{mode_id}:{type(exc).__name__}:{exc}")
                continue
            if not implementation.has_resources:
                self._implementations.pop(mode_id, None)
                successes += 1
                if self._prepared is not None and self._prepared[0] == mode_id:
                    self._prepared = None
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
        carryover, self._carryover = self._carryover, None
        if carryover is not None and carryover.closed and QOpenGLContext.currentContext() is not None:
            # A move's history that never reached a frame here: its names are shared, so they die in this context.
            for payload in carryover.take_all().values():
                discard = getattr(payload, "discard", None)
                if callable(discard):
                    discard()
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
        self._prepared = None
        self._preparation = None
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
        prior_vao = gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING)
        prior_buffer = gl_query.get_int(gl.GL_ARRAY_BUFFER_BINDING)
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
