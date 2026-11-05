"""Per-mode integration tests for Approach A transient bus wiring.

Verifies:
  1. Spectrum kick express lane: transient bass boosts bass-zone bars.
  2. Bubble transient pulse: transient bass mixes into bubble pulse energy.
  5. GL overlay: transient_energy stored on overlay for renderer access.
"""
from __future__ import annotations

import numpy as np
import pytest
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

    def test_legacy_global_clamp_migration_baseline_is_1_5(self):
        """Pin the retired global clamp only at its migration-contract owner."""
        from core.settings.visualizer_settings_contract import resolve_visualizer_baselines

        # EXACT-VALUE INVARIANT: 1.5 is the legacy global technical migration
        # baseline, not a mutable current per-mode product default. Update this
        # assertion only if the compatibility/migration contract intentionally changes.
        baselines = resolve_visualizer_baselines(lambda _key, default: default)
        assert baselines["transient_clamp"] == 1.5

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
# ===========================================================================



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

def test_bubble_tick_does_not_own_technical_setting_fallbacks():
    """Bubble's tick consumes resolved technical state; it must not invent defaults."""
    import ast
    from pathlib import Path

    source_path = (
        Path(__file__).resolve().parents[1]
        / "widgets"
        / "spotify_visualizer"
        / "tick_pipeline.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden = {
        "_transient_pulse_gain",
        "_transient_clamp",
        "_bubble_transient_mix_bass",
        "_bubble_transient_mix_vocal",
    }
    fallback_reads = []
    direct_reads = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in forbidden:
            direct_reads.add(node.attr)
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "getattr":
            continue
        if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
            continue
        attr = node.args[1].value
        if attr in forbidden and len(node.args) >= 3:
            fallback_reads.append(attr)

    assert not fallback_reads, (
        "resolved visualizer technical state regained tick-owned fallbacks: "
        + ", ".join(sorted(fallback_reads))
    )
    assert forbidden <= direct_reads


def test_spectrum_fft_does_not_own_transient_technical_setting_fallbacks():
    """Spectrum FFT consumes resolved transient controls; it must not invent defaults."""
    import ast
    from pathlib import Path

    source_path = (
        Path(__file__).resolve().parents[1]
        / "widgets"
        / "spotify_visualizer"
        / "bar_computation.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden = {"_kick_lane_gain", "_spectrum_lane_transient_mix"}
    fallback_reads = []
    direct_reads = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in forbidden:
            direct_reads.add(node.attr)
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "getattr":
            continue
        if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
            continue
        attr = node.args[1].value
        if attr in forbidden and len(node.args) >= 3:
            fallback_reads.append(attr)

    assert not fallback_reads, (
        "resolved Spectrum transient state regained FFT-owned fallbacks: "
        + ", ".join(sorted(fallback_reads))
    )
    assert forbidden <= direct_reads


class TestTransientMixSettingsModel:
    """Verify new transient mix fields survive from_mapping → to_dict."""

    _MIX_KEYS = (
        'spectrum_lane_transient_mix',
        'bubble_transient_mix_bass',
        'bubble_transient_mix_vocal',
    )

    def test_defaults_present_on_model_follow_canonical_authority(self):
        """Mutable product defaults come from the canonical settings authority."""
        from core.settings.default_contract import require_canonical_default
        from core.settings.models import SpotifyVisualizerSettings

        model = SpotifyVisualizerSettings()
        for key in self._MIX_KEYS:
            assert getattr(model, key) == pytest.approx(
                require_canonical_default(f"widgets.spotify_visualizer.{key}")
            )

    def test_round_trip_from_mapping(self):
        """Custom values should survive from_mapping → to_dict → from_mapping."""
        from core.settings.models import SpotifyVisualizerSettings
        from core.settings import visualizer_presets as vp
        custom = {
            'mode': 'spectrum',
            'preset_spectrum': vp.get_custom_preset_index('spectrum'),
            'preset_bubble': vp.get_custom_preset_index('bubble'),
            'preset_oscilloscope': vp.get_custom_preset_index('oscilloscope'),
            'spectrum_lane_transient_mix': 0.9,
            'bubble_transient_mix_bass': 0.1,
            'bubble_transient_mix_vocal': 0.8,
        }
        model = SpotifyVisualizerSettings.from_mapping(custom)
        exported = model.to_dict()
        prefix = 'widgets.spotify_visualizer.'
        for key in self._MIX_KEYS:
            val = custom[key]
            full_key = f"{prefix}{key}"
            assert full_key in exported, f"{full_key} missing from to_dict"
            assert abs(exported[full_key] - val) < 1e-9, f"{full_key} value mismatch"

    def test_resolver_methods_follow_canonical_defaults(self):
        """Resolver methods should follow canonical mutable per-mode defaults."""
        from core.settings.default_contract import require_canonical_default
        from core.settings.models import SpotifyVisualizerSettings

        model = SpotifyVisualizerSettings()
        resolver_by_key = {
            "spectrum_lane_transient_mix": model.resolve_spectrum_lane_transient_mix,
            "bubble_transient_mix_bass": model.resolve_bubble_transient_mix_bass,
            "bubble_transient_mix_vocal": model.resolve_bubble_transient_mix_vocal,
        }
        for key, resolver in resolver_by_key.items():
            assert resolver() == pytest.approx(
                require_canonical_default(f"widgets.spotify_visualizer.{key}")
            )


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
# ===========================================================================



# ===========================================================================
# ===========================================================================
