"""Mode-transition logic for SpotifyVisualizerWidget.

Extracted to reduce the main widget below the 1500-line monolith threshold.
All functions take the widget instance as the first argument and read/write
its ``_mode_transition_*`` state attributes.

Phase 2 additions: reset_visualizer_state, fade helpers, teardown bookkeeping,
engine prep, shadow cache invalidation.
"""
from __future__ import annotations

import copy
import time
from typing import Any, Callable, Optional

from core.logging.logger import get_logger

logger = get_logger(__name__)


def _clear_mode_activation_commit(widget: Any) -> None:
    """A new switch request invalidates the previous transaction stamp."""
    try:
        widget._mode_activation_committed_for = None
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to clear mode activation commit", exc_info=True)


def _begin_mode_transition_request(widget: Any, target_mode: Any, *, request_kind: str) -> bool:
    if widget._mode_transition_phase != 0:
        return False
    if target_mode == widget._vis_mode:
        return False
    _clear_mode_activation_commit(widget)
    widget._mode_transition_pending = target_mode
    widget._mode_transition_phase = 1
    widget._mode_transition_ts = time.time()
    logger.info(
        "[SPOTIFY_VIS] Mode %s requested: %s -> %s",
        request_kind,
        widget._vis_mode.name,
        target_mode.name,
    )
    return True


def activate_visualization_mode(
    widget: Any,
    mode: Any,
    *,
    reset_runtime: bool = True,
) -> None:
    """Apply a target mode using the canonical direct-switch ordering contract."""
    if mode == widget._vis_mode:
        return
    widget._vis_mode = mode
    try:
        widget._apply_full_runtime_config_for_mode(mode, reason="mode_switch")
        # Stamp this mode as transaction-committed so the later engine-reset
        # phase does not repeat the same configuration work.
        widget._mode_activation_committed_for = mode
    except Exception:
        widget._mode_activation_committed_for = None
        logger.debug("[SPOTIFY_VIS] Failed to apply runtime config on mode switch", exc_info=True)
    widget._last_gpu_geom = None
    widget._last_gpu_fade_sent = -1.0
    widget._has_pushed_first_frame = False
    widget._waiting_for_fresh_engine_frame = True
    widget._waiting_for_fresh_frame = True
    if reset_runtime:
        try:
            reset_mode_owned_runtime_state(widget, reason="mode_switch")
            widget._clear_gl_overlay()
            prepare_engine_for_mode_reset(widget)
            widget._clear_runtime_bar_state()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to prepare engine on mode switch", exc_info=True)
    logger.debug("[SPOTIFY_VIS] Visualization mode changed to %s", mode.name)


def resolve_shared_widget_fade_in_duration_ms() -> int:
    """Return the canonical shared overlay fade-in duration."""

    from widgets.shadow_utils import ShadowFadeProfile

    try:
        return ShadowFadeProfile.default_duration_ms()
    except Exception:
        return max(0, int(getattr(ShadowFadeProfile, "DURATION_MS", 1800)))


def cycle_mode(widget: Any) -> bool:
    """Cycle to the next visualizer mode with a crossfade.

    Returns True if a cycle was initiated, False if already transitioning.
    """
    from widgets.spotify_visualizer.audio_worker import VisualizerMode

    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors

    _CYCLE_MODES = []
    for desc in iter_visualizer_mode_descriptors():
        enum_name = desc.mode_id.upper()
        member = getattr(VisualizerMode, enum_name, None)
        if member is not None:
            _CYCLE_MODES.append(member)
    if not _CYCLE_MODES:
        return False
    try:
        idx = _CYCLE_MODES.index(widget._vis_mode)
    except ValueError:
        idx = -1
    next_mode = _CYCLE_MODES[(idx + 1) % len(_CYCLE_MODES)]
    return _begin_mode_transition_request(widget, next_mode, request_kind="cycle")


def switch_to_mode(widget: Any, mode_id: str) -> bool:
    """Switch to a specific visualizer mode with a crossfade.

    Same transition path as cycle_mode / double-click but targets a
    specific mode by its registry mode_id (e.g. ``"spectrum"``).
    Returns True if initiated, False if already transitioning or same mode.
    """
    from widgets.spotify_visualizer.audio_worker import VisualizerMode

    target_enum = getattr(VisualizerMode, mode_id.upper(), None)
    if target_enum is None:
        logger.warning("[SPOTIFY_VIS] Unknown mode_id for switch: %s", mode_id)
        return False
    return _begin_mode_transition_request(widget, target_enum, request_kind="switch")


