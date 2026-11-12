"""Lazy Quick renderer for the full authored Burn transition shader."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from rendering.gl_programs.burn_program import burn_program
from rendering.transition_settings import require_transition_settings
from ..fullscreen_pass import FullscreenPassRenderer, fullscreen_pass_parts
from ..render_contract import QuickTransitionRenderFrame


@dataclass(frozen=True, slots=True)
class _BurnParameters:
    direction: int
    jaggedness: float
    glow_intensity: float
    glow_color: tuple[float, float, float, float]
    ember_color: tuple[float, float, float, float]
    char_width: float
    smoke_enabled: bool
    smoke_density: float
    ash_enabled: bool
    ash_density: float
    flames: bool
    ember_veins: bool
    seed: float


def _number(parameters: Mapping[str, object], name: str) -> float:
    raw = parameters.get(name)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"Burn requires resolved numeric parameter {name!r}")
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"Burn {name} must be finite")
    return value


def _boolean(parameters: Mapping[str, object], name: str) -> bool:
    raw = parameters.get(name)
    if not isinstance(raw, bool):
        raise ValueError(f"Burn requires resolved boolean parameter {name!r}")
    return raw


def _burn_color(
    parameters: Mapping[str, object],
    name: str,
) -> tuple[float, float, float, float]:
    raw = parameters.get(name)
    if not isinstance(raw, tuple) or len(raw) != 4:
        raise ValueError(
            f"Burn requires resolved normalized RGBA tuple parameter {name!r}"
        )
    channels: list[float] = []
    for channel in raw:
        if isinstance(channel, bool) or not isinstance(channel, (int, float)):
            raise ValueError(f"Burn {name} channels must be numeric")
        value = float(channel)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"Burn {name} channels must be finite and between 0 and 1")
        channels.append(value)
    return tuple(channels)  # type: ignore[return-value]


_RANGED_CONTROLS = ("jaggedness", "glow_intensity", "char_width", "smoke_density", "ash_density")
_BURN_RANGES: dict[str, tuple[float, float]] | None = None


def _burn_ranges() -> dict[str, tuple[float, float]]:
    """The Burn spec's ranges, read once: ``resolve`` runs every frame and the spec is code-owned and immutable."""
    global _BURN_RANGES
    if _BURN_RANGES is None:
        spec = require_transition_settings("burn")
        _BURN_RANGES = {
            name: (float(spec.control(name).low), float(spec.control(name).high)) for name in _RANGED_CONTROLS
        }
    return _BURN_RANGES


def _burn_parameters(parameters: Mapping[str, object]) -> _BurnParameters:
    direction_raw = parameters.get("direction")
    if isinstance(direction_raw, bool) or not isinstance(direction_raw, int):
        raise ValueError("Burn requires resolved integer parameter 'direction'")
    if not 0 <= direction_raw <= 5:
        raise ValueError("Burn direction must be between 0 and 5")

    jaggedness = _number(parameters, "jaggedness")
    glow_intensity = _number(parameters, "glow_intensity")
    char_width = _number(parameters, "char_width")
    smoke_density = _number(parameters, "smoke_density")
    ash_density = _number(parameters, "ash_density")
    seed = _number(parameters, "seed")

    # The trusted runtime contract: the resolver admitted these through the Burn spec, whose ranges this checks.
    ranges = _burn_ranges()
    for name, value in (("jaggedness", jaggedness), ("glow_intensity", glow_intensity), ("char_width", char_width),
                        ("smoke_density", smoke_density), ("ash_density", ash_density)):
        low, high = ranges[name]
        if not low <= value <= high:
            raise ValueError(f"Burn {name} must be between {low:g} and {high:g}")

    return _BurnParameters(
        direction=direction_raw,
        jaggedness=jaggedness,
        glow_intensity=glow_intensity,
        glow_color=_burn_color(parameters, "glow_color"),
        ember_color=_burn_color(parameters, "ember_color"),
        char_width=char_width,
        smoke_enabled=_boolean(parameters, "smoke_enabled"),
        smoke_density=smoke_density,
        ash_enabled=_boolean(parameters, "ash_enabled"),
        ash_density=ash_density,
        flames=_boolean(parameters, "flames"),
        ember_veins=_boolean(parameters, "ember_veins"),
        seed=seed,
    )


def _burn_effect_time_seconds(frame: QuickTransitionRenderFrame) -> float:
    return (
        float(frame.sample.linear_progress)
        * float(frame.run.request.duration_ms)
        / 1000.0
    )


class QuickBurnRenderer(FullscreenPassRenderer):
    transition_id = "burn"
    label = "Quick Burn"
    fragment_source = burn_program.fragment_source
    vertex_source, block = fullscreen_pass_parts(fragment_source, "BurnPass")
    value_names = (
        "u_direction", "u_jaggedness", "u_glow_intensity",
        "u_glow_color", "u_ember_color", "u_char_width", "u_smoke_enabled",
        "u_smoke_density", "u_ash_enabled", "u_ash_density",
        "u_flames", "u_ember_veins",
        "u_time", "u_seed",
    )

    def resolve(self, frame: QuickTransitionRenderFrame):
        return _burn_parameters(frame.run.request.parameter_dict())

    def values(self, params, frame: QuickTransitionRenderFrame) -> dict[str, object]:
        return {
            "u_direction": params.direction,
            "u_jaggedness": params.jaggedness,
            "u_glow_intensity": params.glow_intensity,
            "u_glow_color": params.glow_color,
            "u_ember_color": params.ember_color,
            "u_char_width": params.char_width,
            "u_smoke_enabled": 1 if params.smoke_enabled else 0,
            "u_smoke_density": params.smoke_density,
            "u_ash_enabled": 1 if params.ash_enabled else 0,
            "u_ash_density": params.ash_density,
            "u_flames": 1 if params.flames else 0,
            "u_ember_veins": 1 if params.ember_veins else 0,
            "u_time": _burn_effect_time_seconds(frame),
            "u_seed": params.seed,
        }


def create_transition_renderer() -> QuickBurnRenderer:
    return QuickBurnRenderer()
