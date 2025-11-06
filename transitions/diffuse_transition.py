"""
Diffuse transition - random block reveal animation.

Reveals new image by randomly fading in blocks over time.
"""
import random
from typing import Optional, List
from PySide6.QtCore import QTimer, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor
from PySide6.QtWidgets import QWidget, QLabel

from transitions.base_transition import BaseTransition, TransitionState
from core.logging.logger import get_logger

logger = get_logger(__name__)


class DiffuseTransition(BaseTransition):
    """
    Diffuse transition effect.
    
    Reveals new image through gradual granular diffusion.
    Uses small pixels that fade in randomly across the entire image,
    creating a smooth, organic diffusion effect.
    Speed slows down proportionally with duration for optimal timing.
    """
    
    def __init__(self, duration_ms: int = 2000, block_size: int = 8):
        """
        Initialize diffuse transition.
        
        Args:
            duration_ms: Total duration in milliseconds
            block_size: Size of each block in pixels
        """
        super().__init__(duration_ms)
        
        self._block_size = block_size
        self._widget: Optional[QWidget] = None
        self._old_label: Optional[QLabel] = None
        self._new_label: Optional[QLabel] = None
        self._timer: Optional[QTimer] = None
        self._elapsed_ms = 0
        self._fps = 60
        
        # Diffusion state
        self._pixel_grid: List[tuple] = []  # (x, y, revealed)
        self._reveal_rate = 0.0  # Pixels to reveal per frame
        
        logger.debug(f"DiffuseTransition created (duration={duration_ms}ms, block_size={block_size})")
    
    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap,
              widget: QWidget) -> bool:
        """
        Start diffuse transition.
        
        Args:
            old_pixmap: Previous image (None if first image)
            new_pixmap: New image to diffuse to
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
            self._old_pixmap = old_pixmap
            self._revealed_blocks = []
            
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
            self._old_label.setScaledContents(False)
            self._old_label.show()
            
            self._new_label = QLabel(widget)
            self._new_label.setPixmap(new_pixmap)
            self._new_label.setGeometry(0, 0, width, height)
            self._new_label.setScaledContents(False)
            self._new_label.show()
            self._new_label.lower()  # Behind old label initially
            
            # Create pixel grid for granular diffusion
            self._pixel_grid = self._create_pixel_grid(width, height)
            total_pixels = len(self._pixel_grid)
            
            # Calculate reveal rate (pixels per frame) based on duration
            # Slows down for longer durations to always finish on time
            total_frames = (self.duration_ms / 1000.0) * self._fps
            self._reveal_rate = total_pixels / total_frames if total_frames > 0 else total_pixels
            
            # Ensure minimum reveal rate for short durations
            self._reveal_rate = max(1.0, self._reveal_rate)
            
            self._elapsed_ms = 0
            
            # Create timer for animation
            self._timer = QTimer()
            self._timer.timeout.connect(self._update_diffusion)
            interval_ms = 1000 // self._fps
            self._timer.start(interval_ms)
            
            self._set_state(TransitionState.RUNNING)
            self.started.emit()
            
            logger.info(f"Diffuse transition started ({self.duration_ms}ms, {total_pixels} pixels, rate={self._reveal_rate:.1f}/frame)")
            return True
        
        except Exception as e:
            logger.exception(f"Failed to start diffuse transition: {e}")
            self.error.emit(f"Transition failed: {e}")
            self.cleanup()
            return False
    
    def stop(self) -> None:
        """Stop transition immediately."""
        if self._state != TransitionState.RUNNING:
            return
        
        logger.debug("Stopping diffuse transition")
        
        # Stop timer
        if self._timer:
            try:
                self._timer.stop()
            except RuntimeError:
                pass
        
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()
    
    def cleanup(self) -> None:
        """Clean up transition resources."""
        logger.debug("Cleaning up diffuse transition")
        
        # Stop and delete timer
        if self._timer:
            try:
                self._timer.stop()
                self._timer.deleteLater()
            except RuntimeError:
                pass
            self._timer = None
        
        # Delete labels
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
        self._old_pixmap = None
        self._new_pixmap = None
        self._pixel_grid = []
        
        if self._state not in [TransitionState.FINISHED, TransitionState.CANCELLED]:
            self._set_state(TransitionState.IDLE)
    
    def _create_pixel_grid(self, width: int, height: int) -> List[tuple]:
        """
        Create grid of pixel blocks for diffusion.
        
        Args:
            width: Widget width
            height: Widget height
        
        Returns:
            List of (x, y) tuples in randomized order
        """
        pixels = []
        
        # Use smaller block size for granular effect
        cols = (width + self._block_size - 1) // self._block_size
        rows = (height + self._block_size - 1) // self._block_size
        
        for row in range(rows):
            for col in range(cols):
                x = col * self._block_size
                y = row * self._block_size
                pixels.append((x, y))
        
        # Randomize order for diffusion effect
        random.shuffle(pixels)
        
        return pixels
    
    def _update_diffusion(self) -> None:
        """Update diffusion animation (called by timer)."""
        if self._state != TransitionState.RUNNING:
            return
        
        # Update elapsed time
        interval_ms = 1000 // self._fps
        self._elapsed_ms += interval_ms
        
        # Calculate progress
        progress = min(1.0, self._elapsed_ms / self.duration_ms)
        
        # Reveal pixels for this frame
        pixels_to_reveal = int(self._reveal_rate)
        if random.random() < (self._reveal_rate - pixels_to_reveal):
            pixels_to_reveal += 1  # Fractional part
        
        # Check if finished
        if progress >= 1.0 or not self._pixel_grid:
            self._finish_transition()
            return
        
        # Reveal pixels by making them transparent in old label
        self._reveal_pixels(pixels_to_reveal)
        
        # Emit progress
        self._emit_progress(progress)
    
    def _reveal_pixels(self, count: int) -> None:
        """
        Reveal pixels by punching holes in old image.
        
        Args:
            count: Number of pixels to reveal
        """
        if not self._old_label or not self._old_pixmap:
            return
        
        # Get current pixmap from old label
        current = self._old_label.pixmap()
        if not current or current.isNull():
            current = self._old_pixmap.copy()
        else:
            current = current.copy()
        
        painter = QPainter(current)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        
        # Reveal pixels (punch holes)
        revealed = 0
        while revealed < count and self._pixel_grid:
            x, y = self._pixel_grid.pop(0)
            # Draw transparent block
            painter.fillRect(x, y, self._block_size, self._block_size, QColor(0, 0, 0, 0))
            revealed += 1
        
        painter.end()
        
        # Update old label
        try:
            self._old_label.setPixmap(current)
        except RuntimeError:
            pass
    
    def _finish_transition(self) -> None:
        """Finish the transition."""
        if self._state != TransitionState.RUNNING:
            return
        
        logger.debug("Diffuse animation finished")
        
        # Stop timer
        if self._timer:
            try:
                self._timer.stop()
            except RuntimeError:
                pass
        
        # Hide old label to reveal new image completely
        if self._old_label:
            try:
                self._old_label.hide()
            except RuntimeError:
                pass
        
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        
        # Note: Labels cleaned up in cleanup() method
    
    def _show_image_immediately(self) -> None:
        """Show new image immediately without transition."""
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("Image shown immediately")
    
    def set_block_size(self, size: int) -> None:
        """
        Set block size for diffuse effect.
        
        Args:
            size: Block size in pixels
        """
        if size <= 0:
            logger.warning(f"[FALLBACK] Invalid block size {size}, using 50")
            size = 50
        
        self._block_size = size
        logger.debug(f"Block size set to {size}px")
