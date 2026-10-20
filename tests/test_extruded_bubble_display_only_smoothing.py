"""Qt-free candidate gate: smoothing may change only the stable-ID displayed radius.

Run on Windows: py -3.14 tests/test_extruded_bubble_display_only_smoothing.py
No native renderer or recorded-audio acceptance is implied by passing.
"""
from __future__ import annotations

from dataclasses import replace
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.visualizer_replay.extruded_bubble_startup_probe import simulation_module


def test_display_only_smoothing():
    mod = simulation_module()
    raw = mod.ExtrudedBubbleSimulation(1005)
    soft = mod.ExtrudedBubbleSimulation(1005)
    controls = mod.ExtrudedBubbleControls(
        large_count=(5, 5), mid_count=(8, 8), smoothing=0.0,
        stream_speed=(0.02, 0.20), drift=(0.1, 0.8),
        collision_scope='all', breathing=(0.1, 0.6), small_pulse=(0.1, 0.8),
    )
    differing = False
    for tick in range(390):
        bands = ((0.08, 0.12, 0.06) if tick < 90 else
                 (0.78, 0.55, 0.35) if tick < 180 else
                 (0.25, 0.2, 0.12) if tick < 280 else (0.68, 0.7, 0.5))
        music = mod.MusicInput(1 / 90, True, 1, (), bands)
        a = raw.advance(music, controls)
        b = soft.advance(music, replace(controls, smoothing=1.0))
        # Music, movement, ray/light and emission OWNED data must remain identical.
        for key in ('level', 'flash', 'stream_speed', 'drift', 'emission', 'sustain',
                    'travel', 'rays', 'shimmer', 'motion_phase'):
            assert math.isclose(getattr(a, key), getattr(b, key), rel_tol=0, abs_tol=1e-10), (tick, key)
        assert a.stream == b.stream
        assert len(raw._bubbles) == len(soft._bubbles)
        assert raw._clusters.keys() == soft._clusters.keys()
        assert raw._contacts == soft._contacts
        for x, y in zip(raw._bubbles, soft._bubbles):
            assert x.ident == y.ident and x.large == y.large
            for key in ('x', 'y', 'z', 'radius', 'current_radius', 'alpha', 'cluster', 'leaving', 'popping'):
                v, w = getattr(x, key), getattr(y, key)
                assert math.isclose(v, w, rel_tol=0, abs_tol=1e-9) if isinstance(v, float) else v == w, (tick, x.ident, key)
            if abs(x.visual_radius-y.visual_radius)>0.005:
                differing = True
    assert differing, 'Smoothing needs to visibly affect the displayed radius rather than becoming inert'


if __name__ == '__main__':
    test_display_only_smoothing()
    print('DISPLAY_ONLY_SMOOTHING_CANDIDATE: PASS; visual acceptance still outstanding')
