"""Spotify Visualizer Tick Pipeline — extracted from spotify_visualizer_widget.py.

Contains the core _on_tick logic, heartbeat transient detection, bubble
simulation dispatch, and GPU frame push.  All functions accept the widget
instance as the first parameter to preserve the original interface.

Phase 2 of the Visualizer Architecture Split.
"""
from __future__ import annotations

import math
import time
from typing import Any, Optional

from PySide6.QtCore import QRect
from shiboken6 import Shiboken

from core.logging.logger import (
    get_logger,
    is_perf_metrics_enabled,
    is_viz_diagnostics_enabled,
    is_viz_logging_enabled,
)

logger = get_logger(__name__)

_IDLE_BUBBLE_DT_SCALE = 0.50
_IDLE_LINE_MODE_DT_SCALE = 0.80


def _ensure_fresh_generation_state(widget: Any) -> None:
    """Backfill generation-handoff attrs for live widgets created on older paths."""
    if not hasattr(widget, "_waiting_for_fresh_frame"):
        widget._waiting_for_fresh_frame = False
    if not hasattr(widget, "_waiting_for_fresh_engine_frame"):
        widget._waiting_for_fresh_engine_frame = False
    if not hasattr(widget, "_pending_engine_generation"):
        widget._pending_engine_generation = -1
    if not hasattr(widget, "_last_engine_generation_seen"):
        widget._last_engine_generation_seen = -1


def _mode_requires_fresh_waveform(mode_str: str) -> bool:
    """Return True when a mode should wait for fresh waveform data after reset."""
    return str(mode_str or "").lower() in {"oscilloscope", "sine_wave"}


# ------------------------------------------------------------------
# Heartbeat transient detection (CPU-side)
# ------------------------------------------------------------------

def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def process_heartbeat(widget: Any, now_ts: float) -> None:
    """Detect bass energy spikes and produce a decay envelope for sine heartbeat."""
    if widget._sine_heartbeat <= 0.001 or widget._engine is None:
        return

    eb = widget._engine.get_energy_bands()
    bass_now = getattr(eb, 'bass', 0.0) if eb else 0.0
    mid_now = getattr(eb, 'mid', 0.0) if eb else 0.0
    high_now = getattr(eb, 'high', 0.0) if eb else 0.0

    prev_hb_ts = widget._heartbeat_last_ts
    widget._heartbeat_last_ts = now_ts
    dt_hb = max(0.001, min(0.05, now_ts - prev_hb_ts)) if prev_hb_ts > 0.0 else 0.016

    slider = max(0.0, min(1.0, widget._sine_heartbeat))

    # Fast EMA (~50ms) reacts to current beat, slow EMA (~400ms) is baseline.
    alpha_fast = min(1.0, dt_hb / 0.05)
    alpha_slow = min(1.0, dt_hb / 0.40)
    widget._heartbeat_fast_bass += (bass_now - widget._heartbeat_fast_bass) * alpha_fast
    widget._heartbeat_avg_bass += (bass_now - widget._heartbeat_avg_bass) * alpha_slow

    fast = widget._heartbeat_fast_bass
    slow = widget._heartbeat_avg_bass

    # Spike ratio: how much fast exceeds slow (1.0 = equal, 2.0 = double).
    spike_ratio = fast / max(0.02, slow)
    # Gate: at slider=0.0 need 60% spike above average; at slider=1.0 need 15%.
    trigger_gate = 1.0 + (0.60 - 0.45 * slider)
    cooldown_elapsed = now_ts - widget._heartbeat_last_trigger_ts
    energy_mix = _clamp(bass_now * 0.7 + mid_now * 0.2 + high_now * 0.1, 0.0, 1.0)

    # Transient bus boost (Approach A §8): if transient bus detected a kick
    # onset this frame, lower the trigger gate for immediate response.
    _tb_onset = getattr(widget._engine, '_audio_worker', None)
    _tb_kick = False
    if _tb_onset is not None:
        _tb_kick = (
            getattr(_tb_onset, '_onset_detected', False)
            and getattr(_tb_onset, '_onset_type', '') == 'kick'
        )
    if not _tb_kick and widget._engine is not None:
        try:
            scheduler = widget._engine.get_event_scheduler()
        except Exception:
            scheduler = None
        if scheduler is not None:
            try:
                _tb_kick = bool(scheduler.has_recent('kick', max_age_s=0.16))
            except Exception:
                _tb_kick = False
    if _tb_kick:
        trigger_gate *= 0.6  # much easier to trigger on confirmed kick

    triggered = False

    if (
        spike_ratio > trigger_gate
        and energy_mix > 0.03
        and cooldown_elapsed >= 0.10
    ):
        triggered = True
        widget._heartbeat_last_trigger_ts = now_ts
        # Punch scales with both how big the spike is and slider sensitivity.
        punch = _clamp(0.5 + (spike_ratio - trigger_gate) * 1.0 + energy_mix * 0.4, 0.0, 1.0)
        # Instant rise — set intensity directly to punch (or keep if already higher).
        widget._heartbeat_intensity = max(widget._heartbeat_intensity, punch)
    else:
        # Decay only when NOT triggered this frame.  400ms full decay for punchy feel.
        decay_rate = 1.0 / 0.40
        widget._heartbeat_intensity = max(0.0, widget._heartbeat_intensity - dt_hb * decay_rate)

    widget._heartbeat_fast_prev = fast

    if is_viz_diagnostics_enabled() and (
        triggered or (now_ts - widget._heartbeat_last_log_ts) >= 0.5
    ):
        logger.debug(
            (
                "[SPOTIFY_VIS][SINE][HB] dt=%.3f bass=%.3f fast=%.3f avg=%.3f "
                "spike=%.3f gate=%.3f energy=%.3f slider=%.2f intensity=%.2f trigger=%s"
            ),
            dt_hb,
            bass_now,
            fast,
            slow,
            spike_ratio,
            trigger_gate,
            energy_mix,
            slider,
            widget._heartbeat_intensity,
            triggered,
        )
        widget._heartbeat_last_log_ts = now_ts


