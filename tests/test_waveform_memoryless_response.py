"""Waveform Ribbon's response is memoryless, and Frozen Past's held body enters and leaves cleanly (operator, 7 Nov 2026).

"Adaptivity is the enemy." "A soft start with vocals peaking should read the same as a chorus dropping to soft and
vocals peaking there if they match."

Test-owned controls and inputs with the production constants; structure only, never authored values. The response tests
fail on the former code: the body and its kicks were gated by the bus's presence ratio (loudness over its own 6 s
running level) and each geometry drive was widened about a learned 3 s phrase mean. What Frozen Past holds and where it
moves (only under a band) is owned by tests/test_waveform_reaction_modes.py.
"""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np

from core.waveform_ribbon_dynamics import PulseControls
from tests.test_waveform_ribbon_dynamics import controls, data, primed
from widgets.spotify_visualizer.waveform_ribbon_frame_runtime import WaveformRibbonFrameRuntime

DT = 1/90
DRIVES = ('height', 'width', 'bend', 'lift')


def music(level, swell=0.):
    """A passage at ``level`` (0..1 on the fixed scale); ``swell`` raises it toward a peak (vocals peaking)."""
    level = min(1., level+swell)
    return dict(bands=tuple(level*share for share in (1., .85, .7)), intensity=level, presence=1.)


def test_the_body_and_its_kicks_ignore_the_bus_presence_ratio():
    """The same music at the same loudness draws the same body whatever its ratio to the last few seconds: a quieter
    passage after a loud one is not gated until a running level catches up."""
    def run(presence):
        runtime = WaveformRibbonFrameRuntime()
        args = dict(onsets=(), playing=True, identity=(1, 2, 3), source_identity=(2, 3), controls=controls(),
                    body_bands=(.5, .4, .3), intensity=.6, loudness=6., presence=presence)
        out = []
        for index in range(400):
            if index % 45 == 0 and index >= 90:
                args['onsets'] = (SimpleNamespace(serial=index, kind='kick', strength=1., magnitude=1.5, loudness=6.,
                                                  presence=presence),)
            else:
                args['onsets'] = ()
            snapshot = runtime.advance(now_ts=index*DT, **args)
            out.append((snapshot.packet.payload, dict(snapshot.drives).get('height'), runtime._model._hit))
        return out
    steady, quieter_than_before = run(1.), run(.35)
    assert any(hit > 0. for _, _, hit in steady)
    assert all(a == b for a, b in zip(steady, quieter_than_before))


def drives_through(phases):
    """Run test-owned music through the dynamics: ``phases`` is a list of (seconds, level, swell); returns the drives of
    every tick of the LAST phase."""
    model = primed(replace(controls(), breathing=1.))
    rows = []
    for number, (seconds, level, swell) in enumerate(phases):
        for index in range(round(seconds/DT)):
            # The peak rises over its first second (vocals swelling), then holds.
            rise = min(1., index*DT) if swell else 0.
            model.advance(DT, **music(level, swell*rise))
            if number == len(phases)-1:
                rows.append([model.drive[key] for key in DRIVES])
    return np.asarray(rows)


def test_vocals_peaking_read_the_same_after_a_soft_intro_and_after_a_chorus_drops_to_soft():
    soft_intro = drives_through([(8., .3, 0.), (4., .3, .5)])
    chorus_then_soft = drives_through([(20., 1., 0.), (8., .3, 0.), (4., .3, .5)])
    gap = np.abs(soft_intro-chorus_then_soft).max(axis=0)
    assert (gap < .01).all(), dict(zip(DRIVES, gap.round(4)))
    # The peak is a real reaction, not a flat line that trivially matches.
    assert (soft_intro.max(axis=0)-soft_intro[0] > .1).all()


def test_a_loud_passage_does_not_shrink_as_it_goes_on():
    """After a soft passage, sudden loud music rises to its size and stays there: no overshoot that sinks back as a
    running mean catches up (a loud passage started big and shrank)."""
    loud = drives_through([(6., .25, 0.), (10., .9, 0.)])
    settled = loud[-90:].mean(axis=0)
    assert (loud.max(axis=0) <= settled+.005).all(), dict(zip(DRIVES, (loud.max(axis=0)-settled).round(4)))
    assert (settled-loud[0] > .2).all()   # and the rise itself is large


def frozen_model(mode='Frozen Past'):
    c = replace(controls(), rotation_enabled=False,
                pulse=PulseControls(direction='Tail To Head', width=6., speed=8., fade=4., colour=.6, saturation=.6,
                                    mode=mode))
    c = replace(c, ranges={**c.ranges, 'height': (.2, 1.6), 'width': (.3, 1.2), 'bend': (.2, 2.)})
    return primed(c)


def test_frozen_past_body_enters_and_leaves_without_a_pop():
    model = frozen_model('Travelling Pulse')
    steps, previous = [], None
    for index in range(round(10/DT)):
        if index == round(3/DT):
            model.controls = replace(model.controls, pulse=replace(model.controls.pulse, mode='Frozen Past'))
        if index == round(6/DT):   # leave while the held body differs from the live one (the music softened)
            model.controls = replace(model.controls, pulse=replace(model.controls.pulse, mode='Travelling Pulse'))
        level = .9 if index < round(4.5/DT) else .2
        snapshot = model.advance(DT, hit=1. if index % 45 == 0 and level > .5 else 0., **music(level))
        y = data(snapshot)[:, 4::5, 1].astype(np.float64)
        if previous is not None:
            steps.append(float(np.abs(y-previous).max()))
        previous = y
    steps = np.asarray(steps)
    typical = np.percentile(steps, 99)
    for at in (round(3/DT), round(6/DT)):
        assert steps[at-2:at+3].max() <= typical*1.05, (at, steps[at-2:at+3], typical)
    assert not model._frozen_body_on   # released once eased back to the live body
