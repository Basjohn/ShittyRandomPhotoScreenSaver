"""Build-time shard collisions and in-flight re-shattering for Glass Shatter.

Glass motion stays analytic on the GPU: every shard follows the vertex
shader's path (``GLASS_VERTEX``). When the operator enables collisions or
re-shattering, the events are solved once per run here -- deterministic per
seed, on COMPUTE with the rest of the run geometry -- and reach the shader as
per-piece constants: a visibility window, a velocity kick and a spin kick that
start at the event time. There is no per-frame simulation, clock or state.

* Collisions: shards whose paths meet in flight bounce off each other (equal
  masses, partial restitution, a tangential scatter and a spin kick). Each
  shard collides at most once, which bounds the work and keeps flights legible.
* Re-shattering: a shard splits into two or three convex pieces that follow the
  parent exactly until the split and then drift apart and spin. With
  collisions on, only colliding shards split; with collisions off, each shard
  has a 30% chance to crack at a random point of its flight.
* A second crack: split pieces can break once more. With collisions on this
  only follows an impact (the fracture propagating a moment later); with
  collisions off each split piece has a 30% chance to crack again later in
  its flight. A second crack is a second event stage on the same piece.

* Depth layers (always on): shards whose flights would pass through each other
  on screen are given small, constant depth offsets (within +-``LAYER_RANGE``,
  ramping in as each shard launches), placed so each conflicting pair is
  separated by at least the depth their tumbling can sweep. Crash pairs share a
  layer so they still meet; split pieces keep their parent's layer.

Every kicked piece must still leave the frame by the end of the run: a kick
that would carry a piece back into view is scaled down (or turned outward).
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random

import numpy as np

from .directions import direction_vector
from .fracture_geometry import GlassShard, _clip_cell

# Constants shared with GLASS_VERTEX; the path below must match it exactly.
PATH_END = 0.98
NO_EVENT = 9.0
RANDOM_SPLIT_CHANCE = 0.30
SECOND_SPLIT_CHANCE = 0.30          # split pieces cracking again (no collisions)
IMPACT_SECOND_SPLIT_CHANCE = 0.45   # pieces of a collision cracking again

_RESTITUTION = 0.45
_COLLISION_RADIUS = 0.80   # of the circumradius a tumbling shard sweeps
_SAMPLES = 120
_CRASH_SPEED = 0.20        # closing speed, as a fraction of the shards' speed
_MAX_COLLISIONS = 0.12     # at most this share of shards pairs up in a run
_LATEST_CRASH = 0.80       # later crashes would happen as the shards leave

# Depth layers; LAYER_RANGE is mirrored by GLASS_VERTEX's exit margin for receding shards.
LAYER_RANGE = 0.25
_LAYER_STEP = 0.004
_LAYER_REACH = 0.85        # of the summed circumradii: centres this close may intersect
_LAYER_SAMPLES = 49


@dataclass(frozen=True, slots=True)
class GlassPiece:
    """One rendered prism. ``shard`` carries its own polygon and fan centre."""

    shard: GlassShard
    pivot_center: tuple[float, float]   # the original shard's centre (path pivot)
    radius: float                       # the original shard's circumradius
    life: tuple[float, float] = (0.0, NO_EVENT)
    kick: tuple[float, float, float, float] = (0.0, 0.0, 0.0, NO_EVENT)
    spin: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)
    spin_pivot: tuple[float, float] | None = None       # stage-1 spin pivot (default: own centre)
    kick2: tuple[float, float, float, float] = (0.0, 0.0, 0.0, NO_EVENT)
    spin2: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)
    layer: float = 0.0                                  # depth offset (see separation_layers)


def shard_radius(shard: GlassShard, aspect: float) -> float:
    cx, cy = shard.center
    return max(math.hypot((x - cx) * aspect, y - cy) for x, y in shard.polygon)


class _Paths:
    """Vectorised replica of GLASS_VERTEX's shard-centre path (position space)."""

    def __init__(self, shards, aspect: float, direction: object, depth: float, layers=None):
        self.aspect = aspect
        self.depth = depth
        self.layers = np.zeros(len(shards)) if layers is None else np.asarray(layers, dtype=np.float64)
        u = np.array([s.center[0] for s in shards], dtype=np.float64)
        v = np.array([s.center[1] for s in shards], dtype=np.float64)
        var = np.array([s.variation for s in shards], dtype=np.float64)
        radius = np.array([shard_radius(s, aspect) for s in shards], dtype=np.float64)
        cx, cy = (u - 0.5) * aspect, 0.5 - v
        if direction == "center_out":
            dx, dy = cx + 1e-5, cy + 1e-5
            length = np.hypot(dx, dy)
            dx, dy = dx / length, dy / length
            rank = np.hypot(cx, cy) / math.hypot(aspect * 0.5, 0.5)
        else:
            ux, uy = direction_vector(direction)
            dx, dy = np.full_like(u, ux), np.full_like(u, -uy)
            rank = 0.5 + ((u - 0.5) * ux + (v - 0.5) * uy) / (abs(ux) + abs(uy))
        self.delay = 0.34 * np.clip(rank, 0.0, 1.0) + 0.025 * var
        bend = 0.35 * (var - 0.5)
        dx, dy = dx - dy * bend, dy + dx * bend
        length = np.hypot(dx, dy)
        self.dx, self.dy = dx / length, dy / length
        scale = 1.0 + (0.6 * depth + np.maximum(-self.layers, 0.0)) / 3.0
        extent_x = (aspect * 0.5 + radius * 2.0 + 0.10) * scale
        extent_y = (0.5 + radius * 2.0 + 0.10) * scale
        with np.errstate(divide="ignore", invalid="ignore"):
            to_x = (np.sign(self.dx) * extent_x - cx) / (np.sign(self.dx) * np.maximum(np.abs(self.dx), 1e-5))
            to_y = (np.sign(self.dy) * extent_y - cy) / (np.sign(self.dy) * np.maximum(np.abs(self.dy), 1e-5))
        to_x = np.where(np.abs(self.dx) < 1e-5, 1e5, to_x)
        to_y = np.where(np.abs(self.dy) < 1e-5, 1e5, to_y)
        self.exit = np.minimum(to_x, to_y)
        self.cx, self.cy, self.radius, self.variation = cx, cy, radius, var

    def at(self, t, index=None):
        """Positions (shards, times, 3) of the selected shard centres."""
        t = np.atleast_1d(np.asarray(t, dtype=np.float64))
        idx = np.arange(len(self.delay)) if index is None else np.atleast_1d(index)
        delay = self.delay[idx][:, None]
        local = np.clip((t[None, :] - delay) / (PATH_END - delay), 0.0, 1.0)
        travel = 0.12 * local + 0.88 * local * local
        reach = self.exit[idx][:, None]
        x = self.cx[idx][:, None] + self.dx[idx][:, None] * reach * travel
        y = (self.cy[idx][:, None] + self.dy[idx][:, None] * reach * travel
             - 0.16 * np.sin(math.pi * local) * local)
        impact = np.clip(local / 0.10, 0.0, 1.0)
        impact = impact * impact * (3.0 - 2.0 * impact)
        z = (self.depth * (0.56 * np.sin(math.pi * local) - 0.6 * local * local)
             + self.layers[idx][:, None] * impact)
        return np.stack((x, y, z), axis=-1)

    def point(self, index: int, t: float) -> np.ndarray:
        """One shard centre at one time (scalar twin of ``at``)."""
        delay = float(self.delay[index])
        local = min(1.0, max(0.0, (t - delay) / (PATH_END - delay)))
        travel = (0.12 * local + 0.88 * local * local) * float(self.exit[index])
        arc = math.sin(math.pi * local)
        impact = min(1.0, local / 0.10)
        impact = impact * impact * (3.0 - 2.0 * impact)
        return np.array((
            float(self.cx[index]) + float(self.dx[index]) * travel,
            float(self.cy[index]) + float(self.dy[index]) * travel - 0.16 * arc * local,
            self.depth * (0.56 * arc - 0.6 * local * local) + float(self.layers[index]) * impact,
        ))

    def velocity(self, index: int, t: float) -> np.ndarray:
        h = 1e-4
        ahead, behind = min(t + h, PATH_END), max(t - h, 0.0)
        return (self.point(index, ahead) - self.point(index, behind)) / (ahead - behind)

    def launched(self, t) -> np.ndarray:
        t = np.atleast_1d(np.asarray(t, dtype=np.float64))
        return (t[None, :] - self.delay[:, None]) / (PATH_END - self.delay[:, None]) > 0.02


