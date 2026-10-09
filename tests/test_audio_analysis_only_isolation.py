"""The shared audio worker must never route Sphere through Spectrum's visual shaper.

These tests use synthetic PCM and mode-owned test configurations; no curated
preset values or historical pixel output are frozen as test authorities.
"""
from __future__ import annotations

from dataclasses import asdict

import pytest

from tests.test_sphere_analysis_consumers import (
    _configured_sphere_worker,
    _deterministic_pcm,
)
from widgets.spotify_visualizer.source_config_applier import (
    apply_engine_vis_mode_kwargs,
    resolve_mode_source_config,
)


def _shockwave_profile(model):
    # Test-owned, complete source-shaper values, independent of shipped presets.
    return resolve_mode_source_config("shockwave_grid", {
        **asdict(model),
        "shockwave_grid_mirrored": False,
        "shockwave_grid_shape_nodes": [[0.0, 0.9], [1.0, 0.9]],
        "shockwave_grid_notch_positions_linear": [
            [0.0, "Bass"], [0.35, "Low-Mid"], [0.7, "Vocal"], [1.0, "Treble"],
        ],
        "shockwave_grid_lane_strengths_linear": {
            "Bass": 1.0, "Low-Mid": 1.0, "Vocal": 1.0, "Treble": 1.0,
        },
        "shockwave_grid_wave_amplitude": 0.5,
        "shockwave_grid_profile_floor": 0.1,
        "shockwave_grid_drop_speed": 1.0,
    })


def test_sphere_analysis_skips_shape_without_losing_pre_agc_and_transients(qt_app, monkeypatch):
    import numpy as np
    from widgets.spotify_visualizer import bar_computation

    _model, _technical, engine, worker = _configured_sphere_worker(
        sphere_analysis_notch_positions=[
            [0.0, "Bass"], [0.24, "Mid"], [0.71, "Treble"], [1.0, "End"],
        ],
        sphere_dynamic_floor=False,
        sphere_manual_floor=0.05,
    )
    assert worker._analysis_only_audio is True
    assert worker._spectrum_shape_nodes is None
    assert worker._spectrum_shape_config is None

    def forbidden_shape(*_args, **_kwargs):
        pytest.fail("Sphere invoked Spectrum's lane/shape interpolation")

    monkeypatch.setattr(bar_computation, "_build_lane_energy_profile", forbidden_shape)
    worker._np = np
    pcm = _deterministic_pcm(np)
    first = worker.compute_bars_from_samples(pcm * 0.2)
    second = worker.compute_bars_from_samples(pcm)
    assert first == second == [0.0] * worker._bar_count
    assert worker._freq_values is not None and np.any(worker._freq_values > 0)
    assert worker._pre_agc_live_bass > 0
    assert worker._pre_agc_live_mid > 0
    assert worker._pre_agc_live_treble >= 0
    assert worker._transient_bus is not None
    # The serial-lane snapshot must carry the mode policy, not accidentally
    # revive a Spectrum shaper in the detached worker state.
    detached = worker.make_compute_snapshot()
    assert detached._analysis_only_audio is True
    assert bar_computation.compute_bars_from_samples(detached, pcm) == [0.0] * worker._bar_count
    worker.commit_compute_snapshot(detached)
    assert worker._pre_agc_live_bass > 0


def test_shockwave_owns_real_shaped_horizon_and_clears_sphere_policy(qt_app, monkeypatch):
    import numpy as np
    from widgets.spotify_visualizer import bar_computation

    model, _technical, engine, worker = _configured_sphere_worker(
        sphere_dynamic_floor=False,
        sphere_manual_floor=0.05,
    )
    worker._np = np
    pcm = _deterministic_pcm(np)
    assert worker._analysis_only_audio is True

    calls = []
    original = bar_computation._build_lane_energy_profile

    def observe(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(bar_computation, "_build_lane_energy_profile", observe)
    assert apply_engine_vis_mode_kwargs(engine, _shockwave_profile(model)) is True
    assert worker._analysis_only_audio is False
    assert worker.make_compute_snapshot()._analysis_only_audio is False
    assert worker._spectrum_shape_nodes == [[0.0, 0.9], [1.0, 0.9]]
    assert worker._spectrum_notch_positions[1][1] == "Low-Mid"
    assert isinstance(worker.compute_bars_from_samples(pcm), list)
    assert calls, "Shockwave's authored horizon shape was not evaluated"

    # The same shared engine must fence the previous shape when Sphere returns.
    calls.clear()
    source_sphere = resolve_mode_source_config("sphere", asdict(model))
    assert apply_engine_vis_mode_kwargs(engine, source_sphere) is True
    assert worker._analysis_only_audio is True
    assert worker.make_compute_snapshot()._analysis_only_audio is True
    assert worker._spectrum_notch_positions == model.sphere_analysis_notch_positions
    assert worker.compute_bars_from_samples(pcm) == [0.0] * worker._bar_count
    assert not calls, "Sphere unexpectedly inherited Shockwave's shaper"

    # Spectrum does not inherit Sphere's analysis-only admission either.
    source_spectrum = resolve_mode_source_config("spectrum", asdict(model))
    apply_engine_vis_mode_kwargs(engine, source_spectrum)
    assert worker._analysis_only_audio is False
    assert worker.make_compute_snapshot()._analysis_only_audio is False


def test_sphere_source_does_not_apply_spectrum_shape_to_engine(qt_app):
    model, _technical, engine, worker = _configured_sphere_worker()
    source = resolve_mode_source_config("sphere", asdict(model))
    assert source["_source_analysis_only"] is True
    from widgets.spotify_visualizer.source_config_applier import SPECTRUM_SOURCE_CONFIG_KEYS
    assert not SPECTRUM_SOURCE_CONFIG_KEYS.intersection(source)
    assert source["_source_analysis_notches"] == model.sphere_analysis_notch_positions
    assert worker._analysis_only_audio is True
    assert worker._spectrum_shape_config is None
    assert worker._spectrum_shape_nodes is None
    for mode in ("shockwave_grid", "extruded_spectrum", "spectrum", "bubble"):
        assert resolve_mode_source_config(mode, asdict(model))["_source_analysis_only"] is False
