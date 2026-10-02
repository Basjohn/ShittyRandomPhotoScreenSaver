"""The persistent mapped stream ring and std430 storage layouts (S14).

Real offscreen GL, no window: what the driver reads is what Python wrote, a slot is
written again only after its fence, the generic buffer bindings are never touched,
capacity is fixed and loud, and release returns everything to zero.
"""
from __future__ import annotations

import ctypes

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs.scene3d import Scene3DStorageLayout
from rendering.quick import gl_query
from rendering.quick.render.gl_resources import compile_program
from rendering.quick.scene3d import stream as stream_module
from rendering.quick.scene3d.stream import StreamRing

_VERTEX = """#version 460 core
void main() { vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2); gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0); }
"""
_WIDTHS = {"float": 1, "int": 1, "uint": 1, "vec2": 2, "ivec2": 2, "vec3": 3, "vec4": 4, "mat4": 16}
_LAYOUTS = (
    # Three floats: std430 strides 12 where std140 would pad the record to 16.
    Scene3DStorageLayout.of("Scalars", "Scalar", (("a", "float"), ("b", "float"), ("c", "float"))),
    Scene3DStorageLayout.of("Packed", "PackedRecord", (("position", "vec3"), ("size", "float"))),
    Scene3DStorageLayout.of("Mixed", "MixedRecord", (
        ("a", "float"), ("b", "vec2"), ("c", "int"), ("d", "vec4"), ("e", "uint"), ("f", "mat4"), ("g", "ivec2"),
    )),
)


@pytest.fixture
def context(qt_app):
    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(16, 16)
    yield capture
    capture.close()


def test_std430_offsets_and_strides_follow_the_rules():
    scalars, packed, mixed = _LAYOUTS
    assert (scalars.offsets, scalars.stride) == ((0, 4, 8), 12)
    assert (packed.offsets, packed.stride) == ((0, 12), 16)
    assert (mixed.offsets, mixed.stride) == ((0, 8, 16, 32, 48, 64, 128), 144)
    assert "layout(std430, binding = 3) readonly buffer Packed" in packed.glsl(3)
    assert packed.dtype().itemsize == packed.stride


def _values(layout: Scene3DStorageLayout, record: int) -> dict[str, object]:
    values = {}
    for position, (field, glsl_type) in enumerate(layout.fields, start=1):
        numbers = [record * 100 + position * 10 + item for item in range(_WIDTHS[glsl_type])]
        values[field] = numbers[0] if len(numbers) == 1 else tuple(numbers)
    return values


def test_numpy_records_pack_to_the_same_bytes():
    for layout in _LAYOUTS:
        records = [_values(layout, index) for index in range(5)]
        array = np.zeros(len(records), dtype=layout.dtype())
        for index, record in enumerate(records):
            for field, value in record.items():
                array[index][field] = value
        assert array.tobytes() == layout.pack(records)


def _reader(layout: Scene3DStorageLayout, records: int) -> str:
    """Writes field ``x`` of record ``y`` into pixel (x, y)."""
    lines = []
    for index, (field, glsl_type) in enumerate(layout.fields):
        member = f"{layout.array}[row].{field}"
        value = {
            "float": f"vec4({member})", "int": f"vec4(float({member}))", "uint": f"vec4(float({member}))",
            "vec2": f"vec4({member}, 0.0, 0.0)", "ivec2": f"vec4(vec2({member}), 0.0, 0.0)",
            "vec3": f"vec4({member}, 0.0)", "vec4": member, "mat4": f"{member}[3]",
        }[glsl_type]
        lines.append(f"    if (column == {index}) FragColor = {value};")
    return ("#version 460 core\nout vec4 FragColor;\n" + layout.glsl(5)
            + "void main() {\n    int column = int(gl_FragCoord.x);\n    int row = int(gl_FragCoord.y);\n"
            + "    FragColor = vec4(0.0);\n" + "\n".join(lines) + "\n}\n")


class _Canvas:
    """A float colour target ``width`` x ``height`` to read shader output back from."""

    def __init__(self, context, width: int, height: int) -> None:
        self.context, self.width, self.height = context, width, height
        self.texture, self.fbo, self.vao = (int(gl.glGenTextures(1)), int(gl.glGenFramebuffers(1)),
                                            int(gl.glGenVertexArrays(1)))
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, width, height, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, self.texture, 0)
        gl.glViewport(0, 0, width, height)
        gl.glBindVertexArray(self.vao)

    def pixels(self) -> np.ndarray:
        data = gl.glReadPixels(0, 0, self.width, self.height, gl.GL_RGBA, gl.GL_FLOAT)
        return np.asarray(data).reshape(self.height, self.width, 4)

    def close(self) -> None:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.context.fbo)
        gl.glDeleteFramebuffers(1, [self.fbo])
        gl.glDeleteTextures([self.texture])
        gl.glDeleteVertexArrays(1, [self.vao])


