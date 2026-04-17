from __future__ import annotations

from pathlib import Path

from widgets.spotify_visualizer.blob_math import (
    compute_blob_radius_preview,
    compute_inward_liquid_profile,
    compute_stage_progress,
)


def test_inward_liquid_disables_cleanly_for_ring_or_disabled_mode() -> None:
    disabled = compute_inward_liquid_profile(
        angle_frac=0.25,
        time_seconds=1.2,
        local_radius=0.52,
        local_depth=0.01,
        bass_energy=0.6,
        mid_energy=0.5,
        high_energy=0.3,
        overall_energy=0.55,
        smoothed_energy=0.58,
        enabled=False,
    )
    ring = compute_inward_liquid_profile(
        angle_frac=0.25,
        time_seconds=1.2,
        local_radius=0.52,
        local_depth=0.01,
        bass_energy=0.6,
        mid_energy=0.5,
        high_energy=0.3,
        overall_energy=0.55,
        smoothed_energy=0.58,
        ring_mode=True,
    )

    assert disabled["front_depth"] == 0.0
    assert disabled["mix"] == 0.0
    assert ring["front_depth"] == 0.0
    assert ring["mix"] == 0.0


def test_blob_shader_resolves_stage_progress_for_inward_liquid_in_main_scope() -> None:
    src = Path(
        r"F:\Programming\Apps\ShittyRandomPhotoScreenSaver\widgets\spotify_visualizer\shaders\blob.frag"
    ).read_text(encoding="utf-8")

    assert "vec3 stage_progress_main = compute_stage_progress_values(" in src
    assert "stage_progress_main.x" in src
    assert "stage_progress_main.y" in src
    assert "stage_progress_main.z" in src


def test_inward_liquid_advances_under_energy_but_keeps_a_positive_gap() -> None:
    calm = compute_inward_liquid_profile(
        angle_frac=0.18,
        time_seconds=2.4,
        local_radius=0.48,
        local_depth=0.01,
        bass_energy=0.08,
        mid_energy=0.05,
        high_energy=0.04,
        overall_energy=0.06,
        smoothed_energy=0.07,
        reactivity=1.15,
        max_size=0.32,
    )
    active = compute_inward_liquid_profile(
        angle_frac=0.18,
        time_seconds=2.4,
        local_radius=0.48,
        local_depth=0.01,
        bass_energy=0.70,
        mid_energy=0.62,
        high_energy=0.34,
        overall_energy=0.66,
        smoothed_energy=0.72,
        stage1_t=0.92,
        stage2_t=0.80,
        stage3_t=0.58,
        transient_energy=0.36,
        reactivity=1.15,
        max_size=0.32,
    )

    assert active["advance_drive"] > calm["advance_drive"]
    assert active["mix"] > calm["mix"]
    assert active["retreat_depth"] > calm["retreat_depth"]
    assert calm["front_depth"] >= calm["retained_band_floor"]
    assert active["front_depth"] >= active["retained_band_floor"]
    assert calm["no_contact_gap"] > 0.0
    assert active["no_contact_gap"] > 0.0


def test_inward_liquid_yields_more_in_narrow_or_threatened_regions() -> None:
    roomy = compute_inward_liquid_profile(
        angle_frac=0.42,
        time_seconds=3.1,
        local_radius=0.62,
        local_depth=0.012,
        bass_energy=0.84,
        mid_energy=0.78,
        high_energy=0.30,
        overall_energy=0.74,
        smoothed_energy=0.80,
        stage1_t=1.0,
        stage2_t=0.94,
        stage3_t=0.80,
        transient_energy=0.45,
        reactivity=1.35,
        max_size=0.36,
    )
    narrow = compute_inward_liquid_profile(
        angle_frac=0.42,
        time_seconds=3.1,
        local_radius=0.34,
        local_depth=0.012,
        bass_energy=0.84,
        mid_energy=0.78,
        high_energy=0.30,
        overall_energy=0.74,
        smoothed_energy=0.80,
        stage1_t=1.0,
        stage2_t=0.94,
        stage3_t=0.80,
        transient_energy=0.45,
        reactivity=1.35,
        max_size=0.36,
    )

    roomy_fraction = roomy["front_depth"] / 0.62
    narrow_fraction = narrow["front_depth"] / 0.34

    assert narrow["retreat_depth"] > roomy["retreat_depth"]
    assert narrow_fraction < roomy_fraction
    assert narrow["front_depth"] >= narrow["retained_band_floor"]
    assert narrow["no_contact_gap"] > 0.0


