"""The conventions include (N0.3 rule 3, plan N1.4) and the front-face rule (rule 4).

- The include is Vulkan GLSL: a fragment shader using every function and a compute shader using the mapping part bake
  with ``qsb`` for every shipped target.
- Its block sits at the one reserved binding, and no other resource in any discovered shader takes that binding.
- On OpenGL its values make every function an identity of the arithmetic it replaced (bit for bit, on a real context),
  and the flip is read from the block (with the flip on, ``fragTexel`` mirrors rows): the identity is not vacuous.
- One buffer per context, written once when the first program declaring the block links, held by those programs and
  deleted with the last of them (``delete_program``), never per frame.
- The front face is one function of the item matrix's handedness and the clip-space Y direction.
"""
from __future__ import annotations

import re

import numpy as np
import pytest

from rendering.gl_programs.conventions import (
    CONVENTIONS_BLOCK_NAME,
    OPENGL_CONVENTIONS,
    SRPSS_CONVENTIONS_FRAGMENT_GLSL,
    SRPSS_CONVENTIONS_GLSL,
    conventions_block,
    front_face_clockwise,
)
from rendering.gl_programs.scene3d import SCENE3D_COMPUTE_BLOCK_BINDING, SCENE3D_CONVENTIONS_BLOCK_BINDING
from rendering.quick.scene3d.uniforms import SCENE3D_UNIFORM_BINDING

_QUICK_MATRIX = (2 / 640, 0, 0, 0, 0, -2 / 360, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)   # Quick's item matrix: Y down
_MIRRORED = (-2 / 640, 0, 0, 0, 0, -2 / 360, 0, 0, 0, 0, 1, 0, 1, 1, 0, 1)

_FRAGMENT = ("#version 460 core\nlayout(location = 0) out vec4 Texel;\nlayout(location = 1) out vec4 Uv;\n"
             "layout(std140, binding = 0) uniform Size { vec2 uSize; };\n" + SRPSS_CONVENTIONS_FRAGMENT_GLSL + """
void main() {
    Texel = vec4(vec2(fragTexel(ivec2(uSize))), fragPixel(uSize));
    Uv = vec4(fragUv(uSize), ndcToUv(uvToNdc(fragUv(uSize))));
    gl_FragDepth = viewDepthFromDepthTexture(0.5);
}
""")
_VERTEX = """#version 460 core
void main() { vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2); gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0); }
"""


def test_the_include_bakes_for_every_shipped_target(tmp_path):
    from tools.vulkan_shader_readiness import _qsb, compile_source

    qsb = _qsb()
    if not qsb.exists():
        pytest.skip("this PySide6 has no qsb")
    assert compile_source(qsb, _FRAGMENT, tmp_path / "conventions.frag") == (True, "")
    compute = ("#version 460 core\nlayout(local_size_x = 8) in;\nlayout(std430, binding = 0) buffer B { vec2 v[]; };\n"
               + SRPSS_CONVENTIONS_GLSL + "void main() { uint i = gl_GlobalInvocationID.x; v[i] = ndcToUv(v[i]); }\n")
    assert compile_source(qsb, compute, tmp_path / "mapping.comp") == (True, "")
    # A stage without SRPSS_CONVENTIONS_FRAGMENT gets no gl_FragCoord function and no block.
    assert "gl_FragCoord" not in SRPSS_CONVENTIONS_GLSL.split("#if defined(SRPSS_CONVENTIONS_FRAGMENT)")[0]


def test_the_block_has_one_reserved_binding_no_other_resource_takes():
    from tools.vulkan_shader_readiness import discover

    assert SCENE3D_CONVENTIONS_BLOCK_BINDING not in (SCENE3D_UNIFORM_BINDING, SCENE3D_COMPUTE_BLOCK_BINDING)
    declaration = re.compile(rf"binding\s*=\s*{SCENE3D_CONVENTIONS_BLOCK_BINDING}\b")
    block_line = next(line for line in SRPSS_CONVENTIONS_GLSL.splitlines() if declaration.search(line))
    assert len(declaration.findall(SRPSS_CONVENTIONS_GLSL)) == 1
    holders = 0
    for source in discover()[0]:
        found = declaration.findall(source.text)
        # Only the include's own block line takes the binding (a source composed from several pieces may carry the
        # include more than once; its guard declares the block once).
        assert len(found) == source.text.count(block_line), f"{source.key} takes the conventions block's binding"
        holders += CONVENTIONS_BLOCK_NAME in source.text
    assert holders, "no shader includes the conventions block"


def test_the_opengl_values_flip_nothing():
    assert OPENGL_CONVENTIONS[0] == 0.0
    assert conventions_block() == bytes(16)
    assert len(conventions_block((1.0, 0.0, 0.0, 0.0))) == 16


