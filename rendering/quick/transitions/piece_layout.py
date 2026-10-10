"""Shared transition-piece layout: seeded jigsaw pieces and their order (pure; no GL).

The picture is cut into a grid of interlocking jigsaw pieces. Every interior edge is one seeded
curve (the classic three-Bezier tab of Draradech's jigsaw generator, widened with independent neck,
head width, head height, lean and tilt so no two knobs look alike) stored once, so the two pieces
that share it use the very same points and the cut is watertight. A piece whose knobs would cross
(two large knobs meeting near a corner) has its edges re-seeded with calmer variation until its
outline and its bevel are simple; the nominal knob, always simple, is the last resort. Border edges are
straight. Knob curves are flattened adaptively to an absolute tolerance (a pixel at 1080 lines), so
cut lines and silhouettes stay smooth at any piece count while flat stretches spend few points. Each
piece is solid: a front face, a back face, a narrow bevel ring around each (whose
attribute is the distance from the cut, for screen-pixel outlines and a rounded edge normal) and
the wall between them.

A piece outline is not convex (knobs have necks), so each piece is ear-clipped incrementally (only
the two neighbours of a clipped ear are re-tested; about a millisecond of pure Python per piece; a run prepares
its layout on COMPUTE ahead of time). Shared templates per edge configuration were measured and
rejected: the seeded jitter folded 35-45% of them.

The order planner ranks pieces for a flip that spreads from a corner or a random piece (a ragged
wavefront: distance plus a seeded jitter), or in a shuffled order, and gives each piece the axis
it turns over about (perpendicular to the way the flips travel).

Coordinates: the scene plane of ``rendering/gl_programs/scene3d.py`` (height 1, x across
+-aspect/2, y up) for building; the output vertices carry the rest position as item UV (v down)
so a renderer maps them through the item's real aspect and the pieces always cover the picture
exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

import numpy as np

PIECE_LAYOUT_MAX_PIECES = 160
JIGSAW_TAB = 0.10          # tab size, as a share of the edge (Draradech's t)
# Seeded variation of a knob at full variety (re-seeds halve it): tab size, shoulder heights
# (a, e), knob position along the edge (b), height (c), neck asymmetry (d), then neck width,
# head width and head height as factors, and the head's lean along and tilt across the edge.
_TAB_RANGE = (-0.018, 0.022)
_SHOULDER = 0.06
_ALONG = 0.07
_HEIGHT = 0.035
_ASYMMETRY = 0.05
_NECK_RANGE = (-0.25, 0.15)
_WIDTH_RANGE = (-0.18, 0.20)
_HEAD_RANGE = (-0.15, 0.20)
_LEAN = 0.05
_TILT = 0.05
_RESEEDS = 4
# Largest distance a flattened knob curve may stray from the true Bezier (scene height units):
# two pixels at 2160 lines (one at 1080): cheaper to build than the old uniform sampling (4/8/4
# points per Bezier), whose corners strayed about 6 px on large knobs at 2160.
JIGSAW_CURVE_TOLERANCE = 2.0 / 2160.0
_FLATTEN_DEPTH = 10
# The bevel ring's width (scene height units) and how far its outer normal leans outward.
JIGSAW_BEVEL = 0.004
_RING_TILT = 1.1
# Wavefront jitter, as a share of a cell: enough to break diagonal ties into a ragged front.
_ORDER_JITTER = 0.35

# Interleaved vertex: rest uv (2), side (+0.5 front, -0.5 back), normal (3), distance from the
# cut in scene units (0 on the cut, JIGSAW_BEVEL inside the ring), piece index.
PIECE_VERTEX_ATTRIBUTES = (2, 1, 3, 1, 1)
PIECE_VERTEX_FLOATS = sum(PIECE_VERTEX_ATTRIBUTES)


def piece_grid(count: int, aspect: float) -> tuple[int, int]:
    """Columns and rows for about ``count`` near-square pieces at ``aspect``."""
    count = max(4, int(count))
    aspect = max(0.1, min(10.0, float(aspect)))
    cols = max(2, round(math.sqrt(count * aspect)))
    rows = max(2, round(count / cols))
    while cols * rows > PIECE_LAYOUT_MAX_PIECES:
        if cols / aspect >= rows:
            cols -= 1
        else:
            rows -= 1
    return cols, rows


@dataclass(frozen=True, slots=True)
class EdgeShape:
    """One edge's knob: sign (+1 bulges to the edge's left, -1 right, 0 straight), tab size,
    shoulder heights (a, e), position along (b), height (c), neck asymmetry (d), neck/head width
    and head height factors, and the head's lean and tilt."""
    sign: int
    tab: float = JIGSAW_TAB
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0
    d: float = 0.0
    e: float = 0.0
    neck: float = 1.0
    width: float = 1.0
    height: float = 1.0
    lean: float = 0.0
    tilt: float = 0.0


