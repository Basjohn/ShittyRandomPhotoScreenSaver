"""Studio viewport: an inline QSGRenderNode that draws a mode's production renderer.

The GUI thread hands one immutable frame to the item; Quick's sync copies the
reference into the node; the render thread draws it straight into the window's
framebuffer (no readback, no extra texture copy). The renderer is created lazily on
the render thread and released there, on ``sceneGraphInvalidated`` or node release,
while that context is current. Render failures are reported to the GUI thread and
shown in the viewport; the node never substitutes placeholder pixels.

Snapshots (e.g. starting-point tile previews) are rendered on request only: at most one per
frame, by a second renderer instance (so the live scene's temporal state is never disturbed)
into a small private framebuffer, read back once and handed to the GUI thread. With no
request pending the node does no extra work.
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

# What the scene composites onto: the same opaque backing for the live viewport and every snapshot, never a chrome
# colour. Production modes draw over their card (transparent backgrounds, translucent rims and glows), so whatever
# lies under the render node shows through; the Studio's scene must not follow the Settings theme.
SCENE_BACKING = (0.0, 0.0, 0.0, 1.0)


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


class _SnapshotTarget:
    """A small RGBA8 + depth/stencil framebuffer for snapshot renders (render thread only)."""

    def __init__(self) -> None:
        self.fbo = self._colour = self._depth = 0
        self.size = (0, 0)

    def ensure(self, width: int, height: int) -> int:
        if self.fbo and self.size == (width, height):
            return self.fbo
        self.release()
        self.fbo = int(gl.glGenFramebuffers(1))
        self._colour = int(gl.glGenRenderbuffers(1))
        self._depth = int(gl.glGenRenderbuffers(1))
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._colour)
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_RGBA8, width, height)
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._depth)
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH24_STENCIL8, width, height)
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, 0)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_RENDERBUFFER, self._colour)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_STENCIL_ATTACHMENT, gl.GL_RENDERBUFFER,
                                     self._depth)
        status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        if status != gl.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"Snapshot framebuffer incomplete ({status})")
        self.size = (width, height)
        return self.fbo

    def release(self) -> None:
        if self.fbo:
            gl.glDeleteFramebuffers(1, [self.fbo])
        for buffer in (self._colour, self._depth):
            if buffer:
                gl.glDeleteRenderbuffers(1, [buffer])
        self.fbo = self._colour = self._depth = 0
        self.size = (0, 0)


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
        self._style: tuple = ()
        self._prepared = False
        self._last_error = ""
        self._released = False
        self._drawn_serial = -1
        self._snapshot_job = None
        self._snapshot_renderer: Any = None
        self._snapshot_prepared = False
        self._snapshot_target = _SnapshotTarget()

    # Sync phase (GUI blocked) -------------------------------------------------
    def synchronize(self, frame: Any, serial: int, logical_size: tuple[float, float],
                    extent: tuple[float, float] | None = None, style: tuple = ()) -> None:
        self._extent = extent
        self._style = style
        self._frame = frame
        self._frame_serial = serial
        self._logical_size = (max(0.0, float(logical_size[0])), max(0.0, float(logical_size[1])))

    def take_snapshot_job(self, job) -> None:
        if job is not None and self._snapshot_job is None:
            self._snapshot_job = job

    @property
    def snapshot_busy(self) -> bool:
        return self._snapshot_job is not None

    def rect(self) -> QRectF:
        return QRectF(0.0, 0.0, *self._logical_size)

    def flags(self) -> QSGRenderNode.RenderingFlag:
        return QSGRenderNode.RenderingFlag.BoundedRectRendering

    def changedStates(self) -> QSGRenderNode.StateFlag:
        return (QSGRenderNode.StateFlag.BlendState | QSGRenderNode.StateFlag.CullState
                | QSGRenderNode.StateFlag.DepthState | QSGRenderNode.StateFlag.StencilState
                | QSGRenderNode.StateFlag.ViewportState | QSGRenderNode.StateFlag.ScissorState)

    # Render thread -------------------------------------------------------------
    @staticmethod
    def apply_clip(state) -> None:
        """The viewport slot clips (the scene graph hands its clip as the scissor): a frameless mode that may overflow
        its card (Extruded Spectrum, Sphere) reaches the slot's edge, never the Studio chrome. A renderer's own
        offscreen passes restore the inherited scissor test before they composite; ``render`` disables it after."""
        if state is not None and bool(state.scissorEnabled()):
            rect = state.scissorRect()
            gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glScissor(int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))

    def clear_backing(self, state, viewport, matrix) -> None:
        """Clear the scene's region (the slot's scissor; without one, the item's own rect) to ``SCENE_BACKING``,
        so nothing the chrome painted under the viewport composites into the scene."""
        if state is None or not bool(state.scissorEnabled()):
            data = matrix.data()
            width, height = self._logical_size
            xs = sorted(((data[0] * x + data[12]) + 1.0) * 0.5 * viewport[2] for x in (0.0, width))
            ys = sorted(((data[5] * y + data[13]) + 1.0) * 0.5 * viewport[3] for y in (0.0, height))
            gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glScissor(int(round(xs[0])), int(round(ys[0])), int(round(xs[1] - xs[0])), int(round(ys[1] - ys[0])))
        gl.glClearColor(*SCENE_BACKING)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        self.apply_clip(state)

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
                              quad_vao=self._quad.ensure(), extent=self._extent, style=self._style)
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
                self.apply_clip(state)
                if not self._prepared:
                    self._prepared = bool(self._renderer.prepare(card, frame))
                    if not self._prepared:
                        self._reporter.notePreparing()
                        return
                self.clear_backing(state, viewport, matrix)
                self._renderer.render(card, frame)
            finally:
                inherited.restore_render_host()
                gl.glDisable(gl.GL_SCISSOR_TEST)
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
        if self._snapshot_job is not None:
            self._render_snapshot()

    def _render_snapshot(self) -> None:
        """One requested snapshot: second renderer, private framebuffer, one small readback."""
        key, frame, width, height, logical, extent, style = self._snapshot_job
        from rendering.quick.visualizer.gl_state import InheritedGlState
        inherited = InheritedGlState.capture_render_host()
        prior_draw = _int_state(gl.GL_DRAW_FRAMEBUFFER_BINDING)
        prior_read = _int_state(gl.GL_READ_FRAMEBUFFER_BINDING)
        try:
            if self._snapshot_renderer is None:
                self._snapshot_renderer = self._factory()
            lw, lh = float(logical[0]), float(logical[1])
            # Item pixels (y down) -> clip space for a target exactly the item's size.
            matrix = (2.0 / lw, 0.0, 0.0, 0.0, 0.0, -2.0 / lh, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 1.0, 0.0, 1.0)
            card = RenderCard(viewport=(0, 0, width, height), logical_size=(lw, lh), matrix_values=matrix,
                              quad_vao=self._quad.ensure(), extent=extent, style=style)
            fbo = self._snapshot_target.ensure(width, height)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            gl.glViewport(0, 0, width, height)
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glClearColor(*SCENE_BACKING)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT | gl.GL_STENCIL_BUFFER_BIT)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendEquationSeparate(gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
            gl.glBlendFuncSeparate(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glDisable(gl.GL_CULL_FACE)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glDepthMask(gl.GL_FALSE)
            if not self._snapshot_prepared:
                self._snapshot_prepared = bool(self._snapshot_renderer.prepare(card, frame))
                if not self._snapshot_prepared:
                    self._reporter.noteSnapshotPending()       # keep the job; another frame continues
                    return
            self._snapshot_renderer.render(card, frame)
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, fbo)
            gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
            pixels = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            self._snapshot_job = None
            self._reporter.noteSnapshot(str(key), int(width), int(height), bytes(pixels))
        except Exception as exc:
            self._snapshot_job = None
            logger.exception("[STUDIO] Snapshot render failed")
            self._reporter.noteSnapshotFailed(str(key), f"{type(exc).__name__}: {exc}")
        finally:
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, prior_draw)
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, prior_read)
            inherited.restore_render_host()

    def releaseResources(self) -> None:
        self.release_now()

    def release_now(self) -> None:
        """Retire GL resources; must run with this node's scene-graph context current."""
        if self._released:
            return
        if QOpenGLContext.currentContext() is None:
            return  # a later legal invalidation retries
        renderer, self._renderer = self._renderer, None
        snapshot, self._snapshot_renderer = self._snapshot_renderer, None
        try:
            if renderer is not None:
                renderer.release()
            if snapshot is not None:
                snapshot.release()
        finally:
            self._snapshot_target.release()
            self._snapshot_job = None
            self._quad.release()
            self._released = True
            self._frame = None


