"""
Integration tests for ThreadManager.

Tests the centralized threading functionality including:
- Thread pool initialization
- Task submission and execution
- IO and Compute pool separation
- Task callbacks and results
- Shutdown behavior
- UI thread dispatch
"""
import threading
import time
import pytest
from core.threading import manager as manager_module
from core.threading.manager import (
    _classify_large_timer_gap_warning,
    _describe_timer_callable_context,
    _should_suppress_large_timer_gap_warning,
)

from core.threading.manager import (
    ThreadManager,
    ThreadPoolType,
    TaskPriority,
    TaskResult,
    Task,
)
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle
from PySide6.QtCore import QObject, QThread


class TestThreadManagerInit:
    """Thread manager initialization tests."""

    def test_init_creates_instance(self):
        """Test that ThreadManager can be instantiated."""
        manager = ThreadManager()
        assert manager is not None
        manager.shutdown()

    def test_init_creates_io_pool(self):
        """Test that IO pool is created."""
        manager = ThreadManager()
        assert ThreadPoolType.IO in manager._executors
        manager.shutdown()

    def test_init_creates_compute_pool(self):
        """Test that COMPUTE pool is created."""
        manager = ThreadManager()
        assert ThreadPoolType.COMPUTE in manager._executors
        manager.shutdown()

    def test_init_with_custom_config(self):
        """Test initialization with custom pool sizes."""
        config = {
            ThreadPoolType.IO: 2,
            ThreadPoolType.COMPUTE: 1,
        }
        manager = ThreadManager(config=config)
        assert manager.config[ThreadPoolType.IO] == 2
        assert manager.config[ThreadPoolType.COMPUTE] == 1
        manager.shutdown()

    def test_init_default_io_workers(self):
        """Test default IO worker count."""
        manager = ThreadManager()
        assert manager.config[ThreadPoolType.IO] == 4
        manager.shutdown()

    def test_app_shared_manager_registration_roundtrip(self):
        manager = ThreadManager()
        try:
            ThreadManager.set_app_shared(manager)
            assert ThreadManager.get_app_shared() is manager
        finally:
            manager.shutdown()
            ThreadManager.set_app_shared(None)

    def test_get_or_create_app_shared_reuses_live_manager(self):
        manager = ThreadManager()
        try:
            ThreadManager.set_app_shared(manager)
            shared = ThreadManager.get_or_create_app_shared()
            assert shared is manager
        finally:
            manager.shutdown()
            ThreadManager.set_app_shared(None)

    def test_create_helper_manager_uses_narrow_pool_sizes(self):
        manager = ThreadManager.create_helper_manager(io_workers=2, compute_workers=1)
        try:
            assert manager.config[ThreadPoolType.IO] == 2
            assert manager.config[ThreadPoolType.COMPUTE] == 1
        finally:
            manager.shutdown()

    def test_shutdown_clears_app_shared_manager_when_owned(self):
        manager = ThreadManager()
        ThreadManager.set_app_shared(manager)
        manager.shutdown()
        assert ThreadManager.get_app_shared() is None


class TestTaskClass:
    """Tests for Task wrapper class."""

    def test_task_creation(self):
        """Test Task can be created with function."""
        def sample_func():
            return 42
        
        task = Task(sample_func)
        assert task.func == sample_func
        assert task.priority == TaskPriority.NORMAL

    def test_task_with_args(self):
        """Test Task with positional arguments."""
        def add(a, b):
            return a + b
        
        task = Task(add, 1, 2)
        assert task.args == (1, 2)

    def test_task_with_kwargs(self):
        """Test Task with keyword arguments."""
        def greet(name="World"):
            return f"Hello, {name}"
        
        task = Task(greet, name="Test")
        assert task.kwargs == {"name": "Test"}

    def test_task_with_priority(self):
        """Test Task with custom priority."""
        task = Task(lambda: None, priority=TaskPriority.HIGH)
        assert task.priority == TaskPriority.HIGH

    def test_task_with_task_id(self):
        """Test Task with custom task ID."""
        task = Task(lambda: None, task_id="my_task")
        assert task.task_id == "my_task"

    def test_task_comparison_by_priority(self):
        """Test Task comparison uses priority."""
        low = Task(lambda: None, priority=TaskPriority.LOW)
        high = Task(lambda: None, priority=TaskPriority.HIGH)
        # Higher priority should be "less than" for priority queue
        assert high < low


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_success_result(self):
        """Test successful TaskResult."""
        result = TaskResult(success=True, result=42)
        assert result.success is True
        assert result.result == 42
        assert result.error is None

    def test_failure_result(self):
        """Test failed TaskResult."""
        error = ValueError("test error")
        result = TaskResult(success=False, error=error)
        assert result.success is False
        assert result.error == error

    def test_result_with_execution_time(self):
        """Test TaskResult with execution time."""
        result = TaskResult(success=True, execution_time=1.5)
        assert result.execution_time == 1.5

    def test_result_with_task_id(self):
        """Test TaskResult with task ID."""
        result = TaskResult(success=True, task_id="task_123")
        assert result.task_id == "task_123"


