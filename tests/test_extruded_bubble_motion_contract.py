"""Dependency-free, executable Extruded Bubble motion/ownership gate.

This runs without Qt or graphics context; it is a *logical* test, not physical visual acceptance.
Run with Python directly (avoids Qt test fixtures). Presets remain entirely operator-owned.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # source import only, no environment-variable mutation
MODULE = ROOT / "widgets/spotify_visualizer/extruded_bubble_simulation.py"


def _simulation():
    name = "_standalone_extruded_bubble_simulation"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, MODULE)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module


class ExtrudedBubbleMotionContractTests(unittest.TestCase):
    def setUp(self):
        self.mod = _simulation()
        self.dt = 1 / 60

    def _run(self, sim, controls, *, playing, level, seconds, beats=False):
        frames = []
        for i in range(round(seconds / self.dt)):
            hits = (("kick", 1.0),) if beats and i % 30 == 0 else ()
            frames.append(sim.advance(self.mod.MusicInput(self.dt, playing, level, hits, (level,) * 3), controls))
        return frames

    def test_real_band_changes_have_multi_pixel_motion_at_saturated_presence(self):
        sim = self.mod.ExtrudedBubbleSimulation(72)
        controls = self.mod.ExtrudedBubbleControls(large_count=(14, 14), mid_count=(0, 0),
                                                  breathing=(0.05, 0.25), collision_scope="off")
        frames = [sim.advance(self.mod.MusicInput(self.dt, True, 1.0, (),
                         ((0.3 if i % 60 < 30 else 0.8), 0.4, 0.2)), controls) for i in range(600)]
        swells = []
        for f in frames[-180:]:
            records = [f.bubbles[i:i + 8] for i in range(0, len(f.bubbles), 8)]
            large = [r[5] for r in records if r[4] > 0.95]
            if large:
                swells.append(sum(large) / len(large))
        self.assertGreater(len(swells), 100)
        self.assertGreater((max(swells) - min(swells)) * 0.12 * 540, 4.0)
        self.assertGreater(max(swells), 0.2)

    def test_idle_phase_is_quiet_and_music_accelerates_water_and_beads(self):
        sim = self.mod.ExtrudedBubbleSimulation(73)
        controls = self.mod.ExtrudedBubbleControls(stream_speed=(0.0625, 0.2), idle=0.5,
                                                  collision_scope="off")
        def phase_rates(playing, level, seconds):
            frames = self._run(sim, controls, playing=playing, level=level, seconds=seconds)
            self.assertTrue(all(a.motion_phase <= b.motion_phase and a.travel <= b.travel
                                for a, b in zip(frames, frames[1:])))
            return (frames[-1].motion_phase - frames[-61].motion_phase,
                    5 / self.mod.WORLD_UNIT * (frames[-1].travel - frames[-61].travel))
        quiet_surface, quiet_beads = phase_rates(False, 0, 5)
        loud_surface, loud_beads = phase_rates(True, 1, 9)
        self.assertLess(quiet_surface, 0.35)
        self.assertLess(quiet_beads, 0.4)
        self.assertGreater(loud_surface, 4 * quiet_surface)
        self.assertGreater(loud_beads, 2.5 * quiet_beads)
        phase_rates(False, 0, 12)

    def test_normal_large_bubbles_really_reach_shared_focus_volume(self):
        from rendering.gl_programs import extruded_bubble_scene as scene
        _v, world_to_view, tan, _p = scene.camera(0.0, 0.0, 16 / 9)
        # Normal large bubble, not a separate near-field record, matches the renderer's depth predicate.
        row = scene.bubble_instances((0, 0, -3., 1., 1, 0, 1, -1))[0]
        far = scene.bubble_instances((0, 0, -20., 1., 1, 0, 2, -1))[0]
        import numpy as np
        view = np.asarray(world_to_view).reshape(3, 3)
        def circle(shell, focus):
            depth = -(shell[:3] @ view)[2]
            return 22.0 * max(focus - (depth - shell[3]), 0.0) / max(depth-shell[3],2.5)
        self.assertEqual(row[5], 0.0)
        self.assertGreater(circle(row, 4.0), 1.5)
        self.assertGreater(circle(row, 5.5), circle(row, 4.0))
        self.assertEqual(circle(far, 5.5), 0.0)

    def test_breath_has_no_radius_teleport_at_kick_admission(self):
        sim = self.mod.ExtrudedBubbleSimulation(74)
        controls = self.mod.ExtrudedBubbleControls(large_count=(6, 6), mid_count=(0, 0),
                                                  breathing=(0.05, 0.25), collision_scope="off")
        self._run(sim, controls, playing=True, level=0.5, seconds=3)
        before = sim.advance(self.mod.MusicInput(self.dt, True, 0.5, (), (0.5,) * 3), controls)
        after = sim.advance(self.mod.MusicInput(self.dt, True, 0.5, (("kick", 1),), (0.5,) * 3), controls)
        mapping = lambda snap: {snap.bubbles[i + 6]: snap.bubbles[i + 5]
                                for i in range(0, len(snap.bubbles), 8)}
        prev, curr = mapping(before), mapping(after)
        self.assertTrue(set(prev) & set(curr))
        # A kick is physically eased through the existing logical clock; no full pulse in one 16.7ms step.
        self.assertLess(max(abs(curr[k] - prev[k]) for k in prev.keys() & curr.keys()), 0.025)


if __name__ == "__main__":
    unittest.main()
