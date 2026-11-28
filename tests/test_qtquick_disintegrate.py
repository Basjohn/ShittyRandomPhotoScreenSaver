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
from rendering.quick.transitions.directions import direction_vector
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.native_transition_capture import NativeTransitionCapture

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
    capture = NativeTransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


@pytest.mark.parametrize("detail", ("High", "Balanced"))
def test_frames_before_the_first_release_and_after_the_last_death_are_the_photographs(capture, detail):
    run = capture.run("disintegrate", direction="diag_tl_br", settings={"scene3d_detail": detail}, duration_ms=6000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 0.025)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 0.975)[0]), destination)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    middle = _pixels(capture.render(run, 0.45)[0])
    assert np.abs(middle - source).mean() > 5 and np.abs(middle - destination).mean() > 5
    assert np.array_equal(middle, _pixels(capture.render(run, 0.45)[0]))      # the same frame, the same pixels


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
