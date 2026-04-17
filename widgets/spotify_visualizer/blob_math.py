"""Shared math helpers for blob visualizer radius calculations."""
from __future__ import annotations

import math
from typing import Sequence

from widgets.spotify_visualizer.blob_shaper_solver import (
    build_contour_residual_profile,
    solve_profile_step,
    slew_profile_toward_target,
)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0
    t = _clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def compute_unshaped_organic_base_multiplier(
    *,
    angle_frac: float,
    time_seconds: float,
    smoothed_energy: float,
    overall_energy: float,
) -> float:
    """Return the seam-safe base-shape multiplier for unshaped Blob.

    This is intentionally periodic-by-construction: it works from wrapped angle
    fractions and integer harmonics only, so the left-edge wrap cannot tear.
    The goal is a gel/liquid body language with broad valleys and protrusions,
    not a circular core with late star-like spikes glued onto it.
    """

    angle = (float(angle_frac) % 1.0) * math.tau
    slow_t = float(time_seconds) * 0.12
    se = _clamp(smoothed_energy, 0.0, 1.0)
    overall = _clamp(overall_energy, 0.0, 1.0)
    drift = 0.62 + se * 0.30 + overall * 0.16

    shape = 1.0
    # Broad liquid body language: low harmonics only, phase-shifted so the
    # body breathes as one form rather than reading as radial teeth.
    shape += math.cos(angle * 1.0 + slow_t * 0.41 + 0.70) * 0.082
    shape += math.cos(angle * 2.0 - slow_t * 0.29 + 1.85) * 0.050
    shape += math.cos(angle * 3.0 + slow_t * 0.23 + 3.05) * 0.024
    # A slower asymmetry term keeps the body from settling into a repeated,
    # evenly-balanced clover shape while remaining fully periodic.
    shape += math.cos(angle * 1.0 - slow_t * 0.17 + 2.45) * 0.030 * drift
    shape += math.cos(angle * 2.0 + slow_t * 0.11 + 0.25) * 0.022 * drift

    return _clamp(shape, 0.80, 1.24)