@pytest.mark.qt
@pytest.mark.parametrize("layout", _LAYOUTS, ids=lambda layout: layout.name)
def test_the_driver_reads_our_std430_records_through_the_ring(context, layout):
    count = 4
    program = compile_program(_VERTEX, _reader(layout, count), label="std430 probe")
    ring = StreamRing("std430 probe")
    canvas = _Canvas(context, len(layout.fields), count)
    try:
        # The driver's own offsets and record stride equal the Python layout's.
        stride = None
        for field, offset in zip((field for field, _type in layout.fields), layout.offsets):
            index = gl.glGetProgramResourceIndex(program, gl.GL_BUFFER_VARIABLE,
                                                 f"{layout.array}[0].{field}".encode())
            assert index != gl.GL_INVALID_INDEX, field
            props = (ctypes.c_uint * 2)(gl.GL_OFFSET, gl.GL_TOP_LEVEL_ARRAY_STRIDE)
            out = (ctypes.c_int * 2)()
            gl.glGetProgramResourceiv(program, gl.GL_BUFFER_VARIABLE, index, 2, props, 2, None, out)
            assert out[0] == offset, field
            stride = out[1]
        assert stride == layout.stride

        records = [_values(layout, row) for row in range(count)]
        gl.glUseProgram(program)
        with ring.bound(gl.GL_SHADER_STORAGE_BUFFER, 5, layout.pack(records)):
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        pixels = canvas.pixels()
        for row, record in enumerate(records):
            for column, (field, glsl_type) in enumerate(layout.fields):
                expected = np.atleast_1d(np.asarray(record[field], dtype=np.float64))
                if glsl_type == "mat4":
                    expected = expected[12:16]
                assert np.allclose(pixels[row, column, : expected.size], expected), (row, field)
    finally:
        canvas.close()
        gl.glDeleteProgram(program)
        ring.release()


@pytest.mark.qt
@pytest.mark.parametrize("target", (gl.GL_UNIFORM_BUFFER, gl.GL_SHADER_STORAGE_BUFFER), ids=("ubo", "ssbo"))
def test_binding_restores_the_indexed_range_and_never_touches_the_generic_binding(context, target):
    binding_name, start_name, size_name = {
        gl.GL_UNIFORM_BUFFER: (gl.GL_UNIFORM_BUFFER_BINDING, gl.GL_UNIFORM_BUFFER_START, gl.GL_UNIFORM_BUFFER_SIZE),
        gl.GL_SHADER_STORAGE_BUFFER: (gl.GL_SHADER_STORAGE_BUFFER_BINDING, gl.GL_SHADER_STORAGE_BUFFER_START,
                                      gl.GL_SHADER_STORAGE_BUFFER_SIZE),
    }[target]
    ring = StreamRing("binding probe")
    sentinel, generic = int(gl.glGenBuffers(1)), int(gl.glGenBuffers(1))
    try:
        gl.glBindBuffer(target, sentinel)
        gl.glBufferData(target, 1024, None, gl.GL_STATIC_DRAW)
        gl.glBindBufferRange(target, 6, sentinel, 512, 256)
        gl.glBindBuffer(target, generic)
        with ring.bound(target, 6, bytes(64)):
            assert gl_query.get_indexed_int(binding_name, 6) not in (0, sentinel)
            assert gl_query.get_int(binding_name) == generic
            ring.rebind(target, 6, bytes(32))
            assert gl_query.get_indexed_int64(size_name, 6) == 32
        assert gl_query.get_indexed_int(binding_name, 6) == sentinel
        assert gl_query.get_indexed_int64(start_name, 6) == 512
        assert gl_query.get_indexed_int64(size_name, 6) == 256
        assert gl_query.get_int(binding_name) == generic

        gl.glBindBufferBase(target, 6, sentinel)  # a whole-buffer binding comes back whole
        with ring.bound(target, 6, bytes(64)):
            pass
        assert gl_query.get_indexed_int(binding_name, 6) == sentinel
        assert gl_query.get_indexed_int64(size_name, 6) == 0
        assert gl.glGetError() == gl.GL_NO_ERROR
    finally:
        gl.glBindBufferBase(target, 6, 0)
        gl.glBindBuffer(target, 0)
        gl.glDeleteBuffers(2, [sentinel, generic])
        ring.release()


_COLUMN_READER = """#version 460 core
out vec4 FragColor;
layout(std430, binding = 5) readonly buffer Column { vec4 value; };
void main() { FragColor = value; }
"""


