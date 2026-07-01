"""Centralized Reddit API rate limiter.

Reddit's anonymous API has a rate limit of ~10 requests per minute per IP.
This module coordinates all Reddit API calls across the application to stay
under this limit.

Usage:
    from core.reddit_rate_limiter import RedditRateLimiter, RateLimitPriority
    
    # Before making a Reddit API call (widget - high priority):
    wait_time = RedditRateLimiter.wait_if_needed(priority=RateLimitPriority.HIGH)
    if wait_time > 0:
        time.sleep(wait_time)
    RedditRateLimiter.record_request(namespace="widget")
    
    # RSS source (normal priority):
    wait_time = RedditRateLimiter.wait_if_needed(priority=RateLimitPriority.NORMAL)
    if wait_time > 0:
        time.sleep(wait_time)
    RedditRateLimiter.record_request(namespace="rss")
    
    # Widget reservation (prevents RSS from consuming quota):
    RedditRateLimiter.reserve_quota(count=2, namespace="widget")  # Reserve 2 requests
    # ... do widget fetches ...
    RedditRateLimiter.release_quota(count=2, namespace="widget")  # Release unused
    
    # RSS checks if it should skip Reddit:
    if not RedditRateLimiter.should_skip_for_quota(priority=RateLimitPriority.NORMAL):
        # Safe to fetch
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
import hashlib
from typing import List

from core.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class RedditRequestPersona:
    """Stable request persona for Reddit public-endpoint scraping."""

    key: str
    label: str
    user_agent: str
    headers: dict[str, str]


REDDIT_REQUEST_PERSONAS: tuple[RedditRequestPersona, ...] = (
    RedditRequestPersona(
        key="pulse_reader_win",
        label="PulseReader Desktop",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36 PulseReaderDesktop/6.4"
        ),
        headers={
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.reddit.com/",
            "DNT": "1",
            "X-SRPSS-Reddit-Client": "pulse-reader-desktop",
        },
    ),
    RedditRequestPersona(
        key="threaddeck_win",
        label="ThreadDeck Desktop",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Edg/136.0.0.0 Safari/537.36 ThreadDeckDesktop/3.9"
        ),
        headers={
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-GB,en;q=0.9",
            "Referer": "https://www.reddit.com/",
            "DNT": "1",
            "X-SRPSS-Reddit-Client": "threaddeck-desktop",
        },
    ),
    RedditRequestPersona(
        key="orbitfeed_mac",
        label="OrbitFeed Desktop",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36 OrbitFeedDesktop/5.2"
        ),
        headers={
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.8",
            "Referer": "https://www.reddit.com/",
            "DNT": "1",
            "X-SRPSS-Reddit-Client": "orbitfeed-desktop",
        },
    ),
    RedditRequestPersona(
        key="lumenrelay_win",
        label="LumenRelay Desktop",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) "
            "Gecko/20100101 Firefox/136.0 LumenRelayDesktop/4.7"
        ),
        headers={
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.reddit.com/",
            "DNT": "1",
            "X-SRPSS-Reddit-Client": "lumenrelay-desktop",
        },
    ),
)
REDDIT_PERSONA_ROTATION_WINDOW_SECONDS = 6 * 60 * 60


def get_reddit_request_persona(stable_key: str) -> RedditRequestPersona:
    """Return a stable Reddit request persona for a widget/cache/session key."""

    normalized_key = str(stable_key or "reddit")
    window_bucket = int(time.time() // REDDIT_PERSONA_ROTATION_WINDOW_SECONDS)
    digest = hashlib.sha256(f"{normalized_key}|{window_bucket}".encode("utf-8")).digest()
    index = int.from_bytes(digest[:4], "big") % len(REDDIT_REQUEST_PERSONAS)
    return REDDIT_REQUEST_PERSONAS[index]


class RateLimitPriority(Enum):
    """Priority levels for rate limit requests."""
    NORMAL = "normal"  # Standard behavior (RSS, wallpapers)
    HIGH = "high"      # Prioritized (widgets, user-facing content)


class RedditRateLimiter:
    """Thread-safe singleton rate limiter for Reddit API requests.
    
    Reddit's unauthenticated API limit is 10 requests per minute per IP.
    We enforce 8 requests per minute (-2 safety margin) with 8s minimum interval.
    This ensures we stay well under the limit even with multiple concurrent sources.
    
    Quota tracking is namespaced to distinguish between RSS source and Reddit widget.
    """
    
    _lock = threading.Lock()
    _request_times: List[float] = []
    # Namespace tracking: {namespace: [timestamps]}
    _namespace_requests: dict = {}
    # Quota reservations: {namespace: count} - reserved for high-priority use
    _reserved_quota: dict = {}
    
    # Conservative limit: 8 requests per minute (Reddit allows 10 unauthenticated)
    # This is -2 from the actual limit for safety margin
    MAX_REQUESTS_PER_MINUTE = 8
    WINDOW_SECONDS = 60.0
    
    # Safety threshold - back off RSS when we hit this many requests
    SAFETY_THRESHOLD = 6  # Back off RSS when 6/8 requests used
    
    # Minimum delay between consecutive requests (seconds)
    # 8 seconds = 7.5 req/min theoretical max, staying under our 8 req/min limit
    MIN_REQUEST_INTERVAL = 8.0
    # Public-endpoint blocks are terminal chain cooldowns for widgets. Fifteen
    # minutes is intentionally sparse without making manual recovery useless.
    BLOCK_COOLDOWN_SECONDS = 15.0 * 60.0

    _last_request_time: float = 0.0
    _last_blocked_time: float = 0.0

    @classmethod
    def _prune_window_locked(cls, now: float) -> None:
        cls._request_times = [t for t in cls._request_times if now - t < cls.WINDOW_SECONDS]

    @classmethod
    def _record_request_locked(cls, now: float, namespace: str) -> None:
        cls._request_times.append(now)
        cls._last_request_time = now
        cls._prune_window_locked(now)
        if namespace not in cls._namespace_requests:
            cls._namespace_requests[namespace] = []
        cls._namespace_requests[namespace].append(now)
        cls._namespace_requests[namespace] = [
            t for t in cls._namespace_requests[namespace] if now - t < cls.WINDOW_SECONDS
        ]

    @classmethod
    def _compute_wait_locked(
        cls,
        now: float,
        priority: RateLimitPriority,
        *,
        min_interval_override: float | None = None,
        ignore_blocked_cooldown: bool = False,
    ) -> tuple[float, float, float, float]:
        if min_interval_override is not None:
            min_interval = max(0.0, float(min_interval_override))
        else:
            min_interval = 5.0 if priority == RateLimitPriority.HIGH else cls.MIN_REQUEST_INTERVAL

        time_since_last = now - cls._last_request_time
        if time_since_last < min_interval:
            interval_wait = min_interval - time_since_last
        else:
            interval_wait = 0.0

        cls._prune_window_locked(now)

        if len(cls._request_times) >= cls.MAX_REQUESTS_PER_MINUTE:
            oldest = min(cls._request_times)
            window_wait = cls.WINDOW_SECONDS - (now - oldest) + 1.0
            window_wait = max(0.0, window_wait)
            if priority == RateLimitPriority.HIGH:
                window_wait = window_wait * 0.5
        else:
            window_wait = 0.0

        blocked_wait = 0.0
        if not ignore_blocked_cooldown and cls._last_blocked_time > 0.0:
            blocked_wait = max(0.0, cls.BLOCK_COOLDOWN_SECONDS - (now - cls._last_blocked_time))

        total_wait = max(interval_wait, window_wait, blocked_wait)
        return total_wait, interval_wait, window_wait, blocked_wait
    
    @classmethod
    def can_make_request(cls) -> bool:
        """Check if a request can be made without exceeding rate limit.
        
        Returns:
            True if request can proceed, False if rate limit would be exceeded.
        """
        with cls._lock:
            now = time.time()
            # Remove requests older than the window
            cls._request_times = [t for t in cls._request_times if now - t < cls.WINDOW_SECONDS]
            return len(cls._request_times) < cls.MAX_REQUESTS_PER_MINUTE
    
    @classmethod
    def record_request(cls, namespace: str = "global") -> None:
        """Record that a Reddit API request was made.
        
        Args:
            namespace: Source of the request (e.g., 'rss', 'widget') for quota attribution.
        """
        with cls._lock:
            now = time.time()
            cls._record_request_locked(now, namespace)
            logger.debug("[RATE_LIMIT] Reddit request recorded (ns=%s), %d requests in last minute (global), %d (ns)", 
                        namespace, len(cls._request_times), len(cls._namespace_requests[namespace]))
    
    @classmethod
    def wait_if_needed(cls, priority: RateLimitPriority = RateLimitPriority.NORMAL) -> float:
        """Calculate and return wait time needed before next request.
        
        This method does NOT sleep - caller must handle the wait.
        
        Args:
            priority: Request priority - HIGH priority gets shorter waits
            
        Returns:
            Wait time in seconds (0 if no wait needed).
        """
        with cls._lock:
            now = time.time()
            total_wait, interval_wait, window_wait, blocked_wait = cls._compute_wait_locked(
                now,
                priority,
            )
            
            if total_wait > 0:
                logger.debug("[RATE_LIMIT] Reddit rate limit (%s): wait %.1fs (interval=%.1fs, window=%.1fs, blocked=%.1fs, requests=%d/%d)",
                            priority.value, total_wait, interval_wait, window_wait, blocked_wait,
                            len(cls._request_times), cls.MAX_REQUESTS_PER_MINUTE)
            
            return total_wait

    @classmethod
    def acquire_request_slot(
        cls,
        *,
        priority: RateLimitPriority = RateLimitPriority.NORMAL,
        namespace: str = "global",
        shutdown_event=None,
        skip_if_blocked: bool = False,
        min_interval_override: float | None = None,
        ignore_blocked_cooldown: bool = False,
    ) -> str:
        """Atomically wait for and record a Reddit request slot.

        Returns one of:
        - ``"acquired"`` when the slot was recorded and the caller may issue the request
        - ``"blocked"`` when blocked cooldown is active and ``skip_if_blocked`` asked for an immediate skip
        - ``"shutdown"`` when the provided shutdown event fired during the wait
        """

        while True:
            with cls._lock:
                now = time.time()
                total_wait, interval_wait, window_wait, blocked_wait = cls._compute_wait_locked(
                    now,
                    priority,
                    min_interval_override=min_interval_override,
                    ignore_blocked_cooldown=ignore_blocked_cooldown,
                )
                if skip_if_blocked and blocked_wait > 0.0:
                    logger.warning(
                        "[RATE_LIMIT] Reddit request slot skipped during blocked cooldown (ns=%s remaining=%.1fs)",
                        namespace,
                        blocked_wait,
                    )
                    return "blocked"
                if total_wait <= 0.0:
                    cls._record_request_locked(now, namespace)
                    logger.debug(
                        "[RATE_LIMIT] Reddit request slot acquired (ns=%s priority=%s requests=%d/%d)",
                        namespace,
                        priority.value,
                        len(cls._request_times),
                        cls.MAX_REQUESTS_PER_MINUTE,
                    )
                    return "acquired"
                logger.debug(
                    "[RATE_LIMIT] Reddit request slot waiting %.1fs (ns=%s priority=%s interval=%.1fs window=%.1fs blocked=%.1fs requests=%d/%d)",
                    total_wait,
                    namespace,
                    priority.value,
                    interval_wait,
                    window_wait,
                    blocked_wait,
                    len(cls._request_times),
                    cls.MAX_REQUESTS_PER_MINUTE,
                )

            if shutdown_event is not None:
                try:
                    if shutdown_event.wait(total_wait):
                        return "shutdown"
                except Exception:
                    time.sleep(total_wait)
            else:
                time.sleep(total_wait)
    
    @classmethod
    def get_request_count(cls) -> int:
        """Get current number of requests in the rate limit window."""
        with cls._lock:
            now = time.time()
            cls._request_times = [t for t in cls._request_times if now - t < cls.WINDOW_SECONDS]
            return len(cls._request_times)

    @classmethod
    def get_blocked_cooldown_remaining(cls) -> float:
        """Return remaining public-endpoint blocked cooldown in seconds."""

        with cls._lock:
            if cls._last_blocked_time <= 0.0:
                return 0.0
            return max(0.0, cls.BLOCK_COOLDOWN_SECONDS - (time.time() - cls._last_blocked_time))

    @classmethod
    def record_blocked_response(cls, *, reason: str | None = None) -> None:
        """Record that Reddit blocked a public-endpoint request and start cooldown."""

        with cls._lock:
            cls._last_blocked_time = time.time()
            logger.warning(
                "[RATE_LIMIT] Reddit public endpoint blocked; cooldown started for %.0fs%s",
                cls.BLOCK_COOLDOWN_SECONDS,
                f" ({reason})" if reason else "",
            )
    
    @classmethod
    def get_namespace_count(cls, namespace: str) -> int:
        """Get current number of requests in the rate limit window for a namespace."""
        with cls._lock:
            now = time.time()
            if namespace not in cls._namespace_requests:
                return 0
            cls._namespace_requests[namespace] = [t for t in cls._namespace_requests[namespace] if now - t < cls.WINDOW_SECONDS]
            return len(cls._namespace_requests[namespace])
    
    @classmethod
    def reserve_quota(cls, count: int, namespace: str = "widget") -> bool:
        """Reserve quota for high-priority use (widgets).
        
        This prevents RSS from consuming requests when widgets need them.
        
        Args:
            count: Number of requests to reserve
            namespace: Namespace reserving the quota
            
        Returns:
            True if reservation successful, False if not enough quota available
        """
        with cls._lock:
            now = time.time()
            cls._request_times = [t for t in cls._request_times if now - t < cls.WINDOW_SECONDS]
            
            current_count = len(cls._request_times)
            reserved_total = sum(cls._reserved_quota.values())
            available = cls.MAX_REQUESTS_PER_MINUTE - current_count - reserved_total
            
            if count <= available:
                cls._reserved_quota[namespace] = cls._reserved_quota.get(namespace, 0) + count
                logger.debug("[RATE_LIMIT] Reserved %d quota for %s (available: %d, total reserved: %d)",
                           count, namespace, available - count, reserved_total + count)
                return True
            else:
                logger.debug("[RATE_LIMIT] Failed to reserve %d quota for %s (only %d available)",
                           count, namespace, available)
                return False
    
    @classmethod
    def release_quota(cls, count: int, namespace: str = "widget") -> None:
        """Release previously reserved quota.
        
        Args:
            count: Number of requests to release
            namespace: Namespace that reserved the quota
        """
        with cls._lock:
            current = cls._reserved_quota.get(namespace, 0)
            new_count = max(0, current - count)
            if new_count == 0:
                cls._reserved_quota.pop(namespace, None)
            else:
                cls._reserved_quota[namespace] = new_count
            logger.debug("[RATE_LIMIT] Released %d quota for %s (remaining reserved: %d)",
                       count, namespace, new_count)
    
    @classmethod
    def should_skip_for_quota(cls, priority: RateLimitPriority = RateLimitPriority.NORMAL) -> bool:
        """Check if RSS should skip Reddit fetches to preserve quota for widgets.
        
        Returns True if RSS should skip to preserve quota for high-priority use.
        
        Args:
            priority: Priority of the request
            
        Returns:
            True if should skip, False if safe to proceed
        """
        with cls._lock:
            now = time.time()
            cls._request_times = [t for t in cls._request_times if now - t < cls.WINDOW_SECONDS]
            
            current_count = len(cls._request_times)
            reserved_total = sum(cls._reserved_quota.values())
            
            # HIGH priority never skips
            if priority == RateLimitPriority.HIGH:
                return False
            
            # If we've hit the safety threshold, skip RSS
            if current_count >= cls.SAFETY_THRESHOLD:
                logger.debug("[RATE_LIMIT] RSS skipping Reddit: %d/%d requests used (safety threshold: %d)",
                           current_count, cls.MAX_REQUESTS_PER_MINUTE, cls.SAFETY_THRESHOLD)
                return True
            
            # If there's reserved quota that would push us over, skip
            if current_count + 1 + reserved_total > cls.MAX_REQUESTS_PER_MINUTE:
                logger.debug("[RATE_LIMIT] RSS skipping Reddit: reserved quota would exceed limit (%d used + %d reserved)",
                           current_count, reserved_total)
                return True
            
            return False
    
    @classmethod
    def reset(cls) -> None:
        """Reset the rate limiter (for testing)."""
        with cls._lock:
            cls._request_times = []
            cls._last_request_time = 0.0
            cls._last_blocked_time = 0.0
            cls._namespace_requests = {}
            cls._reserved_quota = {}
        global _user_agent_index
        _user_agent_index = 0
