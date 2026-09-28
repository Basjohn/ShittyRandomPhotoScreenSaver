"""The shared camera: at rest the photograph fills the view exactly; when it moves,
the overscan zoom keeps every frame edge covered (R-63: black = 0); shake is
deterministic and bounded. GL cases draw offscreen; no window is shown.
"""
from __future__ import annotations

import math
import random
from types import SimpleNamespace

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs import scene3d as lib
from rendering.quick.scene3d.resources import MeshResources
from tools.transition_contact_sheet import TransitionCapture

WIDTH, HEIGHT = 320, 180


def _covered(distance, offset, tilt, aspect, zoom) -> bool:
    a, b = (distance, zoom, *offset), (*tilt, 0.0, 0.0)
    half = aspect / 2
    quad = [lib.scene3d_camera_uv((x, y, 0.0), aspect, a, b) for x, y in ((-half, .5), (half, .5), (half, -.5), (-half, -.5))]
    return all(lib._inside_convex(corner, quad) for corner in ((0, 0), (1, 0), (1, 1), (0, 1)))


def test_overscan_is_the_least_zoom_that_covers_the_view():
    rng = random.Random(3)
    assert lib.scene3d_camera_overscan(3.4, (0.0, 0.0), (0.0, 0.0), 16 / 9) == 1.0
    for _ in range(300):
        aspect = rng.choice((16 / 9, 4 / 3, 9 / 16, 21 / 9))
        offset = (rng.uniform(-0.04, 0.04), rng.uniform(-0.04, 0.04))
        tilt = (rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08))
        distance = rng.uniform(2.5, 4.0)
        zoom = lib.scene3d_camera_overscan(distance, offset, tilt, aspect)
        assert zoom >= 1.0 and _covered(distance, offset, tilt, aspect, zoom)
        if zoom > 1.01:
            assert not _covered(distance, offset, tilt, aspect, 1.0 + (zoom - 1.0) * 0.9)


def test_shake_is_deterministic_bounded_and_real_time():
    first = [lib.scene3d_camera_shake(t / 60.0, 0.01, 713) for t in range(600)]
    assert first == [lib.scene3d_camera_shake(t / 60.0, 0.01, 713) for t in range(600)]
    assert first != [lib.scene3d_camera_shake(t / 60.0, 0.01, 714) for t in range(600)]
    assert max(max(abs(x), abs(y)) for x, y in first) <= 0.01
    assert lib.scene3d_camera_shake(2.0, 0.0, 713) == (0.0, 0.0)
    # 3-7 Hz: a 60 fps frame moves it by a fraction of its span, never a jump.
    steps = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(first, first[1:])]
    assert max(steps) < 0.01 * 0.8


@pytest.fixture
def capture(qt_app):
    result = TransitionCapture(WIDTH, HEIGHT)
    yield result
    result.close()


def _frame(capture):
    return SimpleNamespace(viewport=(0, 0, WIDTH, HEIGHT), logical_size=(float(WIDTH), float(HEIGHT)),
                           matrix_values=(2 / WIDTH, 0, 0, 0, 0, -2 / HEIGHT, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                           quad_vao=capture.vao)


def _draw(capture, draw) -> np.ndarray:
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
    gl.glViewport(0, 0, WIDTH, HEIGHT)
    gl.glDisable(gl.GL_SCISSOR_TEST)
    gl.glClearColor(1.0, 0.0, 1.0, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT)
    draw()
    pixels = gl.glReadPixels(0, 0, WIDTH, HEIGHT, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    return np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(HEIGHT, WIDTH, 4).astype(np.int16)


def _exposed(pixels: np.ndarray) -> int:
    return int(np.count_nonzero((pixels[..., 0] == 255) & (pixels[..., 1] == 0) & (pixels[..., 2] == 255)))


@pytest.mark.qt
def test_the_camera_plane_at_rest_is_the_photograph(capture):
    resources = MeshResources("camera test")
    try:
        frame, texture = _frame(capture), capture.textures[0]
        flat = _draw(capture, lambda: resources.draw_image(frame, texture))
        plane = _draw(capture, lambda: resources.draw_camera_plane(frame, texture, (3.4, 1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0)))
        assert np.abs(flat - plane).max() <= 1
    finally:
        resources.release_resources()


@pytest.mark.qt
def test_a_moving_camera_never_exposes_the_frame_edges(capture):
    resources = MeshResources("camera test")
    rng = random.Random(9)
    aspect = WIDTH / HEIGHT
    try:
        frame, texture = _frame(capture), capture.textures[0]
        for _ in range(12):
            offset = (rng.uniform(-0.04, 0.04), rng.uniform(-0.04, 0.04))
            tilt = (rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08))
            zoom = lib.scene3d_camera_overscan(3.4, offset, tilt, aspect)
            a, b = (3.4, zoom, *offset), (*tilt, 0.0, 0.0)
            assert _exposed(_draw(capture, lambda: resources.draw_camera_plane(frame, texture, a, b))) == 0
            # Negative control: the same motion without the overscan shows uncovered pixels.
            if zoom > 1.01:
                unzoomed = (3.4, 1.0, *offset)
                assert _exposed(_draw(capture, lambda: resources.draw_camera_plane(frame, texture, unzoomed, b))) > 0
    finally:
        resources.release_resources()
