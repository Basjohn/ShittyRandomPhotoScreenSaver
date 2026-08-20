"""Phase A3 contracts for display-local Qt Quick presentation pacing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Qt

from rendering.quick.frame_pacer import (
    QuickFrameDemand,
    QuickFramePacer,
    QuickPacerState,
)


ROOT = Path(__file__).resolve().parents[1]


class _Signal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback

    def emit(self) -> None:
        assert self.callback is not None
        self.callback()


class _Timer:
    def __init__(self) -> None:
        self.timeout = _Signal()
        self.single_shot = False
        self.timer_type = None
        self.active = False
        self.started_delays: list[int] = []
        self.stop_count = 0

    def setSingleShot(self, value: bool) -> None:
        self.single_shot = bool(value)

    def setTimerType(self, value) -> None:
        self.timer_type = value

    def start(self, delay_ms: int) -> None:
        self.active = True
        self.started_delays.append(int(delay_ms))

    def stop(self) -> None:
        self.active = False
        self.stop_count += 1

    def fire(self) -> None:
        self.active = False
        self.timeout.emit()


class _Window(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.update_count = 0

    def update(self) -> None:
        self.update_count += 1


class _Clock:
    def __init__(self, now_ns: int = 0) -> None:
        self.now_ns = int(now_ns)

    def __call__(self) -> int:
        return self.now_ns


def _pacer(target_hz: float = 100.0):
    window = _Window()
    timer = _Timer()
    clock = _Clock()
    pacer = QuickFramePacer(
        window,
        target_hz,
        clock_ns=clock,
        timer=timer,
    )
    return pacer, window, timer, clock


@pytest.mark.parametrize("rate", (0.0, -1.0, math.inf, -math.inf, math.nan))
def test_target_rate_must_be_finite_and_positive(rate):
    with pytest.raises(ValueError):
        QuickPacerState(rate)


def test_deadline_state_skips_missed_opportunities_without_catch_up_burst():
    state = QuickPacerState(100.0)
    state.start(0)

    first = state.consume(0)
    delayed = state.consume(45_000_000)

    assert first.due_opportunities == 1
    assert delayed.due_opportunities == 4
    assert state.requested_opportunities == 5
    assert state.paced_requests == 2
    assert state.skipped_deadlines == 3
    assert delayed.next_delay_ms == 5


def test_early_callback_waits_without_creating_an_opportunity():
    state = QuickPacerState(60.0)
    state.start(10_000_000)

    decision = state.consume(9_000_000)

    assert decision.due_opportunities == 0
    assert decision.next_delay_ms == 1
    assert state.requested_opportunities == 0
    assert state.paced_requests == 0


def test_timer_is_precise_single_shot_and_idle_until_first_demand():
    pacer, window, timer, _clock = _pacer(165.0)

    assert timer.single_shot is True
    assert timer.timer_type == Qt.TimerType.PreciseTimer
    assert pacer.is_active() is False
    assert timer.started_delays == []
    assert window.update_count == 0

    pacer.set_transition_active(True)

    assert pacer.is_active() is True
    assert window.update_count == 1
    assert timer.started_delays == [7]


def test_transition_and_visualizer_demands_are_independent_and_idempotent():
    pacer, window, timer, _clock = _pacer()

    pacer.set_transition_active(True)
    pacer.set_transition_active(True)
    pacer.set_visualizer_active(True)
    pacer.set_transition_active(False)

    assert pacer.demands == QuickFrameDemand.VISUALIZER
    assert pacer.is_active() is True
    assert window.update_count == 1
    assert timer.stop_count == 0

    pacer.set_visualizer_active(False)

    assert pacer.demands == QuickFrameDemand.NONE
    assert pacer.is_active() is False
    assert timer.stop_count == 1


def test_late_timer_callback_issues_one_fresh_update_and_counts_skips():
    pacer, window, timer, clock = _pacer(100.0)
    pacer.set_visualizer_active(True)

    clock.now_ns = 45_000_000
    timer.fire()

    assert window.update_count == 2
    assert timer.started_delays == [10, 5]
    described = pacer.describe()
    assert described["requested_opportunities"] == 5
    assert described["issued_update_requests"] == 2
    assert described["skipped_deadlines"] == 3


def test_resume_after_idle_starts_now_without_replaying_idle_debt():
    pacer, window, timer, clock = _pacer(60.0)
    pacer.set_transition_active(True)
    pacer.set_transition_active(False)
    skipped_before = pacer.describe()["skipped_deadlines"]

    clock.now_ns = 5_000_000_000
    pacer.set_visualizer_active(True)

    assert window.update_count == 2
    assert pacer.describe()["skipped_deadlines"] == skipped_before
    assert timer.started_delays[-1] == 17


def test_stop_allows_reuse_but_close_rejects_stale_runtime_admission():
    pacer, _window, timer, _clock = _pacer()
    pacer.set_transition_active(True)

    pacer.stop()
    assert pacer.is_active() is False
    assert timer.stop_count == 1

    pacer.set_visualizer_active(True)
    assert pacer.is_active() is True
    pacer.close()
    assert pacer.describe()["closed"] is True

    with pytest.raises(RuntimeError, match="closed"):
        pacer.set_transition_active(True)


def test_refresh_retarget_starts_fresh_without_replaying_old_deadlines():
    pacer, window, _timer, clock = _pacer(60.0)
    pacer.set_transition_active(True)
    clock.now_ns = 4_000_000

    pacer.set_target_hz(120.0)

    assert pacer.target_hz == 120.0
    assert window.update_count == 2
    assert pacer.describe()["skipped_deadlines"] == 0


def test_only_supported_nonzero_demand_bits_are_accepted():
    pacer, _window, _timer, _clock = _pacer()

    with pytest.raises(ValueError, match="unsupported"):
        pacer.set_demand(QuickFrameDemand.NONE, True)
    with pytest.raises(ValueError, match="unsupported"):
        pacer.set_demand(QuickFrameDemand(8), True)


def test_source_has_no_render_completion_loop_or_logical_cadence_owner():
    source = (ROOT / "rendering" / "quick" / "frame_pacer.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "afterRendering",
        "afterFrameEnd",
        "frameSwapped",
        "paint acknowledgement",
        "VisualizerLogicalRuntime",
        "sleep(",
        "processEvents",
    ):
        assert forbidden not in source
