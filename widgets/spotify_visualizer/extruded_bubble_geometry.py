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


def _inflow_face_weights(direction):
    return tuple(abs(direction[i]) * WORLD_HALF[(i + 1) % 3] * WORLD_HALF[(i + 2) % 3]
                 for i in range(3))


def upstream_source(rng, direction, face_weights=None):
    """Uniform physical inflow: face area times inward stream component.

    A sampled ray through the interior would bias diagonal faces. Select actual
    upstream faces directly; there is no reference to a camera or projected width.
    """
    weights = _inflow_face_weights(direction)
    if face_weights is not None:
        weights = [max(0.0, float(weight)) for weight in face_weights]
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


def scene_track_length(point, direction):
    """Inside distance to the outgoing face from a real upstream boundary sample.

    The only geometric authority is WORLD_CENTER/WORLD_HALF; the camera and
    authored End marker do not attract/steer individual SCENE bubbles.
    """
    candidates = []
    for coordinate, component, centre, half in zip(point, direction, WORLD_CENTER, WORLD_HALF):
        if component > 1e-12:
            candidates.append((centre + half - coordinate) / component)
        elif component < -1e-12:
            candidates.append((centre - half - coordinate) / component)
    return max(0.0, min(candidates)) if candidates else 0.0


def scene_source_face_weights(source, direction):
    """Upstream physical faces selected by the authored normalized Source.

    Floor -> floor face; adjoining floor/wall/corner -> each incident face
    whose inward normal admits the directed stream. If the point is interior,
    or the operator authors an outward-facing impossible inlet, fall back to
    the true weighted upstream faces. Same three weights feed CPU and GPU.
    """
    baseline = _inflow_face_weights(direction)
    chosen = tuple(weight if (abs(float(src)) >= 0.7 and float(src) * d < -1e-7) else 0.0
                   for src, d, weight in zip(source, direction, baseline))
    return chosen if sum(chosen) > 1e-9 else baseline


def scene_mean_passage(direction, face_weights=None):
    """Mean inside track length for the same uniform physical inlet sampler.

    On an entry face the other two exit distances are independent uniforms.
    Integrate their survival product up to the shortest full-axis crossing;
    weight each face exactly as upstream_source does. No camera or sampling.
    """
    weights = _inflow_face_weights(direction) if face_weights is None else face_weights
    total = sum(weights)
    if total <= 0.0:
        raise ValueError('SCENE inlet requires a nonzero inward flow')
    inverse = tuple(abs(d)/(2.0*h) for d,h in zip(direction,WORLD_HALF))
    cap = 1.0/max(inverse)
    length = 0.0
    for axis,weight in enumerate(weights):
        a,b = inverse[(axis+1)%3],inverse[(axis+2)%3]
        length += weight * (cap - .5*(a+b)*cap*cap + a*b*cap*cap*cap/3.0)
    return length/total
