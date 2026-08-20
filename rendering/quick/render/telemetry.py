"""Thread-safe proof telemetry for the first production Quick render node."""

from __future__ import annotations

from dataclasses import dataclass, replace
import threading

from ..transitions.state import TransitionRun, TransitionSample


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
    render_target_size: tuple[int, int] = (0, 0)
    pixel_sample_count: int = 0
    sampled_sync_count: int = 0
    sample_colors: tuple[str, ...] = ()
    active_image_identity: str | None = None
    image_upload_thread_id: int | None = None
    image_release_thread_id: int | None = None
    image_upload_count: int = 0
    image_upload_bytes: int = 0
    image_release_count: int = 0
    image_release_bytes: int = 0
    pending_image_release_count: int = 0
    transition_sample_count: int = 0
    last_transition_run_id: int | None = None
    last_transition_generation: int | None = None
    last_transition_id: str | None = None
    last_transition_linear_progress: float | None = None
    last_transition_eased_progress: float | None = None
    transition_draw_count: int = 0
    last_transition_renderer_id: str | None = None
    transition_midpoint_run_id: int | None = None
    transition_midpoint_linear_progress: float | None = None
    transition_midpoint_eased_progress: float | None = None
    transition_midpoint_colors: tuple[str, ...] = ()
    transition_probe_run_id: int | None = None
    transition_probe_linear_progresses: tuple[float, ...] = ()
    transition_probe_eased_progresses: tuple[float, ...] = ()
    transition_probe_colors: tuple[tuple[str, ...], ...] = ()
    gl_version: str = ""
    error: str | None = None


