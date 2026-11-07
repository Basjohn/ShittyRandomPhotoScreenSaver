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


@pytest.fixture(autouse=True)
def _swell_mechanics_on_test_paths(monkeypatch):
    """These tests examine swell mechanics on short test paths near the centre: launch the swell inside them and keep
    the fixed end taper short (production births swells beyond the ~±30 view and tapers the slide over 20 units)."""
    import core.waveform_ribbon_dynamics as dyn
    monkeypatch.setattr(dyn, 'PULSE_ORIGIN', 3.5)
    monkeypatch.setattr(dyn, 'SURGE_TAPER', 2.)

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
    twin._bands = []
    twin._band_presence[:] = 0.
    twin._band_light[:] = 0.
    twin._whole = twin._whole_fresh = 0.
    for name in ('_drift', '_level', '_focus', '_geom'):
        setattr(twin, name, np.zeros(PULSE_GRID.size))
    twin._frozen_swell = None
    twin._frozen_gain_cells = twin._frozen_gain_shown = twin._frozen_surge = None   # Frozen Past's held swell and surge
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
    monkeypatch.setattr(model, '_frozen_surge', None)   # Frozen Past's surge is the displacement held on its cells
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


# Frozen Past (operator, 7 Nov night): "The pulse is a relatively small horizontal width and the full vertical width
# (except center out where it is 2x). each part stays frozen until the pulse reaches it, then it moves to match the
# current values low or high and freezes again when the pulse leaves."
LOUD = {'bands': (.9, .8, .7), 'intensity': .95, 'presence': 1.}
SOFT = {'bands': (.15, .12, .1), 'intensity': .2, 'presence': 1.}


def frozen(**pulse):
    """A Frozen Past model with the framed view production always supplies (a pulse leaves through its far edge and
    frees its place under Pulse Count)."""
    model = model_for('Frozen Past', **{'direction': 'Tail To Head', 'width': 3., 'speed': 6., 'fade': 4., **pulse})
    model.advance(0., bands=(0., 0., 0.), intensity=0., presence=0., view_span=(-16., 16.))
    return model


def cloth(snapshot):
    """Ribbon 0's knots as {cloth coordinate: (scene x, y)}: a knot's cloth coordinate never changes while it lives. The
    packet's knot x is relative to its world origin, which re-bases now and then, so the key adds the origin back."""
    path = data(snapshot)[0]
    count, start, capacity = int(path[0, 0]), int(path[1, 1]), int(path[1, 2])
    order = (start+np.arange(count)) % capacity
    u, y = path[4::5, 0][order].astype(np.float64), path[4::5, 1][order].astype(np.float64)
    u = u+snapshot.packet.world_origin[0]
    x = u+snapshot.head_x-snapshot.travel
    return {round(float(a), 3): (float(b), float(c)) for a, b, c in zip(u, x, y)}


