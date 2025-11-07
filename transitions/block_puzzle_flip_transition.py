"""
Block Puzzle Flip transition - 3D flip effect with grid.

Creates a grid of blocks that flip from old image to new image
with 3D rotation effect. This is the STAR FEATURE transition.
"""
import random
from typing import Optional, List
from PySide6.QtCore import QTimer, QRect, Qt
from PySide6.QtGui import QPixmap, QRegion
from PySide6.QtWidgets import QWidget, QLabel

from transitions.base_transition import BaseTransition, TransitionState
from core.animation.types import EasingCurve
from core.logging.logger import get_logger

logger = get_logger(__name__)


class FlipBlock:
    """Represents a single flipping block in the grid (rect + flip state only)."""
    
    def __init__(self, rect: QRect):
        """Initialize flip block with its logical rectangle only."""
        self.rect = rect
        self.flip_progress = 0.0  # 0.0 = old, 1.0 = new
        self.is_flipping = False
        self.is_complete = False
        # Randomized start threshold in [0, 1) to stagger starts over the global timeline
        self.start_threshold: float = random.random()
        self.started: bool = False


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
        self._timer: Optional[QTimer] = None  # legacy
        self._flip_timer: Optional[QTimer] = None  # legacy
        self._animation_id: Optional[str] = None
        self._display_label: Optional[QLabel] = None
        
        # FIX: Use ResourceManager for Qt object lifecycle
        try:
            from core.resources.manager import ResourceManager
            self._resource_manager = ResourceManager()
        except Exception:
            self._resource_manager = None
        
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
            
            # Use fitted pixmaps DIRECTLY from DisplayWidget (Crossfade pattern)
            # DO NOT re-fit! They are already processed by ImageProcessor
            self._fitted_old = old_pixmap
            self._fitted_new = new_pixmap
            
            # Create grid of blocks based on the widget logical size
            # (pixmaps are already fitted to widget by ImageProcessor)
            self._create_block_grid(width, height, old_pixmap, new_pixmap)
            
            # Create random flip order
            total_blocks = len(self._blocks)
            self._flip_order = list(range(total_blocks))
            random.shuffle(self._flip_order)
            
            # Note: interval logic handled by AnimationManager progression
            
            # Two-label pattern (old below, new above with evolving mask)
            self._old_label = QLabel(widget)
            self._old_label.setGeometry(0, 0, width, height)
            self._old_label.setScaledContents(False)
            self._old_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._old_label.setPixmap(old_pixmap)
            self._old_label.show()

            self._new_label = QLabel(widget)
            self._new_label.setGeometry(0, 0, width, height)
            self._new_label.setScaledContents(False)
            self._new_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._new_label.setPixmap(new_pixmap)
            # Start fully hidden via empty mask
            self._new_label.setMask(QRegion())
            self._new_label.show()
            
            # Drive via centralized AnimationManager
            am = self._get_animation_manager(widget)
            # Two-phase timeline: start all blocks over duration_ms, then allow
            # an extra flip_duration_ms for the last-started blocks to finish.
            self._total_duration_ms = max(1, int(self.duration_ms + self._flip_duration_ms))
            duration_sec = max(0.001, self._total_duration_ms / 1000.0)
            self._total_dur_sec = duration_sec
            self._last_progress = 0.0
            self._animation_id = am.animate_custom(
                duration=duration_sec,
                easing=EasingCurve.LINEAR,
                update_callback=lambda p, total=total_blocks: self._on_anim_update(p, total),
                on_complete=lambda: self._finish_transition(),
            )
            
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
        
        # Cancel central animation
        if self._animation_id and self._widget:
            try:
                am = self._get_animation_manager(self._widget)
                am.cancel_animation(self._animation_id)
            except Exception:
                pass
        
        self._set_state(TransitionState.CANCELLED)
        self._emit_progress(1.0)
        self.finished.emit()
    
    def cleanup(self) -> None:
        """Clean up transition resources."""
        logger.debug("Cleaning up block puzzle flip")
        
        # Cancel animation
        if self._animation_id and self._widget:
            try:
                am = self._get_animation_manager(self._widget)
                am.cancel_animation(self._animation_id)
            except Exception:
                pass
            self._animation_id = None
        
        # Delete display label
        if self._display_label:
            try:
                self._display_label.deleteLater()
            except RuntimeError:
                pass
        
        self._widget = None
        self._old_pixmap = None
        self._new_pixmap = None
        self._blocks = []
        self._flip_order = []
        self._current_flip_index = 0
        
        if self._state not in [TransitionState.FINISHED, TransitionState.CANCELLED]:
            self._set_state(TransitionState.IDLE)
    
    def _create_block_grid(self, width: int, height: int, fitted_old: QPixmap, fitted_new: QPixmap) -> None:
        """
        Create grid of flip blocks.
        
        Args:
            width: Widget width
            height: Widget height
        """
        self._blocks = []
        
        block_width = max(1, width // self._grid_cols)
        block_height = max(1, height // self._grid_rows)
        
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
                block = FlipBlock(rect)
                self._blocks.append(block)

        # Ensure full coverage (edges clamped in creation)
    
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
    
    def _on_anim_update(self, progress: float, total_blocks: int) -> None:
        """AnimationManager update callback to drive block initiation and flip progress."""
        if self._state != TransitionState.RUNNING:
            return
        progress = max(0.0, min(1.0, progress))
        # Map total progress [0..1] over total_duration to a start-phase progress
        # that reaches 1.0 at t = duration_ms, ensuring all blocks start early.
        total_ms = max(1, getattr(self, "_total_duration_ms", self.duration_ms))
        t_ms = progress * total_ms
        start_phase_progress = min(1.0, t_ms / max(1, self.duration_ms))
        # Initiate flips based on each block's randomized start threshold
        for block in self._blocks:
            if (not getattr(block, 'started', False)) and start_phase_progress >= getattr(block, 'start_threshold', 0.0):
                block.is_flipping = True
                block.started = True
        
        # Advance flipping blocks based on delta progress
        delta = progress - getattr(self, "_last_progress", 0.0)
        self._last_progress = progress
        if delta < 0:
            delta = 0
        # Convert delta to seconds over TOTAL duration (includes drain for last blocks)
        total_dur_sec = max(0.001, getattr(self, "_total_dur_sec", self.duration_ms / 1000.0))
        delta_sec = delta * total_dur_sec
        flip_dur_sec = max(0.001, self._flip_duration_ms / 1000.0)
        flip_increment = delta_sec / flip_dur_sec
        
        all_complete = True
        completed_count = 0
        for block in self._blocks:
            if block.is_flipping and not block.is_complete:
                block.flip_progress += flip_increment
                if block.flip_progress >= 1.0:
                    block.flip_progress = 1.0
                    block.is_complete = True
                    block.is_flipping = False
            # Any block not complete means we are not done yet, regardless of flip state
            if not block.is_complete:
                all_complete = False
            else:
                completed_count += 1
        
        # If we've reached the end of the global timeline, force-complete any stragglers
        if progress >= 1.0:
            for block in self._blocks:
                if not block.is_complete:
                    block.flip_progress = 1.0
                    block.is_complete = True
                    block.is_flipping = False
            self._render_scene(widget_sized=True)
            self._emit_progress(1.0)
            self._finish_transition()
            return
        
        self._render_scene(widget_sized=True)
        if len(self._blocks) > 0:
            completion_progress = completed_count / len(self._blocks)
            self._emit_progress(0.5 + (completion_progress * 0.5))
        if all_complete:
            self._finish_transition()
    
    def _render_scene(self, widget_sized: bool = False) -> None:
        """Update mask on the new label based on block flip progress."""
        if not hasattr(self, "_new_label") or self._new_label is None:
            return
        # Build union region of revealed areas for the new image
        region = QRegion()
        for block in self._blocks:
            p = max(0.0, min(1.0, block.flip_progress))
            if p <= 0.0:
                continue
            # Simulate horizontal center flip: reveal rectangle growing from center
            r = block.rect
            reveal_w = max(1, int(r.width() * p))
            dx = r.x() + (r.width() - reveal_w) // 2
            reveal_rect = QRect(dx, r.y(), reveal_w, r.height())
            region = region.united(QRegion(reveal_rect))
        try:
            self._new_label.setMask(region)
        except RuntimeError:
            return
    
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
        
        # Ensure new image fully visible and clean up labels
        if hasattr(self, "_new_label") and self._new_label:
            try:
                self._new_label.clearMask()
            except RuntimeError:
                pass
        
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        
        # Clean up resources immediately
        self._blocks = []
        
        if hasattr(self, "_old_label") and self._old_label:
            try:
                self._old_label.deleteLater()
            except RuntimeError:
                pass
            self._old_label = None
        if hasattr(self, "_new_label") and self._new_label:
            try:
                self._new_label.deleteLater()
            except RuntimeError:
                pass
            self._new_label = None
    
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
