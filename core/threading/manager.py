"""
Thread Manager for Screensaver Application

Centralized thread management with specialized pools for IO and compute operations.
Adapted from SPQDocker reusable modules for screensaver use.
"""
import os
import threading
import time
import weakref
from concurrent.futures import ThreadPoolExecutor, Future, wait as wait_futures
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from utils.lockfree import SPSCQueue, TripleBuffer
from PySide6.QtCore import QTimer, QObject, QThread, QCoreApplication, Signal, Qt
from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled

logger = get_logger(__name__)

_ui_diagnostic_lock = threading.Lock()
_single_shot_registry_lock = threading.RLock()
_single_shot_timers: Dict[str, set[QTimer]] = {}
_cancelled_single_shot_generations: set[str] = set()
_cancelled_ui_generations: set[str] = set()
_ui_diagnostics: Dict[str, Any] = {
    "queued": 0,
    "delivered": 0,
    "failed": 0,
    "rejected": 0,
    "active": 0,
    "queue_depth": 0,
    "last_callback": "<none>",
    "last_duration_ms": 0.0,
    "last_completed_ts": 0.0,
    "queued_by_generation": {},
    "delivered_by_generation": {},
    "scheduled_single_shots": 0,
    "scheduled_single_shots_by_generation": {},
}


def _qt_dispatch_available() -> bool:
    """Return whether creating or delivering Qt work is still safe."""

    return (
        QCoreApplication.instance() is not None
        and not QCoreApplication.closingDown()
    )


def _generation_key(generation: object | None) -> str:
    return str(generation) if generation is not None else "process_or_unknown"


def _record_ui_queue(func: Callable | None = None) -> None:
    _owner, _owner_class, _owner_id, generation = _callable_runtime_identity(func)
    key = _generation_key(generation)
    with _ui_diagnostic_lock:
        _ui_diagnostics["queued"] += 1
        _ui_diagnostics["queue_depth"] += 1
        queued = _ui_diagnostics["queued_by_generation"]
        queued[key] = int(queued.get(key, 0)) + 1


def _ui_generation_cancelled(generation: object | None) -> bool:
    if generation is None:
        return False
    key = _generation_key(generation)
    with _ui_diagnostic_lock:
        return key in _cancelled_ui_generations


def _record_single_shot_scheduled(generation: object | None) -> None:
    key = _generation_key(generation)
    with _ui_diagnostic_lock:
        _ui_diagnostics["scheduled_single_shots"] += 1
        scheduled = _ui_diagnostics["scheduled_single_shots_by_generation"]
        scheduled[key] = int(scheduled.get(key, 0)) + 1


def _record_single_shot_delivered(generation: object | None) -> None:
    key = _generation_key(generation)
    with _ui_diagnostic_lock:
        _ui_diagnostics["scheduled_single_shots"] = max(
            0, int(_ui_diagnostics["scheduled_single_shots"]) - 1
        )
        scheduled = _ui_diagnostics["scheduled_single_shots_by_generation"]
        remaining = max(0, int(scheduled.get(key, 0)) - 1)
        if remaining:
            scheduled[key] = remaining
        else:
            scheduled.pop(key, None)
    _prune_cancelled_single_shot_generation(key)


def _prune_cancelled_single_shot_generation(key: str) -> None:
    with _ui_diagnostic_lock:
        pending = int(
            _ui_diagnostics["scheduled_single_shots_by_generation"].get(key, 0)
        )
    with _single_shot_registry_lock:
        if pending == 0 and not _single_shot_timers.get(key):
            _cancelled_single_shot_generations.discard(key)
            _single_shot_timers.pop(key, None)


def _single_shot_generation_cancelled(key: str) -> bool:
    with _single_shot_registry_lock:
        return key in _cancelled_single_shot_generations


def _register_single_shot_timer(key: str, timer: QTimer) -> bool:
    with _single_shot_registry_lock:
        if key in _cancelled_single_shot_generations:
            return False
        _single_shot_timers.setdefault(key, set()).add(timer)
        return True


def _unregister_single_shot_timer(key: str, timer: QTimer | None) -> None:
    if timer is not None:
        with _single_shot_registry_lock:
            timers = _single_shot_timers.get(key)
            if timers is not None:
                timers.discard(timer)
                if not timers:
                    _single_shot_timers.pop(key, None)
    _prune_cancelled_single_shot_generation(key)


