"""Engine state management and audio fallback logic for SpotifyVisualizerWidget.

Extracted to reduce the main widget below the 2000-line threshold.
All functions take the widget instance as the first argument.

Phase 3 of the Visualizer Architecture Split.
"""
from __future__ import annotations

import time
from typing import Any, List, Optional

from core.logging.logger import get_logger

logger = get_logger(__name__)


def reset_engine_state(widget: Any, *, reason: str) -> None:
    """Hard-reset beat engine + widget bar/energy state after crossover."""
    from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine

    try:
        engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        engine = None

    if engine is not None:
        try:
            engine.cancel_pending_compute_tasks()
            engine.reset_smoothing_state()
            engine.reset_floor_state()
            engine.set_smoothing(widget._smoothing)
            widget._replay_engine_config(engine)
            # Reapply the active mode's technical config so manual/dynamic floors
            # and sensitivity caches refresh whenever the engine is reset.
            widget._apply_technical_config_for_mode(
                widget._vis_mode,
                reason=f"engine_reset:{reason}" if reason else "engine_reset",
            )
            if should_capture_audio_now(widget):
                engine.ensure_started()
            else:
                engine.set_playback_state(False)
            track_engine_generation(widget, engine)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to reset engine state", exc_info=True)

    zeros = [0.0] * widget._bar_count
    widget._display_bars = list(zeros)
    widget._target_bars = list(zeros)
    widget._visual_bars = list(zeros)
    widget._per_bar_energy = list(zeros)
    widget._waiting_for_fresh_engine_frame = True
    widget._waiting_for_fresh_frame = True
    if reason:
        logger.debug("[SPOTIFY_VIS] Engine state reset reason=%s", reason)


def reset_runtime_activation_state(widget: Any, *, reason: str = "activation") -> None:
    """Cold-reset visualizer runtime state after a mode or preset activation."""
    widget._waiting_for_fresh_engine_frame = True
    widget._waiting_for_fresh_frame = True
    widget._reset_mode_owned_runtime_state(reason=reason)
    widget._clear_gl_overlay()
    widget._prepare_engine_for_mode_reset()
    widget._clear_runtime_bar_state()


def should_capture_audio_now(widget: Any) -> bool:
    """Return True when audio capture/FFT should actively run."""
    return bool(widget._enabled and widget._spotify_playing)


def track_engine_generation(widget: Any, engine: Any) -> None:
    """Record the engine's generation/activation ids for fresh-frame gating."""
    if engine is None:
        widget._pending_engine_generation = -1
        widget._pending_engine_activation_id = -1
        return
    try:
        gen = int(engine.get_generation_id())
    except Exception:
        gen = -1
    try:
        activation_id = int(engine.get_activation_id())
    except Exception:
        activation_id = -1
    widget._pending_engine_generation = gen
    widget._pending_engine_activation_id = activation_id
    widget._last_engine_generation_seen = -1
    widget._last_engine_activation_seen = -1


def handle_mode_cycle_state_reset(widget: Any) -> None:
    """Reset bookkeeping for a mode-cycle transition."""
    widget._reset_teardown_bookkeeping()
    widget._pending_shadow_cache_invalidation = True
    widget._prepare_engine_for_mode_reset()


def clear_gl_overlay(widget: Any) -> None:
    """Destroy the GL bars overlay when visualizer hides."""
    widget._request_overlay_mode_reset(reason="clear_gl_overlay")
    widget._destroy_parent_overlay(reason="clear_gl_overlay")


def is_media_state_stale(widget: Any) -> bool:
    """Return True if Spotify state has not updated within fallback timeout."""
    last = getattr(widget, "_last_media_state_ts", 0.0)
    if last <= 0.0:
        return True
    try:
        timeout = float(widget._media_fallback_timeout)
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        timeout = 8.0
    return (time.time() - last) >= max(1.0, timeout)


def has_audio_activity(
    widget: Any,
    bars: List[float],
    raw_bars: Optional[List[float]] = None,
) -> bool:
    """Heuristic to detect meaningful audio energy on the loopback feed."""
    candidates = raw_bars if isinstance(raw_bars, list) and raw_bars else bars
    if not isinstance(candidates, list) or not candidates:
        return False
    threshold = 0.01
    try:
        return max(candidates) >= threshold
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        return any((b or 0.0) >= threshold for b in candidates)


def is_fallback_forced(widget: Any) -> bool:
    """Return True when the fallback force window is active."""
    return time.time() <= getattr(widget, "_fallback_forced_until", 0.0)


def update_fallback_force_state(widget: Any, audio_active: bool) -> None:
    """Track mismatch between bridge-reported paused state and audio activity."""
    now = time.time()
    if widget._spotify_playing:
        widget._fallback_mismatch_start = 0.0
        widget._fallback_forced_until = 0.0
        return

    if audio_active:
        if widget._fallback_mismatch_start <= 0.0:
            widget._fallback_mismatch_start = now
        elif (now - widget._fallback_mismatch_start) >= 3.0:
            if not is_fallback_forced(widget):
                widget._fallback_forced_until = now + 20.0
                logger.warning(
                    "[SPOTIFY_VIS] Forcing audio fallback for 20s (bridge reports paused but audio active)",
                )
    else:
        widget._fallback_mismatch_start = 0.0


def trigger_wake(widget: Any, *, reason: str = "unspecified", allow_defer: bool = True) -> None:
    """Trigger wake sequence for visualizer recovery after pause."""
    from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine

    if allow_defer and (
        widget._startup_secondary_stage_pending
        or (widget._enabled and not widget._startup_hot_start_started)
    ):
        widget._startup_wake_deferred = True
        logger.debug("[SPOTIFY_VIS] Deferred wake until staged hot start (reason=%s)", reason)
        return

    logger.debug("[SPOTIFY_VIS] Wake triggered (reason=%s)", reason)
    try:
        engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
        if engine and hasattr(engine, 'wake'):
            engine.wake()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Wake failed", exc_info=True)
