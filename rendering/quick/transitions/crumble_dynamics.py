"""Per-run Crumble chunk motion and optional build-time slab collisions.

Crumble motion stays analytic on the GPU (``CRUMBLE_VERTEX``): every wall chunk
is released at its own time, then falls, drifts sideways, comes forward and
tumbles. The per-chunk values that shape that path -- release time, sideways
drift and tumble axis -- are drawn here once per run (seeded), so the path is
known exactly on the CPU and identical on every GPU.

With collisions on, the collapse is simulated once per run, on COMPUTE with the
rest of the run geometry, and baked into a small motion table: for each chunk,
``MOTION_FRAMES`` keyframes of (offset x, y, z, extra tumble angle) that the
shader interpolates and adds to the analytic path. There is no per-frame
simulation, clock or state at render time; with collisions off the table is all
zeros and the motion is the analytic path alone.

The simulation keeps slabs from passing through each other while they are in
view: overlapping slabs (flat discs that sweep a growing volume as they tumble)
exchange mass-weighted impulses (stone: low restitution) and are pushed apart,
so a fast slab falling onto a slower one drives it down instead of falling
through it. A standing wall slab struck by a falling one is knocked loose: it
is released at that moment. Every chunk still leaves the frame.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
import random
import zlib

import numpy as np

# Constants shared with CRUMBLE_VERTEX; the path below must match it exactly.
PATH_END = 0.98
MOTION_FRAMES = 64                 # keyframes over [0, PATH_END]
MOTION_ATTRIBUTES = (4, 3)         # aRelease (begin, drift, table row, 0), aAxis

_STEPS_PER_FRAME = 2
_RESTITUTION = 0.30                # stone is less lively than glass (0.45)
_XY_REACH = 0.72                   # of the circumradius: a wall cell's typical half-width
_REST_GAP = 0.85                   # neighbours must close to this share of their rest spacing
_SEPARATION = 0.45                 # share of an overlap removed per step
_SPIN = 0.6                        # tumble kick per unit of contact speed and radius
_FADE_FRAMES = 15                  # an offset that would hold a chunk in view fades out


@dataclass(frozen=True, slots=True)
class ChunkMotion:
    """One chunk's per-run path constants (see ``CRUMBLE_VERTEX``)."""

    begin: float
    drift: float
    axis: tuple[float, float, float]

    def floats(self, row: int) -> tuple[float, ...]:
        """aRelease (begin, drift, motion-table row, 0) and aAxis."""
        return (self.begin, self.drift, float(row), 0.0, *self.axis)


def release_motions(shards, seed: float, weight_mode: float) -> tuple[ChunkMotion, ...]:
    """Seeded release time, drift and tumble axis per chunk.

    Weighting: 0 top first, 1 bottom first, 2 each chunk top- or bottom-ranked
    at random, 3 one of those three per run, 4 by the chunk's age variation.
    Release runs from 0.30 to 0.58 of the transition, jittered by +-0.02.
    """
    rng = random.Random(f"crumble-release:{float(seed)!r}")
    mode = float(weight_mode)
    if mode == 3.0:
        mode = (0.0, 1.0, 2.0)[rng.randrange(3)]
    motions = []
    for shard in shards:
        v = shard.center[1]
        if mode < 0.5:
            rank = v
        elif mode < 1.5:
            rank = 1.0 - v
        elif mode < 2.5:
            rank = v if rng.random() < 0.5 else 1.0 - v
        else:
            rank = shard.variation
        begin = 0.30 + min(1.0, max(0.0, rank)) * 0.28 + (rng.random() - 0.5) * 0.04
        drift = rng.random() - 0.5
        while True:
            axis = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
            length = math.sqrt(sum(c * c for c in axis))
            if length > 1e-3:
                break
        motions.append(ChunkMotion(begin, drift, tuple(c / length for c in axis)))
    return tuple(motions)


def still_motion_table(count: int) -> np.ndarray:
    """The motion table without collisions: the analytic path alone."""
    return np.zeros((count, MOTION_FRAMES, 4), dtype=np.float32)


