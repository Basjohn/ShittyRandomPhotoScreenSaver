"""Shared inherited OpenGL state fence for Qt Quick visualizer rendering.

The clipped visualizer path needs the same non-stencil Qt Quick state in three
places: the rounded-mask draw, the mode render host, and the rounded-mask
teardown.  Capture it once at the first mask boundary and carry that immutable
snapshot through the locally-owned render operation rather than issuing a
second/third set of synchronous ``glGet*`` queries.

Stencil/scissor ownership deliberately remains in ``clip_host`` because those
states are coupled to QSGRenderNode.RenderState and the nested clip contract.
"""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from dataclasses import dataclass

from OpenGL import GL as gl
from OpenGL import platform as _gl_platform

from core.performance.frame_trace import FrameTraceEvent

# The per-frame reads call the GL entry points directly. PyOpenGL's wrappers allocate and
# convert a numpy array per query (about two thirds of the capture's cost, ~110 -> ~39 us on
# the RTX 4090 driver); the same driver functions are called with the same names in the same
# order, every frame, into a fresh buffer per call (nothing kept across frames or threads).
_GL_LIBRARY = _gl_platform.PLATFORM.GL
_GL_FUNCTION = _gl_platform.PLATFORM.functionTypeFor(_GL_LIBRARY)
_glGetIntegerv = _GL_FUNCTION(None, ctypes.c_uint, ctypes.POINTER(ctypes.c_int))(("glGetIntegerv", _GL_LIBRARY))
_glGetBooleanv = _GL_FUNCTION(None, ctypes.c_uint, ctypes.POINTER(ctypes.c_ubyte))(("glGetBooleanv", _GL_LIBRARY))
_glIsEnabled = _GL_FUNCTION(ctypes.c_ubyte, ctypes.c_uint)(("glIsEnabled", _GL_LIBRARY))


def _int_state(name: int) -> int:
    value = ctypes.c_int(0)
    _glGetIntegerv(name, ctypes.byref(value))
    return int(value.value)


def _int_states(name: int, count: int) -> tuple[int, ...]:
    values = (ctypes.c_int * count)()
    _glGetIntegerv(name, values)
    return tuple(int(value) for value in values)


def _bool_state(name: int) -> bool:
    return _bool_states(name, 1)[0]


def _bool_states(name: int, count: int) -> tuple[bool, ...]:
    values = (ctypes.c_ubyte * count)()
    _glGetBooleanv(name, values)
    return tuple(bool(value) for value in values)


def _is_enabled(capability: int) -> bool:
    return bool(_glIsEnabled(capability))


def _set_enabled(capability: int, enabled: bool) -> None:
    if enabled:
        gl.glEnable(capability)
    else:
        gl.glDisable(capability)


