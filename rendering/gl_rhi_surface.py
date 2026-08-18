"""External-OpenGL QRhi substrate for SRPSS presentation surfaces.

Qt 6.9.1 does not present a ``QOpenGLWidget`` directly: it renders the widget
into an offscreen FBO owned by a *child* ``QOpenGLContext`` and the top-level
QRhi widget compositor then consumes that texture.  ``QRhiWidget`` instead
renders through the **top-level window's QRhi**, removing the extra child
context and its shared-context flush/compose handoff.

This module owns only two things:

1. lifecycle ownership of the **borrowed** Qt-owned QRhi OpenGL context; and
2. exception-safe bracketing of raw OpenGL work inside a QRhi render pass.

It is deliberately not a rendering framework.  Existing PyOpenGL renderers are
reused unchanged; QRhi is only the surface/lifecycle substrate beneath them.

Ownership contract
------------------

* The ``QRhi`` and its ``QOpenGLContext`` are **owned by Qt**.  SRPSS may make
  the context current through the documented QRhi seam, but must never destroy
  it, and must never ``doneCurrent()`` it as though SRPSS owned it.
* ``QRhiWidget.rhi()`` is lifecycle-scoped.  The borrowed identity is captured
  at ``initialize()`` and fenced by a monotonic generation so a QRhi
  replacement cannot leave SRPSS state attached to a dead share group.
* Every SRPSS-owned GL object keeps exactly one deletion owner.  Deletion runs
  while the borrowed context is current and stays fail-closed.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from PySide6.QtCore import QSize
from PySide6.QtGui import (
    QColor,
    QOpenGLContext,
    QPainter,
    QRhi,
    QRhiCommandBuffer,
    QRhiDepthStencilClearValue,
)
from PySide6.QtOpenGL import QOpenGLPaintDevice
from PySide6.QtWidgets import QRhiWidget

from core.logging.logger import get_logger

logger = get_logger(__name__)


# The compositor is opaque: the QRhi pass clears to opaque black exactly like
# the previous QOpenGLWidget surface did before its first draw.
OPAQUE_CLEAR_COLOR = QColor(0, 0, 0, 255)
DEFAULT_DEPTH_STENCIL_CLEAR = QRhiDepthStencilClearValue(1.0, 0)


class BorrowedRhiGLContext:
    """Generation-fenced handle to the Qt-owned QRhi OpenGL context.

    SRPSS never creates or destroys the underlying ``QRhi``/``QOpenGLContext``.
    This object only records *which* Qt-owned context is currently backing the
    surface, so owners can:

    * detect that Qt replaced the QRhi (reparent, screen change, teardown) and
      drop stale numeric GL ids instead of deleting them in a foreign context;
    * make the correct context current for GL work that happens outside a
      render callback; and
    * retire SRPSS-owned share-group dependants when the share group dies.
    """

    __slots__ = ("_rhi", "_context", "_generation")

    def __init__(self) -> None:
        self._rhi: Optional[QRhi] = None
        self._context: Optional[QOpenGLContext] = None
        self._generation: int = 0

    # -- identity ---------------------------------------------------------

    @property
    def generation(self) -> int:
        """Monotonic id of the current borrowed QRhi/context pairing."""
        return self._generation

    @property
    def context(self) -> Optional[QOpenGLContext]:
        """The borrowed Qt-owned context, or None when no QRhi is attached."""
        return self._context

    @property
    def rhi(self) -> Optional[QRhi]:
        return self._rhi

    def is_attached(self) -> bool:
        return self._rhi is not None and self._context is not None

    def capture(self, rhi: Optional[QRhi], context: Optional[QOpenGLContext]) -> bool:
        """Record the borrowed pairing; return True when the generation changed.

        Called from ``QRhiWidget.initialize()``, which Qt invokes both on first
        use *and* whenever the render target is rebuilt.  A target resize keeps
        the same QRhi and therefore the same generation, so immutable GL
        resources are not rebuilt for a resize.
        """
        if rhi is None or context is None:
            return self.invalidate()
        if rhi is self._rhi and context is self._context:
            return False
        self._rhi = rhi
        self._context = context
        self._generation += 1
        return True

    def invalidate(self) -> bool:
        """Detach from the borrowed context without destroying it."""
        if self._rhi is None and self._context is None:
            return False
        self._rhi = None
        self._context = None
        self._generation += 1
        return True

    # -- currentness ------------------------------------------------------

    def make_current(self) -> bool:
        """Make the borrowed OpenGL context current on this thread.

        ``QRhi.makeThreadLocalNativeContextCurrent()`` is the documented Qt
        seam for running foreign OpenGL against a QRhi OpenGL backend.  There
        is deliberately no matching release call: the context belongs to Qt,
        and SRPSS must not ``doneCurrent()`` it.
        """
        rhi = self._rhi
        if rhi is None:
            return False
        try:
            return bool(rhi.makeThreadLocalNativeContextCurrent())
        except Exception:
            logger.debug(
                "[GL RHI] makeThreadLocalNativeContextCurrent failed", exc_info=True
            )
            return False

    def is_current(self) -> bool:
        """Whether the borrowed context is the current context on this thread."""
        context = self._context
        if context is None:
            return False
        try:
            return QOpenGLContext.currentContext() is context
        except Exception:
            return False


class ExternalPassState:
    """Bookkeeping proving the external block/pass nesting stayed balanced.

    The counters exist because a Python exception escaping a QRhi render
    callback is not merely a dropped frame: it can strand QRhi inside an
    external block or an open render pass and poison every later frame, and an
    exception escaping a Qt virtual override can terminate the process.
    """

    __slots__ = ("pass_depth", "external_depth", "passes_begun", "externals_begun")

    def __init__(self) -> None:
        self.pass_depth = 0
        self.external_depth = 0
        self.passes_begun = 0
        self.externals_begun = 0

    def is_balanced(self) -> bool:
        return self.pass_depth == 0 and self.external_depth == 0


@contextmanager
def external_gl_section(
    cb: QRhiCommandBuffer,
    state: Optional[ExternalPassState] = None,
) -> Iterator[None]:
    """Bracket raw OpenGL commands with ``beginExternal``/``endExternal``.

    Valid both inside an ``ExternalContent`` render pass and outside any pass
    (Qt permits the latter, which is what surface initialization uses).
    ``endExternal()`` runs exactly once and only when ``beginExternal()``
    actually succeeded.
    """
    cb.beginExternal()
    if state is not None:
        state.external_depth += 1
        state.externals_begun += 1
    try:
        yield
    finally:
        try:
            cb.endExternal()
        finally:
            if state is not None:
                state.external_depth -= 1


@contextmanager
def external_gl_render_pass(
    cb: QRhiCommandBuffer,
    render_target,
    *,
    clear_color: QColor = OPAQUE_CLEAR_COLOR,
    depth_stencil_clear: QRhiDepthStencilClearValue = DEFAULT_DEPTH_STENCIL_CLEAR,
    state: Optional[ExternalPassState] = None,
) -> Iterator[None]:
    """Open an ``ExternalContent`` render pass and bracket raw OpenGL inside it.

    The pass is ended exactly once on every path, including exceptions, so a
    failed frame cannot leave QRhi mid-pass for the frames that follow.
    """
    cb.beginPass(
        render_target,
        clear_color,
        depth_stencil_clear,
        None,
        QRhiCommandBuffer.BeginPassFlag.ExternalContent,
    )
    if state is not None:
        state.pass_depth += 1
        state.passes_begun += 1
    try:
        with external_gl_section(cb, state):
            yield
    finally:
        try:
            cb.endPass()
        finally:
            if state is not None:
                state.pass_depth -= 1


@contextmanager
def external_gl_painter(
    pixel_size: QSize,
    device_pixel_ratio: float,
) -> Iterator[QPainter]:
    """Yield a ``QPainter`` drawing into the currently bound QRhi GL target.

    ``QPainter(widget)`` targets a QWidget backing store, which is *not* the
    QRhi render texture, so the old ``QPainter(compositor)`` sites cannot be
    carried over unchanged.  ``QOpenGLPaintDevice`` renders into whatever
    framebuffer is bound, which inside the external section is exactly the
    framebuffer Qt bound for the QRhi target.

    The device is sized in physical pixels and given the widget's device pixel
    ratio, matching what ``QOpenGLWidget`` did internally, so callers keep
    drawing in unchanged logical coordinates.
    """
    device = QOpenGLPaintDevice(pixel_size)
    try:
        device.setDevicePixelRatio(float(device_pixel_ratio))
    except Exception:
        logger.debug("[GL RHI] Failed to apply painter device pixel ratio", exc_info=True)
    painter = QPainter(device)
    try:
        yield painter
    finally:
        if painter.isActive():
            painter.end()


class ExternalOpenGLRhiWidget(QRhiWidget):
    """QRhiWidget that runs SRPSS's existing raw OpenGL renderers.

    Subclasses implement the three ``gl_*`` hooks instead of the Qt overrides so
    the pass/external bracketing and the borrowed-context fence stay in one
    place.  The OpenGL backend is selected in the constructor, before the
    widget is realized, because the platform default on Windows is Direct3D and
    this checkpoint deliberately reuses the PyOpenGL renderer rather than
    rewriting shaders into QRhi pipelines.
    """

    # Rendering failures must stay visible without becoming a per-frame log.
    _RHI_FAILURE_LOG_INTERVAL = 300

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Must precede realization: the top-level QRhi backend is resolved from
        # the first texture-backed child, and the existing renderer is OpenGL.
        self.setApi(QRhiWidget.Api.OpenGL)
        self._rhi_gl = BorrowedRhiGLContext()
        self._rhi_pass_state = ExternalPassState()
        self._rhi_render_failures = 0

    def _record_render_failure(self) -> None:
        """Log a render failure loudly but at a bounded rate."""
        self._rhi_render_failures += 1
        count = self._rhi_render_failures
        if count == 1 or count % self._RHI_FAILURE_LOG_INTERVAL == 0:
            logger.error(
                "[GL RHI] Surface render failed (failure_count=%d)",
                count,
                exc_info=True,
            )

    # -- hooks for subclasses --------------------------------------------

    def gl_initialize(self, generation_changed: bool) -> None:
        """Create/validate SRPSS-owned GL resources for the borrowed context.

        ``generation_changed`` is False for a plain render-target resize, where
        immutable resources must be preserved rather than rebuilt.
        """

    def gl_render(self) -> None:
        """Draw one frame with raw OpenGL into the bound QRhi target."""

    def gl_release(self) -> None:
        """Delete SRPSS-owned GL resources; borrowed context stays untouched."""

    # -- painting into the QRhi target ------------------------------------

    @contextmanager
    def gl_target_painter(self) -> Iterator[Optional[QPainter]]:
        """Yield a ``QPainter`` drawing into this surface's QRhi render target.

        Only valid while the external GL section is open, because it paints
        into the currently bound framebuffer. Yields ``None`` when no render
        target is available so callers degrade instead of raising mid-frame.

        The device is sized from the render target and carries the widget's
        device pixel ratio, so callers keep using unchanged logical
        coordinates exactly as they did with ``QPainter(qopenglwidget)``.
        """
        render_target = self.renderTarget()
        if render_target is None:
            yield None
            return
        pixel_size = render_target.pixelSize()
        if pixel_size.width() <= 0 or pixel_size.height() <= 0:
            yield None
            return
        with external_gl_painter(pixel_size, self.devicePixelRatioF()) as painter:
            yield painter

    # -- Qt overrides -----------------------------------------------------

    def initialize(self, cb: QRhiCommandBuffer) -> None:  # type: ignore[override]
        # Qt has made the QRhi's OpenGL context current for this frame, so
        # currentContext() is the authoritative way to observe the borrowed
        # context: PySide6 6.9.1 returns a base QRhiNativeHandles from
        # QRhi.nativeHandles(), which does not expose the GLES2 `context` field.
        context = QOpenGLContext.currentContext()
        generation_changed = self._rhi_gl.capture(self.rhi(), context)
        try:
            with external_gl_section(cb, self._rhi_pass_state):
                self.gl_initialize(generation_changed)
        except Exception:
            # Never let an exception escape a Qt virtual override.
            logger.error("[GL RHI] Surface initialization failed", exc_info=True)

    def render(self, cb: QRhiCommandBuffer) -> None:  # type: ignore[override]
        render_target = self.renderTarget()
        if render_target is None:
            return
        try:
            with external_gl_render_pass(
                cb, render_target, state=self._rhi_pass_state
            ):
                self.gl_render()
        except Exception:
            self._record_render_failure()

    def releaseResources(self) -> None:  # type: ignore[override]
        # Qt calls this when the QRhi is about to change or go away, and it
        # does *not* leave the OpenGL context current, so deletion must make
        # the borrowed context current explicitly or every delete is invalid.
        try:
            self._rhi_gl.make_current()
            self.gl_release()
        except Exception:
            logger.error("[GL RHI] Surface resource release failed", exc_info=True)
