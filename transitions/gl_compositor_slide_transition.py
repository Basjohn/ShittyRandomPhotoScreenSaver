"""GL compositor-driven slide transition.

This transition does not create its own QOpenGLWidget overlay. Instead it
assumes the parent DisplayWidget owns a single GLCompositorWidget child and
uses it to render the slide animation. This removes per-transition GL widgets
while preserving the existing GL Slide visuals.
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QPoint

from core.logging.logger import get_logger
from core.animation.types import EasingCurve

from transitions.base_transition import BaseTransition, TransitionState
from transitions.slide_transition import SlideDirection
from rendering.gl_compositor import GLCompositorWidget


logger = get_logger(__name__)


class GLCompositorSlideTransition(BaseTransition):
    """GPU-backed Slide that targets the shared GL compositor widget.

    The controller owns only timing, direction, easing, and telemetry state.
    Rendering is delegated to the single GLCompositorWidget attached to the
    DisplayWidget.
    """

    def __init__(
        self,
        duration_ms: int = 1000,
        direction: SlideDirection = SlideDirection.LEFT,
        easing: str = "Auto",
    ) -> None:
        super().__init__(duration_ms)
        self._widget: Optional[QWidget] = None
        self._compositor: Optional[GLCompositorWidget] = None
        self._animation_id: Optional[str] = None
        self._direction: SlideDirection = direction
        self._easing_str: str = easing

    # ------------------------------------------------------------------
    # BaseTransition API
    # ------------------------------------------------------------------

    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, widget: QWidget) -> bool:  # type: ignore[override]
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid pixmap for GL compositor slide")
            self.error.emit("Invalid image")
            return False

        self._widget = widget

        # Begin telemetry tracking
        self._mark_start()

        # If there's no old image, just complete immediately.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("No old image, showing new image immediately (GL compositor slide)")
            self._show_image_immediately()
            return True

        # Resolve compositor from widget; fall back to immediate display if absent.
        comp = getattr(widget, "_gl_compositor", None)
        if comp is None or not isinstance(comp, GLCompositorWidget):
            logger.warning("[GL COMPOSITOR] No compositor attached to widget; falling back to immediate display (slide)")
            self._show_image_immediately()
            return True

        self._compositor = comp

        # Ensure compositor matches widget geometry and is above the base.
        try:
            comp.setGeometry(0, 0, widget.width(), widget.height())
            comp.show()
            comp.raise_()
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to configure compositor geometry/visibility (slide)", exc_info=True)

        # Drive slide via shared AnimationManager.
        easing_curve = self._resolve_easing()
        am = self._get_animation_manager(widget)

        width = widget.width()
        height = widget.height()
        old_start, old_end, new_start, new_end = self._calculate_positions(width, height)

        def _on_finished() -> None:
            # Called by compositor when its animation completes.
            self._on_anim_complete()

        self._animation_id = comp.start_slide(
            old_pixmap,
            new_pixmap,
            old_start=old_start,
            old_end=old_end,
            new_start=new_start,
            new_end=new_end,
            duration_ms=self.duration_ms,
            easing=easing_curve,
            animation_manager=am,
            on_finished=_on_finished,
        )

        self._set_state(TransitionState.RUNNING)
        self.started.emit()
        logger.info(
            "GLCompositorSlideTransition started (%dms, dir=%s)",
            self.duration_ms,
            self._direction.value,
        )
        return True

    def stop(self) -> None:  # type: ignore[override]
        if self._state != TransitionState.RUNNING:
            return

        logger.debug("Stopping GLCompositorSlideTransition")

        if self._compositor is not None:
            try:
                # Snap to final frame when cancelling mid-way to avoid pops.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cancel current slide transition", exc_info=True)

        self._animation_id = None
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()

    def cleanup(self) -> None:  # type: ignore[override]
        logger.debug("Cleaning up GLCompositorSlideTransition")

        if self._compositor is not None:
            try:
                # Ensure compositor is no longer animating; do not force snap
                # here, as DisplayWidget will already have updated its base.
                # The compositor remains visible as the primary renderer.
                self._compositor.cancel_current_transition(snap_to_new=False)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cleanup slide compositor", exc_info=True)
            self._compositor = None

        self._widget = None
        self._animation_id = None

        if self._state not in (TransitionState.FINISHED, TransitionState.CANCELLED):
            self._set_state(TransitionState.IDLE)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _calculate_positions(self, width: int, height: int) -> Tuple[QPoint, QPoint, QPoint, QPoint]:
        """Calculate start/end positions for both images.

        Mirrors the logic of SlideTransition._calculate_positions so that the
        compositor-based slide matches existing visuals.
        """
        if self._direction == SlideDirection.LEFT:
            # Old slides left (out), new slides in from right
            old_start = QPoint(0, 0)
            old_end = QPoint(-width, 0)
            new_start = QPoint(width, 0)
            new_end = QPoint(0, 0)
        elif self._direction == SlideDirection.RIGHT:
            # Old slides right (out), new slides in from left
            old_start = QPoint(0, 0)
            old_end = QPoint(width, 0)
            new_start = QPoint(-width, 0)
            new_end = QPoint(0, 0)
        elif self._direction == SlideDirection.UP:
            # Old slides up (out), new slides in from bottom
            old_start = QPoint(0, 0)
            old_end = QPoint(0, -height)
            new_start = QPoint(0, height)
            new_end = QPoint(0, 0)
        elif self._direction == SlideDirection.DOWN:
            # Old slides down (out), new slides in from top
            old_start = QPoint(0, 0)
            old_end = QPoint(0, height)
            new_start = QPoint(0, -height)
            new_end = QPoint(0, 0)
        elif self._direction == SlideDirection.DIAG_TL_BR:
            # Old moves towards top-left, new comes from bottom-right
            old_start = QPoint(0, 0)
            old_end = QPoint(-width, -height)
            new_start = QPoint(width, height)
            new_end = QPoint(0, 0)
        elif self._direction == SlideDirection.DIAG_TR_BL:
            # Old moves towards top-right, new comes from bottom-left
            old_start = QPoint(0, 0)
            old_end = QPoint(width, -height)
            new_start = QPoint(-width, height)
            new_end = QPoint(0, 0)
        else:
            # Default to LEFT if unknown
            old_start = QPoint(0, 0)
            old_end = QPoint(-width, 0)
            new_start = QPoint(width, 0)
            new_end = QPoint(0, 0)

        return old_start, old_end, new_start, new_end

    def _on_anim_complete(self) -> None:
        """Called when the compositor finishes its slide animation."""
        # End telemetry tracking
        self._mark_end()

        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("GLCompositorSlideTransition finished")

    def _show_image_immediately(self) -> None:
        """Immediate completion when no GL compositor path is available."""
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()

    def _resolve_easing(self) -> EasingCurve:
        """Map UI easing string to core EasingCurve with 'Auto' default.

        Uses the same mapping as GLSlideTransition to keep visual behaviour
        aligned with the legacy GL slide overlay.
        """
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
