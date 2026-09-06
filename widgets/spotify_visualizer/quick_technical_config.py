"""Presentation-neutral technical configuration for the Quick visualizer owner.

The mapping accepted here is already resolved by the canonical settings/preset
layer.  This consumer therefore validates/coerces constraints but never chooses
product defaults of its own.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.logging.logger import get_logger, is_viz_diagnostics_enabled

logger = get_logger(__name__)

_REQUIRED_SHARED_KEYS = frozenset(
    {
        "bar_count",
        "dynamic_floor",
        "manual_floor",
        "adaptive_sensitivity",
        "sensitivity",
        "audio_block_size",
        "dynamic_range_enabled",
        "agc_strength",
        "input_gain",
        "kick_lane_gain",
        "transient_pulse_gain",
        "transient_clamp",
        "spectrum_lane_transient_mix",
    }
)
_MODE_REQUIRED_KEYS = {
    "bubble": frozenset({"bubble_transient_mix_bass", "bubble_transient_mix_vocal"}),
    "sine_wave": frozenset({"sine_wave_transient_width_mix"}),
    "oscilloscope": frozenset({"oscilloscope_transient_width_mix"}),
}


def _clamp(value: object, minimum: float, maximum: float) -> float:
    resolved = float(value)
    return max(float(minimum), min(float(maximum), resolved))


def _energy_boost(enabled: bool) -> float:
    """Resolve the worker multiplier for the configured dynamic-range mode.

    These are algorithm semantics, not missing-setting fallbacks.
    """

    return 1.18 if enabled else 0.85


def _require_complete_config(controller: Any, config: Mapping[str, Any]) -> str:
    mode_id = str(getattr(controller, "mode_id", "")).strip().lower()
    missing = set(_REQUIRED_SHARED_KEYS)
    missing.update(_MODE_REQUIRED_KEYS.get(mode_id, ()))
    missing.difference_update(config.keys())
    if missing:
        raise KeyError(
            f"incomplete resolved visualizer technical config for {mode_id or 'unknown'}: "
            + ", ".join(sorted(missing))
        )
    return mode_id


def _apply_worker_only_technical(
    engine: Any,
    *,
    audio_block_size: int,
    kick_lane_gain: float,
    spectrum_lane_transient_mix: float,
    transient_clamp: float,
) -> None:
    worker = getattr(engine, "_audio_worker", None)
    if worker is None:
        raise RuntimeError("visualizer BeatEngine has no audio worker")

    set_block_size = getattr(worker, "set_audio_block_size", None)
    if not callable(set_block_size):
        raise RuntimeError("visualizer audio worker has no block-size authority")
    set_block_size(int(audio_block_size))

    set_transient_lane = getattr(engine, "set_transient_lane_config", None)
    if not callable(set_transient_lane):
        raise RuntimeError("visualizer BeatEngine has no transient-lane config authority")
    set_transient_lane(kick_lane_gain, spectrum_lane_transient_mix, transient_clamp)


def _resize_controller_logical_bar_state(controller: Any, target_bars: int) -> None:
    target = max(1, int(target_bars))
    if target == int(controller.bar_count):
        return

    engine = controller.ensure_engine()
    reconfigure = getattr(engine, "reconfigure_bar_count", None)
    if not callable(reconfigure):
        raise RuntimeError(
            "visualizer BeatEngine does not support presentation-neutral bar-count reconfiguration"
        )

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
    """Apply one complete, already-resolved mode technical mapping."""

    if not isinstance(config, Mapping):
        raise TypeError("visualizer technical config must be a mapping")
    mode_id = _require_complete_config(controller, config)

    engine = controller.ensure_engine()
    state = controller.logical_tick_state

    target_bars = max(1, int(config["bar_count"]))

    dynamic_floor = bool(config["dynamic_floor"])
    manual_floor = _clamp(config["manual_floor"], 0.0, 1.0)
    adaptive = bool(config["adaptive_sensitivity"])
    sensitivity = _clamp(config["sensitivity"], 0.25, 2.5)
    audio_block_size = max(0, int(config["audio_block_size"]))
    dynamic_range_enabled = bool(config["dynamic_range_enabled"])
    agc_strength = _clamp(config["agc_strength"], 0.0, 1.0)
    input_gain = _clamp(config["input_gain"], 0.05, 2.0)
    kick_lane_gain = _clamp(config["kick_lane_gain"], 0.0, 2.0)
    transient_pulse_gain = _clamp(config["transient_pulse_gain"], 0.0, 3.0)
    transient_clamp = _clamp(config["transient_clamp"], 0.0, 3.0)
    spectrum_lane_transient_mix = _clamp(
        config["spectrum_lane_transient_mix"], 0.0, 1.0
    )

    set_floor = getattr(engine, "set_floor_config", None)
    if not callable(set_floor):
        raise RuntimeError("visualizer BeatEngine has no floor-config authority")
    set_floor(dynamic_floor, manual_floor)

    set_sensitivity = getattr(engine, "set_sensitivity_config", None)
    if not callable(set_sensitivity):
        raise RuntimeError("visualizer BeatEngine has no sensitivity-config authority")
    set_sensitivity(adaptive, sensitivity)

    _resize_controller_logical_bar_state(controller, target_bars)

    set_energy = getattr(engine, "set_energy_boost", None)
    if not callable(set_energy):
        raise RuntimeError("visualizer BeatEngine has no energy-boost authority")
    set_energy(_energy_boost(dynamic_range_enabled))

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
        transient_clamp=transient_clamp,
    )

    if is_viz_diagnostics_enabled():
        logger.debug(
            "[VIS_TECH_CONFIG] mode=%s reason=%s bars=%d dynamic_floor=%s "
            "manual_floor=%.3f adaptive=%s sensitivity=%.3f block=%d "
            "dynamic_range=%s energy_boost=%.3f agc=%.3f input_gain=%.3f",
            mode_id or "unknown",
            str(reason),
            target_bars,
            dynamic_floor,
            manual_floor,
            adaptive,
            sensitivity,
            audio_block_size,
            dynamic_range_enabled,
            _energy_boost(dynamic_range_enabled),
            agc_strength,
            input_gain,
        )

    state._transient_pulse_gain = transient_pulse_gain
    state._transient_clamp = transient_clamp
    if mode_id == "bubble":
        state._bubble_transient_mix_bass = _clamp(
            config["bubble_transient_mix_bass"], 0.0, 1.0
        )
        state._bubble_transient_mix_vocal = _clamp(
            config["bubble_transient_mix_vocal"], 0.0, 1.0
        )
    elif mode_id == "sine_wave":
        state._sine_wave_transient_width_mix = _clamp(
            config["sine_wave_transient_width_mix"], 0.0, 1.0
        )
    elif mode_id == "oscilloscope":
        state._osc_transient_width_mix = _clamp(
            config["oscilloscope_transient_width_mix"], 0.0, 1.0
        )


__all__ = ["apply_controller_technical_config"]