def _activate_pending_mode_after_fade_out(widget: Any, *, resume_ts: float) -> None:
    pending = getattr(widget, "_mode_transition_pending", None)
    if pending is None:
        return
    try:
        setattr(widget, "_mode_transition_resume_ts", resume_ts)
    except Exception:
        setattr(widget, "_mode_transition_resume_ts", 0.0)
    # ONE target activation transaction.
    #
    # activate_visualization_mode() performs the full runtime apply, but it
    # returns early when the target equals the current mode - which is exactly
    # what a PRESET cycle looks like. In that shape this call was historically
    # the only apply that ran, so it stays load-bearing and must still happen.
    # Applying in both shapes would be the duplicate transaction that produced
    # triple configuration work and duplicate engine-generation churn.
    mode_changed = pending != widget._vis_mode
    activate_visualization_mode(widget, pending, reset_runtime=False)
    widget._mode_transition_pending = None

    if not mode_changed:
        apply_full = getattr(widget, "_apply_full_runtime_config_for_mode", None)
        if callable(apply_full):
            try:
                # Deliberately NOT stamped: a same-mode transition is a preset
                # cycle, and the engine-reset phase must still apply technical
                # config there because that is what discards engine bleed from
                # the previous preset.
                apply_full(widget._vis_mode, reason="mode_fade_out_complete")
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to apply target config at fade completion", exc_info=True)

    request_overlay_reset = getattr(widget, "_request_overlay_mode_reset", None)
    if callable(request_overlay_reset):
        try:
            request_overlay_reset(mode=widget._vis_mode_str, reason="mode_fade_out_complete")
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to request target overlay reset at fade completion", exc_info=True)


def mode_transition_fade_factor(widget: Any, now_ts: float) -> float:
    """Return a 0..1 fade multiplier for the mode crossfade.

    Driven entirely from the existing tick — no timers or polling.
    Returns 1.0 when no transition is active (zero cost).
    """
    phase = widget._mode_transition_phase
    if phase == 0:
        return 1.0

    elapsed = now_ts - widget._mode_transition_ts
    dur = widget._mode_transition_duration

    if phase == 1:
        # Fading out
        t = min(1.0, elapsed / dur) if dur > 0 else 1.0
        if t >= 1.0:
            # GPU fade-out complete. The actual target-mode activation is
            # owned by on_mode_fade_out_complete(), after the old GL overlay is
            # destroyed. Pushing target frames before that teardown was the
            # source of runtime-only mode bleed.
            try:
                setattr(widget, "_mode_transition_resume_ts", now_ts)
            except Exception:
                setattr(widget, "_mode_transition_resume_ts", 0.0)
            widget._mode_transition_phase = 3  # waiting-for-ready
            widget._mode_transition_ts = now_ts
            if getattr(widget, "_mode_teardown_state", "idle") != "fading_out":
                # Unit/direct path with no ShadowFadeProfile callback.
                on_mode_fade_out_complete(widget)
            return 0.0
        return 1.0 - t

    if phase == 3:
        # Waiting for teardown → reinit pipeline to finish. Bars stay hidden.
        return 0.0

    if phase == 2:
        # Fading in
        t = min(1.0, elapsed / dur) if dur > 0 else 1.0
        if t >= 1.0:
            # Transition complete — persist mode
            widget._mode_transition_phase = 0
            widget._mode_transition_ts = 0.0
            try:
                widget._mode_transition_resume_ts = 0.0
            except Exception:
                pass
            persist_vis_mode(widget)
            return 1.0
        return t

    return 1.0


def persist_vis_mode(widget: Any) -> None:
    """Save the current visualizer mode to SettingsManager (if available)."""
    wm = getattr(widget, '_widget_manager', None)
    if wm is None:
        return
    sm = getattr(wm, '_settings_manager', None)
    if sm is None:
        return
    try:
        mode_str = widget._vis_mode_str
        current_mode = sm.get('widgets.spotify_visualizer.mode', None)
        if current_mode != mode_str:
            sm.set('widgets.spotify_visualizer.mode', mode_str)
            logger.debug("[SPOTIFY_VIS] Persisted vis mode: %s", mode_str)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to persist vis mode", exc_info=True)


