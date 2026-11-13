"""The Visualizer card's clip contract (plan 1C.4, R-188, R-191) read off rendered frames: one reading for every
renderer that composites into the card.

Callers: ``tests/test_visualizer_card_clip_contract.py`` (the Python render node in the production scene) and
``native/core/python/composite_check.py`` (the native core's composite, N2.4, on every backend). Each renders the same
card three ways and hands the frames here (top-down RGBA, numpy):

* ``drawn``: as drawn;
* ``white``: with bright content touching every edge and corner of the card (white lines along the edges, or an
  all-white surface);
* ``hidden``: the same scene, chrome and frame with the Visualizer content hidden.

Against the hidden read:

* every pixel whose centre lies more than ``OUTSIDE_PX`` device pixel outside the card's inner edge (the rounded inner
  path the card draws: the card where the scene put it, inset by the frame as Qt draws it, so the corners are
  included) is unchanged in both reads;
* along the straight edges, every pixel the card frame covers at all is unchanged in both reads (content under the
  frame's blended edge pixel shows through it and reads as the content reaching into the border);
* in the corners, where Qt anti-aliases the frame's inner arc against whatever lies beneath it, content lies only
  under pixels the frame covers by at most ``CORNER_BLEND``;
* the white content touches the frame on all four sides: no card surface shows between the frame's last pixel and the
  content (no seam).

Each within ``TOLERANCE`` levels per channel, the run-to-run floor. The frame is recognised by its colour in the hidden
read: a half-transparent green border (``border_alpha``) over a surface that is neither green.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

TOLERANCE = 2              # 8-bit levels per channel
OUTSIDE_PX = 0.71          # a pixel whose centre lies this far out has no footprint inside the inner edge
CORNER_BLEND = 0.5         # the most frame coverage a corner pixel with content under it may have (the arc's own AA)
OFF_GRID = 0.3             # logical offset of the card's origin: its edges fall inside device pixels at every DPR
# The card the contract is read on (test-owned chrome, handed to the canonical resolver as the display owner does): a
# non-default width and a half-transparent border, so content drawn under the border band would show through it and
# count, not hide beneath an opaque frame.
CONTRACT_CARD = {
    "border_width": 5.0, "corner_radius": 8.0, "content_inset": 0.0,
    "background_color": (0, 0, 0, 255), "border_color": (0, 255, 0, 128),
    "shadow_enabled": False, "shadow_color": (0, 0, 0, 0), "shadow_blur": 0.0,
    "shadow_offset": (0.0, 0.0), "shadow_spread": 0.0, "shadow_extensions": (0.0, 0.0, 0.0, 0.0),
}


def inner_path(card_rect: Sequence[float], presentation: Any, dpr: float):
    """The card's rounded inner path as the scene draws it: the card's geometry (``card_rect``, where the scene put
    it), inset by the frame's width as Qt Quick draws it (rounded to whole device pixels, half up); a frameless shell's
    is its content rect."""
    from core.settings.visualizer_mode_registry import VisualizerShellPolicy

    if presentation.shell_policy is not VisualizerShellPolicy.CARD:
        return tuple(presentation.content_rect), float(presentation.shell_style["inner_corner_radius"])
    x, y, w, h = (float(v) for v in card_rect)
    inset = math.floor(presentation.border_width * dpr + 0.5) / dpr
    radius = max(0.0, float(presentation.shell_style["corner_radius"]) - inset)
    return (x + inset, y + inset, w - 2 * inset, h - 2 * inset), radius


def outside_inner_edge(path, shape, dpr):
    """Device pixels lying wholly outside the card's rounded inner path."""
    import numpy

    height, width = shape
    ys, xs = numpy.mgrid[0:height, 0:width].astype(numpy.float64)
    lx, ly = (xs + 0.5) / dpr, (ys + 0.5) / dpr
    (x, y, w, h), radius = path
    radius = min(radius, w / 2.0, h / 2.0)
    qx = numpy.abs(lx - (x + w / 2.0)) - (w / 2.0 - radius)
    qy = numpy.abs(ly - (y + h / 2.0)) - (h / 2.0 - radius)
    distance = (numpy.sqrt(numpy.maximum(qx, 0.0) ** 2 + numpy.maximum(qy, 0.0) ** 2)
                + numpy.minimum(numpy.maximum(qx, qy), 0.0) - radius)
    return distance * dpr > OUTSIDE_PX


def frame_coverage(hidden, border_alpha: float):
    """How much of each pixel the card frame covers: its half-transparent green over the surface (neither green)."""
    import numpy

    rgb = hidden[..., :3].astype(int)
    return (rgb[..., 1] - numpy.maximum(rgb[..., 0], rgb[..., 2])) / float(border_alpha)


