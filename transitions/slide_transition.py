"""
Slide transition - directional slide animation.

Slides new image in from a direction while old image slides out.
"""
from enum import Enum
from typing import Optional
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QLabel

from transitions.base_transition import BaseTransition, TransitionState
from core.animation.types import EasingCurve
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
        self._animation_id: Optional[str] = None
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
            
            # Pre-fit pixmaps to widget to ensure DPR-correct full-rect painting
            fitted_old = self._fit_pixmap_to_widget(old_pixmap, widget)
            fitted_new = self._fit_pixmap_to_widget(new_pixmap, widget)

            # Create labels for old and new images
            self._old_label = QLabel(widget)
            self._old_label.setPixmap(fitted_old)
            self._old_label.setGeometry(0, 0, width, height)
            self._old_label.setScaledContents(False)
            self._old_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._old_label.setStyleSheet("background: transparent;")
            self._old_label.show()

            self._new_label = QLabel(widget)
            self._new_label.setPixmap(fitted_new)
            self._new_label.setGeometry(0, 0, width, height)
            self._new_label.setScaledContents(False)
            self._new_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._new_label.setStyleSheet("background: transparent;")

            # Calculate start and end positions based on direction
            old_start, old_end, new_start, new_end = self._calculate_positions(width, height)
            
            # Position labels at start
            self._old_label.move(old_start)
            self._new_label.move(new_start)
            self._new_label.show()
            
            # Drive via centralized AnimationManager (no QPropertyAnimation)
            am = self._get_animation_manager(widget)
            duration_sec = max(0.001, self.duration_ms / 1000.0)
            self._animation_id = am.animate_custom(
                duration=duration_sec,
                easing=self._resolve_easing(),
                update_callback=lambda p, os=old_start, oe=old_end, ns=new_start, ne=new_end: self._on_anim_update(p, os, oe, ns, ne),
                on_complete=lambda: self._on_anim_complete(old_end, new_end),
            )

            self._set_state(TransitionState.RUNNING)
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
        
        # Cancel centralized animation
        if self._animation_id and self._widget:
            try:
                am = self._get_animation_manager(self._widget)
                am.cancel_animation(self._animation_id)
            except Exception:
                pass
            self._animation_id = None
        
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()
    
    def cleanup(self) -> None:
        """Clean up transition resources."""
        logger.debug("Cleaning up slide transition")
        
        # Cancel centralized animation if active
        if self._animation_id and self._widget:
            try:
                am = self._get_animation_manager(self._widget)
                am.cancel_animation(self._animation_id)
            except Exception:
                pass
            self._animation_id = None
        
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
    
    def _on_anim_update(self, progress: float, old_start: QPoint, old_end: QPoint, new_start: QPoint, new_end: QPoint) -> None:
        """AnimationManager update: move labels according to eased progress."""
        if self._state != TransitionState.RUNNING:
            return
        try:
            t = max(0.0, min(1.0, progress))
            def lerp(a: QPoint, b: QPoint, t: float) -> QPoint:
                return QPoint(int(a.x() + (b.x() - a.x()) * t), int(a.y() + (b.y() - a.y()) * t))
            if self._old_label:
                self._old_label.move(lerp(old_start, old_end, t))
            if self._new_label:
                self._new_label.move(lerp(new_start, new_end, t))
        except Exception:
            pass
        self._emit_progress(t)

    def _on_anim_complete(self, old_end: QPoint, new_end: QPoint) -> None:
        """Animation completion: finalize positions and cleanup."""
        if self._state != TransitionState.RUNNING:
            return
        try:
            if self._old_label:
                self._old_label.move(old_end)
            if self._new_label:
                self._new_label.move(new_end)
        except Exception:
            pass
        logger.debug("Slide animation finished")
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        # Clean up labels
        if self._old_label:
            try:
                self._old_label.deleteLater()
            except RuntimeError:
                pass
            self._old_label = None
        if self._new_label:
            try:
                self._new_label.deleteLater()
            except RuntimeError:
                pass
            self._new_label = None
        self._widget = None
    
    def _resolve_easing(self) -> EasingCurve:
        """Map UI easing string to core EasingCurve with 'Auto' default."""
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
