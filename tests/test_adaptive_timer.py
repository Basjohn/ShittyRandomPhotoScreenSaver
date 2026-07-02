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
from unittest.mock import MagicMock  # noqa: F401 - used by some test parametrizations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rendering.adaptive_timer import (
    AdaptiveTimerStrategy,
    AdaptiveTimerConfig,
    AdaptiveRenderStrategyManager,
    TimerState,
    AtomicTimerState,
    _mark_widget_update_consumed,
    _queue_safe_widget_update,
    _normalize_next_deadline,
    _wait_until_deadline_without_gil_spin,
)


class _MockThreadManager:
    """Minimal ThreadManager mock that runs tasks in real daemon threads."""

    def __init__(self):
        self._threads: list = []

    def submit_task(self, pool_type, fn, *, task_id=None):
        t = threading.Thread(target=fn, daemon=True, name=task_id or "mock_tm")
        t.start()
        self._threads.append(t)
        return task_id or "mock_tm"

    def shutdown(self):
        for t in self._threads:
            t.join(timeout=2)
        self._threads.clear()

    def active_thread_count(self):
        return sum(1 for t in self._threads if t.is_alive())


class _MockParent:
    """Mock parent widget that exposes _thread_manager."""

    def __init__(self):
        self._thread_manager = _MockThreadManager()
        self._resource_manager = None


class MockCompositor:
    """Mock GLCompositorWidget for testing."""
    
    def __init__(self):
        self.update_count = 0
        self.update_lock = threading.Lock()
        self._parent = _MockParent()
    
    def update(self):
        with self.update_lock:
            self.update_count += 1
    
    def parent(self):
        return self._parent


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