class RenderNodeTelemetry:
    """Latest immutable diagnostics written by GUI/sync/render owners."""

    def __init__(
        self,
        *,
        gui_thread_id: int | None = None,
        capture_pixels: bool = False,
        transition_probe_progresses: tuple[float, ...] = (),
    ) -> None:
        self._lock = threading.Lock()
        self._capture_pixels = bool(capture_pixels)
        probes = tuple(float(progress) for progress in transition_probe_progresses)
        if any(not 0.0 < progress < 1.0 for progress in probes):
            raise ValueError("transition pixel probes must be inside the run")
        if probes != tuple(sorted(set(probes))):
            raise ValueError("transition pixel probes must be unique and increasing")
        self._transition_probe_progresses = probes
        self._transition_probe_run_id: int | None = None
        self._transition_probe_index = 0
        self._transition_probe_candidate: tuple[
            TransitionSample,
            tuple[str, ...],
        ] | None = None
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
        render_target_size: tuple[int, int],
    ) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                render_thread_id=int(render_thread_id),
                render_count=self._snapshot.render_count + 1,
                viewport=tuple(int(value) for value in viewport),
                render_target_size=tuple(
                    int(value) for value in render_target_size
                ),
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

    def note_image_uploaded(
        self,
        *,
        identity: str,
        active_identity: str | None,
        byte_count: int,
        pending_release_count: int,
    ) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                active_image_identity=active_identity,
                image_upload_thread_id=threading.get_ident(),
                image_upload_count=self._snapshot.image_upload_count + 1,
                image_upload_bytes=(
                    self._snapshot.image_upload_bytes + int(byte_count)
                ),
                pending_image_release_count=int(pending_release_count),
            )

    def note_image_released(
        self,
        *,
        active_identity: str | None,
        byte_count: int,
        pending_release_count: int,
    ) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                active_image_identity=active_identity,
                image_release_thread_id=threading.get_ident(),
                image_release_count=self._snapshot.image_release_count + 1,
                image_release_bytes=(
                    self._snapshot.image_release_bytes + int(byte_count)
                ),
                pending_image_release_count=int(pending_release_count),
            )

    def note_image_release_pending(
        self,
        *,
        active_identity: str | None,
        pending_release_count: int,
    ) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                active_image_identity=active_identity,
                pending_image_release_count=int(pending_release_count),
            )

    def note_transition_sample(
        self,
        *,
        run: TransitionRun,
        sample: TransitionSample,
    ) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                transition_sample_count=(
                    self._snapshot.transition_sample_count + 1
                ),
                last_transition_run_id=sample.run_id,
                last_transition_generation=sample.runtime_generation,
                last_transition_id=run.request.transition_id,
                last_transition_linear_progress=sample.linear_progress,
                last_transition_eased_progress=sample.eased_progress,
            )

    def note_transition_drawn(self, *, transition_id: str) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                transition_draw_count=self._snapshot.transition_draw_count + 1,
                last_transition_renderer_id=str(transition_id),
            )

    def wants_transition_midpoint_sample(
        self,
        sample: TransitionSample,
    ) -> bool:
        with self._lock:
            return bool(
                self._capture_pixels
                and self._snapshot.transition_midpoint_run_id != sample.run_id
                and 0.35 <= sample.linear_progress <= 0.75
            )

    def note_transition_midpoint_sample(
        self,
        *,
        sample: TransitionSample,
        colors: tuple[str, ...],
    ) -> None:
        with self._lock:
            if self._snapshot.transition_midpoint_run_id == sample.run_id:
                return
            self._snapshot = replace(
                self._snapshot,
                transition_midpoint_run_id=sample.run_id,
                transition_midpoint_linear_progress=sample.linear_progress,
                transition_midpoint_eased_progress=sample.eased_progress,
                transition_midpoint_colors=tuple(str(color) for color in colors),
            )

    def wants_transition_probe_sample(
        self,
        sample: TransitionSample,
    ) -> bool:
        with self._lock:
            if not self._capture_pixels or not self._transition_probe_progresses:
                return False
            index = (
                self._transition_probe_index
                if self._transition_probe_run_id == sample.run_id
                else 0
            )
            if index >= len(self._transition_probe_progresses):
                return False
            target = self._transition_probe_progresses[index]
            return bool(sample.linear_progress >= target - 0.04 and not sample.complete)

    def note_transition_probe_sample(
        self,
        *,
        sample: TransitionSample,
        colors: tuple[str, ...],
    ) -> None:
        with self._lock:
            run_changed = self._transition_probe_run_id != sample.run_id
            if run_changed:
                self._transition_probe_run_id = sample.run_id
                self._transition_probe_index = 0
                self._transition_probe_candidate = None
            if self._transition_probe_index >= len(
                self._transition_probe_progresses
            ):
                return
            target = self._transition_probe_progresses[self._transition_probe_index]
            colors_value = tuple(str(color) for color in colors)
            candidate = self._transition_probe_candidate
            if candidate is None or abs(sample.linear_progress - target) < abs(
                candidate[0].linear_progress - target
            ):
                candidate = (sample, colors_value)
                self._transition_probe_candidate = candidate
            if sample.linear_progress < target:
                return

            chosen_sample, chosen_colors = candidate
            snapshot_matches_run = (
                self._snapshot.transition_probe_run_id == sample.run_id
            )
            linear = (
                self._snapshot.transition_probe_linear_progresses
                if snapshot_matches_run
                else ()
            )
            eased = (
                self._snapshot.transition_probe_eased_progresses
                if snapshot_matches_run
                else ()
            )
            samples = (
                self._snapshot.transition_probe_colors
                if snapshot_matches_run
                else ()
            )
            self._snapshot = replace(
                self._snapshot,
                transition_probe_run_id=sample.run_id,
                transition_probe_linear_progresses=(
                    *linear,
                    float(chosen_sample.linear_progress),
                ),
                transition_probe_eased_progresses=(
                    *eased,
                    float(chosen_sample.eased_progress),
                ),
                transition_probe_colors=(
                    *samples,
                    chosen_colors,
                ),
            )
            self._transition_probe_index += 1
            self._transition_probe_candidate = None

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
