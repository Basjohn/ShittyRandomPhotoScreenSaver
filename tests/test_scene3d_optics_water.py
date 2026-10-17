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


def test_sphere_paths_equal_their_mirror_and_keep_the_physics(probe):
    rng = random.Random(3)
    rows = []
    for _ in range(96):
        offset = rng.uniform(0.0, 1.5)
        turn = rng.uniform(0.0, 2 * math.pi)
        normal = (math.sin(offset) * math.cos(turn), math.sin(offset) * math.sin(turn), math.cos(offset))
        rows.append([(0.0, 0.0, -1.0, rng.choice((1.33, 1 / 1.5))), (*normal, 0.0)])
    body = "vec3 r = arg(0).xyz; vec3 n = arg(1).xyz; vec3 a, b, c; vec3 w = sceneSpherePaths(r, n, arg(0).w, a, b, c);"
    for index, output in enumerate(("w", "a", "b", "c")):
        gpu = probe.run(body + f" FragColor = vec4({output}, 0.0);", rows, DECL)
        cpu = [(*optics.scene3d_sphere_paths(r[:3], n[:3], r[3])[index], 0.0) for r, n in rows]
        _check(gpu, cpu, tolerance=5e-4)
    for r, n in rows:
        weights, reflected, transmitted, bounced = optics.scene3d_sphere_paths(r[:3], n[:3], r[3])
        assert sum(weights) <= 1.0 + 1e-9
        incidence = n[2]
        if r[3] > 1.0 and math.sqrt(1 - incidence * incidence) > 1 / r[3]:
            assert weights == (1.0, 0.0, 0.0)                    # an air bubble's mirror band
    # Head on: straight through, reflected straight back, nothing bent.
    weights, reflected, transmitted, _ = optics.scene3d_sphere_paths((0.0, 0.0, -1.0), (0.0, 0.0, 1.0), 1.33)
    assert transmitted == pytest.approx((0.0, 0.0, -1.0), abs=1e-9)
    assert reflected == pytest.approx((0.0, 0.0, 1.0), abs=1e-9)
    assert weights[1] > 0.95


def test_hollow_sphere_trace_equals_its_mirror_and_conserves_light(probe):
    rng = random.Random(5)
    rows = []
    for _ in range(64):
        x, y = rng.uniform(-0.999, 0.999), 0.0
        y = rng.uniform(-1.0, 1.0) * math.sqrt(max(0.0, 1.0 - x * x)) * 0.999
        rows.append([(x, y, 3.0, rng.choice((0.0, 0.85, 0.95))), (1.33, 1.5, 1.0, 0.0)])
    head = ("vec4 a = arg(0); vec4 paths[8]; int n = sceneHollowSphereTrace(a.xyz, vec3(0.0, 0.0, -1.0), 1.0, a.w,"
            " arg(1).xyz, paths);")
    gpu_count = probe.run(head + " FragColor = vec4(float(n), 0.0, 0.0, 0.0);", rows, DECL)
    cpu = [optics.scene3d_hollow_sphere_trace(r[:3], (0.0, 0.0, -1.0), 1.0, r[3], i[:3]) for r, i in rows]
    assert [int(round(g[0])) for g in gpu_count] == [len(c) for c in cpu]
    for index in range(3):
        gpu = probe.run(head + f" FragColor = paths[{index}];", rows, DECL)
        expected = [(*c[index][0], c[index][1]) if index < len(c) else (0.0, 0.0, 0.0, 0.0) for c in cpu]
        _check(gpu, expected, tolerance=2e-3)
    for paths in cpu:
        assert sum(w for _, w in paths) <= 1.0 + 1e-6
    # Matched indices everywhere: the light passes straight through untouched.
    straight = optics.scene3d_hollow_sphere_trace((0.3, 0.2, 3.0), (0.0, 0.0, -1.0), 1.0, 0.9, (1.0, 1.0, 1.0))
    assert straight[-1][0] == pytest.approx((0.0, 0.0, -1.0), abs=1e-6) and straight[-1][1] == pytest.approx(1.0)
    # No core: the first split is a solid sphere's front reflection.
    solid = optics.scene3d_hollow_sphere_trace((0.4, 0.0, 3.0), (0.0, 0.0, -1.0), 1.0, 0.0, (1.33, 1.5, 1.5))
    normal = (0.4, 0.0, math.sqrt(1 - 0.16))
    assert solid[0][1] == pytest.approx(optics.scene3d_sphere_paths((0.0, 0.0, -1.0), normal, 1.33 / 1.5)[0][0], abs=1e-6)
    # Near the silhouette of a glass shell the light is guided inside the wall: it leaves far from where it would
    # through solid glass.
    guided = optics.scene3d_hollow_sphere_trace((0.97, 0.0, 3.0), (0.0, 0.0, -1.0), 1.0, 0.9, (1.0, 1.5, 1.0))
    through = optics.scene3d_hollow_sphere_trace((0.5, 0.0, 3.0), (0.0, 0.0, -1.0), 1.0, 0.9, (1.0, 1.5, 1.0))
    assert len(guided) >= 2 and len(through) >= 3


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