def compute_unshaped_motion_offsets(
    *,
    angle_frac: float,
    time_seconds: float,
    bass_energy: float,
    mid_energy: float,
    high_energy: float,
    overall_energy: float,
    smoothed_energy: float,
    reactive_deformation: float,
    constant_wobble: float,
    reactive_wobble: float,
    stretch_tendency: float,
    stretch_inner: float,
    stretch_outer: float,
    pocket_component: float = 0.0,
) -> tuple[float, float]:
    """Return unshaped Blob stretch and wobble offsets in radius units.

    The motion system is intentionally low-frequency and biased toward rounded
    gel-like follow-through. Stretch should steer the existing organic body and
    pockets should locally enrich it, not turn the silhouette back into radial
    teeth.
    """

    angle = (float(angle_frac) % 1.0) * math.tau
    time_value = float(time_seconds)
    e_bass = _clamp(bass_energy, 0.0, 1.0)
    e_mid = _clamp(mid_energy, 0.0, 1.0)
    e_high = _clamp(high_energy, 0.0, 1.0)
    e_overall = _clamp(overall_energy, 0.0, 1.0)
    se = _clamp(smoothed_energy, 0.0, 1.0)
    rd = _clamp(reactive_deformation, 0.0, 3.0)
    cw = _clamp(constant_wobble, 0.0, 2.0)
    rw = _clamp(reactive_wobble, 0.0, 3.0)
    st = _clamp(stretch_tendency, 0.0, 1.0)
    s_inner = _clamp(stretch_inner, 0.0, 1.0)
    s_outer = _clamp(stretch_outer, 0.0, 1.0)

    base_mult = compute_unshaped_organic_base_multiplier(
        angle_frac=angle_frac,
        time_seconds=time_seconds,
        smoothed_energy=smoothed_energy,
        overall_energy=overall_energy,
    )
    base_bias = _clamp((base_mult - 1.0) / 0.16, -1.0, 1.0)

    slow_sway = 0.0
    slow_sway += math.sin(angle * 1.0 + time_value * 0.20 + 0.25) * 0.024
    slow_sway += math.sin(angle * 2.0 - time_value * 0.34 + 1.05) * 0.014
    slow_sway += math.sin(angle * 3.0 + time_value * 0.27 + 2.10) * 0.007
    slow_sway *= 1.0 - abs(base_bias) * 0.18

    reactive_mid = _clamp(e_mid * 0.92 + e_overall * 0.08, 0.0, 1.0)
    reactive_high = _clamp(e_high * 0.82 + e_mid * 0.12, 0.0, 1.0)
    vocal = _clamp(e_mid * 1.02 + e_high * 0.18, 0.0, 1.0)

    reactive_sway = 0.0
    reactive_sway += math.sin(angle * 1.0 + time_value * 0.48 + 0.30) * 0.050 * vocal
    reactive_sway += math.sin(angle * 2.0 - time_value * 0.56 + 1.80) * 0.034 * reactive_mid
    reactive_sway += math.sin(angle * 3.0 + time_value * 0.44 + 2.55) * 0.014 * reactive_high
    reactive_sway += base_bias * vocal * 0.020

    wobble_component = slow_sway * cw + reactive_sway * rw

    pocket_pressure = _clamp(pocket_component, 0.0, 1.8)
    pocket_soft = 1.0 - math.exp(-pocket_pressure * 0.92)
    pocket_shoulder = pocket_soft * (1.0 - pocket_soft * 0.24)

    stretch_component = 0.0
    if st > 0.01:
        vocal_impact = _clamp(e_mid * 1.02 + e_high * 0.20 + se * 0.10, 0.0, 1.0)
        bass_support = _clamp(e_bass * 0.18 + e_overall * 0.14, 0.0, 1.0)
        impact = _clamp(vocal_impact * 0.84 + bass_support * 0.24, 0.0, 1.0)
        impact2 = impact * impact
        impact3 = impact2 * impact

        stretch = 0.0
        stretch += math.sin(angle * 1.0 + time_value * 0.16 + 0.95) * impact2 * 0.142
        stretch += math.sin(angle * 2.0 - time_value * 0.31 + 2.20) * impact3 * 0.104
        stretch += base_bias * impact2 * 0.082
        stretch += base_bias * max(0.0, vocal_impact - 0.18) * 0.044
        stretch += pocket_shoulder * 0.236
        stretch += pocket_soft * max(0.0, 0.35 - abs(base_bias)) * 0.044
        stretch_component = stretch * st

    wobble_component += pocket_shoulder * 0.030
    wobble_component += pocket_soft * base_bias * 0.016

    rd_scale = rd if rd <= 1.0 else 1.0 + (rd - 1.0) ** 3 * 4.0 + (rd - 1.0) * 2.0
    wobble_component *= rd_scale
    stretch_component *= rd_scale

    if stretch_component < 0.0:
        stretch_component *= 0.14 + s_inner * 0.74
    else:
        stretch_component *= 0.28 + s_outer * 1.38

    return (stretch_component, wobble_component)


def compute_unshaped_radius_multiplier(
    *,
    angle_frac: float,
    time_seconds: float,
    bass_energy: float,
    mid_energy: float,
    high_energy: float,
    overall_energy: float,
    smoothed_energy: float,
    reactive_deformation: float,
    constant_wobble: float,
    reactive_wobble: float,
    stretch_tendency: float,
    stretch_inner: float,
    stretch_outer: float,
    core_floor_bias: float,
    stage1_t: float,
    stage2_t: float,
    stage3_t: float,
    pocket_component: float = 0.0,
) -> float:
    """Return the final unshaped radius multiplier relative to staged radius."""

    body_mult = compute_unshaped_organic_base_multiplier(
        angle_frac=angle_frac,
        time_seconds=time_seconds,
        smoothed_energy=smoothed_energy,
        overall_energy=overall_energy,
    )
    stretch_component, wobble_component = compute_unshaped_motion_offsets(
        angle_frac=angle_frac,
        time_seconds=time_seconds,
        bass_energy=bass_energy,
        mid_energy=mid_energy,
        high_energy=high_energy,
        overall_energy=overall_energy,
        smoothed_energy=smoothed_energy,
        reactive_deformation=reactive_deformation,
        constant_wobble=constant_wobble,
        reactive_wobble=reactive_wobble,
        stretch_tendency=stretch_tendency,
        stretch_inner=stretch_inner,
        stretch_outer=stretch_outer,
        pocket_component=pocket_component,
    )
    stage_floor = compute_stage_floor_fraction(
        core_floor_bias=core_floor_bias,
        stage1_t=stage1_t,
        stage2_t=stage2_t,
        stage3_t=stage3_t,
    )
    min_radius_mult = max(0.74, body_mult * max(stage_floor, 0.76))
    stretch_floor = min(min_radius_mult - body_mult, 0.0)
    stretch_component = max(stretch_component, stretch_floor)
    core_mult = body_mult + stretch_component
    fluid_floor = _clamp(0.72 + stage1_t * 0.05 + max(0.0, body_mult - 1.0) * 0.04, 0.72, 0.84)
    final_mult = max(core_mult + wobble_component, core_mult * fluid_floor)
    final_mult = max(final_mult, max(0.74, body_mult * 0.80))
    return final_mult