# ------------------------------------------------------------------
# Phase 2: Visualizer state reset
# ------------------------------------------------------------------

def reset_visualizer_state(
    widget: Any,
    *,
    clear_overlay: bool = False,
    replay_cached: bool = False,
) -> None:
    """Clear runtime visualizer state so the next mode behaves like a cold start."""
    reset_mode_owned_runtime_state(widget, reason="widget_reset_state")
    zeros = [0.0] * widget._bar_count
    widget._display_bars = list(zeros)
    widget._target_bars = list(zeros)
    widget._visual_bars = list(zeros)
    widget._per_bar_energy = list(zeros)
    widget._geom_cache_rect = None
    widget._geom_cache_bar_count = widget._bar_count
    widget._geom_cache_segments = widget._bar_segments_base
    widget._geom_bar_x = []
    widget._geom_seg_y = []
    widget._geom_bar_width = 0
    widget._geom_seg_height = 0
    widget._last_update_ts = -1.0
    widget._last_smooth_ts = 0.0
    widget._has_pushed_first_frame = False
    widget._last_gpu_geom = None
    widget._last_gpu_fade_sent = -1.0
    resume_ts = 0.0
    if getattr(widget, "_mode_transition_phase", 0) != 0:
        resume_ts = float(
            getattr(widget, "_mode_transition_resume_ts", 0.0)
            or getattr(widget, "_mode_transition_ts", 0.0)
            or 0.0
        )
    widget._mode_transition_ts = resume_ts if resume_ts > 0.0 else 0.0
    widget._mode_transition_resume_ts = 0.0
    widget._perf_tick_start_ts = None
    widget._perf_tick_last_ts = None
    widget._perf_tick_frame_count = 0
    widget._perf_tick_min_dt = 0.0
    widget._perf_tick_max_dt = 0.0
    widget._perf_paint_start_ts = None
    widget._perf_paint_last_ts = None
    widget._perf_paint_frame_count = 0
    widget._perf_paint_min_dt = 0.0
    widget._perf_paint_max_dt = 0.0
    widget._perf_audio_lag_last_ms = 0.0
    widget._perf_audio_lag_min_ms = 0.0
    widget._perf_audio_lag_max_ms = 0.0
    widget._perf_last_log_ts = None
    widget._last_tick_spike_log_ts = 0.0
    widget._fallback_mismatch_start = 0.0
    widget._fallback_forced_until = 0.0
    widget._bubble_pos_data = []
    widget._bubble_extra_data = []
    widget._bubble_trail_data = []
    widget._bubble_count = 0
    widget._bubble_compute_pending = False
    clear_pending_bubble_result = getattr(widget, "_clear_pending_bubble_result", None)
    if callable(clear_pending_bubble_result):
        clear_pending_bubble_result()
    widget._bubble_pending_result_skip_count = 0
    widget._bubble_last_tick_ts = 0.0
    # Reset the CPU-side bubble simulation so stale running averages,
    # burst state, and beat timestamps don't bleed across mode switches.
    reset_bubble_simulation = getattr(widget, "_reset_bubble_simulation", None)
    if callable(reset_bubble_simulation):
        try:
            reset_bubble_simulation()
        except Exception:
            pass
    else:
        bubble_sim = getattr(widget, '_bubble_simulation', None)
        if bubble_sim is not None:
            try:
                bubble_sim.reset()
            except Exception:
                pass
    widget._heartbeat_intensity = 0.0
    widget._heartbeat_avg_bass = 0.0
    widget._heartbeat_last_ts = 0.0
    widget._waiting_for_fresh_frame = False
    widget._waiting_for_fresh_engine_frame = False
    widget._pending_engine_generation = -1
    widget._last_engine_generation_seen = -1
    widget._pending_engine_activation_id = -1
    widget._last_engine_activation_seen = -1
    widget._first_overlay_push_probe_key = None
    widget._request_overlay_mode_reset(reason="widget_reset_state")
    if clear_overlay:
        widget._clear_gl_overlay()
    widget._reset_engine_state(reason="widget_reset_state")
    if replay_cached and widget._cached_vis_kwargs:
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs
        try:
            apply_vis_mode_kwargs(widget, copy.deepcopy(widget._cached_vis_kwargs))
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to replay cached settings during reset", exc_info=True)


