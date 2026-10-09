"""Volumetric Dissolve: the schedule finishes everything before the end; through the production
host on a real offscreen context (no window), ends are exact and continuous on every tier, cells
the front has not reached are the untouched old picture, the centre-out sweep reveals the centre
first, mist touches only what the front has passed and never the ends, texture unit 3 (outside the
host fence) is handed back, warm-up allocates the population and park drops it, and the resolver."""
from __future__ import annotations

import random

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs.volumetric_dissolve_options import VOLUMETRIC_DIRECTIONS, VOLUMETRIC_PARTICLE_SIZE_RANGE
from rendering.gl_programs.volumetric_dissolve_program import (
    VOLUMETRIC_RELEASE_JITTER,
    VOLUMETRIC_RELEASE_SPAN,
    VOLUMETRIC_RELEASE_START,
    volumetric_grid,
    volumetric_last_moment,
    volumetric_life,
    volumetric_rank,
    volumetric_release,
)
from rendering.quick import gl_query
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

W, H = 320, 180


def test_everything_has_finished_well_before_the_end():
    assert volumetric_last_moment() <= 0.95
    columns, rows, _size = volumetric_grid(W, H, 4)
    for particle in range(0, columns * rows, 97):
        for direction, radial in (((1.0, 0.0), False), ((0.7071, 0.7071), False), ((0.0, 1.0), True)):
            release = volumetric_release(particle, columns, rows, direction, radial, W / H, 11)
            assert VOLUMETRIC_RELEASE_START <= release <= (
                VOLUMETRIC_RELEASE_START + VOLUMETRIC_RELEASE_SPAN + VOLUMETRIC_RELEASE_JITTER)
            assert release + volumetric_life(particle, 11) <= volumetric_last_moment()


def test_the_front_starts_where_the_sweep_starts():
    aspect = W / H
    assert volumetric_rank(0.0, 0.5, (1.0, 0.0), False, aspect) == pytest.approx(0.0)
    assert volumetric_rank(1.0, 0.5, (1.0, 0.0), False, aspect) == pytest.approx(1.0)
    assert volumetric_rank(0.5, 0.5, (0.0, 1.0), True, aspect) == pytest.approx(0.0)
    assert volumetric_rank(1.0, 1.0, (0.0, 1.0), True, aspect) == pytest.approx(1.0)


def test_the_grid_stays_bounded():
    columns, rows, size = volumetric_grid(7680, 4320, 2)
    assert columns * rows <= 400_000 and size >= 2


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


@pytest.mark.qt
@pytest.mark.parametrize("detail", ("High", "Balanced", "Performance"))
@pytest.mark.parametrize("direction", ("right", "diag_br_tl", "center_out"))
def test_ends_are_exact_and_continuous_on_every_tier(capture, detail, direction):
    run = capture.run("volumetric_dissolve", direction=direction, settings={"scene3d_detail": detail},
                      duration_ms=7000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    assert np.array_equal(_pixels(capture.render(run, 0.003)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 0.96)[0]), destination)


@pytest.mark.qt
def test_cells_the_front_has_not_reached_are_the_untouched_old_picture(capture):
    run = capture.run("volumetric_dissolve", direction="right", duration_ms=7000)
    source = _pixels(capture.images[0])
    frame = _pixels(capture.render(run, 0.12)[0])
    far = np.s_[:, int(W * 0.72):]
    assert np.array_equal(frame[far], source[far])
    assert np.abs(frame[:, : W // 5] - source[:, : W // 5]).mean() > 5     # the start side has gone


@pytest.mark.qt
def test_centre_out_reveals_the_centre_first(capture):
    run = capture.run("volumetric_dissolve", direction="center_out", duration_ms=7000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    frame = _pixels(capture.render(run, 0.5)[0])
    new = (np.abs(frame - destination).sum(-1) < np.abs(frame - source).sum(-1)).astype(float)
    centre = new[H // 3: 2 * H // 3, W // 3: 2 * W // 3].mean()
    corners = np.concatenate([new[: H // 6, : W // 6].ravel(), new[-H // 6:, -W // 6:].ravel()]).mean()
    assert centre > corners + 0.3


@pytest.mark.qt
def test_mist_touches_only_the_passed_front_never_the_ends_and_unit_3_is_handed_back(capture):
    sentinel = int(gl.glGenTextures(1))
    try:
        frames = {}
        for mist in (0.0, 1.0):
            gl.glActiveTexture(gl.GL_TEXTURE3)
            gl.glBindTexture(gl.GL_TEXTURE_2D, sentinel)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            run = capture.run("volumetric_dissolve", direction="right",
                              settings={"volumetric_dissolve": {"mist": mist}}, duration_ms=7000)
            frames[mist] = [_pixels(capture.render(run, p)[0]) for p in (0.003, 0.12, 0.4, 0.96)]
            gl.glActiveTexture(gl.GL_TEXTURE3)
            assert gl_query.get_int(gl.GL_TEXTURE_BINDING_2D) == sentinel
            gl.glActiveTexture(gl.GL_TEXTURE0)
        assert np.array_equal(frames[0.0][0], frames[1.0][0]) and np.array_equal(frames[0.0][3], frames[1.0][3])
        far = np.s_[:, int(W * 0.72):]
        assert np.array_equal(frames[0.0][1][far], frames[1.0][1][far])
        assert np.abs(frames[0.0][2] - frames[1.0][2]).mean() > 1.0
    finally:
        gl.glActiveTexture(gl.GL_TEXTURE3)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glDeleteTextures([sentinel])


@pytest.mark.qt
def test_warmed_runs_compile_and_allocate_nothing_on_their_first_frames(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("volumetric_dissolve", direction="left", settings={"scene3d_detail": "High"},
                          duration_ms=3000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("volumetric_dissolve", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 60
        renderer = capture.host._implementations["volumetric_dissolve"]
        assert renderer._particles.has_resources
        warmed, allocated = work.total, list(work.allocations)
        capture.render(run, 0.0)
        capture.render(run, 0.4)
        assert work.total == warmed and work.allocations == allocated
        capture.host.park()
        assert not renderer._target.has_resources and not renderer._environment.has_resources
        assert not renderer._particles.has_resources
        renderer.release_resources()
        assert not renderer.has_resources
    finally:
        capture.close()


def test_the_resolver_picks_directions_and_repairs_values():
    seen = {resolve_parameterized_phase_c_inputs("volumetric_dissolve", {}, random_source=random.Random(seed))
            .direction for seed in range(80)}
    assert seen == set(VOLUMETRIC_DIRECTIONS.values())
    resolved = resolve_parameterized_phase_c_inputs(
        "volumetric_dissolve", {"volumetric_dissolve": {"direction": "Center Out", "particle_size": 99, "mist": 4,
                                                        "depth": -1}}, random_source=random.Random(1))
    parameters = resolved.parameter_dict()
    assert resolved.direction == "center_out"
    assert parameters["particle_size"] == VOLUMETRIC_PARTICLE_SIZE_RANGE[1]
    assert parameters["mist"] == 1.0 and parameters["depth"] == 0.0
