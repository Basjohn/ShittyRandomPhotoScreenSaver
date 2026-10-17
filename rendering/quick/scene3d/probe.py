"""Scene probe: the scene itself, rendered all round one point into an HDR cube, for reflection and refraction.

Glass, water and bubbles look real only when they show the scene they sit in: the light and its glow, the beams,
lit dust and specks, the other bubbles. A consumer that wants that captures its scene into a ``SceneProbe`` once
per frame (or less often) and samples it in its shading with ``SCENE3D_PROBE_GLSL``:

* ``SceneProbe(label, size)``: one RGBA16F cube (``size`` px per face, a full mip chain) and its depth buffer.
* ``capture(draw, near, far)``: renders the six faces. For each face ``draw(face, world_to_face, projection)``
  is called with the face's 3x3 world-to-view rotation (row-major tuple of 9, the eye at the probe's origin looking
  down -z, as every scene3d view is) and a 90-degree column-major 4x4 projection; the callback draws its scene
  translated by the probe's origin. Depth is cleared and tested per face. The prior framebuffer, viewport, scissor,
  clear colour, depth test, depth mask, blend, program, vertex array and unit 0's cube binding come back.
* Then every mip level is pre-filtered from the one above over a cone of directions (32 taps, Gaussian, sampled
  across face edges), the cone about two of that level's texels wide, so the top level is the hemisphere round each
  direction. Blurred lookups (rough glass, defocus) read a smooth scene; GL's own mipmaps average each face alone and
  read as blocks.
* ``texture``: the cube texture, sampled seamlessly across faces where the driver supports it per texture.
* GLSL ``sceneProbe(probe, direction, blur, levels)``: the scene's light along a world direction; ``blur`` 0..1
  walks the mip chain (0 sharp, 1 the whole cube averaged); ``levels`` is ``SceneProbe.levels``.

CPU mirrors ``scene3d_probe_face_rotation`` and ``scene3d_probe_face_of`` let tests check face orientation against
GL's cube-map convention (+X, -X, +Y, -Y, +Z, -Z; each face's right = forward x up).

Nothing is allocated per frame after the first capture; ``release`` drops the cube, depth and framebuffer.
"""
from __future__ import annotations

import ctypes
import math

from OpenGL import GL as gl

from rendering.quick import gl_query
from rendering.quick.render.gl_resources import compile_program

# (forward, up) per face in GL's cube-map order and convention.
_FACES = (
    ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0)),
    ((-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)),
    ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    ((0.0, -1.0, 0.0), (0.0, 0.0, -1.0)),
    ((0.0, 0.0, 1.0), (0.0, -1.0, 0.0)),
    ((0.0, 0.0, -1.0), (0.0, -1.0, 0.0)),
)

_PREFILTER_VERTEX = """#version 460 core
out vec2 vNdc;
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    vNdc = p * 2.0 - 1.0;
    gl_Position = vec4(vNdc, 0.0, 1.0);
}
"""
_PREFILTER_FRAGMENT = """#version 460 core
in vec2 vNdc;
out vec4 FragColor;
uniform samplerCube uSource;
uniform mat3 uWorldToFace;
uniform float uCone;        // half-angle of the filter cone, radians
uniform float uSourceLod;
void main() {
    vec3 axis = transpose(uWorldToFace) * normalize(vec3(vNdc, -1.0));
    vec3 helper = abs(axis.y) < 0.99 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
    vec3 u = normalize(cross(helper, axis));
    vec3 v = cross(axis, u);
    float sigma = max(uCone * 0.5, 1e-4);
    vec3 sum = vec3(0.0);
    float weights = 0.0;
    for (int i = 0; i < 32; ++i) {
        float cosTheta = 1.0 - (float(i) + 0.5) / 32.0 * (1.0 - cos(uCone));
        float theta = acos(cosTheta);
        float phi = float(i) * 2.39996323;
        vec3 d = axis * cosTheta + (u * cos(phi) + v * sin(phi)) * sin(theta);
        float w = exp(-theta * theta / (2.0 * sigma * sigma));
        sum += textureLod(uSource, d, uSourceLod).rgb * w;
        weights += w;
    }
    FragColor = vec4(sum / weights, 1.0);
}
"""

