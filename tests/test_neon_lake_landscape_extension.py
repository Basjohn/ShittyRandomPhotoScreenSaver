"""Deterministic geometry contracts for the framed basin's endless-looking skirt.

The operator's curated preset data is deliberately not a test oracle.
"""
from __future__ import annotations

import math

from rendering.gl_programs.neon_lake_basin_mesh import (
    BASIN_OVERSCAN, basin_lattice, basin_mesh_points, basin_mesh_vertices,
)


def test_extension_preserves_exact_authored_lattice_and_covers_all_four_sides():
    for cells in ((12, 8), (48, 32), (180, 120)):
        xs, ys = basin_lattice(cells)
        left, right, front, back = BASIN_OVERSCAN
        assert xs[0] == -left and xs[-1] == 1.0 + right
        assert ys[0] == -front and ys[-1] == 1.0 + back
        assert all(a < b for axis in (xs, ys) for a, b in zip(axis, axis[1:]))
        assert all(i / cells[0] in xs for i in range(cells[0] + 1))
        assert all(i / cells[1] in ys for i in range(cells[1] + 1))
        assert xs.count(0.0) == xs.count(1.0) == 1
        assert ys.count(0.0) == ys.count(1.0) == 1
        assert len(xs) - 1 < 2.5 * cells[0] + 80
        assert len(ys) - 1 < 2.5 * cells[1] + 80


def test_points_are_all_and_only_the_shared_triangle_lattice_vertices():
    cells = (10, 7)
    triangles = basin_mesh_vertices(cells)
    vertices = basin_mesh_points(cells)
    tri = set(zip(triangles[::2], triangles[1::2]))
    points = set(zip(vertices[::2], vertices[1::2]))
    xs, ys = basin_lattice(cells)
    assert tri == points
    assert len(tri) == len(xs) * len(ys)
    assert len(triangles) == (len(xs) - 1) * (len(ys) - 1) * 12
    assert len(vertices) == len(xs) * len(ys) * 2
    assert basin_mesh_vertices(cells) is triangles  # no per-frame regeneration
    assert basin_mesh_points(cells) is vertices


def test_extension_progressively_reduces_density_without_a_seam_jump():
    xs, ys = basin_lattice((48, 32))
    for axis, count in ((xs, 48), (ys, 32)):
        core_step = 1.0 / count
        origin = axis.index(0.0)
        end = axis.index(1.0)
        assert math.isclose(axis[origin] - axis[origin-1], core_step)
        assert math.isclose(axis[end+1] - axis[end], core_step)
        assert max(axis[i+1]-axis[i] for i in range(origin, end)) <= core_step + 1e-8
        assert max(b-a for a,b in zip(axis[end+1:], axis[end+2:])) > core_step


def test_overscan_camera_crossings_clip_homogeneously_without_projective_poles():
    """Regression for the huge diagonal sheets caused by pre-clipping XY division.

    The real shader uses the same homogeneous near/far projection; unlike the
    old 2D-first projection, vertices behind the eye never divide by a signed
    or nearly zero camera distance before GL clips their triangles.
    """
    from rendering.gl_programs.scene3d import scene3d_orbit_view

    cells = (48, 32)
    vertices = basin_mesh_vertices(cells)
    half_width = 3.15
    depth = 2.4
    tilt = 0.58 * math.pi / 2.0
    turn = 0.20 * math.pi
    camera = max(3.0, 1.25 * math.sqrt(half_width**2 + (depth/2)**2 + 0.9**2))
    near = 0.12
    far = max(48.0, 20.0 * camera)

    def projected(uv):
        u, v = uv
        x, y, z = scene3d_orbit_view(((2*u-1)*half_width, 0.0, (0.5-v)*depth), tilt, turn)
        distance = camera-z
        w = distance/camera
        # Clip numerators, not a 2D screen-space projection. X/Y may be
        # finite even for points behind the eye, with negative homogeneous W.
        x_clip, y_clip = x/camera, y/camera
        z_clip = ((far+near)*distance-2*far*near)/((far-near)*camera)
        return x_clip, y_clip, z_clip, w, distance

    coords = list(zip(vertices[::2], vertices[1::2]))
    projected_vertices = [projected(uv) for uv in coords]
    assert all(all(math.isfinite(v) for v in projected) for projected in projected_vertices)
    assert any(p[4] < 0.0 for p in projected_vertices), 'overscan must exercise behind-eye land'
    crossing = 0
    for i in range(0, len(projected_vertices), 3):
        a, b, c = projected_vertices[i:i+3]
        if min(a[4], b[4], c[4]) < near < max(a[4], b[4], c[4]):
            crossing += 1
            for p, q in ((a,b),(b,c),(c,a)):
                if (p[4]-near)*(q[4]-near) < 0.0:
                    f = (near-p[4])/(q[4]-p[4])
                    z = p[2]+(q[2]-p[2])*f
                    w = p[3]+(q[3]-p[3])*f
                    assert math.isclose(z,-w,rel_tol=1e-6,abs_tol=1e-6)
    assert crossing > 0, 'the original failure requires triangles straddling the eye'



def test_camera_body_disc_fades_only_when_the_eye_gets_too_close():
    from rendering.gl_programs.neon_celestial import basin_body_camera_coverage
    assert basin_body_camera_coverage(10.0, 0.4) == 1.0
    assert basin_body_camera_coverage(0.4, 0.4) == 0.0
    assert basin_body_camera_coverage(0.8, 0.4) == 0.0
    assert 0.0 < basin_body_camera_coverage(2.0, 0.4) < 1.0
    assert basin_body_camera_coverage(3.5, 0.4) == 1.0
