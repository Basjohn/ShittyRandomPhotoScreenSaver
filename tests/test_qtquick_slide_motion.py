"""Focused contracts for Slide's frozen bounded motion styles."""

from __future__ import annotations

import pytest

from rendering.quick.transitions.implementations.slide import (
    _slide_elastic_arrival,
    _slide_partition_sample,
)
from rendering.quick.transitions.request_resolution import resolve_quick_transition_spec


class _Settings:
    def __init__(self, motion_style: object) -> None:
        self._transitions = {
            "type": "Slide",
            "random_always": False,
            "slide": {"direction": "Left to Right", "motion_style": motion_style},
        }

    def get(self, key, default=None):
        if key == "transitions":
            return self._transitions
        return default


@pytest.mark.parametrize("style", ("Linear", "Elastic", "Wobble", "Flex"))
@pytest.mark.parametrize("direction", ("left", "right", "up", "down"))
def test_slide_motion_styles_have_exact_endpoints_and_one_owner(style, direction):
    horizontal = direction in {"left", "right"}
    for progress, expected_owner in ((0.0, "source"), (1.0, "destination")):
        for pixel in range(131):
            axis = (pixel + 0.5) / 131.0
            coordinate = (axis, 0.347) if horizontal else (0.347, axis)
            owner, uv = _slide_partition_sample(direction, progress, coordinate, style)
            assert owner == expected_owner
            assert uv == coordinate


@pytest.mark.parametrize("style", ("Linear", "Elastic", "Wobble", "Flex"))
@pytest.mark.parametrize("direction", ("left", "right", "up", "down"))
def test_slide_motion_styles_keep_dense_cardinal_partition_covered(style, direction):
    horizontal = direction in {"left", "right"}
    for progress in (index / 113.0 for index in range(114)):
        for pixel in range(131):
            axis = (pixel + 0.5) / 131.0
            coordinate = (axis, 0.619) if horizontal else (0.619, axis)
            owner, uv = _slide_partition_sample(direction, progress, coordinate, style)
            assert owner in {"source", "destination"}
            assert all(0.0 <= component <= 1.0 for component in uv)


def test_elastic_is_an_analytic_arrival_with_rebound_and_exact_completion():
    assert _slide_elastic_arrival(0.0) == 0.0
    assert _slide_elastic_arrival(1.0) == 1.0
    samples = [_slide_elastic_arrival(index / 1000.0) for index in range(1, 1000)]
    assert max(samples) > 1.0
    assert max(samples) <= 1.025
    # There is a true rebound after overshoot, rather than a merely eased ramp.
    peak = samples.index(max(samples))
    assert min(samples[peak + 1 :]) < 1.0


def test_elastic_overshoot_samples_the_departing_edge_without_wrapping():
    progress = next(index / 1000.0 for index in range(1, 1000) if _slide_elastic_arrival(index / 1000.0) > 1.0)
    amount = _slide_elastic_arrival(progress)
    owner, uv = _slide_partition_sample("left", progress, (0.2, 0.5), "Elastic")
    assert owner == "destination"
    assert uv[0] == pytest.approx(0.2 + (amount - 1.0))
    # Distinct interior output pixels retain distinct destination texels rather
    # than collapsing to the clamped departing edge.
    _, second_uv = _slide_partition_sample("left", progress, (0.7, 0.5), "Elastic")
    assert second_uv[0] == pytest.approx(0.7 + (amount - 1.0))
    assert second_uv[0] != uv[0]


@pytest.mark.parametrize("style", ("Linear", "Elastic", "Wobble", "Flex"))
def test_slide_resolution_freezes_the_single_style_choice(style):
    spec = resolve_quick_transition_spec(_Settings(style))
    assert spec is not None
    assert dict(spec.parameters) == {"motion_style": style}


@pytest.mark.parametrize("invalid", ("Perspective", "elastic", "", 3, None, []))
def test_slide_resolution_rejects_invalid_authored_motion_style(invalid):
    with pytest.raises(ValueError, match="unknown Slide motion style"):
        resolve_quick_transition_spec(_Settings(invalid))


@pytest.mark.qt
def test_real_gl_elastic_peak_keeps_varied_destination_interior_texels(qt_app):
    """A real fragment draw guards against an overshoot-wide edge smear."""

    from OpenGL import GL as gl
    from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat
    from rendering.quick.image_state import PresentationImage
    from rendering.quick.transitions.implementations.slide import QuickSlideRenderer
    from rendering.quick.transitions.render_contract import QuickTransitionRenderFrame
    from rendering.quick.transitions.state import TransitionRequest, TransitionRun, TransitionSample

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setVersion(4, 1)
    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        pytest.skip("OpenGL 4.1 context unavailable")
    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid() or not context.makeCurrent(surface):
        pytest.skip("offscreen OpenGL context unavailable")

    width = 8
    destination = bytes(channel for index in range(width) for channel in (20 + index * 25, 40 + index * 15, 80 + index * 9, 255))
    source = bytes((3, 4, 5, 255)) * width
    vao = vbo = old_tex = new_tex = color_tex = framebuffer = 0
    renderer = QuickSlideRenderer()
    try:
        def texture(data):
            texture_id = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, 1, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, data)
            return texture_id

        old_tex, new_tex = texture(source), texture(destination)
        vao = gl.glGenVertexArrays(1)
        vbo = gl.glGenBuffers(1)
        gl.glBindVertexArray(vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        import array
        vertices = array.array("f", (0, 0, 1, 0, 0, 1, 1, 1))
        gl.glBufferData(gl.GL_ARRAY_BUFFER, len(vertices) * 4, vertices.tobytes(), gl.GL_STATIC_DRAW)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, None)
        color_tex = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, color_tex)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, 1, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
        framebuffer = gl.glGenFramebuffers(1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, framebuffer)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, color_tex, 0)
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
        gl.glViewport(0, 0, width, 1)
        peak = max((index / 100000 for index in range(78000, 100000)), key=_slide_elastic_arrival)
        image = PresentationImage("gl", "synthetic", (1, 1), 1, (1, 1), 4, b"\0\0\0\xff")
        request = TransitionRequest(1, "slide", "Slide", False, 1000, "left", (("motion_style", "Elastic"),), image, image)
        run = TransitionRun.start(run_id=1, request=request, start_ns=0)
        sample = TransitionSample(1, 1, peak, peak, False)
        matrix = (2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 1, 0, -1, -1, 0, 1)
        renderer.render(QuickTransitionRenderFrame(run, sample, (0, 0, width, 1), (1.0, 1.0), matrix, vao, old_tex, new_tex))
        pixels = bytes(gl.glReadPixels(0, 0, width, 1, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE))
        observed = [tuple(pixels[index * 4 : index * 4 + 4]) for index in range(width)]
        overshoot = _slide_elastic_arrival(peak) - 1.0
        expected = []
        for index in range(width):
            texel = min(width - 1, int(min(1.0, (index + 0.5) / width + overshoot) * width))
            expected.append(tuple(destination[texel * 4 : texel * 4 + 4]))
        assert observed == expected
        assert len(set(observed[:-1])) > 1
    finally:
        renderer.release_resources()
        if framebuffer: gl.glDeleteFramebuffers(1, [framebuffer])
        if color_tex: gl.glDeleteTextures([color_tex])
        if old_tex: gl.glDeleteTextures([old_tex])
        if new_tex: gl.glDeleteTextures([new_tex])
        if vbo: gl.glDeleteBuffers(1, [vbo])
        if vao: gl.glDeleteVertexArrays(1, [vao])
        context.doneCurrent()
        surface.destroy()
