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
    
    Reveals new image by randomly fading in blocks.
    Uses a grid of blocks that are revealed in random order.
    """
    
    def __init__(self, duration_ms: int = 2000, block_size: int = 50):
        """
        Initialize diffuse transition.
        
        Args:
            duration_ms: Total duration in milliseconds
            block_size: Size of each block in pixels
        """
        super().__init__(duration_ms)
        
        self._block_size = block_size
        self._widget: Optional[QWidget] = None
        self._old_pixmap: Optional[QPixmap] = None
        self._new_pixmap: Optional[QPixmap] = None
        self._display_label: Optional[QLabel] = None
        self._timer: Optional[QTimer] = None
        self._blocks: List[QRect] = []
        self._revealed_blocks: List[QRect] = []
        self._total_blocks = 0
        
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
            
            # Create display label
            self._display_label = QLabel(widget)
            self._display_label.setPixmap(old_pixmap)
            self._display_label.setGeometry(0, 0, width, height)
            self._display_label.show()
            
            # Calculate grid of blocks
            self._blocks = self._create_block_grid(width, height)
            self._total_blocks = len(self._blocks)
            
            # Shuffle blocks for random reveal
            random.shuffle(self._blocks)
            
            # Calculate interval between reveals
            if self._total_blocks > 0:
                interval_ms = max(10, self.duration_ms // self._total_blocks)
            else:
                interval_ms = 10
            
            # Create timer for block reveals
            self._timer = QTimer()
            self._timer.timeout.connect(self._reveal_next_block)
            self._timer.start(interval_ms)
            
            self._set_state(TransitionState.RUNNING)
            self.started.emit()
            
            logger.info(f"Diffuse transition started ({self.duration_ms}ms, {self._total_blocks} blocks)")
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
        
        # Delete display label
        if self._display_label:
            try:
                self._display_label.deleteLater()
            except RuntimeError:
                pass
            self._display_label = None
        
        self._widget = None
        self._old_pixmap = None
        self._new_pixmap = None
        self._blocks = []
        self._revealed_blocks = []
        self._total_blocks = 0
        
        if self._state not in [TransitionState.FINISHED, TransitionState.CANCELLED]:
            self._set_state(TransitionState.IDLE)
    
    def _create_block_grid(self, width: int, height: int) -> List[QRect]:
        """
        Create grid of blocks covering the widget.
        
        Args:
            width: Widget width
            height: Widget height
        
        Returns:
            List of QRect blocks
        """
        blocks = []
        
        cols = (width + self._block_size - 1) // self._block_size
        rows = (height + self._block_size - 1) // self._block_size
        
        for row in range(rows):
            for col in range(cols):
                x = col * self._block_size
                y = row * self._block_size
                
                # Calculate block size (may be smaller at edges)
                block_width = min(self._block_size, width - x)
                block_height = min(self._block_size, height - y)
                
                blocks.append(QRect(x, y, block_width, block_height))
        
        return blocks
    
    def _reveal_next_block(self) -> None:
        """Reveal the next block in the sequence."""
        if self._state != TransitionState.RUNNING:
            return
        
        if not self._blocks:
            # All blocks revealed
            self._finish_transition()
            return
        
        # Get next block
        block = self._blocks.pop(0)
        self._revealed_blocks.append(block)
        
        # Update display
        self._update_display()
        
        # Update progress
        if self._total_blocks > 0:
            progress = len(self._revealed_blocks) / self._total_blocks
            self._emit_progress(progress)
    
    def _update_display(self) -> None:
        """Update the display label with revealed blocks."""
        if not self._display_label or not self._old_pixmap or not self._new_pixmap:
            return
        
        # Create composite pixmap
        composite = QPixmap(self._old_pixmap.size())
        composite.fill(QColor(0, 0, 0, 0))
        
        painter = QPainter(composite)
        
        # Draw old image as base
        painter.drawPixmap(0, 0, self._old_pixmap)
        
        # Draw revealed blocks from new image
        for block in self._revealed_blocks:
            painter.drawPixmap(block.topLeft(), self._new_pixmap, block)
        
        painter.end()
        
        # Update label
        try:
            self._display_label.setPixmap(composite)
        except RuntimeError:
            pass  # Label deleted
    
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
        
        # Show final image
        if self._display_label and self._new_pixmap:
            try:
                self._display_label.setPixmap(self._new_pixmap)
            except RuntimeError:
                pass
        
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        
        # Cleanup resources
        self._timer = None
        
        if self._display_label:
            try:
                self._display_label.deleteLater()
            except RuntimeError:
                pass
            self._display_label = None
        
        self._widget = None
        self._old_pixmap = None
        self._new_pixmap = None
        self._blocks = []
        self._revealed_blocks = []
    
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
