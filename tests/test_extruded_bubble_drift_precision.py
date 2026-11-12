"""The drift solver's arithmetic without any 64-bit float (D4.1), modelled in NumPy float32 in the compute
programs' operation order, against the float64 CPU reference (``MaterialDriftReference``) on runs that start at an
hour's and at eight hours' stream travel and motion phase. No GPU: this proves the formulation the programs use.

The float64 work is done once on the logical side and published: each chain's knot decision per step (the
reference's own ``KnotClock``), the field's growing phase arguments reduced mod 2 pi, travel as a float pair, and
per mote ``carry / span`` as a float pair and the seed as a head. Everything modelled here is float32: the
per-mote quotient ``travel x carry / span`` is rebuilt from pairs (an fma two-product), and the seed and the phase
offset are pairs too, so a mote recycles on the reference's tick at any horizon.
"""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from core.constants.extruded_bubble_world import WORLD_UNIT
from widgets.spotify_visualizer import extruded_bubble_drift as drift
from widgets.spotify_visualizer.extruded_bubble_drift_log import (
    KNOT_DECISION, STEP_INDEX, MaterialDriftReference, float_pair, newest_knots, reduced_angles, seed_heads,
    unpack_steps,
)
from widgets.spotify_visualizer.extruded_bubble_material_paths import PATH_NODES
from widgets.spotify_visualizer.extruded_bubble_simulation import (
    ExtrudedBubbleControls, ExtrudedBubbleSimulation, MusicInput,
)

F = np.float32
R = STEP_INDEX
HOUR, EIGHT_HOURS = (32400., 9400.), (259200., 75000.)   # (travel, motion phase) at the fastest stream speed


# -- the float32 pair arithmetic, one function per shader function, same operation order ----------------------------

def two_sum(a, b):
    s = a + b
    v = s - a
    return s, (a - (s - v)) + (b - v)


def fast_two_sum(a, b):
    s = a + b
    return s, b - (s - a)


def two_prod(a, b):
    """``(p, fma(a, b, -p))``: the error of a float32 product is itself a float32, so float64 computes it exactly."""
    p = a * b
    return p, (np.float64(a) * np.asarray(b, dtype=np.float64) - np.asarray(p, dtype=np.float64)).astype(F)


def mul_pair(x, y):
    (xh, xl), (yh, yl) = x, y
    p, e = two_prod(xh, yh)
    return fast_two_sum(p, e + (xh * yl + xl * yh))


def fract_sum(x, y, z):
    """The fractional part of ``x + y + z`` as a pair: ``x`` any size, ``y`` and ``z`` within [0, 1]."""
    (xh, xl), (yh, yl), (zh, zl) = x, y, z
    n = np.floor(xh)
    head = xh - n
    a, ae = two_sum(head, yh)
    b, be = two_sum(a, zh)
    lo = (((xl + yl) + zl) + ae) + be
    s, se = two_sum(b, lo)
    m = np.floor(s)
    m = np.where((s == m) & (se < 0), m - F(1), m)
    return fast_two_sum(s - m, se)


# -- the float32 drift field (the compute programs' driftVelocity) --------------------------------------------------

_TAU = F(2 * math.pi)


def _sin(x):
    """``sin`` of a bounded argument, brought into [-pi, pi) first as the shader does."""
    return np.sin(x - _TAU * np.floor(x / _TAU + F(.5)))


