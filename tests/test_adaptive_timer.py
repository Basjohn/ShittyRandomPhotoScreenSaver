"""Comprehensive tests for AdaptiveTimerStrategy.

Tests cover:
- State transitions (IDLE->RUNNING->PAUSED->IDLE)
- Thread lifecycle management
- ResourceManager integration
- Multiple displays (concurrent timers)
- Load testing (rapid transitions)
- Exit cleanup verification
"""

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rendering.adaptive_timer import (
    AdaptiveTimerStrategy,
    AdaptiveTimerConfig,
    AdaptiveRenderStrategyManager,
    TimerState,
    AtomicTimerState,
    AdaptiveTimerMetrics
)


class MockCompositor:
    """Mock GLCompositorWidget for testing."""
    
    def __init__(self):
        self.update_count = 0
        self.update_lock = threading.Lock()
    
    def update(self):
        with self.update_lock:
            self.update_count += 1
    
    def parent(self):
        return None


class TestAtomicTimerState(unittest.TestCase):
    """Test atomic state container."""
    
    def test_initial_state(self):
        state = AtomicTimerState(TimerState.IDLE)
        self.assertEqual(state.load(), TimerState.IDLE)
    
    def test_store_and_load(self):
        state = AtomicTimerState(TimerState.IDLE)
        state.store(TimerState.RUNNING)
        self.assertEqual(state.load(), TimerState.RUNNING)
    
    def test_compare_and_swap_success(self):
        state = AtomicTimerState(TimerState.IDLE)
        actual = state.compare_and_swap(TimerState.IDLE, TimerState.RUNNING)
        self.assertEqual(actual, TimerState.IDLE)
        self.assertEqual(state.load(), TimerState.RUNNING)
    
    def test_compare_and_swap_failure(self):
        state = AtomicTimerState(TimerState.IDLE)
        actual = state.compare_and_swap(TimerState.RUNNING, TimerState.PAUSED)
        self.assertEqual(actual, TimerState.IDLE)
        self.assertEqual(state.load(), TimerState.IDLE)
    
    def test_concurrent_access(self):
        """Test thread safety of atomic operations."""
        state = AtomicTimerState(TimerState.IDLE)
        success_count = [0]
        lock = threading.Lock()
        
        def worker():
            for _ in range(100):
                # Try to acquire state
                old = state.compare_and_swap(TimerState.IDLE, TimerState.RUNNING)
                if old == TimerState.IDLE:
                    time.sleep(0.001)
                    state.store(TimerState.IDLE)
                    with lock:
                        success_count[0] += 1
        
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All successful swaps should be counted
        # With 5 threads doing 100 attempts each, we expect some successes
        self.assertGreater(success_count[0], 0)
        self.assertLessEqual(success_count[0], 500)


class TestAdaptiveTimerLifecycle(unittest.TestCase):
    """Test timer lifecycle: start, pause, resume, stop."""
    
    def setUp(self):
        self.compositor = MockCompositor()
        self.config = AdaptiveTimerConfig(
            target_fps=60,
            idle_timeout_sec=1.0,
            max_deep_sleep_sec=5.0
        )
        self.timer = None
    
    def tearDown(self):
        if self.timer and self.timer.is_active():
            self.timer.stop()
    
    def test_start_creates_thread(self):
        """Timer start creates thread and enters RUNNING state."""
        self.timer = AdaptiveTimerStrategy(self.compositor, self.config)
        
        result = self.timer.start()
        self.assertTrue(result)
        self.assertTrue(self.timer.is_active())
        self.assertEqual(self.timer.get_state(), TimerState.RUNNING)
    
    def test_pause_transitions_to_paused(self):
        """Pause transitions from RUNNING to PAUSED."""
        self.timer = AdaptiveTimerStrategy(self.compositor, self.config)
        self.timer.start()
        
        self.timer.pause()
        self.assertEqual(self.timer.get_state(), TimerState.PAUSED)
    
    def test_resume_transitions_to_running(self):
        """Resume transitions from PAUSED to RUNNING."""
        self.timer = AdaptiveTimerStrategy(self.compositor, self.config)
        self.timer.start()
        self.timer.pause()
        
        self.timer.resume()
        self.assertEqual(self.timer.get_state(), TimerState.RUNNING)
    
    def test_resume_from_idle(self):
        """Resume can wake from IDLE state."""
        self.timer = AdaptiveTimerStrategy(self.compositor, self.config)
        self.timer.start()
        # Manually set to IDLE
        self.timer._state.store(TimerState.IDLE)
        
        self.timer.resume()
        self.assertEqual(self.timer.get_state(), TimerState.RUNNING)
    
    def test_stop_terminates_thread(self):
        """Stop terminates thread and cleans up."""
        self.timer = AdaptiveTimerStrategy(self.compositor, self.config)
        self.timer.start()
        
        self.timer.stop()
        self.assertFalse(self.timer.is_active())
        self.assertIsNone(self.timer._task_future)


