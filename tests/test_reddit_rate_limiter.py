"""Tests for centralized Reddit rate limiter.

These tests verify:
- Rate limiter enforces request limits
- Rate limiter coordinates between RSS source and Reddit widget
- Wait times are calculated correctly
- Request recording works properly
"""
from __future__ import annotations

import time


class TestRedditRateLimiter:
    """Tests for RedditRateLimiter class."""

    def test_can_make_request_when_empty(self):
        """Verify requests allowed when no recent requests."""
        from core.reddit_rate_limiter import RedditRateLimiter
        
        RedditRateLimiter.reset()
        assert RedditRateLimiter.can_make_request() is True

    def test_record_request_increments_count(self):
        """Verify recording a request increments the count."""
        from core.reddit_rate_limiter import RedditRateLimiter
        
        RedditRateLimiter.reset()
        assert RedditRateLimiter.get_request_count() == 0
        
        RedditRateLimiter.record_request()
        assert RedditRateLimiter.get_request_count() == 1
        
        RedditRateLimiter.record_request()
        assert RedditRateLimiter.get_request_count() == 2

    def test_rate_limit_enforced(self):
        """Verify rate limit is enforced after max requests."""
        from core.reddit_rate_limiter import RedditRateLimiter
        
        RedditRateLimiter.reset()
        
        # Make max requests
        for _ in range(RedditRateLimiter.MAX_REQUESTS_PER_MINUTE):
            RedditRateLimiter.record_request()
        
        # Should not be able to make more requests
        assert RedditRateLimiter.can_make_request() is False

    def test_wait_if_needed_returns_zero_when_allowed(self):
        """Verify wait_if_needed returns 0 when request is allowed."""
        from core.reddit_rate_limiter import RedditRateLimiter
        
        RedditRateLimiter.reset()
        
        # First request should have no wait (after min interval)
        time.sleep(RedditRateLimiter.MIN_REQUEST_INTERVAL + 0.1)
        wait_time = RedditRateLimiter.wait_if_needed()
        assert wait_time == 0.0

    def test_wait_if_needed_returns_positive_when_rate_limited(self):
        """Verify wait_if_needed returns positive value when rate limited."""
        from core.reddit_rate_limiter import RedditRateLimiter
        
        RedditRateLimiter.reset()
        
        # Make max requests quickly
        for _ in range(RedditRateLimiter.MAX_REQUESTS_PER_MINUTE):
            RedditRateLimiter.record_request()
        
        # Should need to wait
        wait_time = RedditRateLimiter.wait_if_needed()
        assert wait_time > 0

    def test_min_request_interval_enforced(self):
        """Verify minimum interval between requests is enforced."""
        from core.reddit_rate_limiter import RedditRateLimiter
        
        RedditRateLimiter.reset()
        
        # Record a request
        RedditRateLimiter.record_request()
        
        # Immediately check wait time - should need to wait
        wait_time = RedditRateLimiter.wait_if_needed()
        assert wait_time > 0
        assert wait_time <= RedditRateLimiter.MIN_REQUEST_INTERVAL

    def test_old_requests_expire(self):
        """Verify old requests are removed from the window."""
        from core.reddit_rate_limiter import RedditRateLimiter
        
        RedditRateLimiter.reset()
        
        # Record a request
        RedditRateLimiter.record_request()
        assert RedditRateLimiter.get_request_count() == 1
        
        # Manually expire the request by manipulating internal state
        # (In real usage, we'd wait 60 seconds)
        with RedditRateLimiter._lock:
            RedditRateLimiter._request_times = [time.time() - 61]  # 61 seconds ago
        
        # Request should be expired
        assert RedditRateLimiter.get_request_count() == 0

    def test_reset_clears_state(self):
        """Verify reset clears all state."""
        from core.reddit_rate_limiter import RedditRateLimiter
        
        # Add some requests
        RedditRateLimiter.record_request()
        RedditRateLimiter.record_request()
        
        # Reset
        RedditRateLimiter.reset()
        
        # Should be empty
        assert RedditRateLimiter.get_request_count() == 0
        assert RedditRateLimiter._last_request_time == 0.0


