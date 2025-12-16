"""
Block Puzzle Flip transition - 3D flip effect with grid.

Creates a grid of blocks that flip from old image to new image
with 3D rotation effect. This is the STAR FEATURE transition.
"""
import random
import math
from typing import Optional, List
from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from transitions.base_transition import BaseTransition, TransitionState
from core.animation.types import EasingCurve
from core.logging.logger import get_logger
from .slide_transition import SlideDirection

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


class _BlockFlipWidget(QWidget):
    """Custom widget that paints block flip using QPainter (no OpenGL, no masks)."""
    
    def __init__(self, parent: QWidget, old_pixmap: QPixmap, new_pixmap: QPixmap, blocks: List[FlipBlock]):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception:
            pass
        
        self._old = old_pixmap
        self._new = new_pixmap
        self._blocks = blocks
    
    def set_blocks(self, blocks: List[FlipBlock]) -> None:
        """Update blocks and trigger repaint."""
        self._blocks = blocks
        self.update()
    
    def paintEvent(self, event) -> None:  # type: ignore[override]
        """Paint old pixmap fully, then draw new pixmap blocks based on flip progress."""
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            target = self.rect()
            
            # Draw old image fully
            if self._old and not self._old.isNull():
                p.setOpacity(1.0)
                p.drawPixmap(target, self._old)
            
            # Draw new image for each flipped block
            if self._new and not self._new.isNull():
                direction = getattr(self, "_direction", None)
                for block in self._blocks:
                    progress = max(0.0, min(1.0, block.flip_progress))
                    if progress <= 0.0:
                        continue

                    eased = 0.5 - 0.5 * math.cos(math.pi * progress)

                    # Base rectangular reveal used for non-directional mode
                    # and as the final full-block clip once the flip has
                    # completed.
                    r = block.rect
                    reveal_w = max(1, int(r.width() * eased))
                    dx = r.x() + (r.width() - reveal_w) // 2
                    reveal_rect = QRect(dx, r.y(), reveal_w, r.height())

                    p.save()
                    # Triangle prototype: when a direction is configured and
                    # the block has not yet fully completed, use a triangular
                    # clip aligned with the wave direction so each block
                    # appears as a wedge pointing along the reveal.
                    use_triangle = (
                        direction is not None
                        and hasattr(direction, "__class__")
                        and progress < 0.999
                    )
                    if use_triangle:
                        path = QPainterPath()
                        if direction == SlideDirection.LEFT:
                            # Wave travels left→right, base on left edge.
                            x0 = r.x()
                            y0 = r.y()
                            x1 = r.x()
                            y1 = r.y() + r.height()
                            apex_x = r.x() + int(r.width() * eased)
                            if apex_x < r.x():
                                apex_x = r.x()
                            if apex_x > r.x() + r.width():
                                apex_x = r.x() + r.width()
                            apex_y = r.y() + r.height() // 2
                            path.moveTo(x0, y0)
                            path.lineTo(x1, y1)
                            path.lineTo(apex_x, apex_y)
                            path.closeSubpath()
                        elif direction == SlideDirection.RIGHT:
                            # Wave travels right→left, base on right edge.
                            right_x = r.x() + r.width()
                            x0 = right_x
                            y0 = r.y()
                            x1 = right_x
                            y1 = r.y() + r.height()
                            apex_x = right_x - int(r.width() * eased)
                            if apex_x < r.x():
                                apex_x = r.x()
                            if apex_x > right_x:
                                apex_x = right_x
                            apex_y = r.y() + r.height() // 2
                            path.moveTo(x0, y0)
                            path.lineTo(x1, y1)
                            path.lineTo(apex_x, apex_y)
                            path.closeSubpath()
                        elif direction == SlideDirection.DOWN:
                            # Wave travels top→bottom, base on top edge.
                            x0 = r.x()
                            y0 = r.y()
                            x1 = r.x() + r.width()
                            y1 = r.y()
                            apex_y = r.y() + int(r.height() * eased)
                            if apex_y < r.y():
                                apex_y = r.y()
                            if apex_y > r.y() + r.height():
                                apex_y = r.y() + r.height()
                            apex_x = r.x() + r.width() // 2
                            path.moveTo(x0, y0)
                            path.lineTo(x1, y1)
                            path.lineTo(apex_x, apex_y)
                            path.closeSubpath()
                        elif direction == SlideDirection.UP:
                            # Wave travels bottom→top, base on bottom edge.
                            bottom_y = r.y() + r.height()
                            x0 = r.x()
                            y0 = bottom_y
                            x1 = r.x() + r.width()
                            y1 = bottom_y
                            apex_y = bottom_y - int(r.height() * eased)
                            if apex_y < r.y():
                                apex_y = r.y()
                            if apex_y > bottom_y:
                                apex_y = bottom_y
                            apex_x = r.x() + r.width() // 2
                            path.moveTo(x0, y0)
                            path.lineTo(x1, y1)
                            path.lineTo(apex_x, apex_y)
                            path.closeSubpath()
                        else:
                            path = QPainterPath()

                        if not path.isEmpty():
                            p.setClipPath(path)
                        else:
                            p.setClipRect(reveal_rect)
                    else:
                        p.setClipRect(reveal_rect)

                    p.setOpacity(1.0)
                    p.drawPixmap(target, self._new)
                    p.restore()
        finally:
            p.end()


