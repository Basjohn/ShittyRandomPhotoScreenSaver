"""Single-threaded best-effort background CPU lane.

This lane is intentionally separate from ThreadManager's general COMPUTE pool.
It exists for CPU work that is useful only when spare scheduler headroom exists
and must never compete at normal Windows thread priority with Qt Quick/render or
visualizer work.

The worker is created lazily on first submission, owns no timer/cadence, and
executes at most one task at a time.  On Windows it requests
THREAD_PRIORITY_BELOW_NORMAL and disables dynamic priority boosts; if that
priority contract cannot be installed, queued work is failed closed instead of
silently running at normal priority.  Other platforms keep the same serial
lifecycle semantics but cannot claim the Windows scheduling contract.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import ctypes
import os
import threading
import time
from typing import Any, Callable

from core.logging.logger import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class BackgroundTaskResult:
    """TaskResult-compatible completion delivered on the background thread."""

    success: bool
    result: Any = None
    error: BaseException | None = None
    execution_time: float = 0.0
    task_id: str | None = None


@dataclass
class _QueuedTask:
    func: Callable[[], Any]
    callback: Callable[[BackgroundTaskResult], None] | None
    task_id: str
    category: str
    runtime_generation: object | None
    owner_class: str | None
    owner_id: int | None
    queued_perf_ts: float


def _apply_background_thread_priority() -> tuple[bool, str, int | None]:
    """Install the Windows best-effort scheduling contract on the current thread.

    Returns ``(applied, mode, native_priority)``.  Non-Windows platforms return
    an explicit unsupported mode but are allowed to execute for portability and
    testability; SRPSS production is Windows and must not infer a demotion there.
    """

    if os.name != "nt":
        return False, "unsupported_non_windows", None

    try:
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_current_thread = kernel32.GetCurrentThread
        get_current_thread.argtypes = []
        get_current_thread.restype = wintypes.HANDLE

        set_thread_priority = kernel32.SetThreadPriority
        set_thread_priority.argtypes = [wintypes.HANDLE, ctypes.c_int]
        set_thread_priority.restype = wintypes.BOOL

        set_thread_priority_boost = kernel32.SetThreadPriorityBoost
        set_thread_priority_boost.argtypes = [wintypes.HANDLE, wintypes.BOOL]
        set_thread_priority_boost.restype = wintypes.BOOL

        get_thread_priority = kernel32.GetThreadPriority
        get_thread_priority.argtypes = [wintypes.HANDLE]
        get_thread_priority.restype = ctypes.c_int

        # NORMAL_PRIORITY_CLASS + THREAD_PRIORITY_BELOW_NORMAL => base 7 rather
        # than the ordinary base 8.  This is deliberately conservative: the
        # derivative is useful but may take longer under pressure.
        THREAD_PRIORITY_BELOW_NORMAL = -1
        handle = get_current_thread()
        if not set_thread_priority(handle, THREAD_PRIORITY_BELOW_NORMAL):
            error_code = int(ctypes.get_last_error())
            return False, f"set_priority_failed:{error_code}", None

        # Windows normally boosts a thread when a condition wait is satisfied.
        # That is desirable for interactive work but defeats a best-effort CPU
        # lane precisely when it wakes.  Keep this one lane at its base priority.
        if not set_thread_priority_boost(handle, True):
            error_code = int(ctypes.get_last_error())
            return False, f"disable_boost_failed:{error_code}", None

        current_priority = int(get_thread_priority(handle))
        return (
            current_priority == THREAD_PRIORITY_BELOW_NORMAL,
            "windows_below_normal_no_boost",
            current_priority,
        )
    except Exception as exc:  # pragma: no cover - Windows API failure path
        return False, f"priority_exception:{type(exc).__name__}", None


class BackgroundTaskScheduler:
    """One lazy serial worker for genuinely best-effort CPU tasks."""

    def __init__(self, *, max_pending: int = 1) -> None:
        self._max_pending = max(1, int(max_pending))
        self._condition = threading.Condition(threading.RLock())
        self._pending: deque[_QueuedTask] = deque()
        self._thread: threading.Thread | None = None
        self._active: _QueuedTask | None = None
        self._shutdown = False
        self._priority_ready = threading.Event()
        self._priority_applied = False
        self._priority_mode = "not_started"
        self._native_priority: int | None = None
        self._metrics: dict[str, float | int | str | bool | None] = {
            "worker_threads": 0,
            "worker_active": 0,
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_rejected_full": 0,
            "tasks_cancelled_shutdown": 0,
            "callbacks_delivered": 0,
            "callbacks_failed": 0,
            "queue_wait_ms_total": 0.0,
            "queue_wait_ms_max": 0.0,
            "execution_ms_total": 0.0,
            "execution_ms_max": 0.0,
            "callback_ms_total": 0.0,
            "callback_ms_max": 0.0,
            "last_category": "<none>",
            "last_execution_ms": 0.0,
            "last_callback_ms": 0.0,
            "priority_applied": False,
            "priority_mode": "not_started",
            "native_priority": None,
        }

    def submit(
        self,
        func: Callable[[], Any],
        *,
        callback: Callable[[BackgroundTaskResult], None] | None,
        task_id: str,
        category: str,
        runtime_generation: object | None,
        owner_class: str | None,
        owner_id: int | None,
    ) -> str:
        packet = _QueuedTask(
            func=func,
            callback=callback,
            task_id=str(task_id),
            category=str(category or "background"),
            runtime_generation=runtime_generation,
            owner_class=owner_class,
            owner_id=owner_id,
            queued_perf_ts=time.perf_counter(),
        )
        with self._condition:
            if self._shutdown:
                raise RuntimeError("Background task scheduler is shut down")
            if len(self._pending) >= self._max_pending:
                self._metrics["tasks_rejected_full"] = int(
                    self._metrics["tasks_rejected_full"]
                ) + 1
                raise RuntimeError("Background task queue is full")
            self._ensure_thread_locked()
            self._pending.append(packet)
            self._metrics["tasks_submitted"] = int(
                self._metrics["tasks_submitted"]
            ) + 1
            self._condition.notify()
        return packet.task_id

    def _ensure_thread_locked(self) -> None:
        thread = self._thread
        if thread is not None and thread.is_alive():
            return
        thread = threading.Thread(
            target=self._worker_loop,
            name="background_cpu_lane",
            daemon=True,
        )
        self._thread = thread
        self._metrics["worker_threads"] = 1
        thread.start()

    def _worker_loop(self) -> None:
        applied, mode, native_priority = _apply_background_thread_priority()
        with self._condition:
            self._priority_applied = bool(applied)
            self._priority_mode = str(mode)
            self._native_priority = native_priority
            self._metrics["priority_applied"] = bool(applied)
            self._metrics["priority_mode"] = str(mode)
            self._metrics["native_priority"] = native_priority
            self._priority_ready.set()
            self._condition.notify_all()
        if os.name == "nt" and not applied:
            logger.error(
                "Background CPU lane could not install Windows demotion (%s); "
                "best-effort work will fail closed",
                mode,
            )
        else:
            logger.info(
                "Background CPU lane started priority_mode=%s native_priority=%s",
                mode,
                native_priority,
            )

        while True:
            with self._condition:
                while not self._pending and not self._shutdown:
                    self._condition.wait()
                if self._shutdown and not self._pending:
                    return
                packet = self._pending.popleft()
                self._active = packet
                self._metrics["worker_active"] = 1

            queue_wait_ms = max(
                0.0,
                (time.perf_counter() - packet.queued_perf_ts) * 1000.0,
            )
            execution_started = time.perf_counter()
            if os.name == "nt" and not self._priority_applied:
                result = BackgroundTaskResult(
                    success=False,
                    error=RuntimeError(
                        "Windows background thread priority contract was not installed"
                    ),
                    task_id=packet.task_id,
                )
                execution_ms = 0.0
            else:
                try:
                    value = packet.func()
                    execution_ms = (
                        time.perf_counter() - execution_started
                    ) * 1000.0
                    result = BackgroundTaskResult(
                        success=True,
                        result=value,
                        execution_time=execution_ms / 1000.0,
                        task_id=packet.task_id,
                    )
                except Exception as exc:
                    execution_ms = (
                        time.perf_counter() - execution_started
                    ) * 1000.0
                    result = BackgroundTaskResult(
                        success=False,
                        error=exc,
                        execution_time=execution_ms / 1000.0,
                        task_id=packet.task_id,
                    )

            callback_ms = 0.0
            callback_failed = False
            if packet.callback is not None:
                callback_started = time.perf_counter()
                try:
                    packet.callback(result)
                except Exception:
                    callback_failed = True
                    logger.exception(
                        "Background task callback failed task=%s category=%s",
                        packet.task_id,
                        packet.category,
                    )
                callback_ms = (
                    time.perf_counter() - callback_started
                ) * 1000.0

            with self._condition:
                self._active = None
                self._metrics["worker_active"] = 0
                self._metrics["tasks_completed"] = int(
                    self._metrics["tasks_completed"]
                ) + 1
                if not result.success:
                    self._metrics["tasks_failed"] = int(
                        self._metrics["tasks_failed"]
                    ) + 1
                if packet.callback is not None:
                    self._metrics["callbacks_delivered"] = int(
                        self._metrics["callbacks_delivered"]
                    ) + 1
                if callback_failed:
                    self._metrics["callbacks_failed"] = int(
                        self._metrics["callbacks_failed"]
                    ) + 1
                self._metrics["queue_wait_ms_total"] = float(
                    self._metrics["queue_wait_ms_total"]
                ) + queue_wait_ms
                self._metrics["queue_wait_ms_max"] = max(
                    float(self._metrics["queue_wait_ms_max"]), queue_wait_ms
                )
                self._metrics["execution_ms_total"] = float(
                    self._metrics["execution_ms_total"]
                ) + execution_ms
                self._metrics["execution_ms_max"] = max(
                    float(self._metrics["execution_ms_max"]), execution_ms
                )
                self._metrics["callback_ms_total"] = float(
                    self._metrics["callback_ms_total"]
                ) + callback_ms
                self._metrics["callback_ms_max"] = max(
                    float(self._metrics["callback_ms_max"]), callback_ms
                )
                self._metrics["last_category"] = packet.category
                self._metrics["last_execution_ms"] = execution_ms
                self._metrics["last_callback_ms"] = callback_ms
                self._condition.notify_all()

    def diagnostic_snapshot(self) -> dict[str, Any]:
        with self._condition:
            snapshot = dict(self._metrics)
            snapshot.update(
                {
                    "queue_depth": len(self._pending),
                    "active_task": (
                        self._active.task_id if self._active is not None else None
                    ),
                    "active_category": (
                        self._active.category if self._active is not None else "<none>"
                    ),
                    "shutdown": self._shutdown,
                }
            )
            return snapshot

    def lifecycle_work_snapshot(self) -> tuple[dict[str, Any], ...]:
        with self._condition:
            packets = ([self._active] if self._active is not None else []) + list(
                self._pending
            )
            return tuple(
                {
                    "task_id": packet.task_id,
                    "kind": "background_cpu",
                    "category": packet.category,
                    "pool": "background_cpu",
                    "owner_class": packet.owner_class,
                    "owner_id": packet.owner_id,
                    "runtime_generation": packet.runtime_generation,
                    "active": packet is self._active,
                    "pending": packet is not self._active,
                }
                for packet in packets
            )

    def shutdown(self, *, wait: bool, timeout: float | None = None) -> bool:
        with self._condition:
            if not self._shutdown:
                self._shutdown = True
                cancelled = len(self._pending)
                if cancelled:
                    self._metrics["tasks_cancelled_shutdown"] = int(
                        self._metrics["tasks_cancelled_shutdown"]
                    ) + cancelled
                    self._pending.clear()
                self._condition.notify_all()
            thread = self._thread
        if wait and thread is not None:
            thread.join(None if timeout is None else max(0.0, float(timeout)))
        alive = bool(thread is not None and thread.is_alive())
        if not alive:
            with self._condition:
                self._thread = None
                self._metrics["worker_threads"] = 0
        return not alive
