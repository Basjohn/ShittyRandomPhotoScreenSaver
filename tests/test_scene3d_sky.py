"""The shared sky library (``rendering/gl_programs/scene3d_sky.py``): its noise equals the CPU mirrors on the
GPU, and its clouds and nebula behave as their controls say."""
from __future__ import annotations

import random

import numpy as np
import pytest

from rendering.gl_programs import scene3d_sky as sky
from tests.test_scene3d_glsl_mirrors import _check, probe  # noqa: F401  (module-scoped GL probe)

pytestmark = pytest.mark.qt

DECL = sky.SCENE3D_SKY_GLSL   # with the full library already in the probe: the include guards hold


def _points(rng, count, span):
    return [(rng.uniform(-span, span), rng.uniform(-span, span), rng.uniform(-span, span)) for _ in range(count)]


def test_noise_and_octave_sums_equal_their_mirrors_including_negative_cells(probe):
    rng = random.Random(11)
    points = _points(rng, 192, 40.0)
    seeds = [rng.randrange(0, 4096) for _ in points]
    rows = [[(*p, s)] for p, s in zip(points, seeds)]
    gpu = probe.run("vec4 a = arg(0); FragColor = vec4(skyNoise2(a.xy, uint(a.w)), skyNoise3(a.xyz, uint(a.w)), "
                    "skyFbm2(a.xy, 5, uint(a.w)), skyFbm3(a.xyz, 4, uint(a.w)));", rows, DECL)
    cpu = [(sky.sky_noise2(p[0], p[1], s), sky.sky_noise3(*p, s), sky.sky_fbm2(p[0], p[1], 5, s),
            sky.sky_fbm3(*p, 4, s)) for p, s in zip(points, seeds)]
    _check(gpu, cpu, tolerance=2e-5)
    values = np.asarray(cpu)
    assert values.min() >= 0.0 and values.max() <= 1.0
    assert values[:, 0].std() > 0.15, "the noise varies"


def test_a_drifted_mirror_is_caught(probe):
    rng = random.Random(5)
    points = _points(rng, 64, 10.0)
    gpu = probe.run("vec4 a = arg(0); FragColor = vec4(skyNoise2(a.xy, 7u));", [[p] for p in points], DECL)
    drifted = [sky.sky_noise2(p[0] + 0.25, p[1], 7) for p in points]
    with pytest.raises(AssertionError):
        _check(gpu, drifted, tolerance=2e-5)


def _rays(rng, count, *, up=True):
    rays = []
    for _ in range(count):
        x, z = rng.uniform(-1, 1), rng.uniform(-1, 1)
        y = rng.uniform(0.1, 0.9) if up else rng.uniform(-0.9, 0.01)
        length = (x * x + y * y + z * z) ** 0.5
        rays.append((x / length, y / length, z / length))
    return rays


def _clouds(probe, rays, cloud, drift=(0.0, 0.0), light=(1.0, 0.3, 0.0)):
    body = ("vec4 a = arg(0); FragColor = skyClouds(a.xyz, vec3(" + ",".join(map(str, light)) + "), vec4("
            + ",".join(map(str, cloud)) + "), vec2(" + ",".join(map(str, drift)) + "), vec3(0.1, 0.12, 0.2), "
            "vec3(1.0, 0.9, 0.8), 3u, 5);")
    return probe.run(body, [[r] for r in rays], DECL)


def test_clouds_follow_coverage_opacity_and_stay_off_the_ground(probe):
    rng = random.Random(2)
    rays = _rays(rng, 256)
    none = _clouds(probe, rays, (0.0, 0.5, 0.5, 1.0))
    light = _clouds(probe, rays, (0.3, 0.5, 0.5, 1.0))
    heavy = _clouds(probe, rays, (0.8, 0.5, 0.5, 1.0))
    faint = _clouds(probe, rays, (0.8, 0.5, 0.5, 0.3))
    assert np.all(none == 0.0)
    assert 0.0 < light[:, 3].mean() < heavy[:, 3].mean()
    assert faint[:, 3].mean() == pytest.approx(0.3 * heavy[:, 3].mean(), rel=1e-3)
    assert np.all(heavy[:, :3] <= heavy[:, 3:4] + 1e-6), "premultiplied"
    below = _clouds(probe, _rays(rng, 64, up=False), (0.8, 0.5, 0.5, 1.0))
    assert np.all(below == 0.0), "no clouds below the horizon"
    moved = _clouds(probe, rays, (0.6, 0.5, 0.5, 1.0), drift=(0.7, 0.2))
    still = _clouds(probe, rays, (0.6, 0.5, 0.5, 1.0))
    assert np.abs(moved - still).max() > 0.05, "drift moves the clouds"


def test_cloud_light_comes_from_the_light_side(probe):
    rng = random.Random(9)
    rays = _rays(rng, 512)
    toward = _clouds(probe, rays, (0.8, 0.6, 0.5, 1.0), light=(1.0, 0.2, 0.0))
    away = _clouds(probe, rays, (0.8, 0.6, 0.5, 1.0), light=(-1.0, 0.2, 0.0))
    # Same clouds, lit from the other side: coverage identical, shading different.
    assert np.array_equal(toward[:, 3], away[:, 3])
    assert np.abs(toward[:, :3] - away[:, :3]).max() > 0.05


def test_nebula_is_additive_two_coloured_light_that_its_intensity_scales(probe):
    rng = random.Random(4)
    rays = [r for r in _rays(rng, 256)] + [r for r in _rays(rng, 128, up=False)]

    def nebula(intensity, scale=0.5):
        return probe.run("vec4 a = arg(0); FragColor = vec4(skyNebula(a.xyz, vec3(1.0, 0.1, 0.4), vec3(0.1, 0.4, 1.0), "
                         f"vec2({intensity}, {scale}), 5u, 4), 1.0);", [[r] for r in rays], DECL)[:, :3]
    off, half, full = nebula(0.0), nebula(0.5), nebula(1.0)
    assert np.all(off == 0.0)
    assert np.allclose(half, 0.5 * full, atol=1e-6)
    assert full.max() > 0.1 and np.all(full >= 0.0)
    lit = full[full.sum(axis=1) > 0.05]
    assert (lit[:, 0] > lit[:, 2]).any() and (lit[:, 2] > lit[:, 0]).any(), "both colours show"
    assert np.abs(nebula(1.0, 0.1) - full).max() > 0.05, "scale changes the pattern"