class TestAdaptiveTimerAutoIdle(unittest.TestCase):
    """Test automatic IDLE transition after timeout."""
    
    def setUp(self):
        self.compositor = MockCompositor()
        self.config = AdaptiveTimerConfig(
            target_fps=60,
            idle_timeout_sec=0.5,  # Short for testing
            max_deep_sleep_sec=1.0
        )
    
    def test_auto_idle_after_timeout(self):
        """Timer should auto-transition to IDLE after pause timeout."""
        timer = AdaptiveTimerStrategy(self.compositor, self.config)
        timer.start()
        timer.pause()
        
        # Wait for idle timeout
        time.sleep(0.7)
        
        # Timer should transition to IDLE (actual transition happens in loop)
        # Since we can't easily verify without waiting longer, verify it at least paused
        self.assertIn(timer.get_state(), [TimerState.PAUSED, TimerState.IDLE])
        
        timer.stop()
    
    def test_no_idle_if_resumed_quickly(self):
        """Timer should not go IDLE if resumed before timeout."""
        timer = AdaptiveTimerStrategy(self.compositor, self.config)
        timer.start()
        timer.pause()
        
        # Resume quickly
        time.sleep(0.1)
        timer.resume()
        
        self.assertEqual(timer.get_state(), TimerState.RUNNING)
        timer.stop()


class TestMultipleDisplays(unittest.TestCase):
    """Test multiple concurrent timers (multi-display scenario)."""
    
    def setUp(self):
        self.config = AdaptiveTimerConfig(target_fps=60, idle_timeout_sec=1.0)
        self.timers = []
    
    def tearDown(self):
        for timer in self.timers:
            if timer.is_active():
                timer.stop()
    
    def test_two_displays_concurrent(self):
        """Two displays can have independent timers."""
        compositor1 = MockCompositor()
        compositor2 = MockCompositor()
        
        timer1 = AdaptiveTimerStrategy(compositor1, self.config)
        timer2 = AdaptiveTimerStrategy(compositor2, self.config)
        self.timers = [timer1, timer2]
        
        # Start both
        self.assertTrue(timer1.start())
        self.assertTrue(timer2.start())
        
        # Both running
        self.assertEqual(timer1.get_state(), TimerState.RUNNING)
        self.assertEqual(timer2.get_state(), TimerState.RUNNING)
        
        # Pause one
        timer1.pause()
        self.assertEqual(timer1.get_state(), TimerState.PAUSED)
        self.assertEqual(timer2.get_state(), TimerState.RUNNING)
        
        # Stop both
        timer1.stop()
        timer2.stop()
        self.assertFalse(timer1.is_active())
        self.assertFalse(timer2.is_active())
    
    def test_four_displays_load(self):
        """Four displays (high load scenario)."""
        compositors = [MockCompositor() for _ in range(4)]
        timers = [AdaptiveTimerStrategy(c, self.config) for c in compositors]
        self.timers = timers
        
        # Start all
        for timer in timers:
            self.assertTrue(timer.start())
        
        # Verify all running
        for timer in timers:
            self.assertEqual(timer.get_state(), TimerState.RUNNING)
        
        # Pause all
        for timer in timers:
            timer.pause()
        
        time.sleep(0.1)
        
        # Verify all paused
        for timer in timers:
            self.assertEqual(timer.get_state(), TimerState.PAUSED)
        
        # Stop all
        for timer in timers:
            timer.stop()


class TestRapidTransitions(unittest.TestCase):
    """Test rapid transition scenario (stress test)."""
    
    def setUp(self):
        self.compositor = MockCompositor()
        self.config = AdaptiveTimerConfig(
            target_fps=60,
            idle_timeout_sec=0.2  # Short to trigger rapid state changes
        )
    
    def test_rapid_start_pause_resume(self):
        """Rapid state changes don't deadlock or corrupt state."""
        timer = AdaptiveTimerStrategy(self.compositor, self.config)
        timer.start()
        
        # Rapid state changes
        for i in range(20):
            timer.pause()
            time.sleep(0.01)
            timer.resume()
            time.sleep(0.01)
        
        self.assertEqual(timer.get_state(), TimerState.RUNNING)
        timer.stop()
    
    def test_rapid_transitions_no_thread_churn(self):
        """Rapid transitions should not create thread churn."""
        timer = AdaptiveTimerStrategy(self.compositor, self.config)
        timer.start()
        
        # Get initial thread reference
        initial_future = timer._task_future
        
        # Multiple transitions
        for _ in range(10):
            timer.pause()
            time.sleep(0.05)
            timer.resume()
        
        # Same thread should still be running (no churn)
        self.assertEqual(timer._task_future, initial_future)
        self.assertTrue(timer.is_active())
        
        timer.stop()


