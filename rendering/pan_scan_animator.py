"""
Pan & Scan animator for screensaver.

Provides smooth zooming and panning animation across images,
creating a cinematic "Ken Burns effect".
"""
from typing import Optional, Tuple
from PySide6.QtCore import QObject, QTimer, QRectF, QPointF, Signal
from PySide6.QtGui import QPixmap
from enum import Enum
import random

from core.logging.logger import get_logger

logger = get_logger(__name__)


class PanDirection(Enum):
    """Pan direction for movement."""
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"
    TOP_TO_BOTTOM = "top_to_bottom"
    BOTTOM_TO_TOP = "bottom_to_top"
    DIAGONAL_TL_BR = "diagonal_tl_br"  # Top-left to bottom-right
    DIAGONAL_TR_BL = "diagonal_tr_bl"  # Top-right to bottom-left
    RANDOM = "random"


class PanScanAnimator(QObject):
    """
    Pan & Scan animator for creating Ken Burns effect.
    
    Smoothly zooms and pans across images over a configurable duration.
    """
    
    # Signals
    frame_updated = Signal(QRectF)  # Emits current viewport rectangle
    animation_finished = Signal()
    
    def __init__(self, zoom_min: float = 1.2, zoom_max: float = 1.5,
                 duration_ms: int = 10000, fps: int = 30):
        """
        Initialize pan & scan animator.
        
        Args:
            zoom_min: Minimum zoom level (1.0 = no zoom)
            zoom_max: Maximum zoom level
            duration_ms: Animation duration in milliseconds
            fps: Frames per second for updates
        """
        super().__init__()
        
        self._zoom_min = zoom_min
        self._zoom_max = zoom_max
        self._duration_ms = duration_ms
        self._fps = fps
        self._timer: Optional[QTimer] = None
        self._is_active = False
        
        # Animation state
        self._image_width = 0
        self._image_height = 0
        self._viewport_width = 0
        self._viewport_height = 0
        self._start_time = 0
        self._elapsed_ms = 0
        
        # Pan parameters
        self._start_zoom = 1.0
        self._end_zoom = 1.0
        self._start_x = 0.0
        self._start_y = 0.0
        self._end_x = 0.0
        self._end_y = 0.0
        self._direction = PanDirection.RANDOM
        
        logger.debug(f"PanScanAnimator created (zoom={zoom_min}-{zoom_max}, "
                    f"duration={duration_ms}ms, fps={fps})")
    
    def start(self, image_size: Tuple[int, int], viewport_size: Tuple[int, int],
              direction: PanDirection = PanDirection.RANDOM) -> None:
        """
        Start pan & scan animation.
        
        Args:
            image_size: (width, height) of source image
            viewport_size: (width, height) of display viewport
            direction: Pan direction (or RANDOM for random selection)
        """
        if self._is_active:
            logger.warning("[FALLBACK] Animation already active, stopping first")
            self.stop()
        
        self._image_width, self._image_height = image_size
        self._viewport_width, self._viewport_height = viewport_size
        self._elapsed_ms = 0
        
        # Resolve direction
        if direction == PanDirection.RANDOM:
            directions = [d for d in PanDirection if d != PanDirection.RANDOM]
            self._direction = random.choice(directions)
        else:
            self._direction = direction
        
        # Calculate zoom levels and pan positions
        self._calculate_animation_params()
        
        # Start timer
        interval_ms = int(1000 / self._fps)
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_frame)
        self._timer.start(interval_ms)
        
        self._is_active = True
        
        logger.info(f"Pan & scan started (direction={self._direction.value}, "
                   f"zoom={self._start_zoom:.2f}->{self._end_zoom:.2f})")
        
        # Emit initial frame
        self._update_frame()
    
    def stop(self) -> None:
        """Stop animation."""
        if not self._is_active:
            return
        
        logger.debug("Stopping pan & scan animation")
        
        if self._timer:
            try:
                self._timer.stop()
                self._timer.deleteLater()
            except RuntimeError:
                pass
            self._timer = None
        
        self._is_active = False
    
    def is_active(self) -> bool:
        """Check if animation is active."""
        return self._is_active
    
    def _calculate_animation_params(self) -> None:
        """Calculate start/end zoom and pan positions."""
        # Random zoom levels
        self._start_zoom = random.uniform(self._zoom_min, self._zoom_max)
        self._end_zoom = random.uniform(self._zoom_min, self._zoom_max)
        
        # Calculate zoomed viewport sizes
        start_vp_w = self._viewport_width / self._start_zoom
        start_vp_h = self._viewport_height / self._start_zoom
        end_vp_w = self._viewport_width / self._end_zoom
        end_vp_h = self._viewport_height / self._end_zoom
        
        # Calculate max pan ranges (ensure viewport stays within image)
        start_max_x = max(0, self._image_width - start_vp_w)
        start_max_y = max(0, self._image_height - start_vp_h)
        end_max_x = max(0, self._image_width - end_vp_w)
        end_max_y = max(0, self._image_height - end_vp_h)
        
        # Calculate start and end positions based on direction
        if self._direction == PanDirection.LEFT_TO_RIGHT:
            self._start_x = 0
            self._start_y = start_max_y / 2 if start_max_y > 0 else 0
            self._end_x = end_max_x
            self._end_y = end_max_y / 2 if end_max_y > 0 else 0
        
        elif self._direction == PanDirection.RIGHT_TO_LEFT:
            self._start_x = start_max_x
            self._start_y = start_max_y / 2 if start_max_y > 0 else 0
            self._end_x = 0
            self._end_y = end_max_y / 2 if end_max_y > 0 else 0
        
        elif self._direction == PanDirection.TOP_TO_BOTTOM:
            self._start_x = start_max_x / 2 if start_max_x > 0 else 0
            self._start_y = 0
            self._end_x = end_max_x / 2 if end_max_x > 0 else 0
            self._end_y = end_max_y
        
        elif self._direction == PanDirection.BOTTOM_TO_TOP:
            self._start_x = start_max_x / 2 if start_max_x > 0 else 0
            self._start_y = start_max_y
            self._end_x = end_max_x / 2 if end_max_x > 0 else 0
            self._end_y = 0
        
        elif self._direction == PanDirection.DIAGONAL_TL_BR:
            self._start_x = 0
            self._start_y = 0
            self._end_x = end_max_x
            self._end_y = end_max_y
        
        elif self._direction == PanDirection.DIAGONAL_TR_BL:
            self._start_x = start_max_x
            self._start_y = 0
            self._end_x = 0
            self._end_y = end_max_y
        
        logger.debug(f"Animation params: zoom={self._start_zoom:.2f}->{self._end_zoom:.2f}, "
                    f"pos=({self._start_x:.0f},{self._start_y:.0f})->"
                    f"({self._end_x:.0f},{self._end_y:.0f})")
    
    def _update_frame(self) -> None:
        """Update animation frame (timer callback)."""
        if not self._is_active:
            return
        
        # Update elapsed time
        self._elapsed_ms += int(1000 / self._fps)
        
        # Check if animation complete
        if self._elapsed_ms >= self._duration_ms:
            # Emit final frame
            viewport = self._calculate_viewport(1.0)
            self.frame_updated.emit(viewport)
            
            # Finish animation
            self.stop()
            self.animation_finished.emit()
            logger.debug("Pan & scan animation finished")
            return
        
        # Calculate progress (0.0 to 1.0)
        progress = self._elapsed_ms / self._duration_ms
        
        # Apply easing (ease in-out)
        eased_progress = self._ease_in_out_cubic(progress)
        
        # Calculate current viewport
        viewport = self._calculate_viewport(eased_progress)
        
        # Emit frame
        self.frame_updated.emit(viewport)
    
    def _calculate_viewport(self, progress: float) -> QRectF:
        """
        Calculate viewport rectangle for current progress.
        
        Args:
            progress: Animation progress (0.0 to 1.0)
        
        Returns:
            Viewport rectangle in image coordinates
        """
        # Interpolate zoom
        current_zoom = self._start_zoom + (self._end_zoom - self._start_zoom) * progress
        
        # Calculate current viewport size
        vp_w = self._viewport_width / current_zoom
        vp_h = self._viewport_height / current_zoom
        
        # Interpolate position
        current_x = self._start_x + (self._end_x - self._start_x) * progress
        current_y = self._start_y + (self._end_y - self._start_y) * progress
        
        # Create viewport rectangle
        viewport = QRectF(current_x, current_y, vp_w, vp_h)
        
        return viewport
    
    def _ease_in_out_cubic(self, t: float) -> float:
        """
        Cubic ease in-out function.
        
        Args:
            t: Input value (0.0 to 1.0)
        
        Returns:
            Eased value (0.0 to 1.0)
        """
        if t < 0.5:
            return 4 * t * t * t
        else:
            p = 2 * t - 2
            return 1 + p * p * p / 2
    
    def set_zoom_range(self, zoom_min: float, zoom_max: float) -> None:
        """
        Set zoom range.
        
        Args:
            zoom_min: Minimum zoom level
            zoom_max: Maximum zoom level
        """
        if zoom_min < 1.0 or zoom_max < zoom_min:
            logger.warning(f"[FALLBACK] Invalid zoom range {zoom_min}-{zoom_max}, using 1.2-1.5")
            zoom_min, zoom_max = 1.2, 1.5
        
        self._zoom_min = zoom_min
        self._zoom_max = zoom_max
        logger.debug(f"Zoom range set to {zoom_min:.2f}-{zoom_max:.2f}")
    
    def set_duration(self, duration_ms: int) -> None:
        """
        Set animation duration.
        
        Args:
            duration_ms: Duration in milliseconds
        """
        if duration_ms <= 0:
            logger.warning(f"[FALLBACK] Invalid duration {duration_ms}ms, using 10000ms")
            duration_ms = 10000
        
        self._duration_ms = duration_ms
        logger.debug(f"Duration set to {duration_ms}ms")
    
    def set_fps(self, fps: int) -> None:
        """
        Set frames per second.
        
        Args:
            fps: Frames per second
        """
        if fps <= 0 or fps > 120:
            logger.warning(f"[FALLBACK] Invalid FPS {fps}, using 30")
            fps = 30
        
        self._fps = fps
        logger.debug(f"FPS set to {fps}")
