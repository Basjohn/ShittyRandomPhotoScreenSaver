"""
Slide transition - directional slide animation.

Slides new image in from a direction while old image slides out.
"""
from enum import Enum
from typing import Optional
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QLabel

from transitions.base_transition import BaseTransition, TransitionState
from core.logging.logger import get_logger

logger = get_logger(__name__)


class SlideDirection(Enum):
    """Direction for slide transition."""
    LEFT = "left"      # New image slides in from right
    RIGHT = "right"    # New image slides in from left
    UP = "up"          # New image slides in from bottom
    DOWN = "down"      # New image slides in from top
    DIAG_TL_BR = "diag_tl_br"  # Diagonal: top-left to bottom-right
    DIAG_TR_BL = "diag_tr_bl"  # Diagonal: top-right to bottom-left


class SlideTransition(BaseTransition):
    """
    Slide transition effect.
    
    Slides new image in from specified direction while old image slides out.
    Uses QLabel widgets and QPropertyAnimation for smooth movement.
    """
    
    def __init__(self, duration_ms: int = 1000, direction: SlideDirection = SlideDirection.LEFT,
                 easing: str = "InOutQuad"):
        """
        Initialize slide transition.
        
        Args:
            duration_ms: Slide duration in milliseconds
            direction: Direction to slide (LEFT, RIGHT, UP, DOWN)
            easing: Easing curve name (default: InOutQuad)
        """
        super().__init__(duration_ms)
        
        self._direction = direction
        self._easing = easing
        self._widget: Optional[QWidget] = None
        self._old_label: Optional[QLabel] = None
        self._new_label: Optional[QLabel] = None
        self._old_animation: Optional[QPropertyAnimation] = None
        self._new_animation: Optional[QPropertyAnimation] = None
        self._finished_count = 0
        
        # FIX: Use ResourceManager for Qt object lifecycle
        try:
            from core.resources.manager import ResourceManager
            self._resource_manager = ResourceManager()
        except Exception:
            self._resource_manager = None
        
        logger.debug(f"SlideTransition created (duration={duration_ms}ms, direction={direction.value}, easing={easing})")
    
    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap,
              widget: QWidget) -> bool:
        """
        Start slide transition.
        
        Args:
            old_pixmap: Previous image (None if first image)
            new_pixmap: New image to slide to
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
            self._finished_count = 0
            
            # If no old image, just show new one immediately
            if not old_pixmap or old_pixmap.isNull():
                logger.debug("No old image, showing new image immediately")
                self._show_image_immediately()
                return True
            
            # Get widget dimensions
            width = widget.width()
            height = widget.height()
            
            # Create labels for old and new images
            self._old_label = QLabel(widget)
            self._old_label.setPixmap(old_pixmap)
            self._old_label.setGeometry(0, 0, width, height)
            self._old_label.show()
            
            self._new_label = QLabel(widget)
            self._new_label.setPixmap(new_pixmap)
            self._new_label.setGeometry(0, 0, width, height)
            
            # Calculate start and end positions based on direction
            old_start, old_end, new_start, new_end = self._calculate_positions(width, height)
            
            # Position labels at start
            self._old_label.move(old_start)
            self._new_label.move(new_start)
            self._new_label.show()
            
            # Create animations
            self._old_animation = QPropertyAnimation(self._old_label, b"pos")
            self._old_animation.setDuration(self.duration_ms)
            self._old_animation.setStartValue(old_start)
            self._old_animation.setEndValue(old_end)
            self._old_animation.setEasingCurve(self._get_easing_curve(self._easing))
            
            self._new_animation = QPropertyAnimation(self._new_label, b"pos")
            self._new_animation.setDuration(self.duration_ms)
            self._new_animation.setStartValue(new_start)
            self._new_animation.setEndValue(new_end)
            self._new_animation.setEasingCurve(self._get_easing_curve(self._easing))
            
            # Connect signals
            self._old_animation.valueChanged.connect(self._on_animation_value_changed)
            self._old_animation.finished.connect(self._on_animation_finished)
            self._new_animation.finished.connect(self._on_animation_finished)
            
            # Start animations
            self._set_state(TransitionState.RUNNING)
            self._old_animation.start()
            self._new_animation.start()
            self.started.emit()
            
            logger.info(f"Slide transition started ({self.duration_ms}ms, direction={self._direction.value})")
            return True
        
        except Exception as e:
            logger.exception(f"Failed to start slide transition: {e}")
            self.error.emit(f"Transition failed: {e}")
            self.cleanup()
            return False
    
    def stop(self) -> None:
        """Stop transition immediately."""
        if self._state != TransitionState.RUNNING:
            return
        
        logger.debug("Stopping slide transition")
        
        # Stop animations
        if self._old_animation:
            try:
                self._old_animation.stop()
            except RuntimeError:
                pass
        
        if self._new_animation:
            try:
                self._new_animation.stop()
            except RuntimeError:
                pass
        
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()
    
    def cleanup(self) -> None:
        """Clean up transition resources."""
        logger.debug("Cleaning up slide transition")
        
        # Stop and delete animations
        # FIX: Don't set to None after deleteLater - prevents memory leak
        if self._old_animation:
            try:
                self._old_animation.stop()
                self._old_animation.deleteLater()
            except RuntimeError:
                pass
        
        if self._new_animation:
            try:
                self._new_animation.stop()
                self._new_animation.deleteLater()
            except RuntimeError:
                pass
        
        # Delete labels
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
        
        self._widget = None
        self._finished_count = 0
        
        if self._state not in [TransitionState.FINISHED, TransitionState.CANCELLED]:
            self._set_state(TransitionState.IDLE)
    
    def _calculate_positions(self, width: int, height: int) -> tuple:
        """
        Calculate start and end positions for both images.
        
        Args:
            width: Widget width
            height: Widget height
        
        Returns:
            Tuple of (old_start, old_end, new_start, new_end)
        """
        if self._direction == SlideDirection.LEFT:
            # Old slides left (out), new slides in from right
            old_start = QPoint(0, 0)
            old_end = QPoint(-width, 0)
            new_start = QPoint(width, 0)
            new_end = QPoint(0, 0)
        
        elif self._direction == SlideDirection.RIGHT:
            # Old slides right (out), new slides in from left
            old_start = QPoint(0, 0)
            old_end = QPoint(width, 0)
            new_start = QPoint(-width, 0)
            new_end = QPoint(0, 0)
        
        elif self._direction == SlideDirection.UP:
            # Old slides up (out), new slides in from bottom
            old_start = QPoint(0, 0)
            old_end = QPoint(0, -height)
            new_start = QPoint(0, height)
            new_end = QPoint(0, 0)
        
        elif self._direction == SlideDirection.DOWN:
            # Old slides down (out), new slides in from top
            old_start = QPoint(0, 0)
            old_end = QPoint(0, height)
            new_start = QPoint(0, -height)
            new_end = QPoint(0, 0)
        elif self._direction == SlideDirection.DIAG_TL_BR:
            # Old moves towards top-left, new comes from bottom-right
            old_start = QPoint(0, 0)
            old_end = QPoint(-width, -height)
            new_start = QPoint(width, height)
            new_end = QPoint(0, 0)
        elif self._direction == SlideDirection.DIAG_TR_BL:
            # Old moves towards top-right, new comes from bottom-left
            old_start = QPoint(0, 0)
            old_end = QPoint(width, -height)
            new_start = QPoint(-width, height)
            new_end = QPoint(0, 0)
        
        return old_start, old_end, new_start, new_end
    
    def _show_image_immediately(self) -> None:
        """Show new image immediately without transition."""
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("Image shown immediately")
    
    def _on_animation_value_changed(self, value: QPoint) -> None:
        """
        Handle animation value change.
        
        Args:
            value: Current position value
        """
        # Calculate progress based on distance traveled
        if self._old_animation:
            start = self._old_animation.startValue()
            end = self._old_animation.endValue()
            current = value
            
            if self._direction in [SlideDirection.LEFT, SlideDirection.RIGHT]:
                total_distance = abs(end.x() - start.x())
                current_distance = abs(current.x() - start.x())
            else:
                total_distance = abs(end.y() - start.y())
                current_distance = abs(current.y() - start.y())
            
            if total_distance > 0:
                progress = current_distance / total_distance
                self._emit_progress(progress)
    
    def _on_animation_finished(self) -> None:
        """Handle animation completion."""
        if self._state != TransitionState.RUNNING:
            return
        
        self._finished_count += 1
        
        # Wait for both animations to finish
        if self._finished_count >= 2:
            logger.debug("Slide animation finished")
            
            self._set_state(TransitionState.FINISHED)
            self._emit_progress(1.0)
            self.finished.emit()
            
            # Cleanup resources
            self._old_animation = None
            self._new_animation = None
            
            # Clean up labels
            # FIX: Don't set to None after deleteLater - prevents memory leak
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
            
            self._widget = None
    
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
    
    def set_direction(self, direction: SlideDirection) -> None:
        """
        Set slide direction.
        
        Args:
            direction: New direction
        """
        self._direction = direction
        logger.debug(f"Slide direction set to {direction.value}")
    
    def set_easing(self, easing: str) -> None:
        """
        Set easing curve for transition.
        
        Args:
            easing: Easing curve name
        """
        self._easing = easing
        logger.debug(f"Easing curve set to {easing}")
