"""GL compositor-driven Particle transition.

This transition creates smooth round particles that fly in from off-screen and
stack to reveal the new image. All rendering is delegated to the shared
GLCompositorWidget via its particle API.

Modes:
- Directional: Particles come from one direction (L→R, R→L, T→B, B→T, diagonals)
- Swirl: Particles spiral in from edges toward center
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


class GLCompositorParticleTransition(BaseTransition):
    """GPU-backed Particle transition that targets the shared GL compositor.

    Particles fly in from off-screen and stack with slight overlap to reveal
    the new image. Uses a grid-driven analytic approach for predictable
    performance.
    """

    # Direction constants
    DIR_LEFT_TO_RIGHT = 0
    DIR_RIGHT_TO_LEFT = 1
    DIR_TOP_TO_BOTTOM = 2
    DIR_BOTTOM_TO_TOP = 3
    DIR_TOPLEFT_TO_BOTTOMRIGHT = 4
    DIR_TOPRIGHT_TO_BOTTOMLEFT = 5
    DIR_BOTTOMLEFT_TO_TOPRIGHT = 6
    DIR_BOTTOMRIGHT_TO_TOPLEFT = 7
    DIR_RANDOM = 8
    DIR_RANDOM_PLACEMENT = 9

    # Mode constants
    MODE_DIRECTIONAL = 0
    MODE_SWIRL = 1

    def __init__(
        self,
        duration_ms: int = 3000,
        mode: int = 0,
        direction: int = 0,
        particle_radius: float = 24.0,
        overlap: float = 4.0,
        trail_length: float = 0.15,
        trail_strength: float = 0.6,
        swirl_strength: float = 1.0,
        swirl_turns: float = 2.0,
        use_3d_shading: bool = True,
        texture_mapping: bool = True,
        wobble: bool = False,
        gloss_size: float = 64.0,
        light_direction: int = 0,
        swirl_order: int = 0,
    ) -> None:
        super().__init__(duration_ms)
        self._mode = mode
        self._direction = direction
        self._particle_radius = max(8.0, particle_radius)
        self._overlap = max(0.0, overlap)
        self._trail_length = max(0.0, min(1.0, trail_length))
        self._trail_strength = max(0.0, min(1.0, trail_strength))
        self._swirl_strength = max(0.0, swirl_strength)
        self._swirl_turns = max(0.5, swirl_turns)
        self._use_3d_shading = use_3d_shading
        self._texture_mapping = texture_mapping
        self._wobble = wobble
        self._gloss_size = max(16.0, min(128.0, gloss_size))
        self._light_direction = max(0, min(4, light_direction))
        self._swirl_order = max(0, min(2, swirl_order))
        self._widget: Optional[QWidget] = None
        self._compositor: Optional[GLCompositorWidget] = None
        self._animation_id: Optional[str] = None

    # ------------------------------------------------------------------
    # BaseTransition API
    # ------------------------------------------------------------------

    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, widget: QWidget) -> bool:
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid pixmap for GL compositor Particle")
            self.error.emit("Invalid image")
            return False

        self._widget = widget

        # Begin telemetry tracking
        self._mark_start()

        # If there's no old image, just complete immediately.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("No old image, showing new image immediately (GL compositor particle)")
            self._show_image_immediately()
            return True

        # Resolve compositor from widget; fall back to immediate display if absent.
        comp = getattr(widget, "_gl_compositor", None)
        if comp is None or not isinstance(comp, GLCompositorWidget):
            logger.warning(
                "[GL COMPOSITOR] No compositor attached to widget; falling back to immediate display (particle)"
            )
            self._show_image_immediately()
            return True

        self._compositor = comp

        # Best-effort shader texture prewarm
        try:
            warm = getattr(comp, "warm_shader_textures", None)
            if callable(warm):
                warm(old_pixmap, new_pixmap)
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to warm particle textures", exc_info=True)

        # Ensure compositor matches widget geometry and is above the base.
        try:
            comp.setGeometry(0, 0, widget.width(), widget.height())
            comp.show()
            comp.raise_()
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to configure compositor geometry/visibility (particle)", exc_info=True)

        # Drive via shared AnimationManager.
        easing_curve = EasingCurve.CUBIC_IN_OUT
        am = self._get_animation_manager(widget)

        def _on_finished() -> None:
            self._on_anim_complete()

        self._animation_id = comp.start_particle(
            old_pixmap,
            new_pixmap,
            duration_ms=self.duration_ms,
            easing=easing_curve,
            animation_manager=am,
            on_finished=_on_finished,
            mode=self._mode,
            direction=self._direction,
            particle_radius=self._particle_radius,
            overlap=self._overlap,
            trail_length=self._trail_length,
            trail_strength=self._trail_strength,
            swirl_strength=self._swirl_strength,
            swirl_turns=self._swirl_turns,
            use_3d_shading=self._use_3d_shading,
            texture_mapping=self._texture_mapping,
            wobble=self._wobble,
            gloss_size=self._gloss_size,
            light_direction=self._light_direction,
            swirl_order=self._swirl_order,
        )

        self._set_state(TransitionState.RUNNING)
        self.started.emit()
        logger.info(
            "GLCompositorParticleTransition started (%dms, mode=%d, dir=%d)",
            self.duration_ms, self._mode, self._direction
        )
        return True

    def stop(self) -> None:
        if self._state != TransitionState.RUNNING:
            return

        logger.debug("Stopping GLCompositorParticleTransition")

        if self._compositor is not None:
            try:
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cancel current transition (particle)", exc_info=True)

        self._animation_id = None
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()

    def cleanup(self) -> None:
        logger.debug("Cleaning up GLCompositorParticleTransition")

        if self._compositor is not None:
            try:
                self._compositor.cancel_current_transition(snap_to_new=True)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cleanup compositor (particle)", exc_info=True)
            self._compositor = None

        self._widget = None
        self._animation_id = None

        if self._state not in (TransitionState.FINISHED, TransitionState.CANCELLED):
            self._set_state(TransitionState.IDLE)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_anim_complete(self) -> None:
        """Called when the compositor finishes its particle animation."""
        self._mark_end()
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("GLCompositorParticleTransition finished")

    def _show_image_immediately(self) -> None:
        """Immediate completion when no GL compositor path is available."""
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
