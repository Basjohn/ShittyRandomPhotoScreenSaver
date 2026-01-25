"""
Tests for ThreadManager Phase 0.2 enhancements.

Verifies:
- inspect_queues() returns queue statistics including drop counts
- single_shot_ui() respects QApplication lifecycle
- Queue drop threshold warnings are emitted
"""
from unittest import mock

from PySide6.QtCore import QTimer


class TestInspectQueues:
    """Test inspect_queues() method."""

    def test_inspect_queues_returns_dict(self, qtbot):
        """inspect_queues() should return a dict with pool stats."""
        from core.threading.manager import ThreadManager
        
        tm = ThreadManager()
        try:
            result = tm.inspect_queues()
            
            assert isinstance(result, dict)
            assert 'io' in result
            assert 'compute' in result
            assert 'mutation_queue' in result
            
            # Each pool should have dropped and pending keys
            for pool_name, stats in result.items():
                assert 'dropped' in stats, f"Pool {pool_name} missing 'dropped' key"
                assert 'pending' in stats, f"Pool {pool_name} missing 'pending' key"
                assert isinstance(stats['dropped'], int)
                assert isinstance(stats['pending'], int)
        finally:
            tm.shutdown()

    def test_inspect_queues_tracks_mutation_drops(self, qtbot):
        """inspect_queues() should track mutation queue drops."""
        from core.threading.manager import ThreadManager
        
        tm = ThreadManager()
        try:
            # Manually increment drop counter to simulate drops
            tm._queue_drops = 5
            
            result = tm.inspect_queues()
            assert result['mutation_queue']['dropped'] == 5
        finally:
            tm.shutdown()


class TestSingleShotUI:
    """Test single_shot_ui() method."""

    def test_single_shot_ui_returns_timer(self, qtbot):
        """single_shot_ui() should return a QTimer instance."""
        from core.threading.manager import ThreadManager
        
        tm = ThreadManager()
        try:
            called = [False]
            def callback():
                called[0] = True
            
            timer = tm.single_shot_ui(10, callback)
            
            assert timer is not None
            assert isinstance(timer, QTimer)
            
            # Wait for timer to fire
            qtbot.wait(50)
            assert called[0], "Callback was not invoked"
        finally:
            tm.shutdown()

    def test_single_shot_ui_cancellable(self, qtbot):
        """single_shot_ui() timer can be stopped to cancel."""
        from core.threading.manager import ThreadManager
        
        tm = ThreadManager()
        try:
            called = [False]
            def callback():
                called[0] = True
            
            timer = tm.single_shot_ui(100, callback)
            assert timer is not None
            
            # Stop timer before it fires
            timer.stop()
            
            # Wait past the delay
            qtbot.wait(150)
            assert not called[0], "Callback should not have been invoked after stop()"
        finally:
            tm.shutdown()

    def test_single_shot_ui_without_app_returns_none(self):
        """single_shot_ui() should return None without QCoreApplication."""
        from core.threading.manager import ThreadManager
        
        # Create ThreadManager without Qt app context
        tm = ThreadManager()
        try:
            # Mock QCoreApplication.instance() to return None
            with mock.patch('core.threading.manager.QCoreApplication.instance', return_value=None):
                result = tm.single_shot_ui(10, lambda: None)
                assert result is None
        finally:
            tm.shutdown(wait=False)

    def test_single_shot_ui_tracked_in_pending_list(self, qtbot):
        """single_shot_ui() should track timer in _pending_single_shots."""
        from core.threading.manager import ThreadManager
        
        tm = ThreadManager()
        try:
            timer = tm.single_shot_ui(1000, lambda: None)  # Long delay
            
            assert timer is not None
            assert timer in tm._pending_single_shots
            
            # Stop and verify removal
            timer.stop()
            qtbot.wait(10)  # Allow cleanup
        finally:
            tm.shutdown()


class TestDropThreshold:
    """Test queue drop threshold warning."""

    def test_drop_threshold_warning(self, qtbot, caplog):
        """Should warn when drops exceed threshold."""
        from core.threading.manager import ThreadManager
        import logging
        
        tm = ThreadManager()
        try:
            # Set up to trigger warning
            tm._queue_drops = 10
            tm._queue_drops_last_warn = 0.0  # Reset to allow warning
            
            with caplog.at_level(logging.WARNING):
                tm._check_drop_threshold()
            
            # Check warning was logged
            assert any(
                "Queue drops exceeded threshold" in record.message
                for record in caplog.records
            ), "Expected drop threshold warning not found"
        finally:
            tm.shutdown()

    def test_drop_threshold_rate_limited(self, qtbot):
        """Drop warnings should be rate-limited to once per minute."""
        from core.threading.manager import ThreadManager
        
        tm = ThreadManager()
        try:
            # First warning
            tm._queue_drops = 15
            tm._queue_drops_last_warn = 0.0
            tm._check_drop_threshold()
            
            # Counter should be reset after warning
            assert tm._queue_drops == 0
            
            # Set drops again
            tm._queue_drops = 15
            
            # Should not warn again (rate limited)
            tm._check_drop_threshold()
            
            # Counter should not be reset (warning was suppressed)
            assert tm._queue_drops == 15
        finally:
            tm.shutdown()


class TestUIInvokerRegistration:
    """Test UI invoker ResourceManager registration."""

    def test_ui_invoker_registered_with_resource_manager(self, qtbot):
        """_ensure_ui_invoker should register with ResourceManager when provided."""
        from core.threading.manager import _ensure_ui_invoker, _UiInvoker
        from core.threading import manager as tm_module
        from core.resources.manager import ResourceManager
        
        # Reset global state for test
        tm_module._ui_invoker = None
        tm_module._ui_invoker_registered = False
        
        rm = ResourceManager()
        try:
            inv = _ensure_ui_invoker(resource_manager=rm)
            
            assert inv is not None
            assert isinstance(inv, _UiInvoker)
            assert tm_module._ui_invoker_registered is True
        finally:
            rm.cleanup_all()
            # Reset global state
            tm_module._ui_invoker = None
            tm_module._ui_invoker_registered = False
