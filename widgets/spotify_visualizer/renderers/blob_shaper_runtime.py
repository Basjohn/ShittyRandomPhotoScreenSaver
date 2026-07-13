"""Blob Shaper contour runtime helpers.

This module owns the Shaped Blob path only. Keeping it separate from Mighty
Blob makes it easier to improve authored-contour reactivity without dragging
the procedural fluid body back toward shared compromise math.
"""
from __future__ import annotations

import math
import time
from numbers import Real
from typing import Sequence

from widgets.spotify_visualizer.blob_shaper_solver import (
    solve_profile_step,
    slew_profile_toward_target,
)

_SHAPER_N = 128
_SHAPER_REST_DEADZONE = 0.06
_SHAPER_DRIVE_GAIN = 1.35
_SHAPER_ROUTING_PRIMARY_SPREAD = 0.22
_SHAPER_ROUTING_SECONDARY_SPREAD = 0.38
_SHAPER_ROUTING_SMOOTH_PASSES = 3
_SHAPER_OPPOSITE_DELTA_FACTOR = 0.22
_SHAPER_OPPOSITE_BASE_CAP = 0.18
_SHAPER_GAP_EXPONENT_SCALE = 0.35
_SHAPER_GAP_EXPONENT_CAP = 0.70
_SHAPER_MIN_BASE_PROFILE_STRENGTH = 0.22
_SHAPER_ANGULAR_SMOOTH_OFFSETS = (0.0, -1.0 / _SHAPER_N, 1.0 / _SHAPER_N)
_SHAPER_ANGULAR_SMOOTH_WEIGHTS = (0.5, 0.25, 0.25)

_ENERGY_TYPE_INDEX = {
    "bass": 0,
    "mid": 1,
    "vocals": 2,
    "treble": 3,
    "transient": 4,
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _compress_shaper_energy(value: float) -> float:
    """Soft-compress hot live energy without throwing away values above one.

    Blob's stage inputs regularly exceed ``1.0`` on real material.  A hard
    clamp made different vocal and transient levels indistinguishable, while
    the previous drive gain then pinned most authored reactions at their goal.
    This local knee keeps the shared audio contract untouched and preserves a
    useful response across both quiet and hot Shaped input.
    """

    raw = max(0.0, min(4.0, float(value)))
    scaled = raw * 0.68
    if scaled <= 0.88:
        return scaled
    return min(1.14, 0.88 + 0.28 * (1.0 - math.exp(-(scaled - 0.88) / 0.28)))


def _standing_breath(time_value: float, rate: float, phase: float, floor: float) -> float:
    """Return an amplitude envelope for an angularly anchored deformation."""

    pulse = 0.5 + 0.5 * math.sin(time_value * rate + phase)
    return _clamp(floor, 0.0, 1.0) + (1.0 - _clamp(floor, 0.0, 1.0)) * pulse


def _rounded_angular_lobe(angle_frac: float, center_frac: float, half_width: float) -> float:
    """Return a cosine-squared tendril with zero-slope shoulders and tip."""

    diff = abs((float(angle_frac) - float(center_frac)) % 1.0)
    diff = min(diff, 1.0 - diff)
    width = max(1e-4, float(half_width))
    if diff >= width:
        return 0.0
    return math.cos((diff / width) * math.pi * 0.5) ** 2


def _organic_angular_tendril(
    angle_frac: float,
    center_frac: float,
    half_width: float,
) -> float:
    """Return a Shaped tendril with a broad root and rounded narrow tip."""

    shoulder = _rounded_angular_lobe(angle_frac, center_frac, half_width)
    tip = _rounded_angular_lobe(angle_frac, center_frac, half_width * 0.68)
    return shoulder * 0.58 + tip * 0.42


def _catmull_rom(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2.0 * p1)
        + (-p0 + p2) * t
        + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
        + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
    )


def _editor_angle_fraction_from_cartesian(x: float, y: float) -> float:
    angle = math.atan2(y, x) / (2.0 * math.pi)
    return (angle + 0.25) % 1.0


def _routing_falloff(diff: float, spread: float) -> float:
    if spread <= 1e-6 or diff >= spread:
        return 0.0
    return 0.5 * (1.0 + math.cos(math.pi * diff / spread))


def _smooth_cyclic_series(values: Sequence[float], passes: int = _SHAPER_ROUTING_SMOOTH_PASSES) -> list[float]:
    out = [float(v) for v in values]
    if len(out) < 3:
        return out
    for _ in range(max(0, int(passes))):
        prev = out[-1]
        cur = out[0]
        smoothed: list[float] = []
        for idx in range(len(out)):
            nxt = out[(idx + 1) % len(out)]
            smoothed.append(prev * 0.2 + cur * 0.6 + nxt * 0.2)
            prev, cur = cur, nxt
        out = smoothed
    return out


def _limit_cyclic_series_slope(
    values: Sequence[float],
    *,
    max_step: float,
    iterations: int = 10,
) -> list[float]:
    """Project only over-steep contour shoulders into a rounded slope budget."""

    out = [float(value) for value in values]
    if len(out) < 3:
        return out
    limit = max(1e-5, float(max_step))
    for _ in range(max(1, int(iterations))):
        changed = False
        for idx in range(len(out)):
            next_idx = (idx + 1) % len(out)
            delta = out[next_idx] - out[idx]
            if abs(delta) <= limit:
                continue
            excess = (abs(delta) - limit) * 0.5
            direction = 1.0 if delta > 0.0 else -1.0
            out[idx] += direction * excess
            out[next_idx] -= direction * excess
            changed = True
        if not changed:
            break
    return out


def _sample_linear_series(angle_frac: float, series: Sequence[float]) -> float:
    if not series:
        return 0.0
    n = len(series)
    idx_f = (float(angle_frac) % 1.0) * n
    i0 = int(math.floor(idx_f)) % n
    i1 = (i0 + 1) % n
    t = idx_f - math.floor(idx_f)
    return float(series[i0]) + (float(series[i1]) - float(series[i0])) * t


