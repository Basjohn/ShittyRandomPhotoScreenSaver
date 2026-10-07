"""Sphere's owned analysis controls must reach the one existing DSP worker.

These are CPU-only production-seam tests.  They configure a real BeatEngine and
its real audio worker but do not admit native capture: the worker receives a
deterministic PCM buffer directly, just as its serial analysis lane does after
capture has supplied one.
"""
from __future__ import annotations

from dataclasses import asdict

import pytest


_SPHERE_ANALYSIS_KEYS = (
    "bar_count",
    "audio_block_size",
    "adaptive_sensitivity",
    "sensitivity",
    "dynamic_floor",
    "manual_floor",
    "input_gain",
    "transient_clamp",
)
_WORKER_ONLY_CANONICAL_KEYS = {
    "dynamic_range_enabled": "spectrum_dynamic_range_enabled",
    "agc_strength": "spectrum_agc_strength",
    "kick_lane_gain": "spectrum_kick_lane_gain",
    "transient_pulse_gain": "spectrum_transient_pulse_gain",
    "spectrum_lane_transient_mix": "spectrum_lane_transient_mix",
}


def _sphere_settings(**overrides):
    from core.settings.models import SpotifyVisualizerSettings

    return SpotifyVisualizerSettings.from_mapping(
        {"mode": "sphere", **overrides},
        apply_preset_overlay=False,
        resolve_preset_indices=False,
    )


def _configured_sphere_worker(**overrides):
    """Apply Sphere's real source + technical configuration without capture."""
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
    from widgets.spotify_visualizer.quick_technical_config import (
        apply_controller_technical_config,
    )
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.source_config_applier import (
        apply_engine_vis_mode_kwargs,
        resolve_mode_source_config,
    )
    from widgets.spotify_visualizer.technical_config import (
        build_technical_cache,
        resolve_technical_config,
    )

    model = _sphere_settings(**overrides)
    controller = VisualizerRuntimeController(
        runtime_generation=41,
        initial_mode="sphere",
        engine_factory=lambda count: _SpotifyBeatEngine(count),
    )
    controller.settings_model = model
    controller.technical_config_cache = build_technical_cache(None, model)
    engine = controller.ensure_engine()
    source = resolve_mode_source_config("sphere", asdict(model))
    assert apply_engine_vis_mode_kwargs(engine, source)
    technical = resolve_technical_config(controller.technical_config_cache, "sphere")
    apply_controller_technical_config(
        controller, technical, reason="sphere_analysis_consumer_test"
    )
    return model, technical, engine, engine._audio_worker


def _deterministic_pcm(np):
    sample_count = 2048
    index = np.arange(sample_count, dtype=np.float32)
    return (
        # These FFT-bin positions deliberately cross all three of the
        # worker's logarithmic analysis zones.  The previous 37-bin tone was
        # above its bass zone, so it could not demonstrate the actual bass
        # lane Sphere consumes.
        0.62 * np.sin(index * (2.0 * np.pi * 5.0 / sample_count))
        + 0.27 * np.sin(index * (2.0 * np.pi * 35.0 / sample_count))
        + 0.11 * np.sin(index * (2.0 * np.pi * 100.0 / sample_count))
    ).astype(np.float32)


def _analyse(worker, pcm):
    worker._np = __import__("numpy")
    bars = worker.compute_bars_from_samples(pcm)
    assert isinstance(bars, list)
    assert bars
    return tuple(float(value) for value in bars)


def test_sphere_technical_whitelist_keeps_only_consumed_values_persisted(qt_app):
    from core.settings.default_contract import require_canonical_default

    model, technical, engine, worker = _configured_sphere_worker(
        sphere_bar_count=13,
        sphere_audio_block_size=256,
        sphere_adaptive_sensitivity=False,
        sphere_sensitivity=1.7,
        sphere_dynamic_floor=False,
        sphere_manual_floor=0.31,
        sphere_input_gain=1.45,
        sphere_transient_clamp=0.23,
    )

    expected = {
        "bar_count": 13,
        "audio_block_size": 256,
        "adaptive_sensitivity": False,
        "sensitivity": pytest.approx(1.7),
        "dynamic_floor": False,
        "manual_floor": pytest.approx(0.31),
        "input_gain": pytest.approx(1.45),
        "transient_clamp": pytest.approx(0.23),
    }
    assert {key: technical[key] for key in _SPHERE_ANALYSIS_KEYS} == expected

    persisted = asdict(model)
    for key, canonical_key in _WORKER_ONLY_CANONICAL_KEYS.items():
        assert f"sphere_{key}" not in persisted
        assert technical[key] == require_canonical_default(
            f"widgets.spotify_visualizer.{canonical_key}"
        )

    controller_bar_count = engine._bar_count
    assert controller_bar_count == 13
    assert worker._preferred_block_size == 256
    assert worker._last_floor_config == (False, pytest.approx(0.31))
    assert worker._last_sensitivity_config == (False, pytest.approx(1.7))
    assert worker._input_gain == pytest.approx(1.45)
    assert worker._transient_clamp == pytest.approx(0.23)
    assert worker._running is False and worker._backend is None