@pytest.mark.parametrize(("matrix", "ndc_y_up", "clockwise"), [
    (_QUICK_MATRIX, True, False),    # today's draw: counter-clockwise front faces
    (_MIRRORED, True, True),         # a mirrored item turns the winding
    (_QUICK_MATRIX, False, True),    # a clip space whose Y points down turns it too
    (_MIRRORED, False, False),
])
def test_the_front_face_is_one_function_of_handedness_and_clip_space_y(matrix, ndc_y_up, clockwise):
    assert front_face_clockwise(matrix, ndc_y_up=ndc_y_up) is clockwise


def test_sphere_takes_its_winding_from_the_rule():
    from OpenGL import GL as gl

    from rendering.quick.visualizer.implementations.sphere_voxel import _winding

    assert _winding(_QUICK_MATRIX) == gl.GL_CCW
    assert _winding(_MIRRORED) == gl.GL_CW


class _Context:
    def __init__(self):
        from OpenGL import GL as gl
        from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext, QSurfaceFormat

        self.app = QGuiApplication.instance() or QGuiApplication([])
        fmt = QSurfaceFormat()
        fmt.setRenderableType(QSurfaceFormat.OpenGL)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        fmt.setVersion(4, 6)
        self.context = QOpenGLContext()
        self.context.setFormat(fmt)
        assert self.context.create()
        self.surface = QOffscreenSurface()
        self.surface.setFormat(self.context.format())
        self.surface.create()
        assert self.context.makeCurrent(self.surface)
        self.vao = int(gl.glGenVertexArrays(1))

    def close(self):
        from OpenGL import GL as gl

        gl.glDeleteVertexArrays(1, [self.vao])
        self.context.doneCurrent()


def _bound_conventions() -> int:
    import ctypes

    from OpenGL import GL as gl

    value = (ctypes.c_int * 1)()
    gl.glGetIntegeri_v(gl.GL_UNIFORM_BUFFER_BINDING, SCENE3D_CONVENTIONS_BLOCK_BINDING, value)
    return int(value[0])


def _draw(program: int, vao: int, size: tuple[int, int], flip: bool = False) -> tuple[np.ndarray, np.ndarray]:
    import ctypes

    from OpenGL import GL as gl

    width, height = size
    name = (ctypes.c_uint * 1)()
    targets = []
    gl.glCreateFramebuffers(1, name)
    fbo = int(name[0])
    for location in range(2):
        gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
        texture = int(name[0])
        gl.glTextureStorage2D(texture, 1, gl.GL_RGBA32F, width, height)
        gl.glNamedFramebufferTexture(fbo, gl.GL_COLOR_ATTACHMENT0 + location, texture, 0)
        targets.append(texture)
    gl.glNamedFramebufferDrawBuffers(fbo, 2, [gl.GL_COLOR_ATTACHMENT0, gl.GL_COLOR_ATTACHMENT1])
    gl.glCreateBuffers(1, name)
    sizes = int(name[0])
    data = np.array([width, height, 0, 0], dtype=np.float32).tobytes()
    gl.glNamedBufferStorage(sizes, len(data), data, 0)
    gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, 0, sizes)
    flipped, previous = 0, _bound_conventions()
    if flip:
        gl.glCreateBuffers(1, name)
        flipped = int(name[0])
        block = conventions_block((1.0, 0.0, 0.0, 0.0))
        gl.glNamedBufferStorage(flipped, len(block), block, 0)
        gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, SCENE3D_CONVENTIONS_BLOCK_BINDING, flipped)
    try:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glViewport(0, 0, width, height)
        gl.glUseProgram(program)
        gl.glBindVertexArray(vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        out = []
        for texture in targets:
            pixels = np.empty((height, width, 4), dtype=np.float32)
            gl.glGetTextureImage(texture, 0, gl.GL_RGBA, gl.GL_FLOAT, pixels.nbytes, pixels)
            out.append(pixels)
        return out[0], out[1]
    finally:
        if flipped:
            gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, SCENE3D_CONVENTIONS_BLOCK_BINDING, previous)
            gl.glDeleteBuffers(1, [flipped])
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures(2, targets)
        gl.glDeleteBuffers(1, [sizes])