class TestThreadManagerSubmit:
    """Task submission tests."""

    def test_submit_io_task(self):
        """Test submitting task to IO pool."""
        manager = ThreadManager()
        results = []
        
        def task_func():
            results.append("executed")
            return "done"
        
        task_id = manager.submit_task(ThreadPoolType.IO, task_func)
        assert task_id is not None
        
        # Wait for completion
        time.sleep(0.2)
        assert "executed" in results
        manager.shutdown()

    def test_submit_compute_task(self):
        """Test submitting task to COMPUTE pool."""
        manager = ThreadManager()
        results = []
        
        def task_func():
            results.append("computed")
            return 42
        
        task_id = manager.submit_task(ThreadPoolType.COMPUTE, task_func)
        assert task_id is not None
        
        time.sleep(0.2)
        assert "computed" in results
        manager.shutdown()

    def test_submit_task_with_args(self):
        """Test submitting task with arguments."""
        manager = ThreadManager()
        results = []
        
        def add(a, b):
            result = a + b
            results.append(result)
            return result
        
        manager.submit_task(ThreadPoolType.IO, add, 5, 3)
        time.sleep(0.2)
        assert 8 in results
        manager.shutdown()

    def test_submit_task_with_callback(self):
        """Test submitting task with callback."""
        manager = ThreadManager()
        callback_results = []
        
        def task_func():
            return "task_result"
        
        def callback(result: TaskResult):
            callback_results.append(result)
        
        manager.submit_task(ThreadPoolType.IO, task_func, callback=callback)
        time.sleep(0.2)
        
        assert len(callback_results) == 1
        assert callback_results[0].success is True
        assert callback_results[0].result == "task_result"
        manager.shutdown()

    def test_submit_task_error_handling(self):
        """Test that task errors are captured."""
        manager = ThreadManager()
        callback_results = []
        
        def failing_task():
            raise ValueError("intentional error")
        
        def callback(result: TaskResult):
            callback_results.append(result)
        
        manager.submit_task(ThreadPoolType.IO, failing_task, callback=callback)
        time.sleep(0.2)
        
        assert len(callback_results) == 1
        assert callback_results[0].success is False
        assert isinstance(callback_results[0].error, ValueError)
        manager.shutdown()

    def test_submit_after_shutdown_raises(self):
        """Test that submitting after shutdown raises error."""
        manager = ThreadManager()
        manager.shutdown()
        
        with pytest.raises(RuntimeError):
            manager.submit_task(ThreadPoolType.IO, lambda: None)

    def test_active_task_visible_immediately_after_submit(self):
        """Active-task bookkeeping should not depend on the UI mutation drain."""
        manager = ThreadManager()
        started = threading.Event()
        release = threading.Event()

        def blocking_task():
            started.set()
            release.wait(timeout=1.0)
            return "done"

        task_id = manager.submit_task(ThreadPoolType.IO, blocking_task)
        assert started.wait(timeout=0.5)
        assert task_id in manager.get_active_tasks()

        release.set()
        time.sleep(0.1)
        manager.shutdown()

    def test_get_task_result_works_without_ui_mutation_drain(self):
        """Result retrieval should work for an active task even before Qt drains mutations."""
        manager = ThreadManager()
        started = threading.Event()
        release = threading.Event()

        def blocking_task():
            started.set()
            release.wait(timeout=1.0)
            return 123

        task_id = manager.submit_task(ThreadPoolType.IO, blocking_task)
        assert started.wait(timeout=0.5)

        result_ready: list[TaskResult] = []

        def waiter():
            result_ready.append(manager.get_task_result(task_id, timeout=1.0))

        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.05)
        release.set()
        t.join(timeout=1.0)

        assert len(result_ready) == 1
        assert result_ready[0].success is True
        assert result_ready[0].result == 123
        manager.shutdown()


