"""Opt-in GUI stall stacks: separately admitted and silent in lifecycle windows."""
from __future__ import annotations

import time

from core.performance import frame_trace
from core.performance.gui_stall_sampler import GuiStallSampler


def _stalling_gui_work(seconds: float) -> None:
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        sum(range(200))


def test_a_stall_records_the_gui_threads_stack_once_and_its_length(tmp_path):
    sampler = GuiStallSampler(
        tmp_path / "stalls.log",
        threshold_s=0.08,
        suppress_predicate=lambda: False,
    )
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
    sampler = GuiStallSampler(
        tmp_path / "stalls.log",
        threshold_s=0.02,
        idle_s=0.1,
        suppress_predicate=lambda: False,
    )
    try:
        time.sleep(0.1)
        assert sampler.stalls == 0
        sampler.note_wake()
        time.sleep(0.3)
        stalls_after_idle = sampler.stalls
        time.sleep(0.2)
        assert sampler.stalls == stalls_after_idle == 1
    finally:
        sampler.close()
    assert "wakes stopped" in (tmp_path / "stalls.log").read_text(encoding="utf-8")


def test_lifecycle_suppression_disarms_without_stack_capture_and_rearms(tmp_path):
    suppressed = True

    def _suppressed() -> bool:
        return suppressed

    sampler = GuiStallSampler(
        tmp_path / "stalls.log",
        threshold_s=0.03,
        idle_s=0.2,
        suppress_predicate=_suppressed,
    )
    try:
        sampler.note_wake()
        time.sleep(0.12)
        assert sampler.stalls == 0
        assert not (tmp_path / "stalls.log").exists()

        suppressed = False
        sampler.note_wake()
        time.sleep(0.08)
        sampler.note_wake()
        time.sleep(0.02)
    finally:
        sampler.close()

    text = (tmp_path / "stalls.log").read_text(encoding="utf-8")
    assert sampler.stalls == 1
    assert text.count("=== gui_stall") == 1



def test_default_suppression_tracks_binding_lifecycle_window(tmp_path):
    from core.diagnostics import lifecycle_window

    lifecycle_window.close_window()
    sampler = GuiStallSampler(tmp_path / "stalls.log", threshold_s=0.03, idle_s=0.2)
    try:
        lifecycle_window.open_window("test_startup")
        sampler.note_wake()
        time.sleep(0.10)
        assert sampler.stalls == 0
        assert not (tmp_path / "stalls.log").exists()

        lifecycle_window.close_window()
        sampler.note_wake()
        time.sleep(0.08)
        sampler.note_wake()
        time.sleep(0.02)
    finally:
        lifecycle_window.close_window()
        sampler.close()

    assert sampler.stalls == 1
    assert "=== gui_stall" in (tmp_path / "stalls.log").read_text(encoding="utf-8")

def test_binary_frame_trace_does_not_implicitly_admit_heavy_stack_sampler(tmp_path):
    assert frame_trace.start_frame_trace(tmp_path, ["app"]) is None
    assert frame_trace.current_gui_stall_sampler() is None

    sink = frame_trace.start_frame_trace(tmp_path, ["app", "--frame-trace"])
    try:
        assert sink is not None
        assert frame_trace.current_gui_stall_sampler() is None
    finally:
        frame_trace.close_frame_trace()

    assert frame_trace.current_gui_stall_sampler() is None


def test_stack_sampler_requires_its_own_explicit_admission(tmp_path):
    assert frame_trace.gui_stall_stacks_requested(["--frame-trace"]) is False
    assert frame_trace.gui_stall_stacks_requested(["--frame-trace", "--gui-stall-stacks"]) is True

    sink = frame_trace.start_frame_trace(
        tmp_path,
        ["app", "--frame-trace", "--gui-stall-stacks"],
    )
    try:
        assert sink is not None
        sampler = frame_trace.current_gui_stall_sampler()
        assert sampler is not None and sampler.path.parent == tmp_path
    finally:
        frame_trace.close_frame_trace()

    assert frame_trace.current_gui_stall_sampler() is None
    assert not sampler._thread.is_alive()


def test_main_filters_stack_sampler_flag_from_screensaver_mode_parsing():
    from pathlib import Path

    main = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    assert '"--gui-stall-stacks"' in main
    filtered_block = main.split("_filtered = {", 1)[1].split("}", 1)[0]
    assert '"--gui-stall-stacks"' in filtered_block
