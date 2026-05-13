"""Startup staging and lifecycle logic for SpotifyVisualizerWidget.

Extracted to reduce the main widget below the 2000-line threshold.
All functions take the widget instance as the first argument.

Phase 3 of the Visualizer Architecture Split.
"""
from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QTimer

from core.logging.logger import get_logger

logger = get_logger(__name__)


def is_anchor_visible(widget: Any) -> bool:
    """Return True when the anchor media widget is visible (or absent)."""
    anchor = widget._anchor_media
    if anchor is None:
        return True
    try:
        return bool(anchor.isVisible())
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
    return True


def cancel_pending_startup_reveal(widget: Any) -> None:
    """Invalidate any pending staged-reveal sequence."""
    widget._startup_reveal_pending = False
    widget._startup_reveal_token += 1
    widget._startup_reveal_ready_token = -1


def ensure_spotify_secondary_stage_registration(widget: Any) -> None:
    """Self-register with the parent's secondary-stage fade system."""
    if widget._spotify_secondary_stage_registered:
        return

    parent = widget.parent()
    register = getattr(parent, "register_spotify_secondary_fade", None) if parent is not None else None
    if not callable(register):
        return

    try:
        register(widget.begin_spotify_secondary_stage)
        widget._spotify_secondary_stage_registered = True
        logger.debug("[SPOTIFY_VIS] Self-registered Spotify secondary startup stage")
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to self-register Spotify secondary stage", exc_info=True)


def is_parent_secondary_stage_ready(widget: Any) -> bool:
    """Return True when the parent overlay's secondary-stage deadline has passed."""
    parent = widget.parent()
    if parent is None:
        return True
    try:
        overlay_expected = getattr(parent, "_overlay_fade_expected", set()) or set()
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        overlay_expected = set()
    try:
        overlay_started = bool(getattr(parent, "_overlay_fade_started", False))
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        overlay_started = False
    if overlay_expected and not overlay_started:
        return False
    try:
        not_before_ts = float(
            getattr(parent, "_spotify_secondary_not_before_ts", 0.0) or 0.0
        )
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        not_before_ts = 0.0
    if not_before_ts <= 0.0:
        return not overlay_expected
    return time.monotonic() >= not_before_ts


def prewarm_parent_overlay(widget: Any) -> None:
    """Pre-create the GL overlay so first-frame latency is lower."""
    parent = widget.parent()
    if parent is None:
        return
    try:
        from rendering.display_image_ops import prewarm_spotify_visualizer_overlay

        prewarm_spotify_visualizer_overlay(parent)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to prewarm parent GL overlay", exc_info=True)


def finish_staged_startup_reveal(
    widget: Any,
    *,
    reason: str,
    allow_waiting_fallback: bool = False,
) -> None:
    """Complete the staged startup reveal if all preconditions are met."""
    if not widget._enabled or not widget._startup_reveal_pending:
        return
    if not is_anchor_visible(widget):
        return
    if widget._startup_require_playing_before_reveal and not widget._spotify_playing:
        return
    if widget._waiting_for_fresh_frame and not allow_waiting_fallback:
        return
    try:
        not_before_ts = float(getattr(widget, "_startup_reveal_not_before_ts", 0.0) or 0.0)
    except Exception:
        not_before_ts = 0.0
    if not_before_ts > 0.0 and time.monotonic() < not_before_ts:
        if not allow_waiting_fallback and not widget._waiting_for_fresh_frame:
            try:
                delay_ms = max(
                    1,
                    int((not_before_ts - time.monotonic()) * 1000.0),
                )
            except Exception:
                delay_ms = 1
            schedule_ready_driven_startup_reveal(widget, delay_ms=delay_ms)
        return

    cancel_pending_startup_reveal(widget)
    try:
        if not widget.isVisible():
            widget._start_widget_fade_in()
        logger.debug("[SPOTIFY_VIS] Completed staged startup reveal (reason=%s)", reason)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed staged startup reveal", exc_info=True)


