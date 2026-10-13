"""Canonical authored heightfields, independent of Qt, GL and runtime displacement.

Rows run from the near/front edge (v=0) to the far/back edge (v=1). Normalize once at
input/configure boundaries; sampling and packing consume that canonical record. Water
is exactly an authored sampled height of zero, regardless of any rendered displacement.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
import struct

_FLOAT32_MIN_NORMAL = 2.0 ** -126


def _size(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("heightfield size must be a whole number within 2..65")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("heightfield size must be a whole number within 2..65") from exc
    if not math.isfinite(number) or number != int(number) or not 2 <= number <= 65:
        raise ValueError("heightfield size must be a whole number within 2..65")
    return int(number)


def normalize_heightfield(value: object) -> dict:
    if not isinstance(value, Mapping) or value.get("version") != 1 or isinstance(value.get("version"), bool):
        raise ValueError("heightfield requires a version-1 record")
    size = _size(value.get("size"))
    raw = value.get("heights")
    if not isinstance(raw, (list, tuple)) or len(raw) != size * size:
        raise ValueError("heightfield requires exactly size squared heights")
    heights = []
    for height in raw:
        if isinstance(height, bool):
            raise ValueError("heightfield heights must be finite numbers within 0..1")
        try:
            number = float(height)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("heightfield heights must be finite numbers within 0..1") from exc
        if not math.isfinite(number) or not 0.0 <= number <= 1.0:
            raise ValueError("heightfield heights must be finite numbers within 0..1")
        if 0.0 < number < _FLOAT32_MIN_NORMAL:
            raise ValueError("positive heightfield heights must be representable as normal float32 values")
        heights.append(0.0 if number == 0.0 else number)
    return {"version": 1, "size": size, "heights": heights}


def sample_heightfield(data: Mapping, u: float, v: float) -> float:
    """Bilinear sampling of a canonical record; finite UV coordinates clamp to its edges."""
    u, v = float(u), float(v)
    if not math.isfinite(u) or not math.isfinite(v):
        raise ValueError("heightfield sample coordinates must be finite")
    n = data["size"]
    x, y = max(0.0, min(1.0, u)) * (n - 1), max(0.0, min(1.0, v)) * (n - 1)
    x0, y0 = int(x), int(y)
    x1, y1 = min(n - 1, x0 + 1), min(n - 1, y0 + 1)
    fx, fy = x - x0, y - y0
    heights = data["heights"]
    near = heights[y0 * n + x0] * (1.0 - fx) + heights[y0 * n + x1] * fx
    far = heights[y1 * n + x0] * (1.0 - fx) + heights[y1 * n + x1] * fx
    return near * (1.0 - fy) + far * fy


def heightfield_bytes(data: Mapping) -> bytes:
    """Pack a canonical record into immutable little-endian float32 texels."""
    return struct.pack(f"<{len(data['heights'])}f", *data["heights"])


def _distance_transform_1d(costs: list[float]) -> list[float]:
    """Squared Euclidean distance to the nearest finite site in one dimension."""
    size = len(costs)
    first = next((index for index, cost in enumerate(costs) if math.isfinite(cost)), None)
    if first is None:
        return [math.inf] * size

    sites = [0] * size
    boundaries = [0.0] * (size + 1)
    envelope = 0
    sites[0] = first
    boundaries[0] = -math.inf
    boundaries[1] = math.inf
    for index in range(first + 1, size):
        if not math.isfinite(costs[index]):
            continue
        site = sites[envelope]
        crossing = ((costs[index] + index * index) - (costs[site] + site * site)) / (2 * (index - site))
        while crossing <= boundaries[envelope]:
            envelope -= 1
            site = sites[envelope]
            crossing = ((costs[index] + index * index) - (costs[site] + site * site)) / (2 * (index - site))
        envelope += 1
        sites[envelope] = index
        boundaries[envelope] = crossing
        boundaries[envelope + 1] = math.inf

    result = [0.0] * size
    envelope = 0
    for index in range(size):
        while boundaries[envelope + 1] < index:
            envelope += 1
        delta = index - sites[envelope]
        result[index] = delta * delta + costs[sites[envelope]]
    return result


def heightfield_surface_bytes(data: Mapping) -> bytes:
    """Pack row-major RG32F heights and distance-to-bank authored channels.

    The distance is measured from the bilinear-positive support: positive control
    samples are expanded by one Chebyshev texel, then an exact squared Euclidean
    distance transform is normalized by ``size - 1``. An all-water field uses
    distance 1, while every sample in the expanded solid support uses distance 0.
    """
    size = data["size"]
    heights = data["heights"]
    support = [False] * (size * size)
    has_land = False
    for y in range(size):
        for x in range(size):
            if heights[y * size + x] <= 0.0:
                continue
            has_land = True
            for support_y in range(max(0, y - 1), min(size, y + 2)):
                start = support_y * size
                for support_x in range(max(0, x - 1), min(size, x + 2)):
                    support[start + support_x] = True

    if has_land:
        horizontal = [math.inf] * (size * size)
        for y in range(size):
            start = y * size
            row = [0.0 if support[start + x] else math.inf for x in range(size)]
            horizontal[start:start + size] = _distance_transform_1d(row)

        squared_distance = [math.inf] * (size * size)
        for x in range(size):
            column = _distance_transform_1d([horizontal[y * size + x] for y in range(size)])
            for y, distance in enumerate(column):
                squared_distance[y * size + x] = distance
        distances = [math.sqrt(distance) / (size - 1) for distance in squared_distance]
    else:
        distances = [1.0] * (size * size)

    interleaved = []
    for height, distance in zip(heights, distances):
        interleaved.extend((height, distance))
    return struct.pack(f"<{len(interleaved)}f", *interleaved)


def sample_heightfield_curve(data: Mapping, u: float, v: float) -> float:
    """Positive cubic B-spline surface; authored bilinear zero still owns water.

    Positive weights preserve the local height range without Catmull-Rom's
    overshoot/dents. This is opt-in geometric smoothing, not input migration.
    """
    u,v=float(u),float(v)
    if not math.isfinite(u) or not math.isfinite(v):
        raise ValueError("heightfield sample coordinates must be finite")
    n=data["size"]
    x,y=max(0.0,min(1.0,u))*(n-1),max(0.0,min(1.0,v))*(n-1)
    ix,iy=int(x),int(y)

    def weights(t):
        return ((1-t)**3/6, (3*t**3-6*t*t+4)/6,
                (-3*t**3+3*t*t+3*t+1)/6, t**3/6)

    wx,wy=weights(x-ix),weights(y-iy)
    heights=data["heights"]
    return sum(wx[a]*wy[b]*heights[max(0,min(n-1,iy+b-1))*n+max(0,min(n-1,ix+a-1))]
               for b in range(4) for a in range(4))


def basin_profile(size: int = 65) -> dict:
    """Editable synthwave basin: broad zero lake, pointed banks and small islands."""
    n = _size(size)
    heights = []
    for y in range(n):
        v = y / (n - 1)
        for x in range(n):
            u = x / (n - 1)
            radius = math.hypot((u - 0.50) / 0.38, (v - 0.46) / 0.34)
            radius += 0.035*math.sin(17*u+13*v)+0.030*math.cos(23*u-19*v)
            bank = max(0.0, min(1.0, (radius - 1.0) / 0.35))
            peaks = max(amplitude * max(0.0, 1.0-math.hypot((u-px)/wx, (v-py)/wy))
                        for px,py,wx,wy,amplitude in (
                            (0.12,0.65,0.22,0.35,0.76), (0.43,0.94,0.20,0.29,1.0),
                            (0.84,0.72,0.24,0.30,0.70), (0.08,0.18,0.25,0.27,0.44),
                            (0.86,0.12,0.25,0.26,0.50), (0.23,0.94,0.22,0.20,0.46)))
            facets = 0.035 * (math.sin(63*u+19*v) + math.cos(47*v-23*u))
            land = bank * max(0.0, 0.045 + peaks + facets)
            for ix, iy, radius, height in ((0.24,0.57,0.045,0.14),(0.75,0.48,0.035,0.08)):
                distance = math.hypot(u - ix, v - iy) / radius
                if distance < 1.0:
                    land += height * (1.0 - distance * distance) ** 2
            heights.append(min(1.0, land) if land > 0.0 else 0.0)
    return {"version": 1, "size": n, "heights": heights}
