from __future__ import annotations

import logging

import pytest

from core.performance.event_loop_recorder import EventLoopStallRecorder


def _prime(recorder: EventLoopStallRecorder, expected_at: float = 10.0) -> None:
    recorder._running = True
    recorder._expected_at = expected_at


def test_event_loop_recorder_measures_lateness_without_catchup(qt_app):
    recorder = EventLoopStallRecorder(parent=qt_app, interval_ms=50)
    _prime(recorder, expected_at=10.05)

    assert recorder.record_tick(10.075) == pytest.approx(25.0)
    assert recorder._expected_at == pytest.approx(10.125)
    assert recorder.record_tick(10.130) == pytest.approx(5.0)

    snapshot = recorder.snapshot()
    assert snapshot.samples == 2
    assert snapshot.max_ms == pytest.approx(25.0)
    assert snapshot.over_25_ms == 0


def test_event_loop_recorder_retention_is_bounded(qt_app):
    recorder = EventLoopStallRecorder(parent=qt_app, interval_ms=50, window_size=32)
    _prime(recorder, expected_at=1.0)

    now = 1.0
    for index in range(100):
        now += 0.050 + index / 100_000.0
        recorder.record_tick(now)

    snapshot = recorder.snapshot()
    assert snapshot.samples == 100
    assert snapshot.retained_samples == 32
    assert recorder._lateness_ms.maxlen == 32


def test_event_loop_summary_is_periodic_not_per_tick(qt_app, caplog):
    recorder = EventLoopStallRecorder(parent=qt_app, interval_ms=50)
    _prime(recorder)
    recorder.record_tick(10.200)

    with caplog.at_level(logging.INFO, logger="core.performance.event_loop_recorder"):
        recorder._emit_summary(outcome="test")

    summaries = [record.message for record in caplog.records if "[EVENT LOOP] summary" in record.message]
    assert len(summaries) == 1
    assert "late_p99_ms=200.00" in summaries[0]
    assert "period_p99_ms=200.00" in summaries[0]
    assert "over_100_ms=1" in summaries[0]
    assert recorder.period_snapshot().retained_samples == 0


def test_scoring_window_reset_clears_pre_window_history_without_restarting_deadline(qt_app):
    recorder = EventLoopStallRecorder(parent=qt_app, interval_ms=50)
    _prime(recorder, expected_at=10.05)
    recorder._last_report_at = 9.0
    recorder.record_tick(10.200)  # 150 ms pre-window stall
    expected_at = recorder._expected_at

    seq = recorder.reset_scoring_window("steady_B")

    assert seq == 1
    assert recorder.snapshot().retained_samples == 0
    assert recorder.period_snapshot().retained_samples == 0
    assert recorder._expected_at == expected_at
    assert recorder._scoring_label == "steady_B"

    recorder.record_tick(expected_at + 0.003)
    assert recorder.snapshot().p99_ms == pytest.approx(3.0)
    assert recorder.period_snapshot().p99_ms == pytest.approx(3.0)


def test_stopped_recorder_is_inert(qt_app):
    recorder = EventLoopStallRecorder(parent=qt_app)
    assert recorder.record_tick(10.0) is None
    assert recorder.snapshot().samples == 0