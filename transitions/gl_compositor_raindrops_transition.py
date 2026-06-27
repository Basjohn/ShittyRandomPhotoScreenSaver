"""GL compositor-driven Rain Drops transition.

This transition delegates all rendering to the shared GLCompositorWidget
raindrops shader. If the shader path cannot start, the transition fails loudly
instead of substituting a different legacy reveal shape.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.animation.types import EasingCurve, resolve_easing

from transitions.base_transition import BaseTransition, TransitionState
from rendering.gl_compositor import GLCompositorWidget


logger = get_logger(__name__)


class GLCompositorRainDropsTransition(BaseTransition):
    """GPU-backed Rain Drops targeting the shared GL compositor widget.

    Rendering is handled entirely by GLCompositorWidget via its shader path.
    This class must not report a legacy substitute as a successful Rain Drops
    transition.
    """

    def __init__(
        self,
        duration_ms: int = 1400,
        easing: str = "Auto",
        ripple_count: int = 3,
    ) -> None:
        super().__init__(duration_ms)
        self._uses_deferred_start_telemetry = True
        self._widget: Optional[QWidget] = None
        self._compositor: Optional[GLCompositorWidget] = None
        self._animation_id: Optional[str] = None
        self._easing_str: str = easing
        self._ripple_count: int = max(1, min(8, int(ripple_count)))

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

        # If there's no old image, just complete immediately.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("No old image, showing new image immediately (GL compositor rain drops)")
            self._show_image_immediately()
            return True

        # Resolve compositor from widget. Rain Drops is shader-owned, so a
        # missing compositor is a refused transition rather than a fake success.
        comp = getattr(widget, "_gl_compositor", None)
        if comp is None or not isinstance(comp, GLCompositorWidget):
            logger.error(
                "[GL COMPOSITOR][ERROR] No compositor attached; Rain Drops transition refused"
            )
            return False

        self._compositor = comp

        # Ensure compositor matches widget geometry and is above the base.
        try:
            comp.setGeometry(0, 0, widget.width(), widget.height())
            comp.show()
            comp.raise_()
        except Exception:
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
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to warm raindrops textures", exc_info=True)

        # Drive via shared AnimationManager. Rain Drops is shader-owned: if
        # this path is unavailable, fail loudly rather than hiding the problem
        # behind a different transition.
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
                ripple_count=self._ripple_count,
                on_started=self._mark_compositor_actual_start,
            )
        except Exception:
            logger.error(
                "[GL COMPOSITOR][ERROR] Rain Drops shader start raised; refusing legacy substitute",
                exc_info=True,
            )
            return False

        if shader_anim_id:
            self._animation_id = shader_anim_id
            self._set_state(TransitionState.RUNNING)
            self.started.emit()
            logger.info(
                "GLCompositorRainDropsTransition started (shader, %dms)",
                self.duration_ms,
            )
            return True

        logger.error(
            "[GL COMPOSITOR][ERROR] Rain Drops shader unavailable; transition refused instead of using diffuse substitute"
        )
        return False

    def stop(self) -> None:  # type: ignore[override]
        if self._state != TransitionState.RUNNING:
            return

        logger.debug("Stopping GLCompositorRainDropsTransition")

        if self._compositor is not None:
            try:
                # Snap to final frame when cancelling mid-way to avoid pops.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
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
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cleanup rain drops compositor", exc_info=True)
            self._compositor = None

        self._widget = None
        self._animation_id = None

        if self._state not in (TransitionState.FINISHED, TransitionState.CANCELLED):
            self._set_state(TransitionState.IDLE)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_anim_complete(self) -> None:
        if self._state != TransitionState.RUNNING:
            return

        # Telemetry end
        self._mark_end()

        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("GLCompositorRainDropsTransition finished")

    def _resolve_easing(self) -> EasingCurve:
        return resolve_easing(self._easing_str)
