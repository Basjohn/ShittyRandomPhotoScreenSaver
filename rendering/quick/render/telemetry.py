"""Thread-safe proof telemetry for the first production Quick render node."""

from __future__ import annotations

from dataclasses import dataclass, replace
import threading


@dataclass(frozen=True)
class RenderNodeSnapshot:
    gui_thread_id: int
    render_thread_id: int | None = None
    release_thread_id: int | None = None
    invalidation_thread_id: int | None = None
    sync_count: int = 0
    initialize_count: int = 0
    render_count: int = 0
    release_count: int = 0
    invalidation_count: int = 0
    logical_size: tuple[float, float] = (0.0, 0.0)
    device_pixel_ratio: float = 1.0
    viewport: tuple[int, int, int, int] = (0, 0, 0, 0)
    pixel_sample_count: int = 0
    sampled_sync_count: int = 0
    sample_colors: tuple[str, ...] = ()
    gl_version: str = ""
    error: str | None = None


class RenderNodeTelemetry:
    """Latest immutable diagnostics written by GUI/sync/render owners."""

    def __init__(
        self,
        *,
        gui_thread_id: int | None = None,
        capture_pixels: bool = False,
    ) -> None:
        self._lock = threading.Lock()
        self._capture_pixels = bool(capture_pixels)
        self._snapshot = RenderNodeSnapshot(
            gui_thread_id=(
                threading.get_ident() if gui_thread_id is None else int(gui_thread_id)
            )
        )

    def snapshot(self) -> RenderNodeSnapshot:
        with self._lock:
            return self._snapshot

    def note_sync(
        self,
        *,
        logical_size: tuple[float, float],
        device_pixel_ratio: float,
    ) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                sync_count=self._snapshot.sync_count + 1,
                logical_size=(float(logical_size[0]), float(logical_size[1])),
                device_pixel_ratio=float(device_pixel_ratio),
            )

    def note_initialized(self, *, render_thread_id: int, gl_version: str) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                render_thread_id=int(render_thread_id),
                initialize_count=self._snapshot.initialize_count + 1,
                gl_version=str(gl_version),
            )

    def note_render(
        self,
        *,
        render_thread_id: int,
        viewport: tuple[int, int, int, int],
    ) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                render_thread_id=int(render_thread_id),
                render_count=self._snapshot.render_count + 1,
                viewport=tuple(int(value) for value in viewport),
            )

    def wants_pixel_sample(self) -> bool:
        with self._lock:
            return bool(
                self._capture_pixels
                and self._snapshot.sampled_sync_count < self._snapshot.sync_count
            )

    def note_pixel_sample(self, colors: tuple[str, ...]) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                pixel_sample_count=self._snapshot.pixel_sample_count + 1,
                sampled_sync_count=self._snapshot.sync_count,
                sample_colors=tuple(str(color) for color in colors),
            )

    def note_released(self, *, release_thread_id: int) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                release_thread_id=int(release_thread_id),
                release_count=self._snapshot.release_count + 1,
            )

    def note_scene_graph_invalidated(self) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                invalidation_thread_id=threading.get_ident(),
                invalidation_count=self._snapshot.invalidation_count + 1,
            )

    def note_error(self, error: object) -> None:
        with self._lock:
            self._snapshot = replace(self._snapshot, error=str(error))