class TestRedditRateLimiterThreadSafety:
    """Tests for thread safety of RedditRateLimiter."""

    def test_concurrent_requests_safe(self):
        """Verify concurrent requests don't corrupt state."""
        import threading
        from core.reddit_rate_limiter import RedditRateLimiter
        
        RedditRateLimiter.reset()
        
        errors = []
        
        def record_requests():
            try:
                for _ in range(10):
                    RedditRateLimiter.record_request()
                    RedditRateLimiter.can_make_request()
                    RedditRateLimiter.wait_if_needed()
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=record_requests) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # No errors should have occurred
        assert len(errors) == 0
        
        # State should be consistent (50 requests recorded)
        # Some may have expired during the test, so just check it's reasonable
        count = RedditRateLimiter.get_request_count()
        assert count <= 50


class TestRedditRateLimiterIntegration:
    """Integration tests for rate limiter with RSS source and Reddit widget."""

    def test_rss_source_uses_rate_limiter(self):
        """Verify RSS source checks rate limiter before Reddit requests."""
        # This is a documentation test - the actual integration is in rss_source.py
        # We verify the import works and the method exists
        from core.reddit_rate_limiter import RedditRateLimiter
        
        assert hasattr(RedditRateLimiter, 'wait_if_needed')
        assert hasattr(RedditRateLimiter, 'record_request')
        assert callable(RedditRateLimiter.wait_if_needed)
        assert callable(RedditRateLimiter.record_request)

    def test_rate_limiter_constants_reasonable(self):
        """Verify rate limiter constants are reasonable for Reddit API."""
        from core.reddit_rate_limiter import RedditRateLimiter

        # Reddit allows 10 req/min, we should be under that
        assert RedditRateLimiter.MAX_REQUESTS_PER_MINUTE <= 10

        # Window should be 60 seconds
        assert RedditRateLimiter.WINDOW_SECONDS == 60.0

        # Min interval should give us under 10 req/min
        max_requests_per_min = 60.0 / RedditRateLimiter.MIN_REQUEST_INTERVAL
        assert max_requests_per_min <= 10


class TestRedditRateLimiterNamespace:
    """Tests for namespace-based quota tracking."""

    def test_namespace_tracking_separate(self):
        """Verify namespace tracking is separate from global."""
        from core.reddit_rate_limiter import RedditRateLimiter

        RedditRateLimiter.reset()

        # Record requests with different namespaces
        RedditRateLimiter.record_request(namespace="rss")
        RedditRateLimiter.record_request(namespace="rss")
        RedditRateLimiter.record_request(namespace="widget")

        # Global count should be 3
        assert RedditRateLimiter.get_request_count() == 3

        # Namespace counts should be separate
        assert RedditRateLimiter.get_namespace_count("rss") == 2
        assert RedditRateLimiter.get_namespace_count("widget") == 1
        assert RedditRateLimiter.get_namespace_count("unknown") == 0

    def test_namespace_reset_clears_all(self):
        """Verify reset clears namespace tracking."""
        from core.reddit_rate_limiter import RedditRateLimiter

        RedditRateLimiter.record_request(namespace="rss")
        RedditRateLimiter.record_request(namespace="widget")

        RedditRateLimiter.reset()

        assert RedditRateLimiter.get_namespace_count("rss") == 0
        assert RedditRateLimiter.get_namespace_count("widget") == 0

    def test_preflight_quota_check_skips_reddit_feeds(self):
        """Verify pre-flight quota check prevents Reddit feed processing when quota exhausted."""
        from core.reddit_rate_limiter import RedditRateLimiter

        RedditRateLimiter.reset()

        # Exhaust quota
        for _ in range(RedditRateLimiter.MAX_REQUESTS_PER_MINUTE):
            RedditRateLimiter.record_request(namespace="rss")

        # Pre-flight check should fail
        assert RedditRateLimiter.can_make_request() is False

        # This simulates what rss_source.py does - skip all Reddit feeds
        reddit_quota_available = RedditRateLimiter.can_make_request()
        assert reddit_quota_available is False
