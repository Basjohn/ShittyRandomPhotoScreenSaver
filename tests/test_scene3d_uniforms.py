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
_VERTEX = """#version 460 core
void main() { vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2); gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0); }
"""


def test_std140_offsets_follow_the_rules():
    assert _MIXED.offsets == (0, 8, 16, 28, 32, 48, 112, 128)
    assert _MIXED.size == 144
    assert "layout(std140) uniform MixedBlock" in _MIXED.glsl()


_ARRAYS = Scene3DBlockLayout.of("ArrayBlock", (
    ("weights", "float[8]"), ("lanes", "int[4]"), ("centres", "vec3[2]"),
))


def test_fixed_arrays_have_std140_stride_and_reject_incomplete_records():
    import struct
    assert _ARRAYS.offsets == (0, 128, 192)
    assert _ARRAYS.size == 224
    values = {"weights": tuple(range(8)), "lanes": (1, 2, 3, 4), "centres": ((5, 6, 7), (8, 9, 10))}
    packed = _ARRAYS.pack(values)
    assert [struct.unpack_from("<f", packed, index * 16)[0] for index in range(8)] == list(range(8))
    assert struct.unpack_from("<3f", packed, 208) == (8, 9, 10)
    assert _ARRAYS.pack_fields({"weights": tuple(range(8))}) == ((0, packed[:128]),)
    with pytest.raises(ValueError, match="exactly 8"):
        _ARRAYS.pack({**values, "weights": (1,)})


@pytest.mark.qt
def test_fixed_scalar_and_vector_arrays_reach_gpu_and_partial_updates_preserve_other_fields(context):
    fragment = "#version 460 core\nout vec4 FragColor;\n" + _ARRAYS.glsl() + """
void main() {
    int column = int(gl_FragCoord.x);
    if (column < 8) FragColor = vec4(weights[column]);
    else if (column < 12) FragColor = vec4(float(lanes[column - 8]));
    else FragColor = vec4(centres[column - 12], 1.0);
}
"""
    program = compile_program(_VERTEX, fragment, label="fixed-array uniform probe")
    block = UniformBlock(_ARRAYS, "fixed-array uniform probe")
    texture, fbo, vao = int(gl.glGenTextures(1)), int(gl.glGenFramebuffers(1)), int(gl.glGenVertexArrays(1))
    try:
        block.attach(program)
        for index in range(int(gl.glGetProgramiv(program, gl.GL_ACTIVE_UNIFORMS))):
            name = gl.glGetActiveUniform(program, index)[0].decode().split("[")[0].split(".")[-1]
            stride = (ctypes.c_int * 1)()
            gl.glGetActiveUniformsiv(program, 1, (ctypes.c_uint * 1)(index), gl.GL_UNIFORM_ARRAY_STRIDE, stride)
            assert stride[0] == 16, name
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, 14, 1, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
        gl.glViewport(0, 0, 14, 1)
        gl.glUseProgram(program)
        gl.glBindVertexArray(vao)
        values = {"weights": tuple(range(8)), "lanes": (1, 2, 3, 4), "centres": ((5, 6, 7), (8, 9, 10))}
        packed = _ARRAYS.pack(values)
        with pytest.raises(ValueError, match="224 packed bytes"):
            with block.bound(packed[:-1]):
                pytest.fail("invalid packed input reached the stream")
        assert not block.has_resources
        with pytest.raises(RuntimeError, match="not bound"):
            block.update_packed(packed)
        with block.bound(packed):
            block.update_fields({"lanes": (9, 8, 7, 6)})
            with pytest.raises(ValueError, match="224 packed bytes"):
                block.update_packed(packed[:-1])
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        pixels = np.asarray(gl.glReadPixels(0, 0, 14, 1, gl.GL_RGBA, gl.GL_FLOAT)).reshape(-1, 4)
        assert np.array_equal(pixels[:8, 0], np.arange(8))
        assert np.array_equal(pixels[8:12, 0], (9, 8, 7, 6))
        assert np.array_equal(pixels[12:14, :3], values["centres"])
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, context.fbo)
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures([texture])
        gl.glDeleteVertexArrays(1, [vao])
        gl.glDeleteProgram(program)
        block.release()


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
    return ("#version 460 core\nout vec4 FragColor;\n" + layout.glsl()
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


@pytest.mark.qt
def test_partial_updates_reach_the_allocated_block_even_if_the_generic_binding_changes(context):
    """Trail ghosts update only their moving fields through DSA, never whichever UBO is generically bound."""
    layout = EXPLODING_TILES_FRAME_BLOCK
    program = compile_program(_VERTEX, _reader(layout), label="partial block update probe")
    block = UniformBlock(layout, "partial block update probe")
    target, fbo, vao, sentinel = (int(gl.glGenTextures(1)), int(gl.glGenFramebuffers(1)),
                                  int(gl.glGenVertexArrays(1)), int(gl.glGenBuffers(1)))
    values = {}
    try:
        for position, (field, glsl_type) in enumerate(layout.fields, start=1):
            width = {"float": 1, "int": 1, "uint": 1, "vec2": 2, "ivec2": 2, "vec3": 3, "vec4": 4,
                     "mat4": 16}[glsl_type]
            numbers = [position * 10 + item for item in range(width)]
            values[field] = numbers[0] if width == 1 else tuple(numbers)
        updates = {"uProgress": 901.0, "uBlast": (902.0, 903.0), "uShutter": 904.0}
        expected = {**values, **updates}
        block.attach(program)
        gl.glBindTexture(gl.GL_TEXTURE_2D, target)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, len(layout.fields), 1, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, target, 0)
        gl.glViewport(0, 0, len(layout.fields), 1)
        gl.glUseProgram(program)
        gl.glBindVertexArray(vao)
        with block.bound(values):
            gl.glBindBuffer(gl.GL_UNIFORM_BUFFER, sentinel)
            gl.glBufferData(gl.GL_UNIFORM_BUFFER, 256, None, gl.GL_STATIC_DRAW)
            block.update_fields(updates)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        pixels = np.asarray(gl.glReadPixels(0, 0, len(layout.fields), 1, gl.GL_RGBA, gl.GL_FLOAT)).reshape(-1, 4)
        for column, (field, glsl_type) in enumerate(layout.fields):
            expected_value = expected[field]
            if glsl_type == "mat4":
                expected_value = expected_value[12:16]
            expected_value = np.atleast_1d(np.asarray(expected_value, dtype=np.float64))
            assert np.allclose(pixels[column, : expected_value.size], expected_value), (field, pixels[column])
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, context.fbo)
        gl.glBindBuffer(gl.GL_UNIFORM_BUFFER, 0)
        gl.glDeleteBuffers(1, [sentinel])
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures([target])
        gl.glDeleteVertexArrays(1, [vao])
        gl.glDeleteProgram(program)
        block.release()


