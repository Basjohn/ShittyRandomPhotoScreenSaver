"""Focused real-GL wrapper for the remaining parameterized Phase-C effects.

The preserved qtquick_render_node_smoke lifecycle harness stays generic. This
wrapper admits Diffuse, Ripple, Crumble, Particle, and Burn with deterministic
resolved request parameters plus effect-shaped midpoint pixel gates.
"""

from __future__ import annotations

import argparse
import sys

try:
    from tools import qtquick_render_node_smoke as smoke
except ModuleNotFoundError:  # direct ``python tools/qtquick_phase_c_effect_smoke.py``
    import qtquick_render_node_smoke as smoke


_PARTICLE_DIRECTIONS = {
    "left-to-right": 0,
    "right-to-left": 1,
    "top-to-bottom": 2,
    "bottom-to-top": 3,
    "diag-tl-br": 4,
    "diag-tr-bl": 5,
    "diag-bl-tr": 6,
    "diag-br-tl": 7,
    "random-direction": 8,
    "random-placement": 9,
}
_BURN_DIRECTIONS = {
    "left-to-right": 0,
    "right-to-left": 1,
    "top-to-bottom": 2,
    "bottom-to-top": 3,
    "diag-tl-br": 4,
    "diag-tr-bl": 5,
}

_CASES = {
    "diffuse": (
        "rectangle",
        "membrane",
        "lines",
        "diamonds",
        "amorph",
        "random",
    ),
    "ripple": ("count1", "count3", "count8"),
    "crumble": (
        "top",
        "bottom",
        "random-weighted",
        "random-choice",
        "age-weighted",
    ),
    "particle": (*_PARTICLE_DIRECTIONS, "swirl", "converge"),
    "burn": (
        *_BURN_DIRECTIONS,
        "no-smoke",
        "no-ash",
        "no-smoke-or-ash",
    ),
}


def _parameters(effect: str, case: str) -> dict[str, object]:
    if effect == "diffuse":
        shape_mode = _CASES["diffuse"].index(case)
        return {"block_size": 48, "shape_mode": shape_mode}
    if effect == "ripple":
        count = {"count1": 1, "count3": 3, "count8": 8}[case]
        return {"ripple_count": count, "ripple_seed": 123.5}
    if effect == "crumble":
        weight_mode = {
            "top": 0.0,
            "bottom": 1.0,
            "random-weighted": 2.0,
            "random-choice": 3.0,
            "age-weighted": 4.0,
        }[case]
        return {
            "seed": 123.25,
            "piece_count": 14,
            "crack_complexity": 1.0,
            "mosaic_mode": False,
            "weight_mode": weight_mode,
        }
    if effect == "particle":
        if case in _PARTICLE_DIRECTIONS:
            mode = 0
            direction = _PARTICLE_DIRECTIONS[case]
        else:
            mode = {"swirl": 1, "converge": 2}[case]
            direction = 0
        return {
            "seed": 12.5,
            "mode": mode,
            "direction": direction,
            "particle_radius": 16.0,
            "overlap": 4.0,
            "trail_length": 0.15,
            "trail_strength": 0.6,
            "swirl_strength": 1.0,
            "swirl_turns": 3.0,
            "use_3d_shading": True,
            "texture_mapping": True,
            "wobble": True,
            "gloss_size": 72.0,
            "light_direction": 1,
            "swirl_order": 0,
        }
    if effect == "burn":
        direction = _BURN_DIRECTIONS.get(case, 0)
        smoke_enabled = case not in {"no-smoke", "no-smoke-or-ash"}
        ash_enabled = case not in {"no-ash", "no-smoke-or-ash"}
        return {
            "direction": direction,
            "jaggedness": 0.55,
            "glow_intensity": 0.72,
            "glow_color": (1.0, 140.0 / 255.0, 30.0 / 255.0, 1.0),
            "char_width": 0.5,
            "smoke_enabled": smoke_enabled,
            "smoke_density": 0.5,
            "ash_enabled": ash_enabled,
            "ash_density": 0.5,
            "seed": 321.25,
        }
    raise ValueError(f"unknown Phase-C smoke effect: {effect}")


