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

_RESTITUTION = 0.45
_COLLISION_RADIUS = 0.80   # of the circumradius a tumbling shard sweeps
_SAMPLES = 120
_CRASH_SPEED = 0.20        # closing speed, as a fraction of the shards' speed
_MAX_COLLISIONS = 0.12     # at most this share of shards pairs up in a run
_LATEST_CRASH = 0.80       # later crashes would happen as the shards leave


@dataclass(frozen=True, slots=True)
class GlassPiece:
    """One rendered prism. ``shard`` carries its own polygon and fan centre."""

    shard: GlassShard
    pivot_center: tuple[float, float]   # the original shard's centre (path pivot)
    radius: float                       # the original shard's circumradius
    life: tuple[float, float] = (0.0, NO_EVENT)
    kick: tuple[float, float, float, float] = (0.0, 0.0, 0.0, NO_EVENT)
    spin: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)


def shard_radius(shard: GlassShard, aspect: float) -> float:
    cx, cy = shard.center
    return max(math.hypot((x - cx) * aspect, y - cy) for x, y in shard.polygon)


class _Paths:
    """Vectorised replica of GLASS_VERTEX's shard-centre path (position space)."""

    def __init__(self, shards, aspect: float, direction: object, depth: float):
        self.aspect = aspect
        self.depth = depth
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
        scale = 1.0 + 0.6 * depth / 3.0
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
        z = self.depth * (0.56 * np.sin(math.pi * local) - 0.6 * local * local)
        return np.stack((x, y, z), axis=-1)

    def point(self, index: int, t: float) -> np.ndarray:
        """One shard centre at one time (scalar twin of ``at``)."""
        delay = float(self.delay[index])
        local = min(1.0, max(0.0, (t - delay) / (PATH_END - delay)))
        travel = (0.12 * local + 0.88 * local * local) * float(self.exit[index])
        arc = math.sin(math.pi * local)
        return np.array((
            float(self.cx[index]) + float(self.dx[index]) * travel,
            float(self.cy[index]) + float(self.dy[index]) * travel - 0.16 * arc * local,
            self.depth * (0.56 * arc - 0.6 * local * local),
        ))

    def velocity(self, index: int, t: float) -> np.ndarray:
        h = 1e-4
        ahead, behind = min(t + h, PATH_END), max(t - h, 0.0)
        return (self.point(index, ahead) - self.point(index, behind)) / (ahead - behind)

    def launched(self, t) -> np.ndarray:
        t = np.atleast_1d(np.asarray(t, dtype=np.float64))
        return (t[None, :] - self.delay[:, None]) / (PATH_END - self.delay[:, None]) > 0.02


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


def _exits(paths: _Paths, index: int, kick: np.ndarray, start: float, offset: float, extent: float) -> bool:
    """Does a piece with this kick end fully outside the frame (conservatively)?"""
    end = paths.point(index, PATH_END) + kick * max(PATH_END - start, 0.0)
    w = 3.0 - end[2]
    if w <= 0.1:
        return False
    scale = 3.0 / w
    reach = (offset + extent) * 1.1 + 0.02
    ux, uy = end[0] / paths.aspect * scale + 0.5, -end[1] * scale + 0.5
    rx, ry = reach * scale / paths.aspect, reach * scale
    return ux + rx < 0.0 or ux - rx > 1.0 or uy + ry < 0.0 or uy - ry > 1.0


