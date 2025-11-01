"""
Agnostic Thread Manager for Screen Capture Applications

A centralized thread management system designed for applications dealing with
screen capture (DWM/DXGI + renderer) and overlay rendering. Provides specialized
thread pools for different workload types with proper resource management.
"""
import os
import threading
import time
from core.logging import get_logger
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Literal
from utils.lockfree import SPSCQueue, TripleBuffer
from PySide6.QtCore import QTimer, QObject, QThread, QCoreApplication, Signal

# Use centralized core resource manager/types
from core.resources import ResourceManager, ResourceType

def get_resource_manager():
    """Get or create the global ResourceManager instance."""
    if not hasattr(get_resource_manager, '_instance'):
        get_resource_manager._instance = ResourceManager()
    return get_resource_manager._instance

logger = get_logger(__name__)


# UI-thread invoker to guarantee queued execution on the Qt main thread
class _UiInvoker(QObject):
    # Carry (callable, args tuple, kwargs dict)
    invoke = Signal(object, object, object)

    def __init__(self):
        super().__init__()
        # Connect with queued connection (default) so slot runs on this object's thread
        self.invoke.connect(self._on_invoke)

    def _on_invoke(self, func, args, kwargs):
        try:
            func(*args, **(kwargs or {}))
        except Exception as e:
            logger.exception("UI invoker callable raised: %s", e)


_ui_invoker: _UiInvoker | None = None


def _ensure_ui_invoker() -> _UiInvoker | None:
    global _ui_invoker
    try:
        app = QCoreApplication.instance()
        if app is None:
            logger.error("run_on_ui_thread: No QCoreApplication instance")
            return None
        if _ui_invoker is None:
            inv = _UiInvoker()
            # Affinitize to UI/main thread
            inv.moveToThread(app.thread())
            _ui_invoker = inv
        return _ui_invoker
    except Exception as e:
        logger.exception("Failed to initialize UI invoker: %s", e)
        return None

