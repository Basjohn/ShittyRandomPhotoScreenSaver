"""Runtime-shaped contracts for Blob's curved GPU goo field."""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer.blob_tendril_runtime import (
    TENDRIL_COUNT,
    advance_blob_tendril_state,
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


def _state(time_value: float = 1.0) -> SimpleNamespace:
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


def _transport_payload(
    *,
    angle: float,
    reach: float,
    bend: float = 0.45,
    activity: float = 0.90,
) -> tuple[list[float], list[float]]:
    geometry: list[float] = []
    motion: list[float] = []
    for idx in range(TENDRIL_COUNT):
        geometry.extend(((angle + idx / TENDRIL_COUNT) % 1.0, reach, 0.034, 0.022))
        motion.extend((bend, -bend * 0.45, activity, -activity if idx in {3, 8, 11} else activity))
    return geometry, motion


def test_mighty_extreme_controls_create_sparse_broad_lifecycle_goo() -> None:
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
    assert 1 <= len(active) <= 4
    assert 1 <= len(outward) <= 4
    assert len(grooves) <= 1
    assert max(reaches) > 0.08
    assert max(angle_gaps) - min(angle_gaps) > 0.035
    assert all(0.008 <= lane[0][3] <= lane[0][2] for lane in active)
    assert sum(lane[0][1] == 0.0 and lane[0][2] == 0.0 for lane in lanes) >= 7


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

    assert sum(length_deltas) > 0.12
    assert max(length_deltas) > 0.07
    assert max(bend_deltas) > 0.20
    assert max(angle_deltas) > 0.20


def test_mighty_lanes_retire_fully_and_never_form_an_always_on_starburst() -> None:
    lane_reaches = [[] for _ in range(TENDRIL_COUNT)]
    outward_counts: list[int] = []
    groove_counts: list[int] = []
    previous_geometry: list[float] | None = None
    retarget_events = 0
    for frame in range(161):
        geometry, motion = build_blob_tendril_payload(
            _state(frame / 20.0),
            blob_type="mighty",
            profile=_profile(),
        )
        outward_counts.append(
            sum(
                geometry[idx * 4 + 1] > 0.002 and motion[idx * 4 + 3] >= 0.0
                for idx in range(TENDRIL_COUNT)
            )
        )
        groove_counts.append(
            sum(
                geometry[idx * 4 + 1] > 0.002 and motion[idx * 4 + 3] < 0.0
                for idx in range(TENDRIL_COUNT)
            )
        )
        for idx in range(TENDRIL_COUNT):
            lane_reaches[idx].append(geometry[idx * 4 + 1])
            if previous_geometry is not None:
                angle_step = abs(
                    (
                        (geometry[idx * 4] - previous_geometry[idx * 4] + 0.5)
                        % 1.0
                    )
                    - 0.5
                )
                if angle_step > 0.05:
                    retarget_events += 1
                    assert max(
                        geometry[idx * 4 + 1],
                        previous_geometry[idx * 4 + 1],
                    ) < 0.002
        previous_geometry = geometry

    assert max(outward_counts) <= 4
    assert max(groove_counts) <= 1
    assert all(min(reaches) == pytest.approx(0.0) for reaches in lane_reaches)
    active_slots = {0, 4, 7, 11}
    assert all(max(lane_reaches[idx]) > 0.03 for idx in active_slots)
    assert max(max(lane_reaches[idx]) for idx in active_slots) > 0.15
    assert all(
        max(lane_reaches[idx]) == pytest.approx(0.0)
        for idx in range(TENDRIL_COUNT)
        if idx not in active_slots
    )
    assert retarget_events >= 3


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

    assert max(enabled_geometry[1::4]) > 0.08
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
    ring_state = _state()
    ring_state._blob_topology = "ring"
    ring_geometry = build_blob_tendril_payload(
        ring_state,
        blob_type="shaped",
        profile=_profile(),
    )[0]

    assert 1 <= len(outward) <= 3
    assert len(grooves) <= 1
    assert max(lane[0][1] for lane in outward) > 0.060
    assert max(geometry[1::4]) > max(inert_geometry[1::4]) + 0.060
    assert max(inert_geometry[1::4]) == pytest.approx(0.0)
    assert max(ring_geometry[1::4]) > max(geometry[1::4]) * 1.08


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
    ) > 0.18
    assert max(
        abs(early_motion[idx * 4] - later_motion[idx * 4])
        for idx in range(TENDRIL_COUNT)
    ) > 0.18
    angle_deltas = [
        abs(
            ((later_geometry[idx * 4] - early_geometry[idx * 4] + 0.5) % 1.0)
            - 0.5
        )
        for idx in range(TENDRIL_COUNT)
    ]
    assert max(angle_deltas) > 0.05
    assert all(
        min(early_geometry[idx * 4 + 1], later_geometry[idx * 4 + 1]) < 0.004
        for idx, delta in enumerate(angle_deltas)
        if delta > 0.05
    )


