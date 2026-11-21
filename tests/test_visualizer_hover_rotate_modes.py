"""Plan 1E / UI-3: the ordinary Visualizer card's hover Rotate glyph is projected from each mode's capability and
routes through the one CUSTOM ``rotateContent`` authority, for 2D and framed 3D modes alike.

Modes are derived from the registry (never named); the glyph row's placement and the expanded card are pinned in
``test_visualizer_glyph_row.py`` / ``test_hover_rotate_without_edit.py``.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.display_manager import DisplayManager
from tests._display_manager_doubles import (
    bare_display_manager,
    display_runtime_double,
    display_unit_double,
    input_controller_double,
    scene_controller_double,
    visualizer_owner_double,
)
from tests.test_hover_rotate_without_edit import _Stack

pytestmark = pytest.mark.qt


def _modes():
    from core.settings.visualizer_mode_registry import (
        VISUALIZER_MODE_IDS,
        get_visualizer_mode_descriptor,
        get_visualizer_presentation_policy,
    )

    return [(mode, get_visualizer_mode_descriptor(mode), get_visualizer_presentation_policy(mode))
            for mode in VISUALIZER_MODE_IDS]


def _first(predicate) -> str:
    return next(mode for mode, descriptor, policy in _modes() if predicate(descriptor, policy))


def test_the_rotate_glyph_is_offered_exactly_for_rotation_capable_modes():
    """Every registry mode, through the real mode-edge projection: the Rotate glyph follows the mode's own
    ``content_rotation_capable`` (2D and 3D alike, whatever the 3D orbit admission says) and nothing else."""
    modes = _modes()
    assert any(policy.content_rotation_capable for _m, _d, policy in modes)
    assert any(not policy.content_rotation_capable for _m, _d, policy in modes)      # an ineligible mode exists
    for mode, _descriptor, policy in modes:
        for orbit in (False, True):
            calls = []
            ic = input_controller_double(set_view_orbit_enabled=lambda _v: None)
            sc = scene_controller_double(
                set_visualizer_studio_rotate_glyphs=lambda *args, calls=calls: calls.append(args))
            owner = visualizer_owner_double(SimpleNamespace(mode_id=mode, presentation_policy=policy))
            manager = bare_display_manager(_quick_visualizer_owner=owner, _quick_view_orbit_admitted=lambda o=orbit: o)
            unit = display_unit_double(display_runtime_double(input_controller=ic, scene_controller=sc))
            DisplayManager._configure_quick_visualizer_input_admission(manager, unit)
            assert calls and calls[-1][1] is bool(policy.content_rotation_capable), (mode, orbit)


def test_an_inactive_visualizer_offers_no_rotate_glyph():
    mode = _first(lambda _d, policy: policy.content_rotation_capable)
    calls = []
    sc = scene_controller_double(set_visualizer_studio_rotate_glyphs=lambda *args: calls.append(args))
    owner = visualizer_owner_double(SimpleNamespace(mode_id=mode, presentation_policy=SimpleNamespace(
        content_rotation_capable=True)), started=False)
    manager = bare_display_manager(_quick_visualizer_owner=owner, _quick_view_orbit_admitted=lambda: False)
    unit = display_unit_double(display_runtime_double(input_controller=input_controller_double(
        set_view_orbit_enabled=lambda _v: None), scene_controller=sc))
    DisplayManager._configure_quick_visualizer_input_admission(manager, unit)
    assert calls[-1][1] is False


_KINDS = {
    "2d": lambda descriptor, policy: policy.content_rotation_capable and not descriptor.scene_transform_settings,
    "framed_3d": lambda descriptor, policy: policy.content_rotation_capable and bool(descriptor.scene_transform_settings),
}


@pytest.fixture
def stack(qt_app, tmp_path, monkeypatch, request):
    built = _Stack(qt_app, tmp_path, monkeypatch, expanded=False, mode=request.param)
    try:
        yield built
    finally:
        built.close()


def _param(kind: str) -> str:
    try:
        return _first(_KINDS[kind])
    except StopIteration:      # the registry has no such mode: the case is vacuous, not failing
        return ""


@pytest.mark.parametrize("stack", [_param("2d"), _param("framed_3d")], indirect=True, ids=["2d", "framed_3d"])
def test_four_hover_rotations_return_to_the_start_through_the_one_owner(stack):
    """Each click is one committed quarter turn through ``rotateContent`` (one Save, no Edit session, no rebuild, no
    mode switch); four return the card to its start."""
    if not stack.mode:
        pytest.skip("no mode of this kind in the registry")
    assert stack.drawn().content_rotation_quarters == 0
    for step in range(1, 5):
        assert stack.rotate()
        assert not stack.edit.is_active
        assert stack.saves == step and stack.reloads == []
        assert stack.drawn().content_rotation_quarters == step % 4
        assert stack.owner.controller.committed_content_rotation_quarters == step % 4
        assert stack.owner.controller.mode_id == stack.mode
    assert stack.committed_rotation().get(stack.mode, 0) == 0


@pytest.mark.parametrize("stack", [_first(lambda _d, policy: not policy.content_rotation_capable)],
                         indirect=True, ids=["ineligible"])
def test_an_ineligible_mode_refuses_the_hover_rotate_and_changes_nothing(stack):
    assert not stack.rotate()
    assert stack.saves == 0 and stack.committed_rotation() == {} and not stack.edit.is_active
    assert stack.drawn().content_rotation_quarters == 0 and stack.owner.controller.mode_id == stack.mode