def _sample_smoothed_linear_series(angle_frac: float, series: Sequence[float]) -> float:
    if not series:
        return 0.0
    total = 0.0
    weight_total = 0.0
    for offset, weight in zip(_SHAPER_ANGULAR_SMOOTH_OFFSETS, _SHAPER_ANGULAR_SMOOTH_WEIGHTS):
        total += _sample_linear_series(angle_frac + offset, series) * weight
        weight_total += weight
    return total / max(1e-6, weight_total)


def _resample_nodes(nodes: Sequence[Sequence[float]], n: int) -> list[float]:
    if not nodes or n <= 0:
        return [1.0] * n
    normalized_map: dict[float, float] = {}
    for point in nodes:
        try:
            raw_x = float(point[0])
            x = raw_x % 1.0
            y = float(point[1])
        except Exception:
            continue
        key = round(x, 6)
        previous = normalized_map.get(key)
        is_wrap_alias = key == 0.0 and abs(raw_x) > 1e-6
        if previous is None:
            normalized_map[key] = y
        elif not is_wrap_alias and y > previous:
            normalized_map[key] = y
    normalized = [[key, value] for key, value in normalized_map.items()]
    sn = sorted(normalized, key=lambda p: p[0])
    nn = len(sn)
    if nn == 1:
        return [sn[0][1]] * n
    out: list[float] = []
    for i in range(n):
        t = i / n
        if t >= sn[-1][0] or t < sn[0][0]:
            seg_idx = nn - 1
        else:
            seg_idx = 0
            for j in range(nn - 1):
                if sn[j][0] <= t:
                    seg_idx = j
        lo_x = sn[seg_idx][0]
        hi_x = sn[(seg_idx + 1) % nn][0]
        if seg_idx == nn - 1:
            seg_len = (1.0 - lo_x) + hi_x
            if t >= lo_x:
                local_t = (t - lo_x) / seg_len if seg_len > 1e-6 else 0.0
            else:
                local_t = (t + 1.0 - lo_x) / seg_len if seg_len > 1e-6 else 0.0
        else:
            seg_len = hi_x - lo_x
            local_t = (t - lo_x) / seg_len if seg_len > 1e-6 else 0.0
        local_t = max(0.0, min(1.0, local_t))
        p0 = sn[(seg_idx - 1) % nn][1]
        p1 = sn[seg_idx][1]
        p2 = sn[(seg_idx + 1) % nn][1]
        p3 = sn[(seg_idx + 2) % nn][1]
        raw = _catmull_rom(p0, p1, p2, p3, local_t)
        lo = min(p0, p1, p2, p3)
        hi = max(p0, p1, p2, p3)
        out.append(max(max(0.08, lo), min(hi, raw)))
    return out


def _runtime_energy_nodes(energy_nodes: list) -> list[dict]:
    if not energy_nodes:
        return []
    react_nodes: list[dict] = []
    legacy_nodes: list[dict] = []
    for raw_node in energy_nodes:
        if not isinstance(raw_node, dict):
            continue
        canvas = str(raw_node.get("canvas", "")).strip().lower()
        if canvas == "react":
            react_nodes.append(dict(raw_node))
        else:
            legacy_nodes.append(dict(raw_node))
    return react_nodes if react_nodes else legacy_nodes


def _build_energy_routing(
    energy_nodes: list,
    n: int,
    *,
    base_profile: Sequence[float] | None = None,
    react_profile: Sequence[float] | None = None,
) -> list[list[float]]:
    weights = [[0.0] * n for _ in range(5)]
    runtime_nodes = _runtime_energy_nodes(energy_nodes)
    if not runtime_nodes:
        weights[0] = [1.0] * n
        return weights
    for node in runtime_nodes:
        etype = str(node.get("type", "bass")).lower()
        idx = _ENERGY_TYPE_INDEX.get(etype, 0)
        nx = float(node.get("x", 0.5))
        ny = float(node.get("y", 0.5))
        strength = float(node.get("strength", 1.0))
        dir_x = float(node.get("dir_x", 0.0))
        dir_y = float(node.get("dir_y", -1.0))
        cx, cy = nx - 0.5, ny - 0.5
        angle_frac = _editor_angle_fraction_from_cartesian(cx, cy)
        radial_len = math.hypot(cx, cy)
        if radial_len > 1e-6:
            radial_x = cx / radial_len
            radial_y = cy / radial_len
        else:
            radial_x = 0.0
            radial_y = -1.0
        dir_len = math.hypot(dir_x, dir_y)
        if dir_len > 1e-6:
            dir_x /= dir_len
            dir_y /= dir_len
        else:
            dir_x = radial_x
            dir_y = radial_y
        radial_alignment = max(-1.0, min(1.0, dir_x * radial_x + dir_y * radial_y))
        authored_direction = 1.0
        if base_profile and react_profile:
            base_r = _sample_linear_series(angle_frac, base_profile)
            react_r = _sample_linear_series(angle_frac, react_profile)
            react_delta = react_r - base_r
            if abs(react_delta) > 1e-4:
                authored_direction = 1.0 if react_delta >= 0.0 else -1.0
        signed_strength = strength * radial_alignment * authored_direction
        for i in range(n):
            sample_frac = i / n
            diff = abs(sample_frac - angle_frac)
            diff = min(diff, 1.0 - diff)
            primary = _routing_falloff(diff, _SHAPER_ROUTING_PRIMARY_SPREAD)
            secondary = _routing_falloff(diff, _SHAPER_ROUTING_SECONDARY_SPREAD)
            influence = (primary * 0.74 + secondary * 0.26) * signed_strength
            weights[idx][i] += influence
    return [_smooth_cyclic_series(channel) for channel in weights]


