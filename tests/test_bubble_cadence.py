from __future__ import annotations

from types import SimpleNamespace
import time

import pytest

from widgets.spotify_visualizer.bubble_cadence import BubbleCadenceState


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

    clock = SimpleNamespace(now=100.0)

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
            return SimpleNamespace(strength=1.0, timestamp=clock.now)

    scheduler = _Scheduler()

    class _Engine:
        def tick(self) -> None:
            return None

        def get_bubble_energy_bands(self):
            return SimpleNamespace(bass=0.1, mid=0.05, high=0.02, overall=0.08)

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
        for tick_index in range(6):
            clock.now = 100.0 + tick_index * 0.010
            if tick_index == 3:
                scheduler.arm_kick()
            tick_pipeline.on_tick(widget)
            deadline = time.monotonic() + 1.0
            while widget._bubble_compute_pending:
                assert time.monotonic() < deadline
                time.sleep(0.001)

        assert visible_edges[3] == 0.0
        assert visible_edges[4] == pytest.approx(1.0)
        assert visible_edges[5] == 0.0
        assert [index for index, value in enumerate(visible_edges) if value > 0.5] == [4]

        cadence = widget._bubble_cadence_state.diagnostic_snapshot()
        assert cadence["offered_ticks"] == 6
        assert cadence["submitted_tasks"] == 6
        assert cadence["publish_ratio"] == pytest.approx(1.0)
        assert cadence["worker_busy_deferrals"] == 0
        assert cadence["result_waiting_deferrals"] == 0
        lane = widget._bubble_compute_lane.diagnostic_snapshot()
        assert lane["executor_task_submissions"] == 0
        assert lane["logical_steps_published"] == 6
    finally:
        widget._stop_bubble_compute_lane()
        thread_manager.shutdown(wait=True, timeout=1.0)
        widget.deleteLater()
