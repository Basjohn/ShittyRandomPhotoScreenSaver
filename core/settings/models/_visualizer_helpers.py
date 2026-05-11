"""Visualizer helper functions and constants used by SpotifyVisualizerSettings."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Tuple, TYPE_CHECKING

from core.settings.visualizer_settings_contract import (
    PER_MODE_BASELINE_KEYS,
    SPECIAL_PER_MODE_KEYS,
)

if TYPE_CHECKING:
    from core.settings.models._spotify_visualizer import SpotifyVisualizerSettings



def _normalize_visualizer_direction(value: Any, default: str = "top") -> str:
    val = str(value).lower()
    valid = {
        "top", "bottom", "left", "right",
        "top_left", "top_right", "bottom_left", "bottom_right",
        "center_out", "center_out_reverse",
    }
    return val if val in valid else default


_SPECTRUM_LEGACY_NOTCHES_LINEAR = [[0.0, "Bass"], [0.25, "Low"], [0.50, "Mid"], [0.75, "Hi-Mid"], [1.0, "Treble"]]
_SPECTRUM_DEFAULT_NOTCHES_LINEAR = [[0.0, "Bass"], [0.24, "Low-Mid"], [0.46, "Vocal"], [0.72, "Hi-Mid"], [1.0, "Treble"]]
_SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED = {
    "Mid": 0.60,
    "Vocal": 0.64,
    "Low-Mid": 0.70,
    "Bass": 0.80,
}
_SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR = {
    "Bass": 0.80,
    "Low-Mid": 0.70,
    "Vocal": 0.64,
    "Hi-Mid": 0.80,
    "Treble": 1.00,
}


def _normalize_spectrum_linear_notches(value: Any) -> list[list]:
    """Promote old linear notch layouts into the explicit vocal-lane family."""
    if not isinstance(value, list) or len(value) < 2:
        return [list(n) for n in _SPECTRUM_DEFAULT_NOTCHES_LINEAR]

    try:
        normalized = [[float(x), str(label)] for x, label in value]
    except Exception:
        return [list(n) for n in _SPECTRUM_DEFAULT_NOTCHES_LINEAR]

    if len(normalized) == 5:
        labels = [str(label).strip().lower() for _, label in normalized]
        if labels == ["bass", "low", "mid", "hi-mid", "treble"]:
            if normalized == _SPECTRUM_LEGACY_NOTCHES_LINEAR:
                return [list(n) for n in _SPECTRUM_DEFAULT_NOTCHES_LINEAR]
            return [
                [float(normalized[0][0]), "Bass"],
                [float(normalized[1][0]), "Low-Mid"],
                [float(normalized[2][0]), "Vocal"],
                [float(normalized[3][0]), "Hi-Mid"],
                [float(normalized[4][0]), "Treble"],
            ]
        if labels == ["bass", "low-mid", "mid", "hi-mid", "treble"]:
            return [
                [float(normalized[0][0]), "Bass"],
                [float(normalized[1][0]), "Low-Mid"],
                [float(normalized[2][0]), "Vocal"],
                [float(normalized[3][0]), "Hi-Mid"],
                [float(normalized[4][0]), "Treble"],
            ]

    return normalized


def _clamp_lane_strength(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return float(default)


def _normalize_spectrum_lane_strengths(value: Any, defaults: Mapping[str, float]) -> Dict[str, float]:
    if not isinstance(value, Mapping):
        return {label: float(default) for label, default in defaults.items()}
    normalized: Dict[str, float] = {}
    for label, default in defaults.items():
        normalized[label] = _clamp_lane_strength(value.get(label, default), default)
    return normalized


PER_MODE_TECHNICAL_MODES: Tuple[str, ...] = (
    "spectrum",
    "bubble",
    "blob",
    "sine_wave",
    "oscilloscope",
    "devcurve",
)

_ACTIVE_MODE_TECHNICAL_KEYS: Tuple[str, ...] = tuple(
    key for key, _coerce in PER_MODE_BASELINE_KEYS
)
_ACTIVE_MODE_SHARED_VISUAL_KEYS: Tuple[str, ...] = (
    "bar_fill_color",
    "bar_border_color",
    "bar_border_opacity",
)


def _coerce_live_visualizer_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def _coerce_live_visualizer_int(value: Any, default: int) -> int:
    try:
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _coerce_live_visualizer_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _build_live_visualizer_mode_kwargs(
    read_per_mode_value,
    default_model: "SpotifyVisualizerSettings",
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}

    for mode in PER_MODE_TECHNICAL_MODES:
        for key, coerce in PER_MODE_BASELINE_KEYS:
            fallback = getattr(default_model, f"{mode}_{key}")
            raw = read_per_mode_value(mode, key, fallback)
            if coerce is bool:
                kwargs[f"{mode}_{key}"] = _coerce_live_visualizer_bool(raw, bool(fallback))
            elif coerce is int:
                kwargs[f"{mode}_{key}"] = _coerce_live_visualizer_int(raw, int(fallback))
            else:
                kwargs[f"{mode}_{key}"] = _coerce_live_visualizer_float(raw, float(fallback))

    for mode, key, output_key, _fallback_unused, coerce in SPECIAL_PER_MODE_KEYS:
        fallback = getattr(default_model, output_key)
        raw = read_per_mode_value(mode, key, fallback)
        if coerce is bool:
            kwargs[output_key] = _coerce_live_visualizer_bool(raw, bool(fallback))
        elif coerce is int:
            kwargs[output_key] = _coerce_live_visualizer_int(raw, int(fallback))
        else:
            kwargs[output_key] = _coerce_live_visualizer_float(raw, float(fallback))

    return kwargs


def _build_live_visualizer_mode_shared_visual_kwargs(
    read_per_mode_value,
    default_model: "SpotifyVisualizerSettings",
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}
    for mode in PER_MODE_TECHNICAL_MODES:
        kwargs[f"{mode}_bar_fill_color"] = deepcopy(
            read_per_mode_value(mode, "bar_fill_color", getattr(default_model, f"{mode}_bar_fill_color"))
        )
        kwargs[f"{mode}_bar_border_color"] = deepcopy(
            read_per_mode_value(mode, "bar_border_color", getattr(default_model, f"{mode}_bar_border_color"))
        )
        kwargs[f"{mode}_bar_border_opacity"] = _coerce_live_visualizer_float(
            read_per_mode_value(mode, "bar_border_opacity", getattr(default_model, f"{mode}_bar_border_opacity")),
            float(getattr(default_model, f"{mode}_bar_border_opacity")),
        )
    return kwargs


def _resolve_active_mode_technical_state(
    mode_key: str,
    per_mode_kwargs: Mapping[str, Any],
) -> Dict[str, Any]:
    normalized_mode = str(mode_key).lower()
    if normalized_mode not in PER_MODE_TECHNICAL_MODES:
        normalized_mode = PER_MODE_TECHNICAL_MODES[0]

    resolved: Dict[str, Any] = {}
    for key in _ACTIVE_MODE_TECHNICAL_KEYS:
        resolved[key] = per_mode_kwargs[f"{normalized_mode}_{key}"]
    return resolved


def _resolve_active_mode_shared_visual_state(
    mode_key: str,
    per_mode_kwargs: Mapping[str, Any],
) -> Dict[str, Any]:
    normalized_mode = str(mode_key).lower()
    if normalized_mode not in PER_MODE_TECHNICAL_MODES:
        normalized_mode = PER_MODE_TECHNICAL_MODES[0]

    resolved: Dict[str, Any] = {}
    for key in _ACTIVE_MODE_SHARED_VISUAL_KEYS:
        resolved[key] = deepcopy(per_mode_kwargs[f"{normalized_mode}_{key}"])
    return resolved


