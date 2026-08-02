"""Temporary Bubble facade over the approved general COMPUTE executor path.

The rejected persistent scheduler remains available elsewhere for forensic work,
but production Bubble submissions through this facade use the same one-task-per-
lane-free-authored-step executor semantics as the approved pre-lane checkpoint.
The facade exists only to preserve current widget/timing instrumentation until
operator approval allows the rejected lane scaffolding to be removed.
"""

from __future__ import annotations

import threading
from typing import Any, Callable
import weakref


class BubbleComputeLane:
    """Compatibility adapter that does not create a persistent compute lane."""

    def __init__(
        self,
        *,
        worker: Callable[..., Any],
        result_callback: Callable[..., None],
        runtime_generation: int | None,
        task_id: str,
    ) -> None:
        self._runtime_generation = runtime_generation
        self._worker_ref = weakref.WeakMethod(worker)
        self._result_callback_ref = weakref.WeakMethod(result_callback)
        self._task_id = str(task_id)
        self._thread_manager_ref: Callable[[], Any | None] = lambda: None
        self._lock = threading.Lock()
        self._stopped = False
        self._in_flight = False
        self._metrics: dict[str, float | int] = {
            "lane_registrations": 0,
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
            "lane_start_failures": 0,
            "callback_owner_released": 0,
        }

    @property
    def is_stopped(self) -> bool:
        with self._lock:
            return bool(self._stopped)

    def start(self, thread_manager) -> None:
        """Bind the ordinary executor owner without registering a lane."""

        with self._lock:
            if self._stopped:
                raise RuntimeError("Cannot start a stopped Bubble executor adapter")
            try:
                self._thread_manager_ref = weakref.ref(thread_manager)
            except TypeError:
                self._thread_manager_ref = lambda: thread_manager

    def submit(
        self,
        *,
        task_token: tuple[int, int],
        dt: float,
        energy: dict[str, Any],
        settings: dict[str, Any],
        pulse: dict[str, Any],
        source_ts: float,
        authored_ts: float,
    ) -> bool:
        """Submit one authored Bubble step through ``submit_compute_task``."""

        thread_manager = self._thread_manager_ref()
        worker = self._worker_ref()
        if thread_manager is None or worker is None:
            with self._lock:
                self._metrics["owner_releases"] += 1
            return False

        with self._lock:
            if self._stopped:
                self._metrics["submit_rejected_stopped"] += 1
                return False
            if self._in_flight:
                self._metrics["submit_rejected_busy"] += 1
                return False
            self._in_flight = True
            self._metrics["logical_steps_accepted"] += 1
            self._metrics["executor_task_submissions"] += 1

        runtime_generation = self._runtime_generation

        def _job():
            # Match the approved pre-lane worker call: token ownership stays in
            # the publication callback and is not injected into simulation.
            return worker(float(dt), energy, settings, pulse)

        def _on_done(task_result) -> None:
            callback = self._result_callback_ref()
            with self._lock:
                self._in_flight = False
                self._metrics["logical_steps_completed"] += 1
            if callback is None:
                with self._lock:
                    self._metrics["callback_owner_released"] += 1
                    self._metrics["logical_steps_rejected_publication"] += 1
                return
            try:
                callback(
                    task_result,
                    task_token=task_token,
                    source_ts=float(source_ts or 0.0),
                    authored_ts=float(authored_ts or 0.0),
                )
            except Exception:
                with self._lock:
                    self._metrics["callback_failures"] += 1
                raise
            else:
                with self._lock:
                    self._metrics["logical_steps_published"] += 1

        # Preserve current passive lifecycle attribution without changing the
        # approved executor admission or callback sequence.
        _job._srpss_runtime_generation = runtime_generation
        _on_done._srpss_runtime_generation = runtime_generation

        try:
            thread_manager.submit_compute_task(
                _job,
                callback=_on_done,
                task_id=self._task_id,
                category="visualizer.bubble_simulation",
            )
        except Exception:
            with self._lock:
                self._in_flight = False
                self._metrics["worker_failures"] += 1
            return False
        return True

    def cancel_pending(self) -> int:
        thread_manager = self._thread_manager_ref()
        cancel = getattr(thread_manager, "cancel_task", None)
        if not callable(cancel):
            return 0
        try:
            cancelled = bool(cancel(self._task_id))
        except Exception:
            cancelled = False
        if cancelled:
            with self._lock:
                self._in_flight = False
                self._metrics["pending_cancelled"] += 1
            return 1
        return 0

    def stop(self) -> None:
        with self._lock:
            if self._stopped:
                return
            self._stopped = True
        self.cancel_pending()

    def diagnostic_snapshot(self) -> dict[str, Any]:
        with self._lock:
            snapshot: dict[str, Any] = dict(self._metrics)
            snapshot.update(
                {
                    "lane_id": "<general-compute-adapter>",
                    "category": "visualizer.bubble_simulation",
                    "runtime_generation": self._runtime_generation,
                    "stopped": bool(self._stopped),
                    "active": bool(self._in_flight),
                    "publishing": False,
                    "pending": False,
                    "queued": False,
                    "adapter": "general_compute",
                }
            )
            return snapshot
