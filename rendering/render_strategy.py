"""Render strategy abstraction for timer-based rendering.

This module provides timer-based rendering for the compositor.
VSync is completely disabled - we use timer for maximum performance.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import Future
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

from core.logging.logger import get_logger
from core.threading.manager import ThreadManager, ThreadPoolType
from core.resources.manager import ResourceManager
from utils.lockfree.spsc_queue import SPSCQueue

if TYPE_CHECKING:
    from rendering.gl_compositor import GLCompositorWidget

logger = get_logger(__name__)


class RenderStrategyType(Enum):
    """Available render strategy types."""
    TIMER = "timer"      # QTimer-based (only strategy, VSync disabled)


@dataclass
class RenderStrategyConfig:
    """Configuration for render strategies."""
    target_fps: int = 60
    fallback_on_failure: bool = True
    min_frame_time_ms: float = 8.0  # Minimum time between frames


@dataclass 
class RenderMetrics:
    """Metrics for render strategy performance."""
    strategy_type: RenderStrategyType
    frame_count: int = 0
    start_ts: float = field(default_factory=time.time)
    min_dt_ms: float = 0.0
    max_dt_ms: float = 0.0
    last_frame_ts: float = 0.0
    fallback_count: int = 0
    
    def record_frame(self) -> float:
        """Record a frame and return dt in ms."""
        now = time.time()
        dt_ms = 0.0
        if self.last_frame_ts > 0:
            dt_ms = (now - self.last_frame_ts) * 1000.0
            if self.min_dt_ms == 0.0 or dt_ms < self.min_dt_ms:
                self.min_dt_ms = dt_ms
            if dt_ms > self.max_dt_ms:
                self.max_dt_ms = dt_ms
        self.last_frame_ts = now
        self.frame_count += 1
        return dt_ms
    
    def get_avg_fps(self) -> float:
        """Get average FPS."""
        elapsed = time.time() - self.start_ts
        if elapsed > 0:
            return self.frame_count / elapsed
        return 0.0

    def to_dict(self) -> dict:
        """Serialize metrics for logging/debugging."""
        return {
            "frames": self.frame_count,
            "avg_fps": round(self.get_avg_fps(), 2),
            "dt_min_ms": round(self.min_dt_ms, 2),
            "dt_max_ms": round(self.max_dt_ms, 2),
            "strategy": self.strategy_type.value,
            "fallbacks": self.fallback_count,
        }


class RenderStrategy(ABC):
    """Abstract base class for render strategies.
    
    Render strategies control how and when the compositor triggers repaints.
    Strategies must be thread-safe as they may be accessed from multiple threads.
    """
    
    def __init__(self, compositor: "GLCompositorWidget", config: RenderStrategyConfig):
        self._compositor = compositor
        self._config = config
        self._active = False
        self._metrics = RenderMetrics(strategy_type=self.strategy_type)
        self._lock = threading.Lock()
    
    @property
    def config(self) -> RenderStrategyConfig:
        """Return the active configuration for this strategy."""
        return self._config
    
    @property
    @abstractmethod
    def strategy_type(self) -> RenderStrategyType:
        """Return the strategy type."""
        pass
    
    @abstractmethod
    def start(self) -> bool:
        """Start the render strategy. Returns True on success."""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop the render strategy."""
        pass
    
    @abstractmethod
    def request_frame(self) -> None:
        """Request a frame to be rendered."""
        pass
    
    def is_active(self) -> bool:
        """Check if strategy is currently active."""
        with self._lock:
            return self._active
    
    def get_metrics(self) -> RenderMetrics:
        """Get current render metrics."""
        with self._lock:
            return self._metrics


