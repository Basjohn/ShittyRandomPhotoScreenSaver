"""GL compositor-driven Diffuse transition.

Replaces the legacy GLDiffuseTransition overlay path with a controller that
uses the shared GLCompositorWidget. The controller owns only timing, grid
layout, and region construction; all rendering is delegated to the compositor.
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
        # GLSL-backed diffuse supports Rectangle, Membrane, Lines, Diamonds,
        # and Amorph. Clamp unknown shapes to Rectangle.
        _VALID_SHAPES = ("Rectangle", "Membrane", "Lines", "Diamonds", "Amorph", "Random")
        if shape not in _VALID_SHAPES:
            shape = "Rectangle"
        self._shape = shape
        self._easing_str = easing
        self._widget: Optional[QWidget] = None
        self._compositor: Optional[GLCompositorWidget] = None
        self._cells: List[_DiffuseCell] = []
        self._animation_id: Optional[str] = None
        self._region: QRegion = QRegion()
        self._revealed_count: int = 0
        self._total_cells: int = 0
        self._grid_cols: int = 0
        self._grid_rows: int = 0

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

        # Prewarm shader textures for this pixmap pair so any GLSL-backed
        # diffuse path does not pay the full texture upload cost on its first
        # frame. Failures are logged and do not affect the fallback paths.
        try:
            warm = getattr(comp, "warm_shader_textures", None)
            if callable(warm):
                warm(old_pixmap, new_pixmap)
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to warm diffuse textures", exc_info=True)

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

        # Provide grid hints for all diffuse shapes so the compositor can opt
        # into the GLSL diffuse path when available. The region-based
        # implementation remains the authoritative fallback when shaders are
        # disabled or unavailable.
        grid_cols: Optional[int]
        grid_rows: Optional[int]
        grid_cols = self._grid_cols or 0
        grid_rows = self._grid_rows or 0

        self._animation_id = comp.start_diffuse(
            old_pixmap,
            new_pixmap,
            duration_ms=self.duration_ms,
            easing=easing_curve,
            animation_manager=am,
            update_callback=_update,
            on_finished=_on_finished,
            grid_cols=grid_cols,
            grid_rows=grid_rows,
            shape=self._shape,
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
                # Snap to new image so compositor's _base_pixmap matches the
                # final frame. Without this, the compositor may briefly show
                # the old image after transition state is cleared.
                self._compositor.cancel_current_transition(snap_to_new=True)
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
        """Compute grid dimensions for the GLSL shader.

        The GLSL shader handles all per-cell reveal logic in UV space, so we
        only need cols/rows — no QRegion accumulation required. This makes
        small block sizes (4–8px) viable without creating 100K+ QRect objects.
        """
        self._cells = []
        cols = max(1, (width + self._block_size - 1) // self._block_size)
        rows = max(1, (height + self._block_size - 1) // self._block_size)
        self._total_cells = cols * rows
        self._revealed_count = 0
        self._grid_cols = cols
        self._grid_rows = rows

    def _on_anim_update(self, progress: float, total: int) -> None:
        if self._state != TransitionState.RUNNING or self._compositor is None:
            return

        p = max(0.0, min(1.0, float(progress)))

        # The GLSL shader handles per-cell reveal entirely in UV space via
        # u_progress — no QRegion accumulation needed. Just emit progress.
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