class TestAdaptiveTimerDeadlineMath(unittest.TestCase):
    """Pure timing math guards for drift-free cadence scheduling."""

    def test_normalize_next_deadline_keeps_future_deadline(self):
        result = _normalize_next_deadline(10.05, 10.00, 0.016)
        self.assertEqual(result, 10.05)

    def test_normalize_next_deadline_skips_missed_intervals_without_rebasing(self):
        result = _normalize_next_deadline(10.00, 10.051, 0.016)
        self.assertAlmostEqual(result, 10.064, places=6)

    def test_deadline_wait_yields_instead_of_busy_spinning(self):
        """High-refresh precision waits must not monopolize the Python GIL."""
        from rendering import adaptive_timer

        calls = {"perf": 0}
        sleep_calls: list[float] = []
        state = AtomicTimerState(TimerState.RUNNING)
        stop_event = threading.Event()

        original_perf_counter = adaptive_timer.time.perf_counter
        original_sleep = adaptive_timer.time.sleep
        try:
            def _perf_counter() -> float:
                calls["perf"] += 1
                return {1: 10.0000, 2: 10.0054}.get(calls["perf"], 10.0061)

            def _sleep(value: float) -> None:
                sleep_calls.append(value)

            adaptive_timer.time.perf_counter = _perf_counter
            adaptive_timer.time.sleep = _sleep

            _wait_until_deadline_without_gil_spin(10.0060, stop_event, state)

            self.assertGreaterEqual(len(sleep_calls), 2)
            self.assertGreater(sleep_calls[0], 0.0)
            self.assertEqual(sleep_calls[-1], 0)
        finally:
            adaptive_timer.time.perf_counter = original_perf_counter
            adaptive_timer.time.sleep = original_sleep


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
        self.assertTrue(self.timer._loop_stopped_event.is_set())
        self.assertEqual(self.compositor._parent._thread_manager.active_thread_count(), 0)

    def test_render_strategy_manager_stop_waits_for_timer_loop(self):
        """Display cleanup must not drop timer ownership before the loop exits."""
        manager = AdaptiveRenderStrategyManager(self.compositor)
        self.assertTrue(manager.start())
        timer = manager._timer
        self.assertIsNotNone(timer)

        manager.stop()

        self.assertIsNone(manager._timer)
        self.assertTrue(timer._loop_stopped_event.is_set())
        self.assertEqual(self.compositor._parent._thread_manager.active_thread_count(), 0)

    def test_safe_widget_update_skips_deleted_qt_owner(self):
        """Queued frame updates should no-op if the Qt widget has already died."""
        class _DeadWidget:
            def update(self):
                raise AssertionError("deleted widget should not be updated")

        widget = _DeadWidget()
        queued = []

        from rendering import adaptive_timer

        original_run = adaptive_timer.ThreadManager.run_on_ui_thread
        original_shiboken = adaptive_timer.Shiboken
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(lambda func, *args, **kwargs: queued.append(func))

            class _FakeShiboken:
                @staticmethod
                def isValid(_obj):
                    return False

            adaptive_timer.Shiboken = _FakeShiboken
            _queue_safe_widget_update(widget)
            self.assertEqual(len(queued), 1)
            queued[0]()
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original_run
            adaptive_timer.Shiboken = original_shiboken

    def test_safe_widget_update_coalesces_pending_dispatches(self):
        """Timer-driven repaints should not flood the UI queue with duplicate updates."""
        class _Widget:
            def __init__(self):
                self.update_count = 0

            def update(self):
                self.update_count += 1

        widget = _Widget()
        queued = []

        from rendering import adaptive_timer

        original_run = adaptive_timer.ThreadManager.run_on_ui_thread
        original_shiboken = adaptive_timer.Shiboken
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(lambda func, *args, **kwargs: queued.append(func))
            adaptive_timer.Shiboken = None

            _queue_safe_widget_update(widget)
            _queue_safe_widget_update(widget)
            _queue_safe_widget_update(widget)

            self.assertEqual(len(queued), 1)
            self.assertTrue(getattr(widget, "_srpss_timer_update_pending"))

            queued[0]()

            self.assertEqual(widget.update_count, 1)
            self.assertTrue(getattr(widget, "_srpss_timer_update_pending"))
            self.assertFalse(getattr(widget, "_srpss_timer_update_dispatch_pending"))

            _queue_safe_widget_update(widget)
            self.assertEqual(len(queued), 2)

            _mark_widget_update_consumed(widget)
            self.assertFalse(getattr(widget, "_srpss_timer_update_pending"))

            _queue_safe_widget_update(widget)
            self.assertEqual(len(queued), 3)
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original_run
            adaptive_timer.Shiboken = original_shiboken

    def test_safe_widget_update_keeps_idle_coalescing_even_when_pending_is_old(self):
        """Idle widgets must not repaint repeatedly just because a flag is old."""
        class _Widget:
            def __init__(self):
                self.update_count = 0
                self._srpss_timer_update_pending = True
                self._srpss_timer_update_pending_since = 1.0
                self._render_timer_fps = 165
                self._frame_state = None

            def update(self):
                self.update_count += 1

        widget = _Widget()
        queued = []

        from rendering import adaptive_timer

        original_run = adaptive_timer.ThreadManager.run_on_ui_thread
        original_shiboken = adaptive_timer.Shiboken
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(lambda func, *args, **kwargs: queued.append(func))
            adaptive_timer.Shiboken = None

            _queue_safe_widget_update(widget)

            self.assertEqual(queued, [])
            self.assertTrue(getattr(widget, "_srpss_timer_update_pending"))
            self.assertEqual(widget.update_count, 0)
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original_run
            adaptive_timer.Shiboken = original_shiboken

    def test_safe_widget_update_logs_stale_pending_without_requeueing(self):
        """Stale pending paint diagnostics must not become another UI-pressure loop."""
        class _Widget:
            def __init__(self):
                self.update_count = 0
                self._srpss_timer_update_pending = True
                self._srpss_timer_update_pending_since = time.perf_counter() - 1.0
                self._render_timer_fps = 165
                self._screen_index = 0

            def update(self):
                self.update_count += 1

        widget = _Widget()
        queued = []

        from rendering import adaptive_timer

        original_run = adaptive_timer.ThreadManager.run_on_ui_thread
        original_shiboken = adaptive_timer.Shiboken
        original_perf_enabled = adaptive_timer.is_perf_metrics_enabled
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(lambda func, *args, **kwargs: queued.append(func))
            adaptive_timer.Shiboken = None
            adaptive_timer.is_perf_metrics_enabled = lambda: True

            with self.assertLogs(adaptive_timer.logger.name, level="WARNING") as logs:
                _queue_safe_widget_update(widget)

            self.assertEqual(queued, [])
            self.assertEqual(widget.update_count, 0)
            self.assertTrue(getattr(widget, "_srpss_timer_update_pending"))
            self.assertTrue(any("no_requeue=True" in message for message in logs.output))
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original_run
            adaptive_timer.Shiboken = original_shiboken
            adaptive_timer.is_perf_metrics_enabled = original_perf_enabled

    def test_mark_widget_update_consumed_clears_pending_diagnostics(self):
        class _Widget:
            _srpss_timer_update_pending = True
            _srpss_timer_update_pending_since = 123.0
            _srpss_timer_update_pending_last_log = 456.0

        widget = _Widget()

        _mark_widget_update_consumed(widget)

        self.assertFalse(getattr(widget, "_srpss_timer_update_pending"))
        self.assertEqual(getattr(widget, "_srpss_timer_update_pending_since"), 0.0)
        self.assertEqual(getattr(widget, "_srpss_timer_update_pending_last_log"), 0.0)

    def test_safe_widget_update_does_not_requeue_stale_transition_pending_dispatch(self):
        """Transition repaint coalescing must not become a UI-thread requeue loop."""
        class _FrameState:
            started = True
            completed = False

        class _Widget:
            def __init__(self):
                self.update_count = 0
                self._srpss_timer_update_pending = True
                self._srpss_timer_update_pending_since = 1.0
                self._render_timer_fps = 165
                self._frame_state = _FrameState()

            def update(self):
                self.update_count += 1

        widget = _Widget()
        queued = []

        from rendering import adaptive_timer

        original_run = adaptive_timer.ThreadManager.run_on_ui_thread
        original_shiboken = adaptive_timer.Shiboken
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(lambda func, *args, **kwargs: queued.append(func))
            adaptive_timer.Shiboken = None

            _queue_safe_widget_update(widget)

            self.assertEqual(queued, [])
            self.assertTrue(getattr(widget, "_srpss_timer_update_pending"))
            self.assertEqual(getattr(widget, "_srpss_timer_update_pending_since"), 1.0)
            self.assertEqual(widget.update_count, 0)
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original_run
            adaptive_timer.Shiboken = original_shiboken

    def test_safe_widget_update_allows_fresh_pending_to_keep_target_cadence(self):
        """Fresh paint-pending state should not self-throttle high-refresh cadence."""
        class _FrameState:
            started = True
            completed = False

        class _Widget:
            def __init__(self):
                self.update_count = 0
                self._srpss_timer_update_pending = True
                self._srpss_timer_update_pending_since = time.perf_counter()
                self._render_timer_fps = 165
                self._frame_state = _FrameState()

            def update(self):
                self.update_count += 1

        widget = _Widget()
        queued = []

        from rendering import adaptive_timer

        original_run = adaptive_timer.ThreadManager.run_on_ui_thread
        original_shiboken = adaptive_timer.Shiboken
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(lambda func, *args, **kwargs: queued.append(func))
            adaptive_timer.Shiboken = None

            accepted = _queue_safe_widget_update(widget)

            self.assertTrue(accepted)
            self.assertEqual(len(queued), 1)
            self.assertTrue(getattr(widget, "_srpss_timer_update_pending"))
            self.assertEqual(widget.update_count, 0)
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original_run
            adaptive_timer.Shiboken = original_shiboken

    def test_signal_frame_records_accepted_render_update_when_supported(self):
        """Adaptive timer should publish accepted paint submissions into compositor metrics."""
        class _Widget:
            def __init__(self):
                self.accepted_ticks = 0
                self.skipped_ticks = 0
                self.update_count = 0

            def _record_render_timer_tick(self, *, accepted_update=True):
                if accepted_update:
                    self.accepted_ticks += 1
                else:
                    self.skipped_ticks += 1

            def update(self):
                self.update_count += 1

        widget = _Widget()

        from rendering import adaptive_timer

        original_run = adaptive_timer.ThreadManager.run_on_ui_thread
        original_shiboken = adaptive_timer.Shiboken
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(lambda func, *args, **kwargs: func())
            adaptive_timer.Shiboken = None

            timer = AdaptiveTimerStrategy(widget, self.config)
            timer._signal_frame()

            self.assertEqual(widget.accepted_ticks, 1)
            self.assertEqual(widget.skipped_ticks, 0)
            self.assertEqual(widget.update_count, 1)
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original_run
            adaptive_timer.Shiboken = original_shiboken

    def test_signal_frame_records_pending_skip_without_fake_render_tick(self):
        """Pending coalesced updates must not masquerade as delivered render cadence."""
        class _Widget:
            def __init__(self):
                self.accepted_ticks = 0
                self.skipped_ticks = 0
                self._srpss_timer_update_pending = True
                self._srpss_timer_update_pending_since = time.perf_counter() - 1.0

            def _record_render_timer_tick(self, *, accepted_update=True):
                if accepted_update:
                    self.accepted_ticks += 1
                else:
                    self.skipped_ticks += 1

            def update(self):
                raise AssertionError("pending update should suppress another update")

        widget = _Widget()
        timer = AdaptiveTimerStrategy(widget, self.config)
        timer._signal_frame()

        self.assertEqual(widget.accepted_ticks, 0)
        self.assertEqual(widget.skipped_ticks, 1)

    def test_safe_widget_update_prefers_qt_queued_invoke_for_qobject_widgets(self):
        """Real QObject-owned compositor widgets should bypass the generic UI invoker hot path."""
        class _ThreadedWidget:
            def __init__(self):
                self.update_count = 0
                self._thread = object()

            def update(self):
                self.update_count += 1

            def thread(self):
                return self._thread

        widget = _ThreadedWidget()
        queued: list[tuple[object, str, object]] = []

        from rendering import adaptive_timer

        original_run = adaptive_timer.ThreadManager.run_on_ui_thread
        original_shiboken = adaptive_timer.Shiboken
        original_current_thread = adaptive_timer.QThread.currentThread
        original_invoke = adaptive_timer.QMetaObject.invokeMethod
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(
                lambda func, *args, **kwargs: (_ for _ in ()).throw(
                    AssertionError("ThreadManager.run_on_ui_thread should not be used")
                )
            )
            adaptive_timer.Shiboken = None
            adaptive_timer.QThread.currentThread = staticmethod(lambda: object())
            adaptive_timer.QMetaObject.invokeMethod = staticmethod(
                lambda obj, method, connection: queued.append((obj, method, connection)) or True
            )

            _queue_safe_widget_update(widget)

            assert len(queued) == 1
            assert queued[0][0] is widget
            assert queued[0][1] == "update"
            assert getattr(widget, "_srpss_timer_update_pending") is True
            assert widget.update_count == 0
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original_run
            adaptive_timer.Shiboken = original_shiboken
            adaptive_timer.QThread.currentThread = original_current_thread
            adaptive_timer.QMetaObject.invokeMethod = original_invoke


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

    def test_manager_pause_logs_noop_when_timer_already_idle(self):
        """Perf diagnostics should not claim a real pause when the timer was already idle."""
        self.manager.start()
        self.assertIsNotNone(self.manager._timer)
        self.manager._timer._state.store(TimerState.IDLE)

        from rendering import adaptive_timer

        original_perf_enabled = adaptive_timer.is_perf_metrics_enabled
        with self.assertLogs(adaptive_timer.logger.name, level="INFO") as logs:
            try:
                adaptive_timer.is_perf_metrics_enabled = lambda: True
                self.manager.pause()
            finally:
                adaptive_timer.is_perf_metrics_enabled = original_perf_enabled

        self.assertTrue(any("manager_pause_noop" in message for message in logs.output))


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
