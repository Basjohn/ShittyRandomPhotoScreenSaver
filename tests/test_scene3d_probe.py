"""The scene probe captures the scene all round a point into a cube that reads back, in every direction, the
light the scene put there; it hands back the caller's GL state and allocates once.

Offscreen GL through the transition capture harness; no window is shown.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.quick.render.gl_resources import compile_program
from rendering.quick.scene3d.probe import (SCENE3D_PROBE_GLSL, SceneProbe, scene3d_probe_face_of,
                                           scene3d_probe_face_rotation)
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

_FULL = """#version 460 core
out vec2 vNdc;
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    vNdc = p * 2.0 - 1.0;
    gl_Position = vec4(vNdc, 0.0, 1.0);
}
"""
# The scene: every direction's own value (direction * 0.5 + 0.5), from the face's rotation.
_SCENE = """#version 460 core
in vec2 vNdc;
out vec4 FragColor;
uniform mat3 uWorldToFace;
void main() {
    vec3 world = transpose(uWorldToFace) * normalize(vec3(vNdc, -1.0));
    FragColor = vec4(world * 0.5 + 0.5, 1.0);
}
"""
_READ = """#version 460 core
out vec4 FragColor;
uniform samplerCube uProbe;
uniform vec3 uDirections[16];
uniform float uBlur;
uniform float uLevels;
""" + SCENE3D_PROBE_GLSL + """
void main() {
    int i = int(gl_FragCoord.x);
    FragColor = vec4(sceneProbe(uProbe, normalize(uDirections[i]), uBlur, uLevels), 1.0);
}
"""

_DIRECTIONS = [(1, 0.2, -0.1), (-1, 0.3, 0.4), (0.1, 1, 0.2), (0.2, -1, -0.3), (0.3, 0.1, 1), (-0.2, 0.1, -1),
               (1, 1, 1), (-1, -1, 1), (0.7, -0.2, -0.7), (-0.5, 0.8, -0.3), (0.0, 0.0, -1.0), (0.9, 0.1, 0.05),
               (0.05, 0.95, -0.1), (-0.6, -0.6, -0.5), (0.4, -0.9, 0.1), (-0.95, 0.05, -0.2)]


@pytest.fixture
def capture(qt_app):
    result = TransitionCapture(64, 64)
    yield result
    result.close()


def _capture_directions(probe: SceneProbe, vao: int) -> None:
    program = compile_program(_FULL, _SCENE, label="probe test scene")

    def draw(face, world_to_face, projection):
        gl.glUseProgram(program)
        gl.glUniformMatrix3fv(gl.glGetUniformLocation(program, "uWorldToFace"), 1, gl.GL_TRUE, world_to_face)
        gl.glBindVertexArray(vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)

    probe.capture(draw)


def _read_directions(capture, probe: SceneProbe, blur: float) -> np.ndarray:
    program = compile_program(_FULL, _READ, label="probe test read")
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
    gl.glViewport(0, 0, 64, 64)
    gl.glUseProgram(program)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, probe.texture)
    gl.glUniform1i(gl.glGetUniformLocation(program, "uProbe"), 0)
    flat = [v for d in _DIRECTIONS for v in d]
    gl.glUniform3fv(gl.glGetUniformLocation(program, "uDirections"), len(_DIRECTIONS), flat)
    gl.glUniform1f(gl.glGetUniformLocation(program, "uBlur"), blur)
    gl.glUniform1f(gl.glGetUniformLocation(program, "uLevels"), probe.levels)
    gl.glBindVertexArray(capture.vao)
    gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, 0)
    raw = gl.glReadPixels(0, 0, len(_DIRECTIONS), 1, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    return np.frombuffer(bytes(raw), dtype=np.uint8).reshape(len(_DIRECTIONS), 4)[:, :3] / 255.0


def test_face_rotations_follow_the_cube_map_convention():
    for face in range(6):
        rows = scene3d_probe_face_rotation(face)
        right, up, back = rows[0:3], rows[3:6], rows[6:9]
        forward = tuple(-v for v in back)
        assert scene3d_probe_face_of(forward) == face
        # Orthonormal and right-handed (right x up = back).
        cross = (right[1] * up[2] - right[2] * up[1], right[2] * up[0] - right[0] * up[2],
                 right[0] * up[1] - right[1] * up[0])
        assert np.allclose(cross, back)


def test_every_direction_reads_back_the_light_the_scene_put_there(capture):
    probe = SceneProbe("probe test", 64)
    try:
        _capture_directions(probe, capture.vao)
        got = _read_directions(capture, probe, 0.0)
        expected = np.array([np.array(d) / np.linalg.norm(d) * 0.5 + 0.5 for d in _DIRECTIONS])
        assert np.abs(got - expected).max() < 0.03
        # Negative control: a probe face put upside down would read the mirrored direction.
        mirrored = expected.copy()
        mirrored[:, 1] = 1.0 - mirrored[:, 1]
        assert np.abs(got - mirrored).max() > 0.2
    finally:
        probe.release()


def test_blur_is_a_smooth_filter_across_faces_and_full_blur_is_the_hemisphere(capture):
    probe = SceneProbe("probe blur test", 64)
    try:
        _capture_directions(probe, capture.vao)
        unit = np.array([np.array(d) / np.linalg.norm(d) for d in _DIRECTIONS])
        for blur in (0.5, 1.0):
            got = _read_directions(capture, probe, blur)
            # A rotation-invariant filter of the direction field keeps each value along its own direction, scaled
            # the same everywhere; GL's per-face mipmaps would hand every direction on a face that face's average.
            scale = np.einsum("ij,ij->i", got - 0.5, unit) / 0.5
            residual = (got - 0.5) - 0.5 * scale[:, None] * unit
            assert np.abs(residual).max() < 0.06, blur
            assert scale.std() < 0.06, blur
        assert 0.2 < scale.mean() < 0.8      # the hemisphere's average direction, shortened
    finally:
        probe.release()


def test_capture_hands_back_state_and_allocates_once(capture):
    probe = SceneProbe("probe state test", 32)
    try:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
        gl.glViewport(3, 4, 50, 40)
        gl.glEnable(gl.GL_SCISSOR_TEST)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glClearColor(0.25, 0.5, 0.75, 1.0)
        _capture_directions(probe, capture.vao)
        names = (probe.texture, probe._fbo, probe._depth)
        _capture_directions(probe, capture.vao)
        assert (probe.texture, probe._fbo, probe._depth) == names
        assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) == capture.fbo
        assert [int(v) for v in gl.glGetIntegerv(gl.GL_VIEWPORT)] == [3, 4, 50, 40]
        assert gl.glIsEnabled(gl.GL_SCISSOR_TEST) and not gl.glIsEnabled(gl.GL_DEPTH_TEST)
        assert not bool(gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK))
        assert np.allclose(gl.glGetFloatv(gl.GL_COLOR_CLEAR_VALUE), (0.25, 0.5, 0.75, 1.0))
        assert probe.levels == int(math.log2(32)) + 1
    finally:
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glDepthMask(gl.GL_TRUE)
        probe.release()
    assert not probe.has_resources()