def separation_layers(paths: _Paths, groups: tuple[tuple[int, ...], ...] = ()) -> np.ndarray:
    """Constant depth offsets that keep shards from passing through each other.

    Pairs whose centres come within ``_LAYER_REACH`` of their summed circumradii
    while flying and on screen must be separated in depth by the height their
    tumbling sweeps at those moments. Shards are placed greedily (most
    constrained first) at the offset nearest 0 in [-LAYER_RANGE, LAYER_RANGE]
    that satisfies the neighbours already placed, or the least violating one.
    Shards in one ``group`` (a crash pair) share an offset. Solved once per run.
    """
    count = len(paths.radius)
    times = np.linspace(0.02, PATH_END, _LAYER_SAMPLES)
    positions = paths.at(times)
    local = np.clip((times[None, :] - paths.delay[:, None]) / (PATH_END - paths.delay[:, None]), 0.0, 1.0)
    flying = local > 0.0
    rate = (3.8 + 4.5 * paths.variation) * (0.5 + 0.65 * paths.depth)
    lift = paths.radius[:, None] * np.abs(np.sin(local * rate[:, None]))
    scale = 3.0 / (3.0 - positions[:, :, 2])
    screen_x = positions[:, :, 0] / paths.aspect * scale + 0.5
    screen_y = -positions[:, :, 1] * scale + 0.5
    seen = (screen_x > -0.05) & (screen_x < 1.05) & (screen_y > -0.05) & (screen_y < 1.05)
    owner = list(range(count))
    for group in groups:
        for member in group:
            owner[member] = group[0]
    needs: dict[int, dict[int, float]] = {node: {} for node in set(owner)}
    for i in range(count - 1):
        delta = positions[i + 1:] - positions[i]
        gap = np.sqrt(np.einsum("mtc,mtc->mt", delta, delta))
        limit = (paths.radius[i + 1:] + paths.radius[i])[:, None] * _LAYER_REACH
        close = (gap < limit) & flying[i + 1:] & flying[i] & (seen[i + 1:] | seen[i])
        rows = np.flatnonzero(close.any(axis=1))
        if rows.size == 0:
            continue
        need = np.where(close[rows], lift[i + 1:][rows] + lift[i][None, :], 0.0).max(axis=1)
        a = owner[i]
        for row, spacing in zip(rows, need):
            b = owner[i + 1 + int(row)]
            if a == b:
                continue
            spacing = float(spacing)
            needs[a][b] = max(needs[a].get(b, 0.0), spacing)
            needs[b][a] = max(needs[b].get(a, 0.0), spacing)
    grid = np.arange(-LAYER_RANGE, LAYER_RANGE + 1e-9, _LAYER_STEP)
    candidates = grid[np.argsort(np.abs(grid), kind="stable")]
    offset: dict[int, float] = {}
    for node in sorted(needs, key=lambda k: (-sum(needs[k].values()), k)):
        placed = [(offset[other], spacing) for other, spacing in needs[node].items() if other in offset]
        if not placed:
            offset[node] = 0.0
            continue
        others = np.array([value for value, _ in placed])
        spacing = np.array([value for _, value in placed])
        worst = np.maximum(spacing[None, :] - np.abs(candidates[:, None] - others[None, :]), 0.0).max(axis=1)
        fits = np.flatnonzero(worst <= 1e-9)
        offset[node] = float(candidates[fits[0]] if fits.size else candidates[int(np.argmin(worst))])
    return np.array([offset[owner[index]] for index in range(count)])


