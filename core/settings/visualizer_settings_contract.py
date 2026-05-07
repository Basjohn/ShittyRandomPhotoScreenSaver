"""Shared visualizer settings contract helpers.

This module centralizes visualizer technical-key normalization so runtime
settings, SST-shaped mappings, and future per-mode key additions all converge
on one resolution path. Shared/global technical keys are legacy migration
inputs only; canonical runtime and persisted payloads are mode-owned.
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
    "kick_lane_gain": 1.0,
    "transient_pulse_gain": 1.0,
    "transient_clamp": 1.5,
    "audio_block_size": 0,
}

LEGACY_GLOBAL_TECHNICAL_KEYS: tuple[str, ...] = tuple(_BASELINE_DEFAULTS.keys())
LEGACY_GLOBAL_SHARED_VISUAL_KEYS: tuple[str, ...] = (
    "bar_fill_color",
    "bar_border_color",
    "bar_border_opacity",
    "ghosting_enabled",
    "ghost_alpha",
    "ghost_decay",
)

PER_MODE_BASELINE_KEYS: tuple[tuple[str, Callable[[Any], Any]], ...] = (
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

SPECIAL_PER_MODE_KEYS: tuple[tuple[str, str, str, Any, Callable[[Any], Any]], ...] = (
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
    """Resolve legacy shared technical values for visualizer migration only."""
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
        "kick_lane_gain": _coerce_float(read_value("kick_lane_gain", _BASELINE_DEFAULTS["kick_lane_gain"]), _BASELINE_DEFAULTS["kick_lane_gain"]),
        "transient_pulse_gain": _coerce_float(
            read_value("transient_pulse_gain", _BASELINE_DEFAULTS["transient_pulse_gain"]),
            _BASELINE_DEFAULTS["transient_pulse_gain"],
        ),
        "transient_clamp": _coerce_float(
            read_value("transient_clamp", _BASELINE_DEFAULTS["transient_clamp"]),
            _BASELINE_DEFAULTS["transient_clamp"],
        ),
        "audio_block_size": _coerce_int(
            read_value("audio_block_size", _BASELINE_DEFAULTS["audio_block_size"]),
            _BASELINE_DEFAULTS["audio_block_size"],
        ),
    }


def build_visualizer_mode_kwargs(
    read_per_mode_value: Callable[[str, str, Any], Any],
    baselines: Mapping[str, Any],
) -> Dict[str, Any]:
    """Build per-mode technical kwargs, using legacy shared values only as sparse migration fallback."""
    kwargs: Dict[str, Any] = {}
    for mode in VISUALIZER_MODE_IDS:
        for key, coerce in PER_MODE_BASELINE_KEYS:
            fallback = baselines.get(key, _BASELINE_DEFAULTS.get(key))
            raw = read_per_mode_value(mode, key, fallback)
            if coerce is bool:
                kwargs[f"{mode}_{key}"] = _coerce_bool(raw)
            elif coerce is int:
                kwargs[f"{mode}_{key}"] = _coerce_int(raw, int(fallback))
            elif coerce is float:
                kwargs[f"{mode}_{key}"] = _coerce_float(raw, float(fallback))
            else:
                kwargs[f"{mode}_{key}"] = coerce(raw)

    for mode, key, output_key, fallback, coerce in SPECIAL_PER_MODE_KEYS:
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


def migrate_legacy_global_technical_keys(
    data: Mapping[str, Any] | None,
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> Dict[str, Any]:
    """Promote retired global technical keys into missing per-mode keys once.

    This helper is for normalization/repair/import flows only. Live runtime
    resolution must not read the legacy global keys after normalization.
    """
    if not isinstance(data, Mapping):
        return {}

    migrated = dict(data)
    scoped_prefix = f"{prefix}."
    shared_values: dict[str, Any] = {}

    for key in LEGACY_GLOBAL_TECHNICAL_KEYS:
        if key in migrated:
            shared_values[key] = migrated[key]
        dotted_key = f"{scoped_prefix}{key}"
        if dotted_key in migrated and key not in shared_values:
            shared_values[key] = migrated[dotted_key]

    if not shared_values:
        return migrated

    for mode in VISUALIZER_MODE_IDS:
        for key, _coerce in PER_MODE_BASELINE_KEYS:
            if key not in shared_values:
                continue
            plain_mode_key = f"{mode}_{key}"
            dotted_mode_key = f"{scoped_prefix}{plain_mode_key}"
            if plain_mode_key in migrated or dotted_mode_key in migrated:
                continue
            migrated[plain_mode_key] = shared_values[key]

    for key in LEGACY_GLOBAL_TECHNICAL_KEYS:
        migrated.pop(key, None)
        migrated.pop(f"{scoped_prefix}{key}", None)

    return migrated


def migrate_legacy_global_visual_keys(
    data: Mapping[str, Any] | None,
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> Dict[str, Any]:
    """Promote retired shared visual keys into canonical mode-owned keys once.

    Runtime/persistence should no longer depend on shared preset-varying visual
    state such as bar colors or legacy ghost fields. This helper upgrades old
    payloads during normalization/repair and then drops the shared authored form.
    """
    if not isinstance(data, Mapping):
        return {}

    migrated = dict(data)
    scoped_prefix = f"{prefix}."

    shared_values: dict[str, Any] = {}
    for key in LEGACY_GLOBAL_SHARED_VISUAL_KEYS:
        if key in migrated:
            shared_values[key] = migrated[key]
        dotted_key = f"{scoped_prefix}{key}"
        if dotted_key in migrated and key not in shared_values:
            shared_values[key] = migrated[dotted_key]

    if not shared_values:
        return migrated

    for mode in VISUALIZER_MODE_IDS:
        if "bar_fill_color" in shared_values:
            mode_key = f"{mode}_bar_fill_color"
            dotted_mode_key = f"{scoped_prefix}{mode_key}"
            if mode_key not in migrated and dotted_mode_key not in migrated:
                migrated[mode_key] = shared_values["bar_fill_color"]
        if "bar_border_color" in shared_values:
            mode_key = f"{mode}_bar_border_color"
            dotted_mode_key = f"{scoped_prefix}{mode_key}"
            if mode_key not in migrated and dotted_mode_key not in migrated:
                migrated[mode_key] = shared_values["bar_border_color"]
        if "bar_border_opacity" in shared_values:
            mode_key = f"{mode}_bar_border_opacity"
            dotted_mode_key = f"{scoped_prefix}{mode_key}"
            if mode_key not in migrated and dotted_mode_key not in migrated:
                migrated[mode_key] = shared_values["bar_border_opacity"]

    ghost_mode_key_map = {
        "spectrum": ("spectrum_ghosting_enabled", "spectrum_ghost_alpha", "spectrum_ghost_decay"),
        "blob": ("blob_ghosting_enabled", "blob_ghost_alpha", "blob_ghost_decay"),
        "bubble": ("bubble_ghosting_enabled", "bubble_ghost_alpha", "bubble_ghost_decay"),
        "sine_wave": ("sine_ghosting_enabled", "sine_ghost_alpha", "sine_ghost_decay"),
        "devcurve": ("devcurve_ghosting_enabled", "devcurve_ghost_alpha", "devcurve_ghost_decay"),
    }
    for _mode, (enabled_key, alpha_key, decay_key) in ghost_mode_key_map.items():
        if "ghosting_enabled" in shared_values:
            dotted = f"{scoped_prefix}{enabled_key}"
            if enabled_key not in migrated and dotted not in migrated:
                migrated[enabled_key] = shared_values["ghosting_enabled"]
        if "ghost_alpha" in shared_values:
            dotted = f"{scoped_prefix}{alpha_key}"
            if alpha_key not in migrated and dotted not in migrated:
                migrated[alpha_key] = shared_values["ghost_alpha"]
        if "ghost_decay" in shared_values:
            dotted = f"{scoped_prefix}{decay_key}"
            if decay_key not in migrated and dotted not in migrated:
                migrated[decay_key] = shared_values["ghost_decay"]

    for key in LEGACY_GLOBAL_SHARED_VISUAL_KEYS:
        migrated.pop(key, None)
        migrated.pop(f"{scoped_prefix}{key}", None)

    return migrated


def resolve_visualizer_active_mode_rainbow_state(
    read_mode_value: Callable[[str, Any], Any],
) -> dict[str, Any]:
    """Resolve active-mode rainbow state through the same mode-scoped accessor."""
    return {
        "rainbow_enabled": _coerce_bool(read_mode_value("rainbow_enabled", False)),
        "rainbow_speed": _coerce_float(read_mode_value("rainbow_speed", 0.5), 0.5),
    }
