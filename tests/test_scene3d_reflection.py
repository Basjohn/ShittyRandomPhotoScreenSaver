"""S3D-5 planar reflection: registration under a moving Perspective eye, state and ownership (offscreen)."""
import ctypes

import numpy as np
import pytest

from rendering.gl_error_policy import disable_per_call_gl_error_checking
disable_per_call_gl_error_checking()
from OpenGL import GL as gl
from core.settings.framed_camera import perspective_matrix
from rendering.gl_programs.reflection import PLANAR_REFLECTION_GLSL, mirror_view
from rendering.quick import gl_query
from rendering.quick.render.gl_resources import compile_program
from rendering.quick.scene3d.reflection import PlanarReflection
from tools.labs.render_target import OffscreenRenderTarget

pytestmark = pytest.mark.qt
W, H = 200, 150
QUADS = {'red': ((.5, .5, 0.), (1., 1., 0.), (1., 0., 0.)), 'green': ((-1., .2, -.5), (-.5, .6, -.5), (0., 1., 0.))}
_VERTEX = """#version 460 core
layout(location=0) in vec3 aPosition;
uniform mat4 uMvp;
out vec3 vWorld;
void main() { vWorld=aPosition; gl_Position=uMvp*vec4(aPosition,1.0); }
"""
_FLAT = """#version 460 core
uniform vec3 uColour;
out vec4 FragColor;
void main() { FragColor=vec4(uColour,1.0); }
"""
_FLOOR = "#version 460 core\nout vec4 FragColor;\nuniform vec2 uViewport;\n" + PLANAR_REFLECTION_GLSL + """
void main() { FragColor=vec4(planarReflection(gl_FragCoord.xy/uViewport,vec2(0.0),0.0),1.0); }
"""


def look_at(eye, target=(0., 0., 0.)):
    eye, target = np.asarray(eye, float), np.asarray(target, float)
    forward = (target - eye)/np.linalg.norm(target - eye)
    side = np.cross(forward, (0., 1., 0.)); side /= np.linalg.norm(side)
    up = np.cross(side, forward)
    view = np.identity(4)
    view[0, :3], view[1, :3], view[2, :3] = side, up, -forward
    view[:3, 3] = -view[:3, :3] @ eye
    return view


def quad_vertices(low, high):
    (x0, y0, z), (x1, y1, _) = low, high
    return np.array([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y0, z), (x1, y1, z), (x0, y1, z)], np.float32)


@pytest.fixture
def gl_scene(qt_app):
    target = OffscreenRenderTarget(W, H)
    flat, floor = compile_program(_VERTEX, _FLAT, label='flat'), compile_program(_VERTEX, _FLOOR, label='floor')
    vao, vbo = (ctypes.c_uint*1)(), (ctypes.c_uint*1)()
    gl.glGenVertexArrays(1, vao); gl.glGenBuffers(1, vbo)
    gl.glBindVertexArray(vao[0]); gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo[0])
    gl.glEnableVertexAttribArray(0); gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, None)
    reflection = PlanarReflection('reflection test')
    yield target, flat, floor, vbo[0], reflection
    with target.current():
        reflection.release()
        gl.glDeleteBuffers(1, vbo); gl.glDeleteVertexArrays(1, vao)
        gl.glDeleteProgram(flat); gl.glDeleteProgram(floor)
    target.close()


def draw(program, vbo, vertices, mvp, colour=None):
    gl.glUseProgram(program)
    gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_STREAM_DRAW)
    gl.glUniformMatrix4fv(gl.glGetUniformLocation(program, 'uMvp'), 1, gl.GL_FALSE, np.asarray(mvp.T, np.float32))
    if colour is not None:
        gl.glUniform3f(gl.glGetUniformLocation(program, 'uColour'), *colour)
    gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(vertices))