def _collision_candidates(paths: _Paths) -> list[tuple[float, int, int]]:
    """Coarse first contacts that are real crashes, in time order.

    Neighbours flying in parallel graze each other constantly; a contact only
    counts when both shards were clearly apart while flying and they close at a
    meaningful fraction of their own speed.
    """
    times = np.linspace(0.0, PATH_END, _SAMPLES)
    step_time = times[1] - times[0]
    positions = paths.at(times).astype(np.float32)
    flying = paths.launched(times)
    speed = np.linalg.norm(np.diff(positions, axis=1), axis=2) / step_time
    # A crash only counts where it can be seen: both shards on screen, early
    # enough in the flight for the bounce to read before they leave.
    scale = 3.0 / (3.0 - positions[:, :, 2])
    screen_x = positions[:, :, 0] / paths.aspect * scale + 0.5
    screen_y = -positions[:, :, 1] * scale + 0.5
    visible = ((screen_x > 0.02) & (screen_x < 0.98) & (screen_y > 0.02) & (screen_y < 0.98)
               & (times[None, :] < _LATEST_CRASH))
    reach = (_COLLISION_RADIUS * paths.radius).astype(np.float32)
    found = []
    count = len(paths.radius)
    for i in range(count - 1):
        delta = positions[i + 1:] - positions[i]
        gap2 = np.einsum("mkc,mkc->mk", delta, delta)
        limit = (reach[i + 1:] + reach[i])[:, None]
        touching = gap2 < limit * limit
        both = flying[i + 1:] & flying[i]
        seen = visible[i + 1:] & visible[i]
        entering = touching[:, 1:] & ~touching[:, :-1] & both[:, 1:] & both[:, :-1] & seen[:, 1:]
        rows = np.flatnonzero(entering.any(axis=1))
        if rows.size == 0:
            continue
        # Only pairs that actually meet pay for the crash tests.
        gap = np.sqrt(gap2[rows])
        near = limit[rows]
        was_apart = np.maximum.accumulate(both[rows] & (gap > 1.3 * near), axis=1)
        closing = (gap[:, :-1] - gap[:, 1:]) / step_time
        typical = 0.5 * (speed[i + 1:][rows] + speed[i])
        crash = entering[rows] & was_apart[:, :-1] & (closing > _CRASH_SPEED * typical)
        for row, pair_row in zip(rows, crash):
            if pair_row.any():
                step = int(np.argmax(pair_row))
                found.append((float(times[step]), float(times[step + 1]), i, i + 1 + int(row)))
    found.sort()
    return found


