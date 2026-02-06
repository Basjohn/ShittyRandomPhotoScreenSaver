"""
RSSCoordinator - State machine, dynamic limits, orchestration.

Responsibilities:
    - State machine: IDLE → LOADING → LOADED → ERROR
    - Dynamic download budget based on cache size vs TARGET_TOTAL_IMAGES
    - Orchestrate cache, parser, downloader, and health tracker
    - Provide clean API for screensaver_engine (replaces raw RSSSource usage)
    - No time.sleep() in main flow - delegates to downloader's interruptible waits
    - ThreadManager integration for async loading
    - ResourceManager integration via RSSCache
"""
import threading
from enum import Enum, auto
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable, Set

from sources.base_provider import ImageMetadata, ImageSourceType
from sources.rss.constants import (
    DEFAULT_RSS_FEEDS,
    TARGET_TOTAL_IMAGES,
    MAX_PER_FEED_DOWNLOAD,
    MIN_PER_FEED_DOWNLOAD,
    MAX_REDDIT_FEEDS_PER_STARTUP,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_MAX_CACHE_SIZE_MB,
    get_source_priority,
)
from sources.rss.cache import RSSCache
from sources.rss.parser import RSSParser, ParsedEntry
from sources.rss.downloader import RSSDownloader
from sources.rss.health import FeedHealthTracker
from core.logging.logger import get_logger

logger = get_logger(__name__)


class RSSState(Enum):
    """RSS coordinator state machine."""
    IDLE = auto()
    LOADING = auto()
    LOADED = auto()
    ERROR = auto()


