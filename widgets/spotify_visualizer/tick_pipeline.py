"""Spotify Visualizer Tick Pipeline — extracted from spotify_visualizer_widget.py.

Contains the core _on_tick logic, heartbeat transient detection, bubble
simulation dispatch, and GPU frame push.  All functions accept the widget
instance as the first parameter to preserve the original interface.

Phase 2 of the Visualizer Architecture Split.
"""
from __future__ import annotations

import logging
import math
import time
from collections.abc import Sequence
from typing import Any, Optional

from PySide6.QtCore import QRect
from shiboken6 import Shiboken

from core.logging.logger import (
    get_logger,
    is_perf_metrics_enabled,
    is_viz_diagnostics_enabled,
    is_viz_logging_enabled,
)
from widgets.spotify_visualizer.signal_contract import soft_ceiling
from widgets.spotify_visualizer import mode_capabilities, mode_transition
from widgets.spotify_visualizer.logical_runtime import coerce_identity
from widgets.spotify_visualizer.render_state import (
    VisualizerLogicalFrame,
    VisualizerProtectedEdge,
)
from widgets.spotify_visualizer.spectrum_presentation_smoothing import (
    reset_widget_spectrum_presentation_smoothing,
    resolve_widget_spectrum_presentation,
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
    if not hasattr(widget, "_pending_engine_activation_id"):
        widget._pending_engine_activation_id = -1
    if not hasattr(widget, "_last_engine_activation_seen"):
        widget._last_engine_activation_seen = -1


def _mode_requires_fresh_waveform(mode_str: str) -> bool:
    """Return True when a mode should wait for fresh waveform data after reset."""
    return str(mode_str or "").lower() in {"oscilloscope", "sine_wave"}


# Mode capability answers come from one canonical owner; see
# `widgets.spotify_visualizer.mode_capabilities` for why these three questions
# are deliberately distinct.
_mode_allows_idle_reveal_key = mode_capabilities.allows_idle_reveal
_mode_is_idle_self_animating = mode_capabilities.is_idle_self_animating
_mode_requires_authoritative_first_source = (
    mode_capabilities.requires_authoritative_first_source
)


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

def dispatch_devcurve_field(widget: Any, now_ts: float) -> None:
    """Advance Dev Curve runtime and publish sampled curve arrays."""
    if widget._vis_mode_str != 'devcurve':
        return

    from widgets.spotify_visualizer.devcurve_runtime import (
        DevCurveRuntimeState,
        solve_devcurve_frame,
    )
    from widgets.spotify_visualizer.energy_bands import EnergyBands

    state = getattr(widget, '_devcurve_runtime_state', None)
    if state is None:
        state = DevCurveRuntimeState()
        widget._devcurve_runtime_state = state

    prev_ts = getattr(widget, '_devcurve_last_tick_ts', 0.0) or 0.0
    widget._devcurve_last_tick_ts = now_ts
    dt = max(0.001, min(0.1, now_ts - prev_ts)) if prev_ts > 0 else 0.016
    playing = bool(widget._spotify_playing)

    engine = widget._engine
    transient_bus = None
    if playing:
        try:
            energy = engine.get_energy_bands() if engine is not None else None
            transient_bus = engine.get_transient_energy_bands() if engine is not None else None
        except Exception:
            energy = None
            transient_bus = None
    else:
        # Bubble/Sine idle path parity: deterministic low-amplitude motion source
        # while paused so shape stability can be tuned visually.
        idle_phase = now_ts
        idle_bass = 0.018 + 0.010 * (0.5 + 0.5 * math.sin(idle_phase * 0.58))
        idle_mid = 0.015 + 0.007 * (0.5 + 0.5 * math.sin(idle_phase * 0.41 + 1.3))
        idle_high = 0.012 + 0.005 * (0.5 + 0.5 * math.sin(idle_phase * 0.71 + 2.1))
        energy = EnergyBands(
            bass=idle_bass,
            mid=idle_mid,
            high=idle_high,
            overall=0.018,
        )

    layer_settings = {
        "bass": {
            "enabled": bool(getattr(widget, "_devcurve_layer_bass_enabled", True)),
            "power": float(getattr(widget, "_devcurve_layer_bass_power", 1.0)),
            "offset": float(getattr(widget, "_devcurve_layer_bass_offset", 0.0)),
            "order": int(getattr(widget, "_devcurve_layer_bass_order", 1)),
        },
        "vocals": {
            "enabled": bool(getattr(widget, "_devcurve_layer_vocals_enabled", True)),
            "power": float(getattr(widget, "_devcurve_layer_vocals_power", 1.0)),
            "offset": float(getattr(widget, "_devcurve_layer_vocals_offset", 0.0)),
            "order": int(getattr(widget, "_devcurve_layer_vocals_order", 2)),
        },
        "mids": {
            "enabled": bool(getattr(widget, "_devcurve_layer_mids_enabled", True)),
            "power": float(getattr(widget, "_devcurve_layer_mids_power", 1.0)),
            "offset": float(getattr(widget, "_devcurve_layer_mids_offset", 0.0)),
            "order": int(getattr(widget, "_devcurve_layer_mids_order", 3)),
        },
        "transients": {
            "enabled": bool(getattr(widget, "_devcurve_layer_transients_enabled", True)),
            "power": float(getattr(widget, "_devcurve_layer_transients_power", 1.0)),
            "offset": float(getattr(widget, "_devcurve_layer_transients_offset", 0.0)),
            "order": int(getattr(widget, "_devcurve_layer_transients_order", 4)),
        },
    }
    default_nodes = [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]]
    layer_shape_nodes = {
        "bass": list(getattr(widget, "_devcurve_layer_bass_shape_nodes", default_nodes)),
        "vocals": list(getattr(widget, "_devcurve_layer_vocals_shape_nodes", default_nodes)),
        "mids": list(getattr(widget, "_devcurve_layer_mids_shape_nodes", default_nodes)),
        "transients": list(getattr(widget, "_devcurve_layer_transients_shape_nodes", default_nodes)),
    }

    try:
        frame = solve_devcurve_frame(
            state,
            dt=dt,
            now_ts=now_ts,
            layer_shape_nodes=layer_shape_nodes,
            base_level=float(getattr(widget, "_devcurve_base_level", 0.58)),
            motion_power=float(getattr(widget, "_devcurve_motion_power", 1.0)),
            idle_motion=float(getattr(widget, "_devcurve_idle_motion", 0.20)),
            idle_speed=float(getattr(widget, "_devcurve_idle_speed", 0.60)),
            smoothness=float(getattr(widget, "_devcurve_smoothness", 0.55)),
            growth=float(getattr(widget, "_devcurve_growth", 3.0)),
            layer_settings=layer_settings,
            energy_bands=energy,
            transient_bus=transient_bus,
            playing=playing,
        )
    except Exception:
        logger.debug("[SPOTIFY_VIS][DEVCURVE] runtime solve failed", exc_info=True)
        return

    layer_map = frame.get("layers", {}) if isinstance(frame.get("layers", {}), dict) else {}
    widget._devcurve_sample_count = int(frame.get("sample_count", 0))
    widget._devcurve_curve_bass = list(layer_map.get("bass", []))
    widget._devcurve_curve_vocals = list(layer_map.get("vocals", []))
    widget._devcurve_curve_mids = list(layer_map.get("mids", []))
    widget._devcurve_curve_transients = list(layer_map.get("transients", []))
    draw_order = frame.get("draw_order", ["bass", "vocals", "mids", "transients"])
    if isinstance(draw_order, list) and len(draw_order) == 4:
        widget._devcurve_draw_order = list(draw_order)
    widget._devcurve_foreground_layer = str(frame.get("foreground_layer", "") or "")
    widget._devcurve_foreground_layer_id = int(frame.get("foreground_layer_id", -1))
    slots = frame.get("specular_slots", [])
    if isinstance(slots, list) and slots:
        s0 = slots[0] if len(slots) > 0 and isinstance(slots[0], list) else [0.0, 0.0, 0.0, 0.0]
        s1 = slots[1] if len(slots) > 1 and isinstance(slots[1], list) else [0.0, 0.0, 0.0, 0.0]
        s2 = slots[2] if len(slots) > 2 and isinstance(slots[2], list) else [0.0, 0.0, 0.0, 0.0]
        widget._devcurve_specular_slot0 = [
            max(-1.5, min(2.5, float(s0[0] if len(s0) > 0 else 0.0))),
            max(0.0, min(1.0, float(s0[1] if len(s0) > 1 else 0.0))),
            max(0.0, min(1.0, float(s0[2] if len(s0) > 2 else 0.0))),
            max(0.0, min(1.0, float(s0[3] if len(s0) > 3 else 0.0))),
        ]
        widget._devcurve_specular_slot1 = [
            max(-1.5, min(2.5, float(s1[0] if len(s1) > 0 else 0.0))),
            max(0.0, min(1.0, float(s1[1] if len(s1) > 1 else 0.0))),
            max(0.0, min(1.0, float(s1[2] if len(s1) > 2 else 0.0))),
            max(0.0, min(1.0, float(s1[3] if len(s1) > 3 else 0.0))),
        ]
        widget._devcurve_specular_slot2 = [
            max(-1.5, min(2.5, float(s2[0] if len(s2) > 0 else 0.0))),
            max(0.0, min(1.0, float(s2[1] if len(s2) > 1 else 0.0))),
            max(0.0, min(1.0, float(s2[2] if len(s2) > 2 else 0.0))),
            max(0.0, min(1.0, float(s2[3] if len(s2) > 3 else 0.0))),
        ]
    else:
        widget._devcurve_specular_slot0 = [0.0, 0.0, 0.0, 0.0]
        widget._devcurve_specular_slot1 = [0.0, 0.0, 0.0, 0.0]
        widget._devcurve_specular_slot2 = [0.0, 0.0, 0.0, 0.0]
    widget._devcurve_smoothness_max_step = float(frame.get("smoothness_max_step", 0.0))
    widget._devcurve_active_amplitude = float(frame.get("active_amplitude", 0.0))
    widget._devcurve_idle_amplitude = float(frame.get("idle_amplitude", 0.0))
    widget._devcurve_foreground_travel_rate = float(frame.get("foreground_travel_rate", 0.0))
    widget._devcurve_foreground_travel_pos = float(frame.get("foreground_travel_pos", 0.0))
    widget._devcurve_specular_travel_rate = float(frame.get("specular_travel_rate", 0.0))
    current_specular_activity = float(
        getattr(widget, "_devcurve_specular_activity_alpha", 1.0 if playing else 0.0)
    )
    target_specular_activity = 1.0 if playing else 0.0
    fade_seconds = 0.85
    blend = max(0.0, min(1.0, dt / fade_seconds))
    widget._devcurve_specular_activity_alpha = (
        current_specular_activity
        + (target_specular_activity - current_specular_activity) * blend
    )

    if is_viz_diagnostics_enabled() and logger.isEnabledFor(logging.DEBUG):
        last_diag = float(getattr(widget, "_devcurve_diag_last_log_ts", 0.0) or 0.0)
        if now_ts - last_diag >= 0.80:
            e = frame.get("energies", {}) if isinstance(frame.get("energies", {}), dict) else {}
            logger.debug(
                (
                    "[SPOTIFY_VIS][DEVCURVE] mode=%s idle_amp=%.4f active_amp=%.4f smooth_step=%.5f "
                    "fg=%s E[b=%.3f v=%.3f m=%.3f t=%.3f] fg_rate=%.4f fg_pos=%.3f spec_rate=%.4f S[x=%.3f/%.3f/%.3f]"
                ),
                "layered",
                widget._devcurve_idle_amplitude,
                widget._devcurve_active_amplitude,
                widget._devcurve_smoothness_max_step,
                str(getattr(widget, "_devcurve_foreground_layer", "")),
                float(e.get("bass", 0.0)),
                float(e.get("vocals", 0.0)),
                float(e.get("mids", 0.0)),
                float(e.get("transients", 0.0)),
                float(getattr(widget, "_devcurve_foreground_travel_rate", 0.0)),
                float(getattr(widget, "_devcurve_foreground_travel_pos", 0.0)),
                float(getattr(widget, "_devcurve_specular_travel_rate", 0.0)),
                float((getattr(widget, "_devcurve_specular_slot0", [0.0]) or [0.0])[0]),
                float((getattr(widget, "_devcurve_specular_slot1", [0.0]) or [0.0])[0]),
                float((getattr(widget, "_devcurve_specular_slot2", [0.0]) or [0.0])[0]),
            )
            widget._devcurve_diag_last_log_ts = now_ts


