"""Extruded Bubble wake trails: the water a bubble has passed through, carried by the water.

A rising bubble leaves a wake behind it: the water it disturbed stays where the bubble was (dragged after it for a
moment, then at rest) and drifts with the water's own slow motion. So a trail is the bubble's own path history, not a
curve drawn from a direction: when the music turns the bubble, the trail shows the turn where it happened, and its far
end keeps drifting with the water whatever the bubble does next.

``WakePath`` keeps that history on the logical tick (points sampled every ``SAMPLE_SECONDS``, each with its share of
the bubble's velocity, decaying); ``resampled`` hands the GPU ``WAKE_POINTS`` points spaced evenly along the trail from
just behind the bubble to its capped length. Pure numpy; no rendering or clock of its own.
"""
from __future__ import annotations

import math
import random

import numpy as np

from core.constants.extruded_bubble_world import WAKE_POINTS, WORLD_UNIT

SAMPLE_SECONDS = 0.1          # one history point a tenth of a second
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
    """The water's slow, coherent swirl at ``points`` (n x 3): neighbouring trails drift together."""
    x, y, z = points[:, 0] / WORLD_UNIT, points[:, 1] / WORLD_UNIT, points[:, 2] / WORLD_UNIT
    return FLOW * np.stack([np.sin(2.1 * y + 1.3 * z + 0.45 * phase),
                            0.5 * np.sin(1.7 * x - 1.9 * z + 0.3 * phase),
                            np.cos(1.6 * x + 2.3 * y + 0.38 * phase)], axis=-1)


class WakePath:
    """One bubble's wake: its sampled past positions, each drifting in the water."""

    __slots__ = ("points", "carry", "age", "since", "last", "reach")

    def __init__(self, ident: int, radius: float):
        self.points = np.zeros((0, 3))
        self.carry = np.zeros((0, 3))
        self.age = np.zeros(0)
        self.since = SAMPLE_SECONDS
        self.last: tuple[float, float, float] | None = None
        self.reach = radius * random.Random(ident * 104729 + 7).uniform(*LENGTH)

    def advance(self, here, dt: float, phase: float, jump: float) -> None:
        """One logical tick: the old water drifts, the bubble (at ``here``; None once it is gone) lays down new."""
        if len(self.age):
            self.carry *= math.exp(-dt / ENTRAIN_SECONDS)
            self.points += (self.carry + water_flow(self.points, phase)) * dt
            if len(self.age) > 2:
                # Viscous smoothing, stronger with age: the fresh wake keeps the bubble's exact course.
                rate = np.clip(DIFFUSION * dt * np.minimum(self.age[1:-1], 1.0), 0.0, 0.25)[:, None]
                self.points[1:-1] += rate * (self.points[:-2] + self.points[2:] - 2.0 * self.points[1:-1])
            self.age += dt
            keep = self.age < HISTORY_SECONDS
            if not keep.all():
                self.points, self.carry, self.age = self.points[keep], self.carry[keep], self.age[keep]
        if here is None:
            return
        here = np.asarray(here, dtype=np.float64)
        velocity = np.zeros(3)
        if self.last is not None and dt > 0.0:
            step = here - self.last
            if float(np.linalg.norm(step)) > jump:      # a re-entry is not motion: start a fresh wake
                self.points, self.carry, self.age = np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0)
            else:
                velocity = step / dt
        self.last = here
        self.since += dt
        if self.since >= SAMPLE_SECONDS:
            self.since = 0.0
            self.points = np.vstack([self.points, here])
            self.carry = np.vstack([self.carry, velocity * ENTRAIN])
            self.age = np.append(self.age, 0.0)

    def resampled(self, head, skip: float) -> tuple[float, tuple[float, ...]]:
        """(length, ``WAKE_POINTS`` x 3 floats): the trail from ``skip`` behind ``head`` (the bubble's centre; None
        once it is gone) back along its history, evenly spaced, at most ``reach`` long."""
        chain = self.points[::-1]
        if head is not None:
            chain = np.vstack([np.asarray(head, dtype=np.float64)[None, :], chain])
        else:
            skip = 0.0
        if len(chain) < 2:
            anchor = chain[0] if len(chain) else np.zeros(3)
            return 0.0, tuple(float(v) for v in np.tile(anchor, WAKE_POINTS))
        lengths = np.linalg.norm(np.diff(chain, axis=0), axis=1)
        along = np.concatenate([[0.0], np.cumsum(lengths)])
        end = min(float(along[-1]), skip + self.reach)
        start = min(skip, end)
        # Water past the trail's reach is never shown again: drop it.
        beyond = np.searchsorted(along, end + self.reach * 0.25)
        if head is not None and beyond < len(chain) - 1:
            dropped = len(chain) - 1 - beyond
            self.points, self.carry, self.age = self.points[dropped:], self.carry[dropped:], self.age[dropped:]
        targets = np.linspace(start, end, WAKE_POINTS)
        sampled = np.stack([np.interp(targets, along, chain[:, axis]) for axis in range(3)], axis=-1)
        return end - start, tuple(float(v) for v in sampled.reshape(-1))


__all__ = ["ENTRAIN", "FLOW", "HISTORY_SECONDS", "SAMPLE_SECONDS", "WakePath", "trails", "water_flow"]
