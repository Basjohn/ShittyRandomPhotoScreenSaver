"""Shared math helpers for blob visualizer radius calculations."""
from __future__ import annotations


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0
    t = _clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


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

    weighted = _clamp(bass * 0.56 + overall * 0.28 + high * 0.10 + mid * 0.06, 0.0, 1.0)
    weighted_stage1 = _clamp(weighted * 0.88 + se * 0.12, 0.0, 1.0)
    base_stage2_drive = _clamp(
        weighted * 0.74 + bass * 0.10 + mid * 0.12 + high * 0.04,
        0.0,
        1.0,
    )
    stage2_drive = _clamp(base_stage2_drive * 0.84 + se * 0.16, 0.0, 1.0)
    chorus_drive = _clamp(
        max(stage2_drive, bass * 0.38 + overall * 0.30 + mid * 0.18 + high * 0.14),
        0.0,
        1.0,
    )
    chorus_drive = _clamp(max(chorus_drive, se * 0.34 + overall * 0.44 + mid * 0.22), 0.0, 1.0)

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
    stage1_t = _smoothstep(0.08, 0.34, weighted_stage1)
    stage2_t = _smoothstep(0.16, 0.42, stage2_drive)
    stage3_t = _smoothstep(0.24, 0.52, chorus_drive)
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
    stage1_amt = stage_unit * 0.58
    stage2_amt = stage_unit * 1.22
    stage3_amt = stage_unit * 2.10

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
    r += bass * bass * 0.066
    r += bass * 0.077 * blob_pulse
    se = _clamp(smoothed_energy, 0.0, 1.0)
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
    )
    return r


def compute_blob_ghost_min_offset(smoothed_energy: float) -> float:
    """Return the minimum ghost peak offset above the live blob state.

    The ghost should stay visible, but it should not dominate the live blob
    shape or look like the "real" blob on calmer passages.
    """
    se = _clamp(smoothed_energy, 0.0, 1.0)
    return _clamp(max(0.015, se * 0.035), 0.015, 0.035)
