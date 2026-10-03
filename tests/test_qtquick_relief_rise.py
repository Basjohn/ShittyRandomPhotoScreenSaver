"""Relief Rise through the production host on a real offscreen context (no window): the phase
mirror ends exactly; ahead of the wave the old picture and behind it the new one are exact;
the sweep travels the way its label says; gloss touches only the lifted relief; texture unit 3
(outside the host fence) is handed back; warm-up, park/release and the resolver."""
from __future__ import annotations

import random

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs.relief_rise_program import RELIEF_FRONT, relief_lift, relief_phase, relief_rank
from rendering.quick import gl_query
from rendering.quick.transitions.directions import direction_vector
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

W, H = 320, 180


def test_the_phase_ends_exactly_everywhere():
    rng = random.Random(4)
    for _ in range(500):
        rank = rng.random()
        assert relief_phase(0.0, rank) == 0.0 and relief_phase(1.0, rank) == 1.0
        assert relief_lift(relief_phase(0.0, rank)) == 0.0 and relief_lift(relief_phase(1.0, rank)) == 0.0


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


def _ranks(direction) -> np.ndarray:
    u = (np.arange(W) + 0.5) / W
    v = (np.arange(H) + 0.5) / H
    return relief_rank((u[None, :], v[:, None]), direction)


@pytest.mark.parametrize("detail", ("High", "Balanced", "Performance"))
@pytest.mark.parametrize("code", ("right", "up", "diag_br_tl"))
def test_ahead_of_the_wave_and_behind_it_the_pictures_are_exact(capture, code, detail):
    run = capture.run("relief_rise", direction=code, settings={"scene3d_detail": detail}, duration_ms=4000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    ranks = _ranks(direction_vector(code))
    for progress in (0.3, 0.5, 0.7):
        frame = _pixels(capture.render(run, progress)[0])
        front = progress * (1.0 + RELIEF_FRONT)
        ahead = ranks > front + 0.1                    # not reached yet (with room for the relief's perspective)
        behind = ranks < front - RELIEF_FRONT - 0.1    # settled
        assert ahead.any() or behind.any()
        assert np.abs(frame[ahead] - source[ahead]).max(initial=0) <= 1, progress
        assert np.abs(frame[behind] - destination[behind]).max(initial=0) <= 1, progress
        lifted = (ranks < front - 0.1 * RELIEF_FRONT) & (ranks > front - 0.9 * RELIEF_FRONT)
        if lifted.any():
            assert np.abs(frame[lifted] - source[lifted]).mean() > 3


@pytest.mark.parametrize("label,first", (("Left to Right", "left"), ("Bottom to Top", "bottom")))
def test_the_wave_travels_the_way_its_label_says(capture, label, first):
    run = capture.run("relief_rise", settings={"relief_rise": {"direction": label}}, duration_ms=4000)
    destination = _pixels(capture.images[1])
    frame = _pixels(capture.render(run, 0.4)[0])
    near = np.s_[:, :60] if first == "left" else np.s_[-35:]
    far = np.s_[:, -60:] if first == "left" else np.s_[:35]
    assert np.abs(frame[near] - destination[near]).mean() < np.abs(frame[far] - destination[far]).mean()


def test_gloss_touches_only_the_lifted_relief_and_unit_three_comes_back(capture):
    sentinel = int(gl.glGenTextures(1))
    try:
        frames = []
        for gloss in (0.0, 1.0):
            gl.glActiveTexture(gl.GL_TEXTURE3)
            gl.glBindTexture(gl.GL_TEXTURE_2D, sentinel)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            run = capture.run("relief_rise", direction="right", settings={"relief_rise": {"gloss": gloss}},
                              duration_ms=4000)
            frames.append(_pixels(capture.render(run, 0.5)[0]))
            gl.glActiveTexture(gl.GL_TEXTURE3)
            assert gl_query.get_int(gl.GL_TEXTURE_BINDING_2D) == sentinel
            gl.glActiveTexture(gl.GL_TEXTURE0)
        changed = np.abs(frames[0] - frames[1]).max(axis=2) > 0
        ranks = _ranks(direction_vector("right"))
        front = 0.5 * (1.0 + RELIEF_FRONT)
        assert changed.any()
        assert not changed[(ranks > front + 0.1) | (ranks < front - RELIEF_FRONT - 0.1)].any()
    finally:
        gl.glActiveTexture(gl.GL_TEXTURE3)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glDeleteTextures([sentinel])


def test_warmed_runs_compile_and_allocate_nothing_on_their_first_frames(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("relief_rise", direction="left", settings={"scene3d_detail": "High"}, duration_ms=3000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("relief_rise", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 50
        renderer = capture.host._implementations["relief_rise"]
        meshes = dict(renderer._resources._meshes)
        warmed, allocated = work.total, list(work.allocations)
        capture.render(run, 0.0)
        capture.render(run, 0.4)
        assert work.total == warmed and work.allocations == allocated
        assert renderer._resources._meshes == meshes
        capture.host.park()
        assert not renderer._target.has_resources and not renderer._heights.has_resources
        renderer.release_resources()
        assert not renderer.has_resources
    finally:
        capture.close()


def test_the_resolver_picks_directions_and_repairs_values():
    seen = {resolve_parameterized_phase_c_inputs("relief_rise", {}, random_source=random.Random(seed)).direction
            for seed in range(80)}
    assert len(seen) == 8
    resolved = resolve_parameterized_phase_c_inputs(
        "relief_rise", {"relief_rise": {"direction": "Left to Right", "depth": 5, "gloss": -2}},
        random_source=random.Random(1))
    assert resolved.direction == "right"
    assert resolved.parameter_dict()["depth"] == 1.0 and resolved.parameter_dict()["gloss"] == 0.0


def test_the_phase_and_lift_match_their_mirror_on_the_gpu(qt_app):
    from rendering.gl_programs import relief_rise_program as program
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    # The shader's own phase code, with its two frame uniforms as assignable globals.
    declarations = (program._COMMON.replace("uniform vec2 uDirection;", "vec2 uDirection;")
                    .replace("uniform float uProgress;", "float uProgress;"))
    probe = _GlslProbe()
    try:
        rng = random.Random(8)
        cases = []
        for _ in range(200):
            direction = direction_vector(rng.choice(("left", "right", "up", "down", "diag_tl_br", "diag_br_tl")))
            cases.append(((rng.random(), rng.random()), direction, rng.random()))
        gpu = probe.run("vec4 a = arg(0); uDirection = a.zw; uProgress = arg(1).x;"
                        "float phase = reliefPhase(a.xy); FragColor = vec4(phase, reliefLift(phase), 0.0, 0.0);",
                        [[(*uv, *d), (t,)] for uv, d, t in cases], declarations=declarations)
        expected = []
        for uv, d, t in cases:
            phase = relief_phase(t, relief_rank(uv, d))
            expected.append((phase, relief_lift(phase)))
        _check(gpu, expected, tolerance=1e-4)
    finally:
        probe.close()