def velocity32(kind, world, phase, angles, direction, across, depth, origin, amount):
    a0, a1, a2, a3 = (F(a) for a in angles)
    meander = F(1.) if kind == 0 else F(drift._STEERED_WANDER)
    wander = meander * amount * F(.05) * (_sin(a0 + phase) + F(.6) * _sin(a1 + F(2.1) * phase))
    deep = meander * amount * F(.015) * _sin(a2 + F(1.7) * phase)
    directed = np.zeros_like(world)
    if kind == 1:
        directed = directed + amount * (-F(drift._STEER_SPEED) * across)
    elif kind == 2:
        directed = directed + amount * (F(drift._STEER_SPEED) * across)
    elif kind == 3:
        directed = directed + amount * (F(drift._STEER_SPEED) * np.sqrt(F(.5)) * (across + depth))
    elif kind == 6:
        directed = amount * (F(drift._RANDOM_SPEED) * (np.cos(phase)[..., None] * across
                                                       + np.sin(phase)[..., None] * depth)) + directed
    elif kind in (4, 5):
        sway = F(drift._SWISH_SPEED) * _sin(a3 - F(.35) * np.sin(phase))
        directed = directed + amount * sway[..., None] * (across if kind == 4 else depth)
    elif kind in (7, 8):
        r = world - origin
        radial = r - (r @ direction)[..., None] * direction
        distance = np.sqrt((radial * radial).sum(-1))
        with np.errstate(divide="ignore", invalid="ignore"):
            radial = np.where((distance < F(1e-3 * WORLD_UNIT))[..., None],
                              np.cos(phase)[..., None] * across + np.sin(phase)[..., None] * depth,
                              radial / distance[..., None])
        tangent = np.cross(direction, radial).astype(F)
        sign = F(1.) if kind == 8 else F(-1.)
        directed = amount * (sign * F(drift._SWIRL_SPEED) * tangent + F(drift._SWIRL_WIDEN) * radial)
    return across * wander[..., None] + depth * deep[..., None] + directed


def _field(record):
    vec = lambda name: record[R[name + "_x"]:R[name + "_x"] + 3].astype(F)
    angles = tuple(record[R[name]] for name in ("angle_wander", "angle_wander_2", "angle_deep", "angle_swish"))
    return int(record[R["kind"]]), angles, vec("direction"), vec("across"), vec("depth"), vec("origin")


# -- the two programs, modelled -------------------------------------------------------------------------------------

_PROGRESS = (np.arange(PATH_NODES) - 1).astype(F) / F(PATH_NODES - 3)


class ChainModel:
    """The chain program: knot rows of float32 displacement moved by the published decisions."""

    def __init__(self) -> None:
        self.revision = None

    def _geometry(self, family):
        base, spans, carry, phases = family.source
        return (base[:, 0].astype(F), base[:, -1].astype(F), spans.astype(F), carry.astype(F), phases.astype(F))

    def admit(self, family) -> None:
        if family.revision == self.revision:
            if family.capacity != len(self.displacement):
                keep = min(family.capacity, len(self.displacement))
                displacement = np.zeros((family.capacity, PATH_NODES, 3), F)
                displacement[:keep] = self.displacement[:keep]
                shift = np.zeros(family.capacity, F)
                shift[:keep] = self.shift[:keep]
                self.displacement, self.shift = displacement, shift
                self.geometry = self._geometry(family)
            return
        self.rebase = (self.geometry, self.rows) if family.rebase_from and family.rebase_from == self.revision else None
        if self.rebase is None:
            self.displacement = np.zeros((family.capacity, PATH_NODES, 3), F)
            self.shift = np.zeros(family.capacity, F)
            self.rows = 0
        else:
            keep = min(family.capacity, len(self.displacement))
            displacement = np.zeros((family.capacity, PATH_NODES, 3), F)
            displacement[:keep] = self.displacement[:keep]
            shift = np.zeros(family.capacity, F)
            shift[:keep] = self.shift[:keep]
            self.displacement, self.shift = displacement, shift
        self.revision, self.geometry = family.revision, self._geometry(family)

    def step(self, record, decisions: bytes) -> np.ndarray:
        start, end, span, carry, phase = self.geometry
        rows = int(record[R["chain_rows"]])
        decided = np.frombuffer(decisions, dtype=KNOT_DECISION)
        displacement = self.displacement
        displacement[rows:] = 0.                          # a row the step does not hold has no history
        if self.rebase is not None:
            (old_start, old_end, *_), old_rows = self.rebase
            keep = min(rows, old_rows)
            q = (_PROGRESS[None, :] + self.shift[:keep, None])[..., None]
            displacement[:keep] += ((old_start[:keep, None] + (old_end - old_start)[:keep, None] * q)
                                    - (start[:keep, None] + (end - start)[:keep, None] * q))
            self.rebase = None
        moved, shift = decided["moved"], decided["shift"]
        for row in np.flatnonzero(moved > 0):
            source = np.arange(PATH_NODES) - moved[row]
            shifted = displacement[row, np.maximum(source, 0)]
            shifted[source < 0] = 0.
            displacement[row] = shifted
        kind, angles, direction, across, depth, origin = _field(record)
        q = _PROGRESS[None, :] + shift[:, None]
        world = start[:rows, None] + (end - start)[:rows, None] * q[..., None] + displacement[:rows]
        field = velocity32(kind, world, phase[:rows, None], angles, direction, across, depth, origin,
                           F(record[R["amount_chains"]]))
        rate = (F(record[R["speed"]]) * carry[:rows]) / span[:rows]
        available = np.maximum(F(0.), np.minimum(F(record[R["dt"]]), q / np.maximum(rate[:, None], F(1e-12))))
        displacement[:rows] += field * available[..., None]
        displacement[:rows][q <= 0.] = 0.
        self.shift[:rows], self.rows = shift, rows
        out = np.zeros((rows, PATH_NODES, 4), F)
        out[..., :3] = displacement[:rows]
        out[:, 0, 3], out[:, 1, 3] = shift, decided["phase_offset"]
        return out


