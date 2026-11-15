"""Accuracy of decorative bubble masking, without extra full-screen work."""
from types import SimpleNamespace

import numpy as np
import pytest

from widgets.spotify_visualizer.bubble_ambient_geometry import select_ambient_occluders


def test_occlusion_uses_all_visible_bubbles_with_the_exact_rendered_radii():
    bubbles = [SimpleNamespace(is_big=False), SimpleNamespace(is_big=True),
               SimpleNamespace(is_big=True), SimpleNamespace(is_big=False)]
    positions = (0.1, 0.2, 0.009, 1.0,
                 0.3, 0.4, 0.084, 1.0,
                 0.5, 0.6, 0.075, 0.0,
                 0.7, 0.8, 0.008, 1.0)
    assert select_ambient_occluders(bubbles, positions) == (
        0.1, 0.2, 0.009, 1.0,
        0.3, 0.4, 0.084, 1.0,
        0.7, 0.8, 0.008, 1.0,
    )


def test_empty_ambient_mask_and_invalid_contracts():
    assert select_ambient_occluders((), ()) == ()
    with pytest.raises(ValueError):
        select_ambient_occluders([SimpleNamespace(is_big=True)], ())


def test_immutable_bubble_frame_requires_complete_bounded_occlusion_records():
    from widgets.spotify_visualizer.render_state import BubbleFrame
    points = (0.5, 0.5, 3.0, 0.7, 1.0, 1.0)
    frame = BubbleFrame(ambient_points=points,
                        ambient_occluders=(0.45, 0.6, 0.07, 0.9))
    assert frame.ambient_occluders == (0.45, 0.6, 0.07, 0.9)
    with pytest.raises(ValueError):
        BubbleFrame(ambient_occluders=(0.45, 0.6, 0.07, 0.9))
    with pytest.raises(ValueError):
        BubbleFrame(ambient_points=points, ambient_occluders=(0.4, 0.6))
    with pytest.raises(ValueError):
        BubbleFrame(ambient_points=points, ambient_occluders=(0.4, 0.6, float("nan"), 0.7))


# ------------------------------------------------------------------------------------------- the mask on the GPU

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


def _erased(renderer, width, height, occluders, scale):
    """The ambient target filled opaque, then only the hero mask drawn over it: the erased alpha (rows top first)."""
    from OpenGL import GL as gl

    invisible = (0.5, 0.5, 1.0, 0.0, 0.0, 0.0)
    renderer.render_texture((0.0, 0.0, float(width), float(height)), 1.0, invisible, sprite_scale=1.0,
                            micro_color=(1.0, 1.0, 1.0, 1.0), particle_color=(1.0, 1.0, 1.0, 1.0))
    assert renderer.target_size == (width, height)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, renderer._fbo)
    gl.glViewport(0, 0, width, height)
    gl.glClearColor(1.0, 1.0, 1.0, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT)
    gl.glEnable(gl.GL_BLEND)
    renderer._draw_occluders(tuple(occluders), width, height, scale)
    gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    raw = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
    gl.glDisable(gl.GL_BLEND)
    assert gl.glGetError() == gl.GL_NO_ERROR
    pixels = np.frombuffer(raw if isinstance(raw, (bytes, bytearray)) else np.asarray(raw).tobytes(),
                           dtype=np.uint8).reshape(height, width, 4)[::-1]
    return 255 - pixels[..., 3].astype(np.int32)


@pytest.mark.qt
@pytest.mark.parametrize('width,height,scale', [
    (420, 280, 1.0), (420, 280, 1.6), (1600, 250, 0.7), (250, 1600, 1.3),
])
def test_masks_remain_physical_circles_with_correct_response_scaling(ambient, width, height, scale):
    """Each hero circle erases a round disc in texels whatever the target's aspect, of radius r x the response scale
    x the target height, at its alpha; a circle of radius or alpha 0 erases nothing."""
    x, y, r, alpha = 0.4, 0.6, 0.045, 0.75
    erased = _erased(ambient, width, height, (x, y, r, alpha, 0.2, 0.2, 0.0, 1.0, 0.8, 0.2, 0.05, 0.0), scale)
    radius = r * scale * height
    rows, cols = np.nonzero(erased > 0)
    assert rows.size
    # one disc: centred where the circle is, as wide as it is tall, of the projected radius (within the edge's AA)
    assert (cols.max() - cols.min() + 1) == pytest.approx(rows.max() - rows.min() + 1, abs=2)
    assert (rows.max() - rows.min() + 1) == pytest.approx(2 * radius, abs=3)
    assert (cols.min() + cols.max() + 1) / 2 == pytest.approx(x * width, abs=1)
    assert (rows.min() + rows.max() + 1) / 2 == pytest.approx(y * height, abs=1)
    # round, not square: the disc's corners keep their coverage
    assert erased[int(y * height), int(x * width)] == pytest.approx(round(255 * alpha), abs=1)
    corner = (int(y * height - radius * 0.9), int(x * width - radius * 0.9))
    assert erased[corner] == 0
