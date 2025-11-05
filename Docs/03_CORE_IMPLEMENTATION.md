# Core Implementation Details

## ScreensaverEngine

### Purpose
Central controller that orchestrates all screensaver components.

### Responsibilities
1. Initialize all subsystems (threading, resources, events, settings)
2. Manage image queue and rotation timing
3. Coordinate image loading and display
4. Handle user input for exit conditions
5. Clean shutdown on exit

### Implementation

```python
# engine/screensaver_engine.py

from PySide6.QtCore import QObject, QTimer
from core.threading import ThreadManager, ThreadPoolType
from core.resources import ResourceManager, ResourceType
from core.events import EventSystem
from core.settings import SettingsManager
from engine.display_manager import DisplayManager
from sources.folder_source import FolderSource
from sources.rss_source import RSSSource
import logging

logger = logging.getLogger("screensaver.engine")

class ScreensaverEngine(QObject):
    def __init__(self):
        super().__init__()
        
        # Core systems
        self.resource_manager = ResourceManager()
        self.thread_manager = ThreadManager(resource_manager=self.resource_manager)
        self.event_system = EventSystem()
        self.settings_manager = SettingsManager()
        
        # Components
        self.display_manager = None
        self.image_sources = []
        self.image_queue = []
        self.current_index = 0
        
        # Timers
        self.rotation_timer = QTimer()
        self.rotation_timer.timeout.connect(self._next_image)
        
        # Register for cleanup
        self.resource_manager.register_qt(
            self.rotation_timer,
            ResourceType.TIMER,
            "Image rotation timer"
        )
        
        # Subscribe to events
        self._setup_event_handlers()
        
        logger.info("ScreensaverEngine initialized")
    
    def start(self):
        """Start the screensaver"""
        logger.info("Starting screensaver")
        
        # Load settings
        self.settings_manager.load()
        
        # Initialize image sources
        self._initialize_sources()
        
        # Create display manager
        self.display_manager = DisplayManager(
            self.event_system,
            self.settings_manager,
            self.resource_manager
        )
        self.display_manager.initialize()
        
        # Build initial image queue
        self._build_image_queue()
        
        # Display first image
        if self.image_queue:
            self._display_current_image()
            
            # Start rotation timer
            duration = self.settings_manager.get('timing.image_duration', 5.0)
            self.rotation_timer.start(int(duration * 1000))
            logger.info(f"Image rotation started: {duration}s interval")
        else:
            logger.error("No images in queue")
            self._show_error_message("No images found")
    
    def stop(self):
        """Stop the screensaver"""
        logger.info("Stopping screensaver")
        
        # Stop timers
        self.rotation_timer.stop()
        
        # Cleanup
        self.resource_manager.shutdown()
        logger.info("Screensaver stopped")
    
    def _initialize_sources(self):
        """Initialize image sources based on settings"""
        source_mode = self.settings_manager.get('sources.mode', 'folders')
        
        if source_mode in ('folders', 'both'):
            folders = self.settings_manager.get('sources.folders', [])
            if folders:
                folder_source = FolderSource(
                    folders,
                    self.thread_manager,
                    self.event_system
                )
                self.image_sources.append(folder_source)
                logger.info(f"Initialized folder source: {len(folders)} folders")
        
        if source_mode in ('rss', 'both'):
            feeds = self.settings_manager.get('sources.rss_feeds', [])
            if feeds:
                rss_source = RSSSource(
                    feeds,
                    self.thread_manager,
                    self.event_system,
                    self.resource_manager
                )
                self.image_sources.append(rss_source)
                logger.info(f"Initialized RSS source: {len(feeds)} feeds")
    
    def _build_image_queue(self):
        """Build image queue from all sources"""
        logger.debug("Building image queue")
        
        for source in self.image_sources:
            images = source.get_images()
            self.image_queue.extend(images)
            logger.debug(f"Added {len(images)} images from {source.__class__.__name__}")
        
        # Shuffle queue
        import random
        random.shuffle(self.image_queue)
        
        logger.info(f"Image queue built: {len(self.image_queue)} images")
    
    def _display_current_image(self):
        """Display the current image in the queue"""
        if not self.image_queue:
            logger.warning("Image queue is empty")
            return
        
        image_metadata = self.image_queue[self.current_index]
        logger.debug(f"Displaying image: {image_metadata.path}")
        
        # Load image asynchronously
        self.thread_manager.submit_task(
            ThreadPoolType.IO,
            self._load_image,
            image_metadata,
            callback=self._on_image_loaded
        )
    
    def _load_image(self, metadata):
        """Load image from disk (runs on IO thread)"""
        from PySide6.QtGui import QPixmap
        
        pixmap = QPixmap(metadata.path)
        if pixmap.isNull():
            logger.error(f"Failed to load image: {metadata.path}")
            return None
        
        return pixmap
    
    def _on_image_loaded(self, task_result):
        """Callback when image is loaded"""
        if task_result.success and task_result.result:
            pixmap = task_result.result
            
            # Publish event for display widgets
            self.event_system.publish("image.ready", data={
                'pixmap': pixmap,
                'metadata': self.image_queue[self.current_index]
            })
        else:
            logger.error("Failed to load image, skipping to next")
            self._next_image()
    
    def _next_image(self):
        """Advance to next image"""
        self.current_index = (self.current_index + 1) % len(self.image_queue)
        logger.debug(f"Next image: {self.current_index}/{len(self.image_queue)}")
        self._display_current_image()
    
    def _setup_event_handlers(self):
        """Setup event subscriptions"""
        self.event_system.subscribe("user.input", self._on_user_input)
        self.event_system.subscribe("exit.request", self._on_exit_request)
        self.event_system.subscribe("image.queue.empty", self._on_queue_empty)
    
    def _on_user_input(self, event):
        """Handle user input (exit trigger)"""
        logger.info("User input detected, exiting")
        self.event_system.publish("exit.request")
    
    def _on_exit_request(self, event):
        """Handle exit request"""
        self.stop()
        # Exit application
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()
    
    def _on_queue_empty(self, event):
        """Handle empty image queue"""
        logger.warning("Image queue is empty")
        self._show_error_message("No images available")
    
    def _show_error_message(self, message):
        """Display error message on all screens"""
        if self.display_manager:
            self.display_manager.show_error(message)
```

