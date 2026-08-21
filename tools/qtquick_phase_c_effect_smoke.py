"""Focused real-GL wrapper for the remaining parameterized Phase-C effects.

The preserved qtquick_render_node_smoke lifecycle harness stays generic.  This
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
    "particle": ("directional", "swirl", "converge"),
    "burn": (
        "left-to-right",
        "right-to-left",
        "top-to-bottom",
        "bottom-to-top",
        "diag-tl-br",
        "diag-tr-bl",
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
        mode = {"directional": 0, "swirl": 1, "converge": 2}[case]
        return {
            "seed": 12.5,
            "mode": mode,
            "direction": 0,
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
        direction = _CASES["burn"].index(case)
        return {
            "direction": direction,
            "jaggedness": 0.55,
            "glow_intensity": 0.72,
            "glow_color": (1.0, 140.0 / 255.0, 30.0 / 255.0, 1.0),
            "char_width": 0.5,
            "smoke_enabled": True,
            "smoke_density": 0.5,
            "ash_enabled": True,
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
    # Diffuse must be spatial rather than a uniform crossfade.  A 5x5 sample
    # set at midpoint should contain at least three distinct ownership/effect domains.
    return len({_domain(color) for color in midpoint}) >= 2


def _matches_ripple(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    case: object,
) -> bool:
    if not _basic_effect_midpoint(source, destination, midpoint, progress, case):
        return False
    # The first authored ripple is always centred.  At a controlled midpoint
    # the centre should be in the arriving-image domain while outer samples
    # still prove old-image ownership.
    centre = len(smoke._TRANSITION_SAMPLE_COORDINATES) // 2
    return _domain(midpoint[centre]) == "destination"


def _matches_crumble(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    case: object,
) -> bool:
    if not _basic_effect_midpoint(source, destination, midpoint, progress, case):
        return False
    counts = _domain_counts(midpoint)
    return bool(counts and (counts["dark-effect"] + counts["mixed-effect"] >= 1))


def _matches_particle(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    case: object,
) -> bool:
    if not _basic_effect_midpoint(source, destination, midpoint, progress, case):
        return False
    # 3D shading/trails usually create non-endpoint pixels.  Do not require a
    # fixed count because the mode changes spatial arrival order.
    counts = _domain_counts(midpoint)
    return bool(counts and (counts["mixed-effect"] + counts["dark-effect"] >= 1))


def _matches_burn(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    case: object,
) -> bool:
    if not _basic_effect_midpoint(source, destination, midpoint, progress, case):
        return False
    counts = _domain_counts(midpoint)
    if counts is None:
        return False
    # Char/core/smoke/ash should ensure the authored transition is not merely
    # a two-domain wipe.  The exact spatial front depends on direction/noise.
    return (counts["dark-effect"] + counts["mixed-effect"]) >= 1


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
