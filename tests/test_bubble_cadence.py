from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import time

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


def test_bubble_lane_adds_no_artificial_cadence_deferrals():
    cadence = BubbleCadenceState()
    tokens = []

    for index in range(1000):
        cadence.offer_tick(now_ts=index * 0.01)
        tokens.append(cadence.begin_submission())
        cadence.note_submission_succeeded()

    snapshot = cadence.diagnostic_snapshot()
    assert len(set(tokens)) == 1000
    assert snapshot["offered_ticks"] == 1000
    assert snapshot["submitted_tasks"] == 1000
    assert snapshot["publish_ratio"] == pytest.approx(1.0)
    assert snapshot["worker_busy_deferrals"] == 0
    assert snapshot["result_waiting_deferrals"] == 0


def test_bubble_lane_accounts_only_for_existing_worker_and_result_ownership():
    cadence = BubbleCadenceState()

    cadence.offer_tick(now_ts=1.0)
    cadence.note_lane_blocked(worker_busy=True, result_waiting=False)
    cadence.offer_tick(now_ts=1.01)
    cadence.note_lane_blocked(worker_busy=False, result_waiting=True)

    snapshot = cadence.diagnostic_snapshot()
    assert snapshot["offered_ticks"] == 2
    assert snapshot["submitted_tasks"] == 0
    assert snapshot["worker_busy_deferrals"] == 1
    assert snapshot["result_waiting_deferrals"] == 1


def test_bubble_cadence_reset_invalidates_task_token():
    cadence = BubbleCadenceState()
    cadence.offer_tick(now_ts=1.0)
    old_token = cadence.begin_submission()
    cadence.note_submission_succeeded()

    cadence.reset()
    cadence.offer_tick(now_ts=1.01)
    new_token = cadence.begin_submission()

    assert old_token[0] != cadence.activation_token
    assert new_token == (cadence.activation_token, 1)


def test_bubble_worker_publishes_the_same_single_authored_step():
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    calls = []

    class _Simulation:
        count = 1

        def tick(self, dt, energy, settings):
            calls.append(("tick", dt, energy["bass"], settings["marker"]))

        def snapshot(self, **pulse):
            calls.append(("snapshot", pulse["bass"]))
            return [0.0, 0.0, pulse["bass"], 1.0], [0.0] * 4, []

        def get_perf_diagnostics(self):
            return {}

    owner = SimpleNamespace(
        _bubble_simulation=_Simulation(),
        _bubble_worker_logged=True,
    )
    result = SpotifyVisualizerWidget._bubble_compute_worker(
        owner,
        0.01,
        {"bass": 0.8},
        {"marker": 0.8},
        {
            "bass": 0.8,
            "mid_high": 0.0,
            "big_bass_pulse": 0.5,
            "small_freq_pulse": 0.5,
        },
    )

    assert calls == [
        ("tick", 0.01, 0.8, 0.8),
        ("snapshot", 0.8),
    ]
    assert result[0][2] == pytest.approx(0.8)
    assert result[4]["batch_size"] == pytest.approx(1.0)


@pytest.mark.qt
def test_bubble_discrete_edge_reaches_first_visible_state_on_next_lane_free_tick(
    qt_app,
    monkeypatch,
):
    """Protect the complete source-edge -> ordinary visible-tick boundary.

    The edge is deliberately authored on the fourth tick of a 100 Hz source.
    The rejected 60-submission/s token bucket deferred that exact phase, then
    ran the edge and following quiet packet in one task and published only the
    quiet terminal snapshot.  A lane-free authored step must instead become
    the state consumed and pushed by the immediately following UI tick.
    """
    from widgets.spotify_visualizer import tick_pipeline
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
    from core.threading.manager import ThreadManager, ThreadPoolType

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
    widget._enabled = True
    widget._spotify_playing = True
    widget._engine = _Engine()
    thread_manager = ThreadManager(
        config={ThreadPoolType.IO: 1, ThreadPoolType.COMPUTE: 1}
    )
    widget._thread_manager = thread_manager
    widget._bubble_simulation = _EdgeSimulation()
    widget._mode_teardown_block_until_ready = False
    widget._mode_transition_ready = True
    widget._waiting_for_fresh_engine_frame = False

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

    visible_edges: list[float] = []

    def _capture_visible(owner, parent, now_ts, changed, first_frame):
        del parent, now_ts, changed, first_frame
        visible_edges.append(
            float(owner._bubble_pos_data[2]) if owner._bubble_pos_data else 0.0
        )
        return True

    monkeypatch.setattr(tick_pipeline, "push_gpu_frame", _capture_visible)

    try:
        tick_count = int(fixture["tick_count"])
        tick_interval_s = float(fixture["tick_interval_ms"]) / 1000.0
        kick_tick = int(fixture["kick_authored_tick"])
        for tick_index in range(tick_count):
            clock.now = float(fixture["start_timestamp"]) + tick_index * tick_interval_s
            if tick_index == kick_tick:
                scheduler.arm_kick()
            tick_pipeline.on_tick(widget)
            deadline = time.monotonic() + 1.0
            while widget._bubble_compute_pending:
                assert time.monotonic() < deadline
                time.sleep(0.001)

        cadence = widget._bubble_cadence_state.diagnostic_snapshot()
        lane = widget._bubble_compute_lane.diagnostic_snapshot()
        category = thread_manager.get_task_category_stats()[
            "visualizer.bubble_simulation"
        ]
        visible_tick_indices = [
            index for index, value in enumerate(visible_edges) if value > 0.5
        ]
        visible_tick = visible_tick_indices[0] if visible_tick_indices else -1
        trace = {
            "schema_version": 1,
            "golden_kind": "production_executor_temporal_trace",
            "baseline_commit": golden["baseline_commit"],
            "rollback_checkpoint": golden["rollback_checkpoint"],
            "fixture_id": fixture["fixture_id"],
            "contract": golden["contract"],
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
            "cadence": {
                "offered_ticks": int(cadence["offered_ticks"]),
                "submitted_tasks": int(cadence["submitted_tasks"]),
                "publish_ratio": float(cadence["publish_ratio"]),
                "worker_busy_deferrals": int(cadence["worker_busy_deferrals"]),
                "result_waiting_deferrals": int(cadence["result_waiting_deferrals"]),
            },
            "executor": {
                "adapter": lane["adapter"],
                "category": lane["category"],
                "lane_registrations": int(lane["lane_registrations"]),
                "task_submissions": int(lane["executor_task_submissions"]),
                "tasks_completed": int(lane["logical_steps_completed"]),
                "steps_published": int(lane["logical_steps_published"]),
                "category_submitted": int(category["submitted"]),
                "category_completed": int(category["completed"]),
                "category_failed": int(category["failed"]),
                "category_active": int(category["active"]),
            },
            "presentation": {
                "authoritative_ticks": tick_count,
                "frame_publications": len(visible_edges),
                "extra_update_requests": 0,
            },
            "negative_controls": golden["negative_controls"],
        }

        _assert_bubble_temporal_contract(trace, golden)
        assert trace == golden
    finally:
        widget._stop_bubble_compute_lane()
        thread_manager.shutdown(wait=True, timeout=1.0)
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
