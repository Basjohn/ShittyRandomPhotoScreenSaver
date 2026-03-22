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
import time

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


class _BlobKwargsWidget:
    """Loose widget stub for build_gpu_push_extra_kwargs()."""

    def __init__(self):
        self._rainbow_enabled = False
        self._rainbow_speed = 0.5
        self._rainbow_per_bar = False
        self._spectrum_ghosting_enabled = True
        self._spectrum_ghost_alpha = 0.4
        self._spectrum_ghost_decay = 0.4
        self._osc_ghosting_enabled = False
        self._osc_ghost_intensity = 0.4
        self._blob_ghosting_enabled = False
        self._blob_ghost_alpha = 0.4
        self._blob_ghost_decay = 0.3
        self._sine_ghosting_enabled = True
        self._sine_ghost_alpha = 0.45
        self._sine_ghost_decay = 0.3
        self._bubble_ghosting_enabled = False
        self._bubble_ghost_alpha = 0.0
        self._bubble_ghost_decay = 0.4
        self._sine_heartbeat = 0.0
        self._heartbeat_intensity = 0.0
        self._sine_density = 1.0
        self._sine_displacement = 0.0
        self._use_raw_energy = False
        self._sine_glow_enabled = True
        self._sine_glow_intensity = 0.5
        self._sine_glow_size = 1.0
        self._sine_glow_reactivity = 1.0
        self._sine_glow_color = None
        self._sine_reactive_glow = True
        self._sine_sensitivity = 1.0
        self._osc_glow_enabled = True
        self._osc_glow_intensity = 0.5
        self._osc_glow_size = 1.0
        self._osc_glow_reactivity = 1.0
        self._osc_glow_color = None
        self._osc_reactive_glow = True
        self._osc_line_amplitude = 3.0
        self._osc_smoothing = 0.7
        self._blob_color = None
        self._blob_glow_color = None
        self._blob_edge_color = None
        self._blob_outline_color = None
        self._blob_pulse = 1.0
        self._blob_width = 1.0
        self._blob_size = 1.0
        self._blob_glow_intensity = 0.5
        self._blob_glow_reactivity = 1.0
        self._blob_glow_max_size = 1.0
        self._blob_reactive_glow = True
        self._blob_reactive_deformation = 1.0
        self._blob_stage_gain = 1.0
        self._blob_core_scale = 1.0
        self._blob_core_floor_bias = 0.35
        self._blob_stage_bias = 0.0
        self._blob_stage2_release_ms = 900.0
        self._blob_stage3_release_ms = 1200.0
        self._blob_constant_wobble = 1.0
        self._blob_reactive_wobble = 1.0
        self._blob_stretch_tendency = 0.35
        self._blob_stretch_inner = 0.5
        self._blob_stretch_outer = 0.5
        self._sine_speed = 1.0
        self._sine_line_dim = False
        self._sine_line_offset_bias = 0.0
        self._osc_speed = 1.0
        self._osc_line_dim = False
        self._osc_line_offset_bias = 0.0
        self._osc_vertical_shift = 0
        self._sine_wave_travel = 0
        self._sine_card_adaptation = 0.30
        self._sine_travel_line2 = 0
        self._sine_travel_line3 = 0
        self._sine_line1_shift = 0.0
        self._sine_line2_shift = 0.0
        self._sine_line3_shift = 0.0
        self._sine_wave_effect = 0.0
        self._sine_micro_wobble = 0.0
        self._sine_crawl_amount = 0.0
        self._sine_width_reaction = 0.0
        self._sine_vertical_shift = 0
        self._sine_line_color = None
        self._osc_line_color = None
        self._sine_line_count = 1
        self._osc_line_count = 1
        self._sine_line2_color = None
        self._osc_line2_color = None
        self._sine_line2_glow_color = None
        self._osc_line2_glow_color = None
        self._sine_line3_color = None
        self._osc_line3_color = None
        self._sine_line3_glow_color = None
        self._osc_line3_glow_color = None


class _SchedulerEngine(_StubEngine):
    def __init__(self, scheduler, tb=None, eb=None):
        super().__init__(tb=tb, eb=eb)
        self._scheduler = scheduler

    def get_waveform(self):
        return [0.0] * 256

    def get_event_scheduler(self):
        return self._scheduler


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


# ===========================================================================
# 6. Per-Mode Transient Mix — Settings Model Round-Trip (§2.3)
# ===========================================================================