# ------------------------------------------------------------------
# Bubble simulation dispatch
# ------------------------------------------------------------------

def dispatch_goo_field(widget: Any, now_ts: float) -> None:
    """Advance the Goo liquid field on the UI thread (~64 sources).

    Populates ``widget._goo_sources`` so the renderer can upload
    ``u_goo_sources`` during the next GPU push.
    """
    if widget._vis_mode_str != 'goo':
        return

    from widgets.spotify_visualizer.goo_liquid_field import (
        GOO_SOURCE_COUNT_MAX,
        GooFieldState,
        pack_sources_for_upload,
        solve_goo_field_step,
    )

    state = getattr(widget, '_goo_field_state', None)
    if state is None:
        state = GooFieldState()
        widget._goo_field_state = state

    prev_ts = getattr(widget, '_goo_last_tick_ts', 0.0) or 0.0
    widget._goo_last_tick_ts = now_ts
    dt = max(0.001, min(0.1, now_ts - prev_ts)) if prev_ts > 0 else 0.016
    playing = bool(widget._spotify_playing)
    if not playing:
        # Keep Goo subtly alive at idle without driving FFT/engine reads.
        dt *= 0.55

    engine = widget._engine
    if playing:
        try:
            energy = engine.get_energy_bands() if engine is not None else None
        except Exception:
            energy = None
    else:
        # Bubble/Sine idle path parity: deterministic low-amplitude motion source
        # while paused so shape stability can be tuned visually.
        from widgets.spotify_visualizer.energy_bands import EnergyBands

        idle_phase = now_ts
        idle_bass = 0.015 + 0.008 * (0.5 + 0.5 * math.sin(idle_phase * 0.58))
        idle_mid = 0.013 + 0.006 * (0.5 + 0.5 * math.sin(idle_phase * 0.41 + 1.3))
        idle_high = 0.010 + 0.004 * (0.5 + 0.5 * math.sin(idle_phase * 0.71 + 2.1))
        idle_overall = 0.015
        energy = EnergyBands(
            bass=idle_bass,
            mid=idle_mid,
            high=idle_high,
            overall=idle_overall,
        )

    try:
        solve_goo_field_step(
            state,
            dt=dt,
            energy_bands=energy,
            playing=playing,
            core_size=float(getattr(widget, '_goo_core_size', 0.18)),
            edge_inward_depth=float(getattr(widget, '_goo_edge_inward_depth', 0.18)),
            boundary_margin=float(getattr(widget, '_goo_boundary_margin', 0.01)),
            seed=id(widget) & 0xFFFFFFFF,
        )
    except Exception:
        logger.debug("[SPOTIFY_VIS][GOO] solve step failed", exc_info=True)
        return

    sources = pack_sources_for_upload(
        state,
        GOO_SOURCE_COUNT_MAX,
        aspect=float(max(1, int(widget.width()))) / float(max(1, int(widget.height()))),
        boundary_margin=float(getattr(widget, '_goo_boundary_margin', 0.01)),
    )
    widget._goo_sources = sources

    widget._goo_boundary_clamp_count = int(getattr(state, "boundary_clamp_count", 0))
    widget._goo_source_saturation_ratio = float(getattr(state, "source_saturation_ratio", 0.0))
    if is_viz_diagnostics_enabled():
        last_diag = float(getattr(widget, "_goo_diag_last_log_ts", 0.0) or 0.0)
        if now_ts - last_diag >= 0.75:
            logger.debug(
                "[SPOTIFY_VIS][GOO][DIAG] boundary_clamps=%d saturation=%.3f source_count=%d",
                widget._goo_boundary_clamp_count,
                widget._goo_source_saturation_ratio,
                len(sources),
            )
            widget._goo_diag_last_log_ts = now_ts