@dataclass(frozen=True, slots=True)
class InheritedGlState:
    """Immutable non-stencil GL state owned by the surrounding Quick render."""

    viewport: tuple[int, int, int, int]
    program: int
    vao: int
    array_buffer: int
    blend: bool
    blend_src_rgb: int
    blend_dst_rgb: int
    blend_src_alpha: int
    blend_dst_alpha: int
    blend_equation_rgb: int
    blend_equation_alpha: int
    cull: bool
    depth: bool
    depth_write: bool
    color_mask: tuple[bool, bool, bool, bool] | None = None

    @classmethod
    def capture_render_host(cls) -> "InheritedGlState":
        """Capture the legacy render-host fence in its established query order.

        The unclipped/overflow path still uses this exact standalone capture;
        CHK26 only shares state on the ordinary rounded-clipped branch.
        """

        viewport = _int_states(gl.GL_VIEWPORT, 4)
        if len(viewport) != 4:
            raise RuntimeError(f"invalid inherited Quick GL viewport: {viewport}")
        return cls(
            viewport=viewport,
            program=_int_state(gl.GL_CURRENT_PROGRAM),
            vao=_int_state(gl.GL_VERTEX_ARRAY_BINDING),
            array_buffer=_int_state(gl.GL_ARRAY_BUFFER_BINDING),
            blend=_is_enabled(gl.GL_BLEND),
            blend_src_rgb=_int_state(gl.GL_BLEND_SRC_RGB),
            blend_dst_rgb=_int_state(gl.GL_BLEND_DST_RGB),
            blend_src_alpha=_int_state(gl.GL_BLEND_SRC_ALPHA),
            blend_dst_alpha=_int_state(gl.GL_BLEND_DST_ALPHA),
            blend_equation_rgb=_int_state(gl.GL_BLEND_EQUATION_RGB),
            blend_equation_alpha=_int_state(gl.GL_BLEND_EQUATION_ALPHA),
            cull=_is_enabled(gl.GL_CULL_FACE),
            depth=_is_enabled(gl.GL_DEPTH_TEST),
            depth_write=_bool_state(gl.GL_DEPTH_WRITEMASK),
            color_mask=None,
        )

    @classmethod
    def capture_clipped_shared(
        cls,
        *,
        mark: Callable[[FrameTraceEvent], None] | None = None,
    ) -> "InheritedGlState":
        """Capture the union needed by mask + mode exactly once.

        The first two groups preserve CHK25's mask-state marker semantics.  The
        final blend-function/equation group is the state the render host used to
        query again immediately after clip admission.  It is immutable across
        the mask operation, so carrying it forward removes duplicate driver
        queries without weakening the state-restoration fence.
        """

        viewport = _int_states(gl.GL_VIEWPORT, 4)
        if len(viewport) != 4:
            raise RuntimeError(f"invalid inherited Quick GL viewport: {viewport}")
        program = _int_state(gl.GL_CURRENT_PROGRAM)
        vao = _int_state(gl.GL_VERTEX_ARRAY_BINDING)
        array_buffer = _int_state(gl.GL_ARRAY_BUFFER_BINDING)
        if mark is not None:
            mark(FrameTraceEvent.CLIP_BEGIN_MASK_BINDINGS_READY)

        blend = _is_enabled(gl.GL_BLEND)
        cull = _is_enabled(gl.GL_CULL_FACE)
        depth = _is_enabled(gl.GL_DEPTH_TEST)
        depth_write = _bool_state(gl.GL_DEPTH_WRITEMASK)
        color_mask = _bool_states(gl.GL_COLOR_WRITEMASK, 4)
        if len(color_mask) != 4:
            raise RuntimeError(f"invalid inherited Quick GL color mask: {color_mask}")
        if mark is not None:
            mark(FrameTraceEvent.CLIP_BEGIN_MASK_STATE_READY)

        blend_src_rgb = _int_state(gl.GL_BLEND_SRC_RGB)
        blend_dst_rgb = _int_state(gl.GL_BLEND_DST_RGB)
        blend_src_alpha = _int_state(gl.GL_BLEND_SRC_ALPHA)
        blend_dst_alpha = _int_state(gl.GL_BLEND_DST_ALPHA)
        blend_equation_rgb = _int_state(gl.GL_BLEND_EQUATION_RGB)
        blend_equation_alpha = _int_state(gl.GL_BLEND_EQUATION_ALPHA)
        if mark is not None:
            mark(FrameTraceEvent.CLIP_BEGIN_SHARED_GL_STATE_READY)

        return cls(
            viewport=viewport,
            program=program,
            vao=vao,
            array_buffer=array_buffer,
            blend=blend,
            blend_src_rgb=blend_src_rgb,
            blend_dst_rgb=blend_dst_rgb,
            blend_src_alpha=blend_src_alpha,
            blend_dst_alpha=blend_dst_alpha,
            blend_equation_rgb=blend_equation_rgb,
            blend_equation_alpha=blend_equation_alpha,
            cull=cull,
            depth=depth,
            depth_write=depth_write,
            color_mask=(
                bool(color_mask[0]),
                bool(color_mask[1]),
                bool(color_mask[2]),
                bool(color_mask[3]),
            ),
        )

    def restore_render_host(self) -> None:
        """Restore the same render-host state fence as before CHK26."""

        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.array_buffer)
        gl.glUseProgram(self.program)
        gl.glViewport(*self.viewport)
        gl.glBlendEquationSeparate(
            self.blend_equation_rgb,
            self.blend_equation_alpha,
        )
        gl.glBlendFuncSeparate(
            self.blend_src_rgb,
            self.blend_dst_rgb,
            self.blend_src_alpha,
            self.blend_dst_alpha,
        )
        gl.glDepthMask(gl.GL_TRUE if self.depth_write else gl.GL_FALSE)
        _set_enabled(gl.GL_BLEND, self.blend)
        _set_enabled(gl.GL_CULL_FACE, self.cull)
        _set_enabled(gl.GL_DEPTH_TEST, self.depth)


__all__ = ["InheritedGlState"]
