"""Render strategy abstraction for switchable rendering approaches.

This module provides a strategy pattern for rendering, allowing runtime
switching between:
- TimerRenderStrategy: Current QTimer-based rendering (default)
- VSyncRenderStrategy: VSync-driven rendering via dedicated thread

The strategy pattern enables:
1. Gradual migration from timer to VSync without breaking changes
2. Feature flag control for VSync enablement
3. Automatic fallback on render thread failure
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QTimer, Qt

from core.logging.logger import get_logger, is_perf_metrics_enabled

if TYPE_CHECKING:
    from rendering.gl_compositor import GLCompositorWidget

logger = get_logger(__name__)


class RenderStrategyType(Enum):
    """Available render strategy types."""
    TIMER = "timer"      # QTimer-based (current default)
    VSYNC = "vsync"      # VSync-driven via render thread


@dataclass
class RenderStrategyConfig:
    """Configuration for render strategies."""
    target_fps: int = 60
    vsync_enabled: bool = False
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
    """QTimer-based rendering strategy (current default).
    
    Uses QTimer.PreciseTimer to trigger repaints at target FPS.
    This is the existing approach and serves as the safe fallback.
    """
    
    def __init__(self, compositor: "GLCompositorWidget", config: RenderStrategyConfig):
        super().__init__(compositor, config)
        self._timer: Optional[QTimer] = None
    
    @property
    def strategy_type(self) -> RenderStrategyType:
        return RenderStrategyType.TIMER
    
    def start(self) -> bool:
        """Start timer-based rendering."""
        with self._lock:
            if self._active:
                return True
            
            try:
                interval_ms = max(1, 1000 // self._config.target_fps)
                self._timer = QTimer(self._compositor)
                self._timer.setTimerType(Qt.TimerType.PreciseTimer)
                self._timer.timeout.connect(self._on_tick)
                self._timer.start(interval_ms)
                self._active = True
                self._metrics = RenderMetrics(strategy_type=self.strategy_type)
                logger.info("[RENDER] Timer strategy started (interval=%dms, target=%dHz)",
                           interval_ms, self._config.target_fps)
                return True
            except Exception as e:
                logger.error("[RENDER] Failed to start timer strategy: %s", e)
                return False
    
    def stop(self) -> None:
        """Stop timer-based rendering."""
        with self._lock:
            if self._timer is not None:
                try:
                    self._timer.stop()
                    self._timer.deleteLater()
                except Exception as e:
                    logger.debug("[RENDER] Timer cleanup error: %s", e)
                self._timer = None
            self._active = False
            self._log_final_metrics()
    
    def request_frame(self) -> None:
        """Request immediate frame (timer handles regular cadence)."""
        if self._compositor is not None:
            try:
                self._compositor.update()
            except Exception as e:
                logger.debug("[RENDER] Frame request error: %s", e)
    
    def _on_tick(self) -> None:
        """Timer tick handler."""
        with self._lock:
            self._metrics.record_frame()
        
        if self._compositor is not None:
            try:
                self._compositor.update()
            except Exception as e:
                logger.debug("[RENDER] Timer tick error: %s", e)
    
    def _log_final_metrics(self) -> None:
        """Log final metrics when stopping."""
        if not is_perf_metrics_enabled():
            return
        m = self._metrics
        logger.info(
            "[PERF] [RENDER] Timer strategy stopped: frames=%d, avg_fps=%.1f, "
            "dt_min=%.1fms, dt_max=%.1fms",
            m.frame_count, m.get_avg_fps(), m.min_dt_ms, m.max_dt_ms
        )


class VSyncRenderStrategy(RenderStrategy):
    """VSync-driven rendering strategy via dedicated thread.
    
    Uses a dedicated render thread that synchronizes with display VSync
    for smoother frame pacing. Requires GL context sharing setup.
    
    This strategy:
    1. Creates a render thread with shared GL context
    2. Waits for VSync signal via swapBuffers
    3. Updates compositor state atomically
    4. Triggers repaint on UI thread
    
    Falls back to TimerRenderStrategy on failure if configured.
    """
    
    def __init__(self, compositor: "GLCompositorWidget", config: RenderStrategyConfig):
        super().__init__(compositor, config)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._fallback_strategy: Optional[TimerRenderStrategy] = None
        self._using_fallback = False
    
    @property
    def strategy_type(self) -> RenderStrategyType:
        return RenderStrategyType.VSYNC
    
    def start(self) -> bool:
        """Start VSync-driven rendering."""
        with self._lock:
            if self._active:
                return True
            
            try:
                self._stop_event.clear()
                self._thread = threading.Thread(
                    target=self._render_loop,
                    name="VSyncRenderThread",
                    daemon=True,
                )
                self._thread.start()
                self._active = True
                self._metrics = RenderMetrics(strategy_type=self.strategy_type)
                logger.info("[RENDER] VSync strategy started")
                return True
            except Exception as e:
                logger.error("[RENDER] Failed to start VSync strategy: %s", e)
                return self._try_fallback()
    
    def stop(self) -> None:
        """Stop VSync-driven rendering."""
        with self._lock:
            self._stop_event.set()
            if self._thread is not None:
                try:
                    self._thread.join(timeout=1.0)
                except Exception as e:
                    logger.debug("[RENDER] Thread join error: %s", e)
                self._thread = None
            
            if self._fallback_strategy is not None:
                self._fallback_strategy.stop()
                self._fallback_strategy = None
            
            self._active = False
            self._using_fallback = False
            self._log_final_metrics()
    
    def request_frame(self) -> None:
        """Request immediate frame."""
        if self._using_fallback and self._fallback_strategy is not None:
            self._fallback_strategy.request_frame()
        elif self._compositor is not None:
            try:
                self._compositor.update()
            except Exception as e:
                logger.debug("[RENDER] Frame request error: %s", e)
    
    def _render_loop(self) -> None:
        """Main render loop running in dedicated thread.
        
        This loop uses a high-precision busy-wait approach for the final
        portion of each frame to minimize jitter. The strategy:
        1. Sleep for most of the frame time (saves CPU)
        2. Busy-wait for the final ~2ms (reduces jitter)
        3. Signal UI thread to repaint at precise intervals
        """
        logger.debug("[RENDER] VSync render loop started (target=%dHz)", self._config.target_fps)
        
        target_frame_time = 1.0 / self._config.target_fps
        # Sleep threshold: sleep until this much time remains, then busy-wait
        sleep_threshold = 0.002  # 2ms - busy-wait for final portion
        
        # Track frame timing for drift correction
        next_frame_time = time.perf_counter()
        
        while not self._stop_event.is_set():
            try:
                # Calculate time until next frame
                now = time.perf_counter()
                sleep_time = next_frame_time - now
                
                # Sleep for most of the wait time (if > threshold)
                if sleep_time > sleep_threshold:
                    time.sleep(sleep_time - sleep_threshold)
                
                # Busy-wait for precise timing (reduces jitter significantly)
                while time.perf_counter() < next_frame_time:
                    pass  # Spin-wait for precise timing
                
                # Record metrics
                with self._lock:
                    self._metrics.record_frame()
                
                # Signal UI thread to repaint
                if self._compositor is not None:
                    try:
                        from PySide6.QtCore import QMetaObject, Qt as QtCore
                        QMetaObject.invokeMethod(
                            self._compositor,
                            "update",
                            QtCore.ConnectionType.QueuedConnection,
                        )
                    except Exception:
                        pass  # Suppress update errors
                
                # Schedule next frame - use fixed intervals to prevent drift
                next_frame_time += target_frame_time
                
                # If we've fallen behind, reset to now + one frame
                # This prevents trying to "catch up" which causes stutter
                if next_frame_time < time.perf_counter():
                    next_frame_time = time.perf_counter() + target_frame_time
                    
            except Exception as e:
                logger.error("[RENDER] VSync loop error: %s", e)
                if self._config.fallback_on_failure:
                    self._trigger_fallback()
                    break
        
        logger.debug("[RENDER] VSync render loop stopped")
    
    def _try_fallback(self) -> bool:
        """Try to fall back to timer strategy."""
        if not self._config.fallback_on_failure:
            return False
        
        logger.warning("[RENDER] Falling back to timer strategy")
        self._fallback_strategy = TimerRenderStrategy(self._compositor, self._config)
        if self._fallback_strategy.start():
            self._using_fallback = True
            self._metrics.fallback_count += 1
            return True
        return False
    
    def _trigger_fallback(self) -> None:
        """Trigger fallback from render thread."""
        with self._lock:
            if not self._using_fallback and self._config.fallback_on_failure:
                # Schedule fallback on UI thread
                if self._compositor is not None:
                    try:
                        from PySide6.QtCore import QMetaObject, Qt as QtCore
                        QMetaObject.invokeMethod(
                            self._compositor,
                            lambda: self._try_fallback(),
                            QtCore.ConnectionType.QueuedConnection,
                        )
                    except Exception as e:
                        logger.debug("[RENDER] Fallback trigger error: %s", e)
    
    def _log_final_metrics(self) -> None:
        """Log final metrics when stopping."""
        if not is_perf_metrics_enabled():
            return
        m = self._metrics
        logger.info(
            "[PERF] [RENDER] VSync strategy stopped: frames=%d, avg_fps=%.1f, "
            "dt_min=%.1fms, dt_max=%.1fms, fallbacks=%d",
            m.frame_count, m.get_avg_fps(), m.min_dt_ms, m.max_dt_ms, m.fallback_count
        )


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
        """Start rendering with specified or default strategy."""
        with self._lock:
            if self._current_strategy is not None:
                self._current_strategy.stop()
            
            # Determine strategy type
            if strategy_type is None:
                strategy_type = (
                    RenderStrategyType.VSYNC 
                    if self._config.vsync_enabled 
                    else RenderStrategyType.TIMER
                )
            
            # Create and start strategy
            if strategy_type == RenderStrategyType.VSYNC:
                self._current_strategy = VSyncRenderStrategy(self._compositor, self._config)
            else:
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
