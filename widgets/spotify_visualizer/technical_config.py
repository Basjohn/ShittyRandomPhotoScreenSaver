"""Technical-config cache and engine-application helpers for Spotify visualizer.

Extracted to reduce the main widget coordinator while preserving the existing
runtime/application contract.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.logging.logger import get_logger
from core.settings.models import SpotifyVisualizerSettings
from core.settings.models._visualizer_helpers import PER_MODE_TECHNICAL_MODES
from widgets.spotify_visualizer.audio_worker import VisualizerMode

logger = get_logger(__name__)


def map_mode_key_to_enum(mode_key: str) -> VisualizerMode:
    return {
        "spectrum": VisualizerMode.SPECTRUM,
        "oscilloscope": VisualizerMode.OSCILLOSCOPE,
        "blob": VisualizerMode.BLOB,
        "sine_wave": VisualizerMode.SINE_WAVE,
        "bubble": VisualizerMode.BUBBLE,
        "devcurve": VisualizerMode.DEVCURVE,
    }.get(str(mode_key).lower(), VisualizerMode.SPECTRUM)


def extract_technical_config_from_kwargs(
    widget: Any,
    mode_key: str,
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    extracted: Dict[str, Any] = {}
    shared_keys = (
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
    )
    mode_specific_keys = {
        "spectrum": ("spectrum_lane_transient_mix",),
        "bubble": ("bubble_transient_mix_bass", "bubble_transient_mix_vocal"),
        "blob": ("blob_transient_mix_bass", "blob_transient_mix_vocal"),
        "sine_wave": ("sine_wave_transient_width_mix",),
        "oscilloscope": ("oscilloscope_transient_width_mix",),
    }.get(mode_key, ())

    for key in shared_keys:
        prefixed_key = f"{mode_key}_{key}"
        if prefixed_key in kwargs:
            extracted[key] = kwargs[prefixed_key]
        elif key in kwargs:
            extracted[key] = kwargs[key]

    for key in mode_specific_keys:
        if key in kwargs:
            extracted[key] = kwargs[key]

    return extracted


def replace_runtime_technical_overrides(
    widget: Any,
    mode_key: str,
    kwargs: Dict[str, Any],
) -> bool:
    overrides = extract_technical_config_from_kwargs(widget, mode_key, kwargs)
    if not overrides:
        return False
    current: Dict[str, Any] = {}
    if widget._settings_model is not None:
        try:
            current = build_technical_cache(widget, widget._settings_model).get(mode_key, {})
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to rebuild technical cache for mode=%s", mode_key, exc_info=True)
    if not current:
        current = dict(widget._technical_config_cache.get(mode_key, {}))
    current.update(overrides)
    widget._technical_config_cache[mode_key] = current
    return True


def sync_active_mode_legacy_ghost_bridge(widget: Any, mode: VisualizerMode) -> None:
    """Keep the legacy shared ghost bridge aligned with the active mode."""
    mode_key = mode.name.lower()
    if mode_key == "spectrum":
        widget._ghosting_enabled = bool(widget._spectrum_ghosting_enabled)
        widget._ghost_alpha = float(widget._spectrum_ghost_alpha)
        widget._ghost_decay_rate = float(widget._spectrum_ghost_decay)
    elif mode_key == "blob":
        widget._ghosting_enabled = bool(widget._blob_ghosting_enabled)
        widget._ghost_alpha = float(widget._blob_ghost_alpha)
        widget._ghost_decay_rate = float(widget._blob_ghost_decay)
    elif mode_key == "sine_wave":
        widget._ghosting_enabled = bool(widget._sine_ghosting_enabled)
        widget._ghost_alpha = float(widget._sine_ghost_alpha)
        widget._ghost_decay_rate = float(widget._sine_ghost_decay)
    elif mode_key == "bubble":
        widget._ghosting_enabled = bool(widget._bubble_ghosting_enabled)
        widget._ghost_alpha = float(widget._bubble_ghost_alpha)
        widget._ghost_decay_rate = float(widget._bubble_ghost_decay)
    elif mode_key == "devcurve":
        widget._ghosting_enabled = bool(widget._devcurve_ghosting_enabled)
        widget._ghost_alpha = float(widget._devcurve_ghost_alpha)
        widget._ghost_decay_rate = float(widget._devcurve_ghost_decay)
    elif mode_key == "oscilloscope":
        widget._ghosting_enabled = bool(widget._osc_ghosting_enabled)
        widget._ghost_alpha = float(widget._osc_ghost_intensity)
        widget._ghost_decay_rate = float(getattr(widget, "_peak_decay_per_sec", 0.4))


def build_technical_cache(widget: Any, model: SpotifyVisualizerSettings) -> Dict[str, Dict[str, Any]]:
    cache: Dict[str, Dict[str, Any]] = {}
    for mode_key in PER_MODE_TECHNICAL_MODES:
        try:
            cache[mode_key] = {
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
            }
            if mode_key == "spectrum":
                cache[mode_key]["spectrum_lane_transient_mix"] = model.resolve_spectrum_lane_transient_mix()
            elif mode_key == "bubble":
                cache[mode_key]["bubble_transient_mix_bass"] = model.resolve_bubble_transient_mix_bass()
                cache[mode_key]["bubble_transient_mix_vocal"] = model.resolve_bubble_transient_mix_vocal()
            elif mode_key == "blob":
                cache[mode_key]["blob_transient_mix_bass"] = model.resolve_blob_transient_mix_bass()
                cache[mode_key]["blob_transient_mix_vocal"] = model.resolve_blob_transient_mix_vocal()
            elif mode_key == "sine_wave":
                cache[mode_key]["sine_wave_transient_width_mix"] = model.resolve_sine_wave_transient_width_mix()
            elif mode_key == "oscilloscope":
                cache[mode_key]["oscilloscope_transient_width_mix"] = model.resolve_oscilloscope_transient_width_mix()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to cache technical config for mode=%s", mode_key, exc_info=True)
    return cache


def get_mode_technical_config(widget: Any, mode: VisualizerMode) -> Optional[Dict[str, Any]]:
    if not widget._technical_config_cache:
        return None
    mode_key = mode.name.lower()
    return widget._technical_config_cache.get(mode_key)


def apply_technical_config_for_mode(widget: Any, mode: VisualizerMode, *, reason: str) -> None:
    config = get_mode_technical_config(widget, mode)
    if config is None:
        return
    try:
        target_bars = int(config.get("bar_count", widget._bar_count))
    except Exception:
        target_bars = widget._bar_count
    if target_bars != widget._bar_count:
        widget._resize_bar_buffers(target_bars)

    dynamic_floor = bool(config.get("dynamic_floor", True))
    manual_floor = float(config.get("manual_floor", 0.12))
    adaptive = bool(config.get("adaptive_sensitivity", True))
    sensitivity = float(config.get("sensitivity", 1.0))
    audio_block_size = int(config.get("audio_block_size", 0) or 0)
    dynamic_range_enabled = bool(config.get("dynamic_range_enabled", False))
    energy_boost = widget._compute_energy_boost(dynamic_range_enabled)
    agc_strength = max(0.0, min(1.0, float(config.get("agc_strength", 0.5))))
    input_gain = max(0.05, min(2.0, float(config.get("input_gain", 1.0))))

    widget._use_raw_energy = False
    widget._kick_lane_gain = max(0.0, min(2.0, float(config.get("kick_lane_gain", 1.0))))
    widget._transient_pulse_gain = max(0.0, min(3.0, float(config.get("transient_pulse_gain", 1.0))))
    widget._transient_clamp = max(0.0, min(3.0, float(config.get("transient_clamp", 1.5))))
    widget._spectrum_lane_transient_mix = max(0.0, min(1.0, float(config.get("spectrum_lane_transient_mix", 0.65))))
    widget._bubble_transient_mix_bass = max(0.0, min(1.0, float(config.get("bubble_transient_mix_bass", 0.75))))
    widget._bubble_transient_mix_vocal = max(0.0, min(1.0, float(config.get("bubble_transient_mix_vocal", 0.25))))
    widget._blob_transient_mix_bass = max(0.0, min(1.0, float(config.get("blob_transient_mix_bass", 0.5))))
    widget._blob_transient_mix_vocal = max(0.0, min(1.0, float(config.get("blob_transient_mix_vocal", 0.35))))
    widget._sine_wave_transient_width_mix = max(0.0, min(1.0, float(config.get("sine_wave_transient_width_mix", 0.4))))
    widget._osc_transient_width_mix = max(0.0, min(1.0, float(config.get("oscilloscope_transient_width_mix", 0.35))))
    widget.apply_floor_config(dynamic_floor, manual_floor)
    widget.apply_sensitivity_config(adaptive, sensitivity)
    widget._apply_audio_block_size(audio_block_size)
    widget._apply_energy_boost(energy_boost)
    widget._apply_agc_strength(agc_strength)
    widget._apply_input_gain(input_gain)
    if widget._engine is not None:
        aw = getattr(widget._engine, "_audio_worker", None)
        if aw is not None:
            aw._kick_lane_gain = widget._kick_lane_gain
            aw._spectrum_lane_transient_mix = widget._spectrum_lane_transient_mix
    parent = widget.parent()
    overlay = getattr(parent, "_spotify_bars_overlay", None) if parent else None
    if overlay is not None:
        overlay._blob_transient_mix_bass = widget._blob_transient_mix_bass
        overlay._blob_transient_mix_vocal = widget._blob_transient_mix_vocal
        overlay._transient_clamp = widget._transient_clamp
        overlay._sine_wave_transient_width_mix = widget._sine_wave_transient_width_mix
        overlay._osc_transient_width_mix = widget._osc_transient_width_mix

    try:
        from core.logging.logger import is_viz_diagnostics_enabled

        if is_viz_diagnostics_enabled():
            logger.info(
                "[SPOTIFY_VIS][TECHNICAL] mode=%s reason=%s bar_count=%d dyn_floor=%s manual_floor=%.2f adaptive=%s sensitivity=%.2f block=%d dyn_range=%s energy_boost=%.2f",
                mode.name,
                reason,
                widget._bar_count,
                dynamic_floor,
                manual_floor,
                adaptive,
                sensitivity,
                audio_block_size,
                dynamic_range_enabled,
                energy_boost,
            )
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to log technical config", exc_info=True)
