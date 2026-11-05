"""Selectable Waveform reaction modes and the flow rule they all obey.

Flow rule (operator, 5 Nov): a swell moves the waveform only WITH its own shape. Horizontal motion is the steady
history flow plus an along-curve surge that slides knots along their own curve; a swell may deepen the curvature the
waveform already has but never reverses it (no inward dent, flattened kink or new inflection), and there is no axial
scaling. Test-owned controls only (never presets or defaults); the baseline is the same model state at the same
logical time with every reaction field cleared.
"""
import copy
import hashlib
from dataclasses import replace
import numpy as np
import pytest
import core.waveform_ribbon_dynamics as dyn
from core.waveform_ribbon_dynamics import (GEOM_SLOPE, GROUP_SURGE, PULSE_GRID, PULSE_SATURATION, PULSE_SURGE,
                                           REACTION_MODES, SURGE_RATE, PulseControls, carrier_wavelength)
from tests.test_waveform_ribbon_dynamics import controls, primed, data

QUIET = {'bands': (.5, .4, .3), 'intensity': .6, 'presence': 1.}
SILENT = {'bands': (0., 0., 0.), 'intensity': 0., 'presence': 0.}
STRONG_BEND = (2., 3.)


def model_for(mode, **pulse):
    pulse = {'direction': 'Head To Tail', 'width': 10., 'speed': 3., 'fade': 4., 'colour': .6, 'saturation': .6,
             **pulse, 'mode': mode}
    c = replace(controls(), rotation_enabled=False, pulse=PulseControls(**pulse))
    c = replace(c, ranges={**c.ranges, 'bend': STRONG_BEND})
    return primed(c)


def beats(model, count=3, spacing=.25, after=.6, inputs=QUIET):
    for _ in range(count):
        model.advance(1/90, hit=1., **inputs)
        for _ in range(round(spacing*90)):
            model.advance(1/90, **inputs)
    for _ in range(round(after*90)):
        model.advance(1/90, **inputs)
    return model


def unreacted(model):
    """The same state at the same logical time with every reaction field cleared."""
    twin = copy.deepcopy(model)
    twin._pulse[:] = 0.
    twin._fresh[:] = 0.
    twin._held[:] = 0.
    twin._whole = twin._whole_fresh = 0.
    for name in ('_drift', '_level', '_focus', '_geom'):
        setattr(twin, name, np.zeros(PULSE_GRID.size))
    twin._snapshot = None
    return twin.snapshot()


def paths(snapshot):
    out = []
    for path in data(snapshot):
        count, start, capacity = int(path[0, 0]), int(path[1, 1]), int(path[1, 2])
        if count < 8:
            continue
        order = (start+np.arange(count)) % capacity
        out.append((path[4::5, 0][order].astype(np.float64), path[4::5, 1][order].astype(np.float64)))
    return out


def curvature(x, y):
    return np.gradient(np.gradient(y, x), x)


def inflections(x, y):
    k = curvature(x, y)[2:-2]
    k = k[np.abs(k) > 1e-4]
    return int((np.diff(np.sign(k)) != 0).sum())


@pytest.mark.parametrize('mode', REACTION_MODES)
def test_every_mode_moves_the_waveform_only_with_its_own_shape(mode):
    model = beats(model_for(mode))
    swelled, base = model.snapshot(), unreacted(model)
    assert np.abs(data(swelled)[:, 4::5, 1]-data(base)[:, 4::5, 1]).max() > .05  # a strong swell is present
    wavelength = carrier_wavelength(model.controls)
    band = .08*wavelength  # inflection shift bound 2*GEOM_SLOPE/k ~ .064 wavelengths (module docs)
    assert 2.*GEOM_SLOPE/(2.*np.pi/wavelength) < band
    bound = PULSE_SURGE*STRONG_BEND[1]*PULSE_SATURATION*GROUP_SURGE+1e-6
    for (xs, ys), (xb, yb) in zip(paths(swelled), paths(base)):
        assert (np.diff(xs) > 0.).all()  # never folds back
        dx = xs-xb
        assert np.abs(dx).max() <= bound
        moved = np.abs(dx) > 1e-4
        if moved.any():
            # One travel direction everywhere (Head To Tail: toward -x): no outward/inward scaling about a centre.
            assert (dx[moved] < 0.).all()
        # Compare at the same scene x: the baseline's curvature sampled where each swelled knot now is.
        kb = curvature(xb, yb)
        crossings = xb[1:][np.diff(np.sign(kb)) != 0]
        base_at_swelled = np.interp(xs, xb, kb)
        meaningful = np.abs(base_at_swelled) > 1e-3*np.abs(kb).max()
        near = np.zeros(xs.size, bool)
        for at in crossings:
            near |= np.abs(xs-at) < band
        interior = np.zeros(xs.size, bool)
        interior[3:-3] = True
        check = meaningful & ~near & interior
        ks = curvature(xs, ys)
        agree = np.sign(ks[check]) == np.sign(base_at_swelled[check])
        assert agree.all(), (mode, xs[check][~agree])
        assert inflections(xs, ys) <= inflections(xb, yb)


