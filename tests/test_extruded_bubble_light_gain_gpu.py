"""Native Light Strength authority; distance falloff/emitter size are separate gates."""
import numpy as np
import pytest


@pytest.fixture
def particle_light(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import PARTICLE_VERTEX
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    target = TransitionCapture(1, 1)
    program = texture = vao = 0
    try:
        # Keep the actual vertex colour/geometry law; isolate it from Gaussian,
        # bloom, tone mapping and framebuffer quantisation in this diagnostic.
        program = compile_program(PARTICLE_VERTEX, '''#version 460 core
flat in vec3 vColour;out vec4 colour;
void main(){colour=vec4(vColour,1.);}
''', label='particle physical light strength')
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        texture = int(gl.glGenTextures(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, 1, 1, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
        gl.glDrawBuffers(1, [gl.GL_COLOR_ATTACHMENT0])
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
        vao = int(gl.glGenVertexArrays(1))
        gl.glBindVertexArray(vao)
        gl.glUseProgram(program)
        gl.glViewport(0, 0, 1, 1)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_CULL_FACE)
        loc = lambda name: gl.glGetUniformLocation(program, name)
        for name in ('uParticleLighting', 'uLightStrength', 'uPositionalLight', 'uLightSource'):
            assert loc(name) >= 0, name
        gl.glUniformMatrix3fv(loc('uWorldToView'), 1, False, np.eye(3, dtype='f4'))
        gl.glUniformMatrix4fv(loc('uProjection'), 1, False, np.diag([1., 1., 0., 1.]).astype('f4'))
        gl.glUniform1i(loc('uRowMajor'), 0)
        gl.glUniform1f(loc('uPixel'), .001)
        gl.glUniform1f(loc('uParticleRadiusShare'), 1.)
        gl.glUniform1f(loc('uSpecks'), 1.)
        gl.glUniform3f(loc('uSpeckWarm'), .4, .6, .8)

        def draw(strength, *, positional=0., lighting=1., source=(0., 0., -10.),
                 eye=(0., 0., 0.), point=(0., 0., -5., 1.), brightness=1., sun=(0., 0., -1.)):
            for name, value in (('uLightStrength', strength), ('uParticleLighting', lighting),
                                ('uPositionalLight', positional)):
                gl.glUniform1f(loc(name), value)
            for name, value in (('uLightSource', source), ('uEye', eye), ('uSunBelow', sun)):
                gl.glUniform3f(loc(name), *value)
            gl.glVertexAttrib4f(0, *point)
            gl.glVertexAttrib4f(1, brightness, 1., .5, 0.)
            gl.glClearColor(0., 0., 0., 0.)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, 1)
            gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)
            result = np.frombuffer(gl.glReadPixels(0, 0, 1, 1, gl.GL_RGBA, gl.GL_FLOAT), dtype='f4').copy()
            assert np.isfinite(result).all()
            assert gl.glGetError() == gl.GL_NO_ERROR
            assert result[3] == 1.  # The diagnostic sample really intersected its quad.
            return result[:3]

        yield draw
    finally:
        if vao:
            gl.glDeleteVertexArrays(1, [vao])
        if texture:
            gl.glDeleteTextures([texture])
        if program:
            gl.glDeleteProgram(program)
        target.close()


@pytest.mark.qt
@pytest.mark.parametrize('positional', [0., 1.])
def test_production_particle_ambient_survives_and_direct_delta_is_linear(particle_light, positional):
    samples = [particle_light(strength, positional=positional) for strength in (0., .5, 1.)]
    tint = np.array([.4, .6, .8])
    np.testing.assert_allclose(samples[0], tint * .3, rtol=2e-6, atol=0.)
    np.testing.assert_allclose(samples[2], tint * 2.5, rtol=2e-6, atol=0.)
    np.testing.assert_allclose(samples[1] - samples[0], (samples[2] - samples[0]) * .5,
                               rtol=2e-6, atol=0.)


@pytest.mark.qt
def test_production_surface_strength_one_preserves_previous_phase_law(particle_light):
    for sun in ((0., 0., -1.), (.6, 0., -.8), (1., 0., 0.), (0., 0., 1.)):
        expected = np.array([.4, .6, .8]) * (.3 + 2.2 * max(-sun[2], 0.) ** 4)
        np.testing.assert_allclose(particle_light(1., sun=sun), expected, rtol=2e-6, atol=0.)


