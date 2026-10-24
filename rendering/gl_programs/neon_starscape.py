"""Neon-only event-driven star selection; pure deterministic panoramic geometry."""
from __future__ import annotations
import math
import struct
from functools import lru_cache
from rendering.gl_programs.shockwave_grid_program import SHOCKWAVE_DEPTH

# Twenty percent easier again than the prior 0.28 floor: 0.35 * 0.64 = 0.224.
# Only existing admitted onset records participate, never a second detector.
STARSCAPE_BEAT_MIN_STRENGTH = 0.35 * 0.64
# Half the fade speed again (operator 2026-10-17): a beat star now fades over about 5.8 s.
STARSCAPE_BEAT_RELEASE = 1.75 / 0.3
# At most this many beats keep stars; once STARSCAPE_BEAT_HELD newer beats have theirs, an older beat's stars fade
# over STARSCAPE_BEAT_DISPLACE seconds instead of vanishing. Recorded songs admit 1-4 beats a second, so three held
# beats displaced each star within about a second and the long release never showed (2026-10-24).
STARSCAPE_BEAT_EVENTS = 8
STARSCAPE_BEAT_HELD = 6
STARSCAPE_BEAT_STARS = 3 * STARSCAPE_BEAT_EVENTS   # the sky's uBeatStarCells capacity
# A beat star's brightness: a visible floor at the admission strength, full for a big hit (strength 1.2).
STARSCAPE_BEAT_FLOOR = 0.35
STARSCAPE_BEAT_FULL = 1.2
STARSCAPE_BEAT_DISPLACE = 0.6
# Beat stars swell in over this long rather than switching on, so one event's stars rise while the last fade.
STARSCAPE_BEAT_ATTACK = 0.2


def _star_ray(cell):
    lon, lat = (cell[0]+.5)/420., (cell[1]+.5)/420.
    return math.sin(lon)*math.cos(lat), math.sin(lat), -math.cos(lon)*math.cos(lat)


@lru_cache(maxsize=8)
def _terrain_heights(size, data):
    return struct.unpack(f'<{size*size*2}f', data)[::2]


@lru_cache(maxsize=256)
def _terrain_clear(cell, eye, terrain):
    """Thirteen coarse height taps, cached by star/view/authored terrain, never age.

    This is only a cheap admission preference. Actual surface depth/coverage
    remains the renderer's authority, including land beyond the authored basin.
    """
    size, data, half_width, height, *grid = terrain
    left, front, scale = grid[0] if grid else (0., 0., 1.)
    ray = _star_ray(cell)
    near, far = 0., math.inf
    # The authored grid may reach past the basin: its world box, from basin uv -left .. 1/scale-left.
    x_low, x_high = (2.*(-left)-1.)*half_width, (2.*(1./scale-left)-1.)*half_width
    z_low, z_high = -(1./scale-front)*SHOCKWAVE_DEPTH, front*SHOCKWAVE_DEPTH
    for axis, low, high in ((0,x_low,x_high),(2,z_low,z_high)):
        if abs(ray[axis]) < 1e-8:
            if not low <= eye[axis] <= high:
                return True
            continue
        a, b = (low-eye[axis])/ray[axis], (high-eye[axis])/ray[axis]
        near, far = max(near,min(a,b)), min(far,max(a,b))
    if near >= far:
        return True
    heights = _terrain_heights(size,data)
    for step in range(13):
        t = near+(far-near)*step/12.
        x,y,z = (eye[i]+t*ray[i] for i in range(3))
        u = max(0.,min(size-1.,((x/(2*half_width)+.5)+left)*scale*(size-1)))
        v = max(0.,min(size-1.,(-z/SHOCKWAVE_DEPTH+front)*scale*(size-1)))
        ix,iy = min(size-2,int(u)), min(size-2,int(v))
        fx,fy = u-ix,v-iy
        base = ((heights[iy*size+ix]*(1-fx)+heights[iy*size+ix+1]*fx)*(1-fy)
                +(heights[(iy+1)*size+ix]*(1-fx)+heights[(iy+1)*size+ix+1]*fx)*fy)
        if y <= base*height*1.5:
            return False
    return True


