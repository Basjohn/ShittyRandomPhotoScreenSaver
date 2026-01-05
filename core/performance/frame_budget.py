"""
Frame Budget System for coordinated frame timing.

Provides time budget allocation for different rendering systems
to prevent starvation and ensure smooth frame pacing.
"""
from __future__ import annotations

import gc
import time
import threading
from dataclasses import dataclass
from typing import Dict, Optional

from core.logging.logger import get_logger, is_perf_metrics_enabled

logger = get_logger(__name__)


@dataclass
class FrameBudgetConfig:
    """Configuration for frame budget allocation."""
    
    target_fps: int = 60
    frame_time_ms: float = 16.67  # 1000 / 60
    
    # Budget allocation (must sum to <= frame_time_ms)
    gl_render_budget_ms: float = 10.0      # 60% - GL rendering
    visualizer_budget_ms: float = 3.0      # 18% - Spotify visualizer
    image_load_budget_ms: float = 2.0      # 12% - Image loading
    other_budget_ms: float = 1.67          # 10% - Other operations
    
    # Thresholds
    overrun_threshold_ms: float = 5.0      # Log warning if overrun by this much
    spike_threshold_ms: float = 33.33      # 2 frames = spike
    
    def __post_init__(self):
        self.frame_time_ms = 1000.0 / self.target_fps


class FrameBudget:
    """
    Frame budget manager for coordinated rendering.
    
    Tracks time spent in different rendering phases and provides
    budget checking to prevent any single system from starving others.
    
    Thread Safety:
    - Uses lock for frame state access
    - Safe to call from multiple threads
    """
    
    # Budget categories
    CATEGORY_GL_RENDER = "gl_render"
    CATEGORY_VISUALIZER = "visualizer"
    CATEGORY_IMAGE_LOAD = "image_load"
    CATEGORY_OTHER = "other"
    
    def __init__(self, config: Optional[FrameBudgetConfig] = None):
        self._config = config or FrameBudgetConfig()
        self._lock = threading.Lock()
        
        # Current frame tracking
        self._frame_start: float = 0.0
        self._frame_number: int = 0
        self._category_times: Dict[str, float] = {}
        self._category_starts: Dict[str, float] = {}
        
        # Metrics
        self._total_frames: int = 0
        self._overrun_count: int = 0
        self._spike_count: int = 0
        self._last_frame_time_ms: float = 0.0
        self._max_frame_time_ms: float = 0.0
        self._min_frame_time_ms: float = float('inf')
        
        # Budget limits by category
        self._budgets = {
            self.CATEGORY_GL_RENDER: self._config.gl_render_budget_ms,
            self.CATEGORY_VISUALIZER: self._config.visualizer_budget_ms,
            self.CATEGORY_IMAGE_LOAD: self._config.image_load_budget_ms,
            self.CATEGORY_OTHER: self._config.other_budget_ms,
        }
    
    @property
    def target_fps(self) -> int:
        return self._config.target_fps
    
    @property
    def frame_time_ms(self) -> float:
        return self._config.frame_time_ms
    
    def reset_timing(self) -> None:
        """Reset frame timing to avoid false positives from idle gaps.
        
        Call this when a transition starts to prevent the first frame
        from measuring the entire idle gap as a 'spike'.
        """
        with self._lock:
            self._frame_start = 0.0
            self._category_times.clear()
            self._category_starts.clear()
    
    def begin_frame(self) -> None:
        """Mark the start of a new frame."""
        with self._lock:
            now = time.perf_counter()
            
            # Record previous frame metrics - only if we have a valid previous frame
            # Skip spike detection if frame_start is 0 (reset after idle period)
            if self._frame_start > 0:
                frame_time = (now - self._frame_start) * 1000.0
                self._last_frame_time_ms = frame_time
                self._max_frame_time_ms = max(self._max_frame_time_ms, frame_time)
                self._min_frame_time_ms = min(self._min_frame_time_ms, frame_time)
                
                if frame_time > self._config.frame_time_ms + self._config.overrun_threshold_ms:
                    self._overrun_count += 1
                
                # Only log spikes for frames within reasonable range (< 500ms)
                # Larger gaps are idle time between transitions, not actual spikes
                if frame_time > self._config.spike_threshold_ms and frame_time < 500.0:
                    self._spike_count += 1
                    if is_perf_metrics_enabled():
                        logger.warning(
                            "[PERF] [FRAME] Frame spike: %.1fms (target: %.1fms)",
                            frame_time, self._config.frame_time_ms
                        )
            
            self._frame_start = now
            self._frame_number += 1
            self._total_frames += 1
            self._category_times.clear()
            self._category_starts.clear()
    
    def begin_category(self, category: str) -> None:
        """Mark the start of a budget category."""
        with self._lock:
            self._category_starts[category] = time.perf_counter()
    
    def end_category(self, category: str) -> float:
        """
        Mark the end of a budget category.
        
        Returns:
            Time spent in category (ms)
        """
        with self._lock:
            start = self._category_starts.get(category)
            if start is None:
                return 0.0
            
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self._category_times[category] = self._category_times.get(category, 0.0) + elapsed_ms
            
            # Check budget
            budget = self._budgets.get(category, self._config.other_budget_ms)
            if elapsed_ms > budget + self._config.overrun_threshold_ms:
                if is_perf_metrics_enabled():
                    logger.debug(
                        "[PERF] [FRAME] %s overrun: %.1fms (budget: %.1fms)",
                        category, elapsed_ms, budget
                    )
            
            return elapsed_ms
    
    def check_budget(self, category: str) -> bool:
        """
        Check if category is within budget.
        
        Returns:
            True if within budget, False if overrun
        """
        with self._lock:
            spent = self._category_times.get(category, 0.0)
            budget = self._budgets.get(category, self._config.other_budget_ms)
            return spent <= budget
    
    def get_remaining_budget(self, category: str) -> float:
        """
        Get remaining budget for category (ms).
        
        Returns:
            Remaining time in ms (can be negative if overrun)
        """
        with self._lock:
            spent = self._category_times.get(category, 0.0)
            budget = self._budgets.get(category, self._config.other_budget_ms)
            return budget - spent
    
    def get_frame_elapsed(self) -> float:
        """Get elapsed time since frame start (ms)."""
        with self._lock:
            if self._frame_start <= 0:
                return 0.0
            return (time.perf_counter() - self._frame_start) * 1000.0
    
    def get_frame_remaining(self) -> float:
        """Get remaining time in frame budget (ms)."""
        return self._config.frame_time_ms - self.get_frame_elapsed()
    
    def should_skip_work(self) -> bool:
        """
        Check if frame budget is exhausted and work should be skipped.
        
        Returns:
            True if frame budget is exhausted
        """
        return self.get_frame_remaining() < 1.0  # Less than 1ms remaining
    
    def get_metrics(self) -> Dict[str, float]:
        """Get frame budget metrics."""
        with self._lock:
            return {
                "total_frames": self._total_frames,
                "overrun_count": self._overrun_count,
                "spike_count": self._spike_count,
                "last_frame_ms": self._last_frame_time_ms,
                "max_frame_ms": self._max_frame_time_ms,
                "min_frame_ms": self._min_frame_time_ms if self._min_frame_time_ms != float('inf') else 0.0,
                "target_fps": self._config.target_fps,
            }
    
    def log_metrics(self) -> None:
        """Log frame budget metrics."""
        if not is_perf_metrics_enabled():
            return
        
        metrics = self.get_metrics()
        logger.info(
            "[PERF] [FRAME] Budget metrics: frames=%d, overruns=%d, spikes=%d, "
            "last=%.1fms, max=%.1fms, min=%.1fms, target=%dfps",
            metrics["total_frames"],
            metrics["overrun_count"],
            metrics["spike_count"],
            metrics["last_frame_ms"],
            metrics["max_frame_ms"],
            metrics["min_frame_ms"],
            metrics["target_fps"],
        )


