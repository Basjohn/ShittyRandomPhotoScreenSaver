"""Blob Shaper contour runtime helpers.

This module owns the authored-contour Blob path only. Keeping it separate from
unshaped Blob makes it easier to improve shaped reactivity without dragging the
procedural fluid body back toward shared compromise math.
"""
from __future__ import annotations

import math
import time
from typing import Sequence

from widgets.spotify_visualizer.blob_shaper_solver import (
    build_contour_residual_profile,
    solve_profile_step,
    slew_profile_toward_target,
)

_SHAPER_N = 64
_SHAPER_REST_DEADZONE = 0.16
_SHAPER_DRIVE_GAIN = 3.2
_SHAPER_ROUTING_PRIMARY_SPREAD = 0.22
_SHAPER_ROUTING_SECONDARY_SPREAD = 0.38
_SHAPER_ROUTING_SMOOTH_PASSES = 3
_SHAPER_OPPOSITE_DELTA_FACTOR = 0.22
_SHAPER_OPPOSITE_BASE_CAP = 0.18
_SHAPER_GAP_EXPONENT_SCALE = 0.85
_SHAPER_GAP_EXPONENT_CAP = 1.25
_SHAPER_ANGULAR_SMOOTH_OFFSETS = (0.0, -1.0 / _SHAPER_N, 1.0 / _SHAPER_N)
_SHAPER_ANGULAR_SMOOTH_WEIGHTS = (0.5, 0.25, 0.25)

_ENERGY_TYPE_INDEX = {
    "bass": 0,
    "mid": 1,
    "vocals": 2,
    "treble": 3,
    "transient": 4,
}


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
) -> float:
    channels = list(weights[:5])
    channels += [()] * max(0, 5 - len(channels))
    contributions = (
        float(bass) * _sample_smoothed_linear_series(angle_frac, channels[0]),
        float(mid) * _sample_smoothed_linear_series(angle_frac, channels[1]),
        float(mid) * _sample_smoothed_linear_series(angle_frac, channels[2]),
        float(high) * _sample_smoothed_linear_series(angle_frac, channels[3]),
        float(overall) * _sample_smoothed_linear_series(angle_frac, channels[4]),
    )
    positives = [c for c in contributions if c > 0.0]
    negatives = [-c for c in contributions if c < 0.0]
    strongest_outward = max(positives, default=0.0)
    strongest_inward = max(negatives, default=0.0)
    smooth_outward = max(strongest_outward, min(1.0, sum(positives) * 0.72))
    smooth_inward = max(strongest_inward, min(1.0, sum(negatives) * 0.72))
    if max(smooth_outward, smooth_inward) < 1e-6:
        return 0.0
    dominant = smooth_outward if smooth_outward >= smooth_inward else -smooth_inward
    net = smooth_outward - smooth_inward
    signed = max(-1.0, min(1.0, dominant * 0.94 + net * 0.06))
    if abs(signed) < 1e-6:
        signed = dominant if abs(dominant) >= abs(net) else net
    return signed


def _sample_smoothed_shaper_energy(
    angle_frac: float,
    weights: Sequence[Sequence[float]],
    *,
    bass: float,
    mid: float,
    high: float,
    overall: float,
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
        ) * weight
        weight_total += weight
    return total / max(1e-6, weight_total)


def _resolve_shaper_targets(
    base_radius: float,
    react_radius: float,
    *,
    react_strength: float = 1.0,
) -> tuple[float, float, float]:
    shaped_base = float(base_radius)
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
    eased = 1.0 - (1.0 - t) * (1.0 - t)
    return math.copysign(eased, float(signed_energy))


def _resolve_shaper_radius(
    base_radius: float,
    react_radius: float,
    signed_energy: float,
    *,
    base_strength: float = 1.0,
    react_strength: float = 1.0,
    bass_energy: float = 0.0,
    overall_energy: float = 0.0,
    playing: bool,
) -> float:
    shaped_base, shaped_react, opposite_target = _resolve_shaper_targets(
        base_radius,
        react_radius,
        react_strength=react_strength,
    )
    signed_energy = _shape_shaper_energy_for_gap(
        signed_energy,
        base_radius=shaped_base,
        react_radius=shaped_react,
    )
    drive = _remap_shaper_drive(signed_energy, playing=playing)
    _ = float(base_strength)
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
    react_strength: float = 1.0,
    playing: bool,
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
    )
    return _resolve_shaper_radius(
        base_radius,
        react_radius,
        signed_energy,
        bass_energy=bass,
        overall_energy=overall,
        react_strength=react_strength,
        playing=playing,
    )


