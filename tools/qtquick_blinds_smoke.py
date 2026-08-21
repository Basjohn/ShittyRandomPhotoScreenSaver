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


def _blinds_mix_factor(
    direction: object,
    progress: float,
    coordinate: tuple[float, float],
) -> float | None:
    x, y = coordinate
    direction_text = str(direction)
    cols, rows = _GRID
    if direction_text == "horizontal":
        coord = (x * cols) % 1.0
    elif direction_text == "vertical":
        coord = (y * rows) % 1.0
    elif direction_text == "diagonal":
        bands = (cols + rows) * 0.5
        coord = (((x + y) * 0.5) * bands) % 1.0
    else:
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


def _matches_blinds_samples(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    direction: object,
    *,
    tolerance: int = 6,
) -> bool:
    if not all(
        isinstance(value, (tuple, list))
        for value in (source, destination, midpoint)
    ):
        return False
    if (
        not source
        or len(source) != len(destination)
        or len(source) != len(midpoint)
        or len(midpoint) != len(smoke._TRANSITION_SAMPLE_COORDINATES)
        or not 0.20 <= float(progress) <= 0.80
    ):
        return False

    compared = 0
    source_weighted = 0
    destination_weighted = 0
    for old_color, new_color, actual_color, coordinate in zip(
        source,
        destination,
        midpoint,
        smoke._TRANSITION_SAMPLE_COORDINATES,
        strict=True,
    ):
        factor = _blinds_mix_factor(direction, progress, coordinate)
        if factor is None:
            return False
        old = smoke._argb_components(old_color)
        new = smoke._argb_components(new_color)
        actual = smoke._argb_components(actual_color)
        expected = tuple(
            round(old_channel * (1.0 - factor) + new_channel * factor)
            for old_channel, new_channel in zip(old, new, strict=True)
        )
        if any(
            abs(observed - target) > tolerance
            for observed, target in zip(actual, expected, strict=True)
        ):
            return False
        compared += 1
        source_weighted += int(factor <= 0.20)
        destination_weighted += int(factor >= 0.80)

    return bool(
        compared == len(smoke._TRANSITION_SAMPLE_COORDINATES)
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