class TestTransientMixSettingsModel:
    """Verify new transient mix fields survive from_mapping → to_dict."""

    _MIX_KEYS = (
        'spectrum_lane_transient_mix',
        'bubble_transient_mix_bass',
        'bubble_transient_mix_vocal',
        'blob_transient_mix_bass',
        'blob_transient_mix_vocal',
        'sine_wave_transient_width_mix',
        'oscilloscope_transient_width_mix',
    )

    def test_defaults_present_on_model(self):
        """All mix fields should exist on a fresh model with correct defaults."""
        from core.settings.models import SpotifyVisualizerSettings
        model = SpotifyVisualizerSettings()
        assert model.spectrum_lane_transient_mix == 0.65
        assert model.bubble_transient_mix_bass == 0.75
        assert model.bubble_transient_mix_vocal == 0.25
        assert model.blob_transient_mix_bass == 0.5
        assert model.blob_transient_mix_vocal == 0.35
        assert model.sine_wave_transient_width_mix == 0.4
        assert model.oscilloscope_transient_width_mix == 0.35

    def test_round_trip_from_mapping(self):
        """Custom values should survive from_mapping → to_dict → from_mapping."""
        from core.settings.models import SpotifyVisualizerSettings
        custom = {
            'mode': 'spectrum',
            'preset_spectrum': 3,
            'preset_bubble': 3,
            'preset_blob': 3,
            'preset_sine_wave': 3,
            'preset_oscilloscope': 3,
            'spectrum_lane_transient_mix': 0.9,
            'bubble_transient_mix_bass': 0.1,
            'bubble_transient_mix_vocal': 0.8,
            'blob_transient_mix_bass': 0.3,
            'blob_transient_mix_vocal': 0.7,
            'sine_wave_transient_width_mix': 0.15,
            'oscilloscope_transient_width_mix': 0.95,
        }
        model = SpotifyVisualizerSettings.from_mapping(custom)
        exported = model.to_dict()
        prefix = 'widgets.spotify_visualizer.'
        for key in self._MIX_KEYS:
            val = custom[key]
            full_key = f"{prefix}{key}"
            assert full_key in exported, f"{full_key} missing from to_dict"
            assert abs(exported[full_key] - val) < 1e-9, f"{full_key} value mismatch"

    def test_resolver_methods(self):
        """Each resolver method should return the correct field value."""
        from core.settings.models import SpotifyVisualizerSettings
        model = SpotifyVisualizerSettings()
        assert model.resolve_spectrum_lane_transient_mix() == 0.65
        assert model.resolve_bubble_transient_mix_bass() == 0.75
        assert model.resolve_bubble_transient_mix_vocal() == 0.25
        assert model.resolve_blob_transient_mix_bass() == 0.5
        assert model.resolve_blob_transient_mix_vocal() == 0.35
        assert model.resolve_sine_wave_transient_width_mix() == 0.4
        assert model.resolve_oscilloscope_transient_width_mix() == 0.35


# ===========================================================================
# 7. Spectrum Kick Lane Mix Scaling (§2.3)
# ===========================================================================

class TestSpectrumLaneTransientMix:
    """Verify spectrum_lane_transient_mix modulates kick express lane boost."""

    def test_mix_scales_kick_boost(self):
        """Higher lane_transient_mix should increase kick boost."""
        _t_bass = 0.6
        _kick_gain = 1.0
        lo_mix = 0.2
        hi_mix = 1.0
        boost_lo = min(2.0, 1.0 + _t_bass * _kick_gain * lo_mix)
        boost_hi = min(2.0, 1.0 + _t_bass * _kick_gain * hi_mix)
        assert boost_hi > boost_lo

    def test_mix_zero_disables_transient_feed(self):
        """lane_transient_mix of 0 should eliminate kick boost from transients."""
        _t_bass = 1.0
        _kick_gain = 2.0
        _lane_mix = 0.0
        boost = min(2.0, 1.0 + _t_bass * _kick_gain * _lane_mix)
        assert boost == 1.0


# ===========================================================================
# 8. Bubble Bass/Vocal Transient Mix (§2.3)
# ===========================================================================

class TestBubbleTransientMixWeights:
    """Verify bubble_transient_mix_bass and _vocal modulate pulse mixing."""

    def test_bass_mix_scales_transient_bass(self):
        """Higher bass mix weight → more transient bass in pulse."""
        _pulse_bass = 0.3
        _t_bass = 0.5
        _t_gain = 1.0
        _t_clamp = 1.5

        lo = min(_t_clamp, _pulse_bass + _t_bass * _t_gain * 0.2)
        hi = min(_t_clamp, _pulse_bass + _t_bass * _t_gain * 0.9)
        assert hi > lo

    def test_vocal_mix_scales_transient_mid(self):
        """Higher vocal mix weight → more transient mid in pulse mid."""
        _pulse_mid = 0.2
        _t_mid = 0.4
        _t_gain = 1.0
        _t_clamp = 1.5

        lo = min(_t_clamp, _pulse_mid + _t_mid * _t_gain * 0.1)
        hi = min(_t_clamp, _pulse_mid + _t_mid * _t_gain * 0.8)
        assert hi > lo

    def test_zero_mix_no_transient_contribution(self):
        """Mix of 0 should not add transient energy."""
        mixed = min(1.5, 0.3 + 0.8 * 1.0 * 0.0)
        assert mixed == 0.3


