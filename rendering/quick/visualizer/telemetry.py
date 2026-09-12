"""Thread-safe focused telemetry for the inline Quick visualizer node.

Two owners live here:

* ``VisualizerRenderNodeTelemetry`` — the per-node clip/lifecycle counters. Its
  ``note_*`` hot-path calls mutate cheap protected fields under a lock and never
  allocate; the immutable ``VisualizerRenderNodeSnapshot`` is built only when
  ``snapshot()`` is read (rare), so per-frame sync/render/draw no longer churn a
  replacement frozen dataclass.
* ``VisualizerRenderHostLifecycleTelemetry`` — boundary-only render-host
  ownership facts (resolve/release/teardown). It is updated only at existing
  mode-resolve / inactive-release / full-release events, never per frame, and it
  performs no ``glGet*`` queries. Reading its snapshot mutates/releases nothing.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VisualizerRenderNodeSnapshot:
    sync_count: int = 0
    render_count: int = 0
    draw_count: int = 0
    release_count: int = 0
    invalidation_count: int = 0
    admission_rejection_count: int = 0
    render_thread_id: int | None = None
    release_thread_id: int | None = None
    scissor_enabled: bool = False
    scissor_rect: tuple[int, int, int, int] | None = None
    stencil_enabled: bool = False
    stencil_value: int | None = None
    drawn_mode_id: str | None = None
    last_logical_revision: int = 0
    last_logical_timestamp: float = 0.0
    error: str | None = None


class VisualizerRenderNodeTelemetry:
    """Small lifecycle/clip snapshot shared with focused runtime gates.

    Hot-path ``note_*`` calls mutate cheap fields; ``snapshot()`` composes one
    immutable, thread-safe :class:`VisualizerRenderNodeSnapshot` on demand.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sync_count = 0
        self._render_count = 0
        self._draw_count = 0
        self._release_count = 0
        self._invalidation_count = 0
        self._admission_rejection_count = 0
        self._render_thread_id: int | None = None
        self._release_thread_id: int | None = None
        self._scissor_enabled = False
        self._scissor_rect: tuple[int, int, int, int] | None = None
        self._stencil_enabled = False
        self._stencil_value: int | None = None
        self._drawn_mode_id: str | None = None
        self._last_logical_revision = 0
        self._last_logical_timestamp = 0.0
        self._error: str | None = None

    def snapshot(self) -> VisualizerRenderNodeSnapshot:
        with self._lock:
            return VisualizerRenderNodeSnapshot(
                sync_count=self._sync_count,
                render_count=self._render_count,
                draw_count=self._draw_count,
                release_count=self._release_count,
                invalidation_count=self._invalidation_count,
                admission_rejection_count=self._admission_rejection_count,
                render_thread_id=self._render_thread_id,
                release_thread_id=self._release_thread_id,
                scissor_enabled=self._scissor_enabled,
                scissor_rect=self._scissor_rect,
                stencil_enabled=self._stencil_enabled,
                stencil_value=self._stencil_value,
                drawn_mode_id=self._drawn_mode_id,
                last_logical_revision=self._last_logical_revision,
                last_logical_timestamp=self._last_logical_timestamp,
                error=self._error,
            )

    def note_sync(self) -> None:
        with self._lock:
            self._sync_count += 1

    def note_render(
        self,
        *,
        scissor_enabled: bool,
        scissor_rect: tuple[int, int, int, int] | None,
        stencil_enabled: bool,
        stencil_value: int | None,
    ) -> None:
        with self._lock:
            self._render_count += 1
            self._render_thread_id = threading.get_ident()
            self._scissor_enabled = bool(scissor_enabled)
            self._scissor_rect = scissor_rect
            self._stencil_enabled = bool(stencil_enabled)
            self._stencil_value = stencil_value

    def note_release(self) -> None:
        with self._lock:
            self._release_count += 1
            self._release_thread_id = threading.get_ident()

    def note_draw(
        self,
        mode_id: object,
        *,
        logical_revision: int = 0,
        logical_timestamp: float = 0.0,
    ) -> None:
        with self._lock:
            self._draw_count += 1
            self._drawn_mode_id = str(mode_id)
            self._last_logical_revision = max(0, int(logical_revision))
            self._last_logical_timestamp = max(0.0, float(logical_timestamp))

    def note_admission_rejected(self) -> None:
        with self._lock:
            self._admission_rejection_count += 1

    def note_invalidation(self) -> None:
        with self._lock:
            self._invalidation_count += 1

    def note_error(self, message: object) -> None:
        with self._lock:
            self._error = str(message)


