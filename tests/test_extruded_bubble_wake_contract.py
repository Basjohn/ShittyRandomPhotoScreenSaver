"""Extruded Bubble stable wake emitters and rendering-contract checks (not visual acceptance).

No Qt, OpenGL context, environment-variable changes, alternate clocks or live settings mutations.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / 'widgets/spotify_visualizer/extruded_bubble_simulation.py'


def simulation_module():
    name = '_extruded_wake_contract_sim'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, SIM)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


def source_records(snapshot):
    from core.constants.extruded_bubble_world import WAKE_STRIDE
    assert len(snapshot.wakes) % WAKE_STRIDE == 0
    return {int(snapshot.wakes[i + 4]): snapshot.wakes[i:i + WAKE_STRIDE]
            for i in range(0, len(snapshot.wakes), WAKE_STRIDE)}


class WakeOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.mod = simulation_module()
        self.sim = self.mod.ExtrudedBubbleSimulation(711)
        self.controls = self.mod.ExtrudedBubbleControls(large_count=(3, 3), mid_count=(0, 0),
                                                       collision_scope='off')
        self.tick = lambda: self.sim.advance(self.mod.MusicInput(1 / 60, False), self.controls)

    def test_source_identity_survives_pop_and_retirement_is_monotone(self):
        first = source_records(self.tick())
        self.assertEqual(len(first), 3)
        victim = self.sim._bubbles[0]
        ident = victim.ident
        self.assertEqual(first[ident][5], -1.0)
        victim.popping = 0.0
        popped = source_records(self.tick())
        self.assertIn(ident, popped)
        self.assertEqual(popped[ident][5], 0.0)
        self.assertEqual(popped[ident][:5], first[ident][:5])
        self.assertTrue(popped[ident][6] > 0.0)
        ages = []
        for _ in range(62):
            entries = source_records(self.tick())
            self.assertIn(ident, entries)
            ages.append(entries[ident][5])
        self.assertEqual(ages, sorted(ages))
        self.assertGreater(ages[-1], 0.9)
        # Retiring trail is fully gone shortly after the directional fade completes.
        for _ in range(7):
            last = source_records(self.tick())
        self.assertNotIn(ident, last)

    def test_compaction_never_rebinds_retiring_wake_to_new_bubble(self):
        self.tick()
        ident = self.sim._bubbles[0].ident
        self.sim._bubbles[0].popping = self.mod._POP_SECONDS - 1/30
        self.tick()
        self.tick()
        # Other bubbles can continue to occupy compacted shell slots, but the wake keeps its own identity.
        self.assertIn(ident, source_records(self.tick()))
        self.assertNotIn(ident, [b.ident for b in self.sim._bubbles])

    def test_reset_discards_all_retiring_emitters(self):
        self.tick()
        self.sim._bubbles[0].popping = 0.0
        self.tick()
        self.assertTrue(self.sim._wake_retiring)
        self.sim.reset()
        self.assertEqual(self.sim._wake_retiring, {})
        self.assertEqual(self.sim._wake_live, {})

    def test_nominal_radius_is_preserved_separately_from_parent_reaction_and_retirement(self):
        from dataclasses import replace
        controls = replace(self.controls, breathing=(1.,.6))      # the deepest rest
        first = source_records(self.sim.advance(self.mod.MusicInput(1/60,False),controls))
        bases = {b.ident:b.radius for b in self.sim._bubbles}
        for ident,row in first.items():
            self.assertAlmostEqual(row[7],bases[ident])
            self.assertAlmostEqual(row[3]/row[7],self.mod._LARGE_REACTION[1])
        for _ in range(90):
            snap=self.sim.advance(self.mod.MusicInput(1/60,True,1.,(),(.8,.7,.6)),controls)
        live=source_records(snap)
        ident=next(iter(live)); self.sim._find(ident).popping=0.
        retired=source_records(self.sim.advance(self.mod.MusicInput(1/60,False),controls))[ident]
        self.assertEqual(retired[7],live[ident][7])
        self.assertEqual(retired[3],live[ident][3])

    def test_a_trail_is_the_water_its_bubble_passed_through(self):
        import numpy as np
        from widgets.spotify_visualizer.extruded_bubble_wake import WakePath
        path = WakePath(5, 0.5)
        here = np.array([0.0, 0.0, 0.0])
        for _ in range(120):                      # rising to the right ..
            here = here + (0.012, 0.0, 0.0)
            path.advance(tuple(here), 1 / 60, 0.0, 1.0)
        turn = here.copy()
        for _ in range(60):                       # .. then turned upward by the music
            here = here + (0.0, 0.012, 0.0)
            path.advance(tuple(here), 1 / 60, 0.0, 1.0)
        length, flat = path.resampled(tuple(here), 0.3)
        points = np.asarray(flat).reshape(-1, 3)
        self.assertGreater(length, 1.0)
        self.assertAlmostEqual(float(np.linalg.norm(points[0] - here)), 0.3, delta=0.05)    # just behind the bubble
        # Near the bubble the trail runs back down its new course; farther back it lies along the old one.
        self.assertLess(abs(points[1][0] - turn[0]), 0.1)
        self.assertLess(points[1][1], here[1])
        self.assertLess(points[-1][0], turn[0] - 0.3)
        self.assertLess(abs(points[-1][1] - turn[1]), 0.15)

    def test_a_trail_drifts_with_the_water_after_its_bubble_is_gone(self):
        import numpy as np
        from widgets.spotify_visualizer.extruded_bubble_wake import FLOW, WakePath
        path = WakePath(9, 0.5)
        for k in range(120):
            path.advance((0.0, 0.012 * k, 0.0), 1 / 60, 0.0, 1.0)
        for _ in range(90):                       # the drag of the bubble's passing dies away
            path.advance(None, 1 / 60, 0.0, 0.0)
        before = np.asarray(path.resampled(None, 0.0)[1]).reshape(-1, 3)
        path.advance(None, 1 / 60, 0.0, 0.0)
        after = np.asarray(path.resampled(None, 0.0)[1]).reshape(-1, 3)
        # Only the water's slow swirl (and what is left of the drag) moves it: no tail of its own.
        self.assertLess(float(np.abs(after - before).max()), 3.0 * FLOW / 60 + 1e-3)

    def test_wake_trails_choose_trailing_bubbles_and_zero_keeps_no_history(self):
        from dataclasses import replace
        from core.constants.extruded_bubble_world import WAKE_PATH
        rows = source_records(self.tick())
        self.assertTrue(all(row[8] == 0.0 for row in rows.values()))
        self.assertEqual(self.sim._wake_paths, {})
        controls = replace(self.controls, wake_trails=1.0)
        for _ in range(180):                      # music moves the bubbles: their trails grow behind them
            snap = self.sim.advance(self.mod.MusicInput(1 / 60, True, 1., (), (.8, .7, .6)), controls)
        rows = {ident: row for ident, row in source_records(snap).items() if row[5] < 0.0}
        self.assertTrue(rows and all(row[8] == 1.0 and row[9] > 0.0 for row in rows.values()))
        for ident, row in rows.items():
            bubble = self.sim._find(ident)
            first = row[WAKE_PATH:WAKE_PATH + 3]
            # The trail leaves the bubble's widest point: its path starts at the centre plane.
            self.assertAlmostEqual(sum((a - b) ** 2 for a, b in zip(first, (bubble.x, bubble.y, bubble.z))) ** 0.5,
                                   0.0, delta=1e-6)

    def test_no_wake_when_no_parent_population(self):
        self.controls = self.mod.ExtrudedBubbleControls(large_count=(0, 0), mid_count=(0, 0),
                                                        collision_scope='off')
        self.assertFalse(self.tick().wakes)

    def test_wake_gpu_contract_uses_separate_stable_buffer_and_directional_wipe(self):
        shader = (ROOT / 'rendering/gl_programs/extruded_bubble_program.py').read_text()
        renderer = (ROOT / 'rendering/quick/visualizer/implementations/extruded_bubble.py').read_text()
        self.assertIn('EbWakes { float ebWake[]; }', shader)
        self.assertNotIn('EbShells { float ebShell[]; }', shader)
        self.assertIn('retirement - 0.08, retirement + 0.12, tail', shader)
        self.assertIn('self._wakes.buffer', renderer)
        self.assertIn('wake_instances(state.wakes)', renderer)
        self.assertIn('self._wakes.release', renderer)

    def test_micro_glass_stays_lit_by_scene_without_radius_dependent_random_switch(self):
        shader = (ROOT / 'rendering/gl_programs/extruded_bubble_program.py').read_text()
        self.assertIn('textureLod(uProbe, uViewToWorld * reflect(ray, normalV)', shader)
        self.assertIn('texture(uBackground, gl_FragCoord.xy / uTargetSize)', shader)
        self.assertIn('if (vExtra.y > 2.5 && vExtra.y < 3.5)', shader)
        self.assertIn('fract(vExtra.x * 17.31)', shader)
        self.assertIn('aExtra = vec2(beadRandom(seed, 23u), 3.0)', shader)


if __name__ == '__main__':
    unittest.main()
