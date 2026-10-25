"""Extruded Bubble wake trails: the water a bubble has passed through, carried by the water.

A rising bubble leaves a wake behind it: the water it disturbed stays where the bubble was (dragged after it for a
moment, then at rest) and drifts with the water's own slow motion. So a trail is the bubble's own path history, not a
curve drawn from a direction: when the music turns the bubble, the trail shows the turn where it happened, and its far
end keeps drifting with the water whatever the bubble does next.

``WakeField`` keeps every trailing bubble's history in one pooled array. A bubble lays down a point each time it has
moved a fixed share of its trail's reach (``WAKE_POINTS`` points always span the whole trail, whatever its speed); the
water moves (drag, swirl, viscous smoothing) in one batched step ``STEP_SECONDS`` apart for all wakes together. Per tick
only plain arithmetic runs: numpy calls are few and batched, since each holds the GIL the GUI and render threads need
(a per-wake, per-tick resample starved them to 4 fps). The GPU draws the head segment from the bubble itself.
"""
from __future__ import annotations

import math
import random

import numpy as np

from core.constants.extruded_bubble_world import WAKE_POINTS, WORLD_UNIT

STEP_SECONDS = 0.1            # the water moves in one batched step this often
HISTORY_SECONDS = 8.0         # the oldest water a trail can still show
ENTRAIN = 0.45                # share of the bubble's velocity its wake water is first dragged with ..
ENTRAIN_SECONDS = 0.7         # .. decaying over this
FLOW = 0.012 * WORLD_UNIT     # the water's own slow swirl (world units a second): every trail drifts in it alike
LENGTH = (7.0, 15.0)          # a trail's longest reach, in its bubble's radii (stable per bubble)
DIFFUSION = 1.2               # how fast the disturbed water smooths out (viscosity): older wiggles relax into sweeps


def trails(ident: int, share: float) -> bool:
    """Whether bubble ``ident`` trails a wake at Wake Trails ``share`` (stable: the share grows the same set)."""
    return share > 0.0 and random.Random(ident * 7919 + 13).random() < share


def water_flow(points: np.ndarray, phase: float) -> np.ndarray:
    """The water's slow, coherent swirl at ``points`` (... x 3): neighbouring trails drift together."""
    x, y, z = points[..., 0] / WORLD_UNIT, points[..., 1] / WORLD_UNIT, points[..., 2] / WORLD_UNIT
    return FLOW * np.stack([np.sin(2.1 * y + 1.3 * z + 0.45 * phase),
                            0.5 * np.sin(1.7 * x - 1.9 * z + 0.3 * phase),
                            np.cos(1.6 * x + 2.3 * y + 0.38 * phase)], axis=-1)


