"""Studio viewport: an inline QSGRenderNode that draws a mode's production renderer.

The GUI thread hands one immutable frame to the item; Quick's sync copies the
reference into the node; the render thread draws it straight into the window's
framebuffer (no readback, no extra texture copy). The renderer is created lazily on
the render thread and released there, on ``sceneGraphInvalidated`` or node release,
while that context is current. Render failures are reported to the GUI thread and
shown in the viewport; the node never substitutes placeholder pixels.
"""
from __future__ import annotations

import ctypes
import threading
from typing import Any, Callable

from OpenGL import GL as gl
from PySide6.QtCore import QRectF, Qt, Signal, Slot
from PySide6.QtGui import QOpenGLContext
from PySide6.QtQuick import QQuickItem, QQuickWindow, QSGNode, QSGRenderNode

from core.logging.logger import get_logger
from ui.studio.adapter import RenderCard

logger = get_logger(__name__)


def _int_state(name: int) -> int:
    value = gl.glGetIntegerv(name)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(value[0])


class _UnitQuad:
    """The unit item quad (attribute 0) the production scene composites through."""

    def __init__(self) -> None:
        self.vao = 0
        self._vbo = 0

    def ensure(self) -> int:
        if self.vao:
            return self.vao
        prior_vao = _int_state(gl.GL_VERTEX_ARRAY_BINDING)
        prior_buffer = _int_state(gl.GL_ARRAY_BUFFER_BINDING)
        vertices = (ctypes.c_float * 8)(0., 0., 1., 0., 0., 1., 1., 1.)
        try:
            self.vao = int(gl.glGenVertexArrays(1))
            self._vbo = int(gl.glGenBuffers(1))
            gl.glBindVertexArray(self.vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(vertices), vertices, gl.GL_STATIC_DRAW)
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, False, 2 * ctypes.sizeof(ctypes.c_float),
                                     ctypes.c_void_p(0))
        except Exception:
            self.release()
            raise
        finally:
            gl.glBindVertexArray(prior_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, prior_buffer)
        return self.vao

    def release(self) -> None:
        if self._vbo:
            gl.glDeleteBuffers(1, [self._vbo])
        if self.vao:
            gl.glDeleteVertexArrays(1, [self.vao])
        self.vao = self._vbo = 0


