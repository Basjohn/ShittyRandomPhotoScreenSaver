"""Accordion Fold: the fold geometry (CPU mirror, checked on the GPU) and the transition through the
production host on a real offscreen context (no window): pleats keep their width through folding,
flipping and unfolding, the phases meet, the turning stack stays above the picture, creases sit on
grid vertex rows at every tier, exact and continuous ends, the front carries the old picture and
the back the new one, a still backdrop beyond the stack, every edge folds toward itself, a warm-up
that leaves the first frames nothing to do, park/release, and the resolver."""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from rendering.gl_programs.accordion_fold_options import ACCORDION_EDGES
from rendering.gl_programs.accordion_fold_program import (
    ACCORDION_FLIP_END,
    ACCORDION_FOLD_END,
    ACCORDION_GLSL,
    ACCORDION_MAX_FOLD,
    accordion_edge,
    accordion_fold,
    accordion_grid,
    accordion_lift,
    accordion_state,
)
from rendering.gl_programs.scene3d import SCENE3D_DETAIL_TIERS
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

W, H = 320, 180
ASPECT = W / H
_FOLD = 0.5 * ACCORDION_FOLD_END
_UNFOLD = 0.5 * (ACCORDION_FLIP_END + 1.0)


def test_pleats_keep_their_width_through_folding_flipping_and_unfolding():
    length, pleats = ASPECT, 8
    states = [(fold, 0.0) for fold in (0.0, 0.3, ACCORDION_MAX_FOLD)]
    states += [(ACCORDION_MAX_FOLD, flip) for flip in (0.4, 1.5, 2.9)]
    states += [(fold, math.pi) for fold in (ACCORDION_MAX_FOLD, 0.7, 0.2)]
    step = 1e-4
    for fold, flip in states:
        for a in np.linspace(0.0, length - step, 500):
            x0, z0 = accordion_fold(a, length, pleats, fold, flip)
            x1, z1 = accordion_fold(a + step, length, pleats, fold, flip)
            assert math.hypot(x1 - x0, z1 - z0) == pytest.approx(step, rel=1e-3)
            assert z0 >= -1e-12                           # never through the picture
    assert accordion_fold(0.37, length, pleats, 0.0, 0.0) == pytest.approx((0.37, 0.0))
    # Laid flat back up, a point lands mirrored across the picture.
    assert accordion_fold(0.37, length, pleats, 0.0, math.pi) == pytest.approx((length - 0.37, 0.0))


def test_the_phases_meet():
    length, pleats = ASPECT, 8
    for a in np.linspace(0.0, length, 97):
        folded = accordion_fold(a, length, pleats, ACCORDION_MAX_FOLD, 0.0)
        assert accordion_fold(a, length, pleats, ACCORDION_MAX_FOLD, 1e-9) == pytest.approx(folded, abs=1e-7)
        turned = accordion_fold(a, length, pleats, ACCORDION_MAX_FOLD, math.pi - 1e-9)
        assert accordion_fold(a, length, pleats, ACCORDION_MAX_FOLD, math.pi) == pytest.approx(turned, abs=1e-7)
    assert accordion_state(0.0) == (0.0, 0.0) and accordion_state(1.0) == (0.0, math.pi)
    assert accordion_state(ACCORDION_FOLD_END - 1e-9)[0] == pytest.approx(ACCORDION_MAX_FOLD)
    assert accordion_state(ACCORDION_FLIP_END)[1] == pytest.approx(math.pi)
    assert accordion_lift(0.0) == 0.0 and accordion_lift(ACCORDION_MAX_FOLD) == 1.0


