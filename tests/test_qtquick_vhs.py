"""VHS Distortion: the timeline settles before the end; tearing bands leave most lines clean;
through the production host on a real offscreen context (no window), ends are exact in both roll
directions, all strengths at zero leave a clean roll of the two photographs, each strength changes
the picture, warm-up compiles everything a run's first frames need, and the resolver."""
from __future__ import annotations

import random

import numpy as np
import pytest

from rendering.gl_programs.analog_signal import signal_tear
from rendering.gl_programs.vhs_options import VHS_DIRECTIONS
from rendering.gl_programs.vhs_program import (
    VHS_BAR,
    VHS_PERIOD,
    VHS_ROLL_WINDOW,
    VHS_SETTLED,
    vhs_envelope,
    vhs_roll,
)
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

W, H = 320, 180
_CLEAN = {"vhs": {"tracking": 0.0, "bleed": 0.0, "noise": 0.0}}


def test_tracking_and_hold_settle_before_the_end():
    assert vhs_envelope(0.0) == 0.0 and vhs_roll(0.0) == 0.0
    assert VHS_ROLL_WINDOW[1] < VHS_SETTLED < 1.0
    for p in np.linspace(VHS_SETTLED, 1.0, 7):
        assert vhs_envelope(p) == 0.0 and vhs_roll(p) == VHS_PERIOD
    assert vhs_envelope(0.5) == pytest.approx(1.0)
    # The roll gets there: past the period's start by the middle, never running backwards far.
    rolls = [vhs_roll(p) for p in np.linspace(0.0, 1.0, 400)]
    assert max(rolls) <= VHS_PERIOD * 1.05
    assert all(b >= a - 0.02 for a, b in zip(rolls, rolls[1:]))


def test_tearing_bands_leave_most_lines_clean():
    for seed in (3, 77, 4096):
        torn = np.array([signal_tear(y, 1.3, 0.76, seed) for y in np.linspace(0.0, 1.0, 480)])
        assert 0.0 < (torn > 0.0).mean() < 0.35


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


@pytest.mark.qt
@pytest.mark.parametrize("direction", tuple(VHS_DIRECTIONS.values()))
def test_ends_are_exact(capture, direction):
    run = capture.run("vhs", direction=direction, duration_ms=3000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    assert np.array_equal(_pixels(capture.render(run, 0.975)[0]), destination)


def _rolled(source: np.ndarray, destination: np.ndarray, roll: float, sign: float) -> tuple[np.ndarray, np.ndarray]:
    """The clean strip at ``roll``: each screen row's expected colour and whether it is a picture row."""
    expected = np.zeros_like(source, dtype=np.float64)
    picture = np.zeros(H, dtype=bool)
    for row in range(H):
        t = (row + 0.5) / H + sign * roll
        k = np.floor(t / VHS_PERIOD)
        local = t - k * VHS_PERIOD
        if local >= 1.0:
            continue
        image = source if k == 0 else destination
        y = local * H - 0.5
        y0 = int(np.clip(np.floor(y), 0, H - 1))
        y1 = min(y0 + 1, H - 1)
        f = float(np.clip(y - y0, 0.0, 1.0))
        expected[row] = image[y0] * (1 - f) + image[y1] * f
        picture[row] = True
    return expected, picture


@pytest.mark.qt
@pytest.mark.parametrize(("direction", "sign"), (("up", 1.0), ("down", -1.0)))
def test_zero_strengths_leave_a_clean_roll(capture, direction, sign):
    run = capture.run("vhs", direction=direction, settings=_CLEAN, duration_ms=3000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    # Before the roll the picture is untouched, though tracking is already "lost".
    assert np.abs(_pixels(capture.render(run, 0.06)[0]) - source).max() <= 1
    for progress in (0.3, 0.5):
        frame = _pixels(capture.render(run, progress)[0])
        expected, picture = _rolled(source, destination, vhs_roll(progress), sign)
        # Away from the bar's edges, every picture row is the photograph rolled into place.
        interior = picture & (np.convolve(picture, np.ones(5), "same").astype(int) == 5)
        assert interior.sum() > H * (0.9 - VHS_BAR) * 0.9
        assert np.abs(frame[interior] - expected[interior]).mean() < 2.0
        assert frame[~picture].mean() < 40      # the blanking bar is dark


@pytest.mark.qt
@pytest.mark.parametrize("name", ("tracking", "bleed", "noise"))
def test_each_strength_changes_the_picture(capture, name):
    frames = []
    for value in (0.0, 1.0):
        settings = {"vhs": {**_CLEAN["vhs"], name: value}}
        run = capture.run("vhs", direction="up", settings=settings, duration_ms=3000)
        frames.append(_pixels(capture.render(run, 0.06)[0]))
    assert np.abs(frames[0] - frames[1]).mean() > 1.0


@pytest.mark.qt
def test_warmed_runs_compile_nothing_on_their_first_frames(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("vhs", direction="down", duration_ms=3000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("vhs", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 10
        warmed = work.total
        for progress in (0.0, 0.3, 0.6, 1.0):
            capture.render(run, progress)
        assert work.total == warmed
        renderer = capture.host._implementations["vhs"]
        capture.host.park()
        renderer.release_resources()
        assert not renderer.has_resources
    finally:
        capture.close()


def test_the_resolver_picks_directions_and_repairs_values():
    seen = {resolve_parameterized_phase_c_inputs("vhs", {}, random_source=random.Random(seed)).direction
            for seed in range(40)}
    assert seen == set(VHS_DIRECTIONS.values())
    resolved = resolve_parameterized_phase_c_inputs(
        "vhs", {"vhs": {"direction": "Top to Bottom", "tracking": 4, "bleed": -1, "noise": "x"}},
        random_source=random.Random(1))
    parameters = resolved.parameter_dict()
    assert resolved.direction == "down"
    assert parameters["tracking"] == 1.0 and parameters["bleed"] == 0.0 and 0.0 <= parameters["noise"] <= 1.0
    assert isinstance(parameters["seed"], int)
