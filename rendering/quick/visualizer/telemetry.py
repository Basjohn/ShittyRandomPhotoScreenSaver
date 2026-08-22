"""Thread-safe focused telemetry for the inline Quick visualizer node."""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace


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
    error: str | None = None


class VisualizerRenderNodeTelemetry:
    """Small lifecycle/clip snapshot shared with focused runtime gates."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot = VisualizerRenderNodeSnapshot()

    def snapshot(self) -> VisualizerRenderNodeSnapshot:
        with self._lock:
            return self._snapshot

    def note_sync(self) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                sync_count=self._snapshot.sync_count + 1,
            )

    def note_render(
        self,
        *,
        scissor_enabled: bool,
        scissor_rect: tuple[int, int, int, int] | None,
        stencil_enabled: bool,
        stencil_value: int | None,
    ) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                render_count=self._snapshot.render_count + 1,
                render_thread_id=threading.get_ident(),
                scissor_enabled=bool(scissor_enabled),
                scissor_rect=scissor_rect,
                stencil_enabled=bool(stencil_enabled),
                stencil_value=stencil_value,
            )

    def note_release(self) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                release_count=self._snapshot.release_count + 1,
                release_thread_id=threading.get_ident(),
            )

    def note_draw(self, mode_id: object) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                draw_count=self._snapshot.draw_count + 1,
                drawn_mode_id=str(mode_id),
            )

    def note_admission_rejected(self) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                admission_rejection_count=(
                    self._snapshot.admission_rejection_count + 1
                ),
            )

    def note_invalidation(self) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                invalidation_count=self._snapshot.invalidation_count + 1,
            )

    def note_error(self, message: object) -> None:
        with self._lock:
            self._snapshot = replace(self._snapshot, error=str(message))


__all__ = [
    "VisualizerRenderNodeSnapshot",
    "VisualizerRenderNodeTelemetry",
]