class TestThreadManagerConvenience:
    """Convenience method tests."""

    def test_submit_io_task_convenience(self):
        """Test submit_io_task convenience method."""
        manager = ThreadManager()
        results = []
        
        def task():
            results.append("io")
        
        manager.submit_io_task(task)
        time.sleep(0.2)
        assert "io" in results
        manager.shutdown()

    def test_submit_compute_task_convenience(self):
        """Test submit_compute_task convenience method."""
        manager = ThreadManager()
        results = []
        
        def task():
            results.append("compute")
        
        manager.submit_compute_task(task)
        time.sleep(0.2)
        assert "compute" in results
        manager.shutdown()


class TestThreadManagerConcurrency:
    """Concurrency and thread safety tests."""

    def test_multiple_concurrent_tasks(self):
        """Test multiple tasks run concurrently."""
        manager = ThreadManager()
        results = []
        lock = threading.Lock()
        
        def task(task_id):
            time.sleep(0.05)
            with lock:
                results.append(task_id)
        
        # Submit 10 tasks
        for i in range(10):
            manager.submit_task(ThreadPoolType.IO, task, i)
        
        # Wait for completion
        time.sleep(0.5)
        
        assert len(results) == 10
        manager.shutdown()

    def test_io_and_compute_pools_independent(self):
        """Test IO and COMPUTE pools work independently."""
        manager = ThreadManager()
        io_results = []
        compute_results = []
        
        def io_task():
            time.sleep(0.05)
            io_results.append("io")
        
        def compute_task():
            time.sleep(0.05)
            compute_results.append("compute")
        
        # Submit to both pools
        for _ in range(5):
            manager.submit_task(ThreadPoolType.IO, io_task)
            manager.submit_task(ThreadPoolType.COMPUTE, compute_task)
        
        time.sleep(0.5)
        
        assert len(io_results) == 5
        assert len(compute_results) == 5
        manager.shutdown()


class TestThreadManagerShutdown:
    """Shutdown behavior tests."""

    def test_shutdown_completes_pending_tasks(self):
        """Test shutdown waits for pending tasks."""
        manager = ThreadManager()
        results = []
        
        def slow_task():
            time.sleep(0.1)
            results.append("done")
        
        manager.submit_task(ThreadPoolType.IO, slow_task)
        manager.shutdown(wait=True)
        
        # Task should have completed
        assert "done" in results

    def test_shutdown_sets_flag(self):
        """Test shutdown sets shutdown flag."""
        manager = ThreadManager()
        assert manager._shutdown is False
        manager.shutdown()
        assert manager._shutdown is True

    def test_double_shutdown_safe(self):
        """Test calling shutdown twice is safe."""
        manager = ThreadManager()
        manager.shutdown()
        # Should not raise
        manager.shutdown()

    def test_shutdown_waits_for_active_tasks_without_ui_drain(self):
        """Shutdown should see in-flight tasks without requiring a queued registry update."""
        manager = ThreadManager()
        started = threading.Event()
        release = threading.Event()
        results = []

        def slow_task():
            started.set()
            release.wait(timeout=1.0)
            results.append("done")

        manager.submit_task(ThreadPoolType.IO, slow_task)
        assert started.wait(timeout=0.5)

        def releaser():
            time.sleep(0.05)
            release.set()

        threading.Thread(target=releaser, daemon=True).start()
        manager.shutdown(wait=True, timeout=1.0)

        assert results == ["done"]


class TestThreadManagerStats:
    """Statistics tracking tests."""

    def test_stats_initialized(self):
        """Test stats are initialized for each pool."""
        manager = ThreadManager()
        assert ThreadPoolType.IO.value in [k.value for k in manager._stats.keys()] or 'io' in str(manager._stats)
        manager.shutdown()

    def test_stats_dict_structure(self):
        """Test stats dict has expected structure."""
        manager = ThreadManager()
        # Stats are stored internally
        assert isinstance(manager._stats, dict)
        assert ThreadPoolType.IO in manager._stats
        assert ThreadPoolType.COMPUTE in manager._stats
        manager.shutdown()


class TestTaskPriority:
    """Task priority enum tests."""

    def test_priority_values(self):
        """Test priority enum values."""
        assert TaskPriority.LOW.value == 0
        assert TaskPriority.NORMAL.value == 1
        assert TaskPriority.HIGH.value == 2
        assert TaskPriority.CRITICAL.value == 3

    def test_priority_ordering(self):
        """Test priority ordering."""
        assert TaskPriority.LOW.value < TaskPriority.NORMAL.value
        assert TaskPriority.NORMAL.value < TaskPriority.HIGH.value
        assert TaskPriority.HIGH.value < TaskPriority.CRITICAL.value


class TestThreadPoolType:
    """Thread pool type enum tests."""

    def test_pool_type_values(self):
        """Test pool type enum values."""
        assert ThreadPoolType.IO.value == "io"
        assert ThreadPoolType.COMPUTE.value == "compute"


