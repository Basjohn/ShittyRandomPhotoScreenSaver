"""G4.2 — the live viewport-configuration route into the authored Bubble step.

These bars prove the committed CUSTOM viewport extent reaches the next authored
Bubble step as latest spatial configuration, coalescing freely, without a queue,
a clock, or a pointer-driven tick. They do NOT yet assert domain reflow (that is
the Bubble simulation's job, proven separately); they assert the config seam and
its consumption exist and are live.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime
from widgets.spotify_visualizer.render_state import (
    CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
)
from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController


def _scheduler():
    return SimpleNamespace(consume_next=lambda name, max_age_s=0.3: None)


class _ExtentRecordingSimulation:
    """Record the viewport-extent config each authored step received."""

    count = 1

    def __init__(self) -> None:
        self.tick_calls = 0
        self.seen_extents: list[object] = []

    def tick(self, _dt, _energy, settings) -> None:
        self.tick_calls += 1
        self.seen_extents.append(settings.get("_bubble_viewport_extent"))

    def snapshot(self, **_pulse):
        return [0.5, 0.5, 0.05, 1.0], [1.0, 0.0, 0.0, 0.0], []

    @staticmethod
    def reset() -> None:
        return None


def _advance(runtime, *, extent, authored_ts, edge_token):
    return runtime.advance(
        dt=0.011,
        energy={"bass": 0.2},
        settings={"_event_scheduler": _scheduler()},
        pulse={"bass": 0.2},
        source_timestamp=authored_ts - 0.01,
        authored_timestamp=authored_ts,
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        playing=True,
        source_ready=True,
        source_generation=5,
        source_activation_id=7,
        edge_token=edge_token,
        viewport_extent=extent,
    )


def test_runtime_controller_viewport_extent_seam_is_settable_and_coalesces() -> None:
    controller = VisualizerRuntimeController(
        runtime_generation=0,
        bar_count=24,
        initial_mode="bubble",
        engine_factory=lambda _bar_count: object(),
    )
    # The seam starts at the canonical baseline, never uninitialised.
    assert controller.presentation_viewport_extent == CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE

    controller.set_presentation_viewport_extent((630.0, 280.0))
    assert controller.presentation_viewport_extent == (630.0, 280.0)

    # Latest wins: viewport extent is state, not an event, so it coalesces.
    controller.set_presentation_viewport_extent((420.0, 420.0))
    assert controller.presentation_viewport_extent == (420.0, 420.0)

    # None restores the canonical baseline.
    controller.set_presentation_viewport_extent(None)
    assert controller.presentation_viewport_extent == CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE

    for bad in ((0.0, 280.0), (420.0, -1.0)):
        with pytest.raises(ValueError):
            controller.set_presentation_viewport_extent(bad)


def test_bubble_advance_carries_viewport_extent_into_each_authored_step() -> None:
    runtime = BubbleFrameRuntime(simulation_factory=_ExtentRecordingSimulation)

    # A wide extent reaches the current authored step's simulation settings.
    _advance(runtime, extent=(630.0, 280.0), authored_ts=1.0, edge_token=1)
    sim = runtime.simulation
    assert sim.tick_calls == 1
    assert sim.seen_extents[-1] == (630.0, 280.0)

    # A later step sees the latest coalesced extent; no extra step is created by a
    # geometry change.
    _advance(runtime, extent=(420.0, 560.0), authored_ts=1.011, edge_token=2)
    assert sim.tick_calls == 2
    assert sim.seen_extents[-1] == (420.0, 560.0)

    # Returning to baseline (None) is carried through as a strict baseline signal.
    _advance(runtime, extent=None, authored_ts=1.022, edge_token=3)
    assert sim.tick_calls == 3
    assert sim.seen_extents[-1] is None
