"""Passive Bubble authored-step accounting.

Bubble presentation is intentionally authored at the visualizer tick cadence.
This object owns activation/step tokens and diagnostics only; it cannot gate,
queue, defer, or batch authored input.
"""
from __future__ import annotations


class BubbleCadenceState:
    """Track requested and integrated logical steps without changing behaviour."""

    def __init__(self) -> None:
        self.activation_token = 0
        self._step_sequence = 0
        self.requested_steps = 0
        self.integrated_steps = 0
        self.integration_failures = 0

    def request_step(self, *, now_ts: float) -> None:
        """Record an authored opportunity without retaining its live input."""
        del now_ts  # Reserved for future passive interval diagnostics.
        self.requested_steps += 1

    def begin_step(self) -> tuple[int, int]:
        """Reserve a generation-owned token for the current Bubble step."""
        self._step_sequence += 1
        return self.activation_token, self._step_sequence

    def note_step_integrated(self) -> None:
        self.integrated_steps += 1

    def note_step_failed(self) -> None:
        self.integration_failures += 1

    def reset(self) -> None:
        """Invalidate prior step tokens at a mode/runtime boundary."""
        self.activation_token += 1
        self._step_sequence = 0

    def diagnostic_snapshot(self, *, reset: bool = False) -> dict[str, float | int]:
        integration_ratio = (
            float(self.integrated_steps) / float(self.requested_steps)
            if self.requested_steps
            else 0.0
        )
        snapshot: dict[str, float | int] = {
            "activation_token": self.activation_token,
            "requested_steps": self.requested_steps,
            "integrated_steps": self.integrated_steps,
            "integration_ratio": integration_ratio,
            "integration_failures": self.integration_failures,
        }
        if reset:
            self.requested_steps = 0
            self.integrated_steps = 0
            self.integration_failures = 0
        return snapshot
