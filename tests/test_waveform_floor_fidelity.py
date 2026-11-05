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

    def render(self, floor, *, source=None, **view_changes):
        """Floor pixels (float RGB) and the floor mask. ``source``: (x0, y0, x1, y1) uv rectangle, rgb, height."""
        from core.waveform_ribbon_scene import Recipe
        gl, scene = self.gl, self.scene
        scene.recipe, scene.size = Recipe(fog=None, floor=floor), (WIDTH, HEIGHT)
        view, projection, eye, lens = physical_view(camera(**{'tilt': .5, **view_changes}), WIDTH/HEIGHT)
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
        gl.glDepthMask(gl.GL_TRUE)  # clears honour the write mask; set it before clearing depth
        gl.glClearBufferfv(gl.GL_COLOR, 0, SENTINEL)
        gl.glClearBufferfv(gl.GL_DEPTH, 0, (1.,))
        gl.glEnable(gl.GL_DEPTH_TEST); gl.glDepthFunc(gl.GL_LESS)
        scene._floor(mvp, eye, view, (WIDTH, HEIGHT))
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


def test_concrete_reads_with_reflection_off_without_changing_its_level(harness):
    textured, mask = harness.render(material_only())
    assert mask.mean() > .2, 'the view must show a substantial floor area'
    plain, plain_mask = harness.render(material_only(contrast=1., shading=0.))
    flat, _ = harness.render(material_only(contrast=0., shading=0.))
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


def test_reflected_light_forms_a_vertical_column_registered_under_its_source(harness):
    source = ((.49, .15, .51, .19), (4., 2., .5), .2)
    pixels, mask = harness.render(reflection_only(), source=source)
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
        pixels, mask = harness.render(reflection_only(),
                                      source=((.45, .15, .55, .19), (1., 1., 1.), height))
        return float(np.where(mask, pixels.sum(axis=2), 0.).max())
    low, high = peak(.1), peak(30.)
    assert low > 1.5*high > 0.


def test_relief_breaks_the_column_without_dimming_its_mass(harness):
    source = ((.40, .15, .60, .19), (2., 2., 2.), .2)
    smooth, mask = harness.render(reflection_only(), source=source)
    broken, _ = harness.render(reflection_only(breakup=1.), source=source)
    lit = mask & (smooth.sum(axis=2) > .25*smooth.sum(axis=2).max())
    a, b = smooth[lit].sum(axis=1), broken[lit].sum(axis=1)
    assert np.std(b/np.maximum(a, 1.)) > .05  # visible breakup by the surface relief
    assert .6 < b.mean()/a.mean() < 1.4  # the reflected mass keeps its strength


