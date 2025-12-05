"""Centralized profiling helper for GL compositor transitions.

Replaces the per-transition profiling fields in GLCompositorWidget with a
single reusable profiler that tracks frame timing and emits PERF logs.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Environment variable to enable PERF metrics logging
PERF_METRICS_ENABLED = os.environ.get("SRPSS_PERF_METRICS", "0") == "1"


@dataclass
class TransitionProfile:
    """Per-transition profiling state."""
    
    start_ts: Optional[float] = None
    last_ts: Optional[float] = None
    frame_count: int = 0
    min_dt: float = 0.0
    max_dt: float = 0.0


class TransitionProfiler:
    """Centralized profiler for GL compositor transitions.
    
    Usage:
        profiler = TransitionProfiler()
        
        # On transition start:
        profiler.start("peel")
        
        # On each frame:
        profiler.tick("peel")
        
        # On transition complete:
        profiler.complete("peel")
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
    
    def complete(self, name: str) -> None:
        """Complete profiling and emit PERF log."""
        profile = self._profiles.pop(name, None)
        if profile is None:
            return
        
        if not PERF_METRICS_ENABLED:
            return
        
        if profile.start_ts is None:
            return
        
        total_time = time.time() - profile.start_ts
        frame_count = profile.frame_count
        
        if frame_count > 0:
            avg_dt = total_time / frame_count
            avg_fps = 1.0 / avg_dt if avg_dt > 0 else 0.0
        else:
            avg_dt = 0.0
            avg_fps = 0.0
        
        min_fps = 1.0 / profile.max_dt if profile.max_dt > 0 else 0.0
        max_fps = 1.0 / profile.min_dt if profile.min_dt > 0 else 0.0
        
        logger.info(
            "[PERF] [GL COMPOSITOR] %s metrics: frames=%d, total=%.3fs, "
            "avg_dt=%.4fs (%.1f fps), min_dt=%.4fs (%.1f fps), max_dt=%.4fs (%.1f fps)",
            name.capitalize(),
            frame_count,
            total_time,
            avg_dt,
            avg_fps,
            profile.min_dt,
            max_fps,
            profile.max_dt,
            min_fps,
        )
    
    def reset(self, name: str) -> None:
        """Reset profiling state for a transition without logging."""
        self._profiles.pop(name, None)
    
    def is_active(self, name: str) -> bool:
        """Check if a transition is currently being profiled."""
        return name in self._profiles