def _plain(x, y, z):
    """The negative control: what a direct float32 port computes (no pairs), as a pair with no low part."""
    value = (x[0] + y[0]) + z[0]
    return value - np.floor(value), F(0.)


class CloudModel:
    """The cloud program: per mote float32 displacement, its phase offset as a pair, progress from pairs.
    ``plain`` models a direct float32 port instead (the negative control)."""

    def __init__(self, name: str, plain: bool = False) -> None:
        self.name, self.revision, self.plain = name, None, plain

    @staticmethod
    def _geometry(family):
        start, spans, seed, carry, phases = family.source
        head = seed_heads(seed)
        rows = np.frombuffer(family.geometry, dtype=F).reshape(-1, 2, 4)   # the published carry / span pair
        return dict(start=start.astype(F), span=spans.astype(F), seed=(head, head * F(2. ** -24)),
                    ratio=(rows[:, 1, 2].copy(), rows[:, 1, 3].copy()), phase=phases.astype(F), carry=F(carry))

    def _resize(self, capacity: int) -> None:
        keep = min(capacity, len(self.displacement))
        for name in ("displacement", "base", "po_high", "po_low"):
            old = getattr(self, name)
            new = np.zeros((capacity, *old.shape[1:]), F)
            new[:keep] = old[:keep]
            setattr(self, name, new)

    def admit(self, family) -> None:
        if family.revision == self.revision:
            if family.capacity != len(self.displacement):
                self._resize(family.capacity)
                self.geometry = self._geometry(family)
            return
        rebase = family.rebase_from and family.rebase_from == self.revision
        self.rebase = self.geometry if rebase else None
        if rebase:
            self._resize(family.capacity)
        else:
            self.displacement, self.base = np.zeros((family.capacity, 3), F), np.zeros((family.capacity, 3), F)
            self.po_high, self.po_low = np.zeros(family.capacity, F), np.zeros(family.capacity, F)
            self.count, self.last, self.first = 0, (F(0.), F(0.)), True
        self.revision, self.geometry = family.revision, self._geometry(family)

    def step(self, record) -> np.ndarray:
        g = self.geometry
        kind, angles, direction, across, depth, origin = _field(record)
        alive = np.arange(len(self.displacement)) < self.count
        if self.rebase is not None:
            # An edited geometry keeps every mote where it was (ProceduralOffsets), the quotients from pairs.
            old, last, n = self.rebase, self.last, min(self.count, len(self.displacement), len(self.rebase["span"]))
            ratio = tuple(part[:n] for part in g["ratio"])
            a = mul_pair(last, tuple(part[:n] for part in old["ratio"]))
            b = mul_pair(last, ratio)
            d, de = two_sum(a[0], -b[0])
            po = fract_sum((d, de + (a[1] - b[1])), (self.po_high[:n], self.po_low[:n]), (F(0.), F(0.)))
            self.po_high[:n], self.po_low[:n] = po
            previous = fract_sum(b, tuple(part[:n] for part in g["seed"]), po)[0]
            self.displacement[:n] += self.base[:n] - (g["start"][:n] + direction * (previous * g["span"][:n])[:, None])
            self.rebase = None
        count = int(record[R[f"count_{self.name}"]])
        travel = (F(record[R["travel_high"]]), F(record[R["travel_low"]]))
        live = np.arange(len(self.displacement)) < count
        reset = ~live | ~alive
        self.displacement[reset], self.po_high[reset], self.po_low[reset] = 0., 0., 0.
        n = count
        ratio, seed = tuple(p[:n] for p in g["ratio"]), tuple(p[:n] for p in g["seed"])
        po = (self.po_high[:n], self.po_low[:n])
        wrap, mul = ((_plain, lambda x, y: (x[0] * y[0], F(0.))) if self.plain else (fract_sum, mul_pair))
        before = wrap(mul(self.last, ratio), seed, po)[0]
        progress = wrap(mul(travel, ratio), seed, po)[0]
        moved = (travel[0] - self.last[0]) + (travel[1] - self.last[1])
        recycled = (~np.bool_(self.first)) & ((progress < before - F(1e-10)) | (moved * ratio[0] >= F(1.)))
        displacement = self.displacement[:n]
        displacement[recycled] = 0.
        span = g["span"][:n]
        base = g["start"][:n] + direction * (progress * span)[:, None]
        field = velocity32(kind, base + displacement, g["phase"][:n], angles, direction, across, depth, origin,
                           F(record[R[f"amount_{self.name}"]]))
        dt = F(record[R["dt"]])
        available = np.where(recycled, np.minimum(dt, (progress * span) / np.maximum(F(record[R["speed"]]) * g["carry"],
                                                                                      F(1e-12))), dt)
        displacement += field * available[:, None]
        self.base[:n] = base
        self.count, self.last, self.first = count, travel, False
        out = np.empty((n, 4), F)
        out[:, :3], out[:, 3] = displacement, progress - recycled.astype(F)
        return out


