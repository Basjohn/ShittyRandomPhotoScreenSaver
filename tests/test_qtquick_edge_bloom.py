"""Edge Bloom Reveal and its shared edge field.

The field's GPU stages match their CPU mirror (ridges from the blurred luma; flooded distances
within a texel of brute force); the timeline fills everything and fades all light before the end;
through the production host on a real offscreen context (no window), ends are exact, light first
appears on the new picture's contours, the fill reaches contours before flat regions, Glow 0 adds
no light, each field is built once per run, warm-up allocates the fields and park drops them; the
resolver repairs values."""
from __future__ import annotations

import ctypes
import random

import numpy as np
import pytest
from OpenGL import GL as gl
from PIL import Image, ImageDraw

from rendering.gl_programs.edge_bloom_program import (
    EDGE_BLOOM_FADE,
    EDGE_BLOOM_LATEST,
    EDGE_BLOOM_SETTLED,
    EDGE_BLOOM_SOFT,
    edge_bloom_appear,
    edge_bloom_fill_time,
    edge_bloom_thresholds,
)
from rendering.quick.scene3d.edge_field import EDGE_FIELD_SEED, edge_field_jumps, edge_ridge_reference
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

W, H = 320, 180


def test_everything_fills_and_the_light_fades_before_the_end():
    for distance in (0.0, 0.1, 0.5, 4.0):
        for order in (0.0, 1.0):
            for jitter in (-0.5, 0.5):
                assert edge_bloom_fill_time(distance, order, jitter) + EDGE_BLOOM_SOFT[1] < EDGE_BLOOM_SETTLED
                # A contour lights up before the fill leaves it.
                assert edge_bloom_appear(1.0, order) < edge_bloom_fill_time(0.0, order, -0.5)
    assert EDGE_BLOOM_LATEST + EDGE_BLOOM_SOFT[1] <= EDGE_BLOOM_FADE[1] < EDGE_BLOOM_SETTLED
    assert edge_bloom_appear(1.0) < edge_bloom_appear(0.2)     # strongest first


def test_detail_widens_the_contour_window():
    assert edge_bloom_thresholds(1.0)[0] < edge_bloom_thresholds(0.0)[0]


def test_jump_flood_steps_halve_down_to_one_then_refine():
    assert edge_field_jumps((768, 432)) == (512, 256, 128, 64, 32, 16, 8, 4, 2, 1, 1)


def _shapes(fill) -> Image.Image:
    image = Image.new("RGB", (W, H), fill)
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 30, 140, 120), fill=(240, 240, 240))
    draw.ellipse((190, 50, 290, 150), fill=(30, 30, 30))
    return image


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H, Image.new("RGB", (W, H), (120, 120, 120)), _shapes((90, 140, 200)))
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


def _read(texture: int, size: tuple[int, int], channels: int) -> np.ndarray:
    width, height = size
    data = (ctypes.c_float * (width * height * channels))()
    gl.glGetTextureImage(texture, 0, gl.GL_RED if channels == 1 else gl.GL_RG, gl.GL_FLOAT,
                         ctypes.sizeof(data), data)
    return np.frombuffer(data, dtype=np.float32).reshape(height, width, channels)


@pytest.mark.qt
def test_the_field_matches_its_cpu_mirror(capture):
    run = capture.run("edge_bloom", duration_ms=5000)
    capture.render(run, 0.3)
    field = capture.host._implementations["edge_bloom"]._new_field
    size = field._size
    low, high = edge_bloom_thresholds(float(run.request.parameter_dict()["detail"]))
    blurred = _read(field._textures["luma"], size, 1)[..., 0]       # holds the twice-blurred luma
    strength = _read(field._textures["edge"], size, 1)[..., 0]
    expected = edge_ridge_reference(blurred, low, high)
    seeds, expected_seeds = strength >= EDGE_FIELD_SEED, expected >= EDGE_FIELD_SEED
    assert seeds.sum() > 50
    assert (seeds != expected_seeds).mean() < 0.005
    distance = _read(field._textures["field"], size, 2)[..., 0]
    points = np.argwhere(seeds)
    ys, xs = np.mgrid[0:size[1], 0:size[0]]
    exact = np.sqrt(((ys[..., None] - points[:, 0]) ** 2 + (xs[..., None] - points[:, 1]) ** 2).min(-1)) / size[1]
    texel = 1.0 / size[1]
    assert np.abs(distance - exact).mean() < 0.25 * texel and np.abs(distance - exact).max() < 2.0 * texel


