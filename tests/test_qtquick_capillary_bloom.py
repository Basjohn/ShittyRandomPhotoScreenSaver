"""Capillary Bloom and its fibre field: the cost falls along channels by several times and the noise
matches its exact-integer GPU twin; through the production host on a real offscreen context (no
window): exact and continuous ends, the dyed area only grows and covers the picture by the fill,
Fibres reshape the fronts, warm-up builds the whole arrival field in bounded steps so the first frame
compiles and builds nothing, park drops the field, and the resolver."""
from __future__ import annotations

import random

import numpy as np
import pytest

from rendering.gl_programs.capillary_bloom_program import CAPILLARY_FILL, CAPILLARY_SETTLE, capillary_reach
from rendering.gl_programs.capillary_field import (
    CAPILLARY_COST,
    CAPILLARY_COST_MIN,
    CAPILLARY_FIELD_GLSL,
    capillary_cost,
    fibre_channels,
    fibre_noise,
)
from rendering.gl_programs.scene3d import SCENE3D_GLSL
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

W, H = 320, 180


def test_the_cost_falls_along_channels_and_the_reach_lands_on_the_fill():
    assert capillary_cost(0.0, 1.0) == pytest.approx(CAPILLARY_COST)
    assert capillary_cost(1.0, 1.0) == pytest.approx(CAPILLARY_COST_MIN)
    assert capillary_cost(1.0, 0.0) == pytest.approx(CAPILLARY_COST)          # Fibres 0: no channels
    assert capillary_cost(0.0, 1.0) / capillary_cost(0.8, 0.8) > 3.0
    assert capillary_reach(2.0, CAPILLARY_FILL) == pytest.approx(2.0) and capillary_reach(2.0, 0.0) == 0.0
    assert CAPILLARY_FILL < CAPILLARY_SETTLE[0] < CAPILLARY_SETTLE[1] < 1.0


@pytest.mark.qt
def test_the_fibre_field_matches_its_gpu_twin(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        rng = random.Random(12)
        points = [(rng.uniform(-3, 3), rng.uniform(-2, 2)) for _ in range(96)]
        gpu = probe.run("vec2 p = arg(0).xy; FragColor = vec4(fibreNoise(p * 5.0, 7u, 99u), "
                        "fibreChannels(p, vec2(0.6, 0.8), 1234u), capillaryCost(fibreChannels(p, vec2(0.6, 0.8), 1234u), 0.7), 0.0);",
                        [[p] for p in points], declarations=CAPILLARY_FIELD_GLSL)
        _check(gpu, [(fibre_noise((p[0] * 5, p[1] * 5), 7, 99), fibre_channels(p, (0.6, 0.8), 1234),
                      capillary_cost(fibre_channels(p, (0.6, 0.8), 1234), 0.7), 0.0) for p in points], tolerance=1e-4)
    finally:
        probe.close()
    assert "sceneRandom" in SCENE3D_GLSL


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


@pytest.mark.qt
def test_ends_are_exact_and_continuous(capture):
    run = capture.run("capillary_bloom", duration_ms=7000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    assert np.array_equal(_pixels(capture.render(run, CAPILLARY_SETTLE[1])[0]), destination)
    assert np.abs(_pixels(capture.render(run, CAPILLARY_SETTLE[1] - 0.004)[0]) - destination).mean() < 0.5
    assert np.abs(_pixels(capture.render(run, 0.005)[0]) - source).mean() < 1.0


@pytest.mark.qt
def test_the_dye_only_spreads_and_covers_the_picture_by_the_fill(capture):
    run = capture.run("capillary_bloom", duration_ms=7000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    covered = []
    for progress in (0.1, 0.25, 0.4, 0.55, 0.7, CAPILLARY_FILL + 0.03):
        frame = _pixels(capture.render(run, progress)[0])
        nearer_new = np.abs(frame - destination).sum(axis=2) < np.abs(frame - source).sum(axis=2)
        covered.append(nearer_new.mean())
    assert all(b >= a - 0.01 for a, b in zip(covered, covered[1:]))
    # (the last points dyed still show the stain, which carries some of the old picture)
    assert covered[0] < 0.4 and covered[-1] > 0.93


@pytest.mark.qt
def test_fibres_reshape_the_fronts(capture):
    frames = []
    for fibres in (0.0, 1.0):
        run = capture.run("capillary_bloom", settings={"capillary_bloom": {"fibres": fibres}}, duration_ms=7000)
        frames.append(_pixels(capture.render(run, 0.4)[0]))
    assert (np.abs(frames[0] - frames[1]).max(axis=2) > 10).mean() > 0.05


@pytest.mark.qt
def test_warm_up_builds_the_field_so_the_first_frame_builds_nothing(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("capillary_bloom", duration_ms=4000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("capillary_bloom", parameters, size):
            steps += 1
            assert steps < 30
        renderer = capture.host._implementations["capillary_bloom"]
        warmed, built = work.total, renderer._field.builds
        assert built == 1
        for progress in (0.0, 0.3, 0.6, 1.0):
            capture.render(run, progress)
        assert work.total == warmed and renderer._field.builds == built
        capture.host.park()
        assert not renderer._field.has_resources
        renderer.release_resources()
        assert not renderer.has_resources
    finally:
        capture.close()


def test_the_resolver_seeds_runs_and_repairs_values():
    first, second = (resolve_parameterized_phase_c_inputs("capillary_bloom", {}, random_source=random.Random(s))
                     for s in (1, 2))
    assert first.direction is None and first.parameter_dict()["seed"] != second.parameter_dict()["seed"]
    resolved = resolve_parameterized_phase_c_inputs(
        "capillary_bloom", {"capillary_bloom": {"sources": 0, "fibres": 3}}, random_source=random.Random(1))
    assert resolved.parameter_dict()["sources"] == 1 and resolved.parameter_dict()["fibres"] == 1.0