@pytest.mark.parametrize('mode', ('Travelling Pulse', 'Frozen Past', 'Group Wave'))
def test_the_surge_slides_knots_along_the_curve_without_changing_it(mode, monkeypatch):
    model = beats(model_for(mode))
    model._snapshot = None
    surged = model.snapshot()
    monkeypatch.setattr(dyn, 'PULSE_SURGE', 0.)
    model._snapshot = None
    still = model.snapshot()
    moved_any = False
    for (xs, ys), (x0, y0) in zip(paths(surged), paths(still)):
        dx, dy = xs-x0, ys-y0
        moved = np.abs(dx) > 1e-3
        moved_any |= bool(moved.any())
        slope = np.gradient(y0, x0)
        bend = np.gradient(slope, x0)
        # Local Taylor: dy = slope x dx + curvature x dx^2 / 2 (where the slide is short against the wavelength).
        # Second order, because deep troughs keep their real curvature (no longer saturated into flat runs).
        short = moved & (np.abs(dx) < .15)
        np.testing.assert_allclose(dy[short], slope[short]*dx[short]+.5*bend[short]*dx[short]**2, atol=.01)
        # ... and exactly: every knot lies on the unsurged curve (up to the linear reference's chord error).
        np.testing.assert_allclose(ys[3:-3], np.interp(xs, x0, y0)[3:-3], atol=.02)
    assert moved_any


def test_travelling_pulse_is_the_default_mode_and_selecting_it_explicitly_is_identical():
    assert PulseControls().mode == 'Travelling Pulse'
    def digest(pulse):
        model = primed(replace(controls(), pulse=pulse))
        h = hashlib.sha256()
        for index in range(270):
            h.update(model.advance(1/90, bands=(.4, .3, .2), intensity=.6, presence=1.,
                                   hit=1. if index % 45 == 0 else 0.).packet.payload)
        return h.hexdigest()
    implicit = digest(PulseControls(saturation=.6, colour=.6))
    assert implicit == digest(PulseControls(saturation=.6, colour=.6, mode='Travelling Pulse'))
    # No absolute digest: pulse constants are tuned artistic values, never a regression oracle.


def test_frozen_past_holds_the_shaped_cloth_then_a_later_swell_replaces_it():
    model = model_for('Frozen Past', speed=3., fade=1.5)
    model.advance(1/90, hit=1., **QUIET)
    for _ in range(round(1.4*90)):
        model.advance(1/90, **QUIET)
    # The cloth cell holding the strongest memory, tracked by its cloth coordinate (it flows with the history).
    cell = float(PULSE_GRID[int(np.argmax(model._held[0]))])
    u = cell+model.travel
    def here():
        x = u-model.travel
        return float(np.interp(x, PULSE_GRID, model._held[0])), float(np.interp(x, PULSE_GRID, model._pulse.sum(0)))
    strong, _ = here()
    assert strong > .3
    previous = strong
    for _ in range(round(2.*90)):
        model.advance(1/90, **QUIET)
        held, travelling = here()
        assert abs(held-previous) < .02  # never jumps
        previous = held
    held, travelling = here()
    assert held > .9*strong and travelling < .3*strong  # the swell has left; its shape is held
    # A weaker swell reaches the cell and smoothly replaces the held state with its own passage peak.
    model.advance(1/90, hit=.35, **QUIET)
    history = []
    for _ in range(round(6.*90)):
        model.advance(1/90, **QUIET)
        history.append(here()[0])
    steps = np.abs(np.diff(history))
    assert steps.max() < .03*strong  # smooth replacement (FROZEN_REPLACE), never a jump
    assert history[-1] < .8*strong and history[-1] > .05


def test_frozen_past_memory_is_bounded_and_fades_in_silence_without_vanishing():
    model = beats(model_for('Frozen Past'))
    assert model._held.shape == (4, PULSE_GRID.size)
    for _ in range(round(2.*90)):
        model.advance(1/90, **SILENT)
    level = model._held[0].max()
    assert level > 0.
    for _ in range(round(3.*90)):
        model.advance(1/90, **SILENT)
    after = model._held[0].max()
    assert .7*level < after < level  # persists, decays very slowly


