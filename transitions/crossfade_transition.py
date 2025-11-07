"""
Crossfade transition - smooth opacity blend between images.

Uses opacity animation to fade out old image while fading in new image.
"""
from typing import Optional
from PySide6.QtCore import Qt, QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QWidget, QLabel, QGraphicsOpacityEffect
from PySide6.QtGui import QPixmap

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
        self._old_label: Optional[QLabel] = None
        self._new_label: Optional[QLabel] = None
        self._opacity_effect = None
        self._animation: Optional[QPropertyAnimation] = None
        self._easing = easing
        self._elapsed_ms = 0  # FIX: Initialize to prevent AttributeError
        
        # Get ResourceManager for proper cleanup
        try:
            from core.resources.manager import ResourceManager
            self._resource_manager = ResourceManager()
        except Exception:
            self._resource_manager = None
        
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
            
            # Create labels for old and new images
            # FIX: Import moved to top of file
            
            self._old_label = QLabel(widget)
            self._old_label.setPixmap(old_pixmap)
            self._old_label.setGeometry(0, 0, widget.width(), widget.height())
            self._old_label.setScaledContents(False)
            self._old_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._old_label.setStyleSheet("background: transparent;")
            self._old_label.show()
            
            self._new_label = QLabel(widget)
            self._new_label.setPixmap(new_pixmap)
            self._new_label.setGeometry(0, 0, widget.width(), widget.height())
            self._new_label.setScaledContents(False)
            self._new_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._new_label.setStyleSheet("background: transparent;")
            
            # Use QGraphicsOpacityEffect for fade
            self._opacity_effect = QGraphicsOpacityEffect()
            self._opacity_effect.setOpacity(0.0)
            self._new_label.setGraphicsEffect(self._opacity_effect)
            
            self._new_label.show()
            
            # Create smooth property animation
            self._animation = QPropertyAnimation(self._opacity_effect, b"opacity")
            self._animation.setDuration(self.duration_ms)
            self._animation.setStartValue(0.0)
            self._animation.setEndValue(1.0)
            
            # Apply easing curve
            easing_map = {
                'InOutQuad': QEasingCurve.Type.InOutQuad,
                'Linear': QEasingCurve.Type.Linear,
                'InQuad': QEasingCurve.Type.InQuad,
                'OutQuad': QEasingCurve.Type.OutQuad
            }
            easing_type = easing_map.get(self._easing, QEasingCurve.Type.InOutQuad)
            self._animation.setEasingCurve(easing_type)
            
            # Connect finished signal
            self._animation.finished.connect(self._on_animation_finished)
            self._animation.start()
            
            # Start transition
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
        
        # Stop animation
        if self._animation:
            self._animation.stop()
        
        # Set cancelled state before cleanup
        self._set_state(TransitionState.CANCELLED)
        
        self._emit_progress(1.0)
        self.finished.emit()
    
    def cleanup(self) -> None:
        """Clean up transition resources using ResourceManager."""
        logger.debug("Cleaning up crossfade transition")
        
        # Stop animation and let ResourceManager handle cleanup
        if self._animation:
            try:
                self._animation.stop()
                self._animation.deleteLater()
            except RuntimeError:
                pass
            # FIX: Don't set to None - let deleteLater process first
        
        # Remove labels via deleteLater (ResourceManager tracks these)
        if self._old_label:
            try:
                self._old_label.deleteLater()
            except RuntimeError:
                pass
        
        if self._new_label:
            try:
                self._new_label.deleteLater()
            except RuntimeError:
                pass
        
        if self._opacity_effect:
            try:
                self._opacity_effect.deleteLater()
            except RuntimeError:
                pass
        
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
    
    def _on_animation_finished(self) -> None:
        """Handle animation completion from QPropertyAnimation."""
        if self._state != TransitionState.RUNNING:
            return
        
        logger.debug("Crossfade animation finished (QPropertyAnimation)")
        self._emit_progress(1.0)
        self._on_transition_finished()
    
    def _on_transition_finished(self) -> None:
        """Handle transition completion."""
        if self._state != TransitionState.RUNNING:
            return
        
        logger.debug("Crossfade transition finished")
        
        # Stop animation
        if self._animation:
            self._animation.stop()
        
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
    
    def _apply_easing(self, progress: float) -> float:
        """
        Apply easing curve to progress.
        
        Args:
            progress: Linear progress (0.0 to 1.0)
        
        Returns:
            Eased progress value
        """
        easing_curve = self._get_easing_curve(self._easing)
        return easing_curve.valueForProgress(progress)
    
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
