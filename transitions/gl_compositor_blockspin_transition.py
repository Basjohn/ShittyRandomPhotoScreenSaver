"""GL compositor-driven 3D Block Spins transition.

This transition delegates all rendering to the shared :class:`GLCompositorWidget`.
The controller owns only timing and direction and drives the compositor via its
block-spin API (:meth:`start_block_spin`). Historical grid parameters are still
accepted by the constructor for compatibility but are not used to render a grid
of tiles; the GLSL path currently renders a single full-frame 3D slab.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.animation.types import EasingCurve

from transitions.base_transition import BaseTransition, TransitionState
from transitions.slide_transition import SlideDirection
from rendering.gl_compositor import GLCompositorWidget


logger = get_logger(__name__)


class GLCompositorBlockSpinTransition(BaseTransition):
    """GPU-backed 3D Block Spins targeting the shared GL compositor widget.

    The controller carries only duration and direction; all actual drawing
    happens inside :class:`GLCompositorWidget`, which renders a single thin 3D
    slab over a black void. ``grid_rows``/``grid_cols`` and ``use_grid`` are
    kept for legacy configuration compatibility but no longer enable a tile
    grid – the compositor always renders a single slab.
    """

    def __init__(
        self,
        duration_ms: int = 3000,
        easing: str = "Auto",
        direction: SlideDirection = SlideDirection.LEFT,
    ) -> None:
        super().__init__(duration_ms)
        self._direction: SlideDirection = direction
        self._widget: Optional[QWidget] = None
        self._compositor: Optional[GLCompositorWidget] = None
        self._animation_id: Optional[str] = None
        self._easing_str: str = easing

    # ------------------------------------------------------------------
    # BaseTransition API
    # ------------------------------------------------------------------

    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, widget: QWidget) -> bool:  # type: ignore[override]
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid pixmap for GL compositor Block Spins")
            self.error.emit("Invalid image")
            return False

        self._widget = widget

        # Begin telemetry tracking
        self._mark_start()

        # If there's no old image, just complete immediately.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("No old image, showing new image immediately (GL compositor block spins)")
            self._show_image_immediately()
            return True

        # Resolve compositor from widget; fall back to immediate display if absent.
        comp = getattr(widget, "_gl_compositor", None)
        if comp is None or not isinstance(comp, GLCompositorWidget):
            logger.warning(
                "[GL COMPOSITOR] No compositor attached to widget; falling back to immediate display (block spins)"
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
                "[GL COMPOSITOR] Failed to configure compositor geometry/visibility (block spins)",
                exc_info=True,
            )

        # Prewarm shader textures for this pixmap pair so the first
        # BlockSpin frame does not pay the full texture upload cost.
        try:
            warm = getattr(comp, "warm_shader_textures", None)
            if callable(warm):
                warm(old_pixmap, new_pixmap)
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to warm block spins textures", exc_info=True)

        # Drive via shared AnimationManager.
        easing_curve = self._resolve_easing()
        am = self._get_animation_manager(widget)

        def _on_finished() -> None:
            # Called by compositor when its animation completes.
            self._on_anim_complete()

        self._animation_id = comp.start_block_spin(
            old_pixmap,
            new_pixmap,
            duration_ms=self.duration_ms,
            easing=easing_curve,
            animation_manager=am,
            direction=self._direction,
            on_finished=_on_finished,
        )

        self._set_state(TransitionState.RUNNING)
        self.started.emit()
        logger.info(
            "GLCompositorBlockSpinTransition started (%dms, dir=%s)",
            self.duration_ms,
            getattr(self._direction, "value", self._direction),
        )
        return True

    def stop(self) -> None:  # type: ignore[override]
        if self._state != TransitionState.RUNNING:
            return

        logger.debug("Stopping GLCompositorBlockSpinTransition")

        if self._compositor is not None:
            try:
                # Snap to final frame when cancelling mid-way to avoid pops.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cancel current block spins transition", exc_info=True)

        self._animation_id = None
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()

    def cleanup(self) -> None:  # type: ignore[override]
        logger.debug("Cleaning up GLCompositorBlockSpinTransition")

        if self._compositor is not None:
            try:
                # Ensure compositor is no longer animating; do not force snap
                # here, as DisplayWidget will already have updated its base.
                self._compositor.cancel_current_transition(snap_to_new=False)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cleanup block spins compositor", exc_info=True)
            self._compositor = None

        self._widget = None
        self._animation_id = None

        if self._state not in (TransitionState.FINISHED, TransitionState.CANCELLED):
            self._set_state(TransitionState.IDLE)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_anim_complete(self) -> None:
        """Called when the compositor finishes its block spins animation."""
        # End telemetry tracking
        self._mark_end()

        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("GLCompositorBlockSpinTransition finished")

    def _show_image_immediately(self) -> None:
        """Immediate completion when no GL compositor path is available."""
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()

    def _resolve_easing(self) -> EasingCurve:
        """Map UI easing string to core EasingCurve with 'Auto' default."""
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