def _seeded_edge(rng: random.Random, sign: int, variety: float = 1.0) -> EdgeShape:
    def spread(low, high):
        return rng.uniform(low, high) * variety

    def jitter(limit):
        return rng.uniform(-limit, limit) * variety

    return EdgeShape(sign, JIGSAW_TAB + spread(*_TAB_RANGE), jitter(_SHOULDER), jitter(_ALONG), jitter(_HEIGHT),
                     jitter(_ASYMMETRY), jitter(_SHOULDER), 1.0 + spread(*_NECK_RANGE), 1.0 + spread(*_WIDTH_RANGE),
                     1.0 + spread(*_HEAD_RANGE), jitter(_LEAN), jitter(_TILT))


def edge_controls(shape: EdgeShape) -> np.ndarray:
    """The knob's three cubic Beziers in the edge's own frame, (along 0..1, across): ten control
    points, start to end. A straight edge is just its two ends."""
    if shape.sign == 0:
        return np.array([[0.0, 0.0], [1.0, 0.0]])
    t, a, b, c, d, e = shape.tab, shape.a, shape.b, shape.c, shape.d, shape.e
    neck, head, top = t * shape.neck, 2.0 * t * shape.width, 3.0 * t * shape.height
    lean, tilt = shape.lean, shape.tilt
    p = np.array([
        (0.0, 0.0), (0.2, a), (0.5 + b + d, -t + c), (0.5 - neck + b, t + c),
        (0.5 - head + b - d + lean, top + c - tilt), (0.5 + head + b - d + lean, top + c + tilt),
        (0.5 + neck + b, t + c), (0.5 + b + d, -t + c), (0.8, e), (1.0, 0.0),
    ])
    p[:, 1] *= shape.sign
    return p


def _segment_distance(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    u = 0.0 if length2 <= 0.0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - ax - u * dx, py - ay - u * dy)


