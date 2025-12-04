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
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QImage

from core.events import EventSystem, EventType
from core.resources import ResourceManager
from core.threading import ThreadManager
from core.settings import SettingsManager
from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from core.animation import AnimationManager

from engine.display_manager import DisplayManager
from engine.image_queue import ImageQueue
from sources.folder_source import FolderSource
from sources.rss_source import RSSSource
from sources.base_provider import ImageMetadata, ImageSourceType
from rendering.display_modes import DisplayMode
from rendering.image_processor_async import AsyncImageProcessor
from ui.settings_dialog import SettingsDialog
from utils.image_cache import ImageCache
from utils.image_prefetcher import ImagePrefetcher

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
        self._rotation_timer_resource_id: Optional[str] = None
        self._current_image: Optional[ImageMetadata] = None
        self._loading_in_progress: bool = False
        self._loading_lock = threading.Lock()  # FIX: Protect loading flag from race conditions
        # Canonical list of transition types used for C-key cycling. Legacy
        # "Claw Marks" entries have been fully removed from the engine and are
        # mapped to "Crossfade" at selection time for back-compat only. The
        # Shuffle transition has been retired for v1.2 and no longer appears in
        # the active rotation.
        self._transition_types: List[str] = [
            "Crossfade",
            "Slide",
            "Wipe",
            "Peel",
            "Diffuse",
            "Block Puzzle Flip",
            "3D Block Spins",
            "Ripple",  # formerly "Rain Drops"
            "Warp Dissolve",
            "Blinds",
        ]
        self._current_transition_index: int = 0  # Will sync with settings in initialize()
        # Caching / prefetch
        self._image_cache: Optional[ImageCache] = None
        self._prefetcher: Optional[ImagePrefetcher] = None
        self._prefetch_ahead: int = 5
        # Background RSS refresh
        self._rss_refresh_timer: Optional[QTimer] = None
        self._rss_merge_lock = threading.Lock()
        
        logger.info("ScreensaverEngine created")
    
    def initialize(self) -> bool:
        """
        Initialize all engine components.
        
        Returns:
            True if initialization successful, False otherwise
        """
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

            # Global startup cap for RSS images: at most 8 images are
            # downloaded across ALL RSS feeds before the screensaver
            # starts. We divide this cap randomly among configured
            # feeds so the mix varies between runs while staying
            # within the global limit.
            rss_startup_cap = 8
            per_feed_limits: Dict[str, int] = {}
            try:
                if rss_feeds and rss_startup_cap > 0:
                    feed_count = len(rss_feeds)
                    total_slots = max(0, rss_startup_cap)
                    per_feed_limits = {u: 0 for u in rss_feeds}

                    # Ensure at least one slot for as many feeds as the
                    # cap allows, then distribute any remaining slots
                    # randomly to avoid stagnation.
                    base = min(feed_count, total_slots)
                    if base > 0:
                        if feed_count > base:
                            from random import sample
                            initial = sample(rss_feeds, base)
                        else:
                            initial = list(rss_feeds)
                        for u in initial:
                            per_feed_limits[u] += 1
                        remaining = total_slots - base
                        import random as _rnd
                        while remaining > 0 and rss_feeds:
                            u = _rnd.choice(rss_feeds)
                            per_feed_limits[u] += 1
                            remaining -= 1
            except Exception as e:
                logger.debug(f"RSS startup cap distribution failed, falling back to per-feed defaults: {e}")
                per_feed_limits = {}
            
            # Only use RSS feeds if explicitly configured by user
            for feed_url in rss_feeds:
                try:
                    # Create RSS source with save-to-disk settings if enabled
                    if rss_save_to_disk and rss_save_directory:
                        rss_source = RSSSource(
                            feed_urls=[feed_url],
                            save_to_disk=True,
                            save_directory=Path(rss_save_directory),
                            max_images_per_refresh=per_feed_limits.get(feed_url),
                        )
                        logger.info(f"RSS source added with save-to-disk: {feed_url} -> {rss_save_directory}")
                    else:
                        rss_source = RSSSource(
                            feed_urls=[feed_url],
                            max_images_per_refresh=per_feed_limits.get(feed_url),
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

    def _get_rss_background_cap(self) -> int:
        """Return the global background cap for RSS images.

        This limits how many RSS/JSON images we keep queued at any
        given time. Defaults to 30 but can be overridden via
        settings (``sources.rss_background_cap``).
        """
        try:
            if not self.settings_manager:
                return 30
            raw = self.settings_manager.get('sources.rss_background_cap', 30)
            cap = int(raw)
            return cap if cap > 0 else 0
        except Exception:
            return 30

    def _get_rss_stale_minutes(self) -> int:
        """Return TTL in minutes for stale RSS images.

        Defaults to 30 but can be overridden via
        settings (``sources.rss_stale_minutes``). A value
        <= 0 disables stale expiration.
        """
        try:
            if not self.settings_manager:
                return 30
            raw = self.settings_manager.get('sources.rss_stale_minutes', 30)
            minutes = int(raw)
            return minutes if minutes > 0 else 0
        except Exception:
            return 30

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
            except Exception:
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

            cap = self._get_rss_background_cap()
            if cap <= 0:
                return

            try:
                existing = self.image_queue.get_all_images()
            except Exception:
                existing = []

            current_rss = 0
            for m in existing:
                try:
                    if getattr(m, 'source_type', None) == ImageSourceType.RSS:
                        current_rss += 1
                except Exception:
                    continue

            if current_rss >= cap:
                return

            for src in self.rss_sources:
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
                                except Exception:
                                    pass
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
            except Exception:
                existing = []

            existing_keys = set()
            current_rss = 0
            for m in existing:
                try:
                    key = str(m.local_path) if m.local_path else (m.url or "")
                    if key:
                        existing_keys.add(key)
                    if getattr(m, 'source_type', None) == ImageSourceType.RSS:
                        current_rss += 1
                except Exception:
                    continue

            remaining = cap - current_rss
            if remaining <= 0:
                return

            new_items: List[ImageMetadata] = []
            for m in images:
                try:
                    if getattr(m, 'source_type', None) != ImageSourceType.RSS:
                        continue
                    key = str(m.local_path) if m.local_path else (m.url or "")
                    if not key or key in existing_keys:
                        continue
                    new_items.append(m)
                except Exception:
                    continue

            if not new_items:
                return

            try:
                random.shuffle(new_items)
            except Exception:
                pass

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
                    except Exception:
                        snapshot = []

                    try:
                        history_paths = set(self.image_queue.get_history(self.image_queue.history_size))
                    except Exception:
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
                        except Exception:
                            continue

                    if stale_paths:
                        max_remove = min(len(stale_paths), added)
                        for path in stale_paths[:max_remove]:
                            try:
                                if self.image_queue.remove_image(path):
                                    removed_stale += 1
                            except Exception:
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
                    except Exception:
                        final_existing = []

                    total_rss = 0
                    for m in final_existing:
                        try:
                            if getattr(m, 'source_type', None) == ImageSourceType.RSS:
                                total_rss += 1
                        except Exception:
                            continue

                    self.event_system.publish(
                        EventType.RSS_UPDATED,
                        data={"added": added, "removed_stale": removed_stale, "total_rss": total_rss},
                        source=self,
                    )
                except Exception:
                    pass

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
                except Exception:
                    continue
            self._prefetcher.prefetch_paths(paths)
            if paths and is_verbose_logging():
                logger.debug(f"Prefetch scheduled for {len(paths)} upcoming images")
                # Avoid heavy UI-side conversions while transitions are active.
                skip_heavy_ui_work = False
                try:
                    if self.display_manager and hasattr(self.display_manager, "has_running_transition"):
                        skip_heavy_ui_work = self.display_manager.has_running_transition()
                except Exception:
                    skip_heavy_ui_work = False
                # UI warmup: convert first cached QImage to QPixmap to reduce on-demand conversion
                try:
                    if not skip_heavy_ui_work and self.thread_manager and self._image_cache:
                        first = paths[0]
                        def _ui_convert():
                            try:
                                from PySide6.QtGui import QPixmap, QImage
                                cached = self._image_cache.get(first)
                                if isinstance(cached, QImage):
                                    pm = QPixmap.fromImage(cached)
                                    if not pm.isNull():
                                        self._image_cache.put(first, pm)
                                        logger.debug(f"UI warmup: cached QPixmap for {first}")
                            except Exception as e:
                                logger.debug(f"UI warmup failed for {first}: {e}")
                        self.thread_manager.run_on_ui_thread(_ui_convert)
                except Exception:
                    pass
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
                            except Exception:
                                pass
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
                            except Exception:
                                pass
                except Exception:
                    pass
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
            try:
                self._rotation_timer.stop()
            except Exception:
                pass
            if self._rotation_timer_resource_id and self.resource_manager:
                try:
                    self.resource_manager.unregister(self._rotation_timer_resource_id, force=True)
                except Exception:
                    pass
                self._rotation_timer_resource_id = None

        self._rotation_timer = QTimer(self)
        self._rotation_timer.setInterval(interval_ms)
        self._rotation_timer.timeout.connect(self._on_rotation_timer)
        # Register with ResourceManager
        try:
            if self.resource_manager:
                self._rotation_timer_resource_id = self.resource_manager.register_qt(
                    self._rotation_timer,
                    description="Engine rotation timer",
                )
        except Exception:
            pass
        
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
            logger.debug("Engine stop requested (exit_app=%s)", exit_app)

            # Stop background RSS refresh timer if present so no further
            # callbacks run after teardown begins.
            if self._rss_refresh_timer is not None:
                try:
                    if self._rss_refresh_timer.isActive():
                        self._rss_refresh_timer.stop()
                    logger.debug("RSS refresh timer stopped")
                except RuntimeError as e:
                    logger.debug("RSS refresh timer stop during cleanup raised: %s", e, exc_info=True)
                except Exception as e:
                    logger.debug("RSS refresh timer stop failed: %s", e, exc_info=True)
                self._rss_refresh_timer = None
            
            # Stop rotation timer (do not delete here to avoid double-delete on repeated stops)
            if self._rotation_timer:
                try:
                    if self._rotation_timer.isActive():
                        self._rotation_timer.stop()
                    logger.debug("Rotation timer stopped")
                except RuntimeError as e:
                    logger.debug(f"Timer stop during cleanup raised: {e}")
                try:
                    self._rotation_timer.deleteLater()
                except Exception as e:
                    logger.debug("Rotation timer deleteLater failed during stop: %s", e, exc_info=True)
                if self._rotation_timer_resource_id and self.resource_manager:
                    try:
                        self.resource_manager.unregister(self._rotation_timer_resource_id, force=True)
                    except Exception as e:
                        logger.debug(
                            "Failed to unregister rotation timer resource %s during stop: %s",
                            self._rotation_timer_resource_id,
                            e,
                            exc_info=True,
                        )
                    self._rotation_timer_resource_id = None
                self._rotation_timer = None
            
            # Clear and hide/cleanup displays
            if self.display_manager:
                try:
                    try:
                        display_count = self.display_manager.get_display_count()
                    except Exception:
                        display_count = len(getattr(self.display_manager, "displays", []))
                    logger.info(
                        "Stopping displays via DisplayManager (count=%s, exit_app=%s)",
                        display_count,
                        exit_app,
                    )
                except Exception:
                    logger.info(
                        "Stopping displays via DisplayManager (count=?, exit_app=%s)",
                        exit_app,
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
                    # Just pausing (e.g., for settings) - hide windows
                    try:
                        self.display_manager.hide_all()
                        logger.debug("Displays cleared and hidden")
                    except Exception as e:
                        logger.warning("DisplayManager.hide_all() failed during stop: %s", e, exc_info=True)
            
            # Stop any pending image loads
            self._loading_in_progress = False
            
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
            
            logger.info("Engine cleanup complete")
        
        except Exception as e:
            logger.exception(f"Cleanup failed: {e}")
    
    def _show_next_image(self) -> bool:
        """Load and display next image from queue."""
        # If random transitions are enabled, prepare a new non-repeating choice for this change
        try:
            self._prepare_random_transition_if_needed()
        except Exception:
            pass
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
                except Exception:
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
                        except Exception:
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
                            except Exception:
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
            gl_only_types = ["Blinds", "Peel", "3D Block Spins", "Ripple", "Rain Drops", "Warp Dissolve"]

            try:
                raw_hw = self.settings_manager.get('display.hw_accel', False)
                hw = SettingsManager.to_bool(raw_hw, False)
            except Exception:
                hw = False

            pool_cfg = transitions.get('pool', {}) if isinstance(transitions.get('pool', {}), dict) else {}

            def _in_pool(name: str) -> bool:
                try:
                    raw_flag = pool_cfg.get(name, True)
                    return bool(SettingsManager.to_bool(raw_flag, True))
                except Exception:
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
        except Exception:
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
                except Exception:
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
        gl_only = {"Blinds", "Peel", "3D Block Spins", "Ripple", "Rain Drops", "Warp Dissolve", "Shuffle"}

        transitions_config = self.settings_manager.get('transitions', {})
        if not isinstance(transitions_config, dict):
            transitions_config = {}
        pool_cfg = transitions_config.get('pool', {}) if isinstance(transitions_config.get('pool', {}), dict) else {}

        def _in_pool(name: str) -> bool:
            try:
                raw_flag = pool_cfg.get(name, True)
                return bool(SettingsManager.to_bool(raw_flag, True))
            except Exception:
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
                    except Exception:
                        logger.debug("DisplayManager cleanup after settings failed", exc_info=True)
                    self.display_manager = None
                    self._display_initialized = False

                # Reinitialize displays using current settings
                if not self._initialize_display():
                    logger.error("Failed to reinitialize displays after settings; quitting")
                    QApplication.quit()
                    return

                # Recreate rotation timer with any updated timing settings
                self._setup_rotation_timer()

                # Ensure start() does not early-out on a stale running flag
                self._running = False

                if not self.start():
                    logger.error("Failed to restart screensaver after settings; quitting")
                    QApplication.quit()
        except Exception as e:
            logger.exception(f"Failed to open settings dialog: {e}")
            QApplication.quit()
    
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
