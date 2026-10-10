"""Surface Tension Merge: pools spread over the whole picture and the flood passes the threshold
everywhere before the meniscus settles, and through the production host on a real offscreen context
(no window): exact and continuous ends, pools of the new picture appear and grow while the rest is
the untouched old picture, Gloss touches only the edges, more pools make more boundary, warm-up
leaves the first frames nothing to compile, and the resolver."""
from __future__ import annotations

import random

import numpy as np
import pytest

from rendering.gl_programs.surface_tension_program import (
    TENSION_FLOOD,
    TENSION_SETTLE,
    TENSION_THRESHOLD,
    tension_field,
    tension_pools,
    tension_settle,
)
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

W, H = 320, 180
ASPECT = W / H


def test_pools_spread_and_the_flood_covers_before_the_meniscus_settles():
    assert TENSION_FLOOD[1] <= TENSION_SETTLE[1] and TENSION_SETTLE[1] < 1.0
    for count in (4, 10, 20):
        pools = tension_pools(7, count, ASPECT)
        assert len(pools) == count
        xs, ys = [p[0] for p in pools], [p[1] for p in pools]
        assert min(xs) < -ASPECT / 6 and max(xs) > ASPECT / 6 and min(ys) < -0.1 and max(ys) > 0.1
        for x in np.linspace(-ASPECT / 2, ASPECT / 2, 17):
            for y in np.linspace(-0.5, 0.5, 9):
                assert tension_field((x, y), pools, TENSION_FLOOD[1]) > TENSION_THRESHOLD
    assert tension_settle(0.5) == 1.0 and tension_settle(TENSION_SETTLE[1]) == 0.0


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


@pytest.mark.qt
def test_ends_are_exact_and_continuous(capture):
    run = capture.run("surface_tension", duration_ms=6000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    assert np.array_equal(_pixels(capture.render(run, TENSION_SETTLE[1])[0]), destination)
    assert np.abs(_pixels(capture.render(run, TENSION_SETTLE[1] - 0.004)[0]) - destination).mean() < 0.5
    assert np.abs(_pixels(capture.render(run, 0.01)[0]) - source).mean() < 0.5


@pytest.mark.qt
def test_pools_of_the_new_picture_grow_over_the_untouched_old_one(capture):
    run = capture.run("surface_tension", duration_ms=6000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    covered = []
    for progress in (0.2, 0.4, 0.6):
        frame = _pixels(capture.render(run, progress)[0])
        new = np.all(frame == destination, axis=2) & ~np.all(source == destination, axis=2)
        old = np.all(frame == source, axis=2)
        assert old.mean() + new.mean() > 0.8             # away from the edges, each picture exactly
        covered.append(new.mean())
    assert 0.0 < covered[0] < covered[1] < covered[2]


@pytest.mark.qt
def test_gloss_touches_only_the_edges_and_more_pools_make_more_boundary(capture):
    def frame(**section):
        run = capture.run("surface_tension", settings={"surface_tension": section}, duration_ms=6000)
        return _pixels(capture.render(run, 0.4)[0])

    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    dull, shiny = frame(gloss=0.0), frame(gloss=1.0)
    changed = np.abs(dull - shiny).max(axis=2) > 0
    plain = np.all(dull == source, axis=2) | np.all(dull == destination, axis=2)
    assert changed.any() and not (changed & plain).any()

    def edges(image):
        return ~(np.all(image == source, axis=2) | np.all(image == destination, axis=2))

    assert edges(frame(pools=20)).mean() > edges(frame(pools=4)).mean()


@pytest.mark.qt
def test_warmed_runs_compile_nothing_on_their_first_frames(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("surface_tension", duration_ms=4000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("surface_tension", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 10
        warmed = work.total
        for progress in (0.0, 0.3, 0.6, 1.0):
            capture.render(run, progress)
        assert work.total == warmed
        renderer = capture.host._implementations["surface_tension"]
        capture.host.park()
        renderer.release_resources()
        assert not renderer.has_resources
    finally:
        capture.close()


def test_the_resolver_seeds_runs_and_repairs_values():
    first, second = (resolve_parameterized_phase_c_inputs("surface_tension", {}, random_source=random.Random(s))
                     for s in (1, 2))
    assert first.direction is None and first.parameter_dict()["seed"] != second.parameter_dict()["seed"]
    resolved = resolve_parameterized_phase_c_inputs(
        "surface_tension", {"surface_tension": {"pools": 99, "gloss": -2}}, random_source=random.Random(1))
    assert resolved.parameter_dict()["pools"] == 20 and resolved.parameter_dict()["gloss"] == 0.0
