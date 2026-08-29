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
    assert admission.fallback is None
    # Exactly one owner; no other unit is the owner.
    assert admission.is_owner(units[1]) is True
    assert admission.is_owner(units[0]) is False
    assert admission.is_owner(units[2]) is False


def test_requested_present_but_not_participating_holds_on_requested() -> None:
    # Requested screen 2 exists but is not participating yet: hold ownership on
    # it (cautious), do not freelance onto another display.
    units = [_Unit(0, True), _Unit(2, False)]
    admission = resolve_quick_visualizer_admission(2, units)
    assert admission.chosen is units[1]
    assert admission.requested is units[1]
    assert admission.requested_is_participating is False
    assert admission.fallback is units[0]


def test_requested_absent_falls_back_to_first_participating_by_index() -> None:
    # Requested screen 5 is not present at all: fall back to the first
    # participating unit in stable screen-index order.
    units = [_Unit(3, True), _Unit(1, True)]
    admission = resolve_quick_visualizer_admission(5, units)
    assert admission.chosen is units[1]  # screen_index 1 sorts first
    assert admission.requested is None
    assert admission.fallback is units[1]


def test_no_participants_yields_no_owner() -> None:
    units = [_Unit(0, False), _Unit(1, False)]
    admission = resolve_quick_visualizer_admission(0, units)
    # Requested exists (screen 0) though not participating -> held on it.
    assert admission.chosen is units[0]
    assert admission.fallback is None

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
    admission = resolve_quick_visualizer_admission(9, units)
    assert admission.chosen is units[1]