# -- runs -----------------------------------------------------------------------------------------------------------

def controls(kind, emission=(.4, .9), **extra):
    """Test-owned controls; the default emission fills the speck cloud (216,000 motes)."""
    return ExtrudedBubbleControls(large_count=(2, 2), mid_count=(3, 3), bead_chains=(2., 3.), emission=emission,
                                  stream_path=(0., -1., 0., .2, 1., .1), emission_geometry='SCENE',
                                  drift=(.6, 1.), drift_chains=(1., 1.5), drift_snow=(1., 1.), drift_specks=(1., 1.),
                                  drift_direction=kind, stream_speed=(.4, 1.), collision_scope='off', **extra)


def long_log(kind, ticks, start, *, seed=11, edit_at=None, resize_at=None, emission=(.4, .9)):
    """A simulated drive whose stream travel and motion phase start at ``start`` (as after hours of play)."""
    sim = ExtrudedBubbleSimulation(seed)
    sim._travel, sim._motion_phase = start
    c = controls(kind, emission)
    for tick in range(ticks):
        body = .8 if tick % 30 < 12 else .3
        if tick == edit_at:
            c = replace(c, stream_path=(.1, -1., .1, -.2, 1., .2), particle_spread=1.2)
        if tick == resize_at:
            c = replace(c, bead_chains=(3., 4.))
        state = sim.advance(MusicInput(1 / 60, True, body, (('kick', 1.),) if tick % 20 == 0 else (),
                                       (body, body * .8, .5)), c)
        yield state.drift_families, state.drift_steps, state.drift_knots


