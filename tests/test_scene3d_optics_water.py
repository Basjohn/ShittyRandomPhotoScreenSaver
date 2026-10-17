"""Shared optics (``scene3d_optics.py``) and underwater light (``scene3d_water.py``): GLSL equals the CPU mirrors on
the GPU, and each function behaves as its physics says."""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from rendering.gl_programs import scene3d_optics as optics
from rendering.gl_programs import scene3d_water as water
from tests.test_scene3d_glsl_mirrors import _check, probe  # noqa: F401  (module-scoped GL probe)

pytestmark = pytest.mark.qt

DECL = optics.SCENE3D_OPTICS_GLSL + water.SCENE3D_WATER_GLSL


def test_fresnel_and_thin_film_equal_their_mirrors_and_their_physics(probe):
    rng = random.Random(1)
    rows = [[(rng.uniform(0, 1), rng.choice((1.33, 1 / 1.33, 1.5)), rng.uniform(0, 900), 0.0)] for _ in range(128)]
    gpu = probe.run("vec4 a = arg(0); FragColor = vec4(sceneFresnelDielectric(a.x, a.y),"
                    " sceneThinFilm(a.x, a.z, 1.33, 1.0));", rows, DECL)
    cpu = [(optics.scene3d_fresnel_dielectric(c, eta), *optics.scene3d_thin_film(c, d, 1.33, 1.0))
           for (c, eta, d, _), in rows]
    _check(gpu, cpu, tolerance=2e-4)
    assert optics.scene3d_fresnel_dielectric(1.0, 1.33) == pytest.approx(((1.33 - 1) / 2.33) ** 2)
    critical = math.sqrt(1 - 1 / 1.33 ** 2)                      # water into air
    assert optics.scene3d_fresnel_dielectric(critical - 0.01, 1.33) == 1.0
    assert optics.scene3d_fresnel_dielectric(critical + 0.05, 1.33) < 1.0
    assert max(optics.scene3d_thin_film(1.0, 0.0, 1.33, 1.0)) < 1e-9   # no film, no colour
    films = np.array([optics.scene3d_thin_film(1.0, d, 1.33, 1.0) for d in range(150, 750, 25)])
    hues = films / films.sum(axis=1, keepdims=True)
    assert np.ptp(hues, axis=0).min() > 0.1, "fringes change colour with thickness"


def test_refraction_through_an_air_sphere_passes_the_axis_straight_and_spreads_the_rest(probe):
    rows = []
    for offset in (0.0, 0.2, 0.4, 0.6):
        normal = (math.sin(offset), 0.0, math.cos(offset))         # the front surface, facing the eye at +z
        rows.append([(0.0, 0.0, -1.0, 0.0), (*normal, 0.0)])
    gpu = probe.run("vec3 r = arg(0).xyz; vec3 n = arg(1).xyz; FragColor = vec4(sceneSphereRefraction(r, n, 1.33), 0.0);",
                    rows, DECL)
    assert gpu[0][:3] == pytest.approx((0.0, 0.0, -1.0), abs=1e-5)
    # An air bubble in water is a diverging lens: rays further from the axis bend further outward (+x).
    bends = [float(direction[0]) for direction in gpu[1:]]
    assert 0.0 < bends[0] < bends[1] < bends[2]


def test_waves_have_matching_gradients_and_equal_their_mirror(probe):
    rng = random.Random(7)
    points = [(rng.uniform(-5, 5), rng.uniform(-5, 5), rng.uniform(0, 20)) for _ in range(96)]
    gpu = probe.run("vec4 a = arg(0); FragColor = vec4(waterWaves(a.xy, a.z, 1.0), 0.0);",
                    [[(x, z, t, 0.0)] for x, z, t in points], DECL)
    cpu = [(*water.water_waves(x, z, t, 1.0), 0.0) for x, z, t in points]
    _check(gpu, cpu, tolerance=5e-4)
    for x, z, t in points[:16]:
        h, gx, gz = water.water_waves(x, z, t, 1.0)
        e = 1e-4
        assert gx == pytest.approx((water.water_waves(x + e, z, t, 1.0)[0] - water.water_waves(x - e, z, t, 1.0)[0]) / (2 * e),
                                   abs=1e-3)
        assert gz == pytest.approx((water.water_waves(x, z + e, t, 1.0)[0] - water.water_waves(x, z - e, t, 1.0)[0]) / (2 * e),
                                   abs=1e-3)


def test_caustics_are_a_thin_moving_network_equal_to_their_mirror(probe):
    grid = [(x * 0.05, y * 0.05) for y in range(24) for x in range(24)]
    gpu = probe.run("vec4 a = arg(0); FragColor = vec4(waterCaustics(a.xy, a.z));",
                    [[(x, y, 3.0, 0.0)] for x, y in grid], DECL)[:, 0]
    cpu = np.array([water.water_caustics(x, y, 3.0) for x, y in grid])
    assert np.abs(gpu - cpu).max() < 2e-3
    rng = random.Random(9)
    field = np.array([water.water_caustics(rng.uniform(0, 8), rng.uniform(0, 8), 3.0) for _ in range(2000)])
    assert field.min() >= 0.0 and field.max() <= 1.0
    assert 0.03 < (field > 0.6).mean() < 0.35, "bright lines, mostly dim cells"
    later = np.array([water.water_caustics(x, y, 3.5) for x, y in grid])
    assert np.abs(later - cpu).max() > 0.2, "the network moves"


def test_the_surface_from_below_shows_the_sky_inside_snells_window_and_mirrors_the_deep_outside(probe):
    def look(angle):
        ray = (math.sin(angle), math.cos(angle), 0.0)
        return probe.run("vec3 r = arg(0).xyz; FragColor = vec4(waterSurfaceFromBelow(r, vec3(0, 1, 0),"
                         " normalize(vec3(0.0, 1.0, 0.2)), vec3(0.6, 0.8, 1.0), vec3(0.0, 0.05, 0.1), 0.0), 1.0);",
                         [[(*ray, 0.0)]], DECL)[0][:3]
    overhead, edge, outside = look(0.0), look(math.radians(45)), look(math.radians(60))
    assert overhead[2] > 0.9 and overhead[0] > 0.5
    assert overhead[0] > edge[0] > outside[0]            # transmission falls toward the window's edge
    assert outside == pytest.approx((0.0, 0.05, 0.1), abs=1e-5)


def test_the_medium_fades_toward_the_water_colour_with_distance(probe):
    rows = [[(distance, 0.0, 0.0, 0.0)] for distance in (0.0, 1.0, 200.0)]
    gpu = probe.run("float d = arg(0).x; FragColor = vec4(waterMedium(vec3(1.0, 0.8, 0.6), d, vec3(0.4, 0.1, 0.05),"
                    " vec3(0.0, 0.2, 0.3)), 1.0);", rows, DECL)
    assert gpu[0][:3] == pytest.approx((1.0, 0.8, 0.6), abs=1e-5)
    assert gpu[1][0] < gpu[1][1] or gpu[1][0] < 1.0                # red goes first
    assert gpu[2][:3] == pytest.approx((0.0, 0.2, 0.3), abs=0.02)
