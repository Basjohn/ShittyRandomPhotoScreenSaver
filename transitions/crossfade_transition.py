"""
Crossfade transition - smooth opacity blend between images (CPU path).

Uses a dedicated overlay widget that composes old and new pixmaps per-frame
with QPainter. Animation timing is driven by the centralized AnimationManager.
"""
import threading
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPixmap, QPainter

from transitions.base_transition import BaseTransition, TransitionState
from transitions.overlay_manager import (
    get_or_create_overlay,
    notify_overlay_stage,
    schedule_raise_when_ready,
    set_overlay_geometry,
)
from core.animation.types import EasingCurve
from core.logging.logger import get_logger

logger = get_logger(__name__)


class _SWFadeOverlay(QWidget):
    """CPU overlay that blends two pixmaps using QPainter opacity."""

    def __init__(self, parent: QWidget, old_pixmap: QPixmap, new_pixmap: QPixmap) -> None:
        super().__init__(parent)
        self.setAutoFillBackground(False)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception as e:
            logger.debug("[TRANSITION] Exception suppressed: %s", e)
        self._old = old_pixmap
        self._new = new_pixmap
        self._alpha: float = 0.0
        
        # Atomic state flags with lock protection (for consistency with GL overlays)
        self._state_lock = threading.Lock()
        self._first_frame_drawn: bool = False
        self._has_drawn: bool = False

    def set_images(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> None:
        self._old = old_pixmap
        self._new = new_pixmap
        with self._state_lock:
            self._first_frame_drawn = False
            self._has_drawn = False
        self.update()

    def set_alpha(self, a: float) -> None:
        self._alpha = max(0.0, min(1.0, a))
        self.update()

    def has_drawn(self) -> bool:
        return self._has_drawn
    
    def is_ready_for_display(self) -> bool:
        """Thread-safe check if overlay is ready to display."""
        try:
            with self._state_lock:
                return self._first_frame_drawn
        except Exception as e:
            logger.debug("[TRANSITION] Exception suppressed: %s", e)
            return False

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            # Full coverage: draw old fully, then new with alpha
            target = self.rect()
            if self._old and not self._old.isNull():
                p.setOpacity(1.0)
                p.drawPixmap(target, self._old)
            if self._new and not self._new.isNull():
                p.setOpacity(self._alpha)
                p.drawPixmap(target, self._new)
        finally:
            p.end()
        
        # Mark as drawn atomically
        with self._state_lock:
            if not self._first_frame_drawn:
                self._first_frame_drawn = True
                logger.debug("[SW XFADE] First frame drawn, overlay ready")
            self._has_drawn = True


class CrossfadeTransition(BaseTransition):
    """
    Crossfade transition effect.
    
    Smoothly fades from old image to new image by animating opacity.
    Uses QGraphicsOpacityEffect for the fade effect.
    """
    
    def __init__(self, duration_ms: int = 1000, easing: str = "InOutQuad"):
        """
        Initialize crossfade transition.
        
        Args:
            duration_ms: Fade duration in milliseconds
            easing: Easing curve name (default: InOutQuad)
        """
        super().__init__(duration_ms)
        
        self._widget: Optional[QWidget] = None
        self._overlay: Optional[_SWFadeOverlay] = None
        self._animation_id: Optional[str] = None
        self._easing = easing
        self._elapsed_ms = 0  # FIX: Initialize to prevent AttributeError
        
        logger.debug(f"CrossfadeTransition created (duration={duration_ms}ms, easing={easing})")
    
    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, 
              widget: QWidget) -> bool:
        """
        Start crossfade transition.
        
        Args:
            old_pixmap: Previous image (ignored for crossfade)
            new_pixmap: New image to fade to
            widget: Widget to perform transition on
        
        Returns:
            True if started successfully, False otherwise
        """
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid pixmap for transition")
            self.error.emit("Invalid image")
            return False
        
        try:
            self._widget = widget
            self._elapsed_ms = 0
            
            # If no old image, just show new one immediately
            if not old_pixmap or old_pixmap.isNull():
                logger.debug("No old image, showing new image immediately")
                self._show_image_immediately()
                return True
            
            # Begin telemetry tracking for animated crossfade
            self._mark_start()

            # Reuse or create persistent CPU overlay on the widget
            existing = getattr(widget, "_srpss_sw_xfade_overlay", None)
            overlay = get_or_create_overlay(
                widget,
                "_srpss_sw_xfade_overlay",
                _SWFadeOverlay,
                lambda: _SWFadeOverlay(widget, old_pixmap, new_pixmap),
            )

            if overlay is existing:
                logger.debug("[SW XFADE] Reusing persistent CPU overlay")
            else:
                logger.debug("[SW XFADE] Created persistent CPU overlay")

            overlay.set_images(old_pixmap, new_pixmap)
            overlay.set_alpha(0.0)

            self._overlay = overlay
            # Ensure overlay covers widget and prepaint first frame to avoid flash
            set_overlay_geometry(widget, overlay)
            notify_overlay_stage(overlay, "prepaint_start")
            overlay.setVisible(True)
            try:
                overlay.update()
            except Exception as e:
                logger.debug("[TRANSITION] Exception suppressed: %s", e)
            try:
                schedule_raise_when_ready(widget, overlay, stage="initial_raise_sw")
            except Exception as e:
                logger.debug("[TRANSITION] Exception suppressed: %s", e)

            # Drive via centralized AnimationManager
            am = self._get_animation_manager(widget)
            duration_sec = max(0.001, self.duration_ms / 1000.0)
            self._animation_id = am.animate_custom(
                duration=duration_sec,
                easing=self._resolve_easing(),
                update_callback=lambda p: self._on_anim_update(p),
                on_complete=lambda: self._on_anim_complete(),
            )

            self._set_state(TransitionState.RUNNING)
            self.started.emit()
            logger.info(f"Crossfade transition started ({self.duration_ms}ms)")
            return True
        
        except Exception as e:
            logger.exception(f"Failed to start crossfade transition: {e}")
            self.error.emit(f"Transition failed: {e}")
            self.cleanup()
            return False
    
    def stop(self) -> None:
        """Stop transition immediately."""
        if self._state != TransitionState.RUNNING:
            return
        
        logger.debug("Stopping crossfade transition")
        # Cancel central animation
        if self._animation_id and self._widget:
            try:
                am = self._get_animation_manager(self._widget)
                am.cancel_animation(self._animation_id)
            except Exception as e:
                logger.debug("[TRANSITION] Exception suppressed: %s", e)
            self._animation_id = None
        # Set cancelled state before cleanup
        self._set_state(TransitionState.CANCELLED)
        
        self._emit_progress(1.0)
        self.finished.emit()
    
    def cleanup(self) -> None:
        """Clean up transition resources using ResourceManager."""
        logger.debug("Cleaning up crossfade transition")
        # Cancel animation if active
        if self._animation_id and self._widget:
            try:
                am = self._get_animation_manager(self._widget)
                am.cancel_animation(self._animation_id)
            except Exception as e:
                logger.debug("[TRANSITION] Exception suppressed: %s", e)
            self._animation_id = None
        # Hide persistent overlay (do not delete)
        if self._overlay:
            try:
                self._overlay.hide()
            except Exception as e:
                logger.debug("[TRANSITION] Exception suppressed: %s", e)
            self._overlay = None
        # Only clear widget reference
        self._widget = None
        
        if self._state not in [TransitionState.FINISHED, TransitionState.CANCELLED]:
            self._set_state(TransitionState.IDLE)
    
    def _show_image_immediately(self) -> None:
        """Show new image immediately without transition."""
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("Image shown immediately")
    
    def _on_anim_update(self, progress: float) -> None:
        if self._state != TransitionState.RUNNING or not self._overlay:
            return
        progress = max(0.0, min(1.0, progress))
        try:
            self._overlay.set_alpha(progress)
            self._overlay.update()
        except Exception as e:
            logger.debug("[TRANSITION] Exception suppressed: %s", e)
        self._emit_progress(progress)

    def _on_anim_complete(self) -> None:
        if self._state != TransitionState.RUNNING:
            return
        logger.debug("Crossfade transition finished")
        # End telemetry tracking for successful completion
        self._mark_end()
        if self._overlay:
            try:
                self._overlay.set_alpha(1.0)
                self._overlay.update()
            except Exception as e:
                logger.debug("[TRANSITION] Exception suppressed: %s", e)
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
    
    def _resolve_easing(self) -> EasingCurve:
        name = (self._easing or 'Auto').strip()
        if name == 'Auto':
            return EasingCurve.QUAD_IN_OUT
        mapping = {
            'Linear': EasingCurve.LINEAR,
            'InQuad': EasingCurve.QUAD_IN,
            'OutQuad': EasingCurve.QUAD_OUT,
            'InOutQuad': EasingCurve.QUAD_IN_OUT,
            'InCubic': EasingCurve.CUBIC_IN,
            'OutCubic': EasingCurve.CUBIC_OUT,
            'InOutCubic': EasingCurve.CUBIC_IN_OUT,
            'InQuart': EasingCurve.QUART_IN,
            'OutQuart': EasingCurve.QUART_OUT,
            'InOutQuart': EasingCurve.QUART_IN_OUT,
            'InSine': EasingCurve.SINE_IN,
            'OutSine': EasingCurve.SINE_OUT,
            'InOutSine': EasingCurve.SINE_IN_OUT,
            'InExpo': EasingCurve.EXPO_IN,
            'OutExpo': EasingCurve.EXPO_OUT,
            'InOutExpo': EasingCurve.EXPO_IN_OUT,
            'InCirc': EasingCurve.CIRC_IN,
            'OutCirc': EasingCurve.CIRC_OUT,
            'InOutCirc': EasingCurve.CIRC_IN_OUT,
        }
        return mapping.get(name, EasingCurve.QUAD_IN_OUT)
    
    def set_easing(self, easing: str) -> None:
        """
        Set easing curve for transition.
        
        Args:
            easing: Easing curve name
        """
        self._easing = easing
        logger.debug(f"Easing curve set to {easing}")
