"""Procedural unshaped Blob runtime helpers.

Unshaped Blob is intentionally split from Blob Shaper so we can push toward a
stronger fluid body contract without compromising the authored-contour runtime.
"""
from __future__ import annotations

import math
import time
from typing import Sequence

from widgets.spotify_visualizer.blob_math import (
    compute_stage_progress,
    solve_unshaped_blob_profile_step,
)

_SHAPER_N = 64


def _resolve_runtime_unshaped_profile(
    s,
    *,
    pocket_data: Sequence[Sequence[float]],
    pocket_mix: Sequence[Sequence[float]],
    bass: float,
    mid: float,
    high: float,
    overall: float,
) -> list[float]:
    current_ts = float(getattr(s, "_last_update_ts", 0.0) or 0.0)
    if current_ts <= 0.0:
        current_ts = time.monotonic()
    previous_ts = float(getattr(s, "_blob_unshaped_solver_ts", 0.0) or 0.0)
    dt = current_ts - previous_ts if previous_ts > 0.0 else (1.0 / 60.0)
    dt = max(1.0 / 240.0, min(0.05, dt))

    seed = getattr(s, "_blob_unshaped_solver_seed", None)
    if seed is None:
        seed = ((id(s) % 8191) / 8191.0) * math.tau
        setattr(s, "_blob_unshaped_solver_seed", seed)

    stage1_t, stage2_t, stage3_t = compute_stage_progress(
        bass_energy=bass,
        mid_energy=mid,
        high_energy=high,
        overall_energy=overall,
        smoothed_energy=float(getattr(s, "_blob_smoothed_energy", overall)),
        stage_bias=float(getattr(s, "_blob_stage_bias", 0.0)),
    )
    if getattr(s, "_blob_stage_progress_ready", False):
        override = getattr(s, "_blob_stage_progress_filtered", None)
        if override and len(override) >= 3:
            stage1_t = float(override[0])
            stage2_t = float(override[1])
            stage3_t = float(override[2])

    profile_bundle, solved_velocity = solve_unshaped_blob_profile_step(
        previous_profile=getattr(s, "_blob_unshaped_runtime_profile", None),
        previous_velocity=getattr(s, "_blob_unshaped_runtime_velocity", None),
        previous_target_profile=getattr(s, "_blob_unshaped_runtime_target_profile", None),
        sample_count=_SHAPER_N,
        time_seconds=current_ts,
        dt=dt,
        bass_energy=bass,
        mid_energy=mid,
        high_energy=high,
        overall_energy=overall,
        smoothed_energy=float(getattr(s, "_blob_smoothed_energy", overall)),
        reactive_deformation=float(getattr(s, "_blob_reactive_deformation", 1.0)),
        constant_wobble=float(getattr(s, "_blob_constant_wobble", 1.0)),
        reactive_wobble=float(getattr(s, "_blob_reactive_wobble", 1.0)),
        stretch_tendency=float(getattr(s, "_blob_stretch_tendency", 0.35)),
        stretch_inner=float(getattr(s, "_blob_stretch_inner", 0.0)),
        stretch_outer=float(getattr(s, "_blob_stretch_outer", 0.35)),
        core_floor_bias=float(getattr(s, "_blob_core_floor_bias", 0.0)),
        stage1_t=stage1_t,
        stage2_t=stage2_t,
        stage3_t=stage3_t,
        pockets=pocket_data,
        pocket_mix=pocket_mix,
        playing=bool(getattr(s, "_playing", False)),
        seed=float(seed),
    )
    base_profile, raw_target_profile, target_profile, solved_profile = profile_bundle
    setattr(s, "_blob_unshaped_base_profile", list(base_profile))
    setattr(s, "_blob_unshaped_raw_target_profile", list(raw_target_profile))
    setattr(s, "_blob_unshaped_runtime_target_profile", list(target_profile))
    setattr(s, "_blob_unshaped_runtime_profile", list(solved_profile))
    setattr(s, "_blob_unshaped_runtime_velocity", list(solved_velocity))
    setattr(s, "_blob_unshaped_solver_ts", current_ts)
    return list(solved_profile)