def compute_blob_pocket_component(
    *,
    angle_frac: float,
    time_seconds: float,
    bass_energy: float,
    mid_energy: float,
    high_energy: float,
    overall_energy: float,
    smoothed_energy: float,
    pockets: Sequence[Sequence[float]] | None = None,
    pocket_mix: Sequence[Sequence[float]] | None = None,
) -> float:
    """Mirror the shader pocket component for CPU contour solving/tests."""

    if not pockets or not pocket_mix:
        return 0.0

    if pockets and isinstance(pockets[0], (int, float)):
        flat_pockets = list(float(v) for v in pockets)
        pockets = [flat_pockets[idx:idx + 4] for idx in range(0, len(flat_pockets), 4)]
    if pocket_mix and isinstance(pocket_mix[0], (int, float)):
        flat_mix = list(float(v) for v in pocket_mix)
        pocket_mix = [flat_mix[idx:idx + 4] for idx in range(0, len(flat_mix), 4)]

    angle = float(angle_frac) % 1.0
    time_value = float(time_seconds)
    bass = _clamp(bass_energy, 0.0, 1.0)
    mid = _clamp(mid_energy, 0.0, 1.0)
    high = _clamp(high_energy, 0.0, 1.0)
    overall = _clamp(overall_energy, 0.0, 1.0)
    smoothed = _clamp(smoothed_energy, 0.0, 1.0)

    total = 0.0
    for idx, pocket in enumerate(pockets):
        if idx >= len(pocket_mix) or len(pocket) < 4 or len(pocket_mix[idx]) < 4:
            continue
        center = float(pocket[0]) % 1.0
        amplitude = max(0.0, float(pocket[1]))
        if amplitude <= 0.001:
            continue
        width = max(0.05, float(pocket[2]))
        phase = float(pocket[3])
        diff = abs(angle - center)
        diff = min(diff, 1.0 - diff)
        diff_norm = _clamp(diff / max(width, 0.001), 0.0, 1.0)
        lobe = 1.0 - _smoothstep(0.18, 1.0, diff_norm)
        lobe *= lobe
        if lobe <= 0.0:
            continue
        mixv = pocket_mix[idx]
        drive = _clamp(
            bass * float(mixv[0])
            + mid * float(mixv[1])
            + high * float(mixv[2])
            + smoothed * float(mixv[3])
            + overall * 0.10,
            0.0,
            1.8,
        )
        pocket_age = max(0.0, time_value - phase)
        attack_boost = 1.0 + 0.42 * math.exp(-pocket_age / 0.085)
        ripple_phase = pocket_age * 12.0 + diff_norm * 2.0 + float(idx) * 0.7
        ripple = 0.94 + 0.06 * math.sin(ripple_phase)
        shoulder_fill = 1.0 - diff_norm * 0.26
        total += amplitude * drive * lobe * ripple * attack_boost * shoulder_fill
    return total


def _fit_profile_inside_containment(
    profile: Sequence[float],
    *,
    min_allowed: float,
    max_allowed: float,
    center: float = 1.0,
) -> list[float]:
    """Compress contour deviation into a safe envelope without flattening it."""

    if not profile:
        return []
    min_allowed = min(float(min_allowed), float(center))
    max_allowed = max(float(max_allowed), float(center))
    peak_above = max(max(float(v) - center, 0.0) for v in profile)
    peak_below = max(max(center - float(v), 0.0) for v in profile)
    above_cap = max_allowed - center
    below_cap = center - min_allowed
    scale = 1.0
    if peak_above > 1e-6:
        scale = min(scale, above_cap / peak_above)
    if peak_below > 1e-6:
        scale = min(scale, below_cap / peak_below)
    scale = _clamp(scale, 0.0, 1.0)
    return [_clamp(center + (float(v) - center) * scale, min_allowed, max_allowed) for v in profile]


