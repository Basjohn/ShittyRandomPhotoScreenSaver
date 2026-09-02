"""Spotify Visualizer authored logical tick pipeline.

The sole logical runtime advances source-derived mode state here and publishes
immutable ``VisualizerLogicalFrame`` snapshots.  Retained Qt Quick owns all
presentation, geometry and GL commit work; this module owns no QWidget/painter
or presentation cadence.
"""
from __future__ import annotations

import logging
import math
import time
from collections.abc import Sequence
from typing import Any, Optional


from core.logging.logger import (
    get_logger,
    is_perf_metrics_enabled,
    is_viz_diagnostics_enabled,
    is_viz_logging_enabled,
)
from widgets.spotify_visualizer.signal_contract import soft_ceiling
from widgets.spotify_visualizer import mode_capabilities
from widgets.spotify_visualizer.logical_runtime import coerce_identity
from widgets.spotify_visualizer.reactivity_diagnostics import (
    maybe_log_logical_publication,
    maybe_log_reactivity_boundary,
)
from widgets.spotify_visualizer.render_state import (
    VisualizerEnergyState,
    VisualizerLogicalFrame,
    VisualizerProtectedEdge,
    VisualizerTransientState,
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
# DevCurve authored-field dispatch
# ------------------------------------------------------------------

_DEVCURVE_LAYERS = ("bass", "vocals", "mids", "transients")
_DEVCURVE_LAYER_DEFAULTS = {
    "bass": {
        "color": (82, 167, 255, 230),
        "alpha": 0.55,
        "power": 1.0,
        "offset": 0.0,
    },
    "vocals": {
        "color": (136, 190, 255, 220),
        "alpha": 0.42,
        "power": 1.0,
        "offset": -0.01,
    },
    "mids": {
        "color": (100, 145, 255, 220),
        "alpha": 0.46,
        "power": 1.0,
        "offset": 0.01,
    },
    "transients": {
        "color": (215, 240, 255, 240),
        "alpha": 0.66,
        "power": 1.15,
        "offset": 0.0,
    },
}
_DEVCURVE_DEFAULT_NODES = (
    (0.0, 0.58),
    (0.35, 0.64),
    (0.70, 0.52),
    (1.0, 0.60),
)


def _devcurve_parameter_snapshot(widget: Any) -> dict[str, object]:
    """Detach one coherent DevCurve tuning/style input for the logical step."""

    values: dict[str, object] = {
        "devcurve_base_level": float(
            getattr(widget, "_devcurve_base_level", 0.58)
        ),
        "devcurve_motion_power": float(
            getattr(widget, "_devcurve_motion_power", 1.0)
        ),
        "devcurve_idle_motion": float(
            getattr(widget, "_devcurve_idle_motion", 0.20)
        ),
        "devcurve_idle_speed": float(
            getattr(widget, "_devcurve_idle_speed", 0.60)
        ),
        "devcurve_smoothness": float(
            getattr(widget, "_devcurve_smoothness", 0.55)
        ),
        "devcurve_ghosting_enabled": bool(
            getattr(widget, "_devcurve_ghosting_enabled", False)
        ),
        "devcurve_ghost_alpha": float(
            getattr(widget, "_devcurve_ghost_alpha", 0.0)
        ),
        "devcurve_ghost_decay": float(
            getattr(widget, "_devcurve_ghost_decay", 0.4)
        ),
        "devcurve_foreground_shadow_enabled": bool(
            getattr(widget, "_devcurve_foreground_shadow_enabled", False)
        ),
        "devcurve_foreground_shadow_alpha": float(
            getattr(widget, "_devcurve_foreground_shadow_alpha", 0.36)
        ),
        "devcurve_foreground_shadow_darken": float(
            getattr(widget, "_devcurve_foreground_shadow_darken", 0.42)
        ),
        "devcurve_foreground_shadow_offset": float(
            getattr(widget, "_devcurve_foreground_shadow_offset", 0.10)
        ),
        "devcurve_foreground_specular_enabled": bool(
            getattr(widget, "_devcurve_foreground_specular_enabled", False)
        ),
        "devcurve_foreground_specular_alpha": float(
            getattr(widget, "_devcurve_foreground_specular_alpha", 0.78)
        ),
        "devcurve_foreground_specular_width": float(
            getattr(widget, "_devcurve_foreground_specular_width", 0.022)
        ),
        "devcurve_foreground_specular_offset": float(
            getattr(widget, "_devcurve_foreground_specular_offset", 0.028)
        ),
        "devcurve_foreground_specular_crest_bias": float(
            getattr(widget, "_devcurve_foreground_specular_crest_bias", 1.05)
        ),
        "rainbow_enabled": bool(getattr(widget, "_rainbow_enabled", False)),
        "rainbow_speed": float(getattr(widget, "_rainbow_speed", 0.5)),
    }
    for index, name in enumerate(_DEVCURVE_LAYERS):
        defaults = _DEVCURVE_LAYER_DEFAULTS[name]
        prefix = f"devcurve_layer_{name}"
        values.update(
            {
                f"{prefix}_enabled": bool(
                    getattr(widget, f"_{prefix}_enabled", True)
                ),
                f"{prefix}_color": getattr(
                    widget,
                    f"_{prefix}_color",
                    defaults["color"],
                ),
                f"{prefix}_alpha": float(
                    getattr(widget, f"_{prefix}_alpha", defaults["alpha"])
                ),
                f"{prefix}_power": float(
                    getattr(widget, f"_{prefix}_power", defaults["power"])
                ),
                f"{prefix}_offset": float(
                    getattr(widget, f"_{prefix}_offset", defaults["offset"])
                ),
                f"{prefix}_outline_color": getattr(
                    widget,
                    f"_{prefix}_outline_color",
                    (255, 255, 255, 255),
                ),
                f"{prefix}_outline_width": float(
                    getattr(widget, f"_{prefix}_outline_width", 0.006)
                ),
                f"{prefix}_order": int(
                    getattr(widget, f"_{prefix}_order", index + 1)
                ),
            }
        )
    return values


def _devcurve_energy(value: object) -> VisualizerEnergyState:
    return VisualizerEnergyState(
        bass=float(getattr(value, "bass", 0.0) if value is not None else 0.0),
        mid=float(getattr(value, "mid", 0.0) if value is not None else 0.0),
        high=float(getattr(value, "high", 0.0) if value is not None else 0.0),
        overall=float(
            getattr(value, "overall", 0.0) if value is not None else 0.0
        ),
    )


def _devcurve_transient(value: object) -> VisualizerTransientState:
    return VisualizerTransientState(
        bass=float(
            getattr(value, "bass_transient", 0.0)
            if value is not None
            else 0.0
        ),
        mid=float(
            getattr(value, "mid_transient", 0.0)
            if value is not None
            else 0.0
        ),
        high=float(
            getattr(value, "high_transient", 0.0)
            if value is not None
            else 0.0
        ),
        onset_detected=bool(
            getattr(value, "onset_detected", False)
            if value is not None
            else False
        ),
        onset_type=str(
            getattr(value, "onset_type", "") if value is not None else ""
        ),
        onset_strength=float(
            getattr(value, "onset_strength", 0.0)
            if value is not None
            else 0.0
        ),
    )


def dispatch_devcurve_field(widget: Any, now_ts: float) -> None:
    """Advance one DevCurve step on the sole authored logical clock."""

    if widget._vis_mode_str != "devcurve":
        return
    controller = getattr(widget, "runtime_controller", None)
    if controller is None:
        raise RuntimeError("DevCurve logical step requires its runtime controller")

    from widgets.spotify_visualizer.devcurve_frame_runtime import (
        DevCurveFrameRuntime,
    )

    try:
        runtime = controller.resolve_logical_mode_state(
            "devcurve",
            DevCurveFrameRuntime,
        )
    except ValueError:
        if controller.mode_id != "devcurve" or widget._vis_mode_str != "devcurve":
            return
        raise
    if not isinstance(runtime, DevCurveFrameRuntime):
        raise TypeError("DevCurve logical mode state has the wrong type")

    engine = widget._engine
    energy_input = None
    transient_input = None
    engine_generation = -1
    engine_activation = -1
    source_generation = -1
    source_activation = -1
    source_timestamp = 0.0
    if engine is not None:
        try:
            engine_generation = coerce_identity(engine.get_generation_id())
            engine_activation = coerce_identity(engine.get_activation_id())
        except Exception:
            pass
        try:
            energy_input = engine.get_energy_bands()
            transient_input = engine.get_transient_energy_bands()
        except Exception:
            energy_input = None
            transient_input = None
        try:
            (
                raw_source_timestamp,
                raw_source_generation,
                raw_source_activation,
            ) = engine.get_latest_authoritative_frame()
            source_timestamp = float(raw_source_timestamp)
            source_generation = coerce_identity(raw_source_generation)
            source_activation = coerce_identity(raw_source_activation)
        except Exception:
            source_timestamp = 0.0

    resolved_input_energy = _devcurve_energy(energy_input)
    resolved_input_transient = _devcurve_transient(transient_input)
    parameters = _devcurve_parameter_snapshot(widget)
    layer_shape_nodes = {
        name: list(
            getattr(
                widget,
                f"_devcurve_layer_{name}_shape_nodes",
                _DEVCURVE_DEFAULT_NODES,
            )
        )
        for name in _DEVCURVE_LAYERS
    }
    try:
        resolved = runtime.advance(
            now_ts=now_ts,
            runtime_generation=coerce_identity(
                getattr(widget, "_runtime_generation", None)
            ),
            engine_generation=engine_generation,
            activation_id=engine_activation,
            source_generation=source_generation,
            source_activation_id=source_activation,
            source_timestamp=source_timestamp,
            playing=bool(widget._spotify_playing),
            energy=resolved_input_energy,
            transient=resolved_input_transient,
            layer_shape_nodes=layer_shape_nodes,
            parameters=parameters,
        )
    except Exception:
        logger.exception("[SPOTIFY_VIS][DEVCURVE] logical integration failed")
        return
    if resolved is None:
        return
    if controller.mode_id != "devcurve" or widget._vis_mode_str != "devcurve":
        return
    if is_viz_diagnostics_enabled():
        maybe_log_reactivity_boundary(
            widget,
            logger,
            now_ts=now_ts,
            mode="devcurve",
            playing=bool(widget._spotify_playing),
            source_ready=resolved.reactive_source_ready,
            runtime_generation=coerce_identity(
                getattr(widget, "_runtime_generation", None)
            ),
            engine_generation=engine_generation,
            engine_activation=engine_activation,
            source_generation=source_generation,
            source_activation=source_activation,
            source_timestamp=source_timestamp,
            input_energy=resolved_input_energy,
            resolved_energy=resolved.energy,
            event_summary=(
                f"bass_transient={resolved_input_transient.bass:.3f}"
            ),
        )
        # Historical DevCurve intentionally maps its transient layer from the
        # bass-transient lane only.  Mid/high activity is useful source context,
        # but must not trigger a diagnostic that claims the authored transient
        # layer failed when its actual input was zero.
        raw_transient = resolved_input_transient.bass
        last_transient_diag = float(
            getattr(widget, "_devcurve_transient_diag_last_ts", 0.0) or 0.0
        )
        if raw_transient >= 0.025 and now_ts - last_transient_diag >= 0.12:
            energies = resolved.diagnostics.get("energies", {})
            transient_curve = dict(resolved.curves).get("transients", ())
            curve_span = (
                max(transient_curve) - min(transient_curve)
                if transient_curve
                else 0.0
            )
            logger.debug(
                "[VIS_DEVCURVE_TRANSIENT] raw_b=%.3f raw_m=%.3f raw_h=%.3f "
                "smooth_t=%.3f curve_span=%.4f ready=%s",
                resolved_input_transient.bass,
                resolved_input_transient.mid,
                resolved_input_transient.high,
                float(energies.get("transients", 0.0)),
                float(curve_span),
                resolved.reactive_source_ready,
            )
            widget._devcurve_transient_diag_last_ts = now_ts

    # Temporary old-presenter mirror. The controller-owned immutable result is
    # authoritative; the Quick renderer never reads these widget fields.
    curve_map = dict(resolved.curves)
    widget._devcurve_sample_count = int(
        resolved.parameters.get("devcurve_sample_count", 0)
    )
    for name in _DEVCURVE_LAYERS:
        setattr(widget, f"_devcurve_curve_{name}", list(curve_map.get(name, ())))
    widget._devcurve_draw_order = list(resolved.draw_order)
    widget._devcurve_foreground_layer = resolved.foreground_layer
    widget._devcurve_foreground_layer_id = resolved.foreground_layer_id
    slots = list(resolved.specular_slots)
    while len(slots) < 3:
        slots.append((0.0, 0.0, 0.0, 0.0))
    for index, slot in enumerate(slots[:3]):
        setattr(widget, f"_devcurve_specular_slot{index}", list(slot))

    diagnostics = resolved.diagnostics
    widget._devcurve_smoothness_max_step = float(
        diagnostics.get("smoothness_max_step", 0.0)
    )
    widget._devcurve_active_amplitude = float(
        diagnostics.get("active_amplitude", 0.0)
    )
    widget._devcurve_idle_amplitude = float(
        diagnostics.get("idle_amplitude", 0.0)
    )
    widget._devcurve_foreground_travel_rate = float(
        diagnostics.get("foreground_travel_rate", 0.0)
    )
    widget._devcurve_foreground_travel_pos = float(
        diagnostics.get("foreground_travel_pos", 0.0)
    )
    widget._devcurve_specular_travel_rate = float(
        diagnostics.get("specular_travel_rate", 0.0)
    )
    widget._devcurve_specular_activity_alpha = float(
        resolved.parameters.get("devcurve_specular_activity_alpha", 0.0)
    )

    if is_viz_diagnostics_enabled() and logger.isEnabledFor(logging.DEBUG):
        last_diag = float(
            getattr(widget, "_devcurve_diag_last_log_ts", 0.0) or 0.0
        )
        if now_ts - last_diag >= 0.80:
            energies = diagnostics.get("energies", {})
            logger.debug(
                (
                    "[SPOTIFY_VIS][DEVCURVE] mode=layered idle_amp=%.4f "
                    "active_amp=%.4f smooth_step=%.5f fg=%s "
                    "E[b=%.3f v=%.3f m=%.3f t=%.3f] fg_rate=%.4f "
                    "fg_pos=%.3f spec_rate=%.4f S[x=%.3f/%.3f/%.3f]"
                ),
                widget._devcurve_idle_amplitude,
                widget._devcurve_active_amplitude,
                widget._devcurve_smoothness_max_step,
                resolved.foreground_layer,
                float(energies.get("bass", 0.0)),
                float(energies.get("vocals", 0.0)),
                float(energies.get("mids", 0.0)),
                float(energies.get("transients", 0.0)),
                widget._devcurve_foreground_travel_rate,
                widget._devcurve_foreground_travel_pos,
                widget._devcurve_specular_travel_rate,
                float(slots[0][0]),
                float(slots[1][0]),
                float(slots[2][0]),
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
        "bubble_ghosting_enabled": getattr(widget, "_bubble_ghosting_enabled", False),
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
    # Latest committed CUSTOM viewport extent (baseline default until a retained
    # edge drag publishes a wide/tall world). Read as configuration only; it never
    # ticks or gates the authored Bubble step.
    viewport_extent = None
    try:
        viewport_extent = controller.presentation_viewport_extent
    except Exception:
        viewport_extent = None
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
            viewport_extent=viewport_extent,
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
    if is_viz_diagnostics_enabled():
        resolved_energy = (
            energy_payload
            if source_ready
            else {"overall": 0.0, "bass": 0.0, "mid": 0.0, "high": 0.0}
        )
        maybe_log_reactivity_boundary(
            widget,
            logger,
            now_ts=now_ts,
            mode="bubble",
            playing=bool(widget._spotify_playing),
            source_ready=source_ready,
            runtime_generation=coerce_identity(
                getattr(widget, "_runtime_generation", None)
            ),
            engine_generation=engine_generation,
            engine_activation=engine_activation,
            source_generation=source_generation,
            source_activation=source_activation,
            source_timestamp=source_ts,
            input_energy=energy_payload,
            resolved_energy=resolved_energy,
            event_summary=(
                f"bass_pulse={pulse_payload.get('bass', 0.0):.3f},"
                f"mid_high={pulse_payload.get('mid_high', 0.0):.3f}"
            ),
        )
        geometry = dict(resolved.geometry_diagnostics)
        playing = bool(widget._spotify_playing)
        previous_playing = getattr(
            widget,
            "_bubble_geometry_diag_last_playing",
            None,
        )
        burst_remaining = int(
            getattr(widget, "_bubble_geometry_diag_burst_remaining", 0) or 0
        )
        if previous_playing is None or bool(previous_playing) != playing:
            burst_remaining = 8
        last_geometry_log_ts = float(
            getattr(widget, "_bubble_geometry_diag_last_log_ts", 0.0) or 0.0
        )
        motion_event_strength = geometry.get("motion_event_strength", 0.0)
        motion_event_sample_due = (
            motion_event_strength > 0.0
            and now_ts - last_geometry_log_ts >= 0.25
        )
        interval_s = 0.12 if burst_remaining > 0 else 0.8
        if (
            last_geometry_log_ts <= 0.0
            or now_ts - last_geometry_log_ts >= interval_s
            or motion_event_sample_due
            or (
                previous_playing is not None
                and bool(previous_playing) != playing
            )
        ):
            logger.debug(
                "[VIS_BUBBLE_GEOMETRY] stage=B6_B7 sim_ts=%.6f playing=%s "
                "ready=%s final_big_max_r=%.5f final_big_avg_r=%.5f "
                "final_big_delta=%.5f target_big_max_r=%.5f "
                "smooth_lag_max_r=%.5f frozen_big_max_r=%.5f "
                "frozen_any_max_r=%.5f alpha=%.3f "
                "domain=%.3fx%.3f raw=%.3f gated=%.3f pulse=%.3f "
                "clamp_hits=%.0f active=%.0f size=%.3f pulse_gain=%.3f "
                "smoothing=%.3f clamp=%.3f "
                "motion(event=%.3f envelope=%.3f burst=%.3f drift=%.3f "
                "stream_step=%.6f drift_step=%.6f) "
                "track(token=%.0f index=%.0f base=%.5f target=%.5f "
                "display=%.5f delta=%.5f step=%.5f rate_hz=%.3f mix=%.3f)",
                resolved.simulation_timestamp,
                playing,
                source_ready,
                geometry.get("final_big_max_radius", 0.0),
                geometry.get("final_big_avg_radius", 0.0),
                geometry.get("final_big_max_delta", 0.0),
                geometry.get("final_big_target_radius", 0.0),
                geometry.get("final_big_smoothing_lag", 0.0),
                geometry.get("frozen_big_max_radius", 0.0),
                geometry.get("frozen_any_max_radius", 0.0),
                geometry.get("frozen_max_alpha", 0.0),
                geometry.get("domain_w", 1.0),
                geometry.get("domain_h", 1.0),
                geometry.get("max_big_raw_src", 0.0),
                geometry.get("max_big_gated_energy", 0.0),
                geometry.get("max_big_pulse_after", 0.0),
                geometry.get("big_clamp_hits", 0.0),
                geometry.get("active_big_count", 0.0),
                geometry.get("configured_big_size_max", 0.0),
                geometry.get("configured_big_bass_pulse", 0.0),
                geometry.get("configured_big_visual_smoothing", 0.0),
                geometry.get("configured_big_size_clamp", 0.0),
                motion_event_strength,
                geometry.get("motion_transient_envelope", 0.0),
                geometry.get("stream_burst_speed", 0.0),
                geometry.get("transient_drift_drive", 0.0),
                geometry.get("stream_step_mean", 0.0),
                geometry.get("drift_step_mean", 0.0),
                geometry.get("tracked_big_token", 0.0),
                geometry.get("tracked_big_index", -1.0),
                geometry.get("tracked_big_base_radius", 0.0),
                geometry.get("tracked_big_target_radius", 0.0),
                geometry.get("tracked_big_display_radius", 0.0),
                geometry.get("tracked_big_target_delta", 0.0),
                geometry.get("tracked_big_smoothing_step", 0.0),
                geometry.get("tracked_big_smoothing_rate_hz", 0.0),
                geometry.get("tracked_big_smoothing_mix", 0.0),
            )
            widget._bubble_geometry_diag_last_log_ts = now_ts
            if burst_remaining > 0:
                burst_remaining -= 1
        widget._bubble_geometry_diag_burst_remaining = burst_remaining
        widget._bubble_geometry_diag_last_playing = playing

    # Compatibility mirror for logical-state consumers. The immutable
    # controller-owned result is authoritative; retained Quick does not read
    # these mutable mirror fields.
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









def _publish_logical_state(
    widget: Any,
    now_ts: float,
    *,
    changed: bool,
    mode_reveal_ready: bool,
    present_frame: bool = True,
    protected_edges: Sequence[VisualizerProtectedEdge] = (),
) -> Optional[VisualizerLogicalFrame]:
    """Publish one immutable logical result for retained Quick synchronization.

    Latest-wins: a presentation opportunity that cannot keep up loses freshness
    rather than accumulating a backlog, while authored simulation keeps its own
    cadence. A capture overtaken by mode replacement is an expected no-publication
    result.
    """

    from widgets.spotify_visualizer.logical_frame_capture import (
        capture_visualizer_logical_frame,
    )

    payload = capture_visualizer_logical_frame(
        widget,
        now_ts=now_ts,
        changed=changed,
        mode_reveal_ready=mode_reveal_ready,
        present_frame=present_frame,
        protected_edges=protected_edges,
    )
    if payload is None:
        return None
    mailbox = widget._logical_mailbox
    revision = mailbox.publish(
        payload,
        generation=payload.runtime_generation,
        activation_id=payload.activation_id,
        now_ts=payload.logical_timestamp,
    )
    if is_viz_diagnostics_enabled():
        maybe_log_logical_publication(
            widget,
            logger,
            now_ts=now_ts,
            logical=payload,
            revision=revision,
        )
    return payload


def logical_tick(widget: Any) -> Optional[VisualizerLogicalFrame]:
    """Advance authored logical state and publish the latest immutable frame.

    Safe to run off the GUI thread. It must not read presentation geometry,
    touch QPixmap/GL state, or perform any retained Quick scene mutation.
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
    # Preserve logical transition-readiness shape even when fresh-engine wait
    # short-circuits. Retained Quick owns the actual transition/reveal state.
    mode_reveal_ready = bool(widget._check_mode_teardown_ready(widget._engine, now_ts))
    _record_tick_phase("teardown_check")
    # If consume returned (False, False) while waiting for fresh engine frame, bail.
    #
    # A mode whose idle scene is presentation-owned is the exception: it needs no
    # source frame to produce its logical resting scene. The immutable capture
    # downstream builds that state, so returning here would make paused Spectrum
    # simultaneously say "my idle needs no source" and "do not publish my idle
    # until source arrives".
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