def test_capped_reflection_prepass_matches_the_inline_column(harness):
    source = ((.40, .15, .60, .19), (2., 2., 2.), .2)
    inline, mask = harness.render(reflection_only(specular_max_height=10000), source=source)
    capped, _ = harness.render(reflection_only(specular_max_height=HEIGHT//2), source=source)
    a, b = inline[mask].mean(), capped[mask].mean()
    assert a > 1. and .8 < b/a < 1.2, (a, b)


def test_reflected_light_is_bounded_smoothly_without_changing_restrained_light(harness):
    """Strong reflected light compresses toward the ceiling (bounded, monotone, hue kept); restrained light below
    it keeps nearly its linear level."""
    def column(rgb, limit):
        pixels, mask = harness.render(reflection_only(glow_limit=limit),
                                      source=((.45, .15, .55, .19), rgb, .2))
        return pixels[mask]
    unbounded = lambda rgb: column(rgb, 1e4)
    # Restrained: within 10% of the unbounded column
    weak, weak_free = column((.2, .08, .3), 5.), unbounded((.2, .08, .3))
    assert weak_free.max() > 20.
    assert abs(weak.mean() - weak_free.mean())/weak_free.mean() < .1
    # Strong: the column is held well below its unbounded level, but brighter sources still read brighter
    strong, strong_free = column((9., 3., .5), .1), unbounded((9., 3., .5))
    stronger = column((18., 6., 1.), .1)
    assert strong.mean() < .6*strong_free.mean()
    assert stronger.mean() >= strong.mean() - 1.
    # and keeps its hue (orange: red over green over blue)
    bright = strong[strong.sum(axis=1) > np.percentile(strong.sum(axis=1), 90)].mean(axis=0)
    assert bright[0] > bright[1] > bright[2]


def test_surface_light_falls_off_toward_the_camera_into_darkness(harness):
    """The concrete is lit near the sheets and darker toward the camera (dark wet ground in a wide view), smoothly
    and to its far level, never black."""
    reach, _ = harness.render(replace(material_only(light_reach=5., light_far=.4), albedo_gain=1.),
                         camera_fov=20.)
    even, mask = harness.render(replace(material_only(light_reach=1e6, light_far=1.), albedo_gain=1.),
                              camera_fov=20.)
    rows = [r for r in range(HEIGHT) if mask[r].mean() > .9]
    near, far = rows[-max(4, len(rows)//6):], rows[:max(4, len(rows)//6)]  # bottom rows are nearest the camera
    ratio = lambda band: reach[band][mask[band]].mean()/even[band][mask[band]].mean()
    assert ratio(near) < .8*ratio(far)
    assert reach[mask].min() > 0. and ratio(near) > .3


def _flicker(frames, mask):
    """Back-and-forth change of each floor pixel over consecutive frames (consecutive deltas of opposite sign,
    the smaller magnitude), relative to the floor's mean light. Monotone change (a column brightening as its
    source arrives, fading as it leaves) scores zero; a pixel that pops up and down between frames scores."""
    light = np.stack([np.where(mask, frame.sum(axis=2), 0.) for frame in frames])
    a, b = light[1:-1] - light[:-2], light[2:] - light[1:-1]
    alternation = np.where(a*b < 0, np.minimum(np.abs(a), np.abs(b)), 0.)
    return float(alternation[:, mask].mean()/max(light[:, mask].mean(), 1e-6))


def test_a_slowly_moving_source_changes_the_floor_smoothly_without_flicker(harness):
    """A thin sheet drifting one reflection texel per frame through the column's taps: the floor follows it as
    smooth coloured mass. Sparse or winner-take-all taps made the column pop as the sheet crossed between them."""
    from core.waveform_ribbon_scene import Floor
    floor = replace(Floor(), albedo_gain=0., f0=1., reflection=1., column=(1e6, 1., 0.))
    texel = 1./(HEIGHT//2)
    frames = []
    for step in range(12):
        y = .12 + step*texel
        sx = .40 + step*texel*.5  # and drifting sideways, slower
        frames.append(harness.render(floor,
                                     source=((sx, y, sx+.12, y+texel), (1., 3., 2.5), .2))[0])
    mask = harness.render(floor)[1]
    lit = np.stack([frame.sum(axis=2) for frame in frames])[:, mask]
    assert lit.max() > 30., 'the moving sheet must light the floor'
    assert _flicker(frames, mask) < .0095  # the previous sparse, steep, narrow column scored .012


def test_columns_carry_their_sources_saturated_hue_through_a_grey_haze(harness):
    """Teal and orange sheets side by side, inside a broad grey reflected haze (the mirrored mist): each column
    keeps its own sheet's hue and saturation as coloured mass, never the haze's grey or a pastel mix."""
    import colorsys
    from core.waveform_ribbon_scene import Floor
    floor = replace(Floor(), albedo_gain=0., f0=1., reflection=1., column=(1e6, 1., 0.), breakup=0.)
    teal, orange = (.15, 1.6, 1.3), (2.2, .8, .12)
    gl, scene = harness.gl, harness.scene
    size = (WIDTH//2, HEIGHT//2)
    original_end = scene.reflection.end
    def with_sources():
        # grey haze everywhere, then the two sheets, before the target is finalised (mips)
        gl.glEnable(gl.GL_SCISSOR_TEST)
        for (x0, x1), rgb in (((.20, .34), teal), ((.66, .80), orange)):
            gl.glScissor(int(x0*size[0]), int(.14*size[1]), int((x1-x0)*size[0]), max(1, int(.05*size[1])))
            gl.glClearBufferfv(gl.GL_COLOR, 0, (*rgb, float(np.dot(rgb, (.2126, .7152, .0722)))*.2))
        gl.glDisable(gl.GL_SCISSOR_TEST)
        original_end()
    scene.reflection.end = with_sources
    try:
        pixels, mask = harness.render(floor, source=((0., 0., 1., 1.), (.25, .25, .25), 1.))
    finally:
        scene.reflection.end = original_end
    for (x0, x1), rgb in (((.20, .34), teal), ((.66, .80), orange)):
        band = pixels[:, int(x0*WIDTH):int(x1*WIDTH)][mask[:, int(x0*WIDTH):int(x1*WIDTH)]]
        bright = band[band.sum(axis=1) > np.percentile(band.sum(axis=1), 75)]
        mean = bright.mean(axis=0)/255.
        hue, saturation, _ = colorsys.rgb_to_hsv(*mean)
        source_hue, source_saturation, _ = colorsys.rgb_to_hsv(*(np.asarray(rgb)/max(rgb)))
        assert abs((hue - source_hue + .5) % 1. - .5) < 20/360, (rgb, mean)
        assert saturation > .8*source_saturation, (rgb, mean, saturation, source_saturation)
