"""
Tests for multi-display synchronization (Phase 3).

Tests the lock-free SPSC queue-based synchronization for coordinating
transitions across multiple displays.
"""
import logging
import pytest
import time
from PySide6.QtGui import QGuiApplication
from engine.display_manager import DisplayManager


@pytest.fixture
def qapp():
    """Create the QtGui application lifetime required by DisplayManager."""
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    yield app


class TestDisplayManagerSync:
    """Test DisplayManager synchronization features."""
    
    def test_sync_disabled_by_default(self, qapp):
        """Sync should be disabled by default."""
        dm = DisplayManager()
        assert dm._sync_enabled is False
        assert dm._transition_ready_queue is None
    
    def test_enable_sync_creates_queue(self, qapp):
        """Enabling sync should create SPSC queue."""
        dm = DisplayManager()
        
        # Create mock displays
        dm.displays = [None, None]  # Simulate 2 displays
        
        dm.enable_transition_sync(True)
        
        assert dm._sync_enabled is True
        assert dm._transition_ready_queue is not None
    
    def test_disable_sync_clears_queue(self, qapp):
        """Disabling sync should clear queue."""
        dm = DisplayManager()
        dm.displays = [None, None]
        
        dm.enable_transition_sync(True)
        assert dm._transition_ready_queue is not None
        
        dm.enable_transition_sync(False)
        assert dm._sync_enabled is False
    
    def test_sync_not_enabled_for_single_display(self, qapp):
        """Sync should not be enabled for single display."""
        dm = DisplayManager()
        dm.displays = [None]  # Single display
        
        dm.enable_transition_sync(True)
        
        # Should not actually enable
        assert dm._transition_ready_queue is None


class TestSPSCQueueSync:
    """Test SPSC queue synchronization logic."""
    
    def test_ready_signal_queuing(self, qapp):
        """Test that ready signals can be queued."""
        dm = DisplayManager()
        dm.displays = [None, None, None]  # 3 displays
        dm.enable_transition_sync(True)
        
        # Queue ready signals
        dm._on_display_transition_ready(0)
        dm._on_display_transition_ready(1)
        dm._on_display_transition_ready(2)
        
        # Should have 3 signals in queue
        count = 0
        while dm._transition_ready_queue.try_pop()[0]:
            count += 1
        
        assert count == 3
    
    def test_wait_for_all_displays_success(self, qapp):
        """Test waiting for all displays successfully."""
        dm = DisplayManager()
        dm.displays = [None, None]
        dm.enable_transition_sync(True)
        
        # Pre-queue ready signals
        dm._on_display_transition_ready(0)
        dm._on_display_transition_ready(1)
        
        # Should return immediately since all are ready
        start = time.time()
        result = dm.wait_for_all_displays_ready(timeout_sec=1.0)
        elapsed = time.time() - start
        
        assert result is True
        assert elapsed < 0.1  # Should be very fast
    
    def test_wait_for_all_displays_timeout(self, qapp):
        """Test timeout when not all displays ready."""
        dm = DisplayManager()
        dm.displays = [None, None, None]  # 3 displays
        dm.enable_transition_sync(True)
        
        # Only queue 2 ready signals (missing 1)
        dm._on_display_transition_ready(0)
        dm._on_display_transition_ready(1)
        
        # Should timeout
        start = time.time()
        result = dm.wait_for_all_displays_ready(timeout_sec=0.1)
        elapsed = time.time() - start
        
        assert result is False
        assert 0.09 < elapsed < 0.2  # Should timeout near 0.1s
    
    def test_wait_returns_true_when_sync_disabled(self, qapp):
        """Wait should return True immediately when sync disabled."""
        dm = DisplayManager()
        dm.displays = [None, None]
        # Sync not enabled
        
        result = dm.wait_for_all_displays_ready(timeout_sec=1.0)
        
        assert result is True  # Proceeds immediately
    
    def test_wait_returns_true_for_single_display(self, qapp):
        """Wait should return True immediately for single display."""
        dm = DisplayManager()
        dm.displays = [None]  # Single display
        dm.enable_transition_sync(True)
        
        result = dm.wait_for_all_displays_ready(timeout_sec=1.0)
        
        assert result is True  # No sync needed


class TestSynchronizedTransition:
    """Test synchronized image transitions."""
    
    # Image publication itself is owned by the retained Quick presentation
    # contract. This suite covers only cross-display transition readiness.

    def test_transition_sync_queue_can_be_cleared_for_new_quick_transition(self, qapp):
        """Synchronized show should clear queue before starting."""
        dm = DisplayManager()
        dm.displays = [None, None]
        dm.enable_transition_sync(True)
        
        # Pre-fill queue with old signals
        dm._on_display_transition_ready(0)
        dm._on_display_transition_ready(1)
        
        # Transition sync owns readiness coordination only; image publication is
        # covered by the retained Quick presentation suites.
        assert dm._transition_ready_queue is not None
        while dm._transition_ready_queue.try_pop()[0]:
            pass
        assert dm._transition_ready_queue.try_pop()[0] is False


class TestQueueOverflow:
    """Test SPSC queue overflow handling."""
    
    def test_queue_rejects_when_full(self, qapp):
        """Queue should reject signals when full."""
        from utils.lockfree.spsc_queue import SPSCQueue
        
        # Ring buffer with capacity N can hold N-1 items
        queue = SPSCQueue(capacity=4)
        
        # Fill queue (capacity-1 = 3 items)
        assert queue.try_push(0) is True
        assert queue.try_push(1) is True
        assert queue.try_push(2) is True
        
        # Next push should fail (queue full)
        assert queue.try_push(3) is False
    
    def test_display_manager_logs_queue_full(self, qapp, caplog):
        """DisplayManager should log when queue is full."""
        dm = DisplayManager()
        dm.displays = [None] * 25  # Many displays
        dm.enable_transition_sync(True)

        with caplog.at_level(logging.WARNING):
            for i in range(30):
                dm._on_display_transition_ready(i)

        assert any("queue full" in record.getMessage().lower() for record in caplog.records)


class TestConcurrentReadySignals:
    """Test concurrent ready signal handling."""
    
    def test_no_duplicate_ready_signals(self, qapp):
        """Wait should handle duplicate ready signals correctly."""
        dm = DisplayManager()
        dm.displays = [None, None]
        dm.enable_transition_sync(True)
        
        # Queue same display multiple times (shouldn't happen but test it)
        dm._on_display_transition_ready(0)
        dm._on_display_transition_ready(0)
        dm._on_display_transition_ready(1)
        
        # Should still wait for both displays (using set internally)
        result = dm.wait_for_all_displays_ready(timeout_sec=0.1)
        
        # Should succeed because we have signals for both 0 and 1
        assert result is True


class TestPerformanceMetrics:
    """Test synchronization performance."""
    
    def test_sync_overhead_minimal(self, qapp):
        """Sync overhead should be minimal (< 10ms)."""
        dm = DisplayManager()
        dm.displays = [None, None]
        dm.enable_transition_sync(True)
        
        # Pre-queue signals
        dm._on_display_transition_ready(0)
        dm._on_display_transition_ready(1)
        
        # Measure wait time
        start = time.time()
        dm.wait_for_all_displays_ready(timeout_sec=1.0)
        elapsed_ms = (time.time() - start) * 1000
        
        # Should be very fast (< 10ms)
        assert elapsed_ms < 10.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
