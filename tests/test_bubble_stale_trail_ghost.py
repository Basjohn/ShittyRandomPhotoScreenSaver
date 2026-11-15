"""A Bubble frame with no trail samples draws no ghost from an earlier frame's (N5.1 step 1e, R-225).

The simulation publishes no trail samples on a frame where no bubble's smear is active. The ghost pass reads the oldest
sample of each bubble's history whatever the wake does, so samples kept from an earlier frame drew a ghost ring frozen
at that frame's history for as long as the trails stayed inactive. Drawn on the production renderer: a frame with no
trails after one with trails must equal the same frame drawn first.
"""
from __future__ import annotations

import numpy as np
import pytest

from tests.test_qtquick_visualizer_bubble import _snapshot

SIZE = (420, 280)
# The bubble sits at (0.25, 0.5); its oldest sample lies well behind it, so its ghost ring is clear of the bubble.
TRAILS = (0.10, 0.30, 0.45,
          0.15, 0.36, 0.30,
          0.20, 0.42, 0.15)


@pytest.fixture
def host(qt_app):
    from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setVersion(4, 6)
    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        pytest.skip("OpenGL 4.6 context unavailable on this runner")
    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid() or not context.makeCurrent(surface):
        pytest.skip("offscreen OpenGL context unavailable")
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost

    hosts = []

    def make():
        hosts.append(QuickVisualizerRenderHost())
        return hosts[-1]

    try:
        yield make
    finally:
        for made in hosts:
            made.release_resources()
        context.doneCurrent()
        surface.destroy()


def _draw(host, snapshot):
    from OpenGL import GL as gl

    width, height = SIZE
    colour = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, colour)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
    fbo = gl.glGenFramebuffers(1)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, colour, 0)
    gl.glViewport(0, 0, width, height)
    gl.glClearColor(0.0, 0.0, 0.0, 0.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT)
    matrix = (2.0 / width, 0.0, 0.0, 0.0, 0.0, -2.0 / height, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 1.0, 0.0, 1.0)
    host.render(snapshot=snapshot, viewport=(0, 0, width, height), logical_size=(float(width), float(height)),
                matrix_values=matrix)
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    raw = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
    gl.glDeleteFramebuffers(1, [fbo])
    gl.glDeleteTextures([colour])
    raw = raw if isinstance(raw, (bytes, bytearray)) else np.asarray(raw).tobytes()
    return np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)


@pytest.mark.qt
def test_a_frame_without_trails_draws_no_ghost_kept_from_an_earlier_frame(host):
    with_trails, without = _snapshot(trails=TRAILS), _snapshot(trails=())
    fresh = _draw(host(), without)
    reused = host()
    drawn_with_trails = _draw(reused, with_trails)
    after = _draw(reused, without)
    # The trails' frame does draw a ghost and wake there (the comparison below can see a ring), ...
    assert np.abs(drawn_with_trails.astype(int) - fresh).max() > 8
    # ... and the frame without trails that follows it equals that frame drawn first: no frozen ring.
    assert np.array_equal(after, fresh), int((after != fresh).any(axis=2).sum())
