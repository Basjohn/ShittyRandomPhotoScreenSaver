"""Vortex flow (shared primitive, proved on its own): zero strength is the identity, the flow keeps
area, its inverse undoes it exactly, it fades out away from the vortices, different seeds swirl
differently, and the GPU matches the CPU mirror."""
from __future__ import annotations

import math
import random

import pytest

from rendering.gl_programs.vortex_flow import VORTEX_FLOW_GLSL, vortex_flow, vortex_flow_inverse


def _points(seed: int, count: int = 200):
    rng = random.Random(seed)
    return [(rng.uniform(-0.9, 0.9), rng.uniform(-0.5, 0.5)) for _ in range(count)]


def test_zero_strength_is_the_identity_and_the_inverse_undoes_the_flow():
    for p in _points(1):
        assert vortex_flow(p, 17.0, 0.0) == pytest.approx(p, abs=1e-12)
        assert vortex_flow_inverse(vortex_flow(p, 17.0, 2.5), 17.0, 2.5) == pytest.approx(p, abs=1e-9)


def test_the_flow_keeps_area():
    step = 1e-5
    for x, y in _points(2):
        fx = [(a - b) / (2 * step) for a, b in zip(vortex_flow((x + step, y), 5.0, 2.7), vortex_flow((x - step, y), 5.0, 2.7))]
        fy = [(a - b) / (2 * step) for a, b in zip(vortex_flow((x, y + step), 5.0, 2.7), vortex_flow((x, y - step), 5.0, 2.7))]
        assert fx[0] * fy[1] - fx[1] * fy[0] == pytest.approx(1.0, abs=1e-5)


def test_the_swirl_is_local_and_seeded():
    far = (3.0, 2.0)
    assert vortex_flow(far, 9.0, 2.7) == pytest.approx(far, abs=1e-6)
    moved = [math.dist(vortex_flow(p, 9.0, 2.7), p) for p in _points(3)]
    assert max(moved) > 0.1
    assert any(math.dist(vortex_flow(p, 9.0, 2.7), vortex_flow(p, 400.0, 2.7)) > 0.05 for p in _points(3))


@pytest.mark.qt
def test_the_flow_matches_its_mirror_on_the_gpu(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        rng = random.Random(4)
        cases = [(p, rng.uniform(0.0, 990.0), rng.uniform(0.0, 3.0)) for p in _points(4, 128)]
        gpu = probe.run("vec4 a = arg(0); FragColor = vec4(vortexFlow(a.xy, a.z, a.w), vortexFlowInverse(a.xy, a.z, a.w));",
                        [[(*p, seed, strength)] for p, seed, strength in cases], declarations=VORTEX_FLOW_GLSL)
        _check(gpu, [(*vortex_flow(p, seed, strength), *vortex_flow_inverse(p, seed, strength))
                     for p, seed, strength in cases], tolerance=5e-4)
    finally:
        probe.close()