def _contact_time(paths: _Paths, i: int, j: int, lo: float, hi: float) -> float:
    limit = _COLLISION_RADIUS * (paths.radius[i] + paths.radius[j])
    for _ in range(14):
        mid = 0.5 * (lo + hi)
        if np.linalg.norm(paths.point(j, mid) - paths.point(i, mid)) < limit:
            hi = mid
        else:
            lo = mid
    return hi


def _random_axis(rng: random.Random) -> tuple[float, float, float]:
    z = rng.uniform(-1.0, 1.0)
    angle = rng.uniform(0.0, math.tau)
    r = math.sqrt(max(0.0, 1.0 - z * z))
    return (r * math.cos(angle), r * math.sin(angle), z)


def _polygon_area(points) -> float:
    return 0.5 * abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1])))


def split_polygon(shard: GlassShard, aspect: float, rng: random.Random) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Cut a convex shard into two or three convex pieces (uv coordinates).

    Returns ``()`` when no cut leaves every piece a usable size.
    """
    physical = [(x * aspect, y) for x, y in shard.polygon]
    total = _polygon_area(physical)
    radius = shard_radius(shard, aspect)

    def cut(points):
        for _ in range(6):
            angle = rng.uniform(0.0, math.pi)
            nx, ny = math.cos(angle), math.sin(angle)
            px = sum(x for x, _ in points) / len(points) + rng.uniform(-0.2, 0.2) * radius
            py = sum(y for _, y in points) / len(points) + rng.uniform(-0.2, 0.2) * radius
            limit = px * nx + py * ny
            first = _clip_cell(points, nx, ny, limit)
            second = _clip_cell(points, -nx, -ny, -limit)
            if (len(first) >= 3 and len(second) >= 3
                    and min(_polygon_area(first), _polygon_area(second)) > 0.18 * _polygon_area(points)):
                return first, second
        return None

    halves = cut(physical)
    if halves is None:
        return ()
    pieces = list(halves)
    if rng.random() < 0.35:
        larger = max(range(2), key=lambda k: _polygon_area(pieces[k]))
        again = cut(pieces[larger])
        if again is not None and min(_polygon_area(p) for p in again) > 0.10 * total:
            pieces[larger:larger + 1] = list(again)
    return tuple(tuple((x / aspect, y) for x, y in piece) for piece in pieces)


def _exits(paths: _Paths, index: int, kick: np.ndarray, start: float, offset: float, extent: float,
           carried: np.ndarray | None = None) -> bool:
    """Does a piece with this kick end fully outside the frame (conservatively)?

    ``carried`` is displacement already fixed by an earlier event stage.
    """
    end = paths.point(index, PATH_END) + kick * max(PATH_END - start, 0.0)
    if carried is not None:
        end = end + carried
    w = 3.0 - end[2]
    if w <= 0.1:
        return False
    scale = 3.0 / w
    reach = (offset + extent) * 1.1 + 0.02
    ux, uy = end[0] / paths.aspect * scale + 0.5, -end[1] * scale + 0.5
    rx, ry = reach * scale / paths.aspect, reach * scale
    return ux + rx < 0.0 or ux - rx > 1.0 or uy + ry < 0.0 or uy - ry > 1.0


def _leave_the_frame(paths: _Paths, index: int, kick: np.ndarray, start: float,
                     offset: float, extent: float, carried: np.ndarray | None = None) -> np.ndarray:
    def exits(candidate):
        return _exits(paths, index, candidate, start, offset, extent, carried)

    if exits(kick):
        return kick
    lo, hi = 0.0, 1.0
    if exits(np.zeros(3)):
        for _ in range(12):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if exits(kick * mid) else (lo, mid)
        return kick * lo
    # Even without the kick this piece would end too close: push it outward.
    outward = np.array([paths.dx[index], paths.dy[index], 0.0])
    push = 0.25
    for _ in range(16):
        if exits(outward * push):
            return outward * push
        push *= 1.6
    return outward * push


def _centroid(polygon) -> tuple[float, float]:
    return (sum(x for x, _ in polygon) / len(polygon), sum(y for _, y in polygon) / len(polygon))


def _drift(rng: random.Random, aspect: float, origin, point, speed: tuple[float, float]) -> np.ndarray:
    away = np.array([(point[0] - origin[0]) * aspect, origin[1] - point[1], rng.uniform(-0.3, 0.3)])
    away /= max(float(np.linalg.norm(away)), 1e-9)
    return away * rng.uniform(*speed)


def _whole(shard: GlassShard, radius: float, **event) -> GlassPiece:
    return GlassPiece(shard, shard.center, radius, **event)


def solve_glass_pieces(
    shards: tuple[GlassShard, ...],
    aspect: float,
    direction: object,
    depth: float,
    seed: int,
    *,
    collisions: bool,
    reshatter: bool,
) -> tuple[GlassPiece, ...]:
    """Rendered pieces for one run: the shards, their collisions and splits."""
    radii = [shard_radius(shard, aspect) for shard in shards]
    base = _Paths(shards, aspect, direction, depth)
    rng = random.Random(f"glass-dynamics:{seed}")
    spin_scale = 0.5 + 0.5 * depth
    kicks: dict[int, tuple[float, np.ndarray, tuple[float, float, float, float]]] = {}
    split_at: dict[int, float] = {}
    crashes: list[tuple[float, int, int, np.ndarray, float]] = []

    if collisions:
        # Crashes are chosen on the unlayered paths: a crash pair shares one depth
        # layer, which leaves their relative motion (and so the crash) unchanged.
        used: set[int] = set()
        budget = max(2, round(len(shards) * _MAX_COLLISIONS))
        for lo, hi, i, j in _collision_candidates(base):
            if budget <= 0:
                break
            if i in used or j in used:
                continue
            time = _contact_time(base, i, j, lo, hi)
            a, b = base.point(i, time), base.point(j, time)
            normal = b - a
            length = float(np.linalg.norm(normal))
            if length < 1e-9:
                continue
            normal /= length
            closing = float(np.dot(base.velocity(i, time) - base.velocity(j, time), normal))
            if closing <= 0.0:
                continue
            crashes.append((time, i, j, normal, closing))
            used.update((i, j))
            budget -= 1
    layers = separation_layers(base, tuple((i, j) for _time, i, j, _normal, _closing in crashes))
    paths = _Paths(shards, aspect, direction, depth, layers)
    if not collisions and not reshatter:
        return tuple(_whole(shard, radius, layer=float(layers[index]))
                     for index, (shard, radius) in enumerate(zip(shards, radii)))

    if collisions:
        for time, i, j, normal, closing in crashes:
            impulse = 0.5 * (1.0 + _RESTITUTION) * closing
            tangent = np.cross(normal, np.array(_random_axis(rng)))
            tangent /= max(float(np.linalg.norm(tangent)), 1e-9)
            for index, sign in ((i, -1.0), (j, 1.0)):
                scatter = tangent * impulse * rng.uniform(-0.3, 0.3)
                rate = rng.choice((-1.0, 1.0)) * rng.uniform(5.0, 12.0) * spin_scale
                kicks[index] = (time, sign * impulse * normal + scatter, (*_random_axis(rng), rate))
                if reshatter:
                    split_at[index] = time
    else:
        for index in range(len(shards)):
            if rng.random() < RANDOM_SPLIT_CHANCE:
                delay = float(paths.delay[index])
                split_at[index] = delay + rng.uniform(0.12, 0.55) * (PATH_END - delay)

    pieces: list[GlassPiece] = []
    for index, shard in enumerate(shards):
        radius = radii[index]
        layer = float(layers[index])
        event = kicks.get(index)
        base_kick = event[1] if event else np.zeros(3)
        split = split_at.get(index)
        children = split_polygon(shard, aspect, rng) if split is not None else ()
        if not children:
            if event is None:
                pieces.append(_whole(shard, radius, layer=layer))
                continue
            time, kick, spin = event
            kick = _leave_the_frame(paths, index, kick, time, 0.0, radius)
            pieces.append(_whole(shard, radius, kick=(*map(float, kick), time), spin=spin, layer=layer))
            continue
        pieces.append(_whole(shard, radius, life=(0.0, split), layer=layer))
        for polygon in children:
            ux, uy = _centroid(polygon)
            drift = _drift(rng, aspect, shard.center, (ux, uy), (0.25, 0.6))
            offset = math.hypot((ux - shard.center[0]) * aspect, uy - shard.center[1])
            extent = max(math.hypot((x - ux) * aspect, y - uy) for x, y in polygon)
            kick = _leave_the_frame(paths, index, base_kick + drift, split, offset, extent)
            rate = rng.choice((-1.0, 1.0)) * rng.uniform(4.0, 10.0) * spin_scale
            spin = (*_random_axis(rng), rate)
            child = GlassShard((ux, uy), polygon, shard.variation)
            # Second crack: after an impact it follows at once; otherwise at random later.
            if collisions:
                cracks_again = rng.random() < IMPACT_SECOND_SPLIT_CHANCE
                second = split + rng.uniform(0.02, 0.07)
            else:
                cracks_again = rng.random() < SECOND_SPLIT_CHANCE
                second = split + rng.uniform(0.08, 0.35) * (PATH_END - split)
            grandchildren = (split_polygon(child, aspect, rng)
                             if cracks_again and second < PATH_END - 0.05 else ())
            if not grandchildren:
                pieces.append(GlassPiece(child, shard.center, radius, life=(split, NO_EVENT),
                                         kick=(*map(float, kick), split), spin=spin, layer=layer))
                continue
            pieces.append(GlassPiece(child, shard.center, radius, life=(split, second),
                                     kick=(*map(float, kick), split), spin=spin, layer=layer))
            carried = kick * (PATH_END - split)
            for piece_polygon in grandchildren:
                gx, gy = _centroid(piece_polygon)
                grand_offset = math.hypot((gx - shard.center[0]) * aspect, gy - shard.center[1])
                grand_extent = max(math.hypot((x - gx) * aspect, y - gy) for x, y in piece_polygon)
                kick2 = _leave_the_frame(paths, index, _drift(rng, aspect, (ux, uy), (gx, gy), (0.2, 0.5)),
                                         second, grand_offset, grand_extent, carried)
                rate2 = rng.choice((-1.0, 1.0)) * rng.uniform(4.0, 10.0) * spin_scale
                pieces.append(GlassPiece(
                    GlassShard((gx, gy), piece_polygon, shard.variation), shard.center, radius,
                    life=(second, NO_EVENT), kick=(*map(float, kick), split), spin=spin,
                    spin_pivot=(ux, uy), kick2=(*map(float, kick2), second), spin2=(*_random_axis(rng), rate2),
                    layer=layer,
                ))
    return tuple(pieces)


EXTRA_FLOATS = 23


def piece_extras(piece: GlassPiece) -> tuple[float, ...]:
    """The per-vertex event floats GLASS_VERTEX reads after the prism data.

    life2, kick4, spin4, pivot2 (stage 1), kick4, spin4, pivot2 (stage 2), layer.
    """
    pivot = piece.spin_pivot if piece.spin_pivot is not None else piece.shard.center
    return (*piece.life, *piece.kick, *piece.spin, *pivot,
            *piece.kick2, *piece.spin2, *piece.shard.center, piece.layer)


__all__ = [
    "GlassPiece",
    "NO_EVENT",
    "PATH_END",
    "EXTRA_FLOATS",
    "IMPACT_SECOND_SPLIT_CHANCE",
    "LAYER_RANGE",
    "RANDOM_SPLIT_CHANCE",
    "SECOND_SPLIT_CHANCE",
    "piece_extras",
    "separation_layers",
    "shard_radius",
    "solve_glass_pieces",
    "split_polygon",
]
