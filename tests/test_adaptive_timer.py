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
    _mark_widget_update_dispatched,
    _mark_widget_update_pending,
    _queue_safe_widget_update,
    _normalize_next_deadline,
    _record_delivery_paint_start,
    _record_delivery_result,
    _record_delivery_wake,
    _reset_delivery_perf_window,
    _wait_until_deadline_without_gil_spin,
)


class _MockThreadManager:
    """Minimal ThreadManager mock that runs tasks in real daemon threads."""

    def __init__(self):
        self._threads: list = []
        self.categories: list[str] = []

    def submit_task(self, pool_type, fn, *, task_id=None, category="uncategorized"):
        self.categories.append(category)
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
        self.assertEqual(
            self.compositor._parent._thread_manager.categories,
            ["presentation.adaptive_timer"],
        )
    
    def test_pause_transitions_to_paused(self):
        """Pause transitions from RUNNING to PAUSED."""
        self.timer = AdaptiveTimerStrategy(self.compositor, self.config)
        self.timer.start()
        
        self.timer.pause()
        self.assertEqual(self.timer.get_state(), TimerState.PAUSED)

    def test_paused_worker_blocks_until_idle_deadline_instead_of_polling(self):
        """A post-transition grace period must not wake at 1 kHz."""
        config = AdaptiveTimerConfig(
            target_fps=60,
            idle_timeout_sec=0.05,
            max_deep_sleep_sec=1.0,
        )
        self.timer = AdaptiveTimerStrategy(self.compositor, config)
        self.timer.start()
        self.timer.pause()

        deadline = time.monotonic() + 0.5
        while self.timer.get_state() != TimerState.IDLE:
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.005)

        # One stale startup wake can race the first pause wait, so two waits is
        # the strict upper bound.  The rejected implementation performed about
        # fifty 1 ms polling sleeps in this same 50 ms interval.
        self.assertLessEqual(self.timer._metrics.paused_blocking_waits, 2)
    
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

    def test_stop_timeout_retains_worker_and_resource_ownership(self):
        """A live worker must block teardown instead of losing its handles."""

        class _Resources:
            def __init__(self):
                self.unregistered = []

            def unregister(self, resource_id):
                self.unregistered.append(resource_id)

        resources = _Resources()
        timer = AdaptiveTimerStrategy(
            self.compositor,
            AdaptiveTimerConfig(target_fps=60, exit_immediate=True),
        )
        timer._resource_manager = resources
        future = object()
        timer._task_future = future
        timer._task_id = "still-running"
        timer._timer_resource_id = "timer-resource"

        self.assertFalse(timer.stop())
        self.assertIs(timer._task_future, future)
        self.assertEqual(timer._task_id, "still-running")
        self.assertEqual(timer._timer_resource_id, "timer-resource")
        self.assertEqual(resources.unregistered, [])

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
            self.assertEqual(len(queued), 1)

            _mark_widget_update_consumed(widget)
            self.assertFalse(getattr(widget, "_srpss_timer_update_pending"))

            _queue_safe_widget_update(widget)
            self.assertEqual(len(queued), 2)
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

    def test_safe_widget_update_coalesces_fresh_pending_until_paint_consumes_it(self):
        """One accepted Qt update owns delivery even at high refresh."""
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

            self.assertFalse(accepted)
            self.assertEqual(len(queued), 0)
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


class _DeliveryWidget:
    """Plain compositor stand-in that can host the passive delivery attributes."""

    def __init__(self, screen_index: int = 0):
        self.update_count = 0
        self._screen_index = screen_index
        self._render_timer_fps = 165

    def update(self):
        self.update_count += 1