def frame_pixels(hidden, border_alpha: float):
    """Pixels the card frame covers at all."""
    return frame_coverage(hidden, border_alpha) * border_alpha > TOLERANCE


def corner_zones(card_rect, corner_radius, shape, dpr):
    """Device pixels in the four corner squares of the card (the arc and a pixel either side of where it meets an edge)."""
    import numpy

    zones = numpy.zeros(shape, bool)
    x, y, w, h = card_rect
    reach = int(corner_radius * dpr) + 2
    left, top = int(x * dpr) - 1, int(y * dpr) - 1
    right, bottom = int((x + w) * dpr) + 1, int((y + h) * dpr) + 1
    for x0, y0 in ((left, top), (right - reach, top), (left, bottom - reach), (right - reach, bottom - reach)):
        zones[max(0, y0):max(0, y0 + reach), max(0, x0):max(0, x0 + reach)] = True
    return zones


def surface_gaps(frame, white, card_rect, dpr):
    """Device pixels of card surface between the frame's last pixel and the white line, on each side (middle row/col)."""
    import numpy

    ox, oy, ow, oh = card_rect
    height, width = frame.shape
    row, col = int((oy + oh / 2.0) * dpr), int((ox + ow / 2.0) * dpr)
    left, right = max(0, int(ox * dpr) - 2), min(width, int((ox + ow) * dpr) + 3)
    top, bottom = max(0, int(oy * dpr) - 2), min(height, int((oy + oh) * dpr) + 3)
    gaps = {}
    for side, (frame_line, white_line) in {
        # From outside the card's edge to its middle.
        "left": (frame[row, left:col], white[row, left:col]),
        "right": (frame[row, col:right][::-1], white[row, col:right][::-1]),
        "top": (frame[top:row, col], white[top:row, col]),
        "bottom": (frame[row:bottom, col][::-1], white[row:bottom, col][::-1]),
    }.items():
        hits = numpy.flatnonzero(frame_line)
        if hits.size == 0:
            gaps[side] = None
            continue
        breaks = numpy.flatnonzero(numpy.diff(hits) > 1)
        frame_end = int(hits[breaks[0]] if breaks.size else hits[-1])
        first_white = numpy.flatnonzero(white_line[frame_end + 1:])
        gaps[side] = int(first_white[0]) if first_white.size else None
    return gaps


def changed(read, hidden):
    """Pixels a read changes against the hidden read (beyond the run-to-run floor)."""
    import numpy

    return numpy.abs(read[..., :3].astype(int) - hidden[..., :3].astype(int)).max(axis=2) > TOLERANCE


@dataclass(frozen=True)
class ContractReading:
    """``escapes``: changed pixels outside the inner edge (both reads); ``lit``: pixels the drawn read changes inside
    it (zero means the check was vacuous); ``under_frame``: changed pixels the frame covers (both reads; None for a
    frameless shell); ``gaps``: card surface between the frame and the white content per side (None without a
    frame)."""

    escapes: int
    lit: int
    under_frame: int | None
    gaps: dict | None


def read_contract(drawn, white, hidden, *, card_rect: Sequence[float], presentation: Any, dpr: float,
                  border_alpha: float) -> ContractReading:
    """The contract's reading of one card (the module docstring has the rules)."""
    from core.settings.visualizer_mode_registry import VisualizerShellPolicy

    drawn_changed, white_changed = changed(drawn, hidden), changed(white, hidden)
    outside = outside_inner_edge(inner_path(card_rect, presentation, dpr), drawn_changed.shape, dpr)
    escapes = int((drawn_changed & outside).sum() + (white_changed & outside).sum())
    lit = int((drawn_changed & ~outside).sum())
    under_frame = gaps = None
    if presentation.shell_policy is VisualizerShellPolicy.CARD:
        frame = frame_pixels(hidden, border_alpha)
        corners = corner_zones(tuple(card_rect), float(presentation.shell_style["corner_radius"]), frame.shape, dpr)
        # Straight edges: no content under any frame pixel. Corners: only under the arc's own blend.
        forbidden = (frame & ~corners) | (corners & (frame_coverage(hidden, border_alpha) > CORNER_BLEND))
        under_frame = int((drawn_changed & forbidden).sum() + (white_changed & forbidden).sum())
        if presentation.border_width > 0.0:
            # A frame to meet (Hide Borders has none: its coverage is the display, checked above).
            gaps = surface_gaps(frame, white_changed, tuple(card_rect), dpr)
    return ContractReading(escapes, lit, under_frame, gaps)


__all__ = ["CONTRACT_CARD", "CORNER_BLEND", "ContractReading", "OFF_GRID", "OUTSIDE_PX", "TOLERANCE", "changed",
           "corner_zones", "frame_coverage", "frame_pixels", "inner_path", "outside_inner_edge", "read_contract",
           "surface_gaps"]
