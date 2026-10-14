"""Bounded heightfield volume scattering and terrain-light occlusion on real GL."""
from __future__ import annotations

import math

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs.heightfield import heightfield_surface_bytes, normalize_heightfield, sample_heightfield
from rendering.gl_programs.heightfield_volume_glsl import (
    HEIGHTFIELD_VOLUME_GLSL,
    HEIGHTFIELD_VOLUME_MAX_STEPS,
    HEIGHTFIELD_VOLUME_QUALITY_STEPS,
)
from rendering.quick.scene3d.heightfield import HeightfieldTexture
from tools.transition_contact_sheet import TransitionCapture


pytestmark = pytest.mark.qt

_VERTEX = """#version 460 core
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""


def _terrain(*, ridge: bool):
    size = 5
    heights = [0.0] * (size * size)
    if ridge:
        heights[2 * size:3 * size] = [1.0] * size
    return normalize_heightfield({"version": 1, "size": size, "heights": heights})


def _cpu_light_occluded(terrain, point, body, half_width, depth, height_scale):
    """Four-tap reference matching the bounded GLSL light-ray blocker test."""
    for tap in range(1, 5):
        t = tap / 5.0
        sample_x = point[0] + (body[0] - point[0]) * t
        sample_y = point[1] + (body[1] - point[1]) * t
        sample_z = point[2] + (body[2] - point[2]) * t
        if not (-half_width <= sample_x <= half_width and -depth <= sample_z <= 0.0):
            continue
        uv = (sample_x / (2.0 * half_width) + 0.5, -sample_z / depth)
        base = sample_heightfield(terrain, *uv)
        if base != 0.0 and sample_y <= base * max(height_scale, 0.0) * 1.25:
            return True
    return False


def _volume_probe_fragment() -> str:
    return f"""#version 460 core
