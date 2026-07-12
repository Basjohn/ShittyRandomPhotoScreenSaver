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

_MIGHTY_SOLVER_N = 64
_TRANSPORT_N = 128


def _resample_cyclic_profile(values: Sequence[float], count: int) -> list[float]:
    """Linearly resample an already smooth cyclic solver profile for transport."""

    source = [float(value) for value in values]
    if not source or count <= 0:
        return []
    if len(source) == count:
        return source
    result: list[float] = []
    for idx in range(count):
        source_pos = idx * len(source) / count
        left = int(math.floor(source_pos)) % len(source)
        right = (left + 1) % len(source)
        t = source_pos - math.floor(source_pos)
        result.append(source[left] + (source[right] - source[left]) * t)
    return result


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
    runtime_ts = getattr(s, "_blob_runtime_time", None)
    if runtime_ts is None:
        current_ts = time.monotonic()
    else:
        current_ts = max(0.0, float(runtime_ts))
    previous_ts = float(getattr(s, "_blob_unshaped_solver_ts", 0.0) or 0.0)
    dt = current_ts - previous_ts if previous_ts > 0.0 else (1.0 / 60.0)
    dt = max(1.0 / 240.0, min(0.05, dt))

    seed = getattr(s, "_blob_unshaped_solver_seed", None)
    if seed is None:
        epoch = int(getattr(s, "_blob_variant_epoch", 0) or 0)
        seed = (
            ((id(s) % 8191) / 8191.0) * math.tau
            + epoch * 2.399963229728653
        ) % math.tau
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
        previous_profile=getattr(s, "_blob_unshaped_solver_profile", None),
        previous_velocity=getattr(s, "_blob_unshaped_solver_velocity", None),
        previous_target_profile=getattr(s, "_blob_unshaped_solver_target_profile", None),
        sample_count=_MIGHTY_SOLVER_N,
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
    transport_base = _resample_cyclic_profile(base_profile, _TRANSPORT_N)
    transport_raw_target = _resample_cyclic_profile(raw_target_profile, _TRANSPORT_N)
    transport_target = _resample_cyclic_profile(target_profile, _TRANSPORT_N)
    transport_profile = _resample_cyclic_profile(solved_profile, _TRANSPORT_N)
    setattr(s, "_blob_unshaped_solver_profile", list(solved_profile))
    setattr(s, "_blob_unshaped_solver_velocity", list(solved_velocity))
    setattr(s, "_blob_unshaped_solver_target_profile", list(target_profile))
    setattr(s, "_blob_unshaped_base_profile", transport_base)
    setattr(s, "_blob_unshaped_raw_target_profile", transport_raw_target)
    setattr(s, "_blob_unshaped_runtime_target_profile", transport_target)
    setattr(s, "_blob_unshaped_runtime_profile", transport_profile)
    setattr(s, "_blob_unshaped_runtime_velocity", _resample_cyclic_profile(solved_velocity, _TRANSPORT_N))
    setattr(s, "_blob_unshaped_solver_ts", current_ts)
    return transport_profile