def reset_mode_owned_runtime_state(widget: Any, *, reason: str = "mode_activation") -> None:
    """Clear widget-owned visual accumulators that a settings restart recreates.

    This deliberately leaves authored settings/config fields alone. It only
    resets live envelopes, sampled frames, animation phases, and diagnostics
    that can bleed when switching modes or presets without reconstructing the
    widget.
    """
    from widgets.spotify_visualizer.spectrum_presentation_smoothing import (
        reset_widget_spectrum_presentation_smoothing,
    )

    reset_widget_spectrum_presentation_smoothing(widget)

    for attr in (
        "_last_visual_smooth_ts",
        "_heartbeat_intensity",
        "_heartbeat_avg_bass",
        "_heartbeat_fast_bass",
        "_heartbeat_floor_bass",
        "_heartbeat_fast_prev",
        "_heartbeat_last_ts",
        "_heartbeat_last_log_ts",
        "_heartbeat_last_trigger_ts",
        "_crawl_last_log_ts",
        "_latency_last_log_ts",
        "_last_peak_ts",
        "_bubble_last_tick_ts",
        "_devcurve_last_tick_ts",
        "_devcurve_smoothness_max_step",
        "_devcurve_active_amplitude",
        "_devcurve_idle_amplitude",
        "_devcurve_foreground_travel_rate",
        "_devcurve_foreground_travel_pos",
        "_devcurve_specular_travel_rate",
        "_devcurve_specular_activity_alpha",
        "_devcurve_diag_last_log_ts",
        "_line_smoothed_bass",
        "_line_smoothed_mid",
        "_line_smoothed_high",
        "_line_kick_event_strength",
        "_line_snare_event_strength",
        "_line_kick_event_envelope",
        "_line_snare_event_envelope",
        "_sine_peak_bass",
        "_sine_peak_mid",
        "_sine_peak_high",
        "_sine_peak_hold_remaining",
    ):
        try:
            setattr(widget, attr, 0.0)
        except Exception:
            pass

    for attr in (
        "_devcurve_curve_bass",
        "_devcurve_curve_vocals",
        "_devcurve_curve_mids",
        "_devcurve_curve_transients",
        "_bubble_pos_data",
        "_bubble_extra_data",
        "_bubble_trail_data",
        "_peaks",
    ):
        try:
            setattr(widget, attr, [])
        except Exception:
            pass

    for attr in (
        "_devcurve_runtime_state",
        "_latency_last_signature",
    ):
        try:
            setattr(widget, attr, None)
        except Exception:
            pass

    try:
        widget._devcurve_sample_count = 0
        widget._devcurve_foreground_layer = ""
        widget._devcurve_foreground_layer_id = -1
        widget._devcurve_specular_slot0 = [0.0, 0.0, 0.0, 0.0]
        widget._devcurve_specular_slot1 = [0.0, 0.0, 0.0, 0.0]
        widget._devcurve_specular_slot2 = [0.0, 0.0, 0.0, 0.0]
        widget._devcurve_draw_order = ["bass", "vocals", "mids", "transients"]
    except Exception:
        pass

    try:
        widget._bubble_count = 0
        reset_bubble_cadence = getattr(widget, "_reset_bubble_cadence", None)
        if callable(reset_bubble_cadence):
            reset_bubble_cadence()
        else:
            widget._bubble_compute_pending = False
            clear_pending_bubble_result = getattr(widget, "_clear_pending_bubble_result", None)
            if callable(clear_pending_bubble_result):
                clear_pending_bubble_result()
        widget._bubble_pending_result_skip_count = 0
        reset_bubble_simulation = getattr(widget, "_reset_bubble_simulation", None)
        if callable(reset_bubble_simulation):
            reset_bubble_simulation()
        else:
            bubble_sim = getattr(widget, "_bubble_simulation", None)
            if bubble_sim is not None and hasattr(bubble_sim, "reset"):
                bubble_sim.reset()
    except Exception:
        pass

    try:
        zeros = [0.0] * int(getattr(widget, "_bar_count", 0))
        widget._display_bars = list(zeros)
        widget._target_bars = list(zeros)
        widget._visual_bars = list(zeros)
        widget._per_bar_energy = list(zeros)
        widget._has_pushed_first_frame = False
        widget._last_gpu_geom = None
        widget._last_gpu_fade_sent = -1.0
        widget._display_bars_source_generation = -1
        widget._display_bars_source_activation = -1
        widget._target_bars_source_generation = -1
        widget._target_bars_source_activation = -1
        widget._visual_bars_source_generation = -1
        widget._visual_bars_source_activation = -1
        widget._per_bar_energy_source_generation = -1
        widget._per_bar_energy_source_activation = -1
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to clear runtime bar arrays during mode-owned reset", exc_info=True)

    logger.debug("[SPOTIFY_VIS] Mode-owned runtime state reset reason=%s", reason)


