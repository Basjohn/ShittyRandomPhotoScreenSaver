"""SCENE lighting's authored extent, evaluated in the production shaft shader (native GL) and its Python owner.

Surface sunlight enters through the water surface and reaches Ray End's depth; Deep light reaches Light Source ->
Ray End's range, brightest toward its aim; the tank's edge is soft, never a binary sheet. No art golden.
"""
import math

import numpy as np
import pytest

pytestmark = pytest.mark.qt

HALF = (18.0, 8.0, 18.0)
SURFACE = 8.0


@pytest.fixture
def support(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import SHAFT_FRAGMENT
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    prefix = SHAFT_FRAGMENT.rsplit('void main()', 1)[0]
    assert 'float sceneLightSupport(' in prefix
    fragment = prefix + 'uniform vec3 uTestPoint;\nvoid main() { FragColor = vec4(sceneLightSupport(uTestPoint)); }\n'
    vertex = '''#version 460 core
out vec2 vNdc;
void main(){ vec2 p=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2)); vNdc=p*2.-1.; gl_Position=vec4(vNdc,0.,1.); }
'''
    target = TransitionCapture(1, 1)
    program = compile_program(vertex, fragment, label='scene light support')
    texture = int(gl.glGenTextures(1))
    try:
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, 1, 1, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
        gl.glDrawBuffers(1, [gl.GL_COLOR_ATTACHMENT0])
        gl.glBindVertexArray(target.vao)
        gl.glViewport(0, 0, 1, 1)
        gl.glDisable(gl.GL_BLEND)

        def at(point, **uniforms):
            gl.glUseProgram(program)
            values = dict(uWorldCenter=(0., 0., 0.), uWorldHalf=HALF, uShaftY=SURFACE, uPositionalLight=0.,
                          uLightSource=(0., 0., 0.), uLightFaces=(0., 1., 0.), uLightTravel=(0., -1., 0.),
                          uLightAxis=(0., -1., 0.), uLightReach=(0., 0., 0.), uTestPoint=point)
            values.update(uniforms)
            for name, value in values.items():
                location = gl.glGetUniformLocation(program, name)
                if isinstance(value, tuple):
                    gl.glUniform3f(location, *value)
                else:
                    gl.glUniform1f(location, value)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            value = float(np.frombuffer(gl.glReadPixels(0, 0, 1, 1, gl.GL_RGBA, gl.GL_FLOAT), dtype='f4')[0])
            assert math.isfinite(value) and gl.glGetError() == gl.GL_NO_ERROR
            return value

        yield at
    finally:
        gl.glDeleteTextures([texture])
        gl.glDeleteProgram(program)
        target.close()


def test_surface_sunlight_reaches_ray_ends_depth_and_no_further(support):
    reach = 6.0
    shaped = dict(uLightReach=(0., reach, 0.), uLightTravel=(0.3, -0.95, 0.1))
    assert support((0., SURFACE - 0.5 * reach, 0.), **shaped) == pytest.approx(1.0)
    assert support((0., SURFACE - 1.4 * reach, 0.), **shaped) == 0.0
    middle = support((0., SURFACE - 1.1 * reach, 0.), **shaped)
    assert 0.0 < middle < 1.0                                    # a soft fade, not a cut
    # Unshaped (zero reach): the whole depth is lit, as before the extent existed.
    assert support((0., SURFACE - 1.4 * reach, 0.)) == pytest.approx(1.0)


def test_deep_light_reaches_its_range_brightest_toward_its_aim(support):
    source, reach = (0., 4., 0.), 6.0
    deep = dict(uPositionalLight=1., uLightSource=source, uLightReach=(reach, 0., 0.), uLightAxis=(0., -1., 0.),
                uLightFaces=(0., 0., 0.))
    ahead = support((0., 4. - 0.4 * reach, 0.), **deep)
    behind = support((0., 4. + 0.3 * reach, 0.), **deep)
    assert ahead > behind > 0.0
    assert support((0., 4. - 1.2 * reach, 0.), **deep) == 0.0
    # A longer range lights farther.
    far = (0., 4. - 1.0 * reach, 0.)
    assert support(far, **{**deep, 'uLightReach': (2.0 * reach, 0., 0.)}) > support(far, **deep)


def test_the_tank_edge_is_soft(support):
    inside = support((0.9 * HALF[0], 0., 0.))
    edge = support((0.97 * HALF[0], 0., 0.))
    outside = support((1.01 * HALF[0], 0., 0.))
    assert inside == pytest.approx(1.0) and 0.0 < edge < 1.0 and outside == 0.0


def test_scene_light_support_reads_the_authored_ray_path():
    from core.settings.visualizer_paths import world_point
    from rendering.gl_programs.extruded_bubble_scene import SURFACE_Y, scene_light_support
    light = (0.4, 0.9, -0.5, -0.4, -1.0, 0.5)
    ray = (0.0, 1.0, 0.0, 0.0, -0.2, 0.0)
    surface = scene_light_support("surface", light, ray, (0.2, 0.9, 0.1))
    assert surface["faces"] == (0.0, 1.0, 0.0)
    assert surface["reach"][1] == pytest.approx(SURFACE_Y - world_point(ray[3:])[1])
    deep = scene_light_support("deep", light, ray, (0.2, 0.9, 0.1))
    end, emitter = world_point(ray[3:]), world_point(light[:3])
    assert deep["reach"][0] == pytest.approx(math.dist(end, emitter))
    assert deep["axis"] == pytest.approx(tuple((e - s) / math.dist(end, emitter) for e, s in zip(end, emitter)))


def test_sunlit_scene_shafts_stay_visible_from_the_side(qt_app):
    """A side view (ray at right angles to the sun) gets light from the world march itself, not only the sun fan."""
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import FULL_VERTEX, SHAFT_FRAGMENT
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    constant = 'const float SCENE_SIDE_SCATTER = 2.0;'
    assert SHAFT_FRAGMENT.count(constant) == 1
    target = TransitionCapture(1, 1)
    texture = int(gl.glGenTextures(1))
    results = []
    try:
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, 1, 1, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
        gl.glDrawBuffers(1, [gl.GL_COLOR_ATTACHMENT0])
        gl.glBindVertexArray(target.vao)
        gl.glViewport(0, 0, 1, 1)
        gl.glDisable(gl.GL_BLEND)
        for source in (SHAFT_FRAGMENT, SHAFT_FRAGMENT.replace(constant, 'const float SCENE_SIDE_SCATTER = 0.0;')):
            program = compile_program(FULL_VERTEX, source, label='side scatter')
            gl.glUseProgram(program)
            loc = lambda name: gl.glGetUniformLocation(program, name)
            gl.glUniformMatrix3fv(loc('uViewToWorld'), 1, False, np.eye(3, dtype='f4'))   # looking along -z
            gl.glUniform2f(loc('uTan'), 1e-4, 1e-4)
            for name, value in (('uSurfaceShaft', 1.), ('uLightingScene', 1.), ('uPositionalLight', 0.),
                                ('uShaftSoft', .5), ('uShaftScale', .55), ('uShaftY', SURFACE), ('uTime', .7),
                                ('uFanRays', 60.), ('uFanReach', .5), ('uParticleAtten', 0.)):
                gl.glUniform1f(loc(name), value)
            gl.glUniform2f(loc('uFanMix'), .5, .3)
            for name, value in (('uEye', (0., 0., 10.)), ('uSunBelow', (0., 1., 0.)),        # sun straight up
                                ('uWorldCenter', (0., 0., 0.)), ('uWorldHalf', HALF)):
                gl.glUniform3f(loc(name), *value)
            for name in ('uBlock0', 'uBlock1', 'uBlock2', 'uBlock3'):
                gl.glUniform4f(loc(name), 0., 0., 0., 0.)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            results.append(float(np.frombuffer(gl.glReadPixels(0, 0, 1, 1, gl.GL_RGBA, gl.GL_FLOAT), dtype='f4')[0]))
            gl.glDeleteProgram(program)
        assert gl.glGetError() == gl.GL_NO_ERROR
    finally:
        gl.glDeleteTextures([texture])
        target.close()
    with_side, without = results
    assert with_side > 3.0 * max(without, 1e-6) and with_side > 0.0
