"""
Wipe transition effect.

Reveals new image progressively as a line moves across the screen.
Supports multiple directions and configurable speed.
"""
from typing import Optional
from enum import Enum
from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap, QPainter

from transitions.base_transition import BaseTransition, TransitionState
from core.logging.logger import get_logger

logger = get_logger(__name__)


class WipeDirection(Enum):
    """Wipe direction options."""
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"
    TOP_TO_BOTTOM = "top_to_bottom"
    BOTTOM_TO_TOP = "bottom_to_top"


class WipeTransition(BaseTransition):
    """
    Wipe/Reveal transition effect.
    
    Progressively reveals the new image as an invisible line
    moves across the screen. The reveal speed is determined by duration.
    """
    
    def __init__(self, duration_ms: int = 1000, direction: WipeDirection = WipeDirection.LEFT_TO_RIGHT):
        """
        Initialize wipe transition.
        
        Args:
            duration_ms: Duration in milliseconds
            direction: Wipe direction
        """
        super().__init__()
        
        self._duration_ms = duration_ms
        self._direction = direction
        self._display_label: Optional[QLabel] = None
        self._timer: Optional[QTimer] = None
        self._old_pixmap: Optional[QPixmap] = None
        self._new_pixmap: Optional[QPixmap] = None
        self._elapsed_ms = 0
        self._fps = 60
        
        logger.debug(f"WipeTransition created (duration={duration_ms}ms, direction={direction.value})")
    
    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap, 
              widget: QWidget) -> bool:
        """
        Start wipe transition.
        
        Args:
            old_pixmap: Previous image (can be None)
            new_pixmap: New image to display
            widget: Parent widget for display
        
        Returns:
            True if transition started successfully
        """
        if self._state == TransitionState.RUNNING:
            logger.warning("[FALLBACK] Transition already running")
            return False
        
        if not new_pixmap or new_pixmap.isNull():
            logger.error("Invalid new pixmap")
            self.error.emit("Invalid image")
            return False
        
        self._old_pixmap = old_pixmap
        self._new_pixmap = new_pixmap
        self._elapsed_ms = 0
        
        # If no old image, show immediately
        if not old_pixmap or old_pixmap.isNull():
            self._show_image_immediately(widget)
            return True
        
        # Create display label
        self._display_label = QLabel(widget)
        self._display_label.setGeometry(widget.rect())
        self._display_label.setScaledContents(False)
        self._display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._display_label.show()
        
        # Start at old image
        self._display_label.setPixmap(old_pixmap)
        
        # Start timer
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_frame)
        self._timer.start(1000 // self._fps)  # 60 FPS
        
        self._set_state(TransitionState.RUNNING)
        self.started.emit()
        
        logger.info(f"Wipe transition started (direction={self._direction.value})")
        return True
    
    def stop(self) -> None:
        """Stop the transition."""
        if self._state != TransitionState.RUNNING:
            return
        
        logger.debug("Stopping wipe transition")
        
        if self._timer:
            try:
                self._timer.stop()
                self._timer.deleteLater()
            except RuntimeError:
                pass
            self._timer = None
        
        self._set_state(TransitionState.CANCELLED)
    
    def cleanup(self) -> None:
        """Clean up transition resources."""
        logger.debug("Cleaning up wipe transition")
        
        self.stop()
        
        if self._display_label:
            try:
                self._display_label.deleteLater()
            except RuntimeError:
                pass
            self._display_label = None
        
        self._old_pixmap = None
        self._new_pixmap = None
    
    def _update_frame(self) -> None:
        """Update animation frame."""
        if not self._display_label or not self._old_pixmap or not self._new_pixmap:
            return
        
        self._elapsed_ms += 1000 // self._fps
        
        # Calculate progress (0.0 to 1.0)
        progress = min(self._elapsed_ms / self._duration_ms, 1.0)
        
        # Create composite image with wipe effect
        composite = self._create_wipe_frame(progress)
        
        try:
            self._display_label.setPixmap(composite)
        except RuntimeError:
            pass
        
        # Emit progress
        self._emit_progress(progress)
        
        # Check if complete
        if progress >= 1.0:
            self._finish_transition()
    
    def _create_wipe_frame(self, progress: float) -> QPixmap:
        """
        Create a frame with wipe effect.
        
        Args:
            progress: Animation progress (0.0 to 1.0)
        
        Returns:
            Composite pixmap with wipe applied
        """
        width = self._old_pixmap.width()
        height = self._old_pixmap.height()
        
        # Create result pixmap
        result = QPixmap(width, height)
        result.fill(Qt.GlobalColor.black)
        
        painter = QPainter(result)
        
        # Calculate wipe position based on direction
        if self._direction == WipeDirection.LEFT_TO_RIGHT:
            # Draw old image
            painter.drawPixmap(0, 0, self._old_pixmap)
            # Draw new image with clipping
            wipe_x = int(width * progress)
            painter.setClipRect(0, 0, wipe_x, height)
            painter.drawPixmap(0, 0, self._new_pixmap)
        
        elif self._direction == WipeDirection.RIGHT_TO_LEFT:
            # Draw old image
            painter.drawPixmap(0, 0, self._old_pixmap)
            # Draw new image with clipping
            wipe_x = int(width * (1.0 - progress))
            painter.setClipRect(wipe_x, 0, width - wipe_x, height)
            painter.drawPixmap(0, 0, self._new_pixmap)
        
        elif self._direction == WipeDirection.TOP_TO_BOTTOM:
            # Draw old image
            painter.drawPixmap(0, 0, self._old_pixmap)
            # Draw new image with clipping
            wipe_y = int(height * progress)
            painter.setClipRect(0, 0, width, wipe_y)
            painter.drawPixmap(0, 0, self._new_pixmap)
        
        elif self._direction == WipeDirection.BOTTOM_TO_TOP:
            # Draw old image
            painter.drawPixmap(0, 0, self._old_pixmap)
            # Draw new image with clipping
            wipe_y = int(height * (1.0 - progress))
            painter.setClipRect(0, wipe_y, width, height - wipe_y)
            painter.drawPixmap(0, 0, self._new_pixmap)
        
        painter.end()
        return result
    
    def _finish_transition(self) -> None:
        """Finish the transition."""
        if self._state != TransitionState.RUNNING:
            return
        
        logger.debug("Wipe transition finished")
        
        # Stop timer
        if self._timer:
            try:
                self._timer.stop()
                self._timer.deleteLater()
            except RuntimeError:
                pass
            self._timer = None
        
        # Show final image
        if self._display_label and self._new_pixmap:
            try:
                self._display_label.setPixmap(self._new_pixmap)
            except RuntimeError:
                pass
        
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        
        # Clean up immediately
        if self._display_label:
            try:
                self._display_label.deleteLater()
            except RuntimeError:
                pass
            self._display_label = None
    
    def _show_image_immediately(self, widget: QWidget) -> None:
        """Show new image immediately without transition."""
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("Image shown immediately (no old image)")
    
    def set_direction(self, direction: WipeDirection) -> None:
        """
        Set wipe direction.
        
        Args:
            direction: Wipe direction
        """
        self._direction = direction
        logger.debug(f"Wipe direction set to {direction.value}")
    
    def set_duration(self, duration_ms: int) -> None:
        """
        Set transition duration.
        
        Args:
            duration_ms: Duration in milliseconds
        """
        if duration_ms <= 0:
            logger.warning(f"[FALLBACK] Invalid duration {duration_ms}ms, using 1000ms")
            duration_ms = 1000
        
        self._duration_ms = duration_ms
        logger.debug(f"Duration set to {duration_ms}ms")
