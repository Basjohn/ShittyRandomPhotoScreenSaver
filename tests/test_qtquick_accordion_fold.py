"""Accordion Fold: the fold geometry (CPU mirror) and the transition through the production
host on a real offscreen context (no window): pleats keep their width, creases sit on grid
vertex rows at every tier, exact and continuous ends, the uncovered new picture exact (shaded
as the mirror says) beyond the folded stack, every edge folds toward itself, a warm-up that
leaves the first frames nothing to do, park/release, and the resolver."""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from rendering.gl_programs.accordion_fold_options import ACCORDION_EDGES
from rendering.gl_programs.accordion_fold_program import (
    ACCORDION_MAX_ANGLE,
    ACCORDION_SHADE,
    ACCORDION_SHADE_REACH,
    accordion_edge,
    accordion_fold,
    accordion_grid,
    accordion_shade_weight,
    accordion_state,
)
from rendering.gl_programs.scene3d import SCENE3D_DETAIL_TIERS
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

W, H = 320, 180
ASPECT = W / H


def test_pleats_fold_without_stretching():
    length, pleats = ASPECT, 8
    for angle in (0.0, 0.3, 1.0, ACCORDION_MAX_ANGLE):
        step = 1e-4
        for a in np.linspace(0.0, length - step, 500):
            x0, z0 = accordion_fold(a, length, pleats, angle, 0.0)
            x1, z1 = accordion_fold(a + step, length, pleats, angle, 0.0)
            assert math.hypot(x1 - x0, z1 - z0) == pytest.approx(step, rel=1e-3)
    assert accordion_fold(0.37, length, pleats, 0.0, 0.0) == pytest.approx((0.37, 0.0))
    # The stack ends past its edge, and the shade with it.
    angle, slide = accordion_state(1.0, length, pleats)
    assert accordion_fold(length, length, pleats, angle, slide)[0] < 0.0
    assert accordion_shade_weight(1.0) == 0.0 and accordion_shade_weight(0.5) == 1.0


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


@pytest.mark.parametrize("detail", ("High", "Balanced", "Performance"))
@pytest.mark.parametrize("edge", tuple(ACCORDION_EDGES.values()))
def test_the_uncovered_picture_is_exact_beyond_the_stack(capture, edge, detail):
    run = capture.run("accordion_fold", direction=edge, settings={"detail_3d": detail}, duration_ms=4000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    length = 1.0 if edge in ("top", "bottom") else ASPECT
    a = _distance_from_edge(edge)
    for progress in (0.45, 0.6, 0.8):
        frame = _pixels(capture.render(run, progress)[0])
        angle, slide = accordion_state(progress, length, 8)
        front = length * math.cos(angle) - slide
        beyond = a > front + 0.12            # past the stack and its perspective
        assert beyond.any()
        shade = accordion_shade_weight(progress) * ACCORDION_SHADE * np.exp(-(a[beyond] - front) / ACCORDION_SHADE_REACH)
        expected = destination[beyond] * (1.0 - shade[:, None])
        assert np.abs(frame[beyond] - expected).max() <= 2, progress
        near = a < 0.02                      # the stack still stands against its edge while folding
        if progress < 0.72:
            assert np.abs(frame[near] - destination[near]).mean() > 5


def test_ends_are_continuous(capture):
    run = capture.run("accordion_fold", direction="bottom", duration_ms=4000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.abs(_pixels(capture.render(run, 0.01)[0]) - source).mean() < 0.5
    assert np.abs(_pixels(capture.render(run, 0.999)[0]) - destination).mean() < 0.5


def test_gloss_changes_only_the_folded_picture(capture):
    frames = []
    for gloss in (0.0, 1.0):
        run = capture.run("accordion_fold", direction="right", settings={"accordion_fold": {"gloss": gloss}},
                          duration_ms=4000)
        frames.append(_pixels(capture.render(run, 0.5)[0]))
    changed = np.abs(frames[0] - frames[1]).max(axis=2) > 0
    angle, slide = accordion_state(0.5, ASPECT, 8)
    assert changed.any()
    assert not changed[_distance_from_edge("right") > ASPECT * math.cos(angle) - slide + 0.12].any()


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
