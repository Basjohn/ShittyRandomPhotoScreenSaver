"""Membrane Turnover: every part of the membrane turns over and fades by MEMBRANE_DONE, the phase
follows the sweep, and through the production host on a real offscreen context (no window): exact
and continuous ends for every sweep and tier, the twist starts on the side the sweep comes from
(a reversed sweep fails), the turned membrane shows the new picture through it, Gloss changes only
the moving membrane, warm-up leaves the first frames nothing to compile or allocate, park/release,
and the resolver."""
from __future__ import annotations

import random

import numpy as np
import pytest

from rendering.gl_programs.membrane_options import MEMBRANE_SWEEPS, MEMBRANE_SWEEP_VECTORS
from rendering.gl_programs.membrane_program import (
    MEMBRANE_DONE,
    membrane_back_opacity,
    membrane_phase,
    membrane_rank,
)
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

W, H = 320, 180
ASPECT = W / H


def test_the_whole_membrane_turns_and_fades_by_done_following_the_sweep():
    for sweep in MEMBRANE_SWEEP_VECTORS.values():
        first = membrane_rank((-sweep[0] * ASPECT / 2, -sweep[1] / 2), sweep, ASPECT)
        last = membrane_rank((sweep[0] * ASPECT / 2, sweep[1] / 2), sweep, ASPECT)
        assert first == pytest.approx(0.0) and last == pytest.approx(1.0)
    for rank in np.linspace(0.0, 1.0, 11):
        assert membrane_phase(0.0, rank) == 0.0
        assert membrane_phase(MEMBRANE_DONE, rank) == pytest.approx(1.0)
        assert membrane_back_opacity(membrane_phase(MEMBRANE_DONE, rank)) == pytest.approx(0.0)
        phases = [membrane_phase(p, rank) for p in np.linspace(0.0, 1.0, 50)]
        assert all(b >= a for a, b in zip(phases, phases[1:]))
    assert membrane_phase(0.4, 0.1) > membrane_phase(0.4, 0.9)


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


@pytest.mark.qt
@pytest.mark.parametrize("detail", ("High", "Performance"))
@pytest.mark.parametrize("sweep", tuple(MEMBRANE_SWEEPS.values()))
def test_ends_are_exact_and_continuous(capture, sweep, detail):
    run = capture.run("membrane", direction=sweep, settings={"scene3d_detail": detail}, duration_ms=5000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    assert np.array_equal(_pixels(capture.render(run, MEMBRANE_DONE)[0]), destination)
    assert np.abs(_pixels(capture.render(run, MEMBRANE_DONE - 0.004)[0]) - destination).mean() < 0.5
    assert np.abs(_pixels(capture.render(run, 0.005)[0]) - source).mean() < 0.5


@pytest.mark.qt
@pytest.mark.parametrize("sweep", tuple(MEMBRANE_SWEEPS.values()))
def test_the_twist_starts_where_the_sweep_comes_from_and_shows_the_new_picture(capture, sweep):
    run = capture.run("membrane", direction=sweep, duration_ms=5000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    frame = _pixels(capture.render(run, 0.45)[0])
    vector = MEMBRANE_SWEEP_VECTORS[sweep]
    start = {(1.0, 0.0): np.s_[:, : W // 6], (-1.0, 0.0): np.s_[:, -W // 6:],
             (0.0, -1.0): np.s_[: H // 6, :], (0.0, 1.0): np.s_[-H // 6:, :]}[vector]
    end = {(1.0, 0.0): np.s_[:, -W // 6:], (-1.0, 0.0): np.s_[:, : W // 6],
           (0.0, -1.0): np.s_[-H // 6:, :], (0.0, 1.0): np.s_[: H // 6, :]}[vector]
    # Where the twist began, the new picture shows (the membrane there has turned and thinned).
    assert np.abs(frame[start] - destination[start]).mean() < np.abs(frame[start] - source[start]).mean()
    # Where it has not reached yet, the membrane is still the flat old picture.
    assert np.abs(frame[end] - source[end]).mean() < np.abs(frame[end] - destination[end]).mean()


@pytest.mark.qt
def test_gloss_changes_only_the_moving_membrane(capture):
    frames = []
    for gloss in (0.0, 1.0):
        run = capture.run("membrane", direction="right", settings={"membrane": {"gloss": gloss}}, duration_ms=5000)
        frames.append(_pixels(capture.render(run, 0.3)[0]))
    changed = np.abs(frames[0] - frames[1]).max(axis=2) > 0
    assert changed.any()
    assert not changed[:, -W // 5:].any()                 # not yet reached: the flat photograph


@pytest.mark.qt
def test_warmed_runs_compile_and_allocate_nothing_on_their_first_frames(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("membrane", direction="down", settings={"scene3d_detail": "High"}, duration_ms=3000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("membrane", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 50
        renderer = capture.host._implementations["membrane"]
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


def test_the_resolver_picks_sweeps_and_repairs_values():
    seen = {resolve_parameterized_phase_c_inputs("membrane", {}, random_source=random.Random(seed)).direction
            for seed in range(40)}
    assert seen == set(MEMBRANE_SWEEPS.values())
    resolved = resolve_parameterized_phase_c_inputs(
        "membrane", {"membrane": {"direction": "Bottom to Top", "gloss": 4}}, random_source=random.Random(1))
    assert resolved.direction == "up" and resolved.parameter_dict()["gloss"] == 1.0