@dataclass(frozen=True, slots=True)
class VisualizerRenderHostLifecycleSnapshot:
    """Boundary-only render-host ownership facts for the display/teardown snapshot.

    ``resolve_counts_by_mode`` / ``resolved_has_resources`` are tuples of
    ``(mode_id, value)`` pairs so the snapshot stays immutable/hashable. All
    counts advance only at real resolve/release/teardown events, never per frame.
    """

    active_mode_id: str | None = None
    mode_boundary_seq: int = 0
    renderer_resolve_count: int = 0
    resolve_counts_by_mode: tuple[tuple[str, int], ...] = ()
    inactive_release_attempts: int = 0
    inactive_release_successes: int = 0
    inactive_release_failures: int = 0
    resolved_mode_ids: tuple[str, ...] = ()
    resolved_has_resources: tuple[tuple[str, bool], ...] = ()
    quad_vao_owned: bool = False
    quad_vbo_owned: bool = False
    full_release_count: int = 0
    last_release_error: str | None = None


class VisualizerRenderHostLifecycleTelemetry:
    """Accumulate render-host lifecycle facts at existing boundaries only.

    The host records events (resolve, inactive release attempt/outcome, full
    release) and, at each such boundary, captures the already-owned ownership
    facts (resolved mode ids, per-implementation ``has_resources``, shared-quad
    ownership booleans). No frame path, no ``glGet*``, no release from the reader.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_mode_id: str | None = None
        self._mode_boundary_seq = 0
        self._renderer_resolve_count = 0
        self._resolve_counts_by_mode: dict[str, int] = {}
        self._inactive_release_attempts = 0
        self._inactive_release_successes = 0
        self._inactive_release_failures = 0
        self._resolved_mode_ids: tuple[str, ...] = ()
        self._resolved_has_resources: tuple[tuple[str, bool], ...] = ()
        self._quad_vao_owned = False
        self._quad_vbo_owned = False
        self._full_release_count = 0
        self._last_release_error: str | None = None

    def snapshot(self) -> VisualizerRenderHostLifecycleSnapshot:
        with self._lock:
            return VisualizerRenderHostLifecycleSnapshot(
                active_mode_id=self._active_mode_id,
                mode_boundary_seq=self._mode_boundary_seq,
                renderer_resolve_count=self._renderer_resolve_count,
                resolve_counts_by_mode=tuple(
                    sorted(self._resolve_counts_by_mode.items())
                ),
                inactive_release_attempts=self._inactive_release_attempts,
                inactive_release_successes=self._inactive_release_successes,
                inactive_release_failures=self._inactive_release_failures,
                resolved_mode_ids=self._resolved_mode_ids,
                resolved_has_resources=self._resolved_has_resources,
                quad_vao_owned=self._quad_vao_owned,
                quad_vbo_owned=self._quad_vbo_owned,
                full_release_count=self._full_release_count,
                last_release_error=self._last_release_error,
            )

    def note_mode_boundary(self, active_mode_id: str | None) -> None:
        with self._lock:
            self._active_mode_id = active_mode_id
            self._mode_boundary_seq += 1

    def note_resolve(self, mode_id: str) -> None:
        with self._lock:
            self._renderer_resolve_count += 1
            self._resolve_counts_by_mode[mode_id] = (
                self._resolve_counts_by_mode.get(mode_id, 0) + 1
            )

    def note_inactive_release(
        self, *, attempts: int, successes: int, failures: int,
        error: str | None,
    ) -> None:
        with self._lock:
            self._inactive_release_attempts += int(attempts)
            self._inactive_release_successes += int(successes)
            self._inactive_release_failures += int(failures)
            if error is not None:
                self._last_release_error = str(error)

    def note_full_release(self, *, error: str | None) -> None:
        with self._lock:
            self._full_release_count += 1
            if error is not None:
                self._last_release_error = str(error)

    def note_ownership(
        self,
        *,
        resolved_mode_ids: tuple[str, ...],
        resolved_has_resources: tuple[tuple[str, bool], ...],
        quad_vao_owned: bool,
        quad_vbo_owned: bool,
    ) -> None:
        """Record the already-owned ownership facts at an existing boundary."""
        with self._lock:
            self._resolved_mode_ids = resolved_mode_ids
            self._resolved_has_resources = resolved_has_resources
            self._quad_vao_owned = bool(quad_vao_owned)
            self._quad_vbo_owned = bool(quad_vbo_owned)


__all__ = [
    "VisualizerRenderNodeSnapshot",
    "VisualizerRenderNodeTelemetry",
    "VisualizerRenderHostLifecycleSnapshot",
    "VisualizerRenderHostLifecycleTelemetry",
]
