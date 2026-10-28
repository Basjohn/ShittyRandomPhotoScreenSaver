"""Bounded CPU ribbon-path reference. No Qt/GL, clock, simulation or EB coupling.

Coordinates are caller-owned, monotonically increasing logical sample times (or
another declared absolute parameter), never normalized by the live sample count.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

MAX_PATH_SAMPLES = 256
MAX_WORLD_MAGNITUDE = 1e6
MAX_TWIST_MAGNITUDE = 1e6
MAX_COORDINATE_MAGNITUDE = 1e12
RECORD_FLOATS = 8  # q, xyz, positive half-width, unwrapped twist, two reserved zeros


@dataclass(frozen=True, slots=True)
class PathSample:
    coordinate: float
    position: tuple[float, float, float]
    half_width: float = .25
    twist: float = 0.

    def admitted(self) -> 'PathSample':
        try:
            q, width, twist = float(self.coordinate), float(self.half_width), float(self.twist)
            point = tuple(float(v) for v in self.position)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError('Invalid ribbon sample') from error
        if len(point) != 3 or not all(math.isfinite(v) for v in (q, *point, width, twist)) or abs(q) > MAX_COORDINATE_MAGNITUDE or not 0 < width <= MAX_WORLD_MAGNITUDE or abs(twist) > MAX_TWIST_MAGNITUDE or any(abs(v) > MAX_WORLD_MAGNITUDE for v in point):
            raise ValueError('Ribbon samples require finite coordinates, positive width and bounded position/width/twist')
        return PathSample(q, point, width, twist)


def centripetal_point(p0, p1, p2, p3, u: float) -> tuple[float, float, float]:
    """Barry-Goldman reference with the EB wake's sqrt(distance) knot rule.

    Repeated points have a positive knot interval, as in the admitted EB shader.
    This is a reference for new strips; existing EB arithmetic is untouched.
    """
    points = tuple(tuple(float(v) for v in p) for p in (p0, p1, p2, p3))
    if any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in points) or not math.isfinite(u) or not 0 <= u <= 1:
        raise ValueError('Finite 3D spline points and u in [0,1] required')
    p0, p1, p2, p3 = points
    if u == 0 or p1 == p2:
        return p1
    if u == 1:
        return p2
    t1 = math.sqrt(max(math.dist(p0, p1), 1e-6))
    t2 = t1 + math.sqrt(max(math.dist(p1, p2), 1e-6))
    t3 = t2 + math.sqrt(max(math.dist(p2, p3), 1e-6))
    t = t1 + u * (t2 - t1)
    def mix(a, b, f):
        return tuple(x + (y - x) * f for x, y in zip(a, b))
    a1 = mix(p0, p1, t / t1)
    a2 = mix(p1, p2, (t - t1) / (t2 - t1))
    a3 = mix(p2, p3, (t - t2) / (t3 - t2))
    b1 = mix(a1, a2, t / t2)
    b2 = mix(a2, a3, (t - t1) / (t3 - t1))
    result = mix(b1, b2, (t - t1) / (t2 - t1))
    if not all(math.isfinite(v) for v in result):
        raise ValueError('Spline evaluation exceeded finite arithmetic range')
    return result


class RibbonHistory:
    """One fixed ring; every admitted knot retains its absolute coordinate.

    Batch boundaries do not affect results for identical input knots. Callers
    sample their signal on an explicit lattice; this class does not resample
    arbitrary frame observations or promise dt invariance for different knots.
    """
    def __init__(self, capacity: int = MAX_PATH_SAMPLES):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or not 2 <= capacity <= MAX_PATH_SAMPLES:
            raise ValueError('Ribbon capacity must be an integer from 2 to 256')
        self._data = np.zeros((capacity, RECORD_FLOATS), dtype=np.float64)
        self._start = self._count = 0
        self.epoch = 0

    @property
    def capacity(self):
        return len(self._data)

    @property
    def payload_bytes(self):
        return self._data.nbytes

    def __len__(self):
        return self._count

    def clear(self):
        self.epoch += 1
        self._start = self._count = 0
        self._data.fill(0.)

    def _row(self, index):
        return self._data[(self._start + index) % self.capacity]

    def records(self):
        """Owned chronological float64 copy for diagnostics, not a GPU upload ABI."""
        return self._data[(self._start + np.arange(self._count)) % self.capacity].copy()

    def append(self, sample: PathSample):
        self.extend((sample,))

    def extend(self, samples):
        # Validate a bounded complete batch before changing any retained knot.
        admitted = []
        last = self._row(self._count - 1)[0] if self._count else -math.inf
        for sample in samples:
            if len(admitted) >= self.capacity:
                raise ValueError('Batch exceeds ribbon capacity; submit bounded batches')
            value = sample.admitted()
            if value.coordinate <= last:
                raise ValueError('Ribbon coordinates must increase strictly; clear before reset/reversal')
            admitted.append(value)
            last = value.coordinate
        for value in admitted:
            if self._count == self.capacity:
                self._start = (self._start + 1) % self.capacity
                self._count -= 1
            row = self._row(self._count)
            row[:] = (value.coordinate, *value.position, value.half_width, value.twist, 0., 0.)
            self._count += 1

    def evaluate(self, coordinate: float) -> PathSample | None:
        """Evaluate within retained support; expired coordinates fail, never pin.

        End controls are linearly extrapolated. Only segments with their four
        support knots retained are stable across insertion/eviction; newest and
        oldest boundary segments are explicitly provisional.
        """
        if not math.isfinite(coordinate):
            raise ValueError('Finite ribbon coordinate required')
        if not self._count:
            return None
        rows = self.records()
        if not rows[0, 0] <= coordinate <= rows[-1, 0]:
            raise ValueError('Ribbon coordinate is outside retained support')
        if self._count == 1:
            return PathSample(rows[0, 0], tuple(rows[0, 1:4]), rows[0, 4], rows[0, 5])
        index = min(int(np.searchsorted(rows[:, 0], coordinate, side='right')) - 1, self._count - 2)
        left, right = rows[index], rows[index + 1]
        for knot in (left, right):
            if coordinate == knot[0]:
                return PathSample(coordinate, tuple(knot[1:4]), knot[4], knot[5])
        u = (coordinate - left[0]) / (right[0] - left[0])
        p1, p2 = left[1:4], right[1:4]
        p0 = rows[index - 1, 1:4] if index else 2*p1 - p2
        p3 = rows[index + 2, 1:4] if index + 2 < self._count else 2*p2 - p1
        point = centripetal_point(p0, p1, p2, p3, u)
        width = (1-u)*left[4] + u*right[4]
        # Weighted positive terms avoid large-ratio cancellation. Clamp only to
        # authored endpoint bounds (also protects subnormal underflow), no floor.
        width = max(min(left[4], right[4]), min(max(left[4], right[4]), width))
        twist = (1-u)*left[5] + u*right[5]
        return PathSample(coordinate, point, width, twist)
