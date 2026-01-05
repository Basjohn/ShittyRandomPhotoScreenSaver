"""GL compositor-driven Rain Drops transition.

This transition delegates all rendering to the shared GLCompositorWidget. It
uses the compositor's diffuse region API to reveal the new image through a
field of expanding, raindrop-like circular regions.
"""
from __future__ import annotations

import random
from typing import Optional, List

from PySide6.QtCore import QRect, QRectF, QPoint
from PySide6.QtGui import QPixmap, QRegion, QPainterPath
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.animation.types import EasingCurve

from transitions.base_transition import BaseTransition, TransitionState
from rendering.gl_compositor import GLCompositorWidget


logger = get_logger(__name__)


class _RainDrop:
    def __init__(self, center: QPoint, radius: int, threshold: float) -> None:
        self.center = center
        self.radius = max(1, int(radius))
        # Normalized time at which this drop begins to expand (0..1).
        self.threshold = max(0.0, min(1.0, float(threshold)))


class GLCompositorRainDropsTransition(BaseTransition):
    """GPU-backed Rain Drops targeting the shared GL compositor widget.

    The controller builds a sparse field of circular droplets that expand over
    time. Rendering is handled entirely by GLCompositorWidget via its diffuse
    API; this class only owns timing and region construction.
    """

    def __init__(
        self,
        duration_ms: int = 1400,
        easing: str = "Auto",
    ) -> None:
        super().__init__(duration_ms)
        self._widget: Optional[QWidget] = None
        self._compositor: Optional[GLCompositorWidget] = None
        self._animation_id: Optional[str] = None
        self._easing_str: str = easing
        self._drops: List[_RainDrop] = []
        self._region: QRegion = QRegion()

    # ------------------------------------------------------------------
    # BaseTransition API
    # ------------------------------------------------------------------

    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, widget: QWidget) -> bool:  # type: ignore[override]
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid pixmap for GL compositor Rain Drops")
            self.error.emit("Invalid image")
            return False

        self._widget = widget

        # Begin telemetry tracking
        self._mark_start()

        # If there's no old image, just complete immediately.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("No old image, showing new image immediately (GL compositor rain drops)")
            self._show_image_immediately()
            return True

        # Resolve compositor from widget; fall back to immediate display if absent.
        comp = getattr(widget, "_gl_compositor", None)
        if comp is None or not isinstance(comp, GLCompositorWidget):
            logger.warning(
                "[GL COMPOSITOR] No compositor attached to widget; falling back to immediate display (rain drops)"
            )
            self._show_image_immediately()
            return True

        self._compositor = comp

        # Ensure compositor matches widget geometry and is above the base.
        try:
            comp.setGeometry(0, 0, widget.width(), widget.height())
            comp.show()
            comp.raise_()
        except Exception as e:
            logger.debug(
                "[GL COMPOSITOR] Failed to configure compositor geometry/visibility (rain drops)",
                exc_info=True,
            )
        # Prewarm shader textures for this pixmap pair so the first
        # Raindrops frame does not pay the full texture upload cost.
        try:
            warm = getattr(comp, "warm_shader_textures", None)
            if callable(warm):
                warm(old_pixmap, new_pixmap)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Failed to warm raindrops textures", exc_info=True)

        # Drive via shared AnimationManager. Try the shader-based raindrops
        # path first; if it is unavailable or fails to start, fall back to the
        # existing diffuse-region implementation.
        easing_curve = self._resolve_easing()
        am = self._get_animation_manager(widget)

        def _on_finished_shader() -> None:
            self._on_anim_complete()

        shader_anim_id: Optional[str] = None
        try:
            shader_anim_id = comp.start_raindrops(
                old_pixmap,
                new_pixmap,
                duration_ms=self.duration_ms,
                easing=easing_curve,
                animation_manager=am,
                on_finished=_on_finished_shader,
            )
        except Exception as e:
            logger.debug(
                "[GL COMPOSITOR] Failed to start shader-based rain drops; falling back to diffuse region API",
                exc_info=True,
            )

        if shader_anim_id:
            self._animation_id = shader_anim_id
            self._set_state(TransitionState.RUNNING)
            self.started.emit()
            logger.info(
                "GLCompositorRainDropsTransition started (shader, %dms)",
                self.duration_ms,
            )
            return True

        # Fallback: build raindrop regions and drive the diffuse API as
        # before.
        width = max(1, widget.width())
        height = max(1, widget.height())
        self._build_drops(width, height)

        def _update(progress: float) -> None:
            self._on_anim_update(progress)

        def _on_finished_diffuse() -> None:
            self._on_anim_complete()

        self._animation_id = comp.start_diffuse(
            old_pixmap,
            new_pixmap,
            duration_ms=self.duration_ms,
            easing=easing_curve,
            animation_manager=am,
            update_callback=_update,
            on_finished=_on_finished_diffuse,
        )

        self._set_state(TransitionState.RUNNING)
        self.started.emit()
        logger.info(
            "GLCompositorRainDropsTransition started (diffuse, %dms, drops=%d)",
            self.duration_ms,
            len(self._drops),
        )
        return True

    def stop(self) -> None:  # type: ignore[override]
        if self._state != TransitionState.RUNNING:
            return

        logger.debug("Stopping GLCompositorRainDropsTransition")

        if self._compositor is not None:
            try:
                # Snap to final frame when cancelling mid-way to avoid pops.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Failed to cancel current rain drops transition", exc_info=True)

        self._animation_id = None
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()

    def cleanup(self) -> None:  # type: ignore[override]
        logger.debug("Cleaning up GLCompositorRainDropsTransition")

        if self._compositor is not None:
            try:
                # Ensure compositor is no longer animating; do not force snap
                # here, as DisplayWidget will already have updated its base.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Failed to cleanup rain drops compositor", exc_info=True)
            self._compositor = None

        self._widget = None
        self._animation_id = None
        self._drops = []
        self._region = QRegion()

        if self._state not in (TransitionState.FINISHED, TransitionState.CANCELLED):
            self._set_state(TransitionState.IDLE)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_drops(self, width: int, height: int) -> None:
        """Create a field of raindrop centres across the frame.

        Drops are distributed pseudo-randomly but with a gentle stratified
        pattern so the coverage feels even without clumping.
        """

        self._drops = []
        area = float(width * height)
        # Target drop count scales with resolution but is clamped to avoid
        # excessive region complexity. Values tuned for typical 1080p–4K.
        target = int(max(32, min(120, area / 160000.0)))

        # Base radius scales with the shorter dimension for a photo-friendly
        # droplet size (not too tiny, not dominating the frame).
        base_radius = max(8, min(width, height) // 24)

        cols = int(max(4, (target ** 0.5)))
        rows = int(max(3, target / max(1.0, cols)))
        cell_w = width / float(cols)
        cell_h = height / float(rows)

        for r in range(rows):
            for c in range(cols):
                if len(self._drops) >= target:
                    break
                # Jitter the centre within the cell for a natural layout.
                cx = int((c + 0.5 + (random.random() - 0.5) * 0.6) * cell_w)
                cy = int((r + 0.5 + (random.random() - 0.5) * 0.6) * cell_h)
                cx = max(0, min(width - 1, cx))
                cy = max(0, min(height - 1, cy))
                radius = int(base_radius * random.uniform(0.7, 1.3))
                # Early/late thresholds so some drops start sooner and some lag.
                threshold = random.uniform(0.0, 0.7)
                self._drops.append(_RainDrop(QPoint(cx, cy), radius, threshold))

    def _on_anim_update(self, progress: float) -> None:
        if self._state != TransitionState.RUNNING or self._compositor is None:
            return

        p = max(0.0, min(1.0, float(progress)))

        region = QRegion()
        finished = 0
        for drop in self._drops:
            # Local time for this drop once its threshold has been reached.
            local = (p - drop.threshold) / 0.75
            if local <= 0.0:
                continue
            if local >= 1.0:
                local = 1.0
                finished += 1
            # Expand radius over time; clamp to full radius.
            cur_radius = int(drop.radius * local)
            if cur_radius <= 1:
                continue
            rect = QRect(
                drop.center.x() - cur_radius,
                drop.center.y() - cur_radius,
                cur_radius * 2,
                cur_radius * 2,
            )
            path = QPainterPath()
            path.addEllipse(QRectF(rect))
            region = region.united(QRegion(path.toFillPolygon().toPolygon()))

        self._region = region

        if not region.isEmpty():
            try:
                self._compositor.set_diffuse_region(region)
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Failed to update rain drops region", exc_info=True)

        total = len(self._drops) or 1
        # Progress is based on the fraction of droplets that have fully
        # expanded, blended with the global timeline to avoid stalling.
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
        logger.debug("GLCompositorRainDropsTransition finished")

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
