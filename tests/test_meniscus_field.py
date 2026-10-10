"""Meniscus fields (shared primitive, proved on its own): a pool's kernel is compact and peaks at
its centre, two pools near each other bridge into a neck where either alone would not reach, the
signed distance is positive inside and about right near the boundary, the groove rises from the
contact line on both sides, and the GPU equals the CPU mirrors."""
from __future__ import annotations

import random

import pytest

from rendering.gl_programs.meniscus_field import (
    MENISCUS_FIELD_GLSL,
    meniscus_distance,
    meniscus_profile,
    meniscus_slope,
    pool_kernel,
    pool_kernel_radius_at,
)

T = 0.3


def test_a_kernel_is_compact_and_two_near_pools_bridge():
    assert pool_kernel((0.0, 0.0), (0.0, 0.0), 0.4) == 1.0
    assert pool_kernel((0.41, 0.0), (0.0, 0.0), 0.4) == 0.0
    edge = 0.4 * pool_kernel_radius_at(T)
    assert pool_kernel((edge, 0.0), (0.0, 0.0), 0.4) == pytest.approx(T)
    # Midway between two pools a little more than twice the edge apart: either alone stays below the
    # threshold, together they pass it: a neck.
    a, b = (-1.1 * edge, 0.0), (1.1 * edge, 0.0)
    alone = pool_kernel((0.0, 0.0), a, 0.4)
    assert alone < T < alone + pool_kernel((0.0, 0.0), b, 0.4)


def test_the_distance_and_the_groove():
    # One pool along x: the distance from its gradient matches the true distance to the boundary.
    radius, edge = 0.4, 0.4 * pool_kernel_radius_at(T)
    for x in (edge - 0.01, edge + 0.008):
        e = 1e-5
        field = pool_kernel((x, 0.0), (0.0, 0.0), radius)
        slope = (pool_kernel((x + e, 0.0), (0.0, 0.0), radius) - pool_kernel((x - e, 0.0), (0.0, 0.0), radius)) / (2 * e)
        assert meniscus_distance(field, (slope, 0.0), T) == pytest.approx(edge - x, rel=0.15)
    assert meniscus_profile(0.0) == 0.0 and meniscus_profile(1.0) == 1.0
    assert meniscus_slope(0.005, 0.02) > 0.0 > meniscus_slope(-0.005, 0.02) and meniscus_slope(0.03, 0.02) == 0.0


@pytest.mark.qt
def test_the_helpers_match_their_mirrors_on_the_gpu(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        rng = random.Random(9)
        cases = [((rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5)), (rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3)),
                  rng.uniform(0.1, 0.6), rng.uniform(-0.03, 0.03)) for _ in range(96)]
        gpu = probe.run("vec4 a = arg(0), b = arg(1); FragColor = vec4(poolKernel(a.xy, a.zw, b.x), "
                        "meniscusSlope(b.y, 0.02) * 0.01, meniscusProfile(abs(b.y) / 0.02), "
                        "meniscusDistance(0.4, vec2(b.x, b.y), 0.3));",
                        [[(*p, *c), (r, d)] for p, c, r, d in cases], declarations=MENISCUS_FIELD_GLSL)
        _check(gpu, [(pool_kernel(p, c, r), meniscus_slope(d, 0.02) * 0.01, meniscus_profile(abs(d) / 0.02),
                      meniscus_distance(0.4, (r, d), 0.3)) for p, c, r, d in cases], tolerance=1e-3)
    finally:
        probe.close()
