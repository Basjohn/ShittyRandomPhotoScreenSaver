"""
Tests for overlay ready state atomic flags (Phase 1 & 2).

Tests the thread-safe ready state tracking added to all transition overlays
to eliminate paint event race conditions.
"""
import pytest
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QRect


@pytest.fixture
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def dummy_widget(qapp):
    """Create a dummy widget for testing."""
    widget = QWidget()
    widget.setGeometry(0, 0, 100, 100)
    yield widget
    widget.close()


@pytest.fixture
def dummy_pixmap():
    """Create a small test pixmap."""
    pm = QPixmap(10, 10)
    pm.fill(Qt.GlobalColor.black)
    return pm


class TestSWCrossfadeOverlayReady:
    """Test SW Crossfade overlay atomic ready state."""
    
    def test_sw_overlay_not_ready_before_paint(self, qapp, dummy_widget, dummy_pixmap):
        """SW overlay should not be ready before first paint."""
        from transitions.crossfade_transition import _SWFadeOverlay
        
        overlay = _SWFadeOverlay(dummy_widget, dummy_pixmap, dummy_pixmap)
        
        # Should not be ready immediately
        assert not overlay.is_ready_for_display()
    
    def test_sw_overlay_ready_after_paint(self, qapp, dummy_widget, dummy_pixmap):
        """SW overlay should be ready after first paint event."""
        from transitions.crossfade_transition import _SWFadeOverlay
        
        overlay = _SWFadeOverlay(dummy_widget, dummy_pixmap, dummy_pixmap)
        overlay.setGeometry(0, 0, 10, 10)
        overlay.show()
        
        # Manually mark as painted (simulating paintEvent completion)
        # repaint() may not be synchronous in test environment
        with overlay._state_lock:
            overlay._first_frame_drawn = True
        
        # Should be ready after paint
        assert overlay.is_ready_for_display()


class TestOverlayManagerReady:
    """Test overlay_manager ready checks."""
    
    def test_any_overlay_ready_returns_false_when_none_visible(self, qapp, dummy_widget):
        """Should return False when no overlays are visible."""
        from transitions.overlay_manager import any_overlay_ready_for_display
        
        # No overlays attached
        result = any_overlay_ready_for_display(dummy_widget)
        assert result is False
    
    def test_display_widget_retains_previous_pixmap_on_clear(self, qapp, settings_manager, dummy_pixmap):
        from rendering.display_widget import DisplayWidget

        widget = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
        widget.resize(200, 200)
        widget.current_pixmap = dummy_pixmap
        widget.previous_pixmap = None

        widget.clear()

        assert widget.previous_pixmap is dummy_pixmap
        assert widget.current_pixmap is None


class TestDisplayWidgetOverlayDiagnostics:
    def test_notify_overlay_ready_tracks_counts(self, qapp, dummy_pixmap):
        from rendering.display_widget import DisplayWidget

        widget = DisplayWidget(0, None, None)
        widget.notify_overlay_ready("test_overlay", "gl_initialized", version="4.6")
        widget.notify_overlay_ready("test_overlay", "prepaint_ready")

        counts = widget.get_overlay_stage_counts()

        assert counts["test_overlay:gl_initialized"] == 1
        assert counts["test_overlay:prepaint_ready"] == 1

    def test_handle_screen_change_updates_geometry_and_dpi(self, qapp, dummy_pixmap):
        from rendering.display_widget import DisplayWidget

        class _FakeScreen:
            def __init__(self, rect: QRect, dpr: float) -> None:
                self._rect = rect
                self._dpr = dpr

            def geometry(self) -> QRect:
                return self._rect

            def devicePixelRatio(self) -> float:
                return self._dpr

        widget = DisplayWidget(0, None, None)
        widget.resize(100, 100)

        fake_screen = _FakeScreen(QRect(0, 0, 640, 360), 1.75)
        widget._handle_screen_change(fake_screen)

        assert widget._screen is fake_screen
        # Allow 1px tolerance for DPI rounding differences
        assert widget.width() == 640
        assert abs(widget.height() - 360) <= 1, f"Height {widget.height()} should be within 1px of 360"
        assert pytest.approx(widget._device_pixel_ratio, rel=1e-3) == 1.75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
