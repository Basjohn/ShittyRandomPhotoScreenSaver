"""Small lazy GL resource primitives for 3D scenes: programs, meshes, underlay, depth.

Shared by the mesh transitions and available to Visualizer modes. This owns
neither state nor a clock; the consumer's host fences inherited GL state and
every handle stays with its context-local renderer.
"""
from __future__ import annotations

from array import array
import ctypes

from OpenGL import GL as gl

from rendering.gl_programs.scene3d import SCENE3D_GLSL
from rendering.quick import gl_query as _query
from rendering.quick.render.gl_resources import compile_program
from .frame import ITEM_QUAD_VERTEX_SOURCE, SceneFrame


_IMAGE_FRAGMENT = """#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uImage;
void main() { FragColor = texture(uImage, vec2(vUv.x, 1.0-vUv.y)); }
"""

# The photograph plane (z = 0) through a moving camera; texture v runs down the item.
_CAMERA_PLANE_VERTEX = (
    "#version 410 core\n"
    "layout(location = 0) in vec2 aPosition;\n"
    "uniform mat4 uMatrix; uniform vec2 uItemSize; uniform vec4 uCameraA; uniform vec4 uCameraB;\n"
    "out vec2 vUv;\n"
    + SCENE3D_GLSL
    + """
void main() {
    float aspect = uItemSize.x / uItemSize.y;
    vUv = aPosition;
    gl_Position = sceneProjectCamera(uMatrix, uItemSize, vec3((aPosition.x - 0.5) * aspect, 0.5 - aPosition.y, 0.0),
                                     uCameraA, uCameraB);
}
"""
)
_CAMERA_PLANE_FRAGMENT = """#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uImage;
void main() { FragColor = texture(uImage, vUv); }
"""


def pack_floats(values) -> bytes:
    """Pack floats as C ``float`` bytes, ready for ``glBufferData``.

    Byte-identical to ``(ctypes.c_float * n)(*values)`` at roughly a third of the
    cost (Glass default: 153k floats, 14 ms -> 4 ms on the render thread), and it
    creates no ctypes array type. ctypes caches one type per array length
    forever, so building ``c_float * n`` for a per-run mesh size added one
    permanent type per distinct size (R-99); PyOpenGL passes ``bytes`` as a
    plain pointer.
    """
    return array("f", values).tobytes()


# (key, vertex, fragment) of the image underlay ``draw_image`` uses (for a gradual warm-up).
UNDERLAY_PROGRAM = ("underlay", ITEM_QUAD_VERTEX_SOURCE, _IMAGE_FRAGMENT)


def warm_programs(entries) -> bool:
    """One step of a gradual warm-up over (resources, key, vertex, fragment) entries: compile
    the first program not yet compiled, and only that one. True once all are compiled.

    An ordinary synchronous compile on the calling (render) thread: no driver compile threads,
    no status polling, nothing left running between steps."""
    for resources, key, vertex, fragment in entries:
        if resources.has_program(key):
            continue
        resources.program(key, vertex, fragment)
        return False
    return True


def bind_frame(program: int, uniforms: dict[str, int], frame: SceneFrame) -> None:
    """Use the program with the frame's matrix and item size; a transition frame's
    source/destination textures bind to units 0/1 when the program declares them."""
    gl.glUseProgram(program)
    gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
    gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
    for unit, name, attribute in (
        (0, "uOldTex", "source_texture_id"),
        (1, "uNewTex", "destination_texture_id"),
    ):
        if name in uniforms:
            gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
            gl.glBindTexture(gl.GL_TEXTURE_2D, getattr(frame, attribute))
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

    def has_program(self, key: str) -> bool:
        return key in self._programs

    def uniforms(self, key: str, names: tuple[str, ...], *, required: bool = True) -> dict[str, int]:
        """Uniform locations, looked up once. A missing uniform is an error unless the program is
        a variant whose driver may drop what its output no longer reads (``required=False``:
        location -1, which ``glUniform*`` ignores)."""
        if key not in self._uniforms:
            locations = {name: int(gl.glGetUniformLocation(self._programs[key], name)) for name in names}
            missing = [name for name, location in locations.items() if location < 0]
            if missing and required:
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
            data = bytes(vertices) if packed_bytes else pack_floats(vertices)
            gl.glBindVertexArray(vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, len(data), data, gl.GL_STATIC_DRAW)
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

    def draw_image(self, frame: SceneFrame, texture_id: int) -> None:
        program = self.program("underlay", ITEM_QUAD_VERTEX_SOURCE, _IMAGE_FRAGMENT)
        uniforms = self.uniforms("underlay", ("uMatrix", "uItemSize", "uImage"))
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
        gl.glUniform1i(uniforms["uImage"], 0)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def draw_camera_plane(
        self,
        frame: SceneFrame,
        texture_id: int,
        camera_a: tuple[float, float, float, float],
        camera_b: tuple[float, float, float, float],
    ) -> None:
        """The photograph at z = 0 seen through a moving camera (see ``sceneProjectCamera``).

        At rest this draws the same pixels as ``draw_image``; while the camera moves,
        its zoom must come from ``scene3d_camera_overscan`` so no frame edge shows.
        """
        program = self.program("camera_plane", _CAMERA_PLANE_VERTEX, _CAMERA_PLANE_FRAGMENT)
        uniforms = self.uniforms("camera_plane", ("uMatrix", "uItemSize", "uImage", "uCameraA", "uCameraB"))
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glUniform4f(uniforms["uCameraA"], *camera_a)
        gl.glUniform4f(uniforms["uCameraB"], *camera_b)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
        gl.glUniform1i(uniforms["uImage"], 0)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    @staticmethod
    def begin_depth(frame: SceneFrame) -> None:
        """Clear only the admitted viewport intersected with Quick's clip."""
        enabled = bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        inherited = _query.get_ints(gl.GL_SCISSOR_BOX, 4)
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