class WakeField:
    """Every trailing bubble's wake: ``points[slot, k]`` newest first (k = 0 nearest the bubble)."""

    def __init__(self, capacity: int):
        self.points = np.zeros((capacity, WAKE_POINTS, 3))
        self.carry = np.zeros((capacity, WAKE_POINTS, 3))
        self.age = np.zeros((capacity, WAKE_POINTS))
        self.count = np.zeros(capacity, dtype=int)
        self._free = list(range(capacity - 1, -1, -1))
        self._slots: dict[int, int] = {}
        self._spacing: dict[int, float] = {}
        self._last: dict[int, tuple[float, float, float]] = {}
        self._newest: dict[int, tuple[float, float, float]] = {}
        self._flat: dict[int, tuple[tuple[float, ...], float]] = {}      # path floats, its length (head excluded)
        self._since = 0.0

    def __contains__(self, ident: int) -> bool:
        return ident in self._slots

    def __len__(self) -> int:
        return len(self._slots)

    def idents(self) -> list[int]:
        return list(self._slots)

    def add(self, ident: int, radius: float, head) -> bool:
        if not self._free:
            return False
        slot = self._free.pop()
        self._slots[ident] = slot
        self._spacing[ident] = radius * random.Random(ident * 104729 + 7).uniform(*LENGTH) / (WAKE_POINTS - 1)
        self._lay(ident, slot, head, (0.0, 0.0, 0.0), fresh=True)
        return True

    def remove(self, ident: int) -> None:
        slot = self._slots.pop(ident, None)
        if slot is None:
            return
        self.count[slot] = 0
        self._free.append(slot)
        for table in (self._spacing, self._last, self._newest, self._flat):
            table.pop(ident, None)

    def _lay(self, ident: int, slot: int, head, velocity, fresh: bool = False) -> None:
        """A new point where the bubble is now, the older ones moved one place back."""
        if fresh:
            self.count[slot] = 0
        else:
            self.points[slot, 1:] = self.points[slot, :-1]
            self.carry[slot, 1:] = self.carry[slot, :-1]
            self.age[slot, 1:] = self.age[slot, :-1]
        self.points[slot, 0] = head
        self.carry[slot, 0] = tuple(ENTRAIN * v for v in velocity)
        self.age[slot, 0] = 0.0
        self.count[slot] = min(int(self.count[slot]) + 1, WAKE_POINTS)
        self._last[ident] = tuple(head)
        self._newest[ident] = tuple(head)
        self._cache(ident, slot)

    def _cache(self, ident: int, slot: int) -> None:
        n = int(self.count[slot])
        path = self.points[slot, :n]
        length = float(np.linalg.norm(np.diff(path, axis=0), axis=1).sum()) if n > 1 else 0.0
        flat = path.reshape(-1).tolist()
        flat.extend(flat[-3:] * (WAKE_POINTS - n))
        self._flat[ident] = (tuple(flat), length)

    def follow(self, ident: int, head, dt: float, jump: float) -> None:
        """The bubble (at ``head``) moved this tick: lay a point once it is a spacing past the newest."""
        slot = self._slots[ident]
        last = self._last[ident]
        moved = math.dist(head, last)
        if moved > jump:                       # a re-entry is not motion: start a fresh wake
            self._lay(ident, slot, head, (0.0, 0.0, 0.0), fresh=True)
            return
        self._last[ident] = tuple(head)
        if math.dist(head, self._newest[ident]) >= self._spacing[ident]:
            velocity = tuple((h - l) / dt for h, l in zip(head, last)) if dt > 0.0 else (0.0, 0.0, 0.0)
            self._lay(ident, slot, head, velocity)

    def flow(self, dt: float, phase: float) -> None:
        """The water moves: one batched step every ``STEP_SECONDS`` for all wakes together."""
        self._since += dt
        if self._since < STEP_SECONDS or not self._slots:
            self._since = min(self._since, STEP_SECONDS)
            return
        step, self._since = self._since, 0.0
        live = np.fromiter(self._slots.values(), dtype=int)
        points, carry, age = self.points[live], self.carry[live], self.age[live]
        carry *= math.exp(-step / ENTRAIN_SECONDS)
        points += (carry + water_flow(points, phase)) * step
        age += step
        # Viscous smoothing, stronger with age: the fresh wake keeps the bubble's exact course.
        # Only between a wake's own points: its last one has no neighbour beyond (unused slots hold stale points).
        inner = np.arange(1, WAKE_POINTS - 1)[None, :] < (self.count[live] - 1)[:, None]
        rate = np.clip(DIFFUSION * step * np.minimum(age[:, 1:-1], 1.0), 0.0, 0.25) * inner
        points[:, 1:-1] += rate[..., None] * (points[:, :-2] + points[:, 2:] - 2.0 * points[:, 1:-1])
        self.points[live], self.carry[live], self.age[live] = points, carry, age
        counts = np.minimum(self.count[live], (age < HISTORY_SECONDS).sum(axis=1))
        self.count[live] = np.maximum(counts, 1)
        for ident, slot in self._slots.items():
            self._newest[ident] = tuple(self.points[slot, 0].tolist())
            self._cache(ident, slot)

    def record(self, ident: int, head) -> tuple[float, ...]:
        """(length, span, path floats): the trail from ``head`` (the bubble, or where it last was) back along its
        history; ``span`` is how many segments the GPU draws, easing its tail in as the next point nears."""
        slot = self._slots[ident]
        flat, length = self._flat[ident]
        n = int(self.count[slot])
        lead = math.dist(head, self._newest[ident])
        span = float(n)
        if n == WAKE_POINTS:
            span -= min(lead / self._spacing[ident], 1.0)
        return (length + lead, max(span, 0.0), *flat)


__all__ = ["DIFFUSION", "ENTRAIN", "FLOW", "HISTORY_SECONDS", "STEP_SECONDS", "WakeField", "trails", "water_flow"]
