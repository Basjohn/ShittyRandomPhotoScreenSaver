"""Integrated production admission pin for Visualizer CUSTOM monitor routing."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine import display_manager as display_manager_module
from engine.display_manager import DisplayManager
from rendering.quick.display_unit import QuickDisplayUnit
from rendering.quick.visualizer_failover import get_visualizer_failover_state


def _live_unit(screen_index: int, *, binding_loss=None) -> QuickDisplayUnit:
    """Build a live production-unit shell without depending on CI screen count."""

    return QuickDisplayUnit(
        runtime=SimpleNamespace(
            screen_index=screen_index,
            binding_loss=binding_loss,
        ),
        presenter=SimpleNamespace(),
        ctrl_coordinator=SimpleNamespace(),
        ctrl_key=object(),
    )


def _manager(position: str) -> DisplayManager:
    manager = DisplayManager.__new__(DisplayManager)
    manager._runtime_generation = 805
    manager._quick_visualizer_owner = None
    manager._quick_visualizer_unit = None
    manager._quick_visualizer_failover_token = 0
    manager._quick_visualizer_construct_result = "not_attempted"
    manager._quick_visualizer_construct_reject_reason = None
    manager._quick_visualizer_routing_trace_emitted = False
    manager._widgets_config_snapshot = {
        "family_activation": {"media": True, "visualizers": True},
        "media": {
            "enabled": True,
            "position": "Center",
            "monitor": "1",
        },
        "spotify_visualizer": {
            "enabled": True,
            "visualizers_enabled": True,
            "position": position,
            "monitor": "2",
        },
    }
    return manager


@pytest.mark.parametrize(
    ("position", "expected_screen", "expected_effective_monitor"),
    (("Custom", 1, "2"), ("Center", 0, "1")),
)
def test_two_live_units_keep_custom_route_independent_of_media(
    position: str,
    expected_screen: int,
    expected_effective_monitor: str,
    monkeypatch,
) -> None:
    state = get_visualizer_failover_state()
    state.clear_visualizer_failover()
    manager = _manager(position)
    participants = [_live_unit(0), _live_unit(1)]
    constructed: list[QuickDisplayUnit] = []
    messages: list[str] = []

    def _construct(unit: QuickDisplayUnit) -> bool:
        assert manager._quick_visualizer_owner is None
        constructed.append(unit)
        manager._quick_visualizer_owner = object()
        manager._quick_visualizer_unit = unit
        return True

    manager._construct_quick_visualizer_owner_on = _construct
    monkeypatch.setattr(
        display_manager_module.logger,
        "info",
        lambda message, *args: messages.append(message % args),
    )
    try:
        assert all(unit.is_visualizer_participant() for unit in participants)
        assert manager._admit_quick_visualizer(participants) is True
        assert len(constructed) == 1
        assert constructed[0] is participants[expected_screen]
        assert manager._quick_visualizer_unit is participants[expected_screen]
        assert manager._quick_visualizer_owner is not None
        assert (
            sum(unit is manager._quick_visualizer_unit for unit in participants) == 1
        )
        assert state.get_visualizer_failover() is None

        route_records = [
            message for message in messages if "[VIS_ROUTING]" in message
        ]
        assert len(route_records) == 1
        trace = route_records[0]
        assert "runtime_generation=805" in trace
        assert f"spotify_position='{position}'" in trace
        assert "spotify_monitor='2'" in trace
        assert "media_monitor='1'" in trace
        assert f"custom={position == 'Custom'}" in trace
        assert f"effective_monitor='{expected_effective_monitor}'" in trace
        assert f"requested_screen={expected_screen}" in trace
        assert f"chosen_screen={expected_screen}" in trace
        assert "construct_result=admitted" in trace
        assert "reject_reason=None" in trace
        assert "'screen': 0, 'participating': True, 'binding_loss': None" in trace
        assert "'screen': 1, 'participating': True, 'binding_loss': None" in trace
    finally:
        state.clear_visualizer_failover()


def test_generation_trace_records_preconstruction_reject_reason(monkeypatch) -> None:
    manager = _manager("Center")
    manager._widgets_config_snapshot["spotify_visualizer"] = []
    participants = [_live_unit(0), _live_unit(1)]
    messages: list[str] = []
    monkeypatch.setattr(
        display_manager_module.logger,
        "info",
        lambda message, *args: messages.append(message % args),
    )

    assert manager._admit_quick_visualizer(participants) is False
    # A repeated failed attempt in the same manager generation must not create a
    # noisy second routing record.
    assert manager._admit_quick_visualizer(participants) is False

    route_records = [
        message for message in messages if "[VIS_ROUTING]" in message
    ]
    assert len(route_records) == 1
    assert "construct_result=rejected" in route_records[0]
    assert "reject_reason=invalid_visualizer_section" in route_records[0]


def test_custom_missing_target_records_initial_pending_grace_decision(
    monkeypatch,
) -> None:
    state = get_visualizer_failover_state()
    state.clear_visualizer_failover()
    manager = _manager("Custom")
    participants = [
        _live_unit(0),
        _live_unit(
            1,
            binding_loss=SimpleNamespace(
                as_dict=lambda: {"reason": "test_binding_loss"}
            ),
        ),
    ]
    scheduled: list[tuple[int, dict[str, int]]] = []
    messages: list[str] = []
    manager._construct_quick_visualizer_owner_on = lambda _unit: pytest.fail(
        "pending grace must not construct an immediate fallback"
    )
    manager._schedule_visualizer_failover_deadline = (
        lambda delay_ms, **kwargs: scheduled.append((delay_ms, kwargs))
    )
    monkeypatch.setattr(
        display_manager_module.logger,
        "info",
        lambda message, *args: messages.append(message % args),
    )
    try:
        assert manager._admit_quick_visualizer(participants) is False
        record = state.get_visualizer_failover()
        assert record is not None
        assert record["intended_index"] == 1
        assert record["pending"] is True
        assert len(scheduled) == 1
        delay_ms, schedule_kwargs = scheduled[0]
        assert delay_ms == 30000
        assert schedule_kwargs["target_screen_index"] == 1

        route_records = [
            message for message in messages if "[VIS_ROUTING]" in message
        ]
        assert len(route_records) == 1
        trace = route_records[0]
        assert "requested_screen=1" in trace
        assert "chosen_screen=None" in trace
        assert "construct_result=pending_grace" in trace
        assert "reject_reason=requested_custom_display_not_participating" in trace
        assert "'target': 1, 'pending': True" in trace
        assert "'reason': 'test_binding_loss'" in trace
    finally:
        state.clear_visualizer_failover()


def test_constructor_exception_preserves_canonical_stage_reason(monkeypatch) -> None:
    manager = _manager("Center")
    participants = [_live_unit(0), _live_unit(1)]
    messages: list[str] = []

    def _raise_after_stage_reason(_unit: QuickDisplayUnit) -> bool:
        manager._set_quick_visualizer_construct_outcome(
            "exception",
            "owner_configuration_failed",
        )
        raise RuntimeError("synthetic constructor failure")

    manager._construct_quick_visualizer_owner_on = _raise_after_stage_reason
    monkeypatch.setattr(
        display_manager_module.logger,
        "info",
        lambda message, *args: messages.append(message % args),
    )

    with pytest.raises(RuntimeError, match="synthetic constructor failure"):
        manager._admit_quick_visualizer(participants)

    route_records = [
        message for message in messages if "[VIS_ROUTING]" in message
    ]
    assert len(route_records) == 1
    assert "construct_result=exception" in route_records[0]
    assert "reject_reason=owner_configuration_failed" in route_records[0]
