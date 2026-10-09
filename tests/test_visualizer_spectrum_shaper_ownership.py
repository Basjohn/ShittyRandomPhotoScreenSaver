"""Only Spectrum-family modes may run authored Spectrum bar interpolation.

Bubble parity replays the old shaping-enabled engine and the corrected source
policy on the SAME deterministic synthetic PCM. Its oracle is the other live
engine's actual consumed energy and transient outputs, never authored presets
or frozen expected artistic constants.
"""
from __future__ import annotations

from dataclasses import asdict
from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer.source_config_applier import (
    SPECTRUM_SOURCE_CONFIG_KEYS,
    apply_engine_vis_mode_kwargs,
    resolve_mode_source_config,
)

# Synthetic shape used to exercise the ORIGINAL branch, not an authored preset.
_TEST_SHAPE = {
    "spectrum_mirrored": False,
    "spectrum_shape_nodes": [[0.0, 0.68], [0.5, 0.85], [1.0, 0.56]],
    "spectrum_notch_positions_linear": [
        [0.0, "Bass"], [0.30, "Low-Mid"], [0.68, "Vocal"], [1.0, "Treble"],
    ],
    "spectrum_notch_positions_mirrored": [
        [0.0, "Mid"], [0.42, "Vocal"], [1.0, "Bass"],
    ],
    "spectrum_lane_strengths_linear": {
        "Bass": 0.90, "Low-Mid": 0.75, "Vocal": 0.65, "Treble": 0.80,
    },
    "spectrum_lane_strengths_mirrored": {
        "Mid": 0.85, "Vocal": 0.70, "Bass": 0.95,
    },
    "spectrum_wave_amplitude": 0.61,
    "spectrum_profile_floor": 0.11,
    "spectrum_drop_speed": 1.15,
}


def _pair(np, *, dynamic_floor: bool):
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

    def make_engine():
        engine = _SpotifyBeatEngine(32)
        # Identical synthetic Technical profile on both sides of the change.
        engine.set_sensitivity_config(False, 1.0)
        engine.set_floor_config(dynamic_floor, 0.16)
        engine.set_input_gain(1.0)
        engine.set_energy_boost(1.0)
        engine.set_agc_strength(0.45)
        engine.set_transient_lane_config(1.2, 0.45, 1.5)
        engine._audio_worker._np = np
        # The live simulation's play-ramp belongs to playback state, not DSP.
        # Compare both engines after that same warm-up period.
        engine._get_play_ramp_factor = lambda: 1.0
        return engine

    old, new = make_engine(), make_engine()
    # The legacy Bubble source projected global Spectrum keys and executed the
    # Spectrum shaper although Bubble never consumed its authored bar output.
    assert apply_engine_vis_mode_kwargs(old, {
        **_TEST_SHAPE, "_source_spectrum_shaping_enabled": True,
    })
    # New Bubble source owns *analysis zones only*, not shape nodes or lanes.
    new_source = resolve_mode_source_config("bubble", _TEST_SHAPE)
    assert new_source["_source_spectrum_shaping_enabled"] is False
    assert not SPECTRUM_SOURCE_CONFIG_KEYS.intersection(new_source)
    assert apply_engine_vis_mode_kwargs(new, new_source)
    assert old._audio_worker._spectrum_notch_positions == new._audio_worker._spectrum_notch_positions
    return old, new


def _pcm(np, sample_count, amplitude, frame_index):
    idx = np.arange(sample_count, dtype=np.float32)
    # A changing combination of bass, mid and high FFT bands; varied enough
    # to exercise both transient onsets and adaptive-floor drop relief.
    return (amplitude * (
        0.62 * np.sin(idx * (2.0 * np.pi * 4.0 / sample_count))
        + 0.28 * np.sin(idx * (2.0 * np.pi * (24 + frame_index % 4) / sample_count))
        + 0.10 * np.sin(idx * (2.0 * np.pi * 73.0 / sample_count))
    )).astype(np.float32)


def _bubble_output(engine):
    w = engine._audio_worker
    feed = engine.get_bubble_energy_bands()
    transient = engine.get_transient_energy_bands()
    attrs = {
        "pulse_bass": feed.bass, "pulse_mid": feed.mid,
        "pulse_high": feed.high, "pulse_overall": feed.overall,
        "transient_bass": transient.bass_transient,
        "transient_mid": transient.mid_transient,
        "transient_high": transient.high_transient,
        "onset_strength": transient.onset_strength,
        "raw_bass": w._last_raw_bass, "raw_mid": w._last_raw_mid,
        "raw_treble": w._last_raw_treble,
        "pre_agc_bass": w._pre_agc_control_bass,
        "pre_agc_mid": w._pre_agc_control_mid,
        "pre_agc_high": w._pre_agc_control_treble,
        "gate_floor": w._gate_floor,
        "support_pressure": w._support_pressure,
        "last_bass_drop_ratio": w._last_bass_drop_ratio,
    }
    return attrs, (transient.onset_detected, transient.onset_type)


