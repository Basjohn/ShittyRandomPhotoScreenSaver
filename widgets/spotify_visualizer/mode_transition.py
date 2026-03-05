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


def cycle_mode(widget: Any) -> bool:
    """Cycle to the next visualizer mode with a crossfade.

    Returns True if a cycle was initiated, False if already transitioning.
    """
    from widgets.spotify_visualizer.audio_worker import VisualizerMode

    if widget._mode_transition_phase != 0:
        return False

    _CYCLE_MODES = [
        VisualizerMode.SPECTRUM,
        VisualizerMode.OSCILLOSCOPE,
        VisualizerMode.SINE_WAVE,
        VisualizerMode.BLOB,
        VisualizerMode.BUBBLE,
    ]
    try:
        idx = _CYCLE_MODES.index(widget._vis_mode)
    except ValueError:
        idx = -1
    next_mode = _CYCLE_MODES[(idx + 1) % len(_CYCLE_MODES)]
    widget._mode_transition_pending = next_mode
    widget._mode_transition_phase = 1  # start fade-out
    widget._mode_transition_ts = time.time()
    logger.info("[SPOTIFY_VIS] Mode cycle requested: %s -> %s", widget._vis_mode.name, next_mode.name)
    return True


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
            # Fade-out complete: switch mode, begin fade-in
            pending = widget._mode_transition_pending
            if pending is not None:
                try:
                    setattr(widget, "_mode_transition_resume_ts", now_ts)
                except Exception:
                    setattr(widget, "_mode_transition_resume_ts", 0.0)
                try:
                    widget._reset_visualizer_state(
                        clear_overlay=False,
                        replay_cached=bool(getattr(widget, "_cached_vis_kwargs", None)),
                    )
                except Exception:
                    logger.debug("[SPOTIFY_VIS] Mode reset helper failed", exc_info=True)
                widget.set_visualization_mode(pending)
                widget._mode_transition_pending = None
            widget._mode_transition_phase = 3  # waiting-for-ready
            widget._mode_transition_ts = now_ts
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
        cfg = sm.get('widgets', {}) or {}
        vis_cfg = cfg.get('spotify_visualizer', {}) or {}
        if vis_cfg.get('mode') != mode_str:
            vis_cfg['mode'] = mode_str
            cfg['spotify_visualizer'] = vis_cfg
            sm.set('widgets', cfg)
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
        resume_ts = float(getattr(widget, "_mode_transition_resume_ts", 0.0) or 0.0)
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
    widget._bubble_last_tick_ts = 0.0
    widget._heartbeat_intensity = 0.0
    widget._heartbeat_avg_bass = 0.0
    widget._heartbeat_last_ts = 0.0
    widget._waiting_for_fresh_frame = False
    widget._waiting_for_fresh_engine_frame = False
    widget._pending_engine_generation = -1
    widget._last_engine_generation_seen = -1
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


# ------------------------------------------------------------------
# Phase 2: Widget fade in/out
# ------------------------------------------------------------------

def start_widget_fade_in(widget: Any, duration_ms: int = 1500) -> None:
    """Fade the visualizer card in via ShadowFadeProfile."""
    from widgets.shadow_utils import apply_widget_shadow, ShadowFadeProfile

    if duration_ms <= 0:
        try:
            widget.show()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        try:
            ShadowFadeProfile.attach_shadow(
                widget,
                widget._shadow_config,
                has_background_frame=widget._show_background,
            )
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] Failed to attach shadow in no-fade path",
                exc_info=True,
            )
        return

    try:
        ShadowFadeProfile.start_fade_in(
            widget,
            widget._shadow_config,
            has_background_frame=widget._show_background,
        )
    except Exception:
        logger.debug(
            "[SPOTIFY_VIS] _start_widget_fade_in fallback path triggered",
            exc_info=True,
        )
        try:
            widget.show()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        if widget._shadow_config is not None:
            try:
                apply_widget_shadow(
                    widget,
                    widget._shadow_config,
                    has_background_frame=widget._show_background,
                )
            except Exception:
                logger.debug(
                    "[SPOTIFY_VIS] Failed to apply widget shadow in fallback path",
                    exc_info=True,
                )


