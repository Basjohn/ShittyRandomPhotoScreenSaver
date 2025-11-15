"""
Pan and scan effect for images - slow drift/movement across image.

Scales image larger than display and slowly pans across it for dynamic effect.
"""
import math
import random
from typing import Optional
from PySide6.QtCore import QTimer, QPoint, QSize, QRect
from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtCore import Qt

from core.logging.logger import get_logger

logger = get_logger(__name__)


class PanAndScan:
    """
    Manages pan and scan effect for screensaver images.
    
    Features:
    - Image always larger than display (maintains aspect ratio)
    - Slow random drift in random direction
    - Never escapes image bounds or reaches empty space
    - Speed adjustable or auto-calculated based on transition interval
    """
    
    def __init__(self, parent: QWidget):
        """
        Initialize pan and scan manager.
        
        Args:
            parent: Parent widget (DisplayWidget)
        """
        self._parent = parent
        self._label: Optional[QLabel] = None
        self._timer: Optional[QTimer] = None
        self._enabled = False
        
        # Pan state
        self._current_offset = QPoint(0, 0)
        self._current_offset_x_float = 0.0  # Accumulate fractional pixels
        self._current_offset_y_float = 0.0  # Accumulate fractional pixels
        self._target_direction_x = 0.0  # Normalized direction vector X
        self._target_direction_y = 0.0  # Normalized direction vector Y
        self._image_size = QSize(0, 0)
        self._display_size = QSize(0, 0)
        self._scaled_pixmap: Optional[QPixmap] = None
        self._initial_offset: Optional[QPoint] = None
        
        # Settings
        self._speed_pixels_per_second = 2.5  # Default speed (reduced from 20.0)
        self._auto_speed = True
        self._transition_interval_sec = 10.0  # Default
        
        # Timer interval (60 FPS)
        self._fps = 60
        self._timer_interval_ms = 1000 // self._fps
        
        # FIX: Use ResourceManager for Qt object lifecycle
        try:
            from core.resources.manager import ResourceManager
            self._resource_manager = ResourceManager()
        except Exception:
            self._resource_manager = None
        
        logger.debug("Pan and Scan initialized")

    def set_target_fps(self, fps: int) -> None:
        try:
            new_fps = max(10, min(240, int(fps)))
        except Exception:
            new_fps = 60
        if new_fps == self._fps:
            return
        self._fps = new_fps
        self._timer_interval_ms = max(1, int(1000 // self._fps))
        was_running = self._timer.isActive() if self._timer else False
        if was_running:
            try:
                self._timer.stop()
            except Exception:
                pass
            try:
                self._timer.start(self._timer_interval_ms)
            except Exception:
                pass
    
    def set_image(self, pixmap: QPixmap, label: QLabel, display_size: QSize) -> None:
        """
        Set new image for pan and scan.
        
        Args:
            pixmap: Original image pixmap
            label: QLabel to display the image
            display_size: Size of the display widget
        """
        if not self._enabled:
            return
        
        self._label = label
        self._display_size = display_size
        
        # Scale image to be larger than display (maintain aspect ratio)
        self._scaled_pixmap = self._scale_image_for_pan(pixmap, display_size)
        self._image_size = self._scaled_pixmap.size()
        
        # Set scaled image to label
        self._label.setPixmap(self._scaled_pixmap)
        self._label.resize(self._image_size)
        
        # Starting position: use provided initial offset if present; otherwise random
        max_offset_x = max(0, self._image_size.width() - display_size.width())
        max_offset_y = max(0, self._image_size.height() - display_size.height())
        if self._initial_offset is not None:
            start_x = max(0, min(max_offset_x, int(self._initial_offset.x())))
            start_y = max(0, min(max_offset_y, int(self._initial_offset.y())))
        else:
            start_x = random.randint(0, max_offset_x) if max_offset_x > 0 else 0
            start_y = random.randint(0, max_offset_y) if max_offset_y > 0 else 0
        
        self._current_offset = QPoint(start_x, start_y)
        self._current_offset_x_float = float(start_x)
        self._current_offset_y_float = float(start_y)
        self._label.move(-start_x, -start_y)
        # Clear one-shot initial offset after applying
        self._initial_offset = None
        
        # Pick random drift direction
        self._choose_new_direction()
        
        logger.debug(f"Pan and scan image set: {self._image_size.width()}x{self._image_size.height()} "
                    f"on {display_size.width()}x{display_size.height()}, offset ({start_x}, {start_y})")

    def set_initial_offset(self, offset: Optional[QPoint]) -> None:
        """Set an initial offset to use on next set_image (one-shot)."""
        self._initial_offset = offset

    def preview_offset(self, pixmap: QPixmap, display_size: QSize) -> Optional[QPoint]:
        """Compute the centered offset that aligns with preview_scale()."""
        if pixmap.isNull() or not display_size.isValid():
            return None
        scaled = self._scale_image_for_pan(pixmap, display_size)
        img_w, img_h = scaled.width(), scaled.height()
        off_x = max(0, (img_w - display_size.width()) // 2)
        off_y = max(0, (img_h - display_size.height()) // 2)
        return QPoint(off_x, off_y)
    
    def start(self) -> None:
        """Start pan and scan animation."""
        if not self._enabled or self._timer:
            return
        
        # Calculate speed if auto mode
        if self._auto_speed:
            self._calculate_auto_speed()
        
        # Create and start timer
        self._timer = QTimer(self._parent)
        self._timer.timeout.connect(self._update_pan)
        self._timer.start(self._timer_interval_ms)
        
        # Register with ResourceManager for proper lifecycle tracking
        if self._resource_manager:
            try:
                self._resource_manager.register_qt(self._timer, description="PanAndScan timer")
            except Exception:
                pass
        
        logger.info(f"Pan and scan started: speed={self._speed_pixels_per_second:.1f} px/s, "
                   f"auto_speed={self._auto_speed}")
    
    def stop(self) -> None:
        """Stop pan and scan effect."""
        did_change = False
        if self._timer:
            try:
                self._timer.stop()
                self._timer.deleteLater()
            except RuntimeError:
                # Already deleted
                pass
            finally:
                self._timer = None
            did_change = True

        if self._label and self._label.isVisible():
            try:
                self._label.hide()
            except Exception:
                pass
            else:
                did_change = True

        if did_change:
            logger.debug("Pan and scan stopped")
    
    def enable(self, enabled: bool) -> None:
        """
        Enable or disable pan and scan.
        
        Args:
            enabled: True to enable, False to disable
        """
        was_enabled = self._enabled
        self._enabled = enabled

        if not enabled and was_enabled:
            self.stop()
            if self._label:
                try:
                    self._label.hide()
                except Exception:
                    pass

        if was_enabled != enabled:
            logger.debug(f"Pan and scan {'enabled' if enabled else 'disabled'}")
    
    def set_speed(self, pixels_per_second: float) -> None:
        """
        Set pan speed in pixels per second.
        
        Args:
            pixels_per_second: Speed in pixels per second (clamped 1-100)
        """
        # Clamp to reasonable range: 1-100 px/s for manual
        self._speed_pixels_per_second = max(1.0, min(100.0, pixels_per_second))
        self._auto_speed = False
        logger.debug(f"Pan speed set to {self._speed_pixels_per_second:.1f} px/s (manual, clamped from {pixels_per_second:.1f})")
    
    def set_auto_speed(self, auto: bool, transition_interval_sec: float = 10.0) -> None:
        """
        Set auto speed mode.
        
        Args:
            auto: True for auto speed, False for manual
            transition_interval_sec: Seconds between transitions (for auto calculation)
        """
        self._auto_speed = auto
        self._transition_interval_sec = max(1.0, transition_interval_sec)
        
        if auto:
            self._calculate_auto_speed()
        
        logger.debug(f"Pan auto speed: {auto}, interval: {transition_interval_sec}s")
    
    def is_enabled(self) -> bool:
        """Check if pan and scan is enabled."""
        return self._enabled
    
    def preview_scale(self, pixmap: QPixmap, display_size: QSize) -> Optional[QPixmap]:
        """
        Preview what the scaled image will look like for pan & scan.
        
        This is used to provide seamless handoff from transitions to pan & scan
        by ensuring the transition uses the same scale that pan & scan will use.
        
        Args:
            pixmap: Original image
            display_size: Display size
        
        Returns:
            Scaled pixmap (130% of display), or None if not enabled
        """
        if not self._enabled:
            return None
        
        return self._scale_image_for_pan(pixmap, display_size)

    def build_transition_frame(
        self,
        pixmap: QPixmap,
        display_size: QSize,
        device_pixel_ratio: float
    ) -> Optional[QPixmap]:
        """
        Build a transition-ready pixmap that matches the initial pan & scan viewport.

        Produces a widget-sized frame showing the first pan & scan position so
        that the transition seamlessly hands off into the animation.

        Args:
            pixmap: Original image pixmap.
            display_size: Logical display size of the widget.
            device_pixel_ratio: Target device pixel ratio for high-DPI displays.

        Returns:
            A pixmap the size of the display showing the first pan frame, or None.
        """
        if not self._enabled or pixmap.isNull() or not display_size.isValid():
            return None

        scaled = self._scale_image_for_pan(pixmap, display_size)
        if scaled.isNull():
            return None

        source_offset = self.preview_offset(pixmap, display_size)
        if source_offset is None:
            source_offset = QPoint(0, 0)

        max_offset_x = max(0, scaled.width() - display_size.width())
        max_offset_y = max(0, scaled.height() - display_size.height())
        start_x = max(0, min(max_offset_x, source_offset.x()))
        start_y = max(0, min(max_offset_y, source_offset.y()))

        viewport_rect = QRect(start_x, start_y, display_size.width(), display_size.height())
        if viewport_rect.width() <= 0 or viewport_rect.height() <= 0:
            return None

        # Ensure pan & scan starts from the same offset after the transition completes
        self.set_initial_offset(QPoint(start_x, start_y))

        # Create a display-sized canvas and draw the scaled image with the offset applied
        target_width = max(1, int(display_size.width()))
        target_height = max(1, int(display_size.height()))

        frame = QPixmap(target_width, target_height)
        frame.fill(Qt.GlobalColor.black)

        try:
            painter = QPainter(frame)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawPixmap(-start_x, -start_y, scaled)
            painter.end()
        except Exception:
            return None

        # Scale to physical pixels for high-DPI screens if required
        if device_pixel_ratio and device_pixel_ratio > 1.0:
            target_physical_w = int(display_size.width() * device_pixel_ratio)
            target_physical_h = int(display_size.height() * device_pixel_ratio)
            if target_physical_w > 0 and target_physical_h > 0:
                frame = frame.scaled(
                    target_physical_w,
                    target_physical_h,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )

        try:
            frame.setDevicePixelRatio(device_pixel_ratio)
        except Exception:
            pass

        return frame
    
    def _scale_image_for_pan(self, pixmap: QPixmap, display_size: QSize) -> QPixmap:
        """
        Scale image to be larger than display for panning.
        
        Image should be 120-150% of display size to allow room for movement.
        
        Args:
            pixmap: Original image
            display_size: Display size
        
        Returns:
            Scaled pixmap
        """
        # FIX: Validate dimensions to prevent division by zero
        if pixmap.height() == 0 or display_size.height() == 0:
            logger.error(f"Invalid dimensions for pan: display={display_size.width()}x{display_size.height()}, img={pixmap.width()}x{pixmap.height()}")
            return pixmap  # Return original
        
        img_ratio = pixmap.width() / pixmap.height()
        screen_ratio = display_size.width() / display_size.height()
        
        # Scale to 130% of display size minimum
        scale_factor = 1.3
        
        if img_ratio > screen_ratio:
            # Image is wider - scale by height
            target_height = int(display_size.height() * scale_factor)
            target_width = int(target_height * img_ratio)
        else:
            # Image is taller - scale by width
            target_width = int(display_size.width() * scale_factor)
            target_height = int(target_width / img_ratio)
        
        # Ensure minimum size
        target_width = max(target_width, int(display_size.width() * 1.2))
        target_height = max(target_height, int(display_size.height() * 1.2))
        
        from PySide6.QtCore import Qt
        scaled = pixmap.scaled(
            target_width, target_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        logger.debug(f"Scaled for pan: {pixmap.width()}x{pixmap.height()} → "
                    f"{scaled.width()}x{scaled.height()}")
        
        return scaled
    
    def _calculate_auto_speed(self) -> None:
        """
        Calculate optimal pan speed based on transition interval.
        
        Speed should ensure image drifts across available space during interval,
        but not too fast to be distracting.
        """
        # FIX: Add error logging for invalid sizes
        if not self._display_size.isValid() or not self._image_size.isValid():
            logger.error(f"Invalid sizes for pan auto-speed: display={self._display_size.width()}x{self._display_size.height()}, image={self._image_size.width()}x{self._image_size.height()}")
            self._speed_pixels_per_second = 20.0
            return
        
        # Calculate available drift space
        drift_space = max(
            self._image_size.width() - self._display_size.width(),
            self._image_size.height() - self._display_size.height()
        )
        
        if drift_space <= 0:
            self._speed_pixels_per_second = 8.0  # Minimum fallback
            return
        
        # Cover 30-50% of drift space during transition interval
        coverage_ratio = 0.4
        distance_to_cover = drift_space * coverage_ratio
        
        # Calculate speed (pixels per second) - gentle visible movement
        self._speed_pixels_per_second = (distance_to_cover / self._transition_interval_sec) / 4.0
        
        # Clamp to reasonable range: 8-25 px/s for auto
        self._speed_pixels_per_second = max(8.0, min(25.0, self._speed_pixels_per_second))
        
        logger.debug(f"Auto speed calculated: {self._speed_pixels_per_second:.1f} px/s "
                    f"(drift_space={drift_space}, interval={self._transition_interval_sec}s)")
    
    def _update_pan(self) -> None:
        """Update pan position (called by timer)."""
        if not self._label or not self._scaled_pixmap:
            return
        
        # Calculate movement delta (pixels per frame)
        delta_per_frame = self._speed_pixels_per_second / self._fps
        
        # Update offset using normalized direction vector (accumulate fractional pixels)
        self._current_offset_x_float += self._target_direction_x * delta_per_frame
        self._current_offset_y_float += self._target_direction_y * delta_per_frame
        
        # Convert to integer for actual positioning
        new_offset = QPoint(
            int(self._current_offset_x_float),
            int(self._current_offset_y_float)
        )
        
        # Check bounds and reverse direction if needed
        max_offset_x = max(0, self._image_size.width() - self._display_size.width())
        max_offset_y = max(0, self._image_size.height() - self._display_size.height())
        
        # X bounds check
        if new_offset.x() < 0:
            new_offset.setX(0)
            self._current_offset_x_float = 0.0
            self._target_direction_x = abs(self._target_direction_x)
        elif new_offset.x() > max_offset_x:
            new_offset.setX(max_offset_x)
            self._current_offset_x_float = float(max_offset_x)
            self._target_direction_x = -abs(self._target_direction_x)
        
        # Y bounds check
        if new_offset.y() < 0:
            new_offset.setY(0)
            self._current_offset_y_float = 0.0
            self._target_direction_y = abs(self._target_direction_y)
        elif new_offset.y() > max_offset_y:
            new_offset.setY(max_offset_y)
            self._current_offset_y_float = float(max_offset_y)
            self._target_direction_y = -abs(self._target_direction_y)
        
        # Update position
        self._current_offset = new_offset
        self._label.move(-new_offset.x(), -new_offset.y())
        
        # Occasionally change direction slightly for natural movement
        if random.random() < 0.01:  # 1% chance per frame (~0.6x per second)
            self._adjust_direction()
    
    def _choose_new_direction(self) -> None:
        """Choose a new random drift direction (normalized to 1.0)."""
        # Random direction with slight bias toward diagonal movement
        angle = random.uniform(0, 360)
        # Direction vector normalized to magnitude 1.0 for correct speed calculation
        self._target_direction_x = math.cos(math.radians(angle))
        self._target_direction_y = math.sin(math.radians(angle))
        
        logger.debug(f"New pan direction: ({self._target_direction_x:.3f}, {self._target_direction_y:.3f})")
    
    def _adjust_direction(self) -> None:
        """Slightly adjust current direction for natural movement."""
        # Small random adjustment (-10% to +10%)
        adjustment = random.uniform(-0.1, 0.1)
        
        self._target_direction_x *= (1 + adjustment)
        self._target_direction_y *= (1 + adjustment)
        
        # Re-normalize to maintain magnitude 1.0
        magnitude = math.sqrt(self._target_direction_x**2 + self._target_direction_y**2)
        if magnitude > 0:
            self._target_direction_x /= magnitude
            self._target_direction_y /= magnitude
