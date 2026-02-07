"""Control feedback animation system for the MediaWidget.

Extracted from media_widget.py (M-5 refactor) to reduce monolith size.
Contains the shared feedback timer, per-instance feedback processing,
animation triggering, and feedback metric logging.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Qt
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled

if TYPE_CHECKING:
    from widgets.media_widget import MediaWidget

logger = get_logger(__name__)


# ------------------------------------------------------------------
# Shared Feedback System (Class-level operations)
# ------------------------------------------------------------------

def ensure_shared_feedback_timer(cls: type) -> None:
    """Ensure shared feedback timer is running."""
    timer = cls._shared_feedback_timer
    if timer is None:
        timer = QTimer()
        timer.setTimerType(Qt.TimerType.PreciseTimer)
        timer.setInterval(cls._shared_feedback_timer_interval_ms)
        timer.timeout.connect(cls._on_shared_feedback_tick)
        cls._shared_feedback_timer = timer
    if not timer.isActive():
        timer.start()
        if is_perf_metrics_enabled():
            logger.debug("[PERF] Started shared feedback timer")


def cleanup_shared_feedback_timer(cls: type) -> None:
    """Destroy the shared feedback timer when the last instance is gone."""
    timer = cls._shared_feedback_timer
    if timer is None:
        return
    # Only destroy if no live instances remain
    live = sum(1 for inst in list(cls._instances) if Shiboken.isValid(inst))
    if live > 0:
        return
    try:
        timer.stop()
        timer.deleteLater()
    except RuntimeError:
        pass
    cls._shared_feedback_timer = None
    if is_perf_metrics_enabled():
        logger.debug("[PERF] Destroyed shared feedback timer (no instances)")


def maybe_stop_shared_feedback_timer(cls: type) -> None:
    """Stop timer if no active feedback."""
    timer = cls._shared_feedback_timer
    if timer is None or not timer.isActive():
        return

    # Check if ANY instance has active feedback
    has_feedback = False
    for instance in list(cls._instances):
        try:
            if not Shiboken.isValid(instance):
                continue
        except Exception:
            continue
        if instance._controls_feedback:
            has_feedback = True
            break

    # Also check shared events dict
    if not has_feedback and cls._shared_feedback_events:
        has_feedback = True

    # Stop timer only if NO feedback anywhere
    if not has_feedback:
        timer.stop()
        if is_perf_metrics_enabled():
            logger.debug("[PERF] Stopped shared feedback timer (no active feedback)")


def on_shared_feedback_tick(cls: type) -> None:
    """Process feedback tick for all instances."""
    now = time.monotonic()

    # Process each instance
    for instance in list(cls._instances):
        try:
            if not Shiboken.isValid(instance):
                continue
        except Exception:
            continue
        instance._process_feedback_tick(now)

    # Expire old shared events
    expired_ids = []
    for event_id, meta in list(cls._shared_feedback_events.items()):
        duration = meta.get("duration", 0.0) or 0.0
        timestamp = meta.get("timestamp", now)
        if (now - timestamp) >= duration:
            expired_ids.append(event_id)
    for event_id in expired_ids:
        cls._shared_feedback_events.pop(event_id, None)

    # Stop timer if no more feedback
    maybe_stop_shared_feedback_timer(cls)


# ------------------------------------------------------------------
# Instance Feedback Methods
# ------------------------------------------------------------------

def process_feedback_tick(widget: "MediaWidget", now: float) -> bool:
    """Process feedback for this instance. Returns True if active."""
    expired_keys: list[str] = []
    for key, deadline in list(widget._feedback_deadlines.items()):
        if now >= deadline:
            expired_keys.append(key)

    for key in expired_keys:
        widget._feedback_deadlines.pop(key, None)
        finalize_feedback_key(widget, key)

    return bool(widget._controls_feedback)


def trigger_controls_feedback(
    widget: "MediaWidget", key: str, source: str = "manual"
) -> None:
    """Trigger control feedback animation."""
    if key not in ("prev", "play", "next"):
        logger.debug("[MEDIA_WIDGET][FEEDBACK] Invalid feedback key: %s", key)
        return

    logger.debug("[MEDIA_WIDGET][FEEDBACK] Starting feedback animation for %s", key)

    cls = type(widget)
    now = time.monotonic()
    event_id = f"{key}_{int(now * 1000)}"

    # Expire all existing feedback
    expire_all_feedback(widget)

    # Start new feedback
    widget._controls_feedback[key] = (now, event_id)
    widget._feedback_deadlines[key] = now + widget._controls_feedback_duration
    widget._active_feedback_events[key] = event_id
    start_feedback_animation(widget, key)

    # Register in shared events
    cls._shared_feedback_events[event_id] = {
        "key": key,
        "timestamp": now,
        "source": source,
        "duration": widget._controls_feedback_duration,
    }

    # Ensure timer is running
    ensure_shared_feedback_timer(cls)
    widget._safe_update()
    logger.debug("[MEDIA_WIDGET][FEEDBACK] Feedback animation started for %s", key)


def log_feedback_metric(
    widget: "MediaWidget",
    *,
    phase: str,
    key: str,
    source: str,
    event_id: str,
) -> None:
    """Emit structured logs for control feedback when diagnostics enabled."""
    if not (is_perf_metrics_enabled() or is_verbose_logging()):
        return

    overlay = getattr(widget, "_overlay_name", "media")
    message = (
        "[MEDIA_WIDGET][FEEDBACK] overlay=%s phase=%s key=%s source=%s event=%s"
        % (overlay, phase, key, source, event_id)
    )

    if is_perf_metrics_enabled():
        logger.info(message)
    else:
        logger.debug(message)


def start_feedback_animation(widget: "MediaWidget", key: str) -> None:
    """Start fade animation for feedback."""
    try:
        from core.animation.animator import AnimationManager
        from core.animation.types import EasingCurve

        if widget._feedback_anim_mgr is None:
            widget._feedback_anim_mgr = AnimationManager()

        mgr = widget._feedback_anim_mgr
        widget._controls_feedback_progress[key] = 1.0

        def _on_update(progress: float) -> None:
            eased = max(0.0, 1.0 - progress)
            value = eased * eased
            widget._controls_feedback_progress[key] = value
            widget._safe_update()

        def _on_complete() -> None:
            finalize_feedback_key(widget, key)

        anim_id = mgr.animate_custom(
            duration=max(0.01, widget._controls_feedback_duration),
            update_callback=_on_update,
            easing=EasingCurve.CUBIC_OUT,
            on_complete=_on_complete,
        )
        widget._controls_feedback_anim_ids[key] = anim_id
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Feedback animation failed: %s", e)
        # Fallback: just set progress and let timer expire it
        widget._controls_feedback_progress[key] = 1.0


def expire_all_feedback(widget: "MediaWidget") -> None:
    """Expire all active feedback."""
    for key in list(widget._controls_feedback.keys()):
        finalize_feedback_key(widget, key)


def finalize_feedback_key(widget: "MediaWidget", key: str) -> None:
    """Clean up feedback for a key."""
    anim_id = widget._controls_feedback_anim_ids.pop(key, None)
    if anim_id and widget._feedback_anim_mgr:
        try:
            widget._feedback_anim_mgr.cancel_animation(anim_id)
        except Exception:
            pass

    widget._controls_feedback_progress.pop(key, None)
    entry = widget._controls_feedback.pop(key, None)
    if entry:
        _, event_id = entry
        type(widget)._shared_feedback_events.pop(event_id, None)

    widget._feedback_deadlines.pop(key, None)
    active_id = widget._active_feedback_events.pop(key, None)
    if active_id and is_perf_metrics_enabled():
        log_feedback_metric(
            widget,
            phase="expire",
            key=key,
            source="local",
            event_id=active_id,
        )

    # Stop timer if no more feedback
    if not widget._controls_feedback and not widget._feedback_deadlines:
        maybe_stop_shared_feedback_timer(type(widget))

    widget._safe_update()
