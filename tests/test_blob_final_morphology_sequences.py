"""Final-profile oracles for musical Blob morphology rather than helper motion."""
from __future__ import annotations

import json
import math
from pathlib import Path

from widgets.spotify_visualizer.blob_math import solve_unshaped_blob_profile_step
from widgets.spotify_visualizer.renderers.blob_shaper_runtime import (
    _build_energy_routing,
    _resample_nodes,
    _solve_runtime_shaper_profile_step,
)


def _centered_rms_delta(left: list[float], right: list[float]) -> tuple[float, float, float]:
    deltas = [a - b for a, b in zip(left, right)]
    mean_delta = math.fsum(deltas) / len(deltas)
    centered = math.sqrt(
        math.fsum((delta - mean_delta) ** 2 for delta in deltas) / len(deltas)
    )
    raw = math.sqrt(math.fsum(delta * delta for delta in deltas) / len(deltas))
    return centered, abs(mean_delta), raw


def _detail_rms(profile: list[float]) -> float:
    smoothed = [
        math.fsum(profile[(idx + offset) % len(profile)] for offset in range(-4, 5)) / 9.0
        for idx in range(len(profile))
    ]
    return math.sqrt(
        math.fsum((value - smooth) ** 2 for value, smooth in zip(profile, smoothed))
        / len(profile)
    )


def _peak_indices(profile: list[float]) -> set[int]:
    mean = math.fsum(profile) / len(profile)
    rms = math.sqrt(math.fsum((value - mean) ** 2 for value in profile) / len(profile))
    smoothed = [
        math.fsum(profile[(idx + offset) % len(profile)] for offset in (-2, -1, 0, 1, 2)) / 5.0
        for idx in range(len(profile))
    ]
    prominence = max(0.004, rms * 0.10)
    return {
        idx
        for idx, value in enumerate(smoothed)
        if value > smoothed[idx - 1]
        and value >= smoothed[(idx + 1) % len(profile)]
        and value > mean + prominence
    }


def _mighty_sequence() -> dict[str, list[float]]:
    phases = (
        ("quiet", (0.18, 0.16, 0.12, 0.19, 0.18)),
        ("vocal", (0.22, 0.95, 0.55, 0.58, 0.34)),
        ("hit", (1.10, 0.78, 0.88, 0.95, 0.88)),
        ("release", (0.20, 0.18, 0.14, 0.22, 0.24)),
    )
    common = dict(
        sample_count=128,
        reactive_deformation=1.52,
        constant_wobble=0.82,
        reactive_wobble=2.82,
        stretch_tendency=0.94,
        stretch_inner=0.0,
        stretch_outer=0.94,
        core_floor_bias=0.42,
        stage1_t=1.0,
        stage2_t=1.0,
        stage3_t=1.0,
        playing=True,
        seed=0.37,
    )
    profile = velocity = target = None
    captured: dict[str, list[float]] = {}
    step = 0
    for name, (bass, mid, high, overall, smoothed) in phases:
        for _ in range(45):
            bundle, velocity = solve_unshaped_blob_profile_step(
                previous_profile=profile,
                previous_velocity=velocity,
                previous_target_profile=target,
                time_seconds=step / 45.0,
                dt=1.0 / 45.0,
                bass_energy=bass,
                mid_energy=mid,
                high_energy=high,
                overall_energy=overall,
                smoothed_energy=smoothed,
                **common,
            )
            _, _, target, profile = bundle
            step += 1
        captured[name] = list(profile)
    return captured


def _shaped_geometry() -> tuple[list[float], list[float], list[list[float]]]:
    preset_path = (
        Path(__file__).parents[1]
        / "presets"
        / "visualizer_modes"
        / "blob"
        / "preset_7_temp_shaped_warp_garden.json"
    )
    settings = json.loads(preset_path.read_text(encoding="utf-8"))["snapshot"]["widgets"][
        "spotify_visualizer"
    ]
    base = _resample_nodes(settings["blob_shape_base_nodes"], 128)
    reaction = _resample_nodes(settings["blob_shape_reaction_nodes"], 128)
    weights = _build_energy_routing(
        settings["blob_shape_energy_nodes"],
        128,
        base_profile=base,
        react_profile=reaction,
    )
    return base, reaction, weights


def _shaped_sequence() -> dict[str, list[float]]:
    base, reaction, weights = _shaped_geometry()
    phases = (
        ("quiet", (0.18, 0.16, 0.12, 0.19, 0.02)),
        ("vocal", (0.22, 0.95, 0.55, 0.58, 0.08)),
        ("hit", (1.10, 0.78, 0.88, 0.95, 0.90)),
        ("release", (0.20, 0.18, 0.14, 0.22, 0.02)),
    )
    profile = velocity = target = None
    captured: dict[str, list[float]] = {}
    step = 0
    for name, (bass, mid, high, overall, transient) in phases:
        for _ in range(45):
            profile, velocity, target = _solve_runtime_shaper_profile_step(
                base_profile=base,
                react_profile=reaction,
                weights=weights,
                previous_profile=profile,
                previous_velocity=velocity,
                previous_target_profile=target,
                dt=1.0 / 45.0,
                time_value=step / 45.0,
                bass=bass,
                mid=mid,
                high=high,
                overall=overall,
                transient=transient,
                react_strength=0.84,
                shaper_idle_motion=0.68,
                shaper_audio_motion=1.80,
                playing=True,
                base_strength=0.82,
                seed=0.37,
            )
            step += 1
        captured[name] = list(profile)
    return captured


