"""
RSS Feed Image Source - Thin facade for backward compatibility.

The real implementation lives in ``sources/rss/`` (cache, parser, downloader,
coordinator, health, constants).  This file re-exports the public symbols that
other modules historically imported from ``sources.rss_source`` so nothing
breaks during the migration.

Backup of the original monolith: ``bak/rss_source_pre_overhaul.py``
"""
from pathlib import Path
from typing import List, Optional, Callable

from sources.base_provider import ImageProvider, ImageMetadata
from sources.rss.constants import (
    DEFAULT_RSS_FEEDS,  # noqa: F401 - re-exported
    SOURCE_PRIORITY,  # noqa: F401 - re-exported
    get_source_priority as _get_source_priority,  # noqa: F401 - re-exported
    MAX_CACHED_IMAGES_TO_LOAD,  # noqa: F401 - re-exported
    MAX_CONSECUTIVE_FAILURES,  # noqa: F401 - re-exported
    FAILURE_BACKOFF_BASE_SECONDS,  # noqa: F401 - re-exported
    FEED_HEALTH_RESET_HOURS,  # noqa: F401 - re-exported
    MAX_REDDIT_FEEDS_PER_STARTUP,  # noqa: F401 - re-exported
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_MAX_CACHE_SIZE_MB,
    DOMAIN_RATE_LIMIT_PER_MINUTE,  # noqa: F401 - re-exported
    DOMAIN_RATE_LIMIT_WINDOW,  # noqa: F401 - re-exported
)
from sources.rss.coordinator import RSSCoordinator
from core.logging.logger import get_logger

logger = get_logger(__name__)

# Legacy constant aliases
RATE_LIMIT_DELAY_SECONDS = 8.0
RATE_LIMIT_RETRY_DELAY_SECONDS = 120
MIN_CACHE_SIZE_BEFORE_CLEANUP = 20


class RSSSource(ImageProvider):
    """Thin facade around RSSCoordinator for backward compatibility.

    New code should use ``sources.rss.coordinator.RSSCoordinator`` directly.
    """

    def __init__(
        self,
        feed_urls: Optional[List[str]] = None,
        cache_dir: Optional[Path] = None,
        max_cache_size_mb: int = DEFAULT_MAX_CACHE_SIZE_MB,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        save_to_disk: bool = False,
        save_directory: Optional[Path] = None,
        max_images_per_refresh: Optional[int] = None,
    ):
        self.feed_urls = feed_urls or list(DEFAULT_RSS_FEEDS.values())
        self.max_images_per_refresh = max_images_per_refresh

        self._coordinator = RSSCoordinator(
            feed_urls=self.feed_urls,
            cache_dir=cache_dir,
            max_cache_size_mb=max_cache_size_mb,
            timeout=timeout_seconds,
            save_to_disk=save_to_disk,
            save_directory=save_directory,
        )

        # Expose for legacy callers that peek at internals
        self._images = self._coordinator.get_cached_images()
        self.cache_dir = self._coordinator.cache_dir

        logger.info(f"RSSSource facade: {len(self.feed_urls)} feeds, {len(self._images)} cached")

    # ------------------------------------------------------------------
    # ImageProvider interface
    # ------------------------------------------------------------------

    def get_images(self) -> List[ImageMetadata]:
        self._images = self._coordinator.get_all_images()
        return list(self._images)

    def refresh(self, max_images_per_source: int = 10) -> bool:
        if max_images_per_source <= 0:
            logger.info("[RSS] No downloads needed, skipping refresh")
            return True
        new = self._coordinator.load_sync()
        self._images = self._coordinator.get_all_images()
        return len(new) > 0

    def is_available(self) -> bool:
        return len(self.feed_urls) > 0

    # ------------------------------------------------------------------
    # Delegation helpers
    # ------------------------------------------------------------------

    def set_shutdown_check(self, callback: Callable[[], bool]) -> None:
        self._coordinator.set_shutdown_check(callback)

    def refresh_single_feed(self, feed_url: str) -> int:
        new = self._coordinator.refresh_single_feed(feed_url)
        self._images = self._coordinator.get_all_images()
        return len(new)

    def get_feed_health_status(self) -> dict:
        return self._coordinator.get_feed_health()

    def get_source_info(self) -> dict:
        return {
            "type": "RSS Feed",
            "feeds": len(self.feed_urls),
            "cached_images": len(self._images),
            "cache_directory": str(self.cache_dir),
        }

    def add_feed(self, feed_url: str) -> None:
        if feed_url not in self.feed_urls:
            self.feed_urls.append(feed_url)

    def remove_feed(self, feed_url: str) -> bool:
        if feed_url in self.feed_urls:
            self.feed_urls.remove(feed_url)
            return True
        return False

    def clear_cache(self) -> int:
        return self._coordinator._cache.clear_all()