def schedule_ready_driven_startup_reveal(widget: Any, *, delay_ms: int) -> None:
    """Schedule a reveal attempt after a short delay for fresh-frame readiness."""
    if not widget._startup_reveal_pending:
        return
    token = int(getattr(widget, "_startup_reveal_token", 0))
    if widget._startup_reveal_ready_token == token:
        return
    widget._startup_reveal_ready_token = token

    def _maybe_reveal() -> None:
        if token != widget._startup_reveal_token:
            return
        widget._startup_reveal_ready_token = -1
        finish_staged_startup_reveal(widget, reason="fresh_frame_ready_delay")

    try:
        QTimer.singleShot(max(0, int(delay_ms)), _maybe_reveal)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to schedule ready-driven reveal", exc_info=True)
        widget._startup_reveal_ready_token = -1
        _maybe_reveal()


def schedule_startup_reveal_fallback(widget: Any) -> None:
    """Schedule a fallback reveal timer for the staged startup."""
    delay_ms = max(0, int(widget._startup_reveal_fallback_ms))
    widget._startup_reveal_token += 1
    token = widget._startup_reveal_token

    def _maybe_reveal() -> None:
        if token != widget._startup_reveal_token:
            return
        finish_staged_startup_reveal(
            widget,
            reason="fallback_timer",
            allow_waiting_fallback=True,
        )

    try:
        if delay_ms <= 0:
            _maybe_reveal()
        else:
            QTimer.singleShot(delay_ms, _maybe_reveal)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to schedule startup reveal fallback", exc_info=True)
        _maybe_reveal()


def mode_allows_idle_reveal(widget: Any) -> bool:
    """Return True when the current mode should reveal while paused."""
    return str(getattr(widget, "_vis_mode_str", "")).lower() in {"bubble", "sine_wave", "devcurve"}


def arm_staged_startup(widget: Any, *, reason: str) -> None:
    """Arm the staged startup sequence: hide, register, seed state."""
    try:
        widget.hide()
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

    ensure_spotify_secondary_stage_registration(widget)
    cancel_pending_startup_reveal(widget)
    widget._startup_secondary_stage_pending = bool(widget._spotify_secondary_stage_registered)
    widget._startup_hot_start_started = False
    widget._startup_reveal_not_before_ts = 0.0
    widget._startup_wake_deferred = False
    widget._startup_require_playing_before_reveal = False
    widget._seed_playback_state_from_anchor(
        reason=reason,
        request_refresh_if_missing=True,
    )
    widget._startup_require_playing_before_reveal = (
        (not widget._spotify_playing) and (not mode_allows_idle_reveal(widget))
    )


def begin_hot_start(widget: Any, *, reason: str, reset_reason: str) -> None:
    """Start the hot-start phase: acquire engine, schedule reveal."""
    from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine

    if widget._startup_hot_start_started:
        return

    widget._startup_hot_start_started = True
    widget._startup_secondary_stage_pending = False
    widget._startup_reveal_not_before_ts = time.monotonic() + (
        max(0, int(widget._startup_min_reveal_delay_ms)) / 1000.0
    )
    widget._seed_playback_state_from_anchor(
        reason=reason,
        request_refresh_if_missing=False,
    )
    widget._startup_require_playing_before_reveal = (
        (not widget._spotify_playing) and (not mode_allows_idle_reveal(widget))
    )

    try:
        engine = get_shared_spotify_beat_engine(widget._bar_count)
        widget._engine = engine
        if widget._thread_manager is not None:
            engine.set_thread_manager(widget._thread_manager)
        engine.acquire()
        widget._reset_engine_state(reason=reset_reason)
        logger.info(
            "[SPOTIFY_VIS] Staged engine reset applied (reason=%s, mode=%s, bars=%d)",
            reset_reason,
            widget._vis_mode.name,
            widget._bar_count,
        )
        engine.set_playback_state(widget._spotify_playing)
        if widget._startup_wake_deferred:
            widget._startup_wake_deferred = False
            logger.debug(
                "[SPOTIFY_VIS] Consumed deferred wake during staged hot start without explicit engine.wake()",
            )
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to start shared beat engine", exc_info=True)

    if widget._thread_manager is not None and widget._bars_timer is None:
        try:
            widget._bars_timer = widget._thread_manager.schedule_recurring(16, widget._on_tick)
            widget._current_timer_interval_ms = 16
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            widget._bars_timer = None
    elif widget._animation_manager is not None and widget._anim_listener_id is not None:
        widget._using_animation_ticks = True

    prewarm_parent_overlay(widget)
    widget._startup_reveal_pending = True
    schedule_startup_reveal_fallback(widget)