def dispatch_bubble_simulation(widget: Any, now_ts: float) -> None:
    """Snapshot bubble settings on UI thread and submit to COMPUTE pool."""
    if (
        widget._vis_mode_str != 'bubble'
        or widget._bubble_compute_pending
        or widget._mode_teardown_block_until_ready
    ):
        return
    if widget._thread_manager is None:
        return

    widget._bubble_compute_pending = True
    # Bubble owns a full-dynamic continuous energy path. Using the shared
    # post-AGC snapshot here can flatten the mode into a near-constant plateau
    # under hot floor pressure, especially after preset/custom transitions.
    if widget._engine:
        eb_pulse = widget._engine.get_pre_agc_energy_bands()
        eb_smooth = widget._engine.get_pre_agc_energy_bands()
    else:
        eb_pulse = None
        eb_smooth = None
    # Transient bus snapshot for immediate beat response (Approach A §6)
    tb = widget._engine.get_transient_energy_bands() if widget._engine else None
    # Event micro-scheduler (§2.4) — passed to bubble sim for consume-once kicks
    _event_scheduler = widget._engine.get_event_scheduler() if widget._engine else None
    prev_ts = widget._bubble_last_tick_ts
    widget._bubble_last_tick_ts = now_ts
    dt_bubble = max(0.001, min(0.1, now_ts - prev_ts)) if prev_ts > 0 else 0.016
    # Keep bubble alive during pause: low-energy synthetic idle motion.
    if not widget._spotify_playing:
        dt_bubble *= _IDLE_BUBBLE_DT_SCALE
        idle_phase = now_ts
        idle_bass = 0.015 + 0.008 * (0.5 + 0.5 * math.sin(idle_phase * 0.58))
        idle_mid = 0.013 + 0.006 * (0.5 + 0.5 * math.sin(idle_phase * 0.41 + 1.3))
        idle_high = 0.010 + 0.004 * (0.5 + 0.5 * math.sin(idle_phase * 0.71 + 2.1))
        eb_snap = {
            'bass': idle_bass,
            'mid': idle_mid,
            'high': idle_high,
            'overall': 0.015,
            'smooth_mid': idle_mid,
            'smooth_high': idle_high,
        }
    else:
        # Mix transient bass into pulse bass for immediate kick response
        _pulse_bass = getattr(eb_pulse, 'bass', 0.0) if eb_pulse else 0.0
        _t_bass = getattr(tb, 'bass_transient', 0.0) if tb else 0.0
        _t_mid = getattr(tb, 'mid_transient', 0.0) if tb else 0.0
        _t_gain = getattr(widget, '_transient_pulse_gain', 1.0)
        _t_clamp = getattr(widget, '_transient_clamp', 1.5)
        _bmix_bass = getattr(widget, '_bubble_transient_mix_bass', 0.75)
        _bmix_vocal = getattr(widget, '_bubble_transient_mix_vocal', 0.25)
        _mixed_bass = min(_t_clamp, _pulse_bass + _t_bass * _t_gain * _bmix_bass)
        _pulse_mid = getattr(eb_pulse, 'mid', 0.0) if eb_pulse else 0.0
        _mixed_mid = min(_t_clamp, _pulse_mid + _t_mid * _t_gain * _bmix_vocal)
        eb_snap = {
            'bass': _mixed_bass,
            'mid': _mixed_mid,
            'high': getattr(eb_pulse, 'high', 0.0) if eb_pulse else 0.0,
            'overall': getattr(eb_smooth, 'overall', 0.0) if eb_smooth else 0.0,
            'smooth_mid': getattr(eb_smooth, 'mid', 0.0) if eb_smooth else 0.0,
            'smooth_high': getattr(eb_smooth, 'high', 0.0) if eb_smooth else 0.0,
        }
    sim_settings = {
        "bubble_big_count": widget._bubble_big_count,
        "bubble_small_count": widget._bubble_small_count,
        "bubble_surface_reach": widget._bubble_surface_reach,
        "bubble_stream_direction": widget._bubble_stream_direction,
        "bubble_stream_constant_speed": widget._bubble_stream_constant_speed,
        "bubble_stream_speed_cap": widget._bubble_stream_speed_cap,
        "bubble_stream_reactivity": widget._bubble_stream_reactivity,
        "bubble_rotation_amount": widget._bubble_rotation_amount,
        "bubble_drift_amount": widget._bubble_drift_amount,
        "bubble_drift_speed": widget._bubble_drift_speed,
        "bubble_drift_frequency": widget._bubble_drift_frequency,
        "bubble_drift_direction": widget._bubble_drift_direction,
        "bubble_big_size_max": widget._bubble_big_size_max,
        "bubble_small_size_max": widget._bubble_small_size_max,
        "bubble_trail_strength": widget._bubble_trail_strength,
        "bubble_bounce_big_pct": widget._bubble_bounce_big_pct,
        "bubble_bounce_small_pct": widget._bubble_bounce_small_pct,
        "bubble_bounce_big_speed": widget._bubble_bounce_big_speed,
        "bubble_bounce_small_speed": widget._bubble_bounce_small_speed,
        "bubble_bounce_same_only": widget._bubble_bounce_same_only,
        "bubble_collision_pop_mode": getattr(widget, "_bubble_collision_pop_mode", "off"),
        "_event_scheduler": _event_scheduler,
    }
    pulse_params = {
        'bass': eb_snap['bass'],
        'mid_high': (eb_snap['mid'] + eb_snap['high']) * 0.5,
        'big_bass_pulse': widget._bubble_big_bass_pulse,
        'small_freq_pulse': widget._bubble_small_freq_pulse,
        'big_specular_max_size': widget._bubble_big_specular_max_size,
        'big_contraction_bias': widget._bubble_big_contraction_bias,
        'big_size_clamp': widget._bubble_big_size_clamp,
    }
    widget._thread_manager.submit_compute_task(
        widget._bubble_compute_worker,
        dt_bubble, eb_snap, sim_settings, pulse_params,
        callback=widget._bubble_compute_done,
        task_id=f"bubble_sim_{id(widget)}",
    )


