"""Shared heightfield texture contracts on an actual offscreen OpenGL context."""
from __future__ import annotations

import ctypes
import struct

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs.heightfield import (
    heightfield_bytes,
    heightfield_surface_bytes,
    normalize_heightfield,
    sample_heightfield,
    sample_heightfield_curve,
)
from rendering.gl_programs.heightfield_glsl import HEIGHTFIELD_GLSL, HEIGHTFIELD_WIRE_GLSL
from rendering.quick.scene3d import heightfield as texture_module
from rendering.quick.scene3d.heightfield import HeightfieldTexture
from tools.transition_contact_sheet import TransitionCapture


pytestmark = pytest.mark.qt

_VERTEX = """#version 460 core
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""


def _probe_fragment(width: int, height: int) -> str:
    return f"""#version 460 core
out vec4 FragColor;
uniform sampler2D uHeightfield;
uniform int uSize;
{HEIGHTFIELD_GLSL}
void main() {{
    vec2 uv = (gl_FragCoord.xy - vec2(0.5)) / vec2({width - 1}.0, {height - 1}.0);
    float h = sceneHeightfield(uHeightfield, uSize, uv);
    FragColor = vec4(h, sceneHeightfieldWater(h) ? 1.0 : 0.0, 0.0, 1.0);
}}
"""


def _draw_heightfield_probe(capture, texture: HeightfieldTexture, size: int, width: int, height: int):
    from rendering.quick.render.gl_resources import compile_program

    program = compile_program(_VERTEX, _probe_fragment(width, height), label="heightfield sampler probe")
    vao = int(gl.glGenVertexArrays(1))
    colour = int(gl.glGenTextures(1))
    fbo = int(gl.glGenFramebuffers(1))
    try:
        gl.glBindTexture(gl.GL_TEXTURE_2D, colour)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, width, height, 0,
                        gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                                  gl.GL_TEXTURE_2D, colour, 0)
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
        gl.glViewport(0, 0, width, height)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_BLEND)
        gl.glUseProgram(program)
        gl.glUniform1i(gl.glGetUniformLocation(program, "uSize"), size)
        gl.glUniform1i(gl.glGetUniformLocation(program, "uHeightfield"), 0)
        gl.glBindVertexArray(vao)
        with texture.bound(0):
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        raw = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_FLOAT)
        return np.frombuffer(bytes(raw), dtype=np.float32).reshape(height, width, 4).copy()
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures([colour])
        gl.glDeleteVertexArrays(1, [vao])
        gl.glDeleteProgram(program)


def _draw_custom_probe(texture: HeightfieldTexture, size: int, width: int, height: int,
                       fragment: str, label: str):
    from rendering.quick.render.gl_resources import compile_program

    program = compile_program(_VERTEX, fragment, label=label)
    vao = int(gl.glGenVertexArrays(1))
    colour = int(gl.glGenTextures(1))
    fbo = int(gl.glGenFramebuffers(1))
    try:
        gl.glBindTexture(gl.GL_TEXTURE_2D, colour)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, width, height, 0,
                        gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                                  gl.GL_TEXTURE_2D, colour, 0)
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
        gl.glViewport(0, 0, width, height)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_BLEND)
        gl.glUseProgram(program)
        gl.glUniform1i(gl.glGetUniformLocation(program, "uSize"), size)
        gl.glUniform1i(gl.glGetUniformLocation(program, "uHeightfield"), 0)
        gl.glBindVertexArray(vao)
        with texture.bound(0):
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        raw = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_FLOAT)
        return np.frombuffer(bytes(raw), dtype=np.float32).reshape(height, width, 4).copy()
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures([colour])
        gl.glDeleteVertexArrays(1, [vao])
        gl.glDeleteProgram(program)


def _curve_probe_fragment(width: int, height: int) -> str:
    return f"""#version 460 core
out vec4 FragColor;
uniform sampler2D uHeightfield;
uniform int uSize;
{HEIGHTFIELD_GLSL}
void main() {{
    vec2 uv = (gl_FragCoord.xy - vec2(0.5)) / vec2({width - 1}.0, {height - 1}.0);
    float authoredHeight = sceneHeightfield(uHeightfield, uSize, uv);
    float curvedHeight = sceneHeightfieldCurve(uHeightfield, uSize, uv);
    FragColor = vec4(authoredHeight,
                     sceneHeightfieldWater(authoredHeight) ? 1.0 : 0.0,
                     curvedHeight, 1.0);
}}
"""


def _curve_wire_probe_fragment(width: int, height: int) -> str:
    return f"""#version 460 core
