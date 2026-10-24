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
        kinds = {b.ident: b.large for b in self.sim._bubbles}
        big = [r[5] for r in records if kinds[int(r[6])]]
        small = [r[5] for r in records if not kinds[int(r[6])]]
        return (sum(big)/len(big) if big else 0, sum(small)/len(small) if small else 0)

    def test_saturated_scalar_does_not_create_permanent_sine_breathing(self):
        values = [self.lanes(self.step(0, 0, 0)) for _ in range(420)]
        for lane, rest_swell in ((0, -.29), (1, -.0435)):
            tail = [v[lane] for v in values[-120:]]
            # These authored quiet strengths are .05/.03, not the .15 reference.
            # The high handle cannot determine their contracted resting size.
            self.assertAlmostEqual(max(tail), rest_swell, places=8)
            self.assertLess(max(tail) - min(tail), 1e-8)

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

    def test_capture_uses_eb_fixed_scale_feed_not_a_floor_or_clock(self):
        text = CAPTURE.read_text()
        start = text.index('def _capture_extruded_bubble(')
        end = text.index('\ndef _capture_spectrum_family(', start)
        excerpt = text[start:end]
        self.assertIn('get_extruded_bubble_body_bands', excerpt)
        self.assertNotIn('get_bubble_energy_bands()', excerpt)
        self.assertIn('body_bands=body_bands', excerpt)
        self.assertNotIn('dynamic_floor', excerpt)

    def test_eb_body_feed_ignores_floor_state_and_keeps_headroom(self):
        from types import SimpleNamespace
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

        def bands(raw, **floor):
            state = dict(_use_dynamic_floor=False, _raw_bass_avg=0.12, _manual_floor=0.12)
            state.update(floor)
            worker = SimpleNamespace(_last_raw_bass=raw[0], _last_raw_mid=raw[1], _last_raw_treble=raw[2], **state)
            engine = SimpleNamespace(
                _audio_worker=worker, _get_play_ramp_factor=lambda: 1.0,
                **{name: getattr(_SpotifyBeatEngine, name) for name in (
                    'EXTRUDED_BUBBLE_BODY_RAW_REFERENCE', 'EXTRUDED_BUBBLE_BODY_REFERENCE_FFT',
                    'EXTRUDED_BUBBLE_BODY_BLOCK_EXPONENT')})
            result = _SpotifyBeatEngine.get_extruded_bubble_body_bands(engine)
            return (result.bass, result.mid, result.high)

        typical = (3.0, 1.6, 0.45)  # about the median of real playing music at EB's authored gain
        reference = bands(typical)
        for floor in ({'_use_dynamic_floor': True}, {'_raw_bass_avg': 2.5}, {'_manual_floor': 0.4}):
            self.assertEqual(bands(typical, **floor), reference, floor)
        # Typical music sits mid-range, not pinned at a ceiling, and louder raw input still moves it.
        self.assertTrue(all(0.25 < value < 0.8 for value in reference), reference)
        louder = bands(tuple(value * 1.4 for value in typical))
        self.assertTrue(all(b > a for a, b in zip(reference, louder)), (reference, louder))

    def test_eb_body_feed_reads_the_same_music_alike_at_256_and_512_sample_blocks(self):
        import numpy as np
        from types import SimpleNamespace
        from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker
        from widgets.spotify_visualizer.bar_computation import fft_to_bars
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

        # Test-owned signal: a pulsing bass tone, two mid/high tones and some noise.
        rate = 48000
        t = np.arange(rate * 2) / rate
        signal = (0.5 * np.sin(2 * np.pi * 55 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 2 * t))
                  + 0.2 * np.sin(2 * np.pi * 440 * t) + 0.15 * np.sin(2 * np.pi * 1320 * t)
                  + 0.05 * np.random.default_rng(7).standard_normal(t.size)).astype('float32')

        def median_bands(block, *, normalise=True):
            worker = SpotifyVisualizerAudioWorker(32)
            worker._np = np
            worker.set_notch_positions([[0.0, 'Bass'], [0.3, 'Mid'], [0.65, 'Treble'], [1.0, 'End']])
            engine = SimpleNamespace(_audio_worker=worker, _get_play_ramp_factor=lambda: 1.0, **{
                name: getattr(_SpotifyBeatEngine, name) for name in (
                    'EXTRUDED_BUBBLE_BODY_RAW_REFERENCE', 'EXTRUDED_BUBBLE_BODY_REFERENCE_FFT',
                    'EXTRUDED_BUBBLE_BODY_BLOCK_EXPONENT')})
            rows = []
            for start in range(0, signal.size - block, 2048):
                fft_to_bars(worker, np.abs(np.fft.rfft(signal[start:start + block])))
                if not normalise:
                    worker._last_raw_fft_bins = 0  # negative control: lanes read as if at the reference block
                result = _SpotifyBeatEngine.get_extruded_bubble_body_bands(engine)
                rows.append((result.bass, result.mid, result.high))
            return np.median(np.array(rows), axis=0)

        reference = median_bands(256)
        normalised = median_bands(512)
        raw = median_bands(512, normalise=False)
        self.assertTrue(np.all(np.abs(normalised - reference) < 0.08), (reference, normalised))
        # Without the block normalisation the longer block lifts mid/high toward their ceilings.
        self.assertTrue(np.all(raw[1:] - reference[1:] > 0.12), (reference, raw))

    def test_particle_range_is_consumed_only_by_simulation_not_by_renderer(self):
        source = SCENE.read_text()
        start = source.index('def speck_amount(')
        end = source.index('\ndef ray_strength(', start)
        self.assertNotIn('low, high', source[start:end])
        self.assertIn('float(emission)', source[start:end])
        self.assertEqual(MODULE.read_text().count('_lerp(controls.emission,'),1)


if __name__ == '__main__':
    unittest.main()