def _resolve_shaper_wobble_scales(
    constant_wobble: float,
    reactive_wobble: float,
    signed_energy: float,
    *,
    playing: bool,
    overall_energy: float = 0.0,
    mid_energy: float = 0.0,
) -> tuple[float, float]:
    drive = abs(_remap_shaper_drive(signed_energy, playing=playing))
    overall_floor = max(0.0, min(1.0, float(overall_energy)))
    vocal_floor = max(0.0, min(1.0, float(mid_energy)))
    music_floor = (overall_floor * 0.22 + vocal_floor * 0.12) if playing else 0.0
    music_floor = max(0.0, min(0.35, music_floor))
    motion = max(drive, music_floor)
    return (
        float(constant_wobble) * (music_floor * 0.28 + motion * 0.32),
        float(reactive_wobble) * (music_floor * 0.60 + motion * 0.90),
    )


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
    seed: float = 0.0,
) -> tuple[list[float], list[float], list[float]]:
    count = min(len(base_profile), len(react_profile))
    if count <= 0:
        return ([], [], [])

    target_profile: list[float] = []
    min_profile: list[float] = []
    max_profile: list[float] = []
    for idx in range(count):
        angle_frac = idx / count
        base_mult = _sample_smoothed_linear_series(angle_frac, base_profile)
        react_mult = _sample_smoothed_linear_series(angle_frac, react_profile)
        target = _resolve_shaper_radius_at_angle(
            angle_frac,
            base_profile=base_profile,
            react_profile=react_profile,
            weights=weights,
            staged_radius=1.0,
            bass=bass,
            mid=mid,
            high=high,
            overall=overall,
            react_strength=react_strength,
            playing=playing,
        )
        if playing:
            music_floor_mix = max(
                0.0,
                min(0.28, float(overall) * 0.10 + float(mid) * 0.08 + float(bass) * 0.04),
            )
            target += (react_mult - target) * music_floor_mix
        gap = abs(react_mult - base_mult)
        outward_allowance = min(0.10, gap * 0.12 + max(0.0, react_mult - base_mult) * 0.05)
        inward_allowance = min(0.08, gap * 0.10 + max(0.0, base_mult - react_mult) * 0.04)
        min_profile.append(max(0.08, min(base_mult, react_mult) - inward_allowance))
        max_profile.append(max(base_mult, react_mult) + outward_allowance)
        target_profile.append(target)

    vocal_energy = max(0.0, min(1.0, float(mid) * 0.78 + float(high) * 0.18 + float(overall) * 0.10))
    residual_profile = build_contour_residual_profile(
        sample_count=count,
        time_value=time_value,
        idle_motion=float(shaper_idle_motion),
        audio_motion=float(shaper_audio_motion),
        overall_energy=float(overall),
        vocal_energy=vocal_energy,
        high_energy=float(high),
        playing=playing,
        seed=seed,
    )
    target_profile = [
        max(min_profile[idx], min(max_profile[idx], target_profile[idx] + residual_profile[idx]))
        for idx in range(count)
    ]
    target_profile = slew_profile_toward_target(
        previous_target=previous_target_profile,
        current_target=target_profile,
        base_profile=base_profile,
        dt=dt,
        attack_hz=15.5,
        release_hz=2.4 if playing else 1.8,
    )

    current_profile = list(previous_profile or ())
    current_velocity = list(previous_velocity or ())
    if len(current_profile) != count:
        current_profile = list(base_profile[:count])
    if len(current_velocity) != count:
        current_velocity = [0.0] * count

    solved_profile, solved_velocity = solve_profile_step(
        current_profile=current_profile,
        current_velocity=current_velocity,
        target_profile=target_profile,
        min_profile=min_profile,
        max_profile=max_profile,
        dt=dt,
        stiffness=22.0 if playing else 15.0,
        damping=11.0 if playing else 13.0,
        neighbor_strength=14.0 if playing else 10.0,
        smoothing_passes=4 if playing else 3,
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
    current_ts = float(getattr(s, "_last_update_ts", 0.0) or 0.0)
    if current_ts <= 0.0:
        current_ts = time.monotonic()
    previous_ts = float(getattr(s, "_blob_shaper_solver_ts", 0.0) or 0.0)
    dt = current_ts - previous_ts if previous_ts > 0.0 else (1.0 / 60.0)
    dt = max(1.0 / 240.0, min(0.05, dt))

    seed = getattr(s, "_blob_shaper_solver_seed", None)
    if seed is None:
        seed = ((id(s) % 10007) / 10007.0) * math.tau
        setattr(s, "_blob_shaper_solver_seed", seed)

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
        react_strength=float(getattr(s, "_blob_shaper_react_strength", 1.0)),
        shaper_idle_motion=float(getattr(s, "_blob_shaper_idle_motion", 0.18)),
        shaper_audio_motion=float(getattr(s, "_blob_shaper_audio_motion", 1.20)),
        playing=bool(getattr(s, "_playing", False)),
        seed=float(seed),
    )
    setattr(s, "_blob_shaper_runtime_profile", solved_profile)
    setattr(s, "_blob_shaper_runtime_velocity", solved_velocity)
    setattr(s, "_blob_shaper_runtime_target_profile", target_profile)
    setattr(s, "_blob_shaper_solver_ts", current_ts)
    return solved_profile
