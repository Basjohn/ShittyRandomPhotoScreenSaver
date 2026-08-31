"""Presentation-neutral visualizer source/BeatEngine configuration.

The Qt Quick ownership split routes canonical preset/settings values to three
independent consumers:

- authored logical state (``config_applier.apply_logical_vis_mode_kwargs``),
- retained renderer state (``config_applier.apply_presentation_vis_mode_kwargs``),
- BeatEngine/audio-source state (this module).

Historically the QWidget catch-all applier mixed all three responsibilities.  A
Quick owner must not call that widget-era façade, but the source-owned Spectrum
shaping values still need to reach the single shared BeatEngine.  This module is
the narrow replacement authority.  It performs configuration-time setter calls
only; it owns no cadence, polling loop, source, or duplicated runtime state.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.logging.logger import get_logger, is_viz_diagnostics_enabled
from widgets.spotify_visualizer.bar_computation import SpectrumShapeConfig

logger = get_logger(__name__)


SPECTRUM_SOURCE_CONFIG_KEYS = frozenset(
    {
        "spectrum_mirrored",
        "spectrum_shape_nodes",
        "spectrum_notch_positions_mirrored",
        "spectrum_notch_positions_linear",
        "spectrum_lane_strengths_mirrored",
        "spectrum_lane_strengths_linear",
        "spectrum_wave_amplitude",
        "spectrum_profile_floor",
        "spectrum_drop_speed",
    }
)

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
_DEFAULT_SHAPE_NODES = (
    (0.0, 0.40),
    (0.35, 0.75),
    (0.65, 0.55),
    (1.0, 0.80),
)
_DEFAULT_NOTCHES_MIRRORED = (
    (0.0, "Mid"),
    (0.30, "Vocal"),
    (0.65, "Low-Mid"),
    (1.0, "Bass"),
)
_DEFAULT_NOTCHES_LINEAR = (
    (0.0, "Bass"),
    (0.24, "Low-Mid"),
    (0.46, "Vocal"),
    (0.72, "Hi-Mid"),
    (1.0, "Treble"),
)


def _clamp(value: object, minimum: float, maximum: float, default: float) -> float:
    try:
        resolved = float(value)
    except (TypeError, ValueError):
        resolved = float(default)
    return max(float(minimum), min(float(maximum), resolved))


def _normalize_lane_strengths(
    value: object,
    defaults: Mapping[str, float],
) -> dict[str, float]:
    source = value if isinstance(value, Mapping) else {}
    normalized: dict[str, float] = {}
    for label, default in defaults.items():
        normalized[label] = _clamp(source.get(label, default), 0.0, 1.0, default)
    return normalized


def _normalize_list(value: object, default: tuple[tuple[Any, ...], ...], *, minimum: int) -> list:
    if isinstance(value, list) and len(value) >= minimum:
        return list(value)
    return [list(entry) for entry in default]


def _require_engine_method(engine: Any, name: str):
    method = getattr(engine, name, None)
    if not callable(method):
        raise RuntimeError(f"visualizer BeatEngine has no {name} source-config authority")
    return method


def apply_engine_vis_mode_kwargs(engine: Any, kwargs: Mapping[str, Any]) -> bool:
    """Apply source-owned visualizer preset values to the single BeatEngine.

    Returns ``True`` when a source-owned setting was present and therefore an
    engine configuration transaction was performed.  The canonical settings
    model supplied by ``DisplayManager`` is complete, but defaults are retained
    here so focused tests/diagnostics may safely provide a partial Spectrum map.
    """

    if not isinstance(kwargs, Mapping):
        raise TypeError("visualizer source config must be a mapping")
    if not any(key in kwargs for key in SPECTRUM_SOURCE_CONFIG_KEYS):
        return False

    mirrored = bool(kwargs.get("spectrum_mirrored", True))
    shape_nodes = _normalize_list(
        kwargs.get("spectrum_shape_nodes"),
        _DEFAULT_SHAPE_NODES,
        minimum=1,
    )
    notches_mirrored = _normalize_list(
        kwargs.get("spectrum_notch_positions_mirrored"),
        _DEFAULT_NOTCHES_MIRRORED,
        minimum=2,
    )
    notches_linear = _normalize_list(
        kwargs.get("spectrum_notch_positions_linear"),
        _DEFAULT_NOTCHES_LINEAR,
        minimum=2,
    )
    lane_strengths_mirrored = _normalize_lane_strengths(
        kwargs.get("spectrum_lane_strengths_mirrored"),
        _SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED,
    )
    lane_strengths_linear = _normalize_lane_strengths(
        kwargs.get("spectrum_lane_strengths_linear"),
        _SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR,
    )
    wave_amplitude = _clamp(
        kwargs.get("spectrum_wave_amplitude", 0.50), 0.0, 1.0, 0.50
    )
    profile_floor = _clamp(
        kwargs.get("spectrum_profile_floor", 0.12), 0.05, 0.30, 0.12
    )
    drop_speed = _clamp(
        kwargs.get("spectrum_drop_speed", 1.0), 0.5, 3.0, 1.0
    )

    _require_engine_method(engine, "set_spectrum_mirrored")(mirrored)
    _require_engine_method(engine, "set_spectrum_shape_nodes")(shape_nodes)
    _require_engine_method(engine, "set_notch_positions")(
        notches_mirrored if mirrored else notches_linear
    )
    _require_engine_method(engine, "set_spectrum_shape_config")(
        SpectrumShapeConfig(
            lane_strengths_mirrored=lane_strengths_mirrored,
            lane_strengths_linear=lane_strengths_linear,
            wave_amplitude=wave_amplitude,
            profile_floor=profile_floor,
        )
    )
    _require_engine_method(engine, "set_drop_speed")(drop_speed)
    if is_viz_diagnostics_enabled():
        logger.debug(
            "[VIS_SOURCE_CONFIG] spectrum mirrored=%s notches=%s shape_nodes=%d "
            "wave_amp=%.3f profile_floor=%.3f drop_speed=%.3f",
            mirrored,
            notches_mirrored if mirrored else notches_linear,
            len(shape_nodes),
            wave_amplitude,
            profile_floor,
            drop_speed,
        )
    return True


__all__ = ["SPECTRUM_SOURCE_CONFIG_KEYS", "apply_engine_vis_mode_kwargs"]
