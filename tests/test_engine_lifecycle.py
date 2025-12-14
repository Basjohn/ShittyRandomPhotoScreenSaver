"""
Test engine lifecycle state transitions.

This test module verifies the EngineState enum and state transitions
that were introduced to fix the RSS reload bug where async RSS loading
would abort after settings changes.

Key scenarios tested:
1. State transitions follow valid paths
2. _shutting_down property returns correct values for each state
3. Settings changes use REINITIALIZING (not STOPPING)
4. Async RSS loading continues during REINITIALIZING
5. Actual shutdown properly aborts async tasks
"""
import pytest
import threading
from unittest.mock import patch

# Import the engine and state enum
from engine.screensaver_engine import ScreensaverEngine, EngineState


class TestEngineState:
    """Test EngineState enum and state properties."""
    
    def test_engine_state_enum_values(self):
        """Verify all expected states exist."""
        expected_states = [
            'UNINITIALIZED',
            'INITIALIZING', 
            'STOPPED',
            'STARTING',
            'RUNNING',
            'STOPPING',
            'REINITIALIZING',
            'SHUTTING_DOWN',
        ]
        actual_states = [s.name for s in EngineState]
        for expected in expected_states:
            assert expected in actual_states, f"Missing state: {expected}"
    
    def test_initial_state_is_uninitialized(self):
        """Engine should start in UNINITIALIZED state."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            assert engine._get_state() == EngineState.UNINITIALIZED
    
    def test_running_property_false_when_not_running(self):
        """_running property should be False when not in RUNNING state."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            # Initial state
            assert engine._running == False
            
            # Manually set various non-running states
            engine._state = EngineState.STOPPED
            assert engine._running == False
            
            engine._state = EngineState.STOPPING
            assert engine._running == False
            
            engine._state = EngineState.SHUTTING_DOWN
            assert engine._running == False
    
    def test_running_property_true_when_running(self):
        """_running property should be True only in RUNNING state."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            engine._state = EngineState.RUNNING
            assert engine._running == True
    
    def test_initialized_property(self):
        """_initialized property should reflect initialization state."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            
            # Not initialized in UNINITIALIZED
            engine._state = EngineState.UNINITIALIZED
            assert engine._initialized == False
            
            # Not initialized during INITIALIZING
            engine._state = EngineState.INITIALIZING
            assert engine._initialized == False
            
            # Initialized after STOPPED
            engine._state = EngineState.STOPPED
            assert engine._initialized == True
            
            # Initialized in RUNNING
            engine._state = EngineState.RUNNING
            assert engine._initialized == True


class TestShuttingDownProperty:
    """Test the critical _shutting_down property that controls async task abortion."""
    
    def test_shutting_down_false_in_running(self):
        """_shutting_down should be False when RUNNING."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            engine._state = EngineState.RUNNING
            assert engine._shutting_down == False
    
    def test_shutting_down_false_in_reinitializing(self):
        """CRITICAL: _shutting_down should be False when REINITIALIZING.
        
        This is the key fix for the RSS reload bug. When settings change,
        the engine enters REINITIALIZING state, and async RSS loading
        should continue (not abort).
        """
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            engine._state = EngineState.REINITIALIZING
            assert engine._shutting_down == False, \
                "REINITIALIZING should NOT trigger _shutting_down - this was the RSS bug!"
    
    def test_shutting_down_true_in_stopping(self):
        """_shutting_down should be True when STOPPING."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            engine._state = EngineState.STOPPING
            assert engine._shutting_down == True
    
    def test_shutting_down_true_in_shutting_down(self):
        """_shutting_down should be True when SHUTTING_DOWN."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            engine._state = EngineState.SHUTTING_DOWN
            assert engine._shutting_down == True
    
    def test_shutting_down_false_in_other_states(self):
        """_shutting_down should be False in non-shutdown states."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            
            non_shutdown_states = [
                EngineState.UNINITIALIZED,
                EngineState.INITIALIZING,
                EngineState.STOPPED,
                EngineState.STARTING,
                EngineState.RUNNING,
                EngineState.REINITIALIZING,
            ]
            
            for state in non_shutdown_states:
                engine._state = state
                assert engine._shutting_down == False, \
                    f"_shutting_down should be False in {state.name}"