@pytest.mark.qt
def test_on_opengl_every_function_is_the_arithmetic_it_replaced_and_the_flip_is_read_from_the_block(qt_app):
    from rendering.quick.render.gl_resources import compile_program, delete_program

    context = _Context()
    size = (37, 23)                 # odd and non-square: a width/height mix-up or an off-by-one shows
    reference = _FRAGMENT.split(SRPSS_CONVENTIONS_FRAGMENT_GLSL)[0] + """
void main() {
    Texel = vec4(vec2(ivec2(gl_FragCoord.xy)), gl_FragCoord.xy);
    Uv = vec4(gl_FragCoord.xy / uSize, (gl_FragCoord.xy / uSize * 2.0 - 1.0) * 0.5 + 0.5);
    gl_FragDepth = 0.5;
}
"""
    try:
        include = compile_program(_VERTEX, _FRAGMENT, label="conventions test")
        plain = compile_program(_VERTEX, reference, label="conventions reference")
        try:
            texel, uv = _draw(include, context.vao, size)
            texel_ref, uv_ref = _draw(plain, context.vao, size)
            assert texel.tobytes() == texel_ref.tobytes()
            assert uv.tobytes() == uv_ref.tobytes()
            # With the flip on (another backend's value), rows mirror: the functions read the block.
            flipped, _ = _draw(include, context.vao, size, flip=True)
            rows = np.arange(size[1], dtype=np.float32)[:, None]
            assert np.array_equal(texel_ref[..., 1], rows * np.ones((1, size[0]), np.float32))
            assert np.array_equal(flipped[..., 1], (size[1] - 1 - rows) * np.ones((1, size[0]), np.float32))
            assert np.array_equal(flipped[..., 0], texel_ref[..., 0])
        finally:
            delete_program(include)
            delete_program(plain)
    finally:
        context.close()


def _native(qobject) -> int:
    import shiboken6

    return int(shiboken6.getCppPointer(qobject)[0])


class _QtOwnedContext:
    """Qt's global share context, current on an offscreen surface. Qt creates it in C++ (``AA_ShareOpenGLContexts``,
    set by ``configure_quick_graphics`` as the product sets it), as it creates Qt Quick's render-thread context, and
    the test keeps no wrapper of it, as the product keeps none: PySide makes a new wrapper per ``currentContext()``
    call whenever Python holds none. ``key`` is the context's native pointer."""

    def __init__(self):
        import gc

        from PySide6.QtGui import QOffscreenSurface, QOpenGLContext

        share = QOpenGLContext.globalShareContext()
        if share is None:
            pytest.skip("no context created by Qt (AA_ShareOpenGLContexts is not set)")
        self.surface = QOffscreenSurface()
        self.surface.setFormat(share.format())
        self.surface.create()
        assert share.makeCurrent(self.surface)
        self.key = _native(share)
        del share
        gc.collect()

    @staticmethod
    def churn():
        """Ordinary allocations and a collection between two calls, as a render thread makes them."""
        import gc

        _junk = [(float(i), str(i), [i]) for i in range(500)]
        del _junk
        gc.collect()

    def close(self):
        from PySide6.QtGui import QOpenGLContext

        current = QOpenGLContext.currentContext()
        if current is not None:
            current.doneCurrent()


def _held_by(key: int) -> list[int]:
    from rendering.quick.render import gl_resources

    return sorted(program for context, program in gl_resources._convention_programs if context == key)


@pytest.mark.qt
def test_one_buffer_per_context_held_by_the_programs_that_declare_it(qt_app):
    from OpenGL import GL as gl

    from rendering.quick.render.gl_resources import compile_program, delete_program

    context = _QtOwnedContext()
    plain_fragment = "#version 460 core\nout vec4 C;\nvoid main() { C = vec4(1.0); }\n"
    generic = gl.glGetIntegerv(gl.GL_UNIFORM_BUFFER_BINDING)
    try:
        plain = compile_program(_VERTEX, plain_fragment, label="no conventions")
        assert _bound_conventions() == 0                   # a program without the block holds nothing
        first = compile_program(_VERTEX, _FRAGMENT, label="conventions a")
        buffer = _bound_conventions()
        assert buffer and gl.glIsBuffer(buffer)
        values = np.zeros(4, dtype=np.float32)
        gl.glGetNamedBufferSubData(buffer, 0, 16, values)
        assert values.tobytes() == conventions_block()     # this renderer's values, written at creation
        second = compile_program(_VERTEX, _FRAGMENT.replace("0.5", "0.25"), label="conventions b")
        assert _bound_conventions() == buffer              # one buffer for the context
        assert gl.glGetIntegerv(gl.GL_UNIFORM_BUFFER_BINDING) == generic   # the generic binding is untouched
        delete_program(first)
        assert _bound_conventions() == buffer and gl.glIsBuffer(buffer)
        delete_program(second)                             # the last holder: the buffer goes with it
        assert not gl.glIsBuffer(buffer)
        delete_program(plain)
        third = compile_program(_VERTEX, _FRAGMENT, label="conventions again")
        assert _bound_conventions() and gl.glIsBuffer(_bound_conventions())   # a later holder writes it again
        delete_program(third)
    finally:
        context.close()


