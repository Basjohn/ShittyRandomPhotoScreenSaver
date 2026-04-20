"""Goo mode unified liquid field solver.

One unified metaball system with sources anchored to all four card edges,
advancing inward to create organic tendrils that merge into a connected
liquid mass.  Void pockets are the natural gaps between tendrils — no
artificial dual-field barrier needed.

Sources are solved on the CPU/UI thread and packed into a fixed-size vec4
array for the Goo fragment shader.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List

# Edge ids
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


@dataclass
class GooSource:
    """A single Goo metaball source."""

    edge: int
    home_t: float
    t: float
    depth: float
    radius: float
    energy: float
    band: int
    phase: float
    # Per-source variation baked at seed time
    depth_scale: float = 1.0  # 0.6-1.4 multiplier on max depth
    radius_scale: float = 1.0  # 0.7-1.3 multiplier on base radius

    def pos(self, *, boundary_margin: float) -> tuple[float, float]:
        """Return normalized UV position constrained to safe margins."""
        m = max(0.005, min(0.15, float(boundary_margin)))
        t = max(m, min(1.0 - m, self.t))
        d = max(0.0, min(0.50, self.depth))
        if self.edge == EDGE_TOP:
            return (t, m + d)
        if self.edge == EDGE_RIGHT:
            return (1.0 - (m + d), t)
        if self.edge == EDGE_BOTTOM:
            return (t, 1.0 - (m + d))
        # EDGE_LEFT
        return (m + d, t)


@dataclass
class GooFieldState:
    """Unified goo source state + diagnostics."""

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
    """Seed the unified source system deterministically."""
    rng = random.Random(seed or 0x60060)
    count = max(16, min(GOO_SOURCE_COUNT_MAX, int(source_count)))
    bands = _build_band_plan(count, rng=rng)
    state.sources = []

    # Distribute sources across all 4 edges, with slight variation in density
    per_edge = count // 4
    remainder = count - per_edge * 4
    edge_counts = [per_edge] * 4
    for i in range(remainder):
        edge_counts[i % 4] += 1

    idx = 0
    for edge_id, edge_count in enumerate(edge_counts):
        for slot in range(edge_count):
            # Stagger positions along edge with jitter for organic feel
            t = (slot + 0.5) / edge_count + rng.uniform(-0.06, 0.06)
            t = max(0.03, min(0.97, t))
            # Wide depth variance — some sources reach deep (tendrils),
            # others stay shallow (bays), creating the mock's complex topology
            depth_scale = rng.uniform(0.30, 1.70)
            radius_scale = rng.uniform(0.50, 1.55)
            state.sources.append(
                GooSource(
                    edge=edge_id,
                    home_t=t,
                    t=t,
                    depth=0.08 + rng.uniform(0.0, 0.12),
                    radius=0.11 + rng.uniform(-0.02, 0.05),
                    energy=0.0,
                    band=bands[idx % len(bands)],
                    phase=rng.uniform(0.0, math.tau),
                    depth_scale=depth_scale,
                    radius_scale=radius_scale,
                )
            )
            idx += 1

    state.time = 0.0
    state.seeded = True
    state.boundary_clamp_count = 0
    state.source_saturation_ratio = 0.0



def _integrate_energy(current: float, target: float, *, dt: float, attack: float, release: float) -> float:
    rate = attack if target > current else release
    return current + (target - current) * min(1.0, dt * max(0.1, rate))


def _enforce_boundary(
    src: GooSource,
    *,
    boundary_margin: float,
    max_depth: float,
    max_radius: float,
) -> int:
    """Clamp one source to safe ranges and return applied clamp count."""
    clamps = 0
    r = max(0.02, min(max_radius, src.radius))
    if abs(r - src.radius) > 1e-7:
        src.radius = r
        clamps += 1
    d = max(0.0, min(max_depth, src.depth))
    if abs(d - src.depth) > 1e-7:
        src.depth = d
        clamps += 1
    t = max(boundary_margin, min(1.0 - boundary_margin, src.t))
    if abs(t - src.t) > 1e-7:
        src.t = t
        clamps += 1
    return clamps


def solve_goo_field_step(
    state: GooFieldState,
    *,
    dt: float,
    energy_bands,
    playing: bool,
    advance_speed: float,
    retreat_speed: float,
    source_count: int,
    growth: float,
    void_floor: float,
    boundary_margin: float,
    seed: int = 0,
) -> None:
    """Advance the unified goo field.

    Sources advance inward from card edges proportional to their band energy.
    Idle sources stay at moderate depth for pleasant organic coverage.
    """
    target_count = max(16, min(GOO_SOURCE_COUNT_MAX, int(source_count)))
    if not state.seeded or len(state.sources) != target_count:
        seed_goo_field(state, target_count, seed=seed)

    dt = max(0.001, min(0.1, float(dt)))
    state.time += dt
    boundary_margin = max(0.005, min(0.10, float(boundary_margin)))
    void_floor = max(0.0, min(0.40, float(void_floor)))
    growth = max(0.5, min(8.0, float(growth)))

    overall = _band_energy(energy_bands, BAND_OVERALL)

    # Max depth sources can reach — void_floor directly limits penetration
    # so the center void stays prominent even at peak energy.
    max_depth = max(0.15, min(0.40, (0.50 - void_floor) * 0.78))
    max_radius = max(0.08, min(0.32, 0.13 + growth * 0.028))

    state.boundary_clamp_count = 0
    sat = 0
    total = max(1, len(state.sources))

    for src in state.sources:
        band_e = _band_energy(energy_bands, src.band)

        if not playing:
            # Idle: gentle organic breathing, sources stay at moderate depth
            band_e = max(0.08 + overall * 0.12, band_e * 0.30)

        src.energy = _integrate_energy(
            src.energy,
            band_e,
            dt=dt,
            attack=10.0 * advance_speed,
            release=3.5 * retreat_speed,
        )
        src.energy = max(0.0, min(1.6, src.energy))

        # Idle floor — sources never fully retreat, keeping organic coverage
        idle_floor = 0.12 + math.sin(state.time * 0.22 + src.phase) * 0.025
        # Audio-driven depth with per-source variation
        audio_depth = src.energy * max_depth * 0.85 * src.depth_scale
        target_depth = max(idle_floor, audio_depth)

        src.depth = _integrate_energy(
            src.depth,
            target_depth,
            dt=dt,
            attack=3.5 * advance_speed,
            release=2.8 * retreat_speed,
        )

        # Organic tangential wobble along the edge
        wobble_slow = math.sin(state.time * 0.35 + src.phase) * 0.025
        wobble_fast = math.sin(state.time * 1.4 + src.phase * 1.7) * 0.012
        # Audio-reactive slide along edge
        slide = math.sin(state.time * 0.9 + src.phase * 0.6) * src.energy * 0.06
        src.t = src.home_t + wobble_slow + wobble_fast + slide

        # Radius — larger when energized, varied per-source for diverse pool sizes
        target_radius = (0.10 + src.energy * (0.10 + growth * 0.020)) * src.radius_scale
        src.radius = _integrate_energy(src.radius, target_radius, dt=dt, attack=5.0, release=4.0)

        state.boundary_clamp_count += _enforce_boundary(
            src,
            boundary_margin=boundary_margin,
            max_depth=max_depth,
            max_radius=max_radius,
        )
        if src.depth >= max_depth * 0.85:
            sat += 1

    state.source_saturation_ratio = float(sat) / float(total)



def pack_sources_for_upload(
    state: GooFieldState,
    source_count: int,
    *,
    boundary_margin: float,
) -> List[List[float]]:
    """Return a fixed-size vec4 array for the shader."""
    limit = max(0, min(GOO_SOURCE_COUNT_MAX, int(source_count)))
    out: List[List[float]] = []
    for src in state.sources[:limit]:
        x, y = src.pos(boundary_margin=boundary_margin)
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
    "GooSource",
    "GooFieldState",
    "seed_goo_field",
    "solve_goo_field_step",
    "pack_sources_for_upload",
]