def build_unshaped_blob_target_profile(
    *,
    sample_count: int,
    time_seconds: float,
    bass_energy: float,
    mid_energy: float,
    high_energy: float,
    overall_energy: float,
    smoothed_energy: float,
    reactive_deformation: float,
    constant_wobble: float,
    reactive_wobble: float,
    stretch_tendency: float,
    stretch_inner: float,
    stretch_outer: float,
    core_floor_bias: float,
    stage1_t: float,
    stage2_t: float,
    stage3_t: float,
    pockets: Sequence[Sequence[float]] | None = None,
    pocket_mix: Sequence[Sequence[float]] | None = None,
    playing: bool = True,
    seed: float = 0.0,
) -> tuple[list[float], list[float], list[float]]:
    """Build the procedural unshaped contour family in profile space.

    Returns ``(base_profile, target_profile, bounded_target_profile)``.
    """

    count = max(0, int(sample_count))
    if count <= 0:
        return ([], [], [])

    time_value = float(time_seconds)
    bass = _clamp(bass_energy, 0.0, 1.0)
    mid = _clamp(mid_energy, 0.0, 1.0)
    high = _clamp(high_energy, 0.0, 1.0)
    overall = _clamp(overall_energy, 0.0, 1.0)
    smoothed = _clamp(smoothed_energy, 0.0, 1.0)
    stage_floor = compute_stage_floor_fraction(
        core_floor_bias=core_floor_bias,
        stage1_t=stage1_t,
        stage2_t=stage2_t,
        stage3_t=stage3_t,
    )

    residual = build_contour_residual_profile(
        sample_count=count,
        time_value=time_value,
        idle_motion=0.42,
        audio_motion=1.05,
        overall_energy=overall,
        vocal_energy=_clamp(mid * 0.82 + high * 0.18, 0.0, 1.0),
        high_energy=high,
        playing=playing,
        seed=seed + 0.41,
    )

    base_profile: list[float] = []
    target_profile: list[float] = []
    for idx in range(count):
        angle_frac = idx / count
        base_mult = compute_unshaped_organic_base_multiplier(
            angle_frac=angle_frac,
            time_seconds=time_value,
            smoothed_energy=smoothed,
            overall_energy=overall,
        )
        pocket_component = compute_blob_pocket_component(
            angle_frac=angle_frac,
            time_seconds=time_value,
            bass_energy=bass,
            mid_energy=mid,
            high_energy=high,
            overall_energy=overall,
            smoothed_energy=smoothed,
            pockets=pockets,
            pocket_mix=pocket_mix,
        )
        final_mult = compute_unshaped_radius_multiplier(
            angle_frac=angle_frac,
            time_seconds=time_value,
            bass_energy=bass,
            mid_energy=mid,
            high_energy=high,
            overall_energy=overall,
            smoothed_energy=smoothed,
            reactive_deformation=reactive_deformation,
            constant_wobble=constant_wobble,
            reactive_wobble=reactive_wobble,
            stretch_tendency=stretch_tendency,
            stretch_inner=stretch_inner,
            stretch_outer=stretch_outer,
            core_floor_bias=core_floor_bias,
            stage1_t=stage1_t,
            stage2_t=stage2_t,
            stage3_t=stage3_t,
            pocket_component=pocket_component,
        )
        base_profile.append(base_mult)
        target_profile.append(final_mult + residual[idx])

    # Give the solved contour more authority over the silhouette while keeping
    # it card-contained. The body should read as contour pressure, not as a
    # nearly circular scalar radius with small decoration layered on top.
    min_allowed = max(0.48, stage_floor * 0.78, min(base_profile) * 0.66)
    max_allowed = min(1.38, 1.16 + stage1_t * 0.090 + stage2_t * 0.110 + stage3_t * 0.136)
    bounded = _fit_profile_inside_containment(
        target_profile,
        min_allowed=min_allowed,
        max_allowed=max_allowed,
        center=1.0,
    )
    return (base_profile, target_profile, bounded)