@pytest.mark.qt
def test_ends_are_exact(capture):
    run = capture.run("edge_bloom", duration_ms=5000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    assert np.array_equal(_pixels(capture.render(run, EDGE_BLOOM_SETTLED)[0]), destination)


def _near_and_far():
    """Masks of the frame near the new picture's shape outlines and well away from them."""
    outline = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(outline)
    draw.rectangle((40, 30, 140, 120), outline=255, width=3)
    draw.ellipse((190, 50, 290, 150), outline=255, width=3)
    near = np.asarray(outline) > 0
    far = np.ones((H, W), dtype=bool)
    far[10:140, 20:160] = False
    far[30:170, 170:310] = False
    return near, far


@pytest.mark.qt
def test_light_appears_on_the_new_contours_and_the_fill_starts_there(capture):
    near, far = _near_and_far()
    lit = capture.run("edge_bloom", settings={"edge_bloom": {"glow": 1.0}}, duration_ms=5000)
    dark = capture.run("edge_bloom", settings={"edge_bloom": {"glow": 0.0}}, duration_ms=5000)
    added = (_pixels(capture.render(lit, 0.27)[0]) - _pixels(capture.render(dark, 0.27)[0])).sum(-1)
    assert added.min() >= 0                        # Glow only ever adds light
    assert added[near].mean() > 3 * added[far].mean() + 20
    destination = _pixels(capture.images[1])
    frame = _pixels(capture.render(dark, 0.45)[0])
    error = np.abs(frame - destination).sum(-1)
    assert error[near].mean() < error[far].mean()


@pytest.mark.qt
@pytest.mark.parametrize(("source", "red_lines"), (("Custom", False), ("Next Picture", True)))
def test_next_picture_glows_in_the_next_pictures_colour(qt_app, source, red_lines):
    destination = Image.new("RGB", (W, H), (20, 20, 20))
    ImageDraw.Draw(destination).rectangle((60, 40, 260, 140), fill=(220, 30, 30))
    capture = TransitionCapture(W, H, Image.new("RGB", (W, H), (120, 120, 120)), destination)
    try:
        settings = {"edge_bloom": {"color_source": source, "color": [40, 120, 255, 255]}}
        lit = capture.run("edge_bloom", settings={"edge_bloom": {**settings["edge_bloom"], "glow": 1.0}},
                          duration_ms=5000)
        dark = capture.run("edge_bloom", settings={"edge_bloom": {**settings["edge_bloom"], "glow": 0.0}},
                           duration_ms=5000)
        added = _pixels(capture.render(lit, 0.27)[0]) - _pixels(capture.render(dark, 0.27)[0])
        light = added[added.sum(-1) > 60].mean(axis=0)
        assert (light[0] > light[2]) == red_lines
    finally:
        capture.close()


@pytest.mark.qt
def test_each_field_is_built_once_per_run_and_park_drops_it(capture):
    run = capture.run("edge_bloom", duration_ms=5000)
    parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
    steps = 0
    while not capture.host.warm_step("edge_bloom", parameters, size):
        steps += 1
        assert steps < 20
    renderer = capture.host._implementations["edge_bloom"]
    assert renderer._new_field.has_resources and renderer._old_field.has_resources
    allocated = dict(renderer._new_field._textures)
    for progress in (0.1, 0.3, 0.6):
        capture.render(run, progress)
    assert renderer._new_field.builds == 1 and renderer._old_field.builds == 1
    assert renderer._new_field._textures == allocated          # built into the warmed textures
    capture.host.park()
    assert not renderer._new_field.has_resources and not renderer._old_field.has_resources
    renderer.release_resources()
    assert not renderer.has_resources


def test_the_resolver_repairs_values():
    resolved = resolve_parameterized_phase_c_inputs(
        "edge_bloom", {"edge_bloom": {"glow": 3, "detail": -2, "color": "nope"}}, random_source=random.Random(1))
    parameters = resolved.parameter_dict()
    assert resolved.direction is None
    assert parameters["glow"] == 1.0 and parameters["detail"] == 0.0
    assert len(parameters["color"]) == 3 and all(0.0 <= c <= 1.0 for c in parameters["color"])
    assert parameters["color_source"] == "custom"
    for label, code in (("Next Picture", "next"), ("Each Picture", "each"), ("bogus", "custom")):
        resolved = resolve_parameterized_phase_c_inputs("edge_bloom", {"edge_bloom": {"color_source": label}},
                                                        random_source=random.Random(2))
        assert resolved.parameter_dict()["color_source"] == code
    assert isinstance(parameters["seed"], int)