# ------------------------------------------------------------------
# Phase 2: Widget fade in/out
# ------------------------------------------------------------------

def start_widget_fade_in(widget: Any, duration_ms: Optional[int] = None) -> None:
    """Begin the one compositor-owned visualizer fade.

    The card and the visualizer shader are both drawn by the display
    compositor, so a ``QGraphicsOpacityEffect`` on this QWidget cannot fade
    those pixels; relying on it produced a fade whose first half had no pixel
    owner and whose remainder slammed in. The fade authority is now explicit
    and is the sole input to both compositor layers.

    Showing the widget is safe here because compositor card-visual ownership
    was claimed during fade-zero readiness preparation, so ``paintEvent``
    already returns early and the card cannot flash at full opacity.
    """
    from widgets.spotify_visualizer.presentation_fade import ensure_presentation_fade

    if duration_ms is None:
        duration_ms = resolve_shared_widget_fade_in_duration_ms()

    fade = ensure_presentation_fade(widget)

    try:
        widget.show()
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

    if duration_ms <= 0:
        fade.jump_to(1.0)
        return

    fade.begin_fade_in(duration_ms=duration_ms)


def start_widget_fade_out(
    widget: Any,
    duration_ms: int = 1200,
    on_complete: Optional[Callable[[], None]] = None,
) -> None:
    """Fade the compositor-owned visualizer scene out through the same authority.

    Hiding does NOT destroy the visualizer GL resources: the card texture,
    programs and VAO/VBO belong to the compositor generation, and an ordinary
    hide/pause must leave them intact.
    """
    from widgets.spotify_visualizer.presentation_fade import ensure_presentation_fade

    fade = ensure_presentation_fade(widget)
    try:
        fade.begin_fade_out(duration_ms=duration_ms, on_finished=on_complete)
    except Exception:
        logger.warning(
            "[SPOTIFY_VIS][FALLBACK] Fade-out failed; using direct hide", exc_info=True
        )
        try:
            fade.jump_to(0.0)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        try:
            widget.hide()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        if on_complete is not None:
            try:
                on_complete()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed in fade-out callback: %s", e)


# ------------------------------------------------------------------
# Phase 2: Teardown bookkeeping & engine prep
# ------------------------------------------------------------------

def reset_teardown_bookkeeping(widget: Any) -> None:
    """Reset all mode-teardown state to idle."""
    widget._mode_transition_ready = False
    widget._mode_transition_phase = 0
    widget._mode_transition_resume_ts = 0.0
    widget._mode_transition_apply_height_on_resume = False
    widget._pending_shadow_cache_invalidation = False
    widget._mode_teardown_state = "idle"
    widget._mode_teardown_target_generation = -1
    widget._mode_teardown_wait_started_ts = 0.0
    widget._mode_teardown_block_until_ready = False


def on_mode_cycle_requested(widget: Any) -> None:
    """Begin the fade-out phase of a mode cycle."""
    widget._mode_transition_ready = False
    if widget._mode_teardown_state == 'fading_out':
        return
    widget._mode_teardown_state = 'fading_out'
    widget._mode_teardown_block_until_ready = False
    widget._mode_teardown_target_generation = -1
    widget._mode_teardown_wait_started_ts = 0.0
    start_widget_fade_out(widget, on_complete=lambda: on_mode_fade_out_complete(widget))


