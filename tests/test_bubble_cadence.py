from __future__ import annotations

from types import SimpleNamespace

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