@pytest.mark.qt
def test_draws_before_an_update_keep_their_values_and_the_scope_exit_drops_the_updates(context):
    """Each trail ghost draws with its own rebound copy; earlier draws are never rewritten."""
    layout = EXPLODING_TILES_FRAME_BLOCK
    program = compile_program(_VERTEX, _reader(layout), label="ghost copy probe")
    block = UniformBlock(layout, "ghost copy probe")
    target, fbo, vao = int(gl.glGenTextures(1)), int(gl.glGenFramebuffers(1)), int(gl.glGenVertexArrays(1))
    column = [field for field, _type in layout.fields].index("uProgress")
    widths = {"vec2": 2, "ivec2": 2, "vec3": 3, "vec4": 4, "mat4": 16}
    values = {field: 0 if widths.get(kind, 1) == 1 else (0,) * widths[kind] for field, kind in layout.fields}
    values["uProgress"] = 0.25
    try:
        block.attach(program)
        gl.glBindTexture(gl.GL_TEXTURE_2D, target)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, len(layout.fields), 3, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, target, 0)
        gl.glViewport(0, 0, len(layout.fields), 3)
        gl.glUseProgram(program)
        gl.glBindVertexArray(vao)
        gl.glEnable(gl.GL_SCISSOR_TEST)
        with block.bound(values):
            gl.glScissor(0, 0, len(layout.fields), 1)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            block.update_fields({"uProgress": 0.5})
            gl.glScissor(0, 1, len(layout.fields), 1)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            with block.bound(values):  # a nested bind hands back the updated copy
                pass
            gl.glScissor(0, 2, len(layout.fields), 1)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        pixels = np.asarray(gl.glReadPixels(0, 0, len(layout.fields), 3, gl.GL_RGBA, gl.GL_FLOAT)).reshape(3, -1, 4)
        assert [float(pixels[row, column, 0]) for row in range(3)] == [0.25, 0.5, 0.5]
        with pytest.raises(RuntimeError, match="not bound"):
            block.update_fields({"uProgress": 1.0})
    finally:
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, context.fbo)
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures([target])
        gl.glDeleteVertexArrays(1, [vao])
        gl.glDeleteProgram(program)
        block.release()
