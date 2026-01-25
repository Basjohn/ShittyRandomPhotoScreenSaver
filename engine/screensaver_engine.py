"""
Main screensaver engine - orchestrates all components.

The ScreensaverEngine is the central controller that:
- Initializes all core systems
- Manages image sources and queue
- Handles display across monitors
- Controls image rotation timing
- Processes events and user input

State Management:
    The engine uses an EngineState enum to track lifecycle state.
    This replaces the previous ad-hoc boolean flags (_running, _shutting_down, etc.)
    that caused bugs when state transitions were inconsistent.
    
    Valid state transitions:
        UNINITIALIZED -> INITIALIZING -> STOPPED
        STOPPED -> STARTING -> RUNNING
        RUNNING -> STOPPING -> STOPPED
        RUNNING -> REINITIALIZING -> RUNNING (for settings changes)
        Any state -> SHUTTING_DOWN (terminal)
"""
import random
import threading
import time
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from PySide6.QtCore import QObject, Signal, QTimer, QSize, QMetaObject, Qt, QThread, QCoreApplication
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QImage

from core.constants.timing import TRANSITION_STAGGER_MS
from core.events import EventSystem, EventType
from core.logging.tags import TAG_WORKER, TAG_PERF, TAG_RSS, TAG_ASYNC
from core.resources import ResourceManager
from core.threading import ThreadManager
from core.settings import SettingsManager
from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from core.rss.pipeline_manager import get_rss_pipeline_manager, RssPipelineManager
from core.animation import AnimationManager
from core.process import ProcessSupervisor, WorkerType, MessageType
from core.process.workers import (
    image_worker_main,
    rss_worker_main,
    fft_worker_main,
    transition_worker_main,
)

from engine.display_manager import DisplayManager
from engine.image_queue import ImageQueue
from sources.folder_source import FolderSource
from sources.rss_source import RSSSource
from sources.base_provider import (
    ImageMetadata,
    ImageSourceType,
)
from rendering.display_modes import DisplayMode
from rendering.image_processor_async import AsyncImageProcessor
from ui.settings_dialog import SettingsDialog
from utils.image_cache import ImageCache
from utils.image_prefetcher import ImagePrefetcher

logger = get_logger(__name__)


