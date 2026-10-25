"""Extruded Bubble wake trails: the water a bubble has passed through, carried by the water.

A rising bubble leaves a wake behind it: the water it disturbed stays where the bubble was (dragged after it for a
moment, then at rest) and drifts with the water's own slow motion. So a trail is the bubble's own path history, not a
curve drawn from a direction: when the music turns the bubble, the trail shows the turn where it happened, and its far
end keeps drifting with the water whatever the bubble does next.

``WakeField`` keeps every trailing bubble's history in one pooled array. A bubble lays down a point each time it has
moved a fixed ``spacing`` (``WAKE_POINTS`` points always span the whole trail, whatever its speed); the water moves
(drag, swirl, viscous smoothing) every tick in one batched step for all wakes together. Numpy calls are few and
batched, since each holds the GIL the GUI and render threads need (a per-wake, per-tick resample starved them to 4 fps).

Everything drawn in a wake belongs to the water, so it is placed by its **water index**: how far, in spacings, the
bubble had travelled when it passed that water. The bubble itself is at ``water`` (the points laid plus how far it is
into the next spacing); the water ``c`` spacings behind it stays fixed in the water whatever the bubble does next. The
GPU places the sheet's shape and its beads by that index, so laying a point moves nothing (placing them by a fraction
of the chain's segments made beads slide with the bubble and jump back at every new point, and the sheet's root snap).
"""
from __future__ import annotations

import math
import random

import numpy as np

from core.constants.extruded_bubble_world import WAKE_POINTS, WORLD_UNIT

HISTORY_SECONDS = 8.0         # the oldest water a trail can still show
ENTRAIN = 0.45                # share of the bubble's velocity its wake water is first dragged with ..
ENTRAIN_SECONDS = 0.7         # .. decaying over this
FLOW = 0.012 * WORLD_UNIT     # the water's own slow swirl (world units a second): every trail drifts in it alike
LENGTH = (7.7, 16.5)          # a trail's longest reach, in its bubble's radii (stable per bubble)
DIFFUSION = 1.2               # how fast the disturbed water smooths out (viscosity): older wiggles relax into sweeps
RADIUS_SECONDS = 0.4          # the wake's body follows its bubble's size this slowly (the beat swell is the root's)


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
        self._laid: dict[int, int] = {}                 # points laid since the wake began (its water index base)
        self._since: dict[int, float] = {}              # seconds since the newest point was laid
        self._radius: dict[int, float] = {}             # the bubble's size, followed slowly
        self._newest: dict[int, tuple[float, float, float]] = {}
        self._flat: dict[int, tuple[float, ...]] = {}

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
        self._laid[ident] = 0
        self._radius[ident] = radius
        self._lay(ident, slot, head, (0.0, 0.0, 0.0), fresh=True)
        return True

    def remove(self, ident: int) -> None:
        slot = self._slots.pop(ident, None)
        if slot is None:
            return
        self.count[slot] = 0
        self._free.append(slot)
        for table in (self._spacing, self._laid, self._since, self._radius, self._newest, self._flat):
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
        self._laid[ident] += 1
        self._since[ident] = 0.0
        self._newest[ident] = tuple(head)
        flat = self.points[slot].reshape(-1).tolist()
        n = int(self.count[slot])
        self._flat[ident] = tuple(flat[:3 * n] + flat[3 * n - 3:3 * n] * (WAKE_POINTS - n))

    def follow(self, ident: int, head, radius: float, dt: float, jump: float) -> None:
        """The bubble (at ``head``) moved this tick: lay a point once it is a spacing past the newest."""
        slot = self._slots[ident]
        self._radius[ident] += (radius - self._radius[ident]) * (1.0 - math.exp(-max(dt, 0.0) / RADIUS_SECONDS))
        self._since[ident] += dt
        newest = self._newest[ident]
        lead = math.dist(head, newest)
        if lead > jump:                        # a re-entry is not motion: start a fresh wake
            self._laid[ident] = 0
            self._lay(ident, slot, head, (0.0, 0.0, 0.0), fresh=True)
            return
        if lead >= self._spacing[ident]:
            # Its drag: the bubble's mean velocity over the spacing it just crossed (one tick's step is noise).
            since = max(self._since[ident], 1e-3)
            self._lay(ident, slot, head, tuple((h - n) / since for h, n in zip(head, newest)))

    def flow(self, dt: float, phase: float) -> None:
        """The water moves, every tick, in one batched step for all wakes together."""
        if not self._slots or dt <= 0.0:
            return
        idents = list(self._slots)
        live = np.fromiter(self._slots.values(), dtype=int)
        points, carry, age = self.points[live], self.carry[live], self.age[live]
        carry *= math.exp(-dt / ENTRAIN_SECONDS)
        points += (carry + water_flow(points, phase)) * dt
        age += dt
        # Viscous smoothing, stronger with age: the fresh wake keeps the bubble's exact course. Only between a wake's
        # own points: its last one has no neighbour beyond (unused slots hold stale points).
        counts = self.count[live]
        inner = np.arange(1, WAKE_POINTS - 1)[None, :] < (counts - 1)[:, None]
        rate = np.clip(DIFFUSION * dt * np.minimum(age[:, 1:-1], 1.0), 0.0, 0.25) * inner
        points[:, 1:-1] += rate[..., None] * (points[:, :-2] + points[:, 2:] - 2.0 * points[:, 1:-1])
        self.points[live], self.carry[live], self.age[live] = points, carry, age
        counts = np.maximum(np.minimum(counts, (age < HISTORY_SECONDS).sum(axis=1)), 1)
        self.count[live] = counts
        rows = points.reshape(len(live), -1).tolist()
        for ident, row, n in zip(idents, rows, counts.tolist()):
            self._newest[ident] = tuple(row[:3])
            self._flat[ident] = tuple(row[:3 * n] + row[3 * n - 3:3 * n] * (WAKE_POINTS - n))

    def record(self, ident: int, head) -> tuple[float, ...]:
        """(spacing, count, water, lead, radius, path floats) of the trail behind ``head`` (the bubble, or where it
        last was): ``water`` is the bubble's continuous water index, ``lead`` how far (in spacings) it is past its
        newest point, ``radius`` its size followed slowly."""
        spacing = self._spacing[ident]
        lead = min(math.dist(head, self._newest[ident]) / spacing, 1.0)
        n = int(self.count[self._slots[ident]])
        return (spacing, float(n), float(self._laid[ident]) + lead, lead, self._radius[ident], *self._flat[ident])


__all__ = ["DIFFUSION", "ENTRAIN", "FLOW", "HISTORY_SECONDS", "WakeField", "trails", "water_flow"]
