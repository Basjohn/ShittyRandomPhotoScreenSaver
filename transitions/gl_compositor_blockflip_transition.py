"""GL compositor-driven Block Puzzle Flip transition.

This transition delegates all rendering to the shared GLCompositorWidget. It
owns only timing and per-block progression state and drives the compositor via
its block-flip API (set_blockflip_region / start_block_flip).
"""
from __future__ import annotations

import random
import math
from typing import Optional, List

from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap, QRegion
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.animation.types import EasingCurve

from transitions.base_transition import BaseTransition, TransitionState
from transitions.slide_transition import SlideDirection
from rendering.gl_compositor import GLCompositorWidget


logger = get_logger(__name__)


class _CompositorFlipBlock:
    def __init__(self, rect: QRect) -> None:
        self.rect = rect
        self.flip_progress: float = 0.0
        self.started: bool = False
        self.is_complete: bool = False
        self.start_threshold: float = random.random()


class GLCompositorBlockFlipTransition(BaseTransition):
    """GPU-backed Block Puzzle Flip that targets the shared GL compositor.

    The controller mirrors the timing and grid behaviour of the existing GL
    BlockPuzzleFlipTransition, but instead of maintaining its own QOpenGLWidget
    overlay it computes an aggregate QRegion for all in-progress blocks and
    passes that to GLCompositorWidget.
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
        self._grid_rows = grid_rows
        self._grid_cols = grid_cols
        self._flip_duration_ms = flip_duration_ms
        self._widget: Optional[QWidget] = None
        self._compositor: Optional[GLCompositorWidget] = None
        self._blocks: List[_CompositorFlipBlock] = []
        self._animation_id: Optional[str] = None
        self._total_duration_ms: int = max(1, int(duration_ms + flip_duration_ms))
        self._total_dur_sec: float = max(0.001, self._total_duration_ms / 1000.0)
        self._last_progress: float = 0.0
        # Optional direction bias so the compositor-backed Block Puzzle Flip
        # follows the same edge-originated wave model as the CPU variant.
        self._direction: Optional[SlideDirection] = direction

    def get_expected_duration_ms(self) -> int:
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

        # Begin telemetry tracking
        self._mark_start()

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

        # Ensure compositor matches widget geometry and is above the base.
        try:
            comp.setGeometry(0, 0, widget.width(), widget.height())
            comp.show()
            comp.raise_()
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to configure compositor geometry/visibility (block flip)", exc_info=True)

        # Build block grid matching the widget geometry.
        width = widget.width()
        height = widget.height()
        self._create_block_grid(width, height)

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
                self._compositor.cancel_current_transition(snap_to_new=False)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cleanup block flip compositor", exc_info=True)
            self._compositor = None

        self._widget = None
        self._animation_id = None
        self._blocks = []

        if self._state not in (TransitionState.FINISHED, TransitionState.CANCELLED):
            self._set_state(TransitionState.IDLE)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _create_block_grid(self, width: int, height: int) -> None:
        """Create a grid of square-ish blocks covering the widget area.

        Mirrors the grid layout of the existing GLBlockPuzzleFlipTransition so
        visuals remain consistent while the rendering path moves to the
        compositor.
        """
        self._blocks = []

        base_cols = self._grid_cols * 2
        aspect_ratio = height / max(1, width)
        calculated_rows = max(2, int(round(base_cols * aspect_ratio)))

        effective_rows = calculated_rows
        effective_cols = base_cols

        logger.debug(
            "[GL COMPOSITOR BLOCK] Grid: %dx%d (aspect=%.2f, square blocks)",
            effective_cols,
            effective_rows,
            aspect_ratio,
        )

        block_width = max(1, width // effective_cols)
        block_height = max(1, height // effective_rows)

        for row in range(effective_rows):
            for col in range(effective_cols):
                x = col * block_width
                y = row * block_height
                w = block_width if col < effective_cols - 1 else (width - x)
                h = block_height if row < effective_rows - 1 else (height - y)

                block = _CompositorFlipBlock(QRect(x, y, w, h))

                # Apply the same optional direction bias as the CPU
                # BlockPuzzleFlipTransition: encode an edge-originated wave in
                # start_threshold while preserving a small amount of jitter so
                # the motion does not look too mechanical.
                if self._direction is not None:
                    base = 0.0
                    # Horizontal bias (Left/Right)
                    if self._direction == SlideDirection.LEFT:
                        # "Left to Right" – start at the left edge.
                        if effective_cols > 1:
                            base = col / float(effective_cols - 1)
                    elif self._direction == SlideDirection.RIGHT:
                        # "Right to Left" – start at the right edge.
                        if effective_cols > 1:
                            base = (effective_cols - 1 - col) / float(effective_cols - 1)
                    # Vertical bias (Top/Bottom)
                    elif self._direction == SlideDirection.DOWN:
                        # "Top to Bottom" – start at the top edge.
                        if effective_rows > 1:
                            base = row / float(effective_rows - 1)
                    elif self._direction == SlideDirection.UP:
                        # "Bottom to Top" – start at the bottom edge.
                        if effective_rows > 1:
                            base = (effective_rows - 1 - row) / float(effective_rows - 1)

                    span = max(effective_cols, effective_rows)
                    jitter_span = 0.0
                    if span > 0:
                        jitter_span = 0.35 / float(span)
                    if jitter_span > 0.0:
                        base += random.uniform(-jitter_span, jitter_span)
                    if base < 0.0:
                        base = 0.0
                    elif base > 1.0:
                        base = 1.0
                    block.start_threshold = base

                self._blocks.append(block)

    def _on_anim_update(self, progress: float) -> None:
        if self._state != TransitionState.RUNNING or self._compositor is None:
            return

        p = max(0.0, min(1.0, float(progress)))
        total_ms = max(1, self._total_duration_ms)
        t_ms = p * total_ms
        start_phase_progress = min(1.0, t_ms / max(1, self.duration_ms))

        for block in self._blocks:
            if not block.started and start_phase_progress >= block.start_threshold:
                block.started = True

        delta = p - self._last_progress
        self._last_progress = p
        if delta < 0:
            delta = 0.0

        delta_sec = delta * self._total_dur_sec
        flip_dur_sec = max(0.001, self._flip_duration_ms / 1000.0)
        inc = delta_sec / flip_dur_sec

        all_complete = True
        completed_count = 0
        for block in self._blocks:
            if block.started and not block.is_complete:
                block.flip_progress += inc
                if block.flip_progress >= 1.0:
                    block.flip_progress = 1.0
                    block.is_complete = True
            if not block.is_complete:
                all_complete = False
            else:
                completed_count += 1

        region = QRegion()
        for block in self._blocks:
            bp = max(0.0, min(1.0, block.flip_progress))
            if bp <= 0.0:
                continue
            # Match the CPU BlockPuzzleFlipTransition easing so the visual
            # reveal curve is consistent between compositor and QPainter
            # paths.
            eased = 0.5 - 0.5 * math.cos(math.pi * bp)
            r = block.rect
            reveal_w = max(1, int(r.width() * eased))
            dx = r.x() + (r.width() - reveal_w) // 2
            reveal_rect = QRect(dx, r.y(), reveal_w, r.height())
            region = region.united(QRegion(reveal_rect))

        try:
            self._compositor.set_blockflip_region(region)
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to update block flip region", exc_info=True)

        if self._blocks:
            self._emit_progress(0.5 + (completed_count / len(self._blocks)) * 0.5)

        if p >= 1.0 or all_complete:
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

    def _show_image_immediately(self) -> None:
        """Immediate completion when no GL compositor path is available."""
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("GLCompositorBlockFlipTransition showed image immediately")
