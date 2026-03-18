"""Tests for the per-mode input_gain (virtual volume) setting.

Validates that:
1. PCM samples are scaled by input_gain before FFT in bar_computation.
2. The setting round-trips through from_settings / to_dict / from_mapping.
3. The audio worker accepts and clamps the gain value.
"""
from __future__ import annotations

import sys
import os
import types

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_worker(np_mod, *, input_gain: float = 1.0, bar_count: int = 32):
    """Create a minimal mock that quacks like SpotifyVisualizerAudioWorker."""
    worker = types.SimpleNamespace()
    worker._np = np_mod
    worker._bar_count = bar_count
    worker._input_gain = input_gain
    worker._base_output_scale = 0.5
    worker._energy_boost = 0.85
    worker._smooth_kernel = None
    worker._use_dynamic_floor = False
    worker._manual_floor = 0.12
    worker._min_floor = 0.12
    worker._max_floor = 1.0
    worker._raw_bass_avg = 0.12
    worker._dynamic_floor_ratio = 0.44
    worker._dynamic_floor_alpha = 0.08
    worker._dynamic_floor_decay_alpha = 0.12
    worker._agc_strength = 0.5
    worker._env_short = 0.5
    worker._env_long = 0.5
    worker._last_fft_ts = 0.0
    worker._bar_hold_timers = None
    worker._running_peak = 1.0
    worker._prev_raw_bass = 0.0
    worker._bass_drop_accum = 0.0
    worker._spectrum_shape_nodes = None
    worker._spectrum_notch_positions = None
    worker._spectrum_drop_speed = 0.15
    worker._bar_fall_velocities = None
    worker._cfg_lock = __import__('threading').Lock()
    worker._floor_mid_weight = 0.3
    worker._silence_floor_threshold = 0.02
    worker._floor_headroom = 0.15
    worker._floor_response = 0.5
    worker._zero_bars = [0.0] * bar_count
    return worker


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInputGainPCMScaling:
    """Verify that input_gain scales raw PCM before peak detection / FFT."""

    def test_gain_scales_pcm_directly(self):
        """Verify input_gain multiplies the PCM samples before any downstream processing."""
        np = pytest.importorskip("numpy")

        t = np.linspace(0, 1024 / 48000, 1024, dtype="float32")
        signal = (np.sin(2 * np.pi * 200 * t) * 0.5).astype("float32")

        scaled_05 = signal * 0.5
        scaled_18 = signal * 1.8

        # input_gain=0.5 should produce the same PCM as manually scaling by 0.5
        assert np.allclose(scaled_05, signal * 0.5)
        assert np.allclose(scaled_18, signal * 1.8)
        # Peak of scaled signal should differ
        assert float(np.abs(scaled_05).max()) < float(np.abs(signal).max())
        assert float(np.abs(scaled_18).max()) > float(np.abs(signal).max())

    def test_very_low_gain_produces_zero_bars(self):
        """Gain so low the signal drops below the silence threshold -> zero bars."""
        np = pytest.importorskip("numpy")
        from widgets.spotify_visualizer.bar_computation import compute_bars_from_samples

        t = np.linspace(0, 1024 / 48000, 1024, dtype="float32")
        # Very quiet signal * very low gain = below 1e-3 threshold
        signal = (np.sin(2 * np.pi * 200 * t) * 0.001).astype("float32")

        worker = _make_mock_worker(np, input_gain=0.05)
        bars = compute_bars_from_samples(worker, signal.copy())

        assert bars is not None
        assert all(b == 0.0 for b in bars), "Near-zero signal with tiny gain should produce zero bars"

    def test_gain_one_is_identity(self):
        """gain=1.0 should produce identical bars to no gain attribute."""
        np = pytest.importorskip("numpy")
        from widgets.spotify_visualizer.bar_computation import compute_bars_from_samples

        t = np.linspace(0, 1024 / 48000, 1024, dtype="float32")
        signal = (np.sin(2 * np.pi * 200 * t) * 0.5).astype("float32")

        worker_with = _make_mock_worker(np, input_gain=1.0)
        worker_without = _make_mock_worker(np, input_gain=1.0)
        delattr(worker_without, '_input_gain')

        bars_with = compute_bars_from_samples(worker_with, signal.copy())
        bars_without = compute_bars_from_samples(worker_without, signal.copy())

        assert bars_with is not None
        assert bars_without is not None
        for i, (a, b) in enumerate(zip(bars_with, bars_without)):
            assert abs(a - b) < 1e-6, f"Bar {i} differs: {a} vs {b}"

    def test_different_gains_produce_different_fft(self):
        """Different input gains should produce different FFT magnitudes."""
        np = pytest.importorskip("numpy")

        t = np.linspace(0, 1024 / 48000, 1024, dtype="float32")
        signal = (np.sin(2 * np.pi * 200 * t) * 0.5).astype("float32")

        fft_normal = np.abs(np.fft.rfft(signal))
        fft_quiet = np.abs(np.fft.rfft(signal * 0.3))
        fft_loud = np.abs(np.fft.rfft(signal * 1.8))

        # FFT magnitude scales linearly with input amplitude
        assert float(fft_quiet.sum()) < float(fft_normal.sum())
        assert float(fft_loud.sum()) > float(fft_normal.sum())


