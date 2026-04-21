"""Goo mode dual-spline liquid solver.

This solver produces two smooth closed contours:
- Edge contour: the inward border of the outer liquid sheet.
- Core contour: the central liquid body.

The gap between them is intentional void space. Both contours are solved on
the CPU and uploaded to the shader as fixed-size vec4 arrays.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List

EDGE_TOP = 0
EDGE_RIGHT = 1
EDGE_BOTTOM = 2
EDGE_LEFT = 3

BAND_BASS = 0
BAND_MID = 1
BAND_HIGH = 2
BAND_OVERALL = 3

GOO_SOURCE_COUNT_MAX = 64
GOO_SOURCE_COUNT_MIN = 24


@dataclass
class GooContourSource:
    """One spline control source for either edge or core contour."""

    home_angle: float
    angle: float
    radius: float
    energy: float
    band: int
    phase: float
    velocity: float = 0.0


@dataclass
class GooDualFieldState:
    """Runtime dual-contour state + diagnostics."""

    edge_sources: List[GooContourSource] = field(default_factory=list)
    core_sources: List[GooContourSource] = field(default_factory=list)
    time: float = 0.0
    seeded: bool = False
    gap_violation_count: int = 0
    boundary_clamp_count: int = 0
    source_saturation_ratio: float = 0.0


def _band_energy(energy_bands, band: int) -> float:
    if energy_bands is None:
        return 0.0
    try:
        if band == BAND_BASS:
            return float(getattr(energy_bands, "bass", 0.0) or 0.0)
        if band == BAND_MID:
            return float(getattr(energy_bands, "mid", 0.0) or 0.0)
        if band == BAND_HIGH:
            return float(getattr(energy_bands, "high", 0.0) or 0.0)
        return float(getattr(energy_bands, "overall", 0.0) or 0.0)
    except Exception:
        return 0.0


def _build_band_plan(total: int, *, rng: random.Random) -> list[int]:
    counts = {
        BAND_BASS: max(1, round(total * 0.38)),
        BAND_MID: max(1, round(total * 0.28)),
        BAND_HIGH: max(1, round(total * 0.22)),
        BAND_OVERALL: max(1, round(total * 0.12)),
    }
    drift = sum(counts.values()) - total
    counts[BAND_OVERALL] = max(1, counts[BAND_OVERALL] - drift)
    out: list[int] = []
    for band, count in counts.items():
        out.extend([band] * count)
    rng.shuffle(out)
    return out


def _integrate_energy(current: float, target: float, *, dt: float, attack: float, release: float) -> float:
    rate = attack if target > current else release
    return current + (target - current) * min(1.0, dt * max(0.1, rate))


def _periodic_smooth(values: List[float], *, strength: float, passes: int) -> List[float]:
    if not values:
        return values
    out = list(values)
    n = len(out)
    strength = max(0.0, min(1.0, float(strength)))
    passes = max(0, int(passes))
    for _ in range(passes):
        nxt = list(out)
        for i in range(n):
            avg = (out[(i - 1) % n] + out[(i + 1) % n]) * 0.5
            nxt[i] = out[i] + (avg - out[i]) * strength
        out = nxt
    return out


def _limit_corner_deviation(values: List[float], *, max_dev: float) -> List[float]:
    if not values:
        return values
    out = list(values)
    n = len(out)
    max_dev = max(0.0, float(max_dev))
    for i in range(n):
        neighbor_mid = (values[(i - 1) % n] + values[(i + 1) % n]) * 0.5
        delta = values[i] - neighbor_mid
        if delta > max_dev:
            out[i] = neighbor_mid + max_dev
        elif delta < -max_dev:
            out[i] = neighbor_mid - max_dev
    return out


def _superellipse_radius(angle: float, hx: float, hy: float, n: float) -> float:
    c = abs(math.cos(angle))
    s = abs(math.sin(angle))
    tx = (c / max(hx, 1e-6)) ** n
    ty = (s / max(hy, 1e-6)) ** n
    denom = max(1e-16, tx + ty)
    return denom ** (-1.0 / n)


def _angular_distance(a: float, b: float) -> float:
    return abs((a - b + math.pi) % math.tau - math.pi)


def seed_goo_dual_field(state: GooDualFieldState, source_count: int, *, seed: int = 0) -> None:
    """Seed edge/core source rings deterministically."""
    rng = random.Random(seed or 0xB16B00B5)
    count = max(GOO_SOURCE_COUNT_MIN, min(GOO_SOURCE_COUNT_MAX, int(source_count)))
    bands = _build_band_plan(count, rng=rng)

    state.edge_sources = []
    state.core_sources = []
    for i in range(count):
        t = float(i) / float(count)
        angle = t * math.tau
        band = bands[i % len(bands)]
        state.edge_sources.append(
            GooContourSource(
                home_angle=angle,
                angle=angle,
                radius=0.40,
                energy=0.0,
                band=band,
                phase=rng.uniform(0.0, math.tau),
                velocity=0.0,
            )
        )
        state.core_sources.append(
            GooContourSource(
                home_angle=angle,
                angle=angle,
                radius=0.09,
                energy=0.0,
                band=band,
                phase=rng.uniform(0.0, math.tau),
                velocity=0.0,
            )
        )

    state.time = 0.0
    state.seeded = True
    state.gap_violation_count = 0
    state.boundary_clamp_count = 0
    state.source_saturation_ratio = 0.0


def solve_goo_dual_field_step(
    state: GooDualFieldState,
    *,
    dt: float,
    energy_bands,
    playing: bool,
    core_size: float,
    edge_inward_depth: float,
    boundary_margin: float,
    aspect: float,
    seed: int = 0,
) -> None:
    """Advance edge and core contour sources one step."""
    target_count = GOO_SOURCE_COUNT_MAX
    if (
        not state.seeded
        or len(state.edge_sources) != target_count
        or len(state.core_sources) != target_count
    ):
        seed_goo_dual_field(state, target_count, seed=seed)

    dt = max(0.001, min(0.10, float(dt)))
    state.time += dt
    boundary_margin = max(0.005, min(0.10, float(boundary_margin)))
    core_size = max(0.06, min(0.30, float(core_size)))
    edge_inward_depth = max(0.0, min(0.45, float(edge_inward_depth)))
    aspect = max(0.4, min(3.0, float(aspect)))

    bass = _band_energy(energy_bands, BAND_BASS)
    mid = _band_energy(energy_bands, BAND_MID)
    high = _band_energy(energy_bands, BAND_HIGH)
    overall = _band_energy(energy_bands, BAND_OVERALL)
    drive = max(0.0, min(1.4, bass * 0.42 + overall * 0.33 + mid * 0.18 + high * 0.07))
    if playing:
        # Active path must always read stronger than idle, even on quiet tracks.
        drive = max(drive, 0.20)
    else:
        drive *= 0.35

    phase = state.time * (0.110 + 0.090 * drive)
    slow_a = state.time * (0.085 + bass * 0.034)
    slow_b = state.time * (0.100 + mid * 0.030)
    slow_c = state.time * (0.130 + high * 0.026)

    # Outer edge base envelope in UV-space mapped to isotropic metric space.
    hx_base_uv = max(0.28, 0.430 - boundary_margin * 0.90)
    hy_base_uv = max(0.25, 0.385 - boundary_margin * 1.10)
    hx_cap_uv = max(hx_base_uv + 0.060, 0.499 - boundary_margin * 0.16)
    hy_cap_uv = max(hy_base_uv + 0.060, 0.468 - boundary_margin * 0.22)
    hx_base_iso = hx_base_uv * aspect
    hx_cap_iso = hx_cap_uv * aspect
    hy_base_iso = hy_base_uv
    hy_cap_iso = hy_cap_uv
    # Higher exponent packs the contour closer to card corners at idle/active,
    # reducing wasted corner workspace before tendril phases.
    n_shape = 7.2

    # Core stays near circular but architecture supports deformation.
    core_base_radius = 0.030 + core_size * 0.34
    core_wobble_amp = (0.0030 + drive * 0.0100) * (0.55 + edge_inward_depth * 1.45)
    if not playing:
        core_wobble_amp *= 0.35
    core_global_push = drive * 0.0020

    # Keep a robust void band between core and edge until later phases.
    gap_floor = max(0.080, 0.112 + boundary_margin * 0.26 - core_size * 0.05)

    base_ang = phase * 0.83 + math.sin(slow_a) * 0.30 + overall * 1.05
    # Keep low slider values from killing visible motion, but damp very high
    # depths to avoid cap-lock in stress conditions.
    depth_norm = max(0.0, min(1.0, edge_inward_depth / 0.45))
    effective_depth = max(edge_inward_depth, 0.22)
    depth_damp = 1.0 - max(0.0, edge_inward_depth - 0.28) * 1.55
    depth_damp = max(0.62, min(1.10, depth_damp))

    edge_targets: list[float] = []
    core_targets: list[float] = []
    for edge_src, core_src in zip(state.edge_sources, state.core_sources):
        angle = edge_src.home_angle
        edge_src.angle = angle
        core_src.angle = angle

        band_e = _band_energy(energy_bands, edge_src.band)
        if not playing:
            band_e = max(0.05, band_e * 0.35)
        edge_src.energy = _integrate_energy(edge_src.energy, band_e, dt=dt, attack=6.5, release=2.7)
        core_src.energy = edge_src.energy

        base_edge = _superellipse_radius(angle, hx_base_iso, hy_base_iso, n_shape)
        edge_cap = _superellipse_radius(angle, hx_cap_iso, hy_cap_iso, n_shape)

        wave_raw = (
            math.sin(angle * 1.0 + phase * 1.08 + math.sin(slow_c) * 0.66) * 0.52
            + math.sin(angle * 3.0 - phase * 0.82 + math.cos(slow_b) * 0.58 + 1.2) * 0.31
            + math.sin(angle * 5.0 + phase * 0.54 + math.sin(slow_a) * 0.44 + 2.1) * 0.17
        )
        wave = 0.5 + 0.5 * max(-1.0, min(1.0, wave_raw))
        harmonic_raw = (
            math.sin(angle * 2.0 + phase * 1.22 + edge_src.phase * 0.42) * 0.42
            + math.sin(angle * 4.0 - phase * 0.95 + edge_src.phase * 0.27 + 1.4) * 0.34
            + math.sin(angle * 6.0 + phase * 0.70 + 2.5) * 0.24
        )
        harmonic = 0.5 + 0.5 * max(-1.0, min(1.0, harmonic_raw))

        # Constant energy lane: keep all sections subtly alive even when
        # reactive packets are weak, preventing stale quadrants.
        constant_raw = (
            math.sin(angle * 1.0 + slow_a * 0.92 + edge_src.phase * 0.46) * 0.50
            + math.sin(angle * 3.0 - slow_b * 0.78 + edge_src.phase * 0.29 + 0.9) * 0.32
            + math.sin(angle * 5.0 + slow_c * 0.64 + 2.2) * 0.18
        )
        constant_wave = 0.5 + 0.5 * max(-1.0, min(1.0, constant_raw))
        constant_support = 0.30 + 0.70 * constant_wave

        # Reactive energy lane: moving packet field for tendril growth without
        # fixed corner/axis alternation.
        packet_acc = 0.0
        packet_peak = 0.0
        packet_count = 6
        for k in range(packet_count):
            kf = float(k)
            center = (
                base_ang
                + kf * (math.tau / float(packet_count))
                + math.sin(state.time * (0.22 + 0.018 * kf) + kf * 1.27) * 0.55
            )
            width = 0.24 + 0.040 * math.sin(state.time * 0.17 + kf * 0.71)
            width = max(0.17, width)
            diff = _angular_distance(angle, center)
            lobe = math.exp(-(diff * diff) / max(1e-6, 2.0 * width * width))
            breathe = 0.74 + 0.26 * math.sin(state.time * (0.33 + 0.012 * kf) + edge_src.phase * 0.54 + kf * 0.49)
            pkt = lobe * max(0.0, breathe)
            packet_acc += pkt
            packet_peak = max(packet_peak, pkt)

        packet_field = packet_acc / float(packet_count)
        packet_peak = max(0.0, min(1.2, packet_peak))
        packet_mix = max(packet_field, packet_peak * 0.82)
        reactive_gate = max(0.0, min(1.0, (drive - 0.09) / 0.90))
        reactive_support = (
            packet_mix * (0.70 + 0.46 * packet_peak)
            * reactive_gate
            * (0.62 + 0.38 * edge_src.energy)
        )

        tendril_seed = max(
            0.0,
            min(
                1.0,
                (packet_mix - (0.44 - 0.18 * drive)) / max(1e-5, 0.22 + 0.06 * drive),
            ),
        )
        tendril_seed = tendril_seed * tendril_seed * (3.0 - 2.0 * tendril_seed)
        persistence = 0.70 + 0.30 * (
            0.5 + 0.5 * math.sin(state.time * 0.31 + edge_src.phase * 0.9)
        )
        # Local tendril memory: keeps protrusions alive long enough to read as
        # growth, instead of instant in-out jitter that looks like shrinkage.
        tendril_drive = tendril_seed * (0.55 + 0.45 * drive)
        edge_src.velocity = _integrate_energy(
            edge_src.velocity,
            tendril_drive,
            dt=dt,
            attack=16.0,
            release=0.85 if playing else 3.2,
        )
        tendril_memory = max(0.0, min(1.5, edge_src.velocity))

        # Growth-only response for this stage with constant + reactive lanes.
        tendril_support = tendril_seed * persistence
        wave_lobe = max(0.0, wave - 0.50)
        harmonic_lobe = max(0.0, harmonic - 0.62)
        lobe = (
            constant_support * 0.14
            + wave_lobe * 0.96
            + harmonic_lobe * 0.80
            + reactive_support * 3.70
            + tendril_support * 5.60
            + tendril_memory * 4.40
        )

        if playing:
            growth_amp = effective_depth * depth_damp * (0.070 + 0.360 * drive + 0.190 * edge_src.energy)
            baseline = effective_depth * depth_damp * (0.003 + 0.010 * drive)
        else:
            growth_amp = edge_inward_depth * (0.010 + 0.045 * drive + 0.020 * edge_src.energy)
            baseline = edge_inward_depth * 0.0042

        span = max(1e-4, edge_cap - base_edge)
        raw_growth = baseline + lobe * growth_amp
        # Soft headroom saturation avoids hard cap-lock while preserving shape.
        compress = 0.30 + 0.18 * drive
        edge_growth = span * (1.0 - math.exp(-(raw_growth / span) * compress))
        edge_target = max(base_edge, min(edge_cap, base_edge + edge_growth))
        if playing:
            # Non-ratcheting active rest floor: keeps workspace available at
            # sides/corners but does not accumulate toward cap-lock.
            rest_floor = base_edge + span * (0.50 + depth_norm * 0.28 + drive * 0.05)
            edge_target = max(edge_target, min(edge_cap, rest_floor))
        edge_targets.append(edge_target)

        core_wave = (
            math.sin(angle * 2.0 + phase * 0.25 + core_src.phase * 0.50) * 0.50
            + math.sin(angle * 3.0 - phase * 0.20 + core_src.phase * 0.30 + 1.5) * 0.30
            + math.sin(angle * 4.0 + phase * 0.14 + 2.8) * 0.20
        )
        core_target = core_base_radius + core_global_push + core_wave * core_wobble_amp * (0.55 + 0.45 * core_src.energy)
        core_target = max(core_base_radius - core_wobble_amp * 0.90, min(core_base_radius + core_wobble_amp * 1.20, core_target))
        core_targets.append(core_target)

    # Smooth targets to guarantee spline-only curvature (no sharp corners).
    if playing:
        edge_smoothed = _periodic_smooth(edge_targets, strength=0.078 + (1.0 - min(1.0, drive)) * 0.022, passes=1)
        edge_smoothed = _limit_corner_deviation(edge_smoothed, max_dev=0.042)
        edge_smoothed = _periodic_smooth(edge_smoothed, strength=0.074, passes=1)
    else:
        edge_smoothed = _periodic_smooth(edge_targets, strength=0.118, passes=2)
        edge_smoothed = _limit_corner_deviation(edge_smoothed, max_dev=0.030)
        edge_smoothed = _periodic_smooth(edge_smoothed, strength=0.104, passes=2)

    core_smoothed = _periodic_smooth(core_targets, strength=0.56, passes=7)
    core_smoothed = _limit_corner_deviation(core_smoothed, max_dev=0.010)
    core_smoothed = _periodic_smooth(core_smoothed, strength=0.50, passes=4)

    state.gap_violation_count = 0
    state.boundary_clamp_count = 0
    sat = 0
    total = max(1, len(state.edge_sources))

    for i, (edge_src, core_src) in enumerate(zip(state.edge_sources, state.core_sources)):
        angle = edge_src.home_angle
        edge_base = _superellipse_radius(angle, hx_base_iso, hy_base_iso, n_shape)
        edge_cap = _superellipse_radius(angle, hx_cap_iso, hy_cap_iso, n_shape)

        core_candidate = max(0.028, min(0.260, core_smoothed[i]))
        edge_candidate = edge_smoothed[i]
        clamped = False
        if edge_candidate < edge_base:
            edge_candidate = edge_base
            clamped = True
        min_edge = core_candidate + gap_floor
        if edge_candidate < min_edge:
            edge_candidate = min_edge
            state.gap_violation_count += 1
            clamped = True
        if edge_candidate > edge_cap:
            edge_candidate = edge_cap
            clamped = True

        # Integrate at controlled rates so motion reads liquid, not jittery.
        new_edge = _integrate_energy(
            edge_src.radius,
            edge_candidate,
            dt=dt,
            attack=16.0,
            release=0.65 if playing else 11.0,
        )
        new_core = _integrate_energy(core_src.radius, core_candidate, dt=dt, attack=5.5, release=3.8)

        edge_src.radius = max(edge_base, min(edge_cap, new_edge))
        core_src.radius = max(0.028, min(0.260, new_core))
        if abs(edge_src.radius - new_edge) > 1e-8 or abs(core_src.radius - new_core) > 1e-8:
            clamped = True
        if clamped:
            state.boundary_clamp_count += 1

        if edge_src.radius >= (edge_cap - 0.002):
            sat += 1

    state.source_saturation_ratio = float(sat) / float(total)


def _pack_contour(
    sources: list[GooContourSource],
    limit: int,
    *,
    aspect: float,
    boundary_margin: float,
) -> List[List[float]]:
    out: List[List[float]] = []
    axis_x = 1.0 / max(0.4, min(3.0, float(aspect)))
    axis_y = 1.0
    min_xy = boundary_margin + 0.004
    max_xy = 1.0 - min_xy
    ordered = sorted(sources[:limit], key=lambda s: s.angle)
    for src in ordered:
        x = 0.5 + math.cos(src.angle) * (src.radius * axis_x)
        y = 0.5 + math.sin(src.angle) * (src.radius * axis_y)
        x = max(min_xy, min(max_xy, x))
        y = max(min_xy, min(max_xy, y))
        out.append([float(x), float(y), float(src.radius), float(src.energy)])
    while len(out) < limit:
        out.append([0.0, 0.0, 0.0, 0.0])
    return out


def pack_dual_sources_for_upload(
    state: GooDualFieldState,
    source_count: int,
    *,
    aspect: float = 1.0,
    boundary_margin: float,
) -> tuple[List[List[float]], List[List[float]]]:
    """Pack edge/core source arrays for shader upload."""
    limit = max(GOO_SOURCE_COUNT_MIN, min(GOO_SOURCE_COUNT_MAX, int(source_count)))
    boundary_margin = max(0.005, min(0.10, float(boundary_margin)))
    edge = _pack_contour(
        state.edge_sources,
        limit,
        aspect=aspect,
        boundary_margin=boundary_margin,
    )
    core = _pack_contour(
        state.core_sources,
        limit,
        aspect=aspect,
        boundary_margin=boundary_margin,
    )
    return edge, core


__all__ = [
    "EDGE_TOP",
    "EDGE_RIGHT",
    "EDGE_BOTTOM",
    "EDGE_LEFT",
    "BAND_BASS",
    "BAND_MID",
    "BAND_HIGH",
    "BAND_OVERALL",
    "GOO_SOURCE_COUNT_MAX",
    "GOO_SOURCE_COUNT_MIN",
    "GooContourSource",
    "GooDualFieldState",
    "seed_goo_dual_field",
    "solve_goo_dual_field_step",
    "pack_dual_sources_for_upload",
]