def test_the_fold_matches_its_mirror_on_the_gpu(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        rng = random.Random(3)
        cases = []
        for _ in range(160):
            length, pleats = rng.choice((ASPECT, 1.0)), rng.randint(4, 16)
            flip = rng.choice((0.0, math.pi, rng.uniform(0.0, math.pi)))
            fold = ACCORDION_MAX_FOLD if 0.0 < flip < math.pi else rng.uniform(0.0, ACCORDION_MAX_FOLD)
            cases.append((rng.uniform(0.0, length), length, pleats, fold, flip))
        gpu = probe.run("vec4 a = arg(0); FragColor = vec4(accordionFold(a.x, a.y, a.z, a.w, arg(1).x), 0.0, 0.0);",
                        [[(a, length, pleats, fold), (flip,)] for a, length, pleats, fold, flip in cases],
                        declarations=ACCORDION_GLSL)
        _check(gpu, [(*accordion_fold(*case), 0.0, 0.0) for case in cases])
    finally:
        probe.close()


@pytest.mark.parametrize("pleats", (4, 7, 12, 16))
def test_every_crease_lands_on_a_grid_vertex_row(pleats):
    for tier in SCENE3D_DETAIL_TIERS.values():
        for aspect in (16 / 9, 4 / 3, 9 / 16, 21 / 9):
            for vertical in (False, True):
                columns, rows = accordion_grid(pleats, tier.grid_cells, aspect, vertical)
                along, across = (rows, columns) if vertical else (columns, rows)
                assert along % pleats == 0 and along >= 2 * pleats and across == 1


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


def _distance_from_edge(edge: str) -> np.ndarray:
    xs = ((np.arange(W) + 0.5) / W - 0.5) * ASPECT
    ys = 0.5 - (np.arange(H) + 0.5) / H
    direction = accordion_edge(edge)
    length = 1.0 if edge in ("top", "bottom") else ASPECT
    return direction[0] * xs[None, :] + direction[1] * ys[:, None] + 0.5 * length


def _closer(frame, a, b, region) -> bool:
    return np.abs(frame[region] - a[region]).mean() < np.abs(frame[region] - b[region]).mean()


@pytest.mark.parametrize("detail", ("High", "Balanced", "Performance"))
@pytest.mark.parametrize("edge", tuple(ACCORDION_EDGES.values()))
def test_the_front_folds_away_and_the_back_unfolds_as_the_new_picture(capture, edge, detail):
    run = capture.run("accordion_fold", direction=edge, settings={"detail_3d": detail}, duration_ms=4000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    length = 1.0 if edge in ("top", "bottom") else ASPECT
    a = _distance_from_edge(edge)
    for progress, picture, other in ((_FOLD, source, destination), (_UNFOLD, destination, source)):
        frame = _pixels(capture.render(run, progress)[0])
        fold, _flip = accordion_state(progress)
        extent = length * math.cos(fold)
        near = a < 0.6 * extent                          # the sheet, against its own edge
        beyond = a > extent + 0.12                        # past it and its perspective: the backdrop
        assert near.any() and beyond.any()
        assert _closer(frame, picture, other, near), progress
        assert np.abs(frame[beyond] - picture[beyond]).mean() > 5


def test_the_backdrop_beyond_the_stack_holds_still(capture):
    run = capture.run("accordion_fold", direction="left", duration_ms=4000)
    first, second = (_pixels(capture.render(run, p)[0]) for p in (0.42, 0.56))
    beyond = _distance_from_edge("left") > ASPECT * math.cos(ACCORDION_MAX_FOLD) + 0.12
    assert np.array_equal(first[beyond], second[beyond])


def test_ends_are_continuous(capture):
    run = capture.run("accordion_fold", direction="bottom", duration_ms=4000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.abs(_pixels(capture.render(run, 0.01)[0]) - source).mean() < 0.5
    assert np.abs(_pixels(capture.render(run, 0.995)[0]) - destination).mean() < 0.5


def test_gloss_changes_only_the_folded_sheet(capture):
    frames = []
    for gloss in (0.0, 1.0):
        run = capture.run("accordion_fold", direction="right", settings={"accordion_fold": {"gloss": gloss}},
                          duration_ms=4000)
        frames.append(_pixels(capture.render(run, 0.3)[0]))
    changed = np.abs(frames[0] - frames[1]).max(axis=2) > 0
    fold, _flip = accordion_state(0.3)
    assert changed.any()
    assert not changed[_distance_from_edge("right") > ASPECT * math.cos(fold) + 0.12].any()


def test_warmed_runs_compile_and_allocate_nothing_on_their_first_frames(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("accordion_fold", direction="top", settings={"detail_3d": "High"}, duration_ms=3000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("accordion_fold", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 50
        renderer = capture.host._implementations["accordion_fold"]
        meshes = dict(renderer._resources._meshes)
        warmed, allocated = work.total, list(work.allocations)
        capture.render(run, 0.0)
        capture.render(run, 0.4)
        assert work.total == warmed and work.allocations == allocated
        assert renderer._resources._meshes == meshes
        capture.host.park()
        assert not renderer._target.has_resources and not renderer._environment.has_resources
        renderer.release_resources()
        assert not renderer.has_resources
    finally:
        capture.close()


def test_the_resolver_picks_edges_and_repairs_values():
    seen = {resolve_parameterized_phase_c_inputs("accordion_fold", {}, random_source=random.Random(seed)).direction
            for seed in range(40)}
    assert seen == set(ACCORDION_EDGES.values())
    resolved = resolve_parameterized_phase_c_inputs(
        "accordion_fold", {"accordion_fold": {"direction": "Top", "pleats": 99, "gloss": -1}},
        random_source=random.Random(1))
    assert resolved.direction == "top"
    assert resolved.parameter_dict()["pleats"] == 16 and resolved.parameter_dict()["gloss"] == 0.0