def _sample_routed_shaper_energy(
    angle_frac: float,
    weights: Sequence[Sequence[float]],
    *,
    bass: float,
    mid: float,
    high: float,
    overall: float,
    transient: float = 0.0,
) -> float:
    channels = list(weights[:5])
    channels += [()] * max(0, 5 - len(channels))
    contributions = (
        float(bass) * _sample_smoothed_linear_series(angle_frac, channels[0]),
        float(mid) * _sample_smoothed_linear_series(angle_frac, channels[1]),
        float(mid) * _sample_smoothed_linear_series(angle_frac, channels[2]),
        float(high) * _sample_smoothed_linear_series(angle_frac, channels[3]),
        float(transient) * _sample_smoothed_linear_series(angle_frac, channels[4]),
    )
    return _combine_routed_energy(contributions)


def _sample_smoothed_shaper_energy(
    angle_frac: float,
    weights: Sequence[Sequence[float]],
    *,
    bass: float,
    mid: float,
    high: float,
    overall: float,
    transient: float = 0.0,
) -> float:
    total = 0.0
    weight_total = 0.0
    for offset, weight in zip(_SHAPER_ANGULAR_SMOOTH_OFFSETS, _SHAPER_ANGULAR_SMOOTH_WEIGHTS):
        total += _sample_routed_shaper_energy(
            angle_frac + offset,
            weights,
            bass=bass,
            mid=mid,
            high=high,
            overall=overall,
            transient=transient,
        ) * weight
        weight_total += weight
    return total / max(1e-6, weight_total)


def _combine_routed_energy(contributions: Sequence[float]) -> float:
    """Combine signed routing lanes without repeatedly sampling their arrays."""

    positives = [float(value) for value in contributions if value > 0.0]
    negatives = [-float(value) for value in contributions if value < 0.0]
    strongest_outward = max(positives, default=0.0)
    strongest_inward = max(negatives, default=0.0)
    smooth_outward = max(strongest_outward, min(1.0, math.fsum(positives) * 0.72))
    smooth_inward = max(strongest_inward, min(1.0, math.fsum(negatives) * 0.72))
    if max(smooth_outward, smooth_inward) < 1e-6:
        return 0.0
    dominant = smooth_outward if smooth_outward >= smooth_inward else -smooth_inward
    net = smooth_outward - smooth_inward
    signed = _clamp(dominant * 0.94 + net * 0.06, -1.0, 1.0)
    if abs(signed) < 1e-6:
        signed = dominant if abs(dominant) >= abs(net) else net
    return signed


def _sample_grid_smoothed(values: Sequence[float], count: int) -> list[float]:
    """Sample a cyclic series once at the solver grid's smoothing kernel."""

    if count <= 0:
        return []
    return [
        _sample_smoothed_linear_series(idx / count, values)
        for idx in range(count)
    ]


def _build_shaper_signed_energy_profile(
    weights: Sequence[Sequence[float]],
    *,
    sample_count: int,
    bass: float,
    mid: float,
    high: float,
    transient: float,
) -> list[float]:
    """Resolve authored routing once per sample instead of once per helper layer.

    The previous angle helper nested a three-tap contour sample around five
    three-tap routing samples, then repeated the whole operation for the outer
    smoothing kernel.  At the fixed 128-sample transport grid this produces
    the same field much more cheaply by smoothing each lane once, combining
    it, and smoothing the signed result once.
    """

    count = max(0, int(sample_count))
    channels = list(weights[:5])
    channels += [()] * max(0, 5 - len(channels))
    sampled = [_sample_grid_smoothed(channel, count) for channel in channels]
    routed = [
        _combine_routed_energy(
            (
                float(bass) * sampled[0][idx],
                float(mid) * sampled[1][idx],
                float(mid) * sampled[2][idx],
                float(high) * sampled[3][idx],
                float(transient) * sampled[4][idx],
            )
        )
        for idx in range(count)
    ]
    return [
        routed[(idx - 1) % count] * 0.25
        + routed[idx] * 0.50
        + routed[(idx + 1) % count] * 0.25
        for idx in range(count)
    ]


def _resolve_shaper_base_radius(
    base_radius: float,
    *,
    base_strength: float,
    neutral_radius: float = 1.0,
) -> float:
    """Scale authored base relief while retaining a non-circular minimum."""

    authored_base_mix = _SHAPER_MIN_BASE_PROFILE_STRENGTH + (
        1.0 - _SHAPER_MIN_BASE_PROFILE_STRENGTH
    ) * _clamp(base_strength, 0.0, 1.0)
    neutral = max(0.0, float(neutral_radius))
    return neutral + (float(base_radius) - neutral) * authored_base_mix


def _resolve_shaper_targets(
    base_radius: float,
    react_radius: float,
    *,
    base_strength: float = 1.0,
    react_strength: float = 1.0,
    neutral_radius: float = 1.0,
) -> tuple[float, float, float]:
    shaped_base = _resolve_shaper_base_radius(
        base_radius,
        base_strength=base_strength,
        neutral_radius=neutral_radius,
    )
    react_mix = max(0.0, min(1.0, float(react_strength)))
    shaped_react = shaped_base + (float(react_radius) - shaped_base) * react_mix
    react_delta = shaped_react - shaped_base
    delta_mag = abs(react_delta)
    if delta_mag <= 1e-6:
        return shaped_base, shaped_react, shaped_base
    opposite_delta = min(
        delta_mag * _SHAPER_OPPOSITE_DELTA_FACTOR,
        max(0.0, shaped_base) * _SHAPER_OPPOSITE_BASE_CAP,
    )
    opposite_target = shaped_base - math.copysign(opposite_delta, react_delta)
    return shaped_base, shaped_react, opposite_target