# ------------------------------------------------------------------
# Perf metrics inline accounting
# ------------------------------------------------------------------

def record_tick_perf(widget: Any, now_ts: float) -> None:
    """Inline PERF metrics with gap filtering (perf-gated)."""
    if not is_perf_metrics_enabled():
        return

    if widget._perf_tick_last_ts is not None:
        dt = now_ts - widget._perf_tick_last_ts
        # Skip metrics for gaps >100ms (startup, widget paused/hidden).
        if dt > 0.1:
            widget._perf_tick_start_ts = now_ts
            widget._perf_tick_min_dt = 0.0
            widget._perf_tick_max_dt = 0.0
            widget._perf_tick_frame_count = 0
        elif dt > 0.0:
            if widget._perf_tick_min_dt == 0.0 or dt < widget._perf_tick_min_dt:
                widget._perf_tick_min_dt = dt
            if dt > widget._perf_tick_max_dt:
                widget._perf_tick_max_dt = dt
            widget._perf_tick_frame_count += 1
    else:
        widget._perf_tick_start_ts = now_ts
    widget._perf_tick_last_ts = now_ts

    # Periodic PERF snapshot
    if widget._perf_last_log_ts is None or (now_ts - widget._perf_last_log_ts) >= 5.0:
        widget._log_perf_snapshot(reset=False)
        widget._perf_last_log_ts = now_ts