def start_widget_fade_out(
    widget: Any,
    duration_ms: int = 1200,
    on_complete: Optional[Callable[[], None]] = None,
) -> None:
    """Fade the visualizer card out via ShadowFadeProfile."""
    from widgets.shadow_utils import ShadowFadeProfile

    try:
        ShadowFadeProfile.start_fade_out(
            widget,
            duration_ms=duration_ms,
            on_complete=on_complete,
        )
    except Exception:
        logger.debug("[SPOTIFY_VIS] _start_widget_fade_out fallback triggered", exc_info=True)
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
    widget._clear_gl_overlay()
    widget._mode_teardown_state = 'waiting_bars'
    widget._mode_teardown_block_until_ready = True
    widget._mode_teardown_wait_started_ts = time.time()
    widget._pending_shadow_cache_invalidation = True
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
    try:
        engine.cancel_pending_compute_tasks()
        engine.reset_smoothing_state()
        engine.reset_floor_state()
        engine.set_smoothing(widget._smoothing)
        widget._replay_engine_config(engine)
        engine.ensure_started()
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
        start_widget_fade_in(widget, 1500)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Mode fade-in fallback path", exc_info=True)


def check_mode_teardown_ready(widget: Any, engine: Any, now_ts: float) -> None:
    """Check if the engine has delivered a fresh frame after mode reset."""
    if widget._mode_teardown_state != 'waiting_bars':
        return
    ready = False
    if engine is not None and widget._mode_teardown_target_generation > 0:
        try:
            latest = engine.get_latest_generation_with_frame()
        except Exception:
            latest = -1
        if latest >= widget._mode_teardown_target_generation:
            ready = True
    elif (now_ts - widget._mode_teardown_wait_started_ts) >= 0.75:
        ready = True
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
    """Clear the cached shadow effect so it can be recreated after mode switch."""
    from widgets.shadow_utils import clear_cached_shadow_for_widget

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
        clear_cached_shadow_for_widget(widget)
        logger.debug("[SPOTIFY_VIS] Shadow cache cleared for widget=%s", hex(id(widget)))
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to clear cached shadow entry", exc_info=True)
    try:
        setattr(widget, "_shadowfade_effect", None)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to reset shadowfade effect handle", exc_info=True)
    try:
        setattr(widget, "_shadowfade_anim", None)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to reset shadowfade anim handle", exc_info=True)


def on_first_frame_after_cold_start(widget: Any) -> None:
    """Reattach shadow after the first GPU frame arrives."""
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
                logger.debug("[SPOTIFY_VIS] Shadow reattached after fresh frame")
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to reattach shadow after fresh frame", exc_info=True)
        widget._shadow_config_missing = False


def get_gpu_fade_factor(widget: Any, now_ts: float) -> float:
    """Return fade factor for GPU bars based on ShadowFadeProfile.

    We prefer the shared ShadowFadeProfile progress when available so that
    the GL overlay tracks the exact same curve. When no progress is
    present we fall back to 1.0 while the widget is visible.
    """
    try:
        prog = getattr(widget, "_shadowfade_progress", None)
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        prog = None

    if isinstance(prog, (float, int)):
        p = float(prog)
        if p <= 0.0:
            return 0.0
        if p >= 1.0:
            return 1.0

        # Clamp first, then apply a stronger delay so bars fade in well
        # after the card/shadow begin fading.
        p = max(0.0, min(1.0, p))
        delay = 0.65
        if p <= delay:
            return 0.0
        t = (p - delay) / (1.0 - delay)
        # Slower cubic ease-in
        t = t * t * t
        return max(0.0, min(1.0, t))

    # Fallback: when ShadowFadeProfile progress is unavailable
    try:
        completed = getattr(widget, "_shadowfade_completed", False)
        if completed and widget.isVisible():
            return 1.0
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
    return 0.0
