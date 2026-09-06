"""Presentation-neutral visualizer source/BeatEngine configuration.

The Qt Quick ownership split routes canonical preset/settings values to three
independent consumers:

- authored logical state (``config_applier.apply_logical_vis_mode_kwargs``),
- retained renderer state (``config_applier.apply_presentation_vis_mode_kwargs``),
- BeatEngine/audio-source state (this module).

This module owns no product-default literals. Production callers normally supply
a complete resolved map; focused diagnostics may supply a partial Spectrum map,
in which case missing/invalid persisted values repair from canonical defaults.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from core.logging.logger import get_logger, is_viz_diagnostics_enabled
from core.settings.default_contract import require_canonical_default
from widgets.spotify_visualizer.bar_computation import SpectrumShapeConfig

logger = get_logger(__name__)

_VIS_PREFIX = "widgets.spotify_visualizer"

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


def _canonical(key: str) -> Any:
    return require_canonical_default(f"{_VIS_PREFIX}.{key}")


def _clamp(value: object, minimum: float, maximum: float, canonical: float) -> float:
    try:
        resolved = float(value)
    except (TypeError, ValueError):
        resolved = float(canonical)
    return max(float(minimum), min(float(maximum), resolved))


def _normalize_lane_strengths(
    value: object,
    canonical: Mapping[str, float],
) -> dict[str, float]:
    source = value if isinstance(value, Mapping) else {}
    normalized: dict[str, float] = {}
    for label, canonical_value in canonical.items():
        normalized[label] = _clamp(
            source.get(label, canonical_value), 0.0, 1.0, canonical_value
        )
    return normalized


def _normalize_list(value: object, canonical: object, *, minimum: int) -> list:
    if isinstance(value, list) and len(value) >= minimum:
        return deepcopy(value)
    if not isinstance(canonical, list) or len(canonical) < minimum:
        raise ValueError("canonical Spectrum source list is invalid")
    return deepcopy(canonical)


def _require_engine_method(engine: Any, name: str):
    method = getattr(engine, name, None)
    if not callable(method):
        raise RuntimeError(f"visualizer BeatEngine has no {name} source-config authority")
    return method


def apply_engine_vis_mode_kwargs(engine: Any, kwargs: Mapping[str, Any]) -> bool:
    """Apply source-owned Spectrum values to the single BeatEngine.

    Returns ``True`` when a source-owned setting was present.  Partial maps are
    permitted for focused diagnostics, but repair always comes from canonical
    product defaults rather than a second local baseline table.
    """

    if not isinstance(kwargs, Mapping):
        raise TypeError("visualizer source config must be a mapping")
    if not any(key in kwargs for key in SPECTRUM_SOURCE_CONFIG_KEYS):
        return False

    canonical_mirrored = bool(_canonical("spectrum_mirrored"))
    canonical_shape_nodes = _canonical("spectrum_shape_nodes")
    canonical_notches_mirrored = _canonical("spectrum_notch_positions_mirrored")
    canonical_notches_linear = _canonical("spectrum_notch_positions_linear")
    canonical_lanes_mirrored = _canonical("spectrum_lane_strengths_mirrored")
    canonical_lanes_linear = _canonical("spectrum_lane_strengths_linear")
    canonical_wave_amplitude = float(_canonical("spectrum_wave_amplitude"))
    canonical_profile_floor = float(_canonical("spectrum_profile_floor"))
    canonical_drop_speed = float(_canonical("spectrum_drop_speed"))

    mirrored = bool(kwargs.get("spectrum_mirrored", canonical_mirrored))
    shape_nodes = _normalize_list(
        kwargs.get("spectrum_shape_nodes"), canonical_shape_nodes, minimum=1
    )
    notches_mirrored = _normalize_list(
        kwargs.get("spectrum_notch_positions_mirrored"),
        canonical_notches_mirrored,
        minimum=2,
    )
    notches_linear = _normalize_list(
        kwargs.get("spectrum_notch_positions_linear"),
        canonical_notches_linear,
        minimum=2,
    )
    lane_strengths_mirrored = _normalize_lane_strengths(
        kwargs.get("spectrum_lane_strengths_mirrored"), canonical_lanes_mirrored
    )
    lane_strengths_linear = _normalize_lane_strengths(
        kwargs.get("spectrum_lane_strengths_linear"), canonical_lanes_linear
    )
    wave_amplitude = _clamp(
        kwargs.get("spectrum_wave_amplitude", canonical_wave_amplitude),
        0.0,
        1.0,
        canonical_wave_amplitude,
    )
    profile_floor = _clamp(
        kwargs.get("spectrum_profile_floor", canonical_profile_floor),
        0.05,
        0.30,
        canonical_profile_floor,
    )
    drop_speed = _clamp(
        kwargs.get("spectrum_drop_speed", canonical_drop_speed),
        0.5,
        3.0,
        canonical_drop_speed,
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
