"""Build resolved per-mode technical configuration for the Quick visualizer.

This module is intentionally narrow.  Runtime application belongs to
``quick_technical_config`` and callers must pass a complete resolved mapping.
There is no QWidget-era technical fallback/ghost bridge here.
"""
from __future__ import annotations

from typing import Any, Dict

from core.settings.models import SpotifyVisualizerSettings
from core.settings.models._visualizer_helpers import PER_MODE_TECHNICAL_MODES


def build_technical_cache(
    widget: Any,
    model: SpotifyVisualizerSettings,
) -> Dict[str, Dict[str, Any]]:
    """Return the complete canonical/preset-resolved technical map per mode.

    ``widget`` is retained in the signature for call-site compatibility during
    the Qt Quick migration; it is deliberately unused.  Resolution failures are
    authority errors and propagate immediately rather than producing a partial
    cache that later invents values at the consumer.
    """

    cache: Dict[str, Dict[str, Any]] = {}
    spectrum_lane_transient_mix = model.resolve_spectrum_lane_transient_mix()
    for mode_key in PER_MODE_TECHNICAL_MODES:
        mode_config: Dict[str, Any] = {
            "bar_count": model.resolve_bar_count(mode_key),
            "dynamic_floor": model.resolve_dynamic_floor(mode_key),
            "manual_floor": model.resolve_manual_floor(mode_key),
            "adaptive_sensitivity": model.resolve_adaptive_sensitivity(mode_key),
            "sensitivity": model.resolve_sensitivity(mode_key),
            "audio_block_size": model.resolve_audio_block_size(mode_key),
            "dynamic_range_enabled": model.resolve_dynamic_range_enabled(mode_key),
            "agc_strength": model.resolve_agc_strength(mode_key),
            "input_gain": model.resolve_input_gain(mode_key),
            "kick_lane_gain": model.resolve_kick_lane_gain(mode_key),
            "transient_pulse_gain": model.resolve_transient_pulse_gain(mode_key),
            "transient_clamp": model.resolve_transient_clamp(mode_key),
            # The one shared BeatEngine always has a Spectrum transient lane.
            # Every mode therefore carries this resolved source value instead
            # of letting the worker own a second 0.65 baseline.
            "spectrum_lane_transient_mix": spectrum_lane_transient_mix,
        }
        if mode_key == "bubble":
            mode_config["bubble_transient_mix_bass"] = (
                model.resolve_bubble_transient_mix_bass()
            )
            mode_config["bubble_transient_mix_vocal"] = (
                model.resolve_bubble_transient_mix_vocal()
            )
        elif mode_key == "sine_wave":
            mode_config["sine_wave_transient_width_mix"] = (
                model.resolve_sine_wave_transient_width_mix()
            )
        elif mode_key == "oscilloscope":
            mode_config["oscilloscope_transient_width_mix"] = (
                model.resolve_oscilloscope_transient_width_mix()
            )
        cache[mode_key] = mode_config
    return cache


__all__ = ["build_technical_cache"]
