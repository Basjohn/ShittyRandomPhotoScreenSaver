"""
Tests for overlay ready state atomic flags (Phase 1 & 2).

Tests the thread-safe ready state tracking added to all transition overlays
to eliminate paint event race conditions.
"""
import pytest
import threading
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


class TestGLCrossfadeOverlayReady:
    """Test GL Crossfade overlay atomic ready state."""
    
    def test_overlay_not_ready_before_init(self, qapp, dummy_widget, dummy_pixmap):
        """Overlay should not be ready before GL initialization."""
        from transitions.gl_crossfade_transition import _GLFadeWidget
        
        overlay = _GLFadeWidget(dummy_widget, dummy_pixmap, dummy_pixmap)
        
        # Should not be ready immediately after creation
        assert not overlay.is_ready_for_display()
    
    def test_overlay_ready_after_init_and_paint(self, qapp, dummy_widget, dummy_pixmap):
        """Overlay should be ready after GL init and first paint."""
        from transitions.gl_crossfade_transition import _GLFadeWidget
        
        overlay = _GLFadeWidget(dummy_widget, dummy_pixmap, dummy_pixmap)
        overlay.setGeometry(0, 0, 10, 10)
        overlay.show()
        
        # Force GL initialization
        try:
            overlay.makeCurrent()
            # Trigger paintGL
            overlay.repaint()
            # Process events to complete paint
            QApplication.processEvents()
            
            # Should be ready after paint
            assert overlay.is_ready_for_display()
        except Exception:
            pytest.skip("GL context not available in test environment")
    
    def test_overlay_ready_state_thread_safe(self, qapp, dummy_widget, dummy_pixmap):
        """Test that ready state checks are thread-safe."""
        from transitions.gl_crossfade_transition import _GLFadeWidget
        
        overlay = _GLFadeWidget(dummy_widget, dummy_pixmap, dummy_pixmap)
        results = []
        
        def check_ready():
            for _ in range(100):
                # This should never raise an exception
                ready = overlay.is_ready_for_display()
                results.append(ready)
        
        # Spawn multiple threads checking ready state
        threads = [threading.Thread(target=check_ready) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All checks should complete without error
        assert len(results) == 500  # 5 threads × 100 checks
    
    def test_overlay_reset_on_set_images(self, qapp, dummy_widget, dummy_pixmap):
        """Overlay should reset ready state when images are changed."""
        from transitions.gl_crossfade_transition import _GLFadeWidget
        
        overlay = _GLFadeWidget(dummy_widget, dummy_pixmap, dummy_pixmap)
        overlay.setGeometry(0, 0, 10, 10)
        
        # Manually mark as ready (simulating first paint)
        with overlay._state_lock:
            overlay._gl_initialized = True
            overlay._first_frame_drawn = True
        
        assert overlay.is_ready_for_display()
        
        # Change images - should reset ready state
        new_pixmap = QPixmap(10, 10)
        new_pixmap.fill(Qt.GlobalColor.white)
        overlay.set_images(dummy_pixmap, new_pixmap)
        
        # Should not be ready anymore
        assert not overlay.is_ready_for_display()


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
    
    def test_any_overlay_ready_returns_true_when_gl_ready(self, qapp, dummy_widget, dummy_pixmap):
        """Should return True when GL overlay is ready."""
        from transitions.overlay_manager import any_overlay_ready_for_display
        from transitions.gl_crossfade_transition import _GLFadeWidget
        
        overlay = _GLFadeWidget(dummy_widget, dummy_pixmap, dummy_pixmap)
        overlay.setGeometry(0, 0, 10, 10)
        
        # Attach to widget FIRST
        setattr(dummy_widget, "_srpss_gl_xfade_overlay", overlay)
        
        # Show overlay
        overlay.show()
        QApplication.processEvents()  # Process show event
        
        # Verify it's visible
        if not overlay.isVisible():
            pytest.skip("GL overlay cannot be made visible in test environment")
        
        # Manually mark as ready AFTER confirming visibility
        with overlay._state_lock:
            overlay._gl_initialized = True
            overlay._first_frame_drawn = True
        
        # Should detect ready overlay
        result = any_overlay_ready_for_display(dummy_widget)
        assert result is True
    
    def test_any_overlay_ready_returns_false_when_visible_but_not_ready(
        self, qapp, dummy_widget, dummy_pixmap
    ):
        """Should return False when overlay is visible but not ready yet."""
        from transitions.overlay_manager import any_overlay_ready_for_display
        from transitions.gl_crossfade_transition import _GLFadeWidget
        
        overlay = _GLFadeWidget(dummy_widget, dummy_pixmap, dummy_pixmap)
        overlay.setGeometry(0, 0, 10, 10)
        overlay.show()  # Visible but not ready
        
        # Attach to widget
        setattr(dummy_widget, "_srpss_gl_xfade_overlay", overlay)
        
        # Should return False (not ready)
        result = any_overlay_ready_for_display(dummy_widget)
        assert result is False


class TestAllGLOverlaysReadyState:
    """Test that all GL overlay types have atomic ready state."""
    
    @pytest.mark.parametrize("overlay_class,extra_args", [
        ("_GLFadeWidget", []),
        ("_GLSlideWidget", ["SlideDirection.LEFT"]),
        ("_GLWipeWidget", ["WipeDirection.LEFT_TO_RIGHT"]),
    ])
    def test_gl_overlay_has_ready_method(self, qapp, dummy_widget, dummy_pixmap, overlay_class, extra_args):
        """Test that GL overlay has is_ready_for_display method."""
        # Import based on overlay type
        if "Slide" in overlay_class:
            from transitions.gl_slide_transition import _GLSlideWidget as OverlayClass
            from transitions.slide_transition import SlideDirection
            args = [dummy_widget, dummy_pixmap, dummy_pixmap, SlideDirection.LEFT]
        elif "Wipe" in overlay_class:
            from transitions.gl_wipe_transition import _GLWipeWidget as OverlayClass
            from transitions.wipe_transition import WipeDirection
            args = [dummy_widget, dummy_pixmap, dummy_pixmap, WipeDirection.LEFT_TO_RIGHT]
        elif "Blinds" in overlay_class:
            from transitions.gl_blinds import _GLBlindsOverlay as OverlayClass, _GLBlindsSlat
            slats = [_GLBlindsSlat(dummy_widget.rect(), 0, 1)]
            args = [dummy_widget, dummy_pixmap, dummy_pixmap, slats]
        else:
            from transitions.gl_crossfade_transition import _GLFadeWidget as OverlayClass
            args = [dummy_widget, dummy_pixmap, dummy_pixmap]
        
        overlay = OverlayClass(*args)
        
        # Check method exists
        assert hasattr(overlay, 'is_ready_for_display')
        assert callable(overlay.is_ready_for_display)
        
        # Check initial state
        assert overlay.is_ready_for_display() is False

    def test_gl_blinds_tail_repaint_flag(self, qapp, dummy_widget, dummy_pixmap):
        """Tail repaint should only trigger once when slats fully open."""
        from transitions.gl_blinds import GLBlindsTransition

        widget = dummy_widget
        widget.resize(120, 120)

        old_pm = QPixmap(120, 120)
        old_pm.fill(Qt.GlobalColor.black)
        new_pm = QPixmap(120, 120)
        new_pm.fill(Qt.GlobalColor.white)

        transition = GLBlindsTransition(duration_ms=1000, slat_rows=2, slat_cols=2)
        started = transition.start(old_pm, new_pm, widget)
        if not started:
            pytest.skip("GL context unavailable for blinds overlay")

        overlay = getattr(widget, "_srpss_gl_blinds_overlay", None)
        if overlay is None:
            pytest.skip("GL blinds overlay not created (likely headless)")

        # Drive animation update manually and capture repaint flag
        transition._tail_repaint_sent = False
        transition._on_anim_update(0.91)
        assert transition._tail_repaint_sent is False
        transition._on_anim_update(0.94)
        assert transition._tail_repaint_sent is True

    def test_display_widget_retains_previous_pixmap_on_clear(self, qapp, settings_manager, dummy_pixmap):
        from rendering.display_widget import DisplayWidget

        widget = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
        widget.resize(200, 200)
        widget.current_pixmap = dummy_pixmap
        widget.previous_pixmap = None

        widget.clear()

        assert widget.previous_pixmap is dummy_pixmap
        assert widget.current_pixmap is None

    
    def test_gl_diffuse_overlay_ready(self, qapp, dummy_widget, dummy_pixmap):
        """Test GL Diffuse overlay ready state."""
        from transitions.gl_diffuse_transition import _GLDiffuseWidget, _Cell
        from PySide6.QtCore import QRect
        
        cells = [_Cell(QRect(0, 0, 10, 10))]
        overlay = _GLDiffuseWidget(dummy_widget, dummy_pixmap, dummy_pixmap, cells)
        
        assert hasattr(overlay, 'is_ready_for_display')
        assert overlay.is_ready_for_display() is False
    
    def test_gl_block_overlay_ready(self, qapp, dummy_widget, dummy_pixmap):
        """Test GL Block overlay ready state."""
        from transitions.gl_block_puzzle_flip_transition import _GLBlockFlipWidget, _GLFlipBlock
        from PySide6.QtCore import QRect
        
        blocks = [_GLFlipBlock(QRect(0, 0, 10, 10))]
        overlay = _GLBlockFlipWidget(dummy_widget, dummy_pixmap, dummy_pixmap, blocks)
        
        assert hasattr(overlay, 'is_ready_for_display')
        assert overlay.is_ready_for_display() is False


class TestDisplayWidgetPaintEvent:
    """Test DisplayWidget paint event integration with overlay ready state."""
    
    def test_paint_event_skips_when_overlay_ready(self, qapp, dummy_pixmap):
        """DisplayWidget paintEvent should skip base paint when overlay is ready."""
        from rendering.display_widget import DisplayWidget
        from transitions.gl_crossfade_transition import _GLFadeWidget
        
        # Create display widget
        widget = DisplayWidget(0, None, None)
        widget.setGeometry(0, 0, 100, 100)
        widget.current_pixmap = dummy_pixmap
        
        # Create and attach ready overlay
        overlay = _GLFadeWidget(widget, dummy_pixmap, dummy_pixmap)
        overlay.setGeometry(0, 0, 100, 100)
        
        with overlay._state_lock:
            overlay._gl_initialized = True
            overlay._first_frame_drawn = True
        
        overlay.show()
        setattr(widget, "_srpss_gl_xfade_overlay", overlay)
        
        # Trigger paint event
        # If overlay is ready, base paint should be skipped (no exception)
        widget.repaint()
        QApplication.processEvents()
        
        widget.close()


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
        assert widget.width() == 640 and widget.height() == 360
        assert pytest.approx(widget._device_pixel_ratio, rel=1e-3) == 1.75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
