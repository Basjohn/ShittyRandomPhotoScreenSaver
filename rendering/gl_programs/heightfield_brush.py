"""The heightfield brush: one owner of how a stroke paints an authored heightfield (Qt-free, no renderer).

The Neon Lake Studio's brush instrument (``ui/studio/brush.py``) paints with it. Distances are in brush radii,
measured in the grid's own square cells (a round brush is round in the terrain's cells), so a stroke's effect depends
on its path, never on pointer speed or event granularity. Positions are grid uv: (0, 0) the near-left corner of the
authored grid, rows running from the near/front edge (v = 0) to the far/back edge (v = 1), as
``rendering.gl_programs.heightfield`` stores them. Water is an authored height of exactly zero: only the Water mode
writes it, and Lower never turns land into water.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Mapping

from rendering.gl_programs.heightfield import heightfield_basin, normalize_heightfield

MODES = ("Raise", "Lower", "Flatten", "Water")
DAB_SPACING = 0.15        # radii between dabs along a stroke
PRESS_DEPOSIT = 0.25      # a press that never moves applies this much stroke (in radii), once
MAX_RATE = 0.5            # height Raise/Lower add per radius of stroke at 100% strength
FLATTEN_RATE = 6.0        # Flatten's approach per radius of stroke at 100% (100% itself snaps the core)
MIN_LAND = 0.005          # Lower never turns land into water; only the Water brush authors exact zero
RADIUS_RANGE = (0.03, 0.35)   # the brush radius, in grid uv (a share of the grid's side)
STRENGTH_FLOOR = 0.01


def brush_weight(distance: float, falloff: float) -> float:
    """The brush profile at ``distance`` radii: flat in a core of (1 - falloff), then a cosine skirt
    that reaches a little past the drawn radius as falloff grows (hard disc at 0)."""
    falloff = max(0.0, min(1.0, float(falloff)))
    core, outer = 1.0 - falloff, 1.0 + 0.5 * falloff
    if distance <= core:
        return 1.0
    if distance >= outer:
        return 0.0
    return 0.5 * (1.0 + math.cos(math.pi * (distance - core) / (outer - core)))


def brush_reach(falloff: float) -> float:
    """How far (in radii) the brush touches anything."""
    return 1.0 + 0.5 * max(0.0, min(1.0, float(falloff)))


def stroke_rate(strength: float) -> float:
    """Height per radius of stroke: quadratic, so low strengths are genuinely gradual."""
    strength = max(0.0, min(1.0, float(strength)))
    return MAX_RATE * strength * strength


def apply_brush(old: float, mode: str, weight: float, amount: float, strength: float, target: float) -> float:
    """One dab's effect on one height; ``amount`` is the stroke length it stands for, in radii."""
    if weight <= 0.0:
        return old
    if mode == "Water":
        return 0.0 if weight >= 0.5 else old   # water is authored zero, inside the brush's half-weight contour
    if mode == "Flatten":
        target = max(0.0, min(1.0, float(target)))
        if old > 0.0:
            target = max(MIN_LAND, target)
        if strength >= 1.0:
            share = weight
        else:
            share = 1.0 - math.exp(-FLATTEN_RATE * strength * strength * weight * amount)
        return max(0.0, min(1.0, old + (target - old) * share))
    delta = stroke_rate(strength) * weight * amount
    if mode == "Lower":
        if old <= 0.0:
            return old
        return max(MIN_LAND, old - delta)
    return min(1.0, old + delta)


@dataclass(frozen=True)
class BrushSettings:
    """The brush's tool state (not a stored setting): mode, radius (grid uv), strength, falloff and the height
    Flatten moves land toward (each 0..1)."""

    mode: str = "Raise"
    radius: float = 0.12
    strength: float = 0.35
    falloff: float = 0.5
    flatten_height: float = 0.20

    def admitted(self, name: str, value: Any) -> "BrushSettings":
        """A copy with ``name`` set to ``value`` under the brush's own bounds (an unknown mode keeps the current)."""
        if name == "mode":
            return replace(self, mode=str(value)) if str(value) in MODES else self
        if name not in ("radius", "strength", "falloff", "flatten_height"):
            raise KeyError(f"{name} is not a brush setting")
        number = float(value)
        if not math.isfinite(number):
            return self
        low, high = {"radius": RADIUS_RANGE, "strength": (STRENGTH_FLOOR, 1.0)}.get(name, (0.0, 1.0))
        return replace(self, **{name: max(low, min(high, number))})

    def as_map(self) -> dict:
        return {"mode": self.mode, "radius": self.radius, "strength": self.strength, "falloff": self.falloff,
                "flatten_height": self.flatten_height}