def dispatch_bubble_simulation(widget: Any, now_ts: float) -> None:
    """Advance one Bubble step on the sole authored visualizer clock."""
    if (
        widget._vis_mode_str != 'bubble'
        or widget._mode_teardown_block_until_ready
    ):
        return

    cadence = getattr(widget, "_bubble_cadence_state", None)
    if cadence is None:
        from widgets.spotify_visualizer.bubble_cadence import BubbleCadenceState

        cadence = BubbleCadenceState()
        widget._bubble_cadence_state = cadence
    controller = getattr(widget, "runtime_controller", None)
    if controller is None:
        raise RuntimeError("Bubble logical step requires its runtime controller")

    from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime

    try:
        runtime = controller.resolve_logical_mode_state(
            "bubble",
            BubbleFrameRuntime,
        )
    except ValueError:
        if controller.mode_id != "bubble" or widget._vis_mode_str != "bubble":
            return
        raise
    if not isinstance(runtime, BubbleFrameRuntime):
        raise TypeError("Bubble logical mode state has the wrong type")
    cadence.request_step(now_ts=now_ts)

    # Bubble owns a full-dynamic continuous energy path. Using the shared
    # post-AGC snapshot here can flatten the mode into a near-constant plateau
    # under hot floor pressure, especially after preset/custom transitions.
    if widget._engine:
        bubble_feed = getattr(widget._engine, "get_bubble_energy_bands", None)
        if callable(bubble_feed):
            eb_pulse = bubble_feed()
        else:
            eb_pulse = widget._engine.get_pre_agc_energy_bands()
        eb_smooth = eb_pulse
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
    eb_snap = getattr(widget, "_bubble_dispatch_energy_snapshot", None)
    if not isinstance(eb_snap, dict):
        eb_snap = {
            "bass": 0.0,
            "mid": 0.0,
            "high": 0.0,
            "overall": 0.0,
            "smooth_mid": 0.0,
            "smooth_high": 0.0,
            "crest": 0.0,
        }
        widget._bubble_dispatch_energy_snapshot = eb_snap
    prev_dispatch_bass = float(eb_snap.get("bass", 0.0) or 0.0)
    if not widget._spotify_playing:
        dt_bubble *= _IDLE_BUBBLE_DT_SCALE
        idle_phase = now_ts
        idle_bass = 0.015 + 0.008 * (0.5 + 0.5 * math.sin(idle_phase * 0.58))
        idle_mid = 0.013 + 0.006 * (0.5 + 0.5 * math.sin(idle_phase * 0.41 + 1.3))
        idle_high = 0.010 + 0.004 * (0.5 + 0.5 * math.sin(idle_phase * 0.71 + 2.1))
        eb_snap["bass"] = idle_bass
        eb_snap["mid"] = idle_mid
        eb_snap["high"] = idle_high
        eb_snap["overall"] = 0.015
        eb_snap["smooth_mid"] = idle_mid
        eb_snap["smooth_high"] = idle_high
        eb_snap["crest"] = 0.0
        eb_snap["pulse_bass"] = idle_bass
        eb_snap["pulse_mid"] = idle_mid
        eb_snap["pulse_high"] = idle_high
        eb_snap["pulse_overall"] = 0.015
    else:
        # Build two parallel Bubble feeds:
        # - motion feed (`bass`/`mid`) can absorb transient/onset energy
        # - pulse feed (`pulse_*`) stays clean so Bubble size authority can
        #   come from sustained body plus non-transient body-delta
        _pulse_bass = getattr(eb_pulse, 'bass', 0.0) if eb_pulse else 0.0
        _pulse_mid = getattr(eb_pulse, 'mid', 0.0) if eb_pulse else 0.0
        _pulse_high = getattr(eb_pulse, 'high', 0.0) if eb_pulse else 0.0
        _pulse_overall = getattr(eb_pulse, 'overall', 0.0) if eb_pulse else 0.0
        _t_bass = getattr(tb, 'bass_transient', 0.0) if tb else 0.0
        _t_mid = getattr(tb, 'mid_transient', 0.0) if tb else 0.0
        _onset_detected = bool(getattr(tb, 'onset_detected', False)) if tb else False
        _onset_type = str(getattr(tb, 'onset_type', '')) if tb else ''
        _onset_strength = float(getattr(tb, 'onset_strength', 0.0) or 0.0) if tb else 0.0
        _t_gain = getattr(widget, '_transient_pulse_gain', 1.0)
        _t_clamp = getattr(widget, '_transient_clamp', 1.5)
        _bmix_bass = getattr(widget, '_bubble_transient_mix_bass', 0.75)
        _bmix_vocal = getattr(widget, '_bubble_transient_mix_vocal', 0.25)
        _hot_bass_lift = soft_ceiling(
            max(0.0, _pulse_bass - 0.85),
            knee=0.0,
            ceiling=0.12,
            max_input=0.40,
            curve=1.0,
        )
        _hot_presence = soft_ceiling(
            max(0.0, _pulse_bass - 0.92),
            knee=0.0,
            ceiling=0.09,
            max_input=0.42,
            curve=1.0,
        )
        _hot_crest_step = soft_ceiling(
            max(0.0, _pulse_bass - prev_dispatch_bass - 0.020),
            knee=0.0,
            ceiling=0.18,
            max_input=0.20,
            curve=1.0,
        ) * max(0.0, min(1.0, (_pulse_bass - 0.82) / 0.26))
        _onset_crest_scale = 0.0
        if _onset_detected:
            if _onset_type == 'kick':
                _onset_crest_scale = 1.0
            elif _onset_type == 'snare':
                _onset_crest_scale = 0.88
            elif _onset_type == 'vocal_swell':
                _onset_crest_scale = 0.46
        _onset_crest_step = soft_ceiling(
            max(0.0, _onset_strength - 0.10),
            knee=0.0,
            ceiling=0.12,
            max_input=0.45,
            curve=1.0,
        ) * _onset_crest_scale * max(0.0, min(1.0, (_pulse_bass - 0.74) / 0.28))
        _hot_crest_step += _onset_crest_step
        _mixed_bass = min(_t_clamp, _pulse_bass + _t_bass * _t_gain * _bmix_bass)
        _mixed_mid = min(_t_clamp, _pulse_mid + _t_mid * _t_gain * _bmix_vocal)
        eb_snap["bass"] = min(_t_clamp, _mixed_bass + _hot_bass_lift + _hot_crest_step)
        eb_snap["mid"] = _mixed_mid
        eb_snap["high"] = _pulse_high
        eb_snap["smooth_mid"] = max(
            getattr(eb_smooth, 'mid', 0.0) if eb_smooth else 0.0,
            _hot_presence * 0.82 + _hot_crest_step * 0.12,
        )
        eb_snap["smooth_high"] = max(
            getattr(eb_smooth, 'high', 0.0) if eb_smooth else 0.0,
            _hot_presence * 0.34 + _hot_crest_step * 0.05,
        )
        eb_snap["overall"] = max(
            getattr(eb_smooth, 'overall', 0.0) if eb_smooth else 0.0,
            min(
                1.0,
                eb_snap["bass"] * 0.46
                + eb_snap["smooth_mid"] * 0.34
                + eb_snap["smooth_high"] * 0.20,
            ),
        )
        eb_snap["crest"] = min(
            1.0,
            _hot_crest_step * 4.2
            + _onset_crest_step * 1.6,
        )
        eb_snap["pulse_bass"] = _pulse_bass
        eb_snap["pulse_mid"] = _pulse_mid
        eb_snap["pulse_high"] = _pulse_high
        eb_snap["pulse_overall"] = max(
            _pulse_overall,
            min(
                1.0,
                _pulse_bass * 0.46
                + _pulse_mid * 0.34
                + _pulse_high * 0.20,
            ),
        )

    sim_settings = getattr(widget, "_bubble_dispatch_settings", None)
    if not isinstance(sim_settings, dict):
        sim_settings = {}
        widget._bubble_dispatch_settings = sim_settings
    sim_settings.update({
        "bubble_big_count": widget._bubble_big_count,
        "bubble_small_count": widget._bubble_small_count,
        "bubble_surface_reach": widget._bubble_surface_reach,
        "bubble_stream_direction": widget._bubble_stream_direction,
        "bubble_stream_constant_speed": widget._bubble_stream_constant_speed,
        "bubble_stream_speed_cap": widget._bubble_stream_speed_cap,
        "bubble_stream_reactivity": widget._bubble_stream_reactivity,
        "bubble_rotation_amount": widget._bubble_rotation_amount,
        "bubble_drift_amount": widget._bubble_drift_amount,
        "bubble_group_drift": getattr(widget, "_bubble_group_drift", False),
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
    })

    pulse_params = getattr(widget, "_bubble_dispatch_pulse_params", None)
    if not isinstance(pulse_params, dict):
        pulse_params = {}
        widget._bubble_dispatch_pulse_params = pulse_params
    pulse_params.update({
        'bass': eb_snap['bass'],
        'mid_high': (eb_snap['mid'] + eb_snap['high']) * 0.5,
        'big_bass_pulse': widget._bubble_big_bass_pulse,
        'small_freq_pulse': widget._bubble_small_freq_pulse,
        'big_specular_max_size': widget._bubble_big_specular_max_size,
        'big_visual_smoothing': getattr(widget, '_bubble_big_visual_smoothing', 0.5),
        'big_contraction_bias': widget._bubble_big_contraction_bias,
        'big_size_clamp': widget._bubble_big_size_clamp,
    })

    # Freeze one admitted logical input. There is no Bubble worker queue or
    # presentation acknowledgement: the current authored step integrates now.
    energy_payload = dict(eb_snap)
    settings_payload = dict(sim_settings)
    pulse_payload = dict(pulse_params)
    source_ts = 0.0
    source_generation = -1
    source_activation = -1
    engine_generation = -1
    engine_activation = -1
    if widget._engine is not None:
        try:
            engine_generation = coerce_identity(
                widget._engine.get_generation_id()
            )
            engine_activation = coerce_identity(
                widget._engine.get_activation_id()
            )
        except Exception:
            pass
        try:
            (
                raw_source_ts,
                raw_source_generation,
                raw_source_activation,
            ) = widget._engine.get_latest_authoritative_frame()
            source_ts = float(raw_source_ts)
            source_generation = coerce_identity(raw_source_generation)
            source_activation = coerce_identity(raw_source_activation)
        except Exception:
            source_ts = 0.0
    source_ready = bool(
        source_generation >= 0
        and source_activation >= 0
        and source_generation == engine_generation
        and source_activation == engine_activation
    )
    step_token = cadence.begin_step()
    try:
        resolved = runtime.advance(
            dt=dt_bubble,
            energy=energy_payload,
            settings=settings_payload,
            pulse=pulse_payload,
            source_timestamp=source_ts,
            authored_timestamp=now_ts,
            runtime_generation=coerce_identity(
                getattr(widget, "_runtime_generation", None)
            ),
            engine_generation=engine_generation,
            activation_id=engine_activation,
            playing=bool(widget._spotify_playing),
            source_ready=source_ready,
            source_generation=source_generation,
            source_activation_id=source_activation,
            edge_token=int(step_token[1]),
        )
    except Exception:
        cadence.note_step_failed()
        logger.exception("[SPOTIFY_VIS] Bubble logical integration failed")
        return
    if resolved is None:
        return
    cadence.note_step_integrated()

    if controller.mode_id != "bubble" or widget._vis_mode_str != "bubble":
        # A concurrent mode retirement remains authoritative. The completed
        # old-mode result is never mirrored or admitted into the new mode.
        return

    # Temporary old-presenter mirror. The immutable controller-owned result is
    # authoritative; no Quick renderer reads these QWidget adapter fields.
    widget._bubble_pos_data = list(resolved.positions)
    widget._bubble_extra_data = list(resolved.extras)
    widget._bubble_trail_data = list(resolved.trails)
    widget._bubble_count = resolved.bubble_count
    widget._bubble_visible_source_ts = resolved.source_timestamp
    widget._bubble_visible_simulation_ts = resolved.simulation_timestamp
    widget._bubble_visible_render_state_ts = now_ts
    widget._bubble_last_perf_diag = dict(resolved.perf_diagnostics)


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
        and _mode_is_idle_self_animating(getattr(widget, "_vis_mode_str", ""))
        and (
            not bool(getattr(widget, "_startup_idle_reveal_requires_authoritative_media", False))
            or bool(getattr(widget, "_startup_has_authoritative_media_update", False))
        )
    ):
        widget._waiting_for_fresh_engine_frame = False
        widget._pending_engine_generation = -1

    if widget._waiting_for_fresh_engine_frame and widget._pending_engine_generation >= 0:
        try:
            latest_gen = engine.get_latest_generation_with_frame()
        except Exception:
            latest_gen = -1
        try:
            engine_activation_id = engine.get_activation_id()
        except Exception:
            engine_activation_id = -1
        activation_ready = (
            widget._pending_engine_activation_id < 0
            or engine_activation_id == widget._pending_engine_activation_id
        )
        waveform_ready = True
        if _mode_requires_fresh_waveform(getattr(widget, "_vis_mode_str", "")):
            try:
                latest_waveform_gen = engine.get_latest_generation_with_waveform()
            except Exception:
                latest_waveform_gen = -1
            waveform_ready = latest_waveform_gen >= widget._pending_engine_generation
        if latest_gen >= widget._pending_engine_generation and waveform_ready and activation_ready:
            widget._waiting_for_fresh_engine_frame = False
            widget._last_engine_generation_seen = latest_gen
            widget._last_engine_activation_seen = engine_activation_id
            logger.debug(
                "[SPOTIFY_VIS] Engine delivered fresh frame (gen=%d activation=%s) after reset",
                latest_gen,
                engine_activation_id,
            )

    pending_reasons = list(widget._latency_pending_probe)
    widget._latency_pending_probe.clear()
    probe_reason = ",".join(pending_reasons) if pending_reasons else None
    widget._log_audio_latency_metrics(engine, now_ts, force_reason=probe_reason)

    if widget._waiting_for_fresh_engine_frame:
        # Do not copy any engine bars into the display array while the reset
        # generation is unresolved.  Even if a stale compute callback manages
        # to publish data, it gets no visual authority before the verified
        # activation/generation handoff.
        return False, False

    # Get pre-smoothed bars from engine (smoothing done on COMPUTE pool)
    smoothed = engine.get_smoothed_bars()

    # Capture engine generation/activation for source tracking
    try:
        engine_generation = engine.get_generation_id()
    except Exception:
        engine_generation = -1
    try:
        engine_activation = engine.get_activation_id()
    except Exception:
        engine_activation = -1

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

    # Source tracking records the accepted engine frame even when the first
    # fresh post-reset bars happen to be visually quiet. Reactive modes must
    # still prove their first visible frame came from the current activation.
    widget._display_bars_source_generation = engine_generation
    widget._display_bars_source_activation = engine_activation

    _idle_mode_key = getattr(widget, "_vis_mode_str", "")
    if (
        not widget._spotify_playing
        and _mode_allows_idle_reveal_key(_idle_mode_key)
        and (
            # A presentation-owned idle scene needs no engine frame to reveal.
            not _mode_is_idle_self_animating(_idle_mode_key)
            or not bool(getattr(widget, "_waiting_for_fresh_engine_frame", False))
        )
        and bool(getattr(widget, "_waiting_for_fresh_frame", False))
    ):
        try:
            widget._on_first_frame_after_cold_start()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed idle-ready startup reveal handoff", exc_info=True)

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

    mode_str = widget._vis_mode_str
    if mode_str == "spectrum":
        presentation_bars, presentation_changed = resolve_widget_spectrum_presentation(
            widget,
            widget._display_bars,
            now_ts=now_ts,
            first_frame=first_frame,
        )
        changed = changed or presentation_changed
    else:
        presentation_bars = list(widget._display_bars)
        reset_widget_spectrum_presentation_smoothing(widget)

    try:
        resolve_gpu_target_rect = getattr(widget, "_resolve_gpu_target_rect", None)
        if callable(resolve_gpu_target_rect):
            current_geom = resolve_gpu_target_rect()
        else:
            current_geom = widget.geometry()
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        current_geom = None
    last_geom = widget._last_gpu_geom
    geom_changed = last_geom is None or (current_geom is not None and current_geom != last_geom)

    # ONE fade authority, TWO published consumers of the same progress:
    # the authored card pixels use the progress directly, the visualizer
    # shader applies the authored stagger to that same progress. They are
    # resolved and published together so no layer can drift onto a second
    # curve or a QWidget opacity side-channel.
    scene_fade = widget._get_scene_fade_factor(now_ts)
    bars_fade = widget._get_gpu_fade_factor(now_ts)
    # Apply mode-transition crossfade (1.0 when idle, 0→1 during switch).
    #
    # It multiplies the SHADER only. The authored card has always faded on
    # its own reveal curve alone - that is what the QWidget opacity effect
    # used to do - and stacking the crossfade on top of it made a mode
    # switch look dead for most of the transition.
    transition_fade = widget._mode_transition_fade_factor(now_ts)
    bars_fade *= transition_fade
    prev_fade = widget._last_gpu_fade_sent
    prev_bars_fade = float(getattr(widget, "_last_gpu_bars_fade_sent", -1.0))
    widget._last_gpu_fade_sent = scene_fade
    widget._last_gpu_bars_fade_sent = bars_fade
    # The bars curve moves faster than the scene curve inside its window, so
    # a bars-only delta must still count as a change worth publishing.
    fade_changed = (
        prev_fade < 0.0
        or abs(scene_fade - prev_fade) >= 0.01
        or prev_bars_fade < 0.0
        or abs(bars_fade - prev_bars_fade) >= 0.01
    )
    need_card_update = fade_changed

    transitioning = widget._mode_transition_phase != 0
    # Animated modes must push every tick because their visuals change
    # continuously independent of bar data.
    animated_mode = (widget._vis_mode_str != 'spectrum') or getattr(widget, '_rainbow_enabled', False)
    should_push = changed or fade_changed or first_frame or geom_changed or transitioning or animated_mode
    if not should_push:
        return False

    _gpu_push_start = time.time()
    from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs
    extra = build_gpu_push_extra_kwargs(widget, mode_str, widget._engine)

    first_frame_probe_key = None
    primer_problems: list[str] = []
    if first_frame:
        first_frame_probe_key = (
            str(mode_str or "unknown"),
            int(getattr(widget, "_display_bars_source_generation", -1) or -1),
            int(getattr(widget, "_display_bars_source_activation", -1) or -1),
            int(getattr(widget, "_pending_engine_generation", -1) or -1),
            int(getattr(widget, "_pending_engine_activation_id", -1) or -1),
            int(getattr(widget, "_bar_count", 0) or 0),
        )
        if getattr(widget, "_first_overlay_push_probe_key", None) != first_frame_probe_key:
            log_render = getattr(widget, "_log_active_render_state_snapshot", None)
            if callable(log_render):
                try:
                    log_render(reason="before_first_overlay_push")
                except Exception:
                    logger.debug("[SPOTIFY_VIS] Failed to log render state before first overlay push", exc_info=True)
            widget._first_overlay_push_probe_key = first_frame_probe_key
        primer_problems = _collect_first_frame_primer_problems(widget, parent, mode_str)
        if primer_problems and is_viz_logging_enabled():
            logger.info(
                "[SPOTIFY_VIS][FIRST_FRAME_PRIMER] mode=%s problems=%s",
                mode_str,
                ",".join(primer_problems),
            )

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

    effective_fade = 0.0 if primer_problems else scene_fade
    effective_bars_fade = 0.0 if primer_problems else bars_fade

    used_gpu = parent.push_spotify_visualizer_frame(
        bars=presentation_bars,
        bar_count=widget._bar_count,
        segments=widget._dynamic_bar_segments(),
        fill_color=widget._bar_fill_color,
        border_color=widget._bar_border_color,
        fade=effective_fade,
        bars_fade=effective_bars_fade,
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

    if first_frame and used_gpu and not primer_problems:
        log_render = getattr(widget, "_log_active_render_state_snapshot", None)
        if callable(log_render):
            try:
                log_render(reason="after_first_overlay_push")
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to log render state after first overlay push", exc_info=True)
        _warn_on_first_frame_guard_mismatch(widget, parent)

    if used_gpu:
        try:
            if current_geom is None:
                resolve_gpu_target_rect = getattr(widget, "_resolve_gpu_target_rect", None)
                if callable(resolve_gpu_target_rect):
                    current_geom = resolve_gpu_target_rect()
                else:
                    current_geom = widget.geometry()
            widget._last_gpu_geom = QRect(current_geom)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            widget._last_gpu_geom = None
        # Card/background/shadow still repaint via stylesheet
        if need_card_update:
            widget.update()
        if not primer_problems:
            widget._has_pushed_first_frame = True
            widget._first_overlay_push_probe_key = None
            widget._on_first_frame_after_cold_start()
    return used_gpu


def presentation_owned_idle_is_active(widget: Any, mode: Any = None) -> bool:
    """True when the visible scene is presentation-owned and needs no source.

    `presentation_ready` and `reactive_source_ready` are different questions.
    Paused Spectrum is the mixed state that forced the distinction: its card and
    static baseline are built entirely by presentation, while real bars still
    require a fresh current-activation source frame that cannot arrive while
    capture is paused.

    Treating absent source identity as a presentation blocker in that state is
    what forced effective fade to zero and refused the first-frame handoff, so
    the card stayed invisible until Play.
    """

    mode_key = mode_capabilities.mode_key(
        mode if mode is not None else getattr(widget, "_vis_mode_str", "")
    )
    if bool(getattr(widget, "_spotify_playing", False)):
        return False
    return (
        mode_capabilities.allows_idle_reveal(mode_key)
        and mode_capabilities.has_presentation_owned_idle_scene(mode_key)
    )


def _collect_first_frame_primer_problems(widget: Any, parent: Any, mode: str) -> list[str]:
    """Return stale pre-push overlay state that requires a hidden priming push."""
    overlay = getattr(parent, "_spotify_bars_overlay", None) if parent is not None else None
    if overlay is None:
        return []

    problems: list[str] = []
    mode_key = str(mode or "unknown").lower()
    overlay_mode = str(getattr(overlay, "_vis_mode", "") or "").lower()
    overlay_activation = getattr(overlay, "_activation_id", None)
    overlay_generation = getattr(overlay, "_engine_generation", None)
    display_source_generation = int(getattr(widget, "_display_bars_source_generation", -1) or -1)
    display_source_activation = int(getattr(widget, "_display_bars_source_activation", -1) or -1)
    # Source authority is still required for reactive playback, but a
    # presentation-owned idle scene is not waiting on it to become visible.
    requires_authoritative_source = (
        _mode_requires_authoritative_first_source(mode_key)
        and not presentation_owned_idle_is_active(widget, mode_key)
    )

    if overlay_mode and overlay_mode != mode_key:
        problems.append("overlay_mode_stale")

    pending_mode_resets = getattr(overlay, "_pending_mode_resets", None)
    if pending_mode_resets and mode_key in set(pending_mode_resets):
        problems.append("overlay_pending_mode_reset")

    if requires_authoritative_source and display_source_generation < 0:
        problems.append("display_source_generation_missing")
    if requires_authoritative_source and display_source_activation < 0:
        problems.append("display_source_activation_missing")
    if display_source_generation >= 0 and overlay_generation != display_source_generation:
        problems.append("overlay_generation_stale")
    if display_source_activation >= 0 and overlay_activation != display_source_activation:
        problems.append("overlay_activation_stale")

    return problems


def _warn_on_first_frame_guard_mismatch(widget: Any, parent: Any) -> None:
    """Emit an explicit warning when first-push guardrail state looks wrong."""
    overlay = getattr(parent, "_spotify_bars_overlay", None) if parent is not None else None
    overlay_activation = getattr(overlay, "_activation_id", None) if overlay is not None else None
    overlay_generation = getattr(overlay, "_engine_generation", None) if overlay is not None else None
    display_source_generation = int(getattr(widget, "_display_bars_source_generation", -1) or -1)
    display_source_activation = int(getattr(widget, "_display_bars_source_activation", -1) or -1)
    waiting_engine = bool(getattr(widget, "_waiting_for_fresh_engine_frame", False))
    waiting_frame = bool(getattr(widget, "_waiting_for_fresh_frame", False))
    mode = str(getattr(widget, "_vis_mode_str", "unknown") or "unknown")
    requires_authoritative_source = (
        _mode_requires_authoritative_first_source(mode)
        and not presentation_owned_idle_is_active(widget, mode)
    )
    try:
        display_max = max(getattr(widget, "_display_bars", []) or [0.0])
    except Exception:
        display_max = 0.0
    staged_zero_data = (
        display_max <= 0.01
        and display_source_generation < 0
        and not waiting_engine
        and not requires_authoritative_source
    )

    if staged_zero_data:
        return

    problems: list[str] = []
    if waiting_engine:
        problems.append("waiting_engine_after_push")
    if requires_authoritative_source and display_source_generation < 0:
        problems.append("display_missing_source_generation")
    if requires_authoritative_source and display_source_activation < 0:
        problems.append("display_missing_source_activation")
    if display_max > 0.01 and display_source_generation < 0:
        problems.append("display_missing_source_generation")
    if display_source_generation >= 0 and overlay_generation != display_source_generation:
        problems.append("overlay_generation_mismatch")
    if display_source_activation >= 0 and overlay_activation != display_source_activation:
        problems.append("overlay_activation_mismatch")
    if (
        waiting_frame
        and (
            waiting_engine
            or display_source_generation < 0
            or overlay_generation != display_source_generation
            or overlay_activation != display_source_activation
        )
    ):
        problems.append("waiting_frame_after_push")

    if not problems:
        return

    logger.warning(
        "[!!!!][SPOTIFY_VIS][FIRST_FRAME_GUARD] mode=%s problems=%s display_max=%.3f "
        "display_source_generation=%s display_source_activation=%s "
        "overlay_generation=%s overlay_activation=%s waiting_engine=%s waiting_frame=%s",
        mode,
        ",".join(problems),
        display_max,
        display_source_generation,
        display_source_activation,
        overlay_generation,
        overlay_activation,
        waiting_engine,
        waiting_frame,
    )


# ------------------------------------------------------------------
# Audio latency metrics
# ------------------------------------------------------------------

def _ensure_latency_logging_ready(
    widget: Any,
    engine: Optional[Any],
    *,
    source_ts: float,
    source_generation: int,
    source_activation: int,
    current_generation: int,
    current_activation: int,
    latest_frame_generation: int,
) -> bool:
    """Return True only for a fresh frame owned by the current engine epoch."""
    if engine is None:
        return False

    activation_started_ts = float(getattr(widget, "_latency_activation_started_ts", 0.0) or 0.0)
    has_fresh_timestamp = source_ts > 0.0 and (
        activation_started_ts <= 0.0 or source_ts >= (activation_started_ts - 0.05)
    )
    has_current_frame = (
        current_generation >= 0
        and current_activation >= 0
        and latest_frame_generation == current_generation
        and source_generation == current_generation
        and source_activation == current_activation
    )
    if not (has_fresh_timestamp and has_current_frame):
        widget._latency_audio_ready = False
        return False

    widget._latency_audio_ready = True
    widget._latency_authority = (current_generation, current_activation)

    return bool(getattr(widget, "_latency_audio_ready", False))


def log_audio_latency_metrics(
    widget: Any,
    engine: Optional[Any],
    now_ts: float,
    force_reason: Optional[str] = None,
) -> None:
    """Emit viz-only latency diagnostics when enabled via --viz."""
    if engine is None or not is_viz_logging_enabled():
        return
    if not bool(getattr(widget, "_enabled", False)):
        return
    # Transition probes request a sample; they never make paused idle age a
    # meaningful latency measurement.
    if not bool(getattr(widget, "_spotify_playing", False)):
        return

    try:
        current_generation = int(engine.get_generation_id())
    except Exception:
        current_generation = -1
    try:
        current_activation = int(engine.get_activation_id())
    except Exception:
        current_activation = -1
    try:
        latest_frame_generation = int(engine.get_latest_generation_with_frame())
    except Exception:
        latest_frame_generation = -1
    try:
        source_ts, source_generation, source_activation = (
            engine.get_latest_authoritative_frame()
        )
        source_ts = float(source_ts)
        source_generation = int(source_generation)
        source_activation = int(source_activation)
    except Exception:
        # Compatibility for injected test engines. Production engines expose
        # the generation-tagged authoritative snapshot above.
        source_ts = float(getattr(engine, "_last_smooth_ts", -1.0) or -1.0)
        source_generation = current_generation
        source_activation = current_activation
    if source_ts <= 0.0:
        return

    ready = _ensure_latency_logging_ready(
        widget,
        engine,
        source_ts=source_ts,
        source_generation=source_generation,
        source_activation=source_activation,
        current_generation=current_generation,
        current_activation=current_activation,
        latest_frame_generation=latest_frame_generation,
    )
    if not ready:
        return
    if (
        (now_ts - widget._latency_last_log_ts) < widget._latency_log_interval
    ):
        return

    lag_ms = max(0.0, (now_ts - source_ts) * 1000.0)
    phase = widget._mode_transition_phase
    mode = getattr(widget, "_vis_mode_str", "unknown")
    pending = getattr(widget, "_mode_transition_pending", None)
    pending_mode = getattr(pending, "name", None) if pending is not None else None

    if lag_ms < widget._latency_warn_ms:
        # A recovered healthy sample re-arms one future bounded warning.
        widget._latency_last_signature = None
        return

    severity = "high" if lag_ms >= widget._latency_error_ms else "elevated"
    signature = (
        mode,
        current_generation,
        current_activation,
        source_generation,
        source_activation,
    )
    if signature == widget._latency_last_signature:
        return
    widget._latency_last_signature = signature

    trigger_suffix = f" trigger={force_reason}" if force_reason else ""
    msg = (
        "[SPOTIFY_VIS][LATENCY] lag_ms=%.1f severity=%s mode=%s "
        "transition_phase=%d pending=%s engine_generation=%d "
        "activation_id=%d frame_generation=%d frame_activation=%d%s"
        % (
            lag_ms,
            severity,
            mode,
            phase,
            pending_mode or "<none>",
            current_generation,
            current_activation,
            source_generation,
            source_activation,
            trigger_suffix,
        )
    )
    # Source-frame age is diagnostic evidence, not proof that presentation is
    # stale. Actual presentation-staleness owners may still log ERROR.
    logger.warning(msg)

    widget._latency_last_log_ts = now_ts


# ------------------------------------------------------------------
# Main tick entry point
# ------------------------------------------------------------------

def on_tick(widget: Any) -> None:
    """Run one logical step and present it on the GUI thread.

    Retained for the GUI-driven paths that still call the whole tick directly
    (tests, replay harnesses, and any runtime without a logical thread). The
    logical runtime calls `logical_tick()` and the GUI presents through
    `present_tick()`.
    """

    if logical_tick(widget) is None:
        return
    present_tick(widget)


def present_tick(widget: Any) -> bool:
    """GUI-thread half: turn the freshest logical frame into a pushed frame.

    Owns everything the logical thread must not touch - widget geometry, the
    presentation fade, card pixels and the compositor publish.
    """

    if not Shiboken.isValid(widget):
        return False
    frame = widget._logical_mailbox.take() if getattr(widget, "_logical_mailbox", None) else None
    if frame is None:
        return False
    payload = frame.state
    if not isinstance(payload, VisualizerLogicalFrame):
        logger.error(
            "[SPOTIFY_VIS] Rejected non-immutable logical publication: %s",
            type(payload).__name__,
        )
        return False
    generation = coerce_identity(getattr(widget, "_runtime_generation", None))
    if (
        int(frame.generation) != payload.runtime_generation
        or int(frame.activation_id) != payload.activation_id
    ):
        return False
    if generation >= 0 and payload.runtime_generation != generation:
        # A retired generation's frame must never be presented. `coerce_identity`
        # keeps a valid generation 0 as 0 so this fence stays armed for the first
        # generation instead of being disabled by a -1 sentinel.
        return False

    engine = getattr(widget, "_engine", None)
    current_engine_generation = coerce_identity(
        getattr(widget, "_last_engine_generation_seen", None)
    )
    current_activation = coerce_identity(
        getattr(widget, "_last_engine_activation_seen", None)
    )
    if engine is not None:
        try:
            current_engine_generation = coerce_identity(engine.get_generation_id())
            current_activation = coerce_identity(engine.get_activation_id())
        except Exception:
            pass
    if (
        current_engine_generation >= 0
        and payload.engine_generation != current_engine_generation
    ):
        return False
    if current_activation >= 0 and payload.activation_id != current_activation:
        return False
    controller = getattr(widget, "runtime_controller", None)
    current_mode = (
        controller.mode_id
        if controller is not None
        else mode_capabilities.widget_mode_key(widget)
    )
    if payload.mode_id != current_mode:
        return False

    if payload.mode_reveal_ready:
        # The logical half decided; the GUI half performs the reveal.
        mode_transition.execute_mode_reveal(widget, payload.logical_timestamp)
    if not payload.present_frame:
        return False
    parent = widget.parent()
    first_frame = not widget._has_pushed_first_frame
    return bool(
        push_gpu_frame(
            widget,
            parent,
            payload.logical_timestamp,
            payload.changed,
            first_frame,
        )
    )


def request_logical_present(widget: Any) -> None:
    """Ask the GUI thread to present the freshest logical frame.

    Single-pending on purpose: while one present is outstanding, further logical
    steps replace the mailbox slot instead of queueing another callback. A GUI
    stall costs presentation freshness and never builds a backlog, and the
    simulation keeps its own cadence regardless - which is the point of moving
    cadence off the event loop.
    """

    if getattr(widget, "_logical_present_pending", False):
        return
    manager = getattr(widget, "_thread_manager", None)
    if manager is None:
        return
    widget._logical_present_pending = True
    try:
        manager.run_on_ui_thread(present_logical_frame, widget)
    except Exception:
        widget._logical_present_pending = False
        logger.debug("[SPOTIFY_VIS] Failed to request logical present", exc_info=True)


def present_logical_frame(widget: Any) -> None:
    """GUI-thread presentation of the freshest published logical frame."""

    widget._logical_present_pending = False
    try:
        present_tick(widget)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Logical present failed", exc_info=True)


def _publish_logical_state(
    widget: Any,
    now_ts: float,
    *,
    changed: bool,
    mode_reveal_ready: bool,
    present_frame: bool = True,
    protected_edges: Sequence[VisualizerProtectedEdge] = (),
) -> VisualizerLogicalFrame:
    """Publish one immutable logical result for the presentation half.

    Latest-wins: a GUI thread that cannot keep up loses freshness rather than
    accumulating a backlog, and the simulation keeps its own cadence regardless.
    """

    from widgets.spotify_visualizer.legacy_render_snapshot_adapter import (
        capture_legacy_visualizer_logical_frame,
    )

    payload = capture_legacy_visualizer_logical_frame(
        widget,
        now_ts=now_ts,
        changed=changed,
        mode_reveal_ready=mode_reveal_ready,
        present_frame=present_frame,
        protected_edges=protected_edges,
    )
    mailbox = widget._logical_mailbox
    mailbox.publish(
        payload,
        generation=payload.runtime_generation,
        activation_id=payload.activation_id,
        now_ts=payload.logical_timestamp,
    )
    if getattr(widget, "_logical_runtime", None) is not None:
        # Only a thread-owned cadence needs marshalling; the GUI-driven path
        # presents synchronously in `on_tick()`.
        request_logical_present(widget)
    return payload


def logical_tick(widget: Any) -> Optional[VisualizerLogicalFrame]:
    """Plain-data half: advance the simulation and publish the latest state.

    Safe to run off the GUI thread. It must not read widget geometry, touch
    QPixmap/GL state, or call `QWidget.update()`; `present_tick()` owns all of
    that.
    """

    _tick_entry_ts = time.time()
    _tick_phase_start = time.perf_counter()
    _tick_phase_ms: dict[str, float] = {}

    def _record_tick_phase(name: str) -> None:
        nonlocal _tick_phase_start
        now_perf = time.perf_counter()
        _tick_phase_ms[name] = (now_perf - _tick_phase_start) * 1000.0
        _tick_phase_start = now_perf

    _ensure_fresh_generation_state(widget)
    _record_tick_phase("fresh_state")

    if not widget._enabled:
        return None
    _record_tick_phase("validity")

    now_ts = time.time()
    # Transition state deliberately no longer reaches the logical step. It used
    # to retune the tick interval every tick and pause the tick source outright;
    # per Current_Plan sections 7.3 and 8 the authored logical cadence is
    # constant and transition activity is a presentation concern.
    transition_ctx: dict = {}
    _record_tick_phase("context")

    last = widget._last_update_ts
    dt_since_last = 0.0
    if last >= 0.0:
        dt_since_last = now_ts - last

    widget._last_update_ts = now_ts
    _dt_spike_max_reasonable_ms: float = 1000.0
    dt_for_spike_check = min(dt_since_last * 1000.0, _dt_spike_max_reasonable_ms)
    if dt_since_last * 1000.0 >= widget._dt_spike_threshold_ms and dt_for_spike_check < _dt_spike_max_reasonable_ms:
        widget._log_tick_spike(dt_since_last, transition_ctx)

    # Perf metrics accounting
    record_tick_perf(widget, now_ts)
    _record_tick_phase("perf_accounting")

    # Consume bars from engine
    changed, _any_nonzero = consume_engine_bars(widget, now_ts)
    _record_tick_phase("engine_consume")
    # Let paused mode transitions progress even when fresh-engine wait short-circuits.
    # Readiness only. The reveal itself mutates QWidget/QPixmap state and is
    # executed by the presentation half, which is what makes this step safe to
    # own off the GUI thread.
    mode_reveal_ready = bool(widget._check_mode_teardown_ready(widget._engine, now_ts))
    _record_tick_phase("teardown_check")
    # If consume returned (False, False) while waiting for fresh engine frame, bail.
    #
    # A mode whose idle scene is presentation-owned is the exception: it needs no
    # source frame to draw anything, and `push_gpu_frame()` downstream is the
    # only normal call site that builds that scene. Returning here meant paused
    # Spectrum said "my idle needs no source" and "do not run my idle until
    # source arrives" at the same time, which is why its card stayed blank.
    #
    # The wait itself is deliberately preserved: it still gates reactive source
    # authority when playback resumes.
    if widget._waiting_for_fresh_engine_frame and not changed and not _any_nonzero:
        if widget._spotify_playing or not mode_capabilities.has_presentation_owned_idle_scene(
            getattr(widget, "_vis_mode_str", "")
        ):
            # Nothing new to draw, but a decided reveal must still reach the GUI
            # half. Before the split this path ran the reveal inline, so losing
            # it here would strand a completed mode transition.
            return _publish_logical_state(
                widget, now_ts, changed=False, mode_reveal_ready=mode_reveal_ready,
                present_frame=False
            )

    # Heartbeat transient detection for sine mode
    process_heartbeat(widget, now_ts)
    _record_tick_phase("heartbeat")

    if widget._mode_teardown_block_until_ready and not widget._mode_transition_ready:
        return _publish_logical_state(
            widget, now_ts, changed=False, mode_reveal_ready=mode_reveal_ready,
            present_frame=False
        )

    # Bubble logical step
    dispatch_bubble_simulation(widget, now_ts)
    _record_tick_phase("bubble_step")

    # DEVCURVE liquid field solve (UI-thread, cheap: ~32 sources)
    dispatch_devcurve_field(widget, now_ts)
    _record_tick_phase("devcurve_dispatch")

    # Publish the latest logical frame. The slot is latest-wins, so a GUI thread
    # that cannot keep up loses freshness rather than accumulating a backlog -
    # and, critically, the simulation above keeps its own cadence regardless.
    payload = _publish_logical_state(
        widget, now_ts, changed=changed, mode_reveal_ready=mode_reveal_ready
    )
    used_gpu = False
    first_frame = not widget._has_pushed_first_frame
    _record_tick_phase("publish")

    # PERF: Log slow ticks
    _tick_elapsed = (time.time() - _tick_entry_ts) * 1000.0
    if _tick_elapsed > 50.0 and is_perf_metrics_enabled():
        logger.warning("[PERF] [SPOTIFY_VIS] Slow _on_tick: %.2fms", _tick_elapsed)
        phase_payload = " ".join(
            f"{name}_ms={elapsed_ms:.2f}"
            for name, elapsed_ms in _tick_phase_ms.items()
        )
        logger.warning(
            "[PERF] [SPOTIFY_VIS] Tick phase breakdown total_ms=%.2f mode=%s "
            "changed=%s first_frame=%s used_gpu=%s %s",
            _tick_elapsed,
            getattr(widget, "_vis_mode_str", "unknown"),
            changed,
            first_frame,
            used_gpu,
            phase_payload,
        )
    return payload