def begin_spotify_secondary_stage(widget: Any) -> None:
    """Entry point for the secondary startup stage."""
    if not widget._enabled:
        return
    if not is_anchor_visible(widget):
        logger.debug("[SPOTIFY_VIS] Secondary stage skipped until anchor becomes visible")
        return
    begin_hot_start(widget, reason="secondary_stage", reset_reason="secondary_stage")


def activate_impl(widget: Any) -> None:
    """Activate visualizer — lifecycle hook."""
    widget._enabled = True
    arm_staged_startup(widget, reason="activate_impl")
    if not widget._startup_secondary_stage_pending:
        begin_hot_start(
            widget,
            reason="activate_impl_immediate",
            reset_reason="activate_impl",
        )
    logger.debug("[LIFECYCLE] SpotifyVisualizerWidget activated")


def deactivate_impl(widget: Any) -> None:
    """Deactivate visualizer — lifecycle hook."""
    from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine

    try:
        widget._reset_latency_diagnostics()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to reset latency diagnostics on deactivate", exc_info=True)

    try:
        engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        engine = None
    if engine is not None:
        try:
            engine.release()
        except Exception:
            logger.debug("[LIFECYCLE] Failed to release shared beat engine", exc_info=True)

    try:
        widget.detach_from_animation_manager()
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

    if widget._bars_timer is not None:
        try:
            widget._bars_timer.stop()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        widget._bars_timer = None
    widget._using_animation_ticks = False

    widget._log_perf_snapshot(reset=True)
    logger.debug("[LIFECYCLE] SpotifyVisualizerWidget deactivated")


def cleanup_impl(widget: Any) -> None:
    """Clean up visualizer resources — lifecycle hook."""
    deactivate_impl(widget)
    widget._engine = None
    # Free GL handles on the bars overlay to prevent VRAM leaks
    widget._destroy_parent_overlay(reason="cleanup_impl")
    logger.debug("[LIFECYCLE] SpotifyVisualizerWidget cleaned up")


def start_legacy(widget: Any) -> None:
    """Legacy start method."""
    if widget._enabled:
        return
    widget._enabled = True
    arm_staged_startup(widget, reason="start")
    if widget._startup_secondary_stage_pending:
        logger.debug("[SPOTIFY_VIS] Deferred hot start to Spotify secondary stage")
        return
    begin_hot_start(widget, reason="start_immediate", reset_reason="cold_start")


def stop_legacy(widget: Any) -> None:
    """Legacy stop method."""
    from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine

    if not widget._enabled:
        return
    widget._enabled = False
    try:
        widget._reset_latency_diagnostics()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to reset latency diagnostics on stop", exc_info=True)
    widget._startup_secondary_stage_pending = False
    widget._startup_hot_start_started = False
    widget._startup_wake_deferred = False
    widget._startup_require_playing_before_reveal = False
    cancel_pending_startup_reveal(widget)

    try:
        engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        engine = None
    if engine is not None:
        try:
            engine.release()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to release shared beat engine", exc_info=True)

    try:
        widget.detach_from_animation_manager()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to detach from AnimationManager on stop", exc_info=True)

    try:
        if widget._bars_timer is not None:
            widget._bars_timer.stop()
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
    widget._bars_timer = None
    widget._using_animation_ticks = False

    # Emit a concise PERF summary for this widget's activity during the
    # last enabled period so we can see its effective update/paint rate
    # and dt jitter alongside compositor and animation metrics.
    widget._log_perf_snapshot(reset=True)

    try:
        widget.hide()
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