class GCController:
    """
    Garbage collection controller for frame-aware GC.
    
    Disables GC during frame rendering and runs it during idle periods.
    """
    
    def __init__(self, idle_threshold_ms: float = 100.0):
        self._idle_threshold_ms = idle_threshold_ms
        self._gc_disabled = False
        self._last_gc_time: float = 0.0
        self._gc_interval_s: float = 5.0  # Run GC at most every 5 seconds
        self._lock = threading.Lock()
        
        # Store original thresholds
        self._original_thresholds = gc.get_threshold()
        
        # Set higher thresholds to reduce GC frequency
        # Default is (700, 10, 10) - we increase to reduce frequency
        gc.set_threshold(10000, 50, 50)
        
        logger.debug("GCController initialized with thresholds: %s", gc.get_threshold())
    
    def disable_gc(self) -> None:
        """Disable GC for frame rendering."""
        with self._lock:
            if not self._gc_disabled:
                gc.disable()
                self._gc_disabled = True
    
    def enable_gc(self) -> None:
        """Re-enable GC after frame rendering."""
        with self._lock:
            if self._gc_disabled:
                gc.enable()
                self._gc_disabled = False
    
    def run_idle_gc(self, idle_time_ms: float) -> bool:
        """
        Run GC if idle time is sufficient.
        
        Args:
            idle_time_ms: Available idle time
            
        Returns:
            True if GC was run
        """
        if idle_time_ms < self._idle_threshold_ms:
            return False
        
        now = time.time()
        with self._lock:
            if now - self._last_gc_time < self._gc_interval_s:
                return False
            
            # Run only gen-0 collection (fast)
            self.enable_gc()
            start = time.perf_counter()
            collected = gc.collect(generation=0)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            
            self._last_gc_time = now
            
            if is_perf_metrics_enabled() and collected > 0:
                logger.debug(
                    "[PERF] [GC] Idle collection: %d objects in %.1fms",
                    collected, elapsed_ms
                )
            
            return True
    
    def restore_defaults(self) -> None:
        """Restore default GC settings."""
        with self._lock:
            gc.set_threshold(*self._original_thresholds)
            self.enable_gc()


# Global instances
_frame_budget: Optional[FrameBudget] = None
_gc_controller: Optional[GCController] = None


def get_frame_budget() -> FrameBudget:
    """Get the global FrameBudget instance."""
    global _frame_budget
    if _frame_budget is None:
        _frame_budget = FrameBudget()
    return _frame_budget


def get_gc_controller() -> GCController:
    """Get the global GCController instance."""
    global _gc_controller
    if _gc_controller is None:
        _gc_controller = GCController()
    return _gc_controller
