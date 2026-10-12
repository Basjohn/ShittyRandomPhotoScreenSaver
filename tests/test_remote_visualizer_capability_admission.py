"""Remote CUSTOM admission re-reads capability at the production create boundary."""
from __future__ import annotations

import pytest

from tests.test_visualizer_custom_route_contract import _live_unit, _manager


@pytest.mark.parametrize('family', ['media', 'visualizers'])
def test_final_create_blocked_when_required_capability_deactivated(family):
    manager = _manager('Custom')
    target = _live_unit(1)
    manager._widgets_config_snapshot['family_activation'][family] = False
    assert manager._construct_quick_visualizer_owner_on(target) is False
    assert manager._quick_visualizer_owner is None
    assert target._visualizer_owner is None
    assert manager._quick_visualizer_construct_reject_reason == 'visualizer_capability_not_effective'


def test_final_create_blocks_unresolvable_visualizer_section():
    manager = _manager('Custom')
    manager._widgets_config_snapshot['spotify_visualizer'] = None
    assert manager._construct_quick_visualizer_owner_on(_live_unit(1)) is False
    assert manager._quick_visualizer_construct_reject_reason == 'invalid_visualizer_section'


@pytest.mark.parametrize('family', ['media', 'visualizers'])
def test_capability_changed_between_route_selection_and_create_fails_closed(family):
    manager = _manager('Custom')
    target = _live_unit(1)
    original_construct = manager._construct_quick_visualizer_owner_on
    def construct_after_capability_change(unit):
        manager._widgets_config_snapshot['family_activation'][family] = False
        return original_construct(unit)
    manager._construct_quick_visualizer_owner_on = construct_after_capability_change
    assert manager._admit_quick_visualizer([_live_unit(0), target]) is False
    assert manager._quick_visualizer_owner is None
    assert target._visualizer_owner is None
    assert manager._quick_visualizer_construct_reject_reason == 'visualizer_capability_not_effective'
