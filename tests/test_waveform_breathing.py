"""Breathing (operator, 5 Nov): "on soft passages quite a few of the presets look sustained instead of feeling their big
changes with breathing". A soft passage whose phrases swell and fall must swell AND let go within each phrase, while a
loud passage keeps its reach. Test-owned controls and inputs; structure only, never authored values. The negative
control is Breathing 0, which is exactly the former behaviour (release = Decay on both stages at every level)."""
from dataclasses import replace
import numpy as np
from tests.test_waveform_ribbon_dynamics import controls, primed

DT = 1/90


def phrases(breathing, level, seconds=24., period=3.):
    """A passage at ``level`` whose phrases rise for a second and fall for two; returns (height, bend) per tick."""
    model = primed(replace(controls(), breathing=breathing))
    drives = []
    for index in range(round(seconds/DT)):
        t = index*DT
        swell = 1. if t % period < 1. else 0.
        bands = tuple(level*(.55+.45*swell)*share for share in (1., .85, .7))
        snapshot = model.advance(DT, bands=bands, intensity=level*(.6+.4*swell), presence=1.)
        d = dict(snapshot.drives)
        drives.append((d['height'], d['bend']))
    return np.asarray(drives)[round(9/DT):]  # after the gain memory and followers have settled


def contrast(series, period=3.):
    window = round(period/DT)
    return float(np.median([np.ptp(series[i:i+window], axis=0) for i in range(0, len(series)-window, window//2)], axis=0).min())


def test_a_soft_passage_swells_and_releases_within_its_phrases():
    """Breathing is a faster release in soft passages (its former widening about a learned 3 s mean was removed 7 Nov:
    memoryless). The body already lets go within the authored Decay, so 3 s phrases release fully either way; Breathing
    shows the short dips (half-second gaps between phrases) that Decay alone fills in."""
    held, breathing = contrast(phrases(0., .35, period=1.5), 1.5), contrast(phrases(1., .35, period=1.5), 1.5)
    assert breathing >= 1.3*held, (breathing, held)


def test_breathing_keeps_a_loud_passage_reach():
    held, breathing = phrases(0., .9), phrases(1., .9)
    assert breathing.max(axis=0).min() >= .95*held.max(axis=0).min()