def test_synthetic_blob_and_inward_liquid_react_together_without_center_contact() -> None:
    synthetic_frames = [
        dict(bass=0.08, mid=0.06, high=0.04, overall=0.06, smoothed=0.08, transient=0.02),
        dict(bass=0.24, mid=0.20, high=0.10, overall=0.18, smoothed=0.22, transient=0.08),
        dict(bass=0.52, mid=0.46, high=0.18, overall=0.40, smoothed=0.48, transient=0.18),
        dict(bass=0.82, mid=0.74, high=0.30, overall=0.72, smoothed=0.78, transient=0.42),
        dict(bass=0.44, mid=0.54, high=0.26, overall=0.48, smoothed=0.56, transient=0.16),
        dict(bass=0.18, mid=0.16, high=0.08, overall=0.14, smoothed=0.16, transient=0.04),
    ]

    radius_series: list[float] = []
    inward_series: list[float] = []
    gap_series: list[float] = []

    for idx, frame in enumerate(synthetic_frames):
        stage1_t, stage2_t, stage3_t = compute_stage_progress(
            bass_energy=frame["bass"],
            mid_energy=frame["mid"],
            high_energy=frame["high"],
            overall_energy=frame["overall"],
            smoothed_energy=frame["smoothed"],
        )
        radius = compute_blob_radius_preview(
            blob_size=1.0,
            blob_pulse=1.0,
            bass_energy=frame["bass"],
            mid_energy=frame["mid"],
            high_energy=frame["high"],
            overall_energy=frame["overall"],
            smoothed_energy=frame["smoothed"],
            stage_gain=1.0,
            core_scale=1.0,
        )
        profile = compute_inward_liquid_profile(
            angle_frac=0.33,
            time_seconds=idx * 0.16,
            local_radius=radius,
            local_depth=0.012,
            bass_energy=frame["bass"],
            mid_energy=frame["mid"],
            high_energy=frame["high"],
            overall_energy=frame["overall"],
            smoothed_energy=frame["smoothed"],
            stage1_t=stage1_t,
            stage2_t=stage2_t,
            stage3_t=stage3_t,
            transient_energy=frame["transient"],
            reactivity=1.2,
            max_size=0.33,
        )
        radius_series.append(radius)
        inward_series.append(profile["front_depth"])
        gap_series.append(profile["no_contact_gap"])

    radius_peak_index = max(range(len(radius_series)), key=radius_series.__getitem__)
    inward_peak_index = max(range(len(inward_series)), key=inward_series.__getitem__)

    assert abs(radius_peak_index - inward_peak_index) <= 1
    assert inward_series[radius_peak_index] > inward_series[0]
    assert all(gap > 0.0 for gap in gap_series)
    assert min(gap_series) > 0.20


def test_inward_liquid_retreats_more_when_body_pressure_rises_at_same_size_cap() -> None:
    """Extra stage/transient pressure should make the inner front yield sooner."""
    baseline = compute_inward_liquid_profile(
        angle_frac=0.27,
        time_seconds=1.6,
        local_radius=0.33,
        local_depth=0.010,
        bass_energy=0.62,
        mid_energy=0.54,
        high_energy=0.20,
        overall_energy=0.50,
        smoothed_energy=0.58,
        stage1_t=0.18,
        stage2_t=0.08,
        stage3_t=0.02,
        transient_energy=0.04,
        reactivity=1.30,
        max_size=0.36,
    )
    threatened = compute_inward_liquid_profile(
        angle_frac=0.27,
        time_seconds=1.6,
        local_radius=0.33,
        local_depth=0.010,
        bass_energy=0.62,
        mid_energy=0.54,
        high_energy=0.20,
        overall_energy=0.50,
        smoothed_energy=0.58,
        stage1_t=0.94,
        stage2_t=0.82,
        stage3_t=0.66,
        transient_energy=0.38,
        reactivity=1.30,
        max_size=0.36,
    )

    assert abs(threatened["advance_drive"] - baseline["advance_drive"]) < 0.01
    assert threatened["retreat_depth"] > baseline["retreat_depth"]
    assert threatened["front_depth"] <= baseline["front_depth"]
    assert threatened["front_depth"] >= threatened["retained_band_floor"]
    assert baseline["front_depth"] >= baseline["retained_band_floor"]
    assert threatened["no_contact_gap"] >= baseline["no_contact_gap"]
    assert threatened["no_contact_gap"] > 0.0


