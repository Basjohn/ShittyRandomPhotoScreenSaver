"""Beam through the production host on a real offscreen context (no window): the path starts and
ends off the picture and everything cures and dies before the run ends, exact and continuous
ends, both pictures exact beyond the beam's reach (and the new one once cured), scorch and colour
only where they belong, sparks alive only mid-run, a warm-up that leaves nothing to compile,
park/release, and the resolver."""
from __future__ import annotations

import random

import numpy as np
import pytest

from rendering.gl_programs.beam_program import (
    BEAM_CURE_SPAN,
    BEAM_SPARK_LIFE,
    BEAM_SWEEP_END,
    beam_direction,
    beam_intensity,
    beam_line,
    beam_passed_at,
    beam_path,
    beam_reach,
    beam_span,
    beam_spark_life_limit,
)
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

W, H = 320, 180
ASPECT = W / H
CODES = ("left", "right", "up", "down", "diag_tl_br", "diag_tr_bl", "diag_bl_tr", "diag_br_tl")


def test_the_beam_starts_and_ends_off_the_picture_and_everything_settles_in_time():
    for code in CODES:
        direction = beam_direction(code, ASPECT)
        near, far = beam_span(direction, ASPECT)
        for glow in (0.0, 0.6, 1.0):
            reach = beam_reach(glow)
            start, end = beam_path(near, far, reach)
            assert beam_line(0.0, start, end) == start == near - reach
            assert beam_line(BEAM_SWEEP_END, start, end) == end == far + reach
            # The last point it crosses has cured before the run ends.
            assert beam_passed_at(far, start, end) + BEAM_CURE_SPAN < 1.0
    speeds = np.diff([beam_line(t, -1.0, 1.0) for t in np.linspace(0.1, 0.6, 11)])
    assert speeds.max() - speeds.min() < 1e-12                      # a steady pace
    levels = [beam_intensity(t) for t in np.linspace(0.0, 1.0, 50)]
    assert all(b >= a for a, b in zip(levels, levels[1:])) and levels[-1] > levels[0]   # never flickers
    for duration in (1.0, 3.5, 10.0):
        assert beam_spark_life_limit(duration) <= (1.0 - BEAM_SWEEP_END) * duration
        assert beam_spark_life_limit(duration) <= BEAM_SPARK_LIFE[1]


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


def _along(direction) -> np.ndarray:
    xs = ((np.arange(W) + 0.5) / W - 0.5) * ASPECT
    ys = 0.5 - (np.arange(H) + 0.5) / H
    return direction[0] * xs[None, :] + direction[1] * ys[:, None]


def _geometry(code, glow):
    direction = beam_direction(code, ASPECT)
    near, far = beam_span(direction, ASPECT)
    reach = beam_reach(glow)
    return _along(direction), beam_path(near, far, reach), reach


@pytest.mark.parametrize("code", ("right", "down", "diag_tl_br", "diag_br_tl"))
def test_both_pictures_are_exact_beyond_the_beam_and_the_new_one_once_cured(capture, code):
    run = capture.run("beam", direction=code, settings={"beam": {"sparks": False}}, duration_ms=3500)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    along, path, reach = _geometry(code, run.request.parameter_dict()["glow"])
    pixel = 2.0 / H
    for progress in (0.3, 0.45, 0.6):
        frame = _pixels(capture.render(run, progress)[0])
        line = beam_line(progress, *path)
        ahead = along > line + reach + pixel
        cured = (along < line - reach - pixel) & (progress - beam_passed_at(along, *path) > BEAM_CURE_SPAN + 0.01)
        assert ahead.any() or cured.any()
        assert np.abs(frame[ahead] - source[ahead]).max(initial=0) <= 1, progress
        assert np.abs(frame[cured] - destination[cured]).max(initial=0) <= 1, progress
        # Where it has just passed, the new picture shows (scorched); ahead, the old one.
        behind = (along < line - reach - pixel) & (along > line - reach - 0.1)
        if behind.any():
            assert (np.abs(frame[behind] - destination[behind]).mean()
                    < np.abs(frame[behind] - source[behind]).mean())