def on_mode_fade_out_complete(widget: Any) -> None:
    """Called when mode-cycle fade-out finishes."""
    from shiboken6 import Shiboken

    if not Shiboken.isValid(widget):
        return
    if (
        getattr(widget, "_mode_teardown_state", "idle") == "waiting_bars"
        and getattr(widget, "_mode_transition_pending", None) is None
    ):
        return
    widget._clear_gl_overlay()
    _activate_pending_mode_after_fade_out(widget, resume_ts=time.time())
    widget._mode_transition_phase = 3
    widget._mode_teardown_state = 'waiting_bars'
    widget._mode_teardown_block_until_ready = True
    widget._mode_teardown_wait_started_ts = time.time()
    widget._pending_shadow_cache_invalidation = True
    reset_mode_owned_runtime_state(widget, reason="mode_fade_out_complete")
    log_render = getattr(widget, "_log_active_render_state_snapshot", None)
    if callable(log_render):
        try:
            log_render(reason="after_full_runtime_fade_out_complete")
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to log render state after fade_out_complete", exc_info=True)
    try:
        widget._clear_runtime_bar_state()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to clear runtime bars before mode activation", exc_info=True)
    prepare_engine_for_mode_reset(widget)


def prepare_engine_for_mode_reset(widget: Any) -> None:
    """Cancel pending compute, reset engine state, track generation."""
    from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine

    widget._mode_teardown_target_generation = -1
    try:
        engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        engine = None
    if engine is None:
        return
    # The stamp is single-use: it suppresses exactly the applies belonging to
    # its own activation transaction. Leaving it set would make a later preset
    # cycle, settings apply or engine replacement silently skip configuration it
    # genuinely needs.
    committed_for = getattr(widget, "_mode_activation_committed_for", None)
    widget._mode_activation_committed_for = None
    transaction_owns_config = committed_for == widget._vis_mode

    try:
        # All three historical apply sites are retained, because each one is the
        # ONLY apply for some entry shape: a direct mode switch, a same-mode
        # preset cycle, and a plain engine reset. They are now guarded by a
        # single-use transaction stamp instead, so exactly one of them runs per
        # mode switch while every other entry point keeps working.
        if not transaction_owns_config:
            apply_full = getattr(widget, "_apply_full_runtime_config_for_mode", None)
            if callable(apply_full):
                try:
                    apply_full(widget._vis_mode, reason="mode_prepare_reset")
                except Exception:
                    logger.debug(
                        "[SPOTIFY_VIS] Failed to apply target config before engine reset",
                        exc_info=True,
                    )
        log_render = getattr(widget, "_log_active_render_state_snapshot", None)
        if callable(log_render):
            try:
                log_render(reason="after_full_runtime_prepare_reset")
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to log render state after prepare_reset", exc_info=True)
        engine.cancel_pending_compute_tasks()
        engine.reset_smoothing_state()
        engine.reset_floor_state()
        engine.set_smoothing(widget._smoothing)
        try:
            widget._reset_latency_diagnostics()
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] Failed to reset latency diagnostics for mode reset",
                exc_info=True,
            )

        # Ensure technical config cache is populated before applying config
        settings_model = getattr(widget, "_settings_model", None)
        if transaction_owns_config:
            settings_model = None
        if settings_model is not None:
            build_cache = getattr(widget, "_build_technical_cache", None)
            if callable(build_cache):
                try:
                    widget._technical_config_cache = build_cache(settings_model)
                    logger.debug("[SPOTIFY_VIS] Rebuilt technical config cache during mode reset, modes=%d", len(widget._technical_config_cache))
                except Exception:
                    logger.debug("[SPOTIFY_VIS] Failed to rebuild technical config cache during mode reset", exc_info=True)
            else:
                logger.debug("[SPOTIFY_VIS] Widget has settings_model but no _build_technical_cache method")
        else:
            logger.debug("[SPOTIFY_VIS] Widget has no settings_model, cannot rebuild technical config cache")

        apply_technical = getattr(widget, "_apply_technical_config_for_mode", None)
        if callable(apply_technical) and not transaction_owns_config:
            apply_technical(widget._vis_mode, reason="mode_prepare_reset")
            log_render = getattr(widget, "_log_active_render_state_snapshot", None)
            if callable(log_render):
                try:
                    log_render(reason="after_technical_config_prepare_reset")
                except Exception:
                    logger.debug("[SPOTIFY_VIS] Failed to log render state after technical config", exc_info=True)
            try:
                mode_name = getattr(widget._vis_mode, "name", str(widget._vis_mode))
                tech = getattr(widget, "_get_mode_technical_config", None)
                if callable(tech):
                    tech_cfg = tech(widget._vis_mode)
                    logger.info(
                        "[SPOTIFY_VIS][MODE_RESET_ASSERT] mode=%s expected_dynamic=%s expected_manual=%.3f "
                        "expected_sensitivity=%.3f expected_block=%s expected_input_gain=%.3f",
                        mode_name,
                        bool(tech_cfg.get("dynamic_floor", True)) if tech_cfg else None,
                        float(tech_cfg.get("manual_floor", 0.12)) if tech_cfg else -1.0,
                        float(tech_cfg.get("sensitivity", 1.0)) if tech_cfg else -1.0,
                        int(tech_cfg.get("audio_block_size", 0) or 0) if tech_cfg else -1,
                        float(tech_cfg.get("input_gain", 1.0)) if tech_cfg else -1.0,
                    )
                else:
                    logger.warning("[SPOTIFY_VIS][MODE_RESET_ASSERT] mode=%s _get_mode_technical_config not callable", mode_name)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed mode reset config assertion log", exc_info=True)
        should_capture = bool(getattr(widget, "_spotify_playing", False))
        _capture_helper = getattr(widget, "_should_capture_audio_now", None)
        if callable(_capture_helper):
            try:
                should_capture = bool(_capture_helper())
            except Exception:
                should_capture = bool(getattr(widget, "_spotify_playing", False))
        if should_capture:
            engine.ensure_started()
        else:
            engine.set_playback_state(False)
        widget._mode_teardown_target_generation = engine.get_generation_id()
        widget._track_engine_generation(engine)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to prepare engine for mode reset", exc_info=True)


