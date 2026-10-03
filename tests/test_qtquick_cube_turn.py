"""Cube Turn through the production host on a real offscreen context (no window): the turn and
dolly mirror end square on, ends exact and continuous on every tier, the new picture arrives
from the side the box turns away from, gloss touches nothing at rest, warm-up, park/release and
the resolver."""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from rendering.gl_programs.cube_turn_options import CUBE_TURN_DIRECTIONS
from rendering.gl_programs.cube_turn_program import cube_turn_axis, cube_turn_lift, cube_turn_state
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

W, H = 320, 180


def test_the_turn_ends_square_on_with_the_camera_home():
    for direction in CUBE_TURN_DIRECTIONS.values():
        _axis, sign = cube_turn_axis(direction)
        assert cube_turn_state(0.0, sign) == (0.0, 1.0)
        angle, zoom = cube_turn_state(1.0, sign)
        assert angle == pytest.approx(sign * math.pi / 2) and zoom == pytest.approx(1.0)
        assert cube_turn_lift(0.0) == 0.0 and cube_turn_lift(angle) == pytest.approx(0.0, abs=1e-12)
        assert cube_turn_state(0.5, sign)[1] < 0.8               # the camera draws back mid-turn


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


@pytest.mark.parametrize("detail", ("High", "Balanced", "Performance"))
@pytest.mark.parametrize("direction", tuple(CUBE_TURN_DIRECTIONS.values()))
def test_ends_are_exact_and_continuous_and_the_new_picture_comes_from_the_far_side(capture, direction, detail):
    run = capture.run("cube_turn", direction=direction, settings={"scene3d_detail": detail}, duration_ms=4000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    assert np.abs(_pixels(capture.render(run, 0.003)[0]) - source).mean() < 1.0
    assert np.abs(_pixels(capture.render(run, 0.997)[0]) - destination).mean() < 1.0
    frame = _pixels(capture.render(run, 0.6)[0])
    # The box turns its front toward ``direction``: the new picture's side comes from the opposite one.
    incoming = {"left": np.s_[:, W // 2:], "right": np.s_[:, :W // 2], "up": np.s_[H // 2:], "down": np.s_[:H // 2]}
    outgoing = {"left": np.s_[:, :W // 2], "right": np.s_[:, W // 2:], "up": np.s_[:H // 2], "down": np.s_[H // 2:]}
    # Mid-turn the faces are foreshortened, not in place: compare colour, not position. The
    # fixtures' old picture is purple and the new one green, so the new side is the greener.
    def greenness(region):
        pixels = frame[region].reshape(-1, 3)
        return float((pixels[:, 1] - pixels[:, 0]).mean())

    assert destination[..., 1].mean() - destination[..., 0].mean() > source[..., 1].mean() - source[..., 0].mean()
    assert greenness(incoming[direction]) > greenness(outgoing[direction]) + 10


def test_gloss_touches_nothing_at_rest_and_something_mid_turn(capture):
    frames = {}
    for gloss in (0.0, 1.0):
        run = capture.run("cube_turn", direction="up", settings={"cube_turn": {"gloss": gloss}}, duration_ms=4000)
        frames[gloss] = [_pixels(capture.render(run, p)[0]) for p in (0.0, 0.5, 1.0)]
    assert np.array_equal(frames[0.0][0], frames[1.0][0]) and np.array_equal(frames[0.0][2], frames[1.0][2])
    assert np.abs(frames[0.0][1] - frames[1.0][1]).max() > 0


def test_warmed_runs_compile_and_allocate_nothing_on_their_first_frames(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("cube_turn", direction="right", settings={"scene3d_detail": "High"}, duration_ms=3000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("cube_turn", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 50
        renderer = capture.host._implementations["cube_turn"]
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


def test_the_resolver_picks_directions_and_repairs_values():
    seen = {resolve_parameterized_phase_c_inputs("cube_turn", {}, random_source=random.Random(seed)).direction
            for seed in range(40)}
    assert seen == set(CUBE_TURN_DIRECTIONS.values())
    resolved = resolve_parameterized_phase_c_inputs(
        "cube_turn", {"cube_turn": {"direction": "Down", "gloss": 3}}, random_source=random.Random(1))
    assert resolved.direction == "down" and resolved.parameter_dict()["gloss"] == 1.0
