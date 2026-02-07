"""GL compositor-driven Crumble transition.

This transition creates a rock-like crack pattern across the old image, then
the pieces fall away with physics-based motion to reveal the new image. All
rendering is delegated to the shared GLCompositorWidget via its crumble API.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.animation.types import EasingCurve

from transitions.base_transition import BaseTransition, TransitionState
from rendering.gl_compositor import GLCompositorWidget


logger = get_logger(__name__)


class GLCompositorCrumbleTransition(BaseTransition):
    """GPU-backed Crumble transition that targets the shared GL compositor.

    The crumble effect creates a Voronoi-like crack pattern across the old
    image, then the pieces fall away with physics-based motion (gravity,
    rotation, drift) to reveal the new image underneath.
    """

    def __init__(
        self,
        duration_ms: int = 3500,
        piece_count: int = 8,
        crack_complexity: float = 1.0,
        mosaic_mode: bool = False,
        weight_mode: float = 0.0,
    ) -> None:
        super().__init__(duration_ms)
        self._piece_count = max(4, piece_count)
        self._crack_complexity = max(0.5, min(2.0, crack_complexity))
        self._mosaic_mode = mosaic_mode
        # 0=Top Weighted, 1=Bottom Weighted, 2=Random Weighted, 3=Random Choice, 4=Age Weighted
        self._weight_mode = max(0.0, min(4.0, weight_mode))
        self._widget: Optional[QWidget] = None
        self._compositor: Optional[GLCompositorWidget] = None
        self._animation_id: Optional[str] = None

    # ------------------------------------------------------------------
    # BaseTransition API
    # ------------------------------------------------------------------

    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, widget: QWidget) -> bool:  # type: ignore[override]
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid pixmap for GL compositor Crumble")
            self.error.emit("Invalid image")
            return False

        self._widget = widget

        # Begin telemetry tracking
        self._mark_start()

        # If there's no old image, just complete immediately.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("No old image, showing new image immediately (GL compositor crumble)")
            self._show_image_immediately()
            return True

        # Resolve compositor from widget; fall back to immediate display if absent.
        comp = getattr(widget, "_gl_compositor", None)
        if comp is None or not isinstance(comp, GLCompositorWidget):
            logger.warning(
                "[GL COMPOSITOR] No compositor attached to widget; falling back to immediate display (crumble)"
            )
            self._show_image_immediately()
            return True

        self._compositor = comp

        # Best-effort shader texture prewarm so the first GLSL frame does not
        # pay the full upload cost. Failures are logged and ignored so the
        # transition can still fall back safely.
        try:
            warm = getattr(comp, "warm_shader_textures", None)
            if callable(warm):
                warm(old_pixmap, new_pixmap)
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to warm crumble textures", exc_info=True)

        # Ensure compositor matches widget geometry and is above the base.
        try:
            comp.setGeometry(0, 0, widget.width(), widget.height())
            comp.show()
            comp.raise_()
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to configure compositor geometry/visibility (crumble)", exc_info=True)

        # Drive via shared AnimationManager.
        easing_curve = EasingCurve.CUBIC_IN_OUT
        am = self._get_animation_manager(widget)

        def _on_finished() -> None:
            self._on_anim_complete()

        self._animation_id = comp.start_crumble(
            old_pixmap,
            new_pixmap,
            duration_ms=self.duration_ms,
            easing=easing_curve,
            animation_manager=am,
            on_finished=_on_finished,
            piece_count=self._piece_count,
            crack_complexity=self._crack_complexity,
            mosaic_mode=self._mosaic_mode,
            weight_mode=self._weight_mode,
        )

        self._set_state(TransitionState.RUNNING)
        self.started.emit()
        if is_perf_metrics_enabled():
            logger.info("[PERF] GLCompositorCrumbleTransition started")
        mode_str = "glass" if self._mosaic_mode else "rock"
        logger.info(
            "GLCompositorCrumbleTransition started (%dms, pieces=%d, complexity=%.1f, mode=%s)",
            self.duration_ms,
            self._piece_count,
            self._crack_complexity,
            mode_str,
        )
        return True

    def stop(self) -> None:  # type: ignore[override]
        if self._state != TransitionState.RUNNING:
            return

        logger.debug("Stopping GLCompositorCrumbleTransition")

        if self._compositor is not None:
            try:
                # Snap to final frame when cancelling mid-way to avoid pops.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cancel current crumble transition", exc_info=True)

        self._animation_id = None
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()

    def cleanup(self) -> None:  # type: ignore[override]
        logger.debug("Cleaning up GLCompositorCrumbleTransition")

        if self._compositor is not None:
            try:
                # Ensure compositor is no longer animating; do not force snap
                # here, as DisplayWidget will already have updated its base.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cleanup crumble compositor", exc_info=True)
            self._compositor = None

        self._widget = None
        self._animation_id = None

        if self._state not in (TransitionState.FINISHED, TransitionState.CANCELLED):
            self._set_state(TransitionState.IDLE)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_anim_complete(self) -> None:
        """Handle animation completion from the compositor."""
        if self._state != TransitionState.RUNNING:
            return

        self._animation_id = None
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("GLCompositorCrumbleTransition completed")