class _Wall:
    """The analytic chunk paths (CRUMBLE_VERTEX) for every chunk, vectorised."""

    def __init__(self, shards, motions, aspect: float, depth: float, thickness: float):
        self.aspect, self.depth = float(aspect), float(depth)
        u = np.array([s.center[0] for s in shards], dtype=np.float64)
        v = np.array([s.center[1] for s in shards], dtype=np.float64)
        self.cx, self.cy = (u - 0.5) * aspect, 0.5 - v
        self.var = np.array([s.variation for s in shards], dtype=np.float64)
        self.radius = np.array([max(math.hypot((x - s.center[0]) * aspect, y - s.center[1])
                                    for x, y in s.polygon) for s in shards], dtype=np.float64)
        self.slab = self.radius * 0.72 * float(thickness)
        self.begin = np.array([m.begin for m in motions], dtype=np.float64)
        self.drift = np.array([m.drift for m in motions], dtype=np.float64)
        self.fall = 3.1 + 1.9 * self.var
        self.sway = 0.25 + 0.25 * self.depth

    def state(self, t: float):
        """Positions, velocities (per unit progress), tumble angles and local phase at ``t``."""
        span = np.maximum(0.001, PATH_END - self.begin)
        raw = np.clip((t - self.begin) / span, 0.0, 1.0)
        local = raw * raw * (3.0 - 2.0 * raw)
        rate = np.where((raw > 0.0) & (raw < 1.0), 6.0 * raw * (1.0 - raw) / span, 0.0)
        fall = local * local
        position = np.stack((
            self.cx + self.drift * fall * self.sway,
            self.cy - fall * self.fall,
            self.depth * (0.38 * np.sin(math.pi * local) - 0.28 * fall),
        ), axis=1)
        velocity = np.stack((
            self.drift * self.sway * 2.0 * local * rate,
            -self.fall * 2.0 * local * rate,
            self.depth * (0.38 * math.pi * np.cos(math.pi * local) - 0.56 * local) * rate,
        ), axis=1)
        return position, velocity, local * (4.5 + 5.0 * self.var), local

    def out_extent(self, local, angle):
        """Half-extent out of the wall plane: slab thickness, then tumble sweep."""
        grow = np.clip(local / 0.12, 0.0, 1.0)
        grow = grow * grow * (3.0 - 2.0 * grow)
        return 0.5 * self.slab * grow + 0.65 * self.radius * np.minimum(1.0, np.abs(angle) / 1.5)

    def on_screen(self, position):
        w = np.maximum(1.55, 3.15 - position[:, 2])
        scale = 3.15 / w
        ux = position[:, 0] / self.aspect * scale + 0.5
        uy = -position[:, 1] * scale + 0.5
        rx, ry = self.radius * scale / self.aspect, self.radius * scale
        return (ux + rx > 0.0) & (ux - rx < 1.0) & (uy + ry > 0.0) & (uy - ry < 1.0)


def bake_crumble_motion(shards, motions, aspect: float, depth: float, thickness: float,
                        seed: float) -> tuple[tuple[ChunkMotion, ...], np.ndarray]:
    """Simulate the collapse once; return releases (some brought forward) and the table."""
    count = len(shards)
    if count < 2:
        return tuple(motions), still_motion_table(count)
    wall = _Wall(shards, motions, aspect, depth, thickness)
    rng = np.random.default_rng(zlib.crc32(f"crumble-contacts:{float(seed)!r}".encode()))
    mass = wall.radius ** 2
    rest = np.stack((wall.cx, wall.cy), axis=1)
    rest_gap = np.linalg.norm(rest[:, None, :] - rest[None, :, :], axis=2)
    xy_reach = _XY_REACH * wall.radius
    limit = np.minimum(xy_reach[:, None] + xy_reach[None, :], _REST_GAP * rest_gap)
    upper = np.triu(np.ones((count, count), dtype=bool), 1)
    offset = np.zeros((count, 3))
    velocity = np.zeros((count, 3))
    spin = np.zeros(count)
    spin_rate = np.zeros(count)
    touching_before = np.zeros((count, count), dtype=bool)
    table = still_motion_table(count)
    steps = (MOTION_FRAMES - 1) * _STEPS_PER_FRAME
    dt = PATH_END / steps
    for step in range(1, steps + 1):
        t = step * dt
        offset += velocity * dt
        spin += spin_rate * dt
        base, base_velocity, angle, local = wall.state(t)
        position = base + offset
        moving = t > wall.begin
        extent = wall.out_extent(local, angle + spin)
        seen = wall.on_screen(position)
        delta = position[None, :, :] - position[:, None, :]           # j - i
        planar = np.hypot(delta[..., 0], delta[..., 1])
        touching = (upper & (planar < limit)
                    & (np.abs(delta[..., 2]) < extent[:, None] + extent[None, :])
                    & (moving[:, None] | moving[None, :]) & (seen[:, None] | seen[None, :]))
        pairs = np.argwhere(touching)
        if pairs.size:
            _collide(wall, pairs, t, delta, planar, limit, touching_before, base_velocity,
                     velocity, offset, spin_rate, mass, moving, rng)
        touching_before = touching
        if step % _STEPS_PER_FRAME == 0:
            frame = step // _STEPS_PER_FRAME
            table[:, frame, :3] = offset
            table[:, frame, 3] = spin
    _leave_the_frame(wall, table)
    released = tuple(replace(motion, begin=float(wall.begin[index]))
                     for index, motion in enumerate(motions))
    return released, table


