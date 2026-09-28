"""Per-frame uniform blocks: the std140 layout the driver sees is the one Python
packs, the values arrive on the GPU, and binding the block hands back whatever
was bound before. Offscreen GL, no window.
"""
from __future__ import annotations

import ctypes

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs.exploding_tiles_program import EXPLODING_TILES_FRAME_BLOCK
from rendering.gl_programs.scene3d import Scene3DBlockLayout
from rendering.quick import gl_query
from rendering.quick.render.gl_resources import compile_program
from rendering.quick.scene3d.uniforms import SCENE3D_UNIFORM_BINDING, UniformBlock

_MIXED = Scene3DBlockLayout.of("MixedBlock", (
    ("a", "vec2"), ("b", "float"), ("c", "vec3"), ("d", "int"), ("e", "vec2"), ("f", "mat4"), ("g", "vec4"), ("h", "uint"),
))
_VERTEX = """#version 410 core
void main() { vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2); gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0); }
"""


def test_std140_offsets_follow_the_rules():
    assert _MIXED.offsets == (0, 8, 16, 28, 32, 48, 112, 128)
    assert _MIXED.size == 144
    assert "layout(std140) uniform MixedBlock" in _MIXED.glsl()


@pytest.fixture
def context(qt_app):
    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(16, 16)
    yield capture
    capture.close()


def _reader(layout: Scene3DBlockLayout) -> str:
    """A fragment shader that writes every member of ``layout`` into consecutive output pixels."""
    lines = []
    for index, (field, glsl_type) in enumerate(layout.fields):
        value = {
            "float": f"vec4({field})", "int": f"vec4(float({field}))", "uint": f"vec4(float({field}))",
            "vec2": f"vec4({field}, 0.0, 0.0)", "ivec2": f"vec4(vec2({field}), 0.0, 0.0)",
            "vec3": f"vec4({field}, 0.0)", "vec4": field, "mat4": f"{field}[3]",
        }[glsl_type]
        lines.append(f"    if (column == {index}) FragColor = {value};")
    return ("#version 410 core\nout vec4 FragColor;\n" + layout.glsl()
            + "void main() {\n    int column = int(gl_FragCoord.x);\n    FragColor = vec4(0.0);\n"
            + "\n".join(lines) + "\n}\n")


@pytest.mark.qt
@pytest.mark.parametrize("layout", (_MIXED, EXPLODING_TILES_FRAME_BLOCK), ids=("mixed", "exploding-tiles"))
def test_the_driver_sees_our_layout_and_our_values(context, layout):
    program = compile_program(_VERTEX, _reader(layout), label="block layout probe")
    block = UniformBlock(layout, "block layout probe")
    target, fbo, vao = int(gl.glGenTextures(1)), int(gl.glGenFramebuffers(1)), int(gl.glGenVertexArrays(1))
    try:
        # Driver-reported member offsets equal the Python layout's.
        count = gl.glGetProgramiv(program, gl.GL_ACTIVE_UNIFORMS)
        offsets = {}
        for index in range(count):
            name = gl.glGetActiveUniform(program, index)[0].decode().split("[")[0].split(".")[-1]
            out = (ctypes.c_int * 1)()
            gl.glGetActiveUniformsiv(program, 1, (ctypes.c_uint * 1)(index), gl.GL_UNIFORM_OFFSET, out)
            offsets[name] = out[0]
        assert {field: offsets[field] for field, _type in layout.fields} == dict(
            zip((field for field, _type in layout.fields), layout.offsets))

        values = {}
        for position, (field, glsl_type) in enumerate(layout.fields, start=1):
            width = {"float": 1, "int": 1, "uint": 1, "vec2": 2, "ivec2": 2, "vec3": 3, "vec4": 4, "mat4": 16}[glsl_type]
            numbers = [position * 10 + item for item in range(width)]
            values[field] = numbers[0] if width == 1 else tuple(numbers)
        block.attach(program)
        gl.glBindTexture(gl.GL_TEXTURE_2D, target)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, len(layout.fields), 1, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, target, 0)
        gl.glViewport(0, 0, len(layout.fields), 1)
        gl.glUseProgram(program)
        gl.glBindVertexArray(vao)
        with block.bound(values):
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        pixels = np.asarray(gl.glReadPixels(0, 0, len(layout.fields), 1, gl.GL_RGBA, gl.GL_FLOAT)).reshape(-1, 4)
        for column, (field, glsl_type) in enumerate(layout.fields):
            expected = values[field]
            if glsl_type == "mat4":
                expected = expected[12:16]  # column 3
            expected = np.atleast_1d(np.asarray(expected, dtype=np.float64))
            assert np.allclose(pixels[column, : expected.size], expected), (field, pixels[column])
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, context.fbo)
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures([target])
        gl.glDeleteVertexArrays(1, [vao])
        gl.glDeleteProgram(program)
        block.release()


@pytest.mark.qt
def test_binding_the_block_hands_back_the_previous_binding(context):
    block = UniformBlock(_MIXED, "binding probe")
    sentinel, other = int(gl.glGenBuffers(1)), int(gl.glGenBuffers(1))
    try:
        gl.glBindBuffer(gl.GL_UNIFORM_BUFFER, sentinel)
        gl.glBufferData(gl.GL_UNIFORM_BUFFER, 512, None, gl.GL_STATIC_DRAW)
        gl.glBindBufferRange(gl.GL_UNIFORM_BUFFER, SCENE3D_UNIFORM_BINDING, sentinel, 256, 128)
        gl.glBindBuffer(gl.GL_UNIFORM_BUFFER, other)
        values = {field: (0,) * 16 if kind == "mat4" else 0 for field, kind in _MIXED.fields}
        values.update({"a": (0, 0), "c": (0, 0, 0), "e": (0, 0), "g": (0, 0, 0, 0)})
        with block.bound(values):
            assert gl_query.get_indexed_int(gl.GL_UNIFORM_BUFFER_BINDING, SCENE3D_UNIFORM_BINDING) != sentinel
        assert gl_query.get_indexed_int(gl.GL_UNIFORM_BUFFER_BINDING, SCENE3D_UNIFORM_BINDING) == sentinel
        assert gl_query.get_indexed_int64(gl.GL_UNIFORM_BUFFER_START, SCENE3D_UNIFORM_BINDING) == 256
        assert gl_query.get_indexed_int64(gl.GL_UNIFORM_BUFFER_SIZE, SCENE3D_UNIFORM_BINDING) == 128
        assert gl_query.get_int(gl.GL_UNIFORM_BUFFER_BINDING) == other
    finally:
        gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, SCENE3D_UNIFORM_BINDING, 0)
        gl.glBindBuffer(gl.GL_UNIFORM_BUFFER, 0)
        gl.glDeleteBuffers(2, [sentinel, other])
        block.release()
