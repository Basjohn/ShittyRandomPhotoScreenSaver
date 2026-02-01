"""
Thread Manager for Screensaver Application

Centralized thread management with specialized pools for IO and compute operations.
Adapted from SPQDocker reusable modules for screensaver use.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from utils.lockfree import SPSCQueue, TripleBuffer
from PySide6.QtCore import QTimer, QObject, QThread, QCoreApplication, Signal, Qt
from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled

logger = get_logger(__name__)


# UI-thread invoker for reliable main thread dispatch
class _UiInvoker(QObject):
    invoke = Signal(object, object, object)

    def __init__(self):
        super().__init__()
        self.invoke.connect(self._on_invoke)

    def _on_invoke(self, func, args, kwargs):
        try:
            func(*args, **(kwargs or {}))
        except Exception as e:
            logger.exception("UI invoker callable raised: %s", e)


_ui_invoker: Optional[_UiInvoker] = None


def _ensure_ui_invoker() -> Optional[_UiInvoker]:
    global _ui_invoker
    try:
        app = QCoreApplication.instance()
        if app is None:
            logger.error("run_on_ui_thread: No QCoreApplication instance")
            return None
        if _ui_invoker is None:
            inv = _UiInvoker()
            inv.moveToThread(app.thread())
            _ui_invoker = inv
        return _ui_invoker
    except Exception as e:
        logger.exception("Failed to initialize UI invoker: %s", e)
        return None


class TaskPriority(Enum):
    """Task priority levels"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class ThreadPoolType(Enum):
    """Thread pool types for screensaver workloads"""
    IO = "io"               # File I/O, network operations, RSS feeds
    COMPUTE = "compute"     # Image processing, transitions


@dataclass
class TaskResult:
    """Container for task execution results"""
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    task_id: Optional[str] = None


