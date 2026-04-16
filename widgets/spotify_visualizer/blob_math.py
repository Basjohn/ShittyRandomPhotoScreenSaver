"""Shared math helpers for blob visualizer radius calculations."""
from __future__ import annotations

import math


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
    drift = 0.60 + se * 0.28 + overall * 0.12

    shape = 1.0
    # Broad liquid body language: low harmonics only, phase-shifted so the
    # body breathes as one form rather than reading as radial teeth.
    shape += math.cos(angle * 1.0 + slow_t * 0.41 + 0.70) * 0.054
    shape += math.cos(angle * 2.0 - slow_t * 0.29 + 1.85) * 0.031
    shape += math.cos(angle * 3.0 + slow_t * 0.23 + 3.05) * 0.017
    # A slower asymmetry term keeps the body from settling into a repeated,
    # evenly-balanced clover shape while remaining fully periodic.
    shape += math.cos(angle * 1.0 - slow_t * 0.17 + 2.45) * 0.016 * drift

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
    slow_sway += math.sin(angle * 1.0 + time_value * 0.20 + 0.25) * 0.020
    slow_sway += math.sin(angle * 2.0 - time_value * 0.34 + 1.05) * 0.011
    slow_sway += math.sin(angle * 3.0 + time_value * 0.27 + 2.10) * 0.005
    slow_sway *= 1.0 - abs(base_bias) * 0.18

    reactive_mid = _clamp(e_mid * 0.92 + e_overall * 0.08, 0.0, 1.0)
    reactive_high = _clamp(e_high * 0.82 + e_mid * 0.12, 0.0, 1.0)
    vocal = _clamp(e_mid * 1.02 + e_high * 0.18, 0.0, 1.0)

    reactive_sway = 0.0
    reactive_sway += math.sin(angle * 1.0 + time_value * 0.48 + 0.30) * 0.040 * vocal
    reactive_sway += math.sin(angle * 2.0 - time_value * 0.56 + 1.80) * 0.026 * reactive_mid
    reactive_sway += math.sin(angle * 3.0 + time_value * 0.44 + 2.55) * 0.010 * reactive_high
    reactive_sway += base_bias * vocal * 0.015

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
        stretch += math.sin(angle * 1.0 + time_value * 0.16 + 0.95) * impact2 * 0.082
        stretch += math.sin(angle * 2.0 - time_value * 0.31 + 2.20) * impact3 * 0.058
        stretch += base_bias * impact2 * 0.046
        stretch += base_bias * max(0.0, vocal_impact - 0.18) * 0.024
        stretch += pocket_shoulder * 0.138
        stretch += pocket_soft * max(0.0, 0.35 - abs(base_bias)) * 0.022
        stretch_component = stretch * st

    wobble_component += pocket_shoulder * 0.010
    wobble_component += pocket_soft * base_bias * 0.008

    rd_scale = rd if rd <= 1.0 else 1.0 + (rd - 1.0) ** 3 * 4.0 + (rd - 1.0) * 2.0
    wobble_component *= rd_scale
    stretch_component *= rd_scale

    if stretch_component < 0.0:
        stretch_component *= 0.04 + s_inner * 0.48
    else:
        stretch_component *= 0.10 + s_outer * 0.90

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
    min_radius_mult = max(0.84, body_mult * stage_floor)
    stretch_floor = min(min_radius_mult - body_mult, 0.0)
    stretch_component = max(stretch_component, stretch_floor)
    core_mult = body_mult + stretch_component
    fluid_floor = _clamp(0.84 + stage1_t * 0.04 + max(0.0, body_mult - 1.0) * 0.03, 0.84, 0.92)
    final_mult = max(core_mult + wobble_component, core_mult * fluid_floor)
    final_mult = max(final_mult, max(0.84, body_mult * 0.88))
    return final_mult


