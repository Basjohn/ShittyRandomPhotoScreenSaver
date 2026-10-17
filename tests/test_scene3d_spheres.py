"""Sphere impostors (``rendering/gl_programs/scene3d_spheres.py``): the GLSL equals its CPU mirrors, and drawn spheres
match a CPU ray cast pixel for pixel: exact silhouettes, true depth where spheres interpenetrate, softened by blur.

Offscreen GL through the transition capture harness; no window is shown.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs import scene3d_spheres as spheres

pytestmark = pytest.mark.qt

WIDTH, HEIGHT = 320, 200
FOV = math.radians(50.0)
NEAR, FAR = 0.1, 100.0


def _projection() -> tuple[float, ...]:
    f = 1.0 / math.tan(FOV / 2)
    aspect = WIDTH / HEIGHT
    # Column-major perspective (OpenGL convention).
    return (f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (FAR + NEAR) / (NEAR - FAR), -1,
            0, 0, 2 * FAR * NEAR / (NEAR - FAR), 0)


_VERTEX = """#version 460 core
uniform mat4 uProjection;
uniform vec4 uSpheres[8];   // view-space centre, radius
uniform float uBlur[8];
out vec3 vView;
flat out int vId;
""" + spheres.SCENE3D_SPHERES_GLSL + """
void main() {
    vec2 corner = vec2(float(gl_VertexID & 1), float((gl_VertexID >> 1) & 1)) * 2.0 - 1.0;
    vId = gl_InstanceID;
    vView = sceneSphereCorner(uSpheres[vId].xyz, uSpheres[vId].w, uBlur[vId], corner);
    gl_Position = uProjection * vec4(vView, 1.0);
}
"""
_FRAGMENT = """#version 460 core
uniform mat4 uProjection;
uniform vec4 uSpheres[8];
uniform float uBlur[8];
uniform int uSoft;          // 1: write coverage; 0: binary id picture
in vec3 vView;
flat in int vId;
out vec4 FragColor;
""" + spheres.SCENE3D_SPHERES_GLSL + """
void main() {
    vec3 ray = normalize(vView);
    vec4 s = uSpheres[vId];
    float tNear, tFar;
    bool hit = sceneSphereRay(ray, s.xyz, s.w, tNear, tFar);
    float coverage = sceneSphereCoverage(ray, s.xyz, s.w, uBlur[vId]);
    if (uSoft == 0 && !hit) discard;
    if (uSoft == 1 && coverage <= 0.0) discard;
    float t = hit ? tNear : dot(s.xyz, ray);
    gl_FragDepth = sceneSphereDepth(ray * t, uProjection);
    FragColor = vec4(float(vId + 1) / 8.0, coverage, 0.0, 1.0);
}
"""


class _Scene:
    def __init__(self):
        from rendering.quick.render.gl_resources import compile_program
        from tools.transition_contact_sheet import TransitionCapture
        self.capture = TransitionCapture(WIDTH, HEIGHT)
        self.program = compile_program(_VERTEX, _FRAGMENT, label="sphere impostor test")
        self.depth = int(gl.glGenRenderbuffers(1))
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self.depth)
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, WIDTH, HEIGHT)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.capture.fbo)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER, self.depth)

    def draw(self, items, soft=False):
        assert self.capture.context.makeCurrent(self.capture.surface)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.capture.fbo)
        gl.glViewport(0, 0, WIDTH, HEIGHT)
        gl.glClearColor(0, 0, 0, 0)
        gl.glClearDepth(1.0)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glUseProgram(self.program)
        location = lambda name: gl.glGetUniformLocation(self.program, name)
        gl.glUniformMatrix4fv(location("uProjection"), 1, gl.GL_FALSE, _projection())
        flat = [value for centre, radius, _blur in items for value in (*centre, radius)]
        gl.glUniform4fv(location("uSpheres"), len(items), flat)
        gl.glUniform1fv(location("uBlur"), len(items), [blur for *_rest, blur in items])
        gl.glUniform1i(location("uSoft"), int(soft))
        gl.glBindVertexArray(self.capture.vao)
        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, len(items))
        gl.glDisable(gl.GL_DEPTH_TEST)
        raw = gl.glReadPixels(0, 0, WIDTH, HEIGHT, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        return np.frombuffer(bytes(raw), dtype=np.uint8).reshape(HEIGHT, WIDTH, 4)

    def close(self):
        assert self.capture.context.makeCurrent(self.capture.surface)
        gl.glDeleteProgram(self.program)
        gl.glDeleteRenderbuffers(1, [self.depth])
        self.capture.close()


@pytest.fixture
def scene(qt_app):
    result = _Scene()
    yield result
    result.close()


def _cpu_ids(items):
    """The nearest sphere at every pixel centre (0: none), by ray casting the same view."""
    t = math.tan(FOV / 2)
    ids = np.zeros((HEIGHT, WIDTH), dtype=np.int32)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            ndc = ((x + 0.5) / WIDTH * 2 - 1, (y + 0.5) / HEIGHT * 2 - 1)
            ray = spheres._normalize((ndc[0] * t * WIDTH / HEIGHT, ndc[1] * t, -1.0))
            best, nearest = 0, float("inf")
            for index, (centre, radius, _blur) in enumerate(items):
                hit, near, _far = spheres.scene3d_sphere_ray(ray, centre, radius)
                if hit and 0 < near < nearest:
                    best, nearest = index + 1, near
            ids[y, x] = best
    return ids


def test_drawn_spheres_match_a_ray_cast_including_where_they_interpenetrate(scene):
    items = [((-0.6, 0.1, -5.0), 1.0, 0.0), ((0.5, -0.1, -5.6), 1.1, 0.0),     # interpenetrating pair
             ((1.9, 0.9, -8.0), 0.25, 0.0), ((-2.2, -1.0, -4.0), 0.06, 0.0)]  # a small one, a tiny one
    pixels = scene.draw(items)
    gpu = np.rint(pixels[..., 0] / 255 * 8).astype(np.int32)
    cpu = _cpu_ids(items)
    covered = (gpu > 0) | (cpu > 0)
    assert covered.sum() > 5000
    assert (gpu != cpu)[covered].mean() < 0.01             # only edge pixels may disagree
    for index in range(1, len(items) + 1):
        assert (gpu == index).any(), f"sphere {index} drawn"
    # The far sphere of the pair shows where it is nearer: its surface wins on its own side of the intersection.
    assert (gpu == 2).sum() > 500 and (cpu == 2).sum() > 500


def test_silhouettes_are_exact_at_any_size_and_blur_softens_them(scene):
    for radius, depth in ((1.5, -4.0), (0.3, -6.0), (0.02, -3.0)):
        items = [((0.2, -0.1, depth), radius, 0.0)]
        covered = (scene.draw(items)[..., 0] > 0).sum()
        reference = (_cpu_ids(items) > 0).sum()
        assert abs(int(covered) - int(reference)) <= max(3, 0.01 * reference), (radius, covered, reference)
    sharp = scene.draw([((0.0, 0.0, -5.0), 1.0, 0.0)], soft=True)[..., 1]
    soft = scene.draw([((0.0, 0.0, -5.0), 1.0, 0.15)], soft=True)[..., 1]
    partial = lambda image: int(((image > 10) & (image < 245)).sum())
    assert partial(soft) > 4 * partial(sharp) > 0            # a wide soft edge, not a one-pixel one
    assert (soft > 0).sum() > (sharp > 0).sum()              # and reaching further out
