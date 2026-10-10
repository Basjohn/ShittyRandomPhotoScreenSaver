"""Depth cards: a shared, import-safe primitive (GLSL plus CPU mirrors, no GL) for pictures split
into a few large flat cards that move in depth (Depth Card Cascade first; any layered-plate or
parallax effect can reuse it rather than building its own geometry).

* ``card_partition(seed, count, aspect)``: a guillotine partition of the picture (picture heights,
  centred, y up) into ``count`` rectangles that tile it exactly: the largest card is cut across its
  longer side, 35-65% along, until there are enough. Stable for a seed, so a run's cards never
  reshuffle between frames;
* ``CARD_GLSL`` / ``card_pose``: a card point given its offset from the card's centre, turned
  rigidly about an in-plane axis through that centre, lifted toward the viewer and slid;
* ``cardShadow`` / ``card_shadow``: where a lifted point's shadow falls on the picture plane under a
  directional light (``light`` pointing toward the light, ``z > 0``).

Cards are opaque and drawn with depth, so they need no sort; their shadows go on the picture
beneath them first.
"""

from __future__ import annotations

import math
import random

Rect = tuple[float, float, float, float]          # x0, y0, x1, y1


def card_partition(seed: int, count: int, aspect: float) -> list[Rect]:
    """``count`` rectangles tiling the picture exactly (see the module docstring)."""
    rng = random.Random(seed)
    rects: list[Rect] = [(-0.5 * aspect, -0.5, 0.5 * aspect, 0.5)]
    while len(rects) < count:
        index = max(range(len(rects)), key=lambda i: (rects[i][2] - rects[i][0]) * (rects[i][3] - rects[i][1]))
        x0, y0, x1, y1 = rects.pop(index)
        cut = rng.uniform(0.35, 0.65)
        if x1 - x0 >= y1 - y0:
            x = x0 + (x1 - x0) * cut
            rects[index:index] = [(x0, y0, x, y1), (x, y0, x1, y1)]
        else:
            y = y0 + (y1 - y0) * cut
            rects[index:index] = [(x0, y0, x1, y), (x0, y, x1, y1)]
    return rects


CARD_GLSL = """
// A card's point at offset (from the card's centre, on the plane), turned by turn about the
// in-plane unit axis through the centre, then lifted toward the viewer and slid.
vec3 cardPose(vec2 offset, vec2 centre, vec2 axis, float turn, float lift, vec2 slide) {
    vec3 v = vec3(offset, 0.0), k = vec3(axis, 0.0);
    float c = cos(turn), s = sin(turn);
    vec3 turned = v * c + cross(k, v) * s + k * dot(k, v) * (1.0 - c);
    return vec3(centre + slide, lift) + turned;
}
// Where the point's shadow lands on the picture plane, light pointing toward the light (z > 0).
vec2 cardShadow(vec3 world, vec3 light) {
    return world.xy - light.xy / light.z * world.z;
}
"""


def card_pose(offset, centre, axis, turn: float, lift: float, slide) -> tuple[float, float, float]:
    """CPU mirror of ``cardPose`` (Rodrigues' rotation)."""
    v, k = (offset[0], offset[1], 0.0), (axis[0], axis[1], 0.0)
    c, s = math.cos(turn), math.sin(turn)
    cross = (k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0])
    dot = sum(a * b for a, b in zip(k, v))
    turned = tuple(v[i] * c + cross[i] * s + k[i] * dot * (1.0 - c) for i in range(3))
    return centre[0] + slide[0] + turned[0], centre[1] + slide[1] + turned[1], lift + turned[2]


def card_shadow(world, light) -> tuple[float, float]:
    """CPU mirror of ``cardShadow``."""
    return world[0] - light[0] / light[2] * world[2], world[1] - light[1] / light[2] * world[2]
