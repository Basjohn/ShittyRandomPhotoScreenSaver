"""Settings -> production backdrop HDR pixels: direct light preserves ambient."""
import numpy as np
import pytest


@pytest.fixture
def backdrop_light(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import BACKDROP_FRAGMENT, FULL_VERTEX
    from rendering.quick.render.gl_resources import compile_program
    from rendering.quick.visualizer.implementations.extruded_bubble import _Uniforms
    from tools.transition_contact_sheet import TransitionCapture

    target = TransitionCapture(1, 1)
    program = texture = shafts = 0
    try:
        program = compile_program(FULL_VERTEX, BACKDROP_FRAGMENT, label='EB direct light backdrop')
        texture, shafts = gl.glGenTextures(2)
        for name, value in ((texture, None), (shafts, np.ones((1, 1, 4), dtype='f4'))):
            gl.glBindTexture(gl.GL_TEXTURE_2D, name)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, 1, 1, 0, gl.GL_RGBA, gl.GL_FLOAT, value)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
        gl.glDrawBuffer(gl.GL_COLOR_ATTACHMENT0)
        gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)
        gl.glViewport(0, 0, 1, 1)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glBindVertexArray(target.vao)
        gl.glUseProgram(program)
        bank = _Uniforms()

        def draw(values):
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, shafts)
            bank.set(program, {**values, 'uShafts': 0, 'uFrameSize': (1., 1.), 'uLensShift': (0., 0.)})
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            result = np.frombuffer(gl.glReadPixels(0, 0, 1, 1, gl.GL_RGBA, gl.GL_FLOAT), dtype='f4').copy()
            assert gl.glGetError() == gl.GL_NO_ERROR
            assert np.isfinite(result).all()
            return result[:3]

        yield draw
    finally:
        if program:
            gl.glDeleteProgram(program)
        if texture:
            gl.glDeleteTextures([texture, shafts])
        target.close()


@pytest.mark.qt
@pytest.mark.parametrize('light_type', ('Sunlit Surface', 'Deep Light'))
@pytest.mark.parametrize('contribution', ('water', 'shafts', 'veils'))
def test_backdrop_direct_light_scales_once_over_unchanged_ambient(backdrop_light, light_type, contribution):
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs
    from rendering.quick.visualizer.implementations.extruded_bubble import _common

    parameters = {**require_canonical_default('widgets.spotify_visualizer'),
                  'extruded_bubble_light_type': light_type}
    samples = []
    for strength in (0., .5, 1., 2.):
        knobs = scene_knobs({**parameters, 'extruded_bubble_light_strength': strength})
        values = _common(knobs, view_to_world=(1., 0., 0., 0., 1., 0., 0., 0., 1.),
                         tan=(.4, .4), time=.7, surface_travel=.7,
                         rays=.6 if contribution == 'shafts' else 0., streak=(.6, .8))
        values.update(uSunBelow=(0., 0., -1.), uMist=0., uProbeMode=0., uLightPower=0.,
                      uGlintPower=0., uProbeFill=0., uRayFocus=0.,
                      uVeils=.5 if contribution == 'veils' else 0.)
        if contribution != 'water':
            # Remove only the light-derived medium glow, retaining its ambient water.
            values['uGlow'] = 0.
            # A zero dot leaves a small negative broad term when glow is0;
            # move the sun sideways so that term is exactly zero as well.
            values['uSunBelow'] = (1., 0., 0.)
        samples.append(backdrop_light(values))
    ambient = samples[0]
    assert ambient.sum() > .001
    delta = samples[2] - ambient
    assert delta.sum() > .001, contribution
    np.testing.assert_allclose(samples[1] - ambient, delta * .5, rtol=2e-4, atol=2e-6)
    np.testing.assert_allclose(samples[3] - ambient, delta * 2., rtol=2e-4, atol=2e-6)


@pytest.mark.qt
@pytest.mark.parametrize('light_direction', ((0.,0.,-1.), (1.,0.,0.), (0.,0.,1.)))
def test_deep_scene_scattering_survives_side_and_away_views(backdrop_light, light_direction):
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs
    from rendering.quick.visualizer.implementations.extruded_bubble import _common

    parameters = {**require_canonical_default('widgets.spotify_visualizer'),
                  'extruded_bubble_light_type': 'Deep Light'}
    deltas = {}
    for coverage in ('BEAM', 'SCENE'):
        knobs = scene_knobs({**parameters, 'extruded_bubble_lighting_coverage': coverage})
        values = _common(knobs, view_to_world=(1.,0.,0.,0.,1.,0.,0.,0.,1.),
                         tan=(.4,.4), time=.7, surface_travel=.7, rays=1., streak=(.6,.8))
        values.update(uSunBelow=light_direction, uMist=0., uDust=0., uGlow=0.,
                      uVeils=0., uProbeMode=0., uLightPower=0., uGlintPower=0., uProbeFill=0.)
        # A constant positive shaft texture isolates the real final compositing
        # gate. Keep the production Deep ray_focus, which formerly erased SCENE.
        deltas[coverage] = backdrop_light(values) - backdrop_light({**values, 'uRays': 0.})
    assert deltas['SCENE'].sum() > .001
    if light_direction != (0.,0.,-1.):
        np.testing.assert_array_equal(deltas['BEAM'], np.zeros(3))