def _run_tracked_ui_callable(
    func: Callable,
    args: tuple,
    kwargs: dict,
    *,
    was_queued: bool,
) -> None:
    label = _callable_debug_name(func)
    _owner, _owner_class, _owner_id, generation = _callable_runtime_identity(func)
    generation_key = _generation_key(generation)
    started = time.perf_counter()
    rejected = _ui_generation_cancelled(generation) or not _qt_dispatch_available()
    with _ui_diagnostic_lock:
        if was_queued:
            _ui_diagnostics["queue_depth"] = max(
                0,
                int(_ui_diagnostics["queue_depth"]) - 1,
            )
            queued = _ui_diagnostics["queued_by_generation"]
            remaining = max(0, int(queued.get(generation_key, 0)) - 1)
            if remaining:
                queued[generation_key] = remaining
            else:
                queued.pop(generation_key, None)
        _ui_diagnostics["last_callback"] = label
        if rejected:
            _ui_diagnostics["delivered"] += 1
            _ui_diagnostics["rejected"] += 1
            delivered = _ui_diagnostics["delivered_by_generation"]
            delivered[generation_key] = int(delivered.get(generation_key, 0)) + 1
            _ui_diagnostics["last_duration_ms"] = 0.0
            _ui_diagnostics["last_completed_ts"] = time.time()
            return
        _ui_diagnostics["active"] += 1
    failed = False
    try:
        func(*args, **(kwargs or {}))
    except Exception:
        failed = True
        raise
    finally:
        duration_ms = (time.perf_counter() - started) * 1000.0
        with _ui_diagnostic_lock:
            _ui_diagnostics["active"] = max(
                0,
                int(_ui_diagnostics["active"]) - 1,
            )
            _ui_diagnostics["delivered"] += 1
            delivered = _ui_diagnostics["delivered_by_generation"]
            delivered[generation_key] = int(delivered.get(generation_key, 0)) + 1
            if failed:
                _ui_diagnostics["failed"] += 1
            _ui_diagnostics["last_callback"] = label
            _ui_diagnostics["last_duration_ms"] = duration_ms
            _ui_diagnostics["last_completed_ts"] = time.time()


def _callable_debug_name(func: Callable | None) -> str:
    """Return a compact callable label for async diagnostics."""
    if func is None:
        return "None"
    try:
        owner = getattr(func, "__self__", None)
        name = getattr(func, "__qualname__", None) or getattr(func, "__name__", None)
        if owner is not None and name:
            return f"{owner.__class__.__name__}.{name}"
        if name:
            return str(name)
    except Exception:
        pass
    return repr(func)


def _callable_runtime_identity(
    func: Callable | None,
) -> tuple[object | None, str | None, int | None, object | None]:
    """Return passive owner/generation metadata without retaining new owners."""

    if func is None:
        return None, None, None, None
    owner = getattr(func, "__self__", None)
    if owner is None:
        owner = getattr(func, "_srpss_timer_owner", None)
    generation = getattr(func, "_srpss_runtime_generation", None)
    if owner is None:
        return None, None, None, generation

    current = owner
    for _ in range(16):
        value = getattr(current, "_runtime_generation", None)
        if value is not None:
            generation = value
            break
        parent_getter = getattr(current, "parent", None)
        if not callable(parent_getter):
            break
        try:
            current = parent_getter()
        except RuntimeError:
            break
        if current is None:
            break
    return owner, type(owner).__name__, id(owner), generation


def _describe_timer_callable_context(func: Callable) -> dict | None:
    """Best-effort context for recurring-timer gap diagnostics."""
    owner = getattr(func, "__self__", None)
    if owner is None:
        owner = getattr(func, "_srpss_timer_owner", None)
    if owner is None:
        return None

    context: Dict[str, Any] = {
        "owner_type": owner.__class__.__name__,
    }
    try:
        object_name_getter = getattr(owner, "objectName", None)
        if callable(object_name_getter):
            object_name = object_name_getter()
        else:
            object_name = object_name_getter
        if object_name:
            context["object_name"] = object_name
    except Exception:
        pass
    try:
        if hasattr(owner, "isVisible"):
            context["owner_visible"] = bool(owner.isVisible())
        if hasattr(owner, "isEnabled"):
            context["owner_enabled"] = bool(owner.isEnabled())
    except Exception:
        pass
    try:
        if hasattr(owner, "screen_index"):
            context["screen_index"] = getattr(owner, "screen_index")
    except Exception:
        pass
    try:
        if hasattr(owner, "_vis_mode_str"):
            context["vis_mode"] = getattr(owner, "_vis_mode_str")
    except Exception:
        pass
    try:
        if hasattr(owner, "_mode_transition_phase"):
            context["vis_phase"] = getattr(owner, "_mode_transition_phase")
    except Exception:
        pass
    try:
        if hasattr(owner, "_mode_transition_pending"):
            pending = getattr(owner, "_mode_transition_pending")
            context["vis_pending_mode"] = getattr(pending, "name", None) if pending is not None else None
    except Exception:
        pass
    try:
        if hasattr(owner, "_waiting_for_fresh_engine_frame"):
            context["vis_waiting_engine"] = bool(getattr(owner, "_waiting_for_fresh_engine_frame"))
        if hasattr(owner, "_waiting_for_fresh_frame"):
            context["vis_waiting_frame"] = bool(getattr(owner, "_waiting_for_fresh_frame"))
    except Exception:
        pass
    try:
        parent = owner.parent() if hasattr(owner, "parent") else None
        if parent is not None and hasattr(parent, "screen_index"):
            context["parent_screen_index"] = getattr(parent, "screen_index")
        if parent is not None and hasattr(parent, "get_transition_snapshot"):
            context["display_transition"] = parent.get_transition_snapshot()
        gl_compositor = getattr(parent, "_gl_compositor", None) if parent is not None else None
        if gl_compositor is not None and hasattr(gl_compositor, "describe_stall_context"):
            context["compositor"] = gl_compositor.describe_stall_context()
    except Exception:
        logger.debug("[THREADING] Failed to describe timer callable context", exc_info=True)
    try:
        if context.get("owner_type") == "MediaWidget":
            for attr_name, context_name in (
                ("_provider", "media_provider"),
                ("_current_poll_stage", "media_poll_stage"),
                ("_update_timer_interval_ms", "media_timer_interval_ms"),
                ("_refresh_in_flight", "media_refresh_in_flight"),
                ("_is_idle", "media_idle"),
                ("_app_process_running", "media_app_process_running"),
                ("_fade_in_completed", "media_fade_in_completed"),
                ("_has_seen_first_track", "media_seen_first_track"),
            ):
                if hasattr(owner, attr_name):
                    context[context_name] = getattr(owner, attr_name)
    except Exception:
        logger.debug("[THREADING] Failed to describe MediaWidget timer context", exc_info=True)
    return context


