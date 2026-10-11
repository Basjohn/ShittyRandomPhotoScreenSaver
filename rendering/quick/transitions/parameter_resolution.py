"""Pure Settings-to-request resolution for parameterized Quick effects.

The render thread accepts only explicit immutable values. This module keeps
Settings spelling, legacy fall-through behaviour, random choice, clamps, and
colour normalization on the GUI/runtime side before TransitionRequest
construction. Canonical Settings defaults remain the single fallback authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import random
from typing import Protocol

from core.settings.default_contract import require_canonical_default
from rendering.gl_programs.blinds_options import BLINDS_STYLE_CODES
from rendering.gl_programs.edge_bloom_options import EDGE_BLOOM_COLOUR_SOURCES
from rendering.gl_programs.scene3d import (
    SCENE3D_ANTIALIASING_CHOICES,
    SCENE3D_TRAIL_CHOICES,
    SCENE3D_DETAIL_NAMES,
    SCENE3D_EFFECT_CHOICES,
    scene3d_detail,
    scene3d_post_effect,
    scene3d_samples,
)
from rendering.transition_settings import (
    TransitionSettings,
    as_bool,
    as_integer,
    as_number,
    require_transition_settings,
)
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
    value = require_canonical_default(f"transitions.{name}")
    if not isinstance(value, Mapping):
        raise TypeError(f"Canonical transitions.{name} default must be a mapping")
    return value


def _value(
    config: Mapping[str, object],
    defaults: Mapping[str, object],
    name: str,
) -> object:
    if name not in defaults:
        raise KeyError(f"Canonical transition defaults are missing {name!r}")
    return config.get(name, defaults[name])


# The Settings layer's coercion, shared with the Settings page through the specs.
_number = as_number
_integer = as_integer
_bool = as_bool


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
    style = BLINDS_STYLE_CODES[require_transition_settings("blinds").admit("style", cfg, defaults)]
    default_direction = str(defaults["direction"])
    raw_direction = str(_value(cfg, defaults, "direction") or default_direction)
    if style == "slats" and raw_direction not in ("Horizontal", "Vertical"):
        # Slats turn about horizontal or vertical axes: Random and Diagonal pick one per run.
        raw_direction = rng.choice(("Horizontal", "Vertical"))
    if raw_direction == "Random":
        raw_direction = rng.choice(("Horizontal", "Vertical", "Diagonal"))
    direction = {
        "Horizontal": "horizontal",
        "Vertical": "vertical",
        "Diagonal": "diagonal",
    }.get(raw_direction, "horizontal")

    default_feather = float(defaults["feather"])
    ui_feather = _number(_value(cfg, defaults, "feather"), default_feather)
    # Preserve TransitionFactory's UI-scale -> shader-scale conversion.
    feather = max(0.001, min(0.5, (ui_feather / 25.0) * 0.5))
    if style == "flat":
        return _finish(direction, {"feather": feather, "style": style})
    spec = require_transition_settings("blinds")
    return _finish(direction, {
        "feather": feather, "style": style,
        "slats": spec.admit("slats", cfg, defaults),
        "gloss": spec.admit("gloss", cfg, defaults),
        **resolve_scene_quality(settings, cfg, defaults),
    })


def _resolve_ripple(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "ripple")
    defaults = _canonical("ripple")
    return _finish(None, {
        **require_transition_settings("ripple").page_values(cfg, defaults),
        "ripple_seed": float(rng.random()) * 1000.0,
    })


# The release order each Weighting label selects in the shader.
_CRUMBLE_WEIGHT_MODES = {
    "Top Weighted": 0.0,
    "Bottom Weighted": 1.0,
    "Random Weighted": 2.0,
    "Random Choice": 3.0,
    "Age Weighted": 4.0,
}


def _resolve_crumble(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "crumble")
    defaults = _canonical("crumble")
    spec = require_transition_settings("crumble")
    return _finish(None, {
        "seed": float(rng.random()) * 1000.0,
        **spec.page_values(cfg, defaults),
        # Retired Bias labels admit as Top Weighted; the Settings page writes the label on its next save.
        "weight_mode": _CRUMBLE_WEIGHT_MODES[spec.admit("weighting", cfg, defaults)],
        **resolve_scene_quality(settings, cfg, defaults, motion_blur=True, motion_trails=True),
    })


def _resolve_particle(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "particle")
    defaults = _canonical("particle")

    default_mode = str(defaults["mode"])
    mode_text = str(_value(cfg, defaults, "mode") or default_mode)
    mode = {
        "Directional": 0,
        "Swirl": 1,
        "Converge": 2,
        "Random": 3,
    }.get(mode_text, 0)

    default_direction = str(defaults["direction"])
    direction_text = str(
        _value(cfg, defaults, "direction") or default_direction
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

    default_swirl_order = int(defaults["swirl_order"])
    swirl_order = max(
        0,
        min(
            2,
            _integer(
                _value(cfg, defaults, "swirl_order"),
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

    default_radius = float(defaults["particle_radius"])
    radius = max(
        8.0,
        _number(
            _value(cfg, defaults, "particle_radius"),
            default_radius,
        ),
    )
    default_overlap = float(defaults["overlap"])
    overlap = max(
        0.0,
        _number(_value(cfg, defaults, "overlap"), default_overlap),
    )
    if overlap >= radius * 2.0:
        raise ValueError("resolved Particle overlap must be smaller than particle diameter")

    # Preserve the runtime's numerical index contract. Settings labels mirror
    # the shader meanings exactly; the persisted values remain integer indices.
    default_light = int(defaults["light_direction"])
    light_direction = max(
        0,
        min(
            4,
            _integer(
                _value(cfg, defaults, "light_direction"),
                default_light,
            ),
        ),
    )
    default_gloss = float(defaults["gloss_size"])
    gloss_size = max(
        16.0,
        min(
            128.0,
            _number(_value(cfg, defaults, "gloss_size"), default_gloss),
        ),
    )

    default_trail_length = float(defaults["trail_length"])
    default_trail_strength = float(defaults["trail_strength"])
    default_swirl_strength = float(defaults["swirl_strength"])
    default_swirl_turns = float(defaults["swirl_turns"])
    default_3d = bool(defaults["use_3d_shading"])
    default_texture = bool(defaults["texture_mapping"])
    default_wobble = bool(defaults["wobble"])

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
                        _value(cfg, defaults, "trail_length"),
                        default_trail_length,
                    ),
                ),
            ),
            "trail_strength": max(
                0.0,
                min(
                    1.0,
                    _number(
                        _value(cfg, defaults, "trail_strength"),
                        default_trail_strength,
                    ),
                ),
            ),
            "swirl_strength": max(
                0.0,
                _number(
                    _value(cfg, defaults, "swirl_strength"),
                    default_swirl_strength,
                ),
            ),
            "swirl_turns": max(
                0.5,
                _number(
                    _value(cfg, defaults, "swirl_turns"),
                    default_swirl_turns,
                ),
            ),
            "use_3d_shading": _bool(
                _value(cfg, defaults, "use_3d_shading"),
                default_3d,
            ),
            "texture_mapping": _bool(
                _value(cfg, defaults, "texture_mapping"),
                default_texture,
            ),
            "wobble": _bool(
                _value(cfg, defaults, "wobble"),
                default_wobble,
            ),
            "gloss_size": gloss_size,
            "light_direction": light_direction,
            "swirl_order": swirl_order,
        },
    )


def _normalized_glow_color(
    value: object,
    fallback: object,
    *,
    field_name: str = "glow_color",
) -> tuple[float, float, float, float]:
    candidate = value
    if not isinstance(candidate, (tuple, list)) or len(candidate) != 4:
        candidate = fallback
    if not isinstance(candidate, (tuple, list)) or len(candidate) != 4:
        raise ValueError(f"Canonical Burn {field_name} colour must contain four channels")
    channels = tuple(_number(channel, 0.0) for channel in candidate)
    if any(channel < 0.0 for channel in channels):
        raise ValueError(f"Burn {field_name} channels must be non-negative")
    if max(channels) <= 1.0:
        return channels
    if max(channels) > 255.0:
        raise ValueError(f"Burn {field_name} channels must be <= 255")
    return tuple(channel / 255.0 for channel in channels)


def _resolve_burn(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "burn")
    defaults = _canonical("burn")
    default_direction = str(defaults["direction"])
    direction_text = str(
        _value(cfg, defaults, "direction") or default_direction
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

    default_jagged = float(defaults["jaggedness"])
    default_glow = float(defaults["glow_intensity"])
    default_char = float(defaults["char_width"])
    default_smoke_enabled = bool(defaults["smoke_enabled"])
    default_smoke_density = float(defaults["smoke_density"])
    default_ash_enabled = bool(defaults["ash_enabled"])
    default_ash_density = float(defaults["ash_density"])
    default_glow_color = defaults["glow_color"]
    default_ember_color = defaults["ember_color"]

    return _finish(
        None,
        {
            "direction": direction,
            "jaggedness": max(
                0.0,
                min(
                    1.0,
                    _number(
                        _value(cfg, defaults, "jaggedness"),
                        default_jagged,
                    ),
                ),
            ),
            "glow_intensity": max(
                0.0,
                min(
                    1.0,
                    _number(
                        _value(cfg, defaults, "glow_intensity"),
                        default_glow,
                    ),
                ),
            ),
            "glow_color": _normalized_glow_color(
                _value(cfg, defaults, "glow_color"),
                default_glow_color,
            ),
            "ember_color": _normalized_glow_color(
                _value(cfg, defaults, "ember_color"),
                default_ember_color,
                field_name="ember_color",
            ),
            "char_width": max(
                0.1,
                min(
                    1.0,
                    _number(
                        _value(cfg, defaults, "char_width"),
                        default_char,
                    ),
                ),
            ),
            "smoke_enabled": _bool(
                _value(cfg, defaults, "smoke_enabled"),
                default_smoke_enabled,
            ),
            "smoke_density": max(
                0.0,
                min(
                    1.0,
                    _number(
                        _value(cfg, defaults, "smoke_density"),
                        default_smoke_density,
                    ),
                ),
            ),
            "ash_enabled": _bool(
                _value(cfg, defaults, "ash_enabled"),
                default_ash_enabled,
            ),
            "ash_density": max(
                0.0,
                min(
                    1.0,
                    _number(
                        _value(cfg, defaults, "ash_density"),
                        default_ash_density,
                    ),
                ),
            ),
            "flames": _bool(_value(cfg, defaults, "flames"), bool(defaults["flames"])),
            "ember_veins": _bool(_value(cfg, defaults, "ember_veins"), bool(defaults["ember_veins"])),
            "seed": float(rng.random()) * 1000.0,
        },
    )


def _seed(rng: _RandomSource) -> int:
    """Generate one deterministic per-request seed; it is never persisted."""

    return int(rng.randint(1, 65535))


# The request-time field carrying the run's resolved 3D Transitions tier. Never persisted:
# ``resolve_quick_transition_spec`` resolves it once from the 3D Settings and adds it to the
# Transitions mapping the per-transition resolvers read. Named as the Visualizers' activation
# parameter is, and unlike the retired persisted ``transitions.detail_3d``, so a stray retired leaf
# can never be read (or written back) as the run's tier.
SCENE_DETAIL_FIELD = "scene3d_detail"


def resolve_scene_detail(settings: Mapping[str, object]) -> str:
    """The run's 3D Detail tier: the request's resolved tier, else the canonical 3D Settings'."""

    value = settings.get(SCENE_DETAIL_FIELD)
    if isinstance(value, str) and value in SCENE3D_DETAIL_NAMES:
        return value
    from core.settings.scene3d_quality import resolve_scene3d_tier
    from rendering.quick.bootstrap import last_validated_gpu

    return resolve_scene3d_tier(None, "transitions", gpu=last_validated_gpu())


