"""Performance metrics dataclasses for GL compositor transitions.

These dataclasses track timing metrics for animations, paint operations,
and render timer cadence during compositor-driven transitions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


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
    peel_program: int = 0
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
    peel_uniforms: dict = field(default_factory=dict)
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
class _PaintMetrics:
    """Tracks paintGL cadence and duration for transitions."""

    label: str
    slow_threshold_ms: float
    start_ts: float = field(default_factory=time.time)
    last_paint_ts: Optional[float] = None
    frame_count: int = 0
    min_dt: float = 0.0
    max_dt: float = 0.0
    min_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    slow_count: int = 0

    def record(self, paint_duration_ms: float) -> Optional[float]:
        """Record a paint duration and return dt seconds when available."""
        now = time.time()
        dt = None
        if self.last_paint_ts is not None:
            dt = now - self.last_paint_ts
            if dt > 0.0:
                if self.min_dt == 0.0 or dt < self.min_dt:
                    self.min_dt = dt
                if dt > self.max_dt:
                    self.max_dt = dt
        self.last_paint_ts = now
        self.frame_count += 1
        if self.min_duration_ms == 0.0 or paint_duration_ms < self.min_duration_ms:
            self.min_duration_ms = paint_duration_ms
        if paint_duration_ms > self.max_duration_ms:
            self.max_duration_ms = paint_duration_ms
        if paint_duration_ms > self.slow_threshold_ms:
            self.slow_count += 1
        return dt

    def elapsed_seconds(self) -> float:
        return max(0.0, time.time() - self.start_ts)


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
    min_dt: float = 0.0
    max_dt: float = 0.0
    stall_count: int = 0
    last_stall_log_ts: float = 0.0

    def record_tick(self) -> Optional[float]:
        """Record a render timer tick and return dt seconds when available."""
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