def _body_clear(cell, eye, body):
    ray = _star_ray(cell)
    delta = tuple(body[i]-eye[i] for i in range(3))
    along = sum(a*b for a,b in zip(delta,ray))
    return along <= 0. or sum(a*a for a in delta)-along*along > (body[3]*1.15)**2

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


def _visible_star_cell(x: float, y: float, view) -> tuple[int, int]:
    """CPU mirror of NEON_SKY_FRAGMENT_SOURCE's camera ray, at card UV x/y.

    A static latitude derived from orbit tilt can select stars hidden by the
    mountains or completely outside the viewport after framing/zoom/pan.
    These are genuine panorama cells, not fake screen-anchored sprites.
    """
    wx, vy, wz = view.ray(x, y)
    longitude = math.atan2(wx, -wz)
    latitude = math.asin(max(-1.0, min(1.0, vy)))
    return round(longitude*420), round(latitude*420)


def starscape_beat_cells(events, view, *, terrain=None, body=None) -> tuple[tuple[float, ...], ...]:
    """Three spaced existing celestial star-cells per recent powerful onset.

    Derived from the existing bounded onset ring/clock. Nothing is persisted or
    recomputed by a background owner, and disabled mode does no work at all.
    """
    bursts = []
    eye = view.eye
    # The latest strong hits keep independent gentle release tails; older ones give way gradually.
    newer: list[float] = []
    for age, x, z, strength in reversed(events):
        if not (0.0 <= age < STARSCAPE_BEAT_RELEASE and strength >= STARSCAPE_BEAT_MIN_STRENGTH):
            continue
        rank = len(newer)
        newer.append(age)
        displaced = (1.0 if rank < STARSCAPE_BEAT_HELD
                     else max(0.0, 1.0 - newer[rank - STARSCAPE_BEAT_HELD] / STARSCAPE_BEAT_DISPLACE))
        if displaced <= 0.0 or rank >= STARSCAPE_BEAT_EVENTS:
            break
        seed = int(abs(x * 8219.0 + z * 3191.0) * 1871.0)
        for i in range(3):
            # Stratify across the full framed sky's height as well as width.
            # The old y=.07..119 range could never choose middle/lower stars.
            # Rotate the vertical strata per event so no column owns a band.
            x = (0.17,0.5,0.83)[i] + (((seed >> (i*4)) & 15)-7.5)*0.005
            band = (i + seed) % 3
            y = (0.08,0.18,0.28)[band] + (((seed >> (i*3+1)) & 7)-3.5)*0.004
            # Three bounded attempts; prefer clear sky but keep the event's
            # three-star population when a view has no clear candidate here.
            for attempt in range(3):
                px = x + (0.,-.06,.06)[attempt]
                py = max(.025,y-attempt*.07)
                lon, lat = _visible_star_cell(px, py, view)
                cx, cy = _nearby_bright_star(lon,lat)
                cell = (cx,cy)
                if ((body is None or _body_clear(cell,eye,body))
                        and (terrain is None or _terrain_clear(cell,eye,terrain))):
                    break
            rise = min(1.0, age / STARSCAPE_BEAT_ATTACK)
            hit = min(1.0, max(0.0, (strength - STARSCAPE_BEAT_MIN_STRENGTH)
                               / (STARSCAPE_BEAT_FULL - STARSCAPE_BEAT_MIN_STRENGTH)))
            brightness = STARSCAPE_BEAT_FLOOR + (1.0 - STARSCAPE_BEAT_FLOOR) * hit * hit * (3.0 - 2.0 * hit)
            intensity = (brightness * rise * rise * (3.0 - 2.0 * rise)
                         * max(0.0, 1.0 - (age / STARSCAPE_BEAT_RELEASE)**2)**2 * displaced)
            bursts.append((float(cx), float(cy), float(intensity), 0.0))
    return tuple(bursts)

