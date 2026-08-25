"""Performance benchmark tests for widget paint times.

These tests verify that widget paint operations stay within acceptable
time budgets to maintain smooth UI performance.

Expected performance target (from WidgetRefactorPlan.md):
- Media paint time <2ms

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
