"""DisplayManager adapter retirement must detach both visualizer owner authorities."""

from __future__ import annotations

from engine.display_manager import _QuickVisualizerFailoverTopology


class _Owner:
    def __init__(self, *, joins: bool = True) -> None:
        self.is_retired = False
        self.joins = joins
        self.retire_calls = 0

    def retire(self) -> bool:
        self.retire_calls += 1
        if self.joins:
            self.is_retired = True
        return self.is_retired


class _Presenter:
    def __init__(self) -> None:
        self.layout_observer = object()
        self.stack_obstacles = object()

    def set_layout_observer(self, value) -> None:
        self.layout_observer = value

    def set_external_stack_obstacles(self, value) -> None:
        self.stack_obstacles = value


class _Scene:
    def __init__(self) -> None:
        self.double = object()
        self.middle = object()
        self.volume = object()
        self.discard_calls = 0

    def set_visualizer_double_click_admission(self, value) -> None:
        self.double = value

    def set_visualizer_middle_click_admission(self, value) -> None:
        self.middle = value

    def set_visualizer_volume_wheel_handler(self, value) -> None:
        self.volume = value

    def discard_unowned_visualizer_admission(self) -> None:
        self.discard_calls += 1


class _Display:
    def __init__(self, owner: _Owner) -> None:
        self.presenter = _Presenter()
        self.runtime = type("Runtime", (), {"scene_controller": _Scene()})()
        self.visualizer_owner = owner
        self.detach_calls = 0

    def detach_visualizer_owner(self, owner) -> bool:
        assert self.visualizer_owner is owner
        self.detach_calls += 1
        self.visualizer_owner = None
        return True


class _Manager:
    def __init__(self, display: _Display, owner: _Owner) -> None:
        self._quick_visualizer_unit = display
        self._quick_visualizer_owner = owner
        self.disconnect_calls = 0
        self.release_calls = 0

    def _disconnect_quick_visualizer_media_route(self) -> None:
        self.disconnect_calls += 1

    def _release_quick_visualizer_routes(self, display) -> None:
        assert display is self._quick_visualizer_unit
        self.release_calls += 1
        self._quick_visualizer_unit = None
        self._quick_visualizer_owner = None


def test_adapter_retires_before_detaching_manager_and_display_unit_owner():
    owner = _Owner()
    display = _Display(owner)
    manager = _Manager(display, owner)
    topology = _QuickVisualizerFailoverTopology(manager, [display])

    assert topology.cleanup_owner(display) is True
    assert owner.retire_calls == 1
    # Retirement confirmation alone must not strand either authority. The
    # neutral failover lifecycle calls detach_owner only after this succeeds.
    assert manager._quick_visualizer_owner is owner
    assert manager._quick_visualizer_unit is display
    assert display.visualizer_owner is owner

    topology.detach_owner(display)
    assert display.visualizer_owner is None
    assert display.detach_calls == 1
    assert manager._quick_visualizer_owner is None
    assert manager._quick_visualizer_unit is None
    assert manager.release_calls == 1
    assert display.runtime.scene_controller.discard_calls == 1


def test_adapter_keeps_owner_attached_when_logical_retirement_does_not_join():
    owner = _Owner(joins=False)
    display = _Display(owner)
    manager = _Manager(display, owner)
    topology = _QuickVisualizerFailoverTopology(manager, [display])

    assert topology.cleanup_owner(display) is False
    assert owner.retire_calls == 1
    assert manager._quick_visualizer_owner is owner
    assert manager._quick_visualizer_unit is display
    assert display.visualizer_owner is owner
    assert manager.release_calls == 0
    assert display.detach_calls == 0
