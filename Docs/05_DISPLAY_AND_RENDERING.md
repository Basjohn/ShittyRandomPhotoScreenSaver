# Display and Rendering Implementation

## DisplayWidget

### Purpose
Fullscreen window that displays images on a specific monitor.

### Responsibilities
1. Render images with selected display mode
2. Execute transitions between images
3. Host overlay widgets (clock, weather)
4. Capture input for exit
5. Handle pan & scan animation

### Implementation

```python
# rendering/display_widget.py

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, QTimer, pyqtSignal
from PySide6.QtGui import QPixmap, QPainter, QCursor
from rendering.image_processor import ImageProcessor
from rendering.display_modes import DisplayMode
from transitions.crossfade import CrossfadeTransition
from widgets.clock_widget import ClockWidget
from widgets.weather_widget import WeatherWidget
import logging

logger = logging.getLogger("screensaver.display")

class DisplayWidget(QWidget):
    """Fullscreen display widget for a single monitor"""
    
    def __init__(self, screen, event_system, settings_manager, resource_manager):
        super().__init__()
        
        self.screen_obj = screen
        self.event_system = event_system
        self.settings_manager = settings_manager
        self.resource_manager = resource_manager
        
        # Current and previous images
        self.current_pixmap = None
        self.previous_pixmap = None
        
        # Image processor
        self.image_processor = ImageProcessor()
        
        # Transition
        self.current_transition = None
        
        # Overlay widgets
        self.clock_widget = None
        self.weather_widget = None
        
        # Setup UI
        self._setup_ui()
        self._setup_widgets()
        
        # Hide cursor
        self.setCursor(Qt.BlankCursor)
        
        logger.debug(f"DisplayWidget created for {screen.name()}")
    
    def _setup_ui(self):
        """Setup the UI"""
        # Black background
        self.setStyleSheet("background-color: black;")
        
        # Frameless, fullscreen
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        
        # Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Image label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.image_label)
    
    def _setup_widgets(self):
        """Setup overlay widgets"""
        # Clock widget
        if self.settings_manager.get('widgets.clock_enabled', True):
            position = self.settings_manager.get('widgets.clock_position', 'top-right')
            format_24h = self.settings_manager.get('widgets.clock_format', '24h') == '24h'
            
            self.clock_widget = ClockWidget(self, position, format_24h)
        
        # Weather widget
        if self.settings_manager.get('widgets.weather_enabled', False):
            position = self.settings_manager.get('widgets.weather_position', 'top-left')
            location = self.settings_manager.get('widgets.weather_location', '')
            
            if location:
                self.weather_widget = WeatherWidget(self, position, location)
    
    def set_image(self, pixmap: QPixmap, metadata):
        """Set new image with transition"""
        logger.debug(f"Setting image: {metadata.path}")
        
        # Store previous
        self.previous_pixmap = self.current_pixmap
        
        # Process new image
        display_mode = self.settings_manager.get('display.mode', 'fill')
        screen_size = self.size()
        
        processed_pixmap = self.image_processor.process_image(
            pixmap,
            screen_size,
            DisplayMode[display_mode.upper()]
        )
        
        self.current_pixmap = processed_pixmap
        
        # Execute transition
        if self.previous_pixmap:
            self._execute_transition()
        else:
            # First image, no transition
            self.image_label.setPixmap(self.current_pixmap)
    
    def _execute_transition(self):
        """Execute transition between images"""
        transition_type = self.settings_manager.get('transitions.type', 'crossfade')
        duration = self.settings_manager.get('transitions.duration', 1.0)
        
        logger.debug(f"Executing transition: {transition_type}, duration: {duration}s")
        
        # Import transition dynamically
        if transition_type == 'crossfade':
            from transitions.crossfade import CrossfadeTransition
            transition = CrossfadeTransition(
                self.image_label,
                self.previous_pixmap,
                self.current_pixmap,
                duration
            )
        elif transition_type == 'slide':
            from transitions.slide import SlideTransition
            transition = SlideTransition(
                self.image_label,
                self.previous_pixmap,
                self.current_pixmap,
                duration
            )
        elif transition_type == 'block_puzzle':
            from transitions.block_puzzle_flip import BlockPuzzleFlipTransition
            grid = self.settings_manager.get('transitions.block_puzzle_grid', (6, 6))
            transition = BlockPuzzleFlipTransition(
                self.image_label,
                self.previous_pixmap,
                self.current_pixmap,
                duration,
                grid
            )
        else:
            # Fallback to instant
            self.image_label.setPixmap(self.current_pixmap)
            return
        
        # Connect completion
        transition.finished.connect(self._on_transition_complete)
        
        # Start
        transition.start()
        self.current_transition = transition
    
    def _on_transition_complete(self):
        """Handle transition completion"""
        logger.debug("Transition complete")
        self.event_system.publish("transition.complete")
        self.current_transition = None
    
    def show_error(self, message: str):
        """Display error message"""
        error_label = QLabel(message)
        error_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 36px;
                background-color: rgba(255, 0, 0, 0.3);
                padding: 20px;
                border-radius: 10px;
            }
        """)
        error_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(error_label)
    
    # Input handling for exit
    def mouseMoveEvent(self, event):
        """Handle mouse movement"""
        self.event_system.publish("user.input", data={'type': 'mouse_move'})
    
    def mousePressEvent(self, event):
        """Handle mouse press"""
        self.event_system.publish("user.input", data={'type': 'mouse_press'})
    
    def keyPressEvent(self, event):
        """Handle key press"""
        self.event_system.publish("user.input", data={'type': 'key_press', 'key': event.key()})
```

