"""Startup staging and lifecycle logic for SpotifyVisualizerWidget.

Extracted to reduce the main widget below the 2000-line threshold.
All functions take the widget instance as the first argument.

Phase 3 of the Visualizer Architecture Split.
"""
from __future__ import annotations

import time
from typing import Any

from core.logging.logger import get_logger
from core.threading.manager import ThreadManager

logger = get_logger(__name__)


def _schedule_startup_stage(delay_ms: int, callback) -> None:
    """Route startup reveal delays through the app-owned scheduling seam."""

    ThreadManager.single_shot(max(0, int(delay_ms)), callback)


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
    parent = widget.parent()
    manager = getattr(parent, "_widget_manager", None) if parent is not None else None
    if widget._spotify_secondary_stage_registered:
        if manager is None:
            return
        try:
            if (
                getattr(widget, "_spotify_secondary_stage_manager_id", None) == id(manager)
                and getattr(widget, "_spotify_secondary_stage_generation", None)
                == getattr(manager, "_spotify_secondary_registration_generation", None)
            ):
                return
        except Exception as exc:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", exc)
        widget._spotify_secondary_stage_registered = False

    register_widget = (
        getattr(manager, "register_spotify_secondary_stage_widget", None)
        if manager is not None
        else None
    )
    if callable(register_widget):
        try:
            register_widget(widget)
            logger.debug("[SPOTIFY_VIS] Self-registered Spotify secondary startup stage via WidgetManager")
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to self-register Spotify secondary stage", exc_info=True)
        return

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


def scene_needs_reveal(widget: Any) -> bool:
    """Whether the compositor-owned scene is still invisible.

    ``isVisible()`` is not the answer any more: the logical QWidget stays shown
    across a fade-out because the compositor owns the pixels. A reveal gated on
    visibility alone therefore did nothing after any fade-out, leaving the
    visualizer permanently invisible.
    """
    try:
        from widgets.spotify_visualizer.presentation_fade import ensure_presentation_fade

        return bool(ensure_presentation_fade(widget).needs_reveal())
    except Exception:
        logger.debug("[SPOTIFY_VIS] Scene reveal state unavailable", exc_info=True)
        return False


def _owning_compositor(widget: Any):
    """Return the display compositor that owns this visualizer's pixels."""
    try:
        parent = widget.parent()
    except Exception:
        return None
    return getattr(parent, "_gl_compositor", None) if parent is not None else None


def is_renderer_presentation_ready(widget: Any) -> bool:
    """Whether the single-surface renderer can actually draw the visualizer.

    The visible fade may not begin before the compositor owns the visualizer and
    card pixels for the current QRhi generation. A compositor without the
    readiness seam (harness/test double) is treated as ready so this gate can
    never deadlock a runtime that has no such owner.
    """
    compositor = _owning_compositor(widget)
    if compositor is None:
        return True
    probe = getattr(compositor, "visualizer_can_reveal", None)
    if not callable(probe):
        probe = getattr(compositor, "is_visualizer_presentation_ready", None)
    if not callable(probe):
        return True
    try:
        return bool(probe())
    except Exception:
        logger.debug("[SPOTIFY_VIS] Renderer readiness probe failed", exc_info=True)
        return True


def log_renderer_readiness_gap(widget: Any) -> None:
    """One bounded report of what renderer readiness is still waiting for."""
    compositor = _owning_compositor(widget)
    probe = getattr(compositor, "visualizer_presentation_readiness", None)
    if not callable(probe):
        return
    try:
        readiness = probe()
        missing = ",".join(readiness.missing()) or "none"
    except Exception:
        return
    if getattr(widget, "_startup_renderer_readiness_gap", None) == missing:
        return
    try:
        widget._startup_renderer_readiness_gap = missing
    except Exception:
        pass
    logger.debug(
        "[SPOTIFY_VIS][STARTUP] Reveal waiting on renderer readiness missing=%s",
        missing,
    )


