"""
Tests for ThreadManager.
"""
import pytest
import time
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
    
    task_id = manager.submit_task(
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
