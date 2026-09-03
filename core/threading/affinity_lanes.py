"""ThreadManager-owned serial lanes for thread-affine native resources.

Some native APIs (notably COM/WinRT wrappers) bind retained objects to the
thread/apartment that created them.  The general IO executor intentionally does
not guarantee worker affinity, so a resource created in one IO task must never
be detached or released by a later arbitrary worker or the Qt UI thread.

This scheduler owns one lazy dedicated worker and any number of logical lanes.
Every callable submitted through any handle executes on that same worker, so a
lane may safely create, mutate, detach and release thread-affine native state.
There is no polling or cadence owner: the worker sleeps on a Condition and wakes
only for submitted work or shutdown.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import threading
import time
from typing import Any, Callable

from core.logging.logger import get_logger


logger = get_logger(__name__)


@dataclass
class _AffinityLaneState:
    lane_id: str
    category: str
    runtime_generation: object | None
    owner_class: str | None
    owner_id: int | None
    stopped: bool = False
    pending: int = 0
    active: int = 0
    metrics: dict[str, float | int] = field(
        default_factory=lambda: {
            "submitted": 0,
            "completed": 0,
            "failed": 0,
            "wait_timeouts": 0,
            "queue_wait_ms_total": 0.0,
            "queue_wait_ms_max": 0.0,
            "execution_ms_total": 0.0,
            "execution_ms_max": 0.0,
        }
    )


@dataclass
class _AffinityPacket:
    state: _AffinityLaneState
    func: Callable[[], Any]
    queued_perf_ts: float
    done: threading.Event | None = None
    result: Any = None
    error: BaseException | None = None


class AffinityLaneHandle:
    """Owner-held handle for one logical lane on the affinity worker."""

    def __init__(self, scheduler: "AffinityLaneScheduler", state: _AffinityLaneState) -> None:
        self._scheduler = scheduler
        self._state = state

    @property
    def is_stopped(self) -> bool:
        return self._scheduler.is_lane_stopped(self._state)

    def submit(self, func: Callable[[], Any]) -> bool:
        """Queue work and return immediately."""

        return self._scheduler.submit(self._state, func)

    def call(self, func: Callable[[], Any], *, timeout: float | None = None) -> Any:
        """Run work on the affinity thread and synchronously return its result."""

        return self._scheduler.call(self._state, func, timeout=timeout)

    def stop(self, *, wait: bool = True, timeout: float | None = None) -> bool:
        """Close new admission and optionally wait for already-queued work to drain."""

        return self._scheduler.stop_lane(self._state, wait=wait, timeout=timeout)

    def diagnostic_snapshot(self) -> dict[str, Any]:
        return self._scheduler.lane_snapshot(self._state)


class AffinityLaneScheduler:
    """One lazy process worker for serial thread-affine native work."""

    def __init__(self) -> None:
        self._condition = threading.Condition(threading.RLock())
        self._states: dict[str, _AffinityLaneState] = {}
        self._ready: deque[_AffinityPacket] = deque()
        self._thread: threading.Thread | None = None
        self._shutdown = False
        self._worker_ident: int | None = None
        self._metrics: dict[str, float | int | str] = {
            "worker_threads": 0,
            "worker_active": 0,
            "queue_depth": 0,
            "registered_lanes": 0,
            "tasks_completed": 0,
            "last_category": "<none>",
            "last_execution_ms": 0.0,
        }

    def register_lane(
        self,
        *,
        lane_id: str,
        category: str,
        runtime_generation: object | None,
        owner_class: str | None,
        owner_id: int | None,
    ) -> AffinityLaneHandle:
        normalized_id = str(lane_id or "affinity-lane")
        with self._condition:
            if self._shutdown:
                raise RuntimeError("Affinity lane scheduler is shut down")
            if normalized_id in self._states:
                raise RuntimeError(f"Affinity lane already registered: {normalized_id}")
            state = _AffinityLaneState(
                lane_id=normalized_id,
                category=str(category or "affinity_lane"),
                runtime_generation=runtime_generation,
                owner_class=owner_class,
                owner_id=owner_id,
            )
            self._states[normalized_id] = state
            self._ensure_thread_locked()
            self._refresh_counts_locked()
            return AffinityLaneHandle(self, state)

    def _ensure_thread_locked(self) -> None:
        if self._thread is not None:
            return
        thread = threading.Thread(
            target=self._worker_loop,
            name="affinity_io_lane",
            daemon=True,
        )
        self._thread = thread
        self._metrics["worker_threads"] = 1
        thread.start()

    def is_lane_stopped(self, state: _AffinityLaneState) -> bool:
        with self._condition:
            return bool(state.stopped)

    def submit(self, state: _AffinityLaneState, func: Callable[[], Any]) -> bool:
        if not callable(func):
            raise TypeError("Affinity lane work must be callable")
        with self._condition:
            if self._shutdown or state.stopped or self._states.get(state.lane_id) is not state:
                return False
            packet = _AffinityPacket(
                state=state,
                func=func,
                queued_perf_ts=time.perf_counter(),
            )
            state.pending += 1
            state.metrics["submitted"] += 1
            self._ready.append(packet)
            self._refresh_counts_locked()
            self._condition.notify()
            return True

    def call(
        self,
        state: _AffinityLaneState,
        func: Callable[[], Any],
        *,
        timeout: float | None = None,
    ) -> Any:
        """Run one callable on the affinity worker and wait for completion."""

        if threading.get_ident() == self._worker_ident:
            return func()
        done = threading.Event()
        packet = _AffinityPacket(
            state=state,
            func=func,
            queued_perf_ts=time.perf_counter(),
            done=done,
        )
        with self._condition:
            if self._shutdown or state.stopped or self._states.get(state.lane_id) is not state:
                raise RuntimeError(f"Affinity lane is stopped: {state.lane_id}")
            state.pending += 1
            state.metrics["submitted"] += 1
            self._ready.append(packet)
            self._refresh_counts_locked()
            self._condition.notify()
        if not done.wait(timeout=None if timeout is None else max(0.0, float(timeout))):
            with self._condition:
                state.metrics["wait_timeouts"] += 1
            raise TimeoutError(f"Affinity lane call timed out: {state.lane_id}")
        if packet.error is not None:
            raise packet.error
        return packet.result

    def stop_lane(
        self,
        state: _AffinityLaneState,
        *,
        wait: bool = True,
        timeout: float | None = None,
    ) -> bool:
        deadline = None if timeout is None else time.monotonic() + max(0.0, float(timeout))
        with self._condition:
            state.stopped = True
            self._condition.notify_all()
            if wait:
                while state.pending or state.active:
                    if deadline is None:
                        self._condition.wait()
                        continue
                    remaining = deadline - time.monotonic()
                    if remaining <= 0.0:
                        return False
                    self._condition.wait(remaining)
            if not state.pending and not state.active:
                self._states.pop(state.lane_id, None)
            self._refresh_counts_locked()
            return not state.pending and not state.active

    def lane_snapshot(self, state: _AffinityLaneState) -> dict[str, Any]:
        with self._condition:
            return {
                **state.metrics,
                "lane_id": state.lane_id,
                "category": state.category,
                "runtime_generation": state.runtime_generation,
                "owner_class": state.owner_class,
                "owner_id": state.owner_id,
                "stopped": state.stopped,
                "pending": state.pending,
                "active": state.active,
            }

    def diagnostic_snapshot(self) -> dict[str, Any]:
        with self._condition:
            self._refresh_counts_locked()
            return {
                **self._metrics,
                "worker_ident": self._worker_ident,
                "lanes": tuple(self.lane_snapshot(state) for state in self._states.values()),
            }

    def lifecycle_work_snapshot(self) -> tuple[dict[str, Any], ...]:
        with self._condition:
            return tuple(
                {
                    "task_id": state.lane_id,
                    "kind": "affinity_lane",
                    "category": state.category,
                    "pool": "affinity_lane",
                    "owner_class": state.owner_class,
                    "owner_id": state.owner_id,
                    "runtime_generation": state.runtime_generation,
                    "active": bool(state.active),
                    "pending": bool(state.pending),
                }
                for state in self._states.values()
                if not state.stopped or state.pending or state.active
            )

    def shutdown(self, *, wait: bool = True, timeout: float | None = None) -> bool:
        thread: threading.Thread | None
        with self._condition:
            self._shutdown = True
            for state in self._states.values():
                state.stopped = True
            self._condition.notify_all()
            thread = self._thread
        if wait and thread is not None and thread is not threading.current_thread():
            thread.join(timeout=None if timeout is None else max(0.0, float(timeout)))
        complete = thread is None or not thread.is_alive()
        if complete:
            with self._condition:
                self._thread = None
                self._states.clear()
                self._ready.clear()
                self._worker_ident = None
                self._metrics["worker_threads"] = 0
                self._refresh_counts_locked()
        return complete

    def _refresh_counts_locked(self) -> None:
        self._metrics["queue_depth"] = len(self._ready)
        self._metrics["registered_lanes"] = len(self._states)

    def _worker_loop(self) -> None:
        self._worker_ident = threading.get_ident()
        while True:
            with self._condition:
                while not self._ready and not self._shutdown:
                    self._condition.wait()
                if self._shutdown and not self._ready:
                    return
                packet = self._ready.popleft()
                state = packet.state
                state.pending = max(0, state.pending - 1)
                state.active += 1
                self._metrics["worker_active"] = 1
                self._metrics["last_category"] = state.category
                self._refresh_counts_locked()
            queue_wait_ms = max(0.0, (time.perf_counter() - packet.queued_perf_ts) * 1000.0)
            started = time.perf_counter()
            try:
                packet.result = packet.func()
            except BaseException as exc:  # propagate to synchronous callers; log async failures
                packet.error = exc
            execution_ms = max(0.0, (time.perf_counter() - started) * 1000.0)
            with self._condition:
                state.active = max(0, state.active - 1)
                state.metrics["completed"] += 1
                state.metrics["queue_wait_ms_total"] += queue_wait_ms
                state.metrics["queue_wait_ms_max"] = max(
                    float(state.metrics["queue_wait_ms_max"]), queue_wait_ms
                )
                state.metrics["execution_ms_total"] += execution_ms
                state.metrics["execution_ms_max"] = max(
                    float(state.metrics["execution_ms_max"]), execution_ms
                )
                if packet.error is not None:
                    state.metrics["failed"] += 1
                self._metrics["worker_active"] = 0
                self._metrics["tasks_completed"] = int(self._metrics["tasks_completed"]) + 1
                self._metrics["last_execution_ms"] = execution_ms
                if state.stopped and not state.pending and not state.active:
                    self._states.pop(state.lane_id, None)
                self._refresh_counts_locked()
                self._condition.notify_all()
            if packet.error is not None and packet.done is None:
                logger.error(
                    "Affinity lane task failed lane=%s category=%s: %s",
                    state.lane_id,
                    state.category,
                    packet.error,
                    exc_info=(type(packet.error), packet.error, packet.error.__traceback__),
                )
            if packet.done is not None:
                packet.done.set()


__all__ = ["AffinityLaneHandle", "AffinityLaneScheduler"]
