"""Blob-owned curved tendril transport for Mighty and Shaped.

The radial contour remains useful for the breathing body and vocal outline,
but a single radius per angle cannot form bent limbs, hooked tips, or the deep
negative space of an actual goo silhouette.  This module produces a small,
bounded set of curved two-segment tendrils for the Blob shader to smooth-union
with that body.  No shared audio or another visualizer mode is modified.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

from core.settings.visualizer_blob_contract import BLOB_TYPE_SHAPED

TENDRIL_COUNT = 12


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge0 == edge1:
        return 0.0
    t = _clamp((float(value) - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _soft_energy(value: float) -> float:
    raw = max(0.0, float(value)) * 0.72
    if raw <= 0.88:
        return raw
    return min(1.16, 0.88 + 0.30 * (1.0 - math.exp(-(raw - 0.88) / 0.30)))


def _live_bands(state: Any) -> tuple[float, float, float, float, float]:
    fallback = getattr(state, "_energy_bands", None)

    def _read(attr: str, band: str) -> float:
        value = getattr(state, attr, None)
        if value is None:
            value = getattr(fallback, band, 0.0) if fallback is not None else 0.0
        return _soft_energy(float(value or 0.0))

    transient = getattr(state, "_transient_energy", None)
    transient_peak = max(
        float(getattr(transient, "bass_transient", 0.0) if transient else 0.0),
        float(getattr(transient, "mid_transient", 0.0) if transient else 0.0),
        float(getattr(transient, "high_transient", 0.0) if transient else 0.0),
        float(getattr(state, "_blob_kick_event_envelope", 0.0) or 0.0),
        float(getattr(state, "_blob_snare_event_envelope", 0.0) or 0.0),
    )
    return (
        _read("_blob_live_bass_energy", "bass"),
        _read("_blob_live_mid_energy", "mid"),
        _read("_blob_live_high_energy", "high"),
        _read("_blob_live_overall_energy", "overall"),
        _soft_energy(transient_peak),
    )


def _profile_anchor_bias(profile: Sequence[float], angle_frac: float) -> float:
    if not profile:
        return 1.0
    idx = int((float(angle_frac) % 1.0) * len(profile)) % len(profile)
    mean = math.fsum(float(value) for value in profile) / len(profile)
    return _clamp(0.82 + (float(profile[idx]) - mean) * 1.4, 0.70, 1.18)


def _mighty_payload(
    state: Any,
    *,
    profile: Sequence[float],
    time_value: float,
    seed: float,
) -> tuple[list[float], list[float]]:
    bass, mid, high, overall, transient = _live_bands(state)
    vocal = _clamp(mid * 0.90 + high * 0.22, 0.0, 1.16)
    playing = bool(getattr(state, "_playing", False))
    stretch = _clamp(getattr(state, "_blob_stretch_tendency", 0.35), 0.0, 1.0)
    outer = _clamp(getattr(state, "_blob_stretch_outer", 0.35), 0.0, 1.0)
    shape = _clamp(getattr(state, "_blob_reactive_deformation", 1.0), 0.0, 3.0)
    wobble = _clamp(getattr(state, "_blob_reactive_wobble", 1.0), 0.0, 3.0)
    reach_control = stretch * (0.34 + outer * 0.66) * (0.72 + min(shape, 2.0) * 0.34)
    if not playing:
        reach_control *= 0.16

    anchors = (0.015, 0.075, 0.180, 0.235, 0.360, 0.490, 0.545, 0.670, 0.735, 0.820, 0.910, 0.965)
    rates = (0.67, 0.75, 0.83, 0.93, 1.05, 1.17, 1.31, 1.45, 1.59, 1.73, 1.89, 2.07)
    phases = (0.20, 2.60, 5.00, 1.10, 3.50, 5.90, 1.80, 4.20, 0.70, 3.10, 5.50, 2.00)
    reach_scales = (1.34, 0.64, 1.08, 0.82, 1.42, 0.70, 1.18, 0.58, 1.46, 0.76, 1.12, 0.68)
    drivers = (
        vocal * 0.82 + overall * 0.18,
        bass * 0.90 + transient * 0.30,
        mid * 0.70 + transient * 0.44,
        overall * 0.52 + vocal * 0.48,
        high * 0.72 + vocal * 0.34,
        transient * 0.72 + bass * 0.24 + high * 0.20,
        vocal * 0.54 + transient * 0.42 + overall * 0.18,
        bass * 0.42 + mid * 0.36 + high * 0.34,
        mid * 0.62 + overall * 0.28,
        high * 0.54 + transient * 0.38 + vocal * 0.20,
        bass * 0.58 + vocal * 0.32,
        overall * 0.44 + mid * 0.34 + transient * 0.30,
    )
    pockets = list(getattr(getattr(state, "_blob_pocket_state", None), "pockets", ()) or ())
    geometry: list[float] = []
    motion: list[float] = []
    for idx in range(TENDRIL_COUNT):
        wave = 0.5 + 0.5 * math.sin(time_value * rates[idx] + phases[idx] + seed * (0.11 + idx * 0.03))
        birth = _smoothstep(0.22 + (idx % 2) * 0.06, 0.84 - (idx % 3) * 0.03, wave)
        pocket = pockets[idx] if idx < len(pockets) else None
        pocket_amp = _clamp(getattr(pocket, "amplitude", 0.0), 0.0, 1.0) if pocket else 0.0
        pocket_angle = float(getattr(pocket, "angle_frac", anchors[idx])) if pocket else anchors[idx]
        use_pocket = pocket_amp > 0.045
        angle = pocket_angle if use_pocket else anchors[idx]
        opposite_phase = phases[(TENDRIL_COUNT - 1 - idx) % TENDRIL_COUNT]
        angle += math.sin(time_value * (0.13 + idx * 0.021) + opposite_phase) * (0.010 + idx * 0.0012)
        activity = _clamp(
            float(drivers[idx]) * (0.08 + birth * 0.92) + pocket_amp * 0.72,
            0.0,
            1.18,
        )
        if playing:
            sustained_support = max(vocal, overall, bass * 0.82, high * 0.74)
            activity = max(
                activity,
                sustained_support
                * reach_control
                * (0.125 + 0.025 * (0.5 + 0.5 * math.sin(phases[idx]))),
            )
        activity *= _profile_anchor_bias(profile, angle)
        length = _clamp(
            activity * (0.020 + reach_control * 0.145) * reach_scales[idx],
            0.0,
            0.19,
        )
        if activity < 0.045 or reach_control < 0.015:
            length = 0.0
        root_width = _clamp(0.020 + length * 0.20 + activity * 0.010, 0.018, 0.060)
        tip_width = _clamp(root_width * (0.48 + 0.12 * birth), 0.010, root_width * 0.72)
        bend = math.sin(time_value * (0.29 + idx * 0.047) + phases[idx] + seed) * (
            0.22 + activity * 0.48
        )
        hook = math.sin(time_value * (0.41 + idx * 0.053) + opposite_phase - seed * 0.3) * (
            0.16 + activity * 0.42
        )
        light = _clamp(vocal * 0.58 + high * 0.22 + transient * 0.32, 0.0, 1.0)
        geometry.extend((angle % 1.0, length, root_width, tip_width))
        # Two lanes are inward liquid channels. They subtract rounded, curved
        # negative space from the body instead of adding another radial limb.
        kind_or_light = (
            -max(0.18, activity)
            if idx in {3, 8, 11}
            else light * (0.55 + wobble * 0.15)
        )
        motion.extend((bend, hook, activity, kind_or_light))
    return geometry, motion


def _shaped_payload(
    state: Any,
    *,
    profile: Sequence[float],
    time_value: float,
    seed: float,
) -> tuple[list[float], list[float]]:
    bass, mid, high, overall, transient = _live_bands(state)
    vocal = _clamp(mid * 0.86 + high * 0.26, 0.0, 1.16)
    playing = bool(getattr(state, "_playing", False))
    idle = _clamp(getattr(state, "_blob_shaper_idle_motion", 0.18), 0.0, 2.0) / 2.0
    audio = _clamp(getattr(state, "_blob_shaper_audio_motion", 1.20), 0.0, 3.0) / 3.0
    react = _clamp(getattr(state, "_blob_shaper_react_strength", 0.5), 0.0, 1.0)
    anchors = (0.035, 0.120, 0.205, 0.290, 0.375, 0.460, 0.545, 0.630, 0.715, 0.800, 0.885, 0.965)
    phases = (0.50, 2.70, 4.60, 1.50, 3.60, 5.50, 2.20, 4.10, 0.90, 3.00, 5.00, 1.90)
    reach_scales = (1.22, 0.70, 1.18, 0.76, 1.34, 0.66, 1.12, 1.26, 0.72, 1.30, 1.10, 0.64)
    drivers = (
        vocal,
        overall * 0.48 + transient * 0.62,
        mid * 0.62 + high * 0.30,
        bass * 0.52 + overall * 0.38,
        high * 0.68 + vocal * 0.28,
        transient * 0.72 + vocal * 0.26,
        vocal * 0.48 + overall * 0.26 + transient * 0.30,
        mid * 0.38 + high * 0.42 + bass * 0.20,
        overall * 0.40 + vocal * 0.38,
        high * 0.58 + transient * 0.30,
        bass * 0.44 + mid * 0.34 + transient * 0.22,
        vocal * 0.52 + high * 0.26 + overall * 0.18,
    )
    geometry: list[float] = []
    motion: list[float] = []
    for idx in range(TENDRIL_COUNT):
        wave = 0.5 + 0.5 * math.sin(time_value * (0.83 + idx * 0.19) + phases[idx] + seed * 0.17)
        birth = _smoothstep(0.28, 0.80, wave)
        audio_activity = float(drivers[idx]) * audio * (0.06 + birth * 0.94) if playing else 0.0
        idle_activity = idle * (0.018 + birth * 0.12)
        activity = _clamp(audio_activity + idle_activity, 0.0, 1.0)
        if playing:
            activity = max(
                activity,
                max(vocal, overall, high * 0.86)
                * audio
                * (0.115 + react * 0.055),
            )
        opposite_phase = phases[(TENDRIL_COUNT - 1 - idx) % TENDRIL_COUNT]
        angle = anchors[idx] + math.sin(time_value * (0.17 + idx * 0.026) + opposite_phase) * 0.018
        activity *= _profile_anchor_bias(profile, angle)
        length = _clamp(
            (
                idle_activity * 0.035
                + activity * (0.028 + audio * 0.092) * (0.62 + react * 0.38)
            ) * 1.30 * reach_scales[idx],
            0.0,
            0.158,
        )
        if activity < 0.035:
            length = 0.0
        root_width = _clamp(0.016 + length * 0.19 + activity * 0.008, 0.014, 0.044)
        tip_width = _clamp(root_width * (0.46 + birth * 0.14), 0.008, root_width * 0.70)
        bend = math.sin(time_value * (0.37 + idx * 0.061) + phases[idx] + seed) * (
            0.18 + activity * 0.52
        )
        hook = math.sin(time_value * (0.53 + idx * 0.047) + opposite_phase - seed) * (
            0.14 + activity * 0.44
        )
        light = _clamp(vocal * 0.64 + high * 0.24 + transient * 0.38, 0.0, 1.0)
        geometry.extend((angle % 1.0, length, root_width, tip_width))
        kind_or_light = -max(0.16, activity) if idx in {2, 7, 10} else light
        motion.extend((bend, hook, activity, kind_or_light))
    return geometry, motion


def build_blob_tendril_payload(
    state: Any,
    *,
    blob_type: str,
    profile: Sequence[float],
) -> tuple[list[float], list[float]]:
    """Return flattened vec4 geometry/motion arrays for the selected subtype."""

    time_value = max(0.0, float(getattr(state, "_blob_runtime_time", 0.0) or 0.0))
    if blob_type == BLOB_TYPE_SHAPED:
        seed = float(getattr(state, "_blob_shaper_solver_seed", 0.0) or 0.0)
        return _shaped_payload(state, profile=profile, time_value=time_value, seed=seed)
    seed = float(getattr(state, "_blob_unshaped_solver_seed", 0.0) or 0.0)
    return _mighty_payload(state, profile=profile, time_value=time_value, seed=seed)


__all__ = ["TENDRIL_COUNT", "build_blob_tendril_payload"]