@pytest.mark.qt
@pytest.mark.parametrize("sample_count", [512, 2048])
@pytest.mark.parametrize("dynamic_floor", [True, False])
def test_bubble_quantified_consumed_signal_matches_old_spectrum_path(
    qt_app, monkeypatch, sample_count, dynamic_floor
):
    """Max absolute difference <= 1e-6 for every Bubble input, across 44 frames.

    The old path executes Spectrum shaping, the new one does not. Compare
    Bubble's ACTUAL consumed energy, transients and floor history, not its
    discarded bar array. This catches subtle next-frame response drift.
    """
    import numpy as np
    from widgets.spotify_visualizer import transient_bus, bar_computation

    old, new = _pair(np, dynamic_floor=dynamic_floor)
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(transient_bus.time, "time", lambda: clock.now)
    # Ensure old actually visits the Spectrum shaping machinery, new never.
    visits = []
    original = bar_computation._build_lane_energy_profile

    def counting_shape(*args, **kwargs):
        visits.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(bar_computation, "_build_lane_energy_profile", counting_shape)
    levels = ([0.12, 0.18, 0.31, 0.95, 1.32, 0.89, 0.22, 0.08, 0.76, 1.28, 0.16]
              * 4)
    max_absolute_error = 0.0
    highest_bass = 0.0
    largest_transient = 0.0
    for frame_index, amplitude in enumerate(levels):
        clock.now = 1000.0 + frame_index * 0.055
        samples = _pcm(np, sample_count, amplitude, frame_index)
        before = len(visits)
        old_bars = old._audio_worker.compute_bars_from_samples(samples.copy())
        shaped_visits = len(visits) - before
        before = len(visits)
        new_bars = new._audio_worker.compute_bars_from_samples(samples.copy())
        assert old_bars is not None and new_bars == [0.0] * 32
        assert shaped_visits == 1, "legacy comparison did not exercise shaping"
        assert len(visits) == before, "Bubble accidentally invoked Spectrum shaping"
        old_metrics, old_onset = _bubble_output(old)
        new_metrics, new_onset = _bubble_output(new)
        assert old_metrics.keys() == new_metrics.keys()
        assert old_onset == new_onset, f"frame {frame_index}: onset timing/type changed"
        for metric in old_metrics:
            delta = abs(float(old_metrics[metric]) - float(new_metrics[metric]))
            max_absolute_error = max(max_absolute_error, delta)
            assert delta <= 1e-6, (
                f"frame {frame_index}, {metric}: Bubble response drift "
                f"{delta:.9g} (old={old_metrics[metric]}, new={new_metrics[metric]})"
            )
        highest_bass = max(highest_bass, new_metrics["pulse_bass"])
        largest_transient = max(largest_transient, new_metrics["transient_bass"], new_metrics["transient_mid"])
    assert highest_bass > 0.02, "Bubble response collapsed even though old/new matched"
    assert largest_transient > 0.01, "The synthetic audio failed to exercise onset dynamics"
    assert max_absolute_error <= 1e-6


@pytest.mark.qt
@pytest.mark.parametrize("mode", ["sine_wave", "devcurve"])
def test_non_spectrum_energy_consumers_remain_reactive(qt_app, mode):
    """Sine heartbeat/DevCurve layers must not be fed zero-energy bars."""
    import numpy as np
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

    engine = _SpotifyBeatEngine(32)
    engine.set_floor_config(False, 0.05)
    engine.set_sensitivity_config(False, 1.0)
    engine.set_input_gain(1.0)
    engine.set_energy_boost(1.0)
    engine.set_transient_lane_config(1.0, 0.4, 1.5)
    engine._audio_worker._np = np
    engine._get_play_ramp_factor = lambda: 1.0
    source = resolve_mode_source_config(mode, _TEST_SHAPE)
    assert apply_engine_vis_mode_kwargs(engine, source)
    assert engine._audio_worker._spectrum_shaping_enabled is False
    # Before the first analysed frame, no mode may synthesize musical energy.
    quiet = engine.get_energy_bands()
    engine._audio_worker.compute_bars_from_samples(_pcm(np, 2048, 0.75, 1))
    loud = engine.get_energy_bands()
    assert max(loud.bass, loud.mid, loud.high) > 0.01
    assert sum((loud.bass, loud.mid, loud.high)) > sum((quiet.bass, quiet.mid, quiet.high)) + 0.01, (
        "non-Spectrum musical energy became unresponsive"
    )


def test_devcurve_has_its_own_layer_shaper_not_spectrum_shaping():
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    descriptor = get_visualizer_mode_descriptor("devcurve")
    assert descriptor.spectrum_shape_controls is False
    assert resolve_mode_source_config("devcurve", _TEST_SHAPE)["_source_spectrum_shaping_enabled"] is False


def test_descriptor_family_is_the_only_spectrum_shaper_authority():
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    expected = {"spectrum", "extruded_spectrum", "shockwave_grid"}
    modes = iter_all_visualizer_mode_descriptors()
    assert {d.mode_id for d in modes if d.spectrum_shape_controls or d.mode_id == "spectrum"} == expected
    for descriptor in modes:
        source = resolve_mode_source_config(descriptor.mode_id, _TEST_SHAPE)
        assert source["_source_spectrum_shaping_enabled"] is (descriptor.mode_id in expected)
        if descriptor.mode_id not in expected:
            assert not SPECTRUM_SOURCE_CONFIG_KEYS.intersection(source), descriptor.mode_id


def test_partial_sphere_config_uses_canonical_analysis_notches_without_shape():
    """Synthetic source-only maps may omit the Sphere analysis setting."""
    from core.settings.default_contract import require_canonical_default
    canonical = require_canonical_default(
        'widgets.spotify_visualizer.sphere_analysis_notch_positions'
    )
    source = resolve_mode_source_config('sphere', _TEST_SHAPE)
    assert source['_source_spectrum_shaping_enabled'] is False
    assert source['_source_analysis_notches'] == canonical
    assert not SPECTRUM_SOURCE_CONFIG_KEYS.intersection(source)
