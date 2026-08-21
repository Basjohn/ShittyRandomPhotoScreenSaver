"""Pure Settings-to-request resolution for parameterized Phase-C Quick effects.

The render thread accepts only explicit immutable values. This module keeps
Settings spelling, legacy fall-through behaviour, random choice, clamps, and
colour normalization on the GUI/runtime side before TransitionRequest
construction. Canonical Settings defaults remain the single fallback authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
import random
from typing import Protocol

from core.settings.defaults import get_default_settings
from .state import TransitionParameters, TransitionValue, freeze_transition_parameters


class _RandomSource(Protocol):
    def random(self) -> float: ...
    def randint(self, a: int, b: int) -> int: ...
    def choice(self, seq): ...


@dataclass(frozen=True, slots=True)
class ResolvedPhaseCInputs:
    direction: TransitionValue
    parameters: TransitionParameters

    def parameter_dict(self) -> dict[str, TransitionValue]:
        return dict(self.parameters)


def _mapping(settings: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = settings.get(name, {})
    return value if isinstance(value, Mapping) else {}


def _canonical(name: str) -> Mapping[str, object]:
    all_defaults = get_default_settings()
    transitions = all_defaults.get("transitions", {})
    if not isinstance(transitions, Mapping):
        return {}
    value = transitions.get(name, {})
    return value if isinstance(value, Mapping) else {}


def _value(
    config: Mapping[str, object],
    defaults: Mapping[str, object],
    name: str,
    fallback: object,
) -> object:
    return config.get(name, defaults.get(name, fallback))


def _number(value: object, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float(default)
    return result if math.isfinite(result) else float(default)


def _integer(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _bool(value: object, default: bool) -> bool:
    """Preserve the Settings layer's legacy bool coercion at request admission."""

    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "on", "enabled"}:
            return True
        if normalized in {"false", "no", "0", "off", "disabled"}:
            return False
    return bool(default)


def _finish(
    direction: TransitionValue,
    parameters: Mapping[str, object],
) -> ResolvedPhaseCInputs:
    return ResolvedPhaseCInputs(
        direction=direction,
        parameters=freeze_transition_parameters(parameters),
    )


def _resolve_blinds(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "blinds")
    defaults = _canonical("blinds")
    default_direction = str(defaults.get("direction", "Horizontal") or "Horizontal")
    raw_direction = str(_value(cfg, defaults, "direction", default_direction) or default_direction)
    if raw_direction == "Random":
        raw_direction = rng.choice(("Horizontal", "Vertical", "Diagonal"))
    direction = {
        "Horizontal": "horizontal",
        "Vertical": "vertical",
        "Diagonal": "diagonal",
    }.get(raw_direction, "horizontal")

    default_feather = _number(defaults.get("feather", 2), 2.0)
    ui_feather = _number(_value(cfg, defaults, "feather", default_feather), default_feather)
    # Preserve TransitionFactory's UI-scale -> shader-scale conversion.
    feather = max(0.001, min(0.5, (ui_feather / 25.0) * 0.5))
    return _finish(direction, {"feather": feather})


def _resolve_diffuse(
    settings: Mapping[str, object],
    _rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "diffuse")
    defaults = _canonical("diffuse")
    default_block_size = max(1, _integer(defaults.get("block_size", 50), 50))
    block_size = max(
        1,
        _integer(
            _value(cfg, defaults, "block_size", default_block_size),
            default_block_size,
        ),
    )
    default_shape = str(defaults.get("shape", "Rectangle") or "Rectangle")
    shape = str(_value(cfg, defaults, "shape", default_shape) or default_shape).strip().lower()
    shape_mode = {
        "rectangle": 0,
        "membrane": 1,
        "lines": 2,
        "diamonds": 3,
        "amorph": 4,
        "random": 5,
    }.get(shape, 0)
    return _finish(None, {"block_size": block_size, "shape_mode": shape_mode})


def _resolve_ripple(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "ripple")
    defaults = _canonical("ripple")
    default_count = _integer(defaults.get("ripple_count", 3), 3)
    count = max(
        1,
        min(
            8,
            _integer(
                _value(cfg, defaults, "ripple_count", default_count),
                default_count,
            ),
        ),
    )
    return _finish(
        None,
        {
            "ripple_count": count,
            "ripple_seed": float(rng.random()) * 1000.0,
        },
    )