def test_ends_are_continuous(capture):
    run = capture.run("beam", direction="up", duration_ms=3500)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.abs(_pixels(capture.render(run, 0.002)[0]) - source).mean() < 0.5
    assert np.abs(_pixels(capture.render(run, 0.998)[0]) - destination).mean() < 0.5


def test_scorch_darkens_only_what_the_beam_just_crossed(capture):
    frames = {}
    for scorch in (0.0, 1.0):
        run = capture.run("beam", direction="right", settings={"beam": {"scorch": scorch, "sparks": False}},
                          duration_ms=3500)
        frames[scorch] = _pixels(capture.render(run, 0.45)[0])
    along, path, reach = _geometry("right", run.request.parameter_dict()["glow"])
    line = beam_line(0.45, *path)
    changed = np.abs(frames[0.0] - frames[1.0]).max(axis=2) > 0
    assert not changed[along > line].any()                          # never ahead of the beam
    fresh = (along < line - reach) & (along > line - reach - 0.15)
    assert frames[1.0][fresh].sum() < frames[0.0][fresh].sum()      # darker where it just passed
    destination = _pixels(capture.images[1])
    zero = frames[0.0]
    assert np.abs(zero[fresh] - destination[fresh]).max() <= 1      # no scorch: the new picture exactly


def test_the_colour_tints_only_the_beam_and_its_light(capture):
    frames = {}
    for color in ((255, 40, 40, 255), (40, 255, 40, 255)):
        run = capture.run("beam", direction="left", settings={"beam": {"color": list(color), "sparks": False,
                                                                       "scorch": 0.0}}, duration_ms=3500)
        frames[color] = _pixels(capture.render(run, 0.4)[0])
    red, green = frames.values()
    along, path, reach = _geometry("left", run.request.parameter_dict()["glow"])
    line = beam_line(0.4, *path)
    changed = np.abs(red - green).max(axis=2) > 0
    assert changed.any() and not changed[np.abs(along - line) > reach + 2.0 / H].any()
    near = np.abs(along - line) < reach * 0.3
    assert red[near][:, 0].mean() > green[near][:, 0].mean() and green[near][:, 1].mean() > red[near][:, 1].mean()


def test_sparks_fly_mid_run_and_are_gone_before_the_end(capture):
    def frame(sparks, progress, duration_ms=3500):
        run = capture.run("beam", direction="down", settings={"beam": {"sparks": sparks}}, duration_ms=duration_ms)
        return _pixels(capture.render(run, progress)[0])

    assert np.abs(frame(True, 0.4) - frame(False, 0.4)).max() > 40
    assert np.array_equal(frame(True, 0.001), frame(False, 0.001))
    # Even on a short run (where a long-lived spark would still be on screen), none is left.
    for duration_ms in (1000, 3500):
        assert np.array_equal(frame(True, 0.97, duration_ms), frame(False, 0.97, duration_ms))


def test_warmed_runs_compile_nothing_and_beam_allocates_nothing(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("beam", direction="right", duration_ms=3000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("beam", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 20
        warmed, allocated = work.total, list(work.allocations)
        capture.render(run, 0.0)
        capture.render(run, 0.4)
        assert work.total == warmed and work.allocations == allocated == []
        renderer = capture.host._implementations["beam"]
        capture.host.park()
        renderer.release_resources()
        assert not renderer.has_resources
    finally:
        capture.close()


def test_the_resolver_picks_directions_and_repairs_values():
    seen = {resolve_parameterized_phase_c_inputs("beam", {}, random_source=random.Random(seed)).direction
            for seed in range(60)}
    assert seen == set(CODES)
    resolved = resolve_parameterized_phase_c_inputs(
        "beam", {"beam": {"direction": "Left to Right", "color": [255, 0, 128, 255], "glow": 4, "scorch": -1,
                          "sparks": False}}, random_source=random.Random(1))
    parameters = resolved.parameter_dict()
    assert resolved.direction == "right"
    assert parameters["color"] == pytest.approx((1.0, 0.0, 128 / 255))
    assert parameters["glow"] == 1.0 and parameters["scorch"] == 0.0 and parameters["sparks"] is False
    assert isinstance(parameters["seed"], int)
