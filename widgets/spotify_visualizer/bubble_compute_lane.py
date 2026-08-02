"""Bubble facade over ThreadManager's bounded compute-lane scheduler.

Every authored Bubble tick remains a single logical simulation step. The
process-owned scheduler removes per-step Task/Future/resource/UI-stat churn
without occupying a general COMPUTE executor worker while idle, batching
steps, or coupling simulation to paint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
import weakref


@dataclass(frozen=True)
class BubbleStepPacket:
    task_token: tuple[int, int]
    dt: float
    energy: dict[str, Any]
    settings: dict[str, Any]
    pulse: dict[str, Any]
    source_ts: float
    authored_ts: float


class BubbleComputeLane:
    """One serial scheduler lane serving one visualizer activation owner."""

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
        self._lane_id = f"{task_id}:lane:{id(self)}"
        self._handle = None
        self._stopped = False
        self._local_metrics: dict[str, float | int] = {
            "lane_start_failures": 0,
            "callback_owner_released": 0,
        }

    @property
    def is_stopped(self) -> bool:
        handle = self._handle
        return bool(
            self._stopped
            or handle is None
            or getattr(handle, "is_stopped", True)
        )

    def start(self, thread_manager) -> None:
        if self._handle is not None and not self.is_stopped:
            return
        if self._stopped:
            raise RuntimeError("Cannot start a stopped Bubble compute lane")
        creator = getattr(thread_manager, "create_compute_lane", None)
        if not callable(creator):
            self._local_metrics["lane_start_failures"] += 1
            raise RuntimeError("ThreadManager does not provide managed compute lanes")
        self._handle = creator(
            self._execute_packet,
            self._publish_packet,
            lane_id=self._lane_id,
            category="visualizer.bubble_simulation",
            runtime_generation=self._runtime_generation,
        )

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
        handle = self._handle
        if self._stopped or handle is None:
            return False
        return bool(
            handle.submit(
                BubbleStepPacket(
                    task_token=task_token,
                    dt=float(dt),
                    energy=energy,
                    settings=settings,
                    pulse=pulse,
                    source_ts=float(source_ts or 0.0),
                    authored_ts=float(authored_ts or 0.0),
                )
            )
        )

    def cancel_pending(self) -> int:
        handle = self._handle
        if handle is None:
            return 0
        return int(handle.cancel_pending())

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        handle = self._handle
        if handle is not None:
            handle.stop()

    def diagnostic_snapshot(self) -> dict[str, Any]:
        handle = self._handle
        snapshot = (
            handle.diagnostic_snapshot()
            if handle is not None
            else {
                "lane_registrations": 0,
                "executor_task_submissions": 0,
                "logical_steps_accepted": 0,
                "logical_steps_completed": 0,
                "logical_steps_published": 0,
                "submit_rejected_busy": 0,
                "submit_rejected_stopped": 0,
                "pending_cancelled": 0,
                "handoff_ms_mean": 0.0,
                "handoff_ms_max": 0.0,
                "execution_ms_mean": 0.0,
                "execution_ms_max": 0.0,
                "callback_ms_mean": 0.0,
                "callback_ms_max": 0.0,
            }
        )
        snapshot.update(self._local_metrics)
        snapshot["stopped"] = self.is_stopped
        return snapshot

    def _execute_packet(self, packet: BubbleStepPacket) -> Any:
        worker = self._worker_ref()
        if worker is None:
            raise RuntimeError("Bubble compute owner was released")
        return worker(
            packet.dt,
            packet.energy,
            packet.settings,
            packet.pulse,
            task_token=packet.task_token,
        )

    def _publish_packet(self, result, *, payload: BubbleStepPacket) -> None:
        callback = self._result_callback_ref()
        if callback is None:
            self._local_metrics["callback_owner_released"] += 1
            return
        return callback(
            result,
            task_token=payload.task_token,
            source_ts=payload.source_ts,
            authored_ts=payload.authored_ts,
        )
