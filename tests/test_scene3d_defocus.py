"""The defocus layer spreads each pixel over its own circle of confusion, keeps the light it carries, leaves sharp
pixels sharp and hands back the caller's state. Offscreen GL through the transition capture harness; no window."""
from __future__ import annotations

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.quick.render.gl_resources import compile_program
from rendering.quick.scene3d.defocus import SCENE_DEFOCUS_GLSL, DefocusLayer
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

SIZE = 64
_POINTS_VERTEX = """#version 460 core
uniform vec2 uAt[2];
void main() {
    gl_PointSize = 1.0;
    gl_Position = vec4((uAt[gl_VertexID] + 0.5) / 64.0 * 2.0 - 1.0, 0.0, 1.0);
}
"""
_POINTS_FRAGMENT = "#version 460 core\n" + SCENE_DEFOCUS_GLSL + """
uniform float uCircle[2];
flat in int vId;
void main() {
    // Point 0: bright, far out of focus; point 1: dim and sharp.
    int id = gl_PrimitiveID;
    if (id == 0) sceneDefocusWrite(vec3(40.0), 1.0, uCircle[0]);
    else sceneDefocusWrite(vec3(0.5), 1.0, uCircle[1]);
}
"""


@pytest.fixture
def capture(qt_app):
    result = TransitionCapture(SIZE, SIZE)
    yield result
    result.close()


def _float_target():
    texture = int(np.asarray(gl.glGenTextures(1)).ravel()[0])
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
    gl.glTexStorage2D(gl.GL_TEXTURE_2D, 1, gl.GL_RGBA32F, SIZE, SIZE)
    fbo = int(np.asarray(gl.glGenFramebuffers(1)).ravel()[0])
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
    return texture, fbo


def test_a_point_spreads_over_its_circle_keeping_its_light_and_sharp_pixels_stay(capture):
    layer = DefocusLayer("defocus test")
    texture, fbo = _float_target()
    program = compile_program(_POINTS_VERTEX, _POINTS_FRAGMENT.replace("flat in int vId;\n", ""), label="defocus pts")
    try:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glViewport(0, 0, SIZE, SIZE)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        layer.begin(SIZE, SIZE)
        gl.glUseProgram(program)
        gl.glUniform2fv(gl.glGetUniformLocation(program, "uAt"), 2, [20.0, 30.0, 50.0, 10.0])
        gl.glUniform1fv(gl.glGetUniformLocation(program, "uCircle"), 2, [8.0, 0.0])
        gl.glBindVertexArray(capture.vao)
        gl.glDrawArrays(gl.GL_POINTS, 0, 2)
        layer.end()
        # The caller's framebuffer, viewport and blend come back.
        assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) == fbo
        assert [int(v) for v in gl.glGetIntegerv(gl.GL_VIEWPORT)] == [0, 0, SIZE, SIZE]
        assert gl.glIsEnabled(gl.GL_BLEND)
        layer.composite(12.0)
        pixels = np.frombuffer(bytes(gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGBA, gl.GL_FLOAT)),
                               dtype=np.float32).reshape(SIZE, SIZE, 4)
        assert gl.glIsEnabled(gl.GL_BLEND)
        # The sharp point is exactly where it was.
        assert pixels[10, 50, 0] == pytest.approx(0.5, abs=1e-3)
        assert pixels[10, 51, 0] == pytest.approx(0.0, abs=1e-3)
        # The bright point became an even disc of radius ~8 holding (about) its light.
        disc = pixels[:, :, 0].copy()
        disc[10, 50] = 0.0
        assert disc.sum() == pytest.approx(40.0, rel=0.15)
        lit = disc > 40.0 / (np.pi * 64.0) * 0.3
        ys, xs = np.nonzero(lit)
        radius = np.sqrt((xs - 20) ** 2 + (ys - 30) ** 2).max()
        assert 6.0 <= radius <= 10.0           # the circle, its edge softened by the read level's texel
        assert disc[30, 20] > 0.0 and disc[30, 24] > 0.0          # filled, not a ring
        assert disc[30, 32] == pytest.approx(0.0, abs=1e-6)        # nothing past the circle
    finally:
        gl.glDisable(gl.GL_BLEND)
        layer.release()
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures(1, [texture])
    assert not layer.has_resources()


