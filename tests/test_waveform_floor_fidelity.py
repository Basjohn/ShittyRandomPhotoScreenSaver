"""Wet-floor material and reflection behaviour on the production floor program (WR-05 fidelity slice).

The floor pass is driven directly (``WaveformScene._floor``) with test-owned material values, the shipped textures
and a hand-filled reflection target, so each property is isolated from the atmosphere, ribbons and presets:
the concrete reads with reflection Off without changing its level, reflected light forms a vertical column
registered under its source, low light keeps a stronger column than high light, and the capped pre-pass matches.
"""
from dataclasses import replace
import numpy as np
import pytest
from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
from tests.test_waveform_ribbon_camera import camera

pytestmark = pytest.mark.qt

WIDTH, HEIGHT = 192, 128
SENTINEL = (1., 0., 1., 1.)


class FloorHarness:
    def __init__(self):
        from rendering.gl_error_policy import disable_per_call_gl_error_checking
        disable_per_call_gl_error_checking()
        from OpenGL import GL as gl
        from rendering.quick.offscreen_target import OffscreenRenderTarget
        from rendering.quick.scene3d.waveform import WaveformScene
        self.gl = gl
        self.target = OffscreenRenderTarget(WIDTH, HEIGHT)
        self.scene = WaveformScene()
        self.scene.admit_preparation()

    def render(self, floor, *, kind, source=None):
        """Floor pixels (float RGB) and the floor mask. ``source``: (x0, y0, x1, y1) uv rectangle, rgb, height."""
        from core.waveform_ribbon_scene import Recipe
        gl, scene = self.gl, self.scene
        scene.recipe, scene.size = Recipe(fog=None, floor=floor), (WIDTH, HEIGHT)
        view, projection, eye, lens = physical_view(camera(camera_projection=kind, tilt=.5), WIDTH/HEIGHT)
        mvp = tuple((projection @ view).flatten(order='F'))
        size = (WIDTH//2, HEIGHT//2)
        scene.reflection.begin(*size)
        if source is not None:
            (x0, y0, x1, y1), rgb, height = source
            luminance = float(np.dot(rgb, (0.2126, 0.7152, 0.0722)))
            gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glScissor(int(x0*size[0]), int(y0*size[1]), max(1, int((x1-x0)*size[0])), max(1, int((y1-y0)*size[1])))
            gl.glClearBufferfv(gl.GL_COLOR, 0, (*rgb, luminance*height))
            gl.glDisable(gl.GL_SCISSOR_TEST)
        scene.reflection.end()
        self.target.bind()
        gl.glViewport(0, 0, WIDTH, HEIGHT)
        gl.glClearBufferfv(gl.GL_COLOR, 0, SENTINEL)
        gl.glClearBufferfv(gl.GL_DEPTH, 0, (1.,))
        gl.glEnable(gl.GL_DEPTH_TEST); gl.glDepthFunc(gl.GL_LESS); gl.glDepthMask(gl.GL_TRUE)
        scene._floor(mvp, eye, view, lens[2], (WIDTH, HEIGHT))
        pixels = self.target.read_rgba()[:, :, :3].astype(float)
        floor_mask = ~((pixels[:, :, 0] > 250) & (pixels[:, :, 1] < 5) & (pixels[:, :, 2] > 250))
        return pixels, floor_mask

    def close(self):
        try:
            self.scene.release()
        finally:
            self.target.close()


@pytest.fixture
def harness(qt_app):
    probe = FloorHarness()
    try:
        yield probe
    finally:
        probe.close()


def material_only(**changes):
    """Diffuse material alone, lifted into the 8-bit range so its variation is measurable."""
    from core.waveform_ribbon_scene import Floor
    return replace(Floor(), reflection=0., ambient=(1., 1., 1.), albedo_gain=3., **changes)


def reflection_only(**changes):
    """Reflected light alone: no diffuse, full Fresnel, no column fade or relief breakup unless asked."""
    from core.waveform_ribbon_scene import Floor
    floor = Floor()
    values = dict(albedo_gain=0., f0=1., reflection=1., column=(1e6, 1., 0.), breakup=0., lod=(1., 1.),
                  streak=(.3, 1., 1.), hot=(1e-3, 0., floor.hot[2]))
    return replace(floor, **{**values, **changes})


@pytest.mark.parametrize('kind', ('Perspective', 'Orthographic'))
def test_concrete_reads_with_reflection_off_without_changing_its_level(harness, kind):
    textured, mask = harness.render(material_only(), kind=kind)
    assert mask.mean() > .2, 'the view must show a substantial floor area'
    plain, plain_mask = harness.render(material_only(contrast=1., shading=0.), kind=kind)
    flat, _ = harness.render(material_only(contrast=0., shading=0.), kind=kind)
    np.testing.assert_array_equal(mask, plain_mask)
    floor = textured[mask].mean(axis=1)
    # Finite everywhere: a NaN would read back as a black hole in the lit material.
    assert floor.min() > 0.
    # Legibility is restored relative to the raw albedo, and the flat control has (almost) none.
    spread = lambda image: float(np.std(image[mask].mean(axis=1)))
    assert spread(textured) > 2.*spread(plain) > 0.
    assert spread(flat) < .5*spread(plain)
    # Zero-mean variation: the floor keeps the level of its untextured control (never darkened).
    assert abs(floor.mean() - flat[mask].mean())/flat[mask].mean() < .1


@pytest.mark.parametrize('kind', ('Perspective', 'Orthographic'))
def test_reflected_light_forms_a_vertical_column_registered_under_its_source(harness, kind):
    source = ((.49, .15, .51, .19), (4., 2., .5), .2)
    pixels, mask = harness.render(reflection_only(), kind=kind, source=source)
    light = np.where(mask, pixels.sum(axis=2), 0.)
    assert light.max() > 30.
    rows, columns = np.nonzero(light > .25*light.max())
    height, width = np.ptp(rows) + 1, np.ptp(columns) + 1
    assert height > 3*width, (height, width)  # a long column, not a mirrored blob
    centre = float(np.average(np.arange(WIDTH), weights=light.sum(axis=0)))
    assert abs(centre - .5*WIDTH) < .05*WIDTH  # registered under the source
    hue = pixels[rows, columns]
    assert (hue[:, 0] > hue[:, 2]).mean() > .9  # the column keeps its source's colour


def test_low_reflected_light_keeps_a_stronger_column_than_high_light(harness):
    def peak(height):
        pixels, mask = harness.render(reflection_only(), kind='Perspective',
                                      source=((.45, .15, .55, .19), (1., 1., 1.), height))
        return float(np.where(mask, pixels.sum(axis=2), 0.).max())
    low, high = peak(.1), peak(30.)
    assert low > 1.5*high > 0.


def test_relief_breaks_the_column_without_dimming_its_mass(harness):
    source = ((.40, .15, .60, .19), (2., 2., 2.), .2)
    smooth, mask = harness.render(reflection_only(), kind='Perspective', source=source)
    broken, _ = harness.render(reflection_only(breakup=1.), kind='Perspective', source=source)
    lit = mask & (smooth.sum(axis=2) > .25*smooth.sum(axis=2).max())
    a, b = smooth[lit].sum(axis=1), broken[lit].sum(axis=1)
    assert np.std(b/np.maximum(a, 1.)) > .05  # visible breakup by the surface relief
    assert .6 < b.mean()/a.mean() < 1.4  # the reflected mass keeps its strength


@pytest.mark.parametrize('kind', ('Perspective', 'Orthographic'))
def test_capped_reflection_prepass_matches_the_inline_column(harness, kind):
    source = ((.40, .15, .60, .19), (2., 2., 2.), .2)
    inline, mask = harness.render(reflection_only(specular_max_height=10000), kind=kind, source=source)
    capped, _ = harness.render(reflection_only(specular_max_height=HEIGHT//2), kind=kind, source=source)
    a, b = inline[mask].mean(), capped[mask].mean()
    assert a > 1. and .8 < b/a < 1.2, (a, b)