class EngineState(Enum):
    """Engine lifecycle states.
    
    This enum replaces the previous boolean flags (_running, _shutting_down, 
    _initialized, _display_initialized) which had complex interdependencies
    and caused bugs when state transitions were inconsistent.
    
    State Transition Diagram:
        UNINITIALIZED ──► INITIALIZING ──► STOPPED
                                              │
                                              ▼
                                          STARTING ──► RUNNING
                                              ▲            │
                                              │            ▼
                                          STOPPED ◄── STOPPING
                                              │
                                              ▼
                                       SHUTTING_DOWN (terminal)
        
        RUNNING ──► REINITIALIZING ──► RUNNING (for settings changes)
    """
    UNINITIALIZED = auto()    # Initial state before initialize()
    INITIALIZING = auto()     # During initialize()
    STOPPED = auto()          # Initialized but not running
    STARTING = auto()         # During start()
    RUNNING = auto()          # Active and displaying images
    STOPPING = auto()         # During stop() with exit_app=False
    REINITIALIZING = auto()   # During _on_sources_changed()
    SHUTTING_DOWN = auto()    # During stop() with exit_app=True (terminal)


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
    
    # Class-level tracking for engine running state
    _instance_running = False
    _instance_lock = threading.Lock()
    
    @classmethod
    def _is_engine_running(cls) -> bool:
        """Check if any engine instance is currently running."""
        with cls._instance_lock:
            return cls._instance_running
    
    def __init__(self):
        """Initialize screensaver engine."""
        super().__init__()
        
        # Core systems (initialized later)
        self.event_system: Optional[EventSystem] = None
        self.resource_manager: Optional[ResourceManager] = None
        self.thread_manager: Optional[ThreadManager] = None
        self.settings_manager: Optional[SettingsManager] = None
        self._rss_pipeline: RssPipelineManager = get_rss_pipeline_manager()
        
        # Engine components
        self.display_manager: Optional[DisplayManager] = None
        self.image_queue: Optional[ImageQueue] = None
        
        # Image sources
        self.folder_sources: List[FolderSource] = []
        self.rss_sources: List[RSSSource] = []
        
        # State - using EngineState enum for coherent lifecycle management
        # This replaces the previous boolean flags that caused the RSS reload bug
        self._state: EngineState = EngineState.UNINITIALIZED
        self._state_lock = threading.Lock()  # Protect state transitions
        
        # Legacy compatibility properties (read-only, derived from _state)
        # These are kept for backwards compatibility but should not be set directly
        
        self._display_initialized: bool = False  # Still needed for display-specific init
        self._rotation_timer: Optional[QTimer] = None
        self._current_image: Optional[ImageMetadata] = None
        self._loading_in_progress: bool = False
        self._loading_lock = threading.Lock()  # FIX: Protect loading flag from race conditions
        # Canonical list of transition types used for C-key cycling. Legacy
        # "Claw Marks" entries have been fully removed from the engine and are
        # mapped to "Crossfade" at selection time for back-compat only. The
        # Shuffle transition has been retired for v1.2 and no longer appears in
        # the active rotation.
        self._transition_types: List[str] = [
            "Ripple",            # 1. GL-only (formerly "Rain Drops")
            "Wipe",              # 2. Directional
            "3D Block Spins",    # 3. GL-only
            "Diffuse",           # 4. Particle dissolve
            "Slide",             # 5. Directional
            "Crossfade",         # 6. Classic fallback
            "Peel",              # 7. GL-only, directional
            "Block Puzzle Flip", # 8. Tile flip
            "Warp Dissolve",     # 9. GL-only
            "Blinds",            # 10. GL-only
            "Crumble",           # 11. GL-only, falling pieces
            "Particle",
        ]
        self._current_transition_index: int = 0  # Will sync with settings in initialize()
        # Caching / prefetch
        self._image_cache: Optional[ImageCache] = None
        self._prefetcher: Optional[ImagePrefetcher] = None
        self._prefetch_ahead: int = 5
        # Background RSS refresh
        self._rss_refresh_timer: Optional[QTimer] = None
        self._rss_merge_lock = threading.Lock()
        self._rss_async_generation: int = 0
        self._rss_async_active: bool = False
        
        # Process Supervisor for multiprocessing workers
        self._process_supervisor: Optional[ProcessSupervisor] = None
        
        logger.info("ScreensaverEngine created")
    
    # -------------------------------------------------------------------------
    # State Management - EngineState enum with thread-safe transitions
    # -------------------------------------------------------------------------
    
    @property
    def _running(self) -> bool:
        """Legacy compatibility: True if engine is in RUNNING state."""
        return self._state == EngineState.RUNNING
    
    @property
    def _initialized(self) -> bool:
        """Legacy compatibility: True if engine has been initialized."""
        return self._state not in (EngineState.UNINITIALIZED, EngineState.INITIALIZING)
    
    @property
    def _shutting_down(self) -> bool:
        """Legacy compatibility: True if engine is shutting down or stopping.
        
        This is the critical property that async tasks check to abort.
        Returns True for STOPPING and SHUTTING_DOWN states.
        Returns False for REINITIALIZING (settings changes should NOT abort RSS).
        """
        return self._state in (EngineState.STOPPING, EngineState.SHUTTING_DOWN)
    
    def _transition_state(self, new_state: EngineState, expected_from: Optional[List[EngineState]] = None) -> bool:
        """Thread-safe state transition with validation.
        
        Args:
            new_state: The state to transition to
            expected_from: Optional list of valid source states. If provided,
                          transition only succeeds if current state is in this list.
        
        Returns:
            True if transition succeeded, False if invalid transition
        """
        with self._state_lock:
            old_state = self._state
            
            # Validate transition if expected_from is specified
            if expected_from is not None and old_state not in expected_from:
                logger.warning(
                    f"Invalid state transition: {old_state.name} -> {new_state.name} "
                    f"(expected from: {[s.name for s in expected_from]})"
                )
                return False
            
            # Prevent transitions from terminal state
            if old_state == EngineState.SHUTTING_DOWN and new_state != EngineState.SHUTTING_DOWN:
                logger.warning(f"Cannot transition from SHUTTING_DOWN to {new_state.name}")
                return False
            
            self._state = new_state
            logger.info(f"Engine state: {old_state.name} -> {new_state.name}")
            return True
    
    def _get_state(self) -> EngineState:
        """Thread-safe state getter."""
        with self._state_lock:
            return self._state
    
    def _is_state(self, *states: EngineState) -> bool:
        """Thread-safe check if current state is one of the given states."""
        with self._state_lock:
            return self._state in states
    
    def initialize(self) -> bool:
        """
        Initialize all engine components.
        
        State transition: UNINITIALIZED -> INITIALIZING -> STOPPED
        
        Returns:
            True if initialization successful, False otherwise
        """
        # Validate and transition state
        if not self._transition_state(
            EngineState.INITIALIZING, 
            expected_from=[EngineState.UNINITIALIZED]
        ):
            logger.error("Cannot initialize: invalid state")
            return False
        
        try:
            logger.info("=" * 60)
            logger.info("Initializing Screensaver Engine 🚦🚦🚦🚦🚦")
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
            # Initialize cache + prefetcher after queue is ready
            self._initialize_cache_prefetcher()

            if self.image_queue:
                self._rss_pipeline.rebuild_dedupe_index(self.image_queue)
            
            # Initialize display manager
            if not self._initialize_display():
                logger.error("Failed to initialize display")
                return False
            
            # Setup rotation timer
            self._setup_rotation_timer()
            
            # Subscribe to events
            self._subscribe_to_events()

            # Enable background RSS refresh if applicable
            self._start_rss_background_refresh_if_needed()
            
            # Start multiprocessing workers (non-blocking, fallback if workers fail)
            self._start_workers()
            
            # Transition to STOPPED state (ready to start)
            self._transition_state(EngineState.STOPPED)
            
            logger.info("Engine initialization complete")
            return True
        
        except Exception as e:
            logger.exception(f"Engine initialization failed: {e}")
            self.error_occurred.emit(f"Initialization failed: {e}")
            # Revert to UNINITIALIZED on failure
            self._transition_state(EngineState.UNINITIALIZED)
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

            try:
                self.settings_manager.set_event_system(self.event_system)
            except Exception as e:
                logger.debug("[ENGINE] Failed to attach EventSystem to SettingsManager: %s", e)
            
            # Bridge SettingsManager Qt Signal to EventSystem
            # This allows the engine to receive settings changes via EventSystem
            def _on_settings_signal(key: str, value: object) -> None:
                if self.event_system:
                    self.event_system.publish('settings.changed', {'key': key, 'value': value})
            
            self.settings_manager.settings_changed.connect(_on_settings_signal)
            logger.debug("SettingsManager signal bridged to EventSystem")
            
            # Sync transition cycle index with current settings
            current_transition = self.settings_manager.get('transitions', {}).get('type', 'Crossfade')
            try:
                self._current_transition_index = self._transition_types.index(current_transition)
                logger.debug(f"Transition cycle index synced to {self._current_transition_index} ({current_transition})")
            except ValueError:
                self._current_transition_index = 0
                logger.debug(f"Unknown transition '{current_transition}', defaulting to index 0")
            
            # Initialize ProcessSupervisor for multiprocessing workers
            self._process_supervisor = ProcessSupervisor(
                resource_manager=self.resource_manager,
                settings_manager=self.settings_manager,
                event_system=self.event_system,
            )
            
            # Register worker factories
            self._process_supervisor.register_worker_factory(WorkerType.IMAGE, image_worker_main)
            self._process_supervisor.register_worker_factory(WorkerType.RSS, rss_worker_main)
            self._process_supervisor.register_worker_factory(WorkerType.FFT, fft_worker_main)
            self._process_supervisor.register_worker_factory(WorkerType.TRANSITION, transition_worker_main)
            logger.info("ProcessSupervisor initialized with 4 worker factories")
            
            # Initialize RSS pipeline now that core managers exist
            self._rss_pipeline.initialize(
                thread_manager=self.thread_manager,
                resource_manager=self.resource_manager,
                settings_manager=self.settings_manager,
            )

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
            # Cache-related settings
            self._prefetch_ahead = int(self.settings_manager.get('cache.prefetch_ahead', 5))
            logger.info(f"Prefetch ahead: {self._prefetch_ahead}")
            
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
            rss_save_to_disk = self.settings_manager.get('sources.rss_save_to_disk', False)
            rss_save_directory = self.settings_manager.get('sources.rss_save_directory', '')

            # NO startup cap - let RSS sources download as many images as they can
            # The async loading happens in background and doesn't block startup
            # Rate limiting is handled by the RSSSource itself with delays between feeds
            
            # Only use RSS feeds if explicitly configured by user
            for feed_url in rss_feeds:
                try:
                    # Create RSS source with save-to-disk settings if enabled
                    if rss_save_to_disk and rss_save_directory:
                        rss_source = RSSSource(
                            feed_urls=[feed_url],
                            save_to_disk=True,
                            save_directory=Path(rss_save_directory),
                        )
                        logger.info(f"RSS source added with save-to-disk: {feed_url} -> {rss_save_directory}")
                    else:
                        rss_source = RSSSource(
                            feed_urls=[feed_url],
                        )
                        logger.info(f"RSS source added: {feed_url}")
                    
                    self.rss_sources.append(rss_source)
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
        """Build image queue from all sources.
        
        Local images are loaded synchronously for immediate startup.
        RSS images are loaded asynchronously to avoid blocking.
        """
        try:
            logger.info("Building image queue...")
            
            # Get queue settings
            shuffle = self.settings_manager.get('queue.shuffle', True)
            history_size = self.settings_manager.get('queue.history_size', 50)
            local_ratio = self.settings_manager.get('sources.local_ratio', 60)
            
            # Create queue with ratio-based source selection
            self.image_queue = ImageQueue(
                shuffle=shuffle,
                history_size=history_size,
                local_ratio=local_ratio
            )
            
            # Collect LOCAL images first (synchronous - fast)
            local_images: List[ImageMetadata] = []
            for folder_source in self.folder_sources:
                try:
                    images = folder_source.get_images()
                    local_images.extend(images)
                    logger.info(f"Added {len(images)} images from {folder_source.folder_path}")
                except Exception as e:
                    logger.warning(f"[FALLBACK] Failed to get images from folder source: {e}")
            
            # Add local images to queue immediately
            if local_images:
                count = self.image_queue.add_images(local_images)
                logger.info(f"Queue initialized with {count} local images")
            
            # Pre-load cached RSS images BEFORE starting async download
            # This gives immediate RSS variety without waiting for network
            if self.rss_sources:
                per_feed_seed = self._get_rss_sync_seed_limit()
                cached_rss_images: List[ImageMetadata] = []
                for rss_source in self.rss_sources:
                    # get_images() here only returns cached entries because
                    # refresh has not been called yet. Limit per feed so we
                    # do not block startup with hundreds of files.
                    cached = rss_source.get_images()
                    if cached:
                        cached_rss_images.extend(cached[:per_feed_seed])
                
                if cached_rss_images:
                    # Enforce RSS cap on initial load - only load up to rss_rotating_cache_size
                    rotating_cache_size = 20
                    try:
                        if self.settings_manager:
                            rotating_cache_size = int(self.settings_manager.get('sources.rss_rotating_cache_size', 20))
                    except Exception as e:
                        logger.debug(f"{TAG_RSS} Failed to get rotating cache size: %s", e)
                    # Limit cached images to rotating cache size
                    if len(cached_rss_images) > rotating_cache_size:
                        import random
                        random.shuffle(cached_rss_images)
                        cached_rss_images = cached_rss_images[:rotating_cache_size]
                    count = self.image_queue.add_images(cached_rss_images)
                    logger.info(f"Pre-loaded {count} cached RSS images for immediate use (cap={rotating_cache_size})")
                    self._rss_pipeline.record_images(cached_rss_images)
            
            # Load RSS images asynchronously (don't block startup)
            if self.rss_sources:
                self._load_rss_images_async()
            
            # If we have no local images and no RSS sources, fail
            if not local_images and not self.rss_sources:
                logger.error("No images found from any source")
                self.error_occurred.emit("No images found")
                return False
            
            # If we only have RSS sources and no local images, we need to wait
            # for at least some RSS images before we can start
            if not local_images and self.rss_sources:
                logger.info("No local images - waiting for RSS images to load...")
                # This is the ONLY case where we block on RSS
                self._load_rss_images_sync()
                min_required = self._get_minimum_rss_start_images()
                if min_required > 0:
                    if not self._wait_for_min_rss_images(min_required):
                        logger.warning(
                            "[ASYNC RSS] Startup guard timed out with only %d/%d RSS images; continuing anyway",
                            self._count_unique_rss_images(),
                            min_required,
                        )
                if self.image_queue.total_images() == 0:
                    logger.error("No images found from RSS sources")
                    self.error_occurred.emit("No images found")
                    return False
            
            logger.info(f"Image queue ready with {self.image_queue.total_images()} images")
            
            # Log queue stats
            stats = self.image_queue.get_stats()
            logger.debug(f"Queue stats: {stats}")
            
            return True
        
        except Exception as e:
            logger.exception(f"Image queue build failed: {e}")
            return False
    
    def _fetch_rss_via_worker(
        self,
        feed_url: str,
        cache_dir: Optional[str] = None,
        max_images: int = 8,
        timeout_ms: int = 30000,
    ) -> Optional[List[Dict]]:
        """
        Fetch RSS feed using RSSWorker process.
        
        Uses the RSSWorker for fetch/parse in a separate process,
        avoiding blocking the main process. Falls back to None if worker unavailable.
        
        Args:
            feed_url: URL of the RSS feed
            cache_dir: Directory to cache downloaded images
            max_images: Maximum images to fetch
            timeout_ms: Timeout for worker response
            
        Returns:
            List of image info dicts if successful, None if worker unavailable or failed
        """
        if not self._process_supervisor or not self._process_supervisor.is_running(WorkerType.RSS):
            return None
        
        try:
            import time
            
            # Send fetch request to RSSWorker
            correlation_id = self._process_supervisor.send_message(
                WorkerType.RSS,
                MessageType.RSS_FETCH,
                payload={
                    "feed_url": feed_url,
                    "cache_dir": cache_dir,
                    "max_images": max_images,
                },
            )
            
            if not correlation_id:
                logger.debug(f"{TAG_WORKER} Failed to send message to RSSWorker")
                return None
            
            # Poll for response with timeout
            start_time = time.time()
            timeout_s = timeout_ms / 1000.0
            
            while (time.time() - start_time) < timeout_s:
                # Check for shutdown
                if self._shutting_down:
                    return None
                
                responses = self._process_supervisor.poll_responses(WorkerType.RSS, max_count=10)
                
                for response in responses:
                    if response.correlation_id == correlation_id:
                        if response.success:
                            payload = response.payload
                            images = payload.get("images", [])
                            
                            if is_perf_metrics_enabled():
                                proc_time = response.processing_time_ms or 0
                                logger.info(
                                    f"{TAG_PERF} {TAG_WORKER} RSSWorker fetch: %d images in %.1fms",
                                    len(images), proc_time
                                )
                            
                            return images
                        else:
                            error = response.error or "Unknown error"
                            logger.warning(f"{TAG_WORKER} RSSWorker failed: %s", error)
                            return None
                
                # Brief sleep to avoid busy-waiting
                time.sleep(0.05)
            
            logger.warning(f"{TAG_WORKER} RSSWorker timeout after %dms", timeout_ms)
            return None
            
        except Exception as e:
            logger.warning(f"{TAG_WORKER} RSSWorker error: %s", e)
            return None
    
    def _load_rss_images_async(self) -> None:
        """Load RSS images asynchronously in the background.
        
        This doesn't block startup - RSS images are merged into the queue
        when they become available.
        
        IMPORTANT: This task checks self._running and exits immediately
        when the engine is stopped. No blocking waits that prevent exit.
        """
        if not self.rss_sources or not self.thread_manager:
            return
        
        generation = self._next_rss_async_generation()
        self._rss_async_active = True
        logger.info(
            "[ASYNC RSS] Starting async RSS load for %d sources (gen=%d)...",
            len(self.rss_sources),
            generation,
        )
        
        # Capture reference to self for closure
        engine = self
        
        # Set shutdown callback on all RSS sources so they can abort during downloads
        generation_token = generation

        def should_continue() -> bool:
            return (generation_token == engine._rss_async_generation) and (not engine._shutting_down)
        
        for rss_source in self.rss_sources:
            rss_source.set_shutdown_check(should_continue)
        
        def load_rss_task():
            """Background task to load RSS images with rate limiting.
            
            Respects engine shutdown - exits immediately when _running is False.
            Processes non-Reddit sources first for faster cache building.
            Downloads limited images per source to avoid blocking.
            
            Uses RSSWorker process when available for network I/O isolation.
            """
            import time
            from pathlib import Path
            from sources.rss_source import _get_source_priority
            
            rss_images: List[ImageMetadata] = []

            def is_cancelled() -> bool:
                return generation != engine._rss_async_generation or engine._shutting_down
            
            try:
                # Check if RSSWorker is available
                use_worker = (
                    engine._process_supervisor is not None and 
                    engine._process_supervisor.is_running(WorkerType.RSS)
                )
                
                if use_worker:
                    logger.info("[ASYNC RSS] Using RSSWorker process for RSS loading")
                
                # Sort sources by priority - non-Reddit first (higher priority = earlier)
                # Each RSSSource has feed_urls attribute with the feed URL(s)
                def get_source_priority(src):
                    if hasattr(src, 'feed_urls') and src.feed_urls:
                        return _get_source_priority(src.feed_urls[0])
                    return 50
                
                sources = sorted(engine.rss_sources, key=get_source_priority, reverse=True)

                if is_cancelled():
                    logger.debug("[ASYNC RSS] Cancelled before start (gen=%d)", generation)
                    return
                
                # Get cache directory from first source if available
                cache_dir = None
                for src in sources:
                    if hasattr(src, '_cache_dir') and src._cache_dir:
                        cache_dir = str(src._cache_dir)
                        break
                
                for i, rss_source in enumerate(sources):
                    # CHECK FOR SHUTDOWN - only abort if actually shutting down
                    if is_cancelled():
                        logger.info("[ASYNC RSS] Load cancelled mid-run (gen=%d)", generation)
                        logger.info("[ASYNC RSS] Engine shutting down, aborting RSS load")
                        return
                    
                    try:
                        if is_cancelled():
                            logger.info("[ASYNC RSS] Load cancelled mid-run (gen=%d)", generation)
                            return

                        feed_url = rss_source.feed_urls[0] if hasattr(rss_source, 'feed_urls') and rss_source.feed_urls else 'unknown'
                        logger.info(f"[ASYNC RSS] Processing source {i+1}/{len(sources)}: {feed_url[:60]}...")
                        
                        images_before = len(rss_images)
                        images: List[ImageMetadata] = []
                        worker_succeeded = False
                        
                        # Try RSSWorker first if available
                        if use_worker:
                            worker_result = engine._fetch_rss_via_worker(
                                feed_url,
                                cache_dir=cache_dir,
                                max_images=8,
                                timeout_ms=30000,
                                generation_token=generation_token,
                            )
                            
                            if worker_result is not None:
                                # Convert worker response dicts to ImageMetadata objects
                                for img_dict in worker_result:
                                    try:
                                        local_path = img_dict.get("local_path")
                                        if local_path:
                                            local_path = Path(local_path)
                                        
                                        meta = ImageMetadata(
                                            source_type=ImageSourceType.RSS,
                                            source_id=img_dict.get("source_id", ""),
                                            url=img_dict.get("url"),
                                            local_path=local_path,
                                            title=img_dict.get("title", ""),
                                        )
                                        images.append(meta)
                                    except Exception as e:
                                        logger.debug(f"[ASYNC RSS] Failed to convert worker result: {e}")
                                
                                if images:
                                    worker_succeeded = True
                                    logger.debug(f"[ASYNC RSS] RSSWorker returned {len(images)} images")
                        
                        # Fallback to RSSSource if worker failed or unavailable
                        if not worker_succeeded:
                            if use_worker:
                                logger.debug("[ASYNC RSS] RSSWorker failed, falling back to RSSSource")
                            rss_source.refresh(max_images_per_source=8)
                            images = rss_source.get_images()
                        
                        rss_images.extend(images)
                        images_added = len(rss_images) - images_before
                        
                        if images_added > 0:
                            logger.info(f"[ASYNC RSS] Loaded {images_added} images from source")
                            # Add images to queue immediately so user sees them
                            # But respect the background cap
                            if engine.image_queue and not engine._shutting_down:
                                cap = engine._get_rss_background_cap()
                                current_rss = sum(1 for m in engine.image_queue.get_all_images() 
                                                if getattr(m, 'source_type', None) == ImageSourceType.RSS)
                                remaining = max(0, cap - current_rss)
                                if remaining > 0:
                                    to_add = images[:remaining] if len(images) > remaining else images
                                    engine.image_queue.add_images(to_add)
                                    logger.debug(f"[ASYNC RSS] Added {len(to_add)} images (cap={cap}, current={current_rss})")
                                else:
                                    logger.debug(f"[ASYNC RSS] RSS cap reached ({cap}), skipping {len(images)} images")
                        else:
                            logger.warning(f"[ASYNC RSS] Source returned 0 images (may be rate limited): {feed_url}")
                        
                        # Mark first load done so shutdown check works properly
                        engine._rss_first_load_done = True
                        
                        # Add delay between sources to avoid rate limiting
                        # Use shorter delays and check for shutdown during wait
                        # Skip delay if using worker (worker handles rate limiting internally)
                        if i < len(sources) - 1 and not worker_succeeded:
                            for _ in range(4):  # 4 x 0.5s = 2s total, but can exit early
                                if is_cancelled():
                                    logger.info("[ASYNC RSS] Load cancelled during delay (gen=%d)", generation)
                                    logger.info("[ASYNC RSS] Engine shutting down during delay, aborting")
                                    return
                                time.sleep(0.5)
                            
                    except Exception as e:
                        logger.warning(f"[ASYNC RSS] Failed to load RSS source: {e}")
                
                # NO RETRY WAIT - rate-limited sources are skipped, not retried
                # This prevents blocking app exit
                
                if is_cancelled():
                    logger.info("[ASYNC RSS] Load cancelled after completion (gen=%d)", generation)
                    return

                total_loaded = len(rss_images)
                logger.info(f"[ASYNC RSS] Completed: {total_loaded} total images loaded from {len(sources)} sources (gen={generation})")
            finally:
                engine._rss_async_active = False

        # Submit to IO thread pool
        try:
            self.thread_manager.submit_io_task(load_rss_task)
        except Exception as exc:
            self._rss_async_active = False
            logger.warning("[ASYNC RSS] Failed to submit async task: %s", exc)

    def _next_rss_async_generation(self) -> int:
        """Advance and return the async RSS generation counter."""
        self._rss_async_generation += 1
        return self._rss_async_generation

    def _cancel_async_rss_load(self) -> None:
        """Signal any in-flight async RSS loaders to stop early."""
        new_gen = self._next_rss_async_generation()
        logger.debug("[ASYNC RSS] Cancel signal issued (gen=%d)", new_gen)
    
    def _get_rss_image_key(self, image: Optional[ImageMetadata]) -> str:
        """Return a stable key for deduplicating RSS images."""
        if not image:
            return ""
        if image.url:
            return f"url:{image.url}"
        if image.image_id:
            return f"id:{image.source_id}:{image.image_id}"
        if image.local_path:
            return f"path:{image.local_path}"
        return f"obj:{id(image)}"

    def _load_rss_images_sync(self) -> None:
        """Load a small batch of RSS images synchronously when no local images exist."""
        if not self.rss_sources:
            return

        per_feed_seed = self._get_rss_sync_seed_limit()
        seed_total = self._get_rss_sync_seed_total(per_feed_seed)
        if seed_total <= 0:
            return

        logger.info(
            "Loading RSS images synchronously for %d sources (seed=%d total=%d)...",
            len(self.rss_sources),
            per_feed_seed,
            seed_total,
        )

        result: dict[str, List[ImageMetadata]] = {}
        done = threading.Event()

        def worker():
            try:
                images = self._collect_rss_seed_images(per_feed_seed, seed_total)
                result["images"] = images
                if self.event_system:
                    try:
                        self.event_system.publish(
                            EventType.RSS_UPDATED,
                            data={
                                "phase": "sync_seed",
                                "count": len(images),
                            },
                            source=self,
                        )
                    except Exception as exc:
                        logger.debug(f"{TAG_RSS} Failed to publish RSS_UPDATED for sync seed: %s", exc)
            finally:
                done.set()

        submitted = False
        if self.thread_manager:
            try:
                self.thread_manager.submit_io_task(worker)
                submitted = True
            except Exception as exc:
                logger.warning("[ASYNC RSS] Failed to offload sync seed: %s", exc)

        if not submitted:
            worker()
        else:
            if not self._wait_for_event_with_ui_pump(done, timeout_seconds=20.0):
                logger.warning("[ASYNC RSS] Sync seed timed out waiting for worker completion")
                return

        rss_images = result.get("images") or []
        if not rss_images or not self.image_queue:
            return

        cap = self._get_rss_background_cap()
        if len(rss_images) > cap:
            rss_images = rss_images[:cap]
        count = self.image_queue.add_images(rss_images)
        logger.info("Queue initialized with %d RSS images (cap=%d)", count, cap)
        self._rss_pipeline.record_images(rss_images)

    def _collect_rss_seed_images(
        self,
        per_feed_seed: int,
        total_cap: int,
    ) -> List[ImageMetadata]:
        """Collect initial RSS images up to the requested cap."""
        collected: List[ImageMetadata] = []
        seen_keys: set[str] = set()

        for rss_source in self.rss_sources:
            if len(collected) >= total_cap:
                break
            try:
                images = list(rss_source.get_images() or [])
            except Exception as exc:
                logger.warning(f"[FALLBACK] Failed to get images from RSS source: {exc}")
                continue

            if per_feed_seed and len(images) > per_feed_seed:
                images = images[:per_feed_seed]

            for img in images:
                if len(collected) >= total_cap:
                    break
                key = self._get_rss_image_key(img)
                if key and key in seen_keys:
                    continue
                if key:
                    seen_keys.add(key)
                collected.append(img)

            if images:
                logger.debug(
                    "Seeded %d images from RSS source %s",
                    len(images),
                    rss_source.feed_urls[0] if getattr(rss_source, "feed_urls", None) else "unknown",
                )

        return collected

    def _get_rss_sync_seed_total(self, per_feed_seed: int) -> int:
        """Determine how many images we should synchronously seed in total."""
        min_required = self._get_minimum_rss_start_images()
        cap = self._get_rss_background_cap()
        per_feed_seed = max(1, per_feed_seed)

        # Ensure we at least meet the guard, but never exceed the background cap.
        total = max(min_required, per_feed_seed)
        total = min(total, cap)
        return total

    def _wait_for_event_with_ui_pump(
        self,
        event: threading.Event,
        timeout_seconds: float = 20.0,
        poll_interval: float = 0.05,
    ) -> bool:
        """Wait for threading.Event while keeping the Qt event loop responsive."""
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        app = QCoreApplication.instance()

        while not event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            wait_time = min(poll_interval, max(0.0, remaining))
            event.wait(wait_time)
            if app:
                try:
                    app.processEvents()
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug("[ENGINE] Exception suppressed while pumping events: %s", exc)

        return event.is_set()

    def _get_minimum_rss_start_images(self) -> int:
        """Return minimum RSS images required before starting when no local images exist."""
        default_min = 4
        try:
            if not self.settings_manager:
                return default_min
            raw = self.settings_manager.get("sources.rss_min_start_images", default_min)
            value = int(raw)
            return max(0, min(30, value))
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("[ENGINE] Failed to read rss_min_start_images: %s", exc)
            return default_min

    def _count_unique_rss_images(self) -> int:
        """Return the number of unique RSS images currently in the queue."""
        if not self.image_queue:
            return 0
        seen = set()
        for img in self.image_queue.get_all_images():
            if getattr(img, "source_type", None) != ImageSourceType.RSS:
                continue
            key = self._get_rss_image_key(img)
            if not key:
                key = f"obj:{id(img)}"
            seen.add(key)
        return len(seen)

    def _wait_for_min_rss_images(
        self,
        min_required: int,
        timeout_seconds: float = 15.0,
        check_interval: float = 0.5,
    ) -> bool:
        """Block until at least `min_required` RSS images are in the queue or timeout."""
        if min_required <= 0:
            return True

        start_time = time.monotonic()

        while True:
            if self._shutting_down:
                return False

            current = self._count_unique_rss_images()
            if current >= min_required:
                elapsed = time.monotonic() - start_time
                logger.info(
                    "[ASYNC RSS] Startup guard satisfied with %d RSS images (min=%d, elapsed=%.2fs)",
                    current,
                    min_required,
                    elapsed,
                )
                if self.event_system:
                    try:
                        self.event_system.publish(
                            EventType.RSS_GUARD_SATISFIED,
                            data={
                                "required": min_required,
                                "current": current,
                                "elapsed_seconds": elapsed,
                            },
                            source=self,
                        )
                    except Exception as exc:
                        logger.debug(f"{TAG_RSS} Failed to publish guard satisfied event: %s", exc)
                return True

            elapsed = time.monotonic() - start_time
            remaining = timeout_seconds - elapsed
            if remaining <= 0:
                logger.warning(
                    "[ASYNC RSS] Startup guard timed out after %.2fs with %d/%d RSS images",
                    elapsed,
                    current,
                    min_required,
                )
                if self.event_system:
                    try:
                        self.event_system.publish(
                            EventType.RSS_GUARD_TIMEOUT,
                            data={
                                "required": min_required,
                                "current": current,
                                "elapsed_seconds": elapsed,
                            },
                            source=self,
                        )
                    except Exception as exc:
                        logger.debug(f"{TAG_RSS} Failed to publish guard timeout event: %s", exc)
                return False

            sleep_for = min(check_interval, remaining)
            if sleep_for > 0:
                time.sleep(sleep_for)

    def _get_rss_sync_seed_limit(self) -> int:
        """Return the per-feed seed limit for synchronous RSS loading."""
        default_seed = 5
        try:
            if not self.settings_manager:
                return default_seed
            raw = self.settings_manager.get('sources.rss_sync_seed_per_feed', default_seed)
            value = int(raw)
            return max(1, min(10, value))
        except Exception as e:
            logger.debug("[ENGINE] Exception suppressed: %s", e)
            return default_seed

    def _get_rss_background_cap(self) -> int:
        """Return the global background cap for RSS images.

        This limits how many RSS/JSON images we keep queued at any
        given time. The minimum is dynamically adjusted based on
        transition interval to ensure variety.
        
        Can be overridden via settings (``sources.rss_background_cap``).
        """
        try:
            # Get dynamic minimum based on transition interval
            dynamic_min, _ = self._get_dynamic_rss_settings()
            
            if not self.settings_manager:
                return max(30, dynamic_min)
            
            raw = self.settings_manager.get('sources.rss_background_cap', 30)
            cap = int(raw)
            
            # Ensure cap is at least the dynamic minimum
            return max(cap, dynamic_min) if cap > 0 else dynamic_min
        except Exception as e:
            logger.debug("[ENGINE] Exception suppressed: %s", e)
            return 30

    def _get_dynamic_rss_settings(self) -> Tuple[int, int]:
        """Get dynamic RSS minimum cache size and decay time based on transition interval.
        
        Returns:
            Tuple of (min_cache_size, decay_minutes)
            
        Rules based on transition interval:
            <=30s: 20 minimum, 5 min decay (fast transitions need more variety)
            >30s but <=90s: 15 minimum, 10 min decay
            >90s: 10 minimum, 15 min decay (slow transitions can reuse more)
        """
        try:
            interval = 60  # default
            if self.settings_manager:
                interval = int(self.settings_manager.get('timing.interval', 60))
            
            if interval <= 30:
                return (20, 5)
            elif interval <= 90:
                return (15, 10)
            else:
                return (10, 15)
        except Exception as e:
            logger.debug("[ENGINE] Exception suppressed: %s", e)
            return (15, 10)  # Safe default
    
    def _get_rss_stale_minutes(self) -> int:
        """Return TTL in minutes for stale RSS images.

        Dynamically adjusted based on transition interval:
            <=30s: 5 min decay
            >30s but <=90s: 10 min decay  
            >90s: 15 min decay
            
        Can be overridden via settings (``sources.rss_stale_minutes``).
        A value <= 0 disables stale expiration.
        """
        try:
            # Get dynamic decay based on transition interval
            _, dynamic_decay = self._get_dynamic_rss_settings()
            
            if not self.settings_manager:
                return dynamic_decay
            
            # Check if user has explicitly set a value (non-default)
            raw = self.settings_manager.get('sources.rss_stale_minutes', None)
            if raw is not None:
                minutes = int(raw)
                return minutes if minutes > 0 else 0
            
            return dynamic_decay
        except Exception as e:
            logger.debug("[ENGINE] Exception suppressed: %s", e)
            return 10

    def _start_rss_background_refresh_if_needed(self) -> None:
        """Schedule background RSS refresh if RSS sources are present."""
        try:
            if not self.thread_manager or not self.image_queue or not self.rss_sources:
                return
            if self._rss_refresh_timer is not None:
                return

            cap = self._get_rss_background_cap()
            if cap <= 0:
                return

            # Allow user override for refresh interval; default ~10min.
            interval_min = 10
            try:
                if self.settings_manager:
                    raw = self.settings_manager.get('sources.rss_refresh_minutes', 10)
                    interval_min = int(raw)
            except Exception as e:
                logger.debug("[ENGINE] Exception suppressed: %s", e)
                interval_min = 10

            interval_ms = max(60_000, interval_min * 60_000)
            try:
                self._rss_refresh_timer = self.thread_manager.schedule_recurring(
                    interval_ms,
                    self._background_refresh_rss,
                )
                logger.info(
                    "Background RSS refresh enabled (interval=%dms, cap=%d)",
                    interval_ms,
                    cap,
                )
            except Exception as e:
                logger.debug(f"Background RSS refresh scheduling failed: {e}")
                self._rss_refresh_timer = None
        except Exception as e:
            logger.debug(f"Background RSS refresh init failed: {e}")

    def _background_refresh_rss(self) -> None:
        """Periodic background refresh for RSS/JSON sources.

        Runs on the UI thread via ``ThreadManager.schedule_recurring``
        and dispatches IO work to the thread pool.
        """
        try:
            if not self._running:
                return
            if not (self.thread_manager and self.image_queue and self.rss_sources):
                return
            if self._rss_async_active:
                logger.debug("[ASYNC RSS] Skipping background refresh (foreground async active)")
                return

            cap = self._get_rss_background_cap()
            if cap <= 0:
                return

            try:
                existing = self.image_queue.get_all_images()
            except Exception as e:
                logger.debug("[ENGINE] Exception suppressed: %s", e)
                existing = []

            current_rss = 0
            for m in existing:
                try:
                    if getattr(m, 'source_type', None) == ImageSourceType.RSS:
                        current_rss += 1
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
                    continue

            if current_rss >= cap:
                return

            # Randomly shuffle RSS sources to distribute load and variety
            # This ensures we don't always hit the same feeds first
            shuffled_sources = list(self.rss_sources)
            random.shuffle(shuffled_sources)
            
            # Only refresh a subset of sources per tick to avoid overwhelming
            # the network and to spread out the load
            max_sources_per_tick = min(3, len(shuffled_sources))
            sources_to_refresh = shuffled_sources[:max_sources_per_tick]
            
            logger.debug(f"Background RSS refresh: checking {len(sources_to_refresh)} of {len(self.rss_sources)} sources")

            for src in sources_to_refresh:
                def _refresh_source(rss=src):
                    try:
                        rss.refresh()
                        return rss.get_images()
                    except Exception as e:
                        logger.warning(f"[FALLBACK] Background RSS refresh failed for {rss}: {e}")
                        return []

                def _on_done(res):
                    try:
                        if not res or not getattr(res, 'success', False):
                            if self.event_system:
                                try:
                                    self.event_system.publish(EventType.RSS_FAILED, data={"source": "background"}, source=self)
                                except Exception as e:
                                    logger.debug(f"{TAG_RSS} Failed to publish RSS_FAILED event: %s", e)
                            return
                        images = getattr(res, 'result', None) or []
                        if not isinstance(images, list):
                            return
                        self._merge_rss_images_from_refresh(images)
                    except Exception as e:
                        logger.debug(f"Background RSS merge failed: {e}")

                try:
                    self.thread_manager.submit_io_task(_refresh_source, callback=_on_done)
                except Exception as e:
                    logger.debug(f"Background RSS submit failed: {e}")
        except Exception as e:
            logger.debug(f"Background RSS refresh tick failed: {e}")

    def _merge_rss_images_from_refresh(self, images: List[ImageMetadata]) -> None:
        """Merge refreshed RSS images into the queue under the global cap."""
        if not images or not self.image_queue:
            return

        cap = self._get_rss_background_cap()
        if cap <= 0:
            return

        with self._rss_merge_lock:
            try:
                existing = self.image_queue.get_all_images()
            except Exception as e:
                logger.debug("[ENGINE] Exception suppressed: %s", e)
                existing = []

            existing_keys: set[str] = set()
            current_rss = 0
            for m in existing:
                try:
                    key = self._get_rss_image_key(m)
                    if key:
                        existing_keys.add(key)
                    if getattr(m, 'source_type', None) == ImageSourceType.RSS:
                        current_rss += 1
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
                    continue

            remaining = cap - current_rss
            if remaining <= 0:
                return

            new_items: List[ImageMetadata] = []
            for m in images:
                try:
                    if getattr(m, 'source_type', None) != ImageSourceType.RSS:
                        continue
                    key = self._get_rss_image_key(m)
                    if not key or key in existing_keys:
                        continue
                    new_items.append(m)
                    existing_keys.add(key)
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
                    continue

            if not new_items:
                return

            try:
                random.shuffle(new_items)
            except Exception as e:
                logger.debug(f"{TAG_RSS} Failed to shuffle new items: %s", e)

            to_add = new_items[: max(0, remaining)]
            if not to_add:
                return

            added = 0
            try:
                added = self.image_queue.add_images(to_add)
            except Exception as e:
                logger.debug(f"Background RSS queue add failed: {e}")
                return

            removed_stale = 0
            if added > 0:
                stale_minutes = self._get_rss_stale_minutes()
                if stale_minutes > 0:
                    cutoff = datetime.utcnow() - timedelta(minutes=stale_minutes)

                    try:
                        snapshot = self.image_queue.get_all_images()
                    except Exception as e:
                        logger.debug("[ENGINE] Exception suppressed: %s", e)
                        snapshot = []

                    try:
                        history_paths = set(self.image_queue.get_history(self.image_queue.history_size))
                    except Exception as e:
                        logger.debug("[ENGINE] Exception suppressed: %s", e)
                        history_paths = set()

                    stale_paths: List[str] = []
                    for m in snapshot:
                        try:
                            if getattr(m, 'source_type', None) != ImageSourceType.RSS:
                                continue
                            lp = str(m.local_path) if m.local_path else None
                            if not lp or lp in history_paths:
                                continue
                            ts = getattr(m, 'fetched_date', None) or getattr(m, 'created_date', None)
                            if ts is None or not isinstance(ts, datetime):
                                continue
                            if ts < cutoff:
                                stale_paths.append(lp)
                        except Exception as e:
                            logger.debug("[ENGINE] Exception suppressed: %s", e)
                            continue

                    if stale_paths:
                        max_remove = min(len(stale_paths), added)
                        for path in stale_paths[:max_remove]:
                            try:
                                if self.image_queue.remove_image(path):
                                    removed_stale += 1
                            except Exception as e:
                                logger.debug("[ENGINE] Exception suppressed: %s", e)
                                continue

            logger.info(
                "Background RSS refresh merged %d new images (cap=%d, removed_stale=%d)",
                added,
                cap,
                removed_stale,
            )

            if self.event_system and (added > 0 or removed_stale > 0):
                try:
                    try:
                        final_existing = self.image_queue.get_all_images()
                    except Exception as e:
                        logger.debug("[ENGINE] Exception suppressed: %s", e)
                        final_existing = []

                    total_rss = 0
                    for m in final_existing:
                        try:
                            if getattr(m, 'source_type', None) == ImageSourceType.RSS:
                                total_rss += 1
                        except Exception as e:
                            logger.debug("[ENGINE] Exception suppressed: %s", e)
                            continue

                    self.event_system.publish(
                        EventType.RSS_UPDATED,
                        data={"added": added, "removed_stale": removed_stale, "total_rss": total_rss},
                        source=self,
                    )
                except Exception as e:
                    logger.debug(f"{TAG_RSS} Failed to publish RSS_REFRESHED event: %s", e)

    def _initialize_cache_prefetcher(self) -> None:
        try:
            max_items = int(self.settings_manager.get('cache.max_items', 24))
            max_mem_mb = int(self.settings_manager.get('cache.max_memory_mb', 1024))
            max_conc = int(self.settings_manager.get('cache.max_concurrent', 2))
            self._image_cache = ImageCache(max_items=max_items, max_memory_mb=max_mem_mb)
            self._rss_pipeline.attach_image_cache(self._image_cache)
            if self.thread_manager:
                self._prefetcher = ImagePrefetcher(self.thread_manager, self._image_cache, max_concurrent=max_conc)
            logger.info(f"Image prefetcher initialized (ahead={self._prefetch_ahead}, max_concurrent={max_conc})")
            self._schedule_prefetch()
        except Exception as e:
            logger.debug(f"Prefetcher init failed: {e}")

    def _schedule_prefetch(self) -> None:
        try:
            if not self.image_queue or not self._prefetcher or self._prefetch_ahead <= 0:
                return
            upcoming = self.image_queue.peek_many(self._prefetch_ahead)
            paths = []
            for m in upcoming:
                try:
                    p = str(m.local_path) if m and m.local_path else (m.url or "")
                    if p:
                        paths.append(p)
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
                    continue
            self._prefetcher.prefetch_paths(paths)
            if paths and is_verbose_logging():
                logger.debug(f"Prefetch scheduled for {len(paths)} upcoming images")
                # Avoid heavy UI-side conversions while transitions are active.
                skip_heavy_ui_work = False
                try:
                    if self.display_manager and hasattr(self.display_manager, "has_running_transition"):
                        skip_heavy_ui_work = self.display_manager.has_running_transition()
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
                    skip_heavy_ui_work = False
                # UI warmup: convert first cached QImage to QPixmap to reduce on-demand conversion
                # PERFORMANCE FIX: Move QPixmap.fromImage to compute pool (Qt 6 allows this)
                # Only invoke UI thread for final cache storage
                try:
                    if not skip_heavy_ui_work and self.thread_manager and self._image_cache:
                        first = paths[0]
                        def _compute_convert():
                            """Compute pool: Convert QImage to QPixmap (Qt 6 thread-safe)"""
                            try:
                                from PySide6.QtGui import QPixmap, QImage
                                cached = self._image_cache.get(first)
                                if isinstance(cached, QImage):
                                    pm = QPixmap.fromImage(cached)  # ← Now on worker thread
                                    if not pm.isNull():
                                        # Clear QImage reference to free memory (Section 1.1 fix)
                                        cached = None
                                        return (first, pm)
                            except Exception as e:
                                logger.debug(f"Prefetch convert failed for {first}: {e}")
                            return None
                        
                        def _ui_cache(result):
                            """UI thread: Store result in cache"""
                            try:
                                if result and result.success and result.result:
                                    path, pixmap = result.result
                                    self._image_cache.put(path, pixmap)
                                    logger.debug(f"Prefetch warmup: cached QPixmap for {path}")
                            except Exception as e:
                                logger.debug(f"Prefetch cache failed: {e}")
                        
                        self.thread_manager.submit_compute_task(
                            _compute_convert,
                            callback=lambda r: self.thread_manager.run_on_ui_thread(lambda: _ui_cache(r))
                        )
                except Exception as e:
                    logger.debug("[PREFETCH] UI warmup failed: %s", e)
                # Pre-scale proposal: safely compute scaled QImages for distinct display sizes (multi-monitor safe)
                # Optional and removable; computes only for the next image to limit memory.
                try:
                    if not skip_heavy_ui_work and self.thread_manager and self._image_cache:
                        first_path = paths[0]
                        sizes = self._get_distinct_display_sizes()
                        for (w, h) in sizes:
                            scaled_key = f"{first_path}|scaled:{w}x{h}"
                            # Skip work if a scaled variant is already cached for this size.
                            try:
                                if self._image_cache.contains(scaled_key):
                                    continue
                            except Exception as e:
                                logger.debug("[ENGINE] Exception suppressed: %s", e)
                            def _compute_prescale_wh(width=w, height=h, src_path=first_path, cache_key=scaled_key):
                                """Compute-task: scale cached QImage to a target size and store in cache.
                                Safe to remove if not needed. Avoids doing the heavy scale on the next frame.
                                """
                                try:
                                    from PySide6.QtGui import QImage
                                    base = self._image_cache.get(src_path)
                                    if isinstance(base, QImage) and not base.isNull():
                                        # Use the shared QImage-based scaler so behaviour matches
                                        # the AsyncImageProcessor helper (Lanczos disabled here).
                                        scaled = AsyncImageProcessor._scale_image(
                                            base,
                                            width,
                                            height,
                                            use_lanczos=False,
                                            sharpen=False,
                                        )
                                        if not scaled.isNull():
                                            self._image_cache.put(cache_key, scaled)
                                except Exception as e:
                                    logger.debug(f"Pre-scale compute failed ({width}x{height}): {e}")
                            try:
                                submit = getattr(self.thread_manager, 'submit_compute_task', None)
                                if callable(submit):
                                    submit(_compute_prescale_wh)
                            except Exception as e:
                                logger.debug("[ENGINE] Exception suppressed: %s", e)
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
        except Exception as e:
            logger.debug(f"Prefetch schedule failed: {e}")
    
    def _initialize_display(self) -> bool:
        """Initialize display manager."""
        try:
            logger.info("Initializing display...")
            
            # Get display settings
            display_mode_str = self.settings_manager.get('display.mode', 'fill')
            display_mode = DisplayMode.from_string(display_mode_str)
            
            same_image = self.settings_manager.get('display.same_image_all_monitors', True)
            
            # Create display manager (inject core managers)
            self.display_manager = DisplayManager(
                display_mode=display_mode,
                same_image_mode=same_image,
                settings_manager=self.settings_manager,
                resource_manager=self.resource_manager,
                thread_manager=self.thread_manager,
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
            
            # Wire up ProcessSupervisor to displays for FFTWorker integration
            if self._process_supervisor and display_count > 0:
                self.display_manager.set_process_supervisor(self._process_supervisor)
                logger.debug("ProcessSupervisor wired to display manager")
            
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

        if self._rotation_timer:
            self._stop_qtimer_safe(self._rotation_timer, description="Engine rotation timer (reconfigure)")
            self._rotation_timer = None

        if not self.thread_manager:
            logger.error("Cannot configure rotation timer without ThreadManager")
            return

        try:
            self._rotation_timer = self.thread_manager.schedule_recurring(
                interval_ms,
                self._on_rotation_timer,
            )
            logger.info(f"Rotation timer configured: {interval_seconds}s")
        except Exception as e:
            logger.exception("Failed to configure rotation timer: %s", e)
            self._rotation_timer = None
    
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
    
    def _start_workers(self) -> None:
        """Start multiprocessing workers based on settings.
        
        Workers are optional - if they fail to start, the engine falls back
        to ThreadManager-based processing. This is non-blocking.
        
        Respects max_workers setting: 'auto' = half CPU cores, or explicit 1-8.
        """
        if not self._process_supervisor:
            logger.debug("ProcessSupervisor not initialized, skipping worker startup")
            return
        
        # Determine max workers based on settings and CPU cores
        import os
        cpu_count = os.cpu_count() or 4
        max_workers_setting = self.settings_manager.get('workers.max_workers', 'auto')
        
        if max_workers_setting == 'auto':
            # Half CPU cores for background app, minimum 2, maximum 4
            max_workers = max(2, min(4, cpu_count // 2))
        else:
            try:
                max_workers = int(max_workers_setting)
                max_workers = max(1, min(8, max_workers))
            except (ValueError, TypeError):
                max_workers = 4
        
        logger.info(f"Worker pool: max_workers={max_workers} (CPU cores={cpu_count})")
        
        workers_started = 0
        workers_failed = 0
        
        # Priority order: Image > FFT only
        # RSS and Transition workers removed - low value, use ThreadManager instead
        # This reduces process overhead and improves performance
        worker_configs = [
            (WorkerType.IMAGE, 'workers.image.enabled', "ImageWorker", "ThreadManager fallback"),
            (WorkerType.FFT, 'workers.fft.enabled', "FFTWorker", "local processing"),
        ]
        
        for worker_type, setting_key, name, fallback_msg in worker_configs:
            if workers_started >= max_workers:
                logger.debug(f"{name} skipped - max_workers limit reached ({max_workers})")
                continue
                
            if self.settings_manager.get(setting_key, True):
                if self._process_supervisor.start(worker_type):
                    logger.info(f"{name} started successfully")
                    workers_started += 1
                else:
                    logger.warning(f"{name} failed to start - using {fallback_msg}")
                    workers_failed += 1
        
        logger.info(f"Worker startup complete: {workers_started} started, {workers_failed} failed")
    
    def start(self) -> bool:
        """
        Start the screensaver engine.
        
        State transition: STOPPED -> STARTING -> RUNNING
        
        Returns:
            True if started successfully, False otherwise
        """
        # Check if already running (using property)
        if self._running:
            logger.warning("Engine already running")
            return True
        
        # Validate and transition state
        if not self._transition_state(
            EngineState.STARTING,
            expected_from=[EngineState.STOPPED]
        ):
            logger.error("Cannot start: invalid state")
            return False
        
        try:
            logger.info("Starting screensaver engine...")
            
            # Choose random transition for this cycle if enabled
            self._prepare_random_transition_if_needed()
            # Show first image immediately
            if not self._show_next_image():
                logger.warning("[FALLBACK] Failed to show first image")
                # Continue anyway, timer will retry
            
            # Start rotation timer
            if self._rotation_timer:
                self._rotation_timer.start()
                logger.info(f"Rotation timer started ({self._rotation_timer.interval()}ms)")
            
            # Transition to RUNNING state
            self._transition_state(EngineState.RUNNING)
            
            # Set class-level flag for widget perf logging
            with self._instance_lock:
                self.__class__._instance_running = True
            
            self.started.emit()
            logger.info("Screensaver engine started")
            
            return True
        
        except Exception as e:
            logger.exception(f"Engine start failed: {e}")
            self.error_occurred.emit(f"Start failed: {e}")
            # Revert to STOPPED on failure
            self._transition_state(EngineState.STOPPED)
            return False
    
    def stop(self, exit_app: bool = True) -> None:
        """
        Stop the screensaver engine.
        
        State transition: 
            RUNNING -> STOPPING -> STOPPED (if exit_app=False)
            RUNNING -> SHUTTING_DOWN (if exit_app=True, terminal)
        
        Args:
            exit_app: If True, quit the application. If False, just stop the engine.
        """
        # Check if running (using property)
        if not self._running:
            logger.debug("Engine not running")
            return
        
        # Determine target state based on exit_app
        target_state = EngineState.SHUTTING_DOWN if exit_app else EngineState.STOPPING
        
        # Transition to stopping/shutting_down state
        # This makes _shutting_down property return True, signaling async tasks to abort
        if not self._transition_state(
            target_state,
            expected_from=[EngineState.RUNNING, EngineState.STARTING, EngineState.REINITIALIZING]
        ):
            logger.warning(f"Stop called in unexpected state: {self._get_state().name}")
            # Force transition anyway for safety
            with self._state_lock:
                self._state = target_state
        
        try:
            logger.info("Stopping screensaver engine...")
            logger.debug("Engine stop requested (exit_app=%s)", exit_app)

            # Stop background RSS refresh timer if present so no further
            # callbacks run after teardown begins.
            if self._rss_refresh_timer is not None:
                self._stop_qtimer_safe(self._rss_refresh_timer, description="Background RSS refresh timer")
                self._rss_refresh_timer = None
            
            # Stop rotation timer (do not delete here to avoid double-delete on repeated stops)
            if self._rotation_timer:
                self._stop_qtimer_safe(self._rotation_timer, description="Engine rotation timer")
                self._rotation_timer = None
            
            # Clear and hide/cleanup displays
            if self.display_manager:
                try:
                    try:
                        display_count = self.display_manager.get_display_count()
                    except Exception as e:
                        logger.debug("[ENGINE] Exception suppressed: %s", e)
                        display_count = len(getattr(self.display_manager, "displays", []))
                    logger.info(
                        "Stopping displays via DisplayManager (count=%s, exit_app=%s)",
                        display_count,
                        exit_app,
                    )
                except Exception as e:
                    logger.info(
                        "Stopping displays via DisplayManager (count=?, exit_app=%s, error=%s)",
                        exit_app,
                        e,
                    )

                try:
                    self.display_manager.clear_all()
                except Exception as e:
                    logger.debug("DisplayManager.clear_all() failed during stop: %s", e, exc_info=True)

                if exit_app:
                    # Exiting app - full cleanup
                    try:
                        self.display_manager.cleanup()
                        logger.debug("Displays cleared and cleaned up")
                    except Exception as e:
                        logger.warning("DisplayManager.cleanup() failed during stop: %s", e, exc_info=True)
                    else:
                        try:
                            self.display_manager.flush_deferred_reddit_urls(ensure_widgets_dismissed=True)
                        except Exception as e:
                            logger.warning("Deferred Reddit flush failed: %s", e, exc_info=True)
                else:
                    # Just pausing (e.g., for settings) - hide windows
                    try:
                        self.display_manager.hide_all()
                        logger.debug("Displays cleared and hidden")
                    except Exception as e:
                        logger.warning("DisplayManager.hide_all() failed during stop: %s", e, exc_info=True)
            
            # Stop any pending image loads
            self._loading_in_progress = False
            
            # Shutdown ProcessSupervisor and all workers
            if exit_app and self._process_supervisor:
                logger.info("Shutting down ProcessSupervisor...")
                try:
                    self._process_supervisor.shutdown()
                    logger.info("ProcessSupervisor shutdown complete")
                except Exception as e:
                    logger.warning("ProcessSupervisor shutdown failed: %s", e, exc_info=True)
            
            self.stopped.emit()
            logger.info("Screensaver engine stopped")

            # Emit a concise image cache summary for profiling.
            # Tagged with "[PERF] ImageCache" so production builds can grep and
            # gate/strip this debug telemetry if desired.
            if is_perf_metrics_enabled():
                try:
                    if self._image_cache is not None:
                        stats = self._image_cache.get_stats()
                        logger.info(
                            "[PERF] ImageCache: items=%d/%d, mem=%.1f/%.0fMB, hits=%d, "
                            "misses=%d, hit_rate=%.1f%%%%, evictions=%d",
                            stats.get('item_count', 0),
                            stats.get('max_items', 0),
                            stats.get('memory_usage_mb', 0.0),
                            stats.get('max_memory_mb', 0.0),
                            stats.get('hits', 0),
                            stats.get('misses', 0),
                            stats.get('hit_rate_percent', 0.0),
                            stats.get('evictions', 0),
                        )
                except Exception as e:
                    logger.debug("[PERF] ImageCache summary logging failed: %s", e, exc_info=True)
            
            # Clear class-level flag for widget perf logging
            with self._instance_lock:
                self.__class__._instance_running = False
            
            # Transition to final state
            if not exit_app:
                # If not exiting, transition to STOPPED (can restart)
                self._transition_state(EngineState.STOPPED)
            # If exit_app=True, stay in SHUTTING_DOWN (terminal state)
            
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

    def _stop_qtimer_safe(self, timer: Optional[QTimer], *, description: str) -> None:
        """Stop/delete a QTimer on its owning thread."""
        if timer is None:
            return
        try:
            if QThread.currentThread() is timer.thread():
                if timer.isActive():
                    timer.stop()
                try:
                    timer.deleteLater()
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
            else:
                QMetaObject.invokeMethod(
                    timer,
                    "stop",
                    Qt.ConnectionType.QueuedConnection,
                )
                QMetaObject.invokeMethod(
                    timer,
                    "deleteLater",
                    Qt.ConnectionType.QueuedConnection,
                )
            logger.debug("%s stopped", description)
        except Exception as exc:
            logger.debug("%s stop failed: %s", description, exc, exc_info=True)
    
    def cleanup(self) -> None:
        """Clean up all resources."""
        logger.info("Cleaning up screensaver engine...")
        
        try:
            # Stop if running
            if self._running:
                self.stop()

            # Emit a concise summary tying together queue stats and transition skips
            # for prefetch vs transition-skip pacing diagnostics.
            # Tagged with "[PERF] Engine summary" so production builds can grep
            # and gate/strip this debug telemetry if desired.
            if is_perf_metrics_enabled():
                try:
                    if self.image_queue:
                        qstats = self.image_queue.get_stats()
                    else:
                        qstats = None
                    dstats = None
                    if self.display_manager:
                        try:
                            dstats = self.display_manager.get_display_info()
                        except Exception as e:
                            logger.debug("[PERF] Engine summary display info failed: %s", e, exc_info=True)
                            dstats = None
                    logger.info(
                        "[PERF] Engine summary: queue=%s, displays=%s",
                        qstats,
                        dstats,
                    )
                except Exception as e:
                    logger.debug("[PERF] Engine summary logging failed: %s", e, exc_info=True)

            # Cleanup display manager
            if self.display_manager:
                try:
                    self.display_manager.cleanup()
                    logger.debug("Display manager cleaned up")
                except Exception as e:
                    logger.warning("DisplayManager.cleanup() failed during engine cleanup: %s", e, exc_info=True)
                else:
                    try:
                        self.display_manager.flush_deferred_reddit_urls(ensure_widgets_dismissed=True)
                    except Exception as e:
                        logger.warning("Deferred Reddit flush failed during engine cleanup: %s", e, exc_info=True)
            
            # Cleanup thread manager
            if self.thread_manager:
                try:
                    self.thread_manager.shutdown()
                    logger.debug("Thread manager shut down")
                except Exception as e:
                    logger.warning("ThreadManager.shutdown() failed during engine cleanup: %s", e, exc_info=True)
            
            # Cleanup resource manager
            if self.resource_manager:
                try:
                    self.resource_manager.cleanup_all()
                    logger.debug("Resources cleaned up")
                except Exception as e:
                    logger.warning("ResourceManager.cleanup_all() failed during engine cleanup: %s", e, exc_info=True)
            
            # Clear sources
            self.folder_sources.clear()
            self.rss_sources.clear()
            
            # Cleanup global shader program singletons
            try:
                from rendering.gl_compositor import cleanup_global_shader_programs
                cleanup_global_shader_programs()
                logger.debug("Global shader programs cleaned up")
            except Exception as e:
                logger.debug("Shader cleanup skipped: %s", e)
            
            logger.info("Engine cleanup complete")
        
        except Exception as e:
            logger.exception(f"Cleanup failed: {e}")
    
    def _show_next_image(self) -> bool:
        """Load and display next image from queue."""
        # If random transitions are enabled, prepare a new non-repeating choice for this change
        try:
            self._prepare_random_transition_if_needed()
        except Exception as e:
            logger.debug("[TRANSITION] Failed to prepare random transition: %s", e)
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
            
            # ARCHITECTURAL FIX: Use async image processing to avoid UI thread blocking
            # This moves heavy image scaling/cropping to background threads
            if self.thread_manager:
                self._load_and_display_image_async(image_meta)
                return True  # Async - will complete later
            
            # Fallback to sync path if no thread manager
            return self._load_and_display_image(image_meta)
        
        except Exception as e:
            logger.exception(f"Show next image failed: {e}")
            self._loading_in_progress = False
            return False
    
    def _load_image_via_worker(
        self, 
        image_path: str, 
        target_width: int, 
        target_height: int,
        display_mode: str = "fill",
        sharpen: bool = False,
        timeout_ms: int = 500,
    ) -> Optional[QImage]:
        """
        Load and prescale image using ImageWorker process.
        
        Uses the ImageWorker for decode/prescale in a separate process,
        avoiding GIL contention. Falls back to None if worker unavailable.
        
        Args:
            image_path: Path to image file
            target_width: Target width in pixels
            target_height: Target height in pixels
            display_mode: Display mode (fill, fit, shrink)
            sharpen: Whether to apply sharpening
            timeout_ms: Timeout for worker response
            
        Returns:
            QImage if successful, None if worker unavailable or failed
        """
        if not self._process_supervisor or not self._process_supervisor.is_running(WorkerType.IMAGE):
            return None
        
        try:
            import time
            
            # Send prescale request to ImageWorker
            correlation_id = self._process_supervisor.send_message(
                WorkerType.IMAGE,
                MessageType.IMAGE_PRESCALE,
                payload={
                    "path": image_path,
                    "target_width": target_width,
                    "target_height": target_height,
                    "mode": display_mode,
                    "use_lanczos": True,
                    "sharpen": sharpen,
                },
            )
            
            if not correlation_id:
                logger.debug(f"{TAG_WORKER} Failed to send message to ImageWorker")
                return None
            
            # Poll for response with timeout
            start_time = time.time()
            timeout_s = timeout_ms / 1000.0
            
            while (time.time() - start_time) < timeout_s:
                responses = self._process_supervisor.poll_responses(WorkerType.IMAGE, max_count=10)
                
                for response in responses:
                    # Skip WORKER_BUSY/IDLE messages - they're handled internally
                    if response.msg_type in (MessageType.WORKER_BUSY, MessageType.WORKER_IDLE, MessageType.HEARTBEAT_ACK):
                        continue
                    
                    if response.correlation_id == correlation_id:
                        if response.success:
                            payload = response.payload
                            width = payload.get("width", 0)
                            height = payload.get("height", 0)
                            
                            if width <= 0 or height <= 0:
                                logger.warning(f"{TAG_WORKER} ImageWorker returned invalid dimensions")
                                return None
                            
                            # Check for shared memory response (large images)
                            shm_name = payload.get("shared_memory_name")
                            if shm_name:
                                try:
                                    from multiprocessing.shared_memory import SharedMemory
                                    shm_size = payload.get("shared_memory_size", width * height * 4)
                                    shm = SharedMemory(name=shm_name, create=False)
                                    rgba_data = bytes(shm.buf[:shm_size])
                                    shm.close()
                                    # Don't unlink - worker will clean up
                                    
                                    if is_perf_metrics_enabled():
                                        logger.debug(
                                            f"{TAG_PERF} {TAG_WORKER} ImageWorker used shared memory: %.1f MB",
                                            shm_size / (1024 * 1024)
                                        )
                                except Exception as shm_err:
                                    logger.warning(f"{TAG_WORKER} Failed to read shared memory: %s", shm_err)
                                    return None
                            else:
                                # Queue-based transfer (smaller images)
                                rgba_data = payload.get("rgba_data")
                            
                            if rgba_data and width > 0 and height > 0:
                                qimage = QImage(
                                    rgba_data,
                                    width,
                                    height,
                                    width * 4,  # bytes per line
                                    QImage.Format.Format_RGBA8888,
                                )
                                # Make a deep copy since rgba_data may be invalidated
                                qimage = qimage.copy()
                                
                                if is_perf_metrics_enabled():
                                    proc_time = response.processing_time_ms or 0
                                    logger.info(
                                        f"{TAG_PERF} {TAG_WORKER} ImageWorker prescale: %dx%d in %.1fms",
                                        width, height, proc_time
                                    )
                                
                                return qimage
                        else:
                            error = response.error or "Unknown error"
                            logger.warning(f"{TAG_WORKER} ImageWorker failed: %s", error)
                            return None
                
                # Brief sleep to avoid busy-waiting
                time.sleep(0.005)
            
            logger.warning(f"{TAG_WORKER} ImageWorker timeout after %dms", timeout_ms)
            return None
            
        except Exception as e:
            logger.warning(f"{TAG_WORKER} ImageWorker error: %s", e)
            return None
    
    def _load_image_task(self, image_meta: ImageMetadata, preferred_size: Optional[tuple] = None) -> Optional[QPixmap]:
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
            
            # Use cache if available (QImage decoded on IO thread)
            pixmap: Optional[QPixmap] = None
            if self._prefetcher and self._image_cache:
                # Prefer a pre-scaled variant for this display if present
                try:
                    size = preferred_size or self._get_primary_display_size()
                    if size:
                        w, h = size
                        scaled_key = f"{image_path}|scaled:{w}x{h}"
                        scaled_cached = self._image_cache.get(scaled_key)
                        if isinstance(scaled_cached, QPixmap):
                            pixmap = scaled_cached
                        elif isinstance(scaled_cached, QImage) and not scaled_cached.isNull() and self.thread_manager:
                            # Heavy crop/scale already done as QImage; promote once per image.
                            pm = QPixmap.fromImage(scaled_cached)
                            if not pm.isNull():
                                self._image_cache.put(scaled_key, pm)
                                pixmap = pm
                                # Clear QImage reference to free memory (Section 1.1 fix)
                                scaled_cached = None
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
                    pixmap = None

                if pixmap is None or pixmap.isNull():
                    cached = self._image_cache.get(image_path)
                    if isinstance(cached, QPixmap):
                        pixmap = cached
                    elif isinstance(cached, QImage) and not cached.isNull():
                        try:
                            # Convert base QImage to QPixmap once and cache it.
                            pm = QPixmap.fromImage(cached)
                            if not pm.isNull():
                                self._image_cache.put(image_path, pm)
                                pixmap = pm
                                # Clear QImage reference to free memory (Section 1.1 fix)
                                cached = None
                        except Exception as e:
                            logger.debug("[ENGINE] Exception suppressed: %s", e)
                            pixmap = None
                    if pixmap is None:
                        pixmap = QPixmap(image_path)
            else:
                pixmap = QPixmap(image_path)
            
            if pixmap.isNull():
                logger.warning("Image load failed for: %s", image_path)
                return None
            
            logger.debug(f"Image loaded: {image_path} ({pixmap.width()}x{pixmap.height()})")
            return pixmap
        
        except Exception as e:
            logger.exception(f"Image load task failed: {e}")
            return None

    def _load_and_display_image_async(self, image_meta: ImageMetadata, retry_count: int = 0) -> None:
        """
        Load and display image asynchronously. Processes image on background thread.
        
        ARCHITECTURAL NOTE: This method moves heavy image processing off the UI thread
        to eliminate frame timing spikes during image changes. The flow is:
        1. Load QImage on IO thread (or from cache)
        2. Process/scale QImage on COMPUTE thread
        3. Convert to QPixmap and display on UI thread
        
        For "different images on each monitor" mode, this loads separate images for
        each display from the queue.
        
        Args:
            image_meta: Image metadata for first display
            retry_count: Number of retries attempted (max 10)
        """
        if not self.thread_manager or not self.display_manager:
            # Fall back to sync path if no thread manager
            self._load_and_display_image(image_meta, retry_count)
            return

        # Check same_image setting to determine how many images to load
        raw_same_image = self.settings_manager.get('display.same_image_all_monitors', True)
        same_image = SettingsManager.to_bool(raw_same_image, True)
        
        # Build list of images to load - one per display if different images mode
        displays = self.display_manager.displays if self.display_manager else []
        image_metas = [image_meta]  # First display gets the provided image
        
        if not same_image and len(displays) > 1:
            # Load different images for each additional display
            # Track used paths to avoid duplicates
            used_paths = set()
            first_path = str(image_meta.local_path) if image_meta.local_path else (image_meta.url or "")
            used_paths.add(first_path)
            
            for i in range(1, len(displays)):
                # Try to get a unique image (up to 5 attempts to avoid infinite loop)
                next_meta = None
                for attempt in range(5):
                    candidate = self.image_queue.next() if self.image_queue else None
                    if not candidate:
                        break
                    
                    candidate_path = str(candidate.local_path) if candidate.local_path else (candidate.url or "")
                    if candidate_path not in used_paths:
                        next_meta = candidate
                        used_paths.add(candidate_path)
                        break
                    elif attempt < 4:
                        # Got duplicate, try again
                        logger.debug(f"{TAG_ASYNC} Skipping duplicate image for display {i}, attempt {attempt + 1}")
                    else:
                        # Last attempt, use it anyway
                        next_meta = candidate
                        logger.warning(f"{TAG_ASYNC} Could not find unique image for display {i} after 5 attempts")
                
                if next_meta:
                    image_metas.append(next_meta)
                else:
                    # Fallback: reuse first image if queue is empty
                    image_metas.append(image_meta)
                    logger.warning(f"{TAG_ASYNC} Queue empty, reusing first image for display {i}")
            
            logger.debug(f"{TAG_ASYNC} Loading {len(image_metas)} different images for {len(displays)} displays")

        def _do_load_and_process() -> Optional[Dict]:
            """Background task: load and process images for all displays."""
            import time
            from PySide6.QtGui import QPixmap
            try:
                processed_images = {}
                display_list = self.display_manager.displays if self.display_manager else []
                
                # Get quality settings
                sharpen = False
                if self.settings_manager:
                    sharpen = self.settings_manager.get('display.sharpen_downscale', False)
                    if isinstance(sharpen, str):
                        sharpen = sharpen.lower() == 'true'
                
                for i, display in enumerate(display_list):
                    # Get the image metadata for this display
                    meta = image_metas[i] if i < len(image_metas) else image_metas[0]
                    img_path = str(meta.local_path) if meta.local_path else (meta.url or "")
                    
                    if not img_path:
                        logger.warning(f"{TAG_ASYNC} No path for display {i}")
                        continue
                    
                    # Load QImage (thread-safe)
                    qimage: Optional[QImage] = None
                    
                    # Try cache first
                    if self._image_cache:
                        cached = self._image_cache.get(img_path)
                        if isinstance(cached, QImage) and not cached.isNull():
                            qimage = cached
                        elif isinstance(cached, QPixmap) and not cached.isNull():
                            qimage = cached.toImage()
                    
                    # PERFORMANCE FIX: Skip synchronous QImage load - let ImageWorker handle it
                    # The old code loaded the full image here (5+ seconds for large images),
                    # then tried to use ImageWorker. Now we go straight to ImageWorker.
                    # Only load synchronously if ImageWorker fails or is unavailable.
                    
                    # Validate file exists before trying worker
                    if qimage is None or qimage.isNull():
                        from pathlib import Path
                        if not Path(img_path).exists():
                            logger.warning(f"{TAG_ASYNC} Image file not found: {img_path}")
                            # Try to get a replacement image for this display
                            for retry in range(3):
                                replacement = self.image_queue.next() if self.image_queue else None
                                if replacement and replacement.local_path:
                                    replacement_path = str(replacement.local_path)
                                    if Path(replacement_path).exists():
                                        img_path = replacement_path
                                        meta = replacement
                                        logger.info(f"{TAG_ASYNC} Using replacement image for display {i}: {Path(replacement_path).name}")
                                        break
                            
                            if not Path(img_path).exists():
                                logger.warning(f"{TAG_ASYNC} No valid replacement found for display {i}")
                                continue
                    
                    try:
                        # Get target size from display
                        if hasattr(display, 'get_target_size'):
                            target_size = display.get_target_size()
                        else:
                            # Fallback: use display size * DPR
                            dpr = getattr(display, '_device_pixel_ratio', 1.0)
                            target_size = QSize(
                                int(display.width() * dpr),
                                int(display.height() * dpr)
                            )
                        
                        # Get display mode
                        display_mode = getattr(display, 'display_mode', DisplayMode.FILL)
                        display_mode_str = display_mode.value if hasattr(display_mode, 'value') else str(display_mode).lower()
                        
                        # Try ImageWorker (separate process, avoids GIL)
                        # PERFORMANCE: No fallback to sync QImage load - that blocks for 5+ seconds
                        # If worker fails, skip this image entirely and try next one
                        processed_qimage = None
                        
                        if self._process_supervisor and self._process_supervisor.is_running(WorkerType.IMAGE):
                            worker_qimage = self._load_image_via_worker(
                                img_path,
                                target_size.width(),
                                target_size.height(),
                                display_mode=display_mode_str,
                                sharpen=sharpen,
                                timeout_ms=3000,  # 3s timeout: worker needs 273ms × 2 displays + overhead
                            )
                            if worker_qimage and not worker_qimage.isNull():
                                processed_qimage = worker_qimage
                                logger.debug(f"{TAG_ASYNC} Image loaded via ImageWorker for display {i}")
                            else:
                                logger.warning(f"{TAG_ASYNC} ImageWorker failed for display {i}, skipping image")
                                continue  # Skip this display - don't block with sync fallback
                        else:
                            # Worker not available - use cached image if available, otherwise skip
                            if qimage is not None and not qimage.isNull():
                                processed_qimage = AsyncImageProcessor.process_qimage(
                                    qimage,
                                    target_size,
                                    display_mode,
                                    use_lanczos=False,
                                    sharpen=sharpen,
                                )
                            else:
                                logger.warning(f"{TAG_ASYNC} No ImageWorker and no cache for display {i}, skipping")
                                continue
                        
                        # Convert to QPixmap on worker thread (Qt 6 allows this)
                        # PERF INSTRUMENTATION: Track conversion time
                        _conv_start = time.time()
                        processed_pixmap = QPixmap.fromImage(processed_qimage)
                        _conv_elapsed = (time.time() - _conv_start) * 1000
                        if _conv_elapsed > 50 and is_perf_metrics_enabled():
                            logger.warning(f"[PERF] [ASYNC] QPixmap.fromImage took {_conv_elapsed:.1f}ms for display {i}")
                        # Clear QImage reference to free memory (Section 1.1 fix)
                        processed_qimage = None
                        
                        # PERFORMANCE FIX: Don't load original image synchronously (5+ seconds)
                        # Use processed image for both pixmaps - original is only used for fallback
                        if qimage is None or qimage.isNull():
                            # Use processed image as original instead of loading full image
                            original_pixmap = processed_pixmap
                        else:
                            _conv2_start = time.time()
                            original_pixmap = QPixmap.fromImage(qimage)
                            _conv2_elapsed = (time.time() - _conv2_start) * 1000
                            if _conv2_elapsed > 50 and is_perf_metrics_enabled():
                                logger.warning(f"[PERF] [ASYNC] Original QPixmap.fromImage took {_conv2_elapsed:.1f}ms for display {i}")
                            # Clear QImage reference to free memory (Section 1.1 fix)
                            qimage = None
                        
                        processed_images[i] = {
                            'pixmap': processed_pixmap,
                            'original_pixmap': original_pixmap,
                            'target_size': target_size,
                            'path': img_path,
                        }
                    except Exception as e:
                        logger.debug(f"[ASYNC] Failed to process for display {i}: {e}")
                
                if not processed_images:
                    return None
                    
                return {
                    'processed': processed_images,
                    'same_image': same_image,
                }
            except Exception as e:
                logger.exception(f"[ASYNC] Background image processing failed: {e}")
                return None

        def _on_process_complete(result) -> None:
            """UI thread callback: convert to QPixmap and display."""
            try:
                data = result.result if result and result.success else None
                if data is None:
                    logger.warning(f"[ASYNC] Image processing failed, retrying (attempt {retry_count + 1}/10)")
                    self._loading_in_progress = False
                    if retry_count < 10 and self.image_queue:
                        next_meta = self.image_queue.next()
                        if next_meta:
                            self._load_and_display_image_async(next_meta, retry_count + 1)
                    return
                
                processed = data['processed']
                is_same_image = data.get('same_image', True)
                
                displays = self.display_manager.displays if self.display_manager else []
                displayed_paths = []
                
                # PERF: Stagger transition starts by 100ms per display to avoid
                # simultaneous transition completions which cause 100+ms UI blocks.
                stagger_ms = TRANSITION_STAGGER_MS
                
                for i, display in enumerate(displays):
                    if i not in processed:
                        continue
                    
                    proc_data = processed[i]
                    # Pixmaps already converted on worker thread
                    processed_pixmap = proc_data['pixmap']
                    original_pixmap = proc_data['original_pixmap']
                    img_path = proc_data['path']
                    
                    if processed_pixmap.isNull():
                        logger.warning(f"[ASYNC] QPixmap is null for display {i}")
                        continue
                    
                    # Use set_processed_image to avoid re-processing
                    # Stagger display updates to prevent simultaneous transition completions
                    delay_ms = i * stagger_ms
                    if delay_ms > 0:
                        def _delayed_set(d=display, pp=processed_pixmap, op=original_pixmap, ip=img_path):
                            if hasattr(d, 'set_processed_image'):
                                d.set_processed_image(pp, op, ip)
                            else:
                                d.set_image(pp, ip)
                        QTimer.singleShot(delay_ms, _delayed_set)
                    else:
                        if hasattr(display, 'set_processed_image'):
                            display.set_processed_image(processed_pixmap, original_pixmap, img_path)
                        else:
                            display.set_image(processed_pixmap, img_path)
                    
                    displayed_paths.append(img_path)
                
                # Emit signal for first image
                if displayed_paths:
                    self.image_changed.emit(displayed_paths[0])
                    if is_same_image:
                        logger.info(f"[ASYNC] Same image displayed on all monitors: {displayed_paths[0]}")
                    else:
                        logger.info(f"[ASYNC] Different images displayed on {len(displayed_paths)} displays")
                
                self._schedule_prefetch()
                self._loading_in_progress = False
                
            except Exception as e:
                logger.exception(f"[ASYNC] UI callback failed: {e}")
                self._loading_in_progress = False

        # Submit to COMPUTE pool for processing
        try:
            self.thread_manager.submit_compute_task(
                _do_load_and_process,
                callback=lambda r: self.thread_manager.run_on_ui_thread(lambda: _on_process_complete(r))
            )
        except Exception as e:
            logger.warning(f"[ASYNC] Failed to submit task, falling back to sync: {e}")
            self._load_and_display_image(image_meta, retry_count)
    
    def _load_and_display_image(self, image_meta: ImageMetadata, retry_count: int = 0) -> bool:
        """
        Load and display image synchronously. Auto-retries with next image on failure.
        
        NOTE: This is the legacy sync path. For better performance, use
        _load_and_display_image_async() which processes images off the UI thread.
        
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
            raw_same_image = self.settings_manager.get('display.same_image_all_monitors', True)
            same_image = SettingsManager.to_bool(raw_same_image, True)
            logger.debug(
                "Same image on all monitors setting: %s (raw=%r)",
                same_image,
                raw_same_image,
            )

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
                            # Prefer a pre-scaled variant for this display size if available
                            try:
                                d = self.display_manager.displays[i]
                                size = (d.width(), d.height())
                            except Exception as e:
                                logger.debug("[ENGINE] Exception suppressed: %s", e)
                                size = None
                            next_pixmap = self._load_image_task(next_meta, preferred_size=size)
                            if next_pixmap:
                                next_path = str(next_meta.local_path) if next_meta.local_path else next_meta.url or "unknown"
                                self.display_manager.show_image_on_screen(i, next_pixmap, next_path)
                logger.info(f"Different images displayed on {display_count} displays")
            
            self.image_changed.emit(image_path)
            # Schedule prefetch of next images
            self._schedule_prefetch()
            
            self._loading_in_progress = False
            return True
        
        except Exception as e:
            logger.exception(f"Load and display failed: {e}")
            self._loading_in_progress = False
            return False
    
    def _on_rotation_timer(self) -> None:
        """Handle rotation timer timeout."""
        logger.debug("Rotation timer triggered")
        # Update random transition choice for this rotation if enabled
        self._prepare_random_transition_if_needed()
        self._show_next_image()

    def _prepare_random_transition_if_needed(self) -> None:
        try:
            transitions = self.settings_manager.get('transitions', {})
            raw_rnd = transitions.get('random_always', self.settings_manager.get('transitions.random_always', False))
            rnd = SettingsManager.to_bool(raw_rnd, False)
            if not rnd:
                return
            # Available transition types; include GL-only when HW is enabled and
            # restrict to those enabled in the per-transition pool map.
            base_types = ["Crossfade", "Slide", "Wipe", "Diffuse", "Block Puzzle Flip"]
            # Treat legacy 'Rain Drops' entries as equivalent to 'Ripple' when
            # evaluating GL-only pools. "Claw Marks" and "Shuffle" have been
            # removed from the runtime and are no longer part of the random pool.
            gl_only_types = ["Blinds", "Peel", "3D Block Spins", "Ripple", "Warp Dissolve", "Crumble", "Particle"]

            try:
                raw_hw = self.settings_manager.get('display.hw_accel', False)
                hw = SettingsManager.to_bool(raw_hw, False)
            except Exception as e:
                logger.debug("[ENGINE] Exception suppressed: %s", e)
                hw = False

            pool_cfg = transitions.get('pool', {}) if isinstance(transitions.get('pool', {}), dict) else {}

            def _in_pool(name: str) -> bool:
                try:
                    if name == "Ripple":
                        raw_flag = pool_cfg.get("Ripple", pool_cfg.get("Rain Drops", True))
                    else:
                        raw_flag = pool_cfg.get(name, True)
                    return bool(SettingsManager.to_bool(raw_flag, True))
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
                    return True

            available: List[str] = []
            for name in base_types:
                if not _in_pool(name):
                    continue
                available.append(name)

            if hw:
                for name in gl_only_types:
                    if not _in_pool(name):
                        continue
                    available.append(name)

            if not available:
                # Fallback: always ensure at least Crossfade is available so
                # misconfigured pool settings cannot break rotation entirely.
                available = ["Crossfade"]
            # Avoid immediate repeats of transition type. Legacy "Shuffle"
            # selections are treated as "Crossfade" so the engine no longer
            # reintroduces Shuffle into the pool.
            last_type = self.settings_manager.get('transitions.last_random_choice', None)
            if last_type == "Shuffle":
                last_type = "Crossfade"
            candidates = [t for t in available if t != last_type] if last_type in available else available
            if not candidates:
                candidates = available
            choice = random.choice(candidates)
            
            # Also choose random parameters for transitions that need them
            # This ensures all displays use the SAME random parameters
            if choice == "Slide":
                directions = ['Left to Right', 'Right to Left', 'Top to Bottom', 'Bottom to Top']
                last_dir = self.settings_manager.get('transitions.slide.last_direction', None)
                candidates = [d for d in directions if d != last_dir] if last_dir in directions else directions
                direction = random.choice(candidates) if candidates else random.choice(directions)
                # Persist under nested slide key (no diagonals)
                self.settings_manager.set('transitions.slide.direction', direction)
                self.settings_manager.set('transitions.slide.last_direction', direction)
            elif choice == "Wipe":
                # Choose a random wipe direction and persist it
                wipe_directions = ['Left to Right', 'Right to Left', 'Top to Bottom', 'Bottom to Top', 
                                  'Diagonal TL-BR', 'Diagonal TR-BL']
                last_wipe_dir = self.settings_manager.get('transitions.wipe.last_direction', None)
                candidates = [d for d in wipe_directions if d != last_wipe_dir] if last_wipe_dir in wipe_directions else wipe_directions
                wdir = random.choice(candidates) if candidates else random.choice(wipe_directions)
                # Persist under nested wipe key
                self.settings_manager.set('transitions.wipe.direction', wdir)
                self.settings_manager.set('transitions.wipe.last_direction', wdir)
            
            # Persist chosen type for this rotation so all displays share it
            self.settings_manager.set('transitions.random_choice', choice)
            self.settings_manager.set('transitions.last_random_choice', choice)
            self.settings_manager.save()
            logger.info(f"Random transition choice for this rotation: {choice}")
        except Exception as e:
            logger.debug(f"Random transition selection failed: {e}")

    def _get_primary_display_size(self):
        """Return primary display size (width, height) for pre-scaling, or None.
        Safe helper for pre-scaling; returns None if displays not ready.
        """
        try:
            if self.display_manager and self.display_manager.displays:
                d0 = self.display_manager.displays[0]
                w, h = d0.width(), d0.height()
                if w > 0 and h > 0:
                    return (w, h)
        except Exception as e:
            logger.debug("[ENGINE] Exception suppressed: %s", e)
            return None
        return None

    def _get_distinct_display_sizes(self) -> List[Tuple[int, int]]:
        """Return distinct (width, height) pairs for all displays for prescaling.

        This is used by the prefetch pipeline to decide which `|scaled:WxH` keys
        to generate via COMPUTE tasks. It is intentionally conservative and
        returns logical widget sizes rather than attempting to second-guess DPR;
        `DisplayWidget` continues to handle device-pixel scaling when it
        prepares the final pixmap for each screen.
        """

        sizes: List[Tuple[int, int]] = []
        seen: set[Tuple[int, int]] = set()
        try:
            dm = self.display_manager
            if not dm or not getattr(dm, 'displays', None):
                return sizes
            for d in dm.displays:
                try:
                    w, h = d.width(), d.height()
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
                    continue
                if w <= 0 or h <= 0:
                    continue
                key = (w, h)
                if key in seen:
                    continue
                seen.add(key)
                sizes.append(key)
        except Exception:
            # On any unexpected error fall back to an empty list; prescaling is
            # strictly an optimisation and must never break image loading.
            return []
        return sizes
    
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
        
        if not self._transition_types:
            logger.warning("No transitions configured; ignoring cycle request")
            return

        raw_hw = self.settings_manager.get('display.hw_accel', False)
        hw = SettingsManager.to_bool(raw_hw, False)
        gl_only = {"Blinds", "Peel", "3D Block Spins", "Ripple", "Rain Drops", "Warp Dissolve", "Crumble", "Particle"}

        transitions_config = self.settings_manager.get('transitions', {})
        if not isinstance(transitions_config, dict):
            transitions_config = {}
        pool_cfg = transitions_config.get('pool', {}) if isinstance(transitions_config.get('pool', {}), dict) else {}

        def _in_pool(name: str) -> bool:
            try:
                raw_flag = pool_cfg.get(name, True)
                return bool(SettingsManager.to_bool(raw_flag, True))
            except Exception as e:
                logger.debug("[ENGINE] Exception suppressed: %s", e)
                return True

        # Cycle to next transition honoring HW capabilities and per-type pool
        # membership. Types excluded from the pool will not be selected when
        # cycling, but remain available for explicit selection via settings.
        for _ in range(len(self._transition_types)):
            self._current_transition_index = (self._current_transition_index + 1) % len(self._transition_types)
            candidate = self._transition_types[self._current_transition_index]
            if (not hw and candidate in gl_only) or not _in_pool(candidate):
                continue
            new_transition = candidate
            break
        else:
            # Fallback to Crossfade if somehow no valid transition found
            new_transition = "Crossfade"
            self._current_transition_index = self._transition_types.index(new_transition) if new_transition in self._transition_types else 0
        
        # Update settings with permissible transition
        if not hw and new_transition in gl_only:
            new_transition = "Crossfade"
            if new_transition in self._transition_types:
                self._current_transition_index = self._transition_types.index(new_transition)
        transitions_config = self.settings_manager.get('transitions', {})
        if not isinstance(transitions_config, dict):
            transitions_config = {}
        transitions_config['type'] = new_transition
        transitions_config['random_always'] = False
        self.settings_manager.set('transitions', transitions_config)
        self.settings_manager.remove('transitions.random_choice')
        self.settings_manager.remove('transitions.last_random_choice')
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
        
        # Wake media widget from idle mode when returning from settings
        # This ensures Spotify detection resumes if user opened Spotify while in settings
        try:
            if self.display_manager:
                for display in self.display_manager.get_displays():
                    media_widget = getattr(display, 'media_widget', None)
                    if media_widget and hasattr(media_widget, 'wake_from_idle'):
                        media_widget.wake_from_idle()
        except Exception as e:
            logger.debug("[ENGINE] Failed to wake media widget from idle: %s", e)
        
        coordinator = None
        settings_flag_cleared = False
        # Set settings dialog active flag FIRST - this prevents halo from showing
        try:
            from rendering.multi_monitor_coordinator import get_coordinator
            coordinator = get_coordinator()
            coordinator.set_settings_dialog_active(True)
        except Exception as e:
            logger.debug("[ENGINE] Exception suppressed: %s", e)
        
        # Hide and destroy all cursor halo windows
        if self.display_manager:
            for display in getattr(self.display_manager, 'displays', []):
                try:
                    halo = getattr(display, '_ctrl_cursor_hint', None)
                    if halo is not None:
                        halo.hide()
                        halo.close()
                        halo.deleteLater()
                        display._ctrl_cursor_hint = None
                except Exception as e:
                    logger.debug("[ENGINE] Exception suppressed: %s", e)
        
        # Stop the engine but DON'T exit the app
        self.stop(exit_app=False)
        
        try:
            app = QApplication.instance()
            if app:
                animations = AnimationManager(resource_manager=self.resource_manager)
                dialog = SettingsDialog(self.settings_manager, animations)
                # FIX: Use result or mark as intentionally ignored
                _ = dialog.exec()  # Result intentionally ignored - dialog handles its own state
                
                # After dialog closes, fully reset displays and restart
                logger.info("Settings dialog closed, performing full-style restart of screensaver")

                # Tear down any existing display manager stack so we get a fresh
                # set of DisplayWidget instances (clears stale GL/compositor state
                # and avoids banding on secondary displays).
                if self.display_manager:
                    try:
                        self.display_manager.cleanup()
                    except Exception as e:
                        logger.debug("DisplayManager cleanup after settings failed: %s", e, exc_info=True)
                    self.display_manager = None
                    self._display_initialized = False
                
                # Reset coordinator state (halo owner, ctrl state) to avoid stale refs
                try:
                    from rendering.multi_monitor_coordinator import get_coordinator
                    coordinator = get_coordinator()
                    coordinator.set_settings_dialog_active(False)  # Re-enable halo
                    coordinator.cleanup()
                except Exception as e:
                    logger.debug("Coordinator cleanup after settings failed: %s", e, exc_info=True)

                # Reinitialize displays using current settings
                if not self._initialize_display():
                    logger.error("Failed to reinitialize displays after settings; quitting")
                    QApplication.quit()
                    return

                # Recreate rotation timer with any updated timing settings
                self._setup_rotation_timer()

                # Note: stop(exit_app=False) already transitioned state to STOPPED,
                # so start() will not early-out. No need to manually set _running.

                if not self.start():
                    logger.error("Failed to restart screensaver after settings; quitting")
                    QApplication.quit()
        except Exception as e:
            logger.exception(f"Failed to open settings dialog: {e}")
            QApplication.quit()
        finally:
            if not settings_flag_cleared:
                try:
                    if coordinator is None:
                        from rendering.multi_monitor_coordinator import get_coordinator
                        coordinator = get_coordinator()
                    coordinator.set_settings_dialog_active(False)
                except Exception as e:
                    logger.debug("[ENGINE] Failed to reset settings dialog flag in finally: %s", e)
    
    def _on_exit_requested(self) -> None:
        """Handle exit request coming from any display window."""
        logger.info("Exit requested from display")
        self.stop()
    
    def _show_current_image(self) -> bool:
        """Show the current image from queue without advancing."""
        if not self.image_queue:
            return False
        
        current = self.image_queue.current()
        if current:
            return self._load_and_display_image(current)
        return False
    
    def _on_settings_changed(self, event) -> None:
        """Handle settings changed event."""
        # Event is an Event object with data attribute, not a dict
        data = getattr(event, 'data', None) or {}
        setting_key = data.get('key', '') if isinstance(data, dict) else ''
        logger.debug(f"Setting changed event: {setting_key}")
        
        # Handle specific settings changes
        if setting_key.startswith('timing.interval'):
            self._update_rotation_interval()
        elif setting_key.startswith('display.mode'):
            self._update_display_mode()
        elif setting_key.startswith('queue.shuffle'):
            self._update_shuffle_mode()
        elif setting_key.startswith('sources'):
            self._on_sources_changed()
    
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
    
    def _on_sources_changed(self) -> None:
        """Handle source configuration changes.
        
        State transition: RUNNING -> REINITIALIZING -> RUNNING
        
        Reinitializes sources and rebuilds the image queue when the user
        adds/removes folders or RSS feeds in settings. This ensures new
        sources are available immediately without restarting the screensaver.
        
        CRITICAL: Uses REINITIALIZING state (not STOPPING) so that:
        - _shutting_down property returns False
        - Async RSS loading continues (does NOT abort)
        This was the root cause of the RSS reload bug.
        """
        logger.info("Sources changed, reinitializing...")
        
        # Save current state to restore after reinitialization
        was_running = self._running
        
        # Transition to REINITIALIZING state
        # This is NOT a shutdown - _shutting_down will return False
        # allowing async RSS loading to proceed
        if was_running:
            self._transition_state(EngineState.REINITIALIZING)
        
        # Cancel in-flight async RSS loaders so they don't race the new config
        self._cancel_async_rss_load()

        # Clear image cache - old cached images may no longer be valid
        if self._image_cache:
            try:
                self._image_cache.clear()
                logger.info("Image cache cleared due to source change")
            except Exception as e:
                logger.debug(f"Failed to clear image cache: {e}")
        
        # Clear prefetcher inflight set to avoid stale paths
        if self._prefetcher:
            try:
                self._prefetcher.clear_inflight()
            except Exception as e:
                logger.debug(f"Failed to clear prefetcher inflight: {e}")
        
        # Clear existing sources
        self.folder_sources.clear()
        self.rss_sources.clear()
        
        # Reinitialize sources from updated settings
        if self._initialize_sources():
            # Rebuild the queue with new sources
            if self._build_image_queue():
                logger.info("Image queue rebuilt with updated sources")
                
                # Restart prefetcher with new queue
                if hasattr(self, '_prefetcher') and self._prefetcher:
                    try:
                        self._prefetcher.stop()
                    except Exception as e:
                        logger.debug("[ENGINE] Exception suppressed: %s", e)
                
                # Initialize prefetcher for new queue
                try:
                    from utils.image_prefetcher import ImagePrefetcher
                    self._prefetcher = ImagePrefetcher(
                        thread_manager=self.thread_manager,
                        cache=self.image_cache,
                        max_concurrent=2,
                    )
                    logger.info("Prefetcher restarted with updated queue")
                except Exception as e:
                    logger.warning(f"Failed to restart prefetcher: {e}")
            else:
                logger.warning("Failed to rebuild image queue after source change")
        else:
            logger.warning("No valid sources after source change")
        
        # Restore to RUNNING state if we were running before
        if was_running:
            self._transition_state(EngineState.RUNNING)
            logger.info("Sources reinitialization complete, engine back to RUNNING")
    
    def get_stats(self) -> Dict:
        """
        Get engine statistics.
        
        Returns:
            Dict with engine stats
        """
        stats = {
            'state': self._get_state().name,
            'running': self._running,
            'shutting_down': self._shutting_down,
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
