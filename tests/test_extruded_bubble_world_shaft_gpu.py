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
    } else if (uDiagnostic == 2) {
        FragColor = vec4(sceneTransmittance(uTestPoint));
    } else {
        float distance;
        float coverage;
        float integral = worldShafts(uTestRay, uTestJitter, distance, coverage);
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

        def draw(point=(0., 0., -5.), *, controlled=False, integrate=False, shadow=False, uniforms=None):
            program = programs[int(controlled)]
            gl.glUseProgram(program)
            values = dict(uSurfaceShaft=0., uRaySource=(0., 0., 0.), uRayEnd=(0., 0., -20.),
                          uBeamWidth=1., uLightingScene=1., uWorldCenter=(0.,0.,0.), uWorldHalf=(18.,8.,18.),
                          uRayAcross=(1., 0., 0.), uRayUp=(0., 1., 0.), uRayRadius=.9,
                          uFanReach=.3, uShaftSoft=.5, uShaftScale=.55, uShaftY=8.,
                          uSunBelow=(.6, .8, 0.), uEye=(0., 0., 2.), uTime=.7,
                          uLightSource=(0.,0.,0.), uPositionalLight=0., uParticleAtten=0.,
                          uBlock0=(0.,0.,0.,0.), uBlock1=(0.,0.,0.,0.),
                          uBlock2=(0.,0.,0.,0.), uBlock3=(0.,0.,0.,0.),
                          uFlicker=.5, uShimmer=1.3, uTestRay=(0., 0., -1.), uTestJitter=.5,
                          uViewToWorld=np.eye(3, dtype='f4'), uTestPoint=point)
            values.update(uniforms or {})
            for name, value in values.items():
                location = gl.glGetUniformLocation(program, name)
                if name == 'uViewToWorld':
                    gl.glUniformMatrix3fv(location, 1, False, np.asarray(value, dtype='f4'))
                elif isinstance(value, (tuple, list, np.ndarray)):
                    (gl.glUniform4f if len(value) == 4 else gl.glUniform3f)(location, *value)
                else:
                    gl.glUniform1f(location, value)
            gl.glUniform1i(gl.glGetUniformLocation(program, 'uDiagnostic'), 2 if shadow else int(integrate))
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
def test_scene_surface_pattern_backprojects_to_actual_water_plane(world_shaft):
    point=np.array([1.2,-2.3,-5.4])
    uniforms=dict(uSurfaceShaft=1.,uShaftY=8.)
    baseline=world_shaft(point,uniforms=uniforms)
    assert baseline[:2]==pytest.approx((8.925,-5.4),abs=2e-6)
    for distance in (-4.,7.):
        actual=world_shaft(point+np.array([.6,.8,0.])*distance,uniforms=uniforms)
        assert actual==pytest.approx(baseline,abs=2e-6,rel=2e-5)
    offset=np.array([-4.,2.,6.])
    shifted=world_shaft(point+offset,uniforms={**uniforms,'uWorldCenter':tuple(offset),'uShaftY':10.})
    assert shifted==pytest.approx(baseline,abs=2e-6,rel=2e-5)


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


@pytest.mark.qt
@pytest.mark.parametrize('surface', [0., 1.])
def test_scene_lighting_ignores_beam_end_and_width_but_is_fixed_world_bounded(world_shaft, surface):
    uniforms = dict(uLightingScene=1., uSurfaceShaft=surface, uEye=(5., 0., 2.),
                    uTestRay=(0., 0., -1.), uShaftY=8.)
    expected = world_shaft(controlled=True, integrate=True, uniforms=uniforms)
    assert expected[0] > 0.
    for end, width in (((0., 0., 0.), .25), ((0., 0., 2.), 3.)):
        actual = world_shaft(controlled=True, integrate=True,
                             uniforms={**uniforms, 'uRayEnd': end, 'uBeamWidth': width})
        np.testing.assert_array_equal(actual, expected)
    # The real density field, not only a constant-density diagnostic, must
    # ignore the unused beam origin too. Deep remains anchored to Light Source.
    point = (2., -1., -3.)
    pattern = world_shaft(point, uniforms=uniforms)
    for source in ((-8., 3., 6.), (12., -7., -13.)):
        actual = world_shaft(point, uniforms={**uniforms, 'uRaySource': source})
        np.testing.assert_array_equal(actual, pattern)
    outside = world_shaft(controlled=True, integrate=True,
                          uniforms={**uniforms, 'uEye': (100., 0., 2.)})
    assert outside[0] == 0.


def _smooth(a, b, x):
    t = max(0., min(1., (x - a) / (b - a)))
    return t * t * (3. - 2. * t)


@pytest.mark.qt
def test_deep_scene_blocker_behind_emitter_cannot_shadow_forward_sample(world_shaft):
    uniforms = dict(uLightingScene=1., uPositionalLight=1., uLightSource=(0.,0.,0.))
    clear = world_shaft((0.,0.,-8.), shadow=True, uniforms=uniforms)
    behind = world_shaft((0.,0.,-8.), shadow=True,
                        uniforms={**uniforms, 'uBlock0': (0.,0.,2.,.5)})
    between = world_shaft((0.,0.,-8.), shadow=True,
                         uniforms={**uniforms, 'uBlock0': (0.,0.,-4.,.5)})
    np.testing.assert_array_equal(clear, behind)
    assert between[0] == pytest.approx(clear[0]*.84, abs=2e-6)


@pytest.mark.qt
def test_deep_scene_pattern_radiates_from_light_source_not_parallel_planes(world_shaft):
    origin = np.asarray((2.,-1.,3.))
    direction = np.asarray((.4,.7,-.6))
    uniforms = dict(uLightingScene=1.,uSurfaceShaft=0.,uLightSource=tuple(origin))
    near = world_shaft(tuple(origin+direction*2.), uniforms=uniforms)
    far = world_shaft(tuple(origin+direction*9.), uniforms=uniforms)
    np.testing.assert_allclose(near,far,rtol=2e-6,atol=2e-6)


@pytest.mark.qt
@pytest.mark.parametrize('light_type', ['Sunlit Surface', 'Deep Light'])
def test_scene_integral_uses_canonical_light_and_ignores_authored_beam_nodes(world_shaft, light_type):
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs
    from rendering.quick.visualizer.implementations.extruded_bubble import _common

    parameters = {**require_canonical_default('widgets.spotify_visualizer'),
                  'extruded_bubble_light_type': light_type,
                  'extruded_bubble_lighting_coverage': 'SCENE'}
    def sample(**overrides):
        knobs = scene_knobs({**parameters, **overrides})
        mapped = _common(knobs, view_to_world=np.eye(3).ravel(), tan=(1.,1.),
                         time=.7, surface_travel=0., rays=1., streak=(1.,0.))
        keys = ('uSurfaceShaft','uLightingScene','uBeamWidth','uWorldCenter','uWorldHalf',
                'uLightSource','uSunBelow','uShaftY',
                'uFanReach','uShaftSoft','uShaftScale')
        uniforms = {key: mapped[key] for key in keys}
        uniforms.update(uRaySource=knobs['ray_source'], uRayEnd=knobs['ray_end'], uEye=(0.,-2.,2.))
        return world_shaft(integrate=True, uniforms=uniforms)
    expected = sample()
    assert expected[0] > 0.
    changed_beam = sample(extruded_bubble_ray_path=(-.7,.4,.3,.8,-.6,-.9),
                          extruded_bubble_beam_width=3.)
    np.testing.assert_array_equal(changed_beam, expected)
    changed_light = sample(extruded_bubble_light_direction=(-.8,.2,.25,.8,-.7,.9))
    assert not np.array_equal(changed_light, expected)


def _soft_tank(edge):
    """The tank's soft boundary (sceneLightSupport): full inside, easing to nothing over its last 6%."""
    t = min(1., max(0., (edge-.94)/.06))
    return 1.-t*t*(3.-2.*t)


def _controlled_integral(surface,eye,source,ray,shaft_y,jitter):
    """Independent box/medium quadrature, without the retired cone model."""
    eye,source,ray=(np.asarray(v,dtype=float) for v in (eye,source,ray))
    total=moment=0.
    step=45./40.
    for index in range(40):
        distance=(index+jitter)*step
        p=eye+ray*distance
        below=shaft_y-p[1]
        if surface and below<=0.:break
        extent=_soft_tank(float(np.max(np.abs(p)/np.array((18.,8.,18.)))))
        if extent<=0.:continue
        light_distance=below if surface else float(np.linalg.norm(p-source))
        weight=extent*math.exp(-light_distance*.07)*math.exp(-distance*.035)
        total+=weight;moment+=distance*weight
    return total*step,moment/total if total>0. else 0.


@pytest.mark.qt
@pytest.mark.parametrize('surface,eye,ray,shaft_y', [
    (0., (0., 0., 2.), (0., 0., -1.), 8.),
    (1., (0., 0., 0.), (0., 1., 0.), 5.),
])
def test_production_march_and_scalar_centroid_match_controlled_density_oracle(world_shaft, surface, eye, ray, shaft_y):
    for jitter in (.25, .75):
        uniforms = dict(uSurfaceShaft=surface, uEye=eye, uTestRay=ray,
                        uShaftY=shaft_y, uTestJitter=jitter)
        actual = world_shaft(controlled=True, integrate=True, uniforms=uniforms)
        expected = _controlled_integral(surface, eye, (0., 0., 0.), ray, shaft_y, jitter)
        assert actual[:2] == pytest.approx(expected, abs=2e-6, rel=2e-5)
        assert actual[0] > 0. and 0. < actual[1] < 45.
        assert abs(actual[1] - 18.) > 1.  # Real contribution, not the former fixed-depth sample.


@pytest.mark.qt
@pytest.mark.parametrize('uniforms', [
    {'uEye': (100., 0., 2.)},
    {'uSurfaceShaft': 1., 'uEye': (0., 9., 0.), 'uTestRay': (0., 1., 0.)},
])
def test_scene_empty_march_is_finite(world_shaft, uniforms):
    result = world_shaft(controlled=True, integrate=True, uniforms=uniforms)
    assert result[:2] == pytest.approx((0., 0.), abs=0.)


@pytest.mark.qt
@pytest.mark.parametrize('light_type,surface',[('Sunlit Surface',1.),('Deep Light',0.)])
def test_canonical_scene_light_geometry_does_not_depend_on_strength(world_shaft,light_type,surface):
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs
    from rendering.quick.visualizer.implementations.extruded_bubble import _common
    parameters={**require_canonical_default('widgets.spotify_visualizer'),
                'extruded_bubble_light_type':light_type,'extruded_bubble_lighting_coverage':'SCENE'}
    results=[]
    for strength in (0.,1.):
        knobs=scene_knobs({**parameters,'extruded_bubble_light_strength':strength})
        values=_common(knobs,view_to_world=np.eye(3).ravel(),tan=(1.,1.),time=.7,
                       surface_travel=0.,rays=1.,streak=(1.,0.))
        keys=('uSurfaceShaft','uLightingScene','uLightSource','uSunBelow','uShaftY','uWorldCenter','uWorldHalf')
        native={key:values[key] for key in keys}
        assert native['uSurfaceShaft']==surface
        results.append(world_shaft((1.,-2.,-3.),uniforms=native))
    np.testing.assert_array_equal(results[0],results[1])


@pytest.mark.qt
def test_scene_main_shadows_actual_contribution_centroid_not_fixed_depth(qt_app):
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
                                ('uBeamWidth', 1.), ('uLightingScene', 1.), ('uPositionalLight', 1.),
                                ('uShaftSoft', .5), ('uParticleAtten', 0.)):
                gl.glUniform1f(loc(name), value)
            for name, value in (('uEye', (0., 0., 2.)), ('uRaySource', (0., 0., 0.)),
                                ('uRayEnd', (0., 0., -20.)), ('uSunBelow', (0., 0., -1.)),
                                ('uWorldCenter', (0.,0.,0.)), ('uWorldHalf', (18.,8.,18.))):
                gl.glUniform3f(loc(name), *value)
            # At z=-12 this blocker is AFTER the real lit centroid, but BEFORE
            # the former z=-16 sample. Only the latter should inherit its shadow.
            gl.glUniform4f(loc('uBlock0'), 0., 0., -12., .4)
            for name in ('uBlock1', 'uBlock2', 'uBlock3'):
                gl.glUniform4f(loc(name), 0., 0., 0., 0.)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            values = np.frombuffer(gl.glReadPixels(0, 0, 1, 1, gl.GL_RGBA, gl.GL_FLOAT), dtype='f4')
            assert np.isfinite(values).all(); results.append(values.copy())
        distances = (np.arange(40)+.25)*(45./40.)
        weights = np.exp(-np.abs(2.-distances)*.07)*np.exp(-distances*.035)
        weights *= np.array([_soft_tank(abs(2.-d)/18.) for d in distances])
        integral = weights.sum()*(45./40.)
        distance = (weights*distances).sum()/weights.sum()
        assert 2. - distance > -12.
        expected = integral * .13 * 1.25
        assert results[0] == pytest.approx([expected] * 4, rel=2e-5)
        assert results[1] == pytest.approx(results[0] * .84, rel=2e-5)
        assert gl.glGetError() == gl.GL_NO_ERROR
    finally:
        if texture: gl.glDeleteTextures([texture])
        for program in programs: gl.glDeleteProgram(program)
        target.close()
