"""Native production shaft envelope geometry; not final shaft-image acceptance."""
import math

import numpy as np
import pytest


def _smooth(a, b, x):
    t = max(0., min(1., (x - a) / (b - a)))
    return t * t * (3. - 2. * t)


def _extent(point, source, end):
    """Independent oracle for the operator-restored Source/End axial envelope."""
    line=np.asarray(end,dtype=float)-source
    length=float(np.linalg.norm(line))
    if length<.001:return 0.
    along=float((np.asarray(point)-source)@(line/length))
    return _smooth(-1.8,1.2,along)*(1.-_smooth(length-2.,length+1.5,along))


@pytest.fixture
def shaft_geometry(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import SHAFT_FRAGMENT
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    # Execute the real functions unchanged, independently of camera marching,
    # angular pattern, representative-depth masks, blur and final composition.
    start = SHAFT_FRAGMENT.index('float blockAttenuation(')
    stop = SHAFT_FRAGMENT.index('float beamShaftFan(', start)
    functions = SHAFT_FRAGMENT[start:stop]
    vertex = '''#version 460 core
uniform vec3 uRaySource, uRayEnd, uEye;
uniform mat3 uViewToWorld;
uniform float uRayRadius, uFanReach, uShaftSoft, uParticleAtten;
uniform float uBeamWidth, uLightingScene, uPositionalLight;
uniform vec3 uSunBelow,uLightSource;
uniform vec4 uBlock0, uBlock1, uBlock2, uBlock3;
layout(std430,binding=5) readonly buffer Points { vec4 points[]; };
layout(std430,binding=6) writeonly buffer Results { vec4 results[]; };
''' + functions + '''
void main() {
    vec3 p = points[gl_VertexID].xyz;
    results[gl_VertexID] = vec4(acceptedBeamExtent(p), sceneTransmittance(p), 0., 1.);
    gl_Position = vec4(0.,0.,0.,1.);
}
'''
    target = TransitionCapture(32, 32)
    program = 0
    buffers = []
    try:
        program = compile_program(vertex, '#version 460 core\nout vec4 colour;void main(){colour=vec4(0);}',
                                  label='production shaft world envelope')
        buffers = list(map(int, gl.glGenBuffers(2)))
        gl.glUseProgram(program)
        loc = lambda name: gl.glGetUniformLocation(program, name)
        assert loc('uRaySource') >= 0 and loc('uRayEnd') >= 0
        gl.glBindVertexArray(target.vao)
        gl.glEnable(gl.GL_RASTERIZER_DISCARD)

        def evaluate(points, *, source=(0., 0., 0.), end=(0., 0., -10.), eye=(0., 0., 0.), view=None):
            rows = np.ones((len(points), 4), dtype='f4')
            rows[:, :3] = points
            for binding, buffer, data in ((5, buffers[0], rows), (6, buffers[1], np.zeros_like(rows))):
                gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER, buffer)
                gl.glBufferData(gl.GL_SHADER_STORAGE_BUFFER, data.nbytes, data, gl.GL_DYNAMIC_READ)
                gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, binding, buffer)
            for name, xyz in (('uRaySource', source), ('uRayEnd', end), ('uEye', eye)):
                gl.glUniform3f(loc(name), *xyz)
            for name, value in (('uLightingScene',0.),('uParticleAtten',.05)):
                gl.glUniform1f(loc(name), value)
            gl.glUniformMatrix3fv(loc('uViewToWorld'), 1, False,
                                  np.eye(3, dtype='f4') if view is None else np.asarray(view, dtype='f4'))
            # Nonzero blockers/dust make normalize(0) or accidental attenuation
            # visible in the degenerate transmittance result.
            for name in ('uBlock0', 'uBlock1', 'uBlock2', 'uBlock3'):
                gl.glUniform4f(loc(name), 0., 0., 0., .4)
            gl.glDrawArrays(gl.GL_POINTS, 0, len(rows))
            gl.glMemoryBarrier(gl.GL_SHADER_STORAGE_BARRIER_BIT | gl.GL_BUFFER_UPDATE_BARRIER_BIT)
            result = np.empty_like(rows)
            gl.glGetNamedBufferSubData(buffers[1], 0, result.nbytes, result)
            assert np.isfinite(result).all()
            assert gl.glGetError() == gl.GL_NO_ERROR
            return result[:, :2]

        yield evaluate
    finally:
        gl.glDisable(gl.GL_RASTERIZER_DISCARD)
        for binding in (5, 6):
            gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, binding, 0)
        if buffers:
            gl.glDeleteBuffers(len(buffers), buffers)
        if program:
            gl.glDeleteProgram(program)
        target.close()


