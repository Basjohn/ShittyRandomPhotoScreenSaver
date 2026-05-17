"""Shared runtime helpers for service-backed overlay widgets.

These helpers intentionally cover only the lifecycle mechanics that already
repeat across widgets: transition-busy probing, deferred single-shot timer
ownership, and deferred refresh/result staging. Widget-owned rendering,
provider logic, and authored UI behavior stay local.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

from PySide6.QtCore import QTimer


def parent_transition_running(widget: Any) -> bool:
    """Return True when any parent display reports pending or running transition work."""
    parent = widget.parent()
    while parent is not None:
        try:
            has_pending = getattr(parent, "has_transition_work_pending", None)
            if callable(has_pending) and bool(has_pending()):
                return True
            has_running = getattr(parent, "has_running_transition", None)
            if callable(has_running) and bool(has_running()):
                return True
        except Exception:
            return False
        parent = parent.parent() if hasattr(parent, "parent") else None
    return False


def ensure_single_shot_timer(
    widget: Any,
    *,
    attr_name: str,
    delay_ms: int,
    timeout_callback: Callable[[], None],
    resource_name: str,
) -> QTimer:
    """Create or reuse a single-shot timer stored on the widget instance."""
    timer = getattr(widget, attr_name, None)
    if timer is None:
        timer = QTimer(widget)
        timer.setSingleShot(True)
        timer.timeout.connect(timeout_callback)
        widget._register_resource(timer, resource_name)
        setattr(widget, attr_name, timer)
    if not timer.isActive():
        timer.start(int(delay_ms))
    return timer


def stop_qtimer_attr(
    widget: Any,
    attr_name: str,
    *,
    delete_qtimers: bool,
    clear_attr: bool | None = None,
) -> None:
    """Stop an optional QTimer attribute and optionally delete/clear it."""
    timer = getattr(widget, attr_name, None)
    if timer is None:
        if clear_attr:
            setattr(widget, attr_name, None)
        return
    try:
        timer.stop()
        if delete_qtimers and hasattr(timer, "deleteLater"):
            timer.deleteLater()
    except Exception:
        pass
    if clear_attr is None:
        clear_attr = delete_qtimers
    if clear_attr:
        setattr(widget, attr_name, None)


def defer_refresh_if_transition(
    widget: Any,
    *,
    pending_attr: str,
    schedule_callback: Callable[[], None],
    logger: Any | None = None,
    log_message: str | None = None,
) -> bool:
    """Set the pending-refresh flag and schedule a deferred retry if transition work is active."""
    if not parent_transition_running(widget):
        return False
    setattr(widget, pending_attr, True)
    schedule_callback()
    if log_message and logger is not None:
        logger.debug(log_message)
    return True


def defer_value_if_transition(
    widget: Any,
    *,
    attr_name: str,
    value: Any,
    clear_attrs: Iterable[str],
    schedule_callback: Callable[[], None],
    logger: Any | None = None,
    log_message: str | None = None,
) -> bool:
    """Store a deferred value/error payload until the active transition finishes."""
    if not parent_transition_running(widget):
        return False
    setattr(widget, attr_name, value)
    for clear_attr_name in clear_attrs:
        setattr(widget, clear_attr_name, None)
    schedule_callback()
    if log_message and logger is not None:
        logger.debug(log_message)
    return True


def sync_refresh_spinner_for_transition(
    widget: Any,
    pending: bool,
    *,
    restart_callback: Callable[[QTimer], None] | None = None,
    update_callback: Callable[[], None] | None = None,
) -> None:
    """Pause or resume a refresh spinner in response to transition busy state."""
    if not getattr(widget, "_refreshing", False):
        return
    transition_busy = bool(pending) or parent_transition_running(widget)
    timer = getattr(widget, "_refresh_spin_timer", None)
    if transition_busy:
        setattr(widget, "_refresh_spinner_suspended_for_transition", True)
        if timer is not None and timer.isActive():
            timer.stop()
        if update_callback:
            update_callback()
        return
    if getattr(widget, "_refresh_spinner_suspended_for_transition", False):
        setattr(widget, "_refresh_spinner_suspended_for_transition", False)
        if timer is not None and not timer.isActive():
            if restart_callback is not None:
                restart_callback(timer)
            else:
                timer.start()
        if update_callback:
            update_callback()


def begin_fetch_guard(
    widget: Any,
    *,
    flag_attr: str = "_fetch_in_progress",
    lock_attr: str | None = None,
    logger: Any | None = None,
    busy_message: str | None = None,
) -> bool:
    """Return False when a fetch is already active, otherwise mark it active."""

    lock = getattr(widget, lock_attr, None) if lock_attr else None
    if lock is not None:
        with lock:
            if getattr(widget, flag_attr, False):
                if logger is not None and busy_message:
                    logger.debug(busy_message)
                return False
            setattr(widget, flag_attr, True)
            return True
    if getattr(widget, flag_attr, False):
        if logger is not None and busy_message:
            logger.debug(busy_message)
        return False
    setattr(widget, flag_attr, True)
    return True


def end_fetch_guard(
    widget: Any,
    *,
    flag_attr: str = "_fetch_in_progress",
    lock_attr: str | None = None,
) -> None:
    """Clear a fetch-in-progress flag, respecting an optional widget lock."""

    lock = getattr(widget, lock_attr, None) if lock_attr else None
    if lock is not None:
        with lock:
            setattr(widget, flag_attr, False)
        return
    setattr(widget, flag_attr, False)


def trigger_manual_refresh(
    widget: Any,
    *,
    enabled_attr: str = "_enabled",
    fetch_flag_attr: str = "_fetch_in_progress",
    defer_refresh: Callable[[], bool],
    fetch_callback: Callable[[], bool],
    logger: Any | None = None,
    busy_message: str | None = None,
    failure_message: str | None = None,
    start_feedback: Callable[[], None] | None = None,
    stop_feedback: Callable[[], None] | None = None,
) -> bool:
    """Shared manual-refresh request flow for service-backed widgets."""

    if not getattr(widget, enabled_attr, False):
        return False
    if getattr(widget, fetch_flag_attr, False):
        if logger is not None and busy_message:
            logger.debug(busy_message)
        return True
    if defer_refresh():
        return True
    try:
        if start_feedback is not None:
            start_feedback()
        queued = bool(fetch_callback())
        if not queued and stop_feedback is not None:
            stop_feedback()
        return queued
    except Exception:
        if stop_feedback is not None:
            stop_feedback()
        if logger is not None and failure_message:
            logger.debug(failure_message, exc_info=True)
        return False