@pytest.mark.parametrize('eye', [(0., 2., 6.), (-2.5, 2.5, 5.)])
def test_floor_shows_each_object_where_its_mirror_image_projects(gl_scene, eye):
    target, flat, floor, vbo, reflection = gl_scene
    view = look_at(eye)
    proj = np.asarray(perspective_matrix((.6, .45), .1, 50.)).reshape(4, 4, order='F')
    target.bind(clear=(0., 0., 0., 1.))
    framebuffer = gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING)
    reflection.begin(W//2, H//2)
    for low, high, colour in QUADS.values():
        draw(flat, vbo, quad_vertices(low, high), proj @ mirror_view(view, 0.), colour)
    reflection.end()
    assert gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING) == framebuffer
    assert tuple(gl_query.get_ints(gl.GL_VIEWPORT, 4)) == (0, 0, W, H)
    gl.glUseProgram(floor)
    gl.glUniform2f(gl.glGetUniformLocation(floor, 'uViewport'), W, H)
    gl.glUniform1i(gl.glGetUniformLocation(floor, 'uReflection'), 0)
    gl.glUniform4f(gl.glGetUniformLocation(floor, 'uReflectionLook'), 0., 0., 0., 0.)
    gl.glBindTextureUnit(0, reflection.texture)
    floor_quad = np.array([(-9, 0, -9), (9, 0, -9), (9, 0, 9), (-9, 0, -9), (9, 0, 9), (-9, 0, 9)], np.float32)
    draw(floor, vbo, floor_quad, proj @ view)
    pixels = target.read_rgba().astype(int)
    for name, (low, high, colour) in QUADS.items():
        centre = (np.asarray(low) + np.asarray(high))/2
        clip = proj @ view @ np.array((centre[0], -centre[1], centre[2], 1.))  # the mirror image below the floor
        px, py = int((clip[0]/clip[3] + 1)*W/2), int((1 - clip[1]/clip[3])*H/2)
        rgb = pixels[py - 1:py + 2, px - 1:px + 2, :3].mean((0, 1))
        channel = int(np.argmax(colour))
        assert rgb[channel] > 120 and rgb[channel] > 3*np.delete(rgb, channel).max(), (name, px, py, rgb)
    # Negative control: the reflection drawn with the unmirrored view lands somewhere else.
    reflection.begin(W//2, H//2)
    draw(flat, vbo, quad_vertices(*QUADS['red'][:2]), proj @ view, QUADS['red'][2])
    reflection.end()
    target.bind(clear=(0., 0., 0., 1.))
    gl.glBindTextureUnit(0, reflection.texture)
    draw(floor, vbo, floor_quad, proj @ view)
    wrong = target.read_rgba().astype(int)
    low, high, _ = QUADS['red']
    centre = (np.asarray(low) + np.asarray(high))/2
    clip = proj @ view @ np.array((centre[0], -centre[1], centre[2], 1.))
    px, py = int((clip[0]/clip[3] + 1)*W/2), int((1 - clip[1]/clip[3])*H/2)
    assert wrong[py, px, 0] < 60


def test_reflection_allocates_lazily_and_retires_in_its_own_context(gl_scene):
    target, _flat, _floor, _vbo, reflection = gl_scene
    assert not reflection.has_resources
    assert reflection.warm(64, 32) is False and reflection.warm(64, 32) is True
    assert reflection.size == (64, 32) and reflection.has_resources
    other = OffscreenRenderTarget(16, 16)
    try:
        with pytest.raises(RuntimeError, match='foreign'):
            reflection.begin(64, 32)
    finally:
        other.close()
    target.make_current()
    reflection.release()
    assert not reflection.has_resources
    reflection.release()


def test_rough_reflection_stretches_a_highlight_without_repeating_it(gl_scene):
    target,_flat,_floor,vbo,reflection=gl_scene
    # A single small HDR highlight exposes the old seven separated tap copies. Keep the actual reflection
    # owner and production sampling code; the input texture is an independent diagnostic fixture.
    reflection.begin(W,H)
    pixels=np.zeros((H,W,4),np.float32)
    pixels[H//2-2:H//2+2,W//2-2:W//2+2,:3]=8.
    gl.glTextureSubImage2D(reflection.texture,0,0,0,W,H,gl.GL_RGBA,gl.GL_FLOAT,pixels)
    reflection.end()
    fragment=_FLOOR.replace('vec2(0.0),0.0)','vec2(0.0),1.0)')
    program=compile_program(_VERTEX,fragment,label='stretched reflection')
    try:
        target.bind(clear=(0.,0.,0.,1.))
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glUseProgram(program)
        gl.glUniform2f(gl.glGetUniformLocation(program,'uViewport'),W,H)
        gl.glUniform1i(gl.glGetUniformLocation(program,'uReflection'),0)
        gl.glUniform4f(gl.glGetUniformLocation(program,'uReflectionLook'),.3,0.,0.,0.)
        gl.glBindTextureUnit(0,reflection.texture)
        draw(program,vbo,quad_vertices((-1.,-1.,0.),(1.,1.,0.)),np.identity(4))
        result=target.read_rgba()[:,:,0]
        # Segments are offset per pixel (against copy banding): judge the streak as the eye does, over 3 columns.
        rows=np.where(result[:,W//2-1:W//2+2].mean(1)>2)[0]
        columns=np.where(result[H//2,:]>2)[0]
        assert len(rows)>20 and len(columns)<len(rows)*.35
        # Copies leave gaps of many rows; the per-pixel segment offset only dithers single pixels.
        body=np.where(_streak_profile(result,W//2)>2)[0]
        assert len(body)>20 and np.diff(body).max()==1, body
    finally:
        gl.glDeleteProgram(program)


@pytest.mark.parametrize('scale', (1,2))
def test_gentle_gaussian_spreads_light_without_shifting_or_destroying_it(gl_scene,scale):
    target,_flat,program,vbo,reflection=gl_scene
    reflection.begin(W*scale,H*scale)
    pixels=np.zeros((H*scale,W*scale,4),np.float32)
    pixels[(H//2-2)*scale:(H//2+2)*scale,(W//2-2)*scale:(W//2+2)*scale,:3]=.4
    gl.glTextureSubImage2D(reflection.texture,0,0,0,W*scale,H*scale,gl.GL_RGBA,gl.GL_FLOAT,pixels)
    reflection.end()
    measurements=[]
    for sigma in (0.,1.5):
        target.bind(clear=(0.,0.,0.,1.))
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glUseProgram(program)
        gl.glUniform2f(gl.glGetUniformLocation(program,'uViewport'),W,H)
        gl.glUniform1i(gl.glGetUniformLocation(program,'uReflection'),0)
        gl.glUniform4f(gl.glGetUniformLocation(program,'uReflectionLook'),0.,0.,0.,sigma)
        gl.glBindTextureUnit(0,reflection.texture)
        draw(program,vbo,quad_vertices((-1.,-1.,0.),(1.,1.,0.)),np.identity(4))
        value=target.read_rgba()[:,:,0].astype(float)
        y,x=np.indices(value.shape)
        centre=np.array([(value*x).sum(),(value*y).sum()])/value.sum()
        variance=np.array([(value*(x-centre[0])**2).sum(),(value*(y-centre[1])**2).sum()])/value.sum()
        measurements.append((value.sum(),value.max(),centre,variance))
    sharp,soft=measurements
    assert soft[1]<sharp[1] and np.isclose(soft[0],sharp[0],rtol=.12)
    np.testing.assert_allclose(soft[2],sharp[2],atol=.15)
    assert np.all((soft[3]-sharp[3]>1.)&(soft[3]-sharp[3]<4.))
    assert abs(soft[3][0]-soft[3][1])<.5


def _streak_profile(result, column):
    """A streak's vertical profile as the eye integrates it: 3 columns by 5 rows. Long streaks offset their
    segments per pixel (against copy banding), which dithers single pixels near the detection threshold."""
    profile = result[:, column - 1:column + 2].astype(float).mean(1)
    return np.convolve(profile, np.ones(5)/5, mode='same')


def _receive(target, vbo, reflection, fragment, look, contact=(0., 0., 0., 0.)):
    program = compile_program(_VERTEX, fragment, label='receiver probe')
    try:
        target.bind(clear=(0., 0., 0., 1.))
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glUseProgram(program)
        gl.glUniform2f(gl.glGetUniformLocation(program, 'uViewport'), W, H)
        gl.glUniform1i(gl.glGetUniformLocation(program, 'uReflection'), 0)
        gl.glUniform4f(gl.glGetUniformLocation(program, 'uReflectionLook'), *look)
        gl.glUniform4f(gl.glGetUniformLocation(program, 'uReflectionContact'), *contact)
        gl.glBindTextureUnit(0, reflection.texture)
        draw(program, vbo, quad_vertices((-1., -1., 0.), (1., 1., 0.)), np.identity(4))
        return target.read_rgba()[:, :, 0].astype(int)
    finally:
        gl.glDeleteProgram(program)


def _upload(reflection, highlights):
    """Small HDR highlights at (row, column) with luminance-weighted world height in alpha."""
    reflection.begin(W, H)
    pixels = np.zeros((H, W, 4), np.float32)
    for row, column, height in highlights:
        pixels[row-2:row+2, column-2:column+2] = (8., 8., 8., 8.*height)
    gl.glTextureSubImage2D(reflection.texture, 0, 0, 0, W, H, gl.GL_RGBA, gl.GL_FLOAT, pixels)
    reflection.end()


def test_long_streak_stays_narrow_across_by_segmenting_the_footprint(gl_scene):
    # Hardware anisotropy integrates at most 16:1: one footprint as long as the streak coarsened the short axis
    # and washed neighbouring highlights together. Negative control: the same streak forced into one footprint.
    target, _flat, _floor, vbo, reflection = gl_scene
    _upload(reflection, [(H//2, W//2, 0.)])
    fragment = _FLOOR.replace('vec2(0.0),0.0)', 'vec2(0.0),1.0)')
    single = fragment.replace('int(clamp(ceil(2.0*streak*size.y/(16.0*span)),1.0,16.0))', '1')
    assert single != fragment
    width = {}
    for name, source in (('segmented', fragment), ('single', single)):
        result = _receive(target, vbo, reflection, source, (.4, 0., 0., 0.))
        lit = result > 2
        rows, columns = np.where(_streak_profile(result, W//2) > 2)[0], np.where(lit.any(0))[0]
        width[name] = len(columns)
        assert len(rows) > 40 and np.diff(rows).max() == 1, name
    # The single footprint also drifts sideways (its coarse mip's texel centres); the segments stay on the source.
    assert width['segmented'] <= 6 and width['single'] > 2*width['segmented'], width


def test_contact_hardening_spreads_reflections_with_the_height_of_their_light(gl_scene):
    # Light from just above the plane reflects crisply; the same light three units up spreads, mostly vertically.
    target, _flat, _floor, vbo, reflection = gl_scene
    low, high = (H//2, W//4, .1), (H//2, 3*W//4, 3.)
    _upload(reflection, [low, high])

    def extent(result, column):
        rows = np.where(result[:, column] > 2)[0]
        return len(rows), len(np.where(result[H//2, column-30:column+30] > 2)[0])
    off = _receive(target, vbo, reflection, _FLOOR, (0., 0., 0., 0.))
    on = _receive(target, vbo, reflection, _FLOOR, (0., 0., 0., 0.), contact=(0., .01, 6., 5.))
    assert extent(off, low[1]) == extent(off, high[1])  # without contact hardening height is ignored
    low_rows, low_columns = extent(on, low[1])
    high_rows, high_columns = extent(on, high[1])
    assert low_rows <= extent(off, low[1])[0] + 2
    assert high_rows > 3*low_rows and high_rows > 2*high_columns