SCENE3D_PROBE_GLSL = """
#ifndef SCENE3D_PROBE_GLSL
#define SCENE3D_PROBE_GLSL
vec3 sceneProbe(samplerCube probe, vec3 direction, float blur, float levels) {
    return textureLod(probe, direction, clamp(blur, 0.0, 1.0) * max(levels - 1.0, 0.0)).rgb;
}
#endif
"""


def _cross(a, b):
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def scene3d_probe_face_rotation(face: int) -> tuple[float, ...]:
    """The face's world-to-view rotation, row-major: rows right, up, -forward."""
    forward, up = _FACES[face]
    right = _cross(forward, up)
    back = tuple(-v for v in forward)
    return (*right, *up, *back)


def scene3d_probe_face_of(direction) -> int:
    """The cube face a world direction falls on (GL's major-axis rule)."""
    x, y, z = direction
    ax, ay, az = abs(x), abs(y), abs(z)
    if ax >= ay and ax >= az:
        return 0 if x > 0 else 1
    if ay >= az:
        return 2 if y > 0 else 3
    return 4 if z > 0 else 5


def scene3d_probe_projection(near: float, far: float) -> tuple[float, ...]:
    """A 90-degree square perspective projection, column-major."""
    return (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, (far + near) / (near - far), -1.0,
            0.0, 0.0, 2.0 * far * near / (near - far), 0.0)