def test_mighty_final_profile_changes_topology_not_just_size() -> None:
    frames = _mighty_sequence()
    quiet, vocal, hit, release = (
        frames["quiet"],
        frames["vocal"],
        frames["hit"],
        frames["release"],
    )
    quiet_vocal = _centered_rms_delta(quiet, vocal)
    vocal_hit = _centered_rms_delta(vocal, hit)
    hit_release = _centered_rms_delta(hit, release)

    assert max(quiet) - min(quiet) > 0.20
    assert quiet_vocal[0] > 0.075
    assert vocal_hit[0] > 0.10
    assert hit_release[0] > 0.065
    assert quiet_vocal[0] > quiet_vocal[1] * 6.0
    assert _detail_rms(vocal) > _detail_rms(quiet) * 2.4
    assert _peak_indices(quiet) != _peak_indices(vocal)
    assert _peak_indices(vocal) != _peak_indices(hit)
    assert max(
        max(frame[idx] for frame in frames.values())
        - min(frame[idx] for frame in frames.values())
        for idx in range(128)
    ) > 0.24


def test_shaped_final_profile_mutates_beyond_authored_goal_and_scalar_growth() -> None:
    frames = _shaped_sequence()
    quiet, vocal, hit, release = (
        frames["quiet"],
        frames["vocal"],
        frames["hit"],
        frames["release"],
    )
    quiet_vocal = _centered_rms_delta(quiet, vocal)
    vocal_hit = _centered_rms_delta(vocal, hit)
    hit_release = _centered_rms_delta(hit, release)

    assert quiet_vocal[0] > 0.12
    assert vocal_hit[0] > 0.11
    assert hit_release[0] > 0.070
    assert quiet_vocal[0] > quiet_vocal[1] * 0.80
    assert vocal_hit[0] > vocal_hit[1] * 1.8
    assert _detail_rms(vocal) > _detail_rms(quiet) * 2.0
    assert _peak_indices(quiet) != _peak_indices(vocal)
    assert _peak_indices(vocal) != _peak_indices(hit)
    assert max(vocal) < 1.95
    assert min(hit) > 0.12


def _settled_vocal_detail(blob_type: str, *, mid: float, high: float) -> float:
    if blob_type == "mighty":
        profile = velocity = target = None
        for idx in range(75):
            bundle, velocity = solve_unshaped_blob_profile_step(
                previous_profile=profile,
                previous_velocity=velocity,
                previous_target_profile=target,
                sample_count=128,
                time_seconds=2.0 + idx / 45.0,
                dt=1.0 / 45.0,
                bass_energy=0.22,
                mid_energy=mid,
                high_energy=high,
                overall_energy=0.58,
                smoothed_energy=0.34,
                reactive_deformation=1.52,
                constant_wobble=0.82,
                reactive_wobble=2.82,
                stretch_tendency=0.94,
                stretch_inner=0.0,
                stretch_outer=0.94,
                core_floor_bias=0.42,
                stage1_t=1.0,
                stage2_t=1.0,
                stage3_t=1.0,
                playing=True,
                seed=0.37,
            )
            _, _, target, profile = bundle
        return _detail_rms(profile)

    base, reaction, weights = _shaped_geometry()
    profile = velocity = target = None
    for idx in range(75):
        profile, velocity, target = _solve_runtime_shaper_profile_step(
            base_profile=base,
            react_profile=reaction,
            weights=weights,
            previous_profile=profile,
            previous_velocity=velocity,
            previous_target_profile=target,
            dt=1.0 / 45.0,
            time_value=2.0 + idx / 45.0,
            bass=0.22,
            mid=mid,
            high=high,
            overall=0.58,
            transient=0.05,
            react_strength=0.84,
            shaper_idle_motion=0.68,
            shaper_audio_motion=1.80,
            playing=True,
            base_strength=0.82,
            seed=0.37,
        )
    return _detail_rms(profile)


def test_vocals_materially_wobble_mighty_final_contour_not_only_glow() -> None:
    quiet_detail = _settled_vocal_detail("mighty", mid=0.12, high=0.10)
    vocal_detail = _settled_vocal_detail("mighty", mid=0.95, high=0.55)

    assert vocal_detail > 0.018
    assert vocal_detail > quiet_detail * 2.8


def test_vocals_materially_wobble_shaped_final_contour_not_only_glow() -> None:
    quiet_detail = _settled_vocal_detail("shaped", mid=0.12, high=0.10)
    vocal_detail = _settled_vocal_detail("shaped", mid=0.95, high=0.55)

    assert vocal_detail > 0.017
    assert vocal_detail > quiet_detail * 2.4