def finish_staged_startup_reveal(
    widget: Any,
    *,
    reason: str,
) -> None:
    """Complete the staged startup reveal if all preconditions are met."""
    if not widget._enabled or not widget._startup_reveal_pending:
        return
    if not is_anchor_visible(widget):
        return
    if widget._startup_require_playing_before_reveal and not widget._spotify_playing:
        return
    if (
        widget._startup_idle_reveal_requires_authoritative_media
        and not widget._startup_has_authoritative_media_update
    ):
        return
    if widget._waiting_for_fresh_frame:
        return
    if not is_renderer_presentation_ready(widget):
        # Readiness drives reveal. The compositor notifies once its fade-zero
        # preparation completes, which re-enters this function with
        # reason="renderer_ready".
        #
        # No re-attempt is scheduled here on purpose. The layer resets that
        # notification whenever it is cleared, so a clear/re-prepare cycle
        # notifies again, and every other reveal precondition - fresh frame,
        # play state, anchor visibility - re-enters this function on its own
        # event. Polling would add a second driver for a state machine that
        # already has one.
        log_renderer_readiness_gap(widget)
        return
    try:
        not_before_ts = float(getattr(widget, "_startup_reveal_not_before_ts", 0.0) or 0.0)
    except Exception:
        not_before_ts = 0.0
    if not_before_ts > 0.0 and time.monotonic() < not_before_ts:
        if not widget._waiting_for_fresh_frame:
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
        if not widget.isVisible() or scene_needs_reveal(widget):
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
        _schedule_startup_stage(delay_ms, _maybe_reveal)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to schedule ready-driven reveal", exc_info=True)
        widget._startup_reveal_ready_token = -1
        _maybe_reveal()


def schedule_startup_reveal_watchdog(widget: Any) -> None:
    """Schedule a startup watchdog without granting timeout reveal authority."""
    delay_ms = max(0, int(widget._startup_reveal_watchdog_ms))
    widget._startup_reveal_token += 1
    token = widget._startup_reveal_token

    def _maybe_reveal() -> None:
        if token != widget._startup_reveal_token:
            return
        finish_staged_startup_reveal(widget, reason="startup_watchdog")
        if widget._startup_reveal_pending:
            logger.warning(
                "[SPOTIFY_VIS][STARTUP] Reveal watchdog expired while still pending "
                "(mode=%s waiting_frame=%s waiting_engine=%s playing=%s "
                "require_playing=%s authoritative_media=%s)",
                str(getattr(widget, "_vis_mode_str", "unknown") or "unknown"),
                bool(getattr(widget, "_waiting_for_fresh_frame", False)),
                bool(getattr(widget, "_waiting_for_fresh_engine_frame", False)),
                bool(getattr(widget, "_spotify_playing", False)),
                bool(getattr(widget, "_startup_require_playing_before_reveal", False)),
                bool(getattr(widget, "_startup_has_authoritative_media_update", False)),
            )

    try:
        if delay_ms <= 0:
            _maybe_reveal()
        else:
            _schedule_startup_stage(delay_ms, _maybe_reveal)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to schedule startup reveal watchdog", exc_info=True)
        _maybe_reveal()


def mode_allows_idle_reveal(widget: Any) -> bool:
    """Return True when the current mode should reveal while paused."""
    return str(getattr(widget, "_vis_mode_str", "")).lower() in {"bubble", "sine_wave", "oscilloscope", "devcurve", "spectrum"}


