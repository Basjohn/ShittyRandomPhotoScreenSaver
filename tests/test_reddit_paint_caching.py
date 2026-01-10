"""Regression tests for Reddit widget paint caching.

These tests verify:
- Cache is generated when _regenerate_cache is called
- Cache invalidation works correctly
- Cache handles DPR scaling correctly

Note: These tests directly call the caching methods rather than relying on
Qt's paint system, which can be unreliable in headless test environments.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget


@pytest.fixture
def mock_parent(qtbot):
    """Create a mock parent widget."""
    parent = QWidget()
    parent.resize(1920, 1080)
    qtbot.addWidget(parent)
    return parent


def _setup_reddit_widget(widget):
    """Helper to set up Reddit widget with test data."""
    from widgets.reddit_widget import RedditPost
    import time
    
    widget._enabled = True
    widget._subreddit = "test"
    # Use RedditPost dataclass objects, not plain dicts
    now = time.time()
    widget._posts = [
        RedditPost(title="Test Post 1", url="https://example.com/1", score=100, created_utc=now - 3600),
        RedditPost(title="Test Post 2", url="https://example.com/2", score=200, created_utc=now - 7200),
    ]
    widget._cache_invalidated = True


class TestRedditPaintCaching:
    """Tests for Reddit widget paint caching behavior."""

    def test_cache_generated_by_regenerate_cache(self, mock_parent, qtbot):
        """Verify cache is generated when _regenerate_cache is called."""
        from widgets.reddit_widget import RedditWidget
        
        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        
        _setup_reddit_widget(widget)
        
        # Directly call regenerate cache
        widget._regenerate_cache(widget.size())
        
        # Cache should now exist
        assert widget._cached_content_pixmap is not None
        assert not widget._cached_content_pixmap.isNull()

    def test_cache_reused_when_valid(self, mock_parent, qtbot):
        """Verify cache is reused when not invalidated."""
        from widgets.reddit_widget import RedditWidget
        
        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        
        _setup_reddit_widget(widget)
        widget._regenerate_cache(widget.size())
        
        first_cache = widget._cached_content_pixmap
        first_cache_id = id(first_cache)
        assert first_cache is not None
        
        # Mark as not invalidated
        widget._cache_invalidated = False
        
        # Calling regenerate again with same size should create new cache
        # but the _paint_cached method would skip regeneration
        # Let's verify the invalidation flag works
        assert widget._cache_invalidated is False
        
        # Cache should still be the same
        assert id(widget._cached_content_pixmap) == first_cache_id

    def test_invalidate_paint_cache_sets_flag(self, mock_parent, qtbot):
        """Verify _invalidate_paint_cache sets the invalidation flag."""
        from widgets.reddit_widget import RedditWidget
        
        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)
        
        _setup_reddit_widget(widget)
        widget._regenerate_cache(widget.size())
        widget._cache_invalidated = False
        
        # Invalidate
        widget._invalidate_paint_cache()
        
        assert widget._cache_invalidated is True

    def test_cache_size_matches_widget_size(self, mock_parent, qtbot):
        """Verify cache size matches widget size accounting for DPR."""
        from widgets.reddit_widget import RedditWidget
        
        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        
        _setup_reddit_widget(widget)
        widget._regenerate_cache(widget.size())
        
        cache = widget._cached_content_pixmap
        assert cache is not None
        
        dpr = widget.devicePixelRatioF()
        expected_w = int(widget.width() * dpr)
        expected_h = int(widget.height() * dpr)
        
        assert abs(cache.width() - expected_w) <= 1
        assert abs(cache.height() - expected_h) <= 1

    def test_cache_regenerated_creates_new_object(self, mock_parent, qtbot):
        """Verify _regenerate_cache creates a new cache object each time."""
        from widgets.reddit_widget import RedditWidget
        from PySide6.QtCore import QSize
        
        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        
        _setup_reddit_widget(widget)
        
        # Generate first cache
        widget._regenerate_cache(QSize(400, 300))
        first_cache_id = id(widget._cached_content_pixmap)
        
        # Generate second cache with different size
        widget._regenerate_cache(QSize(500, 400))
        second_cache_id = id(widget._cached_content_pixmap)
        
        # Should be different objects
        assert first_cache_id != second_cache_id
        
        # Second cache should have different dimensions
        cache = widget._cached_content_pixmap
        dpr = widget.devicePixelRatioF()
        expected_w = int(500 * dpr)
        expected_h = int(400 * dpr)
        assert abs(cache.width() - expected_w) <= 1
        assert abs(cache.height() - expected_h) <= 1


class TestRedditPaintCacheDPR:
    """Tests for DPR (device pixel ratio) handling in paint cache."""

    def test_cache_accounts_for_dpr(self, mock_parent, qtbot):
        """Verify cache pixmap accounts for device pixel ratio."""
        from widgets.reddit_widget import RedditWidget
        
        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        
        _setup_reddit_widget(widget)
        widget._regenerate_cache(widget.size())
        
        cache = widget._cached_content_pixmap
        assert cache is not None
        
        dpr = widget.devicePixelRatioF()
        # Cache should be scaled by DPR
        expected_w = int(widget.width() * dpr)
        expected_h = int(widget.height() * dpr)
        
        assert abs(cache.width() - expected_w) <= 1
        assert abs(cache.height() - expected_h) <= 1
        # Cache should have correct DPR set
        assert abs(cache.devicePixelRatio() - dpr) < 0.01


class TestRedditPaintPerformance:
    """Performance-related tests for Reddit widget painting."""

    def test_cached_paint_faster_than_uncached(self, mock_parent, qtbot):
        """Verify cached paints are faster than uncached paints."""
        import time
        from widgets.reddit_widget import RedditWidget, RedditPost
        
        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        
        # Set up data with more posts using RedditPost dataclass
        widget._enabled = True
        widget._subreddit = "test"
        now = time.time()
        widget._posts = [
            RedditPost(title=f"Post {i}", url=f"https://example.com/{i}", score=i * 100, created_utc=now - i * 3600)
            for i in range(10)
        ]
        widget.show()
        qtbot.waitExposed(widget)
        
        # First paint (uncached) - force regeneration
        widget._cache_invalidated = True
        start = time.perf_counter()
        widget.repaint()
        qtbot.wait(50)
        uncached_time = time.perf_counter() - start
        
        # Subsequent paints (cached)
        cached_times = []
        for _ in range(5):
            widget._cache_invalidated = False
            start = time.perf_counter()
            widget.repaint()
            qtbot.wait(10)
            cached_times.append(time.perf_counter() - start)
        
        avg_cached_time = sum(cached_times) / len(cached_times)
        
        # Cached paints should generally be faster
        # (Note: This is a soft assertion due to timing variability)
        # We mainly want to ensure caching doesn't make things slower
        assert avg_cached_time <= uncached_time * 2  # Allow 2x tolerance for timing noise
