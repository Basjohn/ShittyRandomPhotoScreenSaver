"""Pure Settings-to-request resolution for parameterized Phase-C Quick effects.

The render thread accepts only explicit immutable values.  This module keeps
Settings spelling, legacy fall-through behaviour, random choice, clamps, and
colour normalization on the GUI/runtime side before TransitionRequest
construction.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
import random
from typing import Protocol

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
    return value if isinstance(value, bool) else bool(default)


def _finish(direction: TransitionValue, parameters: Mapping[str, object]) -> ResolvedPhaseCInputs:
    return ResolvedPhaseCInputs(
        direction=direction,
        parameters=freeze_transition_parameters(parameters),
    )


def _resolve_blinds(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "blinds")
    raw_direction = str(cfg.get("direction", "Horizontal") or "Horizontal")
    if raw_direction == "Random":
        raw_direction = rng.choice(("Horizontal", "Vertical", "Diagonal"))
    direction = {
        "Horizontal": "horizontal",
        "Vertical": "vertical",
        "Diagonal": "diagonal",
    }.get(raw_direction, "horizontal")
    # Preserve TransitionFactory's UI-scale -> shader-scale conversion.
    ui_feather = _number(cfg.get("feather", 2), 2.0)
    feather = max(0.001, min(0.5, (ui_feather / 25.0) * 0.5))
    return _finish(direction, {"feather": feather})


def _resolve_diffuse(settings: Mapping[str, object], _rng: _RandomSource) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "diffuse")
    block_size = max(1, _integer(cfg.get("block_size", 50), 50))
    shape = str(cfg.get("shape", "Rectangle") or "Rectangle").strip().lower()
    shape_mode = {
        "rectangle": 0,
        "membrane": 1,
        "lines": 2,
        "diamonds": 3,
        "amorph": 4,
        "random": 5,
    }.get(shape, 0)
    return _finish(None, {"block_size": block_size, "shape_mode": shape_mode})


def _resolve_ripple(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "ripple")
    count = max(1, min(8, _integer(cfg.get("ripple_count", 3), 3)))
    return _finish(
        None,
        {
            "ripple_count": count,
            "ripple_seed": float(rng.random()) * 1000.0,
        },
    )


def _resolve_crumble(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "crumble")
    piece_count = max(4, _integer(cfg.get("piece_count", 14), 14))
    complexity = max(
        0.5,
        min(2.0, _number(cfg.get("crack_complexity", 1.0), 1.0)),
    )
    weighting = str(cfg.get("weighting", "Random Choice") or "Random Choice")
    # This deliberately preserves the CURRENT old factory semantics.  The
    # Settings UI also exposes "Bias Old Image" / "Bias New Image", but the
    # old factory does not recognize either spelling and therefore falls back
    # to 0.0.  H0 may deliberately repair/rename that UX; Phase C must not
    # silently change the authored presentation while migrating it.
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


def _resolve_particle(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "particle")
    mode_text = str(cfg.get("mode", "Converge") or "Converge")
    mode = {
        "Directional": 0,
        "Swirl": 1,
        "Converge": 2,
        "Random": 3,
    }.get(mode_text, 0)

    direction_text = str(cfg.get("direction", "Left to Right") or "Left to Right")
    # "Random" is intentionally 0: that is the current old factory's
    # fall-through for the Settings UI spelling.  Legacy "Random Direction"
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

    swirl_order = max(0, min(2, _integer(cfg.get("swirl_order", 0), 0)))
    if mode == 3:
        mode = int(rng.choice((0, 1, 2)))
        if mode == 0:
            direction = int(rng.randint(0, 9))
        else:
            swirl_order = int(rng.randint(0, 2))

    radius = max(8.0, _number(cfg.get("particle_radius", 10.0), 10.0))
    overlap = max(0.0, _number(cfg.get("overlap", 4.0), 4.0))
    if overlap >= radius * 2.0:
        raise ValueError("resolved Particle overlap must be smaller than particle diameter")

    # Preserve the old runtime's numerical index contract.  Current Settings
    # labels for light direction / swirl order do not match the shader comments
    # one-for-one; changing those meanings belongs to the later settings epoch.
    light_direction = max(0, min(4, _integer(cfg.get("light_direction", 0), 0)))
    gloss_size = max(16.0, min(128.0, _number(cfg.get("gloss_size", 72.0), 72.0)))

    return _finish(
        None,
        {
            "seed": float(rng.random()) * 1000.0,
            "mode": mode,
            "direction": direction,
            "particle_radius": radius,
            "overlap": overlap,
            "trail_length": max(0.0, min(1.0, _number(cfg.get("trail_length", 0.15), 0.15))),
            "trail_strength": max(0.0, min(1.0, _number(cfg.get("trail_strength", 0.6), 0.6))),
            "swirl_strength": max(0.0, _number(cfg.get("swirl_strength", 1.0), 1.0)),
            "swirl_turns": max(0.5, _number(cfg.get("swirl_turns", 2.0), 2.0)),
            "use_3d_shading": _bool(cfg.get("use_3d_shading", True), True),
            "texture_mapping": _bool(cfg.get("texture_mapping", True), True),
            "wobble": _bool(cfg.get("wobble", False), False),
            "gloss_size": gloss_size,
            "light_direction": light_direction,
            "swirl_order": swirl_order,
        },
    )


def _normalized_glow_color(value: object) -> tuple[float, float, float, float]:
    raw = value if isinstance(value, (tuple, list)) and len(value) == 4 else (255, 140, 30, 255)
    channels = tuple(_number(channel, 0.0) for channel in raw)
    if any(channel < 0.0 for channel in channels):
        raise ValueError("Burn glow_color channels must be non-negative")
    if max(channels) <= 1.0:
        return channels
    if max(channels) > 255.0:
        raise ValueError("Burn glow_color channels must be <= 255")
    return tuple(channel / 255.0 for channel in channels)


def _resolve_burn(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "burn")
    direction_text = str(cfg.get("direction", "Random") or "Random")
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
    return _finish(
        None,
        {
            "direction": direction,
            "jaggedness": max(0.0, min(1.0, _number(cfg.get("jaggedness", 0.5), 0.5))),
            "glow_intensity": max(0.0, min(1.0, _number(cfg.get("glow_intensity", 0.7), 0.7))),
            "glow_color": _normalized_glow_color(cfg.get("glow_color", (255, 140, 30, 255))),
            "char_width": max(0.1, min(1.0, _number(cfg.get("char_width", 0.5), 0.5))),
            "smoke_enabled": _bool(cfg.get("smoke_enabled", True), True),
            "smoke_density": max(0.0, min(1.0, _number(cfg.get("smoke_density", 0.5), 0.5))),
            "ash_enabled": _bool(cfg.get("ash_enabled", True), True),
            "ash_density": max(0.0, min(1.0, _number(cfg.get("ash_density", 0.5), 0.5))),
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
