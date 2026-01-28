"""Centralized Reddit API rate limiter.

Reddit's anonymous API has a rate limit of ~10 requests per minute per IP.
This module coordinates all Reddit API calls across the application to stay
under this limit.

Usage:
    from core.reddit_rate_limiter import RedditRateLimiter
    
    # Before making a Reddit API call:
    wait_time = RedditRateLimiter.wait_if_needed()
    if wait_time > 0:
        time.sleep(wait_time)
    RedditRateLimiter.record_request()
    
    # Then make the request...
"""
from __future__ import annotations

import threading
import time
from typing import List

from core.logging.logger import get_logger

logger = get_logger(__name__)


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
    
    # Conservative limit: 8 requests per minute (Reddit allows 10 unauthenticated)
    # This is -2 from the actual limit for safety margin
    MAX_REQUESTS_PER_MINUTE = 8
    WINDOW_SECONDS = 60.0
    
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
    def wait_if_needed(cls) -> float:
        """Calculate and return wait time needed before next request.
        
        This method does NOT sleep - caller must handle the wait.
        
        Returns:
            Wait time in seconds (0 if no wait needed).
        """
        with cls._lock:
            now = time.time()
            
            # First check: minimum interval between requests
            time_since_last = now - cls._last_request_time
            if time_since_last < cls.MIN_REQUEST_INTERVAL:
                interval_wait = cls.MIN_REQUEST_INTERVAL - time_since_last
            else:
                interval_wait = 0.0
            
            # Second check: rate limit window
            cls._request_times = [t for t in cls._request_times if now - t < cls.WINDOW_SECONDS]
            
            if len(cls._request_times) >= cls.MAX_REQUESTS_PER_MINUTE:
                # Need to wait until oldest request expires from window
                oldest = min(cls._request_times)
                window_wait = cls.WINDOW_SECONDS - (now - oldest) + 1.0  # +1s buffer
                window_wait = max(0.0, window_wait)
            else:
                window_wait = 0.0
            
            total_wait = max(interval_wait, window_wait)
            
            if total_wait > 0:
                logger.debug("[RATE_LIMIT] Reddit rate limit: wait %.1fs (interval=%.1fs, window=%.1fs, requests=%d/%d)",
                            total_wait, interval_wait, window_wait, 
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
    def reset(cls) -> None:
        """Reset the rate limiter (for testing)."""
        with cls._lock:
            cls._request_times = []
            cls._last_request_time = 0.0
            cls._namespace_requests = {}
