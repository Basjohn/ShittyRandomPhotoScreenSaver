"""
Main screensaver engine - orchestrates all components.

The ScreensaverEngine is the central controller that:
- Initializes all core systems
- Manages image sources and queue
- Handles display across monitors
- Controls image rotation timing
- Processes events and user input
"""
import threading
from pathlib import Path
from typing import Optional, List, Dict
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap

from core.events import EventSystem
from core.resources import ResourceManager
from core.threading import ThreadManager
from core.settings import SettingsManager
from core.logging.logger import get_logger
from core.animation import AnimationManager

from engine.display_manager import DisplayManager
from engine.image_queue import ImageQueue
from sources.folder_source import FolderSource
from sources.rss_source import RSSSource
from sources.base_provider import ImageMetadata
from rendering.display_modes import DisplayMode
from ui.settings_dialog import SettingsDialog

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
        self._initialized: bool = False
        self._display_initialized: bool = False
        self._rotation_timer: Optional[QTimer] = None
        self._current_image: Optional[ImageMetadata] = None
        self._loading_in_progress: bool = False
        self._loading_lock = threading.Lock()  # FIX: Protect loading flag from race conditions
        self._transition_types: List[str] = ["Crossfade", "Slide", "Wipe", "Diffuse", "Block Puzzle Flip"]
        self._current_transition_index: int = 0  # Will sync with settings in initialize()
        
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
            
            # Sync transition cycle index with current settings
            current_transition = self.settings_manager.get('transitions', {}).get('type', 'Crossfade')
            try:
                self._current_transition_index = self._transition_types.index(current_transition)
                logger.debug(f"Transition cycle index synced to {self._current_transition_index} ({current_transition})")
            except ValueError:
                self._current_transition_index = 0
                logger.debug(f"Unknown transition '{current_transition}', defaulting to index 0")
            
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
            
            # Get folder sources from settings (using dot notation)
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
            
            # Only use RSS feeds if explicitly configured by user
            for feed_url in rss_feeds:
                try:
                    rss_source = RSSSource(feed_urls=[feed_url])
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
                same_image_mode=same_image,
                settings_manager=self.settings_manager
            )
            
            # Connect exit signal
            self.display_manager.exit_requested.connect(self._on_exit_requested)
            
            # Connect hotkey signals
            self.display_manager.previous_requested.connect(self._on_previous_requested)
            self.display_manager.next_requested.connect(self._on_next_requested)
            self.display_manager.cycle_transition_requested.connect(self._on_cycle_transition)
            self.display_manager.settings_requested.connect(self._on_settings_requested)
            
            # Initialize displays
            display_count = self.display_manager.initialize_displays()
            logger.info(f"Display initialized with {display_count} screens")
            
            # Set flag on success
            if display_count > 0:
                self._display_initialized = True
                return True
            
            return False
        
        except Exception as e:
            logger.exception(f"Display initialization failed: {e}")
            self._display_initialized = False
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
    
    def stop(self, exit_app: bool = True) -> None:
        """
        Stop the screensaver engine.
        
        Args:
            exit_app: If True, quit the application. If False, just stop the engine.
        """
        if not self._running:
            logger.debug("Engine not running")
            return
        
        try:
            logger.info("Stopping screensaver engine...")
            
            # Mark as not running immediately to prevent re-entry
            self._running = False
            
            # Stop rotation timer (check if not already deleted)
            if self._rotation_timer:
                try:
                    self._rotation_timer.stop()
                    self._rotation_timer.deleteLater()
                    logger.debug("Rotation timer stopped")
                except RuntimeError as e:
                    logger.debug(f"Timer already deleted during cleanup: {e}")
            
            # Clear and hide/cleanup displays
            if self.display_manager:
                self.display_manager.clear_all()
                if exit_app:
                    # Exiting app - full cleanup
                    self.display_manager.cleanup()
                    logger.debug("Displays cleared and cleaned up")
                else:
                    # Just pausing (e.g., for settings) - hide windows
                    self.display_manager.hide_all()
                    logger.debug("Displays cleared and hidden")
            
            # Stop any pending image loads
            self._loading_in_progress = False
            
            self.stopped.emit()
            logger.info("Screensaver engine stopped")
            
            # Only exit the Qt event loop if requested
            if exit_app:
                from PySide6.QtWidgets import QApplication
                QApplication.quit()
        
        except Exception as e:
            logger.exception(f"Engine stop failed: {e}")
            # Force quit on error only if exit_app was requested
            if exit_app:
                try:
                    from PySide6.QtWidgets import QApplication
                    QApplication.quit()
                except Exception as quit_error:
                    logger.error(f"Failed to quit application: {quit_error}")
    
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
        
        # FIX: Atomic check-and-set for loading flag to prevent race condition
        with self._loading_lock:
            if self._loading_in_progress:
                logger.debug("Image load already in progress, skipping")
                return False
            # Set flag inside lock to make check-and-set atomic
            self._loading_in_progress = True
        
        try:
            # Get next image from queue
            image_meta = self.image_queue.next()
            
            if not image_meta:
                logger.warning("[FALLBACK] No image from queue")
                self.display_manager.show_error("No images available")
                with self._loading_lock:
                    self._loading_in_progress = False
                return False
            
            self._current_image = image_meta
            
            # Submit to IO thread pool
            # FIX: Use async properly or remove - keeping sync for now
            if self.thread_manager:
                # Future not used - load sync below
                pass
            
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
                    logger.warning("[FALLBACK] No local path for URL image")
                    return None
                image_path = str(image_meta.local_path)
            else:
                logger.warning("[FALLBACK] No path or URL for image")
                return None
            
            # Load pixmap
            pixmap = QPixmap(image_path)
            
            if pixmap.isNull():
                logger.warning("Image load failed for: %s", image_path)
                return None
            
            logger.debug(f"Image loaded: {image_path} ({pixmap.width()}x{pixmap.height()})")
            return pixmap
        
        except Exception as e:
            logger.exception(f"Image load task failed: {e}")
            return None
    
    def _load_and_display_image(self, image_meta: ImageMetadata, retry_count: int = 0) -> bool:
        """
        Load and display image synchronously. Auto-retries with next image on failure.
        
        Args:
            image_meta: Image metadata
            retry_count: Number of retries attempted (max 10)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load image
            pixmap = self._load_image_task(image_meta)
            
            if not pixmap:
                logger.warning(f"[FALLBACK] Image load failed, attempting next image (retry {retry_count + 1}/10)")
                self._loading_in_progress = False
                
                # Try next image automatically (up to 10 times)
                # FIX: Use correct method name 'next()' not 'get_next()'
                if retry_count < 10 and self.image_queue:
                    next_image = self.image_queue.next()
                    if next_image:
                        return self._load_and_display_image(next_image, retry_count + 1)
                
                # All retries exhausted
                logger.error("[FALLBACK] Failed to load any images after 10 attempts")
                self.display_manager.show_error("No valid images available")
                return False
            
            # Display image
            image_path = str(image_meta.local_path) if image_meta.local_path else image_meta.url or "unknown"
            
            # Check if we should show same image on all displays or different images
            same_image = self.settings_manager.get('display.same_image_all_monitors', True)
            logger.debug(f"Same image on all monitors setting: {same_image} (type: {type(same_image)})")
            
            # Convert to bool if string
            if isinstance(same_image, str):
                same_image = same_image.lower() in ('true', '1', 'yes')
            
            if same_image:
                # Show same image on all displays
                self.display_manager.show_image(pixmap, image_path)
                logger.info(f"Image displayed: {image_path}")
            else:
                # Show different image on each display
                display_count = len(self.display_manager.displays)
                for i in range(display_count):
                    if i == 0:
                        # First display gets the current image
                        self.display_manager.show_image_on_screen(i, pixmap, image_path)
                    else:
                        # Other displays get next images from queue
                        next_meta = self.image_queue.next() if self.image_queue else None
                        if next_meta:
                            next_pixmap = self._load_image_task(next_meta)
                            if next_pixmap:
                                next_path = str(next_meta.local_path) if next_meta.local_path else next_meta.url or "unknown"
                                self.display_manager.show_image_on_screen(i, next_pixmap, next_path)
                logger.info(f"Different images displayed on {display_count} displays")
            
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
    
    def _on_previous_requested(self) -> None:
        """Handle previous image request (Z key)."""
        logger.info("Previous image requested")
        if self.image_queue:
            self.image_queue.previous()
            self._show_current_image()
    
    def _on_next_requested(self) -> None:
        """Handle next image request (X key)."""
        logger.info("Next image requested")
        self._show_next_image()
    
    def _on_cycle_transition(self) -> None:
        """Handle cycle transition request (C key)."""
        logger.info("Cycle transition requested")
        
        # Cycle to next transition
        self._current_transition_index = (self._current_transition_index + 1) % len(self._transition_types)
        new_transition = self._transition_types[self._current_transition_index]
        
        # Update settings
        transitions_config = self.settings_manager.get('transitions', {})
        transitions_config['type'] = new_transition
        self.settings_manager.set('transitions', transitions_config)
        self.settings_manager.save()
        
        logger.info(f"Transition cycled to: {new_transition}")
        
        # FIX: Don't force same image on all displays - preserve multi-monitor independence
        # Each display should keep its current image and just use the new transition type
        # No need to reload - the transition type is stored in settings and will be used
        # on the next natural image change
        logger.debug("Transition type updated in settings - will apply on next image change")
    
    def _on_settings_requested(self) -> None:
        """Handle settings request (S key)."""
        logger.info("Settings requested - pausing screensaver and opening config")
        
        # Stop the engine but DON'T exit the app
        self.stop(exit_app=False)
        
        try:
            app = QApplication.instance()
            if app:
                animations = AnimationManager()
                dialog = SettingsDialog(self.settings_manager, animations)
                # FIX: Use result or mark as intentionally ignored
                _ = dialog.exec()  # Result intentionally ignored - dialog handles its own state
                
                # After dialog closes, show displays again and restart
                logger.info("Settings dialog closed, restarting screensaver...")
                
                # Show displays again
                if self.display_manager:
                    self.display_manager.show_all()
                
                if self._display_initialized:
                    self.start()
                else:
                    # If displays weren't initialized, try to initialize them
                    if self.initialize():
                        self.start()
                    else:
                        # Initialization failed, exit
                        logger.error("Failed to restart screensaver")
                        QApplication.quit()
        except Exception as e:
            logger.exception(f"Failed to open settings dialog: {e}")
            QApplication.quit()
    
    def _show_current_image(self) -> bool:
        """Show the current image from queue without advancing."""
        if not self.image_queue:
            return False
        
        current = self.image_queue.current()
        if current:
            return self._load_and_display_image(current)
        return False
    
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
