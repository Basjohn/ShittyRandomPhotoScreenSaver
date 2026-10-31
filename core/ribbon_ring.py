"""Incremental ribbon producer for the WR-02 packet ABI; no GL, clock, timer or simulation.

The stateless route (`strip_path` frames -> `pack_ribbons`) rebuilds every knot and stays the test oracle.
This owner keeps the packet as a persistent float32 staging array with ring addressing, so admitting one
knot per ribbon is O(ribbons) vectorised work and publication is one bytes copy (cached until the next
change). All ribbons share one sampling lattice: one coordinate, one ring cursor. The consuming logical
owner calls `append`/`packet` from its own tick and drops the object on retirement.

Width bases are transported along chords into each knot with the oracle's minimal-rotation formula; the
shader re-projects the interpolated base onto the actual spline tangent and applies twist. A knot after a
start, clear or reversal is pending (invalid) until the next chord seeds it, so a strip never bridges a
break or silently flips roll. Admitted frames are immutable: insertion and eviction rewrite no other knot.

Float32 locals are rebased in bulk only when they drift: coordinates beyond 16 s, positions beyond 64
world units, twist beyond 16 pi from their origins. Retained spans are admitted against the limits below
before any mutation, so a rejected knot leaves the ring unchanged.
"""
import math

import numpy as np

from core.ribbon_frames import CUSP_COSINE, MAX_SUBDIVISIONS
from core.ribbon_geometry import (MAX_COORDINATE_MAGNITUDE, MAX_PATH_SAMPLES, MAX_TWIST_MAGNITUDE,
                                  MAX_WORLD_MAGNITUDE)
from core.ribbon_packet import MAX_LOCAL_SPAN, MAX_RIBBONS, RibbonPacket

HEADER_ROWS = 4  # meta, extra, colourA, colourB (vec4 each)
MIN_HALF_WIDTH = 1e-4  # resolvable beside positions within the local domain (float32 ulp <= 1.5e-5)
COORDINATE_REBASE = 16.
POSITION_REBASE = 64.
MAX_POSITION_SPREAD = 128.  # every |local| <= 128 -> float32 rounding <= 3.9e-6 world units
TWIST_REBASE = 16*math.pi
MAX_TWIST_SPREAD = 64*math.pi
MIN_COORDINATE_STEP = 1e-4  # stays strictly ordered in float32 anywhere in the +/-64 s local window
_CHORD_EPSILON = 1e-12
_NO_KNOT, _PENDING, _ACTIVE = 0, 1, 2


