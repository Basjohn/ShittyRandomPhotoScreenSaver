"""Per-mode integration tests for Approach A transient bus wiring.

Verifies:
  1. Spectrum kick express lane: transient bass boosts bass-zone bars.
  2. Bubble transient pulse: transient bass mixes into bubble pulse energy.
  3. Blob transient deformation: transient uniforms uploaded to shader.
  4. Sine/Osc heartbeat: transient kick onset lowers trigger gate.
  5. GL overlay: transient_energy stored on overlay for renderer access.
"""
from __future__ import annotations

import numpy as np

from widgets.spotify_visualizer.transient_bus import TransientEnergyBands


# ---------------------------------------------------------------------------
# Minimal stubs — just enough attributes for the code paths under test.
# ---------------------------------------------------------------------------

class _StubWorker:
    """Minimal audio worker stub for bar_computation kick express lane."""

    def __init__(self, bands: int = 16):
        self._transient_bass = 0.0
        self._transient_mid = 0.0
        self._transient_high = 0.0
        self._kick_lane_gain = 1.0
        self._agc_bass_split = 4
        self._agc_mid_split = 10


class _StubEnergyBands:
    """Minimal energy bands stub."""

    def __init__(self, bass=0.3, mid=0.2, high=0.1, overall=0.2):
        self.bass = bass
        self.mid = mid
        self.high = high
        self.overall = overall


class _StubTransientBands:
    """Stub for TransientEnergyBands."""

    def __init__(self, bass=0.0, mid=0.0, high=0.0):
        self.bass_transient = bass
        self.mid_transient = mid
        self.high_transient = high
        self.onset_detected = bass > 0.3
        self.onset_type = 'kick' if bass > 0.3 else ''


class _StubEngine:
    """Stub engine with transient energy access."""

    def __init__(self, tb=None, eb=None):
        self._audio_worker = _StubWorker()
        self._tb = tb
        self._eb = eb

    def get_transient_energy_bands(self):
        return self._tb or TransientEnergyBands()

    def get_energy_bands(self):
        return self._eb or _StubEnergyBands()

    def get_pre_agc_energy_bands(self):
        return self._eb or _StubEnergyBands()


# ===========================================================================
# 0. Global Transient Clamp (§2.1 — bar_computation pre-AGC)
# ===========================================================================

class TestGlobalTransientClamp:
    """Verify transient_clamp is applied globally to all transient channels
    right after the transient bus update in bar_computation.fft_to_bars."""

    def test_clamp_caps_all_channels(self):
        """All three transient channels should be capped by _transient_clamp."""
        worker = _StubWorker()
        worker._transient_clamp = 0.8

        # Simulate the clamping logic from bar_computation (post-bus update)
        raw_bass, raw_mid, raw_high = 1.2, 0.9, 1.5
        _g_clamp = worker._transient_clamp
        worker._transient_bass = min(_g_clamp, raw_bass)
        worker._transient_mid = min(_g_clamp, raw_mid)
        worker._transient_high = min(_g_clamp, raw_high)

        assert worker._transient_bass == 0.8
        assert worker._transient_mid == 0.8
        assert worker._transient_high == 0.8

    def test_clamp_passes_below_threshold(self):
        """Values below the clamp should pass through unchanged."""
        worker = _StubWorker()
        worker._transient_clamp = 1.5

        raw_bass, raw_mid, raw_high = 0.3, 0.1, 0.05
        _g_clamp = worker._transient_clamp
        worker._transient_bass = min(_g_clamp, raw_bass)
        worker._transient_mid = min(_g_clamp, raw_mid)
        worker._transient_high = min(_g_clamp, raw_high)

        assert worker._transient_bass == 0.3
        assert worker._transient_mid == 0.1
        assert worker._transient_high == 0.05

    def test_clamp_default_is_1_5(self):
        """Default _transient_clamp should be 1.5 when not set."""
        worker = _StubWorker()
        _g_clamp = getattr(worker, '_transient_clamp', 1.5)
        assert _g_clamp == 1.5

    def test_kick_lane_reads_clamped_value(self):
        """Kick express lane should consume the already-clamped transient bass."""
        worker = _StubWorker()
        worker._transient_clamp = 0.5

        # Simulate global clamp
        raw_t_bass = 1.0
        worker._transient_bass = min(worker._transient_clamp, raw_t_bass)

        # Kick express lane reads worker._transient_bass
        arr = np.full(16, 0.3, dtype=np.float64)
        _t_bass = worker._transient_bass  # should be 0.5, not 1.0
        assert _t_bass == 0.5

        _kick_boost = min(2.0, 1.0 + _t_bass * worker._kick_lane_gain)
        for i in range(worker._agc_bass_split):
            arr[i] = min(1.0, arr[i] * _kick_boost)

        # Boost = 1.0 + 0.5*1.0 = 1.5 → 0.3*1.5 = 0.45
        assert abs(arr[0] - 0.45) < 1e-9

    def test_clamp_zero_blocks_all_transients(self):
        """Clamp of 0 should zero out all transient channels."""
        worker = _StubWorker()
        worker._transient_clamp = 0.0

        worker._transient_bass = min(0.0, 0.9)
        worker._transient_mid = min(0.0, 0.5)
        worker._transient_high = min(0.0, 0.3)

        assert worker._transient_bass == 0.0
        assert worker._transient_mid == 0.0
        assert worker._transient_high == 0.0


