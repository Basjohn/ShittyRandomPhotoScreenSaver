"""Bubble-owned worker lane accounting.

Bubble presentation is intentionally authored at the visualizer tick cadence.
This object owns activation/task tokens and diagnostics only; it must not add a
second cadence gate, queue authored input, or batch several reactions into one
visible result.
"""
from __future__ import annotations


class BubbleCadenceState:
    """Track the bounded single-worker/result lane without changing behaviour."""

    def __init__(self) -> None:
        self.activation_token = 0
        self._task_sequence = 0
        self.offered_ticks = 0
        self.submitted_tasks = 0
        self.worker_busy_deferrals = 0
        self.result_waiting_deferrals = 0
        self.submission_failures = 0

    def offer_tick(self, *, now_ts: float) -> None:
        """Record an authored opportunity without retaining its live input."""
        del now_ts  # Reserved for future passive interval diagnostics.
        self.offered_ticks += 1

    def note_lane_blocked(self, *, worker_busy: bool, result_waiting: bool) -> None:
        """Account for existing ownership backpressure, never artificial delay."""
        if worker_busy:
            self.worker_busy_deferrals += 1
        if result_waiting:
            self.result_waiting_deferrals += 1

    def begin_submission(self) -> tuple[int, int]:
        """Reserve a generation-owned token for one eligible Bubble step."""
        self._task_sequence += 1
        return self.activation_token, self._task_sequence

    def note_submission_succeeded(self) -> None:
        self.submitted_tasks += 1

    def note_submission_failure(self) -> None:
        self.submission_failures += 1

    def reset(self) -> None:
        """Invalidate in-flight task tokens at a mode/runtime boundary."""
        self.activation_token += 1
        self._task_sequence = 0

    def diagnostic_snapshot(self, *, reset: bool = False) -> dict[str, float | int]:
        publish_ratio = (
            float(self.submitted_tasks) / float(self.offered_ticks)
            if self.offered_ticks
            else 0.0
        )
        snapshot: dict[str, float | int] = {
            "activation_token": self.activation_token,
            "offered_ticks": self.offered_ticks,
            "submitted_tasks": self.submitted_tasks,
            "publish_ratio": publish_ratio,
            "worker_busy_deferrals": self.worker_busy_deferrals,
            "result_waiting_deferrals": self.result_waiting_deferrals,
            "submission_failures": self.submission_failures,
        }
        if reset:
            self.offered_ticks = 0
            self.submitted_tasks = 0
            self.worker_busy_deferrals = 0
            self.result_waiting_deferrals = 0
            self.submission_failures = 0
        return snapshot