def test_exposed_motion_controls_own_per_paint_vocal_contour_wobble() -> None:
    mighty = _state()
    shaped = _state()

    assert gpu_vocal_wobble_strength(mighty, blob_type="mighty") > 1.0
    assert gpu_vocal_wobble_strength(shaped, blob_type="shaped") > 0.80

    mighty._blob_reactive_wobble = 0.0
    shaped._blob_shaper_audio_motion = 0.0

    assert gpu_vocal_wobble_strength(mighty, blob_type="mighty") == pytest.approx(0.0)
    assert gpu_vocal_wobble_strength(shaped, blob_type="shaped") == pytest.approx(0.0)


def test_displayed_tendrils_attack_quickly_but_never_pop_to_a_new_reach() -> None:
    state = SimpleNamespace(_blob_runtime_time=0.0)
    quiet_geometry, quiet_motion = _transport_payload(
        angle=0.08,
        reach=0.0,
        bend=0.0,
        activity=0.0,
    )
    hot_geometry, hot_motion = _transport_payload(angle=0.08, reach=0.18)
    advance_blob_tendril_state(
        state,
        blob_type="mighty",
        target_geometry=quiet_geometry,
        target_motion=quiet_motion,
    )

    reaches: list[float] = []
    for frame in range(1, 10):
        state._blob_runtime_time = frame / 90.0
        displayed, _ = advance_blob_tendril_state(
            state,
            blob_type="mighty",
            target_geometry=hot_geometry,
            target_motion=hot_motion,
        )
        reaches.append(displayed[1])

    assert reaches == sorted(reaches)
    assert reaches[0] < 0.04
    assert max(
        later - earlier for earlier, later in zip([0.0, *reaches[:-1]], reaches)
    ) < 0.04
    assert reaches[-1] > 0.15


def test_displayed_tendrils_release_as_a_visible_retraction_not_one_frame_zero() -> None:
    state = SimpleNamespace(_blob_runtime_time=2.0)
    hot_geometry, hot_motion = _transport_payload(angle=0.12, reach=0.18)
    quiet_geometry, quiet_motion = _transport_payload(
        angle=0.12,
        reach=0.0,
        bend=0.0,
        activity=0.0,
    )
    advance_blob_tendril_state(
        state,
        blob_type="shaped",
        target_geometry=hot_geometry,
        target_motion=hot_motion,
    )
    state._blob_runtime_time += 1.0 / 90.0
    first_release, _ = advance_blob_tendril_state(
        state,
        blob_type="shaped",
        target_geometry=quiet_geometry,
        target_motion=quiet_motion,
    )

    assert 0.16 < first_release[1] < 0.18
    for _ in range(30):
        state._blob_runtime_time += 1.0 / 90.0
        released, _ = advance_blob_tendril_state(
            state,
            blob_type="shaped",
            target_geometry=quiet_geometry,
            target_motion=quiet_motion,
        )
    assert 0.0 < released[1] < 0.06


def test_displayed_tendril_anchor_crosses_angle_seam_on_shortest_arc() -> None:
    state = SimpleNamespace(_blob_runtime_time=3.0)
    start_geometry, motion = _transport_payload(angle=0.99, reach=0.12)
    target_geometry, target_motion = _transport_payload(angle=0.01, reach=0.12)
    advance_blob_tendril_state(
        state,
        blob_type="mighty",
        target_geometry=start_geometry,
        target_motion=motion,
    )
    state._blob_runtime_time += 1.0 / 60.0
    displayed, _ = advance_blob_tendril_state(
        state,
        blob_type="mighty",
        target_geometry=target_geometry,
        target_motion=target_motion,
    )

    step = ((displayed[0] - 0.99 + 0.5) % 1.0) - 0.5
    assert 0.0 < step < 0.01
    assert state._blob_tendril_max_step_angle < 0.01


def test_mighty_display_sequence_stays_sparse_while_reach_breathes_deeply() -> None:
    state = _state(0.0)
    displayed_counts: list[int] = []
    target_counts: list[int] = []
    max_reaches: list[float] = []
    reach_steps: list[float] = []
    angle_steps: list[float] = []
    for frame in range(901):
        state._blob_runtime_time = frame / 90.0
        target_geometry, target_motion = build_blob_tendril_payload(
            state,
            blob_type="mighty",
            profile=_profile(),
        )
        displayed_geometry, _ = advance_blob_tendril_state(
            state,
            blob_type="mighty",
            target_geometry=target_geometry,
            target_motion=target_motion,
        )
        target_counts.append(sum(value > 0.002 for value in target_geometry[1::4]))
        displayed_counts.append(
            sum(value > 0.002 for value in displayed_geometry[1::4])
        )
        max_reaches.append(max(displayed_geometry[1::4]))
        reach_steps.append(state._blob_tendril_max_step_reach)
        angle_steps.append(state._blob_tendril_max_step_angle)

    assert 1 <= min(displayed_counts) <= max(displayed_counts) <= 3
    assert max(target_counts) <= 3
    assert min(max_reaches) < 0.06
    assert max(max_reaches) > 0.15
    assert max(reach_steps) < 0.013
    # The larger bound is used only while a lane is hidden and relocating.
    assert max(angle_steps) <= 1.11 / 90.0
