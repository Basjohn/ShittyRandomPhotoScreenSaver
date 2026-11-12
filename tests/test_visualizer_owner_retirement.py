"""DisplayManager CUSTOM Edit retirement must detach both visualizer owner authorities."""

from __future__ import annotations

from engine.display_manager import DisplayManager
from tests._display_manager_doubles import bare_display_manager


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


# _Owner, _Presenter, _Scene and _Display stay hand-built on purpose: they count retire/detach/discard calls and
# model an owner whose retirement does not join, which the shared read-surface doubles do not.
def _Manager(display: _Display, owner: _Owner):
    manager = bare_display_manager(
        _retired=False, _quick_visualizer_unit=display, _quick_visualizer_owner=owner,
        _quick_scene_view_gesture=object(), _quick_view_pose_owner=object(),
        disconnect_calls=0, release_calls=0,
        _refresh_all_quick_context_menus=lambda: None,
        _publish_quick_view_orbit_admission=lambda: None,
    )

    def _disconnect_quick_visualizer_media_route() -> None:
        manager.disconnect_calls += 1

    def _persist_quick_visualizer_view() -> None:
        # Route release saves a held orbit exactly once, while still admitted.
        assert manager._quick_visualizer_owner is not None
        manager.release_calls += 1

    manager._disconnect_quick_visualizer_media_route = _disconnect_quick_visualizer_media_route
    manager._persist_quick_visualizer_view = _persist_quick_visualizer_view
    return manager


def test_edit_disable_retires_and_detaches_both_owner_authorities():
    owner = _Owner()
    display = _Display(owner)
    manager = _Manager(display, owner)
    assert DisplayManager._commit_quick_visualizer_presence(manager, False) is True
    assert owner.retire_calls == 1
    assert display.visualizer_owner is None
    assert display.detach_calls == 1
    assert manager._quick_visualizer_owner is None
    assert manager._quick_visualizer_unit is None
    assert manager.release_calls == 1
    assert display.runtime.scene_controller.discard_calls == 1


def test_edit_disable_keeps_owner_attached_when_logical_retirement_does_not_join():
    owner = _Owner(joins=False)
    display = _Display(owner)
    manager = _Manager(display, owner)
    assert DisplayManager._commit_quick_visualizer_presence(manager, False) is False
    assert owner.retire_calls == 1
    assert manager._quick_visualizer_owner is owner
    assert manager._quick_visualizer_unit is display
    assert display.visualizer_owner is owner
    assert manager.release_calls == 0
    assert display.detach_calls == 0


def test_edit_disable_retirement_exception_preserves_owner_for_retry():
    owner = _Owner()
    display = _Display(owner)
    manager = _Manager(display, owner)
    def raises():
        raise RuntimeError('failed join')
    owner.retire = raises
    assert DisplayManager._commit_quick_visualizer_presence(manager, False) is False
    assert manager._quick_visualizer_owner is owner
    assert display.visualizer_owner is owner
    owner.retire = lambda: setattr(owner, 'is_retired', True)
    assert DisplayManager._commit_quick_visualizer_presence(manager, False) is True
    assert manager._quick_visualizer_owner is None
    assert display.visualizer_owner is None
