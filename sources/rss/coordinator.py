"""RSSCoordinator - the wallpaper-feed pool owner: acquisition and session rotation.

Wallpaper feeds are a separate product from the FEEDS widget (an image pool
for wallpaper rotation, not stories), but they acquire through the same feed
core:

- each feed is a ``core.feeds.source.FeedSource``: conditional requests,
  standards-based discovery, persisted backoff for every feed, a last-good
  document, bounded DNS; structured non-feed sources (JSON image listings)
  are read by ``sources.rss.json_listing`` by shape;
- each image is fetched by ``sources.rss.image_fetch`` through the shared
  vetted public-image stream, judged by its real pixels: admitted only when it
  fills every connected display in fill mode without upscaling, and refused
  from its header (a few kilobytes) otherwise. Refusals are remembered.

Session rotation keeps a full pool fresh: once per process session (not per
settings rebuild) up to a third of the pool target is replaced, stale images
(older than ``STALE_AFTER_HOURS``) oldest first. An old image is retired only
after its replacement is on disk, so an offline session never shrinks the
pool; images that cannot fill the current displays are hidden at once. Retired
files are deleted at the next session start.

There is no scheduler, timer or thread here: the engine's existing IO-lane task
and background refresh drive passes, one at a time.
"""
from __future__ import annotations

from enum import Enum, auto
import math
from pathlib import Path
import shutil
import threading
import time
from typing import Callable, Dict, Iterator, List, Optional, Tuple
from urllib.parse import urlparse

from core.constants import MIN_WALLPAPER_HEIGHT, MIN_WALLPAPER_WIDTH
from core.feeds.cache import FeedCacheStore
from core.feeds.models import FeedDocument, FeedImageCandidate, FeedItem, FeedSourceSpec
from core.feeds.normalization import endpoint_fingerprint, redacted_url_for_log
from core.feeds.transport import normalize_feed_address
from core.logging.logger import get_logger
from sources.base_provider import ImageMetadata
from sources.rss.cache import PoolEntry, RSSCache, url_key
from sources.rss.constants import (
    DEFAULT_MAX_CACHE_SIZE_MB,
    DEFAULT_RSS_FEEDS,
    DEFAULT_TIMEOUT_SECONDS,
    FEED_MAX_ITEMS,
    HOST_MIN_INTERVAL_SECONDS,
    MAX_IMAGE_ATTEMPTS_PER_PASS,
    SESSION_REPLACE_FRACTION,
    STALE_AFTER_HOURS,
    TARGET_TOTAL_IMAGES,
)
from sources.rss.image_fetch import fills_displays, image_size_of_file

logger = get_logger(__name__)

_ROTATION_LOCK = threading.Lock()
_ROTATED_THIS_PROCESS: set[str] = set()
_LOADED_THIS_PROCESS: set[str] = set()


def _first_load_this_process(cache_dir: Path) -> bool:
    """True for the first pool load of a process (a new session), False for rebuilds."""
    key = str(Path(cache_dir).resolve())
    with _ROTATION_LOCK:
        if key in _LOADED_THIS_PROCESS:
            return False
        _LOADED_THIS_PROCESS.add(key)
        return True


def _claim_session_rotation(cache_dir: Path) -> bool:
    """True once per process for a pool directory (settings rebuilds reuse the claim)."""
    key = str(Path(cache_dir).resolve())
    with _ROTATION_LOCK:
        if key in _ROTATED_THIS_PROCESS:
            return False
        _ROTATED_THIS_PROCESS.add(key)
        return True


class RSSState(Enum):
    IDLE = auto()
    LOADING = auto()
    LOADED = auto()
    ERROR = auto()


class _PassStopped(Exception):
    """Shutdown or retirement ended a pass early."""


