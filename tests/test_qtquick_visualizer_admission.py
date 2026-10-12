"""Single-owner visualizer display admission bars (H Finding D)."""

from __future__ import annotations

from dataclasses import dataclass

from rendering.quick.visualizer_admission import (
    resolve_quick_visualizer_admission,
    resolve_quick_visualizer_owner_unit,
)


@dataclass
class _Unit:
    screen_index: int
    participating: bool


def test_requested_participating_display_wins() -> None:
    units = [_Unit(0, True), _Unit(1, True), _Unit(2, True)]
    admission = resolve_quick_visualizer_admission(1, units)
    assert admission.chosen is units[1]
    assert admission.requested_is_participating is True
    # Exactly one owner; no other unit is the owner.
    assert admission.is_owner(units[1]) is True
    assert admission.is_owner(units[0]) is False
    assert admission.is_owner(units[2]) is False


def test_requested_present_but_not_participating_suppresses_owner() -> None:
    # Binding loss must suppress ownership even when another screen is live.
    units = [_Unit(0, True), _Unit(2, False)]
    admission = resolve_quick_visualizer_admission(2, units)
    assert admission.chosen is None
    assert admission.requested is units[1]
    assert admission.requested_is_participating is False


def test_requested_absent_suppresses_owner() -> None:
    # An absent assignment never floods another screen.
    units = [_Unit(3, True), _Unit(1, True)]
    admission = resolve_quick_visualizer_admission(5, units)
    assert admission.chosen is None
    assert admission.requested is None


def test_no_participants_yields_no_owner() -> None:
    units = [_Unit(0, False), _Unit(1, False)]
    admission = resolve_quick_visualizer_admission(0, units)
    assert admission.chosen is None

    empty = resolve_quick_visualizer_admission(0, [])
    assert empty.chosen is None
    assert empty.has_owner is False


def test_single_owner_across_topology_no_duplicate() -> None:
    # Only the chosen unit is the owner across the whole set.
    units = [_Unit(0, True), _Unit(1, True)]
    owner = resolve_quick_visualizer_owner_unit(0, units)
    assert owner is units[0]
    assert sum(1 for u in units if u is owner) == 1


def test_is_visualizer_participant_callable_supported() -> None:
    class _CallableUnit:
        def __init__(self, idx, live):
            self.screen_index = idx
            self._live = live

        def is_visualizer_participant(self):
            return self._live

    units = [_CallableUnit(0, False), _CallableUnit(1, True)]
    admission = resolve_quick_visualizer_admission(-1, units)
    assert admission.chosen is units[1]


def test_all_chooses_first_participating_by_screen_index() -> None:
    units = [_Unit(3, True), _Unit(0, False), _Unit(1, True)]
    assert resolve_quick_visualizer_owner_unit(-1, units) is units[2]
    assert resolve_quick_visualizer_owner_unit(-1, [_Unit(0, False)]) is None


def test_returning_assigned_display_restores_original_owner_choice() -> None:
    first = _Unit(0, True)
    assigned = _Unit(1, True)
    assert resolve_quick_visualizer_owner_unit(1, [first, assigned]) is assigned
    assert resolve_quick_visualizer_owner_unit(1, [first]) is None
    assigned.participating = False
    assert resolve_quick_visualizer_owner_unit(1, [first, assigned]) is None
    assigned.participating = True
    assert resolve_quick_visualizer_owner_unit(1, [first, assigned]) is assigned
