"""Small lazy GL resource primitives for 3D scenes: programs, meshes, underlay, depth.

Shared by the mesh transitions and available to Visualizer modes. This owns
neither state nor a clock; the consumer's host fences inherited GL state and
every handle stays with its context-local renderer.
"""
from __future__ import annotations

from array import array

from OpenGL import GL as gl

from rendering.gl_programs.scene3d import SCENE3D_GLSL
from rendering.quick import gl_query as _query
from rendering.quick.render.gl_resources import compile_compute_program, compile_program
from .frame import ITEM_QUAD_VERTEX_SOURCE, SceneFrame


_IMAGE_FRAGMENT = """#version 460 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uImage;
void main() { FragColor = texture(uImage, vec2(vUv.x, 1.0-vUv.y)); }
"""

# The photograph plane (z = 0) through a moving camera; texture v runs down the item.
_CAMERA_PLANE_VERTEX = (
    "#version 460 core\n"
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
_CAMERA_PLANE_FRAGMENT = """#version 460 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uImage;
void main() { FragColor = texture(uImage, vUv); }
"""


def pack_floats(values) -> bytes:
    """Pack floats as C ``float`` bytes, ready for immutable mesh storage.

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


def _create_one(create) -> int:
    """Call PyOpenGL's output-array DSA creation wrappers for one object."""
    names = (gl.GLuint * 1)()
    create(1, names)
    return int(names[0])


def warm_programs(entries) -> bool:
    """One step of a gradual warm-up over (resources, key, vertex, fragment) entries, or
    (resources, key, compute) for a compute program: compile the first program not yet
    compiled, and only that one. True once all are compiled.

    An ordinary synchronous compile on the calling (render) thread: no driver compile threads,
    no status polling, nothing left running between steps."""
    for resources, key, *sources in entries:
        if resources.has_program(key):
            continue
        if len(sources) == 1:
            resources.compute_program(key, sources[0])
        else:
            resources.program(key, *sources)
        return False
    return True


class _UniformLocations(dict[str, int]):
    """One linked program's locations and its one-time image-sampler setup.

    Instances live only in ``MeshResources._uniforms`` alongside the owning
    program.  Releasing programs drops the mapping too, so a reused GL name
    can never inherit sampler setup from an earlier program generation.
    """

    def __init__(
        self,
        locations: dict[str, int],
        image_samplers: tuple[tuple[int, int, str], ...],
    ) -> None:
        super().__init__(locations)
        self.image_samplers = image_samplers
        self.image_sampler_units_initialized = False


def bind_frame(program: int, uniforms: _UniformLocations, frame: SceneFrame) -> None:
    """Use the program with the frame's matrix and item size; a transition frame's
    source/destination textures bind to units 0/1 when the program declares them.

    ``QuickTransitionRenderFrame`` guarantees both image names are live.  Bind
    only the units the program declares: unlike ``glBindTexture``, a zero name
    given to ``glBindTextures`` unbinds every texture target on that unit.
    """
    gl.glUseProgram(program)
    gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
    gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
    samplers = uniforms.image_samplers
    if not samplers:
        return
    gl.glBindTextures(
        samplers[0][0],
        len(samplers),
        tuple(getattr(frame, attribute) for _unit, _location, attribute in samplers),
    )
    if not uniforms.image_sampler_units_initialized:
        for unit, location, _attribute in samplers:
            if location >= 0:
                gl.glProgramUniform1i(program, location, unit)
        uniforms.image_sampler_units_initialized = True


class MeshResources:
    """Finite named programs/meshes; failed deletions retain their handles."""

    def __init__(self, label: str) -> None:
        self.label = label
        self._programs: dict[str, int] = {}
        self._uniforms: dict[str, _UniformLocations] = {}
        self._meshes: dict[str, tuple[int, int, int]] = {}
        self._instance_buffers: dict[str, int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._programs or self._meshes)

    def program(self, key: str, vertex_source: str, fragment_source: str) -> int:
        if key not in self._programs:
            self._programs[key] = compile_program(vertex_source, fragment_source, label=f"{self.label} {key}")
        return self._programs[key]

    def compute_program(self, key: str, source: str) -> int:
        if key not in self._programs:
            self._programs[key] = compile_compute_program(source, label=f"{self.label} {key}")
        return self._programs[key]

    def has_mesh(self, key: str) -> bool:
        return key in self._meshes

    def has_program(self, key: str) -> bool:
        return key in self._programs

    def uniforms(self, key: str, names: tuple[str, ...], *, required: bool = True) -> _UniformLocations:
        """Uniform locations, looked up once. A missing uniform is an error unless the program is
        a variant whose driver may drop what its output no longer reads (``required=False``:
        location -1, which ``glUniform*`` ignores)."""
        if key not in self._uniforms:
            locations = {name: int(gl.glGetUniformLocation(self._programs[key], name)) for name in names}
            missing = [name for name, location in locations.items() if location < 0]
            if missing and required:
                raise RuntimeError(f"{self.label} {key} missing uniforms: {', '.join(missing)}")
            image_samplers = tuple(
                (unit, locations[name], attribute)
                for unit, name, attribute in (
                    (0, "uOldTex", "source_texture_id"),
                    (1, "uNewTex", "destination_texture_id"),
                )
                if name in locations
            )
            if image_samplers and image_samplers[-1][0] - image_samplers[0][0] + 1 != len(image_samplers):
                raise RuntimeError(f"{self.label} {key} image samplers must occupy contiguous texture units")
            self._uniforms[key] = _UniformLocations(locations, image_samplers)
        return self._uniforms[key]

    def mesh(
        self,
        key: str,
        vertices: tuple[float, ...] | bytes,
        attributes: tuple[int, ...],
        *,
        instances: tuple[float, ...] | bytes | None = None,
        instance_attributes: tuple[int, ...] = (),
    ) -> tuple[int, int]:
        """Upload interleaved float vertices once; *vertices* may be packed C-float bytes.

        ``instances`` (optional, interleaved floats or packed bytes) is a static per-instance
        stream on the same VAO (binding 1, divisor 1); its attributes follow the vertex ones
        (``instance_attributes`` sizes). The caller draws it instanced."""
        held = self._meshes.get(key)
        if held is not None:
            vao, _vbo, count = held
            if count < 0:
                raise RuntimeError(f"{self.label} mesh {key} allocation is incomplete; release before retrying")
            return vao, count
        stride = sum(attributes)
        packed_bytes = isinstance(vertices, (bytes, bytearray))
        if packed_bytes and len(vertices) % 4:
            raise ValueError("packed mesh bytes must hold whole 32-bit floats")
        float_count = len(vertices) // 4 if packed_bytes else len(vertices)
        if not stride or float_count % stride:
            raise ValueError("interleaved mesh must contain complete vertices")
        instance_data = b""
        if instances is not None:
            instance_data = bytes(instances) if isinstance(instances, (bytes, bytearray)) else pack_floats(instances)
            instance_stride = sum(instance_attributes)
            if not instance_stride or len(instance_data) % (4 * instance_stride):
                raise ValueError("interleaved instances must contain complete records")
        vao = _create_one(gl.glCreateVertexArrays)
        self._meshes[key] = (vao, 0, -1)
        vbo = _create_one(gl.glCreateBuffers)
        self._meshes[key] = (vao, vbo, -1)
        if not vao or not vbo:
            raise RuntimeError(f"{self.label} mesh allocation failed")
        data = bytes(vertices) if packed_bytes else pack_floats(vertices)
        gl.glNamedBufferStorage(vbo, len(data), data, 0)
        gl.glVertexArrayVertexBuffer(vao, 0, vbo, 0, stride * 4)
        offset = 0
        for index, size in enumerate(attributes):
            gl.glEnableVertexArrayAttrib(vao, index)
            gl.glVertexArrayAttribFormat(vao, index, size, gl.GL_FLOAT, gl.GL_FALSE, offset * 4)
            gl.glVertexArrayAttribBinding(vao, index, 0)
            offset += size
        if instances is not None:
            instance_vbo = _create_one(gl.glCreateBuffers)
            if not instance_vbo:
                raise RuntimeError(f"{self.label} instance allocation failed")
            self._instance_buffers[key] = instance_vbo
            gl.glNamedBufferStorage(instance_vbo, len(instance_data), instance_data, 0)
            gl.glVertexArrayVertexBuffer(vao, 1, instance_vbo, 0, sum(instance_attributes) * 4)
            gl.glVertexArrayBindingDivisor(vao, 1, 1)
            offset = 0
            for index, size in enumerate(instance_attributes, start=len(attributes)):
                gl.glEnableVertexArrayAttrib(vao, index)
                gl.glVertexArrayAttribFormat(vao, index, size, gl.GL_FLOAT, gl.GL_FALSE, offset * 4)
                gl.glVertexArrayAttribBinding(vao, index, 1)
                offset += size
        count = float_count // stride
        self._meshes[key] = (vao, vbo, count)
        return vao, count

    def drop_mesh(self, key: str) -> None:
        mesh = self._meshes.get(key)
        if mesh is None:
            return
        vao, vbo, count = mesh
        # Record each successful deletion even if the following one fails.
        instance_vbo = self._instance_buffers.get(key)
        if instance_vbo:
            gl.glDeleteBuffers(1, [instance_vbo])
            del self._instance_buffers[key]
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
