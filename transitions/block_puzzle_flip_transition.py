"""
Block Puzzle Flip transition - 3D flip effect with grid.

Creates a grid of blocks that flip from old image to new image
with 3D rotation effect. This is the STAR FEATURE transition.
"""
import random
from typing import Optional, List
from PySide6.QtCore import QTimer, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor
from PySide6.QtWidgets import QWidget, QLabel

from transitions.base_transition import BaseTransition, TransitionState
from core.logging.logger import get_logger

logger = get_logger(__name__)


class FlipBlock:
    """Represents a single flipping block in the grid."""
    
    def __init__(self, rect: QRect, old_pixmap: QPixmap, new_pixmap: QPixmap):
        """
        Initialize flip block.
        
        Args:
            rect: Block rectangle
            old_pixmap: Old image pixmap
            new_pixmap: New image pixmap
        """
        self.rect = rect
        self.old_piece = old_pixmap.copy(rect)
        self.new_piece = new_pixmap.copy(rect)
        self.flip_progress = 0.0  # 0.0 = old, 1.0 = new
        self.is_flipping = False
        self.is_complete = False
    
    def get_current_pixmap(self) -> QPixmap:
        """
        Get current pixmap based on flip progress.
        
        Returns:
            Pixmap to display
        """
        if self.flip_progress < 0.5:
            # First half: show old image with horizontal squeeze
            scale_x = 1.0 - (self.flip_progress * 2.0)
            return self._scale_horizontal(self.old_piece, scale_x)
        else:
            # Second half: show new image with horizontal expand
            scale_x = (self.flip_progress - 0.5) * 2.0
            return self._scale_horizontal(self.new_piece, scale_x)
    
    def _scale_horizontal(self, pixmap: QPixmap, scale: float) -> QPixmap:
        """
        Scale pixmap horizontally (for flip effect).
        
        Args:
            pixmap: Source pixmap
            scale: Horizontal scale (0.0 to 1.0)
        
        Returns:
            Scaled pixmap
        """
        if scale <= 0.0:
            # Return transparent pixmap
            result = QPixmap(pixmap.size())
            result.fill(QColor(0, 0, 0, 0))
            return result
        
        width = int(pixmap.width() * scale)
        if width <= 0:
            width = 1
        
        # Scale horizontally
        from PySide6.QtCore import Qt
        scaled = pixmap.scaled(
            width, pixmap.height(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Center the scaled image
        result = QPixmap(pixmap.width(), pixmap.height())
        result.fill(QColor(0, 0, 0, 0))
        
        painter = QPainter(result)
        x_offset = (pixmap.width() - scaled.width()) // 2
        painter.drawPixmap(x_offset, 0, scaled)
        painter.end()
        
        return result


class BlockPuzzleFlipTransition(BaseTransition):
    """
    Block Puzzle Flip transition effect (STAR FEATURE).
    
    Creates a grid of blocks that flip with 3D effect from old to new image.
    Blocks flip in random order with configurable timing.
    """
    
    def __init__(self, duration_ms: int = 3000, grid_rows: int = 4, 
                 grid_cols: int = 6, flip_duration_ms: int = 500):
        """
        Initialize block puzzle flip transition.
        
        Args:
            duration_ms: Total duration for all flips
            grid_rows: Number of rows in grid
            grid_cols: Number of columns in grid
            flip_duration_ms: Duration for single block flip
        """
        super().__init__(duration_ms)
        
        self._grid_rows = grid_rows
        self._grid_cols = grid_cols
        self._flip_duration_ms = flip_duration_ms
        self._widget: Optional[QWidget] = None
        self._old_pixmap: Optional[QPixmap] = None
        self._new_pixmap: Optional[QPixmap] = None
        self._blocks: List[FlipBlock] = []
        self._flip_order: List[int] = []
        self._current_flip_index = 0
        self._timer: Optional[QTimer] = None
        self._flip_timer: Optional[QTimer] = None
        self._display_label: Optional[QLabel] = None
        
        logger.debug(f"BlockPuzzleFlipTransition created (duration={duration_ms}ms, "
                    f"grid={grid_rows}x{grid_cols}, flip_duration={flip_duration_ms}ms)")
    
    def start(self, old_pixmap: Optional[QPixmap], new_pixmap: QPixmap,
              widget: QWidget) -> bool:
        """
        Start block puzzle flip transition.
        
        Args:
            old_pixmap: Previous image (None if first image)
            new_pixmap: New image to flip to
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
            self._current_flip_index = 0
            
            # If no old image, just show new one immediately
            if not old_pixmap or old_pixmap.isNull():
                logger.debug("No old image, showing new image immediately")
                self._show_image_immediately()
                return True
            
            # Get widget dimensions
            width = widget.width()
            height = widget.height()
            
            # Create grid of blocks
            self._create_block_grid(width, height)
            
            # Create random flip order
            total_blocks = len(self._blocks)
            self._flip_order = list(range(total_blocks))
            random.shuffle(self._flip_order)
            
            # Calculate interval between block flips
            if total_blocks > 0:
                interval_ms = max(50, self.duration_ms // total_blocks)
            else:
                interval_ms = 50
            
            # Create display label for rendering
            self._display_label = QLabel(widget)
            self._display_label.setGeometry(0, 0, width, height)
            self._display_label.setPixmap(old_pixmap)
            self._display_label.show()
            
            # Start main timer for initiating flips
            self._timer = QTimer()
            self._timer.timeout.connect(self._start_next_flip)
            self._timer.start(interval_ms)
            
            # Start flip animation timer (60 FPS)
            self._flip_timer = QTimer()
            self._flip_timer.timeout.connect(self._update_flips)
            self._flip_timer.start(16)  # ~60 FPS
            
            self._set_state(TransitionState.RUNNING)
            self.started.emit()
            
            logger.info(f"Block puzzle flip started ({self.duration_ms}ms, {total_blocks} blocks)")
            return True
        
        except Exception as e:
            logger.exception(f"Failed to start block puzzle flip: {e}")
            self.error.emit(f"Transition failed: {e}")
            self.cleanup()
            return False
    
    def stop(self) -> None:
        """Stop transition immediately."""
        if self._state != TransitionState.RUNNING:
            return
        
        logger.debug("Stopping block puzzle flip")
        
        # Stop timers
        if self._timer:
            try:
                self._timer.stop()
            except RuntimeError:
                pass
        
        if self._flip_timer:
            try:
                self._flip_timer.stop()
            except RuntimeError:
                pass
        
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()
    
    def cleanup(self) -> None:
        """Clean up transition resources."""
        logger.debug("Cleaning up block puzzle flip")
        
        # Stop and delete timers
        if self._timer:
            try:
                self._timer.stop()
                self._timer.deleteLater()
            except RuntimeError:
                pass
            self._timer = None
        
        if self._flip_timer:
            try:
                self._flip_timer.stop()
                self._flip_timer.deleteLater()
            except RuntimeError:
                pass
            self._flip_timer = None
        
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
        self._flip_order = []
        self._current_flip_index = 0
        
        if self._state not in [TransitionState.FINISHED, TransitionState.CANCELLED]:
            self._set_state(TransitionState.IDLE)
    
    def _create_block_grid(self, width: int, height: int) -> None:
        """
        Create grid of flip blocks.
        
        Args:
            width: Widget width
            height: Widget height
        """
        self._blocks = []
        
        block_width = width // self._grid_cols
        block_height = height // self._grid_rows
        
        for row in range(self._grid_rows):
            for col in range(self._grid_cols):
                x = col * block_width
                y = row * block_height
                
                # Calculate block size (handle edges)
                w = block_width
                h = block_height
                
                if col == self._grid_cols - 1:
                    w = width - x
                if row == self._grid_rows - 1:
                    h = height - y
                
                rect = QRect(x, y, w, h)
                block = FlipBlock(rect, self._old_pixmap, self._new_pixmap)
                self._blocks.append(block)
    
    def _start_next_flip(self) -> None:
        """Start flipping the next block."""
        if self._state != TransitionState.RUNNING:
            return
        
        if self._current_flip_index >= len(self._flip_order):
            # All flips initiated, wait for completion
            if self._timer:
                try:
                    self._timer.stop()
                except RuntimeError:
                    pass
            return
        
        # Start next block flip
        block_index = self._flip_order[self._current_flip_index]
        if block_index < len(self._blocks):
            self._blocks[block_index].is_flipping = True
        
        self._current_flip_index += 1
        
        # Update progress
        if len(self._flip_order) > 0:
            progress = self._current_flip_index / len(self._flip_order)
            self._emit_progress(progress * 0.5)  # First half of progress
    
    def _update_flips(self) -> None:
        """Update all flipping blocks (animation step)."""
        if self._state != TransitionState.RUNNING:
            return
        
        # Update flip progress for all flipping blocks
        flip_increment = 1.0 / (self._flip_duration_ms / 16.0)  # Per frame
        
        all_complete = True
        completed_count = 0
        
        for block in self._blocks:
            if block.is_flipping and not block.is_complete:
                block.flip_progress += flip_increment
                
                if block.flip_progress >= 1.0:
                    block.flip_progress = 1.0
                    block.is_complete = True
                    block.is_flipping = False
                else:
                    all_complete = False
            
            if block.is_complete:
                completed_count += 1
        
        # Render current state
        self._render_scene()
        
        # Update second half of progress
        if len(self._blocks) > 0:
            completion_progress = completed_count / len(self._blocks)
            self._emit_progress(0.5 + (completion_progress * 0.5))
        
        # Check if all complete
        if all_complete and self._current_flip_index >= len(self._flip_order):
            self._finish_transition()
    
    def _render_scene(self) -> None:
        """Render current state of all blocks."""
        if not self._display_label or not self._old_pixmap:
            return
        
        # Create composite pixmap
        composite = QPixmap(self._old_pixmap.size())
        composite.fill(QColor(0, 0, 0, 0))
        
        painter = QPainter(composite)
        
        # Render each block
        for block in self._blocks:
            pixmap = block.get_current_pixmap()
            painter.drawPixmap(block.rect.topLeft(), pixmap)
        
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
        
        logger.debug("Block puzzle flip finished")
        
        # Stop timers
        if self._timer:
            try:
                self._timer.stop()
            except RuntimeError:
                pass
        
        if self._flip_timer:
            try:
                self._flip_timer.stop()
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
        
        # Clean up resources immediately
        self._timer = None
        self._flip_timer = None
        self._blocks = []
        
        if self._display_label:
            try:
                self._display_label.deleteLater()
            except RuntimeError:
                pass
            self._display_label = None
    
    def _show_image_immediately(self) -> None:
        """Show new image immediately without transition."""
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        logger.debug("Image shown immediately")
    
    def set_grid_size(self, rows: int, cols: int) -> None:
        """
        Set grid size.
        
        Args:
            rows: Number of rows
            cols: Number of columns
        """
        if rows <= 0 or cols <= 0:
            logger.warning(f"[FALLBACK] Invalid grid size {rows}x{cols}, using 4x6")
            rows, cols = 4, 6
        
        self._grid_rows = rows
        self._grid_cols = cols
        logger.debug(f"Grid size set to {rows}x{cols}")
    
    def set_flip_duration(self, duration_ms: int) -> None:
        """
        Set duration for single block flip.
        
        Args:
            duration_ms: Flip duration in milliseconds
        """
        if duration_ms <= 0:
            logger.warning(f"[FALLBACK] Invalid flip duration {duration_ms}ms, using 500ms")
            duration_ms = 500
        
        self._flip_duration_ms = duration_ms
        logger.debug(f"Flip duration set to {duration_ms}ms")