class HeightfieldStroke:
    """One stroke over a copy of an authored heightfield: a press deposits once, each move dabs every
    ``DAB_SPACING`` radii along the path, the leftover distance carrying to the next move."""

    def __init__(self, record: Mapping[str, Any], settings: BrushSettings) -> None:
        data = normalize_heightfield(record)
        self._size = int(data["size"])
        self._heights = list(data["heights"])
        self._basin = heightfield_basin(data)
        self._settings = settings
        self._last: tuple[float, float] | None = None
        self._carry = 0.0
        self.dabs = 0

    @property
    def settings(self) -> BrushSettings:
        return self._settings

    def record(self) -> dict:
        """The painted heightfield as a canonical record (the basin carried as stored)."""
        out = {"version": 1, "size": self._size, "heights": list(self._heights)}
        if self._basin != (0, 0, self._size - 1):
            out["basin"] = list(self._basin)
        return out

    def _radius(self) -> float:
        return max(RADIUS_RANGE[0], min(RADIUS_RANGE[1], float(self._settings.radius)))

    def _physical(self, du: float, dv: float) -> float:
        """A grid-uv offset's length in brush radii (the grid is square: a round brush)."""
        return math.hypot(du, dv) / self._radius()

    def dab(self, u: float, v: float, amount: float) -> None:
        """One dab at grid uv (u, v) standing for ``amount`` radii of stroke."""
        n = self._size
        settings = self._settings
        reach = self._radius() * brush_reach(settings.falloff)
        lower_x, upper_x = max(0, math.floor((u - reach) * (n - 1))), min(n - 1, math.ceil((u + reach) * (n - 1)))
        lower_y, upper_y = max(0, math.floor((v - reach) * (n - 1))), min(n - 1, math.ceil((v + reach) * (n - 1)))
        strength = max(STRENGTH_FLOOR, min(1.0, float(settings.strength)))
        heights = self._heights
        for y in range(lower_y, upper_y + 1):
            for x in range(lower_x, upper_x + 1):
                weight = brush_weight(self._physical(x / (n - 1) - u, y / (n - 1) - v), settings.falloff)
                if weight > 0.0:
                    index = y * n + x
                    heights[index] = apply_brush(heights[index], settings.mode, weight, amount, strength,
                                                 settings.flatten_height)
        self.dabs += 1

    def press(self, uv: tuple[float, float]) -> None:
        self._last = (float(uv[0]), float(uv[1]))
        self._carry = 0.0
        self.dab(*self._last, PRESS_DEPOSIT)

    def to(self, uv: tuple[float, float]) -> None:
        """Continue the stroke to ``uv`` (a press must come first)."""
        if self._last is None:
            self.press(uv)
            return
        u0, v0 = self._last
        u1, v1 = float(uv[0]), float(uv[1])
        length = self._physical(u1 - u0, v1 - v0)
        if length <= 0.0:
            return
        position = DAB_SPACING - self._carry
        while position <= length:
            t = position / length
            self.dab(u0 + (u1 - u0) * t, v0 + (v1 - v0) * t, DAB_SPACING)
            position += DAB_SPACING
        self._carry = length - (position - DAB_SPACING)
        self._last = (u1, v1)


__all__ = [
    "BrushSettings", "DAB_SPACING", "FLATTEN_RATE", "HeightfieldStroke", "MAX_RATE", "MIN_LAND", "MODES",
    "PRESS_DEPOSIT", "RADIUS_RANGE", "apply_brush", "brush_reach", "brush_weight", "stroke_rate",
]