def test_inward_liquid_retreat_never_collapses_the_retained_band() -> None:
    hot = compute_inward_liquid_profile(
        angle_frac=0.41,
        time_seconds=2.3,
        local_radius=0.24,
        local_depth=0.009,
        bass_energy=1.0,
        mid_energy=0.82,
        high_energy=0.36,
        overall_energy=0.88,
        smoothed_energy=0.96,
        stage1_t=1.0,
        stage2_t=1.0,
        stage3_t=0.94,
        transient_energy=0.44,
        reactivity=1.45,
        max_size=0.38,
    )

    assert hot["retreat_depth"] > 0.0
    assert hot["front_depth"] >= hot["retained_band_floor"]
    assert hot["mix"] > 0.10
    assert hot["no_contact_gap"] > 0.0


def test_synthetic_phrase_yields_under_pressure_then_relaxes_without_contact() -> None:
    """A musical rise/release should show fluid retreat first, then smooth relaxation."""
    synthetic_frames = [
        dict(bass=0.10, mid=0.08, high=0.05, overall=0.08, smoothed=0.10, transient=0.02),
        dict(bass=0.28, mid=0.24, high=0.10, overall=0.22, smoothed=0.26, transient=0.08),
        dict(bass=0.58, mid=0.50, high=0.18, overall=0.44, smoothed=0.52, transient=0.20),
        dict(bass=0.88, mid=0.78, high=0.32, overall=0.76, smoothed=0.82, transient=0.48),
        dict(bass=0.62, mid=0.68, high=0.28, overall=0.58, smoothed=0.66, transient=0.16),
        dict(bass=0.26, mid=0.22, high=0.10, overall=0.18, smoothed=0.22, transient=0.04),
    ]

    retreat_series: list[float] = []
    depth_series: list[float] = []
    gap_series: list[float] = []
    redistribution_series: list[float] = []

    for idx, frame in enumerate(synthetic_frames):
        stage1_t, stage2_t, stage3_t = compute_stage_progress(
            bass_energy=frame["bass"],
            mid_energy=frame["mid"],
            high_energy=frame["high"],
            overall_energy=frame["overall"],
            smoothed_energy=frame["smoothed"],
        )
        radius = compute_blob_radius_preview(
            blob_size=1.0,
            blob_pulse=1.0,
            bass_energy=frame["bass"],
            mid_energy=frame["mid"],
            high_energy=frame["high"],
            overall_energy=frame["overall"],
            smoothed_energy=frame["smoothed"],
            stage_gain=1.0,
            core_scale=1.0,
        )
        profile = compute_inward_liquid_profile(
            angle_frac=0.31,
            time_seconds=idx * 0.15,
            local_radius=radius,
            local_depth=0.010,
            bass_energy=frame["bass"],
            mid_energy=frame["mid"],
            high_energy=frame["high"],
            overall_energy=frame["overall"],
            smoothed_energy=frame["smoothed"],
            stage1_t=stage1_t,
            stage2_t=stage2_t,
            stage3_t=stage3_t,
            transient_energy=frame["transient"],
            reactivity=1.25,
            max_size=0.34,
        )
        retreat_series.append(profile["retreat_depth"])
        depth_series.append(profile["front_depth"])
        gap_series.append(profile["no_contact_gap"])
        redistribution_series.append(abs(profile["redistribution"]))

    peak_index = max(range(len(retreat_series)), key=retreat_series.__getitem__)
    assert peak_index == 3
    assert retreat_series[3] > retreat_series[2]
    assert retreat_series[4] < retreat_series[3]
    assert retreat_series[5] < retreat_series[4]
    assert depth_series[4] > depth_series[1]
    assert depth_series[4] < depth_series[3]
    assert depth_series[5] < depth_series[4]
    assert all(gap > 0.0 for gap in gap_series)
    assert min(gap_series) > 0.20
    assert max(redistribution_series) > 0.0