class ModelRun:
    """Drives the reference and the float32 model over one log, with the decisions the drift log published."""

    def __init__(self) -> None:
        self.reference = MaterialDriftReference()
        self.chains, self.clouds = ChainModel(), {name: CloudModel(name) for name in ("snow", "specks")}
        self.plain, self.plain_channel = {name: CloudModel(name, plain=True) for name in ("snow", "specks")}, 0.
        self.worst, self.wrap_mismatches, self.moved_equal, self.moved_steps = {}, 0, 0, 0

    def apply(self, families, steps, knots) -> None:
        record = unpack_steps(steps)[-1]
        live = {family.family: family for family in families}
        chains = live.get("chains")
        decisions = newest_knots(steps, knots)[1]
        payload = self.reference.apply(families, steps)
        got = {}
        if chains is not None:
            self.chains.admit(chains)
            got["chains"] = self.chains.step(record, decisions)
            reference_clock = self.reference._state["chains"][1].clock
            if reference_clock.moved is not None:
                self.moved_steps += 1
                published = np.frombuffer(decisions, dtype=KNOT_DECISION)["moved"]
                self.moved_equal += int(np.array_equal(published, reference_clock.moved))
        for name in ("snow", "specks"):
            if name in live:
                self.clouds[name].admit(live[name])
                got[name] = self.clouds[name].step(record)
                self.plain[name].admit(live[name])
                plain = self.plain[name].step(record)[:, 3]
                expected = np.frombuffer(payload[name], dtype=np.float32).reshape(-1, 4)[:, 3]
                self.plain_channel = max(self.plain_channel, float(np.abs(plain - expected).max(initial=0.)))
        for name, values in got.items():
            expected = np.frombuffer(payload[name], dtype=np.float32).reshape(values.shape)
            scale = max(1., float(np.abs(expected[..., :3]).max(initial=0.)))
            error = float(np.abs(values[..., :3] - expected[..., :3]).max(initial=0.)) / scale
            channel = np.abs(values[..., 3] - expected[..., 3])
            worst = self.worst.setdefault(name, [0., 0.])
            worst[0], worst[1] = max(worst[0], error), max(worst[1], float(channel.max(initial=0.)))
            self.wrap_mismatches += int((channel > .5).sum())


def run(log) -> ModelRun:
    model = ModelRun()
    for families, steps, knots in log:
        if families:
            model.apply(families, steps, knots)
    return model


# -- the proof ------------------------------------------------------------------------------------------------------

def test_pair_product_is_the_fma_two_product():
    rng = np.random.default_rng(3)
    a = rng.uniform(1., 3e5, 2000).astype(F)
    b = rng.uniform(1e-3, 300., 2000).astype(F)
    p, e = two_prod(a, b)
    assert all(float(e[i]) == float(np.float32(math.fma(float(a[i]), float(b[i]), -float(p[i]))))
               for i in range(len(a)))


def test_published_angles_and_pairs_carry_the_float64_values():
    t = 75000.123456789
    for angle, rate in zip(reduced_angles(t), drift.PHASE_RATES):
        assert 0. <= angle < 2 * math.pi + 1e-6
        assert abs(math.sin(angle + .7) - math.sin(t * rate + .7)) < 1e-6
    high, low = float_pair(np.array([259200.123456789]))
    assert abs(float(high[0]) + float(low[0]) - 259200.123456789) < 259200. * 2. ** -47
    seeds = np.arange(0, 1 << 24, 4099, dtype=np.float64) / float(0xffffff)
    head = seed_heads(seeds).astype(np.float64)
    assert np.abs(head + head * 2. ** -24 - seeds).max() < 2. ** -47
    with pytest.raises(ValueError):
        seed_heads(np.array([.1]))


@pytest.mark.parametrize("start", (HOUR, EIGHT_HOURS), ids=("hour", "eight_hours"))
@pytest.mark.parametrize("kind", ("swish_across", "swirl_cw"))
def test_float32_model_matches_the_float64_reference_at_long_horizon(kind, start):
    # Every tick compared; a geometry edit (the rebase) at 80 and a chain-count change (a resize) at 120.
    model = run(long_log(kind, 160, start, edit_at=80, resize_at=120, emission=(.15, .3)))
    assert set(model.worst) == {"chains", "snow", "specks"}
    assert model.moved_steps > 150 and model.moved_equal == model.moved_steps
    assert model.wrap_mismatches == 0
    assert max(error for error, _channel in model.worst.values()) < 1e-4, model.worst
    assert max(channel for _error, channel in model.worst.values()) < 1e-4, model.worst
    # The bar is not blind: a direct float32 port of the quotient misses it on the same run.
    assert model.plain_channel > 1e-4, model.plain_channel