class StudioViewportItem(QQuickItem):
    """Hosts the render node; GUI-thread API is ``set_frame`` and the status signals."""

    rendered = Signal(int)          # serial of a frame that reached the framebuffer
    renderError = Signal(str)
    preparing = Signal()
    snapshotReady = Signal(str, int, int, bytes)     # key, width, height, RGBA rows bottom-up
    snapshotFailed = Signal(str, str)
    snapshotPending = Signal()

    def __init__(self, factory: Callable[[], Any], parent: QQuickItem | None = None) -> None:
        self._factory = factory
        self._lock = threading.Lock()
        self._node: StudioRenderNode | None = None
        self._frame: Any = None
        self._serial = 0
        self._extent: tuple[float, float] | None = None
        self._base_extent: tuple[float, float] | None = None
        self._fill = False
        self._slot_size = (0.0, 0.0)
        self._style: tuple = ()
        self._bound_window: QQuickWindow | None = None
        self._snapshot_jobs: list = []
        super().__init__(parent)
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)
        self.windowChanged.connect(self._bind_window)
        # A finished snapshot hands the next queued one to the node at the next sync.
        self.snapshotReady.connect(self._next_snapshot, Qt.ConnectionType.QueuedConnection)
        self.snapshotFailed.connect(self._next_snapshot, Qt.ConnectionType.QueuedConnection)
        self._bind_window(self.window())       # constructed inside a window: windowChanged already fired

    # GUI thread ------------------------------------------------------------------
    def set_frame(self, frame: Any) -> int:
        self._frame = frame
        self._serial += 1
        self.update()
        return self._serial

    def request_snapshot(self, key: str, frame: Any, size: tuple[int, int], logical: tuple[float, float],
                         extent: tuple[float, float] | None, style: tuple = ()) -> None:
        """Render ``frame`` once into a ``size`` pixel image (``logical`` item size) on the render thread;
        the result arrives as ``snapshotReady``. Requests are served one per frame, in order."""
        self._snapshot_jobs.append((key, frame, int(size[0]), int(size[1]), logical, extent, tuple(style)))
        self.update()

    @Slot()
    def _next_snapshot(self, *_args) -> None:
        if self._snapshot_jobs:
            self.update()

    @property
    def snapshot_queue(self) -> int:
        return len(self._snapshot_jobs)

    @property
    def frame_serial(self) -> int:
        return self._serial

    extentChanged = Signal()

    @property
    def extent(self) -> tuple[float, float] | None:
        return self._extent

    def set_extent(self, extent: tuple[float, float] | None, style: tuple = (), *, fill: bool = False) -> None:
        """Present this world extent letterboxed inside the slot (None: fill the slot). With ``fill`` the
        extent grows to the slot's shape (more world on one axis, never less), so nothing is letterboxed."""
        base = None if extent is None else (float(extent[0]), float(extent[1]))
        if base == self._base_extent and bool(fill) == self._fill and tuple(style) == self._style:
            return
        self._base_extent, self._fill, self._style = base, bool(fill), tuple(style)
        self._extent = self._presented_extent()
        self.extentChanged.emit()
        self.update()

    def _presented_extent(self) -> tuple[float, float] | None:
        base = self._base_extent
        width, height = self._slot_size
        if base is None or not self._fill or width <= 0.0 or height <= 0.0:
            return base
        from ui.studio.adapter import fill_extent
        return fill_extent(base, width / height)

    def fit_slot(self, width: float, height: float) -> tuple[float, float] | None:
        """The slot's size changed: the extent to present in it (a filling framing follows the slot)."""
        self._slot_size = (float(width), float(height))
        extent = self._presented_extent()
        if extent != self._extent:
            self._extent = extent
            self.update()
        return self._extent

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
        node.synchronize(self._frame, self._serial, (self.width(), self.height()), self._extent, self._style)
        if self._snapshot_jobs and not node.snapshot_busy:
            node.take_snapshot_job(self._snapshot_jobs.pop(0))
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

    def noteSnapshot(self, key: str, width: int, height: int, pixels: bytes) -> None:
        self.snapshotReady.emit(key, width, height, pixels)

    def noteSnapshotFailed(self, key: str, signature: str) -> None:
        self.snapshotFailed.emit(key, signature)

    def noteSnapshotPending(self) -> None:
        self.snapshotPending.emit()


__all__ = ["SCENE_BACKING", "StudioRenderNode", "StudioViewportItem"]
