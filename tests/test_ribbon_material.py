"""Native proof of the ribbon filament material through the Visualizer-shaped scene scope (offscreen)."""
from types import SimpleNamespace

import numpy as np
import pytest

from rendering.gl_error_policy import disable_per_call_gl_error_checking
disable_per_call_gl_error_checking()
from OpenGL import GL as gl
from core.ribbon_ring import RibbonRing
from core.settings.framed_camera import orthographic_matrix
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.ribbon import RibbonMaterial, RibbonPrimitive
from rendering.quick.scene3d.target import SceneTarget
from tools.labs.render_target import OffscreenRenderTarget

pytestmark = pytest.mark.qt
W, H = 200, 120
VIEW = tuple(np.identity(4).flatten(order='F'))  # eye at the origin looking down -z
MVP = orthographic_matrix((2.5, 1.5), .1, 100)


def strip(y, z, colour, *, width=.3, emission=1.):
    ring = RibbonRing(1, colours=[colour])
    for i in range(6):
        ring.append(i, [(i - 2.5, y, z)], width, 0., emission)
    return ring.packet()


@pytest.fixture
def scene(qt_app):
    target = OffscreenRenderTarget(W, H)
    parts = SimpleNamespace(target=target, primitive=RibbonPrimitive(), resources=MeshResources('material test'),
                            scene=SceneTarget('material test'))
    parts.card = SimpleNamespace(viewport=(0, 0, W, H), logical_size=(float(W), float(H)),
                                 matrix_values=(2/W, 0, 0, 0, 0, -2/H, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1), quad_vao=target.vao)
    yield parts
    with target.current():
        parts.primitive.release()
        parts.scene.release()
        parts.resources.release_resources()
    target.close()


def render(parts, packets, *, opaque=None, material=None):
    """Body through OIT, then additive light, as the Visualizer draws it; optional opaque strip first."""
    parts.target.bind(clear=(0., 0., 0., 0.))
    with parts.scene.scope(parts.card, 4, parts.resources, overlay=1.0, bloom=.4, oit=True, hdr=1.0):
        gl.glViewport(0, 0, W, H)
        gl.glClearBufferfv(gl.GL_COLOR, 0, (.01, .01, .02, 1.))
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDepthMask(gl.GL_TRUE)
        if opaque is not None:
            parts.primitive.draw(opaque, MVP)
        with parts.scene.transparent_writes(parts.card, parts.resources):
            for packet in packets:
                parts.primitive.draw(packet, MVP, shading='body', view=VIEW, material=material)
        with parts.scene.emission_writes():
            gl.glEnablei(gl.GL_BLEND, 0)
            gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
            gl.glDepthMask(gl.GL_FALSE)
            for packet in packets:
                parts.primitive.draw(packet, MVP, shading='light', view=VIEW, material=material)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDisablei(gl.GL_BLEND, 0)
    return parts.target.read_rgba().astype(int)


def test_crossing_ribbons_give_the_same_picture_in_either_order_and_brighten(scene):
    cyan = strip(0., -10., (.1, .7, 1., 1.))
    magenta = strip(.15, -12., (.9, .2, .9, 1.))
    forward, backward = render(scene, [cyan, magenta]), render(scene, [magenta, cyan])
    assert np.abs(forward - backward).max() <= 1
    alone = render(scene, [cyan])
    column = W//2
    # Where both sheets cover the pixel, light adds: brighter than either alone, and still finite colour.
    rows = np.where((forward[:, column, :3].sum(1) > 0))[0]
    assert rows.size and forward[:, column, :3].sum(1).max() > alone[:, column, :3].sum(1).max()


def test_opaque_geometry_in_front_hides_body_and_light(scene):
    glowing = strip(0., -12., (.1, .7, 1., 1.), emission=4.)
    wall = strip(0., -5., (0., 1., 0., 1.), width=.6)  # opaque diagnostic strip, nearer, writes depth
    covered, bare, behind = render(scene, [glowing], opaque=wall), render(scene, [], opaque=wall), render(scene, [glowing])
    centre = np.s_[H//2, W//2 - 20:W//2 + 20]
    assert behind[centre][:, 2].min() > 100  # the glowing strip is bright where the wall will be
    # Through the (tone-mapped) wall nothing of the strip behind shows: bloom spill may only touch its edges.
    assert np.abs(covered[centre] - bare[centre]).max() <= 2


def test_extreme_hdr_overlap_stays_finite(scene):
    hot = [strip(0., -10. - i*.2, (1., 1., 1., 1.), width=.5, emission=64.) for i in range(8)]
    pixels = render(scene, hot, material=RibbonMaterial(strand_light=8., rim_light=8., body_alpha=.9))
    centre = pixels[H//2 - 5:H//2 + 5, W//2 - 20:W//2 + 20]
    # NaN/inf accumulation resolves to black holes or garbage; saturated light must read as white.
    assert (centre[:, :, :3] >= 200).all()


def test_material_programs_compile_only_when_used_and_inputs_are_validated(scene):
    packet = strip(0., -10., (.1, .7, 1., 1.))
    scene.target.bind()
    scene.primitive.draw(packet, MVP)
    assert scene.primitive.resources.has_program('diagnostic')
    assert not scene.primitive.resources.has_program('body') and not scene.primitive.resources.has_program('light')
    with pytest.raises(ValueError, match='view matrix'):
        scene.primitive.draw(packet, MVP, shading='light')
    with pytest.raises(ValueError):
        scene.primitive.draw(packet, MVP, shading='glow', view=VIEW)
    for bad in (dict(strands=0), dict(body_alpha=1.), dict(rim_light=-1.), dict(strand_half_width=float('nan'))):
        with pytest.raises(ValueError):
            RibbonMaterial(**bad)



def test_edge_on_slivers_cannot_overflow_into_the_bloom(qt_app):
    # The probe's high scene folds sheets edge-on: MSAA shades sliver pixels at centres far outside the triangle.
    # Unclamped across-width inputs there overflowed exp() to infinity and the bloom spread solid colour blocks.
    from tools.labs import ribbon_material_probe as probe
    target = OffscreenRenderTarget(640, 709)
    primitive, resources, scene = RibbonPrimitive(), MeshResources('sliver test'), SceneTarget('sliver test')
    try:
        for state in probe.STATES:  # without the clamp the low scene showed 4862 garbage pixels, high none
            pixels, _ = probe.render(primitive, target, resources, scene, probe.card_frame(target, 640, 709),
                                     (640, 709), state, RibbonMaterial())
            rgb = pixels[:, :, :3].astype(int)
            garbage = (rgb.max(2) >= 250) & (np.sort(rgb, axis=2)[:, :, 1] < 20)  # a saturated pure primary/secondary
            assert rgb.max() > 200 and not garbage.any(), state
    finally:
        with target.current():
            primitive.release()
            scene.release()
            resources.release_resources()
        target.close()