# ------------------------------------------------------------------
# Engine bar consumption
# ------------------------------------------------------------------

def consume_engine_bars(widget: Any, now_ts: float) -> tuple[bool, bool]:
    """Read smoothed bars from engine, detect changes.

    Returns (changed, any_nonzero).
    """
    from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine

    _ensure_fresh_generation_state(widget)

    engine = widget._engine
    if engine is None:
        engine = get_shared_spotify_beat_engine(widget._bar_count)
        widget._engine = engine
        engine.set_smoothing(widget._smoothing)

    changed = False
    any_nonzero = False

    if engine is None:
        return changed, any_nonzero

    # Trigger engine tick (schedules audio processing + smoothing on COMPUTE pool)
    _engine_tick_start = time.time()
    engine.tick()
    _engine_tick_elapsed = (time.time() - _engine_tick_start) * 1000.0
    if _engine_tick_elapsed > 20.0 and is_perf_metrics_enabled():
        logger.warning("[PERF] [SPOTIFY_VIS] Slow engine.tick(): %.2fms", _engine_tick_elapsed)

    if (
        widget._waiting_for_fresh_engine_frame
        and not widget._spotify_playing
        and str(getattr(widget, "_vis_mode_str", "")).lower() in {"bubble", "sine_wave", "oscilloscope", "spectrum"}
    ):
        widget._waiting_for_fresh_engine_frame = False
        widget._pending_engine_generation = -1

    if widget._waiting_for_fresh_engine_frame and widget._pending_engine_generation >= 0:
        try:
            latest_gen = engine.get_latest_generation_with_frame()
        except Exception:
            latest_gen = -1
        waveform_ready = True
        if _mode_requires_fresh_waveform(getattr(widget, "_vis_mode_str", "")):
            try:
                latest_waveform_gen = engine.get_latest_generation_with_waveform()
            except Exception:
                latest_waveform_gen = -1
            waveform_ready = latest_waveform_gen >= widget._pending_engine_generation
        if latest_gen >= widget._pending_engine_generation and waveform_ready:
            widget._waiting_for_fresh_engine_frame = False
            widget._last_engine_generation_seen = latest_gen
            logger.debug(
                "[SPOTIFY_VIS] Engine delivered fresh frame (gen=%d) after reset",
                latest_gen,
            )

    pending_reasons = list(widget._latency_pending_probe)
    widget._latency_pending_probe.clear()
    probe_reason = ",".join(pending_reasons) if pending_reasons else None
    widget._log_audio_latency_metrics(engine, now_ts, force_reason=probe_reason)

    # Get pre-smoothed bars from engine (smoothing done on COMPUTE pool)
    smoothed = engine.get_smoothed_bars()

    if widget._waiting_for_fresh_engine_frame:
        display_bars = widget._display_bars
        for i in range(widget._bar_count):
            val = smoothed[i] if i < len(smoothed) else 0.0
            display_bars[i] = val
            if val > 0.0:
                any_nonzero = True
        if any_nonzero and widget._pending_engine_generation < 0:
            widget._waiting_for_fresh_engine_frame = False
        else:
            # Still waiting — skip downstream
            return False, False

    # Always drive the bars from audio to avoid Spotify bridge flakiness.
    widget._fallback_logged = False

    # Debug constant-bar mode
    import os
    try:
        _DEBUG_CONST_BARS = float(os.environ.get("SRPSS_SPOTIFY_VIS_DEBUG_CONST", "0.0"))
    except Exception:
        _DEBUG_CONST_BARS = 0.0
    if _DEBUG_CONST_BARS > 0.0:
        const_val = max(0.0, min(1.0, _DEBUG_CONST_BARS))
        smoothed = [const_val] * widget._bar_count

    # Check if bars changed
    bar_count = widget._bar_count
    display_bars = widget._display_bars
    for i in range(bar_count):
        new_val = smoothed[i] if i < len(smoothed) else 0.0
        old_val = display_bars[i] if i < len(display_bars) else 0.0
        if abs(new_val - old_val) > 1e-4:
            changed = True
        if new_val > 0.0:
            any_nonzero = True
        display_bars[i] = new_val

    # Force update during decay (when bars are non-zero but Spotify stopped)
    if any_nonzero and not widget._spotify_playing:
        changed = True

    return changed, any_nonzero