def solve_unshaped_blob_profile_step(
    *,
    previous_profile: Sequence[float] | None,
    previous_velocity: Sequence[float] | None,
    previous_target_profile: Sequence[float] | None,
    sample_count: int,
    time_seconds: float,
    dt: float,
    bass_energy: float,
    mid_energy: float,
    high_energy: float,
    overall_energy: float,
    smoothed_energy: float,
    reactive_deformation: float,
    constant_wobble: float,
    reactive_wobble: float,
    stretch_tendency: float,
    stretch_inner: float,
    stretch_outer: float,
    core_floor_bias: float,
    stage1_t: float,
    stage2_t: float,
    stage3_t: float,
    pockets: Sequence[Sequence[float]] | None = None,
    pocket_mix: Sequence[Sequence[float]] | None = None,
    playing: bool = True,
    seed: float = 0.0,
) -> tuple[list[float], list[float], list[float], list[float]]:
    """Advance the procedural unshaped contour through the shared contour solver."""

    base_profile, raw_target_profile, bounded_target_profile = build_unshaped_blob_target_profile(
        sample_count=sample_count,
        time_seconds=time_seconds,
        bass_energy=bass_energy,
        mid_energy=mid_energy,
        high_energy=high_energy,
        overall_energy=overall_energy,
        smoothed_energy=smoothed_energy,
        reactive_deformation=reactive_deformation,
        constant_wobble=constant_wobble,
        reactive_wobble=reactive_wobble,
        stretch_tendency=stretch_tendency,
        stretch_inner=stretch_inner,
        stretch_outer=stretch_outer,
        core_floor_bias=core_floor_bias,
        stage1_t=stage1_t,
        stage2_t=stage2_t,
        stage3_t=stage3_t,
        pockets=pockets,
        pocket_mix=pocket_mix,
        playing=playing,
        seed=seed,
    )
    count = len(base_profile)
    if count <= 0:
        return ([], [], [], [])

    target_profile = slew_profile_toward_target(
        previous_target=previous_target_profile,
        current_target=bounded_target_profile,
        base_profile=base_profile,
        dt=dt,
        attack_hz=13.5 if playing else 8.0,
        release_hz=3.2 if playing else 2.2,
    )
    current_profile = list(previous_profile or ())
    current_velocity = list(previous_velocity or ())
    if len(current_profile) != count:
        current_profile = list(base_profile)
    if len(current_velocity) != count:
        current_velocity = [0.0] * count

    min_profile = [
        max(0.48, base_profile[idx] * 0.66, stage_floor if (stage_floor := compute_stage_floor_fraction(
            core_floor_bias=core_floor_bias,
            stage1_t=stage1_t,
            stage2_t=stage2_t,
            stage3_t=stage3_t,
        )) else 0.60)
        for idx in range(count)
    ]
    max_profile = [min(1.38, max(base_profile[idx] + 0.36, target_profile[idx] + 0.24)) for idx in range(count)]
    solved_profile, solved_velocity = solve_profile_step(
        current_profile=current_profile,
        current_velocity=current_velocity,
        target_profile=target_profile,
        min_profile=min_profile,
        max_profile=max_profile,
        dt=dt,
        stiffness=19.0 if playing else 13.0,
        damping=7.2 if playing else 10.8,
        neighbor_strength=12.6 if playing else 9.8,
        smoothing_passes=2 if playing else 2,
    )
    solved_profile = _fit_profile_inside_containment(
        solved_profile,
        min_allowed=min(min_profile),
        max_allowed=max(max_profile),
        center=1.0,
    )
    return (base_profile, raw_target_profile, target_profile, solved_profile), solved_velocity


