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
        assert RedditRateLimiter.get_blocked_cooldown_remaining() == 0.0

    def test_blocked_response_starts_cooldown(self):
        """Verify blocked public-endpoint responses trigger a harsher cooldown."""
        from core.reddit_rate_limiter import RedditRateLimiter

        RedditRateLimiter.reset()
        RedditRateLimiter.record_blocked_response(reason="403")

        wait_time = RedditRateLimiter.wait_if_needed()

        assert wait_time > 0
        assert RedditRateLimiter.get_blocked_cooldown_remaining() > 0

    def test_acquire_request_slot_records_request_when_available(self):
        """Verify atomic slot acquisition records a request immediately."""
        from core.reddit_rate_limiter import RedditRateLimiter

        RedditRateLimiter.reset()

        result = RedditRateLimiter.acquire_request_slot(namespace="widget")

        assert result == "acquired"
        assert RedditRateLimiter.get_request_count() == 1

    def test_acquire_request_slot_can_skip_when_blocked_cooldown_is_active(self):
        """Verify blocked cooldown can abort queued requests before they hit Reddit."""
        from core.reddit_rate_limiter import RedditRateLimiter

        RedditRateLimiter.reset()
        RedditRateLimiter.record_blocked_response(reason="403")

        result = RedditRateLimiter.acquire_request_slot(
            namespace="widget",
            skip_if_blocked=True,
        )

        assert result == "blocked"
        assert RedditRateLimiter.get_request_count() == 0

    def test_request_persona_is_stable_for_same_widget_key_within_rotation_window(self):
        """Verify Reddit request personas stay stable for the same key within a window."""
        from core.reddit_rate_limiter import RedditRateLimiter, get_reddit_request_persona

        RedditRateLimiter.reset()

        first = get_reddit_request_persona("reddit:Games:hot")
        second = get_reddit_request_persona("reddit:Games:hot")

        assert first.key == second.key
        assert first.user_agent == second.user_agent
        assert first.headers == second.headers

    def test_request_personas_expose_distinct_client_labels_and_headers(self):
        """Verify persona pool exposes different client/application appearances."""
        from core.reddit_rate_limiter import REDDIT_REQUEST_PERSONAS

        labels = {persona.label for persona in REDDIT_REQUEST_PERSONAS}
        header_clients = {persona.headers.get("X-SRPSS-Reddit-Client") for persona in REDDIT_REQUEST_PERSONAS}

        assert len(labels) == len(REDDIT_REQUEST_PERSONAS)
        assert None not in header_clients
        assert len(header_clients) == len(REDDIT_REQUEST_PERSONAS)


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

    def test_wallpaper_feeds_share_the_reddit_quota(self, monkeypatch):
        """A Reddit wallpaper feed yields to the Reddit widget's quota and counts against it."""
        from core.reddit_rate_limiter import RedditRateLimiter
        from sources.rss.coordinator import RSSCoordinator

        recorded = []
        monkeypatch.setattr(RedditRateLimiter, "should_skip_for_quota", classmethod(lambda cls, **_k: True))
        assert RSSCoordinator._reddit_quota_allows("https://www.reddit.com/r/wallpapers/.rss") is False
        monkeypatch.setattr(RedditRateLimiter, "should_skip_for_quota", classmethod(lambda cls, **_k: False))
        monkeypatch.setattr(RedditRateLimiter, "record_request",
                            classmethod(lambda cls, **kwargs: recorded.append(kwargs)))
        assert RSSCoordinator._reddit_quota_allows("https://www.reddit.com/r/wallpapers/.rss") is True
        assert recorded == [{"namespace": "rss"}]
        # Other hosts never consult the Reddit limiter.
        assert RSSCoordinator._reddit_quota_allows("https://www.nasa.gov/feeds/iotd-feed") is True
        assert recorded == [{"namespace": "rss"}]

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
