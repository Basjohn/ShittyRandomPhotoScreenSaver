"""Centralised helpers for overlay widget timers.

This module standardises how overlay widgets (clock, weather, media,
Reddit, Spotify visualiser, etc.) create and manage recurring timers.

Goals:
- Prefer ThreadManager.schedule_recurring for UI-thread timers so timing
  is centralised and timers are auto-registered with ResourceManager.
- Provide a small, duck-typed API that widgets can call without needing
  direct imports of ThreadManager / ResourceManager.
- Keep behaviour identical to the existing per-widget QTimer code paths
  while reducing boilerplate and the risk of orphaned timers.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import QTimer, QObject, QMetaObject, Qt, QThread

from core.logging.logger import get_logger


logger = get_logger(__name__)


class OverlayTimerHandle:
    """Lightweight wrapper around a recurring timer.

    Widgets keep a reference to this handle instead of the raw QTimer.
    The handle exposes only ``stop`` and ``is_active`` so callers can
    remain agnostic about whether the underlying implementation is a
    QTimer or a ThreadManager-managed timer.
    """

    def __init__(self, timer: Optional[QTimer]) -> None:
        self._timer = timer

    def stop(self) -> None:
        timer = self._timer
        if timer is None:
            return
        try:
            # Ensure the stop call is executed on the timer's owning thread to
            # avoid Qt warnings like "Timers cannot be stopped from another
            # thread". When already on the owning thread we stop immediately;
            # otherwise we queue the call to that thread.
            if QThread.currentThread() is timer.thread():
                timer.stop()
            else:
                QMetaObject.invokeMethod(
                    timer,
                    "stop",
                    Qt.ConnectionType.QueuedConnection,
                )
        except Exception:
            logger.debug("[OVERLAY_TIMER] Failed to stop timer", exc_info=True)
        self._timer = None

    def is_active(self) -> bool:
        timer = self._timer
        if timer is None:
            return False
        try:
            return timer.isActive()
        except Exception:
            return False


def _get_thread_manager_for(widget: QObject) -> Optional[Any]:
    """Best-effort lookup of the shared ThreadManager for a widget.

    We first look for ``_thread_manager`` on the widget itself, then on
    its parent. This mirrors the pattern used by existing widgets where
    DisplayWidget injects a ThreadManager instance.
    """

    try:
        tm = getattr(widget, "_thread_manager", None)
        if tm is not None:
            return tm
    except Exception:
        pass

    try:
        parent = widget.parent()
    except Exception:
        parent = None

    if parent is not None:
        try:
            tm = getattr(parent, "_thread_manager", None)
        except Exception:
            tm = None
        return tm

    return None


def create_overlay_timer(
    widget: QObject,
    interval_ms: int,
    callback: Callable[[], None],
    *,
    description: str = "Overlay timer",
) -> OverlayTimerHandle:
    """Create a recurring UI timer for an overlay widget.

    When a ThreadManager is available on the widget (or its parent), we
    use ``schedule_recurring`` so the timer participates in centralised
    timing and ResourceManager tracking. Otherwise we fall back to a
    widget-local QTimer parented to ``widget``.

    Args:
        widget: Target widget (typically an overlay QLabel/QWidget).
        interval_ms: Interval in milliseconds.
        callback: Zero-arg callable invoked each tick.
        description: Optional description for diagnostics.
    """

    if interval_ms <= 0:
        interval_ms = 1

    tm = _get_thread_manager_for(widget)

    # Preferred path: ThreadManager.schedule_recurring
    if tm is not None and hasattr(tm, "schedule_recurring"):
        try:
            timer = tm.schedule_recurring(interval_ms, callback)
            logger.debug(
                "[OVERLAY_TIMER] Created ThreadManager timer %r (%s ms) for %r",
                timer,
                interval_ms,
                widget,
            )
            return OverlayTimerHandle(timer)
        except Exception:
            logger.debug(
                "[OVERLAY_TIMER] schedule_recurring failed; falling back to local QTimer",
                exc_info=True,
            )

    # Fallback: local QTimer parented to the widget
    try:
        timer = QTimer(widget)
        timer.setSingleShot(False)
        timer.setInterval(int(interval_ms))

        def _invoke() -> None:
            try:
                callback()
            except Exception:
                logger.exception("[OVERLAY_TIMER] recurring callback raised")

        timer.timeout.connect(_invoke)  # type: ignore[arg-type]
        timer.start()
        logger.debug(
            "[OVERLAY_TIMER] Created local QTimer %r (%s ms) for %r", timer, interval_ms, widget
        )
        return OverlayTimerHandle(timer)
    except Exception:
        logger.exception("[OVERLAY_TIMER] Failed to create timer for %r", widget)
        return OverlayTimerHandle(None)