def compute_inward_liquid_profile(
    *,
    edge_distance: float,
    blob_clearance: float,
    perimeter_pos: float,
    time_seconds: float,
    bass_energy: float,
    mid_energy: float,
    high_energy: float,
    overall_energy: float,
    smoothed_energy: float,
    stage1_t: float = 0.0,
    stage2_t: float = 0.0,
    stage3_t: float = 0.0,
    transient_energy: float = 0.0,
    reactivity: float = 1.0,
    max_size: float = 0.28,
    ring_mode: bool = False,
    enabled: bool = True,
) -> dict[str, float]:
    """Return the card-edge inward-liquid profile for one perimeter sample.

    This is intentionally *not* a blob-internal tint band.
    The layer represents liquid advancing inward from the visualizer card
    borders while locally retreating when the blob threatens the front.

    Inputs:
    - ``edge_distance``: normalized distance from the current pixel/sample to
      the nearest card edge
    - ``blob_clearance``: normalized distance from the current pixel/sample to
      the blob body (outside-only clearance)
    - ``perimeter_pos``: wrapped 0..1 coordinate traveling around the card

    The profile should:
    - stay visibly alive at rest
    - advance inward under bounded audio pressure
    - retreat locally when blob pressure threatens contact
    - preserve a strict positive gap to the blob
    - never fully collapse while enabled
    """

    edge_d = max(float(edge_distance), 0.0)
    clearance = max(float(blob_clearance), 0.0)
    if not enabled:
        return {
            "front_depth": 0.0,
            "mix": 0.0,
            "advance_drive": 0.0,
            "retreat_depth": 0.0,
            "redistribution": 0.0,
            "retained_front_floor": 0.0,
            "no_contact_gap": clearance,
        }

    angle = (float(perimeter_pos) % 1.0) * math.tau
    time_value = float(time_seconds)
    bass = _clamp(bass_energy, 0.0, 1.0)
    mid = _clamp(mid_energy, 0.0, 1.0)
    high = _clamp(high_energy, 0.0, 1.0)
    overall = _clamp(overall_energy, 0.0, 1.0)
    se = _clamp(smoothed_energy, 0.0, 1.0)
    stage1 = _clamp(stage1_t, 0.0, 1.0)
    stage2 = _clamp(stage2_t, 0.0, 1.0)
    stage3 = _clamp(stage3_t, 0.0, 1.0)
    transient = _clamp(transient_energy, 0.0, 1.0)
    react = _clamp(reactivity, 0.0, 2.0)
    max_fraction = _clamp(max_size, 0.05, 0.45)

    hard_cap = 0.014 + max_fraction * 0.22
    retained_front_floor = max(0.010, hard_cap * (0.22 + max_fraction * 0.08))

    base_drift = 0.18
    base_drift += math.sin(time_value * 0.74 + angle * 1.7) * 0.05
    base_drift += math.sin(time_value * 1.19 - angle * 2.4 + 0.90) * 0.04
    base_drift = _clamp(base_drift, 0.07, 0.36)

    audio_pressure = _clamp(
        se * 0.24 +
        overall * 0.22 +
        mid * 0.20 +
        bass * 0.10 +
        high * 0.08 +
        transient * 0.12,
        0.0,
        1.4,
    )
    pressure_balance = 0.5 + 0.5 * math.sin(time_value * (1.8 + audio_pressure * 1.8) + angle * 3.1)
    tangential_slide = (pressure_balance - 0.5) * (0.10 + 0.08 * min(react, 1.0))

    advance_drive = _clamp(
        base_drift +
        audio_pressure * (0.18 + 0.14 * react) +
        tangential_slide,
        0.06,
        0.92,
    )
    requested_depth = retained_front_floor + hard_cap * advance_drive

    body_pressure = _clamp(
        se * 0.12 +
        overall * 0.10 +
        mid * 0.08 +
        stage1 * 0.12 +
        stage2 * 0.18 +
        stage3 * 0.26 +
        transient * 0.12,
        0.0,
        1.3,
    )
    local_bias = 0.5 + 0.5 * math.sin(time_value * 0.58 - angle * 1.9 + 1.2)
    no_contact_gap = 0.010 + max_fraction * 0.020 + min(react, 1.0) * 0.006 + body_pressure * 0.010
    crowding = 1.0 - _smoothstep(
        no_contact_gap,
        no_contact_gap + requested_depth * 1.35 + 0.015,
        clearance,
    )
    retreat_signal = _clamp(
        body_pressure * (0.30 + 0.28 * local_bias) +
        crowding * (0.82 + 0.14 * react),
        0.0,
        1.4,
    )
    retreat_weight = _smoothstep(0.16, 0.96, retreat_signal)
    retreat_depth = requested_depth * retreat_weight * (0.28 + body_pressure * 0.26)

    redistribution = retreat_weight * (0.03 + 0.05 * audio_pressure) * math.sin(
        time_value * 1.36 + angle * 4.2 - 0.6
    )
    final_depth = requested_depth - retreat_depth + redistribution * hard_cap
    final_depth = _clamp(final_depth, retained_front_floor, hard_cap)

    front_mask = 1.0 - _smoothstep(
        max(final_depth * 0.22, retained_front_floor * 0.60),
        max(final_depth, retained_front_floor + 0.003),
        edge_d,
    )
    source_anchor = 1.0 - _smoothstep(
        0.0,
        max(final_depth * 0.55, retained_front_floor + 0.003),
        edge_d,
    )
    gap_guard = _smoothstep(
        no_contact_gap,
        no_contact_gap + max(final_depth * 0.30, 0.006),
        clearance,
    )
    retained_mix_floor = 0.18 + source_anchor * 0.05
    mix = front_mask * gap_guard * (0.46 + source_anchor * 0.34 + audio_pressure * 0.14)
    mix = max(mix, front_mask * gap_guard * retained_mix_floor)
    mix = _clamp(mix, 0.0, 0.96)

    return {
        "front_depth": final_depth,
        "mix": mix,
        "advance_drive": advance_drive,
        "retreat_depth": retreat_depth,
        "redistribution": redistribution * hard_cap,
        "retained_front_floor": retained_front_floor,
        "no_contact_gap": no_contact_gap,
    }


