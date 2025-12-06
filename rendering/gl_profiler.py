"""Centralized profiling helper for GL compositor transitions.

Replaces the per-transition profiling fields in GLCompositorWidget with a
single reusable profiler that tracks frame timing and emits PERF logs.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Environment variable to enable PERF metrics logging
PERF_METRICS_ENABLED = os.environ.get("SRPSS_PERF_METRICS", "0") == "1"


def is_perf_metrics_enabled() -> bool:
    """Check if PERF metrics are enabled via environment variable."""
    return PERF_METRICS_ENABLED


@dataclass
class TransitionProfile:
    """Per-transition profiling state."""
    
    start_ts: Optional[float] = None
    last_ts: Optional[float] = None
    frame_count: int = 0
    min_dt: float = 0.0
    max_dt: float = 0.0
    # Paint timing (separate from animation tick timing)
    last_paint_ts: Optional[float] = None
    paint_count: int = 0
    paint_min_dt: float = 0.0
    paint_max_dt: float = 0.0
    # Optional GPU timing (per-frame GPU duration in milliseconds). Only
    # populated when the caller records GPU samples explicitly; otherwise
    # these remain zero and are omitted from logs.
    gpu_sample_count: int = 0
    gpu_total_ms: float = 0.0
    gpu_min_ms: float = 0.0
    gpu_max_ms: float = 0.0


class TransitionProfiler:
    """Centralized profiler for GL compositor transitions.
    
    Usage:
        profiler = TransitionProfiler()
        
        # On transition start:
        profiler.start("peel")
        
        # On each frame:
        profiler.tick("peel")
        
        # On transition complete:
        profiler.complete("peel", viewport_size=(1920, 1080))
        
        # For debug overlay:
        metrics = profiler.get_metrics("peel")
    """
    
    def __init__(self) -> None:
        self._profiles: Dict[str, TransitionProfile] = {}
    
    def start(self, name: str) -> None:
        """Start profiling a transition."""
        self._profiles[name] = TransitionProfile(
            start_ts=time.time(),
            last_ts=None,
            frame_count=0,
            min_dt=0.0,
            max_dt=0.0,
            last_paint_ts=None,
            paint_count=0,
            paint_min_dt=0.0,
            paint_max_dt=0.0,
        )
    
    def tick(self, name: str) -> None:
        """Record a frame tick for a transition."""
        profile = self._profiles.get(name)
        if profile is None:
            return
        
        now = time.time()
        profile.frame_count += 1
        
        if profile.last_ts is not None:
            dt = now - profile.last_ts
            if profile.min_dt == 0.0 or dt < profile.min_dt:
                profile.min_dt = dt
            if dt > profile.max_dt:
                profile.max_dt = dt
        
        profile.last_ts = now
    
    def tick_paint(self, name: str) -> None:
        """Record a paint tick for a transition (called from paintGL)."""
        profile = self._profiles.get(name)
        if profile is None:
            return
        
        now = time.time()
        profile.paint_count += 1
        
        if profile.last_paint_ts is not None:
            dt = now - profile.last_paint_ts
            if profile.paint_min_dt == 0.0 or dt < profile.paint_min_dt:
                profile.paint_min_dt = dt
            if dt > profile.paint_max_dt:
                profile.paint_max_dt = dt
        
        profile.last_paint_ts = now
    
    def tick_gpu(self, name: str, gpu_time_ms: float) -> None:
        """Record a GPU timing sample for a transition.

        The compositor is expected to measure GPU time (for example via
        GL timer queries or a `glFinish()`-bounded span) and call this with
        the elapsed duration in milliseconds. When no GPU samples are
        recorded, GPU metrics remain zero and are omitted from logs.
        """
        profile = self._profiles.get(name)
        if profile is None:
            return
        # Ignore obviously invalid samples to keep metrics robust.
        try:
            value = float(gpu_time_ms)
        except Exception:
            return
        if value <= 0.0:
            return

        profile.gpu_sample_count += 1
        profile.gpu_total_ms += value
        if profile.gpu_min_ms == 0.0 or value < profile.gpu_min_ms:
            profile.gpu_min_ms = value
        if value > profile.gpu_max_ms:
            profile.gpu_max_ms = value
    
    def get_metrics(self, name: str) -> Optional[Tuple[float, float, float, float]]:
        """Get current metrics for debug overlay.
        
        Returns:
            Tuple of (avg_fps, min_dt_ms, max_dt_ms, elapsed_ms) or None if not active.
        """
        profile = self._profiles.get(name)
        if profile is None or profile.start_ts is None or profile.last_ts is None:
            return None
        if profile.frame_count <= 0:
            return None
        
        elapsed = profile.last_ts - profile.start_ts
        if elapsed <= 0:
            return None
        
        avg_fps = profile.frame_count / elapsed
        min_dt_ms = profile.min_dt * 1000.0 if profile.min_dt > 0 else 0.0
        max_dt_ms = profile.max_dt * 1000.0 if profile.max_dt > 0 else 0.0
        elapsed_ms = elapsed * 1000.0
        
        return (avg_fps, min_dt_ms, max_dt_ms, elapsed_ms)
    
    def complete(self, name: str, viewport_size: Optional[Tuple[int, int]] = None) -> None:
        """Complete profiling and emit PERF log.
        
        Args:
            name: Transition name
            viewport_size: Optional (width, height) for log output
        """
        profile = self._profiles.pop(name, None)
        if profile is None:
            return
        
        if not PERF_METRICS_ENABLED:
            return
        
        if profile.start_ts is None:
            return
        
        total_time = time.time() - profile.start_ts
        frame_count = profile.frame_count
        
        if frame_count > 0 and total_time > 0:
            avg_fps = frame_count / total_time
        else:
            avg_fps = 0.0
        
        duration_ms = total_time * 1000.0
        min_dt_ms = profile.min_dt * 1000.0 if profile.min_dt > 0 else 0.0
        max_dt_ms = profile.max_dt * 1000.0 if profile.max_dt > 0 else 0.0
        
        # Paint timing metrics
        paint_count = profile.paint_count
        paint_min_dt_ms = profile.paint_min_dt * 1000.0 if profile.paint_min_dt > 0 else 0.0
        paint_max_dt_ms = profile.paint_max_dt * 1000.0 if profile.paint_max_dt > 0 else 0.0
        paint_avg_fps = paint_count / total_time if paint_count > 0 and total_time > 0 else 0.0
        
        # Optional GPU metrics (only populated when the compositor records
        # GPU samples via tick_gpu()).
        gpu_samples = getattr(profile, "gpu_sample_count", 0)
        if gpu_samples and total_time > 0:
            gpu_avg_ms = profile.gpu_total_ms / float(gpu_samples)
        else:
            gpu_avg_ms = 0.0
        gpu_min_ms = getattr(profile, "gpu_min_ms", 0.0)
        gpu_max_ms = getattr(profile, "gpu_max_ms", 0.0)
        
        if viewport_size:
            logger.info(
                "[PERF] [GL COMPOSITOR] %s metrics: duration=%.1fms, frames=%d, "
                "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, "
                "paint_fps=%.1f, paint_dt_max=%.2fms, "
                "gpu_avg=%.2fms, gpu_dt_min=%.2fms, gpu_dt_max=%.2fms, "
                "size=%dx%d",
                name.capitalize(),
                duration_ms,
                frame_count,
                avg_fps,
                min_dt_ms,
                max_dt_ms,
                paint_avg_fps,
                paint_max_dt_ms,
                gpu_avg_ms,
                gpu_min_ms,
                gpu_max_ms,
                viewport_size[0],
                viewport_size[1],
            )
        else:
            logger.info(
                "[PERF] [GL COMPOSITOR] %s metrics: duration=%.1fms, frames=%d, "
                "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, "
                "paint_fps=%.1f, paint_dt_max=%.2fms, "
                "gpu_avg=%.2fms, gpu_dt_min=%.2fms, gpu_dt_max=%.2fms",
                name.capitalize(),
                duration_ms,
                frame_count,
                avg_fps,
                min_dt_ms,
                max_dt_ms,
                paint_avg_fps,
                paint_max_dt_ms,
                gpu_avg_ms,
                gpu_min_ms,
                gpu_max_ms,
            )
    
    def reset(self, name: str) -> None:
        """Reset profiling state for a transition without logging."""
        self._profiles.pop(name, None)
    
    def is_active(self, name: str) -> bool:
        """Check if a transition is currently being profiled."""
        return name in self._profiles
    
    def get_active_transition(self) -> Optional[str]:
        """Get the name of the currently active transition, if any."""
        for name in self._profiles:
            return name
        return None
