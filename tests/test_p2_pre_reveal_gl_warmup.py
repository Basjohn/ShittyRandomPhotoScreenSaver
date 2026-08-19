"""Deterministic transition GL warmup must complete before the visible fade.

Current_Plan section 4. The previous round moved widget painted-frame
preparation earlier but left the GL ordering untouched, and the installed log
still shows, for both displays:

    fade_completed=True   deferred_gl_warmup_started=False
    ...
    fade_completed=True   deferred_gl_warmup_started=True

`_deferred_warmup_block_reason()` returned `startup_hold` / `first_frame` /
`startup_fade`, so the remaining normal transition programs and resources were
compiled on top of live first-visible motion.

The compositor now takes its own `gl_transition_warmup` startup hold when the
queue is armed, drains it at fade-zero, and releases the hold - which is what
lets the fade start. Real completed work releases readiness; the budget is only
a fail-safe.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from rendering.gl_compositor_pkg import gl_lifecycle
from rendering.gl_compositor_pkg.gl_lifecycle import (
    _GL_TRANSITION_WARMUP_HOLD,
    _acquire_pre_reveal_warmup_hold,
    _deferred_warmup_block_reason,
    _pre_reveal_warmup_active,
    _release_pre_reveal_warmup_hold,
    _warmup_slice_delay_ms,
)


class _Coordinator:
    """The real fade-coordinator hold contract."""

    def __init__(self, state: str = "READY"):
        self.holds: set[str] = set()
        self.state = state
        self.pending: list[str] = []
        self.fades_started = 0

    def add_startup_hold(self, name: str) -> None:
        self.holds.add(name)

    def release_startup_hold(self, name: str) -> None:
        self.holds.discard(name)
        if not self.holds and self.pending:
            self.fades_started += 1

    def describe(self) -> dict:
        return {"startup_holds": sorted(self.holds), "state": self.state}


class _Compositor:
    def __init__(self):
        self._gl_disabled_for_session = False
        self._gl_lifecycle_generation = 1


@pytest.fixture
def rig(monkeypatch):
    coordinator = _Coordinator()
    display = SimpleNamespace(
        _widget_manager=SimpleNamespace(_fade_coordinator=coordinator),
        has_transition_work_pending=lambda: False,
    )
    monkeypatch.setattr(gl_lifecycle, "_live_displays_for_compositor", lambda w: [display])
    monkeypatch.setattr(gl_lifecycle, "_qt_object_is_valid", lambda o: True)
    return _Compositor(), coordinator


class TestTheHoldGatesTheFade:
    def test_arming_warmup_holds_the_startup_fade(self, rig):
        widget, coordinator = rig
        _acquire_pre_reveal_warmup_hold(widget)
        assert _GL_TRANSITION_WARMUP_HOLD in coordinator.holds, (
            "warmup no longer gates the visible fade"
        )

    def test_completion_releases_the_hold(self, rig):
        widget, coordinator = rig
        _acquire_pre_reveal_warmup_hold(widget)
        _release_pre_reveal_warmup_hold(widget, reason="complete")
        assert coordinator.holds == set()

    def test_releasing_the_hold_lets_queued_fades_start(self, rig):
        widget, coordinator = rig
        coordinator.pending.append("clock")
        _acquire_pre_reveal_warmup_hold(widget)
        assert coordinator.fades_started == 0, "the fade started during warmup"
        _release_pre_reveal_warmup_hold(widget, reason="complete")
        assert coordinator.fades_started == 1

    def test_the_hold_is_only_taken_once(self, rig):
        widget, coordinator = rig
        _acquire_pre_reveal_warmup_hold(widget)
        _release_pre_reveal_warmup_hold(widget, reason="complete")
        _acquire_pre_reveal_warmup_hold(widget)
        assert coordinator.holds == set(), (
            "warmup re-held a fade that had already been allowed to start"
        )


class TestTheHoldDoesNotBlockItsOwnWarmup:
    def test_our_own_hold_is_not_a_block_reason(self, rig):
        widget, coordinator = rig
        _acquire_pre_reveal_warmup_hold(widget)
        assert _deferred_warmup_block_reason(widget) is None, (
            "the compositor own pre-reveal hold blocked its own warmup"
        )

    def test_another_startup_hold_still_blocks(self, rig):
        widget, coordinator = rig
        _acquire_pre_reveal_warmup_hold(widget)
        coordinator.holds.add("critical_gl_startup")
        assert _deferred_warmup_block_reason(widget) == "startup_hold"

    def test_first_frame_still_blocks(self, rig):
        widget, coordinator = rig
        coordinator.state = "IDLE"
        assert _deferred_warmup_block_reason(widget) == "first_frame"

    def test_fading_blocks_once_the_pre_reveal_window_is_over(self, rig):
        widget, coordinator = rig
        coordinator.state = "FADING"
        assert _deferred_warmup_block_reason(widget) == "startup_fade"

    def test_fading_does_not_block_inside_the_pre_reveal_window(self, rig):
        """A fade that starts elsewhere must not strand a held warmup."""
        widget, coordinator = rig
        _acquire_pre_reveal_warmup_hold(widget)
        coordinator.state = "FADING"
        assert _deferred_warmup_block_reason(widget) is None

    def test_transition_work_still_blocks(self, rig, monkeypatch):
        widget, coordinator = rig
        display = SimpleNamespace(
            _widget_manager=SimpleNamespace(_fade_coordinator=coordinator),
            has_transition_work_pending=lambda: True,
        )
        monkeypatch.setattr(gl_lifecycle, "_live_displays_for_compositor", lambda w: [display])
        assert _deferred_warmup_block_reason(widget) == "transition_work"


class TestPacing:
    def test_hidden_warmup_drains_without_pacing_delay(self, rig):
        widget, _coordinator = rig
        _acquire_pre_reveal_warmup_hold(widget)
        assert _warmup_slice_delay_ms(widget) == 0, (
            "pre-reveal warmup kept the live pacing delay and cannot finish "
            "before the fade"
        )

    def test_visible_warmup_keeps_the_paced_cadence(self, rig):
        widget, _coordinator = rig
        assert _warmup_slice_delay_ms(widget) == 140


class TestFailSafe:
    def test_an_exhausted_budget_releases_the_fade(self, rig):
        widget, coordinator = rig
        _acquire_pre_reveal_warmup_hold(widget)
        widget._gl_warmup_hold_deadline = 0.0

        assert _pre_reveal_warmup_active(widget) is False
        assert coordinator.holds == set(), (
            "a stalled warmup stranded the startup fade"
        )

    def test_the_budget_is_a_fail_safe_not_the_normal_owner(self):
        assert gl_lifecycle._GL_WARMUP_HOLD_BUDGET_S >= 1.0

    def test_rhi_release_settles_a_held_fade(self, rig):
        widget, coordinator = rig
        _acquire_pre_reveal_warmup_hold(widget)
        _release_pre_reveal_warmup_hold(widget, reason="rhi_release")
        assert coordinator.holds == set()

    def test_no_coordinator_means_no_invented_hold(self, monkeypatch):
        """A hold nothing can release must never be created."""
        monkeypatch.setattr(gl_lifecycle, "_live_displays_for_compositor", lambda w: [])
        widget = _Compositor()

        _acquire_pre_reveal_warmup_hold(widget)

        assert bool(getattr(widget, "_gl_warmup_hold_active", False)) is False
        assert _warmup_slice_delay_ms(widget) == 140


class TestOrderingIsSourceProven:
    def test_arming_the_program_queue_acquires_the_hold(self):
        import inspect

        source = inspect.getsource(gl_lifecycle.schedule_deferred_transition_program_warmup)
        assert "_acquire_pre_reveal_warmup_hold" in source, (
            "the warmup queue is armed without gating the fade"
        )

    def test_every_terminal_resource_path_settles_the_hold(self):
        import inspect

        source = inspect.getsource(gl_lifecycle._schedule_deferred_transition_resource_warmup)
        # Each early return that schedules nothing must settle the hold, or the
        # fade waits on work that will never run.
        assert source.count("_release_pre_reveal_warmup_hold") >= 5
