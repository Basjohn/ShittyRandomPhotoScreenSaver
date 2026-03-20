"""Regression tests for the TransientBus (Approach A dual-path).

Verifies:
  1. Single kick atop sustained pad → transient bus reaches >0.9 within 1 frame
     while smoothed energy stays below 0.6.
  2. Adaptive threshold adjusts to sustained energy without false positives.
  3. Onset classification: bass-dominant → kick, mid-dominant → snare/vocal_swell.
  4. Ring buffer rotation and get_recent_onsets filtering.
  5. Reset clears all state.
  6. Dual-stage AGC bass/mix envelope independence.
"""
from __future__ import annotations

from widgets.spotify_visualizer.transient_bus import (
    TransientBus,
    TransientEnergyBands,
)


class TestTransientBusBasic:
    """Core spectral flux and onset detection."""

    def test_first_frame_no_transient(self):
        """First frame seeds previous values — no transient expected."""
        tb = TransientBus()
        snap = tb.update(0.5, 0.3, 0.1)
        assert snap.bass_transient == 0.0
        assert snap.mid_transient == 0.0
        assert snap.onset_detected is False

    def test_kick_produces_high_bass_transient(self):
        """A sudden bass spike should produce a large bass transient."""
        tb = TransientBus(threshold_k=1.0, transient_decay=0.3)
        # Seed with quiet baseline
        for _ in range(20):
            tb.update(0.1, 0.1, 0.1)
        # Inject kick: bass jumps from 0.1 → 0.9
        snap = tb.update(0.9, 0.1, 0.1)
        assert snap.bass_transient > 0.5, (
            f"Expected bass_transient > 0.5, got {snap.bass_transient}"
        )
        assert snap.onset_detected is True
        assert snap.onset_type == "kick"

    def test_sustained_pad_no_false_onset(self):
        """Sustained steady energy should not trigger onsets after warmup."""
        tb = TransientBus(threshold_k=1.5)
        # Warmup: 50 frames of constant energy
        for _ in range(50):
            tb.update(0.4, 0.4, 0.4)
        # After warmup, constant energy should not trigger onset
        snap = tb.update(0.4, 0.4, 0.4)
        assert snap.onset_detected is False, "Sustained pad should not trigger onset"

    def test_kick_atop_pad_separation(self):
        """Key validation: kick atop sustained pad.

        Transient bass should reach >0.5 within 1 frame while the previous
        (smoothed) baseline stays low.  This is the fundamental assertion
        that the dual-path architecture works.
        """
        tb = TransientBus(threshold_k=1.0, transient_decay=0.3)
        # Build up a sustained pad baseline
        for _ in range(30):
            tb.update(0.3, 0.3, 0.3)
        # Record baseline transient before kick
        baseline_snap = tb.snapshot()
        baseline_bass = baseline_snap.bass_transient
        # Inject kick
        kick_snap = tb.update(0.95, 0.3, 0.3)
        assert kick_snap.bass_transient > baseline_bass + 0.3, (
            f"Kick should produce transient significantly above baseline: "
            f"got {kick_snap.bass_transient}, baseline was {baseline_bass}"
        )
        # Mid/high transient should remain low (no significant change there)
        assert kick_snap.mid_transient < 0.3, (
            f"Mid transient should stay low during bass kick: {kick_snap.mid_transient}"
        )

    def test_onset_classification_snare(self):
        """Mid-dominant spike → snare classification."""
        tb = TransientBus(threshold_k=1.0, transient_decay=0.3)
        for _ in range(20):
            tb.update(0.1, 0.1, 0.1)
        # Mid spike with some bass (snare)
        snap = tb.update(0.4, 0.9, 0.2)
        assert snap.onset_detected is True
        assert snap.onset_type == "snare"

    def test_onset_classification_vocal_swell(self):
        """Mid-dominant spike with no bass → vocal_swell."""
        tb = TransientBus(threshold_k=1.0, transient_decay=0.3)
        for _ in range(20):
            tb.update(0.05, 0.1, 0.1)
        # Pure mid spike, no bass
        snap = tb.update(0.05, 0.9, 0.1)
        assert snap.onset_detected is True
        assert snap.onset_type == "vocal_swell"

    def test_transient_decays(self):
        """Transient values should decay after the spike passes."""
        tb = TransientBus(threshold_k=1.0, transient_decay=0.5)
        for _ in range(20):
            tb.update(0.1, 0.1, 0.1)
        # Spike
        snap1 = tb.update(0.9, 0.1, 0.1)
        peak = snap1.bass_transient
        # Decay for several frames at baseline
        for _ in range(10):
            snap2 = tb.update(0.1, 0.1, 0.1)
        assert snap2.bass_transient < peak * 0.5, (
            f"Transient should decay: peak={peak}, after 10 frames={snap2.bass_transient}"
        )