class TestOverlayTimerIntegration:
    """Overlay timer tests now live with ThreadManager assertions."""

    class _DummyWidget(QObject):
        def __init__(self, parent: QObject | None = None) -> None:
            super().__init__(parent)
            self._thread_manager: ThreadManager | None = None

    def test_overlay_timer_uses_thread_manager_when_available(self, qt_app):
        widget = self._DummyWidget()
        manager = ThreadManager()
        widget._thread_manager = manager  # type: ignore[attr-defined]

        calls = []

        def _cb() -> None:
            calls.append("fire")

        handle = create_overlay_timer(widget, 10, _cb, description="test")
        assert isinstance(handle, OverlayTimerHandle)

        # schedule_recurring inserts a real timer; just ensure manager recorded it.
        qt_app.processEvents()
        time.sleep(0.05)
        qt_app.processEvents()
        assert handle.is_active()
        handle.stop()
        assert not handle.is_active()
        manager.shutdown()

    def test_overlay_timer_missing_thread_manager_raises(self):
        widget = self._DummyWidget()

        with pytest.raises(RuntimeError):
            create_overlay_timer(widget, 5, lambda: None, description="missing")

    def test_overlay_timer_passes_description_and_owner_to_thread_manager(self):
        widget = self._DummyWidget()
        captured: dict[str, object] = {}

        class _StubTimer:
            def isActive(self) -> bool:
                return True

        class _StubManager:
            def schedule_recurring(self, interval_ms, callback, *args, description=None, **kwargs):
                captured["interval_ms"] = interval_ms
                captured["callback"] = callback
                captured["description"] = description
                return _StubTimer()

        widget._thread_manager = _StubManager()  # type: ignore[attr-defined]

        handle = create_overlay_timer(widget, 2500, lambda: None, description="WeatherWidget refresh")

        assert isinstance(handle, OverlayTimerHandle)
        assert captured["interval_ms"] == 2500
        assert captured["description"] == "WeatherWidget refresh"
        callback = captured["callback"]
        assert getattr(callback, "_srpss_timer_owner", None) is widget


class TestUiThreadDispatch:
    """run_on_ui_thread helper coverage."""

    def test_run_on_ui_thread_from_ui_thread(self, qt_app):
        """Executing from UI thread should run synchronously."""
        called = []
        thread_ids = []

        def _fn():
            called.append(True)
            thread_ids.append(QThread.currentThread())

        ThreadManager.run_on_ui_thread(_fn)

        assert called == [True]
        assert thread_ids[0] is qt_app.thread()

    def test_run_on_ui_thread_from_worker_thread(self, qt_app):
        """Worker threads should dispatch back to Qt main thread."""
        called = []
        thread_ids = []

        def _fn():
            called.append(True)
            thread_ids.append(QThread.currentThread())

        def _worker():
            ThreadManager.run_on_ui_thread(_fn)

        t = threading.Thread(target=_worker)
        t.start()

        deadline = time.time() + 2.0
        while not called and time.time() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)

        t.join(timeout=1.0)

        assert called == [True]
        assert thread_ids[0] is qt_app.thread()


class TestRecurringTimers:
    """schedule_recurring helper tests."""

    @pytest.mark.qt_no_exception_capture
    def test_schedule_recurring_invokes_callback(self, qt_app):
        manager = ThreadManager()
        ticks: list[float] = []

        timer = manager.schedule_recurring(5, lambda: ticks.append(time.time()))

        deadline = time.time() + 0.2
        while len(ticks) < 2 and time.time() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)

        timer.stop()
        manager.shutdown()

        assert len(ticks) >= 1

    def test_schedule_recurring_gap_diagnostics_use_live_timer_interval(
        self,
        qt_app,
        monkeypatch,
        caplog,
    ):
        manager = ThreadManager()
        ticks: list[float] = []
        fake_times = [100.0, 102.6, 105.2]

        def _fake_time():
            if fake_times:
                return fake_times.pop(0)
            return 105.2

        monkeypatch.setattr(manager_module, "is_perf_metrics_enabled", lambda: True)
        monkeypatch.setattr(manager_module.time, "time", _fake_time)
        monkeypatch.setattr(manager_module, "_describe_timer_callable_context", lambda _func: {})
        monkeypatch.setattr(
            manager_module,
            "_should_suppress_large_timer_gap_warning",
            lambda _gap, _interval, _context: False,
        )

        timer = manager.schedule_recurring(
            1000,
            lambda: ticks.append(time.monotonic()),
            description="retuned_timer",
        )
        try:
            with caplog.at_level("WARNING"):
                timer.timeout.emit()
                timer.setInterval(2500)
                timer.timeout.emit()
                assert "Large gap for retuned_timer" not in caplog.text

                timer.setInterval(1000)
                timer.timeout.emit()
                assert "Large gap for retuned_timer" in caplog.text
                assert "interval=1000ms" in caplog.text
        finally:
            timer.stop()
            manager.shutdown()