class RSSCoordinator:
    """Orchestrates the full RSS image pipeline.

    Usage from screensaver_engine::

        coord = RSSCoordinator(
            feed_urls=[...],
            thread_manager=self.thread_manager,
            resource_manager=self.resource_manager,
            shutdown_check=lambda: not self._shutting_down,
        )
        # Instant cached images
        cached = coord.get_cached_images()
        # Async load new images (runs on IO pool)
        coord.load_async(on_images=self._on_rss_images)
    """

    def __init__(
        self,
        feed_urls: Optional[List[str]] = None,
        cache_dir: Optional[Path] = None,
        max_cache_size_mb: int = DEFAULT_MAX_CACHE_SIZE_MB,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        save_to_disk: bool = False,
        save_directory: Optional[Path] = None,
        thread_manager=None,
        resource_manager=None,
        shutdown_check: Optional[Callable[[], bool]] = None,
    ):
        self.feed_urls = feed_urls or list(DEFAULT_RSS_FEEDS.values())
        self._state_lock = threading.Lock()  # protects _state reads/writes
        self._state = RSSState.IDLE
        self._thread_manager = thread_manager
        self._shutdown_check = shutdown_check

        # Save-to-disk config
        self._save_to_disk = save_to_disk
        self._save_directory = Path(save_directory) if save_directory else None
        if self._save_to_disk and self._save_directory:
            try:
                self._save_directory.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"[RSS_COORD] Failed to create save dir: {e}")
                self._save_to_disk = False

        # Sub-modules
        self._cache = RSSCache(
            cache_dir=cache_dir,
            max_cache_size_mb=max_cache_size_mb,
            resource_manager=resource_manager,
        )
        self._downloader = RSSDownloader(
            timeout=timeout,
            shutdown_check=shutdown_check,
        )
        self._health = FeedHealthTracker()

        # NOTE: load_from_disk() is NOT called here to avoid blocking
        # the UI thread.  Call warm_cache() explicitly or let load_async()
        # do it on the IO pool.
        self._cache_warmed = False

        logger.info(f"[RSS_COORD] Initialised: {len(self.feed_urls)} feeds")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> RSSState:
        with self._state_lock:
            return self._state

    def _set_state(self, s: RSSState) -> None:
        with self._state_lock:
            self._state = s

    @property
    def cache_dir(self) -> Path:
        return self._cache.cache_dir

    @property
    def cached_count(self) -> int:
        return self._cache.count

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def warm_cache(self) -> int:
        """Load cached images from disk.  Safe to call from any thread.

        Returns count of images loaded.  Idempotent.
        """
        if self._cache_warmed:
            return self._cache.count
        n = self._cache.load_from_disk()
        self._cache_warmed = True
        return n

    def get_cached_images(self) -> List[ImageMetadata]:
        """Return images currently in cache (no network)."""
        return list(self._cache.images)

    def get_all_images(self) -> List[ImageMetadata]:
        """Return all images (cached + freshly downloaded)."""
        return list(self._cache.images)

    def load_async(self, on_images: Optional[Callable[[List[ImageMetadata]], None]] = None) -> None:
        """Start async loading on the IO thread pool.

        Args:
            on_images: Callback invoked with newly downloaded images (on IO thread).
        """
        if self._thread_manager is None:
            logger.warning("[RSS_COORD] No ThreadManager, falling back to sync load")
            self.warm_cache()
            new_images = self._load_feeds()
            if on_images:
                on_images(new_images)
            return

        def _task():
            self.warm_cache()  # disk I/O on IO thread, not UI thread
            new_images = self._load_feeds()
            if on_images:
                on_images(new_images)  # always call so engine can pre-load cache

        self._thread_manager.submit_io_task(_task)

    def load_sync(self) -> List[ImageMetadata]:
        """Synchronous load - blocks until complete. Returns new images."""
        self.warm_cache()
        return self._load_feeds()

    def refresh_single_feed(self, feed_url: str) -> List[ImageMetadata]:
        """Refresh a single feed (for background refresh). Returns new images."""
        return self._process_single_feed(
            feed_url,
            max_images=MAX_PER_FEED_DOWNLOAD,
            existing_paths=self._cache.existing_paths(),
        )

    def set_shutdown_check(self, cb: Optional[Callable[[], bool]]) -> None:
        self._shutdown_check = cb
        self._downloader.set_shutdown_check(cb)

    def request_stop(self) -> None:
        """Signal all sub-modules to abort immediately."""
        self._downloader.request_stop()

    def get_feed_health(self) -> dict:
        return self._health.get_status(self.feed_urls)

    # ------------------------------------------------------------------
    # Core loading logic
    # ------------------------------------------------------------------

    def _load_feeds(self) -> List[ImageMetadata]:
        """Load images from all feeds respecting dynamic limits.

        Returns list of newly downloaded ImageMetadata (not cached ones).
        """
        self._set_state(RSSState.LOADING)

        # Dynamic budget
        cached = self._cache.count
        new_needed = max(0, TARGET_TOTAL_IMAGES - cached)

        if new_needed == 0:
            logger.info(
                f"[RSS_COORD] Cache full ({cached} >= {TARGET_TOTAL_IMAGES}), "
                f"skipping all downloads"
            )
            self._set_state(RSSState.LOADED)
            return []

        num_feeds = len(self.feed_urls)
        if num_feeds == 0:
            self._set_state(RSSState.LOADED)
            return []

        per_feed = max(MIN_PER_FEED_DOWNLOAD, new_needed // num_feeds)
        per_feed = min(per_feed, MAX_PER_FEED_DOWNLOAD)

        logger.info(
            f"[RSS_COORD] Budget: cached={cached}, target={TARGET_TOTAL_IMAGES}, "
            f"new_needed={new_needed}, per_feed={per_feed}, feeds={num_feeds}"
        )

        # Sort by priority (highest first), shuffle within same priority for variety
        sorted_urls = sorted(self.feed_urls, key=get_source_priority, reverse=True)

        # Limit Reddit feeds
        reddit_count = 0
        urls_to_process = []
        for url in sorted_urls:
            is_reddit = "reddit.com" in url.lower()
            if is_reddit:
                if reddit_count >= MAX_REDDIT_FEEDS_PER_STARTUP:
                    logger.debug(f"[RSS_COORD] Skipping Reddit feed (limit): {url[:60]}")
                    continue
                reddit_count += 1
            urls_to_process.append(url)

        existing_paths = self._cache.existing_paths()
        all_new: List[ImageMetadata] = []
        total_budget_remaining = new_needed

        for i, feed_url in enumerate(urls_to_process):
            if not self._should_continue():
                logger.info("[RSS_COORD] Shutdown requested, aborting load")
                break

            if total_budget_remaining <= 0:
                logger.info(f"[RSS_COORD] Budget exhausted after {i} feeds")
                break

            # Skip unhealthy feeds
            if self._health.should_skip(feed_url):
                logger.debug(f"[RSS_COORD] Skipping unhealthy feed: {feed_url[:60]}")
                continue

            feed_limit = min(per_feed, total_budget_remaining)
            logger.info(f"[RSS_COORD] Feed {i+1}/{len(urls_to_process)}: {feed_url[:60]}... (limit={feed_limit})")

            new_images = self._process_single_feed(feed_url, feed_limit, existing_paths)

            if new_images:
                all_new.extend(new_images)
                total_budget_remaining -= len(new_images)
                # Update existing paths for dedup across feeds
                for img in new_images:
                    if img.local_path:
                        existing_paths.add(str(img.local_path))
                self._health.record_success(feed_url)
            else:
                is_reddit = "reddit.com" in feed_url.lower()
                if is_reddit:
                    self._health.record_failure(feed_url)

        # Cleanup cache if we added images and cache is large enough
        if all_new and self._cache.count > 20:
            self._cache.cleanup()

        self._set_state(RSSState.LOADED)
        logger.info(f"[RSS_COORD] Complete: {len(all_new)} new images from {len(urls_to_process)} feeds")
        return all_new

    def _process_single_feed(
        self,
        feed_url: str,
        max_images: int,
        existing_paths: Set[str],
    ) -> List[ImageMetadata]:
        """Download and parse a single feed. Returns list of new ImageMetadata."""
        if not self._should_continue():
            return []

        request_url, mode, original_url = RSSParser.resolve_feed_mode(feed_url)
        entries: List[ParsedEntry] = []

        try:
            if mode == "json":
                data = self._downloader.fetch_json(request_url)
                if data is not None:
                    entries = RSSParser.parse_json(data, original_url, max_entries=max_images)
            else:
                feed_data = self._downloader.fetch_rss(request_url)
                if feed_data is not None:
                    if feed_data.bozo:
                        logger.warning(f"[RSS_COORD] Feed has parsing errors: {feed_url[:60]}")
                    entries = RSSParser.parse_rss(feed_data, feed_url, max_entries=max_images)
        except Exception as e:
            logger.error(f"[RSS_COORD] Feed fetch/parse failed: {feed_url[:60]} - {e}")
            return []

        if not entries:
            return []

        # Download images from parsed entries
        new_images: List[ImageMetadata] = []
        for entry in entries:
            if not self._should_continue():
                break
            if len(new_images) >= max_images:
                break

            # Dedup check
            expected_path = str(self._cache.get_cache_path(entry.image_url))
            if expected_path in existing_paths:
                continue

            cached_path = self._downloader.download_image(
                entry.image_url, self._cache.cache_dir
            )
            if not cached_path:
                continue

            # Save to permanent storage if configured
            if self._save_to_disk and self._save_directory:
                self._downloader.download_image_to_save_dir(cached_path, self._save_directory)

            meta = ImageMetadata(
                source_type=ImageSourceType.RSS,
                source_id=feed_url,
                image_id=entry.image_url.split("/")[-1],
                local_path=cached_path,
                url=entry.image_url,
                title=entry.title,
                description=entry.description,
                author=entry.author,
                created_date=entry.created_date,
                fetched_date=datetime.utcnow(),
                file_size=cached_path.stat().st_size if cached_path.exists() else 0,
                format=cached_path.suffix[1:].upper() if cached_path.suffix else "UNKNOWN",
            )

            self._cache.add(meta)
            self._cache.mark_cached(entry.image_url)
            new_images.append(meta)

        if new_images:
            logger.info(f"[RSS_COORD] +{len(new_images)} images from {feed_url[:60]}")

        return new_images

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _should_continue(self) -> bool:
        if self._shutdown_check is not None:
            return self._shutdown_check()
        return True