@pytest.mark.parametrize('falloff', (.5, 2.))
def test_frozen_past_moves_only_where_a_band_is(falloff):
    model = frozen(falloff=falloff)
    # Half a band's window (its Pulse Width core, 3, and its Pulse Falloff at one side), a grid cell, and the reach of
    # the held surge (cloth a band slid shows the band's own body).
    radius = 1.5+falloff+dyn.PULSE_DX+1.
    still, guarded, moving, previous, bounds = [], [], [], None, None
    for index in range(round(10/(1/90))):
        music = LOUD if (index//45) % 2 else SOFT          # the music changes every half second
        snapshot = model.advance(1/90, hit=1. if index % 45 == 0 else 0., **music)
        now = cloth(snapshot)
        # _surge's fold guard scales a whole ribbon's surge when it would fold the cloth (SURGE_MAX_COMPRESSION). Frozen
        # Past limits the held surge locally, but with this strong Pulse Strength range the end taper still engages the
        # guard; a CHANGE of that scale moves a whole ribbon a little (none measurable on recorded music).
        now_bounds = {key: bound for key, (bound, _) in model._surge_bound.items()}
        guard = bounds is not None and (bounds.keys() != now_bounds.keys()
                                        or any(abs(now_bounds[key]-bounds[key]) > 1e-6 for key in bounds))
        bounds = now_bounds
        if previous is not None and index*(1/90) > 3.:
            centres = [band[0] for band in model._bands if band[3] >= dyn.BAND_PRESENT]
            for u, (x, y) in now.items():
                if u in previous and abs(x) < 12.:   # inside the test scene's ribbon, away from its history ends
                    change = abs(y-previous[u][1])
                    near = min((abs(x-c) for c in centres), default=99.)
                    if near < 1.:
                        moving.append(change)
                    elif near > radius:
                        (guarded if guard else still).append(change)
        previous = now
    assert len(still) > 200 and len(moving) > 50
    # Frozen: nothing outside a band moves (the held state lives on cloth-fixed cells, so it never melts) ...
    assert np.percentile(still, 99) < 1e-4 and max(still) < 2e-3, (np.percentile(still, 99), max(still))
    # ... while under a band it follows the music; even while the fold guard scales a ribbon's surge (this extreme
    # loud/soft toggle; no measurable effect on recorded music) the cloth outside the bands stays nearly still.
    everything = still+guarded
    assert np.percentile(everything, 99) < .15*np.percentile(moving, 90), (np.percentile(everything, 99),
                                                                             np.percentile(moving, 90))


def test_frozen_past_follows_the_current_values_low_or_high_and_holds_after():
    model = frozen(speed=8.)
    height = list(dyn.FROZEN_BODY).index('height')

    def held_here(cell_u):
        return float(np.interp(cell_u-model.travel, model._frozen_cells(), model._frozen_state[height]))

    def presence_here(cell_u):
        return float(np.interp(cell_u-model.travel, dyn.PULSE_GRID, model._band_presence))

    for index in range(round(3/(1/90))):                       # loud: bands pass and shape the cloth loud
        model.advance(1/90, hit=1. if index % 90 == 0 else 0., **LOUD)
    newest = min(model._bands, key=lambda band: band[4])
    # A cell just behind the newest band (bands travel toward +x, the cloth flows toward -x): the band covered it a
    # moment ago and no band reaches it again until the next onset.
    cell = newest[0]-3.+model.travel
    assert presence_here(cell) == 0.
    loud_held = held_here(cell)
    assert abs(loud_held-model.drive['height']) < .05          # it matched the current (high) values
    for _ in range(round(1.5/(1/90))):                         # soft, no onsets: no band, the cell holds
        model.advance(1/90, **SOFT)
    assert model.drive['height'] < loud_held-.2                # the live body really fell
    assert abs(held_here(cell)-loud_held) < .01                # but the cell stayed frozen at its loud values
    covered = []                                               # the live height while a band covers the cell
    for index in range(round(1.5/(1/90))):                     # soft onsets: bands pass and the cell follows LOW
        model.advance(1/90, hit=.3 if index % 90 == 0 else 0., **SOFT)
        if presence_here(cell) > .99:
            covered.append(model.drive['height'])
    assert len(covered) > 15 and presence_here(cell) == 0.     # a band crossed the cell and has left it again
    assert abs(held_here(cell)-covered[-1]) < .05              # it matched the values current when the band left
    assert held_here(cell) < loud_held-.2                      # low as well as high


def test_frozen_past_silence_launches_nothing_and_erases_nothing():
    model = frozen()
    for index in range(round(3/(1/90))):
        model.advance(1/90, hit=1. if index % 45 == 0 else 0., **LOUD)
    launched = len(model._bands)
    for _ in range(round(6/(1/90))):
        model.advance(1/90, **SILENT)
    assert len(model._bands) <= launched and not any(band[4] < 6. for band in model._bands)   # no new band in silence
    assert model._frozen_state is not None and np.ptp(model._frozen_state[0]) > 0.   # the held shape is still there


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
    assert not model._pulse.any() and not model._bands and model._whole == 0.
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