@pytest.mark.qt
def test_slots_are_reused_only_after_their_fence_and_every_draw_reads_its_own_values(context, monkeypatch):
    """Many unsynchronised frames over a tiny ring: each column must still show the values
    written for it, and every reused slot must have been waited on first."""
    # A slot holds exactly one frame, so every frame after the first rotates.
    ring = StreamRing("rotation probe", slots=2, slot_bytes=64, hold_bytes=64)
    frames = 48
    program = compile_program(_VERTEX, _COLUMN_READER, label="rotation probe")
    canvas = _Canvas(context, frames, 1)
    waited, fenced = [], []
    original_wait = ring._wait

    def recording_wait(slot):
        if ring._fences[slot] is not None:
            waited.append(slot)
        original_wait(slot)

    real_fence = gl.glFenceSync

    def recording_fence(*args):
        fenced.append(ring._slot)
        return real_fence(*args)

    monkeypatch.setattr(ring, "_wait", recording_wait)
    monkeypatch.setattr(stream_module.gl, "glFenceSync", recording_fence)
    try:
        gl.glUseProgram(program)
        gl.glEnable(gl.GL_SCISSOR_TEST)
        buffer = None
        for column in range(frames):
            gl.glScissor(column, 0, 1, 1)
            with ring.bound(gl.GL_SHADER_STORAGE_BUFFER, 5, np.array([column, 1, 2, 3], np.float32).tobytes()):
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            buffer = buffer or ring._buffer
            assert ring._buffer == buffer, "the ring never reallocates"
        gl.glDisable(gl.GL_SCISSOR_TEST)
        pixels = canvas.pixels()[0]
        assert np.array_equal(pixels[:, 0], np.arange(frames, dtype=np.float32))
        assert len(fenced) == frames - 1
        # After the first lap every rotation lands on a fenced slot and waits for it.
        assert len(waited) == frames - 2
        assert all(fence is None or slot != ring._slot for slot, fence in enumerate(ring._fences))
    finally:
        monkeypatch.undo()
        canvas.close()
        gl.glDeleteProgram(program)
        ring.release()


@pytest.mark.qt
def test_capacity_is_fixed_and_loud(context):
    ring = StreamRing("capacity probe", slots=2, slot_bytes=1024, hold_bytes=512)
    try:
        with pytest.raises(RuntimeError, match="per-frame capacity"):
            with ring.bound(gl.GL_SHADER_STORAGE_BUFFER, 5, bytes(400)):
                ring.rebind(gl.GL_SHADER_STORAGE_BUFFER, 5, bytes(200))
        assert gl_query.get_indexed_int(gl.GL_SHADER_STORAGE_BUFFER_BINDING, 5) == 0
        with pytest.raises(RuntimeError, match="inside bound"):
            ring.rebind(gl.GL_SHADER_STORAGE_BUFFER, 5, bytes(16))
        with pytest.raises(ValueError):
            StreamRing("bad", slots=1)
    finally:
        ring.release()


def test_a_ring_nobody_uses_owns_nothing_and_makes_no_gl_calls(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("dormant ring touched GL")

    for name in ("glCreateBuffers", "glNamedBufferStorage", "glMapNamedBufferRange", "glFenceSync"):
        monkeypatch.setattr(stream_module.gl, name, forbidden)
    ring = StreamRing("dormant probe")
    assert not ring.has_resources
    ring.release()
    assert not ring.has_resources


@pytest.mark.qt
def test_release_returns_to_zero_retries_failed_deletion_and_rebuilds(context, monkeypatch):
    ring = StreamRing("release probe", slots=2, slot_bytes=1024, hold_bytes=512)
    assert ring.warm() is False and ring.warm() is True
    first = ring._buffer
    for _ in range(4):  # leave a pending fence behind
        with ring.bound(gl.GL_UNIFORM_BUFFER, 7, bytes(16)):
            pass
    assert any(fence is not None for fence in ring._fences)

    real_delete = gl.glDeleteBuffers

    def failing_delete(*_args):
        raise RuntimeError("driver refused")

    monkeypatch.setattr(stream_module.gl, "glDeleteBuffers", failing_delete)
    with pytest.raises(RuntimeError, match="driver refused"):
        ring.release()
    assert ring.has_resources and ring._buffer == first, "a failed deletion keeps its handle"
    monkeypatch.setattr(stream_module.gl, "glDeleteBuffers", real_delete)
    ring.release()
    assert not ring.has_resources
    assert not gl.glIsBuffer(first)

    with ring.bound(gl.GL_UNIFORM_BUFFER, 7, bytes(16)):
        assert ring.has_resources
    ring.release()
    assert not ring.has_resources


@pytest.mark.qt
def test_a_failed_mapping_leaves_no_buffer_behind(context, monkeypatch):
    created = []
    real_create = gl.glCreateBuffers

    def recording_create(count, names):
        real_create(count, names)
        created.append(int(names[0]))

    monkeypatch.setattr(stream_module.gl, "glCreateBuffers", recording_create)
    monkeypatch.setattr(stream_module.gl, "glMapNamedBufferRange", lambda *_args: 0)
    ring = StreamRing("mapping probe")
    with pytest.raises(RuntimeError, match="mapping failed"):
        ring.warm()
    assert not ring.has_resources
    assert created and not gl.glIsBuffer(created[0])
