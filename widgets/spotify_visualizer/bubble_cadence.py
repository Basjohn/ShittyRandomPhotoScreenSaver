"""Bubble-owned worker submission cadence.

The visualizer presentation timer still authors every logical Bubble step.
This module only batches adjacent immutable input snapshots so the compute
pool does not receive one tiny task for every presentation tick.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Optional


@dataclass(frozen=True)
class BubbleSimulationPacket:
    """One authored Bubble simulation step."""

    sequence: int
    dt: float
    energy: dict[str, Any]
    settings: dict[str, Any]
    pulse: dict[str, Any]
    has_discrete_impulse: bool = False

    def coalesce_continuous(self, newer: "BubbleSimulationPacket") -> "BubbleSimulationPacket":
        """Merge overload-only continuous state without losing elapsed time or peaks."""
        combined_dt = max(0.001, min(0.1, float(self.dt) + float(newer.dt)))
        energy = dict(newer.energy)
        pulse = dict(newer.pulse)
        preserve_peak = self.has_discrete_impulse or newer.has_discrete_impulse
        if preserve_peak:
            for key in (
                "bass",
                "mid",
                "high",
                "overall",
                "smooth_mid",
                "smooth_high",
                "crest",
                "pulse_bass",
                "pulse_mid",
                "pulse_high",
                "pulse_overall",
            ):
                energy[key] = max(
                    float(self.energy.get(key, 0.0) or 0.0),
                    float(newer.energy.get(key, 0.0) or 0.0),
                )
            for key in ("bass", "mid_high"):
                pulse[key] = max(
                    float(self.pulse.get(key, 0.0) or 0.0),
                    float(newer.pulse.get(key, 0.0) or 0.0),
                )
        return replace(
            newer,
            dt=combined_dt,
            energy=energy,
            pulse=pulse,
            has_discrete_impulse=preserve_peak,
        )


class BubbleCadenceState:
    """UI-owned token budget and bounded packet queue for Bubble compute."""

    def __init__(self, *, submissions_hz: float = 60.0, max_batch_size: int = 2) -> None:
        self.submissions_hz = max(1.0, float(submissions_hz))
        self.max_batch_size = max(1, int(max_batch_size))
        self.activation_token = 0
        self._task_sequence = 0
        self._packet_sequence = 0
        self._last_budget_ts: Optional[float] = None
        self._credits = 2.0
        self._pending: list[BubbleSimulationPacket] = []
        self.offered_packets = 0
        self.submitted_tasks = 0
        self.submitted_packets = 0
        self.cadence_deferrals = 0
        self.busy_deferrals = 0
        self.coalesced_packets = 0

    def next_packet(
        self,
        *,
        dt: float,
        energy: dict[str, Any],
        settings: dict[str, Any],
        pulse: dict[str, Any],
        has_discrete_impulse: bool,
    ) -> BubbleSimulationPacket:
        self._packet_sequence += 1
        return BubbleSimulationPacket(
            sequence=self._packet_sequence,
            dt=max(0.001, min(0.1, float(dt))),
            energy=dict(energy),
            settings=dict(settings),
            pulse=dict(pulse),
            has_discrete_impulse=bool(has_discrete_impulse),
        )

    def offer(self, packet: BubbleSimulationPacket, *, now_ts: float) -> None:
        self._accrue(now_ts)
        self.offered_packets += 1
        if len(self._pending) < self.max_batch_size:
            self._pending.append(packet)
            return

        # This is an overload path only. Keep the oldest queued step and fold
        # continuous elapsed time/newest state into the final slot.
        self._pending[-1] = self._pending[-1].coalesce_continuous(packet)
        self.coalesced_packets += 1

    def take_ready(
        self,
        *,
        worker_busy: bool,
        result_waiting: bool,
    ) -> Optional[tuple[tuple[int, int], tuple[BubbleSimulationPacket, ...]]]:
        if not self._pending:
            return None
        if worker_busy or result_waiting:
            self.busy_deferrals += 1
            return None
        if self._credits < 1.0:
            self.cadence_deferrals += 1
            return None

        self._credits -= 1.0
        batch = tuple(self._pending[: self.max_batch_size])
        del self._pending[: len(batch)]
        self._task_sequence += 1
        task_token = (self.activation_token, self._task_sequence)
        self.submitted_tasks += 1
        self.submitted_packets += len(batch)
        return task_token, batch

    def reset(self) -> None:
        """Invalidate in-flight task tokens and clear queued mode-owned state."""
        self.activation_token += 1
        self._task_sequence = 0
        self._packet_sequence = 0
        self._last_budget_ts = None
        self._credits = 2.0
        self._pending.clear()

    def restore_batch(self, batch: tuple[BubbleSimulationPacket, ...]) -> None:
        """Restore a batch when task submission itself fails."""
        restored = list(batch) + self._pending
        self._pending = restored[: self.max_batch_size]
        for packet in restored[self.max_batch_size :]:
            self._pending[-1] = self._pending[-1].coalesce_continuous(packet)
            self.coalesced_packets += 1

    def diagnostic_snapshot(self, *, reset: bool = False) -> dict[str, float | int]:
        snapshot: dict[str, float | int] = {
            "activation_token": self.activation_token,
            "offered_packets": self.offered_packets,
            "submitted_tasks": self.submitted_tasks,
            "submitted_packets": self.submitted_packets,
            "pending_packets": len(self._pending),
            "cadence_deferrals": self.cadence_deferrals,
            "busy_deferrals": self.busy_deferrals,
            "coalesced_packets": self.coalesced_packets,
            "average_batch_size": (
                float(self.submitted_packets) / float(self.submitted_tasks)
                if self.submitted_tasks
                else 0.0
            ),
        }
        if reset:
            self.offered_packets = 0
            self.submitted_tasks = 0
            self.submitted_packets = 0
            self.cadence_deferrals = 0
            self.busy_deferrals = 0
            self.coalesced_packets = 0
        return snapshot

    def _accrue(self, now_ts: float) -> None:
        now = float(now_ts)
        if self._last_budget_ts is None:
            self._last_budget_ts = now
            return
        elapsed = max(0.0, min(0.25, now - self._last_budget_ts))
        self._last_budget_ts = now
        # Retain at most one future token. This permits fractional 60 Hz
        # scheduling on a 90/100 Hz source without a multi-task catch-up burst.
        self._credits = min(2.0, self._credits + elapsed * self.submissions_hz)
