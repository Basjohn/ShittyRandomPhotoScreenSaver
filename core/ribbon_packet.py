"""WR-02a immutable std430 input admission; no GL or runtime state."""
from dataclasses import dataclass
import math
from itertools import islice

import numpy as np

from core.ribbon_frames import MAX_SUBDIVISIONS, strip_path
from core.ribbon_geometry import MAX_PATH_SAMPLES

MAX_RIBBONS = 8
KNOT_BYTES = 64
METADATA_BYTES = 64
RIBBON_BYTES = METADATA_BYTES + MAX_PATH_SAMPLES*KNOT_BYTES
MAX_PACKET_BYTES = MAX_RIBBONS*RIBBON_BYTES
MAX_LOCAL_SPAN = 64.


@dataclass(frozen=True, slots=True)
class RibbonPacket:
    payload: bytes
    instances: int
    vertices: int
    world_origin: tuple[float, float, float] = (0., 0., 0.)


def pack_ribbons(paths, *, subdivisions=8, period=1., colour=(.1, .7, .9, 1.)):
    """Each path is (samples, explicit tangents, initial untwisted anchor).

    Only oriented width frames are admitted here. GPU camera-facing/pole behavior
    requires a later native gate. Coordinates remain absolute in caller state.
    """
    if isinstance(subdivisions, bool) or not isinstance(subdivisions, int) or not 1 <= subdivisions <= MAX_SUBDIVISIONS:
        raise ValueError('Ribbon subdivisions must be an integer in 1..8')
    if not math.isfinite(period) or period <= 0:
        raise ValueError('Finite positive strand period required')
    colour = tuple(float(v) for v in colour)
    if len(colour) != 4 or not all(math.isfinite(v) and 0 <= v <= 1 for v in colour):
        raise ValueError('Diagnostic colour requires four finite normalized channels')
    admitted = []
    vertices = 0
    world_origin = None
    for index, (samples, tangents, anchor) in enumerate(paths):
        if index >= MAX_RIBBONS:
            raise ValueError('Ribbon population exceeds 8')
        samples = tuple(islice(samples, MAX_PATH_SAMPLES+1))
        if len(samples) > MAX_PATH_SAMPLES:
            raise ValueError('GPU ribbon knot count exceeds 256')
        samples = tuple(sample.admitted() for sample in samples)
        stations = strip_path(samples, tangents, initial_frame=anchor)
        if len(samples) < 2 or not any(a is not None and b is not None for a, b in zip(stations, stations[1:])):
            continue
        if world_origin is None:
            world_origin = tuple(float(v) for v in samples[0].position)
        origin = float(samples[0].coordinate)
        local = np.array([float(s.coordinate)-origin for s in samples], dtype=np.float64)
        if local[-1] > MAX_LOCAL_SPAN:
            raise ValueError('GPU ribbon local coordinate span exceeds 64 seconds')
        local32 = local.astype(np.float32)
        if np.any(np.diff(local32) <= 0):
            raise ValueError('GPU local coordinates lose ordering; rebase/resample')
        data = np.zeros((4+MAX_PATH_SAMPLES*4, 4), dtype=np.float32)
        phase = (origin % period)/period
        if local[-1]/period > 4096 or not np.finfo(np.float32).tiny <= period <= np.finfo(np.float32).max:
            raise ValueError('GPU strand period exceeds supported phase precision')
        data[0] = (len(samples), subdivisions, phase, period)
        twist_origin = float(samples[0].twist)
        data[1, 0] = twist_origin % (2*math.pi)
        data[1, 2] = MAX_PATH_SAMPLES  # ring capacity; start (data[1, 1]) stays 0: chronological order
        data[2] = colour
        data[3] = colour
        for i, (sample, station) in enumerate(zip(samples, stations)):
            value = sample.admitted()
            at = 4+i*4
            local_position = np.asarray(value.position)-world_origin
            if np.max(np.abs(local_position)) > 1024:
                raise ValueError('GPU packet spatial span exceeds local precision domain')
            data[at] = (*local_position, value.half_width)
            # Admission is explicit instead of silently reducing geometric precision.
            if np.max(np.abs(data[at, :3].astype(float)-local_position)) > 1e-5:
                raise ValueError('GPU world position loses precision; rebase geometry')
            if data[at, 3] <= 0 or abs(float(data[at, 3])/value.half_width-1) > 1e-5:
                raise ValueError('GPU width loses precision')
            twist = value.twist-twist_origin
            if abs(twist) > 64*math.pi:
                raise ValueError('GPU local twist span exceeds 32 turns')
            data[at+1] = (local32[i], twist, station is not None, 0.)
            if station is not None:
                if np.array_equal(np.asarray(np.asarray(station.left)-world_origin, dtype=np.float32), np.asarray(np.asarray(station.right)-world_origin, dtype=np.float32)):
                    raise ValueError('GPU ribbon edges collapse; rebase geometry')
                data[at+2, :3] = station.frame.tangent
                data[at+3, :3] = station.frame.base_side
        if not np.isfinite(data).all() or data[0, 3] <= 0:
            raise ValueError('GPU packet exceeds finite float32 range')
        admitted.append(data.tobytes())
        vertices = max(vertices, (len(samples)-1)*subdivisions*6)
    return RibbonPacket(b''.join(admitted), len(admitted), vertices, world_origin or (0., 0., 0.))