out vec4 FragColor;
uniform sampler2D uHeightfield;
uniform int uSize;
{HEIGHTFIELD_GLSL}
{HEIGHTFIELD_WIRE_GLSL}
void main() {{
    vec2 uv = (gl_FragCoord.xy - vec2(0.5)) / vec2({width - 1}.0, {height - 1}.0);
    float curvedHeight = sceneHeightfieldCurve(uHeightfield, uSize, uv);
    float wire = sceneHeightfieldCurveWire(uv, curvedHeight, 8.0, 1.2);
    FragColor = vec4(wire, curvedHeight, 0.0, 1.0);
}}
"""


def _surface_payload_probe_fragment() -> str:
    return f"""#version 460 core
out vec4 FragColor;
uniform sampler2D uHeightfield;
uniform int uSize;
void main() {{
    ivec2 cell = ivec2(gl_FragCoord.xy - vec2(0.5));
    vec2 authored = texelFetch(uHeightfield, cell, 0).rg;
    FragColor = vec4(authored, 0.0, 1.0);
}}
"""


def _minimum_float_class_probe_fragment() -> str:
    return f"""#version 460 core
out vec4 FragColor;
uniform sampler2D uHeightfield;
uniform int uSize;
{HEIGHTFIELD_GLSL}
void main() {{
    vec2 authored = texelFetch(uHeightfield, ivec2(0, 0), 0).rg;
    FragColor = vec4(authored.r, sceneHeightfieldWater(authored.r) ? 1.0 : 0.0,
                     authored.g, 1.0);
}}
"""


def _field(*heights: float) -> dict:
    return normalize_heightfield({"version": 1, "size": 3, "heights": list(heights)})


def _texture_internal_format(texture_id: int) -> int:
    value = ctypes.c_int()
    gl.glGetTextureLevelParameteriv(
        texture_id, 0, gl.GL_TEXTURE_INTERNAL_FORMAT, ctypes.byref(value),
    )
    return int(value.value)


def test_gpu_bilinear_samples_match_cpu_and_only_authored_zero_is_water(qt_app):
    capture = TransitionCapture(9, 9)
    texture = HeightfieldTexture("heightfield sampler probe")
    terrain = _field(
        0.0, 0.25, 0.0,
        0.5, 0.75, 0.375,
        0.0, 1.0, 0.125,
    )
    try:
        texture.ensure(terrain["size"], heightfield_bytes(terrain))
        actual = _draw_heightfield_probe(capture, texture, terrain["size"], 9, 9)
        expected = np.asarray([
            [sample_heightfield(terrain, x / 8.0, y / 8.0) for x in range(9)]
            for y in range(9)
        ], dtype=np.float32)
        assert np.allclose(actual[..., 0], expected, atol=2e-6, rtol=0.0)
        expected_water = (expected == 0.0).astype(np.float32)
        assert np.array_equal(actual[..., 1], expected_water)
        assert actual[0, 0, 1] == 1.0       # authored base-level corner
        assert actual[0, 1, 1] == 0.0       # positive interpolated shore is land
        assert actual[4, 4, 0] == pytest.approx(0.75, abs=2e-6)
        assert actual[4, 4, 1] == 0.0
    finally:
        texture.release()
        capture.close()


def test_gpu_curve_samples_match_cpu_while_bilinear_zero_remains_water(qt_app):
    capture = TransitionCapture(9, 9)
    texture = HeightfieldTexture("heightfield curve sampler probe")
    terrain = _field(
        0.0, 0.25, 0.0,
        0.5, 0.75, 0.375,
        0.0, 1.0, 0.125,
    )
    try:
        texture.ensure(terrain["size"], heightfield_bytes(terrain))
        actual = _draw_custom_probe(
            texture, terrain["size"], 9, 9,
            _curve_probe_fragment(9, 9), "heightfield curve sampler probe",
        )
        expected_bilinear = np.asarray([
            [sample_heightfield(terrain, x / 8.0, y / 8.0) for x in range(9)]
            for y in range(9)
        ], dtype=np.float32)
        expected_curve = np.asarray([
            [sample_heightfield_curve(terrain, x / 8.0, y / 8.0) for x in range(9)]
            for y in range(9)
        ], dtype=np.float32)
        assert np.allclose(actual[..., 0], expected_bilinear, atol=2e-6, rtol=0.0)
        assert np.allclose(actual[..., 2], expected_curve, atol=2e-6, rtol=0.0)
        assert np.array_equal(actual[..., 1], (expected_bilinear == 0.0).astype(np.float32))
        assert actual[0, 0, 0] == 0.0
        assert actual[0, 0, 1] == 1.0
        assert actual[0, 0, 2] > 0.0  # Curved geometry rises at the coast; water still uses bilinear zero.
    finally:
        texture.release()
        capture.close()


def test_flat_curve_wire_keeps_open_plateau_between_grid_lines(qt_app):
    capture = TransitionCapture(64, 64)
    texture = HeightfieldTexture("flat heightfield curve wire probe")
    flat = _field(*([0.0] * 9))
    try:
        texture.ensure(flat["size"], heightfield_bytes(flat))
        actual = _draw_custom_probe(
            texture, flat["size"], 64, 64,
            _curve_wire_probe_fragment(64, 64), "flat heightfield curve wire probe",
        )
        wire = actual[..., 0]
        assert np.all(actual[..., 1] == 0.0)
        assert np.count_nonzero(wire < 0.01) > wire.size * 0.10
        assert np.count_nonzero(wire > 0.5) < wire.size * 0.90
    finally:
        texture.release()
        capture.close()


def test_texture_storage_and_upload_are_skipped_for_unchanged_frames(qt_app, monkeypatch):
    capture = TransitionCapture(32, 32)
    texture = HeightfieldTexture("heightfield upload probe")
    calls = {"create": 0, "storage": 0, "upload": 0}
    original_create = texture_module.gl.glCreateTextures
    original_storage = texture_module.gl.glTextureStorage2D
    original_upload = texture_module.gl.glTextureSubImage2D

    def create(*args):
        calls["create"] += 1
        return original_create(*args)

    def storage(*args):
        calls["storage"] += 1
        return original_storage(*args)

    def upload(*args):
        calls["upload"] += 1
        return original_upload(*args)

    monkeypatch.setattr(texture_module.gl, "glCreateTextures", create)
    monkeypatch.setattr(texture_module.gl, "glTextureStorage2D", storage)
    monkeypatch.setattr(texture_module.gl, "glTextureSubImage2D", upload)
    first = heightfield_bytes(_field(0.0, 0.25, 0.5, 0.75, 1.0, 0.5, 0.25, 0.1, 0.0))
    try:
        texture_id = texture.ensure(3, first)
        assert gl.glIsTexture(texture_id)
        assert calls == {"create": 1, "storage": 1, "upload": 1}

        for _ in range(120):
            # Distinct but equal bytes model repeated frame snapshots after warm-up.
            texture.ensure(3, memoryview(first).tobytes())
        assert texture.texture_id == texture_id
        assert texture.uploads == 1
        assert calls == {"create": 1, "storage": 1, "upload": 1}

        changed = bytearray(first)
        struct.pack_into("<f", changed, 4 * 4, 0.875)
        assert texture.ensure(3, bytes(changed)) == texture_id
        assert texture.uploads == 2
        assert calls == {"create": 1, "storage": 1, "upload": 2}
    finally:
        texture.release()
        capture.close()


def test_unpack_and_bound_texture_state_restore_even_when_sampling_raises(qt_app):
    capture = TransitionCapture(32, 32)
    texture = HeightfieldTexture("heightfield state probe")
    pbo = int(gl.glGenBuffers(1))
    sentinel_texture = int(gl.glGenTextures(1))
    sentinel_sampler = int(gl.glGenSamplers(1))
    try:
        gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, pbo)
        gl.glBufferData(gl.GL_PIXEL_UNPACK_BUFFER, 512, None, gl.GL_STREAM_DRAW)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glPixelStorei(gl.GL_UNPACK_ROW_LENGTH, 17)
        gl.glPixelStorei(gl.GL_UNPACK_SKIP_ROWS, 2)
        gl.glPixelStorei(gl.GL_UNPACK_SKIP_PIXELS, 3)

        gl.glActiveTexture(gl.GL_TEXTURE3)
        gl.glBindTexture(gl.GL_TEXTURE_2D, sentinel_texture)
        gl.glBindSampler(3, sentinel_sampler)
        gl.glActiveTexture(gl.GL_TEXTURE5)
        unpack_before = {
            name: int(gl.glGetIntegerv(name))
            for name in (gl.GL_PIXEL_UNPACK_BUFFER_BINDING, gl.GL_UNPACK_ALIGNMENT,
                         gl.GL_UNPACK_ROW_LENGTH, gl.GL_UNPACK_SKIP_ROWS, gl.GL_UNPACK_SKIP_PIXELS)
        }
        active_before = int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE))

        data = heightfield_bytes(_field(0.0, 0.25, 0.5, 0.75, 1.0, 0.5, 0.25, 0.1, 0.0))
        texture.ensure(3, data)
        assert {name: int(gl.glGetIntegerv(name)) for name in unpack_before} == unpack_before
        assert int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE)) == active_before

        with pytest.raises(RuntimeError, match="probe failure"):
            with texture.bound(3) as bound_id:
                assert bound_id == texture.texture_id
                assert int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE)) == gl.GL_TEXTURE3
                assert int(gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D)) == texture.texture_id
                assert int(gl.glGetIntegeri_v(gl.GL_SAMPLER_BINDING, 3)) == 0
                raise RuntimeError("probe failure")

        assert int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE)) == active_before
        gl.glActiveTexture(gl.GL_TEXTURE3)
        assert int(gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D)) == sentinel_texture
        assert int(gl.glGetIntegeri_v(gl.GL_SAMPLER_BINDING, 3)) == sentinel_sampler
        gl.glActiveTexture(active_before)
        assert {name: int(gl.glGetIntegerv(name)) for name in unpack_before} == unpack_before
    finally:
        texture.release()
        gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 4)
        gl.glPixelStorei(gl.GL_UNPACK_ROW_LENGTH, 0)
        gl.glPixelStorei(gl.GL_UNPACK_SKIP_ROWS, 0)
        gl.glPixelStorei(gl.GL_UNPACK_SKIP_PIXELS, 0)
        gl.glActiveTexture(gl.GL_TEXTURE3)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glBindSampler(3, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glDeleteSamplers(1, [sentinel_sampler])
        gl.glDeleteTextures([sentinel_texture])
        gl.glDeleteBuffers(1, [pbo])
        capture.close()


def test_release_failure_is_loud_and_keeps_the_texture_for_retry(qt_app, monkeypatch):
    capture = TransitionCapture(32, 32)
    texture = HeightfieldTexture("heightfield release probe")
    data = heightfield_bytes(_field(0.0, 0.25, 0.5, 0.75, 1.0, 0.5, 0.25, 0.1, 0.0))
    try:
        texture_id = texture.ensure(3, data)
        original_delete = texture_module.gl.glDeleteTextures

        def fail_delete(*_args):
            raise RuntimeError("injected heightfield deletion failure")

        monkeypatch.setattr(texture_module.gl, "glDeleteTextures", fail_delete)
        with pytest.raises(RuntimeError, match="injected heightfield deletion failure"):
            texture.release()
        assert texture.has_resources
        assert texture.texture_id == texture_id
        assert gl.glIsTexture(texture_id)

        monkeypatch.setattr(texture_module.gl, "glDeleteTextures", original_delete)
        texture.release()
        assert not texture.has_resources
        assert texture.texture_id == 0
        assert not gl.glIsTexture(texture_id)
    finally:
        # Make cleanup retry the production owner even if an assertion failed above.
        monkeypatch.undo()
        texture.release()
        capture.close()


def test_rg_surface_texture_upload_samples_both_authored_channels_and_reuses_storage(qt_app):
    capture = TransitionCapture(32, 32)
    terrain = _field(
        0.0, 0.0, 0.0,
        0.0, 0.75, 0.0,
        0.0, 0.0, 0.0,
    )
    payload = heightfield_surface_bytes(terrain)
    texture = HeightfieldTexture("height and bank distance probe", components=2)
    single_channel = HeightfieldTexture("default single channel probe")
    pbo = int(gl.glGenBuffers(1))
    sentinel_texture = int(gl.glGenTextures(1))
    sentinel_sampler = int(gl.glGenSamplers(1))
    try:
        assert single_channel.components == 1
        assert texture.components == 2
        with pytest.raises(ValueError, match="components must be 1 or 2"):
            HeightfieldTexture("invalid representation", components=3)
        with pytest.raises(ValueError, match="2 components"):
            texture.ensure(terrain["size"], heightfield_bytes(terrain))
        assert not texture.has_resources

        gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, pbo)
        gl.glBufferData(gl.GL_PIXEL_UNPACK_BUFFER, 512, None, gl.GL_STREAM_DRAW)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glPixelStorei(gl.GL_UNPACK_ROW_LENGTH, 17)
        gl.glPixelStorei(gl.GL_UNPACK_SKIP_ROWS, 2)
        gl.glPixelStorei(gl.GL_UNPACK_SKIP_PIXELS, 3)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, sentinel_texture)
        gl.glBindSampler(0, sentinel_sampler)
        gl.glActiveTexture(gl.GL_TEXTURE3)
        gl.glBindTexture(gl.GL_TEXTURE_2D, sentinel_texture)
        gl.glBindSampler(3, sentinel_sampler)
        gl.glActiveTexture(gl.GL_TEXTURE5)
        unpack_names = (
            gl.GL_PIXEL_UNPACK_BUFFER_BINDING, gl.GL_UNPACK_ALIGNMENT,
            gl.GL_UNPACK_ROW_LENGTH, gl.GL_UNPACK_SKIP_ROWS, gl.GL_UNPACK_SKIP_PIXELS,
        )
        unpack_before = {name: int(gl.glGetIntegerv(name)) for name in unpack_names}
        active_before = int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE))

        texture_id = texture.ensure(terrain["size"], payload)
        assert texture.uploads == 1
        assert _texture_internal_format(texture_id) == gl.GL_RG32F
        assert {name: int(gl.glGetIntegerv(name)) for name in unpack_names} == unpack_before
        assert int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE)) == active_before

        # Let the framebuffer probe allocate its own target with ordinary unpack state.
        gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 4)
        gl.glPixelStorei(gl.GL_UNPACK_ROW_LENGTH, 0)
        gl.glPixelStorei(gl.GL_UNPACK_SKIP_ROWS, 0)
        gl.glPixelStorei(gl.GL_UNPACK_SKIP_PIXELS, 0)

        actual = _draw_custom_probe(
            texture, terrain["size"], terrain["size"], terrain["size"],
            _surface_payload_probe_fragment(), "RG heightfield payload probe",
        )
        expected = np.asarray([
            [(terrain["heights"][y * terrain["size"] + x],
              struct.unpack_from("<f", payload, (y * terrain["size"] + x) * 8 + 4)[0])
             for x in range(terrain["size"])]
            for y in range(terrain["size"])
        ], dtype=np.float32)
        assert np.allclose(actual[..., :2], expected, atol=2e-7, rtol=0.0)
        assert int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE)) == active_before
        gl.glActiveTexture(gl.GL_TEXTURE0)
        assert int(gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D)) == sentinel_texture
        assert int(gl.glGetIntegeri_v(gl.GL_SAMPLER_BINDING, 0)) == sentinel_sampler
        gl.glActiveTexture(active_before)

        assert texture.ensure(terrain["size"], memoryview(payload).tobytes()) == texture_id
        assert texture.uploads == 1
        changed = list(terrain["heights"])
        changed[4] = 0.5
        changed_terrain = normalize_heightfield({"version": 1, "size": 3, "heights": changed})
        changed_payload = heightfield_surface_bytes(changed_terrain)
        assert texture.ensure(terrain["size"], changed_payload) == texture_id
        assert texture.uploads == 2

        single_id = single_channel.ensure(terrain["size"], heightfield_bytes(terrain))
        assert _texture_internal_format(single_id) == gl.GL_R32F
        assert single_channel.uploads == 1
    finally:
        single_channel.release()
        texture.release()
        gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 4)
        gl.glPixelStorei(gl.GL_UNPACK_ROW_LENGTH, 0)
        gl.glPixelStorei(gl.GL_UNPACK_SKIP_ROWS, 0)
        gl.glPixelStorei(gl.GL_UNPACK_SKIP_PIXELS, 0)
        gl.glActiveTexture(gl.GL_TEXTURE3)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glBindSampler(3, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glBindSampler(0, 0)
        gl.glDeleteSamplers(1, [sentinel_sampler])
        gl.glDeleteTextures([sentinel_texture])
        gl.glDeleteBuffers(1, [pbo])
        capture.close()


def test_rg_shader_keeps_lowest_admitted_normal_float32_out_of_water_class(qt_app):
    capture = TransitionCapture(16, 16)
    minimum_normal = 2.0 ** -126
    terrain = normalize_heightfield({
        "version": 1,
        "size": 3,
        "heights": [minimum_normal, 0.0, 0.0,
                    0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0],
    })
    texture = HeightfieldTexture("minimum normal RG heightfield probe", components=2)
    try:
        texture.ensure(terrain["size"], heightfield_surface_bytes(terrain))
        actual = _draw_custom_probe(
            texture, terrain["size"], 3, 3,
            _minimum_float_class_probe_fragment(), "minimum normal RG classification probe",
        )
        assert actual[0, 0, 0] == np.float32(minimum_normal)
        assert actual[0, 0, 0] > 0.0
        assert actual[0, 0, 1] == 0.0
    finally:
        texture.release()
        capture.close()