class TestStateTransitions:
    """Test state transition validation and logging."""
    
    def test_transition_state_success(self):
        """Valid state transitions should succeed."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            
            # UNINITIALIZED -> INITIALIZING
            result = engine._transition_state(
                EngineState.INITIALIZING,
                expected_from=[EngineState.UNINITIALIZED]
            )
            assert result == True
            assert engine._get_state() == EngineState.INITIALIZING
    
    def test_transition_state_invalid_source(self):
        """Invalid source state should fail transition."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            engine._state = EngineState.RUNNING
            
            # Try to transition from RUNNING to INITIALIZING (invalid)
            result = engine._transition_state(
                EngineState.INITIALIZING,
                expected_from=[EngineState.UNINITIALIZED]
            )
            assert result == False
            assert engine._get_state() == EngineState.RUNNING  # State unchanged
    
    def test_transition_from_shutting_down_blocked(self):
        """Cannot transition out of SHUTTING_DOWN (terminal state)."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            engine._state = EngineState.SHUTTING_DOWN
            
            # Try to transition to STOPPED
            result = engine._transition_state(EngineState.STOPPED)
            assert result == False
            assert engine._get_state() == EngineState.SHUTTING_DOWN
    
    def test_transition_without_expected_from(self):
        """Transition without expected_from should always succeed (except from terminal)."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            engine._state = EngineState.RUNNING
            
            result = engine._transition_state(EngineState.STOPPING)
            assert result == True
            assert engine._get_state() == EngineState.STOPPING
    
    def test_is_state_check(self):
        """_is_state should correctly check multiple states."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            engine._state = EngineState.RUNNING
            
            assert engine._is_state(EngineState.RUNNING) == True
            assert engine._is_state(EngineState.STOPPED) == False
            assert engine._is_state(EngineState.RUNNING, EngineState.STOPPED) == True
            assert engine._is_state(EngineState.STOPPED, EngineState.STARTING) == False


class TestStateTransitionThreadSafety:
    """Test thread safety of state transitions."""
    
    def test_concurrent_state_reads(self):
        """Multiple threads should safely read state."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            engine._state = EngineState.RUNNING
            
            results = []
            errors = []
            
            def read_state():
                try:
                    for _ in range(100):
                        state = engine._get_state()
                        results.append(state)
                except Exception as e:
                    errors.append(e)
            
            threads = [threading.Thread(target=read_state) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            
            assert len(errors) == 0, f"Errors during concurrent reads: {errors}"
            assert len(results) == 500
    
    def test_concurrent_state_transitions(self):
        """State transitions should be atomic."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            engine._state = EngineState.RUNNING
            
            transition_count = [0]
            errors = []
            
            def toggle_state():
                try:
                    for _ in range(50):
                        # Try to transition - may fail if another thread changed state
                        if engine._is_state(EngineState.RUNNING):
                            engine._transition_state(EngineState.REINITIALIZING)
                        elif engine._is_state(EngineState.REINITIALIZING):
                            engine._transition_state(EngineState.RUNNING)
                        transition_count[0] += 1
                except Exception as e:
                    errors.append(e)
            
            threads = [threading.Thread(target=toggle_state) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            
            assert len(errors) == 0, f"Errors during concurrent transitions: {errors}"
            # State should be one of the valid states
            assert engine._get_state() in (EngineState.RUNNING, EngineState.REINITIALIZING)


class TestRSSReloadBugScenario:
    """Test the specific scenario that caused the RSS reload bug."""
    
    def test_settings_change_does_not_abort_rss(self):
        """Simulates the bug scenario: settings change should not abort RSS loading.
        
        Bug scenario:
        1. Engine is RUNNING
        2. User opens settings, changes sources
        3. _on_sources_changed() is called
        4. Async RSS loading checks _shutting_down
        5. BUG: _shutting_down was True, aborting RSS loading
        6. FIX: _shutting_down should be False during REINITIALIZING
        """
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            engine._state = EngineState.RUNNING
            
            # Simulate what _on_sources_changed does
            was_running = engine._running
            assert was_running == True
            
            # Transition to REINITIALIZING
            engine._transition_state(EngineState.REINITIALIZING)
            
            # CRITICAL CHECK: _shutting_down should be False
            assert engine._shutting_down == False, \
                "RSS loading would abort here in the buggy version!"
            
            # Simulate async RSS task checking shutdown
            def should_continue():
                return not engine._shutting_down
            
            assert should_continue() == True, \
                "Async RSS task should continue during REINITIALIZING"
            
            # Restore to RUNNING
            engine._transition_state(EngineState.RUNNING)
            assert engine._running == True
    
    def test_actual_shutdown_aborts_rss(self):
        """Actual shutdown should abort RSS loading."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            engine._state = EngineState.RUNNING
            
            # Transition to SHUTTING_DOWN (actual exit)
            engine._transition_state(EngineState.SHUTTING_DOWN)
            
            # _shutting_down should be True
            assert engine._shutting_down == True
            
            # Async RSS task should abort
            def should_continue():
                return not engine._shutting_down
            
            assert should_continue() == False, \
                "Async RSS task should abort during SHUTTING_DOWN"


class TestGetStats:
    """Test engine statistics include state information."""
    
    def test_get_stats_includes_state(self):
        """get_stats should include current state."""
        with patch('engine.screensaver_engine.logger'):
            engine = ScreensaverEngine()
            engine._state = EngineState.RUNNING
            
            stats = engine.get_stats()
            
            assert 'state' in stats
            assert stats['state'] == 'RUNNING'
            assert 'running' in stats
            assert stats['running'] == True
            assert 'shutting_down' in stats
            assert stats['shutting_down'] == False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
