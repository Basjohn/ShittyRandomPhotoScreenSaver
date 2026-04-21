from __future__ import annotations

import math

from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.goo_liquid_field import (
    GOO_SOURCE_COUNT_MIN,
    GooDualFieldState,
    pack_dual_sources_for_upload,
    solve_goo_dual_field_step,
)


def _step(
    state: GooDualFieldState,
    *,
    bands: EnergyBands,
    playing: bool = True,
    core_size: float = 0.18,
    inward_depth: float = 0.18,
    boundary_margin: float = 0.01,
    aspect: float = 1.0,
) -> None:
    solve_goo_dual_field_step(
        state,
        dt=1.0 / 60.0,
        energy_bands=bands,
        playing=playing,
        core_size=core_size,
        edge_inward_depth=inward_depth,
        boundary_margin=boundary_margin,
        aspect=aspect,
        seed=1337,
    )


def _contour_radii(points: list[list[float]], *, aspect: float = 1.0) -> list[float]:
    axis_x = 1.0 / max(0.4, min(3.0, float(aspect)))
    axis_y = 1.0
    out: list[float] = []
    for p in points:
        if p[2] <= 0.0:
            continue
        dx = (float(p[0]) - 0.5) / axis_x
        dy = (float(p[1]) - 0.5) / axis_y
        out.append(math.sqrt(dx * dx + dy * dy))
    return out


def _edge_spread(points: list[list[float]], *, aspect: float = 1.0) -> float:
    radii = _contour_radii(points, aspect=aspect)
    if not radii:
        return 0.0
    return max(radii) - min(radii)


def _edge_protrusion_score(points: list[list[float]], *, aspect: float = 1.0) -> float:
    radii = sorted(_contour_radii(points, aspect=aspect))
    if len(radii) < 8:
        return 0.0
    q60 = radii[int(len(radii) * 0.60)]
    q95 = radii[int(len(radii) * 0.95)]
    return max(0.0, q95 - q60)


def _max_turn_angle(points: list[list[float]]) -> float:
    pts = [(float(p[0]), float(p[1])) for p in points if p[2] > 0.0]
    if len(pts) < 3:
        return 0.0
    max_ang = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[(i - 1) % n]
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        v1x, v1y = x1 - x0, y1 - y0
        v2x, v2y = x2 - x1, y2 - y1
        l1 = math.sqrt(v1x * v1x + v1y * v1y)
        l2 = math.sqrt(v2x * v2x + v2y * v2y)
        if l1 <= 1e-8 or l2 <= 1e-8:
            continue
        dot = (v1x * v2x + v1y * v2y) / (l1 * l2)
        dot = max(-1.0, min(1.0, dot))
        max_ang = max(max_ang, math.acos(dot))
    return max_ang


def _has_self_intersection(points: list[list[float]]) -> bool:
    pts = [(float(p[0]), float(p[1])) for p in points if p[2] > 0.0]
    n = len(pts)
    if n < 4:
        return False

    def _orient(a, b, c) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def _segments_intersect(a, b, c, d) -> bool:
        o1 = _orient(a, b, c)
        o2 = _orient(a, b, d)
        o3 = _orient(c, d, a)
        o4 = _orient(c, d, b)
        return (o1 * o2 < 0.0) and (o3 * o4 < 0.0)

    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or j == (i + 1) % n or (i == 0 and j == n - 1):
                continue
            c = pts[j]
            d = pts[(j + 1) % n]
            if _segments_intersect(a, b, c, d):
                return True
    return False


def test_dual_contours_keep_void_and_soft_curvature_idle():
    state = GooDualFieldState()
    bands = EnergyBands(bass=0.0, mid=0.0, high=0.0, overall=0.0)
    for _ in range(240):
        _step(state, bands=bands, playing=False)
    edge, core = pack_dual_sources_for_upload(state, 64, boundary_margin=0.01)

    edge_r = _contour_radii(edge)
    core_r = _contour_radii(core)
    assert edge_r and core_r
    assert min(edge_r) > max(core_r)
    assert _max_turn_angle(edge) < 0.85
    assert _max_turn_angle(core) < 0.75
    assert not _has_self_intersection(edge)
    assert not _has_self_intersection(core)