def _leave_the_frame(paths: _Paths, index: int, kick: np.ndarray, start: float,
                     offset: float, extent: float) -> np.ndarray:
    if _exits(paths, index, kick, start, offset, extent):
        return kick
    lo, hi = 0.0, 1.0
    if _exits(paths, index, np.zeros(3), start, offset, extent):
        for _ in range(12):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if _exits(paths, index, kick * mid, start, offset, extent) else (lo, mid)
        return kick * lo
    # Even without the kick this piece would end too close: push it outward.
    outward = np.array([paths.dx[index], paths.dy[index], 0.0])
    push = 0.25
    for _ in range(16):
        if _exits(paths, index, outward * push, start, offset, extent):
            return outward * push
        push *= 1.6
    return outward * push


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
    if not collisions and not reshatter:
        return tuple(_whole(shard, radius) for shard, radius in zip(shards, radii))

    rng = random.Random(f"glass-dynamics:{seed}")
    paths = _Paths(shards, aspect, direction, depth)
    spin_scale = 0.5 + 0.5 * depth
    kicks: dict[int, tuple[float, np.ndarray, tuple[float, float, float, float]]] = {}
    split_at: dict[int, float] = {}

    if collisions:
        used: set[int] = set()
        budget = max(2, round(len(shards) * _MAX_COLLISIONS))
        for lo, hi, i, j in _collision_candidates(paths):
            if budget <= 0:
                break
            if i in used or j in used:
                continue
            time = _contact_time(paths, i, j, lo, hi)
            a, b = paths.point(i, time), paths.point(j, time)
            normal = b - a
            length = float(np.linalg.norm(normal))
            if length < 1e-9:
                continue
            normal /= length
            closing = float(np.dot(paths.velocity(i, time) - paths.velocity(j, time), normal))
            if closing <= 0.0:
                continue
            impulse = 0.5 * (1.0 + _RESTITUTION) * closing
            tangent = np.cross(normal, np.array(_random_axis(rng)))
            tangent /= max(float(np.linalg.norm(tangent)), 1e-9)
            for index, sign in ((i, -1.0), (j, 1.0)):
                scatter = tangent * impulse * rng.uniform(-0.3, 0.3)
                rate = rng.choice((-1.0, 1.0)) * rng.uniform(5.0, 12.0) * spin_scale
                kicks[index] = (time, sign * impulse * normal + scatter, (*_random_axis(rng), rate))
                if reshatter:
                    split_at[index] = time
            used.update((i, j))
            budget -= 1
    else:
        for index in range(len(shards)):
            if rng.random() < RANDOM_SPLIT_CHANCE:
                delay = float(paths.delay[index])
                split_at[index] = delay + rng.uniform(0.12, 0.55) * (PATH_END - delay)

    pieces: list[GlassPiece] = []
    for index, shard in enumerate(shards):
        radius = radii[index]
        event = kicks.get(index)
        base_kick = event[1] if event else np.zeros(3)
        split = split_at.get(index)
        children = split_polygon(shard, aspect, rng) if split is not None else ()
        if not children:
            if event is None:
                pieces.append(_whole(shard, radius))
                continue
            time, kick, spin = event
            kick = _leave_the_frame(paths, index, kick, time, 0.0, radius)
            pieces.append(_whole(shard, radius, kick=(*map(float, kick), time), spin=spin))
            continue
        pieces.append(_whole(shard, radius, life=(0.0, split)))
        for polygon in children:
            ux = sum(x for x, _ in polygon) / len(polygon)
            uy = sum(y for _, y in polygon) / len(polygon)
            away = np.array([(ux - shard.center[0]) * aspect, shard.center[1] - uy, rng.uniform(-0.3, 0.3)])
            away /= max(float(np.linalg.norm(away)), 1e-9)
            drift = away * rng.uniform(0.25, 0.6)
            offset = math.hypot((ux - shard.center[0]) * aspect, uy - shard.center[1])
            extent = max(math.hypot((x - ux) * aspect, y - uy) for x, y in polygon)
            kick = _leave_the_frame(paths, index, base_kick + drift, split, offset, extent)
            rate = rng.choice((-1.0, 1.0)) * rng.uniform(4.0, 10.0) * spin_scale
            child = GlassShard((ux, uy), polygon, shard.variation)
            pieces.append(GlassPiece(child, shard.center, radius, life=(split, NO_EVENT),
                                     kick=(*map(float, kick), split), spin=(*_random_axis(rng), rate)))
    return tuple(pieces)


def piece_extras(piece: GlassPiece) -> tuple[float, ...]:
    """The 12 per-vertex event floats GLASS_VERTEX reads after the prism data."""
    return (*piece.life, *piece.kick, *piece.spin, *piece.shard.center)


__all__ = [
    "GlassPiece",
    "NO_EVENT",
    "PATH_END",
    "RANDOM_SPLIT_CHANCE",
    "piece_extras",
    "shard_radius",
    "solve_glass_pieces",
    "split_polygon",
]
