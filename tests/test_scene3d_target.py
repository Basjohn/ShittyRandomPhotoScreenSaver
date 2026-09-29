"""The shared scene target works for any item rect (a full-screen transition or a
Visualizer card): it reproduces a direct draw, reuses its allocation while the
rect fits, and always hands Quick back its framebuffer, viewport and scissor.

Offscreen GL through the transition capture harness; no window is shown.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.quick.scene3d.frame import item_pixel_rect
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.target import SceneTarget
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

WIDTH, HEIGHT = 256, 144


def _card_frame(capture, left: float, top: float, width: float, height: float):
    """An item placed at (left, top) in the window, as a Visualizer card is."""
    matrix = (2 / WIDTH, 0, 0, 0, 0, -2 / HEIGHT, 0, 0, 0, 0, 1, 0,
              2 * left / WIDTH - 1, 1 - 2 * top / HEIGHT, 0, 1)
    return SimpleNamespace(viewport=(0, 0, WIDTH, HEIGHT), logical_size=(width, height),
                           matrix_values=matrix, quad_vao=capture.vao)


def _read(capture) -> np.ndarray:
    pixels = gl.glReadPixels(0, 0, WIDTH, HEIGHT, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    return np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(HEIGHT, WIDTH, 4).astype(np.int16)


def _clear(capture) -> None:
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
    gl.glViewport(0, 0, WIDTH, HEIGHT)
    gl.glDisable(gl.GL_SCISSOR_TEST)
    gl.glClearColor(1.0, 0.0, 1.0, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT)


@pytest.fixture
def capture(qt_app):
    result = TransitionCapture(WIDTH, HEIGHT)
    yield result
    result.close()


def test_item_pixel_rect_follows_the_item_matrix(capture):
    full = _card_frame(capture, 0, 0, WIDTH, HEIGHT)
    assert item_pixel_rect(full) == (0, 0, WIDTH, HEIGHT)
    card = _card_frame(capture, 40, 20, 120, 80)
    # GL rows count up from the bottom: the card spans rows 44..124.
    assert item_pixel_rect(card) == (40, HEIGHT - 20 - 80, 120, 80)
    spill = _card_frame(capture, 200, -10, 120, 80)
    assert item_pixel_rect(spill) == (200, HEIGHT - 70, WIDTH - 200, 70)


@pytest.mark.parametrize("samples", (1, 4))
def test_a_card_drawn_through_the_target_matches_a_direct_draw(capture, samples):
    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        card = _card_frame(capture, 40, 20, 120, 80)
        texture = capture.textures[0]
        _clear(capture)
        resources.draw_image(card, texture)
        direct = _read(capture)

        _clear(capture)
        with target.scope(card, samples, resources):
            resources.draw_image(card, texture)
        through = _read(capture)
        assert np.array_equal(direct, through)
        assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) == capture.fbo
        assert tuple(int(v) for v in gl.glGetIntegerv(gl.GL_VIEWPORT)) == (0, 0, WIDTH, HEIGHT)
    finally:
        target.release()
        resources.release_resources()


def test_the_composite_respects_an_inherited_scissor(capture):
    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        card = _card_frame(capture, 0, 0, WIDTH, HEIGHT)
        _clear(capture)
        gl.glEnable(gl.GL_SCISSOR_TEST)
        gl.glScissor(10, 10, 100, 60)
        with target.scope(card, 4, resources):
            resources.draw_image(card, capture.textures[0])
        assert bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        assert tuple(int(v) for v in gl.glGetIntegerv(gl.GL_SCISSOR_BOX)) == (10, 10, 100, 60)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        pixels = _read(capture)
        magenta = np.array([255, 0, 255, 255])
        assert (pixels[5, 5] == magenta).all() and (pixels[100, 200] == magenta).all()
        assert not (pixels[40, 50] == magenta).all()
    finally:
        target.release()
        resources.release_resources()


def test_the_allocation_is_reused_while_the_rect_fits(capture):
    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        _clear(capture)
        with target.scope(_card_frame(capture, 0, 0, 100, 60), 4, resources):
            pass
        first, fbo = target.allocation, target._names["fbo"]
        assert first == (128, 64, 4)
        with target.scope(_card_frame(capture, 0, 0, 120, 64), 4, resources):
            pass
        assert target.allocation == first and target._names["fbo"] == fbo  # a resize drag inside the bucket
        with target.scope(_card_frame(capture, 0, 0, 130, 60), 4, resources):
            pass
        assert target.allocation == (192, 64, 4)
        target.release()
        assert not target.has_resources and target.allocation is None
    finally:
        target.release()
        resources.release_resources()


def test_a_failing_scene_hands_quick_back_its_state(capture):
    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        _clear(capture)
        gl.glEnable(gl.GL_SCISSOR_TEST)
        gl.glScissor(0, 0, WIDTH, HEIGHT)
        with pytest.raises(RuntimeError, match="mid-scene"):
            with target.scope(_card_frame(capture, 40, 20, 120, 80), 4, resources):
                assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) != capture.fbo
                raise RuntimeError("mid-scene failure")
        assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) == capture.fbo
        assert int(gl.glGetIntegerv(gl.GL_READ_FRAMEBUFFER_BINDING)) == capture.fbo
        assert tuple(int(v) for v in gl.glGetIntegerv(gl.GL_VIEWPORT)) == (0, 0, WIDTH, HEIGHT)
        assert bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
    finally:
        gl.glDisable(gl.GL_SCISSOR_TEST)
        target.release()
        resources.release_resources()


@pytest.mark.parametrize("samples,bloom", ((1, 0.0), (4, 0.0), (1, 1.0), (4, 1.0)))
def test_the_target_resolves_in_shaders_never_through_a_blit(capture, monkeypatch, samples, bloom):
    """A blit resolve of drawn content cost ~0.5 ms at 1440p (see the 3D foundation lessons)."""
    import rendering.quick.scene3d.target as target_module

    def blit(*_args):
        raise AssertionError("scene target resolved through glBlitFramebuffer")

    monkeypatch.setattr(target_module.gl, "glBlitFramebuffer", blit)
    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        card = _card_frame(capture, 40, 20, 120, 80)
        _clear(capture)
        resources.draw_image(card, capture.textures[0])
        direct = _read(capture)
        _clear(capture)
        with target.scope(card, samples, resources, bloom=bloom):
            resources.draw_image(card, capture.textures[0])
            # A photograph emits nothing: in a bloom target its alpha (emitted brightness) is 0.
            gl.glColorMask(gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE, gl.GL_TRUE)
            gl.glClearColor(0.0, 0.0, 0.0, 0.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glColorMask(gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE)
        # So even with bloom the card is the direct draw.
        assert np.abs(_read(capture) - direct).max() <= 1
    finally:
        target.release()
        resources.release_resources()

