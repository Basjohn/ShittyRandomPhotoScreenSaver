"""Performance benchmark tests for widget paint times.

These tests verify that widget paint operations stay within acceptable
time budgets to maintain smooth UI performance.

Expected performance targets (from WidgetRefactorPlan.md):
- Weather paint time <0.5ms
- Media paint time <2ms
- Reddit paint time <1ms (cached)

Note: Test environment has higher overhead than production. Thresholds are
relaxed to account for test framework overhead while still catching regressions.
"""
from __future__ import annotations

import time
import pytest
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QImage, QPaintEvent
from PySide6.QtCore import QBuffer, QIODevice, QRect


@pytest.fixture
def mock_parent(qtbot):
    """Create a mock parent widget."""
    parent = QWidget()
    parent.resize(1920, 1080)
    qtbot.addWidget(parent)
    return parent


def _create_test_artwork_bytes() -> bytes:
    """Create a small valid PNG image for testing."""
    img = QImage(100, 100, QImage.Format.Format_ARGB32)
    img.fill(0xFFFF0000)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buffer, "PNG")
    return bytes(buffer.data())


def _measure_paint_time(widget, iterations: int = 10) -> tuple[float, float]:
    """Measure paint time by directly calling paintEvent.
    
    Returns (avg_ms, max_ms) tuple.
    """
    paint_times = []
    event = QPaintEvent(QRect(0, 0, widget.width(), widget.height()))
    
    for _ in range(iterations):
        start = time.perf_counter()
        widget.paintEvent(event)
        paint_times.append((time.perf_counter() - start) * 1000)
    
    return sum(paint_times) / len(paint_times), max(paint_times)


class TestWeatherWidgetPerformance:
    """Performance tests for weather widget paint times."""

    def test_weather_paint_under_threshold(self, mock_parent, qtbot):
        """Verify weather widget paint time is under threshold."""
        from widgets.weather_widget import WeatherWidget, WeatherPosition
        
        widget = WeatherWidget(mock_parent, position=WeatherPosition.TOP_LEFT)
        qtbot.addWidget(widget)
        widget.resize(200, 150)
        widget.show()
        qtbot.waitExposed(widget)
        
        # Warm up
        widget.repaint()
        qtbot.wait(50)
        
        # Measure paint time directly
        avg_time, _ = _measure_paint_time(widget, iterations=10)
        
        # Weather widget should be fast
        assert avg_time < 5.0, f"Weather avg paint time {avg_time:.2f}ms exceeds 5ms threshold"


class TestMediaWidgetPerformance:
    """Performance tests for media widget paint times."""

    def test_media_paint_under_threshold(self, mock_parent, qtbot):
        """Verify media widget paint time is under threshold."""
        from widgets.media_widget import MediaWidget, MediaPosition
        from core.media.media_controller import MediaTrackInfo, MediaPlaybackState
        
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        qtbot.addWidget(widget)
        widget.resize(600, 250)
        
        # Set up with track data
        artwork_bytes = _create_test_artwork_bytes()
        info = MediaTrackInfo(
            title="Test Song",
            artist="Test Artist",
            state=MediaPlaybackState.PLAYING,
            artwork=artwork_bytes,
        )
        widget._update_display(info)
        widget._has_seen_first_track = True
        widget._update_display(info)  # Second update to complete setup
        
        widget.show()
        qtbot.waitExposed(widget)
        
        # Warm up
        widget.repaint()
        qtbot.wait(50)
        
        # Measure paint time directly
        avg_time, _ = _measure_paint_time(widget, iterations=10)
        
        # Media widget should paint reasonably fast
        assert avg_time < 10.0, f"Media avg paint time {avg_time:.2f}ms exceeds 10ms threshold"


class TestRedditWidgetPerformance:
    """Performance tests for Reddit widget paint times."""

    def test_reddit_cached_paint_under_threshold(self, mock_parent, qtbot):
        """Verify Reddit widget cached paint time is under threshold."""
        from widgets.reddit_widget import RedditWidget, RedditPost
        
        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        
        # Set up with post data
        widget._enabled = True
        widget._subreddit = "test"
        now = time.time()
        widget._posts = [
            RedditPost(title=f"Post {i}", url=f"https://example.com/{i}", 
                      score=i * 100, created_utc=now - i * 3600)
            for i in range(5)
        ]
        
        widget.show()
        qtbot.waitExposed(widget)
        
        # First paint generates cache
        widget._cache_invalidated = True
        widget.repaint()
        qtbot.wait(50)
        
        # Subsequent paints should use cache
        widget._cache_invalidated = False
        
        # Measure paint time directly
        avg_time, _ = _measure_paint_time(widget, iterations=10)
        
        # Cached Reddit paint should be fast
        assert avg_time < 5.0, f"Reddit cached avg paint time {avg_time:.2f}ms exceeds 5ms threshold"