class Task:
    """Wrapper for executable tasks with metadata"""
    def __init__(self, func: Callable, *args, task_id: str = None, 
                 priority: TaskPriority = TaskPriority.NORMAL, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.task_id = task_id or f"task_{id(self)}"
        self.priority = priority
        self.created_at = time.time()
        self.future: Optional[Future] = None

    def __lt__(self, other):
        return self.priority.value > other.priority.value


class ThreadManager:
    """
    Centralized thread manager for screensaver application.
    
    Features:
    - Separate IO and COMPUTE thread pools
    - Task prioritization and result handling
    - Resource cleanup integration
    - UI thread dispatch utilities
    - Lock-free statistics
    """
    def __init__(self, config: Optional[Dict[ThreadPoolType, int]] = None, 
                 resource_manager: Optional[Any] = None):
        """
        Initialize thread manager.
        
        Args:
            config: Dictionary mapping ThreadPoolType to max_workers count
            resource_manager: Optional ResourceManager for cleanup tracking
        """
        self._shutdown = False
        
        # Default configuration for screensaver
        cpu_count = os.cpu_count() or 1
        compute_workers = max(1, cpu_count - 1)
        default_config = {
            ThreadPoolType.IO: 4,        # RSS feeds, file I/O
            ThreadPoolType.COMPUTE: compute_workers,  # Image processing
        }
        self.config = {**default_config, **(config or {})}
        
        self._executors: Dict[ThreadPoolType, ThreadPoolExecutor] = {}
        self._active_tasks: Dict[str, Task] = {}
        self._stats = {pool_type: {'submitted': 0, 'completed': 0, 'failed': 0} 
                      for pool_type in ThreadPoolType}
        
        # Lock-free mutation queue
        self._mut_q: SPSCQueue[tuple] = SPSCQueue(256)
        self._mut_drain_scheduled = False
        
        # Lock-free stats publisher
        self._stats_tb: TripleBuffer[Dict[str, Dict[str, Any]]] = TripleBuffer()
        self._stats_pub_interval_ms: int = 250
        
        self._resource_manager = resource_manager
        self._resource_id = None
        
        # Initialize pools
        self._initialize_pools()
        
        # Start stats publisher
        try:
            self._schedule_stats_publish()
        except Exception as e:
            logger.debug("Stats publisher scheduling failed: %s", e)
        
        # Start mutation drain
        try:
            self._schedule_mutation_drain()
        except Exception as e:
            logger.debug("[THREADING] Exception suppressed: %s", e)
        
        logger.info("ThreadManager initialized with IO=%d, COMPUTE=%d workers",
                   self.config[ThreadPoolType.IO], self.config[ThreadPoolType.COMPUTE])
        
        # Instrumentation: log stack trace when new ThreadManager is created
        # This helps identify code paths creating rogue managers that prevent clean exit
        if is_perf_metrics_enabled():
            import traceback
            stack = ''.join(traceback.format_stack()[:-1])  # Exclude this call itself
            logger.info("[PERF] [THREADING] ThreadManager instantiated from:\n%s", stack)

    def _initialize_pools(self):
        """Initialize thread pools based on configuration."""
        for pool_type, max_workers in self.config.items():
            try:
                executor = ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix=f"{pool_type.value}_pool"
                )
                
                # Register with resource manager if available
                if self._resource_manager:
                    try:
                        from core.resources.types import ResourceType
                        self._resource_manager.register(
                            executor,
                            ResourceType.THREAD_POOL,
                            f"Thread pool for {pool_type.value}",
                            cleanup_handler=lambda e: e.shutdown(wait=True),
                            pool_type=pool_type.value
                        )
                    except Exception as e:
                        logger.debug("Could not register executor: %s", e)
                
                self._executors[pool_type] = executor
                logger.info(f"Initialized {pool_type.value} pool with {max_workers} workers")
            except Exception as e:
                logger.error(f"Failed to initialize {pool_type.value} pool: %s", e)
                self.shutdown()
                raise RuntimeError(f"Failed to initialize {pool_type.value} thread pool")

    def submit_task(self, pool_type: ThreadPoolType, func: Callable, *args,
                   task_id: str = None, priority: TaskPriority = TaskPriority.NORMAL,
                   callback: Callable[[TaskResult], None] = None, **kwargs) -> str:
        """
        Submit a task to the specified thread pool.
        
        Args:
            pool_type: Which thread pool to use
            func: Function to execute
            *args: Positional arguments for func
            task_id: Optional unique identifier
            priority: Task priority
            callback: Optional callback for result
            **kwargs: Keyword arguments for func
        
        Returns:
            str: Task ID for tracking
        """
        if self._shutdown:
            raise RuntimeError("Thread manager is shut down")
        
        task = Task(func, *args, task_id=task_id, priority=priority, **kwargs)
        task.pool_type = pool_type
        executor = self._executors[pool_type]
        
        def wrapped_func():
            start_time = time.time()
            try:
                result = task.func(*task.args, **task.kwargs)
                execution_time = time.time() - start_time
                task_result = TaskResult(
                    success=True,
                    result=result,
                    execution_time=execution_time,
                    task_id=task.task_id
                )
                self._enqueue_mutation(('completed', pool_type.value))
            except Exception as e:
                execution_time = time.time() - start_time
                task_result = TaskResult(
                    success=False,
                    error=e,
                    execution_time=execution_time,
                    task_id=task.task_id
                )
                logger.error(f"Task {task.task_id} failed: {e}")
                self._enqueue_mutation(('failed', pool_type.value))
            finally:
                self._enqueue_mutation(('unregister_active', task.task_id))
            
            # Execute callback
            if callback:
                try:
                    callback(task_result)
                except Exception as e:
                    logger.error(f"Callback for task {task.task_id} failed: {e}")
            
            return task_result
        
        # Submit to executor
        future = executor.submit(wrapped_func)
        task.future = future
        
        # Register with resource manager
        if self._resource_manager:
            try:
                from core.resources.types import ResourceType
                self._resource_manager.register(
                    future,
                    ResourceType.CUSTOM,
                    f"Task future for {task.task_id}",
                    cleanup_handler=lambda f: f.cancel() if not f.done() else None,
                    task_id=task.task_id
                )
            except (TypeError, Exception) as e:
                logger.debug(f"Skipping resource registration for task {task.task_id}: {e}")
        
        # Update tracking
        self._enqueue_mutation(('register_active', task))
        self._enqueue_mutation(('submitted', pool_type.value))
        
        if is_verbose_logging():
            logger.debug(f"Submitted task {task.task_id} to {pool_type.value} pool")
        return task.task_id

    def submit_io_task(self, func: Callable, *args, **kwargs) -> str:
        """Convenience method for IO pool submissions"""
        return self.submit_task(ThreadPoolType.IO, func, *args, **kwargs)

    def submit_compute_task(self, func: Callable, *args, **kwargs) -> str:
        """Convenience method for COMPUTE pool submissions.

        This is primarily used for CPU-heavy work such as image processing
        and pre-scaling so callers do not need to reference ThreadPoolType
        directly.
        """
        return self.submit_task(ThreadPoolType.COMPUTE, func, *args, **kwargs)

    def get_task_result(self, task_id: str, timeout: Optional[float] = None) -> TaskResult:
        """Get the result of a specific task"""
        task = self._active_tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found")
        try:
            return task.future.result(timeout=timeout)
        except TimeoutError:
            raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")

    def cancel_task(self, task_id: str) -> bool:
        """Attempt to cancel a task"""
        task = self._active_tasks.get(task_id)
        if task and task.future:
            cancelled = task.future.cancel()
            if cancelled:
                self._active_tasks.pop(task_id, None)
                logger.info(f"Cancelled task {task_id}")
            return cancelled
        return False

    def get_active_tasks(self) -> List[str]:
        """Get list of currently active task IDs"""
        return list(self._active_tasks.keys())

    def get_pool_stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics for all thread pools"""
        return {pool_type.value: stats.copy() 
               for pool_type, stats in self._stats.items()}

    def shutdown(self, wait: bool = True, timeout: Optional[float] = None):
        """
        Shutdown all thread pools and clean up resources.
        
        Args:
            wait: Whether to wait for active tasks
            timeout: Maximum time to wait
        """
        logger.info("Shutting down thread manager...")
        
        if self._shutdown:
            return
        self._shutdown = True
        
        # Cancel active tasks
        active_ids = list(self._active_tasks.keys())
        if active_ids:
            logger.info("Cancelling %d active tasks before shutdown: %s", len(active_ids), active_ids)
        for task_id in active_ids:
            self.cancel_task(task_id)
        
        # Shutdown executors
        for pool_type, executor in self._executors.items():
            try:
                pool_active = [t.task_id for t in self._active_tasks.values()
                               if getattr(t, 'pool_type', None) == pool_type]
                if pool_active:
                    logger.info("Pool %s has %d pending tasks during shutdown: %s",
                                pool_type.value, len(pool_active), pool_active)
                logger.debug(f"Shutting down {pool_type.value} pool...")
                # FIX: cancel_futures added in Python 3.9, handle older versions
                try:
                    executor.shutdown(wait=wait, cancel_futures=not wait)
                except TypeError:
                    # Python < 3.9 doesn't support cancel_futures parameter
                    executor.shutdown(wait=wait)
                    logger.debug("Using Python < 3.9 shutdown (no cancel_futures)")
            except Exception as e:
                logger.error(f"Error shutting down {pool_type.value} pool: {e}")
        
        # Clear executors to release references
        self._executors.clear()
        self._active_tasks.clear()
        
        logger.info("Thread manager shut down complete")

    # Internal: mutation queue -------------------------------------------
    def _enqueue_mutation(self, ev: tuple) -> None:
        if self._shutdown:
            return
        try:
            self._mut_q.push_drop_oldest(ev)
        except Exception as e:
            # FIX: Log silent failure instead of ignoring
            logger.debug(f"Failed to push mutation to queue: {e}")
            return
        
        if isinstance(ev, tuple) and ev and ev[0] == 'register_active':
            self._schedule_mutation_drain(0)
        else:
            self._schedule_mutation_drain()

    def _schedule_mutation_drain(self, delay_ms: int = 10) -> None:
        if self._shutdown or self._mut_drain_scheduled:
            return
        
        self._mut_drain_scheduled = True
        if QCoreApplication.instance() is not None:
            self.single_shot(max(0, int(delay_ms)), self._drain_mutations_on_ui)
        else:
            self._mut_drain_scheduled = False

    def _drain_mutations_on_ui(self) -> None:
        self._mut_drain_scheduled = False
        try:
            while True:
                ok, ev = self._mut_q.try_pop()
                if not ok:
                    break
                
                try:
                    kind = ev[0]
                except Exception as e:
                    logger.debug("[THREADING] Exception suppressed: %s", e)
                    continue
                
                if kind == 'register_active':
                    try:
                        task_obj = ev[1]
                        if task_obj is not None:
                            self._active_tasks[task_obj.task_id] = task_obj
                    except Exception as e:
                        logger.debug("[THREADING] Exception suppressed: %s", e)
                elif kind == 'unregister_active':
                    try:
                        self._active_tasks.pop(ev[1], None)
                    except Exception as e:
                        logger.debug("[THREADING] Exception suppressed: %s", e)
                else:
                    # Stats mutations
                    try:
                        pool_value = ev[1]
                        pt = next((p for p in ThreadPoolType if p.value == pool_value), None)
                        if pt and kind in self._stats[pt]:
                            self._stats[pt][kind] += 1
                    except Exception as e:
                        logger.debug("[THREADING] Exception suppressed: %s", e)
                        continue
        finally:
            if not self._shutdown and not self._mut_q.is_empty():
                self._schedule_mutation_drain()

    # Internal: stats publisher ------------------------------------------
    def _gather_stats(self) -> Dict[str, Dict[str, Any]]:
        info: Dict[str, Dict[str, Any]] = {}
        try:
            for pool_type, executor in self._executors.items():
                info[pool_type.value] = {
                    'max_workers': executor._max_workers,
                    'stats': self._stats[pool_type].copy()
                }
        except Exception as e:
            logger.debug("get_pool_info failed: %s", e)
            info = {pool.value: self._stats[pool].copy() for pool in ThreadPoolType}
        return info

    def _publish_stats_once(self) -> None:
        if self._shutdown:
            return
        try:
            snapshot = self._gather_stats()
            self._stats_tb.publish(snapshot)
        except Exception as e:
            logger.debug("Stats publish failed: %s", e)
        finally:
            if not self._shutdown:
                self._schedule_stats_publish()

    def _schedule_stats_publish(self) -> None:
        if QCoreApplication.instance() is not None:
            self.single_shot(self._stats_pub_interval_ms, self._publish_stats_once)

    def get_stats_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Return latest thread pool stats without locking"""
        latest = None
        try:
            latest = self._stats_tb.consume_latest()
        except Exception as e:
            logger.debug("[THREADING] Exception suppressed: %s", e)
            latest = None
        return latest if latest is not None else self._gather_stats()

    # UI dispatch utilities ----------------------------------------------
    @staticmethod
    def run_on_ui_thread(func: Callable, *args, **kwargs) -> None:
        """Dispatch a callable to the Qt UI thread"""
        try:
            app = QCoreApplication.instance()
            if app is None:
                logger.debug("run_on_ui_thread called without QCoreApplication")
                return
            
            if QThread.currentThread() is app.thread():
                func(*args, **(kwargs or {}))
                return
            
            inv = _ensure_ui_invoker()
            if inv is None:
                raise RuntimeError("UI invoker unavailable")
            inv.invoke.emit(func, args, kwargs or {})
        except Exception as e:
            logger.exception("run_on_ui_thread dispatch failed: %s", e)

    @staticmethod
    def single_shot(delay_ms: int, func: Callable, *args, **kwargs) -> None:
        """Schedule a callable to run on the UI thread after a delay"""
        try:
            app = QCoreApplication.instance()
            if app is None:
                raise RuntimeError("single_shot called without QCoreApplication")

            def _invoke():
                ThreadManager.run_on_ui_thread(func, *args, **(kwargs or {}))

            if QThread.currentThread() is app.thread():
                QTimer.singleShot(max(0, int(delay_ms)), _invoke)
            else:
                def _schedule_on_ui():
                    QTimer.singleShot(max(0, int(delay_ms)), _invoke)
                ThreadManager.run_on_ui_thread(_schedule_on_ui)
        except Exception as e:
            logger.exception("single_shot failed: %s", e)

    def schedule_recurring(
        self,
        interval_ms: int,
        func: Callable,
        *args,
        description: Optional[str] = None,
        **kwargs,
    ) -> QTimer:
        """
        Schedule a recurring task on the UI thread.
        
        Args:
            interval_ms: Interval in milliseconds
            func: Function to call
            *args, **kwargs: Arguments for func
        
        Returns:
            QTimer: Timer instance (keep reference to prevent GC)
        """
        _last_invoke_ts = [0.0]
        timer_desc = description
        if not timer_desc:
            try:
                timer_desc = getattr(func, "__qualname__", None) or func.__name__
            except Exception as e:
                logger.debug("[THREADING] Exception suppressed: %s", e)
                timer_desc = "recurring_timer"

        def _invoke():
            try:
                now = time.time()
                if _last_invoke_ts[0] > 0.0:
                    gap_ms = (now - _last_invoke_ts[0]) * 1000.0
                    # Only warn if gap exceeds 2x the expected interval AND is
                    # significant (>100ms). For slow timers (e.g. 1000ms weather
                    # refresh) a gap of 1007ms is normal jitter, not a problem.
                    # Modal dialogs (settings) also block the event loop, causing
                    # expected gaps that should not spam warnings.
                    threshold_ms = max(100.0, float(interval_ms) * 2.0)
                    if gap_ms > threshold_ms and is_perf_metrics_enabled():
                        logger.warning(
                            "[PERF] [TIMER] Large gap for %s: %.2fms (interval=%dms)",
                            timer_desc,
                            gap_ms,
                            interval_ms,
                        )
                _last_invoke_ts[0] = now
                func(*args, **(kwargs or {}))
            except Exception as e:
                logger.exception("Recurring task raised: %s", e)
        
        timer = QTimer()
        timer.setTimerType(Qt.TimerType.PreciseTimer)
        timer.timeout.connect(_invoke)
        timer.start(max(1, int(interval_ms)))
        
        # Register with resource manager
        if self._resource_manager:
            try:
                from core.resources.types import ResourceType
                self._resource_manager.register(
                    timer,
                    ResourceType.TIMER,
                    f"Recurring timer ({interval_ms}ms) - {timer_desc}",
                    cleanup_handler=lambda t: t.stop()
                )
            except Exception as e:
                logger.debug("Could not register timer: %s", e)
        
        return timer
