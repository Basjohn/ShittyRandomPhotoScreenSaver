"""Blob contour cadence, cache, and paint-boundary regression bars."""
from __future__ import annotations

from types import SimpleNamespace

from widgets.spotify_visualizer.renderers.blob_runtime_update import (
    PROFILE_SIZE,
    advance_blob_runtime_profile,
    cached_blob_runtime_profile,
)


def _mighty_state() -> SimpleNamespace:
    return SimpleNamespace(
        _blob_type="mighty",
        _blob_shaper_enabled=False,
        _blob_runtime_time=1.0,
        _blob_variant_epoch=1,
        _playing=True,
        _blob_live_bass_energy=0.62,
        _blob_live_mid_energy=0.78,
        _blob_live_high_energy=0.46,
        _blob_live_overall_energy=0.66,
        _blob_smoothed_energy=0.60,
        _blob_reactive_deformation=1.25,
        _blob_constant_wobble=0.80,
        _blob_reactive_wobble=1.75,
        _blob_stretch_tendency=0.72,
        _blob_stretch_inner=0.0,
        _blob_stretch_outer=0.72,
        _blob_core_floor_bias=0.42,
        _blob_stage_bias=0.0,
        _blob_stage_progress_ready=False,
        _blob_pocket_state=None,
    )


def _shaped_state() -> SimpleNamespace:
    state = _mighty_state()
    state._blob_type = "shaped"
    state._blob_shaper_enabled = True
    state._blob_shaper_base_strength = 0.82
    state._blob_shaper_react_strength = 0.84
    state._blob_shaper_idle_motion = 0.68
    state._blob_shaper_audio_motion = 2.15
    state._blob_shape_base_nodes = [
        [0.0, 1.08],
        [0.25, 0.90],
        [0.50, 1.05],
        [0.75, 0.92],
    ]
    state._blob_shape_reaction_nodes = [
        [0.0, 1.42],
        [0.25, 1.12],
        [0.50, 1.54],
        [0.75, 1.16],
    ]
    state._blob_shape_energy_nodes = [
        {
            "canvas": "react",
            "type": "vocals",
            "x": 0.75,
            "y": 0.5,
            "strength": 0.85,
            "dir_x": 1.0,
            "dir_y": 0.0,
        }
    ]
    return state


def test_paint_cache_reads_never_recompute_a_valid_mighty_profile() -> None:
    state = _mighty_state()
    first = advance_blob_runtime_profile(state, force=True)
    compute_count = state._blob_profile_compute_count
    generation = state._blob_profile_generation

    uploads = [cached_blob_runtime_profile(state, "mighty") for _ in range(8)]

    assert len(first) == PROFILE_SIZE
    assert all(profile == first for profile in uploads)
    assert state._blob_profile_compute_count == compute_count == 1
    assert state._blob_profile_generation == generation == 1


def test_cold_paint_fallback_is_non_circular_and_does_not_solve() -> None:
    state = SimpleNamespace(_blob_type="mighty", _blob_shaper_enabled=False)

    fallback = cached_blob_runtime_profile(state, "mighty")

    assert len(fallback) == PROFILE_SIZE
    assert max(fallback) - min(fallback) > 0.10
    assert getattr(state, "_blob_profile_compute_count", 0) == 0
    assert not hasattr(state, "_blob_unshaped_runtime_profile")


def test_profile_cadence_caps_ninety_hz_handoffs_near_thirty_hz(monkeypatch) -> None:
    import widgets.spotify_visualizer.renderers.blob_runtime_update as runtime_update

    state = _mighty_state()
    wall_times = iter(10.0 + idx / 90.0 for idx in range(90))
    monkeypatch.setattr(runtime_update.time, "monotonic", lambda: next(wall_times))

    for idx in range(90):
        state._blob_runtime_time = 1.0 + idx / 90.0
        advance_blob_runtime_profile(state)

    assert state._blob_profile_advance_request_count == 90
    assert 28 <= state._blob_profile_compute_count <= 31
    assert state._blob_profile_skip_count >= 59
    assert state._blob_profile_generation == state._blob_profile_compute_count
    # The expensive contour remains capped, while the cheap displayed-geometry
    # morph follows every coherent state handoff instead of stepping at 30 Hz.
    assert state._blob_tendril_transport_count == 90
    assert state._blob_tendril_transport_max_ms > 0.0


def test_shaped_static_geometry_builds_once_until_authored_nodes_change() -> None:
    state = _shaped_state()

    advance_blob_runtime_profile(state, force=True)
    state._blob_runtime_time += 0.05
    advance_blob_runtime_profile(state, force=True)

    assert state._blob_shaper_geometry_build_count == 1
    assert state._blob_profile_compute_count == 2

    state._blob_shape_base_nodes = [*state._blob_shape_base_nodes, [0.88, 1.16]]
    state._blob_runtime_time += 0.05
    advance_blob_runtime_profile(state, force=True)

    assert state._blob_shaper_geometry_build_count == 2
    assert state._blob_profile_compute_count == 3


def test_shaped_cached_reads_hold_last_coherent_generation() -> None:
    state = _shaped_state()
    profile = advance_blob_runtime_profile(state, force=True)
    generation = state._blob_profile_generation
    compute_count = state._blob_profile_compute_count

    state._blob_runtime_time += 0.01
    cached = cached_blob_runtime_profile(state, "shaped")

    assert cached == profile
    assert state._blob_profile_generation == generation
    assert state._blob_profile_compute_count == compute_count
    assert state._blob_profile_generation_type == "shaped"
