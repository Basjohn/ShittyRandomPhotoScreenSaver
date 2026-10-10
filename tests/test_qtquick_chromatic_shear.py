"""Chromatic Shear: the separation is zero at both ends and the layers turn red first, violet last,
around the middle; through the production host on a real offscreen context (no window): exact and
continuous ends on every axis, slices shear apart along their axis (seams across it), the middle is
neither picture nor a plain crossfade, Spread 0 leaves no shear at all, more slices make more seams,
warm-up leaves the first frames nothing to compile, and the resolver."""
from __future__ import annotations

import random

import numpy as np
import pytest

from rendering.gl_programs.chromatic_shear_options import SHEAR_DIRECTIONS
from rendering.gl_programs.chromatic_shear_program import shear_envelope, shear_switch
from rendering.gl_programs.spectral import SPECTRAL_LAYERS, spectral_weight
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

W, H = 320, 180


def test_the_shear_vanishes_at_the_ends_and_the_layers_turn_in_spectral_order():
    assert shear_envelope(0.0) == 0.0 and shear_envelope(1.0) == pytest.approx(0.0, abs=1e-12)
    assert shear_envelope(0.5) == pytest.approx(1.0)
    for layer in range(SPECTRAL_LAYERS):
        assert shear_switch(0.3, layer) == 0.0 and shear_switch(0.7, layer) == 1.0
    turned = [shear_switch(0.5, layer) for layer in range(SPECTRAL_LAYERS)]
    assert all(a >= b for a, b in zip(turned, turned[1:])) and turned[0] > turned[-1]


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


def _seams(frame: np.ndarray, axis: int) -> int:
    """Rows (axis 0) or columns (axis 1) where the picture jumps more than its neighbours do."""
    step = np.abs(np.diff(frame, axis=axis)).mean(axis=(1 - axis, 2))
    return int((step > 3.0 * np.median(step) + 2.0).sum())


@pytest.mark.qt
@pytest.mark.parametrize("axis", tuple(SHEAR_DIRECTIONS.values()))
def test_ends_are_exact_and_continuous(capture, axis):
    run = capture.run("chromatic_shear", direction=axis, duration_ms=4000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    assert np.abs(_pixels(capture.render(run, 0.995)[0]) - destination).mean() < 0.5
    assert np.abs(_pixels(capture.render(run, 0.005)[0]) - source).mean() < 0.5


@pytest.mark.qt
def test_slices_shear_along_their_axis_and_the_middle_is_no_plain_crossfade(capture):
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    horizontal = _pixels(capture.render(capture.run("chromatic_shear", direction="horizontal", duration_ms=4000), 0.3)[0])
    vertical = _pixels(capture.render(capture.run("chromatic_shear", direction="vertical", duration_ms=4000), 0.3)[0])
    # Horizontal shear: slices are rows, so seams run across rows; vertical: across columns.
    assert _seams(horizontal, 0) > _seams(horizontal, 1) and _seams(vertical, 1) > _seams(vertical, 0)
    middle = _pixels(capture.render(capture.run("chromatic_shear", direction="horizontal", duration_ms=4000), 0.5)[0])
    blend = (source + destination) / 2
    assert np.abs(middle - source).mean() > 5 and np.abs(middle - destination).mean() > 5
    assert np.abs(middle - blend).mean() > 3


@pytest.mark.qt
def test_zero_spread_leaves_only_the_spectral_change_and_slices_add_seams(capture):
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1]).astype(float)
    still = _pixels(capture.render(capture.run("chromatic_shear", direction="horizontal",
                                               settings={"chromatic_shear": {"spread": 0.0}}, duration_ms=4000), 0.5)[0])
    weights = np.array([spectral_weight(i) for i in range(SPECTRAL_LAYERS)])
    turned = np.array([shear_switch(0.5, i) for i in range(SPECTRAL_LAYERS)])
    expected = source * (weights * (1 - turned)[:, None]).sum(0) + destination * (weights * turned[:, None]).sum(0)
    assert np.abs(still - expected).max() <= 2
    few, many = (_pixels(capture.render(capture.run("chromatic_shear", direction="horizontal",
                                                    settings={"chromatic_shear": {"slices": n}}, duration_ms=4000), 0.3)[0])
                 for n in (3, 14))
    assert _seams(many, 0) > _seams(few, 0)


@pytest.mark.qt
def test_warmed_runs_compile_nothing_on_their_first_frames(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("chromatic_shear", direction="diagonal", duration_ms=4000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("chromatic_shear", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 10
        warmed = work.total
        for progress in (0.0, 0.3, 0.6, 1.0):
            capture.render(run, progress)
        assert work.total == warmed
        renderer = capture.host._implementations["chromatic_shear"]
        capture.host.park()
        renderer.release_resources()
        assert not renderer.has_resources
    finally:
        capture.close()


def test_the_resolver_picks_axes_and_repairs_values():
    seen = {resolve_parameterized_phase_c_inputs("chromatic_shear", {}, random_source=random.Random(seed)).direction
            for seed in range(40)}
    assert seen == set(SHEAR_DIRECTIONS.values())
    resolved = resolve_parameterized_phase_c_inputs(
        "chromatic_shear", {"chromatic_shear": {"direction": "Vertical", "slices": 1, "spread": 9}},
        random_source=random.Random(1))
    assert resolved.direction == "vertical"
    assert resolved.parameter_dict()["slices"] == 3 and resolved.parameter_dict()["spread"] == 1.0
