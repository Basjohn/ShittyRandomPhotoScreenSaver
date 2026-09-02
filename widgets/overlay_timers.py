"""Centralised recurring-timer helpers for retained runtime services.

Weather, Media, Gmail and Steam services use the shared ``ThreadManager``
recurring scheduler through this thin QObject-facing handle. There is no
widget-local fallback: missing scheduler ownership is a loud runtime error.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import QTimer, QObject, QMetaObject, Qt, QThread

from core.logging.logger import get_logger
from core.performance import widget_timer_sample


logger = get_logger(__name__)
_MISSING_TM_WARNING_EMITTED = False


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
        except Exception as exc:
            logger.debug("[OVERLAY_TIMER] Failed to stop timer: %s", exc, exc_info=True)
        self._timer = None

    def is_active(self) -> bool:
        timer = self._timer
        if timer is None:
            return False
        try:
            return timer.isActive()
        except Exception as e:
            logger.debug("[OVERLAY] Exception suppressed: %s", e)
            return False


def _get_thread_manager_for(widget: QObject) -> Optional[Any]:
    """Best-effort lookup of the shared ThreadManager for a widget.

    We first look for ``_thread_manager`` on the QObject itself, then on
    its parent. Retained model/service consumers may expose either shape.
    """

    try:
        tm = getattr(widget, "_thread_manager", None)
        if tm is not None:
            return tm
    except Exception as exc:
        logger.debug("[OVERLAY] Exception suppressed: %s", exc)

    try:
        parent = widget.parent()
    except Exception as exc:
        logger.debug("[OVERLAY] Exception suppressed: %s", exc)
        parent = None

    if parent is not None:
        try:
            tm = getattr(parent, "_thread_manager", None)
        except Exception as exc:
            logger.debug("[OVERLAY] Exception suppressed: %s", exc)
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

    The target (or its parent) must expose the shared ``ThreadManager``;
    ``schedule_recurring`` is the only accepted recurring-timer authority.

    Args:
        widget: Target QObject/runtime consumer that owns timer lifetime.
        interval_ms: Interval in milliseconds.
        callback: Zero-arg callable invoked each tick.
        description: Optional description for diagnostics.
    """

    if interval_ms <= 0:
        interval_ms = 1

    tm = _get_thread_manager_for(widget)

    if tm is None or not hasattr(tm, "schedule_recurring"):
        widget_name = getattr(widget, "objectName", lambda: None)()
        global _MISSING_TM_WARNING_EMITTED
        if not _MISSING_TM_WARNING_EMITTED:
            logger.error(
                "[OVERLAY_TIMER] ThreadManager unavailable for widget %r (desc=%s). "
                "All overlay timers must be scheduled via ThreadManager.",
                widget_name or widget,
                description,
            )
            _MISSING_TM_WARNING_EMITTED = True
        raise RuntimeError(
            f"[OVERLAY_TIMER] ThreadManager unavailable for widget {widget_name or widget}. "
            "All overlay timers must be scheduled via ThreadManager."
        )

    metric_name = description or getattr(callback, "__qualname__", None) or "overlay_timer"

    def _instrumented_callback() -> None:
        with widget_timer_sample(widget, metric_name, interval_ms=interval_ms):
            callback()

    try:
        setattr(_instrumented_callback, "_srpss_timer_owner", widget)
        setattr(_instrumented_callback, "_srpss_timer_description", metric_name)
    except Exception:
        logger.debug("[OVERLAY_TIMER] Failed to attach timer diagnostics metadata", exc_info=True)

    try:
        timer = tm.schedule_recurring(
            interval_ms,
            _instrumented_callback,
            description=metric_name,
        )
    except TypeError:
        timer = tm.schedule_recurring(interval_ms, _instrumented_callback)
    logger.debug(
        "[OVERLAY_TIMER] Created ThreadManager timer %r (%s ms) for %r (%s)",
        timer,
        interval_ms,
        widget,
        description,
    )
    return OverlayTimerHandle(timer)
