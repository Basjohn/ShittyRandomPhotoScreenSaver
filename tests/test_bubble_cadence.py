from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer.bubble_cadence import BubbleCadenceState


_TEMPORAL_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "visualizer_temporal"
    / "v1"
    / "bubble_discrete_edge.json"
)
_TEMPORAL_GOLDEN = (
    Path(__file__).parent
    / "goldens"
    / "visualizer_temporal"
    / "v1"
    / "bubble_discrete_edge_general_compute.json"
)
_TEMPORAL_MANIFEST = _TEMPORAL_GOLDEN.parent / "manifest.json"


def _load_temporal_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_visualizer_temporal_manifest_hashes_are_immutable():
    manifest = _load_temporal_json(_TEMPORAL_MANIFEST)
    repo_root = Path(__file__).parent.parent

    for artifact in manifest["artifacts"]:
        path = repo_root / artifact["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == artifact["sha256"], artifact["path"]


def _assert_bubble_temporal_contract(trace: dict, golden: dict) -> None:
    authored_tick = int(trace["first_visible"]["authored_tick"])
    visible_tick = int(trace["first_visible"]["visible_tick"])
    latency_ticks = int(trace["first_visible"]["latency_ticks"])
    visible_count = int(trace["first_visible"]["visible_edge_count"])
    contract = golden["contract"]

    assert authored_tick >= 0, "the discrete edge must be authored"
    assert visible_tick > authored_tick, "the authored edge must reach presentation"
    assert latency_ticks <= int(contract["max_first_visible_latency_ticks"]), (
        "the discrete edge missed the first lane-free visible tick"
    )
    assert visible_count == int(contract["required_visible_edge_count"]), (
        "the discrete edge must be visible exactly once"
    )
    assert trace["executor"]["lane_registrations"] == int(
        contract["prohibited_lane_registrations"]
    ), "persistent-lane ownership is prohibited"
    assert trace["presentation"]["extra_update_requests"] == int(
        contract["prohibited_extra_update_requests"]
    ), "presentation must not create a second update cadence"


def test_bubble_authored_clock_integrates_every_requested_step():
    cadence = BubbleCadenceState()
    tokens = []

    for index in range(1000):
        cadence.request_step(now_ts=index * 0.01)
        tokens.append(cadence.begin_step())
        cadence.note_step_integrated()

    snapshot = cadence.diagnostic_snapshot()
    assert len(set(tokens)) == 1000
    assert snapshot["requested_steps"] == 1000
    assert snapshot["integrated_steps"] == 1000
    assert snapshot["integration_ratio"] == pytest.approx(1.0)
    assert snapshot["integration_failures"] == 0


def test_bubble_cadence_reports_integration_failure_without_deferral_state():
    cadence = BubbleCadenceState()

    cadence.request_step(now_ts=1.0)
    cadence.begin_step()
    cadence.note_step_failed()

    snapshot = cadence.diagnostic_snapshot()
    assert snapshot["requested_steps"] == 1
    assert snapshot["integrated_steps"] == 0
    assert snapshot["integration_ratio"] == 0.0
    assert snapshot["integration_failures"] == 1


def test_bubble_cadence_reset_invalidates_task_token():
    cadence = BubbleCadenceState()
    cadence.request_step(now_ts=1.0)
    old_token = cadence.begin_step()
    cadence.note_step_integrated()

    cadence.reset()
    cadence.request_step(now_ts=1.01)
    new_token = cadence.begin_step()

    assert old_token[0] != cadence.activation_token
    assert new_token == (cadence.activation_token, 1)


@pytest.mark.qt
def test_bubble_discrete_edge_reaches_first_visible_state_on_next_lane_free_tick(
    qt_app,
    monkeypatch,
):
    """Protect the source edge through latest-state Quick synchronization."""
    from core.settings.visualizer_mode_registry import (
        get_visualizer_presentation_policy,
    )
    from widgets.spotify_visualizer import tick_pipeline
    from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_visualizer_presentation,
    )
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    fixture = _load_temporal_json(_TEMPORAL_FIXTURE)
    golden = _load_temporal_json(_TEMPORAL_GOLDEN)
    clock = SimpleNamespace(now=float(fixture["start_timestamp"]))

    class _Scheduler:
        def __init__(self) -> None:
            self._kick_waiting = False

        def arm_kick(self) -> None:
            self._kick_waiting = True

        def consume_next(self, event_type: str, max_age_s: float = 0.5):
            del max_age_s
            if event_type != "kick" or not self._kick_waiting:
                return None
            self._kick_waiting = False
            return SimpleNamespace(
                strength=float(fixture["kick_strength"]),
                timestamp=clock.now,
            )

    scheduler = _Scheduler()

    class _Engine:
        def tick(self) -> None:
            return None

        def get_bubble_energy_bands(self):
            return SimpleNamespace(**fixture["energy"])

        def get_transient_energy_bands(self):
            return SimpleNamespace(
                bass_transient=0.0,
                mid_transient=0.0,
                high_transient=0.0,
                onset_detected=False,
                onset_type="",
                onset_strength=0.0,
            )

        def get_event_scheduler(self):
            return scheduler

        @staticmethod
        def get_generation_id() -> int:
            return 5

        @staticmethod
        def get_activation_id() -> int:
            return 7

        @staticmethod
        def get_latest_generation_with_frame() -> int:
            return 5

        def get_latest_authoritative_frame(self):
            return clock.now, 5, 7

    class _EdgeSimulation:
        count = 1

        def __init__(self) -> None:
            self.visible_edge = 0.0

        def tick(self, dt, energy, settings) -> None:
            del dt, energy
            event = settings["_event_scheduler"].consume_next("kick", max_age_s=0.3)
            self.visible_edge = 1.0 if event is not None else 0.0

        def snapshot(self, **pulse):
            del pulse
            return [0.0, 0.0, self.visible_edge, 1.0], [0.0] * 4, []

        def get_perf_diagnostics(self):
            return {}

    widget = SpotifyVisualizerWidget(parent=None, bar_count=4, initial_mode="bubble")
    widget._runtime_generation = 0
    widget._enabled = True
    widget._spotify_playing = True
    widget._engine = _Engine()
    controller = widget.runtime_controller
    bubble_runtime = BubbleFrameRuntime(simulation_factory=_EdgeSimulation)
    assert controller.resolve_logical_mode_state(
        "bubble",
        lambda: bubble_runtime,
    ) is bubble_runtime
    controller.begin_render_activation(
        engine_generation=5,
        activation_id=7,
    )
    widget._mode_teardown_block_until_ready = False
    widget._mode_transition_ready = True
    widget._waiting_for_fresh_engine_frame = False
    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("bubble"),
        display_size=(1920.0, 1080.0),
        outer_origin=(100.0, 80.0),
        uniform_visual_scale=1.0,
        viewport_extent=(420.0, 280.0),
        border_width=4.0,
        corner_radius=8.0,
    )

    monkeypatch.setattr(tick_pipeline.time, "time", lambda: clock.now)
    monkeypatch.setattr(tick_pipeline, "consume_engine_bars", lambda owner, now: (True, True))
    monkeypatch.setattr(tick_pipeline, "process_heartbeat", lambda owner, now: None)
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda owner, now: None)
    monkeypatch.setattr(tick_pipeline, "dispatch_devcurve_field", lambda owner, now: None)
    monkeypatch.setattr(widget, "_get_transition_context", lambda parent: {"running": False})
    monkeypatch.setattr(widget, "_pause_timer_during_transition", lambda active: None)
    monkeypatch.setattr(widget, "_resolve_max_fps", lambda context: 100.0)
    monkeypatch.setattr(widget, "_update_timer_interval", lambda fps: None)
    monkeypatch.setattr(widget, "_check_mode_teardown_ready", lambda engine, now: None)

    tick_count = int(fixture["tick_count"])
    tick_interval_s = float(fixture["tick_interval_ms"]) / 1000.0
    kick_tick = int(fixture["kick_authored_tick"])
    visible_edges = [0.0] * tick_count
    consumed_revisions: list[int] = []
    # Deliberately miss the kick tick's GUI and Quick synchronization. The
    # newest unread logical state must coalesce the protected resulting state
    # without creating a replay queue.
    synchronization_ticks = {0, 1, 2, 4, 5}
    for tick_index in range(tick_count):
        clock.now = float(fixture["start_timestamp"]) + tick_index * tick_interval_s
        if tick_index == kick_tick:
            scheduler.arm_kick()
        payload = tick_pipeline.logical_tick(widget)
        assert payload is not None
        if tick_index not in synchronization_ticks:
            continue
        publication = widget._logical_mailbox.take()
        assert publication is not None
        assert publication.state.logical_timestamp == payload.logical_timestamp
        assert controller.publish_render_snapshot(
            publication.state,
            presentation,
            logical_revision=publication.revision,
        )
        snapshot = controller.render_bridge.take_for_render(
            runtime_generation=0,
            engine_generation=5,
            activation_id=7,
            mode_id="bubble",
        )
        assert snapshot is not None
        consumed_revisions.append(snapshot.logical_revision)
        positions = snapshot.logical.mode_state.positions
        if snapshot.logical.protected_edges:
            positions = snapshot.logical.protected_edges[-1].result["positions"]
        visible_edges[tick_index] = float(positions[2]) if positions else 0.0

    cadence = widget._bubble_cadence_state.diagnostic_snapshot()
    visible_tick_indices = [
        index for index, value in enumerate(visible_edges) if value > 0.5
    ]
    visible_tick = visible_tick_indices[0] if visible_tick_indices else -1
    trace = {
        "ticks": [
            {
                "tick": tick_index,
                "kick_authored": tick_index == kick_tick,
                "visible_edge": round(float(visible_edges[tick_index]), 7),
            }
            for tick_index in range(tick_count)
        ],
        "first_visible": {
            "authored_tick": kick_tick,
            "visible_tick": visible_tick,
            "latency_ticks": visible_tick - kick_tick,
            "visible_edge_count": len(visible_tick_indices),
        },
        "executor": {"lane_registrations": 0},
        "presentation": {"extra_update_requests": 0},
    }

    _assert_bubble_temporal_contract(trace, golden)
    assert trace["ticks"] == golden["ticks"]
    assert trace["first_visible"] == golden["first_visible"]
    assert cadence["requested_steps"] == tick_count
    assert cadence["integrated_steps"] == tick_count
    assert cadence["integration_ratio"] == pytest.approx(1.0)
    assert cadence["integration_failures"] == 0
    assert consumed_revisions == sorted(set(consumed_revisions))
    assert bubble_runtime.latest.protected_edges == ()
    widget.deleteLater()


def test_bubble_temporal_golden_rejects_terminal_batching_and_persistent_lane():
    golden = _load_temporal_json(_TEMPORAL_GOLDEN)

    terminal_batch = deepcopy(golden)
    terminal_batch["ticks"][4]["visible_edge"] = 0.0
    terminal_batch["first_visible"].update(
        visible_tick=-1,
        latency_ticks=-4,
        visible_edge_count=0,
    )
    with pytest.raises(AssertionError, match="reach presentation"):
        _assert_bubble_temporal_contract(terminal_batch, golden)

    persistent_lane = deepcopy(golden)
    persistent_lane["executor"]["lane_registrations"] = 1
    with pytest.raises(AssertionError, match="persistent-lane"):
        _assert_bubble_temporal_contract(persistent_lane, golden)