def _domain(color: object) -> str:
    _alpha, red, green, blue = smoke._argb_components(color)
    score = red - blue
    if score <= -12:
        return "source"
    if score >= 12:
        return "destination"
    if max(red, green, blue) <= 30:
        return "dark-effect"
    return "mixed-effect"


def _domain_counts(colors: object) -> dict[str, int] | None:
    if not isinstance(colors, (tuple, list)):
        return None
    counts = {
        "source": 0,
        "destination": 0,
        "dark-effect": 0,
        "mixed-effect": 0,
    }
    for color in colors:
        counts[_domain(color)] += 1
    return counts


def _has_effect_pixels(midpoint: object) -> bool:
    """True when at least one sample is effect-colored (dark or blended).

    A plain hard wipe/slide never produces effect-colored pixels, so requiring
    them is a discriminator against a monotonic reveal fallback.
    """

    counts = _domain_counts(midpoint)
    return bool(counts and (counts["dark-effect"] + counts["mixed-effect"]) >= 1)


def _looks_like_crossfade(midpoint: object) -> bool:
    """A uniform crossfade blends every pixel, so no pure ownership survives."""

    counts = _domain_counts(midpoint)
    return bool(
        counts is not None
        and counts["source"] == 0
        and counts["destination"] == 0
    )


def _looks_like_plain_wipe(midpoint: object) -> bool:
    """True when ownership is a monotonic single-axis reveal of pure domains.

    A plain wipe/slide shows only pure source and destination, separable by one
    of the canonical wipe axes. Effects that scatter ownership (Diffuse) or add
    effect-colored pixels (Ripple/Crumble/Particle/Burn) must not satisfy this,
    so the effect oracles can reject a generic wipe-style fallback.
    """

    if not isinstance(midpoint, (tuple, list)):
        return False
    coords = smoke._TRANSITION_SAMPLE_COORDINATES
    if len(midpoint) != len(coords):
        return False
    domains = [_domain(color) for color in midpoint]
    # A plain wipe carries no effect-colored pixels.
    if any(domain not in {"source", "destination"} for domain in domains):
        return False
    labelled = list(zip(domains, coords, strict=True))
    for axis_for in smoke._WIPE_AXES.values():
        dest_axis = [axis_for(x, y) for domain, (x, y) in labelled if domain == "destination"]
        src_axis = [axis_for(x, y) for domain, (x, y) in labelled if domain == "source"]
        if not dest_axis or not src_axis:
            # A single-domain / degenerate reveal is trivially wipe-like.
            return True
        if (
            max(dest_axis) < min(src_axis) + 1e-9
            or max(src_axis) < min(dest_axis) + 1e-9
        ):
            return True
    return False


def _basic_effect_midpoint(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    _case: object,
) -> bool:
    if not all(isinstance(value, (tuple, list)) for value in (source, destination, midpoint)):
        return False
    if (
        len(source) != len(smoke._TRANSITION_SAMPLE_COORDINATES)
        or len(destination) != len(smoke._TRANSITION_SAMPLE_COORDINATES)
        or len(midpoint) != len(smoke._TRANSITION_SAMPLE_COORDINATES)
        or not 0.20 <= float(progress) <= 0.80
    ):
        return False
    if {_domain(color) for color in source} != {"source"}:
        return False
    if {_domain(color) for color in destination} != {"destination"}:
        return False
    counts = _domain_counts(midpoint)
    if counts is None:
        return False
    return bool(
        counts["source"] >= 2
        and counts["destination"] >= 2
        and tuple(midpoint) != tuple(source)
        and tuple(midpoint) != tuple(destination)
    )


def _matches_diffuse(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    case: object,
) -> bool:
    if not _basic_effect_midpoint(source, destination, midpoint, progress, case):
        return False
    if _looks_like_crossfade(midpoint):
        return False
    # Diffuse must be spatial rather than a uniform crossfade. A 5x5 sample
    # set must contain more than one ownership/effect domain at midpoint.
    if len({_domain(color) for color in midpoint}) < 2:
        return False
    # And it must not reduce to a monotonic single-axis wipe: a scattered block
    # dissolve is either spatially non-separable or carries feathered edge
    # pixels a plain wipe never produces.
    return (not _looks_like_plain_wipe(midpoint)) or _has_effect_pixels(midpoint)