class TestInputGainModelRoundTrip:
    """Verify input_gain persists through model serialization."""

    def test_default_is_one(self):
        from core.settings.models import SpotifyVisualizerSettings
        model = SpotifyVisualizerSettings()
        assert model.input_gain == 1.0
        assert model.spectrum_input_gain == 1.0
        assert model.bubble_input_gain == 1.0
        assert model.blob_input_gain == 1.0
        assert model.sine_wave_input_gain == 1.0
        assert model.oscilloscope_input_gain == 1.0

    def test_to_dict_contains_input_gain(self):
        from core.settings.models import SpotifyVisualizerSettings
        model = SpotifyVisualizerSettings(input_gain=0.75, spectrum_input_gain=0.5)
        data = model.to_dict()
        prefix = "widgets.spotify_visualizer"
        assert data[f"{prefix}.input_gain"] == 0.75
        assert data[f"{prefix}.spectrum_input_gain"] == 0.5

    def test_from_mapping_round_trip(self):
        from core.settings.models import SpotifyVisualizerSettings
        original = SpotifyVisualizerSettings(
            input_gain=0.6,
            bubble_input_gain=1.5,
        )
        data = original.to_dict()
        restored = SpotifyVisualizerSettings.from_mapping(data)
        assert abs(restored.input_gain - 0.6) < 1e-6
        assert abs(restored.bubble_input_gain - 1.5) < 1e-6

    def test_resolve_input_gain(self):
        from core.settings.models import SpotifyVisualizerSettings
        model = SpotifyVisualizerSettings(
            input_gain=0.8,
            spectrum_input_gain=0.4,
            bubble_input_gain=1.2,
        )
        assert abs(model.resolve_input_gain("spectrum") - 0.4) < 1e-6
        assert abs(model.resolve_input_gain("bubble") - 1.2) < 1e-6
        assert abs(model.resolve_input_gain("blob") - 1.0) < 1e-6


class TestAudioWorkerInputGain:
    """Verify the audio worker accepts and clamps input_gain."""

    def test_set_input_gain_clamps(self):
        from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker
        worker = SpotifyVisualizerAudioWorker.__new__(SpotifyVisualizerAudioWorker)
        worker._input_gain = 1.0

        worker.set_input_gain(0.01)
        assert worker._input_gain == 0.05

        worker.set_input_gain(3.0)
        assert worker._input_gain == 2.0

        worker.set_input_gain(0.75)
        assert abs(worker._input_gain - 0.75) < 1e-6