# ------------------------------------------------------------------
# GPU frame push
# ------------------------------------------------------------------

def push_gpu_frame(
    widget: Any,
    parent: Any,
    now_ts: float,
    changed: bool,
    first_frame: bool,
) -> bool:
    """Push a visualizer frame to the GPU overlay if available.

    Returns True if GPU rendering was used.
    """
    if parent is None or not hasattr(parent, "push_spotify_visualizer_frame"):
        return False

    try:
        current_geom = widget.geometry()
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        current_geom = None
    last_geom = widget._last_gpu_geom
    geom_changed = last_geom is None or (current_geom is not None and current_geom != last_geom)

    fade = widget._get_gpu_fade_factor(now_ts)
    # Apply mode-transition crossfade (1.0 when idle, 0→1 during switch)
    transition_fade = widget._mode_transition_fade_factor(now_ts)
    fade *= transition_fade
    prev_fade = widget._last_gpu_fade_sent
    widget._last_gpu_fade_sent = fade
    fade_changed = prev_fade < 0.0 or abs(fade - prev_fade) >= 0.01
    need_card_update = fade_changed

    transitioning = widget._mode_transition_phase != 0
    # Animated modes must push every tick because their visuals change
    # continuously independent of bar data.
    animated_mode = (widget._vis_mode_str != 'spectrum') or getattr(widget, '_rainbow_enabled', False)
    should_push = changed or fade_changed or first_frame or geom_changed or transitioning or animated_mode
    if not should_push:
        return False

    _gpu_push_start = time.time()
    mode_str = widget._vis_mode_str

    from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs
    extra = build_gpu_push_extra_kwargs(widget, mode_str, widget._engine)

    if (
        mode_str == 'sine_wave'
        and is_viz_diagnostics_enabled()
    ):
        crawl_now = time.time()
        if crawl_now - widget._crawl_last_log_ts >= 0.75:
            eb = extra.get('energy_bands')
            mid_val = float(getattr(eb, 'mid', 0.0)) if eb is not None else 0.0
            high_val = float(getattr(eb, 'high', 0.0)) if eb is not None else 0.0
            crawl_drive = max(0.0, min(1.2, mid_val * 0.65 + high_val * 0.35))
            logger.debug(
                (
                    "[SPOTIFY_VIS][SINE][CRAWL] slider=%.2f mid=%.3f "
                    "high=%.3f drive=%.3f playing=%s"
                ),
                float(getattr(widget, '_sine_crawl_amount', 0.0)),
                mid_val,
                high_val,
                crawl_drive,
                widget._spotify_playing,
            )
            widget._crawl_last_log_ts = crawl_now

    border_width_px = float(widget._border_width)

    used_gpu = parent.push_spotify_visualizer_frame(
        bars=list(widget._display_bars),
        bar_count=widget._bar_count,
        segments=widget._dynamic_bar_segments(),
        fill_color=widget._bar_fill_color,
        border_color=widget._bar_border_color,
        fade=fade,
        playing=widget._spotify_playing,
        ghosting_enabled=widget._ghosting_enabled,
        ghost_alpha=widget._ghost_alpha,
        ghost_decay=widget._ghost_decay_rate,
        vis_mode=mode_str,
        single_piece=widget._spectrum_single_piece,
        slanted=False,
        border_radius=widget._spectrum_border_radius,
        border_width_px=border_width_px,
        **extra,
    )
    _gpu_push_elapsed = (time.time() - _gpu_push_start) * 1000.0
    if _gpu_push_elapsed > 20.0 and is_perf_metrics_enabled():
        logger.warning("[PERF] [SPOTIFY_VIS] Slow GPU push: %.2fms", _gpu_push_elapsed)

    if used_gpu:
        widget._has_pushed_first_frame = True
        widget._cpu_bars_enabled = False
        try:
            if current_geom is None:
                current_geom = widget.geometry()
            widget._last_gpu_geom = QRect(current_geom)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            widget._last_gpu_geom = None
        # Card/background/shadow still repaint via stylesheet
        if need_card_update:
            widget.update()
        widget._on_first_frame_after_cold_start()
    return used_gpu