def _prepare_shaper_signed_energy(signed_energy: float) -> float:
    return max(-1.0, min(1.0, float(signed_energy) * _SHAPER_DRIVE_GAIN))


def _shape_shaper_energy_for_gap(
    signed_energy: float,
    *,
    base_radius: float,
    react_radius: float,
) -> float:
    magnitude = max(0.0, min(1.0, abs(float(signed_energy))))
    if magnitude <= 1e-6:
        return 0.0
    base = max(1e-6, abs(float(base_radius)))
    gap_norm = abs(float(react_radius) - float(base_radius)) / base
    exponent = 1.0 + min(_SHAPER_GAP_EXPONENT_CAP, gap_norm * _SHAPER_GAP_EXPONENT_SCALE)
    shaped = magnitude ** exponent
    return math.copysign(shaped, float(signed_energy))


def _remap_shaper_drive(signed_energy: float, *, playing: bool) -> float:
    if not playing:
        return 0.0
    signed_energy = _prepare_shaper_signed_energy(signed_energy)
    magnitude = abs(float(signed_energy))
    if magnitude <= _SHAPER_REST_DEADZONE:
        return 0.0
    t = (magnitude - _SHAPER_REST_DEADZONE) / max(1e-6, 1.0 - _SHAPER_REST_DEADZONE)
    t = max(0.0, min(1.0, t))
    # Smoothstep preserves useful distinction through the middle of the live
    # range.  The old ease-out curve plus 3.2x gain reached the authored goal
    # on nearly every music frame and made Shaped look static.
    eased = t * t * (3.0 - 2.0 * t)
    return math.copysign(eased, float(signed_energy))


def _resolve_shaper_radius(
    base_radius: float,
    react_radius: float,
    signed_energy: float,
    *,
    base_strength: float = 1.0,
    react_strength: float = 1.0,
    neutral_radius: float = 1.0,
    bass_energy: float = 0.0,
    overall_energy: float = 0.0,
    playing: bool,
) -> float:
    shaped_base, shaped_react, opposite_target = _resolve_shaper_targets(
        base_radius,
        react_radius,
        base_strength=base_strength,
        react_strength=react_strength,
        neutral_radius=neutral_radius,
    )
    signed_energy = _shape_shaper_energy_for_gap(
        signed_energy,
        base_radius=shaped_base,
        react_radius=shaped_react,
    )
    drive = _remap_shaper_drive(signed_energy, playing=playing)
    sign_mix_t = max(0.0, min(1.0, (drive + 0.20) / 0.40))
    sign_mix = sign_mix_t * sign_mix_t * (3.0 - 2.0 * sign_mix_t)
    react_target = shaped_react
    if drive > 0.0:
        react_delta = max(0.0, shaped_react - shaped_base)
        kick_push = max(0.0, min(0.08, float(bass_energy) * 0.10 + float(overall_energy) * 0.06))
        react_target += react_delta * kick_push * abs(drive)
    target = opposite_target + (react_target - opposite_target) * sign_mix
    return shaped_base + (target - shaped_base) * abs(drive)


def _resolve_shaper_radius_at_angle(
    angle_frac: float,
    *,
    base_profile: Sequence[float],
    react_profile: Sequence[float],
    weights: Sequence[Sequence[float]],
    staged_radius: float,
    bass: float,
    mid: float,
    high: float,
    overall: float,
    base_strength: float = 1.0,
    react_strength: float = 1.0,
    playing: bool,
    transient: float = 0.0,
) -> float:
    base_mult = _sample_smoothed_linear_series(angle_frac, base_profile)
    react_mult = _sample_smoothed_linear_series(angle_frac, react_profile)
    base_radius = staged_radius * base_mult
    react_radius = staged_radius * react_mult
    signed_energy = _sample_smoothed_shaper_energy(
        angle_frac,
        weights,
        bass=bass,
        mid=mid,
        high=high,
        overall=overall,
        transient=transient,
    )
    return _resolve_shaper_radius(
        base_radius,
        react_radius,
        signed_energy,
        base_strength=base_strength,
        neutral_radius=staged_radius,
        bass_energy=bass,
        overall_energy=overall,
        react_strength=react_strength,
        playing=playing,
    )


