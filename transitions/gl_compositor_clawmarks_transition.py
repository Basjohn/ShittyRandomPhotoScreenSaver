"""GL compositor-driven Claw Marks transition.

This transition uses the GLCompositorWidget's diffuse API to reveal the new
image through a small set of diagonal, scratch-like "claw" bands. Each claw
starts at the frame edge and grows over time, carving through the old image to
expose the new one underneath.
"""
from __future__ import annotations

import math
import random
from typing import Optional, List

from PySide6.QtCore import QPoint
from PySide6.QtGui import QPixmap, QRegion, QPolygon
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.animation.types import EasingCurve

from transitions.base_transition import BaseTransition, TransitionState
from rendering.gl_compositor import GLCompositorWidget


logger = get_logger(__name__)


class _Claw:
    def __init__(self, start: QPoint, end: QPoint, thickness: int, threshold: float) -> None:
        self.start = start
        self.end = end
        self.thickness = max(1, int(thickness))
        # Normalized time at which this claw begins to grow (0..1).
        self.threshold = max(0.0, min(1.0, float(threshold)))


class GLCompositorClawMarksTransition(BaseTransition):
    """GPU-backed Claw Marks targeting the shared GL compositor widget.

    The controller builds a handful of diagonal claw strokes that extend over
    time. Rendering is handled entirely by GLCompositorWidget via its diffuse
    API; this class only owns timing and QRegion construction.
    """

    def __init__(self, duration_ms: int = 1400, easing: str = "Auto") -> None:
        super().__init__(duration_ms)
        self._widget: Optional[QWidget] = None
        self._compositor: Optional[GLCompositorWidget] = None
        self._animation_id: Optional[str] = None
        self._easing_str: str = easing
        self._claws: List[_Claw] = []
        self._region: QRegion = QRegion()

    # ------------------------------------------------------------------
    # BaseTransition API
    # ------------------------------------------------------------------

    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, widget: QWidget) -> bool:  # type: ignore[override]
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid pixmap for GL compositor Claw Marks")
            self.error.emit("Invalid image")
            return False

        self._widget = widget

        # Begin telemetry tracking
        self._mark_start()

        # If there's no old image, just complete immediately.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("No old image, showing new image immediately (GL compositor claw marks)")
            self._show_image_immediately()
            return True

        # Resolve compositor from widget; fall back to immediate display if absent.
        comp = getattr(widget, "_gl_compositor", None)
        if comp is None or not isinstance(comp, GLCompositorWidget):
            logger.warning(
                "[GL COMPOSITOR] No compositor attached to widget; falling back to immediate display (claw marks)"
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
                "[GL COMPOSITOR] Failed to configure compositor geometry/visibility (claw marks)",
                exc_info=True,
            )

        width = max(1, widget.width())
        height = max(1, widget.height())
        self._build_claws(width, height)

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
            "GLCompositorClawMarksTransition started (%dms, claws=%d)",
            self.duration_ms,
            len(self._claws),
        )
        return True

    def stop(self) -> None:  # type: ignore[override]
        if self._state != TransitionState.RUNNING:
            return

        logger.debug("Stopping GLCompositorClawMarksTransition")

        if self._compositor is not None:
            try:
                # Snap to final frame when cancelling mid-way to avoid pops.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cancel current claw marks transition", exc_info=True)

        self._animation_id = None
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()

    def cleanup(self) -> None:  # type: ignore[override]
        logger.debug("Cleaning up GLCompositorClawMarksTransition")

        if self._compositor is not None:
            try:
                # Ensure compositor is no longer animating; do not force snap
                # here, as DisplayWidget will already have updated its base.
                self._compositor.cancel_current_transition(snap_to_new=False)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cleanup claw marks compositor", exc_info=True)
            self._compositor = None

        self._widget = None
        self._animation_id = None
        self._claws = []
        self._region = QRegion()

        if self._state not in (TransitionState.FINISHED, TransitionState.CANCELLED):
            self._set_state(TransitionState.IDLE)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_claws(self, width: int, height: int) -> None:
        """Create a small set of diagonal claw strokes across the frame.

        Claws are roughly parallel, angled slashes that start near one edge and
        sweep across the image. We keep the count low to avoid excessive region
        complexity while still feeling dynamic.
        """

        self._claws = []

        # Choose 3–5 claws depending on resolution.
        base_count = 3
        extra = 1 if max(width, height) > 1600 else 0
        count = base_count + extra

        # Randomly decide primary sweep direction: TL->BR or TR->BL.
        diag_left_to_right = random.choice([True, False])

        margin = max(0.04 * min(width, height), 8.0)
        length = math.hypot(width, height) * 1.2  # extend slightly beyond frame

        for i in range(count):
            # Spread starting positions along the top/bottom edges.
            t = (i + 0.5) / float(count)
            jitter = (random.random() - 0.5) * 0.25
            t = max(0.05, min(0.95, t + jitter))

            if diag_left_to_right:
                # From left edge towards bottom-right.
                x0 = -margin
                y0 = int(t * height)
                angle = math.atan2(height, width)
            else:
                # From right edge towards bottom-left.
                x0 = width + margin
                y0 = int(t * height)
                angle = math.atan2(height, -width)

            dx = math.cos(angle) * length
            dy = math.sin(angle) * length

            x1 = int(x0 + dx)
            y1 = int(y0 + dy)

            start = QPoint(int(x0), int(y0))
            end = QPoint(x1, y1)

            # Thickness scales with resolution but stays fairly slim.
            base_thickness = max(6.0, min(width, height) / 90.0)
            thickness = int(base_thickness * random.uniform(0.8, 1.3))

            threshold = random.uniform(0.0, 0.4)
            self._claws.append(_Claw(start, end, thickness, threshold))

    def _on_anim_update(self, progress: float) -> None:
        if self._state != TransitionState.RUNNING or self._compositor is None:
            return

        p = max(0.0, min(1.0, float(progress)))

        region = QRegion()
        finished = 0
        for claw in self._claws:
            local = (p - claw.threshold) / 0.75
            if local <= 0.0:
                continue
            if local >= 1.0:
                local = 1.0
                finished += 1

            # Interpolate current end point along the claw path.
            sx, sy = claw.start.x(), claw.start.y()
            ex, ey = claw.end.x(), claw.end.y()
            cx = sx + (ex - sx) * local
            cy = sy + (ey - sy) * local

            # Build a thin quad around the [start -> current] segment.
            dx = cx - sx
            dy = cy - sy
            length = math.hypot(dx, dy)
            if length <= 0.0:
                continue
            nx = -dy / length
            ny = dx / length
            half_t = claw.thickness / 2.0

            p1 = QPoint(int(sx + nx * half_t), int(sy + ny * half_t))
            p2 = QPoint(int(sx - nx * half_t), int(sy - ny * half_t))
            p3 = QPoint(int(cx - nx * half_t), int(cy - ny * half_t))
            p4 = QPoint(int(cx + nx * half_t), int(cy + ny * half_t))

            poly = QPolygon([p1, p2, p3, p4])
            region = region.united(QRegion(poly))

        self._region = region

        if not region.isEmpty():
            try:
                self._compositor.set_diffuse_region(region)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to update claw marks region", exc_info=True)

        total = len(self._claws) or 1
        frac_finished = finished / float(total)
        self._emit_progress(max(p, frac_finished))

        if p >= 1.0 and finished >= total:
            self._on_anim_complete()

    def _on_anim_complete(self) -> None:
        if self._state != TransitionState.RUNNING:
            return

        # Telemetry end
        self._mark_end()

        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("GLCompositorClawMarksTransition finished")

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
