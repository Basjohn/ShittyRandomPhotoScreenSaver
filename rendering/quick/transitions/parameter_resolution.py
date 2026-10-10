"""Pure Settings-to-request resolution for parameterized Quick effects.

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

from core.settings.default_contract import require_canonical_default
from rendering.gl_programs.accordion_fold_options import ACCORDION_EDGES, ACCORDION_PLEATS_RANGE
from rendering.gl_programs.blinds_options import BLINDS_SLATS_RANGE, BLINDS_STYLE_CHOICES, BLINDS_STYLE_CODES
from rendering.gl_programs.blockspin_options import BLOCK_SPIN_EDGE_GLASS_CHOICES
from rendering.gl_programs.cube_turn_options import CUBE_TURN_DIRECTIONS
from rendering.gl_programs.jigsaw_options import JIGSAW_ORDERS, JIGSAW_PIECES_RANGE
from rendering.gl_programs.vhs_options import VHS_DIRECTIONS
from rendering.gl_programs.volumetric_dissolve_options import VOLUMETRIC_DIRECTIONS, VOLUMETRIC_PARTICLE_SIZE_RANGE
from rendering.gl_programs.page_curl_options import PAGE_CURL_ORIGINS
from rendering.gl_programs.scene3d import (
    SCENE3D_ANTIALIASING_CHOICES,
    SCENE3D_TRAIL_CHOICES,
    SCENE3D_DETAIL_NAMES,
    SCENE3D_EFFECT_CHOICES,
    scene3d_detail,
    scene3d_post_effect,
    scene3d_samples,
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


# A Settings label names the way the motion travels, and so does the resolved code:
# "Left to Right" is ``right``.
_DIRECTION_MAP = {
    "Left to Right": "right",
    "Right to Left": "left",
    "Top to Bottom": "down",
    "Bottom to Top": "up",
    "Diagonal TL-BR": "diag_tl_br",
    "Diagonal TR-BL": "diag_tr_bl",
    "Diagonal TL to BR": "diag_tl_br",
    "Diagonal TR to BL": "diag_tr_bl",
}


def _resolve_direction(
    raw: object,
    *,
    choices: tuple[str, ...],
    mapping: Mapping[str, str],
    rng: _RandomSource,
) -> str:
    text = str(raw or "Random")
    if text == "Random":
        return str(rng.choice(choices))
    resolved = mapping.get(text)
    if resolved is None:
        raise ValueError(f"unknown transition direction: {raw!r}")
    return resolved


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
    style = BLINDS_STYLE_CODES[_scene_choice(cfg, defaults, "style", BLINDS_STYLE_CHOICES)]
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
    low, high = BLINDS_SLATS_RANGE
    return _finish(direction, {
        "feather": feather, "style": style,
        "slats": max(low, min(high, _integer(_value(cfg, defaults, "slats"), int(defaults["slats"])))),
        **_surface_values(cfg, defaults, ("gloss",)),
        **resolve_scene_quality(settings, cfg, defaults),
    })


def _resolve_diffuse(
    settings: Mapping[str, object],
    _rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "diffuse")
    defaults = _canonical("diffuse")
    default_block_size = max(1, int(defaults["block_size"]))
    block_size = max(
        1,
        _integer(
            _value(cfg, defaults, "block_size"),
            default_block_size,
        ),
    )
    default_shape = str(defaults["shape"])
    shape = str(_value(cfg, defaults, "shape") or default_shape).strip().lower()
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
    default_count = int(defaults["ripple_count"])
    count = max(
        1,
        min(
            8,
            _integer(
                _value(cfg, defaults, "ripple_count"),
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
    default_pieces = max(4, int(defaults["piece_count"]))
    piece_count = max(
        4,
        _integer(
            _value(cfg, defaults, "piece_count"),
            default_pieces,
        ),
    )
    piece_count = min(128, piece_count)
    default_complexity = float(defaults["crack_complexity"])
    complexity = max(
        0.5,
        min(
            2.0,
            _number(
                _value(cfg, defaults, "crack_complexity"),
                default_complexity,
            ),
        ),
    )
    default_weighting = str(defaults["weighting"])
    weighting = str(_value(cfg, defaults, "weighting") or default_weighting)
    # Former Bias labels both executed Top Weighted. The Settings page writes
    # the actual release-order label when it next saves an existing profile.
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
            "depth": max(.2, min(1.5, _number(_value(cfg, defaults, "depth"), float(defaults["depth"])))),
            **_surface_values(cfg, defaults, ("thickness", "debris")),
            "weight_mode": weight_mode,
            "collisions": _bool(_value(cfg, defaults, "collisions"), bool(defaults["collisions"])),
            **resolve_scene_quality(settings, cfg, defaults, motion_blur=True, motion_trails=True),
        },
    )


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


_FRACTURE_DIRECTION_MAP = {
    **_DIRECTION_MAP,
    "Center Out": "center_out",
    "center_out": "center_out",
    "left": "left",
    "right": "right",
    "up": "up",
    "down": "down",
    "diag_tl_br": "diag_tl_br",
    "diag_tr_bl": "diag_tr_bl",
}
_FRACTURE_DIRECTIONS = (
    "left",
    "right",
    "up",
    "down",
    "diag_tl_br",
    "diag_tr_bl",
    "center_out",
)
_PIXEL_DIRECTION_MAP = {
    **_FRACTURE_DIRECTION_MAP,
    "Diagonal BL-TR": "diag_bl_tr",
    "Diagonal BR-TL": "diag_br_tl",
    "diag_bl_tr": "diag_bl_tr",
    "diag_br_tl": "diag_br_tl",
}
_PIXEL_DIRECTIONS = (
    "left",
    "right",
    "up",
    "down",
    "diag_tl_br",
    "diag_tr_bl",
    "diag_bl_tr",
    "diag_br_tl",
)



def _seed(rng: _RandomSource) -> int:
    """Generate one deterministic per-request seed; it is never persisted."""

    return int(rng.randint(1, 65535))


def _resolve_detail(
    cfg: Mapping[str, object],
    defaults: Mapping[str, object],
) -> float:
    default_detail = float(defaults["detail"])
    return max(0.5, min(2.0, _number(_value(cfg, defaults, "detail"), default_detail)))


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
    parameters["edge_glass"] = _scene_choice(cfg, defaults, "edge_glass", BLOCK_SPIN_EDGE_GLASS_CHOICES)
    return parameters


def _surface_values(cfg: Mapping[str, object], defaults: Mapping[str, object],
                    names: tuple[str, ...]) -> dict[str, float]:
    return {name: max(0.0, min(1.0, _number(_value(cfg, defaults, name), float(defaults[name]))))
            for name in names}


def _resolve_glass_shatter(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "glass_shatter")
    defaults = _canonical("glass_shatter")
    direction = _resolve_direction(
        _value(cfg, defaults, "direction"),
        choices=_FRACTURE_DIRECTIONS,
        mapping=_FRACTURE_DIRECTION_MAP,
        rng=rng,
    )
    default_shards = int(defaults["shards"])
    default_depth = float(defaults["depth"])
    shards = max(24, min(180, _integer(_value(cfg, defaults, "shards"), default_shards)))
    depth = max(0.2, min(1.5, _number(_value(cfg, defaults, "depth"), default_depth)))
    return _finish(direction, {"seed": _seed(rng), "shards": shards, "depth": depth,
                               "collisions": _bool(_value(cfg, defaults, "collisions"), bool(defaults["collisions"])),
                               "reshatter": _bool(_value(cfg, defaults, "reshatter"), bool(defaults["reshatter"])),
                               **_surface_values(cfg, defaults, ("thickness", "transparency", "refraction", "dispersion", "sheen")),
                               **resolve_scene_quality(settings, cfg, defaults, motion_blur=True, motion_trails=True)})


def _resolve_exploding_tiles(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "exploding_tiles")
    defaults = _canonical("exploding_tiles")
    direction = _resolve_direction(
        _value(cfg, defaults, "direction"),
        choices=_FRACTURE_DIRECTIONS,
        mapping=_FRACTURE_DIRECTION_MAP,
        rng=rng,
    )
    default_columns = int(defaults["columns"])
    default_depth = float(defaults["depth"])
    columns = max(6, min(48, _integer(_value(cfg, defaults, "columns"), default_columns)))
    depth = max(0.2, min(1.5, _number(_value(cfg, defaults, "depth"), default_depth)))
    return _finish(
        direction,
        {"seed": _seed(rng), "columns": columns, "depth": depth,
         **_surface_values(cfg, defaults, ("thickness",)),
         "force": max(.5, min(2., _number(_value(cfg, defaults, "force"), float(defaults["force"])))),
         **resolve_scene_quality(settings, cfg, defaults, bloom=True, motion_blur=True, motion_trails=True)},
    )


def _resolve_pixel_accretion(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "pixel_accretion")
    defaults = _canonical("pixel_accretion")
    direction = _resolve_direction(
        _value(cfg, defaults, "direction"),
        choices=_PIXEL_DIRECTIONS,
        mapping=_PIXEL_DIRECTION_MAP,
        rng=rng,
    )
    default_tile_size = int(defaults["tile_size"])
    default_travel = float(defaults["travel"])
    tile_size = max(4, min(32, _integer(_value(cfg, defaults, "tile_size"), default_tile_size)))
    travel = max(0.1, min(1.0, _number(_value(cfg, defaults, "travel"), default_travel)))
    return _finish(
        direction,
        {"seed": _seed(rng), "tile_size": tile_size, "travel": travel,
         **resolve_scene_quality(settings, cfg, defaults, motion_blur=True, motion_trails=True)},
    )


def _resolve_organic(
    transition_id: str,
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, transition_id)
    defaults = _canonical(transition_id)
    return _finish(
        None,
        {"seed": _seed(rng), "detail": _resolve_detail(cfg, defaults),
         **_surface_values(cfg, defaults, ("depth", "gloss"))},
    )


# Melt starts at an origin rather than sweeping from an edge (operator rework
# 2026-09-23). The Settings label maps to the resolved origin code.
MELT_ORIGIN_LABELS = {
    "Top Left": "top_left",
    "Top Center": "top_center",
    "Top Right": "top_right",
    "Center Out": "center_out",
    "Center In": "center_in",
}
_MELT_ORIGIN_CHOICES = tuple(MELT_ORIGIN_LABELS.values())


def _resolve_melt_drip(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "melt_drip")
    defaults = _canonical("melt_drip")
    raw = str(_value(cfg, defaults, "direction") or "Random")
    origin = MELT_ORIGIN_LABELS.get(raw)
    if origin is None and raw in _MELT_ORIGIN_CHOICES:
        origin = raw
    if origin is None:
        # "Random", and the retired edge directions ("Top to Bottom", ...) that
        # older profiles may still hold, pick an origin per run.
        origin = str(rng.choice(_MELT_ORIGIN_CHOICES))
    return _finish(
        origin,
        {"seed": _seed(rng), "detail": _resolve_detail(cfg, defaults),
         **_surface_values(cfg, defaults, ("depth", "gloss"))},
    )


def _resolve_disintegrate(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "disintegrate")
    defaults = _canonical("disintegrate")
    direction = _resolve_direction(
        _value(cfg, defaults, "direction"),
        choices=_PIXEL_DIRECTIONS,
        mapping=_PIXEL_DIRECTION_MAP,
        rng=rng,
    )
    return _finish(direction, {
        "seed": _seed(rng),
        "grain_size": max(2, min(8, _integer(_value(cfg, defaults, "grain_size"), int(defaults["grain_size"])))),
        "wind": max(0.5, min(2.0, _number(_value(cfg, defaults, "wind"), float(defaults["wind"])))),
        **resolve_scene_quality(settings, cfg, defaults),
    })


def _resolve_accordion_fold(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "accordion_fold")
    defaults = _canonical("accordion_fold")
    edge = ACCORDION_EDGES.get(str(_value(cfg, defaults, "direction") or "Random"))
    if edge is None:
        edge = str(rng.choice(tuple(ACCORDION_EDGES.values())))
    low, high = ACCORDION_PLEATS_RANGE
    return _finish(edge, {
        "pleats": max(low, min(high, _integer(_value(cfg, defaults, "pleats"), int(defaults["pleats"])))),
        **_surface_values(cfg, defaults, ("gloss",)),
        **resolve_scene_quality(settings, cfg, defaults),
    })


def _resolve_relief_rise(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "relief_rise")
    defaults = _canonical("relief_rise")
    direction = _resolve_direction(
        _value(cfg, defaults, "direction"),
        choices=_PIXEL_DIRECTIONS,
        mapping=_PIXEL_DIRECTION_MAP,
        rng=rng,
    )
    return _finish(direction, {**_surface_values(cfg, defaults, ("depth", "gloss")),
                               **resolve_scene_quality(settings, cfg, defaults)})


def _resolve_beam(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "beam")
    defaults = _canonical("beam")
    direction = _resolve_direction(
        _value(cfg, defaults, "direction"),
        choices=_PIXEL_DIRECTIONS,
        mapping=_PIXEL_DIRECTION_MAP,
        rng=rng,
    )
    color = _normalized_glow_color(_value(cfg, defaults, "color"), defaults["color"], field_name="color")
    return _finish(direction, {
        "seed": _seed(rng),
        "color": tuple(min(1.0, channel) for channel in color[:3]),
        "sparks": _bool(_value(cfg, defaults, "sparks"), bool(defaults["sparks"])),
        **_surface_values(cfg, defaults, ("glow", "scorch", "cure")),
    })


def _resolve_cube_turn(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "cube_turn")
    defaults = _canonical("cube_turn")
    direction = CUBE_TURN_DIRECTIONS.get(str(_value(cfg, defaults, "direction") or "Random"))
    if direction is None:
        direction = str(rng.choice(tuple(CUBE_TURN_DIRECTIONS.values())))
    return _finish(direction, {**_surface_values(cfg, defaults, ("gloss",)),
                               **resolve_scene_quality(settings, cfg, defaults)})


def _resolve_page_curl(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "page_curl")
    defaults = _canonical("page_curl")
    origin = PAGE_CURL_ORIGINS.get(str(_value(cfg, defaults, "direction") or "Random"))
    if origin is None:
        # "Random" (and anything unknown) picks a corner or edge per run.
        origin = str(rng.choice(tuple(PAGE_CURL_ORIGINS.values())))
    return _finish(origin, {**_surface_values(cfg, defaults, ("gloss", "size")),
                            **resolve_scene_quality(settings, cfg, defaults)})


def _resolve_jigsaw(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "jigsaw")
    defaults = _canonical("jigsaw")
    # The stored "direction" is the flip order. The run itself has no direction: the order
    # travels as a parameter, so the per-run layout can be keyed (and warmed) from parameters.
    order = JIGSAW_ORDERS.get(str(_value(cfg, defaults, "direction") or "Random"))
    if order is None:
        order = str(rng.choice(tuple(JIGSAW_ORDERS.values())))
    low, high = JIGSAW_PIECES_RANGE
    return _finish(None, {
        "seed": _seed(rng),
        "order": order,
        "pieces": max(low, min(high, _integer(_value(cfg, defaults, "pieces"), int(defaults["pieces"])))),
        **resolve_scene_quality(settings, cfg, defaults),
    })


def _resolve_volumetric_dissolve(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "volumetric_dissolve")
    defaults = _canonical("volumetric_dissolve")
    direction = VOLUMETRIC_DIRECTIONS.get(str(_value(cfg, defaults, "direction") or "Random"))
    if direction is None:
        direction = str(rng.choice(tuple(VOLUMETRIC_DIRECTIONS.values())))
    low, high = VOLUMETRIC_PARTICLE_SIZE_RANGE
    size = max(low, min(high, _integer(_value(cfg, defaults, "particle_size"), int(defaults["particle_size"]))))
    return _finish(direction, {
        "seed": _seed(rng),
        "particle_size": size,
        **_surface_values(cfg, defaults, ("mist", "depth")),
        **resolve_scene_quality(settings, cfg, defaults),
    })


def _resolve_vhs(
    settings: Mapping[str, object],
    rng: _RandomSource,
) -> ResolvedPhaseCInputs:
    cfg = _mapping(settings, "vhs")
    defaults = _canonical("vhs")
    direction = VHS_DIRECTIONS.get(str(_value(cfg, defaults, "direction") or "Random"))
    if direction is None:
        direction = str(rng.choice(tuple(VHS_DIRECTIONS.values())))
    return _finish(direction, {
        "seed": _seed(rng),
        **_surface_values(cfg, defaults, ("tracking", "bleed", "noise")),
    })


_RESOLVERS = {
    "blinds": _resolve_blinds,
    "diffuse": _resolve_diffuse,
    "ripple": _resolve_ripple,
    "crumble": _resolve_crumble,
    "particle": _resolve_particle,
    "burn": _resolve_burn,
    "glass_shatter": _resolve_glass_shatter,
    "exploding_tiles": _resolve_exploding_tiles,
    "pixel_accretion": _resolve_pixel_accretion,
    "ink_bloom": lambda settings, rng: _resolve_organic("ink_bloom", settings, rng),
    "melt_drip": _resolve_melt_drip,
    "page_curl": _resolve_page_curl,
    "disintegrate": _resolve_disintegrate,
    "accordion_fold": _resolve_accordion_fold,
    "relief_rise": _resolve_relief_rise,
    "cube_turn": _resolve_cube_turn,
    "beam": _resolve_beam,
    "jigsaw": _resolve_jigsaw,
    "volumetric_dissolve": _resolve_volumetric_dissolve,
    "vhs": _resolve_vhs,
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