def _flatten(p0, p1, p2, p3, tolerance: float, out: list, depth: int = _FLATTEN_DEPTH) -> None:
    """Append the cubic's points from ``p0`` (inclusive) to ``p3`` (exclusive), halving it until
    its points at a quarter, half and three quarters lie within ``tolerance`` of the chord (and,
    against S-bends, its control polygon within four times that). Three samples estimate the
    error: the curve strays at most about 10% beyond ``tolerance``. Deterministic: the same
    controls always give the very same points."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = p0, p1, p2, p3
    ax, ay = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    bx, by = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
    cx, cy = 0.5 * (x2 + x3), 0.5 * (y2 + y3)
    dx, dy = 0.5 * (ax + bx), 0.5 * (ay + by)
    ex, ey = 0.5 * (bx + cx), 0.5 * (by + cy)
    mx, my = 0.5 * (dx + ex), 0.5 * (dy + ey)
    if depth <= 0:
        out.append(p0)
        return
    hull = max(_segment_distance(x1, y1, x0, y0, x3, y3), _segment_distance(x2, y2, x0, y0, x3, y3))
    if hull <= 4.0 * tolerance:
        # B(1/4) and B(3/4) by their Bernstein weights (27, 27, 9, 1) / 64.
        qx = (27.0 * x0 + 27.0 * x1 + 9.0 * x2 + x3) / 64.0
        qy = (27.0 * y0 + 27.0 * y1 + 9.0 * y2 + y3) / 64.0
        rx = (x0 + 9.0 * x1 + 27.0 * x2 + 27.0 * x3) / 64.0
        ry = (y0 + 9.0 * y1 + 27.0 * y2 + 27.0 * y3) / 64.0
        if max(_segment_distance(mx, my, x0, y0, x3, y3), _segment_distance(qx, qy, x0, y0, x3, y3),
               _segment_distance(rx, ry, x0, y0, x3, y3)) <= tolerance:
            out.append(p0)
            return
    _flatten(p0, (ax, ay), (dx, dy), (mx, my), tolerance, out, depth - 1)
    _flatten((mx, my), (ex, ey), (cx, cy), p3, tolerance, out, depth - 1)


def _edge_points(start, end, knob: float, shape: EdgeShape,
                 tolerance: float = JIGSAW_CURVE_TOLERANCE) -> np.ndarray:
    """The edge in the scene from ``start`` to ``end`` (axis-aligned), knobs scaled by ``knob``
    across, to the left of the direction, flattened to ``tolerance``. Both ends are the given
    corners exactly, so every piece meeting at a corner holds the very same point."""
    start, end = np.asarray(start, dtype=np.float64), np.asarray(end, dtype=np.float64)
    length = float(np.linalg.norm(end - start))
    direction = (end - start) / length
    left = np.array([-direction[1], direction[0]])
    controls = edge_controls(shape)
    scene = start + controls[:, :1] * length * direction + controls[:, 1:] * knob * left
    if len(scene) == 2:
        return np.array([start, end])
    pts = [tuple(map(float, p)) for p in scene]
    out: list = []
    for i in range(3):
        _flatten(pts[3 * i], pts[3 * i + 1], pts[3 * i + 2], pts[3 * i + 3], tolerance, out)
    out.append(pts[9])
    points = np.asarray(out, dtype=np.float64)
    points[0], points[-1] = start, end
    return points


# --- Triangulation ---------------------------------------------------------------------------


def ear_clip(points: np.ndarray) -> tuple[tuple[int, int, int], ...]:
    """Triangles (counter-clockwise) of a simple counter-clockwise polygon.

    Incremental: every vertex's ear status is computed once, and clipping an ear re-tests only
    its two neighbours (a reflex vertex can only turn convex). Only reflex vertices can lie inside
    a candidate ear, and a bounding-box test rejects most of them cheaply."""
    n = len(points)
    xs = [float(x) for x in points[:, 0]]
    ys = [float(y) for y in points[:, 1]]
    prev = [(i - 1) % n for i in range(n)]
    nxt = [(i + 1) % n for i in range(n)]

    def convex(i: int) -> bool:
        a, b = prev[i], nxt[i]
        return (xs[i] - xs[a]) * (ys[b] - ys[a]) - (ys[i] - ys[a]) * (xs[b] - xs[a]) > 1e-14

    reflex = {i for i in range(n) if not convex(i)}

    def is_ear(i: int) -> bool:
        if i in reflex:
            return False
        a, c = prev[i], nxt[i]
        ax, ay, bx, by, cx, cy = xs[a], ys[a], xs[i], ys[i], xs[c], ys[c]
        lo_x, hi_x, lo_y, hi_y = min(ax, bx, cx), max(ax, bx, cx), min(ay, by, cy), max(ay, by, cy)
        for j in reflex:
            if j == a or j == c:
                continue
            px, py = xs[j], ys[j]
            if px < lo_x or px > hi_x or py < lo_y or py > hi_y:
                continue
            if ((bx - ax) * (py - ay) - (by - ay) * (px - ax) >= 0.0
                    and (cx - bx) * (py - by) - (cy - by) * (px - bx) >= 0.0
                    and (ax - cx) * (py - cy) - (ay - cy) * (px - cx) >= 0.0):
                return False
        return True

    ear = [is_ear(i) for i in range(n)]
    triangles: list[tuple[int, int, int]] = []
    count, i, misses = n, 0, 0
    while count > 3:
        if not ear[i]:
            i = nxt[i]
            misses += 1
            if misses > count:
                raise ValueError("polygon could not be ear-clipped (not simple)")
            continue
        misses = 0
        a, c = prev[i], nxt[i]
        triangles.append((a, i, c))
        nxt[a], prev[c] = c, a
        count -= 1
        for v in (a, c):
            if v in reflex and convex(v):
                reflex.discard(v)
        ear[a], ear[c] = is_ear(a), is_ear(c)
        i = c
    triangles.append((prev[i], i, nxt[i]))
    return tuple(triangles)


def is_simple(points: np.ndarray) -> bool:
    """Whether a closed outline never crosses itself (no two non-adjacent segments meet)."""
    a = points
    b = np.roll(points, -1, axis=0)
    n = len(points)

    def orient(p, q, r):
        return (q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0])

    p1, p2 = a[:, None, :], b[:, None, :]
    q1, q2 = a[None, :, :], b[None, :, :]
    d1, d2 = orient(p1, p2, q1), orient(p1, p2, q2)
    d3, d4 = orient(q1, q2, p1), orient(q1, q2, p2)
    crossing = (d1 * d2 < 0.0) & (d3 * d4 < 0.0)
    i, j = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    adjacent = (np.abs(i - j) <= 1) | (np.abs(i - j) == n - 1)
    return not bool(np.any(crossing & ~adjacent))


# --- Pieces ----------------------------------------------------------------------------------


def _outline(edges) -> np.ndarray:
    """A piece's counter-clockwise outline from its bottom-left corner. ``edges`` holds, for the
    bottom, right, top and left sides, (the canonical edge's points, traversed reversed?)."""
    parts = []
    for points, reverse in edges:
        parts.append(points[::-1][:-1] if reverse else points[:-1])
    return np.vstack(parts)


_FOLD_WINDOW = 24   # how many segments apart a local fold of the inset may close


def _remove_folds(points: np.ndarray) -> np.ndarray:
    """Cut the small loops an inward offset forms where the outline curves tighter than the offset
    (knob necks of small pieces): every point of a loop moves onto the loop's crossing, so the
    polygon keeps one point per outline point (some repeated) and becomes simple again."""
    p = points.copy()
    n = len(p)
    window = min(_FOLD_WINDOW, n - 2)
    if window < 2:
        return p
    ks = np.arange(2, window + 1)
    for _ in range(4):
        a = p[:, None, :]                                    # segment i: p[i] -> p[i + 1]
        r = (np.roll(p, -1, axis=0) - p)[:, None, :]
        j = (np.arange(n)[:, None] + ks[None, :]) % n        # segment i + k
        c = p[j]
        q = p[(j + 1) % n] - c
        den = r[..., 0] * q[..., 1] - r[..., 1] * q[..., 0]
        ok = np.abs(den) > 1e-18
        safe = np.where(ok, den, 1.0)
        w = c - a
        t = (w[..., 0] * q[..., 1] - w[..., 1] * q[..., 0]) / safe
        u = (w[..., 0] * r[..., 1] - w[..., 1] * r[..., 0]) / safe
        hit_i, hit_k = np.nonzero(ok & (t > 0.0) & (t < 1.0) & (u > 0.0) & (u < 1.0))
        if not len(hit_i):
            break
        taken = np.zeros(n, dtype=bool)
        for slot in np.argsort(-hit_k, kind="stable"):           # the widest loop first
            i, k = int(hit_i[slot]), int(ks[hit_k[slot]])
            loop = (i + 1 + np.arange(k)) % n
            if taken[loop].any():
                continue
            taken[loop] = True
            p[loop] = p[i] + t[i, hit_k[slot]] * r[i, 0]
    return p


def _inset(points: np.ndarray, distance: float) -> tuple[np.ndarray, np.ndarray]:
    """The outline moved ``distance`` inward (local folds removed), and the outward unit normal at
    each point."""
    forward = np.roll(points, -1, axis=0) - points
    forward /= np.maximum(np.linalg.norm(forward, axis=1, keepdims=True), 1e-12)
    left = np.stack((-forward[:, 1], forward[:, 0]), axis=1)      # inward for a CCW outline
    inward = left + np.roll(left, 1, axis=0)
    inward /= np.maximum(np.linalg.norm(inward, axis=1, keepdims=True), 1e-12)
    miter = 1.0 / np.maximum(np.sum(inward * left, axis=1, keepdims=True), 0.5)
    return _remove_folds(points + inward * distance * miter), -inward


def _distinct(points: np.ndarray) -> np.ndarray:
    """Indices of the points that differ from their predecessor (a cleaned inset repeats some)."""
    keep = np.any(points != np.roll(points, 1, axis=0), axis=1)
    if not keep.any():
        keep[0] = True
    return np.flatnonzero(keep)


@dataclass(frozen=True, slots=True)
class PieceLayout:
    cols: int
    rows: int
    aspect: float
    cell: tuple[float, float]
    outlines: tuple[np.ndarray, ...]      # per piece, counter-clockwise scene points
    centres: np.ndarray                   # (n, 2) scene points


def jigsaw_layout(seed: int, count: int, aspect: float) -> PieceLayout:
    """Seeded interlocking pieces covering the scene plane at ``aspect`` exactly."""
    cols, rows = piece_grid(count, aspect)
    aspect = float(aspect)
    cw, ch = aspect / cols, 1.0 / rows
    knob = min(cw, ch)
    rng = random.Random(f"jigsaw:{int(seed)}")
    left_x, top_y = -0.5 * aspect, 0.5
    # ("h", r, c): the edge below row r - 1 / above row r (r = 1..rows-1), pointing right.
    # ("v", r, c): the edge left of column c (c = 1..cols-1) in row r, pointing up.
    keys = [("h", r, c) for r in range(1, rows) for c in range(cols)]
    keys += [("v", r, c) for r in range(rows) for c in range(1, cols)]
    shapes = {key: _seeded_edge(rng, 1 if rng.random() < 0.5 else -1) for key in keys}
    variety = dict.fromkeys(keys, 1.0)

    def corner(r, c):
        return left_x + c * cw, top_y - r * ch

    def points(key):
        kind, r, c = key
        shape = shapes.get(key, EdgeShape(0))
        if kind == "h":
            return _edge_points(corner(r, c), corner(r, c + 1), knob, shape)
        return _edge_points(corner(r + 1, c), corner(r, c), knob, shape)

    def sides(r, c):
        # Bottom and right run along their canonical edges; top and left run back along them.
        return (("h", r + 1, c), False), (("v", r, c + 1), False), (("h", r, c), True), (("v", r, c), True)

    cache = {}

    def outline(r, c):
        for key, _reverse in sides(r, c):
            if key not in cache:
                cache[key] = points(key)
        return _outline(tuple((cache[key], reverse) for key, reverse in sides(r, c)))

    checked: dict = {}

    def acceptable(r, c):
        # A cell is re-checked only when one of its edges was re-seeded.
        key = tuple(shapes.get(k) for k, _reverse in sides(r, c))
        if key not in checked:
            shape_outline = outline(r, c)
            inner = _inset(shape_outline, JIGSAW_BEVEL)[0]
            checked[key] = is_simple(shape_outline) and is_simple(inner[_distinct(inner)])
        return checked[key]

    cells = [(r, c) for r in range(rows) for c in range(cols)]
    for attempt in range(_RESEEDS + 1):
        crossed = [cell for cell in cells if not acceptable(*cell)]
        if not crossed:
            break
        for r, c in crossed:
            for key, _reverse in sides(r, c):
                if key in shapes:
                    variety[key] *= 0.5
                    calm = variety[key] if attempt < _RESEEDS else 0.0
                    reseed = random.Random(f"jigsaw:{int(seed)}:{key}:{attempt}")
                    shapes[key] = _seeded_edge(reseed, shapes[key].sign, calm)
                    cache.pop(key, None)
    outlines = [outline(r, c) for r, c in cells]
    centres = [(left_x + (c + 0.5) * cw, top_y - (r + 0.5) * ch) for r, c in cells]
    return PieceLayout(cols, rows, aspect, (cw, ch), tuple(outlines), np.asarray(centres))


# --- Order -----------------------------------------------------------------------------------

_CORNERS = {"top_left": (-0.5, 0.5), "top_right": (0.5, 0.5),
            "bottom_left": (-0.5, -0.5), "bottom_right": (0.5, -0.5)}
PIECE_ORDERS = (*_CORNERS, "random_start", "unordered")


def piece_order(order: str, centres: np.ndarray, cell: tuple[float, float], aspect: float,
                seed: int) -> tuple[np.ndarray, np.ndarray]:
    """(rank of each piece, 0 first; the angle of the in-plane axis each piece turns over about).

    A piece turns over away from where the flips started, so its edge nearest the start lifts
    first. Unordered shuffles the ranks and gives each piece a seeded axis."""
    if order not in PIECE_ORDERS:
        raise ValueError(f"unknown piece order {order!r}")
    rng = random.Random(f"order:{int(seed)}:{order}")
    count = len(centres)
    if order == "unordered":
        ranks = list(range(count))
        rng.shuffle(ranks)
        axes = [rng.uniform(0.0, 2.0 * math.pi) for _ in range(count)]
        return np.asarray(ranks, dtype=np.int64), np.asarray(axes)
    if order == "random_start":
        origin = centres[rng.randrange(count)]
    else:
        fx, fy = _CORNERS[order]
        origin = np.array((fx * aspect, fy))
    jitter = _ORDER_JITTER * min(cell)
    away = centres - origin
    distance = np.linalg.norm(away, axis=1) + np.asarray([rng.uniform(0.0, jitter) for _ in range(count)])
    ranks = np.empty(count, dtype=np.int64)
    ranks[np.argsort(distance, kind="stable")] = np.arange(count)
    spin = rng.uniform(0.0, 2.0 * math.pi)
    heading = np.where(np.linalg.norm(away, axis=1) > 1e-9, np.arctan2(away[:, 1], away[:, 0]), spin)
    return ranks, heading + 0.5 * math.pi


# --- Vertices --------------------------------------------------------------------------------


def _uv(points: np.ndarray, aspect: float) -> np.ndarray:
    return np.stack((points[:, 0] / aspect + 0.5, 0.5 - points[:, 1]), axis=1)


def _records(uv, side, normal, bevel, piece) -> np.ndarray:
    n = len(uv)
    out = np.empty((n, PIECE_VERTEX_FLOATS), dtype=np.float32)
    out[:, 0:2] = uv
    out[:, 2] = side
    out[:, 3:6] = normal
    out[:, 6] = bevel
    out[:, 7] = piece
    return out


def piece_vertices(layout: PieceLayout) -> tuple[np.ndarray, int]:
    """(interleaved vertices, how many lead vertices are the front faces and rings).

    Front faces and rings of every piece come first (a renderer draws just them flat for the
    pieces at rest), then the back faces and rings, then the walls."""
    fronts, backs, walls = [], [], []
    aspect = layout.aspect
    for index, outline in enumerate(layout.outlines):
        inner, outward = _inset(outline, JIGSAW_BEVEL)
        distinct = _distinct(inner)
        triangles = distinct[np.asarray(ear_clip(inner[distinct]), dtype=np.int64)]
        n = len(outline)
        nxt = np.roll(np.arange(n), -1)
        uv_out, uv_in = _uv(outline, aspect), _uv(inner, aspect)
        tilt = np.hstack((outward * _RING_TILT, np.ones((n, 1))))
        tilt /= np.linalg.norm(tilt, axis=1, keepdims=True)
        flat = np.tile((0.0, 0.0, 1.0), (n, 1))
        for side, sign, bucket in ((0.5, 1.0, fronts), (-0.5, -1.0, backs)):
            face = triangles.reshape(-1) if sign > 0 else triangles[:, ::-1].reshape(-1)
            bucket.append(_records(uv_in[face], side, flat[face] * sign, JIGSAW_BEVEL, index))
            # Ring quad (outer i, outer i+1, inner i+1, inner i) as two triangles.
            i, j = np.arange(n), nxt
            uv_ring = np.stack((uv_out[i], uv_out[j], uv_in[j], uv_out[i], uv_in[j], uv_in[i]), axis=1)
            normal_out = tilt * np.array((1.0, 1.0, sign))
            normal_ring = np.stack((normal_out[i], normal_out[j], flat[j] * sign,
                                    normal_out[i], flat[j] * sign, flat[i] * sign), axis=1)
            bevel = np.tile((0.0, 0.0, JIGSAW_BEVEL, 0.0, JIGSAW_BEVEL, JIGSAW_BEVEL), n)
            records = _records(uv_ring.reshape(-1, 2), side, normal_ring.reshape(-1, 3), 0.0, index)
            records[:, 6] = bevel
            bucket.append(records)
        i, j = np.arange(n), nxt
        uv_wall = np.stack((uv_out[i], uv_out[j], uv_out[j], uv_out[i], uv_out[j], uv_out[i]), axis=1)
        sides = np.tile((0.5, 0.5, -0.5, 0.5, -0.5, -0.5), n)
        wall_normal = np.hstack((outward, np.zeros((n, 1))))
        normals = np.stack((wall_normal[i], wall_normal[j], wall_normal[j],
                            wall_normal[i], wall_normal[j], wall_normal[i]), axis=1)
        records = _records(uv_wall.reshape(-1, 2), 0.0, normals.reshape(-1, 3), 0.0, index)
        records[:, 2] = sides
        walls.append(records)
    front = np.vstack(fronts)
    return np.vstack((front, *backs, *walls)), len(front)


__all__ = [
    "EdgeShape",
    "JIGSAW_BEVEL",
    "JIGSAW_CURVE_TOLERANCE",
    "PIECE_LAYOUT_MAX_PIECES",
    "PIECE_ORDERS",
    "PIECE_VERTEX_ATTRIBUTES",
    "PIECE_VERTEX_FLOATS",
    "PieceLayout",
    "ear_clip",
    "edge_controls",
    "is_simple",
    "jigsaw_layout",
    "piece_grid",
    "piece_order",
    "piece_vertices",
]
