"""Reaction over whole passages in continuous play (operator, 5 Nov, Preset 7 on Rag Doll): "no decay or breathing in
soft passages", "sustained passages that have changes inside them reading as almost flat", and "the ribbon swelled up
to full power when the song went QUIETER". Test-owned controls and inputs with the PRODUCTION constants (swells born
beyond the view); structure only, never authored values.

Negative controls: Breathing 0 is exactly the former normalisation (it re-lifts the quieter passage here), and every
Group Wave test below fails on `waveform-baseline-2026-11-05`, whose set envelope was built from the long-fade field
(evidence: .artifacts/evidence/waveform_ribbon/reactivity_preset7/)."""
from dataclasses import replace
import numpy as np
import core.waveform_ribbon_dynamics as dyn
from core.waveform_ribbon_dynamics import PulseControls
from tests.test_waveform_ribbon_dynamics import controls, primed
from tests.test_waveform_no_twitch import accelerations

DT = 1/90
VIEW = np.abs(dyn.PULSE_GRID) <= 14.  # the part of the history the production framing shows (aperture x lens)


def loud_then_quieter(breathing, quieter=.7):
    """25 s of loud phrases, then 55 s of the same phrases at ``quieter`` of the level; (time, height, bend) per tick."""
    model = primed(replace(controls(), breathing=breathing))
    rows = []
    for index in range(round(80/DT)):
        t = index*DT
        level = 1. if t < 25. else quieter
        swell = 1. if t % 3. < 1. else 0.
        bands = tuple(level*(.6+.4*swell)*share for share in (1., .85, .7))
        snapshot = model.advance(DT, bands=bands, intensity=level*(.7+.3*swell), presence=1.,
                                 hit=.5*level if t % .5 < DT else 0.)
        drives = dict(snapshot.drives)
        rows.append((t, drives['height'], drives['bend']))
    return np.asarray(rows)


def reach(rows, start, end):
    window = rows[(rows[:, 0] >= start) & (rows[:, 0] < end)]
    return window[:, 1:].max(axis=0)


def test_a_quieter_passage_after_a_loud_one_never_rises_to_loud_reach():
    for breathing, held in ((1., True), (0., False)):
        rows = loud_then_quieter(breathing)
        loud, late = reach(rows, 15., 25.), reach(rows, 70., 80.)
        # Late in a long quieter passage (45-55 s in) the body stays clearly below the loud passage's reach. Breathing 0
        # is the former 30 s memory: it re-normalised the quieter passage up to loud reach (the reproduced symptom).
        assert (late <= .9*loud).all() == held, (breathing, late, loud)


def group_wave(**pulse):
    pulse = {'direction': 'Head To Tail', 'width': 3.5, 'speed': 16., 'fade': 3., 'mode': 'Group Wave', **pulse}
    return primed(replace(controls(), rotation_enabled=False, pulse=PulseControls(**pulse)))


def in_view(model):
    """The geometric swell over the visible history (the gain above 1 the flow rule admits, before Pulse Strength)."""
    return model._geom_share[0]*model._geom[VIEW]


def test_group_wave_never_pins_the_whole_view_in_a_sustained_beating_passage():
    model, spread = group_wave(), []
    for index in range(round(20/DT)):
        model.advance(DT, bands=(.7, .6, .5), intensity=.8, presence=1., hit=.6 if index % 45 == 0 else 0.)
        if index*DT >= 6.:
            swell = in_view(model)
            spread.append(np.median(swell)/swell.max())
    # Sets travel through calmer cloth: the baseline's long-fade pile sat at the soft bound across the view (.98).
    assert np.median(spread) < .75, np.median(spread)


def test_group_wave_shows_the_changes_inside_a_sustained_passage():
    """Same passage level throughout; every 4 s the beat alternates between strong and light hits."""
    model, frames = group_wave(), []
    for index in range(round(24/DT)):
        t = index*DT
        strong = int(t//4) % 2 == 0
        hit = (.8 if strong else .2) if index % 45 == 0 else 0.
        model.advance(DT, bands=(.7, .6, .5), intensity=.8, presence=1., hit=hit)
        frames.append((t, strong, in_view(model).max()))
    frames = np.asarray(frames)
    phrases = [(frames[(frames[:, 0] >= a+1.5) & (frames[:, 0] < a+4.), 2].mean(), a//4 % 2 == 0) for a in range(8, 24, 4)]
    strong = np.mean([m for m, s in phrases if s]); light = np.mean([m for m, s in phrases if not s])
    assert strong >= 1.3*light, (strong, light)


def test_group_wave_breathes_in_a_soft_passage():
    """Soft phrases: beats for one second, then two seconds of rest. The set must let go between phrases."""
    model, frames = group_wave(), []
    for index in range(round(21/DT)):
        t = index*DT
        beating = t % 3. < 1.
        bands = (.35, .3, .25) if beating else (.2, .17, .14)
        model.advance(DT, bands=bands, intensity=.4, presence=1., hit=.35 if beating and index % 30 == 0 else 0.)
        frames.append((t, in_view(model).max()))
    frames = np.asarray(frames)
    for start in (9., 12., 15., 18.):
        phrase = frames[(frames[:, 0] >= start) & (frames[:, 0] < start+3.), 1]
        assert phrase.min() <= .5*phrase.max(), (start, phrase.min(), phrase.max())


def test_group_wave_beats_never_snap_the_body():
    """tests/test_waveform_no_twitch.py's probe on Group Wave. Its stronger along-curve surge moves the cloth more than
    Travelling Pulse's (bounds there .02/.01); the long-fade sets measured .027 vertical and .023 sideways per tick^2,
    the fresh sets .021/.014 (an order below the .155/.114 of the pre-5 Nov snaps)."""
    model = primed(replace(controls(), breathing=1., pulse=PulseControls(speed=12., fade=2.5, mode='Group Wave')))
    acc = accelerations(model)
    assert acc[..., 1].max() < .025, acc[..., 1].max()
    assert acc[..., 0].max() < .02, acc[..., 0].max()
