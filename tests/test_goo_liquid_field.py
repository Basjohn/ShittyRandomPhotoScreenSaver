from __future__ import annotations

import math

from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.goo_liquid_field import (
    GOO_SOURCE_COUNT_MIN,
    GooFieldState,
    pack_sources_for_upload,
    solve_goo_field_step,
)


def _step(
    state: GooFieldState,
    *,
    bands: EnergyBands,
    core_size: float = 0.18,
    inward_depth: float = 0.18,
    boundary_margin: float = 0.01,
) -> None:
    solve_goo_field_step(
        state,
        dt=1.0 / 60.0,
        energy_bands=bands,
        playing=True,
        core_size=core_size,
        edge_inward_depth=inward_depth,
        boundary_margin=boundary_margin,
        seed=1337,
    )


def _contour_radii(points: list[list[float]]) -> list[float]:
    # Inverse of the axis shaping used in pack_sources_for_upload.
    # Tests use aspect=1.0, so both axes are unit scale.
    axis_x = 1.0
    axis_y = 1.0
    out: list[float] = []
    for p in points:
        if p[2] <= 0.0:
            continue
        dx = (float(p[0]) - 0.5) / axis_x
        dy = (float(p[1]) - 0.5) / axis_y
        out.append(math.sqrt(dx * dx + dy * dy))
    return out


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
            # Skip identical and adjacent edges (including wrapped adjacency).
            if j == i or j == (i + 1) % n or (i == 0 and j == n - 1):
                continue
            c = pts[j]
            d = pts[(j + 1) % n]
            if _segments_intersect(a, b, c, d):
                return True
    return False


def test_contour_keeps_center_void_and_soft_curvature_idle():
    state = GooFieldState()
    bands = EnergyBands(bass=0.0, mid=0.0, high=0.0, overall=0.0)
    for _ in range(240):
        _step(state, bands=bands)
    points = pack_sources_for_upload(state, 64, boundary_margin=0.01)
    radii = _contour_radii(points)
    assert radii, "expected populated contour points"
    assert min(radii) >= 0.05, f"center void collapsed too far: min_radius={min(radii):.3f}"
    assert max(radii) <= 0.24, f"contour expanded too far: max_radius={max(radii):.3f}"
    # Hard anti-sharpness assertion.
    assert _max_turn_angle(points) < 0.80
    assert not _has_self_intersection(points), "spline contour self-intersected at idle"


def test_packed_points_stay_inside_boundary_margin():
    state = GooFieldState()
    bands = EnergyBands(bass=0.65, mid=0.45, high=0.25, overall=0.55)
    for _ in range(180):
        _step(state, bands=bands, boundary_margin=0.01)
    points = pack_sources_for_upload(state, 64, boundary_margin=0.01)
    for p in points:
        x, y = float(p[0]), float(p[1])
        if p[2] <= 0.0:
            continue
        assert 0.0 <= x <= 1.0
        assert 0.0 <= y <= 1.0
        assert x >= 0.005 - 1e-6
        assert x <= 1.0 - 0.005 + 1e-6
        assert y >= 0.005 - 1e-6
        assert y <= 1.0 - 0.005 + 1e-6


def test_no_nan_or_inf_under_dense_overlap_stress():
    state = GooFieldState()
    bands = EnergyBands(bass=1.5, mid=1.2, high=1.1, overall=1.4)
    for _ in range(300):
        solve_goo_field_step(
            state,
            dt=1.0 / 120.0,
            energy_bands=bands,
            playing=True,
            core_size=0.36,
            edge_inward_depth=0.30,
            boundary_margin=0.01,
            seed=9,
        )
    for src in state.sources:
        assert math.isfinite(src.angle)
        assert math.isfinite(src.radius)
        assert math.isfinite(src.energy)
        assert math.isfinite(src.home_angle)
        assert math.isfinite(src.home_radius)
    assert math.isfinite(state.source_saturation_ratio)
    assert 0.0 <= state.source_saturation_ratio <= 1.0


def test_source_count_is_clamped_to_minimum_for_smooth_contour():
    state = GooFieldState()
    bands = EnergyBands(bass=0.2, mid=0.2, high=0.2, overall=0.2)
    for _ in range(10):
        _step(state, bands=bands)
    points = pack_sources_for_upload(state, 8, boundary_margin=0.01)
    assert len(state.sources) >= GOO_SOURCE_COUNT_MIN
    assert len(points) >= GOO_SOURCE_COUNT_MIN


def test_core_size_min_max_envelope_remains_stable():
    # Low core size should still keep a small but stable center radius.
    low = GooFieldState()
    low_bands = EnergyBands(bass=0.0, mid=0.0, high=0.0, overall=0.0)
    for _ in range(180):
        _step(low, bands=low_bands, core_size=0.06)
    low_points = pack_sources_for_upload(low, 64, boundary_margin=0.01)
    low_r = _contour_radii(low_points)
    assert low_r
    assert min(low_r) >= 0.035
    assert max(low_r) <= 0.070

    # High core size should scale up but remain bounded and smooth.
    high = GooFieldState()
    high_bands = EnergyBands(bass=0.0, mid=0.0, high=0.0, overall=0.0)
    for _ in range(180):
        _step(high, bands=high_bands, core_size=0.30)
    high_points = pack_sources_for_upload(high, 64, boundary_margin=0.01)
    high_r = _contour_radii(high_points)
    assert high_r
    assert min(high_r) >= 0.090
    assert max(high_r) <= 0.140
    assert not _has_self_intersection(high_points)


def test_shader_outer_radius_guard_uses_tiny_epsilon_regression():
    # Regression guard for full-card collapse bug:
    # large epsilon in outer_base_radius denominator collapses radius.
    import pathlib

    shader_path = pathlib.Path("widgets/spotify_visualizer/shaders/goo.frag")
    src = shader_path.read_text(encoding="utf-8")
    assert "max(1e-30, tx + ty)" in src


def test_shader_wrap_angle_distance_is_branch_cut_safe():
    # Regression guard for left-edge seam/notch artifacts in shader-only
    # outer boundary deformation.
    import pathlib

    shader_path = pathlib.Path("widgets/spotify_visualizer/shaders/goo.frag")
    src = shader_path.read_text(encoding="utf-8")
    assert "mod((a - b) + PI, TAU) - PI" in src