def _apply_stage_bias_to_drives(
    weighted_stage1: float,
    stage2_drive: float,
    chorus_drive: float,
    stage_bias: float,
) -> tuple[float, float, float]:
    """Apply Blob stage bias as a pre-smooth drive nudge, not a blunt cutoff.

    Negative bias should make stages harder to enter, but it should not erase
    modest valid stage motion by subtracting directly from already-smoothed
    progress values.
    """
    if abs(stage_bias) <= 1e-6:
        return (weighted_stage1, stage2_drive, chorus_drive)
    bias = _clamp(stage_bias, -0.60, 0.60)
    return (
        _clamp(weighted_stage1 + bias * 0.12, 0.0, 1.0),
        _clamp(stage2_drive + bias * 0.10, 0.0, 1.0),
        _clamp(chorus_drive + bias * 0.08, 0.0, 1.0),
    )


def compute_stage_progress(
    *,
    bass_energy: float,
    mid_energy: float,
    high_energy: float,
    overall_energy: float,
    smoothed_energy: float,
    stage_bias: float = 0.0,
) -> tuple[float, float, float]:
    """Return the smoothstep progress for stages 1-3."""

    bass = _clamp(bass_energy, 0.0, 1.0)
    mid = _clamp(mid_energy, 0.0, 1.0)
    high = _clamp(high_energy, 0.0, 1.0)
    overall = _clamp(overall_energy, 0.0, 1.0)
    se = _clamp(smoothed_energy, 0.0, 1.0)

    weighted = _clamp(bass * 0.60 + overall * 0.28 + mid * 0.08 + high * 0.04, 0.0, 1.0)
    # Stage 1 should still feel bass-rooted, but fast snare-rich phrases need a
    # viable first rung instead of reading as "local wobble only" forever.
    stage1_drive = max(
        weighted,
        _clamp(
            overall * 0.62
            + min(mid, overall * 0.50) * 0.16
            + min(high, overall * 0.35) * 0.12,
            0.0,
            1.0,
        ),
    )
    weighted_stage1 = _clamp(stage1_drive * 0.84 + se * 0.16, 0.0, 1.0)
    base_stage2_drive = _clamp(
        weighted * 0.56 + bass * 0.12 + mid * 0.22 + high * 0.10,
        0.0,
        1.0,
    )
    stage2_drive = _clamp(base_stage2_drive * 0.74 + se * 0.26, 0.0, 1.0)
    chorus_drive = _clamp(
        max(stage2_drive, bass * 0.28 + overall * 0.24 + mid * 0.29 + high * 0.19),
        0.0,
        1.0,
    )
    chorus_drive = _clamp(
        max(chorus_drive, se * 0.28 + overall * 0.34 + mid * 0.26 + high * 0.12),
        0.0,
        1.0,
    )

    weighted_stage1, stage2_drive, chorus_drive = _apply_stage_bias_to_drives(
        weighted_stage1,
        stage2_drive,
        chorus_drive,
        stage_bias,
    )
    # Blob should climb a ladder, not park on stage 1 forever.
    # Keep stage 1 reachable on ordinary musical support, but leave room for
    # stage 2/3 to appear on stronger passages instead of making the first rung
    # saturate immediately while the later rungs stay effectively unreachable.
    stage1_t = _smoothstep(0.035, 0.59, weighted_stage1)
    stage2_t = _smoothstep(0.13, 0.54, stage2_drive)
    stage3_t = _smoothstep(0.18, 0.60, chorus_drive)
    stage2_t = min(stage2_t, stage1_t)
    stage3_t = min(stage3_t, stage2_t)
    return (stage1_t, stage2_t, stage3_t)