def _resolve_crumble(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "crumble")
    defaults = _canonical("crumble")
    default_pieces = max(4, _integer(defaults.get("piece_count", 14), 14))
    piece_count = max(
        4,
        _integer(
            _value(cfg, defaults, "piece_count", default_pieces),
            default_pieces,
        ),
    )
    default_complexity = _number(defaults.get("crack_complexity", 1.0), 1.0)
    complexity = max(
        0.5,
        min(
            2.0,
            _number(
                _value(cfg, defaults, "crack_complexity", default_complexity),
                default_complexity,
            ),
        ),
    )
    default_weighting = str(defaults.get("weighting", "Random Choice") or "Random Choice")
    weighting = str(_value(cfg, defaults, "weighting", default_weighting) or default_weighting)
    # Deliberately preserve CURRENT old factory semantics. The Settings UI
    # exposes "Bias Old Image" / "Bias New Image", but the old factory does
    # not recognize either spelling and falls through to 0.0. H0 may repair
    # that UX deliberately; Phase C must not silently change presentation.
    weight_mode = {
        "Top Weighted": 0.0,
        "Bottom Weighted": 1.0,
        "Random Weighted": 2.0,
        "Random Choice": 3.0,
        "Age Weighted": 4.0,
        "Bias Old Image": 0.0,
        "Bias New Image": 0.0,
    }.get(weighting, 0.0)
    return _finish(
        None,
        {
            "seed": float(rng.random()) * 1000.0,
            "piece_count": piece_count,
            "crack_complexity": complexity,
            "mosaic_mode": False,
            "weight_mode": weight_mode,
        },
    )


def _resolve_particle(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "particle")
    defaults = _canonical("particle")

    default_mode = str(defaults.get("mode", "Converge") or "Converge")
    mode_text = str(_value(cfg, defaults, "mode", default_mode) or default_mode)
    mode = {
        "Directional": 0,
        "Swirl": 1,
        "Converge": 2,
        "Random": 3,
    }.get(mode_text, 0)

    default_direction = str(defaults.get("direction", "Left to Right") or "Left to Right")
    direction_text = str(
        _value(cfg, defaults, "direction", default_direction) or default_direction
    )
    # "Random" is intentionally 0: that is the current old factory's
    # fall-through for the Settings UI spelling. Legacy "Random Direction"
    # and "Random Placement" retain the shader's explicit 8/9 meanings.
    direction = {
        "Left to Right": 0,
        "Right to Left": 1,
        "Top to Bottom": 2,
        "Bottom to Top": 3,
        "Top-Left to Bottom-Right": 4,
        "Top-Right to Bottom-Left": 5,
        "Bottom-Left to Top-Right": 6,
        "Bottom-Right to Top-Left": 7,
        "Random Direction": 8,
        "Random Placement": 9,
        "Random": 0,
    }.get(direction_text, 0)

    default_swirl_order = _integer(defaults.get("swirl_order", 0), 0)
    swirl_order = max(
        0,
        min(
            2,
            _integer(
                _value(cfg, defaults, "swirl_order", default_swirl_order),
                default_swirl_order,
            ),
        ),
    )
    if mode == 3:
        mode = int(rng.choice((0, 1, 2)))
        if mode == 0:
            direction = int(rng.randint(0, 9))
        else:
            swirl_order = int(rng.randint(0, 2))

    default_radius = _number(defaults.get("particle_radius", 10.0), 10.0)
    radius = max(
        8.0,
        _number(
            _value(cfg, defaults, "particle_radius", default_radius),
            default_radius,
        ),
    )
    default_overlap = _number(defaults.get("overlap", 4.0), 4.0)
    overlap = max(
        0.0,
        _number(_value(cfg, defaults, "overlap", default_overlap), default_overlap),
    )
    if overlap >= radius * 2.0:
        raise ValueError("resolved Particle overlap must be smaller than particle diameter")

    # Preserve the old runtime's numerical index contract. Current Settings
    # labels for light direction / swirl order do not match shader comments
    # one-for-one; changing meanings belongs to the later settings epoch.
    default_light = _integer(defaults.get("light_direction", 0), 0)
    light_direction = max(
        0,
        min(
            4,
            _integer(
                _value(cfg, defaults, "light_direction", default_light),
                default_light,
            ),
        ),
    )
    default_gloss = _number(defaults.get("gloss_size", 72.0), 72.0)
    gloss_size = max(
        16.0,
        min(
            128.0,
            _number(_value(cfg, defaults, "gloss_size", default_gloss), default_gloss),
        ),
    )

    default_trail_length = _number(defaults.get("trail_length", 0.15), 0.15)
    default_trail_strength = _number(defaults.get("trail_strength", 0.6), 0.6)
    default_swirl_strength = _number(defaults.get("swirl_strength", 1.0), 1.0)
    default_swirl_turns = _number(defaults.get("swirl_turns", 3.0), 3.0)
    default_3d = _bool(defaults.get("use_3d_shading", True), True)
    default_texture = _bool(defaults.get("texture_mapping", True), True)
    default_wobble = _bool(defaults.get("wobble", True), True)

    return _finish(
        None,
        {
            "seed": float(rng.random()) * 1000.0,
            "mode": mode,
            "direction": direction,
            "particle_radius": radius,
            "overlap": overlap,
            "trail_length": max(
                0.0,
                min(
                    1.0,
                    _number(
                        _value(cfg, defaults, "trail_length", default_trail_length),
                        default_trail_length,
                    ),
                ),
            ),
            "trail_strength": max(
                0.0,
                min(
                    1.0,
                    _number(
                        _value(cfg, defaults, "trail_strength", default_trail_strength),
                        default_trail_strength,
                    ),
                ),
            ),
            "swirl_strength": max(
                0.0,
                _number(
                    _value(cfg, defaults, "swirl_strength", default_swirl_strength),
                    default_swirl_strength,
                ),
            ),
            "swirl_turns": max(
                0.5,
                _number(
                    _value(cfg, defaults, "swirl_turns", default_swirl_turns),
                    default_swirl_turns,
                ),
            ),
            "use_3d_shading": _bool(
                _value(cfg, defaults, "use_3d_shading", default_3d),
                default_3d,
            ),
            "texture_mapping": _bool(
                _value(cfg, defaults, "texture_mapping", default_texture),
                default_texture,
            ),
            "wobble": _bool(
                _value(cfg, defaults, "wobble", default_wobble),
                default_wobble,
            ),
            "gloss_size": gloss_size,
            "light_direction": light_direction,
            "swirl_order": swirl_order,
        },
    )