def _build_shaped_motion_residual_profile(
    *,
    sample_count: int,
    time_value: float,
    idle_motion: float,
    audio_motion: float,
    overall_energy: float,
    vocal_energy: float,
    high_energy: float,
    transient_energy: float,
    playing: bool,
    seed: float,
) -> list[float]:
    """Build Shaped Blob's living wobble plus bounded music mutations.

    ``idle_motion`` owns broad, slow body warping that remains alive while
    paused. ``audio_motion`` owns a separate energy-gated field of irregular
    mutations plus lighter rounded outward tendrils. Both component fields are
    centred before returning so their controls reshape rather than resize the
    authored body.
    """

    count = max(0, int(sample_count))
    if count <= 0:
        return []

    idle = _clamp(idle_motion, 0.0, 2.0)
    audio = _clamp(audio_motion, 0.0, 3.0) if playing else 0.0
    overall = _compress_shaper_energy(overall_energy)
    vocal = _compress_shaper_energy(vocal_energy)
    high = _compress_shaper_energy(high_energy)
    transient = _compress_shaper_energy(transient_energy)
    energy = _clamp(overall * 0.40 + vocal * 0.34 + high * 0.12 + transient * 0.14, 0.0, 1.0)

    idle_amplitude = min(0.125, idle * 0.105)
    mutation_amplitude = min(0.305, audio * energy * 0.265)
    vocal_amplitude = min(0.235, audio * (vocal * 0.148 + high * 0.052))
    tendril_amplitude = min(
        0.325,
        audio * (overall * 0.043 + vocal * 0.112 + high * 0.034 + transient * 0.102),
    )

    # Each broad harmonic has its own bounded phase and amplitude trajectory.
    # A single shared phase merely rotates an authored silhouette; independent
    # paths change the relationship, count, and reach of its local features.
    idle_phases = (
        seed * 0.61 + math.sin(time_value * 0.19 + seed * 0.37) * 0.62,
        seed * 1.17 + 1.30 + math.sin(time_value * 0.27 + 1.10) * 0.82,
        -seed * 0.43 + 2.80 + math.sin(time_value * 0.39 + 2.40) * 0.96,
    )
    mutation_phases = (
        seed * 0.83 + 0.40 + math.sin(time_value * 0.47 + 0.20) * 0.78,
        seed * 1.31 + 1.90 + math.sin(time_value * 0.63 + 1.70) * 0.94,
        -seed * 0.57 + 3.30 + math.sin(time_value * 0.81 + 3.10) * 1.06,
        seed * 1.67 + 0.90 + math.sin(time_value * 1.07 + 4.20) * 0.88,
        -seed * 1.09 + 2.60 + math.sin(time_value * 1.31 + 2.20) * 0.72,
    )
    living_breaths = (
        _standing_breath(time_value, 0.47, seed * 0.83 + 0.20, 0.42),
        _standing_breath(time_value, 0.63, seed * 1.31 + 1.70, 0.40),
        _standing_breath(time_value, 0.79, seed * 0.57 + 3.10, 0.36),
    )
    mutation_breaths = (
        _standing_breath(time_value, 1.17, seed * 0.91 + 0.40, 0.20),
        _standing_breath(time_value, 1.53, seed * 1.43 + 2.00, 0.18),
        _standing_breath(time_value, 1.91, seed * 0.69 + 4.10, 0.16),
        _standing_breath(time_value, 2.47, seed * 1.77 + 1.10, 0.12),
        _standing_breath(time_value, 3.11, seed * 0.39 + 3.40, 0.10),
    )
    vocal_breaths = (
        _standing_breath(time_value, 2.73, seed * 1.19 + 0.80, 0.18),
        _standing_breath(time_value, 3.67, seed * 0.73 + 2.80, 0.14),
        _standing_breath(time_value, 4.43, seed * 1.43 + 4.10, 0.10),
    )
    tendril_breaths = (
        _standing_breath(time_value, 1.13, seed * 1.07 + 0.30, 0.02),
        _standing_breath(time_value, 1.47, seed * 0.67 + 2.30, 0.02),
        _standing_breath(time_value, 1.83, seed * 1.61 + 4.70, 0.01),
        _standing_breath(time_value, 2.29, seed * 0.49 + 1.40, 0.00),
    )
    tendril_centers = (
        0.08 + (seed * 0.013) % 0.07 + math.sin(time_value * 0.23 + seed) * 0.038,
        0.40 + (seed * 0.017) % 0.08 + math.sin(time_value * 0.19 + seed * 1.7) * 0.046,
        0.70 + (seed * 0.011) % 0.07 + math.sin(time_value * 0.31 - seed * 0.8) * 0.034,
        0.89 + (seed * 0.019) % 0.05 + math.sin(time_value * 0.41 + seed * 0.4) * 0.026,
    )
    mutation_lobe_gates = (
        _standing_breath(time_value, 0.91, seed * 0.53 + 0.60, 0.04),
        _standing_breath(time_value, 1.21, seed * 1.41 + 2.70, 0.03),
        _standing_breath(time_value, 1.57, seed * 0.79 + 4.40, 0.02),
    )
    mutation_lobe_centers = (
        0.20 + math.sin(time_value * 0.29 + seed) * 0.030,
        0.56 + math.sin(time_value * 0.37 + 2.10 - seed * 0.2) * 0.038,
        0.82 + math.sin(time_value * 0.43 + 4.20 + seed * 0.3) * 0.026,
    )
    residual_profile: list[float] = []
    for idx in range(count):
        theta = (idx / count) * math.tau

        # Broad idle warp: low-order standing fields with independently
        # breathing amplitudes.  A tiny common sway prevents mechanical
        # stillness without turning the field into rotational motion.
        living = (
            math.sin(theta + idle_phases[0]) * 0.50 * living_breaths[0]
            + math.sin(theta * 2.0 + idle_phases[1]) * 0.31 * living_breaths[1]
            + math.sin(theta * 3.0 + idle_phases[2]) * 0.19 * living_breaths[2]
        )

        # Music mutation remains anchored as well.  Independent envelopes
        # make fixed sections of the contour push, recede, and change detail;
        # the harmonic mix is intentionally irregular but still rounded.
        mutation = (
            math.sin(theta + mutation_phases[0]) * 0.22 * mutation_breaths[0]
            + math.sin(theta * 2.0 + mutation_phases[1]) * 0.23 * mutation_breaths[1]
            + math.sin(theta * 3.0 + mutation_phases[2]) * 0.24 * mutation_breaths[2]
            + math.sin(theta * 5.0 + mutation_phases[3]) * 0.19 * mutation_breaths[3]
            + math.sin(theta * 7.0 + mutation_phases[4]) * 0.12 * mutation_breaths[4]
        )
        angle_frac = idx / count
        mutation += (
            _organic_angular_tendril(
                angle_frac,
                mutation_lobe_centers[0],
                0.105 + mutation_lobe_gates[0] * 0.030,
            ) * 0.34 * mutation_lobe_gates[0]
            - _organic_angular_tendril(
                angle_frac,
                mutation_lobe_centers[1],
                0.130 + mutation_lobe_gates[1] * 0.025,
            ) * 0.27 * mutation_lobe_gates[1]
            + _organic_angular_tendril(
                angle_frac,
                mutation_lobe_centers[2],
                0.085 + mutation_lobe_gates[2] * 0.025,
            ) * 0.24 * mutation_lobe_gates[2]
        )

        # Mid/high energy owns a faster standing outline ripple.  This is the
        # vocal contour wobble, not a colour/glow proxy.  Keep it below the
        # authored H1/H2 silhouette and below a one-sample corner at the
        # 128-point transport resolution.
        vocal_wobble = (
            math.sin(
                theta * 4.0
                + seed * 0.89
                + math.sin(time_value * 1.73 + seed * 0.31) * 1.24
            ) * 0.46 * vocal_breaths[0]
            + math.sin(
                theta * 6.0
                - seed * 0.53
                + math.sin(time_value * 2.17 + 1.90) * 1.38
            ) * 0.34 * vocal_breaths[1]
            + math.sin(
                theta * 9.0
                + seed * 1.27
                + math.sin(time_value * 2.83 + 3.70) * 1.06
            ) * 0.20 * vocal_breaths[2]
        )

        # Sparse cosine-squared pulls are born and retired on independent
        # envelopes. Their anchor families remain bounded, while widths and
        # lengths breathe, so they read as gel extensions rather than spikes
        # orbiting a fixed goal shape.
        tendrils = (
            _organic_angular_tendril(
                angle_frac,
                tendril_centers[0],
                0.070 + tendril_breaths[0] * 0.040,
            ) * 0.39 * tendril_breaths[0]
            + _organic_angular_tendril(
                angle_frac,
                tendril_centers[1],
                0.060 + tendril_breaths[1] * 0.038,
            ) * 0.29 * tendril_breaths[1]
            + _organic_angular_tendril(
                angle_frac,
                tendril_centers[2],
                0.052 + tendril_breaths[2] * 0.034,
            ) * 0.21 * tendril_breaths[2]
            + _organic_angular_tendril(
                angle_frac,
                tendril_centers[3],
                0.044 + tendril_breaths[3] * 0.030,
            ) * 0.18 * tendril_breaths[3] * max(transient, vocal * 0.42)
        )

        residual_profile.append(
            living * idle_amplitude
            + mutation * mutation_amplitude
            + vocal_wobble * vocal_amplitude
            # Profile-space tendrils are root pressure only; curved 2D limbs
            # own the visible reach in the Blob shader.
            + tendrils * tendril_amplitude * 0.42
        )

    # The analytic fields are smooth by construction. Two one-time passes
    # remove sample-grid shoulders while retaining the authored controls'
    # amplitude; there is no longer any every-frame solver/shader averaging.
    residual_profile = _smooth_cyclic_series(residual_profile, passes=4)
    residual_profile = _limit_cyclic_series_slope(
        residual_profile,
        max_step=1.58 / count,
    )
    residual_profile = _smooth_cyclic_series(residual_profile, passes=4)
    mean = math.fsum(residual_profile) / count
    return [value - mean for value in residual_profile]


