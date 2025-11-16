"""GL compositor-driven Blinds transition.

This transition delegates all rendering to the shared GLCompositorWidget. It
owns only timing and slat geometry and drives the compositor via its blinds
API (start_blinds / set_blinds_region).
"""
from __future__ import annotations

from typing import Optional, List

from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap, QRegion
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.animation.types import EasingCurve

from transitions.base_transition import BaseTransition, TransitionState
from rendering.gl_compositor import GLCompositorWidget


logger = get_logger(__name__)


class _CompositorBlindSlat:
    def __init__(self, rect: QRect) -> None:
        self.rect = rect


class GLCompositorBlindsTransition(BaseTransition):
    """GPU-backed Blinds that targets the shared GL compositor widget.

    The controller mirrors the grid and reveal behaviour of GLBlindsTransition,
    but instead of owning its own QOpenGLWidget overlay it computes an
    aggregate QRegion for all slats and passes that to GLCompositorWidget.
    """

    def __init__(
        self,
        duration_ms: int = 1800,
        slat_rows: int = 5,
        slat_cols: int = 7,
    ) -> None:
        super().__init__(duration_ms)
        self._rows = slat_rows
        self._cols = slat_cols
        self._widget: Optional[QWidget] = None
        self._compositor: Optional[GLCompositorWidget] = None
        self._slats: List[_CompositorBlindSlat] = []
        self._animation_id: Optional[str] = None

    # ------------------------------------------------------------------
    # BaseTransition API
    # ------------------------------------------------------------------

    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, widget: QWidget) -> bool:  # type: ignore[override]
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid pixmap for GL compositor Blinds")
            self.error.emit("Invalid image")
            return False

        self._widget = widget

        # Begin telemetry tracking
        self._mark_start()

        # If there's no old image, just complete immediately.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("No old image, showing new image immediately (GL compositor blinds)")
            self._show_image_immediately()
            return True

        # Resolve compositor from widget; fall back to immediate display if absent.
        comp = getattr(widget, "_gl_compositor", None)
        if comp is None or not isinstance(comp, GLCompositorWidget):
            logger.warning(
                "[GL COMPOSITOR] No compositor attached to widget; falling back to immediate display (blinds)"
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
            logger.debug("[GL COMPOSITOR] Failed to configure compositor geometry/visibility (blinds)", exc_info=True)

        # Build slat grid matching the widget geometry.
        width = widget.width()
        height = widget.height()
        self._create_slats(width, height)

        # Drive via shared AnimationManager.
        easing_curve = EasingCurve.LINEAR
        am = self._get_animation_manager(widget)

        def _update(progress: float) -> None:
            self._on_anim_update(progress)

        def _on_finished() -> None:
            self._on_anim_complete()

        self._animation_id = comp.start_blinds(
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
            "GLCompositorBlindsTransition started (%dms, grid=%dx%d)",
            self.duration_ms,
            self._cols,
            self._rows,
        )
        return True

    def stop(self) -> None:  # type: ignore[override]
        if self._state != TransitionState.RUNNING:
            return

        logger.debug("Stopping GLCompositorBlindsTransition")

        if self._compositor is not None:
            try:
                # Snap to final frame when cancelling mid-way to avoid pops.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cancel current blinds transition", exc_info=True)

        self._animation_id = None
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()

    def cleanup(self) -> None:  # type: ignore[override]
        logger.debug("Cleaning up GLCompositorBlindsTransition")

        if self._compositor is not None:
            try:
                # Ensure compositor is no longer animating; do not force snap
                # here, as DisplayWidget will already have updated its base.
                self._compositor.cancel_current_transition(snap_to_new=False)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cleanup blinds compositor", exc_info=True)
            self._compositor = None

        self._widget = None
        self._animation_id = None
        self._slats = []

        if self._state not in (TransitionState.FINISHED, TransitionState.CANCELLED):
            self._set_state(TransitionState.IDLE)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _create_slats(self, width: int, height: int) -> None:
        """Create a grid of slats covering the widget area.

        Mirrors the grid layout of GLBlindsTransition so visuals remain
        consistent while the rendering path moves to the compositor.
        """
        self._slats = []

        cols = max(2, int(self._cols) * 2)
        aspect = height / max(1, width)
        rows = max(2, int(round(cols * aspect)))

        bw = max(1, width // cols)
        bh = max(1, height // rows)

        for r in range(rows):
            for c in range(cols):
                x = c * bw
                y = r * bh
                w = bw if c < cols - 1 else (width - x)
                h = bh if r < rows - 1 else (height - y)
                self._slats.append(_CompositorBlindSlat(QRect(x, y, w, h)))

    def _on_anim_update(self, progress: float) -> None:
        if self._state != TransitionState.RUNNING or self._compositor is None:
            return

        p = max(0.0, min(1.0, float(progress)))

        region = QRegion()
        for slat in self._slats:
            r = slat.rect
            reveal_w = max(1, int(r.width() * p))
            dx = r.x() + (r.width() - reveal_w) // 2
            reveal_rect = QRect(dx, r.y(), reveal_w, r.height())
            region = region.united(QRegion(reveal_rect))

        try:
            self._compositor.set_blinds_region(region)
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to update blinds region", exc_info=True)

        self._emit_progress(p)

        if p >= 1.0:
            self._on_anim_complete()

    def _on_anim_complete(self) -> None:
        if self._state != TransitionState.RUNNING:
            return

        # Telemetry end
        self._mark_end()

        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("GLCompositorBlindsTransition finished")

    def _show_image_immediately(self) -> None:
        """Immediate completion when no GL compositor path is available."""
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("GLCompositorBlindsTransition showed image immediately")
