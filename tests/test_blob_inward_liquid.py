from __future__ import annotations

from pathlib import Path

from widgets.spotify_visualizer.blob_math import (
    compute_blob_radius_preview,
    compute_inward_liquid_profile,
    compute_stage_progress,
    solve_unshaped_blob_profile_step,
)


def _border_profile(
    *,
    edge_distance: float = 0.006,
    blob_clearance: float = 0.18,
    perimeter_pos: float = 0.25,
    time_seconds: float = 1.2,
    bass_energy: float = 0.30,
    mid_energy: float = 0.26,
    high_energy: float = 0.14,
    overall_energy: float = 0.24,
    smoothed_energy: float = 0.28,
    stage1_t: float = 0.0,
    stage2_t: float = 0.0,
    stage3_t: float = 0.0,
    transient_energy: float = 0.0,
    reactivity: float = 1.15,
    max_size: float = 0.28,
    enabled: bool = True,
) -> dict[str, float]:
    return compute_inward_liquid_profile(
        edge_distance=edge_distance,
        blob_clearance=blob_clearance,
        perimeter_pos=perimeter_pos,
        time_seconds=time_seconds,
        bass_energy=bass_energy,
        mid_energy=mid_energy,
        high_energy=high_energy,
        overall_energy=overall_energy,
        smoothed_energy=smoothed_energy,
        stage1_t=stage1_t,
        stage2_t=stage2_t,
        stage3_t=stage3_t,
        transient_energy=transient_energy,
        reactivity=reactivity,
        max_size=max_size,
        enabled=enabled,
    )


def test_border_liquid_disables_cleanly() -> None:
    disabled = _border_profile(enabled=False)
    assert disabled["front_depth"] == 0.0
    assert disabled["mix"] == 0.0
    assert disabled["retreat_depth"] == 0.0


def test_blob_shader_resolves_stage_progress_for_border_liquid_in_main_scope() -> None:
    src = Path(
        r"F:\Programming\Apps\ShittyRandomPhotoScreenSaver\widgets\spotify_visualizer\shaders\blob.frag"
    ).read_text(encoding="utf-8")

    assert "vec3 stage_progress_main = compute_stage_progress_values(" in src
    assert "card_edge_distance" in src
    assert "perimeter_phase" in src
    assert "max(d_fill, 0.0)" in src


def test_border_liquid_advances_under_energy_but_keeps_gap() -> None:
    calm = _border_profile(
        bass_energy=0.08,
        mid_energy=0.06,
        high_energy=0.05,
        overall_energy=0.07,
        smoothed_energy=0.08,
    )
    active = _border_profile(
        bass_energy=0.72,
        mid_energy=0.62,
        high_energy=0.28,
        overall_energy=0.64,
        smoothed_energy=0.70,
        stage1_t=0.88,
        stage2_t=0.74,
        stage3_t=0.52,
        transient_energy=0.30,
    )

    assert active["advance_drive"] > calm["advance_drive"]
    assert active["mix"] > calm["mix"]
    assert active["front_depth"] >= active["retained_front_floor"] > 0.0
    assert calm["front_depth"] >= calm["retained_front_floor"] > 0.0
    assert active["no_contact_gap"] > 0.0
    assert calm["no_contact_gap"] > 0.0


def test_border_liquid_retreats_when_blob_clearance_shrinks() -> None:
    roomy = _border_profile(
        blob_clearance=0.22,
        bass_energy=0.78,
        mid_energy=0.66,
        high_energy=0.24,
        overall_energy=0.68,
        smoothed_energy=0.74,
        stage1_t=0.94,
        stage2_t=0.82,
        stage3_t=0.58,
        transient_energy=0.36,
        reactivity=1.30,
        max_size=0.32,
    )
    threatened = _border_profile(
        blob_clearance=0.04,
        bass_energy=0.78,
        mid_energy=0.66,
        high_energy=0.24,
        overall_energy=0.68,
        smoothed_energy=0.74,
        stage1_t=0.94,
        stage2_t=0.82,
        stage3_t=0.58,
        transient_energy=0.36,
        reactivity=1.30,
        max_size=0.32,
    )

    assert threatened["retreat_depth"] > roomy["retreat_depth"]
    assert threatened["front_depth"] < roomy["front_depth"]
    assert threatened["no_contact_gap"] > 0.0


def test_border_liquid_retained_front_never_collapses() -> None:
    hot = _border_profile(
        edge_distance=0.004,
        blob_clearance=0.09,
        bass_energy=1.0,
        mid_energy=0.86,
        high_energy=0.34,
        overall_energy=0.90,
        smoothed_energy=0.96,
        stage1_t=1.0,
        stage2_t=1.0,
        stage3_t=0.94,
        transient_energy=0.42,
        reactivity=1.45,
        max_size=0.36,
    )

    assert hot["retreat_depth"] > 0.0
    assert hot["front_depth"] >= hot["retained_front_floor"] > 0.0
    assert hot["mix"] > 0.05
    assert hot["no_contact_gap"] > 0.0