def test_dual_contours_stay_inside_boundary_margin():
    state = GooDualFieldState()
    bands = EnergyBands(bass=0.85, mid=0.72, high=0.58, overall=0.80)
    for _ in range(220):
        _step(state, bands=bands, boundary_margin=0.01)
    edge, core = pack_dual_sources_for_upload(state, 64, boundary_margin=0.01)
    for p in edge + core:
        x, y = float(p[0]), float(p[1])
        if p[2] <= 0.0:
            continue
        assert 0.0 <= x <= 1.0
        assert 0.0 <= y <= 1.0
        assert x >= 0.005 - 1e-6
        assert x <= 1.0 - 0.005 + 1e-6
        assert y >= 0.005 - 1e-6
        assert y <= 1.0 - 0.005 + 1e-6


def test_solver_has_no_nan_or_inf_under_stress():
    state = GooDualFieldState()
    bands = EnergyBands(bass=1.5, mid=1.2, high=1.1, overall=1.4)
    for _ in range(360):
        solve_goo_dual_field_step(
            state,
            dt=1.0 / 120.0,
            energy_bands=bands,
            playing=True,
            core_size=0.30,
            edge_inward_depth=0.45,
            boundary_margin=0.01,
            aspect=1.9,
            seed=9,
        )
    for src in state.edge_sources + state.core_sources:
        assert math.isfinite(src.angle)
        assert math.isfinite(src.radius)
        assert math.isfinite(src.energy)
        assert math.isfinite(src.home_angle)
    assert math.isfinite(state.source_saturation_ratio)
    assert 0.0 <= state.source_saturation_ratio <= 1.0


def test_source_count_is_clamped_to_minimum_for_both_contours():
    state = GooDualFieldState()
    bands = EnergyBands(bass=0.2, mid=0.2, high=0.2, overall=0.2)
    for _ in range(16):
        _step(state, bands=bands)
    edge, core = pack_dual_sources_for_upload(state, 8, boundary_margin=0.01)
    assert len(state.edge_sources) >= GOO_SOURCE_COUNT_MIN
    assert len(state.core_sources) >= GOO_SOURCE_COUNT_MIN
    assert len(edge) >= GOO_SOURCE_COUNT_MIN
    assert len(core) >= GOO_SOURCE_COUNT_MIN


def test_core_size_scales_core_contour_radius():
    low = GooDualFieldState()
    high = GooDualFieldState()
    bands = EnergyBands(bass=0.0, mid=0.0, high=0.0, overall=0.0)

    for _ in range(200):
        _step(low, bands=bands, core_size=0.06, playing=False)
        _step(high, bands=bands, core_size=0.30, playing=False)

    _, low_core = pack_dual_sources_for_upload(low, 64, boundary_margin=0.01)
    _, high_core = pack_dual_sources_for_upload(high, 64, boundary_margin=0.01)
    low_r = _contour_radii(low_core)
    high_r = _contour_radii(high_core)
    assert low_r and high_r
    assert max(low_r) < min(high_r)


def test_playback_growth_does_not_shrink_edge_contour():
    idle = GooDualFieldState()
    active = GooDualFieldState()
    idle_bands = EnergyBands(bass=0.0, mid=0.0, high=0.0, overall=0.0)
    active_bands = EnergyBands(bass=1.0, mid=0.85, high=0.65, overall=0.95)

    for _ in range(220):
        _step(idle, bands=idle_bands, playing=False, inward_depth=0.35)
        _step(active, bands=active_bands, playing=True, inward_depth=0.35)

    idle_edge, _ = pack_dual_sources_for_upload(idle, 64, boundary_margin=0.01)
    active_edge, _ = pack_dual_sources_for_upload(active, 64, boundary_margin=0.01)
    idle_r = _contour_radii(idle_edge)
    active_r = _contour_radii(active_edge)
    assert idle_r and active_r
    # Growth-only intent: active contour should not contract below idle minimum.
    assert min(active_r) >= min(idle_r) - 1e-4


