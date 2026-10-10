"""Folded sheets: shared pleat geometry and two-sided shading for paper-like surfaces on the
bendable grid (``scene3d_grid_vertex_source``). Import-safe: GLSL text and CPU mirrors, no GL.

Proved by Accordion Fold (retired 2026-10-10) and kept for sheet and card effects (Membrane
Turnover, Depth Card Cascade). A sheet of length ``len`` along its fold axis folds into ``pleats``
equal strips alternately tilted up and down, compressing toward its edge: a point ``a`` from that
edge lies at ``a cos(fold)`` from it, as high as its distance from the nearest crease times
``sin(fold)``, so every pleat keeps its width (a fold, never a stretch). ``turn`` (0 to pi) then
rotates the folded stack over toward the viewer about its own middle, lifting clear of the plane
as it turns; at ``turn = pi`` the stack lies laid out from the far edge, ridges and valleys
swapped, which is exactly where the turned stack left it, so folding back down from there
unfolds the sheet's back side across the picture.

* ``SHEET_FOLD_GLSL`` / ``sheet_fold``: the point's (distance from the edge, height);
* ``crease_grid``: grid columns and rows putting a vertex row on every crease, so creases stay
  sharp at any 3D Detail tier (one cell across: the pleats are flat strips);
* ``SHEET_SIDES_GLSL``: which side of a two-sided sheet faces the viewer, the back's mirrored
  print, and a flat pleat face's normal from screen-space derivatives (fragment shaders only);
* ``SHEET_TWIST_GLSL`` / ``sheet_twist``: a ribbon twist (Membrane Turnover first): each
  cross-section of the sheet across an axis turns about that axis by its own angle, the axis
  rising by the sheet's half-width times ``sin(angle)`` so the turning sheet stays in front of the
  picture plane and lands back on it, back up, at ``angle = pi``. Each cross-section turns
  rigidly (its width is kept); varying the angle along the axis stretches the sheet between
  them, as a membrane would.
"""

from __future__ import annotations

import math

SHEET_FOLD_GLSL = """
// A point a from the folding edge along the fold axis: (distance from the edge, height).
// fold: the pleats' angle; turn: 0 folded front up, pi laid out from the far edge, between: turning over.
vec2 sheetFold(float a, float len, float pleats, float fold, float turn) {
    float width = len / pleats;
    float local = a - width * floor(a / width);
    float crease = min(local, width - local);
    if (turn >= 3.14159265) return vec2((len - a) * cos(fold), (0.5 * width - crease) * sin(fold));
    vec2 p = vec2(a * cos(fold), crease * sin(fold));
    if (turn <= 0.0) return p;
    vec2 centre = vec2(0.5 * len * cos(fold), 0.25 * width * sin(fold));
    vec2 d = p - centre;
    float c = cos(turn), s = sin(turn);
    return centre + vec2(d.x * c - d.y * s, d.x * s + d.y * c + (centre.x + 2.0 * centre.y) * s);
}
"""

SHEET_SIDES_GLSL = """
// True where the viewer sees the sheet's back (its geometric normal faces away).
bool sheetShowsBack(vec3 normal, vec3 world) {
    return dot(normal, normalize(vec3(0.0, 0.0, SCENE_CAMERA) - world)) < 0.0;
}
// The back's print: mirrored across the axis the sheet turned over (mirror (1, 0) for a
// horizontal fold axis, (0, 1) for a vertical one), so laid flat it reads the right way round.
vec2 sheetBackUv(vec2 uv, vec2 mirror) {
    return mix(uv, 1.0 - uv, mirror);
}
// A flat pleat face's normal, facing the viewer: from screen-space derivatives, so every
// face shades as one plane however coarse the grid.
vec3 sheetFaceNormal(vec3 world) {
    vec3 n = normalize(cross(dFdx(world), dFdy(world)));
    return dot(n, vec3(0.0, 0.0, SCENE_CAMERA) - world) < 0.0 ? -n : n;
}
"""


SHEET_TWIST_GLSL = """
// Turn the plane point p (z = 0) about the axis through pivot along unit axis by angle, the axis
// rising by halfWidth * sin(angle): every point stays at or in front of the plane.
vec3 sheetTwist(vec2 p, vec2 axis, vec2 pivot, float angle, float halfWidth) {
    vec2 across = vec2(-axis.y, axis.x);
    vec2 rel = p - pivot;
    float along = dot(rel, axis), off = dot(rel, across);
    float c = cos(angle), s = sin(angle);
    return vec3(pivot + axis * along + across * (off * c), (off + halfWidth) * s);
}
"""


def sheet_twist(p: tuple[float, float], axis: tuple[float, float], pivot: tuple[float, float], angle: float,
                half_width: float) -> tuple[float, float, float]:
    """CPU mirror of ``sheetTwist``."""
    across = (-axis[1], axis[0])
    rel = (p[0] - pivot[0], p[1] - pivot[1])
    along = rel[0] * axis[0] + rel[1] * axis[1]
    off = rel[0] * across[0] + rel[1] * across[1]
    c, s = math.cos(angle), math.sin(angle)
    return (pivot[0] + axis[0] * along + across[0] * off * c, pivot[1] + axis[1] * along + across[1] * off * c,
            (off + half_width) * s)


def sheet_fold(a: float, length: float, pleats: int, fold: float, turn: float) -> tuple[float, float]:
    """CPU mirror of ``sheetFold``: (distance from the edge, height) of the point ``a`` from it."""
    width = length / pleats
    local = a - width * math.floor(a / width)
    crease = min(local, width - local)
    if turn >= math.pi:
        return (length - a) * math.cos(fold), (0.5 * width - crease) * math.sin(fold)
    x, z = a * math.cos(fold), crease * math.sin(fold)
    if turn <= 0.0:
        return x, z
    cx, cz = 0.5 * length * math.cos(fold), 0.25 * width * math.sin(fold)
    c, s = math.cos(turn), math.sin(turn)
    dx, dz = x - cx, z - cz
    return cx + dx * c - dz * s, cz + dx * s + dz * c + (cx + 2.0 * cz) * s


def crease_grid(pleats: int, tier_cells: int, aspect: float, vertical: bool) -> tuple[int, int]:
    """(columns, rows) for a sheet folding along x (``vertical`` False) or y: along the fold axis a
    whole number of cells per pleat, every crease on a vertex row, at about the tier's density;
    across it one cell."""
    along_length = 1.0 if vertical else aspect
    long_side = max(aspect, 1.0)
    cells = max(2, round(tier_cells * along_length / long_side / pleats)) * pleats
    return (1, cells) if vertical else (cells, 1)