def begin_mode_fade_in(widget: Any, now_ts: float) -> None:
    """Transition from waiting-for-bars to fade-in phase."""
    if widget._mode_transition_phase == 3:
        widget._mode_transition_phase = 2
        widget._mode_transition_ts = now_ts
    elif widget._mode_transition_phase == 0:
        widget._mode_transition_phase = 2
        widget._mode_transition_ts = now_ts
    widget._mode_transition_ready = True
    widget._mode_teardown_state = 'fading_in'
    widget._mode_teardown_block_until_ready = False
    invalidate_shadow_cache_if_needed(widget)
    apply_pending_mode_transition_layout(widget)
    try:
        start_widget_fade_in(widget)
    except Exception:
        logger.warning("[SPOTIFY_VIS][FALLBACK] Mode fade-in fallback path", exc_info=True)


def check_mode_teardown_ready(widget: Any, engine: Any, now_ts: float) -> None:
    """Check if the engine has delivered a fresh frame after mode reset."""
    if widget._mode_teardown_state != 'waiting_bars':
        return
    ready = False
    wait_started = float(getattr(widget, "_mode_teardown_wait_started_ts", 0.0) or 0.0)
    if wait_started <= 0.0:
        wait_started = float(getattr(widget, "_mode_transition_ts", 0.0) or now_ts)
    waited_s = max(0.0, now_ts - wait_started)
    capture_now = False
    _capture_helper = getattr(widget, "_should_capture_audio_now", None)
    if callable(_capture_helper):
        try:
            capture_now = bool(_capture_helper())
        except Exception:
            capture_now = bool(getattr(widget, "_spotify_playing", False))
    else:
        capture_now = bool(getattr(widget, "_spotify_playing", False))
    if engine is not None and widget._mode_teardown_target_generation > 0:
        try:
            latest = engine.get_latest_generation_with_frame()
        except Exception:
            latest = -1
        waveform_ready = True
        if getattr(widget, "_vis_mode_str", "") in {"oscilloscope", "sine_wave"}:
            try:
                latest_waveform = engine.get_latest_generation_with_waveform()
            except Exception:
                latest_waveform = -1
            waveform_ready = latest_waveform >= widget._mode_teardown_target_generation
        if latest >= widget._mode_teardown_target_generation and waveform_ready:
            ready = True
    # Never allow permanent waiting_bars deadlocks.
    # Paused/idle mode cycles must complete without worker frames.
    timeout_s = 1.50 if capture_now else 0.35
    if not ready and waited_s >= timeout_s:
        ready = True
        logger.warning(
            "[SPOTIFY_VIS][FALLBACK] Mode teardown timeout fallback "
            "(capture_now=%s waited=%.2fs target_gen=%s)",
            capture_now,
            waited_s,
            getattr(widget, "_mode_teardown_target_generation", -1),
        )
    if ready and not widget._mode_transition_ready:
        widget._mode_teardown_state = 'ready'
        begin_mode_fade_in(widget, now_ts)