out vec4 FragColor;
uniform sampler2D uHeightfield;
uniform int uHeightfieldSize;
uniform vec3 uBodyWorld;
uniform vec3 uRayOrigin;
uniform vec3 uRayDirection;
uniform float uHalfWidth;
uniform float uDepth;
uniform float uHeightScale;
uniform vec4 uBodyColour;
uniform float uDensity;
uniform float uPhaseAnisotropy;
uniform float uStrength;
uniform int uSteps;
{HEIGHTFIELD_VOLUME_GLSL}
void main() {{
    FragColor = sceneHeightfieldVolume(
        uBodyWorld, uRayOrigin, uRayDirection, uHalfWidth, uDepth, uHeightScale,
        uHeightfield, uHeightfieldSize, uBodyColour, uDensity,
        uPhaseAnisotropy, uStrength, uSteps);
}}
"""


def test_cpu_four_tap_occlusion_uses_land_and_leaves_exact_zero_water_open():
    water = _terrain(ridge=False)
    ridge = _terrain(ridge=True)
    point = (0.0, 0.5, -0.1)
    body = (0.0, 1.5, -2.4)
    assert not _cpu_light_occluded(water, point, body, 1.0, 2.4, 1.5)
    assert _cpu_light_occluded(ridge, point, body, 1.0, 2.4, 1.5)
    assert sample_heightfield(water, 0.5, 0.5) == 0.0
    assert sample_heightfield(ridge, 0.5, 0.5) == 1.0
    from rendering.gl_programs.scene3d import SCENE3D_DETAIL_NAMES
    assert tuple(HEIGHTFIELD_VOLUME_QUALITY_STEPS) == SCENE3D_DETAIL_NAMES
    budgets=tuple(HEIGHTFIELD_VOLUME_QUALITY_STEPS.values())
    assert list(budgets)==sorted(budgets,reverse=True)
    assert 4<=min(budgets)<=max(budgets)<=HEIGHTFIELD_VOLUME_MAX_STEPS


def test_gl_volume_is_premultiplied_bounded_and_occluded_by_raised_land(qt_app):
    capture = TransitionCapture(16, 16)
    texture = HeightfieldTexture("heightfield volume probe", components=2)
    from rendering.quick.render.gl_resources import compile_program

    program = compile_program(_VERTEX, _volume_probe_fragment(), label="heightfield volume probe")
    vao = int(gl.glGenVertexArrays(1))
    colour = int(gl.glGenTextures(1))
    fbo = int(gl.glGenFramebuffers(1))
    terrain_water = _terrain(ridge=False)
    terrain_ridge = _terrain(ridge=True)
    body = (0.0, 1.5, -2.4)
    origin = (0.0, 0.5, 0.1)
    direction = (0.0, 0.0, -1.0)
    body_colour = (0.95, 0.45, 0.20, 1.0)

    def draw(terrain, *, density=0.8, phase=0.4, strength=0.7, steps=12,
             origin_y=None, body_y=None):
        texture.ensure(terrain["size"], heightfield_surface_bytes(terrain))
        gl.glUseProgram(program)
        ray_origin = (origin[0], origin[1] if origin_y is None else origin_y, origin[2])
        body_position = (body[0], body[1] if body_y is None else body_y, body[2])
        for name, value in (("uBodyWorld", body_position), ("uRayOrigin", ray_origin),
                            ("uRayDirection", direction)):
            gl.glUniform3f(gl.glGetUniformLocation(program, name), *value)
        gl.glUniform1f(gl.glGetUniformLocation(program, "uHalfWidth"), 1.0)
        gl.glUniform1f(gl.glGetUniformLocation(program, "uDepth"), 2.4)
        gl.glUniform1f(gl.glGetUniformLocation(program, "uHeightScale"), 1.5)
        gl.glUniform4f(gl.glGetUniformLocation(program, "uBodyColour"), *body_colour)
        gl.glUniform1f(gl.glGetUniformLocation(program, "uDensity"), density)
        gl.glUniform1f(gl.glGetUniformLocation(program, "uPhaseAnisotropy"), phase)
        gl.glUniform1f(gl.glGetUniformLocation(program, "uStrength"), strength)
        gl.glUniform1i(gl.glGetUniformLocation(program, "uSteps"), steps)
        gl.glUniform1i(gl.glGetUniformLocation(program, "uHeightfieldSize"), terrain["size"])
        gl.glUniform1i(gl.glGetUniformLocation(program, "uHeightfield"), 0)
        gl.glBindVertexArray(vao)
        with texture.bound(0):
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        raw = gl.glReadPixels(0, 0, 1, 1, gl.GL_RGBA, gl.GL_FLOAT)
        return np.frombuffer(bytes(raw), dtype=np.float32).copy()

    try:
        gl.glBindTexture(gl.GL_TEXTURE_2D, colour)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, 1, 1, 0,
                        gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                                  gl.GL_TEXTURE_2D, colour, 0)
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
        gl.glViewport(0, 0, 1, 1)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_BLEND)

        water = draw(terrain_water)
        assert np.isfinite(water).all()
        assert 0.0 < water[3] < 1.0
        assert np.all(water[:3] >= 0.0) and np.all(water[:3] <= water[3])
        assert water[1] / water[0] == pytest.approx(body_colour[1] / body_colour[0], abs=1e-6)
        assert water[2] / water[0] == pytest.approx(body_colour[2] / body_colour[0], abs=1e-6)

        near_water_point = (0.0, 0.08, -0.1)
        higher_air_point = (0.0, 0.5, -0.1)
        near_water_body = (0.0, 1.08, -2.4)
        higher_air_body = (0.0, 1.5, -2.4)
        # Translate the same light/view path vertically over exact-zero water;
        # distance, phase, and opaque terrain blockers stay equivalent.
        assert not _cpu_light_occluded(
            terrain_water, near_water_point, near_water_body, 1.0, 2.4, 1.5)
        assert not _cpu_light_occluded(
            terrain_water, higher_air_point, higher_air_body, 1.0, 2.4, 1.5)
        near_water = draw(terrain_water, origin_y=near_water_point[1], body_y=near_water_body[1])
        higher_air = draw(terrain_water, origin_y=higher_air_point[1], body_y=higher_air_body[1])
        assert np.isfinite(near_water).all() and np.isfinite(higher_air).all()
        assert 0.0 < higher_air[3] < near_water[3]

        weaker_density = draw(terrain_water, density=0.4)
        weaker_phase = draw(terrain_water, phase=-0.4)
        assert 0.0 <= weaker_density[3] < water[3]
        assert 0.0 <= weaker_phase[3] < water[3]
        assert np.allclose(draw(terrain_water, strength=0.0), np.zeros(4, dtype=np.float32), atol=0.0)
        assert np.allclose(draw(terrain_water, steps=128), water, atol=2e-6, rtol=0.0)

        raised = draw(terrain_ridge)
        assert np.isfinite(raised).all()
        assert 0.0 <= raised[3] < water[3] * 0.1
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures([colour])
        gl.glDeleteVertexArrays(1, [vao])
        gl.glDeleteProgram(program)
        texture.release()
        capture.close()