def compute_inward_liquid_profile(
    *,
    angle_frac: float,
    time_seconds: float,
    local_radius: float,
    local_depth: float,
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
    """Return the inward-liquid motion profile for one contour sample.

    The layer is built as a contour-following inner fluid band. It should:
    - stay alive at rest via low-amplitude drift
    - advance under bounded audio pressure
    - yield locally when the body is energetic or the gap grows too crowded
    - redistribute some of that pressure tangentially instead of hard-popping
    - always preserve a positive interior gap
    """

    local_r = max(float(local_radius), 1e-4)
    local_d = max(float(local_depth), 0.0)
    if not enabled or ring_mode:
        return {
            "front_depth": 0.0,
            "mix": 0.0,
            "advance_drive": 0.0,
            "retreat_depth": 0.0,
            "redistribution": 0.0,
            "no_contact_gap": local_r,
        }

    angle = (float(angle_frac) % 1.0) * math.tau
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

    base_drift = 0.20
    base_drift += math.sin(time_value * 0.82 + angle * 1.8) * 0.08
    base_drift += math.sin(time_value * 1.31 - angle * 2.7 + 0.90) * 0.06
    base_drift = _clamp(base_drift, 0.08, 0.34)

    audio_pressure = _clamp(
        se * 0.22 +
        overall * 0.25 +
        mid * 0.24 +
        bass * 0.11 +
        high * 0.08 +
        transient * 0.10,
        0.0,
        1.4,
    )
    ripple_wave = math.sin(time_value * (2.0 + audio_pressure * 2.2) + angle * 3.5)
    contour_ripple = 0.5 + 0.5 * ripple_wave
    tangential_slide = (contour_ripple - 0.5) * (0.08 + 0.06 * min(react, 1.0))

    advance_drive = _clamp(
        base_drift +
        audio_pressure * (0.12 + 0.10 * react) +
        tangential_slide,
        0.06,
        0.92,
    )
    hard_cap = local_r * max_fraction
    requested_depth = hard_cap * advance_drive

    body_pressure = _clamp(
        se * 0.18 +
        overall * 0.20 +
        mid * 0.10 +
        stage1 * 0.10 +
        stage2 * 0.18 +
        stage3 * 0.28 +
        transient * 0.08,
        0.0,
        1.3,
    )
    local_bias = 0.5 + 0.5 * math.sin(time_value * 0.64 - angle * 2.1 + 1.2)
    crowding = _clamp(requested_depth / max(hard_cap, 1e-4), 0.0, 1.0)
    thin_region = _smoothstep(0.58, 0.28, local_r)
    retreat_signal = _clamp(
        body_pressure * (0.48 + 0.34 * local_bias) +
        crowding * 0.58 +
        thin_region * 0.24,
        0.0,
        1.4,
    )
    retreat_weight = _smoothstep(0.45, 1.02, retreat_signal)
    retreat_depth = hard_cap * retreat_weight * (0.10 + body_pressure * 0.14 + thin_region * 0.08)

    redistribution = retreat_weight * (0.03 + 0.05 * audio_pressure) * math.sin(
        time_value * 1.45 + angle * 4.4 - 0.6
    )
    final_depth = requested_depth - retreat_depth + redistribution * hard_cap
    final_depth = _clamp(final_depth, local_r * 0.04, hard_cap)

    front_softness = max(final_depth * 0.38, 0.006)
    front_start = max(final_depth - front_softness, 0.0)
    front_mask = 1.0 - _smoothstep(front_start, final_depth, local_d)
    source_anchor = 1.0 - _smoothstep(0.0, max(final_depth * 0.75, 0.012), local_d)
    body_preserve = _smoothstep(0.0, max(local_r * 0.45, 0.02), local_d)
    mix = front_mask * (0.34 + source_anchor * 0.22 + audio_pressure * 0.16) * (1.0 - body_preserve * 0.45)
    mix = _clamp(mix, 0.0, 0.78)

    return {
        "front_depth": final_depth,
        "mix": mix,
        "advance_drive": advance_drive,
        "retreat_depth": retreat_depth,
        "redistribution": redistribution * hard_cap,
        "no_contact_gap": max(local_r - final_depth, local_r * (1.0 - max_fraction)),
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

    stage_unit = base_size * 0.18 + 0.02
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
    r = 0.44 * blob_size
    r += bass * bass * 0.066 * blob_pulse
    r += bass * 0.077 * blob_pulse
    se = _clamp(smoothed_energy, 0.0, 1.0)
    breath = max(bass, se * 0.82)
    r += max(0.03, breath) * 0.020 * blob_pulse
    r -= (1.0 - se) * 0.028 * blob_pulse
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