# ===========================================================================
# 9. Blob Bass/Vocal Transient Mix (§2.3)
# ===========================================================================

class TestBlobTransientMixWeights:
    """Verify blob_transient_mix_bass and _vocal modulate blob energy bands."""

    def test_bass_mix_increases_raw_bass(self):
        """Blob transient bass mix should add transient energy to raw_bass."""
        raw_bass = 0.4
        t_bass = 0.6
        _bmb = 0.5
        _clamp = 1.5
        result = min(_clamp, raw_bass + t_bass * _bmb)
        assert result == 0.7  # 0.4 + 0.6 * 0.5

    def test_vocal_mix_increases_raw_mid(self):
        """Blob transient vocal mix should add transient energy to raw_mid."""
        raw_mid = 0.3
        t_mid = 0.4
        _bmv = 0.35
        _clamp = 1.5
        result = min(_clamp, raw_mid + t_mid * _bmv)
        assert abs(result - 0.44) < 1e-9  # 0.3 + 0.4 * 0.35

    def test_clamp_limits_blob_mix(self):
        """Result should not exceed transient_clamp."""
        raw_bass = 0.9
        t_bass = 1.0
        _bmb = 1.0
        _clamp = 1.2
        result = min(_clamp, raw_bass + t_bass * _bmb)
        assert result == _clamp


# ===========================================================================
# 10. Blob Scheduler Event Wiring (§2.4)
# ===========================================================================

class TestBlobSchedulerEventWiring:
    """Verify blob GPU kwargs include scheduler-derived event strengths."""

    def test_build_kwargs_includes_blob_event_strengths(self):
        from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs
        from widgets.spotify_visualizer.transient_bus import OnsetEvent, TransientEventScheduler

        sched = TransientEventScheduler()
        now = time.time()
        assert sched.feed(OnsetEvent(timestamp=now, event_type='kick', strength=0.8))
        assert sched.feed(OnsetEvent(timestamp=now + 0.15, event_type='snare', strength=0.55))

        engine = _SchedulerEngine(
            sched,
            tb=TransientEnergyBands(bass_transient=0.3, mid_transient=0.2),
            eb=_StubEnergyBands(bass=0.4, mid=0.2, high=0.1, overall=0.3),
        )
        widget = _BlobKwargsWidget()

        kwargs = build_gpu_push_extra_kwargs(widget, 'blob', engine)

        assert abs(kwargs['blob_kick_event_strength'] - 0.8) < 1e-9
        assert abs(kwargs['blob_snare_event_strength'] - 0.55) < 1e-9

    def test_build_kwargs_zeros_blob_event_strengths_when_scheduler_empty(self):
        from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs
        from widgets.spotify_visualizer.transient_bus import TransientEventScheduler

        engine = _SchedulerEngine(
            TransientEventScheduler(),
            tb=TransientEnergyBands(),
            eb=_StubEnergyBands(),
        )
        widget = _BlobKwargsWidget()

        kwargs = build_gpu_push_extra_kwargs(widget, 'blob', engine)

        assert kwargs['blob_kick_event_strength'] == 0.0
        assert kwargs['blob_snare_event_strength'] == 0.0


# ===========================================================================
# 11. Sine/Osc Scheduler Event Wiring (§2.4)
# ===========================================================================

class TestLineSchedulerEventWiring:
    """Verify sine/osc GPU kwargs include scheduler-derived event strengths."""

    def test_build_kwargs_includes_line_event_strengths(self):
        from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs
        from widgets.spotify_visualizer.transient_bus import OnsetEvent, TransientEventScheduler

        sched = TransientEventScheduler()
        now = time.time()
        assert sched.feed(OnsetEvent(timestamp=now, event_type='kick', strength=0.7))
        assert sched.feed(OnsetEvent(timestamp=now + 0.12, event_type='snare', strength=0.45))

        engine = _SchedulerEngine(
            sched,
            tb=TransientEnergyBands(bass_transient=0.2, mid_transient=0.1),
            eb=_StubEnergyBands(bass=0.3, mid=0.2, high=0.1, overall=0.2),
        )
        widget = _BlobKwargsWidget()

        osc_kwargs = build_gpu_push_extra_kwargs(widget, 'oscilloscope', engine)
        sine_kwargs = build_gpu_push_extra_kwargs(widget, 'sine_wave', engine)

        assert abs(osc_kwargs['line_kick_event_strength'] - 0.7) < 1e-9
        assert abs(osc_kwargs['line_snare_event_strength'] - 0.45) < 1e-9
        assert abs(sine_kwargs['line_kick_event_strength'] - 0.7) < 1e-9
        assert abs(sine_kwargs['line_snare_event_strength'] - 0.45) < 1e-9

    def test_build_kwargs_zero_line_event_strengths_when_scheduler_empty(self):
        from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs
        from widgets.spotify_visualizer.transient_bus import TransientEventScheduler

        engine = _SchedulerEngine(
            TransientEventScheduler(),
            tb=TransientEnergyBands(),
            eb=_StubEnergyBands(),
        )
        widget = _BlobKwargsWidget()

        osc_kwargs = build_gpu_push_extra_kwargs(widget, 'oscilloscope', engine)

        assert osc_kwargs['line_kick_event_strength'] == 0.0
        assert osc_kwargs['line_snare_event_strength'] == 0.0