---

## Image Processor

### Purpose
Scale, crop, and process images for display.

### Display Modes
1. **Fill**: Crop and scale to fill screen (no letterboxing)
2. **Fit**: Scale to fit within screen (may have letterboxing)
3. **Shrink**: Only scale down if larger than screen

### Implementation

```python
# rendering/image_processor.py

from PySide6.QtCore import QSize, Qt, QRect
from PySide6.QtGui import QPixmap, QPainter
from rendering.display_modes import DisplayMode
import logging

logger = logging.getLogger("screensaver.processor")

class ImageProcessor:
    """Process images for display"""
    
    def process_image(self, pixmap: QPixmap, target_size: QSize, mode: DisplayMode) -> QPixmap:
        """
        Process image according to display mode.
        
        Args:
            pixmap: Source image
            target_size: Target screen size
            mode: Display mode
            
        Returns:
            Processed QPixmap
        """
        if mode == DisplayMode.FILL:
            return self._fill_mode(pixmap, target_size)
        elif mode == DisplayMode.FIT:
            return self._fit_mode(pixmap, target_size)
        elif mode == DisplayMode.SHRINK:
            return self._shrink_mode(pixmap, target_size)
        else:
            logger.warning(f"Unknown display mode: {mode}, using FILL")
            return self._fill_mode(pixmap, target_size)
    
    def _fill_mode(self, pixmap: QPixmap, target_size: QSize) -> QPixmap:
        """
        Fill mode: Crop and scale to fill entire screen.
        Maintains aspect ratio, crops excess.
        NO letterboxing or pillarboxing.
        """
        img_ratio = pixmap.width() / pixmap.height()
        screen_ratio = target_size.width() / target_size.height()
        
        if img_ratio > screen_ratio:
            # Image is wider - crop sides
            new_height = pixmap.height()
            new_width = int(new_height * screen_ratio)
            x_offset = (pixmap.width() - new_width) // 2
            cropped = pixmap.copy(x_offset, 0, new_width, new_height)
        else:
            # Image is taller - crop top/bottom
            new_width = pixmap.width()
            new_height = int(new_width / screen_ratio)
            y_offset = (pixmap.height() - new_height) // 2
            cropped = pixmap.copy(0, y_offset, new_width, new_height)
        
        # Scale to target size
        return cropped.scaled(
            target_size,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
        )
    
    def _fit_mode(self, pixmap: QPixmap, target_size: QSize) -> QPixmap:
        """
        Fit mode: Scale to fit within screen bounds.
        Maintains aspect ratio, may have letterboxing.
        """
        scaled = pixmap.scaled(
            target_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        # Create black background
        result = QPixmap(target_size)
        result.fill(Qt.black)
        
        # Center image
        painter = QPainter(result)
        x = (target_size.width() - scaled.width()) // 2
        y = (target_size.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()
        
        return result
    
    def _shrink_mode(self, pixmap: QPixmap, target_size: QSize) -> QPixmap:
        """
        Shrink mode: Only scale down if larger than screen.
        Never upscale.
        """
        if pixmap.width() <= target_size.width() and pixmap.height() <= target_size.height():
            # Image fits, create centered version
            result = QPixmap(target_size)
            result.fill(Qt.black)
            
            painter = QPainter(result)
            x = (target_size.width() - pixmap.width()) // 2
            y = (target_size.height() - pixmap.height()) // 2
            painter.drawPixmap(x, y, pixmap)
            painter.end()
            
            return result
        else:
            # Scale down using fit mode
            return self._fit_mode(pixmap, target_size)
```

---

## Display Modes Enum

```python
# rendering/display_modes.py

from enum import Enum

class DisplayMode(Enum):
    """Display modes for images"""
    FILL = "fill"      # Crop to fill screen
    FIT = "fit"        # Scale to fit (letterbox)
    SHRINK = "shrink"  # Only scale down
```

---

## Pan & Scan Animator

### Purpose
Animate movement across zoomed images.

### Implementation

