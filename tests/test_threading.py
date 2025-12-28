"""
Tests for ThreadManager.
"""
import pytest
import time
import threading
from PySide6.QtCore import QThread
from core.threading.manager import ThreadManager, ThreadPoolType, TaskResult


def test_thread_manager_initialization(qt_app):
    """Test ThreadManager initialization."""
    manager = ThreadManager()
    
    assert manager is not None
    assert ThreadPoolType.IO in manager._executors
    assert ThreadPoolType.COMPUTE in manager._executors
    
    manager.shutdown()


def test_submit_io_task(qt_app):
    """Test submitting an IO task."""
    manager = ThreadManager()
    
    result_value = []
    
    def task():
        return "IO task result"
    
    def callback(result: TaskResult):
        result_value.append(result.result)
    
    task_id = manager.submit_task(
        ThreadPoolType.IO,
        task,
        callback=callback
    )
    
    assert task_id is not None
    
    # Wait for task completion
    time.sleep(0.1)
    
    manager.shutdown()
    
    assert len(result_value) == 1
    assert result_value[0] == "IO task result"


def test_submit_compute_task(qt_app):
    """Test submitting a compute task."""
    manager = ThreadManager()
    
    result_value = []
    
    def compute_task(x, y):
        time.sleep(0.01)  # Small delay to ensure async behavior
        return x + y
    
    def callback(result: TaskResult):
        result_value.append(result)
    
    manager.submit_task(
        ThreadPoolType.COMPUTE,
        compute_task,
        5, 3,
        callback=callback
    )
    
    # Wait for task to complete
    time.sleep(0.1)
    
    assert len(result_value) == 1
    assert result_value[0].success is True
    assert result_value[0].result == 8
    
    manager.shutdown()


def test_get_pool_stats(qt_app):
    """Test getting pool statistics."""
    manager = ThreadManager()
    
    stats = manager.get_pool_stats()
    
    assert 'io' in stats
    assert 'compute' in stats
    assert 'submitted' in stats['io']
    assert 'completed' in stats['io']
    assert 'failed' in stats['io']
    
    manager.shutdown()


def test_thread_manager_shutdown(qt_app):
    """Test ThreadManager shutdown."""
    manager = ThreadManager()
    
    # Submit a task
    manager.submit_task(ThreadPoolType.IO, lambda: time.sleep(0.01))
    
    # Shutdown
    manager.shutdown(wait=True)
    
    # Should not be able to submit after shutdown
    with pytest.raises(RuntimeError):
        manager.submit_task(ThreadPoolType.IO, lambda: None)


def test_run_on_ui_thread_from_ui_thread(qt_app):
    """run_on_ui_thread executes immediately when already on the UI thread.

    This is important for callers that may be on the UI thread already (e.g.
    DisplayWidget callbacks) and rely on synchronous behaviour.
    """

    called = []
    thread_ids = []

    def _fn():
        called.append(True)
        thread_ids.append(QThread.currentThread())

    # In tests with qt_app, we are already running on the main Qt thread.
    ThreadManager.run_on_ui_thread(_fn)

    assert called == [True]
    assert thread_ids[0] is qt_app.thread()


def test_run_on_ui_thread_from_worker_thread(qt_app):
    """run_on_ui_thread dispatches work back onto the UI thread from workers.

    Future async ImageProcessor paths and other background tasks depend on this
    to safely update Qt objects from ThreadManager IO/COMPUTE pools.
    """

    called = []
    thread_ids = []

    def _fn():
        called.append(True)
        thread_ids.append(QThread.currentThread())

    def _worker():
        # Simulate a background thread (could be IO/COMPUTE pool) calling into
        # the UI dispatch helper.
        ThreadManager.run_on_ui_thread(_fn)

    t = threading.Thread(target=_worker)
    t.start()

    # Pump the Qt event loop until the callback runs or we timeout.
    deadline = time.time() + 2.0
    while not called and time.time() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    t.join(timeout=1.0)

    assert called == [True]
    # The callback must have executed on the main Qt thread, not the worker.
    assert thread_ids[0] is qt_app.thread()


@pytest.mark.qt_no_exception_capture
def test_schedule_recurring_invokes_callback(qt_app):
    """schedule_recurring should tick callbacks without requiring description."""
    manager = ThreadManager()

    ticks = []

    def _tick():
        ticks.append(time.time())

    timer = manager.schedule_recurring(5, _tick)

    deadline = time.time() + 0.2
    while len(ticks) < 2 and time.time() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    timer.stop()
    manager.shutdown()

    assert len(ticks) >= 1


@pytest.mark.qt_no_exception_capture
def test_schedule_recurring_with_description(qt_app):
    """Explicit descriptions should not change timer behaviour."""
    manager = ThreadManager()
    ticks = []

    timer = manager.schedule_recurring(5, lambda: ticks.append(time.time()), description="test_timer")

    deadline = time.time() + 0.2
    while len(ticks) < 2 and time.time() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    timer.stop()
    manager.shutdown()

    assert len(ticks) >= 1
