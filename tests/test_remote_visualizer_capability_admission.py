"""Remote CUSTOM visualizer capability admission, incl. delayed callback (E2 §2).

Re-homed onto the presentation-neutral Quick failover lifecycle after the legacy
physical-host owner was deleted. These cross the ACTUAL create boundary / delayed
fallback-recheck / immediate reconcile seams and prove a stale/delayed callback
cannot create a Visualizer after Media or Visualizers was deactivated, because
current canonical capability state is re-read at the create boundary and fails
closed.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import rendering.quick.visualizer_failover_lifecycle as fol
from rendering.quick.visualizer_failover import get_visualizer_failover_state


ACTIVE = {"family_activation": {"media": True, "visualizers": True}}
VIS_OFF = {"family_activation": {"media": True, "visualizers": False}}
MEDIA_OFF = {"family_activation": {"media": False, "visualizers": True}}


class _Display:
    def __init__(self, screen_index=1):
        self.screen_index = screen_index
        self.owner = None
        self.create_calls = 0


class _Topology:
    """Deterministic fake adapter; ``widgets`` drives live capability + routing."""

    def __init__(self, widgets, *, target=None, participating=True, configured_index=1):
        self.widgets = widgets            # None models an unresolvable settings state
        self.target = target
        self.participating = participating
        self.configured_index = configured_index
        self.custom = True
        self._token = 0
        self.scheduled: list = []

    def capability_admitted(self) -> bool:
        from core.settings.capability_activation import is_widget_family_effective

        if not isinstance(self.widgets, dict):
            return False                  # unresolvable -> fail closed
        try:
            return bool(is_widget_family_effective(self.widgets, "visualizers"))
        except Exception:
            return False

    def live_widgets(self):
        return self.widgets

    def is_custom_selected(self, widgets) -> bool:
        return bool(self.custom)

    def effective_monitor_index(self, widgets):
        return self.configured_index

    def resolve(self, intended_index):
        return SimpleNamespace(
            requested_display=self.target,
            requested_is_participating=self.participating,
            fallback_display=self.target if self.participating else None,
        )

    def owner_present_on(self, display) -> bool:
        return display is not None and getattr(display, "owner", None) is not None

    def screen_index_of(self, display):
        return getattr(display, "screen_index", None)

    def create_owner(self, display, intended_index) -> bool:
        display.create_calls += 1
        display.owner = object()
        return True

    def cleanup_owner(self, display) -> bool:
        return True

    def detach_owner(self, display) -> None:
        display.owner = None

    def current_token(self) -> int:
        return self._token

    def bump_token(self) -> int:
        self._token += 1
        return self._token

    def schedule(self, delay_ms, *, target_screen_index, token, generation) -> None:
        self.scheduled.append((target_screen_index, token, generation))


@pytest.fixture(autouse=True)
def _isolate():
    get_visualizer_failover_state().clear_visualizer_failover()
    yield
    get_visualizer_failover_state().clear_visualizer_failover()


# --- Final creation boundary ------------------------------------------------


def test_final_create_blocked_when_visualizers_deactivated():
    target = _Display()
    topo = _Topology(VIS_OFF, target=target)
    assert fol.create_visualizer_owner_on_target(topo, target, 1) is False
    assert target.create_calls == 0


def test_final_create_blocked_when_media_deactivated():
    target = _Display()
    topo = _Topology(MEDIA_OFF, target=target)
    assert fol.create_visualizer_owner_on_target(topo, target, 1) is False
    assert target.create_calls == 0


def test_final_create_blocked_when_capability_unresolvable():
    # Cannot resolve current capability state -> fail closed.
    target = _Display()
    topo = _Topology(None, target=target)
    assert fol.create_visualizer_owner_on_target(topo, target, 1) is False
    assert target.create_calls == 0


def test_final_create_allowed_when_active():
    target = _Display()
    topo = _Topology(ACTIVE, target=target)
    assert fol.create_visualizer_owner_on_target(topo, target, 1) is True
    assert target.create_calls == 1


# --- Delayed fallback recheck (the formerly broken path) --------------------


def _run_delayed(widgets_at_deadline, target):
    # Arm a grace so the recheck's global generation check is satisfied; the
    # capability outcome is what these tests isolate. The recheck re-reads live
    # capability/routing, so the deadline widgets are what decide the outcome.
    state = get_visualizer_failover_state()
    generation = state.arm_visualizer_grace(intended_index=1, origin_manager=None)
    topo = _Topology(widgets_at_deadline, target=target, participating=True, configured_index=1)
    fol.run_fallback_recheck(
        topo, target_screen_index=1, token=topo.current_token(), generation=generation,
    )


def test_delayed_recheck_no_create_when_visualizers_deactivated():
    target = _Display()
    _run_delayed(VIS_OFF, target)
    assert target.create_calls == 0


def test_delayed_recheck_no_create_when_media_deactivated():
    target = _Display()
    _run_delayed(MEDIA_OFF, target)
    assert target.create_calls == 0


def test_delayed_recheck_creates_when_still_active():
    target = _Display()
    _run_delayed(ACTIVE, target)
    assert target.create_calls == 1


# --- Immediate reconcile ----------------------------------------------------


def test_immediate_reconcile_no_create_or_schedule_when_capability_inactive():
    # Immediate reconcile with capability inactive -> neither creates nor
    # schedules a delayed recheck.
    target = _Display()
    topo = _Topology(VIS_OFF, target=target, participating=False, configured_index=1)
    fol.reconcile_custom_visualizer(topo)
    assert target.create_calls == 0
    assert topo.scheduled == []