```python
# rendering/pan_scan_animator.py

from PySide6.QtCore import QTimer, QPoint, QSize, QRect, QObject, pyqtSignal
from PySide6.QtGui import QPixmap
import math
import logging

logger = logging.getLogger("screensaver.panscan")

class PanScanAnimator(QObject):
    """Animates pan & scan across zoomed images"""
    
    position_updated = pyqtSignal(QRect)
    animation_complete = pyqtSignal()
    
    def __init__(self, pixmap: QPixmap, screen_size: QSize, zoom_level: float = 1.3, speed: float = 1.0):
        super().__init__()
        
        self.screen_size = screen_size
        self.zoom_level = zoom_level
        self.speed = speed
        
        # Zoom the image
        zoomed_width = int(screen_size.width() * zoom_level)
        zoomed_height = int(screen_size.height() * zoom_level)
        self.zoomed_size = QSize(zoomed_width, zoomed_height)
        
        self.zoomed_pixmap = pixmap.scaled(
            self.zoomed_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        # Calculate pan range
        self.max_x = max(0, self.zoomed_pixmap.width() - screen_size.width())
        self.max_y = max(0, self.zoomed_pixmap.height() - screen_size.height())
        
        # Animation state
        self.current_offset = QPoint(0, 0)
        self.start_time = 0
        self.duration = 10.0  # seconds
        
        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._update)
        
        logger.debug(f"PanScanAnimator: zoom={zoom_level}, max_pan=({self.max_x}, {self.max_y})")
    
    def start(self):
        """Start animation"""
        logger.debug("Pan & scan animation started")
        self.start_time = 0
        self.timer.start(16)  # ~60 FPS
    
    def stop(self):
        """Stop animation"""
        self.timer.stop()
        logger.debug("Pan & scan animation stopped")
    
    def _update(self):
        """Update animation frame"""
        self.start_time += 0.016 * self.speed  # 16ms per frame
        
        if self.start_time >= self.duration:
            self.animation_complete.emit()
            return
        
        # Calculate progress (0.0 to 1.0)
        progress = self.start_time / self.duration
        
        # Smooth easing (ease-in-out)
        eased = self._ease_in_out(progress)
        
        # Calculate position (diagonal sweep)
        x = int(self.max_x * eased)
        y = int(self.max_y * eased)
        
        self.current_offset = QPoint(x, y)
        
        # Emit visible region
        visible_rect = QRect(self.current_offset, self.screen_size)
        self.position_updated.emit(visible_rect)
    
    def _ease_in_out(self, t: float) -> float:
        """Ease-in-out function"""
        return t * t * (3.0 - 2.0 * t)
    
    def get_visible_region(self) -> QRect:
        """Get current visible region"""
        return QRect(self.current_offset, self.screen_size)
```

---

## Monitor Utilities

### Purpose
Helper functions for multi-monitor support.

### Implementation

```python
# utils/monitors.py

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect
import logging

logger = logging.getLogger("screensaver.monitors")

def get_all_screens():
    """Get all connected screens"""
    app = QApplication.instance()
    screens = app.screens()
    logger.debug(f"Detected {len(screens)} screens")
    return screens

def get_primary_screen():
    """Get primary screen"""
    app = QApplication.instance()
    return app.primaryScreen()

def get_screen_geometry(screen) -> QRect:
    """Get screen geometry"""
    return screen.geometry()

def get_screen_by_name(name: str):
    """Get screen by name"""
    for screen in get_all_screens():
        if screen.name() == name:
            return screen
    return None

def get_total_screen_area() -> QRect:
    """Get bounding rectangle of all screens"""
    screens = get_all_screens()
    if not screens:
        return QRect()
    
    min_x = min(s.geometry().x() for s in screens)
    min_y = min(s.geometry().y() for s in screens)
    max_x = max(s.geometry().x() + s.geometry().width() for s in screens)
    max_y = max(s.geometry().y() + s.geometry().height() for s in screens)
    
    return QRect(min_x, min_y, max_x - min_x, max_y - min_y)
```

---

## Testing

```python
# tests/test_image_processor.py

import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QSize
from rendering.image_processor import ImageProcessor
from rendering.display_modes import DisplayMode

def test_fill_mode_wide_image():
    """Test fill mode with wide image"""
    processor = ImageProcessor()
    
    # Create wide image (2000x1000)
    pixmap = QPixmap(2000, 1000)
    
    # Target 1920x1080
    target = QSize(1920, 1080)
    
    result = processor.process_image(pixmap, target, DisplayMode.FILL)
    
    assert result.width() == 1920
    assert result.height() == 1080

def test_fit_mode_letterbox():
    """Test fit mode creates letterbox"""
    processor = ImageProcessor()
    
    # Create tall image (1000x2000)
    pixmap = QPixmap(1000, 2000)
    
    # Target 1920x1080
    target = QSize(1920, 1080)
    
    result = processor.process_image(pixmap, target, DisplayMode.FIT)
    
    # Result should be target size with black bars
    assert result.width() == 1920
    assert result.height() == 1080

def test_shrink_mode_no_upscale():
    """Test shrink mode doesn't upscale"""
    processor = ImageProcessor()
    
    # Create small image (800x600)
    pixmap = QPixmap(800, 600)
    
    # Target 1920x1080
    target = QSize(1920, 1080)
    
    result = processor.process_image(pixmap, target, DisplayMode.SHRINK)
    
    # Result should be target size but image not upscaled
    assert result.width() == 1920
    assert result.height() == 1080
```

---

**Next Document**: `06_TRANSITIONS.md` - Transition effects implementation
