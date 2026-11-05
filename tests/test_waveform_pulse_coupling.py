"""Travelling pulse coupling: saturation, swell-carried particles and restrained strands near the swell.

Test-owned controls only (never presets or defaults). Structure is asserted, never authored values.
"""
import colorsys
import math
from dataclasses import replace
import numpy as np
import pytest
from core.ribbon_bursts import CAPACITY, MAX_BURST, RibbonBursts
from core.ribbon_strand_cohorts import ROOTS_PER_ACCENT, RibbonStrandCohorts
from core.waveform_ribbon_dynamics import PulseControls
from tests.test_ribbon_bursts import controls_with, waved
from tests.test_ribbon_strand_cohorts import controls as strand_controls, packet as strand_packet, snapshot as strand_snapshot
from tests.test_waveform_energy_pulse import beat, pulsed
from tests.test_waveform_ribbon_dynamics import controls, primed, data


@pytest.fixture(autouse=True)
def _swell_mechanics_on_test_paths(monkeypatch):
    """These tests examine swell mechanics on short test paths near the centre: launch the swell inside them and keep
    the fixed end taper short (production births swells beyond the ~±30 view and tapers the slide over 20 units)."""
    import core.waveform_ribbon_dynamics as dyn
    monkeypatch.setattr(dyn, 'PULSE_ORIGIN', 3.5)
    monkeypatch.setattr(dyn, 'SURGE_TAPER', 2.)

QUIET = {'bands': (.3, .3, .3), 'intensity': .5, 'presence': 1.}


def swell_at(centre, width=3.):
    return lambda x: np.exp(-.5*((np.asarray(x, np.float64)-centre)/width)**2)


# --- saturation -------------------------------------------------------------------------------------------------

def tint(model, ribbon=0):
    model._snapshot = None
    return data(model.snapshot())[ribbon, 8::5]


def swelled(**pulse):
    model = pulsed(direction='Centre Out', speed=0., width=8., fade=20., **pulse)
    beat(model, .4)
    return model


def test_a_swell_raises_saturation_where_it_is_without_whitening_or_shifting_hue():
    plain, vivid = swelled(colour=0., saturation=0.), swelled(colour=0., saturation=1.)
    a, b = tint(plain), tint(vivid)
    swell = vivid.pulse_at(np.zeros(1))[0]
    assert swell > .3
    hsv_a = np.array([colorsys.rgb_to_hsv(*row[:3]) for row in a])
    hsv_b = np.array([colorsys.rgb_to_hsv(*row[:3]) for row in b])
    raised = hsv_b[:, 1] > hsv_a[:, 1]+1e-3
    assert raised.any() and (b[:, 3] >= a[:, 3]-1e-6).all()
    # Value (brightness) and hue keep their own logic: the swell deepens colour, it never whitens it.
    np.testing.assert_allclose(hsv_b[raised, 2], hsv_a[raised, 2], atol=1e-4)
    hue = np.abs((hsv_b[raised, 0]-hsv_a[raised, 0]+.5) % 1.-.5)
    assert hue.max() < 1e-3
    assert (hsv_b[:, 1] <= 1.+1e-6).all()


def test_saturation_control_at_zero_leaves_the_pulse_colour_exactly_as_before():
    a, b = tint(swelled(colour=.6)), tint(swelled(colour=.6, saturation=0.))
    np.testing.assert_array_equal(a, b)


# --- particles: burst admission -----------------------------------------------------------------------------------

def test_pulse_births_are_placed_on_the_swell_and_share_the_cohort_cap():
    field = RibbonBursts()
    count = field.admit(waved(), controls_with(spark_count=(0., 0.)), 0., swell=swell_at(6.), density=1., extra=40)
    assert count == 40 and field.consumed == 40
    born = field.records[field.records[:, 7] > 0]
    assert abs(np.median(born[:, 0])-6.) < 2. and (np.abs(born[:, 0]-6.) < 7.).mean() > .9
    # Accent and pulse births together never exceed the per-event cap or the shared gap.
    field = RibbonBursts()
    assert field.admit(waved(), controls_with(spark_count=(64., 64.)), 1., swell=swell_at(6.), density=1.,
                       extra=MAX_BURST) == MAX_BURST
    assert field.admit(waved(.1), controls_with(spark_count=(64., 64.)), 1., swell=swell_at(6.), extra=8) == 0
    assert field.consumed == 0


def test_pulse_births_fill_headroom_and_never_mask_the_spark_count():
    def far_from_swell(spark_count):
        field = RibbonBursts()
        count = field.admit(waved(), controls_with(spark_count=(spark_count, spark_count)), 1., swell=swell_at(6.),
                            density=0., extra=MAX_BURST)
        assert count == MAX_BURST and field.consumed == MAX_BURST
        born = field.records[field.records[:, 7] > 0]
        return int((np.abs(born[:, 0]-6.) > 9.).sum())
    # Every authored accent survives a full pulse offer, so Spark Count still changes what is born away from it.
    assert far_from_swell(48.) > far_from_swell(4.)+8


