"""Qt-free logical gates for unaccepted EB count saturation / occupancy candidate.

Run: py -3.14 tests/test_extruded_bubble_population_candidate.py
Not a recorded-music or native visual acceptance gate.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.visualizer_replay.eb_simulation_support import simulation_module


USUAL = .65  # PassageIntensity.USUAL: an ordinary passage on the fixed real-music scale


def _steady(bands: tuple[float,float,float], seconds: float = 6.0, passage: float = USUAL):
    mod = simulation_module()
    sim = mod.ExtrudedBubbleSimulation(430)
    controls = mod.ExtrudedBubbleControls(
        large_count=(6,14), mid_count=(20,48),
        stream_speed=(0,0), drift=(0,0), sway=0, collision_scope='off')
    for _ in range(round(seconds*90)):
        sim.advance(mod.MusicInput(1/90, True, passage, (), bands), controls)
    return sim


def test_count_peak_requires_more_than_one_normalized_band():
    # The passage places occupancy; inside one usual passage the bands still order it.
    full = _steady((1,1,1))
    bass = _steady((1,0.1,0.05))
    mid = _steady((0.05,1,0.1))
    half = _steady((0.5,0.5,0.5))
    assert 0 < mid._population_drive < bass._population_drive < full._population_drive
    assert half._population_drive < full._population_drive
    assert all(len(sim._bubbles) <= 62 for sim in (full,bass,mid,half))
    # No max occupancy on solitary bass in an ordinary passage, unlike the original max(bass,vocals) mapping.
    assert bass._population_drive < .8
    # Only a loud passage with full bands reaches the loud handle; a quiet one stays near the quiet handle.
    assert _steady((1,1,1), passage=1.)._population_drive == 1
    assert _steady((1,1,1), passage=.15)._population_drive < .1


def test_population_fast_attack_slow_decay_without_hard_gate():
    mod = simulation_module()
    sim = mod.ExtrudedBubbleSimulation(471)
    controls = mod.ExtrudedBubbleControls(large_count=(6,14), mid_count=(20,48), collision_scope='off')
    d = []
    for i in range(360):
        quiet = i<90 or i>=210
        bands = (0.12,0.11,0.07) if quiet else (0.78,0.68,0.5)
        sim.advance(mod.MusicInput(1/90,True,.1 if quiet else 1.,(),bands),controls)
        d.append(sim._population_drive)
    assert max(d[:90]) < .04
    assert d[135] > d[91] and d[205] > d[135]
    assert d[210] > d[275] > d[359]  # release stays connected, no binary drop
    assert d[250] > .06
    assert max(abs(b-a) for a,b in zip(d[1:],d[2:])) < .045


if __name__ == '__main__':
    test_count_peak_requires_more_than_one_normalized_band()
    test_population_fast_attack_slow_decay_without_hard_gate()
    print('POPULATION_CURVE_CANDIDATE: PASS; recorded audio/native acceptance outstanding')
