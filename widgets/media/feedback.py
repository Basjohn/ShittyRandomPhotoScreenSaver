"""Control feedback animation system for the MediaWidget.

Extracted from media_widget.py (M-5 refactor) to reduce monolith size.
Contains the shared feedback timer, per-instance feedback processing,
animation triggering, and feedback metric logging.
"""
from __future__ import annotations

import time
import weakref
from typing import TYPE_CHECKING

from PySide6.QtCore import QRect, QTimer, Qt
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
        try:
            from core.resources.manager import ResourceManager
            ResourceManager.get_or_create_app_shared().register_qt(
                timer,
                description="MediaWidget shared feedback timer",
            )
        except Exception:
            pass
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

    # Check if ANY instance has feedback that actually depends on this timer.
    # Static transition feedback is owned by one managed single-shot callback.
    has_feedback = False
    for instance in list(cls._instances):
        try:
            if not Shiboken.isValid(instance):
                continue
        except Exception:
            continue
        for _key, entry in instance._controls_feedback.items():
            event_id = entry[1] if entry else None
            meta = cls._shared_feedback_events.get(event_id, {})
            if meta.get("mode") != "static":
                has_feedback = True
                break
        if has_feedback:
            break

    # Also check shared events that use the fallback deadline sweep.
    if not has_feedback:
        has_feedback = any(
            meta.get("mode") != "static"
            for meta in cls._shared_feedback_events.values()
        )

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
        if meta.get("mode") == "static":
            continue
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


def _has_transition_work(widget: "MediaWidget") -> bool:
    """Return whether feedback must avoid a frame-by-frame repaint stream."""

    try:
        checker = getattr(type(widget), "_has_transition_work_on_any_display", None)
        return bool(checker()) if callable(checker) else False
    except Exception:
        logger.debug(
            "[MEDIA_WIDGET][FEEDBACK] Failed to inspect transition state",
            exc_info=True,
        )
        return False


def _record_feedback_paint_request(
    cls: type, event_id: str, *, full_card: bool
) -> None:
    meta = cls._shared_feedback_events.get(event_id)
    if meta is not None:
        meta["paint_requests"] = int(meta.get("paint_requests", 0)) + 1
        if full_card:
            meta["full_card_paint_requests"] = (
                int(meta.get("full_card_paint_requests", 0)) + 1
            )


def _feedback_dirty_rect(widget: "MediaWidget") -> QRect | None:
    """The card region a feedback repaint must cover: the controls row plus a
    small margin for the glow that can bleed a few pixels past it.

    The transport controls are a band across the bottom of the card; the
    artwork, metadata text, header and playback progress all sit above it. So a
    feedback repaint confined to this rect draws only the (cached) background
    frame and the controls row - Qt clips the whole paint to the requested
    region, and `BaseOverlayWidget.paintEvent` re-clears the band to the frame
    pixmap before the semi-transparent row composites over it, so there is no
    stale-alpha accumulation. Returns None when the layout is unavailable, so
    the caller falls back to a full-card update.
    """

    try:
        layout = widget._compute_controls_layout()
    except Exception:
        logger.debug("[MEDIA_WIDGET][FEEDBACK] controls layout unavailable", exc_info=True)
        return None
    if not layout:
        return None
    row_rect = layout.get("row_rect")
    if row_rect is None or row_rect.isNull():
        return None

    margin = max(6, int(row_rect.height() * 0.25))
    dirty = row_rect.adjusted(-margin, -margin, margin, margin)
    try:
        return dirty.intersected(widget.rect())
    except Exception:
        return dirty


def _safe_update_region(widget: "MediaWidget", rect: QRect) -> None:
    """Best-effort partial `QWidget.update(rect)` that tolerates deleted objects."""
    if Shiboken is not None:
        try:
            if not Shiboken.isValid(widget):
                return
        except Exception:
            pass
    try:
        widget.update(rect)
    except RuntimeError:
        pass
    except Exception as exc:
        logger.debug("[MEDIA_WIDGET] region update suppressed: %s", exc)