# ------------------------------------------------------------------
# Audio latency metrics
# ------------------------------------------------------------------

def log_audio_latency_metrics(
    widget: Any,
    engine: Optional[Any],
    now_ts: float,
    force_reason: Optional[str] = None,
) -> None:
    """Emit viz-only latency diagnostics when enabled via --viz."""
    if engine is None or not is_viz_logging_enabled():
        return

    last_audio_ts = float(getattr(engine, "_last_audio_ts", 0.0) or 0.0)
    last_smooth_ts = float(getattr(engine, "_last_smooth_ts", -1.0) or -1.0)
    source_ts = max(last_audio_ts, last_smooth_ts)
    if source_ts <= 0.0:
        return

    force_logging = bool(force_reason)
    if (
        not force_logging
        and (now_ts - widget._latency_last_log_ts) < widget._latency_log_interval
    ):
        return

    lag_ms = max(0.0, (now_ts - source_ts) * 1000.0)
    phase = widget._mode_transition_phase
    mode = getattr(widget, "_vis_mode_str", "unknown")
    pending = getattr(widget, "_mode_transition_pending", None)
    pending_mode = getattr(pending, "name", None) if pending is not None else None

    level: Optional[str] = None
    if lag_ms >= widget._latency_error_ms:
        level = "error"
    elif lag_ms >= widget._latency_warn_ms:
        level = "warning"

    if level is None:
        return

    rounded = round(lag_ms, 1)
    signature = (level, rounded, mode, phase, pending_mode, force_reason)
    if signature == widget._latency_last_signature:
        return
    widget._latency_last_signature = signature

    trigger_suffix = f" trigger={force_reason}" if force_reason else ""
    msg = (
        "[SPOTIFY_VIS][LATENCY] lag_ms=%.1f mode=%s transition_phase=%d pending=%s%s"
        % (lag_ms, mode, phase, pending_mode or "<none>", trigger_suffix)
    )
    if level == "error":
        logger.error(msg)
    else:
        logger.warning(msg)

    widget._latency_last_log_ts = now_ts


