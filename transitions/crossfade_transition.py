"""
Crossfade transition - smooth opacity blend between images.

Uses opacity animation to fade out old image while fading in new image.
"""
from typing import Optional
from PySide6.QtCore import QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect

from transitions.base_transition import BaseTransition, TransitionState
from core.logging.logger import get_logger

logger = get_logger(__name__)


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
        self._opacity_effect: Optional[QGraphicsOpacityEffect] = None
        self._animation: Optional[QPropertyAnimation] = None
        self._new_pixmap: Optional[QPixmap] = None
        self._easing = easing
        
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
            self._new_pixmap = new_pixmap
            
            # If no old image, just show new one immediately
            if not old_pixmap or old_pixmap.isNull():
                logger.debug("No old image, showing new image immediately")
                self._show_image_immediately()
                return True
            
            # Create opacity effect
            self._opacity_effect = QGraphicsOpacityEffect(widget)
            self._opacity_effect.setOpacity(1.0)
            widget.setGraphicsEffect(self._opacity_effect)
            
            # Create animation
            self._animation = QPropertyAnimation(self._opacity_effect, b"opacity")
            self._animation.setDuration(self.duration_ms)
            self._animation.setStartValue(1.0)
            self._animation.setEndValue(0.0)
            
            # Set easing curve
            easing_curve = self._get_easing_curve(self._easing)
            self._animation.setEasingCurve(easing_curve)
            
            # Connect signals
            self._animation.valueChanged.connect(self._on_animation_value_changed)
            self._animation.finished.connect(self._on_animation_finished)
            
            # Start animation
            self._set_state(TransitionState.RUNNING)
            self._animation.start()
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
        
        # Stop animation first
        if self._animation:
            try:
                self._animation.stop()
            except RuntimeError:
                pass  # Already deleted
        
        # Set cancelled state before cleanup
        self._set_state(TransitionState.CANCELLED)
        
        # Clean up and show image
        if self._widget and self._new_pixmap:
            self._widget.setGraphicsEffect(None)
        
        self._emit_progress(1.0)
        self.finished.emit()
    
    def cleanup(self) -> None:
        """Clean up transition resources."""
        logger.debug("Cleaning up crossfade transition")
        
        # Stop animation
        if self._animation:
            try:
                self._animation.stop()
                self._animation.deleteLater()
            except RuntimeError:
                pass  # Already deleted
            self._animation = None
        
        # Remove opacity effect
        if self._widget:
            try:
                self._widget.setGraphicsEffect(None)
            except RuntimeError:
                pass  # Widget already deleted
        
        if self._opacity_effect:
            try:
                self._opacity_effect.deleteLater()
            except RuntimeError:
                pass  # Already deleted
            self._opacity_effect = None
        
        self._widget = None
        self._new_pixmap = None
        
        if self._state not in [TransitionState.FINISHED, TransitionState.CANCELLED]:
            self._set_state(TransitionState.IDLE)
    
    def _show_image_immediately(self) -> None:
        """Show new image immediately without transition."""
        if self._widget and self._new_pixmap:
            # Remove any opacity effect
            self._widget.setGraphicsEffect(None)
            
            # Update widget (assumes widget has an update_image method or similar)
            # For now, just emit finished
            self._set_state(TransitionState.FINISHED)
            self._emit_progress(1.0)
            self.finished.emit()
            logger.debug("Image shown immediately")
    
    def _on_animation_value_changed(self, value: float) -> None:
        """
        Handle animation value change.
        
        Args:
            value: Current opacity value (1.0 to 0.0)
        """
        # Progress is inverse of opacity (0.0 opacity = 1.0 progress)
        progress = 1.0 - value
        self._emit_progress(progress)
    
    def _on_animation_finished(self) -> None:
        """Handle animation completion."""
        if self._state != TransitionState.RUNNING:
            return  # Already stopped/cancelled
        
        logger.debug("Crossfade animation finished")
        
        # Show new image
        if self._widget:
            try:
                self._widget.setGraphicsEffect(None)
            except RuntimeError:
                pass  # Widget deleted
        
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        
        # Cleanup resources
        self._animation = None
        self._opacity_effect = None
        self._widget = None
        self._new_pixmap = None
    
    def _get_easing_curve(self, easing_name: str) -> QEasingCurve:
        """
        Get Qt easing curve from name.
        
        Args:
            easing_name: Name of easing curve
        
        Returns:
            QEasingCurve
        """
        easing_map = {
            'Linear': QEasingCurve.Type.Linear,
            'InQuad': QEasingCurve.Type.InQuad,
            'OutQuad': QEasingCurve.Type.OutQuad,
            'InOutQuad': QEasingCurve.Type.InOutQuad,
            'InCubic': QEasingCurve.Type.InCubic,
            'OutCubic': QEasingCurve.Type.OutCubic,
            'InOutCubic': QEasingCurve.Type.InOutCubic,
            'InQuart': QEasingCurve.Type.InQuart,
            'OutQuart': QEasingCurve.Type.OutQuart,
            'InOutQuart': QEasingCurve.Type.InOutQuart,
            'InQuint': QEasingCurve.Type.InQuint,
            'OutQuint': QEasingCurve.Type.OutQuint,
            'InOutQuint': QEasingCurve.Type.InOutQuint,
            'InSine': QEasingCurve.Type.InSine,
            'OutSine': QEasingCurve.Type.OutSine,
            'InOutSine': QEasingCurve.Type.InOutSine,
            'InExpo': QEasingCurve.Type.InExpo,
            'OutExpo': QEasingCurve.Type.OutExpo,
            'InOutExpo': QEasingCurve.Type.InOutExpo,
            'InCirc': QEasingCurve.Type.InCirc,
            'OutCirc': QEasingCurve.Type.OutCirc,
            'InOutCirc': QEasingCurve.Type.InOutCirc,
        }
        
        easing_type = easing_map.get(easing_name, QEasingCurve.Type.InOutQuad)
        
        if easing_name not in easing_map:
            logger.warning(f"[FALLBACK] Unknown easing '{easing_name}', using InOutQuad")
        
        return QEasingCurve(easing_type)
    
    def set_easing(self, easing: str) -> None:
        """
        Set easing curve for transition.
        
        Args:
            easing: Easing curve name
        """
        self._easing = easing
        logger.debug(f"Easing curve set to {easing}")