def _request_feedback_paint(widget: "MediaWidget", event_id: str) -> None:
    """Repaint the control feedback.

    A feedback fade animates a small control glow. Repainting the whole media
    card once per animation frame (the old `_safe_update()` path) cost ~35-66
    full-card paints over the 1.35s fade and starved presentation delivery on
    the Pause/Play edge. The feedback only touches the controls row, so a
    dirty-region update confines the paint there; a full-card repaint is used
    only when the controls layout is unavailable.
    """
    dirty = _feedback_dirty_rect(widget)
    if dirty is not None and not dirty.isNull():
        _record_feedback_paint_request(type(widget), event_id, full_card=False)
        _safe_update_region(widget, dirty)
    else:
        _record_feedback_paint_request(type(widget), event_id, full_card=True)
        widget._safe_update()


def schedule_static_feedback_clear(
    widget: "MediaWidget",
    key: str,
    event_id: str,
) -> None:
    """Clear collision-time feedback once without a recurring timer."""

    from core.threading.manager import ThreadManager

    cls = type(widget)
    widget_ref = weakref.ref(widget)

    def _clear_once() -> None:
        candidate = widget_ref()
        if candidate is None:
            cls._shared_feedback_events.pop(event_id, None)
            return
        try:
            if not Shiboken.isValid(candidate):
                cls._shared_feedback_events.pop(event_id, None)
                return
        except Exception:
            cls._shared_feedback_events.pop(event_id, None)
            return
        if candidate._active_feedback_events.get(key) != event_id:
            return
        finalize_feedback_key(candidate, key)

    delay_ms = max(0, round(widget._controls_feedback_duration * 1000.0))
    ThreadManager.single_shot(delay_ms, _clear_once)


def trigger_controls_feedback(
    widget: "MediaWidget", key: str, source: str = "manual"
) -> None:
    """Trigger control feedback animation."""
    if key not in ("prev", "play", "next"):
        logger.debug("[MEDIA_WIDGET][FEEDBACK] Invalid feedback key: %s", key)
        return

    logger.debug("[MEDIA_WIDGET][FEEDBACK] Starting feedback for %s", key)

    cls = type(widget)
    now = time.monotonic()
    event_id = f"{key}_{int(now * 1000)}"

    # Expire all existing feedback
    expire_all_feedback(widget)

    # Start new feedback
    widget._controls_feedback[key] = (now, event_id)
    widget._active_feedback_events[key] = event_id
    transition_static = _has_transition_work(widget)
    if not transition_static:
        widget._feedback_deadlines[key] = now + widget._controls_feedback_duration

    # Register before animation/scheduling so every paint request belongs to
    # one inspectable event.
    cls._shared_feedback_events[event_id] = {
        "key": key,
        "timestamp": now,
        "source": source,
        "duration": widget._controls_feedback_duration,
        "transition_active": transition_static,
        "mode": "static" if transition_static else "animated",
        "paint_requests": 0,
        "full_card_paint_requests": 0,
    }

    if transition_static:
        # A normal feedback fade repaints the complete media card at 60 Hz for
        # 1.35 seconds.  During a compositor transition that otherwise-cheap
        # stream can starve presentation delivery.  Preserve immediate visual
        # acknowledgement as one static frame and retire it through one managed,
        # token-checked callback.
        widget._controls_feedback_progress[key] = 1.0
        schedule_static_feedback_clear(widget, key, event_id)
    else:
        start_feedback_animation(widget, key)

    _request_feedback_paint(widget, event_id)
    log_feedback_metric(
        widget,
        phase="start",
        key=key,
        source=source,
        event_id=event_id,
        presentation="static_transition" if transition_static else "animated",
    )
    log_feedback_path_metric(
        widget,
        phase="start",
        key=key,
        event_id=event_id,
    )

    # Animated feedback keeps the existing deadline timer as a completion
    # fallback. Static transition feedback has exactly one managed callback.
    if not transition_static:
        ensure_shared_feedback_timer(cls)
    logger.debug("[MEDIA_WIDGET][FEEDBACK] Feedback started for %s", key)