class StudioRenderNode(QSGRenderNode):
    """Render-thread owner of one Studio renderer and its GL resources."""

    def __init__(self, factory: Callable[[], Any], reporter: "StudioViewportItem") -> None:
        super().__init__()
        self._factory = factory
        self._reporter = reporter
        self._renderer: Any = None
        self._quad = _UnitQuad()
        self._frame: Any = None
        self._frame_serial = 0
        self._logical_size = (0.0, 0.0)
        self._extent: tuple[float, float] | None = None
        self._prepared = False
        self._last_error = ""
        self._released = False
        self._drawn_serial = -1

    # Sync phase (GUI blocked) -------------------------------------------------
    def synchronize(self, frame: Any, serial: int, logical_size: tuple[float, float],
                    extent: tuple[float, float] | None = None) -> None:
        self._extent = extent
        self._frame = frame
        self._frame_serial = serial
        self._logical_size = (max(0.0, float(logical_size[0])), max(0.0, float(logical_size[1])))

    def rect(self) -> QRectF:
        return QRectF(0.0, 0.0, *self._logical_size)

    def flags(self) -> QSGRenderNode.RenderingFlag:
        return QSGRenderNode.RenderingFlag.BoundedRectRendering

    def changedStates(self) -> QSGRenderNode.StateFlag:
        return (QSGRenderNode.StateFlag.BlendState | QSGRenderNode.StateFlag.CullState
                | QSGRenderNode.StateFlag.DepthState | QSGRenderNode.StateFlag.StencilState
                | QSGRenderNode.StateFlag.ViewportState | QSGRenderNode.StateFlag.ScissorState)

    # Render thread -------------------------------------------------------------
    def render(self, state: QSGRenderNode.RenderState) -> None:
        frame = self._frame
        if frame is None or min(self._logical_size) <= 0.0 or self._released:
            return
        from rendering.quick.visualizer.gl_state import InheritedGlState
        try:
            target = self.renderTarget()
            if target is None:
                raise RuntimeError("Studio viewport has no render target")
            size = target.pixelSize()
            viewport = (0, 0, int(size.width()), int(size.height()))
            if min(viewport[2:]) <= 0:
                raise RuntimeError(f"Studio viewport has an invalid render target {viewport[2:]}")
            matrix = self.projectionMatrix() * self.matrix()
            if self._renderer is None:
                self._renderer = self._factory()
            card = RenderCard(viewport=viewport, logical_size=self._logical_size,
                              matrix_values=tuple(float(v) for v in matrix.data()),
                              quad_vao=self._quad.ensure(), extent=self._extent)
            inherited = InheritedGlState.capture_render_host()
            try:
                gl.glEnable(gl.GL_BLEND)
                gl.glBlendEquationSeparate(gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
                gl.glBlendFuncSeparate(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE,
                                       gl.GL_ONE_MINUS_SRC_ALPHA)
                gl.glDisable(gl.GL_CULL_FACE)
                gl.glDisable(gl.GL_DEPTH_TEST)
                gl.glDepthMask(gl.GL_FALSE)
                gl.glViewport(*viewport)
                if not self._prepared:
                    self._prepared = bool(self._renderer.prepare(card, frame))
                    if not self._prepared:
                        self._reporter.notePreparing()
                        return
                self._renderer.render(card, frame)
            finally:
                inherited.restore_render_host()
            from rendering.gl_error_policy import raise_pending_gl_error
            raise_pending_gl_error(gl, "Studio viewport")
            if self._last_error:
                self._last_error = ""
            if self._drawn_serial != self._frame_serial:
                self._drawn_serial = self._frame_serial
                self._reporter.noteRendered(self._frame_serial)
        except Exception as exc:  # surfaced in the viewport, never swallowed into fake pixels
            signature = f"{type(exc).__name__}: {exc}"
            if signature != self._last_error:
                self._last_error = signature
                logger.exception("[STUDIO] Viewport render failed")
            self._reporter.noteError(signature)

    def releaseResources(self) -> None:
        self.release_now()

    def release_now(self) -> None:
        """Retire GL resources; must run with this node's scene-graph context current."""
        if self._released:
            return
        if QOpenGLContext.currentContext() is None:
            return  # a later legal invalidation retries
        renderer, self._renderer = self._renderer, None
        try:
            if renderer is not None:
                renderer.release()
        finally:
            self._quad.release()
            self._released = True
            self._frame = None


class StudioViewportItem(QQuickItem):
    """Hosts the render node; GUI-thread API is ``set_frame`` and the status signals."""

    rendered = Signal(int)          # serial of a frame that reached the framebuffer
    renderError = Signal(str)
    preparing = Signal()

    def __init__(self, factory: Callable[[], Any], parent: QQuickItem | None = None) -> None:
        self._factory = factory
        self._lock = threading.Lock()
        self._node: StudioRenderNode | None = None
        self._frame: Any = None
        self._serial = 0
        self._extent: tuple[float, float] | None = None
        self._bound_window: QQuickWindow | None = None
        super().__init__(parent)
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)
        self.windowChanged.connect(self._bind_window)
        self._bind_window(self.window())       # constructed inside a window: windowChanged already fired

    # GUI thread ------------------------------------------------------------------
    def set_frame(self, frame: Any) -> int:
        self._frame = frame
        self._serial += 1
        self.update()
        return self._serial

    @property
    def frame_serial(self) -> int:
        return self._serial

    extentChanged = Signal()

    @property
    def extent(self) -> tuple[float, float] | None:
        return self._extent

    def set_extent(self, extent: tuple[float, float] | None) -> None:
        """Present this world extent letterboxed inside the slot (None: fill the slot)."""
        extent = None if extent is None else (float(extent[0]), float(extent[1]))
        if extent == self._extent:
            return
        self._extent = extent
        self.extentChanged.emit()
        self.update()

    @Slot(QQuickWindow)
    def _bind_window(self, window: QQuickWindow | None) -> None:
        if window is self._bound_window:
            return
        if self._bound_window is not None:
            try:
                self._bound_window.sceneGraphInvalidated.disconnect(self._invalidate)
            except (RuntimeError, TypeError):
                pass
        self._bound_window = window
        if window is not None:
            window.sceneGraphInvalidated.connect(self._invalidate, Qt.ConnectionType.DirectConnection)

    def detach(self) -> None:
        """Stop accepting frames (GUI thread). GL retirement follows scene-graph invalidation."""
        self._frame = None
        self.update()

    # Render thread -----------------------------------------------------------------
    def _invalidate(self) -> None:
        with self._lock:
            node, self._node = self._node, None
        if node is not None:
            node.release_now()

    def updatePaintNode(self, old_node: QSGNode | None, _data: QQuickItem.UpdatePaintNodeData) -> QSGNode:
        node = old_node if isinstance(old_node, StudioRenderNode) else StudioRenderNode(self._factory, self)
        node.synchronize(self._frame, self._serial, (self.width(), self.height()), self._extent)
        with self._lock:
            self._node = node
        return node

    # Called from the render thread; signals queue to the GUI thread.
    def noteRendered(self, serial: int) -> None:
        self.rendered.emit(int(serial))

    def noteError(self, signature: str) -> None:
        self.renderError.emit(str(signature))

    def notePreparing(self) -> None:
        self.preparing.emit()


__all__ = ["StudioRenderNode", "StudioViewportItem"]