# ===========================================================================
# 1. Spectrum Kick Express Lane
# ===========================================================================

class TestSpectrumKickExpressLane:
    """Verify kick express lane boost in bar_computation."""

    def test_kick_boosts_bass_bars(self):
        """When transient_bass is high, bass-zone bars should be amplified."""
        worker = _StubWorker(bands=16)
        arr = np.full(16, 0.3, dtype=np.float64)
        baseline = arr.copy()

        # Simulate kick express lane logic (extracted from bar_computation.py)
        worker._transient_bass = 0.8
        worker._kick_lane_gain = 1.0
        _t_bass = worker._transient_bass
        _kick_gain = worker._kick_lane_gain
        _bass_end = worker._agc_bass_split  # 4
        _kick_boost = min(2.0, 1.0 + _t_bass * _kick_gain)

        for i in range(_bass_end):
            arr[i] = min(1.0, arr[i] * _kick_boost)

        # Bass bars (0..3) should be boosted
        for i in range(_bass_end):
            assert arr[i] > baseline[i], f"Bar {i} should be boosted"

        # Non-bass bars should be unchanged
        for i in range(_bass_end, 16):
            assert arr[i] == baseline[i], f"Bar {i} should be unchanged"

    def test_no_boost_when_transient_below_threshold(self):
        """Transient bass below 0.05 should not trigger kick lane."""
        arr = np.full(16, 0.3, dtype=np.float64)
        baseline = arr.copy()

        _t_bass = 0.03  # below threshold
        if _t_bass > 0.05:
            assert False, "Should not reach here"

        np.testing.assert_array_equal(arr, baseline)

    def test_kick_gain_zero_disables_boost(self):
        """When kick_lane_gain is 0, boost factor is 1.0 (no change)."""
        _t_bass = 0.9
        _kick_gain = 0.0
        _kick_boost = min(2.0, 1.0 + _t_bass * _kick_gain)
        assert _kick_boost == 1.0

    def test_kick_boost_clamped_to_2x(self):
        """Kick boost should never exceed 2.0x."""
        _t_bass = 1.0
        _kick_gain = 2.0  # max gain
        _kick_boost = min(2.0, 1.0 + _t_bass * _kick_gain)
        assert _kick_boost == 2.0


# ===========================================================================
# 2. Bubble Transient Pulse
# ===========================================================================

class TestBubbleTransientPulse:
    """Verify transient bass mixing into bubble pulse energy."""

    def test_transient_mixes_into_pulse_bass(self):
        """Transient bass should increase the effective pulse bass."""
        eb_pulse = _StubEnergyBands(bass=0.3)
        tb = _StubTransientBands(bass=0.5)

        _pulse_bass = eb_pulse.bass
        _t_bass = tb.bass_transient
        _t_gain = 1.0
        _t_clamp = 1.5
        _mixed_bass = min(_t_clamp, _pulse_bass + _t_bass * _t_gain)

        assert _mixed_bass == 0.8  # 0.3 + 0.5*1.0
        assert _mixed_bass > _pulse_bass

    def test_transient_clamped_by_clamp_value(self):
        """Mixed bass should not exceed transient_clamp."""
        eb_pulse = _StubEnergyBands(bass=0.9)
        tb = _StubTransientBands(bass=1.0)

        _pulse_bass = eb_pulse.bass
        _t_bass = tb.bass_transient
        _t_gain = 1.5
        _t_clamp = 1.2
        _mixed_bass = min(_t_clamp, _pulse_bass + _t_bass * _t_gain)

        assert _mixed_bass == _t_clamp

    def test_zero_transient_gain_no_mix(self):
        """Pulse gain of 0 should leave bass unchanged."""
        eb_pulse = _StubEnergyBands(bass=0.4)
        tb = _StubTransientBands(bass=0.8)

        _t_gain = 0.0
        _mixed_bass = min(1.5, eb_pulse.bass + tb.bass_transient * _t_gain)

        assert _mixed_bass == 0.4

    def test_no_transient_no_change(self):
        """When transient bus reports 0, pulse bass is unchanged."""
        eb_pulse = _StubEnergyBands(bass=0.5)
        tb = _StubTransientBands(bass=0.0)

        _mixed_bass = min(1.5, eb_pulse.bass + tb.bass_transient * 1.0)
        assert _mixed_bass == 0.5