@pytest.mark.qt
def test_production_deep_particle_uses_source_at_particle_not_camera_or_authored_direction(particle_light):
    point = np.array([0., 0., -5.])
    eye = np.zeros(3)
    tint = np.array([.4, .6, .8])
    for source in ((0., 0., -10.), (3., 0., -9.), (5., 0., -5.), (0., 0., 0.)):
        delta = np.asarray(source) - point
        direction = delta / np.linalg.norm(delta)
        expected = tint * (.3 + 2.2 * max(float(np.array([0., 0., -1.]) @ direction), 0.) ** 4)
        baseline = particle_light(1., positional=1., source=source, sun=(1., 0., 0.))
        np.testing.assert_allclose(baseline, expected, rtol=2e-6, atol=0.)
        # Translate the entire physical configuration; camera-relative world
        # conversion and point-light direction must retain the same result.
        offset = np.array([7., -3., 2.])
        moved = particle_light(1., positional=1., source=tuple(np.asarray(source) + offset),
                               eye=tuple(eye + offset), point=(*tuple(point + offset), 1.), sun=(0., 1., 0.))
        np.testing.assert_allclose(moved, baseline, rtol=2e-6, atol=0.)
    # Undefined Source direction has no direct phase, and must not yield NaNs.
    np.testing.assert_allclose(particle_light(1., positional=1., source=tuple(point)),
                               tint * .3, rtol=2e-6, atol=0.)


def _parameters():
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_mode_settings import require_mode_settings
    return {entry.key: require_canonical_default('widgets.spotify_visualizer.' + entry.key)
            for entry in require_mode_settings('extruded_bubble').entries
            if entry.key.startswith('extruded_bubble_')}


@pytest.mark.qt
@pytest.mark.parametrize('light_type', ['Sunlit Surface', 'Deep Light'])
def test_already_lit_cpu_proxies_bypass_second_strength_gain(particle_light, light_type):
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs, glint_proxies
    params = _parameters()
    params['extruded_bubble_light_type'] = light_type
    shells = np.array([[0., 0., -5., .5, .1, 0., 1.]], dtype='f4')
    colours = []
    for strength in (0., .5, 1.):
        knobs = scene_knobs({**params, 'extruded_bubble_light_strength': strength})
        proxy = glint_proxies(shells, (0., 0., -1.), knobs['proxy_power'],
                              light_source=(0., 0., -10.) if light_type == 'Deep Light' else None)[0]
        colours.append(particle_light(strength, positional=float(light_type == 'Deep Light'), lighting=0.,
                                       point=tuple(proxy[:4]), brightness=float(proxy[4])))
    assert np.count_nonzero(colours[0]) == 0
    assert colours[2].sum() > 0.
    np.testing.assert_allclose(colours[1], colours[2] * .5, rtol=2e-6, atol=0.)
    # Fixed already-lit input must ignore this second strength entirely.
    np.testing.assert_array_equal(particle_light(0., lighting=0.), particle_light(1., lighting=0.))


@pytest.mark.parametrize('light_type,positional', [('Sunlit Surface', 0.), ('Deep Light', 1.)])
def test_shared_uniform_owner_applies_strength_to_rays_exactly_once(light_type, positional):
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs, ray_strength
    from rendering.quick.visualizer.implementations.extruded_bubble import _common
    params = _parameters()
    params.update(extruded_bubble_light_type=light_type, extruded_bubble_rays_enabled=True,
                  extruded_bubble_rays=(.2, .8))
    authored_rays = ray_strength(params, .6)
    for strength in (0., .5, 1.):
        knobs = scene_knobs({**params, 'extruded_bubble_light_strength': strength})
        uniforms = _common(knobs, view_to_world=np.eye(3).ravel(), tan=(1., 1.), time=0.,
                           surface_travel=0., rays=authored_rays, streak=(1., 0.))
        assert uniforms['uLightStrength'] == strength
        assert uniforms['uPositionalLight'] == positional  # Mode survives Strength0.
        assert uniforms['uRays'] == pytest.approx(authored_rays * strength)