# ------------------------------------------------------------------
# Main tick entry point
# ------------------------------------------------------------------

def on_tick(widget: Any) -> None:
    """Periodic UI tick — PERFORMANCE OPTIMIZED.

    Consumes the latest bar frame from the engine and smoothly
    interpolates towards it for visual stability.
    """
    _tick_entry_ts = time.time()
    _ensure_fresh_generation_state(widget)

    # PERFORMANCE: Fast validity check without nested try/except
    if not Shiboken.isValid(widget):
        if widget._bars_timer is not None:
            widget._bars_timer.stop()
            widget._bars_timer = None
        widget._enabled = False
        return

    if not widget._enabled:
        return

    now_ts = time.time()
    parent = widget.parent()
    transition_ctx = widget._get_transition_context(parent)
    is_transition_active = transition_ctx.get("running", False)
    was_transition_active = widget._last_transition_running
    if is_transition_active and not was_transition_active:
        widget._request_latency_probe("transition_start")
    elif not is_transition_active and was_transition_active:
        widget._request_latency_probe("transition_end")
    widget._last_transition_running = is_transition_active

    # PERFORMANCE: Pause dedicated timer during transitions when AnimationManager is active
    widget._pause_timer_during_transition(is_transition_active)

    max_fps = widget._resolve_max_fps(transition_ctx)
    widget._update_timer_interval(max_fps)

    min_dt = 1.0 / max_fps if max_fps > 0.0 else 0.0
    last = widget._last_update_ts
    dt_since_last = 0.0
    if last >= 0.0:
        dt_since_last = now_ts - last
    if last >= 0.0 and dt_since_last < min_dt and not widget._waiting_for_fresh_engine_frame:
        return

    widget._last_update_ts = now_ts
    _dt_spike_max_reasonable_ms: float = 1000.0
    dt_for_spike_check = min(dt_since_last * 1000.0, _dt_spike_max_reasonable_ms)
    if dt_since_last * 1000.0 >= widget._dt_spike_threshold_ms and dt_for_spike_check < _dt_spike_max_reasonable_ms:
        widget._log_tick_spike(dt_since_last, transition_ctx)

    # Perf metrics accounting
    record_tick_perf(widget, now_ts)

    # Consume bars from engine
    changed, _any_nonzero = consume_engine_bars(widget, now_ts)
    # Let paused mode transitions progress even when fresh-engine wait short-circuits.
    widget._check_mode_teardown_ready(widget._engine, now_ts)
    # If consume returned (False, False) while waiting for fresh engine frame, bail
    if widget._waiting_for_fresh_engine_frame and not changed and not _any_nonzero:
        return

    # Heartbeat transient detection for sine mode
    process_heartbeat(widget, now_ts)

    if widget._mode_teardown_block_until_ready and not widget._mode_transition_ready:
        return

    # Bubble simulation dispatch
    dispatch_bubble_simulation(widget, now_ts)

    # Goo liquid field solve (UI-thread, cheap: ~32 sources)
    dispatch_goo_field(widget, now_ts)

    # GPU frame push
    first_frame = not widget._has_pushed_first_frame
    used_gpu = push_gpu_frame(widget, parent, now_ts, changed, first_frame)

    if not used_gpu:
        # Fallback: when there is no DisplayWidget/GPU bridge
        has_gpu_parent = parent is not None and hasattr(parent, "push_spotify_visualizer_frame")
        if not has_gpu_parent or widget._software_visualizer_enabled:
            widget._cpu_bars_enabled = True
            widget.update()
            widget._has_pushed_first_frame = True
            widget._on_first_frame_after_cold_start()

    # PERF: Log slow ticks
    _tick_elapsed = (time.time() - _tick_entry_ts) * 1000.0
    if _tick_elapsed > 50.0 and is_perf_metrics_enabled():
        logger.warning("[PERF] [SPOTIFY_VIS] Slow _on_tick: %.2fms", _tick_elapsed)
