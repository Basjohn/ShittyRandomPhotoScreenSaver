"""Sphere impostor GLSL equals its CPU mirrors on the GPU (its own module: the probe owns a module-scoped context)."""
from __future__ import annotations

import random

import pytest

from rendering.gl_programs import scene3d_spheres as spheres
from tests.test_scene3d_glsl_mirrors import _check, probe  # noqa: F401  (module-scoped GL probe)

pytestmark = pytest.mark.qt


def test_sphere_ray_and_corner_equal_their_mirrors(probe):
    rng = random.Random(3)
    rows, cpu_ray, cpu_corner = [], [], []
    for _ in range(96):
        centre = (rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(-9, -3))
        radius = rng.uniform(0.1, 1.2)
        ray = spheres._normalize((centre[0] + rng.uniform(-1, 1), centre[1] + rng.uniform(-1, 1), centre[2]))
        corner = (rng.choice((-1.0, 1.0)), rng.choice((-1.0, 1.0)))
        blur = rng.uniform(0.0, 0.3)
        rows.append([(*centre, radius), (*ray, blur), (*corner, 0.0, 0.0)])
        hit, near, far = spheres.scene3d_sphere_ray(ray, centre, radius)
        cpu_ray.append((float(hit), near, far, 0.0))
        cpu_corner.append((*spheres.scene3d_sphere_corner(centre, radius, blur, corner), 0.0))
    decl = spheres.SCENE3D_SPHERES_GLSL
    gpu_ray = probe.run("vec4 s = arg(0); vec4 r = arg(1); float n, f; bool hit = sceneSphereRay(r.xyz, s.xyz, s.w, n, f);"
                        " FragColor = vec4(float(hit), n, f, 0.0);", rows, decl)
    gpu_corner = probe.run("vec4 s = arg(0); vec4 r = arg(1); vec4 c = arg(2);"
                           " FragColor = vec4(sceneSphereCorner(s.xyz, s.w, r.w, c.xy), 0.0);", rows, decl)
    _check(gpu_ray, cpu_ray, tolerance=2e-4)
    _check(gpu_corner, cpu_corner, tolerance=2e-4)