def _should_suppress_large_timer_gap_warning(
    gap_ms: float,
    interval_ms: int,
    context: dict | None,
) -> bool:
    """Return True when a recurring-timer gap is expected by shared transition ownership.

    The visualizer hands steady cadence to AnimationManager during transitions and
    resumes its dedicated recurring timer afterward. That intentional handoff should
    not be logged as a pathological UI-thread stall.
    """
    if not isinstance(context, dict):
        return False

    if bool(context.get("vis_waiting_engine")) or bool(context.get("vis_waiting_frame")):
        return True
    if context.get("vis_pending_mode"):
        return True

    display_transition = context.get("display_transition")
    if isinstance(display_transition, dict):
        if bool(display_transition.get("running")) or bool(display_transition.get("pending")):
            return True

    compositor = context.get("compositor")
    if not isinstance(compositor, dict):
        return False

    if compositor.get("current_transition") or bool(compositor.get("has_frame_state")):
        return True

    render_strategy = compositor.get("render_strategy")
    timer_state = None
    if isinstance(render_strategy, dict):
        timer = render_strategy.get("timer")
        if isinstance(timer, dict):
            timer_state = timer.get("state")

    if not isinstance(display_transition, dict):
        return False

    last_transition = display_transition.get("last_transition")
    idle_age = display_transition.get("idle_age")
    try:
        idle_age_ms = max(0.0, float(idle_age) * 1000.0) if idle_age is not None else None
    except Exception:
        idle_age_ms = None

    # Suppress the first resumed dedicated-timer tick after a transition if most
    # of the measured gap clearly belonged to the transition-owned cadence window.
    if (
        last_transition
        and timer_state in {"PAUSED", "IDLE"}
        and idle_age_ms is not None
        and gap_ms > max(100.0, float(interval_ms) * 2.0)
        and idle_age_ms <= min(500.0, gap_ms * 0.25)
    ):
        return True

    return False


def _classify_large_timer_gap_warning(context: dict | None) -> str:
    """Return a coarse likely-cause label for loud timer-gap diagnostics."""
    if not isinstance(context, dict):
        return "unknown_ui_thread_stall"

    if bool(context.get("vis_waiting_engine")) or bool(context.get("vis_waiting_frame")) or context.get("vis_pending_mode"):
        return "visualizer_reconfiguration_starvation"

    if context.get("owner_type") == "MediaWidget":
        return "media_widget_poll_starvation"

    display_transition = context.get("display_transition")
    if isinstance(display_transition, dict):
        if bool(display_transition.get("running")) or bool(display_transition.get("pending")):
            return "display_transition_starvation"

    compositor = context.get("compositor")
    if isinstance(compositor, dict):
        if compositor.get("current_transition") or bool(compositor.get("has_frame_state")):
            return "compositor_transition_starvation"
        render_strategy = compositor.get("render_strategy")
        if isinstance(render_strategy, dict):
            timer = render_strategy.get("timer")
            if isinstance(timer, dict) and timer.get("state") in {"RUNNING", "PAUSED"}:
                return "compositor_cadence_starvation"

    return "unknown_ui_thread_stall"


# UI-thread invoker for reliable main thread dispatch
class _UiInvoker(QObject):
    invoke = Signal(object, object, object)

    def __init__(self):
        super().__init__()
        self.invoke.connect(self._on_invoke)

    def _on_invoke(self, func, args, kwargs):
        try:
            _run_tracked_ui_callable(
                func,
                tuple(args or ()),
                dict(kwargs or {}),
                was_queued=True,
            )
        except Exception as e:
            logger.exception("UI invoker callable raised: %s", e)


_ui_invoker: Optional[_UiInvoker] = None


