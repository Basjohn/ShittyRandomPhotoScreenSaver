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

from core.threading.manager import (
    ThreadManager,
    ThreadPoolType,
    TaskPriority,
    TaskResult,
    Task,
)


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