class RSSCoordinator:
    """Owns the wallpaper pool: cache, feed sources, image acquisition, rotation."""

    def __init__(
        self,
        feed_urls: Optional[List[str]] = None,
        cache_dir: Optional[Path] = None,
        max_cache_size_mb: int = DEFAULT_MAX_CACHE_SIZE_MB,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        save_to_disk: bool = False,
        save_directory: Optional[Path] = None,
        target_total_images: int = TARGET_TOTAL_IMAGES,
        thread_manager=None,
        resource_manager=None,
        shutdown_check: Optional[Callable[[], bool]] = None,
        required_size: Optional[Tuple[int, int]] = None,
    ):
        urls = feed_urls if feed_urls is not None else list(DEFAULT_RSS_FEEDS.values())
        self.feed_urls: List[str] = list(dict.fromkeys(
            normalize_feed_address(url) for url in urls if str(url or "").strip()))
        self._state_lock = threading.Lock()
        self._state = RSSState.IDLE
        self._thread_manager = thread_manager
        self._shutdown_check = shutdown_check
        self._timeout = max(5, int(timeout))
        self._target_total_images = max(1, int(target_total_images))
        self._required = self._valid_required(required_size)
        self._save_directory = Path(save_directory) if save_to_disk and save_directory else None
        if self._save_directory is not None:
            try:
                self._save_directory.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.error(f"[RSS_COORD] Failed to create save dir: {e}")
                self._save_directory = None

        self._cache = RSSCache(cache_dir=cache_dir, max_cache_size_mb=max_cache_size_mb,
                               resource_manager=resource_manager)
        self._feed_store: Optional[FeedCacheStore] = None
        self._sources: Dict[str, object] = {}
        self._stop = threading.Event()
        self._pass_lock = threading.Lock()
        self._retired_lock = threading.Lock()
        self._retired_paths: List[str] = []
        self._host_last_request: Dict[str, float] = {}
        self._cache_warmed = False
        logger.info("[RSS_COORD] Initialised: %d feeds, admission >= %dx%d (fill, no upscaling)",
                    len(self.feed_urls), *self._required)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @staticmethod
    def _valid_required(size) -> Tuple[int, int]:
        try:
            width, height = int(size[0]), int(size[1])
        except (TypeError, ValueError, IndexError):
            return MIN_WALLPAPER_WIDTH, MIN_WALLPAPER_HEIGHT
        if width <= 0 or height <= 0:
            return MIN_WALLPAPER_WIDTH, MIN_WALLPAPER_HEIGHT
        return width, height

    @property
    def state(self) -> RSSState:
        with self._state_lock:
            return self._state

    def _set_state(self, state: RSSState) -> None:
        with self._state_lock:
            self._state = state

    @property
    def cache_dir(self) -> Path:
        return self._cache.cache_dir

    @property
    def cached_count(self) -> int:
        return self._cache.count

    @property
    def required_size(self) -> Tuple[int, int]:
        return self._required

    # ------------------------------------------------------------------
    # Public API (engine)
    # ------------------------------------------------------------------

    def warm_cache(self) -> int:
        """Load the pool from disk (cheap: an index read, no image probing). Idempotent."""
        if not self._cache_warmed:
            self._cache.load_from_disk(purge_retired=_first_load_this_process(self._cache.cache_dir))
            self._cache_warmed = True
        return self._cache.count

    def get_cached_images(self) -> List[ImageMetadata]:
        """Pool images that can fill the displays (unmeasured legacy files included)."""
        return [entry.metadata for entry in self._cache.entries if self._admissible(entry)]

    def get_all_images(self) -> List[ImageMetadata]:
        return self.get_cached_images()

    def take_retired_paths(self) -> List[str]:
        """Paths retired since the last call; the engine removes them from its queue."""
        with self._retired_lock:
            paths, self._retired_paths = self._retired_paths, []
        return paths

    def load_async(self, on_images: Optional[Callable[[List[ImageMetadata]], None]] = None) -> None:
        """Session pass on the IO lane: warm, rotate, top up; ``on_images`` gets new images."""
        if self._thread_manager is None:
            new_images = self.load_sync()
            if on_images:
                on_images(new_images)
            return

        def _task():
            new_images = self.load_sync()
            if on_images:
                on_images(new_images)  # always called so the engine can pre-load the pool

        self._thread_manager.submit_io_task(_task, category="rss_startup_load")

    def load_sync(self) -> List[ImageMetadata]:
        self.warm_cache()
        return self._run_pass(self.feed_urls, session=True)

    def refresh_single_feed(self, feed_url: str) -> List[ImageMetadata]:
        """Background top-up from one feed (conditional; no rotation). Returns new images."""
        url = normalize_feed_address(feed_url)
        return self._run_pass([url] if url in self.feed_urls else [], session=False)

    def set_shutdown_check(self, cb: Optional[Callable[[], bool]]) -> None:
        self._shutdown_check = cb

    def request_stop(self) -> None:
        """Abort passes at their next check (interruptible waits wake at once)."""
        self._stop.set()

    # ------------------------------------------------------------------
    # Pass
    # ------------------------------------------------------------------

    def _alive(self) -> bool:
        if self._stop.is_set():
            return False
        return True if self._shutdown_check is None else bool(self._shutdown_check())

    def _admissible(self, entry: PoolEntry) -> bool:
        if entry.width is None or entry.height is None:
            return True
        return fills_displays(entry.width, entry.height, self._required)

    def _run_pass(self, feeds: List[str], *, session: bool) -> List[ImageMetadata]:
        if not self._pass_lock.acquire(blocking=False):
            logger.debug("[RSS_COORD] A pass is already running; skipped")
            return []
        self._set_state(RSSState.LOADING)
        new_images: List[ImageMetadata] = []
        try:
            replace: List[PoolEntry] = []
            if session and _claim_session_rotation(self._cache.cache_dir):
                replace = self._begin_session_rotation()
            missing = max(0, self._target_total_images - self._cache.count)
            wanted = missing + len(replace)
            if wanted and feeds:
                logger.info("[RSS_COORD] Pass: pool=%d target=%d missing=%d replacing=%d feeds=%d",
                            self._cache.count, self._target_total_images, missing, len(replace), len(feeds))
                for entry in self._acquire(feeds, wanted):
                    new_images.append(entry.metadata)
                    if missing > 0:
                        missing -= 1
                    elif replace:
                        self._retire([replace.pop(0)])
            self._cache.cleanup()
            self._set_state(RSSState.LOADED)
        except _PassStopped:
            logger.info("[RSS_COORD] Pass stopped (shutdown/retirement)")
            self._set_state(RSSState.LOADED)
        except Exception:
            logger.exception("[RSS_COORD] Pass failed")
            self._set_state(RSSState.ERROR)
        finally:
            self._cache.save_state()
            self._release_transports()
            self._pass_lock.release()
        if new_images:
            logger.info("[RSS_COORD] Pass complete: %d new images", len(new_images))
        return new_images

    def _begin_session_rotation(self) -> List[PoolEntry]:
        """Measure unmeasured files, hide undersized ones, pick stale ones to replace."""
        for entry in list(self._cache.entries):
            if entry.width is None or entry.height is None:
                measured = image_size_of_file(entry.path)
                if measured is not None:
                    self._cache.record_size(entry, *measured[0])
        undersized = [e for e in self._cache.entries if not self._admissible(e)]
        if undersized:
            logger.info("[RSS_COORD] Hiding %d pool images that cannot fill %dx%d",
                        len(undersized), *self._required)
            self._retire(undersized)
        cutoff = time.time() - STALE_AFTER_HOURS * 3600.0
        stale = sorted((e for e in self._cache.entries if e.fetched_at < cutoff),
                       key=lambda e: e.fetched_at)
        quota = max(1, math.ceil(self._target_total_images / SESSION_REPLACE_FRACTION))
        return stale[:quota]

    def _retire(self, entries: List[PoolEntry]) -> None:
        paths = self._cache.retire(entries)
        if paths:
            with self._retired_lock:
                self._retired_paths.extend(paths)

    # ------------------------------------------------------------------
    # Acquisition
    # ------------------------------------------------------------------

    def _acquire(self, feeds: List[str], wanted: int) -> Iterator[PoolEntry]:
        """New pool entries, taken round-robin across feeds, until ``wanted`` or bounds."""
        streams = []
        for feed_url in feeds:
            if not self._alive():
                raise _PassStopped()
            document = self._document(feed_url)
            if document is not None:
                streams.append((feed_url, iter(document.items)))
        attempts = [0]
        produced = 0
        while streams and produced < wanted:
            for feed_url, items in list(streams):
                item = next(items, None)
                if item is None:
                    streams.remove((feed_url, items))
                    continue
                entry = self._acquire_item(feed_url, item, attempts)
                if entry is not None:
                    produced += 1
                    yield entry
                    if produced >= wanted:
                        return
                if attempts[0] >= MAX_IMAGE_ATTEMPTS_PER_PASS:
                    logger.info("[RSS_COORD] Attempt bound reached (%d)", attempts[0])
                    return

    def _ordered_candidates(self, item: FeedItem) -> List[FeedImageCandidate]:
        """Declared-large first, then unsized; an entry declared too small is skipped whole."""
        declared = [c for c in item.images if c.width and c.height]
        large = sorted((c for c in declared if fills_displays(c.width, c.height, self._required)),
                       key=lambda c: -(c.width * c.height))
        if declared and not large and item.images[0] in declared:
            return []  # its own image is too small; variants (thumbnails) are smaller still
        unsized = [c for c in item.images if not (c.width and c.height)]
        return large + unsized

    def _acquire_item(self, feed_url: str, item: FeedItem, attempts: List[int]) -> Optional[PoolEntry]:
        from core.feeds.artwork import ArtworkCancelled
        from core.feeds.artwork_transport import ArtworkFetchError
        from sources.rss.image_fetch import WallpaperRejected, fetch_wallpaper

        for candidate in self._ordered_candidates(item):
            if self._cache.has_url(candidate.url):
                return None  # this entry is already in the pool
            if self._cache.is_rejected(candidate.url, self._required):
                continue
            if attempts[0] >= MAX_IMAGE_ATTEMPTS_PER_PASS or not self._alive():
                if not self._alive():
                    raise _PassStopped()
                return None
            attempts[0] += 1
            self._pace(candidate.url)
            try:
                result = fetch_wallpaper(candidate.url, self._cache.cache_dir,
                                         file_stem=url_key(candidate.url),
                                         still_needed=self._alive, required=self._required)
            except WallpaperRejected as rejected:
                self._cache.remember_rejected(candidate.url, rejected.size)
                if rejected.size is not None and candidate is item.images[0]:
                    return None  # its own image is too small; variants are smaller still
                continue
            except ArtworkCancelled:
                raise _PassStopped()
            except ArtworkFetchError as exc:
                logger.debug("[RSS_COORD] Image fetch failed %s: %s",
                             redacted_url_for_log(candidate.url), exc)
                continue
            except Exception as exc:  # one odd image never ends the pass
                logger.warning("[RSS_COORD] Image skipped %s: %s",
                               redacted_url_for_log(candidate.url), type(exc).__name__)
                continue
            entry = self._cache.add(result.path, width=result.width, height=result.height,
                                    url=candidate.url, source=feed_url, title=item.title)
            self._save_copy(result.path)
            logger.info("[RSS_COORD] +1 %dx%d from %s", result.width, result.height,
                        redacted_url_for_log(feed_url))
            return entry
        return None

    def _pace(self, url: str) -> None:
        host = (urlparse(url).hostname or "").casefold()
        last = self._host_last_request.get(host)
        if last is not None:
            wait = HOST_MIN_INTERVAL_SECONDS - (time.monotonic() - last)
            if wait > 0 and self._stop.wait(wait):
                raise _PassStopped()
        self._host_last_request[host] = time.monotonic()

    def _save_copy(self, path: Path) -> None:
        if self._save_directory is None:
            return
        try:
            destination = self._save_directory / path.name
            if not destination.exists():
                shutil.copy2(path, destination)
        except OSError as e:
            logger.warning(f"[RSS_COORD] Save-to-disk failed: {e}")

    # ------------------------------------------------------------------
    # Feed documents (shared feed core)
    # ------------------------------------------------------------------

    def _source(self, feed_url: str):
        source = self._sources.get(feed_url)
        if source is None:
            from core.feeds.source import FeedSource
            from core.feeds.transport import FeedHttpTransport
            from sources.rss.image_fetch import WALLPAPER_USER_AGENT
            from sources.rss.json_listing import json_image_listing

            if self._feed_store is None:
                self._feed_store = FeedCacheStore(self._cache.state_dir / "feeds")
            fingerprint = endpoint_fingerprint(feed_url)
            timeout = float(self._timeout)
            source = FeedSource(
                FeedSourceSpec(f"wallpaper:endpoint:{fingerprint}", feed_url,
                               f"wallpaper_endpoint_{fingerprint}", max_items=FEED_MAX_ITEMS),
                transport_factory=lambda: FeedHttpTransport(
                    connect_timeout=min(timeout, 4.0), read_timeout=timeout,
                    user_agent=WALLPAPER_USER_AGENT, should_continue=self._alive),
                cache=self._feed_store,
                should_continue=self._alive,
                document_adapter=json_image_listing,
            )
            self._sources[feed_url] = source
        return source

    def _document(self, feed_url: str) -> Optional[FeedDocument]:
        from core.feeds.source import FeedRefreshCancelled

        if not self._reddit_quota_allows(feed_url):
            return None
        try:
            result = self._source(feed_url).refresh()
        except FeedRefreshCancelled:
            raise _PassStopped()
        except Exception as exc:
            logger.warning("[RSS_COORD] Feed failed %s: %s", redacted_url_for_log(feed_url), type(exc).__name__)
            return None
        if result.status not in {"available", "not_modified"}:
            logger.info("[RSS_COORD] Feed %s: %s (%s)", redacted_url_for_log(feed_url),
                        result.status, result.failure or "-")
        return result.snapshot.document if result.snapshot is not None else None

    @staticmethod
    def _reddit_quota_allows(feed_url: str) -> bool:
        """Reddit feeds share the Reddit widget's strictly enforced request quota."""
        host = (urlparse(feed_url).hostname or "").casefold()
        if host != "reddit.com" and not host.endswith(".reddit.com"):
            return True
        try:
            from core.reddit_rate_limiter import RateLimitPriority, RedditRateLimiter
            if RedditRateLimiter.should_skip_for_quota(priority=RateLimitPriority.NORMAL):
                logger.info("[RSS_COORD] Reddit feed skipped to preserve the Reddit widget's quota")
                return False
            RedditRateLimiter.record_request(namespace="rss")
        except ImportError:
            pass
        return True

    def _release_transports(self) -> None:
        """No HTTP session outlives its pass."""
        for source in self._sources.values():
            transport = getattr(source, "transport", None)
            if transport is not None:
                try:
                    transport.close()
                except Exception:
                    pass
                source.transport = None


__all__ = ["RSSCoordinator", "RSSState"]