def test_whole_swell_is_spatially_uniform_and_nothing_travels():
    model = model_for('Whole Swell')
    for _ in range(round(3.*90)):  # settle the body-energy rise of leaving silence
        model.advance(1/90, **QUIET)
    model.advance(1/90, hit=1., **QUIET)
    levels = []
    for _ in range(round(1.5*90)):
        model.advance(1/90, **QUIET)
        levels.append(model._level[0])
        assert np.ptp(model._level) == 0. and np.ptp(model._geom) == 0.
        assert not model._drift.any() and not model._pulse.any()
    peak = max(levels)
    reached = next(index for index, level in enumerate(levels) if level >= .7*peak)
    assert peak > .3 and (reached+1)/90 <= .12  # fast rise (DevCurve: 45-80 ms class)
    assert levels[-1] < .6*peak                  # gentle settle
    swelled, base = model.snapshot(), unreacted(model)
    np.testing.assert_array_equal(data(swelled)[:, 4::5, 0], data(base)[:, 4::5, 0])


def test_group_wave_surge_change_is_rate_limited_and_crests_lean_to_the_leading_edge():
    model = model_for('Group Wave', speed=3., width=6.)
    previous = model._drift.copy()
    for index in range(round(2.*90)):
        model.advance(1/90, hit=1. if index % 20 == 0 else 0., **QUIET)
        assert np.abs(model._drift-previous).max() <= SURGE_RATE/90+1e-9
        previous = model._drift.copy()
    travelling = model._pulse[0]
    lead = model._geom
    centre = float((PULSE_GRID*travelling).sum()/travelling.sum())
    leaning = float((PULSE_GRID*lead).sum()/lead.sum())
    assert leaning < centre  # Head To Tail travels toward -x: the leading edge is lower x


def test_group_wave_lifts_a_whole_set_of_crests_where_travelling_pulse_lifts_one_swell():
    """5 Nov 8 s strips: a group no wider than the pulse's own envelope read as Travelling Pulse."""
    def spans(mode):
        model = beats(model_for(mode, width=2.5, speed=6.), count=1, after=.5)
        geom, light = model._geom, model._level
        return [float((field > .5*field.max()).sum()*(PULSE_GRID[1]-PULSE_GRID[0])) for field in (geom, light)]
    (pulse_geom, pulse_light), (group_geom, group_light) = spans('Travelling Pulse'), spans('Group Wave')
    wavelength = carrier_wavelength(model_for('Group Wave').controls)
    assert group_geom > 1.8*pulse_geom and group_geom > 2.5*wavelength  # several crests lift together
    assert group_light > 1.8*pulse_light                                 # and the light covers the set


@pytest.mark.parametrize('mode', REACTION_MODES)
def test_silence_injects_nothing_in_any_mode(mode):
    model = model_for(mode)
    for _ in range(round(3.*90)):
        model.advance(1/90, **SILENT)
    assert not model._pulse.any() and not model._held.any() and model._whole == 0.
    assert not model._drift.any() and not model._level.any() and not model._geom.any()
    assert model.snapshot().packet.payload == unreacted(model).packet.payload


def test_reaction_mode_is_validated():
    with pytest.raises(ValueError):
        PulseControls(mode='Sideways Burst')


def test_hit_light_swells_instead_of_flashing():
    """Twitch guard: the rim light follows a hit with a quick rise and a gentle settle, never a one-tick flash."""
    model = model_for('Travelling Pulse')
    for _ in range(round(2.*90)):
        model.advance(1/90, **QUIET)
    model.advance(1/90, hit=1., **QUIET)
    trace = [model._glow]
    for _ in range(round(1.*90)):
        model.advance(1/90, **QUIET)
        trace.append(model._glow)
    peak = int(np.argmax(trace))
    assert trace[0] < .5*trace[peak] and peak/90 <= .15
    assert trace[round(.5*90)] > .35*trace[peak]
    assert (np.diff(trace[peak:]) <= 1e-12).all()  # settles monotonically: no back-and-forth


def test_row_gradient_is_bit_identical_to_numpy_gradient_per_row():
    """The vectorised surge relies on this to keep the published packet byte-identical (5 Nov optimisation)."""
    from core.waveform_ribbon_dynamics import row_gradient
    rng = np.random.default_rng(7)
    xs = np.cumsum(rng.uniform(.05, .3, (3, 40)), axis=1).astype(np.float32)
    xs[1] = np.arange(40, dtype=np.float32)*.25  # exactly uniform spacing: NumPy switches formula
    for f in (rng.normal(size=(3, 40)), rng.normal(size=(3, 40)).astype(np.float32)):
        out = row_gradient(f, xs)
        for row in range(3):
            expected = np.gradient(f[row], xs[row])
            assert out.dtype == expected.dtype and np.array_equal(out[row], expected)
