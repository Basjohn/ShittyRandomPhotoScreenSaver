"""
Main screensaver engine - orchestrates all components.

The ScreensaverEngine is the central controller that:
- Initializes all core systems
- Manages image sources and queue
- Handles display across monitors
- Controls image rotation timing
- Processes events and user input
"""
from typing import List, Optional, Dict
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QPixmap

from core.events import EventSystem
from core.resources import ResourceManager
from core.threading import ThreadManager
from core.settings import SettingsManager
from core.logging.logger import get_logger

from engine.display_manager import DisplayManager
from engine.image_queue import ImageQueue
from sources.folder_source import FolderSource
from sources.rss_source import RSSSource
from sources.base_provider import ImageMetadata
from rendering.display_modes import DisplayMode

logger = get_logger(__name__)


class ScreensaverEngine(QObject):
    """
    Main screensaver engine orchestrating all components.
    
    Responsibilities:
    - Initialize and coordinate all subsystems
    - Manage image sources (folder, RSS)
    - Build and maintain image queue
    - Control image rotation timing
    - Load images asynchronously
    - Handle display across monitors
    - Process events (exit, errors, etc.)
    - Clean up resources
    
    Signals:
    - started: Engine started successfully
    - stopped: Engine stopped
    - image_changed: New image displayed (path)
    - error_occurred: Error occurred (message)
    """
    
    started = Signal()
    stopped = Signal()
    image_changed = Signal(str)  # image path
    error_occurred = Signal(str)  # error message
    
    def __init__(self):
        """Initialize screensaver engine."""
        super().__init__()
        
        # Core systems (initialized later)
        self.event_system: Optional[EventSystem] = None
        self.resource_manager: Optional[ResourceManager] = None
        self.thread_manager: Optional[ThreadManager] = None
        self.settings_manager: Optional[SettingsManager] = None
        
        # Engine components
        self.display_manager: Optional[DisplayManager] = None
        self.image_queue: Optional[ImageQueue] = None
        
        # Image sources
        self.folder_sources: List[FolderSource] = []
        self.rss_sources: List[RSSSource] = []
        
        # State
        self._running: bool = False
        self._rotation_timer: Optional[QTimer] = None
        self._current_image: Optional[ImageMetadata] = None
        self._loading_in_progress: bool = False
        
        logger.info("ScreensaverEngine created")
    
    def initialize(self) -> bool:
        """
        Initialize all engine components.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("=" * 60)
            logger.info("Initializing Screensaver Engine")
            logger.info("=" * 60)
            
            # Initialize core systems
            if not self._initialize_core_systems():
                logger.error("Failed to initialize core systems")
                return False
            
            # Load settings
            if not self._load_settings():
                logger.error("Failed to load settings")
                return False
            
            # Initialize image sources
            if not self._initialize_sources():
                logger.warning("[FALLBACK] No image sources initialized")
                # Continue anyway, might add sources later
            
            # Build image queue
            if not self._build_image_queue():
                logger.error("Failed to build image queue")
                return False
            
            # Initialize display manager
            if not self._initialize_display():
                logger.error("Failed to initialize display")
                return False
            
            # Setup rotation timer
            self._setup_rotation_timer()
            
            # Subscribe to events
            self._subscribe_to_events()
            
            logger.info("Engine initialization complete")
            return True
        
        except Exception as e:
            logger.exception(f"Engine initialization failed: {e}")
            self.error_occurred.emit(f"Initialization failed: {e}")
            return False
    
    def _initialize_core_systems(self) -> bool:
        """Initialize core framework systems."""
        try:
            logger.info("Initializing core systems...")
            
            # Event system
            self.event_system = EventSystem()
            logger.debug("EventSystem initialized")
            
            # Resource manager
            self.resource_manager = ResourceManager()
            logger.debug("ResourceManager initialized")
            
            # Thread manager
            self.thread_manager = ThreadManager()
            logger.debug("ThreadManager initialized")
            
            # Settings manager
            self.settings_manager = SettingsManager()
            logger.debug("SettingsManager initialized")
            
            logger.info("Core systems initialized successfully")
            return True
        
        except Exception as e:
            logger.exception(f"Core system initialization failed: {e}")
            return False
    
    def _load_settings(self) -> bool:
        """Load settings from configuration."""
        try:
            logger.info("Loading settings...")
            
            # Settings already loaded by SettingsManager on init
            # Just verify key settings exist
            
            interval = self.settings_manager.get('timing.interval', 10)
            logger.info(f"Image rotation interval: {interval}s")
            
            display_mode = self.settings_manager.get('display.mode', 'fill')
            logger.info(f"Display mode: {display_mode}")
            
            shuffle = self.settings_manager.get('queue.shuffle', True)
            logger.info(f"Shuffle enabled: {shuffle}")
            
            return True
        
        except Exception as e:
            logger.exception(f"Settings load failed: {e}")
            return False
    
    def _initialize_sources(self) -> bool:
        """Initialize image sources from settings."""
        try:
            logger.info("Initializing image sources...")
            
            sources_initialized = 0
            
            # Get folder sources from settings
            folder_paths = self.settings_manager.get('sources.folders', [])
            for folder_path in folder_paths:
                try:
                    folder_source = FolderSource(Path(folder_path))
                    self.folder_sources.append(folder_source)
                    logger.info(f"Folder source added: {folder_path}")
                    sources_initialized += 1
                except Exception as e:
                    logger.warning(f"[FALLBACK] Failed to add folder source {folder_path}: {e}")
            
            # Get RSS sources from settings
            rss_feeds = self.settings_manager.get('sources.rss_feeds', [])
            
            # If no custom RSS feeds, use defaults
            if not rss_feeds:
                logger.info("No custom RSS feeds, using defaults")
                rss_source = RSSSource()  # Uses default feeds
                self.rss_sources.append(rss_source)
                sources_initialized += 1
            else:
                for feed_url in rss_feeds:
                    try:
                        rss_source = RSSSource(custom_feeds=[feed_url])
                        self.rss_sources.append(rss_source)
                        logger.info(f"RSS source added: {feed_url}")
                        sources_initialized += 1
                    except Exception as e:
                        logger.warning(f"[FALLBACK] Failed to add RSS source {feed_url}: {e}")
            
            logger.info(f"Initialized {sources_initialized} image sources "
                       f"({len(self.folder_sources)} folder, {len(self.rss_sources)} RSS)")
            
            return sources_initialized > 0
        
        except Exception as e:
            logger.exception(f"Source initialization failed: {e}")
            return False
    
    def _build_image_queue(self) -> bool:
        """Build image queue from all sources."""
        try:
            logger.info("Building image queue...")
            
            # Get shuffle setting
            shuffle = self.settings_manager.get('queue.shuffle', True)
            history_size = self.settings_manager.get('queue.history_size', 50)
            
            # Create queue
            self.image_queue = ImageQueue(shuffle=shuffle, history_size=history_size)
            
            # Collect images from all sources
            all_images: List[ImageMetadata] = []
            
            # Folder sources
            for folder_source in self.folder_sources:
                try:
                    images = folder_source.get_images()
                    all_images.extend(images)
                    logger.info(f"Added {len(images)} images from {folder_source.folder_path}")
                except Exception as e:
                    logger.warning(f"[FALLBACK] Failed to get images from folder source: {e}")
            
            # RSS sources
            for rss_source in self.rss_sources:
                try:
                    images = rss_source.get_images()
                    all_images.extend(images)
                    logger.info(f"Added {len(images)} images from RSS source")
                except Exception as e:
                    logger.warning(f"[FALLBACK] Failed to get images from RSS source: {e}")
            
            if not all_images:
                logger.error("No images found from any source")
                self.error_occurred.emit("No images found")
                return False
            
            # Add to queue
            count = self.image_queue.add_images(all_images)
            logger.info(f"Image queue built with {count} images")
            
            # Log queue stats
            stats = self.image_queue.get_stats()
            logger.debug(f"Queue stats: {stats}")
            
            return True
        
        except Exception as e:
            logger.exception(f"Image queue build failed: {e}")
            return False
    
    def _initialize_display(self) -> bool:
        """Initialize display manager."""
        try:
            logger.info("Initializing display...")
            
            # Get display settings
            display_mode_str = self.settings_manager.get('display.mode', 'fill')
            display_mode = DisplayMode.from_string(display_mode_str)
            
            same_image = self.settings_manager.get('display.same_image_all_monitors', True)
            
            # Create display manager
            self.display_manager = DisplayManager(
                display_mode=display_mode,
                same_image_mode=same_image
            )
            
            # Connect exit signal
            self.display_manager.exit_requested.connect(self._on_exit_requested)
            
            # Initialize displays
            display_count = self.display_manager.initialize_displays()
            logger.info(f"Display initialized with {display_count} screens")
            
            return display_count > 0
        
        except Exception as e:
            logger.exception(f"Display initialization failed: {e}")
            return False
    
    def _setup_rotation_timer(self) -> None:
        """Setup timer for image rotation."""
        interval_seconds = self.settings_manager.get('timing.interval', 10)
        interval_ms = interval_seconds * 1000
        
        self._rotation_timer = QTimer(self)
        self._rotation_timer.setInterval(interval_ms)
        self._rotation_timer.timeout.connect(self._on_rotation_timer)
        
        logger.info(f"Rotation timer configured: {interval_seconds}s")
    
    def _subscribe_to_events(self) -> None:
        """Subscribe to relevant events."""
        if not self.event_system:
            return
        
        # Subscribe to settings changes
        self.event_system.subscribe('settings.changed', self._on_settings_changed)
        
        # Subscribe to monitor changes
        if self.display_manager:
            self.display_manager.monitors_changed.connect(self._on_monitors_changed)
        
        logger.debug("Event subscriptions configured")
    
    def start(self) -> bool:
        """
        Start the screensaver engine.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self._running:
            logger.warning("Engine already running")
            return True
        
        try:
            logger.info("Starting screensaver engine...")
            
            # Show first image immediately
            if not self._show_next_image():
                logger.warning("[FALLBACK] Failed to show first image")
                # Continue anyway, timer will retry
            
            # Start rotation timer
            if self._rotation_timer:
                self._rotation_timer.start()
                logger.info(f"Rotation timer started ({self._rotation_timer.interval()}ms)")
            
            self._running = True
            self.started.emit()
            logger.info("Screensaver engine started")
            
            return True
        
        except Exception as e:
            logger.exception(f"Engine start failed: {e}")
            self.error_occurred.emit(f"Start failed: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the screensaver engine."""
        if not self._running:
            logger.debug("Engine not running")
            return
        
        try:
            logger.info("Stopping screensaver engine...")
            
            # Stop rotation timer
            if self._rotation_timer:
                self._rotation_timer.stop()
                logger.debug("Rotation timer stopped")
            
            # Clear displays
            if self.display_manager:
                self.display_manager.clear_all()
                logger.debug("Displays cleared")
            
            self._running = False
            self.stopped.emit()
            logger.info("Screensaver engine stopped")
        
        except Exception as e:
            logger.exception(f"Engine stop failed: {e}")
    
    def cleanup(self) -> None:
        """Clean up all resources."""
        logger.info("Cleaning up screensaver engine...")
        
        try:
            # Stop if running
            if self._running:
                self.stop()
            
            # Cleanup display manager
            if self.display_manager:
                self.display_manager.cleanup()
                logger.debug("Display manager cleaned up")
            
            # Cleanup thread manager
            if self.thread_manager:
                self.thread_manager.shutdown()
                logger.debug("Thread manager shut down")
            
            # Cleanup resource manager
            if self.resource_manager:
                self.resource_manager.cleanup_all()
                logger.debug("Resources cleaned up")
            
            # Clear sources
            self.folder_sources.clear()
            self.rss_sources.clear()
            
            logger.info("Engine cleanup complete")
        
        except Exception as e:
            logger.exception(f"Cleanup failed: {e}")
    
    def _show_next_image(self) -> bool:
        """Load and display next image from queue."""
        if not self.image_queue or not self.display_manager:
            logger.warning("[FALLBACK] Queue or display not initialized")
            return False
        
        if self._loading_in_progress:
            logger.debug("Image load already in progress, skipping")
            return False
        
        try:
            # Get next image from queue
            image_meta = self.image_queue.next()
            
            if not image_meta:
                logger.warning("[FALLBACK] No image from queue")
                self.display_manager.show_error("No images available")
                return False
            
            self._current_image = image_meta
            
            # Load image asynchronously
            self._loading_in_progress = True
            
            # Submit to IO thread pool
            if self.thread_manager:
                future = self.thread_manager.submit_io_task(
                    self._load_image_task,
                    image_meta
                )
                # Note: Callback would be added here in production
                # For now, load synchronously in next step
            
            # For basic version, load synchronously
            return self._load_and_display_image(image_meta)
        
        except Exception as e:
            logger.exception(f"Show next image failed: {e}")
            self._loading_in_progress = False
            return False
    
    def _load_image_task(self, image_meta: ImageMetadata) -> Optional[QPixmap]:
        """
        Load image task (runs in thread pool).
        
        Args:
            image_meta: Image metadata
        
        Returns:
            Loaded QPixmap or None if failed
        """
        try:
            # Determine path
            if image_meta.local_path:
                image_path = str(image_meta.local_path)
            elif image_meta.url:
                # For RSS images, download first (already cached by RSSSource)
                logger.debug(f"Loading from URL: {image_meta.url}")
                # URL would be downloaded by RSSSource, use local_path
                if not image_meta.local_path:
                    logger.warning(f"[FALLBACK] No local path for URL image")
                    return None
                image_path = str(image_meta.local_path)
            else:
                logger.warning("[FALLBACK] No path or URL for image")
                return None
            
            # Load pixmap
            pixmap = QPixmap(image_path)
            
            if pixmap.isNull():
                logger.warning(f"[FALLBACK] Failed to load image: {image_path}")
                return None
            
            logger.debug(f"Image loaded: {image_path} ({pixmap.width()}x{pixmap.height()})")
            return pixmap
        
        except Exception as e:
            logger.exception(f"Image load task failed: {e}")
            return None
    
    def _load_and_display_image(self, image_meta: ImageMetadata) -> bool:
        """
        Load and display image synchronously.
        
        Args:
            image_meta: Image metadata
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load image
            pixmap = self._load_image_task(image_meta)
            
            if not pixmap:
                logger.warning("[FALLBACK] Image load failed")
                self.display_manager.show_error("Failed to load image")
                self._loading_in_progress = False
                return False
            
            # Display image
            image_path = str(image_meta.local_path) if image_meta.local_path else image_meta.url or "unknown"
            self.display_manager.show_image(pixmap, image_path)
            
            logger.info(f"Image displayed: {image_path}")
            self.image_changed.emit(image_path)
            
            self._loading_in_progress = False
            return True
        
        except Exception as e:
            logger.exception(f"Load and display failed: {e}")
            self._loading_in_progress = False
            return False
    
    def _on_rotation_timer(self) -> None:
        """Handle rotation timer timeout."""
        logger.debug("Rotation timer triggered")
        self._show_next_image()
    
    def _on_exit_requested(self) -> None:
        """Handle exit request from display."""
        logger.info("Exit requested from display")
        self.stop()
    
    def _on_settings_changed(self, event: Dict) -> None:
        """Handle settings changed event."""
        setting_key = event.get('key', '')
        logger.info(f"Setting changed: {setting_key}")
        
        # Handle specific settings changes
        if setting_key.startswith('timing.interval'):
            self._update_rotation_interval()
        elif setting_key.startswith('display.mode'):
            self._update_display_mode()
        elif setting_key.startswith('queue.shuffle'):
            self._update_shuffle_mode()
    
    def _on_monitors_changed(self, new_count: int) -> None:
        """Handle monitor configuration change."""
        logger.info(f"Monitor configuration changed: {new_count} monitors")
        
        # Reinitialize displays
        if self.display_manager:
            self.display_manager.cleanup()
            self._initialize_display()
            
            # Redisplay current image
            if self._current_image:
                self._load_and_display_image(self._current_image)
    
    def _update_rotation_interval(self) -> None:
        """Update rotation timer interval from settings."""
        if not self._rotation_timer:
            return
        
        interval_seconds = self.settings_manager.get('timing.interval', 10)
        interval_ms = interval_seconds * 1000
        
        self._rotation_timer.setInterval(interval_ms)
        logger.info(f"Rotation interval updated: {interval_seconds}s")
    
    def _update_display_mode(self) -> None:
        """Update display mode from settings."""
        if not self.display_manager:
            return
        
        display_mode_str = self.settings_manager.get('display.mode', 'fill')
        display_mode = DisplayMode.from_string(display_mode_str)
        
        self.display_manager.set_display_mode(display_mode)
        logger.info(f"Display mode updated: {display_mode}")
    
    def _update_shuffle_mode(self) -> None:
        """Update shuffle mode from settings."""
        if not self.image_queue:
            return
        
        shuffle = self.settings_manager.get('queue.shuffle', True)
        self.image_queue.set_shuffle_enabled(shuffle)
        logger.info(f"Shuffle mode updated: {shuffle}")
    
    def get_stats(self) -> Dict:
        """
        Get engine statistics.
        
        Returns:
            Dict with engine stats
        """
        stats = {
            'running': self._running,
            'current_image': str(self._current_image.local_path) if self._current_image and self._current_image.local_path else None,
            'loading': self._loading_in_progress,
            'folder_sources': len(self.folder_sources),
            'rss_sources': len(self.rss_sources),
        }
        
        if self.image_queue:
            stats['queue'] = self.image_queue.get_stats()
        
        if self.display_manager:
            stats['displays'] = self.display_manager.get_display_count()
        
        return stats
    
    def is_running(self) -> bool:
        """Check if engine is running."""
        return self._running
