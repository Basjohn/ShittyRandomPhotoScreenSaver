"""Bubble's opt-in particle glow, measured on the production ambient pass in native GL.

One particle through ``QuickBubbleAmbientPoints.render_texture`` into its own offscreen target; the
coverage (8-bit) and light (float, linear) attachments are read back. Properties, not authored values:
a fixed core whatever the glow, light that falls monotonically from the core (no dark moat), light in
the particle's own hue, steady total light as the particle moves between pixel centres (no twinkle),
and no light target at all while nothing glows.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

SIZE = 64


@pytest.fixture
def ambient(qt_app):
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
    from rendering.quick.visualizer.implementations.bubble_ambient_gl import QuickBubbleAmbientPoints

    renderer = QuickBubbleAmbientPoints()
    try:
        yield renderer
    finally:
        renderer.release_resources()
        context.doneCurrent()
        surface.destroy()


def _draw(renderer, x, y, diameter, glow, colour=(0.55, 0.75, 1.0, 1.0)):
    """Render one particle at pixel position (x, y); return (coverage RGBA, light RGB or None)."""
    from OpenGL import GL as gl

    point = (x / SIZE, y / SIZE, diameter, 1.0, glow, 1.0)
    texture, light = renderer.render_texture(
        (0.0, 0.0, float(SIZE), float(SIZE)), 1.0, point, sprite_scale=1.0, glow_spread=1.0,
        micro_color=(1.0, 1.0, 1.0, 1.0), particle_color=colour)
    assert texture
    gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, renderer._fbo)
    gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)
    coverage = np.frombuffer(gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGBA, gl.GL_FLOAT),
                             dtype=np.float32).reshape(SIZE, SIZE, 4)[::-1].copy()
    radiance = None
    if light:
        gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT1)
        radiance = np.frombuffer(gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGB, gl.GL_FLOAT),
                                 dtype=np.float32).reshape(SIZE, SIZE, 3)[::-1].copy()
    gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, 0)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return coverage, radiance


def _linear_light(coverage, radiance):
    """Total light the particle adds over black: coverage colour (sRGB) decoded, plus emitted light."""
    rgb = coverage[..., :3]
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    luminance = linear @ np.array([0.2126, 0.7152, 0.0722])
    if radiance is not None:
        luminance = luminance + radiance @ np.array([0.2126, 0.7152, 0.0722])
    return luminance


@pytest.mark.qt
def test_nothing_glowing_allocates_no_light_target(ambient):
    _coverage, radiance = _draw(ambient, 32.5, 32.5, 2.4, 0.0)
    assert radiance is None and ambient._light_texture == 0
    _coverage, radiance = _draw(ambient, 32.5, 32.5, 2.4, 1.0)
    assert radiance is not None and ambient._light_texture
    _coverage, radiance = _draw(ambient, 32.5, 32.5, 2.4, 0.0)
    assert radiance is None and ambient._light_texture == 0


@pytest.mark.qt
def test_core_coverage_is_fixed_whatever_the_glow(ambient):
    for diameter in (0.9, 2.4, 7.0):
        reference, _ = _draw(ambient, 32.3, 31.7, diameter, 0.0)
        for glow in (0.2, 2.0, 6.0):
            coverage, radiance = _draw(ambient, 32.3, 31.7, diameter, glow)
            # Same pixels; the 8-bit target may round a filtered edge pixel differently (sprite size differs).
            assert np.abs(coverage - reference).max() <= 1.0 / 255.0 + 1e-6, (diameter, glow)
            assert np.array_equal(coverage[..., 3] > 0, reference[..., 3] > 0)
            assert radiance is not None and radiance.max() > 0.0


@pytest.mark.qt
def test_light_falls_monotonically_from_the_core_in_the_particle_hue(ambient):
    colour = (0.55, 0.75, 1.0, 1.0)
    coverage, radiance = _draw(ambient, 32.5, 32.5, 1.5, 2.0, colour)
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    distance = np.hypot(xx + 0.5 - 32.5, yy + 0.5 - 32.5)
    luminance = radiance @ np.array([0.2126, 0.7152, 0.0722])
    rings = [float(luminance[(distance >= r) & (distance < r + 1.0)].mean()) for r in range(0, 16)]
    # No dark moat: every ring is at most as bright as the one inside it, and the light reaches well past the core.
    assert all(outer <= inner * 1.0001 for inner, outer in zip(rings, rings[1:]))
    assert rings[6] > 0.0 and rings[0] > 20 * rings[6]
    # Coverage stays inside the core; light is what reaches the water around it.
    assert coverage[..., 3][distance > 4.0].max() == 0.0
    # The halo keeps the emitter's hue: same channel order as the colour, never washed toward grey.
    halo = radiance[(distance > 3.0) & (distance < 8.0)].mean(axis=0)
    assert halo[2] > halo[1] > halo[0] > 0.0
    lin = [((c + 0.055) / 1.055) ** 2.4 for c in colour[:3]]
    assert (halo[2] - halo[0]) / halo[2] >= (lin[2] - lin[0]) / lin[2]


@pytest.mark.qt
@pytest.mark.parametrize("diameter", (0.9, 1.5, 2.4, 4.0))
@pytest.mark.parametrize("glow", (0.0, 0.3, 2.0))
def test_total_light_is_steady_as_the_particle_moves_between_pixel_centres(ambient, diameter, glow):
    """Sixteen sub-pixel offsets: a particle drifting slowly must not twinkle (it used to vary by up to 136%)."""
    totals = []
    for k in range(16):
        x = 32.0 + (k % 4) / 4.0 + 0.125
        y = 31.0 + (k // 4) / 4.0 + 0.125
        coverage, radiance = _draw(ambient, x, y, diameter, glow)
        totals.append(float(_linear_light(coverage, radiance).sum()))
    mean = sum(totals) / len(totals)
    assert mean > 0.0
    spread = math.sqrt(sum((t - mean) ** 2 for t in totals) / len(totals)) / mean
    assert spread < 0.03, (diameter, glow, spread)
