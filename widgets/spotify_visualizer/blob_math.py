"""Shared math helpers for Blob visualizer radius calculations.

The public ``unshaped`` helper names are retained for compatibility, but that
procedural contour is the Mighty Blob product type.
"""
from __future__ import annotations

import math
from typing import Sequence

from widgets.spotify_visualizer.blob_shaper_solver import (
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


def _compress_blob_energy(value: float) -> float:
    """Compress hot Blob-local energy without flattening everything at 1.0.

    Live diagnostics routinely show healthy per-band values in the 0.8..1.4
    range. Hard clamping that range made the contour spend whole passages at
    one fixed amplitude, leaving only phase travel visible. This soft knee is
    deliberately Blob-owned; shared audio remains untouched.
    """

    raw = max(0.0, float(value))
    scaled = raw * 0.72
    if scaled <= 0.90:
        return scaled
    # Preserve the very useful 0.5..1.5 live range almost linearly, then bend
    # only genuinely hot values into a bounded ceiling.
    return min(1.18, 0.90 + 0.30 * (1.0 - math.exp(-(scaled - 0.90) / 0.30)))


def _rounded_outward_lobe(angle: float, center: float, half_width: float) -> float:
    """Return a compact cosine-squared bulge with zero-slope shoulders."""

    width = max(0.08, float(half_width))
    diff = abs(math.atan2(math.sin(angle - center), math.cos(angle - center)))
    if diff >= width:
        return 0.0
    t = diff / width
    return (0.5 + 0.5 * math.cos(math.pi * t)) ** 2


def _organic_tendril_lobe(angle: float, center: float, half_width: float) -> float:
    """Return a rounded tendril with a broad root and narrower gel tip."""

    shoulder = _rounded_outward_lobe(angle, center, half_width)
    tip = _rounded_outward_lobe(angle, center, half_width * 0.54)
    return shoulder * 0.38 + tip * 0.62


def _smooth_cyclic_profile(values: Sequence[float], *, passes: int = 3) -> list[float]:
    """Round angular shoulders without changing the profile's cyclic seam."""

    out = [float(value) for value in values]
    if len(out) < 3:
        return out
    for _ in range(max(0, int(passes))):
        out = [
            out[idx] * 0.52
            + out[(idx - 1) % len(out)] * 0.24
            + out[(idx + 1) % len(out)] * 0.24
            for idx in range(len(out))
        ]
    return out


def _smooth_max(a: float, b: float, softness: float = 0.014) -> float:
    """Differentiable max used to keep containment from drawing hard cuts."""

    delta = float(a) - float(b)
    soft = max(1e-6, float(softness))
    return 0.5 * (float(a) + float(b) + math.sqrt(delta * delta + soft * soft))


def compute_unshaped_organic_base_multiplier(
    *,
    angle_frac: float,
    time_seconds: float,
    smoothed_energy: float,
    overall_energy: float,
) -> float:
    """Return the seam-safe living body multiplier for Mighty Blob.

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

    # The living body is always present, even when every reactive control is
    # zero.  That prevents a configuration or playback transition from
    # exposing the raw circular SDF underneath Mighty.
    return _clamp(shape, 0.88, 1.16)


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
    """Return Mighty Blob tendril and wobble offsets in radius units.

    Broad standing fields and rounded local lobes deliberately avoid the old
    phase-travelling radial-fan vocabulary.  The profile builder recentres the
    resulting body before containment, so outward reach does not silently
    inflate its mean radius.
    """

    angle = (float(angle_frac) % 1.0) * math.tau
    time_value = float(time_seconds)
    e_bass = _compress_blob_energy(bass_energy)
    e_mid = _compress_blob_energy(mid_energy)
    e_high = _compress_blob_energy(high_energy)
    e_overall = _compress_blob_energy(overall_energy)
    se = _compress_blob_energy(smoothed_energy)
    rd = _clamp(reactive_deformation, 0.0, 3.0)
    cw = _clamp(constant_wobble, 0.0, 2.0)
    rw = _clamp(reactive_wobble, 0.0, 3.0)
    st = _clamp(stretch_tendency, 0.0, 1.0)
    s_inner = _clamp(stretch_inner, 0.0, 1.0)
    s_outer = _clamp(stretch_outer, 0.0, 1.0)

    # Constant living wobble uses standing waves whose amplitudes breathe.
    # Linear phase travel made a fixed deformation rotate around the blob;
    # these anchored lobes instead swell, shrink, and trade dominance.
    constant_field = 0.0
    constant_field += math.sin(angle + 0.35) * 0.052 * (0.76 + 0.24 * math.sin(time_value * 0.43 + 0.2))
    constant_field += math.sin(angle * 2.0 + 1.40) * 0.042 * (0.72 + 0.28 * math.sin(time_value * 0.61 + 1.1))
    constant_field += math.sin(angle * 3.0 + 2.65) * 0.026 * (0.70 + 0.30 * math.sin(time_value * 0.79 + 2.0))
    constant_field += math.sin(angle * 5.0 + 0.90) * 0.012 * (0.68 + 0.32 * math.sin(time_value * 1.07 + 0.6))

    reactive_mid = _clamp(e_mid * 0.92 + e_overall * 0.08, 0.0, 1.0)
    reactive_high = _clamp(e_high * 0.82 + e_mid * 0.12, 0.0, 1.0)
    vocal = _clamp(e_mid * 1.02 + e_high * 0.18, 0.0, 1.0)

    # Music-reactive outline wobble is also spatially anchored. Vocal energy
    # changes its amplitude while small standing-wave pulses keep the contour
    # visibly flexing even through sustained notes.
    vocal_pulse = 0.78 + 0.22 * math.sin(time_value * 1.83 + 0.45)
    mid_pulse = 0.78 + 0.22 * math.sin(time_value * 1.31 + 1.75)
    high_pulse = 0.82 + 0.18 * math.sin(time_value * 2.17 + 2.30)
    reactive_field = 0.0
    reactive_field += math.sin(angle * 2.0 + 0.62) * 0.125 * vocal * vocal_pulse
    reactive_field += math.sin(angle * 3.0 + 2.10) * 0.084 * reactive_mid * mid_pulse
    reactive_field += math.sin(angle * 4.0 + 1.18) * 0.071 * vocal * vocal * (1.0 - vocal_pulse * 0.35)
    reactive_field += math.sin(angle * 5.0 + 2.85) * 0.047 * reactive_mid * (0.55 + mid_pulse * 0.45)
    reactive_field += math.sin(angle * 7.0 + 0.15) * 0.026 * reactive_high * high_pulse

    pocket_pressure = _clamp(pocket_component, 0.0, 1.8)
    pocket_soft = 1.0 - math.exp(-pocket_pressure * 0.92)
    pocket_shoulder = pocket_soft * (1.0 - pocket_soft * 0.24)

    stretch_component = 0.0
    if st > 0.01:
        peak = max(e_bass, e_mid, e_high, se * 0.86, e_overall * 0.82)
        peak2 = peak * peak
        peak3 = peak2 * peak

        # Rounded cosine-squared bulges have zero-slope shoulders. Their
        # centers only sway slightly; energy changes their length, so a hit
        # reads as a tendril growing and relaxing rather than orbiting.
        center_sway = math.sin(time_value * 0.31) * 0.09
        vocal_breath = 0.08 + 0.92 * (0.5 + 0.5 * math.sin(time_value * 1.11 + 0.4))
        bass_breath = 0.12 + 0.88 * (0.5 + 0.5 * math.sin(time_value * 0.83 + 2.0))
        mid_breath = 0.08 + 0.92 * (0.5 + 0.5 * math.sin(time_value * 1.47 + 1.25))
        high_breath = 0.05 + 0.95 * (0.5 + 0.5 * math.sin(time_value * 2.09 + 2.70))
        tendrils = 0.0
        tendrils += _organic_tendril_lobe(angle, 0.55 + center_sway, 0.72) * peak3 * 0.360 * vocal_breath
        tendrils += _organic_tendril_lobe(angle, 3.76 - center_sway * 0.65, 0.78) * peak2 * 0.285 * bass_breath
        tendrils += _organic_tendril_lobe(angle, 2.08 + center_sway * 0.35, 0.58) * e_mid * e_mid * 0.265 * mid_breath
        tendrils += _organic_tendril_lobe(angle, 5.25 - center_sway * 0.45, 0.48) * e_high * 0.175 * high_breath

        # The authored inward control adds only a much smaller, independently
        # centred counter-lobe.  Even at maximum it cannot recreate the old
        # deep radial pinch family.
        inward_detail = 0.0
        inward_detail += math.sin(angle * 2.0 + 2.30) * peak3 * 0.025
        inward_detail += math.sin(angle * 3.0 + 0.45) * e_mid * e_mid * 0.018

        outer_gain = 0.42 + s_outer * 1.38
        inner_gain = s_inner * 0.34
        stretch_component = (tendrils * outer_gain + inward_detail * inner_gain) * st
        stretch_component += pocket_shoulder * (0.055 + s_outer * 0.105) * st
        stretch_component += pocket_soft * 0.014 * st

    # Shape Reactivity scales music motion only. Idle Edge Motion remains a
    # useful independent control, and the old cubic >1 boost can no longer
    # slam the profile into containment caps.
    rd_scale = rd if rd <= 1.0 else 1.0 + (rd - 1.0) * 0.75
    wobble_component = constant_field * cw + reactive_field * rw * rd_scale
    wobble_component += pocket_shoulder * 0.018 * rd_scale
    stretch_component *= rd_scale

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
    """Return Mighty Blob's final contour multiplier relative to staged radius."""

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
    contour_floor = max(0.84, body_mult * max(0.84, stage_floor))
    candidate = body_mult + stretch_component + wobble_component
    # A differentiable organic floor avoids the hard max junctions that drew
    # cut-like shoulders. The floor follows the living base, never a circle.
    final_mult = _smooth_max(candidate, contour_floor)
    return max(0.84, final_mult)


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
    # Preserve the healthy >1.0 Blob-local live range seen in diagnostics;
    # the motion helper applies its own soft-knee compression. Hard clipping
    # here was what made sustained passages look phase-animated but static.
    bass = max(0.0, float(bass_energy))
    mid = max(0.0, float(mid_energy))
    high = max(0.0, float(high_energy))
    overall = max(0.0, float(overall_energy))
    smoothed = max(0.0, float(smoothed_energy))

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
    above_cap = max_allowed - center
    below_cap = center - min_allowed
    # Inward safety and outward expression are independent authorities.
    # A single shared scale let the protected inward floor suppress every
    # outward tendril whenever one valley approached containment.  Smooth
    # tanh shoulders also avoid drawing exact-radius plateaus at either bound.
    fitted: list[float] = []
    for value in profile:
        delta = float(value) - center
        if delta >= 0.0:
            mapped = above_cap * math.tanh(delta / max(above_cap, 1e-6))
        else:
            mapped = -below_cap * math.tanh((-delta) / max(below_cap, 1e-6))
        fitted.append(_clamp(center + mapped, min_allowed, max_allowed))
    return fitted


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
    """Build the procedural Mighty contour family in profile space.

    Returns ``(base_profile, target_profile, bounded_target_profile)``.
    """

    count = max(0, int(sample_count))
    if count <= 0:
        return ([], [], [])

    time_value = float(time_seconds)
    # Keep the healthy >1.0 live range until the subtype-owned soft knee in
    # ``compute_unshaped_motion_offsets``.  Hard clipping here was flattening
    # loud passages into one constant-amplitude profile.
    bass = max(0.0, float(bass_energy))
    mid = max(0.0, float(mid_energy))
    high = max(0.0, float(high_energy))
    overall = max(0.0, float(overall_energy))
    smoothed = max(0.0, float(smoothed_energy))
    stage_floor = compute_stage_floor_fraction(
        core_floor_bias=core_floor_bias,
        stage1_t=stage1_t,
        stage2_t=stage2_t,
        stage3_t=stage3_t,
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
        target_profile.append(final_mult)

    # Profile-space rounding is authoritative. This prevents a single hot
    # pocket/tendril sample from becoming a radial knife edge in the SDF.
    # Analytic standing waves and cosine-squared lobes are already smooth.
    # Two one-time passes remove sample-grid shoulders without the former
    # every-frame attenuation stack that erased tendrils.
    target_profile = _smooth_cyclic_profile(target_profile, passes=2)

    # Harmonics and centred tendril lobes should redistribute the body rather
    # than silently resize it.  Re-centering before containment also cancels
    # the positive mean introduced by local pocket impulses while preserving
    # their angular contrast.
    base_mean = math.fsum(base_profile) / count
    target_mean = math.fsum(target_profile) / count
    mean_shift = base_mean - target_mean
    target_profile = [value + mean_shift for value in target_profile]

    # Give the solved contour more authority over the silhouette while keeping
    # it card-contained.  Mighty has a hard ~0.84 inward limit and a larger
    # outward reserve for musical tendrils.
    min_allowed = max(0.84, stage_floor * 0.92)
    max_allowed = min(1.58, 1.34 + stage1_t * 0.060 + stage2_t * 0.080 + stage3_t * 0.100)
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
    """Advance Mighty Blob's procedural contour through the shared solver."""

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
        attack_hz=30.0 if playing else 10.0,
        release_hz=8.0 if playing else 3.0,
    )
    current_profile = list(previous_profile or ())
    current_velocity = list(previous_velocity or ())
    if len(current_profile) != count:
        # A fresh activation must reflect the current, bounded audio contour on
        # its first visible frame.  Seeding from the calm base made every type
        # reset briefly look static/circular even though healthy audio was
        # already available; the fade owns any visual softening needed here.
        current_profile = list(target_profile)
    if len(current_velocity) != count:
        current_velocity = [0.0] * count

    stage_floor = compute_stage_floor_fraction(
        core_floor_bias=core_floor_bias,
        stage1_t=stage1_t,
        stage2_t=stage2_t,
        stage3_t=stage3_t,
    )
    min_profile = [max(0.84, base_profile[idx] * max(0.84, stage_floor)) for idx in range(count)]
    max_profile = [min(1.58, max(base_profile[idx] + 0.58, target_profile[idx] + 0.22)) for idx in range(count)]
    solved_profile, solved_velocity = solve_profile_step(
        current_profile=current_profile,
        current_velocity=current_velocity,
        target_profile=target_profile,
        min_profile=min_profile,
        max_profile=max_profile,
        dt=dt,
        stiffness=55.0 if playing else 18.0,
        damping=8.0 if playing else 10.0,
        neighbor_strength=3.0 if playing else 4.0,
        smoothing_passes=0,
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
    # Mighty/Shaped share a readable body baseline; contour motion still owns
    # the silhouette, while this scalar lane provides restrained breathing.
    r = 0.31 * blob_size
    r += bass * bass * 0.008 * blob_pulse
    r += bass * 0.009 * blob_pulse
    se = _clamp(smoothed_energy, 0.0, 1.0)
    breath = max(bass, se * 0.82)
    r += max(0.02, breath) * 0.004 * blob_pulse
    r -= (1.0 - se) * 0.004 * blob_pulse
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
