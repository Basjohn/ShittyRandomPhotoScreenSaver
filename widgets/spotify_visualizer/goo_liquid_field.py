"""Goo mode spline-contour solver.

Goo now uses a smooth, closed contour that defines a central void boundary.
The shader renders liquid *outside* this contour, producing a connected ring
around the card edges with an explicit center hole (mock-aligned topology).

The contour points are solved on the CPU/UI thread and packed into a fixed-size
vec4 array for the Goo fragment shader:
    vec4(x, y, radius_meta, energy_meta)
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List

# Legacy edge ids kept for compatibility with older imports/tests.
EDGE_TOP = 0
EDGE_RIGHT = 1
EDGE_BOTTOM = 2
EDGE_LEFT = 3

# Band ids
BAND_BASS = 0
BAND_MID = 1
BAND_HIGH = 2
BAND_OVERALL = 3

GOO_SOURCE_COUNT_MAX = 64
GOO_SOURCE_COUNT_MIN = 24


@dataclass
class GooSource:
    """A single Goo spline control point."""

    home_angle: float
    angle: float
    home_radius: float
    radius: float
    energy: float
    band: int
    phase: float
    drift: float = 0.0
    velocity: float = 0.0


@dataclass
class GooFieldState:
    """Spline contour state + diagnostics."""

    sources: List[GooSource] = field(default_factory=list)
    time: float = 0.0
    seeded: bool = False
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


def seed_goo_field(state: GooFieldState, source_count: int, *, seed: int = 0) -> None:
    """Seed the spline contour deterministically."""
    rng = random.Random(seed or 0x60060)
    count = max(GOO_SOURCE_COUNT_MIN, min(GOO_SOURCE_COUNT_MAX, int(source_count)))
    bands = _build_band_plan(count, rng=rng)
    state.sources = []

    for i in range(count):
        t = float(i) / float(count)
        # Idle contour must begin as an even spline circle.
        angle = t * math.tau
        home_radius = 0.18
        state.sources.append(
            GooSource(
                home_angle=angle,
                angle=angle,
                home_radius=home_radius,
                radius=home_radius,
                energy=0.0,
                band=bands[i % len(bands)],
                phase=rng.uniform(0.0, math.tau),
                drift=0.0,
                velocity=0.0,
            )
        )

    state.time = 0.0
    state.seeded = True
    state.boundary_clamp_count = 0
    state.source_saturation_ratio = 0.0


def _integrate_energy(current: float, target: float, *, dt: float, attack: float, release: float) -> float:
    rate = attack if target > current else release
    return current + (target - current) * min(1.0, dt * max(0.1, rate))


def _periodic_smooth(values: List[float], *, strength: float, passes: int) -> List[float]:
    """Diffuse neighboring radius deltas to guarantee soft curvature."""
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


def solve_goo_field_step(
    state: GooFieldState,
    *,
    dt: float,
    energy_bands,
    playing: bool,
    core_size: float,
    edge_inward_depth: float,
    boundary_margin: float,
    seed: int = 0,
) -> None:
    """Advance the smooth closed contour.

    Audio raises/lowers a central void boundary while preserving continuity,
    enabling grow/recede/tendril behavior without sharp corners.
    """
    target_count = GOO_SOURCE_COUNT_MAX
    if not state.seeded or len(state.sources) != target_count:
        seed_goo_field(state, target_count, seed=seed)

    dt = max(0.001, min(0.1, float(dt)))
    state.time += dt
    boundary_margin = max(0.005, min(0.10, float(boundary_margin)))
    core_size = max(0.06, min(0.30, float(core_size)))
    edge_inward_depth = max(0.0, min(0.45, float(edge_inward_depth)))

    bass = _band_energy(energy_bands, BAND_BASS)
    mid = _band_energy(energy_bands, BAND_MID)
    high = _band_energy(energy_bands, BAND_HIGH)
    overall = _band_energy(energy_bands, BAND_OVERALL)
    drive = max(0.0, min(1.4, bass * 0.42 + overall * 0.33 + mid * 0.18 + high * 0.07))
    if not playing:
        drive *= 0.45

    # Core size is a visual sizing control, mapped to a stable radius envelope.
    base_core_radius = 0.03 + core_size * 0.27
    expansion = drive * 0.035
    target_global_radius = base_core_radius + expansion

    min_radius = max(0.03, 0.03 + boundary_margin * 1.0)
    max_radius = min(0.46 - boundary_margin * 0.80, 0.455)

    state.boundary_clamp_count = 0
    sat = 0
    total = max(1, len(state.sources))

    # Keep the core contour perfectly circular before deformation stages.
    global_breathe = math.sin(state.time * 0.42) * (0.0012 + drive * 0.0018)

    for src in state.sources:
        band_e = _band_energy(energy_bands, src.band)
        if not playing:
            band_e = max(0.06, band_e * 0.35)

        src.energy = _integrate_energy(src.energy, band_e, dt=dt, attack=8.0, release=2.8)
        src.energy = max(0.0, min(1.6, src.energy))

        # `edge_inward_depth` is intentionally not applied to the core in this
        # stage; it drives the outer layer until contour deformation starts.
        _ = edge_inward_depth
        target_radius = target_global_radius + global_breathe
        src.radius = _integrate_energy(src.radius, target_radius, dt=dt, attack=5.0, release=4.0)

        # Keep point ordering deterministic in this stabilization pass.
        src.angle = src.home_angle
        if src.angle < 0.0:
            src.angle += math.tau
        elif src.angle >= math.tau:
            src.angle -= math.tau

    # Global curvature smoothing: this is the key anti-sharpness guardrail.
    smoothed = _periodic_smooth(
        [float(src.radius) for src in state.sources],
        strength=0.42 + (1.0 - min(1.0, drive)) * 0.18,
        passes=5,
    )

    # Clamp point-to-neighbor deviation to suppress hard corners under spikes.
    limited = list(smoothed)
    n = len(limited)
    max_corner_dev = 0.045
    for i in range(n):
        neighbor_mid = (smoothed[(i - 1) % n] + smoothed[(i + 1) % n]) * 0.5
        delta = smoothed[i] - neighbor_mid
        if delta > max_corner_dev:
            limited[i] = neighbor_mid + max_corner_dev
        elif delta < -max_corner_dev:
            limited[i] = neighbor_mid - max_corner_dev
    smoothed = _periodic_smooth(limited, strength=0.40, passes=3)

    for i, src in enumerate(state.sources):
        candidate = smoothed[i]
        src.radius = max(min_radius, min(max_radius, candidate))
        if abs(src.radius - candidate) > 1e-7:
            state.boundary_clamp_count += 1
        if src.radius >= (max_radius - 0.020):
            sat += 1

    state.source_saturation_ratio = float(sat) / float(total)


def pack_sources_for_upload(
    state: GooFieldState,
    source_count: int,
    *,
    aspect: float = 1.0,
    boundary_margin: float,
) -> List[List[float]]:
    """Return a fixed-size vec4 array for the shader."""
    limit = max(GOO_SOURCE_COUNT_MIN, min(GOO_SOURCE_COUNT_MAX, int(source_count)))
    boundary_margin = max(0.005, min(0.10, float(boundary_margin)))
    out: List[List[float]] = []

    # Pre-compensate for card aspect to keep idle contour circular on screen.
    aspect = max(0.4, min(3.0, float(aspect)))
    axis_x = 1.0 / aspect
    axis_y = 1.0
    min_xy = boundary_margin + 0.004
    max_xy = 1.0 - min_xy

    ordered = sorted(state.sources[:limit], key=lambda s: s.angle)
    for src in ordered:
        x = 0.5 + math.cos(src.angle) * (src.radius * axis_x)
        y = 0.5 + math.sin(src.angle) * (src.radius * axis_y)
        x = max(min_xy, min(max_xy, x))
        y = max(min_xy, min(max_xy, y))
        out.append([float(x), float(y), float(src.radius), float(src.energy)])
    while len(out) < limit:
        out.append([0.0, 0.0, 0.0, 0.0])
    return out



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
    "GooSource",
    "GooFieldState",
    "seed_goo_field",
    "solve_goo_field_step",
    "pack_sources_for_upload",
]