def arm_staged_startup(widget: Any, *, reason: str) -> None:
    """Arm the staged startup sequence: hide, register, seed state."""
    try:
        widget.hide()
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

    # The scene fade must be genuinely at zero before preparation begins, so a
    # re-arm can never inherit a part-way (or completed) fade from the previous
    # staging attempt and reveal mid-curve.
    try:
        from widgets.spotify_visualizer.presentation_fade import ensure_presentation_fade

        ensure_presentation_fade(widget).reset()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to reset presentation fade", exc_info=True)
    try:
        widget._startup_renderer_readiness_gap = None
    except Exception:
        pass

    ensure_spotify_secondary_stage_registration(widget)
    cancel_pending_startup_reveal(widget)
    widget._startup_secondary_stage_pending = bool(widget._spotify_secondary_stage_registered)
    widget._startup_hot_start_started = False
    widget._startup_reveal_not_before_ts = 0.0
    widget._startup_wake_deferred = False
    widget._startup_wake_deferred_reason = ""
    widget._startup_require_playing_before_reveal = False
    widget._startup_idle_reveal_requires_authoritative_media = False
    widget._startup_has_authoritative_media_update = False
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
        set_generation = getattr(engine, "set_runtime_generation", None)
        if callable(set_generation):
            set_generation(getattr(widget, "_runtime_generation", None))
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
            deferred_reason = widget._startup_wake_deferred_reason or "staged_hot_start"
            widget._startup_wake_deferred = False
            widget._startup_wake_deferred_reason = ""
            logger.debug(
                "[SPOTIFY_VIS] Replaying deferred wake during staged hot start (reason=%s)",
                deferred_reason,
            )
            widget._trigger_wake(reason=deferred_reason, allow_defer=False)
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
    schedule_startup_reveal_watchdog(widget)


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
    from widgets.spotify_visualizer.media_bridge import clear_pending_playback_pause
    from widgets.spotify_visualizer.spectrum_presentation_smoothing import (
        reset_widget_spectrum_presentation_smoothing,
    )

    reset_widget_spectrum_presentation_smoothing(widget)

    try:
        clear_pending_playback_pause(widget)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to clear pending playback pause on deactivate", exc_info=True)

    try:
        widget._reset_latency_diagnostics()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to reset latency diagnostics on deactivate", exc_info=True)
    try:
        widget._reset_bubble_cadence()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to reset Bubble cadence on deactivate", exc_info=True)
    stop_lane = getattr(widget, "_stop_bubble_compute_lane", None)
    if callable(stop_lane):
        stop_lane()

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
    stop_lane = getattr(widget, "_stop_bubble_compute_lane", None)
    if callable(stop_lane):
        stop_lane()
    widget._engine = None
    # Free GL handles on the bars overlay to prevent VRAM leaks
    widget._destroy_parent_overlay(reason="cleanup_impl")
    logger.debug("[LIFECYCLE] SpotifyVisualizerWidget cleaned up")


# ------------------------------------------------------------------
# Edit-session suspend / resume
# ------------------------------------------------------------------


def is_edit_suspended(widget: Any) -> bool:
    return bool(getattr(widget, "_edit_suspended", False))


def suspend_for_edit(widget: Any, *, reason: str) -> bool:
    """Suspend a LIVE visualizer runtime for a CUSTOM edit session.

    An edit session is not a runtime lifecycle boundary, so it must not use
    ``stop_legacy()``/``start_legacy()``. Those are STARTUP entry points:
    ``start_legacy()`` re-arms staged startup, and mid-runtime that defers to
    the Spotify secondary stage - a one-shot event that has already fired. The
    installed ``--geo`` run recorded exactly that on Cancel:

        Seeded playback state from anchor (start ... state=playing)
        Deferred hot start to Spotify secondary stage

    and no later ``Audio worker started``.

    Suspension keeps the runtime generation, the committed mode/config, the
    engine identity and every GL resource. It only stops the work an edit
    session must not be doing, and records enough to resume directly.
    """
    if is_edit_suspended(widget):
        return False
    if not getattr(widget, "_enabled", False):
        return False

    from widgets.spotify_visualizer.media_bridge import clear_pending_playback_pause

    try:
        was_visible = bool(widget.isVisible())
    except Exception:
        was_visible = True

    widget._edit_suspended = True
    widget._edit_suspend_reason = str(reason)
    widget._edit_suspend_was_visible = was_visible
    # The tick, publication and media paths all gate on this, so clearing it
    # stops logical admission without discarding any staged-startup state.
    widget._enabled = False

    try:
        clear_pending_playback_pause(widget)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to clear pending playback pause for edit", exc_info=True)

    try:
        widget.detach_from_animation_manager()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to detach animation ticks for edit", exc_info=True)
    try:
        if widget._bars_timer is not None:
            widget._bars_timer.stop()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to stop logical tick for edit", exc_info=True)
    widget._bars_timer = None
    widget._using_animation_ticks = False

    # Release the engine REFERENCE only. The engine object, its generation and
    # its configuration survive; capture follows the authored warm-grace policy.
    engine = getattr(widget, "_engine", None)
    if engine is not None:
        try:
            engine.release()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to release engine for edit", exc_info=True)

    try:
        widget.hide()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to hide visualizer for edit", exc_info=True)

    logger.info(
        "[SPOTIFY_VIS] Visualizer suspended for edit session (reason=%s was_visible=%s)",
        reason,
        was_visible,
    )
    return True