class SceneProbe:
    """One HDR cube of the scene round a point, with a full mip chain."""

    def __init__(self, label: str, size: int = 256) -> None:
        self.label = label
        self.size = int(size)
        self.levels = int(math.log2(self.size)) + 1
        self._texture = 0
        self._depth = 0
        self._fbo = 0
        self._program = 0
        self._vao = 0

    @property
    def texture(self) -> int:
        return self._texture

    def has_resources(self) -> bool:
        return bool(self._texture or self._depth or self._fbo or self._program or self._vao)

    def _allocate(self) -> None:
        texture = gl.glGenTextures(1)
        self._texture = int(texture if not hasattr(texture, "__len__") else texture[0])
        gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, self._texture)
        gl.glTexStorage2D(gl.GL_TEXTURE_CUBE_MAP, self.levels, gl.GL_RGBA16F, self.size, self.size)
        gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T, gl.GL_TEXTURE_WRAP_R):
            gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, wrap, gl.GL_CLAMP_TO_EDGE)
        try:   # ARB_seamless_cubemap_per_texture: filter across face edges without global state
            gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_CUBE_MAP_SEAMLESS, gl.GL_TRUE)
        except Exception:
            pass
        gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, 0)
        # Created (not merely named) so they can be set up without binding over the caller's targets.
        name = (ctypes.c_uint * 1)()
        gl.glCreateRenderbuffers(1, name)
        self._depth = int(name[0])
        gl.glNamedRenderbufferStorage(self._depth, gl.GL_DEPTH_COMPONENT32F, self.size, self.size)
        gl.glCreateFramebuffers(1, name)
        self._fbo = int(name[0])
        if not (self._depth and self._fbo):
            raise RuntimeError(f"{self.label}: probe allocation failed")
        gl.glNamedFramebufferRenderbuffer(self._fbo, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER, self._depth)
        gl.glCreateVertexArrays(1, name)
        self._vao = int(name[0])
        self._program = compile_program(_PREFILTER_VERTEX, _PREFILTER_FRAGMENT, label=f"{self.label} prefilter")

    def _prefilter(self) -> None:
        program = self._program
        gl.glUseProgram(program)
        gl.glBindVertexArray(self._vao)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_BLEND)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, self._texture)
        gl.glUniform1i(gl.glGetUniformLocation(program, "uSource"), 0)
        rotation, cone, lod = (gl.glGetUniformLocation(program, name) for name in ("uWorldToFace", "uCone", "uSourceLod"))
        try:
            for level in range(1, self.levels):
                side = max(self.size >> level, 1)
                # Sample only the level above while this one is written (never a feedback loop).
                gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_BASE_LEVEL, level - 1)
                gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_MAX_LEVEL, level - 1)
                gl.glUniform1f(cone, min(2.2 * (math.pi / 2.0) / side, math.pi / 2.0))
                gl.glUniform1f(lod, float(level - 1))
                gl.glViewport(0, 0, side, side)
                for face in range(6):
                    gl.glNamedFramebufferTextureLayer(self._fbo, gl.GL_COLOR_ATTACHMENT0, self._texture, level, face)
                    gl.glUniformMatrix3fv(rotation, 1, gl.GL_TRUE, scene3d_probe_face_rotation(face))
                    gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        finally:
            gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_BASE_LEVEL, 0)
            gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_MAX_LEVEL, self.levels - 1)

    def capture(self, draw, near: float = 0.05, far: float = 200.0) -> None:
        if not self._texture:
            self._allocate()
        prior_fbo = gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING)
        prior_viewport = gl_query.get_ints(gl.GL_VIEWPORT, 4)
        scissor = gl_query.is_enabled(gl.GL_SCISSOR_TEST)
        depth_test = gl_query.is_enabled(gl.GL_DEPTH_TEST)
        depth_mask = bool(gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK))
        clear_colour = [float(v) for v in gl.glGetFloatv(gl.GL_COLOR_CLEAR_VALUE)]
        blend = gl_query.is_enabled(gl.GL_BLEND)
        prior_program = gl_query.get_int(gl.GL_CURRENT_PROGRAM)
        prior_vao = gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING)
        prior_active = gl_query.get_int(gl.GL_ACTIVE_TEXTURE)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        prior_cube = gl_query.get_int(gl.GL_TEXTURE_BINDING_CUBE_MAP)
        projection = scene3d_probe_projection(near, far)
        try:
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._fbo)
            gl.glViewport(0, 0, self.size, self.size)
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glClearColor(0.0, 0.0, 0.0, 1.0)
            for face in range(6):
                gl.glNamedFramebufferTextureLayer(self._fbo, gl.GL_COLOR_ATTACHMENT0, self._texture, 0, face)
                gl.glNamedFramebufferDrawBuffer(self._fbo, gl.GL_COLOR_ATTACHMENT0)
                if gl.glCheckNamedFramebufferStatus(self._fbo, gl.GL_DRAW_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                    raise RuntimeError(f"{self.label}: probe face {face} incomplete")
                gl.glEnable(gl.GL_DEPTH_TEST)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
                draw(face, scene3d_probe_face_rotation(face), projection)
            self._prefilter()
        finally:
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, prior_fbo)
            gl.glViewport(*prior_viewport)
            (gl.glEnable if scissor else gl.glDisable)(gl.GL_SCISSOR_TEST)
            (gl.glEnable if depth_test else gl.glDisable)(gl.GL_DEPTH_TEST)
            gl.glDepthMask(gl.GL_TRUE if depth_mask else gl.GL_FALSE)
            gl.glClearColor(*clear_colour)
            (gl.glEnable if blend else gl.glDisable)(gl.GL_BLEND)
            gl.glUseProgram(prior_program)
            gl.glBindVertexArray(prior_vao)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, prior_cube)
            gl.glActiveTexture(prior_active)

    def release(self) -> None:
        if self._fbo:
            gl.glDeleteFramebuffers(1, [self._fbo])
        if self._depth:
            gl.glDeleteRenderbuffers(1, [self._depth])
        if self._texture:
            gl.glDeleteTextures(1, [self._texture])
        if self._vao:
            gl.glDeleteVertexArrays(1, [self._vao])
        if self._program:
            gl.glDeleteProgram(self._program)
        self._texture = self._depth = self._fbo = self._program = self._vao = 0


__all__ = ["SCENE3D_PROBE_GLSL", "SceneProbe", "scene3d_probe_face_of", "scene3d_probe_face_rotation",
           "scene3d_probe_projection"]