def _collide(wall, pairs, t, delta, planar, limit, touching_before, base_velocity,
             velocity, offset, spin_rate, mass, moving, rng) -> None:
    """One step of contact response for every overlapping pair at once."""
    count = len(mass)
    i, j = pairs[:, 0], pairs[:, 1]
    # A standing slab struck by a moving one is knocked loose now.
    for index in np.unique(pairs):
        if not moving[index]:
            wall.begin[index] = t
    normal = delta[i, j]
    length = np.linalg.norm(normal, axis=1, keepdims=True)
    normal = np.where(length > 1e-9, normal / np.maximum(length, 1e-9), np.array((0.0, -1.0, 0.0)))
    total = base_velocity + velocity
    closing = np.einsum("pc,pc->p", total[i] - total[j], normal)
    inverse = 1.0 / mass[i] + 1.0 / mass[j]
    impulse = np.where(closing > 0.0, (1.0 + _RESTITUTION) * closing / inverse, 0.0)
    fresh = ~touching_before[i, j]
    scatter = np.where(fresh, rng.uniform(-0.2, 0.2, len(i)), 0.0) * impulse
    tangent = np.cross(normal, np.array((0.0, 0.0, 1.0)))
    tangent /= np.maximum(np.linalg.norm(tangent, axis=1, keepdims=True), 1e-9)
    push = impulse[:, None] * normal + scatter[:, None] * tangent
    change = np.zeros((count, 3))
    np.add.at(change, i, -push / mass[i][:, None])
    np.add.at(change, j, push / mass[j][:, None])
    velocity += change
    # Push overlapping slabs apart in the wall plane; the heavier moves less.
    overlap = np.maximum(0.0, limit[i, j] - planar[i, j])
    flat = normal[:, :2] / np.maximum(np.linalg.norm(normal[:, :2], axis=1, keepdims=True), 1e-9)
    share_i = (mass[j] / (mass[i] + mass[j]))[:, None]
    separation = np.zeros((count, 2))
    np.add.at(separation, i, -flat * overlap[:, None] * _SEPARATION * share_i)
    np.add.at(separation, j, flat * overlap[:, None] * _SEPARATION * (1.0 - share_i))
    offset[:, :2] += separation
    # A fresh contact sets both slabs tumbling a little harder.
    kick = np.zeros(count)
    np.add.at(kick, i, np.where(fresh, impulse / mass[i], 0.0))
    np.add.at(kick, j, np.where(fresh, impulse / mass[j], 0.0))
    struck = kick > 0.0
    if struck.any():
        spin_rate[struck] += (rng.choice((-1.0, 1.0), int(struck.sum())) * kick[struck]
                              / np.maximum(wall.radius[struck], 0.02) * _SPIN
                              * rng.uniform(0.6, 1.0, int(struck.sum())))


def _leave_the_frame(wall: _Wall, table: np.ndarray) -> None:
    """Fade out, over the last frames, any offset that would hold a chunk in view."""
    base = wall.state(PATH_END)[0]
    held = wall.on_screen(base + table[:, -1, :3].astype(np.float64))
    if not held.any():
        return
    frames = np.arange(MOTION_FRAMES)
    fade = np.clip((MOTION_FRAMES - 1 - frames) / _FADE_FRAMES, 0.0, 1.0).astype(np.float32)
    table[held, :, :3] *= fade[None, :, None]


__all__ = [
    "MOTION_ATTRIBUTES",
    "MOTION_FRAMES",
    "PATH_END",
    "ChunkMotion",
    "bake_crumble_motion",
    "release_motions",
    "still_motion_table",
]
