"""Centralized global clock ticker for all clock widgets.

This module provides a shared 1-second timer for retained Clock presentation models
subscribe to, eliminating per-widget timers and ensuring synchronized updates
across all displays.

The global ticker uses ThreadManager for centralized timing and automatically
starts/stops based on subscriber count.
"""
from __future__ import annotations

from typing import Any, Callable, Optional, TYPE_CHECKING
import weakref
from PySide6.QtCore import QCoreApplication, QObject, Signal

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
        
        self._subscribers: list[weakref.WeakMethod | Callable[[], None]] = []
        self._timer_handle: Optional[object] = None
        self._thread_manager: Optional["ThreadManager"] = None
        self._is_running = False
        
        logger.debug("[CLOCK_TICKER] Global clock ticker initialized")
    
    def set_thread_manager(self, thread_manager: "ThreadManager") -> None:
        """Set the thread manager for scheduling the ticker."""
        self._thread_manager = thread_manager
    
    def subscribe(self, callback: Callable[[], None]) -> None:
        """Subscribe a clock widget to receive tick events."""
        if any(self._resolve(record) == callback for record in self._subscribers):
            return
        owner = getattr(callback, "__self__", None)
        if owner is not None and getattr(callback, "__func__", None) is not None:
            try:
                record: weakref.WeakMethod | Callable[[], None] = weakref.WeakMethod(
                    callback
                )
            except TypeError:
                record = callback
        else:
            record = callback
        self._subscribers.append(record)
        logger.debug("[CLOCK_TICKER] Subscriber added (count=%d)", len(self._subscribers))
        
        # Start ticker if first subscriber
        if len(self._subscribers) == 1:
            self._start()
    
    def unsubscribe(self, callback: Callable[[], None]) -> None:
        """Unsubscribe a clock widget from tick events."""
        self._subscribers = [
            record
            for record in self._subscribers
            if self._resolve(record) not in {None, callback}
        ]
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
        if not self._is_running and self._timer_handle is None:
            return
        
        if self._timer_handle is not None:
            try:
                timer = self._timer_handle
                stop = getattr(timer, "stop", None)
                if callable(stop):
                    stop()
                delete_later = getattr(timer, "deleteLater", None)
                if (
                    callable(delete_later)
                    and QCoreApplication.instance() is not None
                    and not QCoreApplication.closingDown()
                ):
                    delete_later()
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
        live_records = []
        for record in list(self._subscribers):
            callback = self._resolve(record)
            if callback is None:
                continue
            live_records.append(record)
            try:
                callback()
            except Exception as e:
                logger.debug("[CLOCK_TICKER] Subscriber callback failed: %s", e)
        self._subscribers = live_records
        if not live_records:
            self._stop()

    @staticmethod
    def _resolve(
        record: weakref.WeakMethod | Callable[[], None],
    ) -> Callable[[], None] | None:
        return record() if isinstance(record, weakref.WeakMethod) else record

    @staticmethod
    def _callback_runtime_identity(callback: Callable[[], None]) -> tuple[Any, str, int]:
        owner = getattr(callback, "__self__", None)
        owner_class = type(owner).__name__ if owner is not None else "function"
        owner_id = id(owner) if owner is not None else id(callback)
        current = owner
        generation = getattr(callback, "_srpss_runtime_generation", None)
        for _ in range(16):
            if current is None:
                break
            value = getattr(current, "_runtime_generation", None)
            if value is not None:
                generation = value
                break
            parent_getter = getattr(current, "parent", None)
            if not callable(parent_getter):
                break
            try:
                current = parent_getter()
            except RuntimeError:
                break
        return generation, owner_class, owner_id

    def get_lifecycle_ownership_snapshot(self) -> dict[str, object]:
        """Return bounded passive subscriber ownership for lifecycle diagnostics."""

        live_records = []
        subscribers = []
        subscribers_by_generation: dict[str, int] = {}
        for record in self._subscribers:
            callback = self._resolve(record)
            if callback is None:
                continue
            live_records.append(record)
            generation, owner_class, owner_id = self._callback_runtime_identity(
                callback
            )
            generation_key = (
                str(generation) if generation is not None else "process_or_unknown"
            )
            subscribers_by_generation[generation_key] = (
                subscribers_by_generation.get(generation_key, 0) + 1
            )
            if len(subscribers) < 64:
                subscribers.append(
                    {
                        "runtime_generation": generation,
                        "owner_class": owner_class,
                        "owner_id": owner_id,
                    }
                )
        self._subscribers = live_records
        try:
            timer_active = bool(
                self._timer_handle is not None
                and getattr(self._timer_handle, "isActive", lambda: False)()
            )
        except RuntimeError:
            timer_active = False
        return {
            "total": len(live_records),
            "subscribers": tuple(subscribers),
            "subscribers_by_generation": subscribers_by_generation,
            "omitted": max(0, len(live_records) - len(subscribers)),
            "timer_active": timer_active,
        }
    
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
