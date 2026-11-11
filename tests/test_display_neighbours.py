"""Which display lies to the left and to the right of another (plan 1B.12, relative form; ``core.display_neighbours``).

The Visualizer's full-display glyphs offer the display to the left and to the right of the Visualizer's own display.
Left and right come from the displays' arrangement on the virtual desktop, never their index: every arrangement here
is built from geometry in the test, and the keys are deliberately not in left-to-right order. The expected neighbour
is read off the arrangement as built (the one placed beside it), never a pinned index.
"""
from __future__ import annotations

import itertools

import pytest

from core.display_neighbours import neighbour_on_side, side_neighbours

FHD, QHD, UHD = (1920, 1080), (2560, 1440), (3840, 2160)


def _row(*sizes, y: float = 0.0, x: float = 0.0, keys=None):
    """Displays placed left to right, edge to edge (each a (key, rect)); keys default to the reverse order."""
    keys = list(keys) if keys is not None else list(reversed(range(len(sizes))))
    placed = []
    for key, (width, height) in zip(keys, sizes):
        placed.append((key, (x, y, float(width), float(height))))
        x += width
    return placed


def _scaled(native_x: float, native_y: float, native: tuple[int, int], scale: float):
    """A display's device-independent rect as Qt reports it under per-monitor scaling: the native origin, the size
    divided by the scale (so a scaled display leaves a gap to the display that touches it natively)."""
    return (native_x, native_y, round(native[0] / scale), round(native[1] / scale))


def _neighbours(placed, key):
    rects = dict(placed)
    return side_neighbours(rects[key], {other: rect for other, rect in placed if other != key})


def test_one_display_has_no_side_neighbours():
    placed = _row(QHD)
    assert _neighbours(placed, placed[0][0]) == (None, None)


@pytest.mark.parametrize("sizes", [(FHD, FHD), (QHD, FHD), (FHD, UHD)])
def test_two_side_by_side_offer_right_from_the_left_one_and_left_from_the_right_one(sizes):
    (left_key, _l), (right_key, _r) = placed = _row(*sizes)
    assert _neighbours(placed, left_key) == (None, right_key)
    assert _neighbours(placed, right_key) == (left_key, None)


@pytest.mark.parametrize("keys", list(itertools.permutations(range(3))))
def test_three_in_a_row_from_each_display(keys):
    """Every key order: the left end offers right only, the middle both, the right end left only."""
    placed = _row(FHD, QHD, FHD, keys=keys)
    (a, _), (b, _), (c, _) = placed
    assert _neighbours(placed, a) == (None, b)
    assert _neighbours(placed, b) == (a, c)
    assert _neighbours(placed, c) == (b, None)


@pytest.mark.parametrize("top,bottom,offset", [
    (FHD, FHD, 0), (QHD, FHD, 0), (FHD, QHD, 300), (UHD, FHD, -900),
])
def test_a_vertical_stack_has_no_side_neighbours(top, bottom, offset):
    """Stacked displays overlap horizontally (offset or of different widths): each is above or below, never beside."""
    placed = [(0, (float(offset), -float(top[1]), float(top[0]), float(top[1]))),
              (1, (0.0, 0.0, float(bottom[0]), float(bottom[1])))]
    assert _neighbours(placed, 0) == (None, None)
    assert _neighbours(placed, 1) == (None, None)


def test_a_display_offset_up_or_down_beside_the_source_is_its_side_neighbour():
    """Beside it with only part of its height shared (offset, different heights): still left / right."""
    source = (0.0, 0.0, 2560.0, 1440.0)
    right_lower = (2560.0, 900.0, 1920.0, 1080.0)      # shares 540 px of the source's height
    left_higher = (-1920.0, -700.0, 1920.0, 1080.0)    # shares 380 px
    assert side_neighbours(source, {"r": right_lower, "l": left_higher}) == ("l", "r")


def test_a_diagonal_display_counts_only_when_nothing_on_that_side_shares_the_height():
    """Touching only at a corner (wholly above or below): it is on that side, but a display beside the source wins
    even when it is farther away."""
    source = (0.0, 0.0, 1920.0, 1080.0)
    corner = (1920.0, 1080.0, 1920.0, 1080.0)          # below-right, corner to corner
    assert side_neighbours(source, {"corner": corner}) == (None, "corner")
    beside_far = (2600.0, 200.0, 1920.0, 1080.0)       # beside it, past a gap
    assert neighbour_on_side(source, {"corner": corner, "beside": beside_far}, 1) == "beside"


def test_the_nearest_display_on_a_side_is_offered():
    source = (0.0, 0.0, 1920.0, 1080.0)
    near = (1920.0, 0.0, 1920.0, 1080.0)
    far = (3840.0, 0.0, 1920.0, 1080.0)
    assert neighbour_on_side(source, {"far": far, "near": near}, 1) == "near"


def test_two_stacked_displays_on_one_side_offer_the_one_closer_to_the_sources_middle():
    source = (0.0, 0.0, 2560.0, 1440.0)
    upper = (2560.0, -500.0, 1920.0, 1080.0)           # both share part of the source's height, at no gap
    lower = (2560.0, 580.0, 1920.0, 1080.0)
    source_mid = source[1] + source[3] / 2
    distances = {key: abs(rect[1] + rect[3] / 2 - source_mid) for key, rect in (("upper", upper), ("lower", lower))}
    expected = min(distances, key=distances.get)
    assert neighbour_on_side(source, {"upper": upper, "lower": lower}, 1) == expected


def test_an_exact_tie_takes_the_lowest_key():
    source = (0.0, 0.0, 1920.0, 1080.0)
    upper = (1920.0, -540.0, 1920.0, 1080.0)
    lower = (1920.0, 540.0, 1920.0, 1080.0)            # mirror images about the source's middle
    assert neighbour_on_side(source, {5: lower, 2: upper}, 1) == 2
    assert neighbour_on_side(source, {2: lower, 5: upper}, 1) == 2


def test_mixed_scaling_gaps_keep_the_arrangement():
    """Qt keeps native origins and scales sizes: a 150% display leaves a gap to the one it touches natively; the row
    still reads left to right."""
    left = _scaled(-3840, 0, UHD, 1.5)                 # 3840 native wide at 150%: 2560 logical, gap of 1280
    middle = _scaled(0, 0, QHD, 1.25)
    right = _scaled(2560, 0, FHD, 1.0)
    placed = [(1, left), (0, middle), (2, right)]
    assert _neighbours(placed, 0) == (1, 2)
    assert _neighbours(placed, 1) == (None, 0)
    assert _neighbours(placed, 2) == (0, None)


def test_invalid_rectangles_are_ignored():
    source = (0.0, 0.0, 1920.0, 1080.0)
    assert side_neighbours(source, {"empty": (1920.0, 0.0, 0.0, 1080.0)}) == (None, None)
    assert side_neighbours((0.0, 0.0, 0.0, 0.0), {"r": (1920.0, 0.0, 1920.0, 1080.0)}) == (None, None)