def _matches_ripple(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    case: object,
) -> bool:
    if not _basic_effect_midpoint(source, destination, midpoint, progress, case):
        return False
    if _looks_like_crossfade(midpoint):
        return False
    # The first authored ripple is always centred. At a controlled midpoint
    # the centre should be in the arriving-image domain while outer samples
    # still prove old-image ownership.
    centre = len(smoke._TRANSITION_SAMPLE_COORDINATES) // 2
    if _domain(midpoint[centre]) != "destination":
        return False
    # Radial arrival from the centre is not a monotonic linear wipe.
    return (not _looks_like_plain_wipe(midpoint)) or _has_effect_pixels(midpoint)


def _matches_crumble(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    case: object,
) -> bool:
    if not _basic_effect_midpoint(source, destination, midpoint, progress, case):
        return False
    if _looks_like_crossfade(midpoint):
        return False
    # Falling pieces and their cracks produce effect-colored pixels a plain
    # two-domain wipe never shows.
    if not _has_effect_pixels(midpoint):
        return False
    return not _looks_like_plain_wipe(midpoint)


def _matches_particle(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    case: object,
) -> bool:
    if not _basic_effect_midpoint(source, destination, midpoint, progress, case):
        return False
    if _looks_like_crossfade(midpoint):
        return False
    # 3D shading/trails create non-endpoint pixels. Do not require a fixed count
    # because direction/mode changes spatial arrival order, but a plain wipe has
    # no such pixels.
    if not _has_effect_pixels(midpoint):
        return False
    return not _looks_like_plain_wipe(midpoint)


def _matches_burn(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    case: object,
) -> bool:
    if not _basic_effect_midpoint(source, destination, midpoint, progress, case):
        return False
    if _looks_like_crossfade(midpoint):
        return False
    # Char/core survives even when smoke/ash are disabled, so every Burn case
    # remains distinguishable from a plain two-domain wipe by its effect pixels.
    if not _has_effect_pixels(midpoint):
        return False
    return not _looks_like_plain_wipe(midpoint)


_ORACLES = {
    "diffuse": _matches_diffuse,
    "ripple": _matches_ripple,
    "crumble": _matches_crumble,
    "particle": _matches_particle,
    "burn": _matches_burn,
}


def _install_contract(effect: str, case: str) -> None:
    if effect not in smoke._TRANSITION_IDS:
        smoke._TRANSITION_IDS = (*smoke._TRANSITION_IDS, effect)
    smoke._TRANSITION_SMOKE_DIRECTIONS[effect] = _CASES[effect]
    smoke._TRANSITION_DIRECTION_CHOICES = tuple(
        sorted(set(smoke._TRANSITION_DIRECTION_CHOICES) | set(_CASES[effect]))
    )
    smoke._TRANSITION_PALETTE_RGB[effect] = smoke._DIRECTIONAL_PALETTE_RGB
    smoke._TRANSITION_SMOKE_PARAMETERS[effect] = _parameters(effect, case)
    smoke._TRANSITION_SMOKE_DURATIONS_MS[effect] = 900
    smoke._TRANSITION_MIDPOINT_ORACLES[effect] = _ORACLES[effect]


def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effect", choices=tuple(_CASES), required=True)
    parser.add_argument("--case")
    parser.add_argument("--windows", type=int, choices=(1, 2), default=1)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    cases = _CASES[args.effect]
    if args.case is None:
        args.case = cases[0]
    elif args.case not in cases:
        parser.error(
            f"--case {args.case!r} is invalid for {args.effect}; "
            f"choose one of {', '.join(cases)}"
        )
    return args


def main(argv: list[str] | None = None) -> int:
    args = _arguments(sys.argv[1:] if argv is None else argv)
    _install_contract(args.effect, args.case)
    forwarded = [
        "--windows",
        str(args.windows),
        "--generations",
        "1",
        "--size",
        "480x270",
        "--phase-delay-ms",
        "500",
        "--transition-id",
        args.effect,
        "--transition-direction",
        args.case,
    ]
    if args.output:
        forwarded.extend(("--output", args.output))
    return smoke.main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
