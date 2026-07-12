"""Runtime-shaped contracts for Blob's curved GPU goo field."""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer.blob_tendril_runtime import (
    TENDRIL_COUNT,
    build_blob_tendril_payload,
    gpu_vocal_wobble_strength,
)


def _profile() -> list[float]:
    return [
        1.0
        + math.sin(math.tau * idx / 128.0 + 0.4) * 0.08
        + math.sin(math.tau * 2.0 * idx / 128.0 + 2.1) * 0.035
        for idx in range(128)
    ]


def _state(time_value: float = 2.0) -> SimpleNamespace:
    return SimpleNamespace(
        _blob_runtime_time=time_value,
        _blob_unshaped_solver_seed=0.37,
        _blob_shaper_solver_seed=0.37,
        _playing=True,
        _blob_live_bass_energy=0.82,
        _blob_live_mid_energy=0.94,
        _blob_live_high_energy=0.72,
        _blob_live_overall_energy=0.84,
        _blob_stretch_tendency=0.94,
        _blob_stretch_outer=0.94,
        _blob_reactive_deformation=1.52,
        _blob_reactive_wobble=2.82,
        _blob_pocket_state=None,
        _blob_kick_event_envelope=0.80,
        _blob_snare_event_envelope=0.65,
        _transient_energy=SimpleNamespace(
            bass_transient=0.80,
            mid_transient=0.65,
            high_transient=0.45,
        ),
        _blob_shaper_idle_motion=0.68,
        _blob_shaper_audio_motion=2.15,
        _blob_shaper_react_strength=0.84,
    )


def _lanes(
    geometry: list[float],
    motion: list[float],
) -> list[tuple[tuple[float, ...], tuple[float, ...]]]:
    return [
        (
            tuple(geometry[idx * 4 : idx * 4 + 4]),
            tuple(motion[idx * 4 : idx * 4 + 4]),
        )
        for idx in range(TENDRIL_COUNT)
    ]


def test_mighty_extreme_controls_create_dense_irregular_2d_goo_field() -> None:
    geometry, motion = build_blob_tendril_payload(
        _state(),
        blob_type="mighty",
        profile=_profile(),
    )
    lanes = _lanes(geometry, motion)
    active = [lane for lane in lanes if lane[0][1] > 0.002]
    outward = [lane for lane in active if lane[1][3] >= 0.0]
    grooves = [lane for lane in active if lane[1][3] < 0.0]
    reaches = [lane[0][1] for lane in outward]
    angles = sorted(lane[0][0] for lane in lanes)
    angle_gaps = [
        (angles[(idx + 1) % len(angles)] - angles[idx]) % 1.0
        for idx in range(len(angles))
    ]

    assert len(geometry) == TENDRIL_COUNT * 4
    assert len(motion) == TENDRIL_COUNT * 4
    assert len(active) >= 11
    assert len(outward) >= 8
    assert len(grooves) == 3
    assert max(reaches) > 0.12
    assert max(reaches) - min(reaches) > 0.09
    assert max(angle_gaps) - min(angle_gaps) > 0.035
    assert all(0.008 <= lane[0][3] <= lane[0][2] for lane in active)


def test_mighty_gpu_limbs_grow_retract_and_bend_without_orbiting() -> None:
    early_geometry, early_motion = build_blob_tendril_payload(
        _state(1.0),
        blob_type="mighty",
        profile=_profile(),
    )
    later_geometry, later_motion = build_blob_tendril_payload(
        _state(2.5),
        blob_type="mighty",
        profile=_profile(),
    )
    length_deltas = [
        abs(early_geometry[idx * 4 + 1] - later_geometry[idx * 4 + 1])
        for idx in range(TENDRIL_COUNT)
    ]
    angle_deltas = [
        abs(early_geometry[idx * 4] - later_geometry[idx * 4])
        for idx in range(TENDRIL_COUNT)
    ]
    bend_deltas = [
        abs(early_motion[idx * 4] - later_motion[idx * 4])
        for idx in range(TENDRIL_COUNT)
    ]

    assert sum(length_deltas) > 0.35
    assert max(length_deltas) > 0.07
    assert max(bend_deltas) > 0.20
    # Anchors only sway within their family; visible motion comes from reach
    # and curvature, not a clockwise cursor around the body.
    assert max(angle_deltas) < 0.025


def test_mighty_stretch_setting_owns_gpu_limb_reach() -> None:
    enabled = _state()
    disabled = _state()
    disabled._blob_stretch_tendency = 0.0
    enabled_geometry = build_blob_tendril_payload(
        enabled,
        blob_type="mighty",
        profile=_profile(),
    )[0]
    disabled_geometry = build_blob_tendril_payload(
        disabled,
        blob_type="mighty",
        profile=_profile(),
    )[0]

    assert max(enabled_geometry[1::4]) > 0.12
    assert max(disabled_geometry[1::4]) == pytest.approx(0.0)


def test_shaped_audio_motion_adds_thirty_percent_class_mutation_reach() -> None:
    driven = _state()
    geometry, motion = build_blob_tendril_payload(
        driven,
        blob_type="shaped",
        profile=_profile(),
    )
    lanes = _lanes(geometry, motion)
    outward = [lane for lane in lanes if lane[0][1] > 0.002 and lane[1][3] >= 0.0]
    grooves = [lane for lane in lanes if lane[0][1] > 0.002 and lane[1][3] < 0.0]

    inert = _state()
    inert._blob_shaper_idle_motion = 0.0
    inert._blob_shaper_audio_motion = 0.0
    inert_geometry = build_blob_tendril_payload(
        inert,
        blob_type="shaped",
        profile=_profile(),
    )[0]

    assert len(outward) >= 8
    assert len(grooves) == 3
    assert max(lane[0][1] for lane in outward) > 0.060
    assert max(geometry[1::4]) > max(inert_geometry[1::4]) + 0.060
    assert max(inert_geometry[1::4]) == pytest.approx(0.0)


def test_shaped_gpu_mutations_change_reach_at_fixed_anchor_families() -> None:
    early = build_blob_tendril_payload(
        _state(1.0),
        blob_type="shaped",
        profile=_profile(),
    )
    later = build_blob_tendril_payload(
        _state(2.5),
        blob_type="shaped",
        profile=_profile(),
    )
    early_geometry, early_motion = early
    later_geometry, later_motion = later

    assert sum(
        abs(early_geometry[idx * 4 + 1] - later_geometry[idx * 4 + 1])
        for idx in range(TENDRIL_COUNT)
    ) > 0.20
    assert max(
        abs(early_motion[idx * 4] - later_motion[idx * 4])
        for idx in range(TENDRIL_COUNT)
    ) > 0.18
    assert max(
        abs(early_geometry[idx * 4] - later_geometry[idx * 4])
        for idx in range(TENDRIL_COUNT)
    ) < 0.025


def test_exposed_motion_controls_own_per_paint_vocal_contour_wobble() -> None:
    mighty = _state()
    shaped = _state()

    assert gpu_vocal_wobble_strength(mighty, blob_type="mighty") > 1.0
    assert gpu_vocal_wobble_strength(shaped, blob_type="shaped") > 0.80

    mighty._blob_reactive_wobble = 0.0
    shaped._blob_shaper_audio_motion = 0.0

    assert gpu_vocal_wobble_strength(mighty, blob_type="mighty") == pytest.approx(0.0)
    assert gpu_vocal_wobble_strength(shaped, blob_type="shaped") == pytest.approx(0.0)
