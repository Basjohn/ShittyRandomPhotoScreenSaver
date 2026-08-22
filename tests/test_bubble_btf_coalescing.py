"""BTF semantic: two protected Bubble results before one synchronization.

The bounded latest-state bridge coalesces protected authored edges by ``kind``.
Bubble uses one kind (``bubble_visible_result``), so two protected results before
a synchronization collapse to the newer token. This is CORRECT for Bubble
because the simulation integrates one authored step per advance (no skipping),
so the newer result's geometry is the continuous forward evolution that already
incorporates the older authored consequence.

These bars make that guarantee explicit and would fail if:

- an authored Bubble step were skipped (B not integrated from A), or
- coalescing dropped forward-carried state so B no longer reflected A.

They deliberately do NOT assert two historical frames are replayed; BTF is about
the latest authored result carrying the required visible consequence exactly
once, not FIFO history.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime
from widgets.spotify_visualizer.render_bridge import VisualizerSnapshotBridge
from widgets.spotify_visualizer.render_state import (
    BubbleFrame,
    VisualizerCommonState,
    VisualizerLogicalFrame,
    compose_visualizer_render_snapshot,
    freeze_render_fields,
)


class _AccumulatingSimulation:
    """State that accumulates each authored step's input into position X.

    This makes the older authored consequence observable in the newer snapshot:
    if step A was integrated before step B, B's position X carries A's input.
    """

    count = 1

    def __init__(self) -> None:
        self.value = 0.0
        self.tick_calls = 0

    def tick(self, _dt, energy, settings) -> None:
        self.tick_calls += 1
        self.value += float(energy.get("bass", 0.0))
        # Consume an authored event so a protected visible-result edge is produced.
        settings["_event_scheduler"].consume_next("kick", max_age_s=0.3)

    def snapshot(self, **_pulse):
        return [self.value, 0.5, 0.05, 1.0], [1.0, 0.0, 0.0, 0.0], []

    @staticmethod
    def reset() -> None:
        return None


def _scheduler():
    return SimpleNamespace(
        consume_next=lambda name, max_age_s=0.3: (
            SimpleNamespace(strength=1.0, timestamp=1.0)
            if name == "kick"
            else None
        )
    )


def _advance(runtime, *, bass, authored_ts, edge_token):
    return runtime.advance(
        dt=0.011,
        energy={"bass": bass},
        settings={"_event_scheduler": _scheduler()},
        pulse={"bass": bass},
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
    )


def _logical_with_edge(frame, *, timestamp):
    return VisualizerLogicalFrame(
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        source_generation=5,
        source_activation_id=7,
        mode_id="bubble",
        playing=True,
        logical_timestamp=timestamp,
        source_timestamp=timestamp - 0.01,
        changed=True,
        present_frame=True,
        mode_reveal_ready=True,
        common=VisualizerCommonState(bars=(), bar_count=0),
        mode_state=BubbleFrame(
            positions=frame.positions,
            extras=frame.extras,
            trails=frame.trails,
            bubble_count=frame.bubble_count,
            source_timestamp=frame.source_timestamp,
            simulation_timestamp=frame.simulation_timestamp,
            parameters=freeze_render_fields({}),
        ),
        protected_edges=frame.protected_edges,
    )


def _presentation():
    from core.settings.visualizer_mode_registry import (
        get_visualizer_presentation_policy,
    )
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_visualizer_presentation,
    )

    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("bubble"),
        display_size=(1920.0, 1080.0),
        outer_origin=(120.0, 80.0),
        uniform_visual_scale=1.0,
        viewport_extent=(420.0, 280.0),
        border_width=4.0,
        corner_radius=8.0,
    )


def test_newer_bubble_result_incorporates_the_older_authored_consequence():
    # A then B on one runtime: each authored step integrates exactly once.
    runtime = BubbleFrameRuntime(simulation_factory=_AccumulatingSimulation)
    frame_a = _advance(runtime, bass=0.3, authored_ts=5.0, edge_token=1)
    frame_b = _advance(runtime, bass=0.5, authored_ts=5.011, edge_token=2)

    assert runtime.simulation.tick_calls == 2  # one integration per authored step
    assert len(frame_a.protected_edges) == 1
    assert len(frame_b.protected_edges) == 1
    # A's authored input (0.3) is carried forward into B's geometry (0.3 + 0.5).
    assert frame_a.protected_edges[0].result["positions"][0] == pytest.approx(0.3)
    assert frame_b.protected_edges[0].result["positions"][0] == pytest.approx(0.8)

    # Control: B alone (A never integrated) would only reflect 0.5, proving the
    # 0.8 above genuinely contains A's consequence rather than B in isolation.
    control = BubbleFrameRuntime(simulation_factory=_AccumulatingSimulation)
    frame_b_only = _advance(control, bass=0.5, authored_ts=5.0, edge_token=1)
    assert frame_b_only.protected_edges[0].result["positions"][0] == pytest.approx(0.5)
    assert frame_b.protected_edges[0].result["positions"][0] != pytest.approx(0.5)


def test_two_protected_results_before_one_sync_coalesce_to_the_carrying_result():
    runtime = BubbleFrameRuntime(simulation_factory=_AccumulatingSimulation)
    frame_a = _advance(runtime, bass=0.3, authored_ts=5.0, edge_token=1)
    frame_b = _advance(runtime, bass=0.5, authored_ts=5.011, edge_token=2)

    bridge = VisualizerSnapshotBridge()
    identity = bridge.begin_activation(
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        mode_id="bubble",
    )
    presentation = _presentation()

    # Publish A, then B, with NO synchronization consume in between.
    assert bridge.publish(
        compose_visualizer_render_snapshot(
            _logical_with_edge(frame_a, timestamp=5.0),
            presentation,
            logical_revision=1,
        )
    )
    assert bridge.publish(
        compose_visualizer_render_snapshot(
            _logical_with_edge(frame_b, timestamp=5.011),
            presentation,
            logical_revision=2,
        )
    )
    assert bridge.superseded_count == 1  # B superseded the unread A slot

    taken = bridge.take_for_render(
        runtime_generation=identity.runtime_generation,
        engine_generation=identity.engine_generation,
        activation_id=identity.activation_id,
        mode_id=identity.mode_id,
    )
    assert taken is not None
    edges = taken.logical.protected_edges
    # Exactly one coalesced bubble edge, the newer token, whose geometry already
    # incorporates A's authored consequence (0.8, not 0.5).
    bubble_edges = [e for e in edges if e.kind == "bubble_visible_result"]
    assert len(bubble_edges) == 1
    assert bubble_edges[0].token == 2
    assert bubble_edges[0].result["positions"][0] == pytest.approx(0.8)

    # The slot is empty after the single synchronization consume (no FIFO replay).
    assert bridge.peek() is None