class TaskPriority(Enum):
    """Task priority levels for queue management"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

class ThreadPoolType(Enum):
    """Different thread pool types for specific workloads"""
    CAPTURE = "capture"      # Screen capture operations (DWM/DXGI)
    RENDER = "render"        # Renderer operations (e.g., D3D11)  
    IO = "io"               # File I/O, network operations
    COMPUTE = "compute"     # Heavy computational tasks
    UI = "ui"              # UI-related background tasks

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
        """Enable priority queue sorting"""
        return self.priority.value > other.priority.value

class ThreadManager:
    """
    Centralized thread manager with specialized pools for different workloads.
    Designed for screen capture applications with overlay rendering.
    Provides thread-safe task submission, result handling, and resource management.
    Features:
    - Thread pools for different workload types (capture, render, IO, etc.)
    - Task prioritization and dependency tracking
    - Resource cleanup and lifecycle management
    - Integration with ResourceManager for unified resource tracking
    - Thread-local storage for overlay resources
    - Statistics and monitoring
    """
    def __init__(self, config: Optional[Dict[ThreadPoolType, int]] = None, 
                 resource_manager: Optional[Any] = None):
        """
        Initialize thread manager with configurable pool sizes.
        Args:
            config: Dictionary mapping ThreadPoolType to max_workers count
                   If None, uses sensible defaults for capture applications
            resource_manager: Optional ResourceManager instance for resource tracking.
                            If None, a new instance will be created.
        """
        self._shutdown = False
        # Lock-free: Uses atomic operations and UI thread dispatch
        # Default configuration optimized for capture applications
        cpu_count = os.cpu_count() or 1
        # Keep UI responsiveness by reserving one core if possible
        compute_workers = max(1, cpu_count - 1)
        default_config = {
            ThreadPoolType.CAPTURE: 2,   # Usually 1-2 capture threads sufficient
            ThreadPoolType.RENDER: 1,    # Single OpenGL context thread
            ThreadPoolType.IO: 4,        # Multiple I/O operations
            ThreadPoolType.COMPUTE: compute_workers, # Explicit CPU count minus one
            ThreadPoolType.UI: 2         # Light UI tasks
        }
        self.config = {**default_config, **(config or {})}
        self._executors: Dict[ThreadPoolType, ThreadPoolExecutor] = {}
        self._active_tasks: Dict[str, Task] = {}
        self._stats = {pool_type: {'submitted': 0, 'completed': 0, 'failed': 0} 
                      for pool_type in ThreadPoolType}
        # Stage 2 scaffold: single-writer mutation queue (SPSC) and shadow stats
        # Producer: any thread enqueues tiny mutation events; Consumer: UI-thread drain
        self._mut_q: SPSCQueue[tuple] = self.create_spsc_queue(256)
        self._mut_shadow_stats = {pool_type: {'submitted': 0, 'completed': 0, 'failed': 0}
                                  for pool_type in ThreadPoolType}
        self._mut_drain_scheduled = False
        # Lock-free stats publisher (SPSC) - producer: TM internal; consumer: observers/UI
        self._stats_tb: TripleBuffer[Dict[str, Dict[str, Any]]] = TripleBuffer()
        self._stats_pub_interval_ms: int = 250  # light cadence
        # Initialize or use provided centralized resource manager
        self._resource_manager = resource_manager or get_resource_manager()
        # Attach this ThreadManager to ResourceManager to avoid circular imports
        try:
            attach = getattr(self._resource_manager, "attach_thread_manager", None)
            if callable(attach):
                attach(self)
        except Exception as e:
            logger.debug(f"ResourceManager.attach_thread_manager failed or not present: {e}")
        # Register thread manager as a resource and capture the assigned id
        self._resource_id = self._resource_manager.register(
            self,
            ResourceType.CUSTOM,
            "Thread manager instance",
            cleanup_handler=lambda obj: self.shutdown(),
            tags={"thread_manager"}
        )
        self._initialize_pools()
        # Start periodic stats publisher after pools initialized
        try:
            self._schedule_stats_publish()
        except Exception as e:
            logger.debug("Stats publisher scheduling failed: %s", e)
        # Start initial mutation drain tick (coalesced on UI thread)
        try:
            self._schedule_mutation_drain()
        except Exception:
            # Non-fatal; scaffold only
            pass
        # Now that executors are initialized, start ResourceManager worker
        try:
            start_worker = getattr(self._resource_manager, "start_mutation_worker", None)
            if callable(start_worker):
                start_worker(self)
        except Exception as e:
            logger.error(f"Failed to start ResourceManager mutation worker: {e}")
    def _initialize_pools(self):
        """
        Initialize thread pools based on configuration.
        
        Creates ThreadPoolExecutor instances for each configured pool type
        and registers them with the ResourceManager for cleanup tracking.
        """
        for pool_type, max_workers in self.config.items():
            if max_workers is None:
                max_workers = None  # Let ThreadPoolExecutor decide
            try:
                # Create the executor
                executor = ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix=f"{pool_type.value}_pool"
                )
                # Register the executor as a resource
                self._resource_manager.register(
                    executor,
                    ResourceType.THREAD_POOL,
                    f"Thread pool for {pool_type.value}",
                    cleanup_handler=lambda e: e.shutdown(wait=True),
                    pool_type=pool_type.value,
                    role="thread_pool"
                )
                self._executors[pool_type] = executor
                logger.info(f"Initialized {pool_type.value} pool with {max_workers} workers")
            except Exception as e:
                logger.error(f"Failed to initialize {pool_type.value} pool: {e}")
                # Clean up any partially initialized executors
                self.shutdown()
                raise RuntimeError(f"Failed to initialize {pool_type.value} thread pool: {e}")
    def submit_task(self, pool_type: ThreadPoolType, func: Callable, *args,
                   task_id: str = None, priority: TaskPriority = TaskPriority.NORMAL,
                   callback: Callable[[TaskResult], None] = None, 
                   resource_tags: Optional[Set[str]] = None, **kwargs) -> str:
        """
        Submit a task to the specified thread pool.
        Args:
            pool_type: Which thread pool to use
            func: Function to execute
            *args: Positional arguments for func
            task_id: Optional unique identifier for the task
            priority: Task priority (currently informational)
            callback: Optional callback function for result handling
            **kwargs: Keyword arguments for func
        Returns:
            str: Task ID for tracking
        Raises:
            RuntimeError: If thread manager is shut down
        """
        if self._shutdown:
            raise RuntimeError("Thread manager is shut down")
        task = Task(func, *args, task_id=task_id, priority=priority, **kwargs)
        # Lock-free: Atomic read of executor reference
        executor = self._executors[pool_type]
        # Wrap the function to handle result processing
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
                    # Route stats mutation via single-writer queue (authoritative)
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
                    # Route stats mutation via single-writer queue (authoritative)
                    self._enqueue_mutation(('failed', pool_type.value))
                finally:
                    # Route active-task unregister via single-writer queue
                    self._enqueue_mutation(('unregister_active', task.task_id))
                # Execute callback if provided
                if callback:
                    try:
                        callback(task_result)
                    except Exception as e:
                        logger.error(f"Callback for task {task.task_id} failed: {e}")
                return task_result
        # Submit to executor
        future = executor.submit(wrapped_func)
        task.future = future
        # Register the future as a resource if resource manager is available
        if self._resource_manager:
            try:
                self._resource_manager.register(
                    future,
                    ResourceType.CUSTOM,
                    f"Task future for {task.task_id} in pool {pool_type.value}",
                    cleanup_handler=lambda f: f.cancel() if not f.done() else None,
                    pool=pool_type.value,
                    task_id=task.task_id,
                    function=getattr(func, "__name__", str(func)),
                    created_by="ThreadManager.submit_task",
                    tags=list({"task", f"pool:{pool_type.value}", *(resource_tags or set() or set())})
                )
            except TypeError as e:
                # Skip registration if object is not weakref-able
                logger.debug(f"Skipping resource registration for task {task.task_id}: {e}")
        # Route active-task register and stats submitted via single-writer queue
        self._enqueue_mutation(('register_active', task))
        self._enqueue_mutation(('submitted', pool_type.value))
        logger.debug(f"Submitted task {task.task_id} to {pool_type.value} pool")
        return task.task_id

    def submit_io_task(self, func: Callable, *args, **kwargs) -> str:
        """Convenience API for IO pool submissions used by ResourceManager.

        This avoids ResourceManager needing to import ThreadPoolType.
        """
        return self.submit_task(ThreadPoolType.IO, func, *args, **kwargs)
    def get_task_result(self, task_id: str, timeout: Optional[float] = None) -> TaskResult:
        """
        Get the result of a specific task.
        Args:
            task_id: The task identifier
            timeout: Maximum time to wait for result
        Returns:
            TaskResult: The task execution result
        Raises:
            KeyError: If task_id is not found
            TimeoutError: If timeout is exceeded
        """
        # Lock-free: Atomic read of task reference
        task = self._active_tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found or already completed")
        try:
            return task.future.result(timeout=timeout)
        except Exception as e:
            if timeout and isinstance(e, TimeoutError):
                raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")
            raise
    def cancel_task(self, task_id: str) -> bool:
        """
        Attempt to cancel a task.
        Args:
            task_id: The task identifier
        Returns:
            bool: True if task was successfully cancelled
        """
        # Lock-free: Atomic read of task reference
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
        # Lock-free: Atomic read of task keys
        return list(self._active_tasks.keys())
    def get_pool_stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics for all thread pools"""
        # Lock-free: Atomic read of stats
        return {pool_type.value: stats.copy() 
               for pool_type, stats in self._stats.items()}
    def get_pool_info(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed information about thread pools"""
        info = {}
        # Lock-free: Atomic read of executor info
        for pool_type, executor in self._executors.items():
            info[pool_type.value] = {
                'max_workers': executor._max_workers,
                    'active_threads': len(executor._threads),
                    'pending_tasks': executor._work_queue.qsize(),
                    'stats': self._stats[pool_type].copy()
                }
        return info
    @contextmanager
    def capture_context(self):
        """
        Context manager for capture operations.
        Provides easy access to capture-specific functionality.
        Example:
            with thread_manager.capture_context() as ctx:
                ctx.submit_capture(capture_func)
                ctx.submit_render(render_func)
        """
        if self._shutdown:
            raise RuntimeError("Thread manager is shut down")
        # Create a simple namespace for the context
        class CaptureContext:
            def __init__(self, manager):
                self.manager = manager
            def submit_capture(self, func: Callable, *args, **kwargs) -> str:
                return self.manager.submit_task(ThreadPoolType.CAPTURE, func, *args, **kwargs)
            def submit_render(self, func: Callable, *args, **kwargs) -> str:
                # Render pool is intentionally single-threaded for renderer/DWM context affinity
                return self.manager.submit_task(ThreadPoolType.RENDER, func, *args, **kwargs)
        # Create context and yield it
        ctx = CaptureContext(self)
        yield ctx
    def shutdown(self, wait: bool = True, timeout: Optional[float] = None):
        """
        Shutdown all thread pools and clean up resources.
        Args:
            wait: Whether to wait for active tasks to complete
            timeout: Maximum time to wait for shutdown
        """
        logger.info("Shutting down thread manager...")
        try:
            # Pre-shutdown diagnostics
            info = self.get_pool_info()
            logger.debug(f"[TM] Pre-shutdown pool info: {info}")
            logger.debug(f"[TM] Active tasks before shutdown: {list(self._active_tasks.keys())}")
        except Exception:
            pass
        current_thread = threading.current_thread()
        
        # Lock-free: Atomic check and set shutdown state
        if self._shutdown:
            return  # Already shutting down or shut down
        self._shutdown = True
        
        # Capture references we need
        resource_manager = self._resource_manager
        active_task_ids = list(self._active_tasks.keys())
        executors = list(self._executors.items())
        resource_id = getattr(self, "_resource_id", None)
        
        # Attempt to proactively stop HotkeyManager message loop to unblock IO pool
        try:
            from core.hotkeys.manager import HotkeyManager  # local import to avoid cycles
            try:
                hk = HotkeyManager()
                hk.shutdown()
                logger.debug("[TM] Proactively shut down HotkeyManager prior to executor shutdown")
            except Exception as e:
                logger.debug(f"[TM] HotkeyManager pre-shutdown failed or not present: {e}")
        except Exception:
            pass

        # Now perform potentially blocking operations without holding the lock
        # Proactively stop ResourceManager's IO-pool mutation worker to avoid pool shutdown hangs
        try:
            if resource_manager is not None:
                stop = getattr(resource_manager, "stop_mutation_worker", None)
                if callable(stop):
                    stop(timeout=0.75)
        except Exception:
            # Best effort; continue shutdown regardless
            pass
            
        # Cancel all active tasks
        for task_id in active_task_ids:
            self.cancel_task(task_id)
            
        # Shutdown executors with awareness of caller thread to avoid self-join deadlocks
        for pool_type, executor in executors:
            try:
                in_pool = False
                try:
                    in_pool = hasattr(executor, "_threads") and (current_thread in executor._threads)  # type: ignore[attr-defined]
                except Exception:
                    in_pool = False
                if in_pool:
                    logger.debug(
                        "Shutting down %s pool from one of its worker threads; using non-blocking shutdown to avoid deadlock",
                        pool_type.value,
                    )
                    executor.shutdown(wait=False, cancel_futures=True)
                else:
                    logger.debug(f"Shutting down {pool_type.value} pool...")
                    executor.shutdown(wait=wait, cancel_futures=not wait)
            except Exception as e:
                logger.error(f"Error shutting down {pool_type.value} pool: {e}")
                
        # Clean up resource manager registration if present
        if resource_manager and resource_id:
            try:
                # Avoid enqueueing unregister on ResourceManager mutation worker if it's active
                worker_active = bool(getattr(resource_manager, "_worker_started", False))
                on_pool_thread = any(
                    hasattr(ex, "_threads") and (current_thread in ex._threads)  # type: ignore[attr-defined]
                    for _, ex in executors
                )
                if worker_active and on_pool_thread:
                    logger.debug(
                        "Skipping ResourceManager.unregister for ThreadManager during shutdown (worker active on pool thread)"
                    )
                else:
                    if getattr(resource_manager, "get", None):
                        if resource_manager.get(resource_id) is not None:
                            resource_manager.unregister(resource_id, force=True)  # type: ignore[arg-type]
                    else:
                        # Fallback: attempt to unregister directly
                        resource_manager.unregister(resource_id, force=True)  # type: ignore[arg-type]
            except Exception:
                # Best-effort cleanup; do not mask shutdown path
                pass

        # Post-shutdown diagnostics
        try:
            info2 = self.get_pool_info()
            logger.debug(f"[TM] Post-executor-shutdown pool info: {info2}")
            logger.debug(f"[TM] Active tasks after shutdown: {list(self._active_tasks.keys())}")
        except Exception:
            pass

    # Internal: stats publisher ------------------------------------------------
    def _gather_stats(self) -> Dict[str, Dict[str, Any]]:
        info: Dict[str, Dict[str, Any]] = {}
        # Use existing get_pool_info which already handles locking
        try:
            info = self.get_pool_info()
        except Exception as e:
            logger.debug("get_pool_info failed for stats publish: %s", e)
            # Fallback minimal stats
            # Lock-free: Atomic read of stats
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
            # Reschedule if still active
            if not self._shutdown:
                self._schedule_stats_publish()

    # Stage 2 scaffold: mutation queue drain ----------------------------------
    def _enqueue_mutation(self, ev: tuple) -> None:
        """Best-effort enqueue of a tiny mutation event.

        Event formats:
          - ("register_active", Task)
          - ("unregister_active", task_id)
          - ("submitted"|"completed"|"failed", pool_value)
        """
        if self._shutdown:
            return
        try:
            self._mut_q.push_drop_oldest(ev)
        except Exception:
            # Drop on failure; best-effort
            return
        # For registration, schedule immediate drain to preserve submit semantics
        if isinstance(ev, tuple) and ev and ev[0] == 'register_active':
            self._schedule_mutation_drain(0)
        else:
            self._schedule_mutation_drain()

    def _schedule_mutation_drain(self, delay_ms: int = 10) -> None:
        if self._shutdown:
            return
        # Coalesce drains onto UI thread using existing timer infra
        if not self._mut_drain_scheduled:
            self._mut_drain_scheduled = True
            # Guard against early initialization before Qt app exists
            from PySide6.QtCore import QCoreApplication
            if QCoreApplication.instance() is not None:
                # Small window to batch bursts
                self.single_shot(max(0, int(delay_ms)), self._drain_mutations_on_ui)
            else:
                # No Qt yet - just mark as not scheduled so it can retry later
                self._mut_drain_scheduled = False

    def _drain_mutations_on_ui(self) -> None:
        self._mut_drain_scheduled = False
        drained = 0
        try:
            while True:
                ok, ev = self._mut_q.try_pop()
                if not ok:
                    break
                drained += 1
                try:
                    kind = ev[0]
                except Exception:
                    continue
                # Active task registration/unregistration
                if kind == 'register_active':
                    # ev[1] is Task object
                    try:
                        task_obj = ev[1]
                        if task_obj is not None:
                            # Lock-free: Atomic write to active tasks
                            self._active_tasks[task_obj.task_id] = task_obj
                    except Exception:
                        pass
                    continue
                if kind == 'unregister_active':
                    try:
                        task_id = ev[1]
                        # Lock-free: Atomic removal from active tasks
                        self._active_tasks.pop(task_id, None)
                    except Exception:
                        pass
                    continue
                # Stats mutations: ('submitted'|'completed'|'failed', pool_value)
                try:
                    pool_value = ev[1]
                    pt = next((p for p in ThreadPoolType if p.value == pool_value), None)
                    if pt is None:
                        continue
                    # Lock-free: Atomic stats update
                    stats = self._stats[pt]
                    if kind in stats:
                        stats[kind] += 1
                        sh = self._mut_shadow_stats[pt]
                        if kind in sh:
                            sh[kind] += 1
                except Exception:
                    continue
        finally:
            # If queue not empty, schedule another tick
            if not self._shutdown and not self._mut_q.is_empty():
                self._schedule_mutation_drain()

    def _schedule_stats_publish(self) -> None:
        # Use single_shot to avoid raw timers here and keep cadence light
        # Guard against early initialization before Qt app exists
        from PySide6.QtCore import QCoreApplication
        if QCoreApplication.instance() is not None:
            self.single_shot(self._stats_pub_interval_ms, self._publish_stats_once)
        # else: skip stats publishing until Qt is ready (non-critical feature)

    def get_stats_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Return latest thread pool stats without taking locks if available.

        Falls back to a locked copy if no published snapshot yet.
        """
        latest = None
        try:
            latest = self._stats_tb.consume_latest()
        except Exception:
            latest = None
        if latest is not None:
            return latest
        # Fallback
        return self._gather_stats()

    # UI dispatch utilities ---------------------------------------------------
    @staticmethod
    def run_on_ui_thread(func: Callable, *args, **kwargs) -> None:
        """Dispatch a callable to the Qt UI thread reliably.

        - If already on the UI thread, invoke immediately.
        - Otherwise, enqueue via a UI-thread-affine QObject signal.
        """
        try:
            app = QCoreApplication.instance()
            if app is None:
                # During test teardown, QApplication may be destroyed - silently skip
                logger = get_logger("ThreadManager")
                logger.debug("run_on_ui_thread called without QCoreApplication - skipping (likely test teardown)")
                return
            # If we are already on UI thread, call directly
            if QThread.currentThread() is app.thread():
                func(*args, **(kwargs or {}))
                return
            inv = _ensure_ui_invoker()
            if inv is None:
                raise RuntimeError("UI invoker unavailable")
            inv.invoke.emit(func, args, kwargs or {})
        except Exception as e:
            logger.exception("run_on_ui_thread dispatch failed: %s", e)

    def run_in_main_thread(self, func: Callable, *args, **kwargs):
        """Execute callable on Qt main thread and return its result.

        Behavior:
        - If no Q(Core)Application exists (e.g., unit tests), executes inline.
        - If already on UI thread, executes inline.
        - Otherwise, dispatches to UI thread and blocks until completion.
        """
        try:
            app = QCoreApplication.instance()
            if app is None:
                # In tests or early bootstrap without Qt, execute inline
                return func(*args, **(kwargs or {}))
            if QThread.currentThread() is app.thread():
                return func(*args, **(kwargs or {}))

            # Cross-thread: dispatch and wait
            done = threading.Event()
            box: Dict[str, Any] = {}

            def _invoke():
                try:
                    box['result'] = func(*args, **(kwargs or {}))
                except Exception as e:
                    box['error'] = e
                finally:
                    done.set()

            ThreadManager.run_on_ui_thread(_invoke)
            done.wait()
            if 'error' in box:
                raise box['error']
            return box.get('result', None)
        except Exception as e:
            logger.exception("run_in_main_thread failed: %s", e)
            # Best-effort fallback: try inline to avoid complete failure in production
            try:
                return func(*args, **(kwargs or {}))
            except Exception:
                raise

    @staticmethod
    def single_shot(delay_ms: int, func: Callable, *args, **kwargs) -> None:
        """Schedule a callable to run on the UI thread after a delay.

        Centralized timer-based deferral using QTimer under the hood.
        This preserves the no-raw-QTimer policy for application modules.

        Args:
            delay_ms: Delay in milliseconds (0 for next event loop tick)
            func: Callable to execute on the UI thread
            *args, **kwargs: Arguments for the callable
        """
        try:
            app = QCoreApplication.instance()
            if app is None:
                raise RuntimeError("single_shot called without a QCoreApplication")

            def _invoke():
                ThreadManager.run_on_ui_thread(func, *args, **(kwargs or {}))

            # Always create the QTimer on the UI/main thread to avoid
            # "QObject::startTimer" errors from worker threads.
            if QThread.currentThread() is app.thread():
                # Already on UI thread; safe to start timer directly
                QTimer.singleShot(max(0, int(delay_ms)), _invoke)
            else:
                # Bounce to UI thread to create the timer there
                def _schedule_on_ui():
                    QTimer.singleShot(max(0, int(delay_ms)), _invoke)
                ThreadManager.run_on_ui_thread(_schedule_on_ui)
        except Exception as e:
            logger.exception("single_shot failed: %s", e)

    # Lock-free primitive factories ------------------------------------------
    def create_spsc_queue(self, capacity: int) -> SPSCQueue:
        """Create a bounded SPSC ring buffer for single producer/consumer handoff.

        Args:
            capacity: Fixed capacity (>1)
        Returns:
            SPSCQueue instance
        """
        return SPSCQueue(capacity)

    def create_triple_buffer(self) -> TripleBuffer:
        """Create a TripleBuffer for latest-value exchange in SPSC scenarios."""
        return TripleBuffer()

    def create_ui_coalescer(
        self,
        name: str,
        capacity: int = 64,
        mode: Literal["latest", "merge"] = "latest",
        window_ms: int = 7,
    ) -> "UICoalescer":
        """Factory for a UI coalescer helper.

        Registers the coalescer with ResourceManager for tracked cleanup.
        """
        if self._shutdown:
            raise RuntimeError("Thread manager is shut down")
        coalescer = UICoalescer(name=name, thread_manager=self, capacity=capacity, mode=mode, window_ms=window_ms)
        # Register with ResourceManager for lifecycle tracking
        if self._resource_manager:
            try:
                self._resource_manager.register(
                    coalescer,
                    ResourceType.CUSTOM,
                    f"UI Coalescer '{name}'",
                    cleanup_handler=lambda c: c.shutdown(),
                    tags={"ui_coalescer", name},
                    mode=mode,
                    capacity=int(capacity),
                    window_ms=int(window_ms),
                    created_by="ThreadManager.create_ui_coalescer",
                )
            except TypeError:
                # Non-weakref-able scenario should be rare; skip registration
                pass
        return coalescer

    # UI Coalescer ------------------------------------------------------------
    
class UICoalescer:
    """UI-thread coalescer backed by SPSCQueue.

    - Single producer (background) enqueues small UI tasks via `submit(callable)`.
    - A single scheduled drain runs on the UI thread after a small window to
      batch and coalesce bursts. No raw QTimer usage outside ThreadManager.
    - Mode 'latest' drops oldest entries on overflow.
    """
    def __init__(
        self,
        name: str,
        thread_manager: "ThreadManager",
        capacity: int = 64,
        mode: Literal["latest", "merge"] = "latest",
        window_ms: int = 7,
    ) -> None:
        self._name = name
        self._tm = thread_manager
        self._q: SPSCQueue[Callable[[], None]] = self._tm.create_spsc_queue(int(capacity))
        self._mode = mode
        self._window_ms = max(0, int(window_ms))
        self._shutdown = False
        # Guard scheduling flag across producer (any thread) and consumer (UI)
        # Lock-free: Uses atomic flag for scheduling coordination
        self._drain_scheduled = False
        # Note: _sched_lock removed in lock-free migration - using atomic flag only

    def submit(self, task: Callable[[], None]) -> None:
        if self._shutdown or task is None:
            return
        try:
            # Coalescing policy: drop-oldest on overflow to keep freshest tasks
            self._q.push_drop_oldest(task)
        except Exception as e:
            logger.exception("UICoalescer[%s] enqueue failed: %s", self._name, e)
            return
        # Schedule a drain tick if not already scheduled (lock-free atomic flag)
        if not self._drain_scheduled:
            self._drain_scheduled = True
            self._tm.single_shot(self._window_ms, self._drain_on_ui)

    def flush(self) -> None:
        """Force an immediate drain on the UI thread."""
        if self._shutdown:
            return
        # Force immediate drain (lock-free atomic flag)
        if not self._drain_scheduled:
            self._drain_scheduled = True
            self._tm.single_shot(0, self._drain_on_ui)

    def shutdown(self) -> None:
        """Stop scheduling and best-effort drain then clear."""
        self._shutdown = True
        try:
            self.flush()
        except Exception:
            pass
        try:
            self._q.clear()
        except Exception:
            pass

    # Internal ----------------------------------------------------------------
    def _drain_on_ui(self) -> None:
        if self._shutdown:
            self._drain_scheduled = False
            return
        count = 0
        try:
            while True:
                ok, task = self._q.try_pop()
                if not ok:
                    break
                if task is None:
                    continue
                try:
                    task()
                except Exception as e:
                    logger.exception("UICoalescer[%s] task raised: %s", self._name, e)
                count += 1
        finally:
            # Reset scheduling flag (lock-free atomic)
            self._drain_scheduled = False
        if count > 1:
            logger.debug("UICoalescer[%s] drained %d tasks (coalesced=%d)", self._name, count, count - 1)
        # If items arrived during drain, schedule another tick
        if not self._shutdown and not self._q.is_empty():
            # Force immediate drain (lock-free atomic flag)
            if not self._drain_scheduled:
                self._drain_scheduled = True
                self._tm.single_shot(0, self._drain_on_ui)