def _shaped_motion_allowance(
    *,
    idle_motion: float,
    audio_motion: float,
    bass: float,
    mid: float,
    high: float,
    overall: float,
    transient: float,
    playing: bool,
) -> float:
    """Return a contour-space mutation budget independent of authored gap."""

    idle_budget = min(0.125, _clamp(idle_motion, 0.0, 2.0) * 0.105)
    energy = _clamp(
        _compress_shaper_energy(overall) * 0.40
        + _compress_shaper_energy(mid) * 0.26
        + _compress_shaper_energy(bass) * 0.12
        + _compress_shaper_energy(high) * 0.09
        + _compress_shaper_energy(transient) * 0.13,
        0.0,
        1.0,
    )
    audio_budget = 0.0
    if playing:
        audio_budget = min(0.315, _clamp(audio_motion, 0.0, 3.0) * energy * 0.235)
    return min(0.380, idle_budget + audio_budget)


def _get_shaper_energy_bands(s) -> tuple[float, float, float, float]:
    eb = getattr(s, "_energy_bands", None)
    fallback = (
        float(getattr(s, "_blob_live_bass_energy", getattr(eb, "bass", 0.0)) or 0.0),
        float(getattr(s, "_blob_live_mid_energy", getattr(eb, "mid", 0.0)) or 0.0),
        float(getattr(s, "_blob_live_high_energy", getattr(eb, "high", 0.0)) or 0.0),
        float(getattr(s, "_blob_live_overall_energy", getattr(eb, "overall", 0.0)) or 0.0),
    )

    def _stage_band(attr: str, fallback_value: float) -> float:
        raw = getattr(s, attr, None)
        if raw is None:
            return float(fallback_value)
        return float(raw)

    def _blend(stage_value: float, live_value: float, mix: float) -> float:
        stage = float(stage_value)
        live = float(live_value)
        return max(live, live + (stage - live) * mix)

    return (
        _blend(_stage_band("_blob_stage_input_bass", fallback[0]), fallback[0], 0.92),
        _blend(_stage_band("_blob_stage_input_mid", fallback[1]), fallback[1], 0.78),
        _blend(_stage_band("_blob_stage_input_high", fallback[2]), fallback[2], 0.76),
        _blend(_stage_band("_blob_stage_input_overall", fallback[3]), fallback[3], 0.88),
    )