class BlockPuzzleFlipTransition(BaseTransition):
    """
    Block Puzzle Flip transition effect (STAR FEATURE).
    
    Creates a grid of blocks that flip with 3D effect from old to new image.
    Blocks flip in random order with configurable timing.
    """
    
    def __init__(
        self,
        duration_ms: int = 3000,
        grid_rows: int = 4,
        grid_cols: int = 6,
        flip_duration_ms: int = 500,
        direction: Optional[SlideDirection] = None,
    ) -> None:
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
        self._animation_id: Optional[str] = None
        self._overlay: Optional[_BlockFlipWidget] = None
        self._timer: Optional[QTimer] = None
        self._flip_timer: Optional[QTimer] = None
        # Optional direction bias reused from the Slide direction model so
        # blocks can flip in a wave from the chosen edge when configured.
        self._direction: Optional[SlideDirection] = direction
        
        logger.debug(f"BlockPuzzleFlipTransition created (duration={duration_ms}ms, "
                    f"grid={grid_rows}x{grid_cols}, flip_duration={flip_duration_ms}ms)")
    
    def get_expected_duration_ms(self) -> int:
        total = getattr(self, "_total_duration_ms", None)
        if isinstance(total, (int, float)) and total > 0:
            return int(total)
        return self.duration_ms
    
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
            
            # Begin telemetry tracking for animated block puzzle flip
            self._mark_start()

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
            
            # CRITICAL: Create/reuse QPainter overlay widget (replaces old label approach)
            overlay = getattr(widget, "_srpss_sw_blockflip_overlay", None)
            if overlay is None or not isinstance(overlay, _BlockFlipWidget):
                logger.debug("[SW BLOCK] Creating persistent QPainter overlay")
                overlay = _BlockFlipWidget(widget, old_pixmap, new_pixmap, self._blocks)
                setattr(overlay, "_direction", self._direction)
                overlay.setGeometry(0, 0, width, height)
                setattr(widget, "_srpss_sw_blockflip_overlay", overlay)
                if self._resource_manager:
                    try:
                        self._resource_manager.register_qt(overlay, description="SW Block QPainter overlay")
                    except Exception:
                        pass
            else:
                logger.debug("[SW BLOCK] Reusing persistent QPainter overlay")
                # Update pixmaps and blocks
                overlay._old = old_pixmap
                overlay._new = new_pixmap
                overlay.set_blocks(self._blocks)
                setattr(overlay, "_direction", self._direction)
                overlay.setGeometry(0, 0, width, height)
            
            # Show overlay
            if not overlay.isVisible():
                overlay.show()
            try:
                overlay.raise_()
            except Exception:
                pass
            
            # Keep clock widget above overlay if present
            try:
                if hasattr(widget, "clock_widget") and getattr(widget, "clock_widget"):
                    widget.clock_widget.raise_()
            except Exception:
                pass
            
            # Store reference
            self._overlay = overlay

            # Present initial frame synchronously to avoid a one-frame flash
            try:
                widget.update()
            except Exception:
                pass
            
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
        
        # Note: overlay is persistent and managed by parent widget
        
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
        
        # Calculate square blocks based on aspect ratio
        # Use cols as base (doubled for more blocks), calculate rows to maintain square aspect
        base_cols = self._grid_cols * 2  # Double the blocks
        aspect_ratio = height / max(1, width)
        calculated_rows = max(2, int(round(base_cols * aspect_ratio)))
        
        # Use calculated rows for square blocks
        effective_rows = calculated_rows
        effective_cols = base_cols
        
        logger.debug(f"[SW BLOCK] Grid: {effective_cols}x{effective_rows} (aspect={aspect_ratio:.2f}, square blocks)")
        
        block_width = max(1, width // effective_cols)
        block_height = max(1, height // effective_rows)
        
        for row in range(effective_rows):
            for col in range(effective_cols):
                x = col * block_width
                y = row * block_height
                
                # Calculate block size (handle edges)
                w = block_width
                h = block_height
                
                if col == effective_cols - 1:
                    w = width - x
                if row == effective_rows - 1:
                    h = height - y
                
                rect = QRect(x, y, w, h)
                block = FlipBlock(rect)

                # Apply an optional direction bias so blocks begin flipping in
                # a wave from the selected edge (Left/Right/Top/Bottom), while
                # retaining slight jitter so the effect does not look overly
                # mechanical. When no direction is configured we keep the
                # original fully-random thresholds.
                if self._direction is not None:
                    base = 0.0
                    # Horizontal bias (Left/Right)
                    if self._direction == SlideDirection.LEFT:
                        # "Left to Right" – start at the left edge.
                        if effective_cols > 1:
                            base = col / float(effective_cols - 1)
                    elif self._direction == SlideDirection.RIGHT:
                        # "Right to Left" – start at the right edge.
                        if effective_cols > 1:
                            base = (effective_cols - 1 - col) / float(effective_cols - 1)
                    # Vertical bias (Top/Bottom)
                    elif self._direction == SlideDirection.DOWN:
                        # "Top to Bottom" – start at the top edge.
                        if effective_rows > 1:
                            base = row / float(effective_rows - 1)
                    elif self._direction == SlideDirection.UP:
                        # "Bottom to Top" – start at the bottom edge.
                        if effective_rows > 1:
                            base = (effective_rows - 1 - row) / float(effective_rows - 1)

                    # Small jitter so neighbouring blocks do not all start at
                    # exactly the same moment; scaled by grid density so the
                    # wavefront remains visually coherent.
                    span = max(effective_cols, effective_rows)
                    jitter_span = 0.0
                    if span > 0:
                        jitter_span = 0.18 / float(span)
                    if jitter_span > 0.0:
                        base += random.uniform(-jitter_span, jitter_span)
                    if base < 0.0:
                        base = 0.0
                    elif base > 1.0:
                        base = 1.0
                    block.start_threshold = base

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
        """Update QPainter overlay based on block flip progress."""
        if not self._overlay:
            return
        # Just trigger repaint - overlay will read block states in paintEvent
        try:
            self._overlay.update()
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
        
        # Ensure new image fully visible - set all blocks to complete
        for block in self._blocks:
            block.flip_progress = 1.0
            block.is_complete = True
        # Trigger final paint
        if self._overlay:
            try:
                self._overlay.update()
            except RuntimeError:
                pass
        
        # End telemetry tracking for successful completion
        self._mark_end()
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        
        # Clean up resources immediately
        self._blocks = []
        
        # Hide persistent overlay (don't delete - it'll be reused)
        if self._overlay:
            try:
                self._overlay.hide()
            except RuntimeError:
                pass
            self._overlay = None
    
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