def _normalized_glow_color(
    value: object,
    fallback: object = (255, 140, 30, 255),
) -> tuple[float, float, float, float]:
    candidate = value
    if not isinstance(candidate, (tuple, list)) or len(candidate) != 4:
        candidate = fallback
    if not isinstance(candidate, (tuple, list)) or len(candidate) != 4:
        candidate = (255, 140, 30, 255)
    channels = tuple(_number(channel, 0.0) for channel in candidate)
    if any(channel < 0.0 for channel in channels):
        raise ValueError("Burn glow_color channels must be non-negative")
    if max(channels) <= 1.0:
        return channels
    if max(channels) > 255.0:
        raise ValueError("Burn glow_color channels must be <= 255")
    return tuple(channel / 255.0 for channel in channels)


def _resolve_burn(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "burn")
    defaults = _canonical("burn")
    default_direction = str(defaults.get("direction", "Random") or "Random")
    direction_text = str(
        _value(cfg, defaults, "direction", default_direction) or default_direction
    )
    direction_map = {
        "Left to Right": 0,
        "Right to Left": 1,
        "Top to Bottom": 2,
        "Bottom to Top": 3,
        "Diagonal TL-BR": 4,
        "Diagonal TR-BL": 5,
    }
    direction = (
        int(rng.randint(0, 5))
        if direction_text == "Random"
        else direction_map.get(direction_text, 0)
    )

    default_jagged = _number(defaults.get("jaggedness", 0.5), 0.5)
    default_glow = _number(defaults.get("glow_intensity", 0.7), 0.7)
    default_char = _number(defaults.get("char_width", 0.5), 0.5)
    default_smoke_enabled = _bool(defaults.get("smoke_enabled", True), True)
    default_smoke_density = _number(defaults.get("smoke_density", 0.5), 0.5)
    default_ash_enabled = _bool(defaults.get("ash_enabled", True), True)
    default_ash_density = _number(defaults.get("ash_density", 0.5), 0.5)
    default_glow_color = defaults.get("glow_color", (255, 140, 30, 255))

    return _finish(
        None,
        {
            "direction": direction,
            "jaggedness": max(
                0.0,
                min(
                    1.0,
                    _number(
                        _value(cfg, defaults, "jaggedness", default_jagged),
                        default_jagged,
                    ),
                ),
            ),
            "glow_intensity": max(
                0.0,
                min(
                    1.0,
                    _number(
                        _value(cfg, defaults, "glow_intensity", default_glow),
                        default_glow,
                    ),
                ),
            ),
            "glow_color": _normalized_glow_color(
                _value(cfg, defaults, "glow_color", default_glow_color),
                default_glow_color,
            ),
            "char_width": max(
                0.1,
                min(
                    1.0,
                    _number(
                        _value(cfg, defaults, "char_width", default_char),
                        default_char,
                    ),
                ),
            ),
            "smoke_enabled": _bool(
                _value(cfg, defaults, "smoke_enabled", default_smoke_enabled),
                default_smoke_enabled,
            ),
            "smoke_density": max(
                0.0,
                min(
                    1.0,
                    _number(
                        _value(cfg, defaults, "smoke_density", default_smoke_density),
                        default_smoke_density,
                    ),
                ),
            ),
            "ash_enabled": _bool(
                _value(cfg, defaults, "ash_enabled", default_ash_enabled),
                default_ash_enabled,
            ),
            "ash_density": max(
                0.0,
                min(
                    1.0,
                    _number(
                        _value(cfg, defaults, "ash_density", default_ash_density),
                        default_ash_density,
                    ),
                ),
            ),
            "seed": float(rng.random()) * 1000.0,
        },
    )


_RESOLVERS = {
    "blinds": _resolve_blinds,
    "diffuse": _resolve_diffuse,
    "ripple": _resolve_ripple,
    "crumble": _resolve_crumble,
    "particle": _resolve_particle,
    "burn": _resolve_burn,
}


def resolve_parameterized_phase_c_inputs(
    transition_id: str,
    transition_settings: Mapping[str, object],
    *,
    random_source: _RandomSource | None = None,
) -> ResolvedPhaseCInputs:
    """Resolve one parameterized Phase-C effect before request admission."""

    stable_id = str(transition_id).strip().lower()
    resolver = _RESOLVERS.get(stable_id)
    if resolver is None:
        raise ValueError(f"no parameterized Phase-C resolver for {transition_id!r}")
    rng = random_source if random_source is not None else random
    return resolver(transition_settings, rng)
