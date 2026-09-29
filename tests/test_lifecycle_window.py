"""Startup and teardown are lifecycle windows, not stall points (operator rule 2026-09-29).

Spike and stall diagnostics neither warn nor count inside a window; frames after the
coordinated reveal count again, so startup cost that bleeds past it is still caught.
"""
from __future__ import annotations

import logging
import struct
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.diagnostics import lifecycle_window
from core.performance.frame_trace import FrameTraceEvent


@pytest.fixture(autouse=True)
def _closed_window():
    lifecycle_window.close_window()
    yield
    lifecycle_window.close_window()


def test_the_window_opens_once_closes_once_and_marks_the_frame_trace(monkeypatch):
    import core.diagnostics.lifecycle_window as module

    recorded = []
    monkeypatch.setattr(module, "current_frame_trace",
                        lambda: SimpleNamespace(record=lambda event: recorded.append(event)))
    assert not lifecycle_window.is_open()
    lifecycle_window.open_window("settings")
    lifecycle_window.open_window("teardown:settings")            # already open: first reason kept
    assert lifecycle_window.is_open() and lifecycle_window.reason() == "settings"
    lifecycle_window.close_window()
    lifecycle_window.close_window()
    assert not lifecycle_window.is_open()
    assert recorded == [FrameTraceEvent.LIFECYCLE_BEGIN, FrameTraceEvent.LIFECYCLE_END]


def test_every_display_teardown_opens_the_window_before_anything_is_torn_down():
    from engine.engine_lifecycle import teardown_display_runtime

    seen = []
    manager = SimpleNamespace(
        _runtime_generation=4,
        get_display_count=lambda: 2,
        quiesce_all=lambda: seen.append(("quiesce", lifecycle_window.is_open())),
        cleanup=lambda: seen.append(("cleanup", lifecycle_window.is_open())),
    )
    engine = SimpleNamespace(display_manager=manager, thread_manager=None, _runtime_generation=4)
    teardown_display_runtime(engine, reason="settings")
    assert seen == [("quiesce", True), ("cleanup", True)]
    assert lifecycle_window.reason() == "teardown:settings"


def test_the_coordinated_reveal_closes_the_window(monkeypatch):
    import core.logging.logger as logger_module
    import core.performance.resource_metrics as resource_metrics
    from engine.screensaver_engine import ScreensaverEngine

    monkeypatch.setattr(resource_metrics, "log_lifecycle_resource_snapshot", lambda *a, **k: None)
    monkeypatch.setattr(logger_module, "is_perf_metrics_enabled", lambda: False)
    monkeypatch.setattr(logger_module, "is_lifecycle_logging_enabled", lambda: False)
    current = [False]
    engine = SimpleNamespace(
        _is_runtime_identity_current=lambda generation, manager: current[0],
        _record_stale_runtime_callback=lambda *args: None,
        _end_replacement_watchdog=lambda reason: None,
        _runtime_lifecycle_event="settings",
        _prepare_next_transition=lambda: None,
    )
    lifecycle_window.open_window("settings")
    ScreensaverEngine._on_startup_reveal_completed(engine, 5, object(), 5)
    assert lifecycle_window.is_open()                              # a retired generation's reveal: no
    current[0] = True
    ScreensaverEngine._on_startup_reveal_completed(engine, 5, object(), 5)
    assert not lifecycle_window.is_open()


def test_the_event_loop_recorder_does_not_count_lifecycle_stalls(qt_app):
    from core.performance.event_loop_recorder import EventLoopStallRecorder

    recorder = EventLoopStallRecorder(parent=qt_app, interval_ms=50)
    recorder._running, recorder._expected_at = True, 10.0
    lifecycle_window.open_window("settings")
    assert recorder.record_tick(10.80) is None                     # an 800 ms Settings stall
    assert recorder._expected_at == pytest.approx(10.85)
    lifecycle_window.close_window()
    assert recorder.record_tick(10.95) == pytest.approx(100.0)     # after the reveal it counts
    snapshot = recorder.snapshot()
    assert snapshot.samples == 1 and snapshot.max_ms == pytest.approx(100.0)


def test_visualizer_latency_is_not_a_finding_during_startup_or_teardown(monkeypatch, caplog):
    import widgets.spotify_visualizer.tick_pipeline as tick_pipeline
    from tests.test_tick_pipeline_latency import _make_engine, _make_widget

    monkeypatch.setattr(tick_pipeline, "is_viz_logging_enabled", lambda: True)
    epoch = 10_000.0
    engine = _make_engine(source_ts=epoch + 1.0, playback_epoch_ts=epoch)
    with caplog.at_level(logging.DEBUG, logger="widgets.spotify_visualizer.tick_pipeline"):
        lifecycle_window.open_window("teardown:settings")
        tick_pipeline.log_audio_latency_metrics(_make_widget(), engine, now_ts=epoch + 1.5)
        assert not [r for r in caplog.records if "[SPOTIFY_VIS][LATENCY]" in r.message]
        lifecycle_window.close_window()
        tick_pipeline.log_audio_latency_metrics(_make_widget(), engine, now_ts=epoch + 1.5)
    assert [r for r in caplog.records if "[SPOTIFY_VIS][LATENCY]" in r.message and r.levelno == logging.WARNING]


def test_visualizer_slow_ticks_are_not_spikes_during_startup_or_teardown(monkeypatch):
    from tests.test_visualizer_tick_phase_diagnostics import _slow_tick

    lifecycle_window.open_window("cold_start")
    warnings, _recorders = _slow_tick(monkeypatch, perf=True)
    assert not [w for w in warnings if "[SPOTIFY_VIS]" in w]
    lifecycle_window.close_window()
    warnings, _recorders = _slow_tick(monkeypatch, perf=True)
    assert [w for w in warnings if w.startswith("[PERF] [SPOTIFY_VIS] Slow _on_tick: ")]


def test_the_trace_report_keeps_lifecycle_frames_apart_and_checks_the_frames_after(tmp_path: Path):
    header, record = struct.Struct("<8sHHI"), struct.Struct("<QHhqqq")
    ms = 1_000_000
    rows = [(0, 62, -1, -1, 0, 0)]                                  # cold start
    t = 0
    for gap in [10] * 5 + [300] + [10] * 5:                          # a 300 ms startup frame
        t += gap
        rows.append((t * ms, 6, 1, len(rows), 0, 1))
    rows.append(((t + 5) * ms, 63, -1, -1, 0, 0))                    # reveal complete
    for gap in [10, 40] + [10] * 300 + [60] + [10] * 5:              # 40 ms just after (poison), 60 ms later
        t += gap
        rows.append((t * ms, 6, 1, len(rows), 0, 1))
    trace = tmp_path / "trace.bin"
    payload = bytearray(header.pack(b"SRPSSFT1", 1, record.size, 4096))
    for row in rows:
        payload.extend(record.pack(*row))
    trace.write_bytes(payload)
    out = subprocess.run([sys.executable, "tools/frame_trace_report.py", str(trace)],
                         cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True,
                         check=True).stdout
    assert "lifecycle_windows=1 " in out
    steady = next(line for line in out.splitlines() if line.startswith("screen=1 steady_swap_spacing_ms"))
    assert "over_25=2 over_50=1 over_100=0" in steady                 # the 300 ms startup frame is not in it
    poison = next(line for line in out.splitlines() if line.startswith("screen=1 post_lifecycle_2s"))
    assert "late_over_25=1 " in poison and "max_ms=40.000" in poison
