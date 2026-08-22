"""Focused real-GL wrapper for the production Quick Blinds transition smoke.

Run one authored direction at a time.  The wrapper extends the generic
qtquick_render_node_smoke without expanding that preserved lifecycle harness
merely to admit one Phase-C transition.
"""

from __future__ import annotations

import argparse
import sys

try:
    from tools import qtquick_render_node_smoke as smoke
except ModuleNotFoundError:  # direct ``python tools/qtquick_blinds_smoke.py``
    import qtquick_render_node_smoke as smoke


_DIRECTIONS = ("horizontal", "vertical", "diagonal")
_GRID = (14.0, 8.0)  # fixed 16:9 smoke size after the generic harness resize
_FEATHER = 0.04      # canonical raw setting 2 resolved by old runtime: 2/25*0.5


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge1 <= edge0:
        return 1.0 if value >= edge1 else 0.0
    amount = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return amount * amount * (3.0 - 2.0 * amount)


def _blinds_band_coord(
    direction: object,
    coordinate: tuple[float, float],
) -> float | None:
    x, y = coordinate
    direction_text = str(direction)
    cols, rows = _GRID
    if direction_text == "horizontal":
        return (x * cols) % 1.0
    if direction_text == "vertical":
        return (y * rows) % 1.0
    if direction_text == "diagonal":
        bands = (cols + rows) * 0.5
        return (((x + y) * 0.5) * bands) % 1.0
    return None


def _blinds_mix_factor(
    direction: object,
    progress: float,
    coordinate: tuple[float, float],
) -> float | None:
    coord = _blinds_band_coord(direction, coordinate)
    if coord is None:
        return None
    t = max(0.0, min(1.0, float(progress)))
    half_width = 0.5 * t
    left = 0.5 - half_width
    right = 0.5 + half_width
    first_edge = _smoothstep(left - _FEATHER, left, coord)
    second_edge = 1.0 - _smoothstep(right, right + _FEATHER, coord)
    band_mask = max(0.0, min(1.0, first_edge * second_edge))
    tail = _smoothstep(0.96, 1.0, t)
    return max(band_mask, tail)


def _blinds_near_band_edge(
    direction: object,
    progress: float,
    coordinate: tuple[float, float],
    *,
    guard: float = _FEATHER,
) -> bool:
    """True when a sample sits within one feather of a growing band edge.

    The authored shader softens each band edge symmetrically, while the pure
    model ramps the feather only on the outside of the edge. Samples that land
    inside a feather of ``left``/``right`` are therefore genuinely ambiguous and
    are skipped, mirroring how the slide/wipe oracles skip near-boundary
    samples. Interior source/destination samples are still checked at full
    colour tolerance, which already distinguishes each authored direction.
    """

    coord = _blinds_band_coord(direction, coordinate)
    if coord is None:
        return False
    t = max(0.0, min(1.0, float(progress)))
    if _smoothstep(0.96, 1.0, t) > 0.0:
        return False
    half_width = 0.5 * t
    left = 0.5 - half_width
    right = 0.5 + half_width
    return min(abs(coord - left), abs(coord - right)) <= guard


def _matches_blinds_samples(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    direction: object,
) -> bool:
    # Source/destination fixtures are the sparse endpoint captures (used only to
    # sanity-check fixture purity); the midpoint is the dense grid so the banded
    # reveal is sampled at every phase without aliasing against the band count.
    sparse = smoke._TRANSITION_SAMPLE_COORDINATES
    dense = smoke._TRANSITION_DENSE_SAMPLE_COORDINATES
    if not all(
        isinstance(value, (tuple, list))
        for value in (source, destination, midpoint)
    ):
        return False
    if (
        len(source) != len(sparse)
        or len(destination) != len(sparse)
        or len(midpoint) != len(dense)
        or not 0.20 <= float(progress) <= 0.80
    ):
        return False
    if {smoke._slide_color_domain(color) for color in source} != {"source"}:
        return False
    if {smoke._slide_color_domain(color) for color in destination} != {"destination"}:
        return False

    compared = 0
    source_weighted = 0
    destination_weighted = 0
    for actual_color, coordinate in zip(
        midpoint,
        smoke._TRANSITION_DENSE_SAMPLE_COORDINATES,
        strict=True,
    ):
        factor = _blinds_mix_factor(direction, progress, coordinate)
        if factor is None:
            return False
        # Skip transitional / feathered-edge samples: the shader's symmetric
        # edge and the model legitimately disagree only there (mirrors the
        # slide/wipe near-boundary skip).
        if 0.20 < factor < 0.80 or _blinds_near_band_edge(direction, progress, coordinate):
            continue
        expected = "destination" if factor >= 0.80 else "source"
        observed = smoke._slide_color_domain(actual_color)
        if observed is None:
            # Ambiguous blended pixel between fixtures; do not count.
            continue
        if observed != expected:
            return False
        compared += 1
        source_weighted += int(expected == "source")
        destination_weighted += int(expected == "destination")

    # The dense grid samples every band phase, so a correct blinds midpoint
    # exposes a periodic banded mix of both domains. A plain wipe (single
    # boundary) or crossfade (all-ambiguous) cannot satisfy this banded pattern.
    return bool(
        compared >= 24
        and source_weighted >= 3
        and destination_weighted >= 3
    )


def _install_blinds_smoke_contract() -> None:
    if "blinds" not in smoke._TRANSITION_IDS:
        smoke._TRANSITION_IDS = (*smoke._TRANSITION_IDS, "blinds")
    smoke._TRANSITION_SMOKE_DIRECTIONS["blinds"] = _DIRECTIONS
    smoke._TRANSITION_DIRECTION_CHOICES = tuple(
        sorted(set(smoke._TRANSITION_DIRECTION_CHOICES) | set(_DIRECTIONS))
    )
    smoke._TRANSITION_PALETTE_RGB["blinds"] = smoke._DIRECTIONAL_PALETTE_RGB
    smoke._TRANSITION_SMOKE_PARAMETERS["blinds"] = {"feather": _FEATHER}
    smoke._TRANSITION_MIDPOINT_ORACLES["blinds"] = _matches_blinds_samples
    # The banded oracle consumes the dense midpoint grid to avoid aliasing the
    # band count against a sparse sample grid (vertical had 8 bands vs 5 rows).
    smoke._DENSE_MIDPOINT_TRANSITION_IDS.add("blinds")


def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direction", choices=_DIRECTIONS, required=True)
    parser.add_argument("--windows", type=int, choices=(1, 2), default=1)
    parser.add_argument("--output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(sys.argv[1:] if argv is None else argv)
    _install_blinds_smoke_contract()
    forwarded = [
        "--windows",
        str(args.windows),
        "--generations",
        "1",
        "--size",
        "480x270",
        "--phase-delay-ms",
        "350",
        "--transition-id",
        "blinds",
        "--transition-direction",
        args.direction,
    ]
    if args.output:
        forwarded.extend(("--output", args.output))
    return smoke.main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
