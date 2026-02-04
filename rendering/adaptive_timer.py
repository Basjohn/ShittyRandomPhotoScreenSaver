"""Adaptive timer strategy with hybrid state management.

This module provides an optimized timer that:
- Runs continuously during transitions (no thread churn)
- Enters low-power pause state after transitions end
- Goes to deep sleep after idle timeout
- Uses atomic operations for state transitions (no locks in hot path)

Fully integrated with ThreadManager, ResourceManager following project policies.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.threading.manager import ThreadManager, ThreadPoolType
from core.resources.manager import ResourceManager
from utils.lockfree.spsc_queue import SPSCQueue

if TYPE_CHECKING:
    from rendering.gl_compositor import GLCompositorWidget

logger = get_logger(__name__)


class TimerState(Enum):
    """Adaptive timer states.
    
    IDLE: Deep sleep, minimal CPU usage. Wakes on transition start.
    PAUSED: Recently stopped transition, checking if should go idle.
    RUNNING: Active transition, full timing precision.
    """
    IDLE = auto()
    PAUSED = auto()
    RUNNING = auto()


@dataclass
class AdaptiveTimerConfig:
    """Configuration for adaptive timer strategy."""
    target_fps: int = 60
    fallback_on_failure: bool = True
    min_frame_time_ms: float = 8.0
    # New: Time before transitioning PAUSED -> IDLE (seconds)
    idle_timeout_sec: float = 5.0
    # New: Max deep sleep duration before safety check (seconds)
    max_deep_sleep_sec: float = 60.0
    # New: Exit fast-path flag for shutdown (set to True on shutdown)
    exit_immediate: bool = False


@dataclass
class AdaptiveTimerMetrics:
    """Extended metrics for adaptive timer."""
    frame_count: int = 0
    state_transitions: int = 0
    start_ts: float = field(default_factory=time.time)
    time_in_idle_ms: float = 0.0
    time_in_paused_ms: float = 0.0
    time_in_running_ms: float = 0.0
    last_state_change_ts: float = field(default_factory=time.time)
    
    def record_state_change(self, old_state: TimerState) -> None:
        """Record transition from old_state to new state."""
        now = time.time()
        elapsed_ms = (now - self.last_state_change_ts) * 1000.0
        
        if old_state == TimerState.IDLE:
            self.time_in_idle_ms += elapsed_ms
        elif old_state == TimerState.PAUSED:
            self.time_in_paused_ms += elapsed_ms
        elif old_state == TimerState.RUNNING:
            self.time_in_running_ms += elapsed_ms
            
        self.state_transitions += 1
        self.last_state_change_ts = now


class AtomicTimerState:
    """Lock-free atomic state container for timer state.
    
    Uses simple compare-and-swap pattern with threading.Lock
    for state transitions (transitions are rare, reads are frequent).
    """
    
    def __init__(self, initial: TimerState = TimerState.IDLE):
        self._state = initial
        self._lock = threading.Lock()
    
    def load(self) -> TimerState:
        """Read current state (fast, no lock for read)."""
        return self._state
    
    def compare_and_swap(self, expected: TimerState, new: TimerState) -> TimerState:
        """Atomic compare-and-swap. Returns actual state (may be expected or different)."""
        with self._lock:
            actual = self._state
            if actual == expected:
                self._state = new
            return actual
    
    def store(self, new: TimerState) -> None:
        """Atomic store."""
        with self._lock:
            self._state = new


class AdaptiveTimerStrategy:
    """Adaptive timer with hybrid state machine for optimal performance.
    
    State Machine:
    - IDLE: Thread blocked on Event.wait(), ~0% CPU
    - PAUSED: Brief sleep checks (1ms), ~0.1% CPU, transitions to IDLE after timeout
    - RUNNING: Full precision timing, ~1-2% CPU per display
    
    Transitions:
    - IDLE -> RUNNING: On start_transition() (wake event)
    - RUNNING -> PAUSED: On end_transition()
    - PAUSED -> IDLE: After idle_timeout_sec of no new transitions
    - Any -> STOPPED: On stop() (app exit)
    
    Thread Safety:
    - State changes use AtomicTimerState (CAS operations)
    - Frame queue uses SPSCQueue (lock-free)
    - Wake event uses threading.Event (standard)
    """
    
    def __init__(self, compositor: "GLCompositorWidget", config: AdaptiveTimerConfig):
        self._compositor = compositor
        self._config = config
        
        # Atomic state management
        self._state = AtomicTimerState(TimerState.IDLE)
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()  # For waking from deep sleep
        
        # Frame request queue (lock-free)
        self._frame_queue: SPSCQueue[bool] = SPSCQueue(4)
        
        # Threading
        self._task_future = None
        self._task_id: Optional[str] = None
        self._thread_manager: Optional[ThreadManager] = None
        
        # Resource management
        self._resource_manager: Optional[ResourceManager] = None
        self._timer_resource_id: Optional[str] = None
        
        # Metrics
        self._metrics = AdaptiveTimerMetrics()
        self._transition_ended_at: float = 0.0
        
        # Get managers from compositor context
        try:
            parent = getattr(compositor, 'parent', lambda: None)()
            if parent is not None:
                self._thread_manager = getattr(parent, '_thread_manager', None)
                self._resource_manager = getattr(parent, '_resource_manager', None)
        except Exception:
            pass
    
    def start(self) -> bool:
        """Start adaptive timer (creates thread if not exists, wakes if sleeping)."""
        # Check if already running in any capacity
        if self._task_future is not None and not self._task_future.done():
            # Timer thread exists - just wake it
            current = self._state.load()
            if current != TimerState.RUNNING:
                self._metrics.record_state_change(current)
                self._state.store(TimerState.RUNNING)
                self._wake_event.set()
                if is_perf_metrics_enabled():
                    logger.info("[PERF][ADAPTIVE_TIMER] wake_to_running id=%s state=%s", self._task_id, current.name)
                else:
                    logger.debug("[ADAPTIVE_TIMER] Waking from %s to RUNNING", current.name)
            return True
        
        # Need to create thread - ThreadManager is required
        if self._thread_manager is None:
            logger.error(
                "[ADAPTIVE_TIMER] ThreadManager required but not available. "
                "Ensure compositor has a parent with _thread_manager."
            )
            return False
        
        # Use ThreadManager
        try:
            self._stop_event.clear()
            self._wake_event.clear()
            self._frame_queue.clear()
            
            # Start in IDLE state, thread will wait for wake
            self._state.store(TimerState.IDLE)
            
            # Submit to ThreadManager COMPUTE pool
            task_id = f"adaptive_timer_{id(self)}"
            self._thread_manager.submit_task(
                ThreadPoolType.COMPUTE,
                self._timer_loop,
                task_id=task_id
            )
            # Store task_id to track if thread is running
            self._task_id = task_id
            self._task_future = None
            
            # Register with ResourceManager
            if self._resource_manager is not None:
                try:
                    from core.resources.types import ResourceType
                    self._timer_resource_id = self._resource_manager.register(
                        self,
                        ResourceType.TIMER,
                        f"Adaptive timer ({self._config.target_fps}Hz)",
                    )
                except Exception as e:
                    logger.debug("[ADAPTIVE_TIMER] Could not register: %s", e)
            
            # Immediately wake to RUNNING state
            self._state.store(TimerState.RUNNING)
            self._wake_event.set()
            
            logger.info("[ADAPTIVE_TIMER] Started (target=%dHz, task=%s)", self._config.target_fps, self._task_id)
            return True
            
        except Exception as e:
            logger.error("[ADAPTIVE_TIMER] Failed to start: %s", e)
            return False
    
    def pause(self) -> None:
        """Pause timer (transition RUNNING -> PAUSED)."""
        current = self._state.load()
        if current == TimerState.RUNNING:
            self._metrics.record_state_change(current)
            self._state.store(TimerState.PAUSED)
            self._transition_ended_at = time.monotonic()
            if is_perf_metrics_enabled():
                logger.info("[PERF][ADAPTIVE_TIMER] paused id=%s", self._task_id)
            else:
                logger.debug("[ADAPTIVE_TIMER] Paused")
    
    def resume(self) -> None:
        """Resume timer (transition PAUSED/IDLE -> RUNNING)."""
        current = self._state.load()
        if current != TimerState.RUNNING:
            self._metrics.record_state_change(current)
            self._state.store(TimerState.RUNNING)
            self._wake_event.set()
            if is_perf_metrics_enabled():
                logger.info("[PERF][ADAPTIVE_TIMER] resumed_from=%s id=%s", current.name, self._task_id)
            else:
                logger.debug("[ADAPTIVE_TIMER] Resumed from %s", current.name)
    
    def stop(self) -> None:
        """Stop timer permanently (app exit).
        
        If exit_immediate is set in config, skip wait and tear down instantly.
        """
        # Signal stop
        self._stop_event.set()
        self._wake_event.set()
        
        # Fast-path: don't wait for thread if exit_immediate
        if self._config.exit_immediate:
            if is_perf_metrics_enabled():
                logger.info("[PERF][ADAPTIVE_TIMER] fast_stop id=%s", self._task_id)
            self._task_future = None
            self._task_id = None
            return
        
        # Normal wait with timeout
        if self._task_future is not None:
            try:
                max_wait = max(1.0, 2 * self._config.min_frame_time_ms / 1000.0)
                self._task_future.result(timeout=max_wait)
            except Exception:
                pass
            self._task_future = None
        self._task_id = None
        
        # Unregister from ResourceManager
        if self._timer_resource_id and self._resource_manager:
            try:
                self._resource_manager.unregister(self._timer_resource_id)
            except Exception:
                pass
            self._timer_resource_id = None
        
        if is_perf_metrics_enabled():
            logger.info("[PERF][ADAPTIVE_TIMER] stopped")
        else:
            logger.info("[ADAPTIVE_TIMER] Stopped")
        self._log_metrics()

    def describe_state(self) -> dict:
        """Return current timer snapshot for diagnostics."""
        state = self._state.load()
        return {
            "task_id": self._task_id,
            "state": state.name,
            "stop_event": self._stop_event.is_set(),
            "wake_event": self._wake_event.is_set(),
            "frames": self._metrics.frame_count,
        }
    
    def _timer_loop(self) -> None:
        """Main timer loop with state machine."""
        target_interval = max(1.0, 1000.0 / self._config.target_fps) / 1000.0
        sleep_threshold = 0.002
        
        logger.debug("[ADAPTIVE_TIMER] Loop started (target=%.2fms)", target_interval * 1000)
        
        while not self._stop_event.is_set():
            state = self._state.load()
            
            if state == TimerState.IDLE:
                # Deep sleep - but use short timeout to check stop_event frequently
                # Use 1 second chunks to allow quick shutdown response
                if self._wake_event.wait(timeout=1.0):
                    self._wake_event.clear()
                # Continue loop to check state
                continue
            
            elif state == TimerState.PAUSED:
                # Check if should go idle
                elapsed = time.monotonic() - self._transition_ended_at
                if elapsed > self._config.idle_timeout_sec:
                    # Transition to IDLE
                    old_state = self._state.compare_and_swap(TimerState.PAUSED, TimerState.IDLE)
                    if old_state == TimerState.PAUSED:
                        self._metrics.record_state_change(TimerState.PAUSED)
                        logger.debug("[ADAPTIVE_TIMER] Auto-idle after %.1fs", elapsed)
                    continue
                
                # Brief sleep before rechecking
                time.sleep(0.001)
                continue
            
            elif state == TimerState.RUNNING:
                # Full-precision timing
                try:
                    # Check for immediate frame requests
                    has_request = False
                    while True:
                        ok, _ = self._frame_queue.try_pop()
                        if not ok:
                            break
                        has_request = True
                    
                    if has_request:
                        self._signal_frame()
                        continue
                    
                    # Precise timing - use shorter sleeps for better shutdown response
                    start_ts = time.perf_counter()
                    
                    # Sleep for most of interval but in smaller chunks to check stop_event
                    remaining = target_interval - sleep_threshold
                    while remaining > 0.01:  # Sleep in 10ms chunks
                        if self._stop_event.is_set():
                            break
                        sleep_chunk = min(0.01, remaining)
                        time.sleep(sleep_chunk)
                        remaining -= sleep_chunk
                    
                    if remaining > 0 and not self._stop_event.is_set():
                        time.sleep(remaining)
                    
                    # Busy-wait for precision
                    while time.perf_counter() - start_ts < target_interval:
                        if self._stop_event.is_set() or self._state.load() != TimerState.RUNNING:
                            break
                        pass
                    
                    # Only signal if still running
                    if (not self._stop_event.is_set() and 
                        self._state.load() == TimerState.RUNNING):
                        self._signal_frame()
                        
                except Exception as e:
                    logger.error("[ADAPTIVE_TIMER] Loop error: %s", e)
                    break
        
        logger.debug("[ADAPTIVE_TIMER] Loop stopped")
    
    def _signal_frame(self) -> None:
        """Signal UI thread to render."""
        if self._compositor is not None:
            try:
                # Log occasional frame signals for debugging
                if self._metrics.frame_count % 100 == 0:
                    logger.debug("[ADAPTIVE_TIMER] Signaling frame %d", self._metrics.frame_count)
                ThreadManager.run_on_ui_thread(self._compositor.update)
                self._metrics.frame_count += 1
            except Exception as e:
                logger.debug("[ADAPTIVE_TIMER] Frame signal failed: %s", e)
    
    def request_frame(self) -> None:
        """Queue immediate frame request."""
        self._frame_queue.push_drop_oldest(True)
    
    def _log_metrics(self) -> None:
        """Log final metrics."""
        m = self._metrics
        total_time = time.time() - m.start_ts
        logger.info(
            "[ADAPTIVE_TIMER] Metrics: frames=%d, transitions=%d, "
            "time_idle=%.1fms, time_paused=%.1fms, time_running=%.1fms, "
            "total_runtime=%.1fs",
            m.frame_count, m.state_transitions,
            m.time_in_idle_ms, m.time_in_paused_ms, m.time_in_running_ms,
            total_time
        )
    
    def is_active(self) -> bool:
        """Check if timer is active (not stopped)."""
        # _task_future is actually a task_id string (ThreadManager returns task_id, not Future)
        # Just check if timer thread was started (not None) and not explicitly stopped
        return self._task_future is not None
    
    def get_state(self) -> TimerState:
        """Get current timer state."""
        return self._state.load()


class AdaptiveRenderStrategyManager:
    """Manager for adaptive timer render strategy.
    
    Maintains persistent timer across transitions.
    """
    
    def __init__(self, compositor: "GLCompositorWidget"):
        self._compositor = compositor
        self._config = AdaptiveTimerConfig()
        self._timer: Optional[AdaptiveTimerStrategy] = None
        self._lock = threading.Lock()
    
    def configure(self, config: AdaptiveTimerConfig) -> None:
        """Update configuration."""
        with self._lock:
            self._config = config
    
    def start(self) -> bool:
        """Start or resume adaptive timer."""
        with self._lock:
            if self._timer is None:
                self._timer = AdaptiveTimerStrategy(self._compositor, self._config)
            result = self._timer.start()
        if is_perf_metrics_enabled():
            logger.info("[PERF][ADAPTIVE_TIMER] manager_start result=%s state=%s", result, self.describe_state())
        return result
    
    def pause(self) -> None:
        """Pause timer after transition ends."""
        with self._lock:
            if self._timer is not None:
                self._timer.pause()
        if is_perf_metrics_enabled():
            logger.info("[PERF][ADAPTIVE_TIMER] manager_paused state=%s", self.describe_state())
    
    def resume(self) -> None:
        """Resume timer for new transition."""
        with self._lock:
            if self._timer is not None:
                self._timer.resume()
        if is_perf_metrics_enabled():
            logger.info("[PERF][ADAPTIVE_TIMER] manager_resumed state=%s", self.describe_state())
    
    def stop(self) -> None:
        """Stop timer permanently."""
        with self._lock:
            if self._timer is not None:
                # Enable exit fast-path before stopping
                self._timer._config.exit_immediate = True
                self._timer.stop()
                self._timer = None
        if is_perf_metrics_enabled():
            logger.info("[PERF][ADAPTIVE_TIMER] manager_stopped state=%s", self.describe_state())
    
    def request_frame(self) -> None:
        """Request immediate frame."""
        with self._lock:
            if self._timer is not None:
                self._timer.request_frame()
    
    def is_running(self) -> bool:
        """Check if timer is active."""
        with self._lock:
            return self._timer is not None and self._timer.is_active()

    def describe_state(self) -> dict:
        """Snapshot of manager/timer state for diagnostics."""
        with self._lock:
            config_snapshot = asdict(self._config)
            timer_state = self._timer.describe_state() if self._timer else None
        return {
            "config": config_snapshot,
            "timer": timer_state,
        }