def _bright_point_disc(capture, circle, max_radius, highlight, masked=False):
    layer = DefocusLayer("defocus disc test")
    texture, fbo = _float_target()
    program = compile_program(_POINTS_VERTEX, _POINTS_FRAGMENT.replace("flat in int vId;\n", ""), label="defocus pts")
    try:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glViewport(0, 0, SIZE, SIZE)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        if masked:      # as a scene target leaves its emission index outside emission_writes()
            gl.glColorMaski(1, gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE)
        layer.begin(SIZE, SIZE)
        gl.glUseProgram(program)
        gl.glUniform2fv(gl.glGetUniformLocation(program, "uAt"), 2, [32.0, 32.0, 32.0, 32.0])
        gl.glUniform1fv(gl.glGetUniformLocation(program, "uCircle"), 2, [circle, circle])
        gl.glBindVertexArray(capture.vao)
        gl.glDrawArrays(gl.GL_POINTS, 0, 1)
        layer.end()
        if masked:
            assert [bool(v) for v in gl.glGetBooleani_v(gl.GL_COLOR_WRITEMASK, 1)] == [False] * 4   # handed back
        layer.composite(max_radius, highlight)
        return np.frombuffer(bytes(gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGBA, gl.GL_FLOAT)),
                             dtype=np.float32).reshape(SIZE, SIZE, 4)[:, :, 0].copy()
    finally:
        gl.glColorMaski(1, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE)
        layer.release()
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures(1, [texture])


def _evenness(disc, radius):
    ys, xs = np.mgrid[0:SIZE, 0:SIZE]
    d = np.hypot(xs - 32, ys - 32)
    inner = disc[d < radius * 0.5]
    return inner.std() / inner.mean(), d


def test_a_highlight_under_a_wide_circle_is_one_even_round_disc(capture):
    # A bright point far out of focus: the fixed taps of the gather read it at a coarse level and catch it unevenly
    # (a striped, lumpy blob); highlights are drawn as one disc of their own circle instead.
    disc = _bright_point_disc(capture, 20.0, 24.0, 0.25)
    spread, d = _evenness(disc, 20.0)
    assert spread < 0.1                                           # even inside
    assert disc.sum() == pytest.approx(40.0, rel=0.1)             # its light kept
    # Its edge ends at the circle: the disc sits on its texel of the read level (up to ~2.8 px off at level 2); past
    # that only the faint gathered remainder (the light below the highlight limit, read bilinearly) and nothing at
    # all a texel further out.
    assert disc[d > 23.5].max() < 0.1 * disc[d < 10.0].mean()
    assert disc[d > 28.0].max() == pytest.approx(0.0, abs=1e-6)
    assert disc[(d > 17.0) & (d < 19.0)].mean() > 0.8 * disc[d < 10.0].mean()   # round to its edge, not a falling blob
    # The gather alone (threshold out of reach) is the uneven case this guards.
    gathered, _ = _evenness(_bright_point_disc(capture, 20.0, 24.0, 1e9), 20.0)
    assert gathered > spread * 2.0


def test_a_callers_masked_draw_buffer_does_not_stop_the_layer_spreading(capture):
    """Colour masks belong to draw buffer indices, not framebuffers: drawn while a scene target masks its emission
    index (outside emission_writes()), the layer still records each pixel's circle and spreads it, then hands the
    mask back (Extruded Bubble's near giants came out sharp before)."""
    plain = _bright_point_disc(capture, 20.0, 24.0, 0.25)
    masked = _bright_point_disc(capture, 20.0, 24.0, 0.25, masked=True)
    assert np.abs(masked - plain).max() <= 1e-4 * max(1.0, plain.max())
    _spread, d = _evenness(masked, 20.0)
    assert masked[(d > 12.0) & (d < 16.0)].mean() > 0.0          # a disc, not the sharp point
