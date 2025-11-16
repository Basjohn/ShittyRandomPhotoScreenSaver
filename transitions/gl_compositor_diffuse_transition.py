"""GL compositor-driven Diffuse transition.

Replaces the legacy GLDiffuseTransition overlay path with a controller that
uses the shared GLCompositorWidget. The controller owns only timing, grid
layout, and region construction; all rendering is delegated to the compositor.
"""

from __future__ import annotations

import random
from typing import Optional, List

from PySide6.QtCore import QRect, QRectF, QPoint
from PySide6.QtGui import QPixmap, QRegion, QPainterPath, QPolygon
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.animation.types import EasingCurve

from transitions.base_transition import BaseTransition, TransitionState
from rendering.gl_compositor import GLCompositorWidget


logger = get_logger(__name__)


class _DiffuseCell:
    def __init__(self, rect: QRect) -> None:
        self.rect = rect
        self.revealed: bool = False
        self.threshold: float = random.random()


class GLCompositorDiffuseTransition(BaseTransition):
    """GPU-backed Diffuse that targets the shared GL compositor widget.

    This controller mirrors the grid and random-threshold behaviour of the
    legacy GLDiffuseTransition, but instead of maintaining its own overlay it
    computes an aggregate QRegion for all revealed cells and passes that to
    GLCompositorWidget via its diffuse API.
    """

    def __init__(
        self,
        duration_ms: int = 1000,
        block_size: int = 50,
        shape: str = "Rectangle",
        easing: str = "Auto",
    ) -> None:
        super().__init__(duration_ms)
        self._block_size = max(1, int(block_size))
        valid_shapes = ["Rectangle", "Circle", "Diamond", "Plus", "Triangle"]
        self._shape = shape if shape in valid_shapes else "Rectangle"
        self._easing_str = easing
        self._widget: Optional[QWidget] = None
        self._compositor: Optional[GLCompositorWidget] = None
        self._cells: List[_DiffuseCell] = []
        self._animation_id: Optional[str] = None
        self._region: QRegion = QRegion()
        self._revealed_count: int = 0
        self._total_cells: int = 0

    # ------------------------------------------------------------------
    # BaseTransition API
    # ------------------------------------------------------------------

    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, widget: QWidget) -> bool:  # type: ignore[override]
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid pixmap for GL compositor Diffuse")
            self.error.emit("Invalid image")
            return False

        self._widget = widget

        # Begin telemetry tracking
        self._mark_start()

        # If there's no old image, just complete immediately.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("No old image, showing new image immediately (GL compositor diffuse)")
            self._show_image_immediately()
            return True

        # Resolve compositor from widget; fall back to immediate display if absent.
        comp = getattr(widget, "_gl_compositor", None)
        if comp is None or not isinstance(comp, GLCompositorWidget):
            logger.warning(
                "[GL COMPOSITOR] No compositor attached to widget; falling back to immediate display (diffuse)"
            )
            self._show_image_immediately()
            return True

        self._compositor = comp

        # Ensure compositor matches widget geometry and is above the base.
        try:
            comp.setGeometry(0, 0, widget.width(), widget.height())
            comp.show()
            comp.raise_()
        except Exception:
            logger.debug(
                "[GL COMPOSITOR] Failed to configure compositor geometry/visibility (diffuse)",
                exc_info=True,
            )

        # Build cell grid matching the widget geometry.
        width = widget.width()
        height = widget.height()
        self._build_cells(width, height)
        total = len(self._cells)

        # Drive via shared AnimationManager.
        easing_curve = self._resolve_easing()
        am = self._get_animation_manager(widget)

        def _update(progress: float) -> None:
            self._on_anim_update(progress, total)

        def _on_finished() -> None:
            self._on_anim_complete()

        self._animation_id = comp.start_diffuse(
            old_pixmap,
            new_pixmap,
            duration_ms=self.duration_ms,
            easing=easing_curve,
            animation_manager=am,
            update_callback=_update,
            on_finished=_on_finished,
        )

        self._set_state(TransitionState.RUNNING)
        self.started.emit()
        logger.info(
            "GLCompositorDiffuseTransition started (%dms, block=%dpx, shape=%s)",
            self.duration_ms,
            self._block_size,
            self._shape,
        )
        return True

    def stop(self) -> None:  # type: ignore[override]
        if self._state != TransitionState.RUNNING:
            return

        logger.debug("Stopping GLCompositorDiffuseTransition")

        if self._compositor is not None:
            try:
                # Snap to final frame when cancelling mid-way to avoid pops.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
                logger.debug(
                    "[GL COMPOSITOR] Failed to cancel current diffuse transition", exc_info=True
                )

        self._animation_id = None
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()

    def cleanup(self) -> None:  # type: ignore[override]
        logger.debug("Cleaning up GLCompositorDiffuseTransition")

        if self._compositor is not None:
            try:
                # Ensure compositor is no longer animating; do not force snap
                # here, as DisplayWidget will already have updated its base.
                self._compositor.cancel_current_transition(snap_to_new=False)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cleanup diffuse compositor", exc_info=True)
            self._compositor = None

        self._widget = None
        self._animation_id = None
        self._cells = []
        self._region = QRegion()
        self._revealed_count = 0
        self._total_cells = 0

        if self._state not in (TransitionState.FINISHED, TransitionState.CANCELLED):
            self._set_state(TransitionState.IDLE)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_cells(self, width: int, height: int) -> None:
        """Create a grid of cells covering the widget area.

        Mirrors the grid layout of GLDiffuseTransition so visuals remain
        consistent while the rendering path moves to the compositor.
        """
        self._cells = []

        cols = max(1, (width + self._block_size - 1) // self._block_size)
        rows = max(1, (height + self._block_size - 1) // self._block_size)
        for r in range(rows):
            for c in range(cols):
                x = c * self._block_size
                y = r * self._block_size
                w = self._block_size if c < cols - 1 else (width - x)
                h = self._block_size if r < rows - 1 else (height - y)
                self._cells.append(_DiffuseCell(QRect(x, y, w, h)))

        self._region = QRegion()
        self._revealed_count = 0
        self._total_cells = len(self._cells)

    def _on_anim_update(self, progress: float, total: int) -> None:
        if self._state != TransitionState.RUNNING or self._compositor is None:
            return

        p = max(0.0, min(1.0, float(progress)))

        any_new = False
        for cell in self._cells:
            if not cell.revealed and p >= cell.threshold:
                cell.revealed = True
                any_new = True
                self._revealed_count += 1
                r = cell.rect
                if self._shape == "Circle":
                    path = QPainterPath()
                    path.addEllipse(QRectF(r))
                    self._region = self._region.united(QRegion(path.toFillPolygon().toPolygon()))
                elif self._shape == "Triangle":
                    top = QPoint(r.x() + r.width() // 2, r.y())
                    bottom_left = QPoint(r.x(), r.y() + r.height())
                    bottom_right = QPoint(r.x() + r.width(), r.y() + r.height())
                    self._region = self._region.united(QRegion(QPolygon([top, bottom_left, bottom_right])))
                elif self._shape == "Diamond":
                    cx = r.x() + r.width() // 2
                    cy = r.y() + r.height() // 2
                    top = QPoint(cx, r.y())
                    right = QPoint(r.x() + r.width(), cy)
                    bottom = QPoint(cx, r.y() + r.height())
                    left = QPoint(r.x(), cy)
                    self._region = self._region.united(QRegion(QPolygon([top, right, bottom, left])))
                elif self._shape == "Plus":
                    size_w = max(1, r.width())
                    size_h = max(1, r.height())
                    thickness_w = max(1, size_w // 3)
                    thickness_h = max(1, size_h // 3)
                    cx = r.x() + size_w // 2
                    cy = r.y() + size_h // 2
                    v_rect = QRect(cx - thickness_w // 2, r.y(), thickness_w, size_h)
                    h_rect = QRect(r.x(), cy - thickness_h // 2, size_w, thickness_h)
                    self._region = self._region.united(QRegion(v_rect))
                    self._region = self._region.united(QRegion(h_rect))
                else:
                    self._region = self._region.united(QRegion(r))

        if any_new:
            try:
                self._compositor.set_diffuse_region(self._region)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to update diffuse region", exc_info=True)

        if total > 0:
            self._emit_progress(self._revealed_count / total)

        if p >= 1.0 and self._revealed_count >= total:
            self._on_anim_complete()

    def _on_anim_complete(self) -> None:
        if self._state != TransitionState.RUNNING:
            return

        # Telemetry end
        self._mark_end()

        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("GLCompositorDiffuseTransition finished")

    def _show_image_immediately(self) -> None:
        """Immediate completion when no GL compositor path is available."""
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("GLCompositorDiffuseTransition showed image immediately")

    def _resolve_easing(self) -> EasingCurve:
        name = (self._easing_str or "Auto").strip()
        if name == "Auto":
            return EasingCurve.QUAD_IN_OUT
        mapping = {
            "Linear": EasingCurve.LINEAR,
            "InQuad": EasingCurve.QUAD_IN,
            "OutQuad": EasingCurve.QUAD_OUT,
            "InOutQuad": EasingCurve.QUAD_IN_OUT,
            "InCubic": EasingCurve.CUBIC_IN,
            "OutCubic": EasingCurve.CUBIC_OUT,
            "InOutCubic": EasingCurve.CUBIC_IN_OUT,
        }
        return mapping.get(name, EasingCurve.QUAD_IN_OUT)