def test_large_timer_gap_warning_suppressed_during_transition_handoff():
    context = {
        "display_transition": {
            "running": False,
            "pending": False,
            "last_transition": "GLCompositorRainDropsTransition",
            "idle_age": 0.02,
        },
        "compositor": {
            "current_transition": None,
            "has_frame_state": False,
            "render_strategy": {
                "timer": {
                    "state": "PAUSED",
                }
            },
        },
    }

    assert _should_suppress_large_timer_gap_warning(7557.0, 16, context) is True


def test_large_timer_gap_warning_not_suppressed_for_plain_idle_gap():
    context = {
        "display_transition": {
            "running": False,
            "pending": False,
            "last_transition": "GLCompositorRainDropsTransition",
            "idle_age": 1.8,
        },
        "compositor": {
            "current_transition": None,
            "has_frame_state": False,
            "render_strategy": {
                "timer": {
                    "state": "RUNNING",
                }
            },
        },
    }

    assert _should_suppress_large_timer_gap_warning(400.0, 16, context) is False


def test_large_timer_gap_warning_suppressed_for_visualizer_reconfiguration_window():
    context = {
        "vis_pending_mode": "BUBBLE",
        "vis_waiting_engine": True,
        "vis_waiting_frame": False,
        "display_transition": {
            "running": False,
            "pending": False,
            "last_transition": None,
            "idle_age": 12.0,
        },
        "compositor": {
            "current_transition": None,
            "has_frame_state": False,
            "render_strategy": {
                "timer": {
                    "state": "IDLE",
                }
            },
        },
    }

    assert _should_suppress_large_timer_gap_warning(140.0, 16, context) is True


def test_large_timer_gap_warning_classifies_active_compositor_transition():
    context = {
        "display_transition": {
            "running": False,
            "pending": False,
        },
        "compositor": {
            "current_transition": "GLCompositorBlockSpinTransition",
            "has_frame_state": True,
        },
    }

    assert _classify_large_timer_gap_warning(context) == "compositor_transition_starvation"


def test_large_timer_gap_warning_classifies_visualizer_reconfiguration():
    context = {
        "vis_pending_mode": "BUBBLE",
        "vis_waiting_engine": False,
        "vis_waiting_frame": True,
    }

    assert _classify_large_timer_gap_warning(context) == "visualizer_reconfiguration_starvation"


def test_timer_context_includes_media_widget_poll_state(qt_app):
    class _Display(QObject):
        screen_index = 1

    class _MediaOwner(QObject):
        def __init__(self, parent: QObject) -> None:
            super().__init__(parent)
            self.setObjectName("media_overlay")
            self._provider = "spotify"
            self._current_poll_stage = 0
            self._update_timer_interval_ms = 1000
            self._refresh_in_flight = False
            self._is_idle = False
            self._app_process_running = True
            self._fade_in_completed = True
            self._has_seen_first_track = True

    _MediaOwner.__name__ = "MediaWidget"
    display = _Display()
    owner = _MediaOwner(display)

    def _callback() -> None:
        return None

    setattr(_callback, "_srpss_timer_owner", owner)

    context = _describe_timer_callable_context(_callback)

    assert context is not None
    assert context["owner_type"] == "MediaWidget"
    assert context["object_name"] == "media_overlay"
    assert context["parent_screen_index"] == 1
    assert context["media_provider"] == "spotify"
    assert context["media_poll_stage"] == 0
    assert context["media_timer_interval_ms"] == 1000
    assert context["media_refresh_in_flight"] is False
    assert context["media_fade_in_completed"] is True
    assert _classify_large_timer_gap_warning(context) == "media_widget_poll_starvation"

    @pytest.mark.qt_no_exception_capture
    def test_schedule_recurring_respects_description(self, qt_app):
        manager = ThreadManager()
        ticks: list[float] = []

        timer = manager.schedule_recurring(
            5,
            lambda: ticks.append(time.time()),
            description="test_timer",
        )

        deadline = time.time() + 0.2
        while len(ticks) < 2 and time.time() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)

        timer.stop()
        manager.shutdown()

        assert len(ticks) >= 1
