"""GL compositor-driven Shuffle transition.

Blocks of the new image slide in from a chosen/random edge while the old image
remains visible elsewhere. The effect is implemented using the compositor's
Diffuse API: this controller computes a moving reveal region composed of
rectangular blocks and sends it to GLCompositorWidget.
"""
from __future__ import annotations

import random
from typing import Optional, List

from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap, QRegion
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.animation.types import EasingCurve

from transitions.base_transition import BaseTransition, TransitionState
from rendering.gl_compositor import GLCompositorWidget


logger = get_logger(__name__)


class _ShuffleBlock:
    def __init__(self, rect: QRect, threshold: float) -> None:
        self.rect = rect
        self.threshold = max(0.0, min(1.0, float(threshold)))


class GLCompositorShuffleTransition(BaseTransition):
    """GPU-backed Shuffle that targets the shared GL compositor widget.

    The controller owns only timing, grid layout and diffuse region updates;
    all drawing is delegated to GLCompositorWidget via its diffuse API.
    """

    def __init__(
        self,
        duration_ms: int = 1400,
        block_size: int = 80,
        direction: str = "Random",
        easing: str = "Auto",
    ) -> None:
        super().__init__(duration_ms)
        self._widget: Optional[QWidget] = None
        self._compositor: Optional[GLCompositorWidget] = None
        self._animation_id: Optional[str] = None
        self._block_size: int = max(8, int(block_size))
        self._easing_str: str = easing
        self._direction_str: str = direction
        self._blocks: List[_ShuffleBlock] = []
        self._region: QRegion = QRegion()
        self._edge: str = "L2R"  # Encoded edge: L2R, R2L, T2B, B2T
        self._width: int = 0
        self._height: int = 0

    # ------------------------------------------------------------------
    # BaseTransition API
    # ------------------------------------------------------------------

    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, widget: QWidget) -> bool:  # type: ignore[override]
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid pixmap for GL compositor Shuffle")
            self.error.emit("Invalid image")
            return False

        self._widget = widget

        # Begin telemetry tracking
        self._mark_start()

        # If there's no old image, just complete immediately.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("No old image, showing new image immediately (GL compositor shuffle)")
            self._show_image_immediately()
            return True

        # Resolve compositor from widget; fall back to immediate display if absent.
        comp = getattr(widget, "_gl_compositor", None)
        if comp is None or not isinstance(comp, GLCompositorWidget):
            logger.warning(
                "[GL COMPOSITOR] No compositor attached to widget; falling back to immediate display (shuffle)"
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
                "[GL COMPOSITOR] Failed to configure compositor geometry/visibility (shuffle)",
                exc_info=True,
            )

        width = max(1, widget.width())
        height = max(1, widget.height())
        self._width = width
        self._height = height
        self._build_blocks(width, height)

        # Drive via shared AnimationManager using the diffuse API.
        easing_curve = self._resolve_easing()
        am = self._get_animation_manager(widget)

        def _update(progress: float) -> None:
            self._on_anim_update(progress)

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
            "GLCompositorShuffleTransition started (%dms, blocks=%d, dir=%s)",
            self.duration_ms,
            len(self._blocks),
            self._edge,
        )
        return True

    def stop(self) -> None:  # type: ignore[override]
        if self._state != TransitionState.RUNNING:
            return

        logger.debug("Stopping GLCompositorShuffleTransition")

        if self._compositor is not None:
            try:
                # Snap to final frame when cancelling mid-way to avoid pops.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cancel current shuffle transition", exc_info=True)

        self._animation_id = None
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()

    def cleanup(self) -> None:  # type: ignore[override]
        logger.debug("Cleaning up GLCompositorShuffleTransition")

        if self._compositor is not None:
            try:
                # Ensure compositor is no longer animating; do not force snap
                # here, as DisplayWidget will already have updated its base.
                self._compositor.cancel_current_transition(snap_to_new=False)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cleanup shuffle compositor", exc_info=True)
            self._compositor = None

        self._widget = None
        self._animation_id = None
        self._blocks = []
        self._region = QRegion()

        if self._state not in (TransitionState.FINISHED, TransitionState.CANCELLED):
            self._set_state(TransitionState.IDLE)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_blocks(self, width: int, height: int) -> None:
        """Create a grid of shuffle blocks covering the widget area."""

        self._blocks = []
        # Clamp effective block size for performance while preserving user intent.
        bs = max(32, min(self._block_size, min(width, height)))

        cols = max(1, (width + bs - 1) // bs)
        rows = max(1, (height + bs - 1) // bs)

        for r in range(rows):
            for c in range(cols):
                x = c * bs
                y = r * bs
                w = bs if c < cols - 1 else (width - x)
                h = bs if r < rows - 1 else (height - y)
                rect = QRect(x, y, w, h)
                threshold = random.random()
                self._blocks.append(_ShuffleBlock(rect, threshold))

        # Shuffle order so neighbouring blocks don't share identical timing.
        random.shuffle(self._blocks)

        # Resolve entry edge for this transition.
        name = (self._direction_str or "Random").strip()
        if name == "Left to Right":
            edge = "L2R"
        elif name == "Right to Left":
            edge = "R2L"
        elif name == "Top to Bottom":
            edge = "T2B"
        elif name == "Bottom to Top":
            edge = "B2T"
        else:
            edge = random.choice(["L2R", "R2L", "T2B", "B2T"])
        self._edge = edge

    def _on_anim_update(self, progress: float) -> None:
        if self._state != TransitionState.RUNNING or self._compositor is None:
            return

        p = max(0.0, min(1.0, float(progress)))

        region = QRegion()
        finished = 0
        width = max(1, self._width)
        height = max(1, self._height)

        for block in self._blocks:
            # Spread start times so multiple blocks move at once but avoid
            # uniform row/column activation.
            start = block.threshold * 0.7
            if p <= start:
                continue
            local = (p - start) / max(0.0001, 1.0 - start)
            if local >= 1.0:
                local = 1.0
                finished += 1
                rect = block.rect
                region = region.united(QRegion(rect))
                continue
            local = max(0.0, min(1.0, local))

            rect = self._compute_block_rect(block.rect, local, width, height)
            if rect.width() <= 0 or rect.height() <= 0:
                continue
            region = region.united(QRegion(rect))

        self._region = region

        if not region.isEmpty():
            try:
                self._compositor.set_diffuse_region(region)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to update shuffle region", exc_info=True)

        total = len(self._blocks) or 1
        frac_finished = finished / float(total)
        self._emit_progress(max(p, frac_finished))

        if p >= 1.0 and finished >= total:
            self._on_anim_complete()

    def _compute_block_rect(self, target: QRect, local: float, width: int, height: int) -> QRect:
        """Compute the current reveal rect for a single block.

        The rect extends from the entry edge towards the target block; over
        time it grows until the entire block area is revealed.
        """

        if self._edge == "L2R":
            start_x = -target.width()
            end_x = target.x() + target.width()
            head = start_x + (end_x - start_x) * local
            x1 = int(min(start_x, head))
            x2 = int(max(start_x, head))
            return QRect(x1, target.y(), x2 - x1, target.height())
        if self._edge == "R2L":
            start_x = width + target.width()
            end_x = target.x() - target.width()
            head = start_x + (end_x - start_x) * local
            x1 = int(min(start_x, head))
            x2 = int(max(start_x, head))
            return QRect(x1, target.y(), x2 - x1, target.height())
        if self._edge == "T2B":
            start_y = -target.height()
            end_y = target.y() + target.height()
            head = start_y + (end_y - start_y) * local
            y1 = int(min(start_y, head))
            y2 = int(max(start_y, head))
            return QRect(target.x(), y1, target.width(), y2 - y1)
        # B2T
        start_y = height + target.height()
        end_y = target.y() - target.height()
        head = start_y + (end_y - start_y) * local
        y1 = int(min(start_y, head))
        y2 = int(max(start_y, head))
        return QRect(target.x(), y1, target.width(), y2 - y1)

    def _on_anim_complete(self) -> None:
        if self._state != TransitionState.RUNNING:
            return

        # Telemetry end
        self._mark_end()

        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("GLCompositorShuffleTransition finished")

    def _show_image_immediately(self) -> None:
        """Immediate completion when no GL compositor path is available."""
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()

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
