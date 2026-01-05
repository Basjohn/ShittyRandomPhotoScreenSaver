"""GL compositor-driven crossfade transition.

This transition does not create its own QOpenGLWidget overlay. Instead it
assumes the parent DisplayWidget owns a single GLCompositorWidget child and
uses it to render the crossfade. This reduces the number of GL surfaces and
stacking changes required during transitions.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.animation.types import EasingCurve

from transitions.base_transition import BaseTransition, TransitionState
from rendering.gl_compositor import GLCompositorWidget


logger = get_logger(__name__)


class GLCompositorCrossfadeTransition(BaseTransition):
    """GPU-backed crossfade that targets the shared GL compositor widget.

    This controller delegates all actual drawing to a single
    GLCompositorWidget attached to the DisplayWidget. It only owns timing,
    easing and telemetry state.
    """

    def __init__(self, duration_ms: int = 1000, easing: str = "Auto") -> None:
        super().__init__(duration_ms)
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
            logger.error("Invalid pixmap for GL compositor crossfade")
            self.error.emit("Invalid image")
            return False

        self._widget = widget

        # Begin telemetry tracking
        self._mark_start()

        # Resolve compositor from widget; fall back to immediate display if absent.
        comp = getattr(widget, "_gl_compositor", None)
        if comp is None or not isinstance(comp, GLCompositorWidget):
            logger.warning("[GL COMPOSITOR] No compositor attached to widget; falling back to immediate display")
            self._show_image_immediately()
            return True

        self._compositor = comp

        # Ensure compositor matches widget geometry and is above the base.
        try:
            comp.setGeometry(0, 0, widget.width(), widget.height())
            comp.show()
            comp.raise_()
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Failed to configure compositor geometry/visibility", exc_info=True)

        # Drive crossfade via shared AnimationManager.
        easing_curve = self._resolve_easing()
        am = self._get_animation_manager(widget)

        def _on_finished() -> None:
            # Called by compositor when its animation completes.
            self._on_anim_complete()

        self._animation_id = comp.start_crossfade(
            old_pixmap,
            new_pixmap,
            duration_ms=self.duration_ms,
            easing=easing_curve,
            animation_manager=am,
            on_finished=_on_finished,
        )

        self._set_state(TransitionState.RUNNING)
        self.started.emit()
        logger.info("GLCompositorCrossfadeTransition started (%dms)", self.duration_ms)
        return True

    def stop(self) -> None:  # type: ignore[override]
        if self._state != TransitionState.RUNNING:
            return

        logger.debug("Stopping GLCompositorCrossfadeTransition")

        if self._compositor is not None:
            try:
                # Snap to final frame when cancelling mid-way to avoid pops.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Failed to cancel current transition", exc_info=True)

        self._animation_id = None
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()

    def cleanup(self) -> None:  # type: ignore[override]
        logger.debug("Cleaning up GLCompositorCrossfadeTransition")

        if self._compositor is not None:
            try:
                # Ensure compositor is no longer animating; do not force snap
                # here, as DisplayWidget will already have updated its base.
                # The compositor remains visible as the primary renderer.
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Failed to cleanup compositor", exc_info=True)
            self._compositor = None

        self._widget = None
        self._animation_id = None

        if self._state not in (TransitionState.FINISHED, TransitionState.CANCELLED):
            self._set_state(TransitionState.IDLE)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_anim_complete(self) -> None:
        """Called when the compositor finishes its crossfade animation."""
        # End telemetry tracking
        self._mark_end()

        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("GLCompositorCrossfadeTransition finished")

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
            "InQuart": EasingCurve.QUART_IN,
            "OutQuart": EasingCurve.QUART_OUT,
            "InOutQuart": EasingCurve.QUART_IN_OUT,
            "InExpo": EasingCurve.EXPO_IN,
            "OutExpo": EasingCurve.EXPO_OUT,
            "InOutExpo": EasingCurve.EXPO_IN_OUT,
            "InSine": EasingCurve.SINE_IN,
            "OutSine": EasingCurve.SINE_OUT,
            "InOutSine": EasingCurve.SINE_IN_OUT,
            "InCirc": EasingCurve.CIRC_IN,
            "OutCirc": EasingCurve.CIRC_OUT,
            "InOutCirc": EasingCurve.CIRC_IN_OUT,
            "InBack": EasingCurve.BACK_IN,
            "OutBack": EasingCurve.BACK_OUT,
            "InOutBack": EasingCurve.BACK_IN_OUT,
        }
        return mapping.get(name, EasingCurve.QUAD_IN_OUT)
