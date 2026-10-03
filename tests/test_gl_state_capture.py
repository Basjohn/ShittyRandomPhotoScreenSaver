"""CHK26 inherited-state capture: the direct per-frame reads (gl_state.py) return exactly what
PyOpenGL's own reads return, for every captured field, on the real driver; capture order and
restoration are untouched."""
from __future__ import annotations

import dataclasses
import random

import pytest

pytest.importorskip("OpenGL")


@pytest.fixture
def gl_context(qt_app):
    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(32, 32)
    yield capture
    capture.close()


def _reference(gl):
    """The capture as PyOpenGL's wrappers read it (the pre-fast-path implementation)."""
    def integer(name):
        value = gl.glGetIntegerv(name)
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(value[0])

    return dict(
        viewport=tuple(int(v) for v in gl.glGetIntegerv(gl.GL_VIEWPORT)),
        program=integer(gl.GL_CURRENT_PROGRAM), vao=integer(gl.GL_VERTEX_ARRAY_BINDING),
        array_buffer=integer(gl.GL_ARRAY_BUFFER_BINDING), blend=bool(gl.glIsEnabled(gl.GL_BLEND)),
        blend_src_rgb=integer(gl.GL_BLEND_SRC_RGB), blend_dst_rgb=integer(gl.GL_BLEND_DST_RGB),
        blend_src_alpha=integer(gl.GL_BLEND_SRC_ALPHA), blend_dst_alpha=integer(gl.GL_BLEND_DST_ALPHA),
        blend_equation_rgb=integer(gl.GL_BLEND_EQUATION_RGB),
        blend_equation_alpha=integer(gl.GL_BLEND_EQUATION_ALPHA), cull=bool(gl.glIsEnabled(gl.GL_CULL_FACE)),
        depth=bool(gl.glIsEnabled(gl.GL_DEPTH_TEST)), depth_write=bool(gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK)),
        color_mask=tuple(bool(v) for v in gl.glGetBooleanv(gl.GL_COLOR_WRITEMASK)),
    )


def test_direct_reads_match_pyopengl_for_every_field_on_the_real_driver(gl_context):
    from OpenGL import GL as gl
    from OpenGL.GL import shaders

    from rendering.quick.visualizer.gl_state import InheritedGlState

    program = int(shaders.compileProgram(
        shaders.compileShader("#version 330 core\nvoid main(){gl_Position=vec4(0.0);}", gl.GL_VERTEX_SHADER),
        shaders.compileShader("#version 330 core\nout vec4 c;void main(){c=vec4(1.0);}", gl.GL_FRAGMENT_SHADER),
        validate=False))
    vaos, buffers = list(gl.glGenVertexArrays(2)), list(gl.glGenBuffers(2))
    funcs = (gl.GL_ONE, gl.GL_ZERO, gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_DST_COLOR)
    equations = (gl.GL_FUNC_ADD, gl.GL_FUNC_SUBTRACT, gl.GL_MAX)
    rng = random.Random(26)
    for _ in range(60):
        gl.glViewport(rng.randint(-40, 40), rng.randint(-40, 40), rng.randint(1, 3840), rng.randint(1, 2160))
        gl.glUseProgram(rng.choice((0, program)))
        gl.glBindVertexArray(rng.choice((0, *vaos)))
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, rng.choice((0, *buffers)))
        for capability in (gl.GL_BLEND, gl.GL_CULL_FACE, gl.GL_DEPTH_TEST):
            (gl.glEnable if rng.random() < 0.5 else gl.glDisable)(capability)
        gl.glBlendFuncSeparate(*(rng.choice(funcs) for _ in range(4)))
        gl.glBlendEquationSeparate(rng.choice(equations), rng.choice(equations))
        gl.glDepthMask(rng.random() < 0.5)
        gl.glColorMask(*(rng.random() < 0.5 for _ in range(4)))
        expected = _reference(gl)
        assert dataclasses.asdict(InheritedGlState.capture_clipped_shared()) == expected
        assert dataclasses.asdict(InheritedGlState.capture_render_host()) == {**expected, "color_mask": None}
    gl.glUseProgram(0)
    gl.glDeleteProgram(program)


def test_the_capture_reads_every_frame_and_keeps_nothing(gl_context):
    """No inherited state is cached: a state change between two captures is always seen."""
    from OpenGL import GL as gl

    from rendering.quick.visualizer.gl_state import InheritedGlState

    gl.glViewport(0, 0, 10, 10)
    gl.glDisable(gl.GL_BLEND)
    first = InheritedGlState.capture_clipped_shared()
    gl.glViewport(3, 4, 50, 60)
    gl.glEnable(gl.GL_BLEND)
    second = InheritedGlState.capture_clipped_shared()
    assert (first.viewport, first.blend) == ((0, 0, 10, 10), False)
    assert (second.viewport, second.blend) == ((3, 4, 50, 60), True)