def _scene_choice(cfg: Mapping[str, object], defaults: Mapping[str, object], field: str,
                  choices: tuple[str, ...]) -> str:
    value = _value(cfg, defaults, field)
    return value if isinstance(value, str) and value in choices else str(defaults[field])


def resolve_scene_quality(settings: Mapping[str, object], cfg: Mapping[str, object],
                          defaults: Mapping[str, object], *, bloom: bool = False,
                          motion_blur: bool = False, motion_trails: bool = False) -> dict[str, object]:
    """A 3D transition's effective quality: the global 3D Detail tier, with the
    transition's own choices authoritative ("Auto" follows the tier).

    Returns ``detail`` (the tier, for tier-only features), ``samples`` and, for an
    effect with emitted light, ``bloom`` (its strength, 0 when off); for an effect
    that writes its screen motion, ``motion_blur`` (on or off); for one that can draw
    its ghosts, ``motion_trails`` (on or off: a look, not a tier choice, so no Auto).
    """
    detail_name = resolve_scene_detail(settings)
    detail = scene3d_detail(detail_name)
    quality: dict[str, object] = {
        "detail": detail_name,
        "samples": scene3d_samples(detail, _scene_choice(cfg, defaults, "antialiasing", SCENE3D_ANTIALIASING_CHOICES)),
    }
    if bloom:
        on = scene3d_post_effect(detail, _scene_choice(cfg, defaults, "bloom", SCENE3D_EFFECT_CHOICES))
        strength = max(0.0, min(1.0, _number(_value(cfg, defaults, "bloom_strength"), float(defaults["bloom_strength"]))))
        quality["bloom"] = strength if on else 0.0
    if motion_blur:
        quality["motion_blur"] = scene3d_post_effect(
            detail, _scene_choice(cfg, defaults, "motion_blur", SCENE3D_EFFECT_CHOICES))
    if motion_trails:
        quality["motion_trails"] = _scene_choice(cfg, defaults, "motion_trails", SCENE3D_TRAIL_CHOICES) == "On"
    return quality


