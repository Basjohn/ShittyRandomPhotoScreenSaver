"""
RSSDownloader - Shutdown-aware network I/O with domain rate limiting.

Responsibilities:
    - Fetch RSS feeds (via feedparser) and JSON feeds (via requests)
    - Download individual images with atomic write (temp → rename)
    - Domain-based rate limiting (shared state per instance, sequential processing)
    - Shutdown checks before and during every network call
    - No time.sleep() - returns wait times for coordinator to handle
    - Reddit rate limiter coordination for Reddit feeds
"""
import os
import time
import hashlib
import shutil
import threading
import requests
import feedparser
from pathlib import Path
from typing import Optional, Callable
from urllib.parse import urlparse

from sources.rss.constants import (
    DOMAIN_RATE_LIMIT_PER_MINUTE,
    DOMAIN_RATE_LIMIT_WINDOW,
    DEFAULT_TIMEOUT_SECONDS,
)
from core.logging.logger import get_logger

logger = get_logger(__name__)


class RSSDownloader:
    """Handles all network I/O for the RSS system.

    Designed for sequential, single-threaded use on an IO pool thread.
    No locks needed - only one feed is processed at a time.
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        shutdown_check: Optional[Callable[[], bool]] = None,
    ):
        self.timeout = timeout
        self._shutdown_check = shutdown_check
        self._stop_event = threading.Event()
        # Domain rate limiting: {domain: [timestamp, ...]}
        self._domain_requests: dict = {}

    # ------------------------------------------------------------------
    # Shutdown awareness
    # ------------------------------------------------------------------

    def _should_continue(self) -> bool:
        if self._shutdown_check is not None:
            return self._shutdown_check()
        return True

    def set_shutdown_check(self, cb: Optional[Callable[[], bool]]) -> None:
        self._shutdown_check = cb

    def request_stop(self) -> None:
        """Signal the stop event so any interruptible wait wakes immediately."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Domain rate limiting
    # ------------------------------------------------------------------

    def domain_wait_time(self, url: str) -> float:
        """Return seconds to wait before making a request to this domain.

        Returns 0.0 if safe to proceed immediately.
        """
        domain = self._get_domain(url)
        now = time.time()

        if domain in self._domain_requests:
            self._domain_requests[domain] = [
                t for t in self._domain_requests[domain]
                if now - t < DOMAIN_RATE_LIMIT_WINDOW
            ]
        else:
            self._domain_requests[domain] = []

        count = len(self._domain_requests[domain])
        if count >= DOMAIN_RATE_LIMIT_PER_MINUTE:
            oldest = min(self._domain_requests[domain])
            return max(0.0, DOMAIN_RATE_LIMIT_WINDOW - (now - oldest) + 1.0)

        return 0.0

    def _record_domain_request(self, url: str) -> None:
        domain = self._get_domain(url)
        self._domain_requests.setdefault(domain, []).append(time.time())

    @staticmethod
    def _get_domain(url: str) -> str:
        try:
            netloc = urlparse(url).netloc.lower()
            return netloc[4:] if netloc.startswith("www.") else netloc
        except Exception:
            return url.lower()

    # ------------------------------------------------------------------
    # User agent
    # ------------------------------------------------------------------

    @staticmethod
    def _user_agent() -> str:
        try:
            from core.reddit_rate_limiter import get_reddit_user_agent
            return get_reddit_user_agent()
        except ImportError:
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    # ------------------------------------------------------------------
    # Feed fetching
    # ------------------------------------------------------------------

    def fetch_rss(self, url: str):
        """Fetch and parse an RSS/Atom feed via feedparser.

        Returns the feedparser result or None on failure / shutdown.
        """
        if not self._should_continue():
            return None

        wait = self.domain_wait_time(url)
        if wait > 0:
            logger.info(f"[RSS_DL] Domain rate limit: waiting {wait:.1f}s for {self._get_domain(url)}")
            if not self._interruptible_wait(wait):
                return None

        if not self._should_continue():
            return None

        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": self._user_agent()})
            self._record_domain_request(url)
            return feed
        except Exception as e:
            logger.error(f"[RSS_DL] Failed to fetch RSS {url}: {e}")
            return None

    def fetch_json(self, url: str) -> Optional[dict]:
        """Fetch a JSON feed (Flickr or Reddit).

        For Reddit URLs, coordinates with RedditRateLimiter.
        Returns parsed JSON dict or None on failure / shutdown.
        """
        if not self._should_continue():
            return None

        is_reddit = "reddit.com" in url.lower()

        # Reddit quota check
        if is_reddit:
            try:
                from core.reddit_rate_limiter import RedditRateLimiter, RateLimitPriority
                if RedditRateLimiter.should_skip_for_quota(priority=RateLimitPriority.NORMAL):
                    logger.info("[RSS_DL] Skipping Reddit fetch to preserve widget quota")
                    return None
            except ImportError:
                pass

        # Domain rate limit
        wait = self.domain_wait_time(url)
        if wait > 0:
            logger.info(f"[RSS_DL] Domain rate limit: waiting {wait:.1f}s for {self._get_domain(url)}")
            if not self._interruptible_wait(wait):
                return None

        # Reddit-specific rate limiter
        if is_reddit:
            try:
                from core.reddit_rate_limiter import RedditRateLimiter, RateLimitPriority
                rw = RedditRateLimiter.wait_if_needed(priority=RateLimitPriority.NORMAL)
                if rw > 0:
                    logger.info(f"[RSS_DL] Reddit rate limit: waiting {rw:.1f}s")
                    if not self._interruptible_wait(rw):
                        return None
                RedditRateLimiter.record_request(namespace="rss")
            except ImportError:
                pass

        if not self._should_continue():
            return None

        try:
            resp = requests.get(
                url,
                timeout=self.timeout,
                headers={"User-Agent": self._user_agent(), "Accept": "application/json"},
            )
            resp.raise_for_status()
            self._record_domain_request(url)
            return resp.json()
        except Exception as e:
            logger.error(f"[RSS_DL] Failed to fetch JSON {url}: {e}")
            return None

    # ------------------------------------------------------------------
    # Image downloading
    # ------------------------------------------------------------------

    def download_image(self, image_url: str, cache_dir: Path) -> Optional[Path]:
        """Download an image to cache with atomic write.

        Returns the cache Path on success, or the existing path if already cached.
        Returns None on failure or shutdown.
        """
        if not self._should_continue():
            return None

        url_hash = hashlib.md5(image_url.encode()).hexdigest()
        parsed = urlparse(image_url)
        ext = Path(parsed.path).suffix or ".jpg"
        cache_file = cache_dir / f"{url_hash}{ext}"
        temp_file = cache_dir / f".tmp.{url_hash}{ext}"

        # Already cached
        if cache_file.exists():
            return cache_file

        try:
            resp = requests.get(
                image_url,
                timeout=self.timeout,
                headers={"User-Agent": self._user_agent()},
                stream=True,
            )
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type:
                logger.debug(f"[RSS_DL] Not an image: {content_type} for {image_url}")
                return None

            downloaded = 0
            with open(temp_file, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if not self._should_continue():
                        logger.info("[RSS_DL] Shutdown during download, aborting")
                        f.close()
                        self._safe_unlink(temp_file)
                        return None
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

            # Atomic replace with retry for Windows WinError 32 (handle held
            # briefly by antivirus / filesystem journal after close).
            renamed = False
            for attempt in range(4):
                # Re-check: another thread may have finished the same download
                if cache_file.exists():
                    self._safe_unlink(temp_file)
                    return cache_file
                try:
                    os.replace(str(temp_file), str(cache_file))
                    renamed = True
                    break
                except OSError:
                    if attempt < 3:
                        time.sleep(0.05 * (attempt + 1))
            if not renamed:
                logger.warning("[RSS_DL] Rename failed after retries: %s -> %s", temp_file.name, cache_file.name)
                self._safe_unlink(temp_file)
                # Final race check — file may now exist from another thread
                if cache_file.exists():
                    return cache_file
                return None

            logger.debug(f"[RSS_DL] Downloaded {cache_file.name} ({downloaded} bytes)")
            return cache_file

        except Exception as e:
            logger.warning(f"[RSS_DL] Download failed for {image_url}: {e}")
            self._safe_unlink(temp_file)
            return None

    def download_image_to_save_dir(self, cache_path: Path, save_dir: Path) -> None:
        """Copy a cached image to permanent storage."""
        try:
            dest = save_dir / cache_path.name
            if not dest.exists():
                shutil.copy2(cache_path, dest)
        except Exception as e:
            logger.warning(f"[RSS_DL] Save-to-disk failed: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _interruptible_wait(self, seconds: float) -> bool:
        """Wait up to *seconds*, waking instantly on shutdown.

        Uses threading.Event.wait() instead of time.sleep() so the IO
        pool thread unblocks the moment ``request_stop()`` is called.
        Returns True if the wait completed, False if shutdown was requested.
        """
        if self._stop_event.wait(timeout=seconds):
            return False  # stop was requested
        return self._should_continue()

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