def _get_shaper_transient_energy(s) -> float:
    """Read Blob's existing transient envelope for authored transient nodes.

    Continuous ``overall`` energy must never impersonate an onset.  Prefer the
    already mode-mixed diagnostic envelopes produced by Blob's live-band
    helper, with a direct transient-bus fallback for synthetic/runtime tests
    and the first frame before those diagnostics exist.
    """

    def _numeric(value, fallback: float = 0.0) -> float:
        if not isinstance(value, Real):
            return float(fallback)
        numeric = float(value)
        return numeric if math.isfinite(numeric) else float(fallback)

    mixed_values = (
        getattr(s, "_blob_diag_transient_bass", None),
        getattr(s, "_blob_diag_transient_mid", None),
        getattr(s, "_blob_diag_transient_high", None),
    )
    envelope = 0.0
    pre_scaled_overlay_envelope = False
    if any(isinstance(value, Real) for value in mixed_values):
        envelope = max(0.0, *(_numeric(value) for value in mixed_values))
        pre_scaled_overlay_envelope = True
    else:
        transient = getattr(s, "_transient_energy", None)
        if transient is None or not any(
            isinstance(getattr(transient, attr, None), Real)
            for attr in ("bass_transient", "mid_transient", "high_transient", "onset_strength")
        ):
            return 0.0
        bass_mix_raw = getattr(s, "_blob_transient_mix_bass", 0.5)
        vocal_mix_raw = getattr(s, "_blob_transient_mix_vocal", 0.35)
        bass_mix = _clamp(_numeric(bass_mix_raw, 0.5), 0.0, 1.0)
        vocal_mix = _clamp(_numeric(vocal_mix_raw, 0.35), 0.0, 1.0)
        bass_value = max(0.0, _numeric(getattr(transient, "bass_transient", 0.0))) * bass_mix
        mid_value = max(0.0, _numeric(getattr(transient, "mid_transient", 0.0))) * vocal_mix
        high_value = max(0.0, _numeric(getattr(transient, "high_transient", 0.0))) * max(
            0.10,
            vocal_mix * 0.30,
        )
        onset_value = 0.0
        if getattr(transient, "onset_detected", False) is True:
            onset_value = max(0.0, _numeric(getattr(transient, "onset_strength", 0.0))) * max(
                bass_mix,
                vocal_mix,
            )
        envelope = max(bass_value, mid_value, high_value, onset_value)

    gain_raw = getattr(s, "_transient_pulse_gain", 1.0)
    clamp_raw = getattr(s, "_transient_clamp", 1.5)
    gain = _clamp(_numeric(gain_raw, 1.0), 0.0, 3.0)
    clamp_max = _clamp(_numeric(clamp_raw, 1.5), 0.0, 3.0)
    return min(clamp_max, envelope if pre_scaled_overlay_envelope else envelope * gain)


def _solve_runtime_shaper_profile_step(
    *,
    base_profile: Sequence[float],
    react_profile: Sequence[float],
    weights: Sequence[Sequence[float]],
    previous_profile: Sequence[float] | None,
    previous_velocity: Sequence[float] | None,
    previous_target_profile: Sequence[float] | None,
    dt: float,
    time_value: float,
    bass: float,
    mid: float,
    high: float,
    overall: float,
    react_strength: float,
    shaper_idle_motion: float,
    shaper_audio_motion: float,
    playing: bool,
    base_strength: float = 1.0,
    seed: float = 0.0,
    transient: float = 0.0,
    filled_topology: bool = False,
) -> tuple[list[float], list[float], list[float]]:
    count = min(len(base_profile), len(react_profile))
    if count <= 0:
        return ([], [], [])

    # Keep compression entirely inside Shaped Blob.  Shared audio and the
    # values used by every other visualizer remain byte-for-byte untouched.
    drive_bass = _compress_shaper_energy(bass)
    drive_mid = _compress_shaper_energy(mid)
    drive_high = _compress_shaper_energy(high)
    drive_overall = _compress_shaper_energy(overall)
    drive_transient = _compress_shaper_energy(transient)

    motion_allowance = _shaped_motion_allowance(
        idle_motion=shaper_idle_motion,
        audio_motion=shaper_audio_motion,
        bass=bass,
        mid=mid,
        high=high,
        overall=overall,
        transient=transient,
        playing=playing,
    )
    smoothed_base_profile = _sample_grid_smoothed(base_profile, count)
    smoothed_react_profile = _sample_grid_smoothed(react_profile, count)
    signed_energy_profile = _build_shaper_signed_energy_profile(
        weights,
        sample_count=count,
        bass=drive_bass,
        mid=drive_mid,
        high=drive_high,
        transient=drive_transient,
    )
    target_profile: list[float] = []
    resolved_base_profile: list[float] = []
    min_profile: list[float] = []
    max_profile: list[float] = []
    for idx in range(count):
        authored_base_mult = smoothed_base_profile[idx]
        base_mult = _resolve_shaper_base_radius(
            authored_base_mult,
            base_strength=base_strength,
        )
        react_mult = smoothed_react_profile[idx]
        target = _resolve_shaper_radius(
            authored_base_mult,
            react_mult,
            base_strength=base_strength,
            neutral_radius=1.0,
            bass_energy=drive_bass,
            overall_energy=drive_overall,
            react_strength=react_strength,
            signed_energy=signed_energy_profile[idx],
            playing=playing,
        )
        gap = abs(react_mult - base_mult)
        gap_outward_allowance = min(0.10, gap * 0.12 + max(0.0, react_mult - base_mult) * 0.05)
        gap_inward_allowance = min(0.08, gap * 0.10 + max(0.0, base_mult - react_mult) * 0.04)
        # A small authored base/react gap must not disable the living or music
        # layers.  The motion controls own an independent, capped envelope;
        # large authored gaps keep their existing wider reaction envelope.
        outward_allowance = max(gap_outward_allowance, motion_allowance)
        inward_allowance = max(gap_inward_allowance, motion_allowance * 0.84)
        min_profile.append(max(0.12, min(base_mult, react_mult) - inward_allowance))
        max_profile.append(min(1.95, max(base_mult, react_mult) + outward_allowance))
        target_profile.append(target)
        resolved_base_profile.append(base_mult)

    vocal_energy = max(0.0, float(mid) * 0.78 + float(high) * 0.18 + float(overall) * 0.10)
    residual_profile = _build_shaped_motion_residual_profile(
        sample_count=count,
        time_value=time_value,
        idle_motion=shaper_idle_motion,
        audio_motion=shaper_audio_motion,
        overall_energy=float(overall),
        vocal_energy=vocal_energy,
        high_energy=float(high),
        transient_energy=float(transient),
        playing=playing,
        seed=seed,
    )
    target_profile = [
        max(min_profile[idx], min(max_profile[idx], target_profile[idx] + residual_profile[idx]))
        for idx in range(count)
    ]
    if filled_topology:
        # Filled silhouettes cannot use the ring's effectively unbounded
        # negative space to separate very deep and very tall authored lobes.
        # Keep the goal recognisable, but softly compress only its scalar
        # inflation and extreme centered range. Ring deliberately retains the
        # wider mutation budget that makes its hollow topology successful.
        base_mean = math.fsum(resolved_base_profile) / count
        target_mean = math.fsum(target_profile) / count
        stable_mean = _clamp(
            target_mean,
            max(0.72, base_mean - 0.14),
            max(1.18, base_mean + 0.18),
        )
        centered_limit = 0.41
        target_profile = [
            stable_mean
            + math.tanh((value - target_mean) / centered_limit) * centered_limit
            for value in target_profile
        ]
        filled_max = min(1.70, stable_mean + 0.45)
        filled_min = min(filled_max, max(0.62, stable_mean - 0.45))
        # Clamp both sides through the same monotonic interval. Authored Filled
        # contours can legitimately exceed the visual cap; independently
        # raising the low side and lowering the high side inverted the solver
        # interval for those samples and let the nominal low bound exceed 1.70.
        min_profile = [
            _clamp(value, filled_min, filled_max) for value in min_profile
        ]
        max_profile = [
            _clamp(value, filled_min, filled_max) for value in max_profile
        ]
        target_profile = [
            _clamp(target_profile[idx], min_profile[idx], max_profile[idx])
            for idx in range(count)
        ]
    target_profile = slew_profile_toward_target(
        previous_target=previous_target_profile,
        current_target=target_profile,
        base_profile=resolved_base_profile,
        dt=dt,
        attack_hz=22.0,
        release_hz=7.0 if playing else 3.8,
    )
    if filled_topology:
        target_profile = [
            _clamp(target_profile[idx], min_profile[idx], max_profile[idx])
            for idx in range(count)
        ]

    current_profile = list(previous_profile or ())
    current_velocity = list(previous_velocity or ())
    if len(current_profile) != count:
        # A fresh Shaped activation must start from this activation's bounded
        # target, not one static base-only frame.  Variant resets already
        # guarantee there is no prior contour to release from, and the outer
        # startup fade owns visual softening.
        current_profile = list(target_profile)
    if len(current_velocity) != count:
        current_velocity = [0.0] * count

    solved_profile, solved_velocity = solve_profile_step(
        current_profile=current_profile,
        current_velocity=current_velocity,
        target_profile=target_profile,
        min_profile=min_profile,
        max_profile=max_profile,
        dt=dt,
        stiffness=55.0 if playing else 24.0,
        damping=8.0 if playing else 10.0,
        neighbor_strength=3.0 if playing else 4.0,
        smoothing_passes=0,
    )
    return solved_profile, solved_velocity, target_profile


