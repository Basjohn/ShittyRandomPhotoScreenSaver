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
from enum import Enum
from typing import List

from core.logging.logger import get_logger

logger = get_logger(__name__)


# User-Agent rotation for scraping Reddit public JSON endpoints
# Reddit aggressively rate-limits based on User-Agent
REDDIT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Brave/120.0.0.0 Chrome/120.0.0.0 Safari/537.36",
]


def get_reddit_user_agent() -> str:
    """Get a User-Agent string for Reddit scraping.
    
    Returns a rotating browser User-Agent to avoid rate limiting
    based on User-Agent fingerprinting.
    
    Returns:
        User-Agent string suitable for Reddit requests.
    """
    import random
    return random.choice(REDDIT_USER_AGENTS)


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
    
    _last_request_time: float = 0.0
    
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
            cls._request_times.append(now)
            cls._last_request_time = now
            # Cleanup old entries
            cls._request_times = [t for t in cls._request_times if now - t < cls.WINDOW_SECONDS]
            # Track by namespace
            if namespace not in cls._namespace_requests:
                cls._namespace_requests[namespace] = []
            cls._namespace_requests[namespace].append(now)
            cls._namespace_requests[namespace] = [t for t in cls._namespace_requests[namespace] if now - t < cls.WINDOW_SECONDS]
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
            
            # Adjust minimum interval based on priority
            # HIGH: 5s (allows faster widget updates)
            # NORMAL: 8s (standard for RSS/wallpapers)
            min_interval = 5.0 if priority == RateLimitPriority.HIGH else cls.MIN_REQUEST_INTERVAL
            
            # First check: minimum interval between requests
            time_since_last = now - cls._last_request_time
            if time_since_last < min_interval:
                interval_wait = min_interval - time_since_last
            else:
                interval_wait = 0.0
            
            # Second check: rate limit window
            cls._request_times = [t for t in cls._request_times if now - t < cls.WINDOW_SECONDS]
            
            if len(cls._request_times) >= cls.MAX_REQUESTS_PER_MINUTE:
                # Need to wait until oldest request expires from window
                oldest = min(cls._request_times)
                window_wait = cls.WINDOW_SECONDS - (now - oldest) + 1.0  # +1s buffer
                window_wait = max(0.0, window_wait)
                # HIGH priority can reduce window wait by up to 50%
                if priority == RateLimitPriority.HIGH:
                    window_wait = window_wait * 0.5
            else:
                window_wait = 0.0
            
            total_wait = max(interval_wait, window_wait)
            
            if total_wait > 0:
                logger.debug("[RATE_LIMIT] Reddit rate limit (%s): wait %.1fs (interval=%.1fs, window=%.1fs, requests=%d/%d)",
                            priority.value, total_wait, interval_wait, window_wait, 
                            len(cls._request_times), cls.MAX_REQUESTS_PER_MINUTE)
            
            return total_wait
    
    @classmethod
    def get_request_count(cls) -> int:
        """Get current number of requests in the rate limit window."""
        with cls._lock:
            now = time.time()
            cls._request_times = [t for t in cls._request_times if now - t < cls.WINDOW_SECONDS]
            return len(cls._request_times)
    
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
            cls._namespace_requests = {}
            cls._reserved_quota = {}
