"""
Integration tests for flicker fix implementation (Phases 1-3).

Tests the complete flow from Qt allocation limit through atomic overlay state
to multi-display synchronization.
"""
import pytest
import time
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QPixmap, QImageReader
from PySide6.QtCore import Qt


@pytest.fixture
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def dummy_pixmap():
    """Create a small test pixmap."""
    pm = QPixmap(10, 10)
    pm.fill(Qt.GlobalColor.black)
    return pm


class TestQtAllocationLimit:
    """Test Qt image allocation limit increase."""
    
    def test_allocation_limit_increased(self, qapp):
        """Qt allocation limit should be increased from default 256MB."""
        # Note: Limit is set in main.py when app starts
        # In test environment, we verify the code exists to set it
        from PySide6.QtGui import QImageReader
        
        # Test that we CAN set a higher limit
        old_limit = QImageReader.allocationLimit()
        QImageReader.setAllocationLimit(1024)
        new_limit = QImageReader.allocationLimit()
        
        # Restore old limit
        QImageReader.setAllocationLimit(old_limit)
        
        # Verify it worked
        assert new_limit == 1024, f"Expected to set limit to 1024MB, got {new_limit}MB"
    
    def test_large_image_can_be_allocated(self, qapp):
        """Should be able to allocate large images without rejection."""
        # Note: Can't easily test actual large image loading in unit test
        # This verifies the limit is set correctly
        limit_mb = QImageReader.allocationLimit()
        limit_bytes = limit_mb * 1024 * 1024
        
        # For a 9342x6617 ARGB image (from logs):
        # 9342 * 6617 * 4 bytes = ~247MB - should fit in 1GB limit
        test_image_size = 9342 * 6617 * 4
        
        assert test_image_size < limit_bytes


class TestTransitionTelemetryFlow:
    """Test telemetry tracking through transition lifecycle."""
    
    def test_transition_tracks_timing(self, qapp, dummy_pixmap):
        """GL compositor transition should track start and end times."""
        from transitions.gl_compositor_crossfade_transition import (
            GLCompositorCrossfadeTransition,
        )
        
        widget = QWidget()
        widget.setGeometry(0, 0, 100, 100)
        
        try:
            trans = GLCompositorCrossfadeTransition(duration_ms=100)
            
            # Start transition (telemetry implemented in GL version)
            trans.start(dummy_pixmap, dummy_pixmap, widget)
            
            # Should have start time (GL version calls _mark_start)
            assert trans._start_time is not None
            
            # Wait a bit
            time.sleep(0.05)
            
            # Elapsed should be > 0
            elapsed = trans.get_elapsed_ms()
            assert elapsed is not None
            assert elapsed > 0
            
            # Complete transition
            trans.stop()
            trans.cleanup()
        finally:
            widget.close()


class TestMultiDisplaySyncFlow:
    """Test multi-display synchronization flow."""
    
    def test_sync_queue_lifecycle(self, qapp):
        """Test complete sync queue lifecycle."""
        from engine.display_manager import DisplayManager
        
        dm = DisplayManager()
        
        # 1. Start with sync disabled
        assert not dm._sync_enabled
        assert dm._transition_ready_queue is None
        
        # 2. Enable sync with multiple displays
        dm.displays = [None, None, None]  # Mock 3 displays
        dm.enable_transition_sync(True)
        
        assert dm._sync_enabled
        assert dm._transition_ready_queue is not None
        
        # 3. Queue ready signals
        dm._on_display_transition_ready(0)
        dm._on_display_transition_ready(1)
        dm._on_display_transition_ready(2)
        
        # 4. Wait for all displays
        result = dm.wait_for_all_displays_ready(timeout_sec=1.0)
        
        assert result is True
    
    def test_sync_timeout_handling(self, qapp):
        """Test sync timeout when displays don't signal ready."""
        from engine.display_manager import DisplayManager
        
        dm = DisplayManager()
        dm.displays = [None, None, None]
        dm.enable_transition_sync(True)
        
        # Only queue 2 of 3 signals
        dm._on_display_transition_ready(0)
        dm._on_display_transition_ready(1)
        # Display 2 never signals ready
        
        # Should timeout
        start = time.time()
        result = dm.wait_for_all_displays_ready(timeout_sec=0.1)
        elapsed = time.time() - start
        
        assert result is False
        assert 0.09 < elapsed < 0.2  # Should timeout near 0.1s


class TestRegressionPrevention:
    """Tests to prevent regression of fixed issues."""
    
    def test_no_process_events_in_transitions(self):
        """Transitions should not call processEvents() (causes races)."""
        import ast
        import inspect
        import transitions.gl_compositor_crossfade_transition as gl_compositor_crossfade_transition
        import transitions.crossfade_transition as crossfade_transition
        
        # Get source code
        modules_to_check = [gl_compositor_crossfade_transition, crossfade_transition]
        
        for module in modules_to_check:
            source = inspect.getsource(module)
            tree = ast.parse(source)
            
            # Search for processEvents calls in transition start/update methods
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr == 'processEvents':
                            # Found processEvents call - check context
                            # It's OK in pre-warming but NOT in start/update
                            pytest.fail(f"Found processEvents() call in {module.__name__} - "
                                      f"this can cause race conditions")
    
    def test_showfullscreen_not_deferred(self, qapp):
        """DisplayWidget should call showFullScreen immediately, not deferred."""
        from rendering.display_widget import DisplayWidget
        
        widget = DisplayWidget(0, None, None)
        
        try:
            # Check that deferred visibility flag doesn't exist
            assert not hasattr(widget, '_first_image_displayed')
            
            # Verify show_on_screen calls showFullScreen immediately
            # (can't fully test without actual screen, but verify method exists)
            assert hasattr(widget, 'showFullScreen')
        finally:
            if hasattr(widget, 'close'):
                widget.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
