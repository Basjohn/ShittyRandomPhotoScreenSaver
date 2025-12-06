"""Frame interpolation for smooth animation rendering.

Decouples animation state updates from rendering by storing timestamped
progress values and interpolating to the actual render time. This eliminates
visual judder caused by timer callback jitter.

Architecture:
    Animation Thread: Animation.update() → writes (timestamp, progress) to FrameState
    Render Thread: paintGL() reads FrameState, interpolates to current time

The interpolator uses linear extrapolation based on the velocity between
the last two samples. When the animation is near completion (>95%), it
snaps to the target to avoid overshooting.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

from core.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FrameSample:
    """A single animation state sample."""
    timestamp: float  # time.time() when this sample was recorded
    progress: float   # 0.0 to 1.0 (already eased)


@dataclass
class FrameState:
    """Thread-safe animation state for interpolation.
    
    Stores the last two samples to compute velocity for extrapolation.
    The render thread reads the latest state and interpolates to the
    actual render time, smoothing out timer jitter.
    """
    
    # Last two samples for velocity calculation
    _prev: Optional[FrameSample] = None
    _curr: Optional[FrameSample] = None
    _lock: Lock = field(default_factory=Lock)
    
    # Animation metadata
    duration: float = 1.0
    started: bool = False
    completed: bool = False
    
    def push(self, progress: float) -> None:
        """Push a new progress sample (called from animation thread)."""
        now = time.time()
        with self._lock:
            self._prev = self._curr
            self._curr = FrameSample(timestamp=now, progress=progress)
            if not self.started:
                self.started = True
    
    def mark_complete(self) -> None:
        """Mark animation as complete."""
        with self._lock:
            self.completed = True
            # Ensure final progress is 1.0
            now = time.time()
            self._prev = self._curr
            self._curr = FrameSample(timestamp=now, progress=1.0)
    
    def reset(self) -> None:
        """Reset state for a new animation."""
        with self._lock:
            self._prev = None
            self._curr = None
            self.started = False
            self.completed = False
    
    def get_interpolated_progress(self, render_time: Optional[float] = None) -> float:
        """Get interpolated progress for the given render time.
        
        Uses linear extrapolation based on velocity between last two samples.
        Clamps result to [0, 1] and snaps to 1.0 when near completion.
        
        Args:
            render_time: Time to interpolate to (defaults to now)
            
        Returns:
            Interpolated progress value (0.0 to 1.0)
        """
        if render_time is None:
            render_time = time.time()
        
        with self._lock:
            if self.completed:
                return 1.0
            
            if self._curr is None:
                return 0.0
            
            curr = self._curr
            prev = self._prev
        
        # If we only have one sample, return it directly
        if prev is None:
            return max(0.0, min(1.0, curr.progress))
        
        # Calculate velocity (progress per second)
        dt = curr.timestamp - prev.timestamp
        if dt <= 0.0:
            return max(0.0, min(1.0, curr.progress))
        
        velocity = (curr.progress - prev.progress) / dt
        
        # Extrapolate to render time
        time_since_sample = render_time - curr.timestamp
        
        # Limit extrapolation to avoid wild overshoots
        # Max extrapolation: 100ms ahead (allows for timer jitter up to 100ms)
        time_since_sample = min(time_since_sample, 0.1)
        
        extrapolated = curr.progress + velocity * time_since_sample
        
        # Clamp to valid range
        result = max(0.0, min(1.0, extrapolated))
        
        # Snap to 1.0 when very close to avoid floating point issues
        if result > 0.995:
            result = 1.0
        
        return result


class FrameInterpolator:
    """Manages frame states for multiple animations.
    
    Each animation gets its own FrameState identified by a string key.
    The compositor creates a state when starting a transition and reads
    from it during paintGL().
    """
    
    def __init__(self) -> None:
        self._states: dict[str, FrameState] = {}
        self._lock = Lock()
    
    def create_state(self, key: str, duration: float = 1.0) -> FrameState:
        """Create a new frame state for an animation."""
        state = FrameState(duration=duration)
        with self._lock:
            self._states[key] = state
        return state
    
    def get_state(self, key: str) -> Optional[FrameState]:
        """Get the frame state for an animation."""
        with self._lock:
            return self._states.get(key)
    
    def remove_state(self, key: str) -> None:
        """Remove a frame state when animation completes."""
        with self._lock:
            self._states.pop(key, None)
    
    def get_interpolated_progress(self, key: str, render_time: Optional[float] = None) -> float:
        """Get interpolated progress for an animation.
        
        Convenience method that handles missing states gracefully.
        """
        state = self.get_state(key)
        if state is None:
            return 0.0
        return state.get_interpolated_progress(render_time)


# Global interpolator instance for the compositor
_global_interpolator: Optional[FrameInterpolator] = None


def get_frame_interpolator() -> FrameInterpolator:
    """Get the global frame interpolator instance."""
    global _global_interpolator
    if _global_interpolator is None:
        _global_interpolator = FrameInterpolator()
    return _global_interpolator
