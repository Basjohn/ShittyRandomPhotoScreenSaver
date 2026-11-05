"""Continuous play (operator, 5 Nov): "make sure we are as reactive in the middle of a song as we are at the start ...
especially bad 30 s into a song on a sustained passage". Test-owned controls; structure only, never authored values.

The force a routine kick earns is guarded at the frame runtime (tests/test_waveform_ribbon_dynamics.py,
test_a_steady_beat_keeps_its_force_and_a_bigger_hit_still_lands_bigger, which fails on the former running-mean
contrast). Here the body itself: the visible swell ONE extra kick adds (with minus without, same everything else)
40 s into a sustained, beating passage stays that of the same kick 3 s in."""
from dataclasses import replace
import numpy as np
import core.waveform_ribbon_dynamics as dyn
from core.waveform_ribbon_dynamics import PulseControls
from tests.test_waveform_ribbon_dynamics import controls, primed

DT = 1/45
VIEW = np.abs(dyn.PULSE_GRID) <= 30.


def visible_swell(model):
    return model._geom_share[0]*.7*model._value('bend')*model._geom[VIEW]*model._value('height')


def sustained(extra=None, until=None):
    """2 s of silence, then a sustained passage with a beat every 0.5 s; an extra identical kick at tick ``extra``."""
    model = primed(replace(controls(), pulse=PulseControls(speed=12., fade=2.5)))
    frames = []
    for index in range(until):
        on = index >= 2/DT
        beat = (index-round(2/DT)) % round(.5/DT)
        bands = ((.75, .55, .4) if beat < 2 else (.55, .45, .35)) if on else (0., 0., 0.)
        hit = .3 if on and (beat == 0 or index == extra) else 0.
        model.advance(DT, bands=bands, intensity=.7 if on else 0., presence=1. if on else 0., hit=hit)
        frames.append(visible_swell(model))
    return np.asarray(frames)


def kick_response(seconds_in, base):
    """Largest visible difference one extra kick (half-way between two beats) makes over the next 2.5 s."""
    tick = round((2.+seconds_in)/DT)+round(.25/DT)
    end = tick+round(2.5/DT)
    with_kick = sustained(extra=tick, until=end)
    return float(np.abs(with_kick[tick:end]-base[tick:end]).max())


def test_a_kick_deep_in_a_sustained_passage_moves_the_body_like_one_near_its_start():
    base = sustained(until=round(45/DT))
    early, deep = kick_response(3., base), kick_response(40., base)
    assert early > .05, early
    assert deep >= .85*early, (deep, early)