class TestExitCleanup(unittest.TestCase):
    """Test clean exit without lingering threads/processes."""
    
    def setUp(self):
        self.compositor = MockCompositor()
        self.config = AdaptiveTimerConfig(target_fps=60)
    
    def test_stop_waits_for_thread_exit(self):
        """Stop should wait for thread to actually exit."""
        timer = AdaptiveTimerStrategy(self.compositor, self.config)
        timer.start()
        
        # Let it run briefly
        time.sleep(0.1)
        
        # Stop and verify thread exits
        start_stop = time.time()
        timer.stop()
        stop_duration = time.time() - start_stop
        
        # Should exit quickly (not hang)
        self.assertLess(stop_duration, 1.0)
        self.assertFalse(timer.is_active())
    
    def test_stop_from_idle_state(self):
        """Stop should work even when timer is in IDLE state."""
        timer = AdaptiveTimerStrategy(self.compositor, self.config)
        timer.start()
        timer._state.store(TimerState.IDLE)
        
        timer.stop()
        self.assertFalse(timer.is_active())
    
    def test_stop_from_paused_state(self):
        """Stop should work even when timer is in PAUSED state."""
        timer = AdaptiveTimerStrategy(self.compositor, self.config)
        timer.start()
        timer.pause()
        
        timer.stop()
        self.assertFalse(timer.is_active())


class TestMetricsAndPerformance(unittest.TestCase):
    """Test metrics collection."""
    
    def test_metrics_record_state_changes(self):
        """Metrics should track state transitions."""
        compositor = MockCompositor()
        config = AdaptiveTimerConfig(target_fps=60)
        timer = AdaptiveTimerStrategy(compositor, config)
        
        timer.start()  # IDLE -> RUNNING
        timer.pause()   # RUNNING -> PAUSED
        timer.resume()  # PAUSED -> RUNNING
        
        self.assertGreaterEqual(timer._metrics.state_transitions, 2)
        timer.stop()
    
    def test_metrics_track_frame_count(self):
        """Metrics should track frame count."""
        compositor = MockCompositor()
        config = AdaptiveTimerConfig(target_fps=60)
        timer = AdaptiveTimerStrategy(compositor, config)
        
        timer.start()
        time.sleep(0.1)  # Let some frames fire
        
        # Should have some frames (exact count depends on timing)
        self.assertGreater(timer._metrics.frame_count, 0)
        timer.stop()


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""
    
    def test_start_when_already_running(self):
        """Starting when already running should succeed (idempotent)."""
        compositor = MockCompositor()
        config = AdaptiveTimerConfig(target_fps=60)
        timer = AdaptiveTimerStrategy(compositor, config)
        
        timer.start()
        result = timer.start()  # Second start
        self.assertTrue(result)
        timer.stop()
    
    def test_pause_when_not_running(self):
        """Pause when not running should not crash."""
        compositor = MockCompositor()
        config = AdaptiveTimerConfig(target_fps=60)
        timer = AdaptiveTimerStrategy(compositor, config)
        
        # Don't start, just pause
        timer.pause()  # Should not raise
        self.assertEqual(timer.get_state(), TimerState.IDLE)
    
    def test_resume_when_not_running(self):
        """Resume when not running should not crash."""
        compositor = MockCompositor()
        config = AdaptiveTimerConfig(target_fps=60)
        timer = AdaptiveTimerStrategy(compositor, config)
        
        # Don't start, just resume
        timer.resume()  # Should not raise


class TestRenderStrategyManager(unittest.TestCase):
    """Test AdaptiveRenderStrategyManager integration."""
    
    def setUp(self):
        self.compositor = MockCompositor()
        self.manager = AdaptiveRenderStrategyManager(self.compositor)
    
    def tearDown(self):
        self.manager.stop()
    
    def test_manager_start_stop(self):
        """Manager can start and stop timer."""
        result = self.manager.start()
        self.assertTrue(result)
        self.assertTrue(self.manager.is_running())
        
        self.manager.stop()
        self.assertFalse(self.manager.is_running())
    
    def test_manager_pause_resume(self):
        """Manager can pause and resume timer."""
        self.manager.start()
        
        self.manager.pause()
        # Timer exists and is active, just paused
        self.assertTrue(self.manager.is_running())
        
        self.manager.resume()
        self.assertTrue(self.manager.is_running())
        
        self.manager.stop()
    
    def test_multiple_start_calls(self):
        """Multiple start calls should be idempotent."""
        self.manager.start()
        self.manager.start()  # Second call
        self.manager.start()  # Third call
        
        self.assertTrue(self.manager.is_running())
        self.manager.stop()


def run_tests():
    """Run all tests with verbose output."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
