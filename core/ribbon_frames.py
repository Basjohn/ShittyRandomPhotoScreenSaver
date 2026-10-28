"""CPU strip-width reference; caller owns tangent sampling and persistent anchors.

No renderer, camera controller, frame cache, simulation or sampling clock.
"""
from dataclasses import dataclass
import math
from itertools import zip_longest

from core.ribbon_geometry import MAX_PATH_SAMPLES, MAX_TWIST_MAGNITUDE, PathSample

MAX_SUBDIVISIONS = 8
MAX_STRIP_STATIONS = (MAX_PATH_SAMPLES - 1)*MAX_SUBDIVISIONS + 1
EPSILON = 1e-10
CUSP_COSINE = -1 + 1e-6
CAMERA_POLE_SINE = .05
ROLL_AMBIGUITY_DOT = .1


class FrameDiscontinuity(ValueError):
    """An actual/near reversal requires an explicit strip break or more samples."""


def _vector(value):
    v = tuple(float(x) for x in value)
    if len(v) != 3 or not all(math.isfinite(x) for x in v):
        raise ValueError('Finite three-component vector required')
    return v


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _unit(v, *, minimum=EPSILON):
    length = math.hypot(*v)
    if not math.isfinite(length):
        raise ValueError('Vector magnitude exceeds finite arithmetic')
    return tuple(x/length for x in v) if length > minimum else None


def _perpendicular(side, tangent):
    d = _dot(side, tangent)
    return _unit(tuple(s-d*t for s, t in zip(side, tangent)))


@dataclass(frozen=True, slots=True)
class WidthFrame:
    tangent: tuple[float, float, float]
    base_side: tuple[float, float, float]  # untwisted; seed the next transport with this
    side: tuple[float, float, float]
    normal: tuple[float, float, float]    # centre-line frame, not a displaced mesh normal
    camera_parallel: bool = False


def width_frame(tangent, *, previous: WidthFrame | None = None, seed_side=(0., 1., 0.),
                twist=0., mode='oriented', projection='orthographic',
                view_direction=(0., 0., -1.), position=(0., 0., 0.), eye=(0., 0., 10.)):
    """Transport an untwisted frame, then apply this station's twist exactly once.

    Zero tangents return None (do not draw); caller retains the last valid anchor.
    Near-antiparallel tangents raise rather than silently choosing a roll/UV flip.
    Camera poles explicitly report camera_parallel and use the transported side.
    """
    if mode not in ('oriented', 'camera_facing') or projection not in ('orthographic', 'perspective'):
        raise ValueError('Unknown ribbon width mode or projection')
    if not math.isfinite(twist) or abs(twist) > MAX_TWIST_MAGNITUDE:
        raise ValueError('Finite bounded twist required')
    t = _unit(_vector(tangent), minimum=0.)
    if t is None:
        return None
    candidate = None
    sine = 1.
    if mode == 'camera_facing':
        if projection == 'orthographic':
            sight = _unit(_vector(view_direction), minimum=0.)
        else:
            sight = _unit(tuple(p-e for p, e in zip(_vector(position), _vector(eye))), minimum=0.)
        if sight is None:
            raise ValueError('Camera sight direction is undefined')
        cross = _cross(t, sight)
        sine = math.hypot(*cross)
        candidate = _unit(cross)
    if previous is None:
        seed = _unit(_vector(seed_side), minimum=0.)
        base = _perpendicular(seed, t) if seed is not None else None
        if base is None and candidate is not None and sine >= CAMERA_POLE_SINE:
            base = candidate
        if base is None:
            raise FrameDiscontinuity('Seed side is parallel to tangent; choose an explicit initial side')
    else:
        for vector in (previous.tangent, previous.base_side, previous.side, previous.normal):
            if abs(math.hypot(*_vector(vector))-1.) > 1e-7:
                raise ValueError('Previous frame must have finite unit axes')
        if abs(_dot(previous.tangent, previous.base_side)) > 1e-7:
            raise ValueError('Previous frame axes must be perpendicular')
        # Minimal rotation in vector form: R(s) = s + v×s + v×(v×s)/(1+c).
        c = max(-1., min(1., _dot(previous.tangent, t)))
        if c <= CUSP_COSINE:
            raise FrameDiscontinuity('Tangent reversal requires a strip break or denser sampling')
        axis = _cross(previous.tangent, t)
        first = _cross(axis, previous.base_side)
        second = _cross(axis, first)
        base = _perpendicular(tuple(s+a+b/(1+c) for s, a, b in zip(previous.base_side, first, second)), t)
        if base is None:
            raise FrameDiscontinuity('Transport lost its width basis')
    parallel = False
    if mode == 'camera_facing':
        parallel = sine < CAMERA_POLE_SINE
        if candidate is not None:
            alignment = _dot(candidate, base)
            if abs(alignment) < ROLL_AMBIGUITY_DOT:
                raise FrameDiscontinuity('Camera side is roll-ambiguous; provide a continuous anchor or break the strip')
            if alignment < 0:
                candidate = tuple(-x for x in candidate)
            weight = min(1., sine/CAMERA_POLE_SINE)
            weight = weight*weight*(3-2*weight)
            base = _unit(tuple((1-weight)*a+weight*b for a, b in zip(base, candidate)))
    n = _cross(t, base)
    side = tuple(math.cos(twist)*s + math.sin(twist)*v for s, v in zip(base, n))
    return WidthFrame(t, base, side, _cross(t, side), parallel)


@dataclass(frozen=True, slots=True)
class StripStation:
    coordinate: float
    left: tuple[float, float, float]
    right: tuple[float, float, float]
    frame: WidthFrame
    # UV longitudinal coordinate stays absolute in this CPU reference; GPU must rebase.
    left_uv: tuple[float, float]
    right_uv: tuple[float, float]


def strip_station(sample: PathSample, tangent, **frame_options) -> StripStation | None:
    value = sample.admitted()
    frame = width_frame(tangent, twist=value.twist, position=value.position, **frame_options)
    if frame is None:
        return None
    left = tuple(p-value.half_width*s for p, s in zip(value.position, frame.side))
    right = tuple(p+value.half_width*s for p, s in zip(value.position, frame.side))
    if left == right:
        raise FrameDiscontinuity('Width collapsed at current coordinate precision; rebase geometry')
    return StripStation(value.coordinate, left, right, frame, (value.coordinate, 0.), (value.coordinate, 1.))


def strip_path(samples, tangents, *, initial_frame=None, **frame_options):
    """Bounded diagnostic batch. None entries are strip breaks, never bridged.

    Resume another batch with its last valid frame as initial_frame. Retain the
    untwisted anchor for the preceding station when evicting history; reseeding
    the new oldest knot does not promise the same roll.
    """
    pairs = []
    missing = object()
    for sample, tangent in zip_longest(samples, tangents, fillvalue=missing):
        if sample is missing or tangent is missing:
            raise ValueError('Every station needs one explicit tangent')
        if len(pairs) >= MAX_STRIP_STATIONS:
            raise ValueError('Strip station capacity exceeded')
        admitted = sample.admitted()
        if pairs and admitted.coordinate <= pairs[-1][0].coordinate:
            raise ValueError('Strip station coordinates must increase strictly')
        pairs.append((admitted, _vector(tangent)))
    result = []
    previous = initial_frame
    for sample, tangent in pairs:
        station = strip_station(sample, tangent, previous=previous, **frame_options)
        result.append(station)
        if station is not None:
            previous = station.frame
    return tuple(result)