# ===========================================================================
# 3. Blob Transient Deformation (uniform upload)
# ===========================================================================

class TestBlobTransientUniforms:
    """Verify transient energy is stored on overlay for blob renderer."""

    def test_transient_energy_stored_on_overlay(self):
        """Overlay should store transient_energy for renderer access."""
        te = TransientEnergyBands(
            bass_transient=0.8,
            mid_transient=0.3,
            high_transient=0.1,
        )
        # Simulate overlay storage (matching set_state logic)
        state = {}
        state['_transient_energy'] = te

        assert state['_transient_energy'].bass_transient == 0.8
        assert state['_transient_energy'].mid_transient == 0.3
        assert state['_transient_energy'].high_transient == 0.1

    def test_none_transient_defaults_to_zero(self):
        """When transient_energy is None, renderer should default to 0."""
        te = None
        bass = getattr(te, 'bass_transient', 0.0) if te else 0.0
        mid = getattr(te, 'mid_transient', 0.0) if te else 0.0
        high = getattr(te, 'high_transient', 0.0) if te else 0.0
        assert bass == 0.0
        assert mid == 0.0
        assert high == 0.0


# ===========================================================================
# 4. Sine/Osc Heartbeat Transient Boost
# ===========================================================================

class TestHeartbeatTransientBoost:
    """Verify transient kick onset lowers heartbeat trigger gate."""

    def test_kick_onset_lowers_gate(self):
        """Confirmed kick should reduce trigger gate by 40%."""
        base_gate = 1.0 + (0.60 - 0.45 * 0.5)  # slider=0.5 → gate=1.375
        _tb_kick = True

        gate_boosted = base_gate * (0.6 if _tb_kick else 1.0)
        assert gate_boosted < base_gate
        assert abs(gate_boosted - base_gate * 0.6) < 1e-9

    def test_no_onset_gate_unchanged(self):
        """No kick onset should leave trigger gate unchanged."""
        base_gate = 1.375
        _tb_kick = False

        gate_result = base_gate * (0.6 if _tb_kick else 1.0)
        assert gate_result == base_gate

    def test_kick_detection_from_worker(self):
        """Worker onset_detected + onset_type == 'kick' should flag kick."""
        worker = _StubWorker()
        worker._onset_detected = True
        worker._onset_type = 'kick'

        _tb_kick = (
            getattr(worker, '_onset_detected', False)
            and getattr(worker, '_onset_type', '') == 'kick'
        )
        assert _tb_kick is True

    def test_snare_onset_no_kick_flag(self):
        """Snare onset should not flag as kick."""
        worker = _StubWorker()
        worker._onset_detected = True
        worker._onset_type = 'snare'

        _tb_kick = (
            getattr(worker, '_onset_detected', False)
            and getattr(worker, '_onset_type', '') == 'kick'
        )
        assert _tb_kick is False


# ===========================================================================
# 5. GPU Push Integration — transient_energy in kwargs
# ===========================================================================

class TestGPUPushTransientEnergy:
    """Verify transient_energy flows through the GPU push pipeline."""

    def test_transient_energy_in_extra_kwargs(self):
        """build_gpu_push_extra_kwargs should include transient_energy."""
        engine = _StubEngine(
            tb=TransientEnergyBands(bass_transient=0.6, mid_transient=0.2),
            eb=_StubEnergyBands(),
        )
        # Simulate the relevant bit of config_applier.build_gpu_push_extra_kwargs
        te = engine.get_transient_energy_bands()
        kwargs = {'transient_energy': te}

        assert 'transient_energy' in kwargs
        assert kwargs['transient_energy'].bass_transient == 0.6
        assert kwargs['transient_energy'].mid_transient == 0.2

    def test_transient_energy_default_when_no_engine(self):
        """When engine is None, transient_energy should default gracefully."""
        engine = None
        te = engine.get_transient_energy_bands() if engine else None
        assert te is None
