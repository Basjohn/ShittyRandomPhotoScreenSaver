"""Shared offscreen GL ownership for labs and production-renderer diagnostics.

This owns a context, RGBA/depth target and optional diagnostic quad. Callers own
their renderer/scene, explicit logical time and retirement before target.close().
There is no mode registry, scheduler, Settings store or alternate graphics API.
"""
from __future__ import annotations

from contextlib import contextmanager

from PySide6.QtCore import QCoreApplication, QThread
from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext, QSurfaceFormat


class OffscreenRenderTarget:
    def __init__(self, width: int, height: int, *, label="visualizer-lab"):
        from OpenGL import GL as gl
        from rendering.quick.bootstrap import QUICK_OPENGL_VERSION, validate_current_opengl_context

        self._validate_size(width, height)
        existing = QCoreApplication.instance()
        if existing is not None and not isinstance(existing, QGuiApplication):
            raise RuntimeError("Offscreen rendering requires QGuiApplication, not QCoreApplication")
        self.app = existing or QGuiApplication([])
        self._check_thread()
        self.context = None
        self.surface = None
        self.fbo = self.depth = self.color_texture = 0
        self.width = self.height = 0
        self._mesh = None
        self._vao = 0
        self._closed = False
        previous = QOpenGLContext.currentContext()
        previous_surface = previous.surface() if previous is not None else None
        try:
            fmt = QSurfaceFormat()
            fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
            fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
            fmt.setVersion(*QUICK_OPENGL_VERSION)
            fmt.setDepthBufferSize(24)
            self.context = QOpenGLContext()
            self.context.setFormat(fmt)
            if not self.context.create():
                raise RuntimeError(f"OpenGL {QUICK_OPENGL_VERSION} context unavailable")
            self.surface = QOffscreenSurface()
            self.surface.setFormat(self.context.format())
            self.surface.create()
            self.make_current()
            validate_current_opengl_context(reason=label, context=self.context)
            self.driver = gl.glGetString(gl.GL_RENDERER).decode()
            self.resize(width, height)
        except Exception:
            self.close()
            if previous is not None and previous_surface is not None:
                if not previous.makeCurrent(previous_surface):
                    raise RuntimeError("Could not restore caller's GL context after failed admission")
            raise

    @staticmethod
    def _validate_size(width, height):
        if (isinstance(width, bool) or isinstance(height, bool)
                or not isinstance(width, int) or not isinstance(height, int)
                or width <= 0 or height <= 0):
            raise ValueError("Offscreen target dimensions must be positive integers")

    def _check_thread(self):
        if QThread.currentThread() != self.app.thread():
            raise RuntimeError("Offscreen target operations belong to the Qt GUI thread")

    def make_current(self):
        self._check_thread()
        if self._closed:
            raise RuntimeError("Offscreen target is closed")
        if self.context is None or self.surface is None or not self.surface.isValid():
            raise RuntimeError("Offscreen GL context/surface is not admitted")
        if QOpenGLContext.currentContext() != self.context:
            if not self.context.makeCurrent(self.surface):
                raise RuntimeError("Could not make offscreen GL context current")

    @property
    def closed(self):
        return self._closed

    @contextmanager
    def current(self):
        """Run a caller-owned GL operation and restore its previous context."""
        previous = QOpenGLContext.currentContext()
        previous_surface = previous.surface() if previous is not None else None
        entered = self.context
        self.make_current()
        try:
            yield self
        finally:
            if previous is not None and previous != entered and previous_surface is not None:
                if not previous.makeCurrent(previous_surface):
                    raise RuntimeError("Could not restore caller's GL context")
            elif previous is None and self.context is not None:
                self.context.doneCurrent()

    @property
    def vao(self):
        if self._closed:
            raise RuntimeError("Offscreen target is closed")
        if not self._vao:
            with self.current():
                from rendering.quick.scene3d.resources import MeshResources
                if self._mesh is None:
                    self._mesh = MeshResources("diagnostic quad")
                self._vao = self._mesh.mesh("quad", (0., 0., 1., 0., 0., 1., 1., 1.), (2,))[0]
        return self._vao

    @staticmethod
    def _delete_target(fbo, depth, color):
        from OpenGL import GL as gl
        if fbo:
            gl.glDeleteFramebuffers(1, [fbo])
        if depth:
            gl.glDeleteRenderbuffers(1, [depth])
        if color:
            gl.glDeleteTextures([color])

    def resize(self, width: int, height: int):
        """Replace only this target after a complete new allocation succeeds."""
        from OpenGL import GL as gl
        self._validate_size(width, height)
        self.make_current()
        if (width, height) == (self.width, self.height):
            return
        fbo = depth = color = 0
        try:
            color = int(gl.glGenTextures(1))
            gl.glBindTexture(gl.GL_TEXTURE_2D, color)
            for axis in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
                gl.glTexParameteri(gl.GL_TEXTURE_2D, axis, gl.GL_CLAMP_TO_EDGE)
            for filt in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
                gl.glTexParameteri(gl.GL_TEXTURE_2D, filt, gl.GL_LINEAR)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0,
                            gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
            depth = int(gl.glGenRenderbuffers(1))
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, depth)
            gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, width, height)
            fbo = int(gl.glGenFramebuffers(1))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, color, 0)
            gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER, depth)
            if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError("Offscreen diagnostic framebuffer incomplete")
        except Exception:
            self._delete_target(fbo, depth, color)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
            raise
        previous = self.fbo, self.depth, self.color_texture
        self.fbo, self.depth, self.color_texture = fbo, depth, color
        self.width, self.height = width, height
        self._delete_target(*previous)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)

    def bind(self, *, clear=(0., 0., 0., 0.)):
        from OpenGL import GL as gl
        self.make_current()
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glViewport(0, 0, self.width, self.height)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(*clear)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

    def read_rgba(self):
        """Owned, contiguous top-left raw RGBA; no alpha or colour conversion."""
        import numpy as np
        from OpenGL import GL as gl
        self.make_current()
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        pixels = gl.glReadPixels(0, 0, self.width, self.height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        from rendering.gl_error_policy import raise_pending_gl_error
        raise_pending_gl_error(gl, "offscreen capture")
        return np.ascontiguousarray(np.frombuffer(bytes(pixels), dtype=np.uint8)
                                    .reshape(self.height, self.width, 4)[::-1])

    def close(self):
        """Retire owned GL resources legally, once; callers retire their scenes first."""
        from OpenGL import GL as gl
        self._check_thread()
        if self._closed:
            return
        previous = QOpenGLContext.currentContext()
        previous_surface = previous.surface() if previous is not None else None
        owned_context = self.context
        try:
            has_resources = bool(self.fbo or self.depth or self.color_texture or self._mesh is not None)
            if has_resources:
                self.make_current()
                if self._mesh is not None:
                    self._mesh.release_resources()
                    self._mesh = None
                    self._vao = 0
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
                self._delete_target(self.fbo, self.depth, self.color_texture)
                self.fbo = self.depth = self.color_texture = 0
            if self.context is not None and QOpenGLContext.currentContext() == self.context:
                self.context.doneCurrent()
            if self.surface is not None:
                self.surface.destroy()
            self.context = self.surface = None
            self._closed = True
        finally:
            if previous is not None and previous != owned_context and previous_surface is not None:
                if not previous.makeCurrent(previous_surface):
                    raise RuntimeError("Could not restore caller's GL context after target retirement")
