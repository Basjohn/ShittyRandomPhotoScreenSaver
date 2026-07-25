"""Performance metrics dataclasses for GL compositor transitions.

These dataclasses track timing metrics for animations, paint operations,
and render timer cadence during compositor-driven transitions.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


_PAINT_TIMING_WINDOW_SIZE = 512


@dataclass
class _GLPipelineState:
    """GL pipeline state for shader-backed transitions.
    
    Holds OpenGL object IDs and uniform location dicts.
    Texture management delegated to GLTextureManager.
    """
    # Geometry IDs
    quad_vao: int = 0
    quad_vbo: int = 0
    box_vao: int = 0
    box_vbo: int = 0
    box_vertex_count: int = 0
    
    # Shader program IDs
    basic_program: int = 0
    raindrops_program: int = 0
    warp_program: int = 0
    diffuse_program: int = 0
    blockflip_program: int = 0
    crossfade_program: int = 0
    slide_program: int = 0
    wipe_program: int = 0
    blinds_program: int = 0
    crumble_program: int = 0
    particle_program: int = 0
    burn_program: int = 0

    # Uniform locations for basic card-flip program
    u_angle_loc: int = -1
    u_aspect_loc: int = -1
    u_old_tex_loc: int = -1
    u_new_tex_loc: int = -1
    u_spec_dir_loc: int = -1
    u_axis_mode_loc: int = -1
    u_block_rect_loc: int = -1
    u_block_uv_rect_loc: int = -1

    # Uniform location dicts (populated by program helpers)
    raindrops_uniforms: dict = field(default_factory=dict)
    warp_uniforms: dict = field(default_factory=dict)
    diffuse_uniforms: dict = field(default_factory=dict)
    blockflip_uniforms: dict = field(default_factory=dict)
    blinds_uniforms: dict = field(default_factory=dict)
    crumble_uniforms: dict = field(default_factory=dict)
    particle_uniforms: dict = field(default_factory=dict)
    burn_uniforms: dict = field(default_factory=dict)
    crossfade_uniforms: dict = field(default_factory=dict)
    slide_uniforms: dict = field(default_factory=dict)
    wipe_uniforms: dict = field(default_factory=dict)

    initialized: bool = False


@dataclass
class _AnimationRunMetrics:
    """Lightweight animation tick telemetry for compositor-driven transitions."""

    name: str
    duration_ms: int
    target_fps: int
    dt_spike_threshold_ms: float
    start_ts: float = field(default_factory=time.time)
    last_tick_ts: Optional[float] = None
    frame_count: int = 0
    min_dt: float = 0.0
    max_dt: float = 0.0
    last_progress: float = 0.0
    dt_spike_count: int = 0
    last_spike_log_ts: float = 0.0

    def record_tick(self, progress: float) -> Optional[float]:
        """Record an animation tick and return dt in seconds if available."""
        now = time.time()
        dt = None
        if self.last_tick_ts is not None:
            dt = now - self.last_tick_ts
            if dt > 0.0:
                if self.min_dt == 0.0 or dt < self.min_dt:
                    self.min_dt = dt
                if dt > self.max_dt:
                    self.max_dt = dt
        self.last_tick_ts = now
        self.last_progress = progress
        self.frame_count += 1
        return dt

    def should_log_spike(self, dt: float, cooldown_s: float = 0.4) -> bool:
        """Return True when this dt exceeds the spike threshold and cooldown."""
        if dt * 1000.0 < self.dt_spike_threshold_ms:
            return False
        now = time.time()
        if self.last_spike_log_ts and (now - self.last_spike_log_ts) < cooldown_s:
            return False
        self.last_spike_log_ts = now
        self.dt_spike_count += 1
        return True

    def elapsed_seconds(self) -> float:
        return max(0.0, time.time() - self.start_ts)


@dataclass
class _PaintTimingSample:
    """One passive paint-delivery observation retained in the bounded window."""

    frame_index: int
    scene_generation: int
    paint_start_ts: float
    paint_end_ts: float
    paint_duration_ms: float
    paint_interval_ms: Optional[float]
    request_to_paint_age_ms: Optional[float]


@dataclass
class _PaintMetrics:
    """Tracks bounded passive paint-delivery timing for transitions."""

    label: str
    slow_threshold_ms: float
    start_ts: float = field(default_factory=time.perf_counter)
    last_paint_ts: Optional[float] = None
    frame_count: int = 0
    min_dt: float = 0.0
    max_dt: float = 0.0
    min_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    slow_count: int = 0
    render_request_count: int = 0
    skipped_request_count: int = 0
    presented_frame_index: int = 0
    _pending_request_ts: Optional[float] = None
    _active_paint_start_ts: Optional[float] = None
    _active_scene_generation: int = 0
    _active_request_to_paint_age_ms: Optional[float] = None
    _active_presented_frame_index: int = 0
    samples: deque[_PaintTimingSample] = field(
        default_factory=lambda: deque(maxlen=_PAINT_TIMING_WINDOW_SIZE)
    )

    def record_render_request(
        self,
        *,
        accepted_update: bool,
        request_ts: Optional[float] = None,
    ) -> None:
        """Record request acceptance without influencing the existing update path."""
        if not accepted_update:
            self.skipped_request_count += 1
            return
        self.render_request_count += 1
        self._pending_request_ts = time.perf_counter() if request_ts is None else request_ts

    def record_paint_start(self, paint_start_ts: float, scene_generation: int) -> None:
        """Capture the delivery age before paint consumes the pending request."""
        self.presented_frame_index += 1
        self._active_presented_frame_index = self.presented_frame_index
        self._active_paint_start_ts = paint_start_ts
        self._active_scene_generation = scene_generation
        request_ts = self._pending_request_ts
        self._pending_request_ts = None
        self._active_request_to_paint_age_ms = (
            max(0.0, (paint_start_ts - request_ts) * 1000.0)
            if request_ts is not None
            else None
        )

    def record(
        self,
        paint_duration_ms: float,
        *,
        paint_start_ts: Optional[float] = None,
        paint_end_ts: Optional[float] = None,
    ) -> Optional[float]:
        """Record a paint duration and return start-to-start dt seconds when available."""
        end_ts = time.perf_counter() if paint_end_ts is None else paint_end_ts
        start_ts = (
            paint_start_ts if paint_start_ts is not None else self._active_paint_start_ts
        )
        if start_ts is None:
            start_ts = end_ts - max(0.0, paint_duration_ms) / 1000.0
        dt = None
        if self.last_paint_ts is not None:
            dt = start_ts - self.last_paint_ts
            if dt > 0.0:
                if self.min_dt == 0.0 or dt < self.min_dt:
                    self.min_dt = dt
                if dt > self.max_dt:
                    self.max_dt = dt
        self.last_paint_ts = start_ts
        self.frame_count += 1
        if self.min_duration_ms == 0.0 or paint_duration_ms < self.min_duration_ms:
            self.min_duration_ms = paint_duration_ms
        if paint_duration_ms > self.max_duration_ms:
            self.max_duration_ms = paint_duration_ms
        if paint_duration_ms > self.slow_threshold_ms:
            self.slow_count += 1
        if self._active_paint_start_ts is None:
            self.presented_frame_index += 1
            self._active_presented_frame_index = self.presented_frame_index
        self.samples.append(
            _PaintTimingSample(
                frame_index=self._active_presented_frame_index,
                scene_generation=self._active_scene_generation,
                paint_start_ts=start_ts,
                paint_end_ts=end_ts,
                paint_duration_ms=paint_duration_ms,
                paint_interval_ms=dt * 1000.0 if dt is not None and dt > 0.0 else None,
                request_to_paint_age_ms=self._active_request_to_paint_age_ms,
            )
        )
        self._active_paint_start_ts = None
        self._active_request_to_paint_age_ms = None
        return dt

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
        return ordered[index]

    def timing_summary(self) -> dict[str, float | int]:
        """Return bounded-window timing tails for the final perf summary."""
        intervals = [sample.paint_interval_ms for sample in self.samples if sample.paint_interval_ms is not None]
        durations = [sample.paint_duration_ms for sample in self.samples]
        ages = [sample.request_to_paint_age_ms for sample in self.samples if sample.request_to_paint_age_ms is not None]
        last_sample = self.samples[-1] if self.samples else None
        request_attempts = self.render_request_count + self.skipped_request_count
        return {
            "window_frames": len(self.samples),
            "requests": self.render_request_count,
            "skipped_requests": self.skipped_request_count,
            "request_acceptance_pct": (
                self.render_request_count / request_attempts * 100.0
                if request_attempts > 0
                else 0.0
            ),
            "last_presented_frame_index": (
                last_sample.frame_index if last_sample is not None else 0
            ),
            "last_scene_generation": (
                last_sample.scene_generation if last_sample is not None else 0
            ),
            "interval_p50_ms": self._percentile(intervals, 0.50),
            "interval_p90_ms": self._percentile(intervals, 0.90),
            "interval_p95_ms": self._percentile(intervals, 0.95),
            "interval_p99_ms": self._percentile(intervals, 0.99),
            "interval_max_ms": max(intervals, default=0.0),
            "interval_over_25_ms": sum(value > 25.0 for value in intervals),
            "interval_over_33_ms": sum(value > 33.0 for value in intervals),
            "interval_over_50_ms": sum(value > 50.0 for value in intervals),
            "interval_over_100_ms": sum(value > 100.0 for value in intervals),
            "duration_p50_ms": self._percentile(durations, 0.50),
            "duration_p90_ms": self._percentile(durations, 0.90),
            "duration_p95_ms": self._percentile(durations, 0.95),
            "duration_p99_ms": self._percentile(durations, 0.99),
            "duration_max_ms": max(durations, default=0.0),
            "request_age_p50_ms": self._percentile(ages, 0.50),
            "request_age_p90_ms": self._percentile(ages, 0.90),
            "request_age_p95_ms": self._percentile(ages, 0.95),
            "request_age_p99_ms": self._percentile(ages, 0.99),
            "request_age_max_ms": max(ages, default=0.0),
        }

    def elapsed_seconds(self) -> float:
        return max(0.0, time.perf_counter() - self.start_ts)

@dataclass
class _RenderTimerMetrics:
    """Telemetry for render timer cadence."""

    target_fps: int
    interval_ms: int
    stall_threshold_ms: float = 120.0
    stall_factor: float = 2.5
    start_ts: float = field(default_factory=time.time)
    last_tick_ts: Optional[float] = None
    frame_count: int = 0
    wakeup_count: int = 0
    pending_skip_count: int = 0
    min_dt: float = 0.0
    max_dt: float = 0.0
    stall_count: int = 0
    last_stall_log_ts: float = 0.0

    def record_tick(self, *, accepted_update: bool = True) -> Optional[float]:
        """Record a render wakeup and return accepted-update dt when available."""
        self.wakeup_count += 1
        if not accepted_update:
            self.pending_skip_count += 1
            return None

        now = time.time()
        dt = None
        if self.last_tick_ts is not None:
            dt = now - self.last_tick_ts
            if dt > 0.0:
                if self.min_dt == 0.0 or dt < self.min_dt:
                    self.min_dt = dt
                if dt > self.max_dt:
                    self.max_dt = dt
                threshold_ms = max(self.stall_threshold_ms, self.interval_ms * self.stall_factor)
                if dt * 1000.0 > threshold_ms:
                    self.stall_count += 1
        self.last_tick_ts = now
        self.frame_count += 1
        return dt

    def should_log_stall(self, dt_seconds: float, cooldown_s: float = 0.5) -> bool:
        """Return True when this tick gap should be logged as a stall."""
        threshold_ms = max(self.stall_threshold_ms, self.interval_ms * self.stall_factor)
        if dt_seconds * 1000.0 <= threshold_ms:
            return False
        now = time.time()
        if self.last_stall_log_ts and (now - self.last_stall_log_ts) < cooldown_s:
            return False
        self.last_stall_log_ts = now
        return True

    def elapsed_seconds(self) -> float:
        return max(0.0, time.time() - self.start_ts)