---

## DisplayManager

### Purpose
Manage multiple monitors and coordinate display widgets.

### Responsibilities
1. Detect all connected monitors
2. Create DisplayWidget for each monitor
3. Handle monitor hotplug events
4. Synchronize or distribute images based on settings

### Implementation

```python
# engine/display_manager.py

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject
from rendering.display_widget import DisplayWidget
import logging

logger = logging.getLogger("screensaver.display")

class DisplayManager(QObject):
    def __init__(self, event_system, settings_manager, resource_manager):
        super().__init__()
        
        self.event_system = event_system
        self.settings_manager = settings_manager
        self.resource_manager = resource_manager
        
        self.display_widgets = []
        self.screens = []
        
        # Subscribe to events
        self.event_system.subscribe("image.ready", self._on_image_ready)
        
        # Monitor screen changes
        app = QApplication.instance()
        app.screenAdded.connect(self._on_screen_added)
        app.screenRemoved.connect(self._on_screen_removed)
    
    def initialize(self):
        """Initialize display widgets for all screens"""
        self.screens = QApplication.screens()
        logger.info(f"Detected {len(self.screens)} monitors")
        
        for screen in self.screens:
            self._create_display_widget(screen)
        
        logger.info(f"Initialized {len(self.display_widgets)} display widgets")
    
    def _create_display_widget(self, screen):
        """Create a display widget for a screen"""
        geometry = screen.geometry()
        logger.debug(f"Creating widget for screen: {screen.name()}, geometry: {geometry}")
        
        widget = DisplayWidget(
            screen,
            self.event_system,
            self.settings_manager,
            self.resource_manager
        )
        
        # Position on screen
        widget.setGeometry(geometry)
        widget.showFullScreen()
        
        self.display_widgets.append(widget)
        
        # Register for cleanup
        self.resource_manager.register_qt(
            widget,
            ResourceType.GUI_COMPONENT,
            f"DisplayWidget: {screen.name()}"
        )
    
    def _on_image_ready(self, event):
        """Handle image ready event"""
        pixmap = event.data['pixmap']
        metadata = event.data['metadata']
        
        multi_monitor_mode = self.settings_manager.get('multi_monitor.mode', 'same')
        
        if multi_monitor_mode == 'same':
            # Send same image to all widgets
            for widget in self.display_widgets:
                widget.set_image(pixmap, metadata)
        else:
            # Different mode: each widget gets different images
            # TODO: Implement separate queues per widget
            pass
    
    def _on_screen_added(self, screen):
        """Handle monitor connected"""
        logger.info(f"Monitor connected: {screen.name()}")
        self._create_display_widget(screen)
        self.event_system.publish("monitor.connected", data={'screen': screen})
    
    def _on_screen_removed(self, screen):
        """Handle monitor disconnected"""
        logger.info(f"Monitor disconnected: {screen.name()}")
        
        # Find and remove corresponding widget
        for i, widget in enumerate(self.display_widgets):
            if widget.screen() == screen:
                widget.close()
                self.display_widgets.pop(i)
                break
        
        self.event_system.publish("monitor.disconnected", data={'screen': screen})
    
    def show_error(self, message):
        """Display error message on all screens"""
        for widget in self.display_widgets:
            widget.show_error(message)
```

