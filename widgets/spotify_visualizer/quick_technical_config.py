"""Presentation-neutral technical configuration for the Quick visualizer owner.

This is the destination counterpart of the legacy QWidget technical apply.  It
accepts an already-resolved per-mode technical mapping and applies each value to
its actual owner:

- BeatEngine / audio worker: capture + DSP technical configuration.
- VisualizerRuntimeController: bar-count authority.
- VisualizerLogicalTickState: values consumed by authored logical evolution.

It does not resolve SettingsManager/presets, touch QWidget geometry/GPU caches,
or mirror state into the legacy compositor overlay.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from widgets.spotify_visualizer.runtime_config import compute_energy_boost


def _clamp(value: object, minimum: float, maximum: float, default: float) -> float:
    try:
        resolved = float(value)
    except (TypeError, ValueError):
        resolved = float(default)
    return max(float(minimum), min(float(maximum), resolved))


def _apply_worker_only_technical(
    engine: Any,
    *,
    audio_block_size: int,
    kick_lane_gain: float,
    spectrum_lane_transient_mix: float,
) -> None:
    """Apply the few technical controls not exposed by BeatEngine forwarding APIs.

    The audio worker is part of the shared BeatEngine/source implementation, not
    presentation state.  Keeping this reach here prevents QWidget from remaining
    the technical-config authority.  If BeatEngine later grows public forwarding
    methods, this helper can switch to them without changing owner semantics.
    """

    worker = getattr(engine, "_audio_worker", None)
    if worker is None:
        return

    set_block_size = getattr(worker, "set_audio_block_size", None)
    if callable(set_block_size):
        set_block_size(int(audio_block_size))

    worker._kick_lane_gain = float(kick_lane_gain)
    worker._spectrum_lane_transient_mix = float(spectrum_lane_transient_mix)


def _resize_controller_logical_bar_state(controller: Any, target_bars: int) -> None:
    """Keep controller + authored logical mirror coherent after engine resize."""

    target = max(1, int(target_bars))
    if target == int(controller.bar_count):
        return

    engine = controller.ensure_engine()
    reconfigure = getattr(engine, "reconfigure_bar_count", None)
    if not callable(reconfigure):
        raise RuntimeError(
            "visualizer BeatEngine does not support presentation-neutral bar-count reconfiguration"
        )

    # Engine reconfiguration owns its generation/activation invalidation.  Only
    # after that succeeds do we commit the controller/logical mirror.
    reconfigure(target)
    controller.bar_count = target

    state = controller.logical_tick_state
    state._display_bars = [0.0] * target
    state._display_bars_source_generation = -1
    state._display_bars_source_activation = -1
    state._waiting_for_fresh_frame = True
    state._waiting_for_fresh_engine_frame = True


def apply_controller_technical_config(
    controller: Any,
    config: Mapping[str, Any],
    *,
    reason: str = "quick_owner_configure",
) -> None:
    """Apply one already-resolved mode technical mapping without a QWidget."""

    if not isinstance(config, Mapping):
        raise TypeError("visualizer technical config must be a mapping")

    engine = controller.ensure_engine()
    state = controller.logical_tick_state

    target_bars = max(1, int(config.get("bar_count", controller.bar_count)))
    _resize_controller_logical_bar_state(controller, target_bars)

    dynamic_floor = bool(config.get("dynamic_floor", True))
    manual_floor = _clamp(config.get("manual_floor", 0.12), 0.0, 1.0, 0.12)
    adaptive = bool(config.get("adaptive_sensitivity", True))
    sensitivity = _clamp(config.get("sensitivity", 1.0), 0.25, 2.5, 1.0)
    audio_block_size = max(0, int(config.get("audio_block_size", 0) or 0))
    dynamic_range_enabled = bool(config.get("dynamic_range_enabled", False))
    agc_strength = _clamp(config.get("agc_strength", 0.5), 0.0, 1.0, 0.5)
    input_gain = _clamp(config.get("input_gain", 1.0), 0.05, 2.0, 1.0)
    kick_lane_gain = _clamp(config.get("kick_lane_gain", 1.0), 0.0, 2.0, 1.0)
    transient_pulse_gain = _clamp(
        config.get("transient_pulse_gain", 1.0), 0.0, 3.0, 1.0
    )
    transient_clamp = _clamp(config.get("transient_clamp", 1.5), 0.0, 3.0, 1.5)
    spectrum_lane_transient_mix = _clamp(
        config.get("spectrum_lane_transient_mix", 0.65), 0.0, 1.0, 0.65
    )

    set_floor = getattr(engine, "set_floor_config", None)
    if not callable(set_floor):
        raise RuntimeError("visualizer BeatEngine has no floor-config authority")
    set_floor(dynamic_floor, manual_floor)

    set_sensitivity = getattr(engine, "set_sensitivity_config", None)
    if not callable(set_sensitivity):
        raise RuntimeError("visualizer BeatEngine has no sensitivity-config authority")
    set_sensitivity(adaptive, sensitivity)

    set_energy = getattr(engine, "set_energy_boost", None)
    if not callable(set_energy):
        raise RuntimeError("visualizer BeatEngine has no energy-boost authority")
    set_energy(compute_energy_boost(dynamic_range_enabled))

    set_agc = getattr(engine, "set_agc_strength", None)
    if not callable(set_agc):
        raise RuntimeError("visualizer BeatEngine has no AGC authority")
    set_agc(agc_strength)

    set_input = getattr(engine, "set_input_gain", None)
    if not callable(set_input):
        raise RuntimeError("visualizer BeatEngine has no input-gain authority")
    set_input(input_gain)

    _apply_worker_only_technical(
        engine,
        audio_block_size=audio_block_size,
        kick_lane_gain=kick_lane_gain,
        spectrum_lane_transient_mix=spectrum_lane_transient_mix,
    )

    # These originated in the "technical" settings section, but authored logical
    # evolution consumes them.  Consumer ownership therefore wins over UI naming.
    state._transient_pulse_gain = transient_pulse_gain
    state._transient_clamp = transient_clamp
    state._bubble_transient_mix_bass = _clamp(
        config.get("bubble_transient_mix_bass", 0.75), 0.0, 1.0, 0.75
    )
    state._bubble_transient_mix_vocal = _clamp(
        config.get("bubble_transient_mix_vocal", 0.25), 0.0, 1.0, 0.25
    )
    state._sine_wave_transient_width_mix = _clamp(
        config.get("sine_wave_transient_width_mix", 0.4), 0.0, 1.0, 0.4
    )
    state._osc_transient_width_mix = _clamp(
        config.get("oscilloscope_transient_width_mix", 0.35), 0.0, 1.0, 0.35
    )


__all__ = ["apply_controller_technical_config"]