@pytest.mark.qt
def test_a_context_qt_owns_has_one_entry_one_buffer_and_every_hold_with_no_wrapper_kept(qt_app):
    """The audit's probe as a guard (Fable, 12 Nov evening): N links in one context Qt owns, the wrapper dropped and
    memory churned between calls. Keyed by ``id()`` of the wrapper this gave N entries, N buffers, holds of 1 each, and
    all of them left after the deletes."""
    from OpenGL import GL as gl

    from rendering.quick.render import gl_resources
    from rendering.quick.render.gl_resources import compile_program, delete_program

    count = 6
    context = _QtOwnedContext()
    before = dict(gl_resources._conventions)
    programs = []
    try:
        for index in range(count):
            programs.append(compile_program(_VERTEX, _FRAGMENT.replace("0.5", repr(0.1 * (index + 1))),
                                            label=f"qt-owned holder {index}"))
            context.churn()
        added = {key: entry for key, entry in gl_resources._conventions.items() if key not in before}
        assert list(added) == [context.key]                           # one entry, for this context
        buffer, holds = added[context.key][:2]
        assert holds == count and _held_by(context.key) == sorted(programs)
        assert _bound_conventions() == buffer and gl.glIsBuffer(buffer)   # one buffer, bound here
        for program in programs[:-1]:
            delete_program(program)
            context.churn()
        assert gl_resources._conventions[context.key][1] == 1 and gl.glIsBuffer(buffer)
        delete_program(programs[-1])                                  # the last hold deletes the buffer
        programs.clear()
        assert context.key not in gl_resources._conventions
        assert not gl.glIsBuffer(buffer) and _held_by(context.key) == []
        assert dict(gl_resources._conventions) == before              # nothing else was left
    finally:
        for program in programs:
            delete_program(program)
        context.close()


@pytest.mark.qt
def test_two_sharing_contexts_each_bind_their_own_buffer_and_a_foreign_delete_is_refused(qt_app, caplog):
    """A second display's context shares the first's objects but not its bindings: each context that links a holder
    gets its own buffer at the binding. A holder deleted from the other context keeps its hold, loudly, rather than
    unbinding the block where it was linked."""
    from OpenGL import GL as gl
    from PySide6.QtGui import QOpenGLContext

    from rendering.quick.render import gl_resources
    from rendering.quick.render.gl_resources import compile_program, delete_program

    first = _QtOwnedContext()
    second = QOpenGLContext()
    second.setFormat(QOpenGLContext.globalShareContext().format())
    second.setShareContext(QOpenGLContext.globalShareContext())
    assert second.create()
    try:
        held_first = compile_program(_VERTEX, _FRAGMENT, label="first display holder")
        buffer_first = _bound_conventions()
        first.churn()
        assert second.makeCurrent(first.surface)
        held_second = compile_program(_VERTEX, _FRAGMENT, label="second display holder")
        buffer_second = _bound_conventions()
        assert buffer_second and buffer_second != buffer_first        # bound in this context too, its own buffer
        assert gl_resources._conventions[_native(second)][1] == 1
        with caplog.at_level("ERROR"):
            delete_program(held_first)                                # from the wrong context
        assert any("outside the context" in record.getMessage() for record in caplog.records)
        assert _held_by(first.key) == [held_first]                    # the hold is kept
        delete_program(held_second)
        assert not gl.glIsBuffer(buffer_second)
        assert QOpenGLContext.globalShareContext().makeCurrent(first.surface)
        assert _bound_conventions() == buffer_first and gl.glIsBuffer(buffer_first)
        gl_resources._release_conventions(held_first)                 # its program is gone; hand the hold back here
        assert first.key not in gl_resources._conventions and not gl.glIsBuffer(buffer_first)
    finally:
        first.close()
        second.doneCurrent()


@pytest.mark.qt
def test_a_destroyed_context_leaves_no_entry(qt_app):
    """A context that goes with holders still linked (its objects go with it) is forgotten exactly once, so a later
    context at the same native address starts clean."""
    import gc

    from rendering.quick.render import gl_resources
    from rendering.quick.render.gl_resources import compile_program

    context = _Context()
    key = _native(context.context)
    compile_program(_VERTEX, _FRAGMENT, label="holder left to its context")
    assert gl_resources._conventions[key][1] == 1
    context.close()
    context.context = None
    del context
    gc.collect()
    assert key not in gl_resources._conventions and _held_by(key) == []
    assert key not in getattr(gl_resources, "_watched_contexts", ())
