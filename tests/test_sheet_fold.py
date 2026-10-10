"""Folded sheets (shared primitive, proved on its own): pleats keep their width through folding,
turning over and unfolding from the far edge, the phases meet, the GPU matches the CPU mirror,
every crease lands on a grid vertex row at every tier, and the two-sided helpers pick the side
facing the viewer and mirror the back's print."""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from rendering.gl_programs.scene3d import SCENE3D_CAMERA, SCENE3D_DETAIL_TIERS
from rendering.gl_programs.sheet_fold import (
    SHEET_FOLD_GLSL,
    SHEET_SIDES_GLSL,
    SHEET_TWIST_GLSL,
    crease_grid,
    sheet_fold,
    sheet_twist,
)

ASPECT = 16 / 9
MAX_FOLD = 0.36 * math.pi


def test_pleats_keep_their_width_through_folding_turning_and_unfolding():
    length, pleats = ASPECT, 8
    states = [(fold, 0.0) for fold in (0.0, 0.3, MAX_FOLD)]
    states += [(MAX_FOLD, turn) for turn in (0.4, 1.5, 2.9)]
    states += [(fold, math.pi) for fold in (MAX_FOLD, 0.7, 0.2)]
    step = 1e-4
    for fold, turn in states:
        for a in np.linspace(0.0, length - step, 500):
            x0, z0 = sheet_fold(a, length, pleats, fold, turn)
            x1, z1 = sheet_fold(a + step, length, pleats, fold, turn)
            assert math.hypot(x1 - x0, z1 - z0) == pytest.approx(step, rel=1e-3)
            assert z0 >= -1e-12                           # never through the plane
    assert sheet_fold(0.37, length, pleats, 0.0, 0.0) == pytest.approx((0.37, 0.0))
    # Laid out from the far edge, a point lands mirrored across the sheet.
    assert sheet_fold(0.37, length, pleats, 0.0, math.pi) == pytest.approx((length - 0.37, 0.0))


def test_the_phases_meet():
    length, pleats = ASPECT, 8
    for a in np.linspace(0.0, length, 97):
        folded = sheet_fold(a, length, pleats, MAX_FOLD, 0.0)
        assert sheet_fold(a, length, pleats, MAX_FOLD, 1e-9) == pytest.approx(folded, abs=1e-7)
        turned = sheet_fold(a, length, pleats, MAX_FOLD, math.pi - 1e-9)
        assert sheet_fold(a, length, pleats, MAX_FOLD, math.pi) == pytest.approx(turned, abs=1e-7)


@pytest.mark.parametrize("pleats", (4, 7, 12, 16))
def test_every_crease_lands_on_a_grid_vertex_row(pleats):
    for tier in SCENE3D_DETAIL_TIERS.values():
        for aspect in (16 / 9, 4 / 3, 9 / 16, 21 / 9):
            for vertical in (False, True):
                columns, rows = crease_grid(pleats, tier.grid_cells, aspect, vertical)
                along, across = (rows, columns) if vertical else (columns, rows)
                assert along % pleats == 0 and along >= 2 * pleats and across == 1


@pytest.mark.qt
def test_the_fold_and_the_sides_match_their_mirrors_on_the_gpu(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        rng = random.Random(3)
        cases = []
        for _ in range(160):
            length, pleats = rng.choice((ASPECT, 1.0)), rng.randint(4, 16)
            turn = rng.choice((0.0, math.pi, rng.uniform(0.0, math.pi)))
            fold = MAX_FOLD if 0.0 < turn < math.pi else rng.uniform(0.0, MAX_FOLD)
            cases.append((rng.uniform(0.0, length), length, pleats, fold, turn))
        gpu = probe.run("vec4 a = arg(0); FragColor = vec4(sheetFold(a.x, a.y, a.z, a.w, arg(1).x), 0.0, 0.0);",
                        [[(a, length, pleats, fold), (turn,)] for a, length, pleats, fold, turn in cases],
                        declarations=SHEET_FOLD_GLSL)
        _check(gpu, [(*sheet_fold(*case), 0.0, 0.0) for case in cases])

        sides = []
        for _ in range(64):
            normal = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
            world = (rng.uniform(-0.8, 0.8), rng.uniform(-0.5, 0.5), rng.uniform(-0.2, 0.4))
            uv, mirror = (rng.random(), rng.random()), rng.choice(((1.0, 0.0), (0.0, 1.0)))
            sides.append((normal, world, uv, mirror))
        gpu = probe.run("vec2 uv = sheetBackUv(arg(2).xy, arg(2).zw);"
                        "FragColor = vec4(sheetShowsBack(arg(0).xyz, arg(1).xyz) ? 1.0 : 0.0, uv, 0.0);",
                        [[n, w, (*uv, *m)] for n, w, uv, m in sides],
                        declarations=SHEET_SIDES_GLSL)
        expected = []
        for normal, world, uv, mirror in sides:
            view = (-world[0], -world[1], SCENE3D_CAMERA - world[2])
            back = sum(n * v for n, v in zip(normal, view)) < 0.0
            expected.append((1.0 if back else 0.0, uv[0] + mirror[0] * (1.0 - 2.0 * uv[0]),
                             uv[1] + mirror[1] * (1.0 - 2.0 * uv[1]), 0.0))
        _check(gpu, expected)
    finally:
        probe.close()


def test_a_twisted_cross_section_keeps_its_width_stays_in_front_and_lands_back_up():
    axis, pivot, half = (1.0, 0.0), (0.0, 0.0), 0.5
    for angle in (0.0, 0.7, math.pi / 2, 2.4, math.pi):
        top, bottom = (sheet_twist((0.3, y), axis, pivot, angle, half) for y in (half, -half))
        assert math.dist(top, bottom) == pytest.approx(2 * half)
        assert min(top[2], bottom[2]) >= -1e-12
        assert top[0] == bottom[0] == pytest.approx(0.3)         # turns about the axis, never along it
    assert sheet_twist((0.3, 0.2), axis, pivot, 0.0, half) == pytest.approx((0.3, 0.2, 0.0))
    # Turned over, it lies flat again with the cross-section reversed.
    assert sheet_twist((0.3, 0.2), axis, pivot, math.pi, half) == pytest.approx((0.3, -0.2, 0.0), abs=1e-12)


@pytest.mark.qt
def test_the_twist_matches_its_mirror_on_the_gpu(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        rng = random.Random(6)
        cases = []
        for _ in range(96):
            a = rng.uniform(0, 2 * math.pi)
            cases.append(((rng.uniform(-0.9, 0.9), rng.uniform(-0.5, 0.5)), (math.cos(a), math.sin(a)),
                          (rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2)), rng.uniform(0, math.pi), rng.uniform(0.3, 1.0)))
        gpu = probe.run("vec4 a = arg(0), b = arg(1); FragColor = vec4(sheetTwist(a.xy, a.zw, b.xy, b.z, b.w), 0.0);",
                        [[(*p, *axis), (*pivot, angle, half)] for p, axis, pivot, angle, half in cases],
                        declarations=SHEET_TWIST_GLSL)
        _check(gpu, [(*sheet_twist(*case), 0.0) for case in cases])
    finally:
        probe.close()
