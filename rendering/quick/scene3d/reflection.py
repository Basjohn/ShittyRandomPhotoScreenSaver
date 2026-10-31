"""Planar reflection target (S3D-5): the mirrored scene as one mipmapped HDR texture for a flat receiver.

``begin(width, height)`` binds an RGBA16F colour (full mip chain) with a depth renderbuffer, clears it to no light,
and enables depth testing; the caller draws everything above the plane through
``rendering.gl_programs.reflection.mirror_view`` (winding flips: do not cull by winding). ``end()`` builds the mip
chain the receiver's roughness reads and hands back the caller's framebuffer, viewport, depth state and colour mask.
``texture`` is then sampled by ``PLANAR_REFLECTION_GLSL``.

Allocation happens at the first ``begin`` at a size and is reused while the size holds; ``warm`` allocates on a
hidden frame instead. ``release`` deletes everything under the owning context; nothing is held otherwise.
"""
from __future__ import annotations

import ctypes
import weakref

from OpenGL import GL as gl

from rendering.quick import gl_query


class PlanarReflection:
    def __init__(self, label: str) -> None:
        self.label = label
        self._size = (0, 0)
        self._colour = 0
        self._depth = 0
        self._fbo = 0
        self._saved = None
        self._context_ref = None

    @property
    def has_resources(self) -> bool:
        return bool(self._colour or self._depth or self._fbo)

    @property
    def texture(self) -> int:
        return self._colour

    @property
    def size(self) -> tuple[int, int]:
        return self._size

    def _check_context(self, *, admit: bool = False) -> None:
        from PySide6.QtGui import QOpenGLContext
        current = QOpenGLContext.currentContext()
        if current is None:
            raise RuntimeError(f"{self.label}: reflection GL work needs its owning current context")
        if self._context_ref is None and admit:
            self._context_ref = weakref.ref(current)
        if self._context_ref is None or self._context_ref() != current:
            raise RuntimeError(f"{self.label}: reflection used in a foreign context")

    def _allocate(self, width: int, height: int) -> None:
        self._drop()
        name = (ctypes.c_uint * 1)()
        gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
        self._colour = int(name[0])
        gl.glTextureStorage2D(self._colour, max(width, height).bit_length(), gl.GL_RGBA16F, width, height)
        gl.glTextureParameteri(self._colour, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
        gl.glTextureParameteri(self._colour, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
            gl.glTextureParameteri(self._colour, wrap, gl.GL_CLAMP_TO_EDGE)
        gl.glCreateRenderbuffers(1, name)
        self._depth = int(name[0])
        gl.glNamedRenderbufferStorage(self._depth, gl.GL_DEPTH_COMPONENT24, width, height)
        gl.glCreateFramebuffers(1, name)
        self._fbo = int(name[0])
        gl.glNamedFramebufferTexture(self._fbo, gl.GL_COLOR_ATTACHMENT0, self._colour, 0)
        gl.glNamedFramebufferRenderbuffer(self._fbo, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER, self._depth)
        if gl.glCheckNamedFramebufferStatus(self._fbo, gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"{self.label}: reflection target incomplete at {width}x{height}")
        self._size = (width, height)

    def warm(self, width: int, height: int) -> bool:
        """One warm-up step: True when already allocated at this size, else allocate now (on a hidden frame)."""
        self._check_context(admit=True)
        if self._size == (int(width), int(height)) and self._fbo:
            return True
        self._allocate(int(width), int(height))
        return False

    def begin(self, width: int, height: int) -> None:
        if self._saved is not None:
            raise RuntimeError(f"{self.label}: reflection begin() without end()")
        self._check_context(admit=True)
        width, height = max(1, int(width)), max(1, int(height))
        if self._size != (width, height) or not self._fbo:
            self._allocate(width, height)
        self._saved = (gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING), gl_query.get_ints(gl.GL_VIEWPORT, 4),
                       gl_query.get_bool(gl.GL_DEPTH_WRITEMASK), gl_query.is_enabled(gl.GL_DEPTH_TEST),
                       gl_query.get_indexed_bools(gl.GL_COLOR_WRITEMASK, 0))
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._fbo)
        gl.glViewport(0, 0, *self._size)
        gl.glColorMaski(0, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glClearBufferfv(gl.GL_COLOR, 0, (0.0, 0.0, 0.0, 0.0))
        gl.glClearBufferfv(gl.GL_DEPTH, 0, (1.0,))
        gl.glEnable(gl.GL_DEPTH_TEST)

    def end(self) -> None:
        if self._saved is None:
            raise RuntimeError(f"{self.label}: reflection end() without begin()")
        framebuffer, viewport, depth_mask, depth_test, mask = self._saved
        self._saved = None
        try:
            gl.glGenerateTextureMipmap(self._colour)
        finally:
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, framebuffer)
            gl.glViewport(*viewport)
            gl.glDepthMask(gl.GL_TRUE if depth_mask else gl.GL_FALSE)
            (gl.glEnable if depth_test else gl.glDisable)(gl.GL_DEPTH_TEST)
            gl.glColorMaski(0, *mask)

    def _drop(self) -> None:
        if self._fbo:
            gl.glDeleteFramebuffers(1, [self._fbo])
        if self._depth:
            gl.glDeleteRenderbuffers(1, [self._depth])
        if self._colour:
            gl.glDeleteTextures(1, [self._colour])
        self._fbo = self._depth = self._colour = 0
        self._size = (0, 0)

    def release(self) -> None:
        if self.has_resources:
            self._check_context()
        self._drop()
        self._context_ref = None


__all__ = ["PlanarReflection"]
