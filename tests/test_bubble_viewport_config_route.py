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

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
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


def _controller():
    return VisualizerRuntimeController(
        runtime_generation=0,
        bar_count=24,
        initial_mode="bubble",
        engine_factory=lambda _bar_count: object(),
    )


def _commit(controller, extent):
    """Simulate the ordinary presentation publication committing an extent."""

    controller.commit_presentation_metrics(
        resolve_visualizer_presentation(
            policy=get_visualizer_presentation_policy("bubble"),
            display_size=(1920.0, 1080.0),
            outer_origin=(40.0, 60.0),
            viewport_extent=extent,
        )
    )


def test_custom_override_takes_precedence_over_committed_extent_and_coalesces() -> None:
    controller = _controller()
    # Starts at the canonical committed baseline with no override.
    assert controller.committed_viewport_extent == CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
    assert controller.has_custom_viewport_override is False
    assert controller.presentation_viewport_extent == CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE

    # While a CUSTOM override is active it wins; the latest value coalesces.
    controller.set_custom_viewport_override((630.0, 280.0))
    assert controller.presentation_viewport_extent == (630.0, 280.0)
    controller.set_custom_viewport_override((420.0, 420.0))
    assert controller.presentation_viewport_extent == (420.0, 420.0)

    # Retiring the override falls back to committed (never manufactured canonical
    # when committed is non-canonical).
    _commit(controller, (760.0, 280.0))
    controller.set_custom_viewport_override(None)
    assert controller.has_custom_viewport_override is False
    assert controller.presentation_viewport_extent == (760.0, 280.0)

    for bad in ((0.0, 280.0), (420.0, -1.0)):
        with pytest.raises(ValueError):
            controller.set_custom_viewport_override(bad)


def test_cancel_restores_committed_and_save_promotes_committed() -> None:
    # Scenario 1: canonical committed -> CUSTOM wide -> Cancel -> canonical.
    c1 = _controller()
    c1.set_custom_viewport_override((630.0, 280.0))
    c1.set_custom_viewport_override(None)  # Cancel retires override; no commit.
    assert c1.presentation_viewport_extent == CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE

    # Scenario 2: committed wide -> CUSTOM taller -> Cancel -> original wide.
    c2 = _controller()
    _commit(c2, (630.0, 280.0))
    c2.set_custom_viewport_override((630.0, 420.0))
    c2.set_custom_viewport_override(None)  # Cancel.
    assert c2.presentation_viewport_extent == (630.0, 280.0)

    # Scenario 3: canonical committed -> CUSTOM wide -> Save -> saved wide.
    c3 = _controller()
    c3.set_custom_viewport_override((630.0, 280.0))
    _commit(c3, (630.0, 280.0))       # Save promotes the new committed extent...
    c3.set_custom_viewport_override(None)  # ...then the override retires.
    assert c3.presentation_viewport_extent == (630.0, 280.0)

    # Scenario 4: committed wide -> CUSTOM canonical -> Save -> canonical.
    c4 = _controller()
    _commit(c4, (630.0, 280.0))
    c4.set_custom_viewport_override((420.0, 280.0))
    _commit(c4, (420.0, 280.0))       # Save promotes canonical.
    c4.set_custom_viewport_override(None)
    assert c4.presentation_viewport_extent == CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE


def test_ordinary_publication_cannot_erase_a_live_custom_override() -> None:
    # Scenario 5: an ordinary committed-presentation publication while CUSTOM is
    # active updates only the committed extent and cannot erase the working
    # override that the authored step actually consumes.
    controller = _controller()
    controller.set_custom_viewport_override((630.0, 280.0))
    _commit(controller, (420.0, 280.0))
    assert controller.committed_viewport_extent == (420.0, 280.0)
    assert controller.presentation_viewport_extent == (630.0, 280.0)
    # And once CUSTOM retires, the ordinary committed value applies.
    controller.set_custom_viewport_override(None)
    assert controller.presentation_viewport_extent == (420.0, 280.0)


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
