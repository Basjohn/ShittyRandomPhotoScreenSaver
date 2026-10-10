"""Depth Card Cascade: cards start in a wave along the sweep and every card has cleared the frame
by the end of its flight, before CASCADE_DONE; through the production host on a real offscreen
context (no window): exact and continuous ends for every sweep and tier, the cards near the
sweep's start lift first showing the new picture under them, Shadows only darken the new picture,
warm-up compiles everything, park drops the cards, and the resolver."""
from __future__ import annotations

import random

import numpy as np
import pytest

from rendering.gl_programs.depth_cascade_options import CASCADE_SWEEPS, CASCADE_SWEEP_VECTORS
from rendering.gl_programs.depth_cascade_program import (
    CASCADE_DONE,
    CASCADE_FLIGHT,
    cascade_cards,
    cascade_corner,
    screen_point,
)
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

W, H = 320, 180
ASPECT = W / H


def test_cards_start_along_the_sweep_and_clear_the_frame_before_done():
    assert CASCADE_DONE < 1.0
    for sweep in CASCADE_SWEEP_VECTORS.values():
        for seed in range(12):
            for count in (4, 8, 14):
                cards = cascade_cards(seed, count, ASPECT, sweep)
                first = min(cards, key=lambda c: c[4])
                last = max(cards, key=lambda c: c[4])
                lead = lambda c: 0.5 * (c[0] + c[2]) * sweep[0] + 0.5 * (c[1] + c[3]) * sweep[1]
                assert lead(first) < lead(last)
                for card in cards:
                    assert card[4] + CASCADE_FLIGHT <= CASCADE_DONE + 1e-9
                    points = [screen_point(cascade_corner(card, (u, v), card[4] + CASCADE_FLIGHT))
                              for u in (0.0, 1.0) for v in (0.0, 1.0)]
                    xs, ys = [p[0] for p in points], [p[1] for p in points]
                    assert (min(xs) > ASPECT / 2 or max(xs) < -ASPECT / 2 or min(ys) > 0.5 or max(ys) < -0.5)


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


@pytest.mark.qt
@pytest.mark.parametrize("detail", ("High", "Performance"))
@pytest.mark.parametrize("sweep", tuple(CASCADE_SWEEPS.values()))
def test_ends_are_exact_and_continuous(capture, sweep, detail):
    run = capture.run("depth_cascade", direction=sweep, settings={"scene3d_detail": detail}, duration_ms=6000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    assert np.array_equal(_pixels(capture.render(run, CASCADE_DONE)[0]), destination)
    assert np.abs(_pixels(capture.render(run, CASCADE_DONE - 0.004)[0]) - destination).mean() < 0.5
    assert np.abs(_pixels(capture.render(run, 0.003)[0]) - source).mean() < 0.5


@pytest.mark.qt
@pytest.mark.parametrize("sweep", tuple(CASCADE_SWEEPS.values()))
def test_cards_near_the_start_lift_first_over_the_new_picture(capture, sweep):
    run = capture.run("depth_cascade", direction=sweep, duration_ms=6000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    frame = _pixels(capture.render(run, 0.3)[0])
    start = {"right": np.s_[:, : W // 5], "left": np.s_[:, -W // 5:],
             "down": np.s_[: H // 5, :], "up": np.s_[-H // 5:, :]}[sweep]
    end = {"right": np.s_[:, -W // 6:], "left": np.s_[:, : W // 6],
           "down": np.s_[-H // 6:, :], "up": np.s_[: H // 6, :]}[sweep]
    moved = lambda region: np.abs(frame[region] - source[region]).mean()
    assert moved(start) > moved(end) + 3
    assert (np.abs(frame[start] - destination[start]).max(axis=2) == 0).mean() > 0.05


@pytest.mark.qt
def test_shadows_only_darken_the_new_picture(capture):
    frames = []
    for shadows in (False, True):
        run = capture.run("depth_cascade", direction="right", settings={"depth_cascade": {"shadows": shadows, "antialiasing": "Off"}},
                          duration_ms=6000)
        frames.append(_pixels(capture.render(run, 0.3)[0]))
    plain, shaded = frames
    changed = np.abs(plain - shaded).max(axis=2) > 0
    destination = _pixels(capture.images[1])
    assert changed.any()
    # Only where the new picture showed (no multisampled rims with anti-aliasing off), always darker.
    assert np.all(plain[changed] == destination[changed], axis=-1).all()
    assert (shaded[changed].sum(axis=-1) <= plain[changed].sum(axis=-1)).all()


@pytest.mark.qt
def test_warmed_runs_compile_nothing_and_park_drops_the_cards(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("depth_cascade", direction="up", settings={"scene3d_detail": "High"}, duration_ms=4000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("depth_cascade", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 50
        warmed = work.total
        capture.render(run, 0.0)
        capture.render(run, 0.4)
        assert work.total == warmed
        renderer = capture.host._implementations["depth_cascade"]
        assert renderer._resources.has_mesh("cards")
        capture.host.park()
        assert not renderer._resources.has_mesh("cards")
        assert not renderer._target.has_resources and not renderer._environment.has_resources
        renderer.release_resources()
        assert not renderer.has_resources
    finally:
        capture.close()


def test_the_resolver_picks_sweeps_and_repairs_values():
    seen = {resolve_parameterized_phase_c_inputs("depth_cascade", {}, random_source=random.Random(seed)).direction
            for seed in range(40)}
    assert seen == set(CASCADE_SWEEPS.values())
    resolved = resolve_parameterized_phase_c_inputs(
        "depth_cascade", {"depth_cascade": {"direction": "Top to Bottom", "cards": 40, "gloss": -1, "shadows": False}},
        random_source=random.Random(1))
    params = resolved.parameter_dict()
    assert resolved.direction == "down" and params["cards"] == 14 and params["gloss"] == 0.0
    assert params["shadows"] is False