def test_pulse_births_without_a_visible_swell_are_consumed_not_banked():
    field = RibbonBursts()
    assert field.admit(waved(), controls_with(), 0., swell=lambda x: np.zeros_like(x), density=1., extra=20) == 0
    assert field.consumed == 20 and field.serial == 0 and field.payload == b''


def test_accent_births_lean_toward_the_swell_with_the_density_control():
    def near(density):
        field = RibbonBursts()
        field.admit(waved(), controls_with(spark_count=(64., 64.)), 1., swell=swell_at(-6.), density=density)
        born = field.records[field.records[:, 7] > 0]
        return (np.abs(born[:, 0]+6.) < 3.).mean()
    assert near(2.) > near(0.)+.1


# --- particles: dynamics coupling ---------------------------------------------------------------------------------

def sparked(particles):
    return primed(replace(controls(), rotation_enabled=False, accents=controls_with(),
                          pulse=PulseControls(speed=4., width=6., fade=4., particles=particles)))


def population(model):
    b = model._bursts
    if b is None:
        return 0
    age = model.time-b.origin-b.records[:, 3]
    return int(((b.records[:, 7] > 0) & (age >= 0) & (age < b.records[:, 7])).sum())


def test_a_swell_carries_extra_bounded_births_and_silence_carries_none():
    def run(particles, silent=False):
        model = sparked(particles)
        inputs = {'bands': (0., 0., 0.), 'intensity': 0., 'presence': 0.} if silent else QUIET
        # The beat's accent is withheld so only the swell can add births.
        model.advance(1/90, hit=1., accent=0., **inputs)
        for _ in range(120):
            model.advance(1/90, accent=0., **inputs)
            assert 0. <= model._pulse_births <= MAX_BURST and model._pulse_credit <= 4.*MAX_BURST
        return model
    assert population(run(0.)) == 0
    carried = run(1.)
    assert population(carried) > 0 and carried._bursts.records[:, 7].astype(bool).sum() <= CAPACITY
    assert population(run(1., silent=True)) == 0


def test_swell_births_are_deterministic():
    def records():
        model = sparked(1.)
        model.advance(1/90, hit=1., accent=0., **QUIET)
        for _ in range(90):
            model.advance(1/90, accent=0., **QUIET)
        return model._bursts.records.copy()
    np.testing.assert_array_equal(records(), records())


def test_pulse_controls_reject_out_of_range_coupling():
    for bad in ({'saturation': 1.5}, {'particles': -.1}, {'strands': 2.}, {'particles': math.nan}):
        with pytest.raises(ValueError):
            PulseControls(**bad)


# --- strands ------------------------------------------------------------------------------------------------------

def strand_run(swell=None, gather=0., serial_events=1):
    p = strand_packet()
    cohorts = RibbonStrandCohorts(1)
    for event in range(serial_events):
        cohorts.update(strand_snapshot(p, 1.+event), strand_controls(), 1., history=p, knot_hz=6., swell=swell, gather=gather)
    timing = cohorts.records[0, :, 0]
    x = np.frombuffer(p.payload, np.float32).reshape(1, -1, 4)[0, 4:].reshape(-1, 5, 4)[:, 0, 0]+p.world_origin[0]
    return cohorts, timing[:, 0] > 0., x


def test_strands_lean_toward_the_swell_but_never_grow_in_number():
    base, active, x = strand_run()
    leaned, leaned_active, _ = strand_run(swell_at(4., 2.), gather=1.)
    assert 0 < leaned_active.sum() <= active.sum() <= ROOTS_PER_ACCENT
    assert np.abs(x[leaned_active]-4.).mean() < np.abs(x[active]-4.).mean()
    # Chance and glow rise only modestly and life/fade are untouched (approved tip-first retirement).
    chance = base.records[0, active, 0, 0].max()
    assert leaned.records[0, leaned_active, 0, 0].max() <= min(1., 1.5*chance)+1e-6
    assert leaned.records[0, leaned_active, 2, 3].max() <= 1.5*base.records[0, active, 2, 3].max()+1e-6
    np.testing.assert_array_equal(np.unique(leaned.records[0, leaned_active, 3, :2], axis=0),
                                  np.unique(base.records[0, active, 3, :2], axis=0))


def test_strand_gather_at_zero_is_exactly_the_unswelled_admission():
    a, _, _ = strand_run(serial_events=3)
    b, _, _ = strand_run(swell_at(4., 2.), gather=0., serial_events=3)
    np.testing.assert_array_equal(a.records, b.records)