def compute_stage_floor_fraction(
    *,
    core_floor_bias: float,
    stage1_t: float,
    stage2_t: float,
    stage3_t: float,
) -> float:
    """Return the preserved radius fraction enforced by the core floor clamp."""

    bias = _clamp(core_floor_bias, 0.0, 0.95)
    bias += stage1_t * 0.05
    bias += stage2_t * 0.08
    bias += stage3_t * 0.12
    return _clamp(bias, 0.0, 0.9)


def compute_stage_offset(
    *,
    blob_size: float,
    bass_energy: float,
    mid_energy: float,
    high_energy: float,
    overall_energy: float,
    stage_gain: float,
    core_scale: float,
    smoothed_energy: float,
    stage_bias: float = 0.0,
    stage_progress_override: tuple[float, float, float] | None = None,
) -> float:
    """Return the staged radius boost applied on top of the base blob radius."""

    base_size = _clamp(blob_size, 0.1, 2.5)
    stage_gain = _clamp(stage_gain, 0.0, 2.0)
    core_scale = _clamp(core_scale, 0.25, 2.5)

    if stage_progress_override is not None:
        stage1_t, stage2_t, stage3_t = stage_progress_override
        stage1_t = _clamp(stage1_t, 0.0, 1.0)
        stage2_t = _clamp(stage2_t, 0.0, 1.0)
        stage3_t = _clamp(stage3_t, 0.0, 1.0)
    else:
        stage1_t, stage2_t, stage3_t = compute_stage_progress(
            bass_energy=bass_energy,
            mid_energy=mid_energy,
            high_energy=high_energy,
            overall_energy=overall_energy,
            smoothed_energy=smoothed_energy,
            stage_bias=stage_bias,
        )

    # Keep stage growth secondary to the fluid body language. The blob should
    # not read as "a big pulse that happens to wobble"; stage is support, not
    # the main silhouette author.
    stage_unit = base_size * 0.11 + 0.012
    stage1_amt = stage_unit * 0.70
    stage2_amt = stage_unit * 1.52
    stage3_amt = stage_unit * 2.70

    offset = stage1_t * stage1_amt
    offset += stage2_t * max(0.0, stage2_amt - stage1_amt)
    offset += stage3_t * max(0.0, stage3_amt - stage2_amt)

    return offset * stage_gain * core_scale


def compute_blob_radius_preview(
    *,
    blob_size: float,
    blob_pulse: float,
    bass_energy: float,
    mid_energy: float,
    high_energy: float,
    overall_energy: float,
    smoothed_energy: float,
    stage_gain: float,
    core_scale: float,
) -> float:
    """Mirror the shader radius math for diagnostics/tests."""

    blob_size = _clamp(blob_size, 0.1, 2.5)
    bass = _clamp(bass_energy, 0.0, 1.0)
    blob_pulse = max(0.0, blob_pulse)
    # A calmer baseline leaves room for fluid deformation to imply growth.
    r = 0.285 * blob_size
    r += bass * bass * 0.016 * blob_pulse
    r += bass * 0.018 * blob_pulse
    se = _clamp(smoothed_energy, 0.0, 1.0)
    breath = max(bass, se * 0.82)
    r += max(0.02, breath) * 0.007 * blob_pulse
    r -= (1.0 - se) * 0.010 * blob_pulse
    r += compute_stage_offset(
        blob_size=blob_size,
        bass_energy=bass,
        mid_energy=mid_energy,
        high_energy=high_energy,
        overall_energy=overall_energy,
        stage_gain=stage_gain,
        core_scale=core_scale,
        smoothed_energy=smoothed_energy,
        stage_bias=0.0,
    ) * blob_pulse
    return r


def compute_blob_ghost_min_offset(smoothed_energy: float) -> float:
    """Return the minimum ghost peak offset above the live blob state.

    The ghost should stay visible, but it should not dominate the live blob
    shape or look like the "real" blob on calmer passages.
    """
    se = _clamp(smoothed_energy, 0.0, 1.0)
    return _clamp(max(0.015, se * 0.035), 0.015, 0.035)
