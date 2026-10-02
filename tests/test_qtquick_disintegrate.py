"""Disintegrate through the production host on a real offscreen context (no window).

The release schedule (CPU mirror) keeps the run's ends exact; the GPU's live grains are the
mirror's, in id order; frames before the first release and after the last grain dies are the
photographs exactly although they take the full population path; a frame renders identically
twice; the first frames after warm-up compile and allocate nothing; park/release; resolver.
"""
from __future__ import annotations

import random

import numpy as np
import pytest

from rendering.gl_programs.disintegrate_program import (
    DISINTEGRATE_MAX_GRAINS,
    disintegrate_grid,
    disintegrate_life,
    disintegrate_noise,
    disintegrate_release,
)
from rendering.quick.scene3d.population import POPULATION_FIRST_BINDING
from rendering.quick.transitions.directions import direction_vector
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

W, H = 320, 180


def test_the_schedule_leaves_both_ends_exact_and_the_grid_bounded():
    columns, rows, _size = disintegrate_grid(W, H, 3)
    rng = random.Random(3)
    for _ in range(2000):
        grain = rng.randrange(columns * rows)
        direction = direction_vector(rng.choice(("left", "diag_br_tl", "up")))
        seed = rng.randint(1, 65535)
        release = disintegrate_release(grain, columns, rows, direction, W / H, seed)
        assert 0.03 <= release and release + disintegrate_life(grain, seed) <= 0.97
        assert 0.0 <= disintegrate_noise(rng.uniform(0, 40), rng.uniform(0, 20), seed) <= 1.0
    columns, rows, size = disintegrate_grid(7680, 4320, 2)
    assert columns * rows <= DISINTEGRATE_MAX_GRAINS and size > 2


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


@pytest.mark.parametrize("detail", ("High", "Balanced"))
def test_frames_before_the_first_release_and_after_the_last_death_are_the_photographs(capture, detail):
    run = capture.run("disintegrate", direction="diag_tl_br", settings={"detail_3d": detail}, duration_ms=6000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 0.025)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 0.975)[0]), destination)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    middle = _pixels(capture.render(run, 0.45)[0])
    assert np.abs(middle - source).mean() > 5 and np.abs(middle - destination).mean() > 5
    assert np.array_equal(middle, _pixels(capture.render(run, 0.45)[0]))      # the same frame, the same pixels


@pytest.mark.parametrize("direction", ("right", "up", "diag_bl_tr"))
def test_the_gpu_grains_are_the_mirrors_live_grains_in_order(capture, direction):
    from OpenGL import GL as gl

    run = capture.run("disintegrate", direction=direction, duration_ms=6000)
    parameters = run.request.parameter_dict()
    seed, grain = parameters["seed"], parameters["grain_size"]
    columns, rows, _size = disintegrate_grid(W, H, grain)
    vector = direction_vector(direction)
    for progress in (0.2, 0.5, 0.8):
        capture.render(run, progress)
        expected = []
        for g in range(columns * rows):
            release = disintegrate_release(g, columns, rows, vector, W / H, seed)
            if release <= progress < release + disintegrate_life(g, seed):
                expected.append(g)
        names = capture.host._implementations["disintegrate"]._grains._names
        gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)
        command = np.zeros(4, np.uint32)
        gl.glGetNamedBufferSubData(names[POPULATION_FIRST_BINDING + 2], 0, command.nbytes, command)
        ids = np.zeros(int(command[1]), np.uint32)
        if len(ids):
            gl.glGetNamedBufferSubData(names[POPULATION_FIRST_BINDING + 3], 0, ids.nbytes, ids)
        # Float rounding may move a release that sits exactly on this progress by one ulp.
        borderline = {g for g in range(columns * rows)
                      if abs(disintegrate_release(g, columns, rows, vector, W / H, seed) - progress) < 1e-5
                      or abs(disintegrate_release(g, columns, rows, vector, W / H, seed)
                             + disintegrate_life(g, seed) - progress) < 1e-5}
        got = [g for g in ids.tolist() if g not in borderline]
        assert got == [g for g in expected if g not in borderline], progress
        assert ids.tolist() == sorted(ids.tolist())


def test_warmed_runs_compile_and_allocate_nothing_on_their_first_frames(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("disintegrate", direction="left", settings={"detail_3d": "High"}, duration_ms=3000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("disintegrate", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 50
        renderer = capture.host._implementations["disintegrate"]
        buffers = dict(renderer._grains._names)
        assert buffers                                                  # the run's population is ready
        warmed, allocated = work.total, list(work.allocations)
        capture.render(run, 0.0)
        capture.render(run, 0.4)
        assert work.total == warmed and work.allocations == allocated
        assert renderer._grains._names == buffers
        capture.host.park()
        assert not renderer._grains.has_resources and not renderer._target.has_resources
        renderer.release_resources()
        assert not renderer.has_resources
    finally:
        capture.close()


def test_the_resolver_picks_directions_and_repairs_values():
    seen = set()
    for seed in range(80):
        seen.add(resolve_parameterized_phase_c_inputs("disintegrate", {}, random_source=random.Random(seed)).direction)
    assert len(seen) == 8
    resolved = resolve_parameterized_phase_c_inputs(
        "disintegrate", {"disintegrate": {"direction": "Right to Left", "grain_size": 40, "wind": 0.1}},
        random_source=random.Random(1))
    parameters = resolved.parameter_dict()
    assert resolved.direction == "left"
    assert parameters["grain_size"] == 8 and parameters["wind"] == 0.5 and 1 <= parameters["seed"] <= 65535


@pytest.mark.parametrize("label,first", (("Left to Right", "left"), ("Right to Left", "right"),
                                         ("Top to Bottom", "top"), ("Bottom to Top", "bottom")))
def test_the_wind_blows_the_way_its_label_says(capture, label, first):
    run = capture.run("disintegrate", settings={"disintegrate": {"direction": label}}, duration_ms=6000)
    destination = _pixels(capture.images[1])
    frame = _pixels(capture.render(run, 0.35)[0])
    sides = {"left": np.s_[:, :80], "right": np.s_[:, -80:], "top": np.s_[:45], "bottom": np.s_[-45:]}
    opposite = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}[first]
    near = np.abs(frame[sides[first]] - destination[sides[first]]).mean()
    far = np.abs(frame[sides[opposite]] - destination[sides[opposite]]).mean()
    assert near < far                       # the side the wind comes from is uncovered first