def apply_pending_mode_transition_layout(widget: Any) -> None:
    """Apply deferred card height change after mode switch."""
    if not widget._mode_transition_apply_height_on_resume:
        return
    widget._mode_transition_apply_height_on_resume = False
    try:
        widget._apply_preferred_height()
        widget._request_reposition()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Deferred card height apply failed", exc_info=True)


def invalidate_shadow_cache_if_needed(widget: Any) -> None:
    """Clear transient opacity state after mode switch."""

    if not widget._pending_shadow_cache_invalidation:
        return
    widget._pending_shadow_cache_invalidation = False
    try:
        effect = widget.graphicsEffect()
    except Exception:
        effect = None
    if effect is not None:
        try:
            widget.setGraphicsEffect(None)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to clear graphics effect during shadow reset", exc_info=True)
    try:
        setattr(widget, "_shadowfade_effect", None)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to reset shadowfade effect handle", exc_info=True)
    try:
        setattr(widget, "_shadowfade_anim", None)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to reset shadowfade anim handle", exc_info=True)


def on_first_frame_after_cold_start(widget: Any) -> None:
    """Refresh painted shadow state after the first GPU frame arrives."""
    from widgets.shadow_utils import ShadowFadeProfile

    if not getattr(widget, "_waiting_for_fresh_frame", False):
        return
    widget._waiting_for_fresh_frame = False
    if getattr(widget, "_shadow_config_missing", False):
        if widget._shadow_config is not None:
            try:
                ShadowFadeProfile.attach_shadow(
                    widget,
                    widget._shadow_config,
                    has_background_frame=widget._show_background,
                )
                logger.debug("[SPOTIFY_VIS] Painted shadow refreshed after fresh frame")
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to refresh shadow after fresh frame", exc_info=True)
        widget._shadow_config_missing = False
    try:
        finish_reveal = getattr(widget, "_finish_staged_startup_reveal", None)
        if callable(finish_reveal):
            finish_reveal(reason="fresh_frame")
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed staged startup reveal after fresh frame", exc_info=True)


def get_scene_fade_factor(widget: Any, now_ts: float) -> float:
    """Return the ONE authoritative visualizer scene fade progress.

    This is the authored 1800 ms InOutCubic reveal progress owned by
    ``VisualizerPresentationFade``. The authored card/background/border/shadow
    pixels use it directly - which is what the QWidget opacity effect used to
    provide before the compositor owned those pixels.

    It deliberately does NOT consult ``_shadowfade_progress``,
    ``_shadowfade_completed`` or widget visibility. Those made fade progress
    reachable by a second owner, so the fade could jump to full opacity simply
    because a QGraphicsOpacityEffect had been torn down.
    """
    del now_ts  # progress is animation-driven, not sampled from a clock here
    from widgets.spotify_visualizer.presentation_fade import ensure_presentation_fade

    try:
        return ensure_presentation_fade(widget).card_fade()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Scene fade unavailable", exc_info=True)
        return 0.0


def get_gpu_fade_factor(widget: Any, now_ts: float) -> float:
    """Return the visualizer shader fade for the current scene fade progress.

    The authored stagger - bars arrive after the card/shadow are established -
    is preserved, but it is now a pure function of the same single fade
    progress rather than a separate curve reading a widget side-channel.
    """
    del now_ts
    from widgets.spotify_visualizer.presentation_fade import ensure_presentation_fade

    try:
        return ensure_presentation_fade(widget).bars_fade()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Bars fade unavailable", exc_info=True)
        return 0.0
