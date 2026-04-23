"""Shared visualizer settings contract helpers.

This module centralizes the baseline/per-mode fallback rules that were being
duplicated inside ``SpotifyVisualizerSettings.from_settings()`` and
``SpotifyVisualizerSettings.from_mapping()``. The goal is to keep sparse
settings reconstruction, SST-shaped mappings, and future per-mode key additions
on one shared resolution path.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Dict

from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS

_BASELINE_DEFAULTS: dict[str, Any] = {
    "bar_count": 32,
    "adaptive_sensitivity": True,
    "sensitivity": 1.0,
    "dynamic_floor": True,
    "manual_floor": 0.12,
    "dynamic_range_enabled": False,
    "agc_strength": 0.5,
    "input_gain": 1.0,
}

_PER_MODE_BASELINE_KEYS: tuple[tuple[str, Callable[[Any], Any]], ...] = (
    ("dynamic_floor", bool),
    ("manual_floor", float),
    ("dynamic_range_enabled", bool),
    ("agc_strength", float),
    ("input_gain", float),
    ("kick_lane_gain", float),
    ("transient_pulse_gain", float),
    ("transient_clamp", float),
    ("audio_block_size", int),
    ("adaptive_sensitivity", bool),
    ("sensitivity", float),
    ("bar_count", int),
)

_SPECIAL_PER_MODE_KEYS: tuple[tuple[str, str, str, Any, Callable[[Any], Any]], ...] = (
    ("spectrum", "lane_transient_mix", "spectrum_lane_transient_mix", 0.65, float),
    ("bubble", "transient_mix_bass", "bubble_transient_mix_bass", 0.75, float),
    ("bubble", "transient_mix_vocal", "bubble_transient_mix_vocal", 0.25, float),
    ("blob", "transient_mix_bass", "blob_transient_mix_bass", 0.5, float),
    ("blob", "transient_mix_vocal", "blob_transient_mix_vocal", 0.35, float),
    ("sine_wave", "transient_width_mix", "sine_wave_transient_width_mix", 0.4, float),
    ("oscilloscope", "transient_width_mix", "oscilloscope_transient_width_mix", 0.35, float),
)

_SPECTRUM_RENDER_MODE_ALIASES: dict[str, str] = {
    "segment": "segment",
    "segments": "segment",
    "segmented": "segment",
    "bars": "bars",
    "bar": "bars",
    "single_piece": "bars",
    "singlepiece": "bars",
    "solid": "bars",
    "curve": "curve",
    "spline": "curve",
    "well": "curve",
}


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def _coerce_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def normalize_spectrum_render_mode(value: Any, fallback: str = "bars") -> str:
    """Normalize authored/runtime Spectrum render-mode values."""
    normalized = str(value).strip().lower()
    if not normalized:
        return fallback
    return _SPECTRUM_RENDER_MODE_ALIASES.get(normalized, fallback)


def resolve_spectrum_render_mode(read_value: Callable[[str, Any], Any]) -> str:
    """Resolve canonical Spectrum render mode from new or legacy keys."""
    explicit = read_value("spectrum_render_mode", None)
    if explicit is not None:
        return normalize_spectrum_render_mode(explicit)

    legacy = read_value("spectrum_single_piece", None)
    if legacy is not None:
        return "bars" if _coerce_bool(legacy) else "segment"

    return "bars"


def resolve_spectrum_unique_colors(read_value: Callable[[str, Any], Any]) -> bool:
    """Resolve Spectrum unique-colour behavior from new or legacy keys."""
    explicit = read_value("spectrum_unique_colors", None)
    if explicit is not None:
        return _coerce_bool(explicit)

    legacy = read_value("spectrum_rainbow_per_bar", None)
    if legacy is not None:
        return _coerce_bool(legacy)

    global_legacy = read_value("rainbow_per_bar", None)
    if global_legacy is not None:
        return _coerce_bool(global_legacy)

    return True


def resolve_visualizer_baselines(read_value: Callable[[str, Any], Any]) -> dict[str, Any]:
    """Resolve the shared legacy baseline values for visualizer settings."""
    return {
        "bar_count": _coerce_int(read_value("bar_count", _BASELINE_DEFAULTS["bar_count"]), _BASELINE_DEFAULTS["bar_count"]),
        "adaptive_sensitivity": _coerce_bool(
            read_value("adaptive_sensitivity", _BASELINE_DEFAULTS["adaptive_sensitivity"])
        ),
        "sensitivity": _coerce_float(read_value("sensitivity", _BASELINE_DEFAULTS["sensitivity"]), _BASELINE_DEFAULTS["sensitivity"]),
        "dynamic_floor": _coerce_bool(read_value("dynamic_floor", _BASELINE_DEFAULTS["dynamic_floor"])),
        "manual_floor": _coerce_float(read_value("manual_floor", _BASELINE_DEFAULTS["manual_floor"]), _BASELINE_DEFAULTS["manual_floor"]),
        "dynamic_range_enabled": _coerce_bool(
            read_value("dynamic_range_enabled", _BASELINE_DEFAULTS["dynamic_range_enabled"])
        ),
        "agc_strength": _coerce_float(read_value("agc_strength", _BASELINE_DEFAULTS["agc_strength"]), _BASELINE_DEFAULTS["agc_strength"]),
        "input_gain": _coerce_float(read_value("input_gain", _BASELINE_DEFAULTS["input_gain"]), _BASELINE_DEFAULTS["input_gain"]),
    }


def build_visualizer_mode_kwargs(
    read_per_mode_value: Callable[[str, str, Any], Any],
    baselines: Mapping[str, Any],
) -> Dict[str, Any]:
    """Build the per-mode technical kwarg mapping from a shared resolver."""
    kwargs: Dict[str, Any] = {}
    for mode in VISUALIZER_MODE_IDS:
        for key, coerce in _PER_MODE_BASELINE_KEYS:
            fallback = baselines.get(key, _BASELINE_DEFAULTS.get(key))
            if key == "kick_lane_gain":
                fallback = 1.0
            elif key == "transient_pulse_gain":
                fallback = 1.0
            elif key == "transient_clamp":
                fallback = 1.5
            elif key == "audio_block_size":
                fallback = 0
            raw = read_per_mode_value(mode, key, fallback)
            if coerce is bool:
                kwargs[f"{mode}_{key}"] = _coerce_bool(raw)
            elif coerce is int:
                kwargs[f"{mode}_{key}"] = _coerce_int(raw, int(fallback))
            elif coerce is float:
                kwargs[f"{mode}_{key}"] = _coerce_float(raw, float(fallback))
            else:
                kwargs[f"{mode}_{key}"] = coerce(raw)

    for mode, key, output_key, fallback, coerce in _SPECIAL_PER_MODE_KEYS:
        raw = read_per_mode_value(mode, key, fallback)
        if coerce is bool:
            kwargs[output_key] = _coerce_bool(raw)
        elif coerce is int:
            kwargs[output_key] = _coerce_int(raw, int(fallback))
        elif coerce is float:
            kwargs[output_key] = _coerce_float(raw, float(fallback))
        else:
            kwargs[output_key] = coerce(raw)
    return kwargs


def resolve_visualizer_active_mode_rainbow_state(
    read_mode_value: Callable[[str, Any], Any],
) -> dict[str, Any]:
    """Resolve active-mode rainbow state through the same mode-scoped accessor."""
    return {
        "rainbow_enabled": _coerce_bool(read_mode_value("rainbow_enabled", False)),
        "rainbow_speed": _coerce_float(read_mode_value("rainbow_speed", 0.5), 0.5),
    }
