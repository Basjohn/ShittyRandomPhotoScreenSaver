from __future__ import annotations

import math

from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.goo_liquid_field import (
    GooFieldState,
    pack_sources_for_upload,
    solve_goo_field_step,
)


def _step(
    state: GooFieldState,
    *,
    bands: EnergyBands,
    count: int = 64,
    boundary_margin: float = 0.01,
) -> None:
    solve_goo_field_step(
        state,
        dt=1.0 / 60.0,
        energy_bands=bands,
        playing=True,
        advance_speed=1.2,
        retreat_speed=1.0,
        source_count=count,
        growth=3.5,
        void_floor=0.15,
        boundary_margin=boundary_margin,
        seed=1337,
    )


def test_sources_have_good_idle_coverage():
    state = GooFieldState()
    bands = EnergyBands(bass=0.0, mid=0.0, high=0.0, overall=0.0)
    for _ in range(240):
        _step(state, bands=bands)
    srcs = pack_sources_for_upload(state, 64, boundary_margin=0.01)
    depths = [src[1] for src in srcs[:16]]
    assert all(d >= 0.05 for d in depths), f"idle depths too shallow: {depths}"


def test_packed_sources_stay_inside_boundary_margin():
    state = GooFieldState()
    bands = EnergyBands(bass=0.65, mid=0.45, high=0.25, overall=0.55)
    for _ in range(180):
        _step(state, bands=bands, boundary_margin=0.01)
    srcs = pack_sources_for_upload(state, 64, boundary_margin=0.01)
    for src in srcs:
        x, y = float(src[0]), float(src[1])
        if src[2] <= 0.0:
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
            advance_speed=2.0,
            retreat_speed=0.6,
            source_count=64,
            growth=5.5,
            void_floor=0.08,
            boundary_margin=0.01,
            seed=9,
        )
    for src in state.sources:
        assert math.isfinite(src.t)
        assert math.isfinite(src.depth)
        assert math.isfinite(src.radius)
        assert math.isfinite(src.energy)
    assert math.isfinite(state.source_saturation_ratio)
    assert 0.0 <= state.source_saturation_ratio <= 1.0

