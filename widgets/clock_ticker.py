"""Centralized global clock ticker for all clock widgets.

This module provides a shared 1-second timer that all ClockWidget instances
subscribe to, eliminating per-widget timers and ensuring synchronized updates
across all displays.

The global ticker uses ThreadManager for centralized timing and automatically
starts/stops based on subscriber count.
"""
from __future__ import annotations

from typing import Callable, Set, Optional, TYPE_CHECKING
from PySide6.QtCore import QObject, Signal

from core.logging.logger import get_logger

if TYPE_CHECKING:
    from core.threading.manager import ThreadManager

logger = get_logger(__name__)


class GlobalClockTicker(QObject):
    """Singleton global clock ticker shared by all clock widgets.
    
    Uses a single ThreadManager recurring timer that broadcasts tick events
to all registered clock widgets, ensuring synchronized updates across displays.
    """
    
    _instance: Optional["GlobalClockTicker"] = None
    _initialized = False
    
    # Signal emitted every second
    tick = Signal()  # type: ignore
    
    def __new__(cls) -> "GlobalClockTicker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if GlobalClockTicker._initialized:
            return
        super().__init__()
        GlobalClockTicker._initialized = True
        
        self._subscribers: Set[Callable[[], None]] = set()
        self._timer_handle: Optional[object] = None
        self._thread_manager: Optional["ThreadManager"] = None
        self._is_running = False
        
        logger.debug("[CLOCK_TICKER] Global clock ticker initialized")
    
    def set_thread_manager(self, thread_manager: "ThreadManager") -> None:
        """Set the thread manager for scheduling the ticker."""
        self._thread_manager = thread_manager
    
    def subscribe(self, callback: Callable[[], None]) -> None:
        """Subscribe a clock widget to receive tick events."""
        self._subscribers.add(callback)
        logger.debug("[CLOCK_TICKER] Subscriber added (count=%d)", len(self._subscribers))
        
        # Start ticker if first subscriber
        if len(self._subscribers) == 1:
            self._start()
    
    def unsubscribe(self, callback: Callable[[], None]) -> None:
        """Unsubscribe a clock widget from tick events."""
        self._subscribers.discard(callback)
        logger.debug("[CLOCK_TICKER] Subscriber removed (count=%d)", len(self._subscribers))
        
        # Stop ticker if no subscribers
        if not self._subscribers:
            self._stop()
    
    def _start(self) -> None:
        """Start the global ticker."""
        if self._is_running or self._timer_handle is not None:
            return
        
        if self._thread_manager is None:
            logger.error("[CLOCK_TICKER] Cannot start: no ThreadManager set")
            return
        
        # Schedule 1-second recurring timer
        self._timer_handle = self._thread_manager.schedule_recurring(
            interval_ms=1000,
            func=self._on_tick,
            description="GlobalClockTicker"
        )
        self._is_running = True
        logger.info("[CLOCK_TICKER] Started (interval=1000ms)")
    
    def _stop(self) -> None:
        """Stop the global ticker."""
        if not self._is_running:
            return
        
        if self._timer_handle is not None:
            try:
                # Cancel the timer via ThreadManager
                self._thread_manager.cancel_task(self._timer_handle)  # type: ignore
            except Exception as e:
                logger.debug("[CLOCK_TICKER] Exception stopping timer: %s", e)
            self._timer_handle = None
        
        self._is_running = False
        logger.info("[CLOCK_TICKER] Stopped")
    
    def _on_tick(self) -> None:
        """Called every second - broadcast to all subscribers."""
        # Emit Qt signal for any widgets using signal/slot
        self.tick.emit()
        
        # Direct callback invocation for efficiency
        for callback in list(self._subscribers):
            try:
                callback()
            except Exception as e:
                logger.debug("[CLOCK_TICKER] Subscriber callback failed: %s", e)
    
    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful for testing)."""
        if cls._instance is not None:
            cls._instance._stop()
            cls._instance._subscribers.clear()
        cls._instance = None
        cls._initialized = False


# Global accessor
def get_global_clock_ticker() -> GlobalClockTicker:
    """Get the singleton GlobalClockTicker instance."""
    return GlobalClockTicker()
