"""BTF semantic: two protected Bubble results before one synchronization.

The bounded latest-state bridge coalesces protected authored edges by ``kind``.
Bubble uses one kind (``bubble_visible_result``), so two protected
renderer-visible Bubble result snapshots before a synchronization collapse to
the newer token.

The precise invariant this exercises:

    same-kind coalescing is safe ONLY WHILE every protected real Bubble
    consequence is forward-carried into the next renderer-visible result.

That holds for current Bubble because the simulation integrates one authored
step per advance (no skipping) and the authored event consequences
(kick spawn/promotion, vocal/snare persistent stream-burst envelope and the
velocities/positions it drives) persist in the continuously evolving state that
the newer renderer-visible result snapshot captures. The renderer reads only
``positions``/``extras``/``trails`` from that result (``event_kinds`` is
diagnostic).

These bars would fail if:

- an authored Bubble step were skipped (B not integrated from A), or
- coalescing dropped forward-carried state so B no longer reflected A's real
  authored consequence.

They deliberately do NOT assert two historical frames are replayed; BTF is about
the latest renderer-visible result carrying the required consequence exactly
once, not FIFO history. If a future authored Bubble consequence were visible for
a single frame and NOT forward-carried, the invariant above would be violated
and the coalescing rule (not the tests) would need per-kind history.
"""

from __future__ import annotations

import random
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


# --- Production Bubble event semantics (real BubbleSimulation) --------------
#
# The accumulating fixture above proves the bridge/coalescing RULE. These bars
# prove the invariant against the ACTUAL production Bubble event semantics: a
# real authored event consumed at step A produces a persistent consequence that
# is forward-carried into the next renderer-visible result at step B, so the
# coalesced newer result still contains A's consequence. Quiet continuous energy
# is used so the discrete authored event dominates the persistent stream-burst
# envelope (otherwise loud continuous energy saturates it and masks the event).


def _make_scheduler(fire: dict[str, bool]):
    state = dict(fire)

    def consume_next(name, max_age_s=0.3):
        if state.get(name):
            state[name] = False
            return SimpleNamespace(strength=1.0, timestamp=1.0)
        return None

    return SimpleNamespace(consume_next=consume_next)


def _advance_real(runtime, *, fire, authored_ts, edge_token):
    return runtime.advance(
        dt=0.011,
        energy={"bass": 0.05, "mid": 0.05, "high": 0.05},
        settings={"_event_scheduler": _make_scheduler(fire)},
        pulse={"bass": 0.05},
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


@pytest.mark.parametrize("event_kind", ["vocal_swell", "snare"])
def test_real_bubble_event_consequence_forward_carries_into_next_result(event_kind):
    """A real authored event at A persists into the renderer-visible result at B.

    Uses the real BubbleSimulation through the production advance() path. Both
    runs are seeded identically and receive identical input except the authored
    event at step A, so any difference in B is caused by that event's persistent
    consequence being forward-carried (the event path itself consumes no random).
    """

    def run(fire_event_at_a: bool):
        random.seed(99)
        runtime = BubbleFrameRuntime()  # real BubbleSimulation (default factory)
        frame_a = _advance_real(
            runtime,
            fire={event_kind: True} if fire_event_at_a else {},
            authored_ts=5.0,
            edge_token=1,
        )
        frame_b = _advance_real(
            runtime, fire={}, authored_ts=5.011, edge_token=2
        )
        return frame_a, frame_b

    (treat_a, treat_b) = run(True)
    (ctrl_a, ctrl_b) = run(False)

    # The authored event is consumed and recorded on A's protected edge; the
    # control produces no edge at A.
    assert len(treat_a.protected_edges) == 1
    assert treat_a.protected_edges[0].result["event_kinds"] == (event_kind,)
    assert ctrl_a.protected_edges == ()

    # B is produced with no event on either run, yet the treatment's B differs
    # from the control's B: the event's real consequence persisted forward into
    # the next renderer-visible result. Coalescing A away would therefore still
    # keep A's consequence (it lives in B), which is why same-kind coalescing is
    # safe for current Bubble semantics.
    assert treat_b.positions != ctrl_b.positions
    l1 = sum(abs(x - y) for x, y in zip(treat_b.positions, ctrl_b.positions))
    assert l1 > 0.0


def test_real_bubble_keeps_one_authored_step_per_integration():
    """No second logical clock / no batching: one advance -> one integration."""

    random.seed(99)
    runtime = BubbleFrameRuntime()
    _advance_real(runtime, fire={"vocal_swell": True}, authored_ts=5.0, edge_token=1)
    first_time = runtime.simulation._time
    _advance_real(runtime, fire={}, authored_ts=5.011, edge_token=2)
    second_time = runtime.simulation._time
    # The simulation clock advanced by exactly one authored dt per advance.
    assert second_time == pytest.approx(first_time + 0.011)