def _arm_edit_resume_reveal(widget: Any) -> None:
    """Arm ONLY the reveal gate, not staged startup.

    Resume still reveals through the current fade/readiness owner: the layer
    was cleared on suspend, so the compositor has to prepare the renderer at
    fade zero again before the visible fade may begin. Going straight to
    ``_start_widget_fade_in()`` would reintroduce a part-way first frame.
    """
    widget._startup_reveal_pending = True
    widget._startup_reveal_token = int(getattr(widget, "_startup_reveal_token", 0)) + 1
    widget._startup_reveal_ready_token = -1
    widget._startup_reveal_not_before_ts = 0.0
    # None of these are startup conditions for a runtime that is already up.
    widget._startup_require_playing_before_reveal = False
    widget._startup_idle_reveal_requires_authoritative_media = False
    widget._startup_has_authoritative_media_update = True


def resume_after_edit(widget: Any, *, reason: str) -> bool:
    """Resume the existing visualizer runtime after an edit session.

    Deliberately not ``start_legacy()``: no staged startup, no secondary-stage
    event, no engine reset and therefore no new engine generation. The runtime
    that was suspended is the runtime that resumes.
    """
    if not is_edit_suspended(widget):
        return False

    from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine

    was_visible = bool(getattr(widget, "_edit_suspend_was_visible", True))
    widget._edit_suspended = False
    widget._edit_suspend_reason = ""
    widget._enabled = True

    seed = getattr(widget, "_seed_playback_state_from_anchor", None)
    if callable(seed):
        try:
            seed(reason=reason, request_refresh_if_missing=False)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to reseed playback state after edit", exc_info=True)

    engine = getattr(widget, "_engine", None)
    if engine is None:
        try:
            engine = get_shared_spotify_beat_engine(widget._bar_count)
            widget._engine = engine
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to resolve engine after edit", exc_info=True)
            engine = None
    if engine is not None:
        try:
            if widget._thread_manager is not None:
                engine.set_thread_manager(widget._thread_manager)
            set_generation = getattr(engine, "set_runtime_generation", None)
            if callable(set_generation):
                set_generation(getattr(widget, "_runtime_generation", None))
            # Re-acquire the reference released by suspend. No reset, so no
            # activation/generation boundary is crossed by cancelling an edit.
            engine.acquire()
            engine.set_playback_state(bool(getattr(widget, "_spotify_playing", False)))
            should_capture = getattr(widget, "_should_capture_audio_now", None)
            if callable(should_capture) and should_capture():
                engine.ensure_started()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to reacquire engine after edit", exc_info=True)

    if widget._thread_manager is not None and widget._bars_timer is None:
        try:
            interval = max(1, int(getattr(widget, "_current_timer_interval_ms", 16) or 16))
            widget._bars_timer = widget._thread_manager.schedule_recurring(
                interval, widget._on_tick
            )
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to restart logical tick after edit", exc_info=True)
            widget._bars_timer = None
    elif widget._animation_manager is not None and widget._anim_listener_id is not None:
        widget._using_animation_ticks = True

    if was_visible:
        _arm_edit_resume_reveal(widget)
        finish_staged_startup_reveal(widget, reason="edit_resume")

    logger.info(
        "[SPOTIFY_VIS] Visualizer resumed after edit session (reason=%s was_visible=%s)",
        reason,
        was_visible,
    )
    return True


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
    from widgets.spotify_visualizer.media_bridge import clear_pending_playback_pause

    if not widget._enabled:
        return
    widget._enabled = False
    try:
        clear_pending_playback_pause(widget)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to clear pending playback pause on stop", exc_info=True)
    try:
        widget._reset_latency_diagnostics()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to reset latency diagnostics on stop", exc_info=True)
    try:
        widget._reset_bubble_cadence()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to reset Bubble cadence on stop", exc_info=True)
    stop_lane = getattr(widget, "_stop_bubble_compute_lane", None)
    if callable(stop_lane):
        stop_lane()
    widget._startup_secondary_stage_pending = False
    widget._startup_hot_start_started = False
    widget._startup_wake_deferred = False
    widget._startup_wake_deferred_reason = ""
    widget._startup_require_playing_before_reveal = False
    widget._startup_idle_reveal_requires_authoritative_media = False
    widget._startup_has_authoritative_media_update = False
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