---

## ImageQueue Management

### Purpose
Manage the queue of images to display.

### Implementation

```python
# engine/image_queue.py

import random
from typing import List
from dataclasses import dataclass
import logging

logger = logging.getLogger("screensaver.queue")

@dataclass
class ImageMetadata:
    """Image metadata"""
    path: str
    width: int = 0
    height: int = 0
    aspect_ratio: float = 0.0
    file_size: int = 0
    modified_time: float = 0.0
    source: str = "unknown"

class ImageQueue:
    """Manages queue of images for display"""
    
    def __init__(self, shuffle=True):
        self.images: List[ImageMetadata] = []
        self.current_index = 0
        self.shuffle = shuffle
        self.history = []
    
    def add_images(self, images: List[ImageMetadata]):
        """Add images to queue"""
        self.images.extend(images)
        logger.debug(f"Added {len(images)} images to queue")
        
        if self.shuffle:
            self._shuffle()
    
    def _shuffle(self):
        """Shuffle the queue"""
        random.shuffle(self.images)
        logger.debug("Queue shuffled")
    
    def next(self) -> ImageMetadata:
        """Get next image"""
        if not self.images:
            logger.warning("Queue is empty")
            return None
        
        image = self.images[self.current_index]
        self.history.append(image)
        
        self.current_index = (self.current_index + 1) % len(self.images)
        
        # Reshuffle when we loop back
        if self.current_index == 0 and self.shuffle:
            self._shuffle()
        
        return image
    
    def current(self) -> ImageMetadata:
        """Get current image without advancing"""
        if not self.images:
            return None
        return self.images[self.current_index]
    
    def size(self) -> int:
        """Get queue size"""
        return len(self.images)
    
    def clear(self):
        """Clear the queue"""
        self.images.clear()
        self.current_index = 0
        logger.debug("Queue cleared")
```

---

## Command-Line Handler

### Purpose
Parse Windows screensaver command-line arguments.

### Implementation

```python
# main.py (partial)

import sys
from enum import Enum

class ScreensaverMode(Enum):
    RUN = "run"
    CONFIG = "config"
    PREVIEW = "preview"

def parse_screensaver_args():
    """
    Parse Windows screensaver command-line arguments.
    
    Returns:
        tuple: (mode, preview_hwnd)
        
    Modes:
        /s or no args -> RUN mode
        /c -> CONFIG mode
        /p <hwnd> -> PREVIEW mode with window handle
    """
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg == '/s':
            return (ScreensaverMode.RUN, None)
        elif arg == '/c':
            return (ScreensaverMode.CONFIG, None)
        elif arg.startswith('/p'):
            hwnd = int(sys.argv[2]) if len(sys.argv) > 2 else None
            return (ScreensaverMode.PREVIEW, hwnd)
    
    # Default to run mode
    return (ScreensaverMode.RUN, None)
```

---

## Logging Configuration

### Purpose
Setup centralized logging for the application.

### Implementation

```python
# core/logging/logger.py

import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging(debug=False):
    """
    Setup application logging.
    
    Args:
        debug: Enable debug level logging
    """
    # Create logs directory
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure root logger
    level = logging.DEBUG if debug else logging.INFO
    
    # Format
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler (rotating)
    log_file = os.path.join(log_dir, "screensaver.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # Configure root
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Log startup
    logger = logging.getLogger("screensaver")
    logger.info("=" * 80)
    logger.info("Screensaver logging initialized")
    logger.info(f"Log level: {logging.getLevelName(level)}")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 80)
```

---

**Next Document**: `04_IMAGE_SOURCES.md` - Image source implementations
