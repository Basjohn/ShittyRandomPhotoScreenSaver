"""Which display lies to the left and to the right of another, from the displays' physical arrangement.

The Visualizer card's full-display glyphs (plan 1B.12, relative form) offer "full display on the display to the left"
and "... to the right" of the display the Visualizer is on. Left and right come from where the displays sit on the
virtual desktop, never from their index. The rule is pure (rectangles in, keys out) so the glyph row's publication and
the press resolve through the same function. Edit's display-hop arrows (and the hover transfer options that project
them, ``QuickCustomLayoutOwner._adjacent_binding_for_identity``) use the same rule: one left/right for displays.

Rectangles are ``(x, y, width, height)`` in the virtual desktop's device-independent coordinates (``QScreen.geometry``
as each display unit's ``display_identity.geometry`` carries it). With mixed scaling Qt keeps every display's native
origin and scales only its size, so logical rectangles never overlap; they may leave a gap between displays that touch
natively. Gaps change nothing below (only order and overlap are compared).

The rule:

* **Side.** A display is on the right of the source when its left edge is at or past the source's right edge, and on
  the left when its right edge is at or before the source's left edge (``EDGE_SLACK`` absorbs a rounded pixel). A
  display whose horizontal range overlaps the source's is on neither side: it is above or below (a vertical stack
  offers no side neighbours, even when the stacked displays are offset or of different widths).
* **Overlapping vertical ranges first.** Among the displays on a side, one that shares some of the source's vertical
  range (it sits beside the source, even when offset up or down) is preferred to one that does not (a display that
  is only diagonal: its whole height is above or below the source, touching at most at a corner). A diagonal display
  still counts when nothing on that side shares the source's height.
* **Nearest.** Then the smallest horizontal gap (the distance between the facing edges), then the smallest distance
  between the vertical centres.
* **Ties.** Then the lowest key (the display manager uses the screen index), so the choice is deterministic.

Only one display per side is offered. A display that is reachable only past another one (three or more in a row) is
reached by moving to the nearer one first.
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from typing import TypeVar

#: (x, y, width, height) in the virtual desktop's device-independent coordinates.
Rect = tuple[float, float, float, float]

K = TypeVar("K", bound=Hashable)

#: Horizontal overlap still read as "beside" (a rounded logical pixel); anything more is above or below.
EDGE_SLACK = 1.0


def _valid(rect: Rect | None) -> bool:
    try:
        return rect is not None and float(rect[2]) > 0.0 and float(rect[3]) > 0.0
    except (TypeError, IndexError, ValueError):
        return False


def neighbour_on_side(source: Rect, others: Mapping[K, Rect], side: int) -> K | None:
    """The key of the nearest display on ``side`` (-1 left, +1 right) of ``source``, or None (see the module rule).

    ``others`` maps each candidate's key to its rectangle; an entry equal to ``source`` by key is the caller's to
    leave out. Invalid rectangles (no area) are ignored.
    """

    if side not in (-1, 1) or not _valid(source):
        return None
    sx, sy, sw, sh = (float(value) for value in source)
    s_right, s_bottom, s_mid_y = sx + sw, sy + sh, sy + sh / 2.0
    ranked: list[tuple[tuple[int, float, float], K]] = []
    for key, rect in others.items():
        if not _valid(rect):
            continue
        cx, cy, cw, ch = (float(value) for value in rect)
        if side > 0:
            gap = cx - s_right
        else:
            gap = sx - (cx + cw)
        if gap < -EDGE_SLACK:
            continue                                   # overlaps the source horizontally: above or below it
        shares_height = min(s_bottom, cy + ch) - max(sy, cy) > 0.0
        ranked.append(((0 if shares_height else 1, max(0.0, gap), abs((cy + ch / 2.0) - s_mid_y)), key))
    if not ranked:
        return None
    try:
        ranked.sort(key=lambda entry: (entry[0], entry[1]))
    except TypeError:                                  # keys that do not order: the rank alone, in insertion order
        ranked.sort(key=lambda entry: entry[0])
    return ranked[0][1]


def side_neighbours(source: Rect, others: Mapping[K, Rect]) -> tuple[K | None, K | None]:
    """``(left, right)``: the keys of the displays to the left and to the right of ``source`` (None: no display)."""

    return neighbour_on_side(source, others, -1), neighbour_on_side(source, others, 1)


__all__ = ["EDGE_SLACK", "Rect", "neighbour_on_side", "side_neighbours"]
