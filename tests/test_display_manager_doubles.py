"""The shared DisplayManager doubles (``tests/_display_manager_doubles.py``) follow the real classes."""
from __future__ import annotations

import pytest

from tests._display_manager_doubles import (
    bare_display_manager,
    display_runtime_double,
    display_unit_double,
    input_controller_double,
    scene_controller_double,
    visualizer_owner_double,
)


def test_a_bare_manager_carries_the_plain_init_defaults_and_overrides():
    manager = bare_display_manager(_widgets_config_snapshot={"x": 1})
    # Members __init__ always assigns as plain defaults (the ones stale stubs lacked among them).
    assert manager.displays == [] and manager._quick_visualizer_owner is None
    assert manager._widgets_config_snapshot == {"x": 1}
    # Each manager gets its own containers.
    assert bare_display_manager().displays is not manager.displays


def test_controller_doubles_offer_every_real_setter_and_refuse_invented_members():
    from rendering.quick.input_controller import QuickInputController
    from rendering.quick.scene_controller import QuickSceneController

    scene, inputs = scene_controller_double(), input_controller_double()
    for cls, double in ((QuickSceneController, scene), (QuickInputController, inputs)):
        setters = [name for name in dir(cls) if name.startswith("set_") and callable(getattr(cls, name))]
        assert setters and all(getattr(double, name)(True) is None for name in setters)
    with pytest.raises(AttributeError):
        scene_controller_double(set_no_such_member=lambda *_a: None)


def test_the_owner_double_is_the_real_owners_read_surface():
    owner = visualizer_owner_double(object(), started=False)
    assert owner.is_started is False and owner.is_retired is False
    with pytest.raises(AttributeError):
        visualizer_owner_double(object(), no_such_member=True)


def test_unit_and_runtime_doubles_are_the_real_read_surfaces():
    from rendering.quick.scene_controller import QuickSceneController

    unit = display_unit_double(screen_index=1)
    assert unit.is_retired is False and unit.screen_index == 1
    # The runtime's controllers default to the setter doubles: every real setter is there.
    setters = [name for name in dir(QuickSceneController) if name.startswith("set_")]
    assert setters and all(hasattr(unit.runtime.scene_controller, name) for name in setters)
    assert hasattr(unit.runtime.input_controller, "set_view_orbit_enabled")
    scene = object()
    assert display_unit_double(display_runtime_double(scene_controller=scene)).runtime.scene_controller is scene
    with pytest.raises(AttributeError):
        display_unit_double(no_such_member=True)
    with pytest.raises(AttributeError):
        display_runtime_double(no_such_member=True)
