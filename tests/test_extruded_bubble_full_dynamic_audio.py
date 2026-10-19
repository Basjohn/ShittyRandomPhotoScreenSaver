"""New negative-control gate: scalar saturation cannot manufacture musical breathing.

These CPU tests are NOT operator or offscreen-pixel visual acceptance. No Qt dependency.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'widgets/spotify_visualizer/extruded_bubble_simulation.py'
SCENE = ROOT / 'rendering/gl_programs/extruded_bubble_scene.py'
CAPTURE = ROOT / 'widgets/spotify_visualizer/logical_frame_capture.py'


def sim_module():
    key = '_eb_full_dynamic_simulation_fixture'
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, MODULE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


class FullDynamicAudioOwnership(unittest.TestCase):
    def setUp(self):
        self.mod = sim_module()
        self.controls = self.mod.ExtrudedBubbleControls(
            large_count=(8, 8), mid_count=(16, 16), collision_scope='off',
            breathing=(0.05, 0.35), small_pulse=(0.03, 0.2), emission=(0.1, 0.9))
        self.sim = self.mod.ExtrudedBubbleSimulation(21)

    def step(self, bass, mid, high, *, scalar=1.0, beats=()):
        return self.sim.advance(self.mod.MusicInput(1/60, True, scalar, beats, (bass, mid, high)), self.controls)

    def lanes(self, snap):
        records = [snap.bubbles[i:i + 8] for i in range(0, len(snap.bubbles), 8)]
        # Stable numeric classifications for these authored fixed-radius test settings.
        big = [r[5] for r in records if r[3] >= 0.075]
        small = [r[5] for r in records if r[3] < 0.075]
        return (sum(big)/len(big) if big else 0, sum(small)/len(small) if small else 0)

    def test_saturated_scalar_does_not_create_permanent_sine_breathing(self):
        values = [self.lanes(self.step(0, 0, 0)) for _ in range(420)]
        self.assertLess(max(v[0] for v in values[-120:]), 0.002)
        self.assertLess(max(v[1] for v in values[-120:]), 0.002)

    def test_bass_and_vocal_changes_drive_different_bubble_sizes_with_constant_scalar(self):
        for _ in range(240):
            base = self.step(0, 0, 0)
        bass_peak = [self.lanes(self.step(0.95, 0.08, 0.08)) for _ in range(18)]
        self.assertGreater(bass_peak[-1][0], self.lanes(base)[0] + 0.09)
        for _ in range(260):
            self.step(0.1, 0.1, 0.1)
        vocal_peak = [self.lanes(self.step(0.15, 0.95, 0.7)) for _ in range(18)]
        self.assertGreater(vocal_peak[-1][1], 0.045)
        self.assertGreater(vocal_peak[-1][1], vocal_peak[-1][0] * 0.35)

    def test_emission_rays_and_stream_follow_bands_not_saturated_scalar(self):
        for _ in range(210):
            quiet = self.step(0, 0, 0)
        for _ in range(210):
            loud = self.step(0.92, 0.88, 0.83)
        self.assertGreater(loud.level, quiet.level + 0.65)
        self.assertGreater(loud.emission, quiet.emission + 0.3)
        self.assertGreater(loud.rays, quiet.rays + 0.25)
        self.assertGreater(loud.stream_speed, quiet.stream_speed * 1.9)

    def test_breathing_and_mid_pulse_remain_owned_by_their_own_ranges(self):
        mod = self.mod
        muted = mod.ExtrudedBubbleControls(
            large_count=(8, 8), mid_count=(16, 16), collision_scope='off',
            breathing=(0.0, 0.0), small_pulse=(0.0, 0.0))
        sim = mod.ExtrudedBubbleSimulation(21)
        for _ in range(180):
            snap = sim.advance(mod.MusicInput(1/60, True, 1.0, (), (0.95, 0.85, 0.75)), muted)
        self.assertTrue(all(abs(snap.bubbles[i + 5]) < 1e-8
                            for i in range(0, len(snap.bubbles), 8)))

    def test_music_stops_clear_both_body_envelopes_even_if_scalar_is_saturated(self):
        for _ in range(90):
            self.step(0.9, 0.8, 0.7)
        mod = self.mod
        for _ in range(320):
            snap = self.sim.advance(mod.MusicInput(1/60, False, 1.0, (), (1.0, 1.0, 1.0)), self.controls)
        self.assertLess(max((snap.bubbles[i + 5] for i in range(0, len(snap.bubbles), 8)), default=0.0), 0.002)

    def test_capture_uses_existing_bubble_feed_not_a_new_floor_or_clock(self):
        text = CAPTURE.read_text()
        start = text.index('def _capture_extruded_bubble(')
        end = text.index('\ndef _capture_spectrum_family(', start)
        excerpt = text[start:end]
        self.assertIn('get_bubble_energy_bands', excerpt)
        self.assertIn('body_bands=body_bands', excerpt)
        self.assertNotIn('dynamic_floor', excerpt)

    def test_particle_range_is_consumed_only_by_simulation_not_by_renderer(self):
        source = SCENE.read_text()
        start = source.index('def speck_amount(')
        end = source.index('\ndef ray_strength(', start)
        self.assertNotIn('low, high', source[start:end])
        self.assertIn('float(emission)', source[start:end])
        self.assertIn('_lerp(controls.emission, level)', MODULE.read_text())


if __name__ == '__main__':
    unittest.main()
