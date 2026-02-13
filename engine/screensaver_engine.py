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
import threading
import random
from enum import Enum, auto
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QPixmap, QImage

from core.events import EventSystem
from core.resources import ResourceManager
from core.threading import ThreadManager
from core.settings import SettingsManager
from core.logging.logger import get_logger
from core.process.types import WorkerType
from core.process.supervisor import ProcessSupervisor
from core.process.workers import (
    image_worker_main,
    rss_worker_main,
    fft_worker_main,
    transition_worker_main,
)

from engine.display_manager import DisplayManager
from engine.image_queue import ImageQueue
from sources.folder_source import FolderSource
from sources.rss.coordinator import RSSCoordinator
from sources.base_provider import ImageMetadata
from rendering.display_modes import DisplayMode
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
        
        # Engine components
        self.display_manager: Optional[DisplayManager] = None
        self.image_queue: Optional[ImageQueue] = None
        
        # Image sources
        self.folder_sources: List[FolderSource] = []
        self.rss_coordinator: Optional[RSSCoordinator] = None
        
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
            
            # Migrate legacy storage paths (safe to call multiple times)
            try:
                from core.settings.storage_paths import run_all_migrations
                run_all_migrations()
            except Exception as exc:
                logger.debug("[STORAGE] Migration failed (non-fatal): %s", exc)
            
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
            
            # Settings manager (skip if pre-assigned, e.g. by tests)
            if self.settings_manager is None:
                self.settings_manager = SettingsManager()
            logger.debug("SettingsManager initialized")
            
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

            # Create single RSSCoordinator with all feed URLs
            if rss_feeds:
                try:
                    self.rss_coordinator = RSSCoordinator(
                        feed_urls=rss_feeds,
                        save_to_disk=bool(rss_save_to_disk and rss_save_directory),
                        save_directory=Path(rss_save_directory) if rss_save_directory else None,
                        thread_manager=self.thread_manager,
                        resource_manager=self.resource_manager,
                        shutdown_check=lambda: not self._shutting_down,
                    )
                    sources_initialized += 1
                    logger.info(f"RSSCoordinator created with {len(rss_feeds)} feeds")
                except Exception as e:
                    logger.warning(f"[FALLBACK] Failed to create RSSCoordinator: {e}")
            
            rss_count = len(rss_feeds) if self.rss_coordinator else 0
            logger.info(f"Initialized {sources_initialized} image sources "
                       f"({len(self.folder_sources)} folder, {rss_count} RSS feeds)")
            
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
            
            # If we have no local images and no RSS sources at all, fail
            if not local_images and not self.rss_coordinator:
                logger.error("No images found from any source")
                self.error_occurred.emit("No images found")
                return False

            # When RSS feeds exist, warm the disk cache first so cached
            # images are available immediately without network I/O.
            if self.rss_coordinator:
                try:
                    cached_count = self.rss_coordinator.warm_cache()
                    if cached_count > 0:
                        cached_imgs = self.rss_coordinator.get_cached_images()
                        if cached_imgs:
                            import random as _rnd
                            cap = 35
                            try:
                                if self.settings_manager:
                                    cap = int(self.settings_manager.get(
                                        'sources.rss_rotating_cache_size', 20))
                            except Exception:
                                pass
                            if len(cached_imgs) > cap:
                                _rnd.shuffle(cached_imgs)
                                cached_imgs = cached_imgs[:cap]
                            n = self.image_queue.add_images(cached_imgs)
                            logger.info(f"Pre-loaded {n} cached RSS images from disk (of {cached_count} in cache)")
                except Exception as exc:
                    logger.debug("[ENGINE] RSS cache warm failed: %s", exc)

            # Start async RSS loading for fresh images (non-blocking)
            if self.rss_coordinator:
                self._load_rss_images_async()

            # If we still have zero images after cache pre-load AND no local
            # images, do a short sync load as last resort.
            if self.image_queue.total_images() == 0 and self.rss_coordinator:
                logger.info("No cached or local images - waiting for RSS images to load...")
                self._load_rss_images_sync()
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
    
    def _load_rss_images_async(self) -> None:
        """Delegates to engine.engine_rss."""
        from engine.engine_rss import load_rss_images_async
        load_rss_images_async(self)

    def _load_rss_images_sync(self) -> None:
        """Delegates to engine.engine_rss."""
        from engine.engine_rss import load_rss_images_sync
        load_rss_images_sync(self)

    def _get_rss_background_cap(self) -> int:
        """Delegates to engine.engine_rss."""
        from engine.engine_rss import get_rss_background_cap
        return get_rss_background_cap(self)

    def _get_dynamic_rss_settings(self):
        """Delegates to engine.engine_rss."""
        from engine.engine_rss import get_dynamic_rss_settings
        return get_dynamic_rss_settings(self)

    def _get_rss_stale_minutes(self) -> int:
        """Delegates to engine.engine_rss."""
        from engine.engine_rss import get_rss_stale_minutes
        return get_rss_stale_minutes(self)

    def _start_rss_background_refresh_if_needed(self) -> None:
        """Delegates to engine.engine_rss."""
        from engine.engine_rss import start_rss_background_refresh_if_needed
        start_rss_background_refresh_if_needed(self)

    def _background_refresh_rss(self) -> None:
        """Delegates to engine.engine_rss."""
        from engine.engine_rss import background_refresh_rss
        background_refresh_rss(self)

    def _merge_rss_images_from_refresh(self, images) -> None:
        """Delegates to engine.engine_rss."""
        from engine.engine_rss import merge_rss_images_from_refresh
        merge_rss_images_from_refresh(self, images)

    def _initialize_cache_prefetcher(self) -> None:
        try:
            max_items = int(self.settings_manager.get('cache.max_items', 24))
            max_mem_mb = int(self.settings_manager.get('cache.max_memory_mb', 1024))
            max_conc = int(self.settings_manager.get('cache.max_concurrent', 2))
            self._image_cache = ImageCache(max_items=max_items, max_memory_mb=max_mem_mb)
            if self.thread_manager:
                self._prefetcher = ImagePrefetcher(self.thread_manager, self._image_cache, max_concurrent=max_conc)
            logger.info(f"Image prefetcher initialized (ahead={self._prefetch_ahead}, max_concurrent={max_conc})")
            self._schedule_prefetch()
        except Exception as e:
            logger.debug(f"Prefetcher init failed: {e}")

    def _schedule_prefetch(self) -> None:
        """Delegates to engine.image_pipeline."""
        from engine.image_pipeline import schedule_prefetch
        schedule_prefetch(self)

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
        """Delegates to engine.engine_lifecycle."""
        from engine.engine_lifecycle import stop
        stop(self, exit_app)

    def _stop_qtimer_safe(self, timer=None, *, description: str) -> None:
        """Delegates to engine.engine_lifecycle."""
        from engine.engine_lifecycle import stop_qtimer_safe
        stop_qtimer_safe(self, timer, description=description)

    def cleanup(self) -> None:
        """Delegates to engine.engine_lifecycle."""
        from engine.engine_lifecycle import cleanup
        cleanup(self)

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
        """Delegates to engine.image_pipeline."""
        from engine.image_pipeline import load_image_via_worker
        return load_image_via_worker(
            self, image_path, target_width, target_height,
            display_mode=display_mode, sharpen=sharpen, timeout_ms=timeout_ms,
        )

    def _load_image_task(self, image_meta: ImageMetadata, preferred_size: Optional[tuple] = None) -> Optional[QPixmap]:
        """Delegates to engine.image_pipeline."""
        from engine.image_pipeline import load_image_task
        return load_image_task(self, image_meta, preferred_size=preferred_size)

    def _load_and_display_image_async(self, image_meta: ImageMetadata, retry_count: int = 0) -> None:
        """Delegates to engine.image_pipeline."""
        from engine.image_pipeline import load_and_display_image_async
        load_and_display_image_async(self, image_meta, retry_count)


    def _load_and_display_image(self, image_meta: ImageMetadata, retry_count: int = 0) -> bool:
        from engine.image_pipeline import load_and_display_image
        return load_and_display_image(self, image_meta, retry_count)

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
                except Exception as _e:
                    logger.debug("[ENGINE] Exception suppressed: %s", _e)
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
                except Exception as _e:
                    logger.debug("[ENGINE] Exception suppressed: %s", _e)
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
        """Delegates to engine.engine_handlers."""
        from engine.engine_handlers import on_cycle_transition
        on_cycle_transition(self)

    def _on_settings_requested(self) -> None:
        """Delegates to engine.engine_handlers."""
        from engine.engine_handlers import on_settings_requested
        on_settings_requested(self)

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
        """Delegates to engine.engine_handlers."""
        from engine.engine_handlers import on_sources_changed
        on_sources_changed(self)

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
            'rss_sources': len(self.rss_coordinator.feed_urls) if self.rss_coordinator else 0,
        }
        
        if self.image_queue:
            stats['queue'] = self.image_queue.get_stats()
        
        if self.display_manager:
            stats['displays'] = self.display_manager.get_display_count()
        
        return stats
    
    def is_running(self) -> bool:
        """Check if engine is running."""
        return self._running
