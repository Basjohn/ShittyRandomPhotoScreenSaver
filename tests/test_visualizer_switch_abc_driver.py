"""State-machine coverage for the opt-in, deterministic A/B/C driver (P4).

Drives the driver through injected fake DM seams and a controllable scheduler, so
the auto-drive logic is validated without a live GL surface. Proves the corrective
contract:

* every condition begins with a verified baseline recreation (A really is Bubble);
* A holds without switching or further recreation;
* B/C perform the EXACT ``Sphere -> Spectrum -> Oscilloscope -> Sine -> Bubble``
  sequence for exactly 5 cycles (25 switches, no DevCurve), each advancing only on
  a genuine completion edge, then settle on Bubble;
* C produces both a pre-recreation and a post-recreation scored window;
* fail-closed: a rejected/incomplete/wrong-mode switch, a disabled required mode, a
  failed/unverified recreation, or a watchdog expiry marks the run INVALID and
  never continues.
"""

from __future__ import annotations

import pytest

from core.performance.visualizer_switch_abc_driver import (
    EXPOSURE_SEQUENCE,
    VisualizerSwitchAbcDriver,
)


class _FakeWorld:
    """A controllable stand-in for the DisplayManager seams + scheduler."""

    def __init__(self) -> None:
        self.generation = 1
        self.mode = "bubble"
        self.enabled = set(EXPOSURE_SEQUENCE)
        self.custom_ok = True
        self.owner_ok = True
        self.load_ok = True
        self.reject_request = False

        self.requested: list[str] = []
        self.load_calls = 0
        self.pending_switch: tuple[str, object] | None = None
        self.recreation_cb = None
        self.recreation_gen_before = None
        self.scheduled: list[tuple[int, str, object]] = []
        self.completed: list[dict] = []

    # -- injected seams --------------------------------------------------------
    def load_layout(self) -> bool:
        self.load_calls += 1
        return self.load_ok

    def active_mode(self):
        return self.mode

    def runtime_generation(self):
        return self.generation

    def request_mode(self, target, on_complete) -> bool:
        if self.reject_request:
            return False
        if target not in self.enabled or target == self.mode:
            return False
        self.requested.append(target)
        self.pending_switch = (target, on_complete)
        return True

    def mode_enabled(self, mode) -> bool:
        return mode in self.enabled

    def custom_baseline_ok(self) -> bool:
        return self.custom_ok

    def owner_healthy(self) -> bool:
        return self.owner_ok

    def watch_recreation(self, generation_before, on_ready) -> None:
        self.recreation_gen_before = generation_before
        self.recreation_cb = on_ready

    def schedule(self, delay_ms, kind, callback) -> None:
        self.scheduled.append((delay_ms, kind, callback))

    def on_complete(self, result) -> None:
        self.completed.append(result)

    # -- test drivers ----------------------------------------------------------
    def fire(self, kind: str) -> bool:
        for index in range(len(self.scheduled) - 1, -1, -1):
            if self.scheduled[index][1] == kind:
                _, _, callback = self.scheduled.pop(index)
                callback()
                return True
        return False

    def complete_recreation(self, new_generation: int) -> None:
        self.generation = new_generation
        self.mode = "bubble"  # the slot restores the intended Bubble baseline
        callback, self.recreation_cb = self.recreation_cb, None
        assert callback is not None, "no recreation observer registered"
        callback(new_generation)

    def complete_switch(self, *, wrong: bool = False) -> None:
        assert self.pending_switch is not None, "no switch in flight"
        target, callback = self.pending_switch
        self.pending_switch = None
        if wrong:
            callback("devcurve")  # a mode that was never requested
            return
        self.mode = target
        callback(target)

    def run_all_switches(self) -> None:
        while self.pending_switch is not None:
            self.complete_switch()

    def advance_hold(self) -> None:
        assert self.fire("exclusion")
        assert self.fire("hold")


def _driver(world: _FakeWorld, condition: str) -> VisualizerSwitchAbcDriver:
    return VisualizerSwitchAbcDriver(
        condition=condition,
        load_layout=world.load_layout,
        active_mode=world.active_mode,
        runtime_generation=world.runtime_generation,
        request_mode=world.request_mode,
        mode_enabled=world.mode_enabled,
        custom_baseline_ok=world.custom_baseline_ok,
        owner_healthy=world.owner_healthy,
        watch_recreation=world.watch_recreation,
        on_complete=world.on_complete,
        schedule=world.schedule,
    )


# --- happy paths ------------------------------------------------------------


def test_condition_a_verifies_baseline_then_holds_without_switching(qt_app):
    world = _FakeWorld()
    driver = _driver(world, "A")
    driver.start()
    assert world.load_calls == 1  # baseline recreation only
    world.complete_recreation(2)
    world.advance_hold()  # steady_A
    assert world.requested == []  # no mode switches at all
    assert world.load_calls == 1  # no further recreation
    assert world.completed == [{"condition": "A", "valid": True, "reason": None}]


