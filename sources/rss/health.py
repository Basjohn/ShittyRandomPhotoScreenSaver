"""
Feed health tracking with persistent storage.

Responsibilities:
    - Track consecutive failures per feed URL
    - Exponential backoff for unhealthy feeds
    - Persist health data across restarts (JSON in temp dir)
    - Auto-reset after FEED_HEALTH_RESET_HOURS
"""
import json
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional

from sources.rss.constants import (
    MAX_CONSECUTIVE_FAILURES,
    FAILURE_BACKOFF_BASE_SECONDS,
    FEED_HEALTH_RESET_HOURS,
)
from core.logging.logger import get_logger

logger = get_logger(__name__)

_HEALTH_FILE = Path(tempfile.gettempdir()) / "srpss_feed_health.json"


class FeedHealthTracker:
    """Tracks feed health with exponential backoff and persistent storage."""

    def __init__(self, health_file: Optional[Path] = None):
        self._file = health_file or _HEALTH_FILE
        self._health: Dict[str, dict] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_skip(self, feed_url: str) -> bool:
        """Return True if this feed should be skipped due to backoff."""
        if feed_url not in self._health:
            return False

        h = self._health[feed_url]
        now = time.time()

        # Reset after FEED_HEALTH_RESET_HOURS
        last_fail = h.get("last_failure", 0)
        if now - last_fail > FEED_HEALTH_RESET_HOURS * 3600:
            self._health.pop(feed_url, None)
            self._save()
            return False

        if h.get("failures", 0) >= MAX_CONSECUTIVE_FAILURES:
            skip_until = h.get("skip_until", 0)
            if now < skip_until:
                return True
            # Backoff period elapsed, allow retry
            return False

        return False

    def record_success(self, feed_url: str) -> None:
        """Reset failure count for a feed."""
        if feed_url in self._health:
            del self._health[feed_url]
            self._save()

    def record_failure(self, feed_url: str) -> None:
        """Increment failure count and calculate next skip_until."""
        now = time.time()
        if feed_url not in self._health:
            self._health[feed_url] = {"failures": 0, "last_failure": 0, "skip_until": 0}

        h = self._health[feed_url]
        h["failures"] = h.get("failures", 0) + 1
        h["last_failure"] = now
        # Exponential backoff: 60, 120, 240, 480, ...
        backoff = FAILURE_BACKOFF_BASE_SECONDS * (2 ** (h["failures"] - 1))
        h["skip_until"] = now + backoff
        logger.info(f"[FEED_HEALTH] {feed_url}: failure #{h['failures']}, backoff {backoff}s")
        self._save()

    def get_status(self, feed_urls: list) -> Dict[str, dict]:
        """Return health status for a list of feed URLs."""
        now = time.time()
        result = {}
        for url in feed_urls:
            if url in self._health:
                h = self._health[url]
                result[url] = {
                    "healthy": h.get("failures", 0) < MAX_CONSECUTIVE_FAILURES,
                    "failures": h.get("failures", 0),
                    "skip_until": h.get("skip_until", 0),
                    "skipped": now < h.get("skip_until", 0),
                }
            else:
                result[url] = {"healthy": True, "failures": 0, "skip_until": 0, "skipped": False}
        return result

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        try:
            if self._file.exists():
                with open(self._file, "r") as f:
                    self._health = json.load(f)
                logger.debug(f"[FEED_HEALTH] Loaded health for {len(self._health)} feeds")
        except Exception as e:
            logger.debug(f"[FEED_HEALTH] Load failed: {e}")
            self._health = {}

    def _save(self) -> None:
        try:
            with open(self._file, "w") as f:
                json.dump(self._health, f)
        except Exception as e:
            logger.debug(f"[FEED_HEALTH] Save failed: {e}")