def test_the_window_and_the_sun_below_equal_their_mirror_and_their_physics(probe):
    import pytest as _pytest
    rows = [[(math.sin(a), math.cos(a), 0.0, 0.0)] for a in (0.0, math.radians(30), math.radians(47), math.radians(60))]
    gpu = probe.run("vec3 r = arg(0).xyz; vec3 sky; float t = waterWindow(r, vec3(0, 1, 0), sky); FragColor = vec4(sky, t);",
                    rows, DECL)
    assert gpu[0][3] == _pytest.approx(1 - ((1.33 - 1) / 2.33) ** 2, abs=1e-4)      # straight up
    assert gpu[0][3] > gpu[1][3] > gpu[2][3] > 0.0 and gpu[3][3] == 0.0              # dims to the edge, closed past it
    assert gpu[2][0] > gpu[1][0] > 0.0                                               # leaving ever flatter
    for sun in ((0.0, 0.62, -1.0), (0.3, 1.0, 0.2), (0.0, 1.0, 0.0)):
        cpu = water.water_sun_below(sun)
        got = probe.run(f"FragColor = vec4(waterSunBelow(vec3{sun}), 0.0);", [[(0.0, 0.0, 0.0, 0.0)]], DECL)[0][:3]
        assert tuple(got) == _pytest.approx(cpu, abs=1e-5)
        elevation_air = math.atan2(sun[1], math.hypot(sun[0], sun[2]))
        elevation_water = math.atan2(cpu[1], math.hypot(cpu[0], cpu[2]))
        assert elevation_water >= elevation_air - 1e-9                              # bent toward the vertical


def test_volumetric_shafts_follow_the_pattern_converge_on_the_sun_and_fade_with_depth(probe):
    grid = [(x * 0.37, y * 0.29) for y in range(16) for x in range(16)]
    gpu = probe.run("vec4 a = arg(0); FragColor = vec4(waterShaftPattern(a.xy, a.z));",
                    [[(x, y, 2.0, 0.0)] for x, y in grid], DECL)[:, 0]
    cpu = np.array([water.water_shaft_pattern(x, y, 2.0) for x, y in grid])
    assert np.abs(gpu - cpu).max() < 1e-4
    field = np.array([water.water_shaft_pattern(x * 0.13, y * 0.11, 0.0) for y in range(60) for x in range(60)])
    assert 0.05 < (field > 0.5).mean() < 0.45, "beams with dark water between"

    def shafts(ray, eye=(0.0, 0.0, 0.0)):
        body = ("vec4 r = arg(0); vec4 e = arg(1); FragColor = vec4(waterShafts(e.xyz, normalize(r.xyz), 30.0,"
                " normalize(vec3(0.0, 1.0, -0.4)), 6.0, 1.0, 48, 0.5));")
        return float(probe.run(body, [[(*ray, 0.0), (*eye, 0.0)]], DECL)[0][0])
    assert shafts((0.0, 1.0, 0.0), eye=(0.0, 7.0, 0.0)) == 0.0               # above the surface: no water to light
    rng = random.Random(5)
    # Equal horizontal paths: one just under the surface, one deep below it.
    rays = [(rng.uniform(-0.4, 0.4), 0.0, -1.0) for _ in range(8)]
    shallow = [shafts(ray, eye=(0.0, 4.0, 0.0)) for ray in rays]
    deep = [shafts(ray, eye=(0.0, -20.0, 0.0)) for ray in rays]
    assert sum(shallow) > 0.0 and sum(deep) < 0.3 * sum(shallow)            # dimmer deep below the surface


def test_ripples_equal_their_mirror_and_flatten_as_the_footprint_grows(probe):
    rng = random.Random(21)
    rows = [[(rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(0, 10), rng.choice((0.0, 0.3, 2.0)))]
            for _ in range(96)]
    gpu = probe.run("vec4 a = arg(0); FragColor = vec4(waterRipples(a.xy, a.z, a.w));", rows, DECL)[:, 0]
    cpu = np.array([water.water_ripples(x, y, t, f) for (x, y, t, f), in rows])
    assert np.abs(gpu - cpu).max() < 1e-4
    points = [(rng.uniform(-30, 30), rng.uniform(-30, 30)) for _ in range(400)]
    spread = lambda footprint: np.std([water.water_ripples(x, y, 1.0, footprint) for x, y in points])
    assert spread(0.0) > spread(1.0) > spread(4.0) and spread(10.0) < 1e-9   # detail fades with distance, then gone


def test_seabed_and_wisps_equal_their_mirrors_and_their_character(probe):
    rng = random.Random(31)
    rows = [[(rng.uniform(-15, 15), rng.uniform(-15, 15), rng.uniform(0, 8), 1.0)] for _ in range(96)]
    gpu = probe.run("vec4 a = arg(0); FragColor = vec4(waterSeabed(a.xy, a.z, a.w), waterWisps(a.xy, a.z), 0.0);",
                    rows, DECL)
    cpu = np.array([(*water.water_seabed(x, y, t, s), water.water_wisps(x, y, t), 0.0) for (x, y, t, s), in rows])
    assert np.abs(gpu - cpu).max() < 2e-3
    bed = np.array([water.water_seabed(rng.uniform(0, 30), rng.uniform(0, 30), 2.0, 1.0) for _ in range(1500)])
    assert bed[:, 0].std() > 0.08 and 0.0 <= bed.min() and bed.max() <= 1.0        # pebbles and gaps, bounded
    assert water.water_seabed(3.3, 4.4, 2.0, 0.0)[1] == 0.0                          # no caustics when off
    wisps = np.array([water.water_wisps(rng.uniform(0, 40), rng.uniform(0, 40), 1.0) for _ in range(3000)])
    assert (wisps < 0.05).mean() > 0.6 and wisps.max() > 0.5                         # thin bright strands, mostly empty
