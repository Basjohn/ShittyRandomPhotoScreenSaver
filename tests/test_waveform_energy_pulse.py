"""Travelling energy pulse: music launches swells that travel along the waveform and swell its OWN shape.

Test-owned controls only (never presets). The field is logical state on the sole clock; projection samples it.
"""
from dataclasses import replace
import numpy as np
from core.waveform_ribbon_dynamics import PULSE_GRID, PULSE_ORIGIN, PulseControls
from tests.test_waveform_ribbon_dynamics import controls, primed, data


def pulsed(**pulse):
    return primed(replace(controls(), rotation_enabled=False, pulse=PulseControls(**pulse)))


def beat(model, seconds_after, **inputs):
    inputs = {'bands': (.3, .3, .3), 'intensity': .5, 'presence': 1., **inputs}
    model.advance(1/90, hit=1., **inputs)
    for _ in range(round(seconds_after*90)):
        model.advance(1/90, **inputs)
    return model


def peak(field):
    return float(PULSE_GRID[int(np.argmax(field))])


def test_a_beat_travels_in_the_authored_direction_at_the_authored_speed():
    model = beat(pulsed(direction='Head To Tail', speed=6., width=3.), .5)
    first = peak(model._pulse[0])
    # The hit is released over a ~0.1 s rise, so the crest trails the ideal launch by about half a unit.
    assert abs(first-(PULSE_ORIGIN-6.*.5)) < 1. and model._pulse[1].max() == 0.
    for _ in range(45):
        model.advance(1/90, bands=(.3, .3, .3), intensity=.5, presence=1.)
    assert abs((first-peak(model._pulse[0]))-3.) < .4
    back = beat(pulsed(direction='Tail To Head', speed=6.), .5)
    assert peak(back._pulse[1]) > -PULSE_ORIGIN and back._pulse[0].max() == 0.


def test_centre_out_sends_two_swells_and_width_is_honoured():
    model = beat(pulsed(direction='Centre Out', speed=5., width=2.), .4)
    assert peak(model._pulse[0]) < -1. and peak(model._pulse[1]) > 1.
    def half_width(width):
        field = beat(pulsed(direction='Centre Out', speed=0., width=width), .12)._pulse[0]
        return float((field > .5*field.max()).sum()*(PULSE_GRID[1]-PULSE_GRID[0]))
    assert half_width(6.) > 2.*half_width(2.)


def test_the_swell_amplifies_the_waveform_with_its_shape_never_against_it():
    still = pulsed(direction='Centre Out', speed=0., width=8., fade=20.)
    moved = pulsed(direction='Centre Out', speed=0., width=8., fade=20.)
    quiet = {'bands': (.3, .3, .3), 'intensity': .5, 'presence': 1.}
    moved.advance(1/90, hit=1., **quiet)
    still.advance(1/90, **quiet)
    for _ in range(40):
        a, b = moved.advance(1/90, **quiet), still.advance(1/90, **quiet)
    ya, yb = data(a)[0, 4::5, 1], data(b)[0, 4::5, 1]
    count = int(data(a)[0, 0, 0])
    lift = dict(b.realized)['lift']
    da, db = (ya[:count]-lift), (yb[:count]-lift)
    moved_part = np.abs(da-db) > 1e-3
    assert moved_part.any()
    # Crests rise, troughs deepen: the swell scales displacement about the axis, so its sign never flips.
    assert (np.sign(da[moved_part]) == np.sign(db[moved_part])).all()
    assert (np.abs(da[moved_part]) >= np.abs(db[moved_part])-1e-6).all()


def test_silence_injects_nothing_and_travelling_energy_fades_without_vanishing():
    model = pulsed(fade=1.)
    for _ in range(180):
        model.advance(1/90, bands=(0., 0., 0.), intensity=0., presence=0.)
    assert model._pulse.max() == 0.
    beat(model, .2)
    level = model._pulse.max()
    model.advance(1/90, bands=(0., 0., 0.), intensity=0., presence=0.)
    assert .97*level < model._pulse.max() < level*1.05
    for _ in range(450):
        model.advance(1/90, bands=(0., 0., 0.), intensity=0., presence=0.)
    assert model._pulse.max() < .02*level
