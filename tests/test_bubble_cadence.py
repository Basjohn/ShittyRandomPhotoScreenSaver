from __future__ import annotations

from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer.bubble_cadence import BubbleCadenceState


def _packet(
    cadence: BubbleCadenceState,
    sequence_value: float,
    *,
    impulse: bool = False,
):
    return cadence.next_packet(
        dt=0.01,
        energy={
            "bass": sequence_value,
            "mid": 0.0,
            "high": 0.0,
            "overall": sequence_value,
            "crest": 1.0 if impulse else 0.0,
        },
        settings={"marker": sequence_value},
        pulse={
            "bass": sequence_value,
            "mid_high": 0.0,
            "big_bass_pulse": 0.5,
            "small_freq_pulse": 0.5,
        },
        has_discrete_impulse=impulse,
    )


def test_bubble_cadence_caps_worker_tasks_and_preserves_logical_packet_order():
    cadence = BubbleCadenceState(submissions_hz=60.0, max_batch_size=2)
    submitted = []

    for index in range(1000):
        now_ts = index * 0.01
        cadence.offer(_packet(cadence, float(index)), now_ts=now_ts)
        ready = cadence.take_ready(worker_busy=False, result_waiting=False)
        if ready is not None:
            _token, batch = ready
            submitted.append(batch)

    assert len(submitted) <= 601
    assert max(len(batch) for batch in submitted) <= 2
    flattened = [packet for batch in submitted for packet in batch]
    assert [packet.sequence for packet in flattened] == list(
        range(1, len(flattened) + 1)
    )
    assert len(flattened) >= 999


def test_bubble_cadence_overflow_preserves_impulse_peak_and_elapsed_time():
    cadence = BubbleCadenceState(submissions_hz=60.0, max_batch_size=2)
    cadence.offer(_packet(cadence, 0.1), now_ts=1.0)
    cadence.offer(_packet(cadence, 0.9, impulse=True), now_ts=1.001)
    cadence.offer(_packet(cadence, 0.2), now_ts=1.002)

    _token, batch = cadence.take_ready(worker_busy=False, result_waiting=False)

    assert len(batch) == 2
    assert batch[-1].has_discrete_impulse is True
    assert batch[-1].energy["bass"] == pytest.approx(0.9)
    assert batch[-1].energy["crest"] == pytest.approx(1.0)
    assert batch[-1].dt == pytest.approx(0.02)
    assert cadence.coalesced_packets == 1


def test_bubble_cadence_reset_invalidates_task_token_and_clears_queue():
    cadence = BubbleCadenceState(submissions_hz=60.0, max_batch_size=2)
    cadence.offer(_packet(cadence, 0.1), now_ts=1.0)
    old_token, _batch = cadence.take_ready(
        worker_busy=False,
        result_waiting=False,
    )

    cadence.offer(_packet(cadence, 0.2), now_ts=1.01)
    cadence.reset()
    snapshot = cadence.diagnostic_snapshot()

    assert old_token[0] != cadence.activation_token
    assert snapshot["pending_packets"] == 0


@pytest.mark.qt
def test_bubble_worker_batches_each_tick_and_snapshot_in_order(qt_app, monkeypatch):
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    widget = SpotifyVisualizerWidget(parent=None, bar_count=4)
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

    widget._bubble_simulation = _Simulation()
    cadence = BubbleCadenceState(submissions_hz=60.0, max_batch_size=2)
    second = _packet(cadence, 0.8)

    result = widget._bubble_compute_worker(
        0.01,
        {"bass": 0.2},
        {"marker": 0.2},
        {
            "bass": 0.2,
            "mid_high": 0.0,
            "big_bass_pulse": 0.5,
            "small_freq_pulse": 0.5,
        },
        (second,),
    )

    assert calls == [
        ("tick", 0.01, 0.2, 0.2),
        ("snapshot", 0.2),
        ("tick", 0.01, 0.8, 0.8),
        ("snapshot", 0.8),
    ]
    assert result[0][2] == pytest.approx(0.8)
    assert result[4]["batch_size"] == pytest.approx(2.0)
