"""GL compositor-driven burn transition.

Simulates a burning-paper effect using a GLSL shader: a noisy jagged edge
eats across the screen leaving a warm glow zone and a charred black zone
before revealing the new image.  Optional smoke puffs and falling ash
particles add to the effect.

The controller owns only timing, direction, easing, and per-transition
settings.  Rendering is delegated to the single GLCompositorWidget attached
to the DisplayWidget.
"""
from __future__ import annotations

import random
from typing import Optional

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.animation.types import EasingCurve

from transitions.base_transition import BaseTransition, TransitionState
from rendering.gl_compositor import GLCompositorWidget


logger = get_logger(__name__)


class GLCompositorBurnTransition(BaseTransition):
    """GPU-backed Burn transition that targets the shared GL compositor widget.

    Parameters
    ----------
    duration_ms:
        Total transition duration in milliseconds.
    direction:
        Burn direction — 0=L→R, 1=R→L, 2=T→B, 3=B→T, 4=center→out.
    jaggedness:
        Edge noise amplitude (0.0–1.0).
    glow_intensity:
        Brightness of the incandescent glow zone (0.0–1.0).
    glow_color:
        RGBA tuple for the primary glow colour (default: warm orange).
    char_width:
        Width of the charred zone relative to screen (0.1–1.0).
    smoke_enabled:
        Whether smoke puffs are rendered.
    smoke_density:
        Smoke opacity/density (0.0–1.0).
    ash_enabled:
        Whether falling ash specks are rendered.
    ash_density:
        Ash particle density (0.0–1.0).
    easing:
        Easing curve name string (e.g. "Auto", "Linear", "InOutCubic").
    """

    def __init__(
        self,
        duration_ms: int = 2000,
        direction: int = 0,
        jaggedness: float = 0.5,
        glow_intensity: float = 0.7,
        glow_color: tuple = (1.0, 0.55, 0.12, 1.0),
        char_width: float = 0.5,
        smoke_enabled: bool = True,
        smoke_density: float = 0.5,
        ash_enabled: bool = True,
        ash_density: float = 0.5,
        easing: str = "Auto",
    ) -> None:
        super().__init__(duration_ms)
        self._widget: Optional[QWidget] = None
        self._compositor: Optional[GLCompositorWidget] = None
        self._animation_id: Optional[str] = None

        self._direction: int = max(0, min(3, int(direction)))
        self._jaggedness: float = max(0.0, min(1.0, float(jaggedness)))
        self._glow_intensity: float = max(0.0, min(1.0, float(glow_intensity)))
        self._glow_color: tuple = tuple(glow_color)
        self._char_width: float = max(0.1, min(1.0, float(char_width)))
        self._smoke_enabled: bool = bool(smoke_enabled)
        self._smoke_density: float = max(0.0, min(1.0, float(smoke_density)))
        self._ash_enabled: bool = bool(ash_enabled)
        self._ash_density: float = max(0.0, min(1.0, float(ash_density)))
        self._easing_str: str = easing
        self._seed: float = random.random() * 1000.0

    # ------------------------------------------------------------------
    # BaseTransition API
    # ------------------------------------------------------------------

    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, widget: QWidget) -> bool:  # type: ignore[override]
        if self._state == TransitionState.RUNNING:
            logger.warning("[BURN] Transition already running")
            return False
        if not new_pixmap or new_pixmap.isNull():
            logger.error("[BURN] Invalid pixmap for GL compositor burn")
            self.error.emit("Invalid image")
            return False

        self._widget = widget
        self._mark_start()

        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[BURN] No old image, showing new image immediately")
            self._show_image_immediately()
            return True

        comp = getattr(widget, "_gl_compositor", None)
        if comp is None or not isinstance(comp, GLCompositorWidget):
            logger.warning("[BURN] No compositor attached to widget; falling back to immediate display")
            self._show_image_immediately()
            return True

        self._compositor = comp

        try:
            comp.setGeometry(0, 0, widget.width(), widget.height())
            comp.show()
            comp.raise_()
        except Exception:
            logger.debug("[BURN] Failed to configure compositor geometry/visibility", exc_info=True)

        easing_curve = self._resolve_easing()
        am = self._get_animation_manager(widget)

        def _on_finished() -> None:
            self._on_anim_complete()

        self._animation_id = comp.start_burn(
            old_pixmap,
            new_pixmap,
            duration_ms=self.duration_ms,
            easing=easing_curve,
            animation_manager=am,
            on_finished=_on_finished,
            direction=self._direction,
            jaggedness=self._jaggedness,
            glow_intensity=self._glow_intensity,
            glow_color=self._glow_color,
            char_width=self._char_width,
            smoke_enabled=self._smoke_enabled,
            smoke_density=self._smoke_density,
            ash_enabled=self._ash_enabled,
            ash_density=self._ash_density,
            seed=self._seed,
        )

        self._set_state(TransitionState.RUNNING)
        self.started.emit()
        logger.info(
            "[BURN] GLCompositorBurnTransition started (%dms, dir=%d, jag=%.2f)",
            self.duration_ms, self._direction, self._jaggedness,
        )
        return True

    def stop(self) -> None:  # type: ignore[override]
        if self._state != TransitionState.RUNNING:
            return

        logger.debug("[BURN] Stopping GLCompositorBurnTransition")

        if self._compositor is not None:
            try:
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
                logger.debug("[BURN] Failed to cancel burn transition", exc_info=True)

        self._animation_id = None
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()

    def cleanup(self) -> None:  # type: ignore[override]
        logger.debug("[BURN] Cleaning up GLCompositorBurnTransition")

        if self._compositor is not None:
            try:
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
                logger.debug("[BURN] Failed to cleanup burn compositor", exc_info=True)
            self._compositor = None

        self._widget = None
        self._animation_id = None

        if self._state not in (TransitionState.FINISHED, TransitionState.CANCELLED):
            self._set_state(TransitionState.IDLE)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_anim_complete(self) -> None:
        self._mark_end()
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("[BURN] GLCompositorBurnTransition finished")

    def _show_image_immediately(self) -> None:
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()

    def _resolve_easing(self) -> EasingCurve:
        name = (self._easing_str or "Auto").strip()
        if name == "Auto":
            return EasingCurve.CUBIC_IN_OUT
        mapping = {
            "Linear": EasingCurve.LINEAR,
            "InQuad": EasingCurve.QUAD_IN,
            "OutQuad": EasingCurve.QUAD_OUT,
            "InOutQuad": EasingCurve.QUAD_IN_OUT,
            "InCubic": EasingCurve.CUBIC_IN,
            "OutCubic": EasingCurve.CUBIC_OUT,
            "InOutCubic": EasingCurve.CUBIC_IN_OUT,
        }
        return mapping.get(name, EasingCurve.CUBIC_IN_OUT)