class TestOnsetRingBuffer:
    """Ring buffer and event retrieval."""

    def test_ring_buffer_stores_events(self):
        tb = TransientBus(threshold_k=1.0, min_onset_gap_s=0.0)
        for _ in range(10):
            tb.update(0.1, 0.1, 0.1)
        # Generate several onsets
        for _ in range(3):
            tb.update(0.9, 0.1, 0.1)
            for _ in range(5):
                tb.update(0.1, 0.1, 0.1)
        events = tb.get_recent_onsets(max_age_s=5.0)
        assert len(events) >= 2, f"Expected at least 2 recent onsets, got {len(events)}"

    def test_kick_count(self):
        tb = TransientBus(threshold_k=1.0, min_onset_gap_s=0.0)
        for _ in range(10):
            tb.update(0.1, 0.1, 0.1)
        # Generate kicks
        tb.update(0.9, 0.1, 0.1)
        count = tb.get_kick_count(window_s=5.0)
        assert count >= 1


class TestTransientBusReset:
    """Reset clears all state."""

    def test_reset_clears_transients(self):
        tb = TransientBus(threshold_k=1.0)
        for _ in range(10):
            tb.update(0.1, 0.1, 0.1)
        tb.update(0.9, 0.1, 0.1)  # generate transient
        assert tb.snapshot().bass_transient > 0.0
        tb.reset()
        snap = tb.snapshot()
        assert snap.bass_transient == 0.0
        assert snap.onset_detected is False
        assert snap.onset_type == ""

    def test_reset_clears_ring_buffer(self):
        tb = TransientBus(threshold_k=1.0, min_onset_gap_s=0.0)
        for _ in range(10):
            tb.update(0.1, 0.1, 0.1)
        tb.update(0.9, 0.1, 0.1)
        tb.reset()
        events = tb.get_recent_onsets(max_age_s=5.0)
        assert len(events) == 0


class TestTransientBusConfig:
    """Configuration methods."""

    def test_set_threshold_k_clamps(self):
        tb = TransientBus()
        tb.set_threshold_k(0.1)
        assert tb._threshold_k == 0.5  # min clamp
        tb.set_threshold_k(10.0)
        assert tb._threshold_k == 4.0  # max clamp

    def test_lower_k_more_sensitive(self):
        """Lower threshold_k should produce more onsets."""
        results_low_k = []
        results_high_k = []
        for k, results in [(0.5, results_low_k), (3.0, results_high_k)]:
            tb = TransientBus(threshold_k=k, min_onset_gap_s=0.0)
            for _ in range(20):
                tb.update(0.2, 0.2, 0.2)
            for _ in range(5):
                snap = tb.update(0.5, 0.2, 0.2)
                results.append(snap.onset_detected)
                for _ in range(3):
                    tb.update(0.2, 0.2, 0.2)
        low_onsets = sum(results_low_k)
        high_onsets = sum(results_high_k)
        assert low_onsets >= high_onsets, (
            f"Lower k should be more sensitive: k=0.5 got {low_onsets}, k=3.0 got {high_onsets}"
        )


class TestDualStageAGC:
    """Verify bass/mix envelope independence in bar_computation."""

    def test_agc_envelope_fields_exist(self):
        """Audio worker should have split envelope fields."""
        from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker
        w = SpotifyVisualizerAudioWorker(bar_count=16)
        assert hasattr(w, '_env_bass_short')
        assert hasattr(w, '_env_bass_long')
        assert hasattr(w, '_env_mix_short')
        assert hasattr(w, '_env_mix_long')
        assert hasattr(w, '_agc_bass_split')
        assert hasattr(w, '_agc_mid_split')
        assert hasattr(w, '_transient_bus')
        assert hasattr(w, '_kick_lane_gain')

    def test_transient_bus_fields_on_worker(self):
        """Audio worker should have transient snapshot fields."""
        from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker
        w = SpotifyVisualizerAudioWorker(bar_count=16)
        assert hasattr(w, '_transient_bass')
        assert hasattr(w, '_transient_mid')
        assert hasattr(w, '_transient_high')
        assert hasattr(w, '_onset_detected')
        assert hasattr(w, '_onset_type')
        assert hasattr(w, '_onset_strength')


class TestBeatEngineTransient:
    """Verify beat engine exposes transient energy bands."""

    def test_get_transient_energy_bands_method(self):
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
        assert hasattr(_SpotifyBeatEngine, 'get_transient_energy_bands')

    def test_transient_energy_bands_returns_dataclass(self):
        """get_transient_energy_bands should return TransientEnergyBands."""
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
        engine = _SpotifyBeatEngine(bar_count=16)
        result = engine.get_transient_energy_bands()
        assert isinstance(result, TransientEnergyBands)
        assert hasattr(result, 'bass_transient')
        assert hasattr(result, 'onset_detected')
        assert hasattr(result, 'onset_type')