def test_condition_b_drives_exact_five_cycles_then_settles_on_bubble(qt_app):
    world = _FakeWorld()
    driver = _driver(world, "B")
    driver.start()
    world.complete_recreation(2)
    world.run_all_switches()
    world.advance_hold()  # steady_B
    # Exactly 25 switches, exact order, DevCurve never touched, settled on Bubble.
    assert world.requested == list(EXPOSURE_SEQUENCE) * 5
    assert len(world.requested) == 25
    assert "devcurve" not in world.requested
    assert world.mode == "bubble"
    assert world.load_calls == 1  # B never recreates the runtime
    assert world.completed == [{"condition": "B", "valid": True, "reason": None}]


def test_condition_c_exposes_holds_recreates_then_holds_again(qt_app):
    world = _FakeWorld()
    driver = _driver(world, "C")
    driver.start()
    world.complete_recreation(2)
    world.run_all_switches()
    world.advance_hold()  # steady_C_pre -> triggers the intervention recreation
    assert world.load_calls == 2  # baseline + one C intervention
    world.complete_recreation(3)  # runtime generation advances again
    world.advance_hold()  # steady_C_post
    assert world.requested == list(EXPOSURE_SEQUENCE) * 5
    assert world.completed == [{"condition": "C", "valid": True, "reason": None}]


# --- fail-closed paths ------------------------------------------------------


def test_layout_slot_load_failure_is_invalid(qt_app):
    world = _FakeWorld()
    world.load_ok = False
    _driver(world, "A").start()
    assert world.completed[0]["valid"] is False
    assert "layout slot load failed" in world.completed[0]["reason"]


def test_recreation_watchdog_expiry_is_invalid(qt_app):
    world = _FakeWorld()
    _driver(world, "A").start()
    # Recreation never becomes ready; the bounded watchdog fires.
    assert world.fire("recreate_watchdog")
    assert world.completed[0]["valid"] is False
    assert "watchdog" in world.completed[0]["reason"]


def test_unchanged_runtime_generation_after_recreation_is_invalid(qt_app):
    world = _FakeWorld()
    _driver(world, "A").start()
    world.complete_recreation(1)  # same as generation_before
    assert world.completed[0]["valid"] is False
    assert "generation did not change" in world.completed[0]["reason"]


def test_missing_custom_baseline_is_invalid(qt_app):
    world = _FakeWorld()
    world.custom_ok = False
    _driver(world, "A").start()
    world.complete_recreation(2)
    assert world.completed[0]["valid"] is False
    assert "CUSTOM" in world.completed[0]["reason"]


def test_bubble_not_restored_after_recreation_is_invalid(qt_app):
    world = _FakeWorld()
    _driver(world, "A").start()
    world.generation = 2
    world.mode = "spectrum"  # recreation did not restore Bubble
    world.recreation_cb(2)
    assert world.completed[0]["valid"] is False
    assert "Bubble not restored" in world.completed[0]["reason"]


def test_disabled_required_mode_is_invalid_without_enabling(qt_app):
    world = _FakeWorld()
    world.enabled = set(EXPOSURE_SEQUENCE) - {"oscilloscope"}
    _driver(world, "B").start()
    world.complete_recreation(2)
    # Preflight rejects before any switch is requested; nothing was enabled.
    assert world.requested == []
    assert world.completed[0]["valid"] is False
    assert "oscilloscope" in world.completed[0]["reason"]
    assert "disabled" in world.completed[0]["reason"]


def test_switch_request_rejection_is_invalid(qt_app):
    world = _FakeWorld()
    world.reject_request = True
    _driver(world, "B").start()
    world.complete_recreation(2)
    assert world.completed[0]["valid"] is False
    assert "request rejected" in world.completed[0]["reason"]


def test_switch_watchdog_expiry_is_invalid(qt_app):
    world = _FakeWorld()
    _driver(world, "B").start()
    world.complete_recreation(2)
    assert world.pending_switch is not None  # first switch requested
    assert world.fire("switch_watchdog")  # never completes
    assert world.completed[0]["valid"] is False
    assert "did not complete" in world.completed[0]["reason"]


def test_wrong_completed_mode_is_invalid(qt_app):
    world = _FakeWorld()
    _driver(world, "B").start()
    world.complete_recreation(2)
    world.complete_switch(wrong=True)  # reports a different mode than requested
    assert world.completed[0]["valid"] is False
    assert "completed mode wrong" in world.completed[0]["reason"]


def test_invalid_condition_is_rejected(qt_app):
    world = _FakeWorld()
    with pytest.raises(ValueError, match="unsupported A/B/C condition"):
        _driver(world, "Z")
