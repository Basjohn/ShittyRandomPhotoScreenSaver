"""Neon-only event-driven star selection; pure deterministic panoramic geometry."""
from __future__ import annotations
import math
from functools import lru_cache

# Twenty percent lower than the operator-accepted 0.35 entry floor.
# Only existing admitted onset records participate, never a second detector.
STARSCAPE_BEAT_MIN_STRENGTH = 0.35 * 0.80

def _star_hash(x: int, y: int) -> float:
    value = math.sin(float(x) * 41.37 + float(y) * 289.13) * 24634.6345
    return value - math.floor(value)


@lru_cache(maxsize=64)
def _nearby_bright_star(lon: int, lat: int) -> tuple[int, int]:
    """Choose one fixed star of the existing panorama, never a screen-attached sprite."""
    for distance in range(12):
        for dx in range(-distance, distance + 1):
            for dy in range(-distance, distance + 1):
                if max(abs(dx),abs(dy)) == distance and _star_hash(lon + dx, lat + dy) >= .99:
                    return lon + dx, lat + dy
    return lon, lat


def _visible_star_cell(x: float, y: float, tilt: float, turn: float,
                       camera: float, fit: tuple[float, float],
                       pose: tuple[float, float, float], aspect: float) -> tuple[int, int]:
    """CPU mirror of NEON_SKY_FRAGMENT_SOURCE's camera ray, at card UV x/y.

    A static latitude derived from orbit tilt can select stars hidden by the
    mountains or completely outside the viewport after framing/zoom/pan.
    These are genuine panorama cells, not fake screen-anchored sprites.
    """
    scale, pan_x, pan_y = pose
    sx = (x - 0.5 - pan_x) * aspect / (max(scale, 1e-5) * fit[0])
    sy = (fit[1] - 0.5 - (y - 0.5 - pan_y) / max(scale, 1e-5)) / fit[0]
    ct, st, cy, syaw = math.cos(tilt), math.sin(tilt), math.cos(turn), math.sin(turn)
    vy = sy*ct-camera*st
    vz = -sy*st-camera*ct
    wx = sx*cy-vz*syaw
    wz = sx*syaw+vz*cy
    norm = math.sqrt(wx*wx+vy*vy+wz*wz)
    longitude = math.atan2(wx,-wz)
    latitude = math.asin(max(-1.0,min(1.0,vy/norm)))
    return round(longitude*420),round(latitude*420)


def starscape_beat_cells(events, tilt: float, turn: float, *,
                         camera: float | None = None,
                         fit: tuple[float, float] | None = None,
                         pose: tuple[float, float, float] = (1.0,0.0,0.0),
                         aspect: float = 1.7) -> tuple[tuple[float, ...], ...]:
    """Three distant existing celestial star-cells per recent powerful onset.

    Derived from the existing bounded onset ring/clock. Nothing is persisted or
    recomputed by a background owner, and disabled mode does no work at all.
    """
    bursts = []
    # Latest two strong hits retain independent gentle release tails.
    for age, x, z, strength in reversed(events):
        if not (0.0 <= age < 1.75 and strength >= STARSCAPE_BEAT_MIN_STRENGTH):
            continue
        seed = int(abs(x * 8219.0 + z * 3191.0) * 1871.0)
        for i in range(3):
            # Three distinct visible sky sectors at a shallow top margin.
            # Use the real sky ray for this pose, not a tilt-only estimate.
            x = (0.20,0.50,0.80)[i] + (((seed >> (i*4)) & 15)-7.5)*0.005
            y = 0.07 + (((seed >> (i*3+1)) & 7))*0.007
            if camera is not None and fit is not None:
                lon, lat = _visible_star_cell(x,y,tilt,turn,camera,fit,pose,aspect)
            else:
                # Backward-compatible standalone / unavailable-fit fallback.
                longitude=turn+(i-1)*0.22
                latitude=-tilt+0.13
                lon,lat=round(longitude*420),round(latitude*420)
            cx, cy = _nearby_bright_star(lon,lat)
            intensity = min(1.0, strength * 0.95) * max(0.0, 1.0 - (age / 1.75)**2)**2
            bursts.append((float(cx), float(cy), float(intensity), 0.0))
        if len(bursts) >= 6:
            break
    return tuple(bursts)