class RibbonRing:
    def __init__(self, ribbons: int, *, capacity: int = MAX_PATH_SAMPLES, subdivisions: int = 8,
                 period: float = 1., colours=None, seed_side=(0., 1., 0.)):
        if isinstance(ribbons, bool) or not isinstance(ribbons, int) or not 1 <= ribbons <= MAX_RIBBONS:
            raise ValueError('Ribbon count must be an integer in 1..8')
        if isinstance(capacity, bool) or not isinstance(capacity, int) or not 2 <= capacity <= MAX_PATH_SAMPLES:
            raise ValueError('Ribbon capacity must be an integer from 2 to 256')
        if isinstance(subdivisions, bool) or not isinstance(subdivisions, int) or not 1 <= subdivisions <= MAX_SUBDIVISIONS:
            raise ValueError('Ribbon subdivisions must be an integer in 1..8')
        if not math.isfinite(period) or not np.finfo(np.float32).tiny <= period <= np.finfo(np.float32).max:
            raise ValueError('Finite positive strand period required')
        if MAX_LOCAL_SPAN/period > 4096:
            raise ValueError('Strand period too short for the local phase window')
        colours = np.broadcast_to(np.asarray((.1, .7, .9, 1.) if colours is None else colours, dtype=np.float64), (ribbons, 4))
        if not (np.isfinite(colours).all() and (colours >= 0).all() and (colours <= 1).all()):
            raise ValueError('Ribbon colours require finite normalized channels')
        seed = np.asarray(seed_side, dtype=np.float64)
        if seed.shape != (3,) or not np.isfinite(seed).all() or not np.linalg.norm(seed) > 0:
            raise ValueError('Finite non-zero seed side required')
        self.ribbons, self.capacity, self.subdivisions, self.period = ribbons, capacity, subdivisions, float(period)
        self._seed = seed/np.linalg.norm(seed)
        self._gpu = np.zeros((ribbons, HEADER_ROWS + MAX_PATH_SAMPLES*4, 4), dtype=np.float32)
        self._gpu[:, 0, 1], self._gpu[:, 0, 3] = subdivisions, period
        self._gpu[:, 1, 2] = capacity
        self._gpu[:, 2] = self._gpu[:, 3] = colours
        self._coordinate = np.zeros(capacity)
        self._position = np.zeros((ribbons, capacity, 3))
        self._twist = np.zeros((ribbons, capacity))
        self._last_position = np.zeros((ribbons, 3))
        self._last_tangent = np.zeros((ribbons, 3))
        self._base = np.zeros((ribbons, 3))
        self._state = np.zeros(ribbons, dtype=np.int8)
        self._start = self._count = 0
        self._coordinate_origin = 0.
        self._position_origin = np.zeros(3)
        self._twist_origin = np.zeros(ribbons)
        self._packet = None
        self.epoch = 0

    def __len__(self):
        return self._count

    @property
    def payload_bytes(self):
        return self._gpu.nbytes

    def clear(self):
        """Forget all knots and frames; the next knots start new pending strips."""
        self.epoch += 1
        self._start = self._count = 0
        self._gpu[:, HEADER_ROWS:] = 0
        self._gpu[:, 0, 0] = self._gpu[:, 1, 1] = 0
        self._state[:] = _NO_KNOT
        self._packet = None

    def append(self, coordinate: float, positions, half_widths, twists=0.):
        """Admit one knot per ribbon at one shared lattice coordinate; validated before any mutation."""
        q = float(coordinate)
        p = np.asarray(positions, dtype=np.float64)
        w = np.broadcast_to(np.asarray(half_widths, dtype=np.float64), (self.ribbons,))
        tw = np.broadcast_to(np.asarray(twists, dtype=np.float64), (self.ribbons,))
        if p.shape != (self.ribbons, 3):
            raise ValueError('One 3D position per ribbon required')
        if not math.isfinite(q) or abs(q) > MAX_COORDINATE_MAGNITUDE:
            raise ValueError('Finite bounded ribbon coordinate required')
        if not (np.isfinite(p).all() and np.isfinite(w).all() and np.isfinite(tw).all()):
            raise ValueError('Ribbon knots require finite positions, widths and twists')
        if (np.abs(p) > MAX_WORLD_MAGNITUDE).any() or (np.abs(tw) > MAX_TWIST_MAGNITUDE).any():
            raise ValueError('Ribbon position or twist exceeds the reference range')
        if (w < MIN_HALF_WIDTH).any() or (w > MAX_WORLD_MAGNITUDE).any():
            raise ValueError('Ribbon half-width must be resolvable and bounded')
        full = self._count == self.capacity
        if self._count:
            newest = self._coordinate[(self._start + self._count - 1) % self.capacity]
            if q <= newest:
                raise ValueError('Ribbon coordinates must increase strictly; clear before reset/reversal')
            if q - newest < MIN_COORDINATE_STEP:
                raise ValueError('Ribbon coordinate step is below the float32 local resolution')
            oldest_index = 1 if full else 0
            if self._count > oldest_index and q - self._coordinate[(self._start + oldest_index) % self.capacity] > MAX_LOCAL_SPAN:
                raise ValueError('Retained ribbon history exceeds the 64-second local coordinate span')
        start = (self._start + 1) % self.capacity if full else self._start
        count = self._count if full else self._count + 1
        slot = (start + count - 1) % self.capacity
        rebase = (not self._count or q - self._coordinate_origin > COORDINATE_REBASE
                  or (np.abs(p - self._position_origin) > POSITION_REBASE).any()
                  or (np.abs(tw - self._twist_origin) > TWIST_REBASE).any())
        if rebase:
            retained = (start + np.arange(count - 1)) % self.capacity
            origin_q, origin_p, origin_tw = q, p.mean(axis=0), tw.copy()
            if count > 1:
                if (np.abs(self._position[:, retained] - origin_p) > MAX_POSITION_SPREAD).any():
                    raise ValueError('Retained ribbon positions spread beyond the float32 local domain')
                if (np.abs(self._twist[:, retained] - origin_tw[:, None]) > MAX_TWIST_SPREAD).any():
                    raise ValueError('Retained ribbon twist spans beyond the float32 local domain')
            local_q = 0.
        else:
            local_q = q - self._coordinate_origin

        # Frames: chord into this knot, transported from the previous chord (oracle formula).
        state = self._state
        chord = p - self._last_position
        length = np.sqrt((chord*chord).sum(axis=1))
        moving = (state != _NO_KNOT) & (length > _CHORD_EPSILON*np.maximum(1., np.abs(p).max(axis=1)))
        tangent = np.divide(chord, length[:, None], out=np.zeros_like(chord), where=moving[:, None])
        base = self._base.copy()
        new_state = state.copy()
        valid = state == _ACTIVE  # active + repeated point keeps its base
        resolve_previous = np.zeros(self.ribbons, dtype=bool)
        seeded = moving & (state == _PENDING)
        if seeded.any():
            candidate = self._seed - tangent*(tangent @ self._seed)[:, None]
            norm = np.sqrt((candidate*candidate).sum(axis=1))
            ok = seeded & (norm > 1e-10)
            base[ok] = candidate[ok]/norm[ok, None]
            valid |= ok
            resolve_previous = ok
            new_state[ok] = _ACTIVE
        carried = moving & (state == _ACTIVE)
        if carried.any():
            previous = self._last_tangent
            c = np.clip((previous*tangent).sum(axis=1), -1., 1.)
            axis = np.cross(previous, tangent)
            first = np.cross(axis, self._base)
            second = np.cross(axis, first)
            rotated = self._base + first + second/np.maximum(1. + c, 1e-300)[:, None]
            rotated -= tangent*(rotated*tangent).sum(axis=1)[:, None]
            norm = np.sqrt((rotated*rotated).sum(axis=1))
            ok = carried & (c > CUSP_COSINE) & (norm > 1e-10)
            base[ok] = rotated[ok]/norm[ok, None]
            broken = carried & ~ok
            valid[broken] = False  # explicit strip break: this knot waits for a new seed
            new_state[broken] = _PENDING
        new_state[state == _NO_KNOT] = _PENDING

        # Commit: nothing below can fail.
        if rebase:
            self._coordinate_origin, self._position_origin, self._twist_origin = origin_q, origin_p, origin_tw
            self._gpu[:, 0, 2] = (origin_q % self.period)/self.period
            self._gpu[:, 1, 0] = origin_tw % (2*math.pi)
            if count > 1:
                rows = HEADER_ROWS + 4*retained
                self._gpu[:, rows, 0:3] = self._position[:, retained] - origin_p
                self._gpu[:, rows + 1, 0] = self._coordinate[retained] - origin_q
                self._gpu[:, rows + 1, 1] = self._twist[:, retained] - origin_tw[:, None]
        row = HEADER_ROWS + 4*slot
        self._coordinate[slot] = q
        self._position[:, slot] = p
        self._twist[:, slot] = tw
        self._gpu[:, row, 0:3] = p - self._position_origin
        self._gpu[:, row, 3] = w
        self._gpu[:, row + 1] = 0
        self._gpu[:, row + 1, 0] = local_q
        self._gpu[:, row + 1, 1] = tw - self._twist_origin
        self._gpu[:, row + 1, 2] = valid
        self._gpu[:, row + 2, 0:3] = tangent
        self._gpu[:, row + 3, 0:3] = np.where(valid[:, None], base, 0.)
        if resolve_previous.any() and count > 1:
            previous_row = HEADER_ROWS + 4*((slot - 1) % self.capacity)
            self._gpu[resolve_previous, previous_row + 1, 2:4] = 1.  # valid, and starts a strip
            self._gpu[resolve_previous, previous_row + 2, 0:3] = tangent[resolve_previous]
            self._gpu[resolve_previous, previous_row + 3, 0:3] = base[resolve_previous]
        self._last_position = p.copy()
        self._last_tangent = np.where(moving[:, None], tangent, self._last_tangent)
        self._base = np.where(valid[:, None], base, self._base)
        self._state = new_state
        self._start, self._count = start, count
        self._gpu[:, 0, 0] = count
        self._gpu[:, 1, 1] = start
        self._packet = None

    def packet(self) -> RibbonPacket:
        """Immutable publication of the current knots; repeated calls without changes reuse it."""
        if self._packet is None:
            drawable = False
            if self._count >= 2:
                slots = (self._start + np.arange(self._count)) % self.capacity
                flags = self._gpu[:, HEADER_ROWS + 4*slots + 1, 2:4] > .5
                live, starts = flags[..., 0], flags[..., 1]
                drawable = bool((live[:, :-1] & live[:, 1:] & ~starts[:, 1:]).any())
            if drawable:
                self._packet = RibbonPacket(self._gpu.tobytes(), self.ribbons,
                                            (self._count - 1)*self.subdivisions*6, tuple(self._position_origin.tolist()))
            else:
                self._packet = RibbonPacket(b'', 0, 0)
        return self._packet
