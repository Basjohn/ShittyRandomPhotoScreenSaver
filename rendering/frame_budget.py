"""Frame budget enforcement for smooth 60 FPS rendering.

This module provides frame timing tracking and budget enforcement to prevent
frame spikes during transitions and heavy rendering operations.
"""

from __future__ import annotations

import time
from typing import Optional
from dataclasses import dataclass

from core.logging.logger import get_logger, is_perf_metrics_enabled

logger = get_logger(__name__)


@dataclass
class FrameBudget:
    """Frame budget configuration and tracking."""
    
    target_fps: int = 60
    budget_ms: float = 16.67  # 1000ms / 60fps
    warning_threshold_ms: float = 20.0  # Warn if frame takes >20ms
    
    # Tracking
    frame_start_time: float = 0.0
    last_frame_time: float = 0.0
    frame_count: int = 0
    spike_count: int = 0
    
    # Budget enforcement
    budget_exceeded: bool = False
    defer_heavy_work: bool = False


class FrameBudgetTracker:
    """Tracks frame timing and enforces budget constraints.
    
    Usage:
        tracker = FrameBudgetTracker(target_fps=60)
        
        # At frame start
        tracker.begin_frame()
        
        # Check if we should defer heavy work
        if not tracker.should_defer_work():
            do_expensive_operation()
        
        # At frame end
        tracker.end_frame()
    """
    
    def __init__(self, target_fps: int = 60):
        """Initialize frame budget tracker.
        
        Args:
            target_fps: Target frames per second (default: 60)
        """
        self.target_fps = target_fps
        self.budget_ms = 1000.0 / target_fps
        self.warning_threshold_ms = self.budget_ms * 1.2  # 20% over budget
        
        self._frame_start_time: float = 0.0
        self._last_frame_time: float = 0.0
        self._frame_count: int = 0
        self._spike_count: int = 0
        
        # Budget enforcement state
        self._budget_exceeded: bool = False
        self._defer_heavy_work: bool = False
        
        # Rolling average for adaptive thresholds
        self._recent_frame_times: list[float] = []
        self._max_recent_samples: int = 10
        
    def begin_frame(self) -> None:
        """Mark the start of a new frame."""
        self._frame_start_time = time.perf_counter()
        self._budget_exceeded = False
        self._defer_heavy_work = False
        
    def end_frame(self) -> None:
        """Mark the end of a frame and update statistics."""
        if self._frame_start_time == 0.0:
            return
            
        frame_end_time = time.perf_counter()
        frame_duration_ms = (frame_end_time - self._frame_start_time) * 1000.0
        
        self._last_frame_time = frame_duration_ms
        self._frame_count += 1
        
        # Update rolling average
        self._recent_frame_times.append(frame_duration_ms)
        if len(self._recent_frame_times) > self._max_recent_samples:
            self._recent_frame_times.pop(0)
        
        # Check for budget violations
        if frame_duration_ms > self.budget_ms:
            self._budget_exceeded = True
            
            if frame_duration_ms > self.warning_threshold_ms:
                self._spike_count += 1
                
                if is_perf_metrics_enabled():
                    logger.warning(
                        "[PERF] [FRAME_BUDGET] Frame spike: %.1fms (budget: %.1fms, target: %d FPS)",
                        frame_duration_ms,
                        self.budget_ms,
                        self.target_fps,
                    )
        
        # Reset frame start time
        self._frame_start_time = 0.0
        
    def check_budget_remaining(self) -> float:
        """Check how much frame budget remains in milliseconds.
        
        Returns:
            Remaining budget in ms (negative if over budget)
        """
        if self._frame_start_time == 0.0:
            return self.budget_ms
            
        elapsed_ms = (time.perf_counter() - self._frame_start_time) * 1000.0
        return self.budget_ms - elapsed_ms
        
    def should_defer_work(self, work_estimate_ms: float = 5.0) -> bool:
        """Check if heavy work should be deferred to next frame.
        
        Args:
            work_estimate_ms: Estimated time for the work in milliseconds
            
        Returns:
            True if work should be deferred, False if it can proceed
        """
        remaining = self.check_budget_remaining()
        
        # If we have less than the estimated work time remaining, defer
        if remaining < work_estimate_ms:
            self._defer_heavy_work = True
            
            if is_perf_metrics_enabled():
                logger.debug(
                    "[PERF] [FRAME_BUDGET] Deferring work (remaining: %.1fms, estimate: %.1fms)",
                    remaining,
                    work_estimate_ms,
                )
            
            return True
            
        return False
        
    def get_average_frame_time(self) -> float:
        """Get average frame time from recent samples.
        
        Returns:
            Average frame time in milliseconds
        """
        if not self._recent_frame_times:
            return 0.0
        return sum(self._recent_frame_times) / len(self._recent_frame_times)
        
    def get_statistics(self) -> dict[str, float]:
        """Get frame timing statistics.
        
        Returns:
            Dictionary with timing statistics
        """
        avg_frame_time = self.get_average_frame_time()
        avg_fps = 1000.0 / avg_frame_time if avg_frame_time > 0 else 0.0
        
        return {
            "frame_count": self._frame_count,
            "spike_count": self._spike_count,
            "last_frame_ms": self._last_frame_time,
            "avg_frame_ms": avg_frame_time,
            "avg_fps": avg_fps,
            "budget_ms": self.budget_ms,
            "target_fps": self.target_fps,
        }
        
    def reset_statistics(self) -> None:
        """Reset all statistics counters."""
        self._frame_count = 0
        self._spike_count = 0
        self._recent_frame_times.clear()
        
    def log_statistics(self) -> None:
        """Log current frame timing statistics."""
        if not is_perf_metrics_enabled():
            return
            
        stats = self.get_statistics()
        logger.info(
            "[PERF] [FRAME_BUDGET] Stats: frames=%d, spikes=%d, avg_fps=%.1f, avg_ms=%.1fms, budget=%.1fms",
            stats["frame_count"],
            stats["spike_count"],
            stats["avg_fps"],
            stats["avg_frame_ms"],
            stats["budget_ms"],
        )
