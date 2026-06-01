"""GL compositor-driven Block Puzzle Flip transition.

This transition delegates all rendering to the shared GLCompositorWidget. It
owns timing plus shader-grid hints and drives the compositor via its
block-flip API.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.animation.types import EasingCurve

from transitions.base_transition import BaseTransition, TransitionState
from transitions.base_transition import SlideDirection
from rendering.gl_compositor import GLCompositorWidget


logger = get_logger(__name__)


class GLCompositorBlockFlipTransition(BaseTransition):
    """GPU-backed Block Puzzle Flip that targets the shared GL compositor.

    The controller mirrors the timing and grid behaviour of the existing GL
    BlockPuzzleFlipTransition, but instead of maintaining its own QOpenGLWidget
    overlay it computes only the effective shader grid and lets the compositor
    shader own the reveal path entirely.
    """

    def __init__(
        self,
        duration_ms: int = 3000,
        grid_rows: int = 4,
        grid_cols: int = 6,
        flip_duration_ms: int = 500,
        direction: Optional[SlideDirection] = None,
    ) -> None:
        super().__init__(duration_ms)
        self._uses_deferred_start_telemetry = True
        self._grid_rows = grid_rows
        self._grid_cols = grid_cols
        self._flip_duration_ms = flip_duration_ms
        self._widget: Optional[QWidget] = None
        self._compositor: Optional[GLCompositorWidget] = None
        self._animation_id: Optional[str] = None
        self._total_duration_ms: int = max(1, int(duration_ms + flip_duration_ms))
        # Optional direction bias so the compositor-backed Block Puzzle Flip
        # follows the same edge-originated wave model as the CPU variant.
        self._direction: Optional[SlideDirection] = direction
        # Effective grid used by the GLSL BlockFlip shader; populated when the
        # block grid is created so the compositor can mirror the controller
        # layout.
        self._shader_cols: int = 0
        self._shader_rows: int = 0

    def get_expected_duration_ms(self) -> int:
        if getattr(self, "_effective_duration_ms", None):
            return int(self._effective_duration_ms)
        total = getattr(self, "_total_duration_ms", None)
        if isinstance(total, (int, float)) and total > 0:
            return int(total)
        return self.duration_ms

    # ------------------------------------------------------------------
    # BaseTransition API
    # ------------------------------------------------------------------

    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, widget: QWidget) -> bool:  # type: ignore[override]
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid pixmap for GL compositor Block Puzzle Flip")
            self.error.emit("Invalid image")
            return False

        self._widget = widget

        # If there's no old image, just complete immediately.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("No old image, showing new image immediately (GL compositor block flip)")
            self._show_image_immediately()
            return True

        # Resolve compositor from widget; fall back to immediate display if absent.
        comp = getattr(widget, "_gl_compositor", None)
        if comp is None or not isinstance(comp, GLCompositorWidget):
            logger.warning(
                "[GL COMPOSITOR] No compositor attached to widget; falling back to immediate display (block flip)"
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
            logger.debug("[GL COMPOSITOR] Failed to warm blockflip textures", exc_info=True)

        # Ensure compositor matches widget geometry and is above the base.
        try:
            comp.setGeometry(0, 0, widget.width(), widget.height())
            comp.show()
            comp.raise_()
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to configure compositor geometry/visibility (block flip)", exc_info=True)

        # Build the effective shader grid matching the widget geometry.
        width = widget.width()
        height = widget.height()
        self._create_shader_grid(width, height)

        # Drive via shared AnimationManager.
        easing_curve = EasingCurve.LINEAR
        am = self._get_animation_manager(widget)

        def _update(progress: float) -> None:
            self._on_anim_update(progress)

        def _on_finished() -> None:
            self._on_anim_complete()

        self._animation_id = comp.start_block_flip(
            old_pixmap,
            new_pixmap,
            duration_ms=self._total_duration_ms,
            easing=easing_curve,
            animation_manager=am,
            update_callback=_update,
            on_finished=_on_finished,
            grid_cols=self._shader_cols or 0,
            grid_rows=self._shader_rows or 0,
            direction=self._direction,
            on_started=self._mark_compositor_actual_start,
        )

        self._set_state(TransitionState.RUNNING)
        self.started.emit()
        logger.info(
            "GLCompositorBlockFlipTransition started (%dms, grid=%dx%d)",
            self.duration_ms,
            self._grid_cols,
            self._grid_rows,
        )
        return True

    def stop(self) -> None:  # type: ignore[override]
        if self._state != TransitionState.RUNNING:
            return

        logger.debug("Stopping GLCompositorBlockFlipTransition")

        if self._compositor is not None:
            try:
                # Snap to final frame when cancelling mid-way to avoid pops.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cancel current block flip transition", exc_info=True)

        self._animation_id = None
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()

    def cleanup(self) -> None:  # type: ignore[override]
        logger.debug("Cleaning up GLCompositorBlockFlipTransition")

        if self._compositor is not None:
            try:
                # Ensure compositor is no longer animating; do not force snap
                # here, as DisplayWidget will already have updated its base.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cleanup block flip compositor", exc_info=True)
            self._compositor = None

        self._widget = None
        self._animation_id = None

        if self._state not in (TransitionState.FINISHED, TransitionState.CANCELLED):
            self._set_state(TransitionState.IDLE)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _create_shader_grid(self, width: int, height: int) -> None:
        """Compute the aspect-aware shader grid for the compositor path."""
        base_cols = self._grid_cols * 2
        aspect_ratio = height / max(1, width)
        calculated_rows = max(2, int(round(base_cols * aspect_ratio)))

        effective_rows = calculated_rows
        effective_cols = base_cols

        # Expose the effective grid to the compositor/GLSL path so
        # GLCompositorWidget can mirror this layout in its BlockFlip shader.
        self._shader_cols = effective_cols
        self._shader_rows = effective_rows

        logger.debug(
            "[GL COMPOSITOR BLOCK] Grid: %dx%d (aspect=%.2f, square blocks)",
            effective_cols,
            effective_rows,
            aspect_ratio,
        )

    def _on_anim_update(self, progress: float) -> None:
        if self._state != TransitionState.RUNNING or self._compositor is None:
            return

        p = max(0.0, min(1.0, float(progress)))
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
        logger.debug("GLCompositorBlockFlipTransition finished")