@pytest.mark.qt
def test_accepted_beam_does_not_reintroduce_the_rejected_lateral_cone(shaft_geometry):
    points=[(x,0.,-5.) for x in (-100.,-5.,0.,5.,100.)]
    assert shaft_geometry(points)[:,0]==pytest.approx([1.]*len(points),abs=2e-6)


@pytest.mark.qt
def test_accepted_source_end_envelope_is_rigid_and_camera_independent(shaft_geometry):
    source,end=np.array([0.,0.,0.]),np.array([0.,0.,-10.])
    points=np.array([[0.,0.,-5.],[2.,0.,-5.],[4.,0.,-5.],[0.,0.,-10.]])
    baseline=shaft_geometry(points)[:,0]
    rotation=np.array([[0.,0.,-1.],[0.,1.,0.],[1.,0.,0.]])
    offset=np.array([7.,-3.,11.])
    moved=shaft_geometry(points@rotation.T+offset,source=rotation@source+offset,
                         end=rotation@end+offset)[:,0]
    assert moved==pytest.approx(baseline,abs=2e-6,rel=2e-5)
    assert shaft_geometry(points,eye=(12.,-6.,3.),view=rotation)[:,0]==pytest.approx(baseline,abs=0.)


@pytest.mark.qt
@pytest.mark.parametrize('end', [(0., 0., -10.), (0., 0., 10.), (0., 0., -.002), (0., 0., -.001)])
def test_production_on_axis_retains_previous_axial_fades_including_reverse_and_short(shaft_geometry, end):
    length = float(np.linalg.norm(end))
    axis = np.asarray(end) / length
    distances = [-2., -1.8, -.3, 0., .6, 1.2, length - 2., length, length + 1.5, length + 2.]
    points = [axis * d for d in distances]
    expected = [_smooth(-1.8, 1.2, d) * (1. - _smooth(length - 2., length + 1.5, d)) for d in distances]
    assert shaft_geometry(points, end=end)[:, 0] == pytest.approx(expected, abs=2e-6, rel=2e-5)


@pytest.mark.qt
@pytest.mark.parametrize('end', [(0., 0., 0.), (0., 0., -.0005)])
def test_production_degenerate_segment_emits_nothing_and_has_neutral_transmittance(shaft_geometry, end):
    result = shaft_geometry([(0., 0., 0.), (0., 0., -1.), (3., 4., 5.)], end=end)
    assert result[:, 0] == pytest.approx([0.] * 3, abs=0.)
    assert result[:, 1] == pytest.approx([1.] * 3, abs=0.)


@pytest.mark.qt
@pytest.mark.parametrize('light_type', ['Sunlit Surface', 'Deep Light'])
def test_actual_scene_knobs_feed_mode_owned_source_and_end(shaft_geometry, light_type):
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_mode_settings import require_mode_settings
    from core.settings.visualizer_paths import admit_path, world_point
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs

    params = {entry.key: require_canonical_default('widgets.spotify_visualizer.' + entry.key)
              for entry in require_mode_settings('extruded_bubble').entries
              if entry.key.startswith('extruded_bubble_')}
    params.update(extruded_bubble_light_type=light_type,
                  extruded_bubble_light_direction=(-.8, .2, .25, .8, -.7, .9),
                  extruded_bubble_ray_path=(.4, -.5, -.2, .5, .6, -.6))
    knobs = scene_knobs(params)
    expected_source = knobs['light_source'] if light_type == 'Deep Light' else world_point(
        admit_path(params['extruded_bubble_ray_path'], [0., 1., 0., 0., -1., 0.], 'light')[:3])
    assert knobs['ray_source'] == pytest.approx(expected_source)
    assert knobs['ray_end'] == pytest.approx(world_point(
        admit_path(params['extruded_bubble_ray_path'], [0., 1., 0., 0., -1., 0.], 'light')[3:]))
    if light_type == 'Deep Light':
        assert knobs['ray_end'] != knobs['light_end']
    else:
        assert knobs['ray_source'] != knobs['light_source']
    source, end = np.asarray(knobs['ray_source']), np.asarray(knobs['ray_end'])
    points = [source, (source + end) * .5, end, source + np.array([100., 100., 100.])]
    actual = shaft_geometry(points,source=source,end=end)[:,0]
    expected = [_extent(p,source,end) for p in points]
    assert actual == pytest.approx(expected, abs=2e-6, rel=2e-5)