def resolve_block_spins_parameters(settings: Mapping[str, object], cfg: Mapping[str, object],
                                   defaults: Mapping[str, object]) -> dict[str, object]:
    """3D Block Spins' request parameters: its quality plus its Edge Glass look."""
    parameters = resolve_scene_quality(settings, cfg, defaults, motion_blur=True, motion_trails=True)
    parameters["edge_glass"] = require_transition_settings("blockspin").admit("edge_glass", cfg, defaults)
    return parameters


def _spec_inputs(
    section: str,
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> tuple[TransitionSettings, Mapping[str, object], Mapping[str, object], object]:
    """A spec'd transition's spec, persisted section, canonical section and resolved direction
    (None when the page offers no Direction)."""

    spec = require_transition_settings(section)
    cfg = _mapping(settings, section)
    defaults = _canonical(section)
    direction = None
    if spec.directions is not None:
        direction = spec.directions.resolve(_value(cfg, defaults, "direction"), rng)
    return spec, cfg, defaults, direction


def _colour(spec: TransitionSettings, cfg: Mapping[str, object], defaults: Mapping[str, object],
            name: str = "color") -> tuple[float, float, float]:
    color = _normalized_glow_color(_value(cfg, defaults, name), defaults[name], field_name=name)
    return tuple(min(1.0, channel) for channel in color[:3])


def _resolve_glass_shatter(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    spec, cfg, defaults, direction = _spec_inputs("glass_shatter", settings, rng)
    return _finish(direction, {"seed": _seed(rng), **spec.page_values(cfg, defaults),
                               **resolve_scene_quality(settings, cfg, defaults, motion_blur=True, motion_trails=True)})


def _resolve_exploding_tiles(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    spec, cfg, defaults, direction = _spec_inputs("exploding_tiles", settings, rng)
    return _finish(direction, {
        "seed": _seed(rng), **spec.page_values(cfg, defaults),
        **resolve_scene_quality(settings, cfg, defaults, bloom=True, motion_blur=True, motion_trails=True)})


def _resolve_pixel_accretion(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    spec, cfg, defaults, direction = _spec_inputs("pixel_accretion", settings, rng)
    return _finish(direction, {"seed": _seed(rng), **spec.page_values(cfg, defaults),
                               **resolve_scene_quality(settings, cfg, defaults, motion_blur=True, motion_trails=True)})


def _resolve_melt_drip(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    # Melt starts at an origin rather than sweeping from an edge (operator rework 2026-09-23); the
    # retired edge directions older profiles may hold pick an origin per run, as Random does.
    spec, cfg, defaults, origin = _spec_inputs("melt_drip", settings, rng)
    return _finish(origin, {"seed": _seed(rng), **spec.page_values(cfg, defaults)})


def _resolve_disintegrate(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    spec, cfg, defaults, direction = _spec_inputs("disintegrate", settings, rng)
    return _finish(direction, {"seed": _seed(rng), **spec.page_values(cfg, defaults),
                               **resolve_scene_quality(settings, cfg, defaults)})


def _resolve_beam(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    spec, cfg, defaults, direction = _spec_inputs("beam", settings, rng)
    return _finish(direction, {"seed": _seed(rng), "color": _colour(spec, cfg, defaults),
                               **spec.page_values(cfg, defaults)})


def _resolve_cube_turn(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    spec, cfg, defaults, direction = _spec_inputs("cube_turn", settings, rng)
    return _finish(direction, {**spec.page_values(cfg, defaults), **resolve_scene_quality(settings, cfg, defaults)})


def _resolve_page_curl(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    # The direction is where the page starts to peel: a corner or an edge.
    spec, cfg, defaults, origin = _spec_inputs("page_curl", settings, rng)
    return _finish(origin, {**spec.page_values(cfg, defaults), **resolve_scene_quality(settings, cfg, defaults)})


def _resolve_jigsaw(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    # The stored "direction" is the flip order. The run itself has no direction: the order
    # travels as a parameter, so the per-run layout can be keyed (and warmed) from parameters.
    spec, cfg, defaults, order = _spec_inputs("jigsaw", settings, rng)
    return _finish(None, {"seed": _seed(rng), "order": order, **spec.page_values(cfg, defaults),
                          **resolve_scene_quality(settings, cfg, defaults)})


def _resolve_volumetric_dissolve(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    spec, cfg, defaults, direction = _spec_inputs("volumetric_dissolve", settings, rng)
    return _finish(direction, {"seed": _seed(rng), **spec.page_values(cfg, defaults),
                               **resolve_scene_quality(settings, cfg, defaults)})


def _resolve_vhs(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    spec, cfg, defaults, direction = _spec_inputs("vhs", settings, rng)
    return _finish(direction, {"seed": _seed(rng), **spec.page_values(cfg, defaults)})


def _resolve_edge_bloom(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    spec, cfg, defaults, _direction = _spec_inputs("edge_bloom", settings, rng)
    return _finish(None, {
        "seed": _seed(rng),
        "color": _colour(spec, cfg, defaults),
        "color_source": EDGE_BLOOM_COLOUR_SOURCES[spec.admit("color_source", cfg, defaults)],
        **spec.page_values(cfg, defaults),
    })


def _resolve_liquid_lens(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    # The lens always starts in the middle; its seeded path replaces an origin choice.
    spec, cfg, defaults, _direction = _spec_inputs("liquid_lens", settings, rng)
    return _finish(None, {"seed": _seed(rng), **spec.page_values(cfg, defaults)})


def _resolve_membrane(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    spec, cfg, defaults, sweep = _spec_inputs("membrane", settings, rng)
    return _finish(sweep, {"seed": _seed(rng), **spec.page_values(cfg, defaults),
                           **resolve_scene_quality(settings, cfg, defaults)})


def _resolve_surface_tension(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    spec, cfg, defaults, _direction = _spec_inputs("surface_tension", settings, rng)
    return _finish(None, {"seed": _seed(rng), **spec.page_values(cfg, defaults)})


def _resolve_chromatic_shear(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    spec, cfg, defaults, axis = _spec_inputs("chromatic_shear", settings, rng)
    return _finish(axis, {"seed": _seed(rng), **spec.page_values(cfg, defaults)})


def _resolve_depth_cascade(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    spec, cfg, defaults, sweep = _spec_inputs("depth_cascade", settings, rng)
    return _finish(sweep, {"seed": _seed(rng), **spec.page_values(cfg, defaults),
                           **resolve_scene_quality(settings, cfg, defaults)})


def _resolve_capillary_bloom(settings: Mapping[str, object], rng: _RandomSource) -> ResolvedPhaseCInputs:
    spec, cfg, defaults, _direction = _spec_inputs("capillary_bloom", settings, rng)
    return _finish(None, {"seed": _seed(rng), **spec.page_values(cfg, defaults)})


_RESOLVERS = {
    "blinds": _resolve_blinds,
    "ripple": _resolve_ripple,
    "crumble": _resolve_crumble,
    "particle": _resolve_particle,
    "burn": _resolve_burn,
    "glass_shatter": _resolve_glass_shatter,
    "exploding_tiles": _resolve_exploding_tiles,
    "pixel_accretion": _resolve_pixel_accretion,
    "melt_drip": _resolve_melt_drip,
    "page_curl": _resolve_page_curl,
    "disintegrate": _resolve_disintegrate,
    "cube_turn": _resolve_cube_turn,
    "beam": _resolve_beam,
    "jigsaw": _resolve_jigsaw,
    "volumetric_dissolve": _resolve_volumetric_dissolve,
    "vhs": _resolve_vhs,
    "edge_bloom": _resolve_edge_bloom,
    "liquid_lens": _resolve_liquid_lens,
    "membrane": _resolve_membrane,
    "surface_tension": _resolve_surface_tension,
    "chromatic_shear": _resolve_chromatic_shear,
    "depth_cascade": _resolve_depth_cascade,
    "capillary_bloom": _resolve_capillary_bloom,
}


PARAMETERIZED_TRANSITION_IDS = frozenset(_RESOLVERS)


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
