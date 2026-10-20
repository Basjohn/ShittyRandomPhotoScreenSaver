"""Pure, finite two-endpoint world-volume paths for the framed 3D Settings controls.

Coordinates are normalized to [-1, 1] across the fixed world box, x horizontal,
y vertical (surface/floor), z depth. Legacy [around, height] is admitted to a
boundary-to-boundary path, WITHOUT changing operator-authored preset files.
"""
from __future__ import annotations

import math

from core.constants.extruded_bubble_world import WORLD_HALF


def legacy_path(value, kind: str) -> tuple[float, ...]:
    around, height = (math.radians(float(v)) for v in value)
    if kind == 'stream':
        direction = (math.sin(around) * math.cos(height), math.cos(around) * math.cos(height),
                     -math.sin(height))
        # Stream SOURCE opposite the direction of travel.
        sign = -1.0
    else:
        direction = (math.sin(around) * math.cos(height), math.sin(height),
                     -math.cos(around) * math.cos(height))
        # A light is SOURCE-facing, so its beam travels *against* the old sun vector.
        sign = 1.0
    half = WORLD_HALF
    norm = max(abs(v) / h for v, h in zip(direction, half))
    start = tuple(round(sign * v / (norm * h), 4) for v, h in zip(direction, half))
    return (*start, *(-v for v in start))


def admit_path(value, default, kind='stream') -> tuple[float, ...]:
    """Normalize 6 authored coordinates, or migrate a 2-value legacy direction."""
    try:
        vals = tuple(float(x) for x in value)
        if len(vals) == 2 and all(math.isfinite(v) for v in vals):
            return legacy_path(vals, kind)
        if len(vals) == 6 and all(math.isfinite(v) for v in vals):
            clipped = tuple(round(max(-1.0, min(1.0, v)), 4) for v in vals)
            if sum((clipped[i+3] - clipped[i])**2 for i in range(3)) > 0.0001:
                return clipped
    except (TypeError, ValueError, OverflowError):
        pass
    if value is default:
        raise ValueError('Path defaults must contain two legacy angles or six noncoincident coordinates')
    return admit_path(default, default, kind)


def world_point(normalized, half=WORLD_HALF):
    return tuple(float(normalized[i]) * half[i] for i in range(3))


def direction_of(path, half=WORLD_HALF):
    delta = tuple((path[i+3] - path[i]) * half[i] for i in range(3))
    length = math.sqrt(sum(v*v for v in delta))
    if length <= 1.e-6:
        raise ValueError('Coincident path endpoints')
    return tuple(v / length for v in delta)


def square_to_disc(x: float, y: float) -> tuple[float, float]:
    """Map the whole [-1,1]² world XY square to the control's circular face.

    Corners/ceiling must remain reachable; naive circular clipping would silently
    change legacy paths whenever one of their two XY coordinates is near an edge.
    """
    radius = math.hypot(x, y)
    outer = max(abs(x), abs(y))
    return ((x / radius * outer, y / radius * outer) if radius > 1e-12 else (0., 0.))


def disc_to_square(x: float, y: float) -> tuple[float, float]:
    radius = math.hypot(x, y)
    if radius < 1e-12:
        return 0., 0.
    ux, uy = x / radius, y / radius
    side = min(1., radius) / max(abs(ux), abs(uy))
    return ux * side, uy * side