class TimerRenderStrategy(RenderStrategy):
    """Timer-based rendering using ThreadManager with lock-free coordination.
    
    Uses ThreadManager COMPUTE pool for timing thread, SPSCQueue for
    frame request coalescing, and atomic Event for stop signaling.
    Integrates with ResourceManager for proper lifecycle tracking.
    """
    
    def __init__(self, compositor: "GLCompositorWidget", config: RenderStrategyConfig):
        super().__init__(compositor, config)
        self._stop_event = threading.Event()
        self._frame_queue: SPSCQueue[bool] = SPSCQueue(4)
        self._task_future: Optional[Future] = None
        self._thread_manager: Optional[ThreadManager] = None
        self._resource_manager: Optional[ResourceManager] = None
        self._timer_resource_id: Optional[str] = None
        
        # Try to get managers from compositor's context
        try:
            parent = getattr(compositor, 'parent', lambda: None)()
            if parent is not None:
                self._thread_manager = getattr(parent, '_thread_manager', None)
                self._resource_manager = getattr(parent, '_resource_manager', None)
        except Exception:
            pass
    
    @property
    def strategy_type(self) -> RenderStrategyType:
        return RenderStrategyType.TIMER
    
    def start(self) -> bool:
        """Start timer-based rendering using ThreadManager."""
        with self._lock:
            if self._active:
                return True
            
            if self._thread_manager is None:
                logger.error("[RENDER] Cannot start: ThreadManager not available")
                return False
            
            try:
                interval_ms = max(1, 1000 // self._config.target_fps)
                self._stop_event.clear()
                self._frame_queue.clear()
                
                # Submit timing loop to ThreadManager COMPUTE pool
                self._task_future = self._thread_manager.submit_task(
                    ThreadPoolType.COMPUTE,
                    self._timer_loop,
                    interval_ms,
                    task_id=f"timer_{id(self)}"
                )
                
                # Register with ResourceManager for cleanup tracking
                # NOTE: No cleanup_handler - stop() manages lifecycle to avoid circular calls
                if self._resource_manager is not None:
                    try:
                        from core.resources.types import ResourceType
                        self._timer_resource_id = self._resource_manager.register(
                            self,
                            ResourceType.TIMER,
                            f"Render timer (interval={interval_ms}ms)",
                        )
                    except Exception as e:
                        logger.debug("[RENDER] Could not register timer with ResourceManager: %s", e)
                
                self._active = True
                self._metrics = RenderMetrics(strategy_type=self.strategy_type)
                logger.info("[RENDER] Timer started (interval=%dms, target=%dHz, tm=True)",
                           interval_ms, self._config.target_fps)
                return True
                
            except Exception as e:
                logger.error("[RENDER] Failed to start timer: %s", e)
                return False
    
    def _timer_loop(self, interval_ms: int) -> None:
        """High-precision timing loop running in ThreadManager pool."""
        target_interval = interval_ms / 1000.0
        sleep_threshold = 0.002
        
        logger.debug("[RENDER] Timer loop started: target=%.2fms", interval_ms)
        
        while not self._stop_event.is_set():
            try:
                # Check for immediate frame requests (coalesced)
                has_request = False
                while True:
                    ok, _ = self._frame_queue.try_pop()
                    if not ok:
                        break
                    has_request = True
                
                if has_request:
                    self._signal_frame()
                    continue
                
                # Precise timing
                start_ts = time.perf_counter()
                
                # Sleep for most of interval
                if target_interval > sleep_threshold:
                    time.sleep(target_interval - sleep_threshold)
                
                # Busy-wait for precision
                while time.perf_counter() - start_ts < target_interval:
                    if self._stop_event.is_set():
                        break
                    pass
                
                if not self._stop_event.is_set():
                    self._signal_frame()
                    
            except Exception as e:
                logger.error("[RENDER] Timer loop error: %s", e)
                break
        
        logger.debug("[RENDER] Timer loop stopped")
    
    def _signal_frame(self) -> None:
        """Signal UI thread to render using ThreadManager."""
        if self._compositor is not None:
            try:
                ThreadManager.run_on_ui_thread(
                    self._compositor.update
                )
            except Exception:
                pass
    
    def stop(self) -> None:
        """Stop timer and cleanup - non-blocking to avoid deadlocks."""
        with self._lock:
            # Signal stop first
            self._stop_event.set()
            
            # Clear task reference without blocking wait
            # Thread will exit naturally when it checks _stop_event
            self._task_future = None
            
            # Unregister from ResourceManager
            if self._timer_resource_id and self._resource_manager:
                try:
                    self._resource_manager.unregister(self._timer_resource_id)
                except Exception:
                    pass
                self._timer_resource_id = None
            
            self._active = False
            self._log_final_metrics()
    
    def _log_final_metrics(self) -> None:
        """Log final metrics when stopping."""
        m = self._metrics
        logger.info(
            "[PERF] [RENDER] Timer stopped: frames=%d, avg_fps=%.1f, "
            "dt_min=%.1fms, dt_max=%.1fms",
            m.frame_count, m.get_avg_fps(), m.min_dt_ms, m.max_dt_ms
        )
    
    def request_frame(self) -> None:
        """Queue immediate frame request (coalesced)."""
        self._frame_queue.push_drop_oldest(True)

    def describe_state(self) -> dict:
        """Return current timer diagnostics."""
        with self._lock:
            return {
                "active": self._active,
                "stop_event": self._stop_event.is_set(),
                "resource_id": self._timer_resource_id,
                "frames": self._metrics.frame_count,
            }


class RenderStrategyManager:
    """Manager for switching between render strategies.
    
    Provides:
    - Strategy selection based on configuration
    - Runtime strategy switching
    - Automatic fallback handling
    - Feature flag integration
    """
    
    def __init__(self, compositor: "GLCompositorWidget"):
        self._compositor = compositor
        self._config = RenderStrategyConfig()
        self._current_strategy: Optional[RenderStrategy] = None
        self._lock = threading.Lock()
    
    def configure(self, config: RenderStrategyConfig) -> None:
        """Update configuration."""
        with self._lock:
            self._config = config
    
    def start(self, strategy_type: Optional[RenderStrategyType] = None) -> bool:
        """Start rendering with timer strategy (only option, VSync disabled)."""
        with self._lock:
            if self._current_strategy is not None:
                self._current_strategy.stop()
            
            # Always use timer strategy (VSync completely disabled)
            if strategy_type is None:
                strategy_type = RenderStrategyType.TIMER
            
            # Create and start timer strategy
            self._current_strategy = TimerRenderStrategy(self._compositor, self._config)
            
            return self._current_strategy.start()
    
    def stop(self) -> None:
        """Stop current render strategy."""
        with self._lock:
            if self._current_strategy is not None:
                self._current_strategy.stop()
                self._current_strategy = None
    
    def switch_strategy(self, strategy_type: RenderStrategyType) -> bool:
        """Switch to a different render strategy at runtime."""
        logger.info("[RENDER] Switching to %s strategy", strategy_type.value)
        self.stop()
        return self.start(strategy_type)
    
    def request_frame(self) -> None:
        """Request a frame from current strategy."""
        with self._lock:
            if self._current_strategy is not None:
                self._current_strategy.request_frame()
    
    def is_running(self) -> bool:
        """Check if a strategy is currently active and running."""
        with self._lock:
            if self._current_strategy is not None:
                return self._current_strategy.is_active()
            return False
    
    def get_current_strategy_type(self) -> Optional[RenderStrategyType]:
        """Get the current strategy type."""
        with self._lock:
            if self._current_strategy is not None:
                return self._current_strategy.strategy_type
            return None
    
    def get_metrics(self) -> Optional[RenderMetrics]:
        """Get metrics from current strategy."""
        with self._lock:
            if self._current_strategy is not None:
                return self._current_strategy.get_metrics()
            return None

    def describe_state(self) -> dict:
        """Return lightweight debug info about the active strategy."""
        with self._lock:
            strategy_type = self._current_strategy.strategy_type if self._current_strategy else None
            return {
                "strategy": strategy_type.value if strategy_type else None,
                "running": self._current_strategy.is_active() if self._current_strategy else False,
                "metrics": self._current_strategy.get_metrics().to_dict() if (self._current_strategy and self._current_strategy.get_metrics()) else None,
                "timer": getattr(self._current_strategy, "describe_state", lambda: None)(),
            }