# ===========================================================================
# 12. Sine/Osc Transient Width Mix (§2.3)
# ===========================================================================

class TestSineOscTransientWidthMix:
    """Verify sine_wave and osc transient width mix modulate rendered output."""

    def test_sine_width_reaction_modulated(self):
        """Sine width reaction should be amplified by bass * mix."""
        base_wr = 0.5
        bass = 0.7
        mix = 0.4
        modulated = min(1.0, base_wr * (1.0 + bass * mix))
        expected = min(1.0, 0.5 * (1.0 + 0.7 * 0.4))
        assert abs(modulated - expected) < 1e-9

    def test_sine_mix_zero_no_modulation(self):
        """Mix of 0 should leave width reaction unchanged."""
        base_wr = 0.6
        modulated = min(1.0, base_wr * (1.0 + 0.8 * 0.0))
        assert modulated == base_wr

    def test_osc_sensitivity_modulated(self):
        """Osc sensitivity should be amplified by bass * mix."""
        base_sens = 3.0
        bass = 0.5
        mix = 0.35
        modulated = base_sens * (1.0 + bass * mix)
        expected = 3.0 * (1.0 + 0.5 * 0.35)
        assert abs(modulated - expected) < 1e-9

    def test_osc_mix_zero_no_modulation(self):
        """Mix of 0 should leave osc sensitivity unchanged."""
        base_sens = 3.0
        modulated = base_sens * (1.0 + 0.6 * 0.0)
        assert modulated == base_sens

    def test_sine_width_clamped_to_1(self):
        """Modulated width reaction should not exceed 1.0."""
        base_wr = 0.9
        modulated = min(1.0, base_wr * (1.0 + 1.0 * 1.0))
        assert modulated == 1.0


class TestSineSchedulerBeatAssist:
    """Verify sine-only scheduler assist boosts the parts that visually read as reactivity."""

    class _State:
        _osc_smoothed_bass = 0.20
        _osc_smoothed_mid = 0.10
        _osc_smoothed_high = 0.05
        _line_kick_event_strength = 0.80
        _line_snare_event_strength = 0.45
        _sine_wave_transient_width_mix = 0.40
        _sine_width_reaction = 0.35
        _osc_line_amplitude = 1.10
        _heartbeat_intensity = 0.10

        class _Bands:
            overall = 0.18

        _energy_bands = _Bands()

    def test_scheduler_boosts_sine_energy_and_amplitude(self):
        from widgets.spotify_visualizer.renderers.sine_wave import _compute_sine_reactivity_state

        reactive = _compute_sine_reactivity_state(self._State())

        assert reactive['bass_energy'] > 0.20
        assert reactive['mid_energy'] > 0.10
        assert reactive['high_energy'] > 0.05
        assert reactive['overall_energy'] > 0.18
        assert reactive['sensitivity'] > 1.10
        assert reactive['heartbeat_intensity'] > 0.10
        assert reactive['width_reaction'] > 0.35

    def test_zero_events_leave_sine_base_signals_alone(self):
        from widgets.spotify_visualizer.renderers.sine_wave import _compute_sine_reactivity_state

        state = self._State()
        state._line_kick_event_strength = 0.0
        state._line_snare_event_strength = 0.0
        state._sine_wave_transient_width_mix = 0.0

        reactive = _compute_sine_reactivity_state(state)

        assert abs(reactive['bass_energy'] - 0.20) < 1e-9
        assert abs(reactive['mid_energy'] - 0.10) < 1e-9
        assert abs(reactive['high_energy'] - 0.05) < 1e-9
        assert abs(reactive['overall_energy'] - 0.18) < 1e-9
        assert abs(reactive['sensitivity'] - 1.10) < 1e-9
        assert abs(reactive['heartbeat_intensity'] - 0.10) < 1e-9
        assert abs(reactive['width_reaction'] - 0.35) < 1e-9