def test_synthetic_blob_and_border_liquid_hold_gap_through_phrase() -> None:
    synthetic_frames = [
        dict(bass=0.08, mid=0.06, high=0.05, overall=0.06, smoothed=0.08, transient=0.02),
        dict(bass=0.22, mid=0.18, high=0.10, overall=0.16, smoothed=0.20, transient=0.06),
        dict(bass=0.48, mid=0.42, high=0.18, overall=0.38, smoothed=0.44, transient=0.16),
        dict(bass=0.82, mid=0.70, high=0.28, overall=0.72, smoothed=0.78, transient=0.40),
        dict(bass=0.40, mid=0.48, high=0.24, overall=0.42, smoothed=0.50, transient=0.14),
        dict(bass=0.14, mid=0.12, high=0.08, overall=0.12, smoothed=0.14, transient=0.04),
    ]

    front_depths: list[float] = []
    gaps: list[float] = []
    mixes: list[float] = []
    radii: list[float] = []

    for idx, frame in enumerate(synthetic_frames):
        stage1_t, stage2_t, stage3_t = compute_stage_progress(
            bass_energy=frame["bass"],
            mid_energy=frame["mid"],
            high_energy=frame["high"],
            overall_energy=frame["overall"],
            smoothed_energy=frame["smoothed"],
        )
        radius = compute_blob_radius_preview(
            blob_size=0.35,
            blob_pulse=1.0,
            bass_energy=frame["bass"],
            mid_energy=frame["mid"],
            high_energy=frame["high"],
            overall_energy=frame["overall"],
            smoothed_energy=frame["smoothed"],
            stage_gain=0.72,
            core_scale=0.88,
        )
        clearance = max(0.44 - radius, 0.0)
        profile = _border_profile(
            edge_distance=0.006,
            blob_clearance=clearance,
            perimeter_pos=0.31,
            time_seconds=idx * 0.16,
            bass_energy=frame["bass"],
            mid_energy=frame["mid"],
            high_energy=frame["high"],
            overall_energy=frame["overall"],
            smoothed_energy=frame["smoothed"],
            stage1_t=stage1_t,
            stage2_t=stage2_t,
            stage3_t=stage3_t,
            transient_energy=frame["transient"],
            reactivity=1.20,
            max_size=0.30,
        )
        radii.append(radius)
        front_depths.append(profile["front_depth"])
        gaps.append(profile["no_contact_gap"])
        mixes.append(profile["mix"])

    assert all(gap > 0.0 for gap in gaps)
    assert front_depths[3] >= front_depths[0]
    assert mixes[3] > mixes[0]
    assert max(radii) < 0.30


def test_small_unshaped_blob_contour_has_visible_screen_space_delta() -> None:
    stage1_t, stage2_t, stage3_t = compute_stage_progress(
        bass_energy=0.15,
        mid_energy=0.18,
        high_energy=0.12,
        overall_energy=0.20,
        smoothed_energy=0.22,
        stage_bias=-0.08,
    )
    profile_bundle, _velocity = solve_unshaped_blob_profile_step(
        previous_profile=None,
        previous_velocity=None,
        previous_target_profile=None,
        sample_count=64,
        time_seconds=1.23,
        dt=0.016,
        bass_energy=0.15,
        mid_energy=0.18,
        high_energy=0.12,
        overall_energy=0.20,
        smoothed_energy=0.22,
        reactive_deformation=1.0,
        constant_wobble=1.0,
        reactive_wobble=1.0,
        stretch_tendency=0.55,
        stretch_inner=0.0,
        stretch_outer=0.55,
        core_floor_bias=0.12,
        stage1_t=stage1_t,
        stage2_t=stage2_t,
        stage3_t=stage3_t,
        playing=True,
        seed=0.3,
    )
    _base_profile, _raw_target, _target_profile, solved_profile = profile_bundle

    radius = compute_blob_radius_preview(
        blob_size=0.35,
        blob_pulse=1.0,
        bass_energy=0.15,
        mid_energy=0.18,
        high_energy=0.12,
        overall_energy=0.20,
        smoothed_energy=0.22,
        stage_gain=0.72,
        core_scale=0.88,
    )
    contour_authority = 2.75 + 0.22 * 0.36 + stage1_t * 0.30 + stage2_t * 0.18 + stage3_t * 0.14
    screen_space_delta = (max(solved_profile) - min(solved_profile)) * contour_authority * radius * 576.0

    assert screen_space_delta > 24.0