def log_feedback_metric(
    widget: "MediaWidget",
    *,
    phase: str,
    key: str,
    source: str,
    event_id: str,
    presentation: str | None = None,
) -> None:
    """Emit structured logs for control feedback when diagnostics enabled."""
    if not (is_perf_metrics_enabled() or is_verbose_logging()):
        return

    overlay = getattr(widget, "_overlay_name", "media")
    message = (
        "[MEDIA_WIDGET][FEEDBACK] overlay=%s phase=%s key=%s source=%s event=%s"
        % (overlay, phase, key, source, event_id)
    )
    if presentation:
        message += " presentation=%s" % presentation

    if is_perf_metrics_enabled():
        logger.info(message)
    else:
        logger.debug(message)


def log_feedback_path_metric(
    widget: "MediaWidget",
    *,
    phase: str,
    key: str,
    event_id: str,
    event_meta: dict | None = None,
) -> None:
    """Emit feedback-specific cost and scheduling telemetry."""

    if not is_perf_metrics_enabled():
        return
    meta = (
        event_meta
        if event_meta is not None
        else type(widget)._shared_feedback_events.get(event_id, {})
    )
    started_at = float(meta.get("timestamp", time.monotonic()))
    configured_duration = float(
        meta.get("duration", widget._controls_feedback_duration)
    )
    if phase == "start":
        duration_ms = configured_duration * 1000.0
    else:
        duration_ms = max(0.0, (time.monotonic() - started_at) * 1000.0)
    logger.info(
        "[PERF][MEDIA_FEEDBACK] phase=%s command=%s duplicate_suppressed=False "
        "transition_active=%s mode=%s duration_ms=%.2f paint_requests=%d "
        "event=%s source=%s",
        phase,
        key,
        bool(meta.get("transition_active", False)),
        str(meta.get("mode", "unknown")),
        duration_ms,
        int(meta.get("paint_requests", 0)),
        event_id,
        str(meta.get("source", "unknown")),
    )


def start_feedback_animation(widget: "MediaWidget", key: str) -> None:
    """Start fade animation for feedback."""
    try:
        from core.animation.animator import AnimationManager
        from core.animation.types import EasingCurve

        event_id = widget._active_feedback_events.get(key)
        if widget._feedback_anim_mgr is None:
            widget._feedback_anim_mgr = AnimationManager.get_or_create_app_shared()

        mgr = widget._feedback_anim_mgr
        widget._controls_feedback_progress[key] = 1.0

        def _on_update(progress: float) -> None:
            if widget._active_feedback_events.get(key) != event_id:
                return
            eased = max(0.0, 1.0 - progress)
            value = eased * eased
            widget._controls_feedback_progress[key] = value
            if event_id is not None:
                _request_feedback_paint(widget, event_id)
            else:
                widget._safe_update()

        def _on_complete() -> None:
            if widget._active_feedback_events.get(key) == event_id:
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
    event_id = entry[1] if entry else None
    event_meta = (
        type(widget)._shared_feedback_events.get(event_id)
        if event_id is not None
        else None
    )
    if entry:
        type(widget)._shared_feedback_events.pop(event_id, None)

    widget._feedback_deadlines.pop(key, None)
    active_id = widget._active_feedback_events.pop(key, None)
    if active_id and event_meta is not None:
        # The final clearing repaint below is a single full-card update: it
        # retires the feedback and lets the card settle. Counted so the "start
        # and end only" full-card bound stays honest.
        event_meta["paint_requests"] = int(event_meta.get("paint_requests", 0)) + 1
        event_meta["full_card_paint_requests"] = (
            int(event_meta.get("full_card_paint_requests", 0)) + 1
        )
        log_feedback_path_metric(
            widget,
            phase="complete",
            key=key,
            event_id=active_id,
            event_meta=event_meta,
        )
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