def test_synthetic_audio_active_deformation_exceeds_idle():
    idle = GooDualFieldState()
    active = GooDualFieldState()
    idle_bands = EnergyBands(bass=0.0, mid=0.0, high=0.0, overall=0.0)

    idle_motion: list[float] = []
    active_motion: list[float] = []
    idle_protrusions: list[float] = []
    active_protrusions: list[float] = []
    active_octant_motion = [0.0] * 8
    prev_idle_r: list[float] | None = None
    prev_active_r: list[float] | None = None
    for i in range(260):
        _step(idle, bands=idle_bands, playing=False, inward_depth=0.35, aspect=1.8)

        # Deterministic synthetic musical path with bass pulses.
        t = float(i)
        bass = 0.55 + 0.38 * (0.5 + 0.5 * math.sin(t * 0.33))
        mid = 0.38 + 0.28 * (0.5 + 0.5 * math.sin(t * 0.21 + 1.1))
        high = 0.22 + 0.20 * (0.5 + 0.5 * math.sin(t * 0.43 + 2.0))
        overall = min(1.0, bass * 0.42 + mid * 0.35 + high * 0.23)
        bands = EnergyBands(bass=bass, mid=mid, high=high, overall=overall)
        _step(active, bands=bands, playing=True, inward_depth=0.35, aspect=1.8)

        idle_edge, _ = pack_dual_sources_for_upload(idle, 64, aspect=1.8, boundary_margin=0.01)
        active_edge, _ = pack_dual_sources_for_upload(active, 64, aspect=1.8, boundary_margin=0.01)
        idle_r = _contour_radii(idle_edge, aspect=1.8)
        active_r = _contour_radii(active_edge, aspect=1.8)
        idle_protrusions.append(_edge_protrusion_score(idle_edge, aspect=1.8))
        active_protrusions.append(_edge_protrusion_score(active_edge, aspect=1.8))
        if prev_idle_r is not None and prev_active_r is not None:
            idle_motion.append(sum(abs(a - b) for a, b in zip(idle_r, prev_idle_r)) / max(1, len(idle_r)))
            active_motion.append(sum(abs(a - b) for a, b in zip(active_r, prev_active_r)) / max(1, len(active_r)))
            for idx, (curr, prev) in enumerate(zip(active_r, prev_active_r)):
                octant = int((idx * 8) / max(1, len(active_r)))
                octant = max(0, min(7, octant))
                active_octant_motion[octant] += abs(curr - prev)
        prev_idle_r = idle_r
        prev_active_r = active_r

    assert sum(active_motion) / len(active_motion) > (sum(idle_motion) / len(idle_motion)) * 3.0
    # Active should preserve growth-only behavior vs idle (no global recession).
    idle_edge, _ = pack_dual_sources_for_upload(idle, 64, aspect=1.8, boundary_margin=0.01)
    active_edge, _ = pack_dual_sources_for_upload(active, 64, aspect=1.8, boundary_margin=0.01)
    idle_r = _contour_radii(idle_edge, aspect=1.8)
    active_r = _contour_radii(active_edge, aspect=1.8)
    assert min(active_r) >= min(idle_r) - 1e-4
    # Active should show stronger protrusion pockets than idle.
    assert max(active_protrusions) > max(idle_protrusions) + 0.003
    # Guard against quadrant-lock behavior where only alternating sections move.
    assert min(active_octant_motion) > max(active_octant_motion) * 0.36


def test_synthetic_audio_produces_visible_tendril_protrusions():
    state = GooDualFieldState()
    protrusions: list[float] = []
    saturation: list[float] = []
    for i in range(220):
        t = float(i)
        bass = 0.62 + 0.32 * (0.5 + 0.5 * math.sin(t * 0.39))
        mid = 0.40 + 0.26 * (0.5 + 0.5 * math.sin(t * 0.25 + 1.3))
        high = 0.24 + 0.22 * (0.5 + 0.5 * math.sin(t * 0.51 + 2.2))
        overall = min(1.0, bass * 0.42 + mid * 0.35 + high * 0.23)
        bands = EnergyBands(bass=bass, mid=mid, high=high, overall=overall)
        _step(state, bands=bands, playing=True, inward_depth=0.40, aspect=1.8)
        edge, _ = pack_dual_sources_for_upload(state, 64, aspect=1.8, boundary_margin=0.01)
        protrusions.append(_edge_protrusion_score(edge, aspect=1.8))
        saturation.append(float(getattr(state, "source_saturation_ratio", 0.0)))

    # Active path should form clear protrusion pockets, not just a uniformly inflated ring.
    assert max(protrusions) >= 0.030
    # Prevent full-ring cap lock that visually kills deformation.
    assert sum(saturation) / len(saturation) < 0.55


def test_shader_declares_dual_contour_uniforms():
    import pathlib

    shader_path = pathlib.Path("widgets/spotify_visualizer/shaders/goo.frag")
    src = shader_path.read_text(encoding="utf-8")
    assert "u_goo_edge_sources" in src
    assert "u_goo_core_sources" in src
