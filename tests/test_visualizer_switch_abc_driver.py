"""State-machine coverage for the opt-in A/B/C visualizer-switch driver (P4).

Drives the driver's tick state machine with injected fake DM seams and a
controllable clock, so the auto-drive logic is validated without a live GL
surface. Proves: A holds without switching/recreation; B performs the switch
exposure and settles on Bubble with no recreation; C performs the same exposure,
then recreates through the real load-layout seam (runtime generation changes),
then holds again; and every condition completes and fires on_complete.
"""

from __future__ import annotations

import pytest

from core.performance import visualizer_switch_abc_driver as drv_mod
from core.performance.visualizer_switch_abc_driver import (
    VisualizerSwitchAbcDriver,
    _Phase,
)


class _Clock:
    def __init__(self) -> None:
        self.mono = 0.0
        self.wall = 1000.0

    def monotonic(self) -> float:
        return self.mono

    def time(self) -> float:
        return self.wall

    def advance(self, dt: float) -> None:
        self.mono += dt
        self.wall += dt


_MODES = ("bubble", "spectrum", "oscilloscope", "sine_wave", "devcurve", "sphere")


def _make(condition, monkeypatch, *, cycles=2):
    clock = _Clock()
    monkeypatch.setattr(drv_mod.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(drv_mod.time, "time", clock.time)
    state = {
        "idx": 0,
        "cycle_calls": 0,
        "layout_calls": 0,
        "generation": 1,
        "completed": 0,
    }

    def cycle_mode() -> None:
        state["cycle_calls"] += 1
        state["idx"] = (state["idx"] + 1) % len(_MODES)

    def active_mode():
        return _MODES[state["idx"]]

    def load_layout() -> bool:
        state["layout_calls"] += 1
        state["generation"] += 1  # real recreation changes the runtime generation
        state["idx"] = 0  # restored intended Bubble configuration
        return True

    def runtime_generation():
        return state["generation"]

    def on_complete() -> None:
        state["completed"] += 1

    driver = VisualizerSwitchAbcDriver(
        condition=condition,
        cycle_mode=cycle_mode,
        active_mode=active_mode,
        load_layout=load_layout,
        runtime_generation=runtime_generation,
        on_complete=on_complete,
        settle_mode="bubble",
        cycles=cycles,
        exclude_seconds=1.0,
        hold_seconds=5.0,
        poll_ms=50,
    )
    return driver, state, clock


def _drive(driver, clock, *, max_ticks=5000) -> bool:
    for _ in range(max_ticks):
        if driver._phase is _Phase.DONE:
            return True
        driver._tick()
        clock.advance(0.5)  # elapse the exclude/hold windows over successive ticks
    return False


def test_condition_a_holds_without_switching_or_recreation(qt_app, monkeypatch):
    driver, state, clock = _make("A", monkeypatch)
    assert _drive(driver, clock)
    assert state["cycle_calls"] == 0
    assert state["layout_calls"] == 0
    assert state["completed"] == 1


def test_condition_b_switch_exposure_settles_on_bubble_without_recreation(
    qt_app, monkeypatch
):
    driver, state, clock = _make("B", monkeypatch)
    assert _drive(driver, clock)
    # cycles(2) * estimated modes(6) exposure switches, then settle to bubble.
    assert state["cycle_calls"] >= 12
    assert state["layout_calls"] == 0
    assert _MODES[state["idx"]] == "bubble"
    assert state["completed"] == 1


def test_condition_c_exposes_then_recreates_through_real_load_layout(
    qt_app, monkeypatch
):
    driver, state, clock = _make("C", monkeypatch)
    generation_before = state["generation"]
    assert _drive(driver, clock)
    assert state["cycle_calls"] >= 12
    assert state["layout_calls"] == 1  # exactly one recreation intervention
    assert state["generation"] != generation_before  # runtime generation changed
    assert _MODES[state["idx"]] == "bubble"
    assert state["completed"] == 1


def test_invalid_condition_is_rejected(qt_app):
    with pytest.raises(ValueError, match="unsupported A/B/C condition"):
        VisualizerSwitchAbcDriver(
            condition="Z",
            cycle_mode=lambda: None,
            active_mode=lambda: "bubble",
            load_layout=lambda: True,
            runtime_generation=lambda: 1,
        )
