"""S3D-5 planar reflection: registration under a moving eye in both projections, state and ownership (offscreen)."""
import ctypes

import numpy as np
import pytest

from rendering.gl_error_policy import disable_per_call_gl_error_checking
disable_per_call_gl_error_checking()
from OpenGL import GL as gl
from core.settings.framed_camera import orthographic_matrix, perspective_matrix
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


@pytest.mark.parametrize('projection,eye', [('orthographic', (0., 2., 6.)), ('orthographic', (3., 1.5, 5.)),
                                            ('perspective', (0., 2., 6.)), ('perspective', (-2.5, 2.5, 5.))])
def test_floor_shows_each_object_where_its_mirror_image_projects(gl_scene, projection, eye):
    target, flat, floor, vbo, reflection = gl_scene
    view = look_at(eye)
    proj = (np.asarray(orthographic_matrix((2., 1.5), .1, 50.)) if projection == 'orthographic'
            else np.asarray(perspective_matrix((.6, .45), .1, 50.))).reshape(4, 4, order='F')
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
