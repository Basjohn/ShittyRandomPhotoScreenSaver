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
    assert len(snapshot.wakes) % 8 == 0
    return {int(snapshot.wakes[i + 4]): snapshot.wakes[i:i + 8]
            for i in range(0, len(snapshot.wakes), 8)}


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
        self.sim._bubbles[0].popping = 0.0
        self.tick()
        for _ in range(24):
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
        self.assertIn('wake_instances(state.wakes, tan, pose)', renderer)
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
