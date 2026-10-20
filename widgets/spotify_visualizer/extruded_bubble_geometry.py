"""Pure Extruded Bubble world units, independent of every camera and viewport.

The simulation owns positions, lifetimes and contacts. The renderer only packs them;
GPU procedural populations receive this same fixed domain. No live scene owner here.
The length conversion preserves nominal scale at the former 15-unit reference depth,
not at every depth. Authored counts remain global population limits.
"""
from __future__ import annotations

import math

from core.constants.extruded_bubble_world import (
    WORLD_UNIT, WORLD_CENTER, WORLD_HALF, WORLD_MARGIN, WATER_SURFACE_Y,
)


def stream_basis(direction):
    """Two orthonormal transverse world axes, including a depth-facing stream."""
    x, y, z = direction
    length = math.hypot(x, y)
    across = (y / length, -x / length, 0.0) if length > 1e-10 else (1.0, 0.0, 0.0)
    return across, (y * across[2] - z * across[1],
                    z * across[0] - x * across[2], x * across[1] - y * across[0])


def upstream_source(rng, direction):
    """Uniform physical inflow: face area times inward stream component.

    A sampled ray through the interior would bias diagonal faces. Select actual
    upstream faces directly; there is no reference to a camera or projected width.
    """
    weights = [abs(direction[i]) * WORLD_HALF[(i + 1) % 3] * WORLD_HALF[(i + 2) % 3]
               for i in range(3)]
    choice = rng.random() * sum(weights)
    axis = 2
    for i, weight in enumerate(weights):
        choice -= weight
        if choice <= 0.0 and weight > 0.0:
            axis = i
            break
    point = [WORLD_CENTER[i] + rng.uniform(-WORLD_HALF[i], WORLD_HALF[i]) for i in range(3)]
    point[axis] = WORLD_CENTER[axis] - math.copysign(WORLD_HALF[axis], direction[axis])
    return tuple(point)


def box_entry(point, direction):
    """Entry of a world line into the fixed domain, or None if it misses.

    Column placement changes a transverse line, so recompute its true upstream
    boundary rather than pretending the original sampled face still applies.
    """
    enter, leave = -math.inf, math.inf
    for p, d, c, h in zip(point, direction, WORLD_CENTER, WORLD_HALF):
        if abs(d) < 1e-12:
            if abs(p - c) > h:
                return None
            continue
        a, b = (c - h - p) / d, (c + h - p) / d
        enter, leave = max(enter, min(a, b)), min(leave, max(a, b))
    return tuple(p + d * enter for p, d in zip(point, direction)) if enter <= leave else None