def _resolve_runtime_shaper_profile(
    s,
    *,
    base_profile: Sequence[float],
    react_profile: Sequence[float],
    weights: Sequence[Sequence[float]],
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
    previous_ts = float(getattr(s, "_blob_shaper_solver_ts", 0.0) or 0.0)
    dt = current_ts - previous_ts if previous_ts > 0.0 else (1.0 / 60.0)
    dt = max(1.0 / 240.0, min(0.05, dt))

    seed = getattr(s, "_blob_shaper_solver_seed", None)
    if seed is None:
        epoch = int(getattr(s, "_blob_variant_epoch", 0) or 0)
        seed = (
            ((id(s) % 10007) / 10007.0) * math.tau
            + epoch * 2.399963229728653
        ) % math.tau
        setattr(s, "_blob_shaper_solver_seed", seed)

    transient = _get_shaper_transient_energy(s)
    filled_topology = getattr(s, "_blob_topology", "circle") != "ring"
    topology_signature = "filled" if filled_topology else "ring"
    if getattr(s, "_blob_shaper_runtime_topology", None) != topology_signature:
        setattr(s, "_blob_shaper_runtime_profile", None)
        setattr(s, "_blob_shaper_runtime_velocity", None)
        setattr(s, "_blob_shaper_runtime_target_profile", None)
        dt = 1.0 / 60.0

    solved_profile, solved_velocity, target_profile = _solve_runtime_shaper_profile_step(
        base_profile=base_profile,
        react_profile=react_profile,
        weights=weights,
        previous_profile=getattr(s, "_blob_shaper_runtime_profile", None),
        previous_velocity=getattr(s, "_blob_shaper_runtime_velocity", None),
        previous_target_profile=getattr(s, "_blob_shaper_runtime_target_profile", None),
        dt=dt,
        time_value=current_ts,
        bass=bass,
        mid=mid,
        high=high,
        overall=overall,
        transient=transient,
        base_strength=float(getattr(s, "_blob_shaper_base_strength", 0.5)),
        react_strength=float(getattr(s, "_blob_shaper_react_strength", 1.0)),
        shaper_idle_motion=float(getattr(s, "_blob_shaper_idle_motion", 0.18)),
        shaper_audio_motion=float(getattr(s, "_blob_shaper_audio_motion", 1.20)),
        playing=bool(getattr(s, "_playing", False)),
        seed=float(seed),
        filled_topology=filled_topology,
    )
    setattr(s, "_blob_shaper_runtime_profile", solved_profile)
    setattr(s, "_blob_shaper_runtime_velocity", solved_velocity)
    setattr(s, "_blob_shaper_runtime_target_profile", target_profile)
    setattr(s, "_blob_shaper_runtime_topology", topology_signature)
    setattr(s, "_blob_shaper_solver_ts", current_ts)
    return solved_profile
