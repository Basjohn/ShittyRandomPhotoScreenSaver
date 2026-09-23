"""Small lazy GL resource primitives shared by the admitted mesh transitions.

This owns neither transition state nor a clock. The existing transition host
fences inherited GL state; every handle stays with its context-local renderer.
"""
from __future__ import annotations

from array import array
import ctypes
import math

from OpenGL import GL as gl

from rendering.quick.render.gl_resources import compile_program
from .render_contract import QUICK_TRANSITION_VERTEX_SOURCE, QuickTransitionRenderFrame


_IMAGE_FRAGMENT = """#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uImage;
void main() { FragColor = texture(uImage, vec2(vUv.x, 1.0-vUv.y)); }
"""

_DIRECTIONS = {
    "left": (-1.0, 0.0), "right": (1.0, 0.0),
    "up": (0.0, -1.0), "down": (0.0, 1.0),
    "diag_tl_br": (1.0, 1.0), "diag_tr_bl": (-1.0, 1.0),
    "diag_bl_tr": (1.0, -1.0), "diag_br_tl": (-1.0, -1.0),
}


def direction_vector(direction: object) -> tuple[float, float]:
    value = _DIRECTIONS.get(str(direction))
    if value is None:
        raise ValueError(f"unresolved mesh transition direction: {direction!r}")
    length = math.hypot(*value)
    return value[0] / length, value[1] / length


def pack_floats(values) -> tuple[array, ctypes.Array]:
    """Pack floats as C ``float`` without star-unpacking into a ctypes constructor.

    Byte-identical to ``(ctypes.c_float * n)(*values)`` at roughly a third of the
    cost (Glass default: 153k floats, 14 ms -> 4 ms on the render thread). The
    returned ctypes array is a view of the returned ``array``; keep both alive
    until the upload has consumed them.
    """
    storage = array("f", values)
    return storage, (ctypes.c_float * len(storage)).from_buffer(storage)


def bind_frame(program: int, uniforms: dict[str, int], frame: QuickTransitionRenderFrame) -> None:
    gl.glUseProgram(program)
    gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
    gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
    for unit, name, texture in (
        (0, "uOldTex", frame.source_texture_id),
        (1, "uNewTex", frame.destination_texture_id),
    ):
        if name in uniforms:
            gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glUniform1i(uniforms[name], unit)


class MeshResources:
    """Finite named programs/meshes; failed deletions retain their handles."""

    def __init__(self, label: str) -> None:
        self.label = label
        self._programs: dict[str, int] = {}
        self._uniforms: dict[str, dict[str, int]] = {}
        self._meshes: dict[str, tuple[int, int, int]] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._programs or self._meshes)

    def program(self, key: str, vertex_source: str, fragment_source: str) -> int:
        if key not in self._programs:
            self._programs[key] = compile_program(vertex_source, fragment_source, label=f"{self.label} {key}")
        return self._programs[key]

    def uniforms(self, key: str, names: tuple[str, ...]) -> dict[str, int]:
        if key not in self._uniforms:
            locations = {name: int(gl.glGetUniformLocation(self._programs[key], name)) for name in names}
            missing = [name for name, location in locations.items() if location < 0]
            if missing:
                raise RuntimeError(f"{self.label} {key} missing uniforms: {', '.join(missing)}")
            self._uniforms[key] = locations
        return self._uniforms[key]

    def mesh(
        self,
        key: str,
        vertices: tuple[float, ...] | bytes,
        attributes: tuple[int, ...],
    ) -> tuple[int, int]:
        """Upload interleaved float vertices once; *vertices* may be packed C-float bytes."""
        if key not in self._meshes:
            stride = sum(attributes)
            packed_bytes = isinstance(vertices, (bytes, bytearray))
            if packed_bytes and len(vertices) % 4:
                raise ValueError("packed mesh bytes must hold whole 32-bit floats")
            float_count = len(vertices) // 4 if packed_bytes else len(vertices)
            if not stride or float_count % stride:
                raise ValueError("interleaved mesh must contain complete vertices")
            vao = int(gl.glGenVertexArrays(1))
            self._meshes[key] = (vao, 0, 0)
            vbo = int(gl.glGenBuffers(1))
            self._meshes[key] = (vao, vbo, 0)
            if not vao or not vbo:
                raise RuntimeError(f"{self.label} mesh allocation failed")
            if packed_bytes:
                values = (ctypes.c_float * float_count).from_buffer_copy(vertices)
            else:
                _storage, values = pack_floats(vertices)
            gl.glBindVertexArray(vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(values), values, gl.GL_STATIC_DRAW)
            offset = 0
            for index, size in enumerate(attributes):
                gl.glEnableVertexAttribArray(index)
                gl.glVertexAttribPointer(index, size, gl.GL_FLOAT, gl.GL_FALSE, stride * 4, ctypes.c_void_p(offset * 4))
                offset += size
            self._meshes[key] = (vao, vbo, float_count // stride)
        vao, _vbo, count = self._meshes[key]
        return vao, count

    def drop_mesh(self, key: str) -> None:
        mesh = self._meshes.get(key)
        if mesh is None:
            return
        vao, vbo, count = mesh
        # Record each successful deletion even if the following one fails.
        if vbo:
            gl.glDeleteBuffers(1, [vbo])
            vbo = 0
            self._meshes[key] = (vao, vbo, count)
        if vao:
            gl.glDeleteVertexArrays(1, [vao])
        del self._meshes[key]

    def draw_image(self, frame: QuickTransitionRenderFrame, texture_id: int) -> None:
        program = self.program("underlay", QUICK_TRANSITION_VERTEX_SOURCE, _IMAGE_FRAGMENT)
        uniforms = self.uniforms("underlay", ("uMatrix", "uItemSize", "uImage"))
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
        gl.glUniform1i(uniforms["uImage"], 0)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    @staticmethod
    def begin_depth(frame: QuickTransitionRenderFrame) -> None:
        """Clear only the admitted viewport intersected with Quick's clip."""
        enabled = bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        inherited = tuple(int(v) for v in gl.glGetIntegerv(gl.GL_SCISSOR_BOX))
        x, y, width, height = frame.viewport
        if enabled:
            sx, sy, sw, sh = inherited
            right, top = min(x + width, sx + sw), min(y + height, sy + sh)
            x, y = max(x, sx), max(y, sy)
            width, height = max(0, right - x), max(0, top - y)
        gl.glDepthMask(gl.GL_TRUE)
        try:
            gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glScissor(x, y, width, height)
            gl.glClearDepth(1.0)
            gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
        finally:
            gl.glScissor(*inherited)
            if not enabled:
                gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)

    def release_resources(self) -> None:
        errors: list[str] = []
        for key in tuple(self._meshes):
            try:
                self.drop_mesh(key)
            except Exception as exc:
                errors.append(f"mesh {key}: {exc}")
        for key, program in tuple(self._programs.items()):
            try:
                gl.glDeleteProgram(program)
            except Exception as exc:
                errors.append(f"program {key}: {exc}")
            else:
                del self._programs[key]
                self._uniforms.pop(key, None)
        if errors:
            raise RuntimeError(f"{self.label} cleanup incomplete: {' | '.join(errors)}")
