"""Production world-shaft helpers in native GL; no golden-art acceptance claim."""
import math

import numpy as np
import pytest


def _constant_pattern(source):
    """Control density only; retain the production march and envelope unchanged."""
    start = source.index('float shaftPattern(')
    opening = source.index('{', start)
    level = 1
    closing = opening + 1
    while level:
        level += (source[closing] == '{') - (source[closing] == '}')
        closing += 1
    return source[:opening] + '{ return 1.0; }' + source[closing:]


@pytest.fixture
def world_shaft(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import SHAFT_FRAGMENT
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    prefix = SHAFT_FRAGMENT.rsplit('void main()', 1)[0]
    assert 'float worldShafts(' in prefix and 'vec2 shaftPatternCoords(' in prefix
    diagnostic = '''
uniform int uDiagnostic;
uniform vec3 uTestPoint, uTestRay;
uniform float uTestJitter;
void main() {
    if (uDiagnostic == 0) {
        vec2 q = shaftPatternCoords(uTestPoint);
        FragColor = vec4(q, shaftPattern(q, uTime), 1.);
    } else {
        float distance;
        float integral = worldShafts(uTestRay, uTestJitter, distance);
        FragColor = vec4(integral, distance, 0., 1.);
    }
}
'''
    vertex = '''#version 460 core
out vec2 vNdc;
void main(){
    vec2 p=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2));
    vNdc=p*2.-1.;gl_Position=vec4(vNdc,0.,1.);
}
'''
    target = TransitionCapture(1, 1)
    programs = []
    texture = 0
    try:
        for label, fragment in (('actual density', prefix), ('controlled density', _constant_pattern(prefix))):
            programs.append(compile_program(vertex, fragment + diagnostic, label='world shafts ' + label))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        texture = int(gl.glGenTextures(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, 1, 1, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
        gl.glDrawBuffers(1, [gl.GL_COLOR_ATTACHMENT0])
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
        gl.glBindVertexArray(target.vao)
        gl.glViewport(0, 0, 1, 1)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_CULL_FACE)

        def draw(point=(0., 0., -5.), *, controlled=False, integrate=False, uniforms=None):
            program = programs[int(controlled)]
            gl.glUseProgram(program)
            values = dict(uSurfaceShaft=0., uRaySource=(0., 0., 0.), uRayEnd=(0., 0., -20.),
                          uRayAcross=(1., 0., 0.), uRayUp=(0., 1., 0.), uRayRadius=.9,
                          uFanReach=.3, uShaftSoft=.5, uShaftScale=.55, uShaftY=8.,
                          uSunBelow=(.6, .8, 0.), uEye=(0., 0., 2.), uTime=.7,
                          uFlicker=.5, uShimmer=1.3, uTestRay=(0., 0., -1.), uTestJitter=.5,
                          uViewToWorld=np.eye(3, dtype='f4'), uTestPoint=point)
            values.update(uniforms or {})
            for name, value in values.items():
                location = gl.glGetUniformLocation(program, name)
                if name == 'uViewToWorld':
                    gl.glUniformMatrix3fv(location, 1, False, np.asarray(value, dtype='f4'))
                elif isinstance(value, (tuple, list, np.ndarray)):
                    gl.glUniform3f(location, *value)
                else:
                    gl.glUniform1f(location, value)
            gl.glUniform1i(gl.glGetUniformLocation(program, 'uDiagnostic'), int(integrate))
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)
            result = np.frombuffer(gl.glReadPixels(0, 0, 1, 1, gl.GL_RGBA, gl.GL_FLOAT), dtype='f4').copy()
            assert np.isfinite(result).all()
            assert gl.glGetError() == gl.GL_NO_ERROR
            return result

        yield draw
    finally:
        if texture:
            gl.glDeleteTextures([texture])
        for program in programs:
            gl.glDeleteProgram(program)
        target.close()


@pytest.mark.qt
@pytest.mark.parametrize('surface', [0., 1.])
def test_production_world_coords_and_noise_do_not_move_with_camera(world_shaft, surface):
    point = (1.2, -2.3, -5.4)
    baseline = world_shaft(point, uniforms={'uSurfaceShaft': surface})
    for eye, view in (((12., -6., 3.), ((0., 0., -1.), (0., 1., 0.), (1., 0., 0.))),
                      ((-9., 4., 15.), np.eye(3))):
        actual = world_shaft(point, uniforms={'uSurfaceShaft': surface, 'uEye': eye, 'uViewToWorld': view})
        np.testing.assert_array_equal(actual, baseline)


@pytest.mark.qt
def test_production_surface_pattern_follows_parallel_refracted_light(world_shaft):
    source = np.array([2., 3., -1.])
    point = source + np.array([1., -2., 3.])
    uniforms = dict(uSurfaceShaft=1., uRaySource=tuple(source))
    baseline = world_shaft(point, uniforms=uniforms)
    assert baseline[:2] == pytest.approx((2.5, 3.), abs=2e-6)
    for distance in (-4., 7.):
        actual = world_shaft(point + np.array([.6, .8, 0.]) * distance, uniforms=uniforms)
        assert actual == pytest.approx(baseline, abs=2e-6, rel=2e-5)
    offset = np.array([-4., 2., 6.])
    assert world_shaft(point + offset, uniforms={**uniforms, 'uRaySource': tuple(source + offset)}) == pytest.approx(
        baseline, abs=2e-6, rel=2e-5)


@pytest.mark.qt
def test_production_deep_projector_preserves_normalized_cone_coordinates(world_shaft):
    from widgets.spotify_visualizer.extruded_bubble_geometry import stream_basis
    axis = np.array([.6, 0., -.8])
    across, up = map(np.asarray, stream_basis(axis))
    source = np.array([2., -1., 3.])
    uniforms = dict(uSurfaceShaft=0., uRaySource=tuple(source), uRayEnd=tuple(source + axis * 20.),
                    uRayAcross=tuple(across), uRayUp=tuple(up))
    results = []
    for distance in (1., 5., 12.):
        radius = .9 + distance * math.tan(.3)
        point = source + axis * distance + across * (.2 * radius) - up * (.1 * radius)
        results.append(world_shaft(point, uniforms=uniforms))
    for result in results:
        assert result[:2] == pytest.approx((.18, -.09), abs=2e-6)
        assert result == pytest.approx(results[0], abs=2e-6, rel=2e-5)


@pytest.mark.qt
def test_production_pattern_softness_and_flicker_are_live_continuous_consumers(world_shaft):
    points = [(x, -.7, -z) for x in (-3., -.9, .4, 2.1) for z in (1., 4., 9.)]
    def samples(**uniforms):
        return np.array([world_shaft(p, uniforms=uniforms)[2] for p in points])
    quiet = samples(uFlicker=0.)
    middle = samples(uFlicker=.5)
    full = samples(uFlicker=1.)
    assert quiet.max() > 0.
    assert not np.array_equal(quiet, full)
    np.testing.assert_allclose(middle, (quiet + full) * .5, rtol=2e-5, atol=2e-7)
    assert not np.array_equal(samples(uShaftSoft=0.), samples(uShaftSoft=1.))
    assert not np.array_equal(samples(uShimmer=0.), samples(uShimmer=2.))


def _smooth(a, b, x):
    t = max(0., min(1., (x - a) / (b - a)))
    return t * t * (3. - 2. * t)


def _controlled_integral(surface, eye, source, end, ray, shaft_y, jitter):
    eye, source, end, ray = map(lambda value: np.asarray(value, dtype=float), (eye, source, end, ray))
    length = float(np.linalg.norm(end - source))
    if length < .001:
        return 0., 0.
    axis = (end - source) / length
    total = moment = 0.
    step = 45. / 40.
    for index in range(40):
        distance = (index + jitter) * step
        p = eye + ray * distance
        below = shaft_y - p[1]
        if surface and below <= 0.:
            break
        delta = p - source
        along = float(delta @ axis)
        lateral = float(np.linalg.norm(delta - along * axis))
        outer = .9 + max(along, 0.) * math.tan(.3)
        extent = (_smooth(-1.8, 1.2, along) * (1. - _smooth(length - 2., length + 1.5, along))
                  * (1. - _smooth(outer * .6, outer, lateral)))
        light_distance = below if surface else float(np.linalg.norm(delta))
        weight = extent * math.exp(-light_distance * .07) * math.exp(-distance * .035)
        total += weight
        moment += distance * weight
    return total * step, moment / total if total > 0. else 0.


@pytest.mark.qt
@pytest.mark.parametrize('surface,eye,end,ray,shaft_y', [
    (0., (0., 0., 2.), (0., 0., -20.), (0., 0., -1.), 8.),
    (1., (0., 0., 0.), (0., 20., 0.), (0., 1., 0.), 5.),
])
def test_production_march_and_scalar_centroid_match_controlled_density_oracle(world_shaft, surface, eye, end, ray, shaft_y):
    for jitter in (.25, .75):
        uniforms = dict(uSurfaceShaft=surface, uEye=eye, uRayEnd=end, uTestRay=ray,
                        uShaftY=shaft_y, uTestJitter=jitter)
        actual = world_shaft(controlled=True, integrate=True, uniforms=uniforms)
        expected = _controlled_integral(surface, eye, (0., 0., 0.), end, ray, shaft_y, jitter)
        assert actual[:2] == pytest.approx(expected, abs=2e-6, rel=2e-5)
        assert actual[0] > 0. and 0. < actual[1] < 45.
        assert abs(actual[1] - 18.) > 1.  # Real contribution, not the former fixed-depth sample.


@pytest.mark.qt
@pytest.mark.parametrize('uniforms', [
    {'uRayEnd': (0., 0., 0.)},
    {'uRayEnd': (0., 0., -.0005)},
    {'uEye': (100., 0., 2.)},
    {'uSurfaceShaft': 1., 'uEye': (0., 9., 0.), 'uTestRay': (0., 1., 0.)},
])
def test_production_empty_march_and_degenerate_projector_are_finite(world_shaft, uniforms):
    result = world_shaft(controlled=True, integrate=True, uniforms=uniforms)
    assert result[:2] == pytest.approx((0., 0.), abs=0.)
    if 'uRayEnd' in uniforms:
        world_shaft((1., 2., 3.), uniforms=uniforms)  # Actual projector/noise must also remain finite.


@pytest.mark.qt
@pytest.mark.parametrize('light_type,surface', [('Sunlit Surface', 1.), ('Deep Light', 0.)])
def test_production_mode_and_basis_come_from_canonical_effective_ray_path(world_shaft, light_type, surface):
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_mode_settings import require_mode_settings
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs
    from rendering.quick.visualizer.implementations.extruded_bubble import _common
    from widgets.spotify_visualizer.extruded_bubble_geometry import stream_basis

    params = {entry.key: require_canonical_default('widgets.spotify_visualizer.' + entry.key)
              for entry in require_mode_settings('extruded_bubble').entries
              if entry.key.startswith('extruded_bubble_')}
    params.update(extruded_bubble_light_type=light_type,
                  extruded_bubble_light_direction=(-.8, .2, .25, .8, -.7, .9),
                  extruded_bubble_ray_path=(.4, -.5, -.2, .5, .6, -.6))
    for strength in (0., 1.):
        params['extruded_bubble_light_strength'] = strength
        knobs = scene_knobs(params)
        axis = np.asarray(knobs['ray_end']) - knobs['ray_source']
        axis /= np.linalg.norm(axis)
        across, up = stream_basis(axis)
        assert knobs['surface_shaft'] == surface
        assert knobs['ray_across'] == pytest.approx(across)
        assert knobs['ray_up'] == pytest.approx(up)
        uniforms = _common(knobs, view_to_world=np.eye(3).ravel(), tan=(1., 1.), time=.7,
                           surface_travel=0., rays=1., streak=(1., 0.))
        assert uniforms['uSurfaceShaft'] == surface
        assert uniforms['uRayAcross'] == pytest.approx(across)
        assert uniforms['uRayUp'] == pytest.approx(up)
        # The camera-derived Deep uSunBelow must not steer its fixed projector.
        native = {key: uniforms[key] for key in ('uSurfaceShaft', 'uRaySource', 'uRayEnd',
                  'uRayAcross', 'uRayUp', 'uRayRadius', 'uFanReach', 'uSunBelow') if key in uniforms}
        # Endpoint upload currently belongs to the renderer's shafts block,
        # while _common publishes the mode and canonical transverse basis.
        native.update(uRaySource=knobs['ray_source'], uRayEnd=knobs['ray_end'])
        point = np.asarray(knobs['ray_source']) + axis * 4. + np.asarray(across) * .2
        baseline = world_shaft(point, uniforms=native)
        if not surface:
            expected_q = (.2 * knobs['ray_radius'] /
                          (knobs['ray_radius'] + 4. * math.tan(knobs['fan_reach'])), 0.)
            assert baseline[:2] == pytest.approx(expected_q, abs=2e-6)
        if not surface:
            assert world_shaft(point, uniforms={**native, 'uSunBelow': (1., 0., 0.)}) == pytest.approx(baseline, abs=0.)


@pytest.mark.qt
def test_production_main_shadows_actual_contribution_centroid_not_fixed_depth(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import FULL_VERTEX, SHAFT_FRAGMENT
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    # Control only noise density and sample jitter. Keep production main wiring,
    # envelope, integration, phase and four-proxy attenuation unchanged.
    source = _constant_pattern(SHAFT_FRAGMENT)
    jitter = 'float jitter = fract(52.9829189*fract(dot(gl_FragCoord.xy,vec2(0.06711056,0.00583715))));'
    assert source.count(jitter) == 1
    source = source.replace(jitter, 'float jitter = 0.25;')
    former = source.replace('sceneTransmittance(uEye+ray*atDistance)', 'sceneTransmittance(uEye+ray*18.0)')
    assert former != source
    target = TransitionCapture(1, 1)
    programs = []
    texture = 0
    try:
        texture = int(gl.glGenTextures(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, 1, 1, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
        gl.glDrawBuffers(1, [gl.GL_COLOR_ATTACHMENT0])
        gl.glBindVertexArray(target.vao)
        gl.glViewport(0, 0, 1, 1)
        gl.glDisable(gl.GL_BLEND); gl.glDisable(gl.GL_DEPTH_TEST); gl.glDisable(gl.GL_CULL_FACE)
        results = []
        for fragment in (source, former):
            program = compile_program(FULL_VERTEX, fragment, label='actual shaft main centroid')
            programs.append(program); gl.glUseProgram(program)
            loc = lambda name: gl.glGetUniformLocation(program, name)
            gl.glUniformMatrix3fv(loc('uViewToWorld'), 1, False, np.eye(3, dtype='f4'))
            gl.glUniform2f(loc('uTan'), 1., 1.); gl.glUniform2f(loc('uLensShift'), 0., 0.)
            for name, value in (('uSurfaceShaft', 0.), ('uRayRadius', .9), ('uFanReach', .3),
                                ('uShaftSoft', .5), ('uParticleAtten', 0.)):
                gl.glUniform1f(loc(name), value)
            for name, value in (('uEye', (0., 0., 2.)), ('uRaySource', (0., 0., 0.)),
                                ('uRayEnd', (0., 0., -20.)), ('uSunBelow', (0., 0., -1.))):
                gl.glUniform3f(loc(name), *value)
            # At z=-12 this blocker is AFTER the real lit centroid, but BEFORE
            # the former z=-16 sample. Only the latter should inherit its shadow.
            gl.glUniform4f(loc('uBlock0'), 0., 0., -12., .4)
            for name in ('uBlock1', 'uBlock2', 'uBlock3'):
                gl.glUniform4f(loc(name), 0., 0., 0., 0.)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            values = np.frombuffer(gl.glReadPixels(0, 0, 1, 1, gl.GL_RGBA, gl.GL_FLOAT), dtype='f4')
            assert np.isfinite(values).all(); results.append(values.copy())
        integral, distance = _controlled_integral(0., (0., 0., 2.), (0., 0., 0.),
                                                    (0., 0., -20.), (0., 0., -1.), 8., .25)
        assert 2. - distance > -12.
        expected = integral * .13 * 1.25
        assert results[0] == pytest.approx([expected] * 4, rel=2e-5)
        assert results[1] == pytest.approx(results[0] * .84, rel=2e-5)
        assert gl.glGetError() == gl.GL_NO_ERROR
    finally:
        if texture: gl.glDeleteTextures([texture])
        for program in programs: gl.glDeleteProgram(program)
        target.close()
