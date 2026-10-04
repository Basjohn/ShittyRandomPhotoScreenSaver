"""The --frame-trace GUI stall sampler (Current_Plan N1e): names what the GUI thread was doing when Visualizer
GUI wakes stalled, does nothing at rest, and is owned by the trace admission."""
from __future__ import annotations

import time

from core.performance import frame_trace
from core.performance.gui_stall_sampler import GuiStallSampler


def _stalling_gui_work(seconds: float) -> None:
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:      # pure Python on the "GUI" (test) thread
        sum(range(200))


def test_a_stall_records_the_gui_threads_stack_once_and_its_length(tmp_path):
    sampler = GuiStallSampler(tmp_path / "stalls.log", threshold_s=0.08)
    try:
        for _ in range(5):
            sampler.note_wake()
            time.sleep(0.005)
        sampler.note_wake()
        _stalling_gui_work(0.3)
        sampler.note_wake()
        time.sleep(0.05)
    finally:
        sampler.close()
    text = (tmp_path / "stalls.log").read_text(encoding="utf-8")
    assert sampler.stalls == 1
    assert text.count("=== gui_stall") == 1
    assert "--- thread GUI" in text and "_stalling_gui_work" in text
    assert "stall_end total_ms=" in text


def test_nothing_happens_before_the_first_wake_or_after_wakes_stop(tmp_path):
    sampler = GuiStallSampler(tmp_path / "stalls.log", threshold_s=0.02, idle_s=0.1)
    try:
        time.sleep(0.1)                         # never woken: no sampling at rest
        assert sampler.stalls == 0
        sampler.note_wake()
        time.sleep(0.3)                         # wakes stop: one stall, then idle (no repeats)
        stalls_after_idle = sampler.stalls
        time.sleep(0.2)
        assert sampler.stalls == stalls_after_idle == 1
    finally:
        sampler.close()
    assert "wakes stopped" in (tmp_path / "stalls.log").read_text(encoding="utf-8")


def test_the_sampler_exists_only_with_the_trace_admission(tmp_path):
    assert frame_trace.start_frame_trace(tmp_path, ["app"]) is None
    assert frame_trace.current_gui_stall_sampler() is None
    sink = frame_trace.start_frame_trace(tmp_path, ["app", "--frame-trace"])
    try:
        assert sink is not None
        sampler = frame_trace.current_gui_stall_sampler()
        assert sampler is not None and sampler.path.parent == tmp_path
    finally:
        frame_trace.close_frame_trace()
    assert frame_trace.current_gui_stall_sampler() is None
    assert not sampler._thread.is_alive()