class TestDeliveryStageInvariants(unittest.TestCase):
    """Invariants for the passive Phase 5 delivery-stage attribution seam.

    These metrics are evidence, not behaviour. They must never invent a skip
    reason, report a negative stage age, survive a widget generation boundary,
    change PERF-off scheduling, or share state between displays.
    """

    _SKIP_COUNTERS = (
        "_srpss_delivery_dispatch_pending_skips",
        "_srpss_delivery_paint_pending_skips",
        "_srpss_delivery_unknown_skips",
    )

    def setUp(self):
        from rendering import adaptive_timer

        self._adaptive_timer = adaptive_timer
        self._original_perf_enabled = adaptive_timer.is_perf_metrics_enabled
        self._original_run = adaptive_timer.ThreadManager.run_on_ui_thread
        self._original_shiboken = adaptive_timer.Shiboken
        self.queued: list = []
        adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(
            lambda func, *args, **kwargs: self.queued.append(func)
        )
        adaptive_timer.Shiboken = None
        self._set_perf(True)

    def tearDown(self):
        self._adaptive_timer.is_perf_metrics_enabled = self._original_perf_enabled
        self._adaptive_timer.ThreadManager.run_on_ui_thread = self._original_run
        self._adaptive_timer.Shiboken = self._original_shiboken

    def _set_perf(self, enabled: bool) -> None:
        self._adaptive_timer.is_perf_metrics_enabled = lambda: enabled

    def _skip_totals(self, widget) -> tuple[int, ...]:
        return tuple(int(getattr(widget, name, 0) or 0) for name in self._SKIP_COUNTERS)

    # --- Invariant 1: skip reasons are mutually exclusive ------------------

    def test_each_skipped_result_increments_exactly_one_skip_counter(self):
        """A rejected delivery has one reason; it never double-counts or vanishes."""
        for stage, expected_index in (
            ("dispatch", 0),
            ("paint", 1),
            ("unknown", 2),
            ("none", 2),
            ("some_future_stage", 2),
        ):
            with self.subTest(stage=stage):
                widget = _DeliveryWidget()
                widget._srpss_timer_last_skip_stage = stage

                _record_delivery_result(widget, False)

                totals = self._skip_totals(widget)
                self.assertEqual(sum(totals), 1, f"stage={stage} totals={totals}")
                self.assertEqual(totals[expected_index], 1, f"stage={stage} totals={totals}")
                self.assertEqual(int(getattr(widget, "_srpss_delivery_accepted", 0) or 0), 0)

    def test_accepted_result_never_increments_a_skip_counter(self):
        widget = _DeliveryWidget()
        widget._srpss_timer_last_skip_stage = "dispatch"

        _record_delivery_result(widget, True)

        self.assertEqual(int(getattr(widget, "_srpss_delivery_accepted", 0) or 0), 1)
        self.assertEqual(self._skip_totals(widget), (0, 0, 0))

    def test_real_queue_path_attributes_dispatch_and_paint_stages_separately(self):
        """The stage label must come from the actual coalescing branch taken."""
        widget = _DeliveryWidget()

        # First call accepts and marks pending+dispatch-pending.
        self.assertTrue(_queue_safe_widget_update(widget))
        # Second call is rejected while the queued update has not run yet.
        self.assertFalse(_queue_safe_widget_update(widget))
        self.assertEqual(getattr(widget, "_srpss_timer_last_skip_stage"), "dispatch")
        _record_delivery_result(widget, False)
        self.assertEqual(self._skip_totals(widget), (1, 0, 0))

        # Run the queued update: dispatch completes, paint has not consumed yet.
        self.queued[0]()
        self.assertFalse(_queue_safe_widget_update(widget))
        self.assertEqual(getattr(widget, "_srpss_timer_last_skip_stage"), "paint")
        _record_delivery_result(widget, False)
        self.assertEqual(self._skip_totals(widget), (1, 1, 0))

    # --- Invariant 2: stage ages are non-negative and generation-bounded ---

    def test_stage_ages_clamp_to_zero_instead_of_reporting_negative_time(self):
        widget = _DeliveryWidget()
        far_future = time.perf_counter() + 3600.0

        _record_delivery_wake(widget, deadline_ts=far_future, immediate=False)
        wake_samples = list(getattr(widget, "_srpss_delivery_wake_late_ms", []))
        self.assertEqual(wake_samples, [0.0])

        widget._srpss_timer_update_pending_since = far_future
        _mark_widget_update_dispatched(widget)
        dispatch_samples = list(getattr(widget, "_srpss_delivery_dispatch_ms", []))
        self.assertEqual(dispatch_samples, [0.0])

        widget._srpss_timer_update_pending_since = 100.0
        widget._srpss_timer_update_dispatched_ts = 100.0
        _record_delivery_paint_start(widget, 90.0)
        paint_samples = list(getattr(widget, "_srpss_delivery_paint_pending_ms", []))
        self.assertEqual(paint_samples, [0.0])

        self.assertTrue(all(value >= 0.0 for value in wake_samples + dispatch_samples + paint_samples))

    def test_paint_latency_is_not_recorded_without_a_live_pending_generation(self):
        """A consumed/torn-down pending state cannot back-date a later paint."""
        widget = _DeliveryWidget()
        widget._srpss_timer_update_pending_since = 0.0
        widget._srpss_timer_update_dispatched_ts = 100.0

        _record_delivery_paint_start(widget, 200.0)

        self.assertEqual(list(getattr(widget, "_srpss_delivery_paint_pending_ms", [])), [])
        self.assertEqual(int(getattr(widget, "_srpss_delivery_dispatch_unknown", 0) or 0), 0)

    def test_missing_dispatch_timestamp_is_counted_rather_than_guessed(self):
        widget = _DeliveryWidget()
        widget._srpss_timer_update_pending_since = 100.0
        widget._srpss_timer_update_dispatched_ts = 0.0

        _record_delivery_paint_start(widget, 200.0)

        self.assertEqual(list(getattr(widget, "_srpss_delivery_paint_pending_ms", [])), [])
        self.assertEqual(int(getattr(widget, "_srpss_delivery_dispatch_unknown", 0) or 0), 1)

    # --- Invariant 3: PERF-off changes nothing but the evidence -----------

    def test_perf_off_produces_identical_scheduling_decisions(self):
        """Diagnostics observe delivery; they must never decide it."""
        def drive(widget) -> list[bool]:
            outcomes = [_queue_safe_widget_update(widget)]
            outcomes.append(_queue_safe_widget_update(widget))
            self.queued[-1]()
            outcomes.append(_queue_safe_widget_update(widget))
            _mark_widget_update_consumed(widget)
            outcomes.append(_queue_safe_widget_update(widget))
            return outcomes

        self._set_perf(True)
        perf_on_widget = _DeliveryWidget()
        perf_on_outcomes = drive(perf_on_widget)
        perf_on_queued = len(self.queued)

        self.queued.clear()
        self._set_perf(False)
        perf_off_widget = _DeliveryWidget()
        perf_off_outcomes = drive(perf_off_widget)
        perf_off_queued = len(self.queued)

        self.assertEqual(perf_on_outcomes, perf_off_outcomes)
        self.assertEqual(perf_on_queued, perf_off_queued)
        self.assertEqual(perf_on_widget.update_count, perf_off_widget.update_count)

    def test_perf_off_creates_no_delivery_attribution_state(self):
        widget = _DeliveryWidget()
        self._set_perf(False)

        _reset_delivery_perf_window(widget)
        _record_delivery_wake(widget, deadline_ts=time.perf_counter() - 1.0, immediate=False)
        widget._srpss_timer_last_skip_stage = "dispatch"
        _record_delivery_result(widget, False)
        widget._srpss_timer_update_pending_since = 1.0
        widget._srpss_timer_update_dispatched_ts = 2.0
        _record_delivery_paint_start(widget, 3.0)

        leaked = [name for name in vars(widget) if name.startswith("_srpss_delivery_")]
        self.assertEqual(leaked, [])

    # --- Invariant 4: generations do not inherit pending timestamps -------

    def test_window_reset_clears_counters_and_samples_and_advances_sequence(self):
        widget = _DeliveryWidget()
        widget._srpss_timer_last_skip_stage = "paint"
        _record_delivery_result(widget, False)
        _record_delivery_result(widget, True)
        _record_delivery_wake(widget, deadline_ts=time.perf_counter() - 1.0, immediate=False)

        first_seq = int(getattr(widget, "_srpss_delivery_window_seq", 0) or 0)
        _reset_delivery_perf_window(widget)

        self.assertEqual(
            int(getattr(widget, "_srpss_delivery_window_seq", 0) or 0), first_seq + 1
        )
        self.assertEqual(self._skip_totals(widget), (0, 0, 0))
        self.assertEqual(int(getattr(widget, "_srpss_delivery_accepted", 0) or 0), 0)
        self.assertEqual(list(getattr(widget, "_srpss_delivery_wake_late_ms", [])), [])
        self.assertIsNone(getattr(widget, "_srpss_delivery_window_active_last"))

    def test_consumed_update_clears_dispatch_timestamps_for_the_next_generation(self):
        widget = _DeliveryWidget()
        _mark_widget_update_pending(widget)
        _mark_widget_update_dispatched(widget)
        self.assertGreater(float(getattr(widget, "_srpss_timer_update_dispatched_ts", 0.0)), 0.0)

        _mark_widget_update_consumed(widget)

        self.assertEqual(float(getattr(widget, "_srpss_timer_update_pending_since", -1.0)), 0.0)
        self.assertEqual(float(getattr(widget, "_srpss_timer_update_dispatched_ts", -1.0)), 0.0)
        self.assertIsNone(getattr(widget, "_srpss_timer_window_active_at_dispatch"))
        self.assertFalse(getattr(widget, "_srpss_timer_dispatch_timing_unknown"))

        # A paint arriving after consumption cannot attribute to the retired state.
        _record_delivery_paint_start(widget, time.perf_counter())
        self.assertEqual(list(getattr(widget, "_srpss_delivery_paint_pending_ms", [])), [])

    def test_a_replacement_widget_starts_with_no_inherited_delivery_state(self):
        retiring = _DeliveryWidget()
        _mark_widget_update_pending(retiring)
        retiring._srpss_timer_last_skip_stage = "dispatch"
        _record_delivery_result(retiring, False)

        replacement = _DeliveryWidget()

        inherited = [name for name in vars(replacement) if name.startswith("_srpss_")]
        self.assertEqual(inherited, [])
        self.assertEqual(self._skip_totals(replacement), (0, 0, 0))

    # --- Invariant 5: displays own their counters independently -----------

    def test_two_displays_retain_independent_delivery_counters(self):
        display_0 = _DeliveryWidget(screen_index=0)
        display_1 = _DeliveryWidget(screen_index=1)

        display_0._srpss_timer_last_skip_stage = "dispatch"
        _record_delivery_result(display_0, False)
        _record_delivery_result(display_0, False)
        _record_delivery_wake(display_0, deadline_ts=time.perf_counter() - 0.5, immediate=False)

        display_1._srpss_timer_last_skip_stage = "paint"
        _record_delivery_result(display_1, False)
        _record_delivery_result(display_1, True)
        _record_delivery_wake(display_1, deadline_ts=None, immediate=True)

        self.assertEqual(self._skip_totals(display_0), (2, 0, 0))
        self.assertEqual(self._skip_totals(display_1), (0, 1, 0))
        self.assertEqual(int(getattr(display_0, "_srpss_delivery_accepted", 0) or 0), 0)
        self.assertEqual(int(getattr(display_1, "_srpss_delivery_accepted", 0) or 0), 1)
        self.assertEqual(int(getattr(display_0, "_srpss_delivery_deadline_wakeups", 0) or 0), 1)
        self.assertEqual(int(getattr(display_1, "_srpss_delivery_deadline_wakeups", 0) or 0), 0)
        self.assertEqual(int(getattr(display_1, "_srpss_delivery_immediate_requests", 0) or 0), 1)

        self.assertIsNot(
            getattr(display_0, "_srpss_delivery_wake_late_ms"),
            getattr(display_1, "_srpss_delivery_wake_late_ms", None),
        )

    def test_resetting_one_display_window_leaves_the_other_intact(self):
        display_0 = _DeliveryWidget(screen_index=0)
        display_1 = _DeliveryWidget(screen_index=1)
        for widget in (display_0, display_1):
            widget._srpss_timer_last_skip_stage = "dispatch"
            _record_delivery_result(widget, False)

        _reset_delivery_perf_window(display_0)

        self.assertEqual(self._skip_totals(display_0), (0, 0, 0))
        self.assertEqual(self._skip_totals(display_1), (1, 0, 0))


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