def _ensure_ui_invoker() -> Optional[_UiInvoker]:
    global _ui_invoker
    try:
        app = QCoreApplication.instance()
        if app is None or QCoreApplication.closingDown():
            logger.debug("run_on_ui_thread: Qt event loop is unavailable")
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
    """Wrapper for executable tasks with metadata."""

    def __init__(
        self,
        func: Callable,
        *args,
        task_id: str = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        category: str = "uncategorized",
        **kwargs,
    ):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.task_id = task_id or f"task_{id(self)}"
        self.priority = priority
        self.category = str(category or "uncategorized")
        self.created_at = time.time()
        self.future: Optional[Future] = None
        _owner, owner_class, owner_id, generation = _callable_runtime_identity(func)
        self.owner_class = owner_class
        self.owner_id = owner_id
        self.runtime_generation = generation

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
    _app_shared_manager: Optional["ThreadManager"] = None
    _app_shared_lock = threading.RLock()
    _max_task_categories = 64
    _max_task_category_length = 80

    @classmethod
    def set_app_shared(cls, manager: Optional["ThreadManager"]) -> Optional["ThreadManager"]:
        """Register the app-shared ThreadManager used by runtime/helper fallback paths."""
        with cls._app_shared_lock:
            cls._app_shared_manager = manager
            return cls._app_shared_manager

    @classmethod
    def get_app_shared(cls) -> Optional["ThreadManager"]:
        """Return the currently registered app-shared ThreadManager, if any."""
        with cls._app_shared_lock:
            manager = cls._app_shared_manager
            if manager is not None and getattr(manager, "_shutdown", False):
                cls._app_shared_manager = None
                return None
            return manager

    @classmethod
    def get_or_create_app_shared(
        cls,
        *,
        resource_manager: Optional[Any] = None,
        config: Optional[Dict[ThreadPoolType, int]] = None,
    ) -> "ThreadManager":
        """Return the app-shared ThreadManager, creating one if necessary."""
        with cls._app_shared_lock:
            manager = cls._app_shared_manager
            if manager is None or getattr(manager, "_shutdown", False):
                manager = cls(config=config, resource_manager=resource_manager)
                cls._app_shared_manager = manager
            return manager

    @classmethod
    def create_helper_manager(
        cls,
        *,
        resource_manager: Optional[Any] = None,
        io_workers: int = 2,
        compute_workers: int = 1,
    ) -> "ThreadManager":
        """Create a narrow helper manager for small UI-only/background helper tasks."""
        config = {
            ThreadPoolType.IO: max(1, int(io_workers)),
            ThreadPoolType.COMPUTE: max(1, int(compute_workers)),
        }
        return cls(config=config, resource_manager=resource_manager)

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
        self._active_tasks_lock = threading.RLock()
        self._category_stats_lock = threading.RLock()
        self._category_stats: Dict[str, Dict[str, int]] = {}
        self._diagnostic_lock = threading.Lock()
        self._diagnostic_pools: Dict[str, Dict[str, Any]] = {
            pool_type.value: {
                "worker_active": 0,
                "tasks_started": 0,
                "tasks_finished": 0,
                "callbacks_active": 0,
                "callbacks_delivered": 0,
                "callbacks_failed": 0,
                "queue_wait_ms_total": 0.0,
                "queue_wait_ms_max": 0.0,
                "execution_ms_total": 0.0,
                "execution_ms_max": 0.0,
                "callback_ms_total": 0.0,
                "callback_ms_max": 0.0,
                "last_task_category": "<none>",
                "last_task": "<none>",
                "last_queue_wait_ms": 0.0,
                "last_execution_ms": 0.0,
                "last_callback": "<none>",
                "last_callback_ms": 0.0,
            }
            for pool_type in ThreadPoolType
        }
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
                   callback: Callable[[TaskResult], None] = None,
                   category: str = "uncategorized", **kwargs) -> str:
        """
        Submit a task to the specified thread pool.
        
        Args:
            pool_type: Which thread pool to use
            func: Function to execute
            *args: Positional arguments for func
            task_id: Optional unique identifier
            priority: Task priority
            callback: Optional callback for result
            category: Stable diagnostics category. This passive metadata never
                affects scheduling.
            **kwargs: Keyword arguments for func
        
        Returns:
            str: Task ID for tracking
        """
        if self._shutdown:
            raise RuntimeError("Thread manager is shut down")
        
        task = Task(
            func,
            *args,
            task_id=task_id,
            priority=priority,
            category=category,
            **kwargs,
        )
        task.pool_type = pool_type
        executor = self._executors[pool_type]
        
        def wrapped_func():
            queue_wait_ms = max(0.0, (time.time() - task.created_at) * 1000.0)
            start_time = time.time()
            outcome = "failed"
            pool_diag = self._diagnostic_pools[pool_type.value]
            with self._diagnostic_lock:
                pool_diag["worker_active"] += 1
                pool_diag["tasks_started"] += 1
                pool_diag["queue_wait_ms_total"] += queue_wait_ms
                pool_diag["queue_wait_ms_max"] = max(
                    float(pool_diag["queue_wait_ms_max"]),
                    queue_wait_ms,
                )
                pool_diag["last_task_category"] = task.category
                pool_diag["last_task"] = _callable_debug_name(task.func)
                pool_diag["last_queue_wait_ms"] = queue_wait_ms
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
                outcome = "completed"
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
                outcome = "failed"
            finally:
                self._unregister_active_task(task.task_id, outcome=outcome)

            execution_ms = execution_time * 1000.0
            with self._diagnostic_lock:
                pool_diag["tasks_finished"] += 1
                pool_diag["execution_ms_total"] += execution_ms
                pool_diag["execution_ms_max"] = max(
                    float(pool_diag["execution_ms_max"]),
                    execution_ms,
                )
                pool_diag["last_execution_ms"] = execution_ms

            try:
                # Execute callback on the worker by contract.
                if callback:
                    callback_label = _callable_debug_name(callback)
                    callback_started = time.perf_counter()
                    callback_failed = False
                    with self._diagnostic_lock:
                        pool_diag["callbacks_active"] += 1
                        pool_diag["last_callback"] = callback_label
                    try:
                        callback(task_result)
                    except Exception as e:
                        callback_failed = True
                        logger.exception(
                            "Callback for task %s failed: %s "
                            "(pool=%s func=%s callback=%s execution_ms=%.2f)",
                            task.task_id,
                            e,
                            pool_type.value,
                            _callable_debug_name(task.func),
                            callback_label,
                            execution_ms,
                        )
                    finally:
                        callback_ms = (
                            time.perf_counter() - callback_started
                        ) * 1000.0
                        with self._diagnostic_lock:
                            pool_diag["callbacks_active"] = max(
                                0,
                                int(pool_diag["callbacks_active"]) - 1,
                            )
                            pool_diag["callbacks_delivered"] += 1
                            if callback_failed:
                                pool_diag["callbacks_failed"] += 1
                            pool_diag["callback_ms_total"] += callback_ms
                            pool_diag["callback_ms_max"] = max(
                                float(pool_diag["callback_ms_max"]),
                                callback_ms,
                            )
                            pool_diag["last_callback"] = callback_label
                            pool_diag["last_callback_ms"] = callback_ms
                return task_result
            finally:
                with self._diagnostic_lock:
                    pool_diag["worker_active"] = max(
                        0,
                        int(pool_diag["worker_active"]) - 1,
                    )
        
        # Active-task bookkeeping is authoritative at submit time. Register before
        # the executor can run a fast task and unregister itself.
        self._register_active_task(task)
        try:
            future = executor.submit(wrapped_func)
        except Exception:
            self._unregister_active_task(task.task_id, outcome="rejected")
            raise
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
                    task_id=task.task_id,
                    runtime_generation=task.runtime_generation,
                    lifetime_scope=(
                        "runtime"
                        if task.runtime_generation is not None
                        else "process"
                    ),
                    owner_class=task.owner_class,
                    owner_id=task.owner_id,
                )
            except (TypeError, Exception) as e:
                logger.debug(f"Skipping resource registration for task {task.task_id}: {e}")
        
        # Update tracking
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
        with self._active_tasks_lock:
            task = self._active_tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found")
        try:
            return task.future.result(timeout=timeout)
        except TimeoutError:
            raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")

    def cancel_task(self, task_id: str) -> bool:
        """Attempt to cancel a task"""
        with self._active_tasks_lock:
            task = self._active_tasks.get(task_id)
        if task and task.future:
            cancelled = task.future.cancel()
            if cancelled:
                self._unregister_active_task(task_id, outcome="cancelled")
                logger.info(f"Cancelled task {task_id}")
            return cancelled
        return False

    def get_active_tasks(self) -> List[str]:
        """Get list of currently active task IDs"""
        with self._active_tasks_lock:
            return list(self._active_tasks.keys())

    def get_pool_stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics for all thread pools"""
        return {pool_type.value: stats.copy() 
               for pool_type, stats in self._stats.items()}

    def get_task_category_stats(self) -> Dict[str, Dict[str, int]]:
        """Return an authoritative passive snapshot of task counts by category."""
        with self._category_stats_lock:
            return {
                category: counts.copy()
                for category, counts in sorted(self._category_stats.items())
            }

    def get_diagnostic_snapshot(self) -> Dict[str, Any]:
        """Return bounded passive queue, worker, callback and UI-delivery counters."""
        with self._diagnostic_lock:
            pools = {
                pool_name: values.copy()
                for pool_name, values in self._diagnostic_pools.items()
            }
        for pool_type, executor in self._executors.items():
            queue_depth = -1
            try:
                queue_depth = int(executor._work_queue.qsize())
            except Exception:
                pass
            pools.setdefault(pool_type.value, {})["queue_depth"] = queue_depth
        with _ui_diagnostic_lock:
            ui = dict(_ui_diagnostics)
        return {
            "pools": pools,
            "ui": ui,
        }

    def get_frame_delivery_snapshot(self) -> Dict[str, Any]:
        """Return the small counter set needed by frame-gap owner diagnostics.

        Unlike ``get_diagnostic_snapshot()``, this path deliberately avoids
        copying the complete cumulative timing dictionaries on every paint.
        The compositor keeps one display-local previous snapshot and derives
        delivery deltas without changing scheduling.
        """
        with self._diagnostic_lock:
            io_diag = self._diagnostic_pools[ThreadPoolType.IO.value]
            compute_diag = self._diagnostic_pools[ThreadPoolType.COMPUTE.value]
            snapshot: Dict[str, Any] = {
                "io_worker_active": int(io_diag["worker_active"]),
                "io_callbacks_delivered": int(io_diag["callbacks_delivered"]),
                "io_callbacks_active": int(io_diag["callbacks_active"]),
                "io_last_task": str(io_diag["last_task"]),
                "io_last_callback": str(io_diag["last_callback"]),
                "io_last_queue_wait_ms": float(io_diag["last_queue_wait_ms"]),
                "io_last_execution_ms": float(io_diag["last_execution_ms"]),
                "io_last_callback_ms": float(io_diag["last_callback_ms"]),
                "compute_worker_active": int(compute_diag["worker_active"]),
                "compute_callbacks_delivered": int(
                    compute_diag["callbacks_delivered"]
                ),
                "compute_callbacks_active": int(compute_diag["callbacks_active"]),
                "compute_last_task": str(compute_diag["last_task"]),
                "compute_last_callback": str(compute_diag["last_callback"]),
                "compute_last_queue_wait_ms": float(
                    compute_diag["last_queue_wait_ms"]
                ),
                "compute_last_execution_ms": float(
                    compute_diag["last_execution_ms"]
                ),
                "compute_last_callback_ms": float(
                    compute_diag["last_callback_ms"]
                ),
            }
        for pool_type in ThreadPoolType:
            queue_depth = -1
            executor = self._executors.get(pool_type)
            try:
                queue_depth = int(executor._work_queue.qsize())
            except Exception:
                pass
            snapshot[f"{pool_type.value}_queue_depth"] = queue_depth
        with _ui_diagnostic_lock:
            snapshot.update(
                {
                    "ui_queued": int(_ui_diagnostics["queued"]),
                    "ui_delivered": int(_ui_diagnostics["delivered"]),
                    "ui_failed": int(_ui_diagnostics["failed"]),
                    "ui_active": int(_ui_diagnostics["active"]),
                    "ui_queue_depth": int(_ui_diagnostics["queue_depth"]),
                    "ui_last_callback": str(_ui_diagnostics["last_callback"]),
                    "ui_last_duration_ms": float(
                        _ui_diagnostics["last_duration_ms"]
                    ),
                    "ui_last_completed_ts": float(
                        _ui_diagnostics["last_completed_ts"]
                    ),
                }
            )
        return snapshot

    def get_lifecycle_ownership_snapshot(self) -> Dict[str, Any]:
        """Return active task and queued-UI ownership grouped by generation."""

        with self._active_tasks_lock:
            tasks = tuple(
                {
                    "task_id": task.task_id,
                    "category": task.category,
                    "pool": getattr(getattr(task, "pool_type", None), "value", None),
                    "owner_class": task.owner_class,
                    "owner_id": task.owner_id,
                    "runtime_generation": task.runtime_generation,
                }
                for task in self._active_tasks.values()
            )
        with _ui_diagnostic_lock:
            ui = {
                "queue_depth": int(_ui_diagnostics["queue_depth"]),
                "queued_by_generation": dict(
                    _ui_diagnostics["queued_by_generation"]
                ),
                "scheduled_single_shots": int(
                    _ui_diagnostics["scheduled_single_shots"]
                ),
                "scheduled_single_shots_by_generation": dict(
                    _ui_diagnostics["scheduled_single_shots_by_generation"]
                ),
            }
        return {"active_tasks": tasks, "ui": ui}

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
        try:
            self.cancel_all_scheduled_single_shots()
        except RuntimeError:
            logger.debug(
                "ThreadManager delayed-callback cancellation was not on the UI thread"
            )
        with self.__class__._app_shared_lock:
            if self.__class__._app_shared_manager is self:
                self.__class__._app_shared_manager = None
        
        # Cancel active tasks
        with self._active_tasks_lock:
            active_ids = list(self._active_tasks.keys())
        if active_ids:
            logger.info("Cancelling %d active tasks before shutdown: %s", len(active_ids), active_ids)
        for task_id in active_ids:
            self.cancel_task(task_id)
        
        if wait and timeout is not None:
            with self._active_tasks_lock:
                futures = [
                    task.future for task in self._active_tasks.values()
                    if task.future is not None
                ]
            if futures:
                done, not_done = wait_futures(futures, timeout=max(0.0, float(timeout)))
                if not_done:
                    with self._active_tasks_lock:
                        stuck_ids = [
                            task.task_id for task in self._active_tasks.values()
                            if task.future in not_done
                        ]
                    logger.warning(
                        "ThreadManager shutdown timed out after %.1fs with %d active tasks: %s",
                        float(timeout),
                        len(not_done),
                        stuck_ids,
                    )
                    for future in not_done:
                        future.cancel()
                    wait = False

        # Shutdown executors
        for pool_type, executor in self._executors.items():
            try:
                with self._active_tasks_lock:
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
        with self._active_tasks_lock:
            self._active_tasks.clear()
        
        logger.info("Thread manager shut down complete")

    def _register_active_task(self, task: Task) -> None:
        """Synchronously register an in-flight task so bookkeeping is immediately authoritative."""
        with self._active_tasks_lock:
            self._active_tasks[task.task_id] = task
        with self._category_stats_lock:
            category = task.category.strip()[: self._max_task_category_length] or "uncategorized"
            if (
                category not in self._category_stats
                and len(self._category_stats) >= self._max_task_categories - 1
            ):
                category = "other"
            task.category = category
            counts = self._category_stats.setdefault(
                category,
                {
                    "submitted": 0,
                    "completed": 0,
                    "failed": 0,
                    "cancelled": 0,
                    "rejected": 0,
                    "active": 0,
                },
            )
            counts["submitted"] += 1
            counts["active"] += 1

    def _unregister_active_task(
        self,
        task_id: str,
        *,
        outcome: str | None = None,
    ) -> None:
        """Synchronously remove an in-flight task from the authoritative registry."""
        with self._active_tasks_lock:
            task = self._active_tasks.pop(task_id, None)
        if task is None:
            return
        with self._category_stats_lock:
            counts = self._category_stats.get(task.category)
            if counts is None:
                return
            counts["active"] = max(0, int(counts.get("active", 0)) - 1)
            if outcome in {"completed", "failed", "cancelled", "rejected"}:
                counts[outcome] = int(counts.get(outcome, 0)) + 1

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
        if _qt_dispatch_available():
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
            if app is None or QCoreApplication.closingDown():
                logger.debug("run_on_ui_thread called without a live Qt event loop")
                return
            _owner, _owner_class, _owner_id, generation = (
                _callable_runtime_identity(func)
            )
            if _ui_generation_cancelled(generation):
                logger.debug(
                    "Rejected retired-generation UI callback generation=%s callback=%s",
                    generation,
                    _callable_debug_name(func),
                )
                return
            
            if QThread.currentThread() is app.thread():
                _run_tracked_ui_callable(
                    func,
                    tuple(args or ()),
                    dict(kwargs or {}),
                    was_queued=False,
                )
                return
            
            inv = _ensure_ui_invoker()
            if inv is None:
                raise RuntimeError("UI invoker unavailable")
            _record_ui_queue(func)
            inv.invoke.emit(func, args, kwargs or {})
        except Exception as e:
            logger.exception("run_on_ui_thread dispatch failed: %s", e)

    @staticmethod
    def single_shot(delay_ms: int, func: Callable, *args, **kwargs) -> None:
        """Schedule a cancellable, generation-owned UI callback."""
        try:
            app = QCoreApplication.instance()
            if app is None or QCoreApplication.closingDown():
                logger.debug("single_shot ignored without a live Qt event loop")
                return

            owner, owner_class, owner_id, generation = _callable_runtime_identity(func)
            generation_key = _generation_key(generation)
            weak_method = None
            if owner is not None and getattr(func, "__func__", None) is not None:
                try:
                    weak_method = weakref.WeakMethod(func)
                except TypeError:
                    weak_method = None
            strong_func = None if weak_method is not None else func

            _record_single_shot_scheduled(generation)

            def _create_timer_on_ui() -> None:
                if (
                    not _qt_dispatch_available()
                    or _single_shot_generation_cancelled(generation_key)
                    or _ui_generation_cancelled(generation)
                ):
                    _record_single_shot_delivered(generation)
                    return
                try:
                    timer_parent = owner if isinstance(owner, QObject) else app
                    timer = QTimer(timer_parent)
                except Exception:
                    _record_single_shot_delivered(generation)
                    raise

                timer.setSingleShot(True)
                timer._runtime_generation = generation
                timer._srpss_owner_class = owner_class
                timer._srpss_owner_id = owner_id
                timer_ref = weakref.ref(timer)
                state = {"finished": False}

                def _finish(*, execute: bool) -> None:
                    if state["finished"]:
                        return
                    state["finished"] = True
                    current_timer = timer_ref()
                    _unregister_single_shot_timer(
                        generation_key,
                        current_timer,
                    )
                    _record_single_shot_delivered(generation)
                    if current_timer is not None:
                        try:
                            current_timer.stop()
                            current_timer.timeout.disconnect()
                        except (RuntimeError, TypeError):
                            pass
                        try:
                            current_timer._srpss_cancel_single_shot = None
                        except RuntimeError:
                            pass
                    if execute:
                        target = (
                            weak_method()
                            if weak_method is not None
                            else strong_func
                        )
                        if target is not None:
                            ThreadManager.run_on_ui_thread(
                                target,
                                *args,
                                **(kwargs or {}),
                            )
                    if current_timer is not None and _qt_dispatch_available():
                        try:
                            current_timer.deleteLater()
                        except RuntimeError:
                            pass

                def _invoke() -> None:
                    _finish(execute=True)

                def _on_destroyed(*_args: object) -> None:
                    _finish(execute=False)

                timer._srpss_cancel_single_shot = lambda: _finish(execute=False)
                timer.timeout.connect(_invoke)
                timer.destroyed.connect(_on_destroyed)
                if not _register_single_shot_timer(generation_key, timer):
                    _finish(execute=False)
                    return
                try:
                    timer.start(max(0, int(delay_ms)))
                except Exception:
                    _finish(execute=False)
                    raise

            if QThread.currentThread() is app.thread():
                _create_timer_on_ui()
            else:
                def _schedule_on_ui() -> None:
                    try:
                        _create_timer_on_ui()
                    except Exception:
                        logger.exception("single_shot UI timer creation failed")
                _schedule_on_ui._srpss_runtime_generation = generation
                ThreadManager.run_on_ui_thread(_schedule_on_ui)
        except Exception as e:
            logger.exception("single_shot failed: %s", e)

    @staticmethod
    def cancel_scheduled_single_shots(runtime_generation: object) -> int:
        """Synchronously cancel all delayed callbacks for one retired runtime."""

        app = QCoreApplication.instance()
        if app is None:
            return 0
        if QThread.currentThread() is not app.thread():
            raise RuntimeError(
                "Runtime single-shot cancellation must run on the Qt UI thread"
            )
        key = _generation_key(runtime_generation)
        with _single_shot_registry_lock:
            _cancelled_single_shot_generations.add(key)
            timers = tuple(_single_shot_timers.get(key, ()))
        cancelled = 0
        for timer in timers:
            cancel = getattr(timer, "_srpss_cancel_single_shot", None)
            if callable(cancel):
                cancel()
                cancelled += 1
        _prune_cancelled_single_shot_generation(key)
        return cancelled

    @staticmethod
    def cancel_queued_ui_callbacks(runtime_generation: object) -> int:
        """Reject queued and future UI publications from a retired generation."""

        key = _generation_key(runtime_generation)
        with _ui_diagnostic_lock:
            _cancelled_ui_generations.add(key)
            return int(_ui_diagnostics["queued_by_generation"].get(key, 0))

    @staticmethod
    def cancel_all_scheduled_single_shots() -> int:
        """Cancel every delayed callback while terminal shutdown owns the UI."""

        app = QCoreApplication.instance()
        if app is None:
            return 0
        if QThread.currentThread() is not app.thread():
            raise RuntimeError(
                "Global single-shot cancellation must run on the Qt UI thread"
            )
        with _ui_diagnostic_lock:
            scheduled_keys = tuple(
                _ui_diagnostics["scheduled_single_shots_by_generation"]
            )
        with _single_shot_registry_lock:
            keys = tuple(set(_single_shot_timers).union(scheduled_keys))
            _cancelled_single_shot_generations.update(keys)
            timers = tuple(
                timer
                for group in _single_shot_timers.values()
                for timer in group
            )
        cancelled = 0
        for timer in timers:
            cancel = getattr(timer, "_srpss_cancel_single_shot", None)
            if callable(cancel):
                cancel()
                cancelled += 1
        for key in keys:
            _prune_cancelled_single_shot_generation(key)
        return cancelled

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
        if self._shutdown:
            raise RuntimeError("Cannot schedule a recurring timer after shutdown")
        if not _qt_dispatch_available():
            raise RuntimeError(
                "Cannot schedule a recurring timer without a live Qt event loop"
            )
        _last_invoke_ts = [0.0]
        timer_desc = description
        if not timer_desc:
            try:
                timer_desc = getattr(func, "__qualname__", None) or func.__name__
            except Exception as e:
                logger.debug("[THREADING] Exception suppressed: %s", e)
                timer_desc = "recurring_timer"

        timer_ref: list[Optional[QTimer]] = [None]

        def _invoke():
            try:
                now = time.time()
                if _last_invoke_ts[0] > 0.0:
                    gap_ms = (now - _last_invoke_ts[0]) * 1000.0
                    active_interval_ms = int(interval_ms)
                    timer = timer_ref[0]
                    if timer is not None:
                        try:
                            active_interval_ms = int(timer.interval())
                        except Exception:
                            active_interval_ms = int(interval_ms)
                    # Only warn if gap exceeds 2x the expected interval AND is
                    # significant (>100ms). For slow timers (e.g. 1000ms weather
                    # refresh) a gap of 1007ms is normal jitter, not a problem.
                    # Modal dialogs (settings) also block the event loop, causing
                    # expected gaps that should not spam warnings.
                    threshold_ms = max(100.0, float(active_interval_ms) * 2.0)
                    if gap_ms > threshold_ms and is_perf_metrics_enabled():
                        context = _describe_timer_callable_context(func)
                        if not _should_suppress_large_timer_gap_warning(gap_ms, active_interval_ms, context):
                            likely_cause = _classify_large_timer_gap_warning(context)
                            logger.warning(
                                "[PERF] [TIMER] Large gap for %s: %.2fms (interval=%dms likely=%s context=%s)",
                                timer_desc,
                                gap_ms,
                                active_interval_ms,
                                likely_cause,
                                context,
                            )
                _last_invoke_ts[0] = now
                func(*args, **(kwargs or {}))
            except Exception as e:
                logger.exception("Recurring task raised: %s", e)
        
        owner, owner_class, owner_id, runtime_generation = _callable_runtime_identity(func)
        timer_parent = owner if isinstance(owner, QObject) else None
        timer = QTimer(timer_parent)
        timer._runtime_generation = runtime_generation
        timer._srpss_owner_class = owner_class
        timer._srpss_owner_id = owner_id
        timer_ref[0] = timer
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
                    cleanup_handler=lambda t: t.stop(),
                    runtime_generation=runtime_generation,
                    lifetime_scope=(
                        "runtime" if runtime_generation is not None else "process"
                    ),
                    owner_class=owner_class,
                    owner_id=owner_id,
                )
            except Exception as e:
                logger.debug("Could not register timer: %s", e)
        
        return timer