def test_sphere_pcm_controls_change_the_real_pre_agc_worker_outputs(qt_app):
    import numpy as np

    low_model, _low_technical, _low_engine, low = _configured_sphere_worker(
        sphere_bar_count=11,
        sphere_adaptive_sensitivity=False,
        sphere_sensitivity=0.35,
        sphere_dynamic_floor=False,
        sphere_manual_floor=0.42,
        sphere_input_gain=0.10,
        sphere_transient_clamp=0.08,
    )
    high_model, _high_technical, _high_engine, high = _configured_sphere_worker(
        sphere_bar_count=19,
        sphere_adaptive_sensitivity=False,
        sphere_sensitivity=2.20,
        sphere_dynamic_floor=False,
        sphere_manual_floor=0.05,
        sphere_input_gain=1.85,
        sphere_transient_clamp=1.50,
    )
    pcm = _deterministic_pcm(np)
    # A real onset is a change between two worker blocks; the second block
    # verifies the owned clamp against the production transient bus.
    _analyse(low, pcm * 0.10)
    _analyse(high, pcm * 0.10)
    low_bars = _analyse(low, pcm)
    high_bars = _analyse(high, pcm)

    assert low_model.sphere_bar_count == len(low_bars) == len(low._freq_values) == 11
    assert high_model.sphere_bar_count == len(high_bars) == len(high._freq_values) == 19
    assert high._pre_agc_live_bass > low._pre_agc_live_bass
    assert high._pre_agc_live_mid > low._pre_agc_live_mid
    assert high._pre_agc_live_treble > low._pre_agc_live_treble
    assert low._transient_bass <= 0.080001
    assert high._transient_bass > low._transient_bass


def test_sphere_selected_notches_route_real_worker_zones_without_spectrum_mirroring(qt_app):
    import numpy as np

    bass_wide = [
        [0.0, "Bass"],
        [0.72, "Low-Mid"],
        [0.82, "Vocal"],
        [0.91, "Hi-Mid"],
        [1.0, "Treble"],
    ]
    bass_narrow = [
        [0.0, "Bass"],
        [0.18, "Low-Mid"],
        [0.41, "Vocal"],
        [0.68, "Hi-Mid"],
        [1.0, "Treble"],
    ]
    wide_model, _wide_technical, _wide_engine, wide = _configured_sphere_worker(
        sphere_bar_count=20,
        sphere_analysis_notch_positions=bass_wide,
        spectrum_mirrored=True,
        spectrum_notch_positions_mirrored=bass_narrow,
        spectrum_notch_positions_linear=bass_narrow,
    )
    narrow_model, _narrow_technical, _narrow_engine, narrow = _configured_sphere_worker(
        sphere_bar_count=20,
        sphere_analysis_notch_positions=bass_narrow,
        spectrum_mirrored=True,
        spectrum_notch_positions_mirrored=bass_wide,
        spectrum_notch_positions_linear=bass_wide,
    )

    # Deliberately supply opposite Spectrum mirror/notch values.  Sphere's one
    # selected analysis snapshot must be the worker's only zone authority.
    pcm = _deterministic_pcm(np)
    _analyse(wide, pcm)
    _analyse(narrow, pcm)

    assert wide_model.sphere_analysis_notch_positions == [
        [0.0, "Bass"], [0.72, "Mid"], [0.91, "Treble"], [1.0, "End"],
    ]
    assert narrow_model.sphere_analysis_notch_positions == [
        [0.0, "Bass"], [0.18, "Mid"], [0.68, "Treble"], [1.0, "End"],
    ]
    assert wide._spectrum_notch_positions == wide_model.sphere_analysis_notch_positions
    assert narrow._spectrum_notch_positions == narrow_model.sphere_analysis_notch_positions
    assert wide._agc_bass_split == 14
    assert narrow._agc_bass_split == 3
    assert wide._last_raw_bass != pytest.approx(narrow._last_raw_bass)
    assert wide._last_raw_mid != pytest.approx(narrow._last_raw_mid)
