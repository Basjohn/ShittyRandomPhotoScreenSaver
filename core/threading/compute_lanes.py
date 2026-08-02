"""Bounded process-owned compute lanes without per-step Futures.

The general COMPUTE executor remains available for bursty image work. A small
set of long-lived scheduler threads serves high-frequency, one-outstanding
visualizer lanes from a condition-protected queue. Lanes do not reserve a
shared executor worker while idle and do not allocate a Task/Future or enqueue
ThreadManager UI-stat mutations for every 1--2 ms logical step.

The scheduler never invents cadence, batches authored steps, or couples a
producer to paint.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import threading
import time
from typing import Any, Callable
import weakref

from core.logging.logger import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class ComputeLaneResult:
    """TaskResult-compatible result delivered on a lane worker thread."""

    success: bool
    result: Any = None
    error: BaseException | None = None
    execution_time: float = 0.0
    task_id: str | None = None


def _weak_callable(
    callback: Callable[..., Any],
    *,
    on_release: Callable[[], None] | None = None,
) -> Callable[[], Callable[..., Any] | None]:
    def _released(_ref: object) -> None:
        if on_release is not None:
            on_release()

    owner = getattr(callback, "__self__", None)
    if owner is not None and getattr(callback, "__func__", None) is not None:
        return weakref.WeakMethod(callback, _released)
    try:
        return weakref.ref(callback, _released)
    except TypeError:
        # Module functions are process-owned and safe to retain. Runtime
        # closures should use a bound owner so their generation is observable.
        return lambda: callback


@dataclass
class _LaneState:
    lane_id: str
    category: str
    runtime_generation: object | None
    owner_class: str | None
    owner_id: int | None
    worker_ref: Callable[[], Callable[..., Any] | None]
    callback_ref: Callable[[], Callable[..., Any] | None]
    pending: Any = None
    queued: bool = False
    active: bool = False
    publishing: bool = False
    stopped: bool = False
    metrics: dict[str, float | int] = field(
        default_factory=lambda: {
            "lane_registrations": 1,
            "executor_task_submissions": 0,
            "logical_steps_accepted": 0,
            "logical_steps_completed": 0,
            "logical_steps_published": 0,
            "logical_steps_rejected_publication": 0,
            "submit_rejected_busy": 0,
            "submit_rejected_stopped": 0,
            "pending_cancelled": 0,
            "worker_failures": 0,
            "callback_failures": 0,
            "owner_releases": 0,
            "handoff_ms_total": 0.0,
            "handoff_ms_max": 0.0,
            "execution_ms_total": 0.0,
            "execution_ms_max": 0.0,
            "callback_ms_total": 0.0,
            "callback_ms_max": 0.0,
        }
    )


@dataclass(frozen=True)
class _QueuedPacket:
    payload: Any
    queued_perf_ts: float


class ComputeLaneHandle:
    """Owner-held handle for one serial, one-outstanding compute lane."""

    def __init__(self, scheduler: "ComputeLaneScheduler", state: _LaneState) -> None:
        self._scheduler_ref = weakref.ref(scheduler)
        self._state = state

    @property
    def is_stopped(self) -> bool:
        scheduler = self._scheduler_ref()
        if scheduler is None:
            return True
        with scheduler._condition:
            return bool(self._state.stopped)

    def submit(self, payload: Any) -> bool:
        scheduler = self._scheduler_ref()
        if scheduler is None:
            return False
        return scheduler.submit(self._state, payload)

    def cancel_pending(self) -> int:
        scheduler = self._scheduler_ref()
        if scheduler is None:
            return 0
        return scheduler.cancel_pending(self._state)

    def stop(self) -> None:
        scheduler = self._scheduler_ref()
        if scheduler is not None:
            scheduler.stop_lane(self._state)

    def diagnostic_snapshot(self) -> dict[str, Any]:
        scheduler = self._scheduler_ref()
        if scheduler is None:
            return {
                **self._state.metrics,
                "lane_id": self._state.lane_id,
                "category": self._state.category,
                "stopped": True,
                "active": False,
                "publishing": False,
                "pending": False,
                "queued": False,
            }
        return scheduler.lane_snapshot(self._state)


class ComputeLaneScheduler:
    """Small ThreadManager-owned scheduler for high-rate serial lanes."""

    def __init__(self, worker_count: int = 2) -> None:
        self._worker_count = max(1, min(4, int(worker_count)))
        self._condition = threading.Condition(threading.RLock())
        self._states: dict[str, _LaneState] = {}
        self._ready: deque[str] = deque()
        self._threads: list[threading.Thread] = []
        self._started = False
        self._shutdown = False
        self._scheduler_metrics: dict[str, float | int | str] = {
            "worker_threads": self._worker_count,
            "worker_active": 0,
            "worker_active_max": 0,
            "callbacks_delivered": 0,
            "callbacks_failed": 0,
            "logical_steps_completed": 0,
            "last_category": "<none>",
            "last_execution_ms": 0.0,
            "last_callback_ms": 0.0,
        }

    def register_lane(
        self,
        *,
        lane_id: str,
        category: str,
        worker: Callable[[Any], Any],
        callback: Callable[..., None],
        runtime_generation: object | None,
        owner_class: str | None,
        owner_id: int | None,
    ) -> ComputeLaneHandle:
        normalized_id = str(lane_id or f"compute-lane-{id(worker)}")
        scheduler_ref = weakref.ref(self)

        def _callable_released() -> None:
            scheduler = scheduler_ref()
            if scheduler is not None:
                scheduler._release_lane_owner(normalized_id)

        with self._condition:
            if self._shutdown:
                raise RuntimeError("Compute lane scheduler is shut down")
            existing = self._states.get(normalized_id)
            if existing is not None:
                raise RuntimeError(f"Compute lane already registered: {normalized_id}")
            state = _LaneState(
                lane_id=normalized_id,
                category=str(category or "compute_lane"),
                runtime_generation=runtime_generation,
                owner_class=owner_class,
                owner_id=owner_id,
                worker_ref=_weak_callable(
                    worker,
                    on_release=_callable_released,
                ),
                callback_ref=_weak_callable(
                    callback,
                    on_release=_callable_released,
                ),
            )
            self._states[normalized_id] = state
            self._ensure_threads_locked()
            return ComputeLaneHandle(self, state)

    def _release_lane_owner(self, lane_id: str) -> None:
        """Stop an ownerless lane without retaining its generation forever."""

        with self._condition:
            state = self._states.get(lane_id)
            if state is None:
                return
            state.metrics["owner_releases"] += 1
            state.stopped = True
            if state.pending is not None:
                state.pending = None
                state.metrics["pending_cancelled"] += 1
            if not state.active and not state.publishing:
                self._states.pop(lane_id, None)
            self._condition.notify_all()

    def _ensure_threads_locked(self) -> None:
        if self._started:
            return
        self._started = True
        for index in range(self._worker_count):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"compute_lane_{index}",
                daemon=True,
            )
            self._threads.append(thread)
            thread.start()

    def submit(self, state: _LaneState, payload: Any) -> bool:
        packet = _QueuedPacket(payload=payload, queued_perf_ts=time.perf_counter())
        with self._condition:
            if self._shutdown or state.stopped:
                state.metrics["submit_rejected_stopped"] += 1
                return False
            if state.active or state.pending is not None:
                state.metrics["submit_rejected_busy"] += 1
                return False
            state.pending = packet
            state.metrics["logical_steps_accepted"] += 1
            # A packet may be accepted while the previous callback is
            # publishing. Queue it only after publication completes so two
            # scheduler workers can never execute one lane concurrently.
            if not state.publishing and not state.queued:
                state.queued = True
                self._ready.append(state.lane_id)
                self._condition.notify()
            return True

    def cancel_pending(self, state: _LaneState) -> int:
        with self._condition:
            if state.pending is None:
                return 0
            state.pending = None
            state.metrics["pending_cancelled"] += 1
            return 1

    def stop_lane(self, state: _LaneState) -> None:
        with self._condition:
            if state.stopped:
                return
            state.stopped = True
            if state.pending is not None:
                state.pending = None
                state.metrics["pending_cancelled"] += 1
            if not state.active and not state.publishing:
                self._states.pop(state.lane_id, None)
            self._condition.notify_all()

    def lane_snapshot(self, state: _LaneState) -> dict[str, Any]:
        with self._condition:
            snapshot: dict[str, Any] = dict(state.metrics)
            snapshot.update(
                {
                    "lane_id": state.lane_id,
                    "category": state.category,
                    "runtime_generation": state.runtime_generation,
                    "stopped": state.stopped,
                    "active": state.active,
                    "publishing": state.publishing,
                    "pending": state.pending is not None,
                    "queued": state.queued,
                }
            )
            completed = max(1, int(state.metrics["logical_steps_completed"]))
            snapshot["handoff_ms_mean"] = (
                float(state.metrics["handoff_ms_total"]) / completed
            )
            snapshot["execution_ms_mean"] = (
                float(state.metrics["execution_ms_total"]) / completed
            )
            snapshot["callback_ms_mean"] = (
                float(state.metrics["callback_ms_total"]) / completed
            )
            return snapshot

    def diagnostic_snapshot(self) -> dict[str, Any]:
        with self._condition:
            return {
                **self._scheduler_metrics,
                "queue_depth": len(self._ready),
                "registered_lanes": len(self._states),
                "lanes": tuple(
                    self.lane_snapshot(state)
                    for state in tuple(self._states.values())
                ),
            }

    def frame_snapshot(self) -> dict[str, Any]:
        """Return only constant-size counters used by per-paint diagnostics."""

        with self._condition:
            return {
                **self._scheduler_metrics,
                "queue_depth": len(self._ready),
                "registered_lanes": len(self._states),
            }

    def lifecycle_work_snapshot(self) -> tuple[dict[str, Any], ...]:
        """Return every live lane handle/work item for destruction barriers."""

        with self._condition:
            return tuple(
                {
                    "task_id": state.lane_id,
                    "kind": "compute_lane",
                    "category": state.category,
                    "pool": "compute_lane",
                    "owner_class": state.owner_class,
                    "owner_id": state.owner_id,
                    "runtime_generation": state.runtime_generation,
                    "active": state.active,
                    "publishing": state.publishing,
                    "pending": state.pending is not None,
                }
                for state in self._states.values()
                if not state.stopped or state.active or state.publishing
            )

    def _worker_loop(self) -> None:
        while True:
            with self._condition:
                while not self._ready and not self._shutdown:
                    self._condition.wait()
                if self._shutdown and not self._ready:
                    return
                lane_id = self._ready.popleft()
                state = self._states.get(lane_id)
                if state is None:
                    continue
                state.queued = False
                if state.stopped or state.pending is None or state.publishing:
                    if state.stopped and not state.active and not state.publishing:
                        self._states.pop(lane_id, None)
                    continue
                packet = state.pending
                state.pending = None
                state.active = True
                self._scheduler_metrics["worker_active"] += 1
                self._scheduler_metrics["worker_active_max"] = max(
                    int(self._scheduler_metrics["worker_active_max"]),
                    int(self._scheduler_metrics["worker_active"]),
                )

            handoff_ms = max(
                0.0,
                (time.perf_counter() - packet.queued_perf_ts) * 1000.0,
            )
            worker = state.worker_ref()
            execution_started = time.perf_counter()
            if worker is None:
                lane_result = ComputeLaneResult(
                    success=False,
                    error=RuntimeError("Compute lane worker owner was released"),
                    task_id=state.lane_id,
                )
                execution_ms = 0.0
            else:
                try:
                    value = worker(packet.payload)
                    execution_ms = (
                        time.perf_counter() - execution_started
                    ) * 1000.0
                    lane_result = ComputeLaneResult(
                        success=True,
                        result=value,
                        execution_time=execution_ms / 1000.0,
                        task_id=state.lane_id,
                    )
                except Exception as exc:
                    execution_ms = (
                        time.perf_counter() - execution_started
                    ) * 1000.0
                    lane_result = ComputeLaneResult(
                        success=False,
                        error=exc,
                        execution_time=execution_ms / 1000.0,
                        task_id=state.lane_id,
                    )

            with self._condition:
                state.active = False
                state.publishing = True
                self._scheduler_metrics["worker_active"] = max(
                    0,
                    int(self._scheduler_metrics["worker_active"]) - 1,
                )
                if not lane_result.success:
                    state.metrics["worker_failures"] += 1

            callback_ms = 0.0
            published = False
            callback_delivered = False
            callback = state.callback_ref()
            if callback is not None and not state.stopped:
                callback_started = time.perf_counter()
                try:
                    callback_result = callback(
                        lane_result,
                        payload=packet.payload,
                    )
                    callback_delivered = True
                    # Callback delivery and authoritative publication are
                    # distinct.  Visualizer callbacks return False when a
                    # generation/activation boundary rejected the result.
                    published = callback_result is not False
                except Exception:
                    with self._condition:
                        state.metrics["callback_failures"] += 1
                        self._scheduler_metrics["callbacks_failed"] += 1
                    logger.exception(
                        "Compute lane callback failed lane=%s category=%s",
                        state.lane_id,
                        state.category,
                    )
                callback_ms = (
                    time.perf_counter() - callback_started
                ) * 1000.0

            with self._condition:
                state.publishing = False
                state.metrics["logical_steps_completed"] += 1
                if published:
                    state.metrics["logical_steps_published"] += 1
                elif callback_delivered:
                    state.metrics["logical_steps_rejected_publication"] += 1
                if callback_delivered:
                    self._scheduler_metrics["callbacks_delivered"] += 1
                state.metrics["handoff_ms_total"] += handoff_ms
                state.metrics["handoff_ms_max"] = max(
                    float(state.metrics["handoff_ms_max"]), handoff_ms
                )
                state.metrics["execution_ms_total"] += execution_ms
                state.metrics["execution_ms_max"] = max(
                    float(state.metrics["execution_ms_max"]), execution_ms
                )
                state.metrics["callback_ms_total"] += callback_ms
                state.metrics["callback_ms_max"] = max(
                    float(state.metrics["callback_ms_max"]), callback_ms
                )
                self._scheduler_metrics["logical_steps_completed"] += 1
                self._scheduler_metrics["last_category"] = state.category
                self._scheduler_metrics["last_execution_ms"] = execution_ms
                self._scheduler_metrics["last_callback_ms"] = callback_ms

                if state.stopped:
                    self._states.pop(state.lane_id, None)
                elif state.pending is not None and not state.queued:
                    state.queued = True
                    self._ready.append(state.lane_id)
                    self._condition.notify()
                self._condition.notify_all()

    def shutdown(self, *, wait: bool, timeout: float | None = None) -> bool:
        with self._condition:
            if not self._shutdown:
                self._shutdown = True
                for state in self._states.values():
                    state.stopped = True
                    if state.pending is not None:
                        state.pending = None
                        state.metrics["pending_cancelled"] += 1
                self._ready.clear()
                self._condition.notify_all()
            threads = tuple(self._threads)
        if wait:
            deadline = (
                None
                if timeout is None
                else time.monotonic() + max(0.0, float(timeout))
            )
            for thread in threads:
                remaining = (
                    None
                    if deadline is None
                    else max(0.0, deadline - time.monotonic())
                )
                thread.join(remaining)
        alive_threads = tuple(thread for thread in threads if thread.is_alive())
        with self._condition:
            if alive_threads:
                # Keep the scheduler, live state, and thread handles visible.
                # A caller may retry shutdown after the owner releases a
                # blocked worker; lifecycle accounting must never claim zero
                # while Python is still executing owner code.
                self._threads[:] = list(alive_threads)
                return False
            self._states.clear()
            self._threads.clear()
            return True
