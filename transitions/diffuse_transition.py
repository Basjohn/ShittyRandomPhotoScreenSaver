"""
Diffuse transition - random block reveal animation.

Reveals new image by randomly fading in blocks over time.
"""
import random
from typing import Optional, List
from PySide6.QtCore import Qt
from core.animation.types import EasingCurve
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
    
    def __init__(self, duration_ms: int = 2000, block_size: int = 8, shape: str = 'Rectangle'):
        """
        Initialize diffuse transition.

        Args:
            duration_ms: Total duration in milliseconds
            block_size: Size of each block in pixels
            shape: Shape type ('Rectangle', 'Membrane')
        """
        super().__init__(duration_ms)
        
        self._block_size = block_size
        self._widget: Optional[QWidget] = None
        self._old_label: Optional[QLabel] = None
        self._new_label: Optional[QLabel] = None
        self._animation_id: Optional[str] = None
        self._timer = None
        self._elapsed_ms = 0
        self._fps = 60
        
        # FIX: Initialize pixmap attributes to prevent AttributeError
        self._old_pixmap: Optional[QPixmap] = None
        self._new_pixmap: Optional[QPixmap] = None
        
        # Diffusion state
        self._pixel_grid: List[tuple] = []  # (x, y, revealed)
        self._reveal_rate = 0.0  # Pixels to reveal per frame
        
        # Clamp initial shape to the supported set so legacy settings do not
        # request shapes that are no longer available.
        if shape not in ("Rectangle", "Membrane"):
            shape = "Rectangle"
        self._shape = shape
        logger.debug(f"DiffuseTransition created (duration={duration_ms}ms, block_size={block_size}, shape={shape})")
    
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
            # FIX: Removed unused _revealed_blocks variable - _pixel_grid is used instead
            
            # If no old image, just show new one immediately
            if not old_pixmap or old_pixmap.isNull():
                logger.debug("No old image, showing new image immediately")
                self._show_image_immediately()
                return True
            
            # Begin telemetry tracking for animated diffuse
            self._mark_start()

            # Get widget dimensions
            width = widget.width()
            height = widget.height()
            
            # Pre-fit pixmaps to widget to ensure 1:1 geometry and alpha pipeline
            fitted_old = self._fit_pixmap_to_widget(old_pixmap, widget)
            fitted_new = self._fit_pixmap_to_widget(new_pixmap, widget)
            
            # Labels sized to widget; use fitted pixmaps (no scaledContents to avoid artifacts)
            self._old_label = QLabel(widget)
            self._old_label.setPixmap(fitted_old)
            self._old_label.setGeometry(0, 0, width, height)
            self._old_label.setScaledContents(False)
            self._old_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._old_label.setStyleSheet("background: transparent;")
            self._old_label.show()
            if self._resource_manager:
                try:
                    self._resource_manager.register_qt(self._old_label, description="DiffuseTransition old label")
                except Exception:
                    pass
            
            self._new_label = QLabel(widget)
            self._new_label.setPixmap(fitted_new)
            self._new_label.setGeometry(0, 0, width, height)
            self._new_label.setScaledContents(False)
            self._new_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._new_label.setStyleSheet("background: transparent;")
            self._new_label.show()
            self._new_label.lower()  # Behind old label initially
            if self._resource_manager:
                try:
                    self._resource_manager.register_qt(self._new_label, description="DiffuseTransition new label")
                except Exception:
                    pass
            
            # Create pixel grid for granular diffusion
            self._pixel_grid = self._create_pixel_grid(width, height)
            total_pixels = len(self._pixel_grid)
            self._total_pixels = total_pixels
            
            # Calculate reveal rate (pixels per frame) based on duration
            # Slows down for longer durations to always finish on time
            total_frames = (self.duration_ms / 1000.0) * self._fps
            self._reveal_rate = total_pixels / total_frames if total_frames > 0 else total_pixels
            
            # Ensure minimum reveal rate for short durations
            self._reveal_rate = max(1.0, self._reveal_rate)
            
            self._elapsed_ms = 0
            
            # Drive via centralized AnimationManager (no raw QTimer)
            am = self._get_animation_manager(widget)
            duration_sec = max(0.001, self.duration_ms / 1000.0)
            # Derive per-frame reveal based on 60fps
            self._last_progress = 0.0
            self._animation_id = am.animate_custom(
                duration=duration_sec,
                easing=EasingCurve.LINEAR,
                update_callback=lambda p: self._on_anim_update(p),
                on_complete=lambda: self._on_anim_complete(),
            )
            
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
        
        # Cancel animation
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
        logger.debug("Cleaning up diffuse transition")
        
        # Cancel animation
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
        self._timer = None
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
    
    def _on_anim_update(self, progress: float) -> None:
        """AnimationManager update callback for diffusion progress."""
        if self._state != TransitionState.RUNNING:
            return
        # Reveal proportionally to progress so we don't dump the remainder at the end
        progress = max(0.0, min(1.0, progress))
        total = getattr(self, "_total_pixels", 0)
        remaining = len(self._pixel_grid)
        if total == 0 or remaining == 0:
            self._finish_transition()
            return
        revealed_so_far = total - remaining
        target_revealed = int(round(total * progress))
        to_reveal = max(0, target_revealed - revealed_so_far)
        if to_reveal > 0:
            self._reveal_pixels(to_reveal)
        # If we've reached the end and nothing remains, finish; otherwise continue until grid empties
        if progress >= 1.0 and len(self._pixel_grid) == 0:
            self._finish_transition()
            return
        self._emit_progress(progress)
    
    def _reveal_pixels(self, count: int) -> None:
        """
        Reveal pixels by punching holes in old image.
        
        Args:
            count: Number of pixels to reveal
        """
        if not self._old_label or not self._old_pixmap:
            logger.warning("[DIFFUSE] _reveal_pixels called but label or pixmap is None")
            return
        
        # Get current pixmap from old label
        current = self._old_label.pixmap()
        if not current or current.isNull():
            logger.debug("[DIFFUSE] Old label pixmap is null, using stored copy")
            current = self._old_pixmap.copy()
        else:
            current = current.copy()
        
        painter = QPainter(current)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Set up for transparent filled shapes
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)

        # Reveal pixels (punch holes)
        revealed = 0
        while revealed < count and self._pixel_grid:
            x, y = self._pixel_grid.pop(0)

            # Draw transparent rectangular hole; CPU fallback uses a simple
            # block dissolve while shaped variants live in the GLSL path.
            painter.fillRect(x, y, self._block_size, self._block_size, QColor(0, 0, 0, 0))

            revealed += 1
        
        painter.end()
        
        # Update old label
        try:
            self._old_label.setPixmap(current)
        except RuntimeError:
            logger.warning("[DIFFUSE] RuntimeError updating old label pixmap")
            pass
    
    def _finish_transition(self) -> None:
        """Finish the transition."""
        if self._state != TransitionState.RUNNING:
            return
        
        logger.debug("Diffuse animation finished")
        
        # Stop timer if present (older implementations used a QTimer here)
        if getattr(self, "_timer", None):
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
        
        # End telemetry tracking for successful completion
        self._mark_end()
        self._set_state(TransitionState.FINISHED)
        self._emit_progress(1.0)
        self.finished.emit()
        
        # Note: Labels cleaned up in cleanup() method
    
    def _on_anim_complete(self) -> None:
        """Animator completion hook: drain remaining pixels, then finish."""
        if self._state != TransitionState.RUNNING:
            return
        # Reveal any remaining grid in one pass
        if self._pixel_grid:
            self._reveal_pixels(len(self._pixel_grid))
        # Now finish
        self._finish_transition()
    
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
    
    def set_shape(self, shape: str) -> None:
        """
        Set shape type for diffuse effect.

        Args:
            shape: Shape type ('Rectangle', 'Membrane')
        """
        valid_shapes = ["Rectangle", "Membrane"]
        if shape not in valid_shapes:
            logger.warning(f"[FALLBACK] Invalid shape {shape}, using Rectangle")
            shape = "Rectangle"

        self._shape = shape
        logger.debug(f"Diffuse shape set to {shape}")
