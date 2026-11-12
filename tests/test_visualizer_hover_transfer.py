"""Hover transfer is a view and entry into the existing CUSTOM transaction."""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

from engine.display_manager import DisplayManager
from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner, _DisplayBinding
from rendering.quick.scene_controller import QuickSceneController
from tests._display_manager_doubles import bare_display_manager, display_runtime_double, display_unit_double


def test_hover_and_edit_share_live_identity_topology_selection():
    owner = QuickCustomLayoutOwner(settings_manager=SimpleNamespace(), participants_provider=lambda: (),
                                  visualizer_provider=lambda: (None, None), reload_request=lambda _: None)
    source, left, right = object(), object(), object()
    bindings = {key: _DisplayBinding(key, str(index+1), unit, object(), QRect(x, 0, 800, 600))
                for index, (key, unit, x) in enumerate((("left", left, -800), ("source", source, 0), ("right", right, 800)))}
    owner._live_display_bindings = lambda: bindings
    item = SimpleNamespace(model_identity="spotify_visualizer", current_display_identity="source")
    assert owner.visualizer_display_transfer_options(source) == (True, True)
    assert owner._adjacent_display_binding(item, "right", bindings).unit is right
    del bindings["right"]
    assert owner.visualizer_display_transfer_options(source) == (True, False)
    del bindings["left"]
    assert owner.visualizer_display_transfer_options(source) == (False, False)
    assert owner.visualizer_display_transfer_options(object()) == (False, False)


def _manager_for_click(*, options=(True, True), moved=True, existing_edit=False):
    calls = []
    target = SimpleNamespace(current_display_identity="source", source_key=SimpleNamespace(widget_id="spotify_visualizer"),
                             current_enabled=True, removed=False, profile_parked=False)
    session = SimpleNamespace(items=lambda: [target], selected_item=lambda: target, select_item=lambda _: None)
    def transfer(row, direction):
        calls.append(("transfer", row, direction))
        if isinstance(moved, Exception):
            raise moved
        return moved
    model = SimpleNamespace(_items=[target], transferItem=transfer)
    state = SimpleNamespace(admission_open=True, exiting=False, context_menu_active=False,
                            interaction_mode_enabled=True, ctrl_held=False, always_show_glyphs=True)
    # The scene stays hand-built on purpose: it carries the scene's private admission state (_input_state), which
    # DisplayManager's glyph route reads and the setter double refuses as an instance-only name.
    source = display_unit_double(display_runtime_double(scene_controller=SimpleNamespace(
        _input_state=state, custom_layout_overlay=SimpleNamespace(model=model))))
    owner = SimpleNamespace(is_editing=existing_edit, is_active=existing_edit, session=session, _bindings={
        "source": SimpleNamespace(identity="source", unit=source)}, visualizer_display_transfer_options=lambda _: options,
        prepared=[], released=[])
    owner.prepare_visualizer_display_transfer = lambda unit, direction: owner.prepared.append(direction) or True
    owner.release_visualizer_display_preparation = lambda: owner.released.append(True) or True
    manager = bare_display_manager(_retired=False, displays=[source], _quick_visualizer_unit=source,
                                   _quick_custom_layout_owner=owner,
                                   _start_quick_custom_layout_session=lambda _entry: calls.append("start") or True,
                                   cancel_custom_layout_session=lambda: calls.append("cancel") or True)
    return manager, source, calls


@pytest.mark.parametrize("moved,existing_edit", [(True, False), (False, False), (False, True)])
def test_transfer_click_reuses_session_and_cancels_only_its_failed_new_edit(moved, existing_edit):
    manager, source, calls = _manager_for_click(moved=moved, existing_edit=existing_edit)
    assert DisplayManager._route_hover_edit_glyph(manager, source, "transfer_right", "spotify_visualizer") == moved
    assert calls == ["start", ("transfer", 0, "right")] + (["cancel"] if not moved and not existing_edit else [])
    # A click that moved leaves the prepared display to the hop that adopted it; one that did not releases it once.
    assert manager._quick_custom_layout_owner.released == ([] if moved else [True])


def test_the_hover_arrows_edges_prepare_and_release_and_the_clicks_own_leave_is_held():
    """1C.2: entering a hover transfer arrow prepares the display its click moves to, leaving releases it; the leave
    the click's own Edit session causes (it retires the hover chrome) arrives while the click runs and is held, so
    the hop adopts what was prepared. Negative control (pre-change): no route existed and the click's leave would
    have released the prepared display before the hop."""
    manager, source, calls = _manager_for_click()
    owner = manager._quick_custom_layout_owner
    assert DisplayManager._route_hover_transfer_preparation(manager, source, "transfer_right", True)
    assert owner.prepared == ["right"]
    assert DisplayManager._route_hover_transfer_preparation(manager, source, "transfer_right", False)
    assert owner.released == [True]
    model = source.runtime.scene_controller.custom_layout_overlay.model
    held = []

    def transfer(row, direction):
        held.append(DisplayManager._route_hover_transfer_preparation(manager, source, "transfer_" + direction, False))
        return True
    model.transferItem = transfer
    assert DisplayManager._route_hover_edit_glyph(manager, source, "transfer_right", "spotify_visualizer")
    assert held == [False] and owner.released == [True]
    # Not the Visualizer's display, or Edit already open: an entry prepares nothing.
    owner.is_active = True
    assert not DisplayManager._route_hover_transfer_preparation(manager, source, "transfer_left", True)
    assert owner.prepared == ["right"]


def test_transfer_exception_cancels_new_edit_and_remains_loud():
    manager, source, calls = _manager_for_click(moved=RuntimeError("transfer failed"))
    with pytest.raises(RuntimeError, match="transfer failed"):
        DisplayManager._route_hover_edit_glyph(manager, source, "transfer_left", "spotify_visualizer")
    assert calls[-1] == "cancel"


@pytest.mark.parametrize("options,widget,blocked", [((False, False), "spotify_visualizer", False),
                                                  ((True, True), "clock", False),
                                                  ((True, True), "spotify_visualizer", True)])
def test_stale_or_ineligible_hover_does_not_enter_edit(options, widget, blocked):
    manager, source, calls = _manager_for_click(options=options)
    source.runtime.scene_controller._input_state.context_menu_active = blocked
    assert not DisplayManager._route_hover_edit_glyph(manager, source, "transfer_left", widget)
    assert calls == []


def test_scene_retains_capabilities_before_lazy_root_creation_and_only_updates_on_change():
    calls = []
    scene = SimpleNamespace(_visualizer_display_transfer_available=(False, False), _visualizer_root=None)
    QuickSceneController.set_visualizer_display_transfer_available(scene, True, False)
    assert scene._visualizer_display_transfer_available == (True, False)
    scene._visualizer_root = SimpleNamespace(setProperty=lambda *args: calls.append(args))
    QuickSceneController.set_visualizer_display_transfer_available(scene, True, False)
    assert calls == []
    QuickSceneController.set_visualizer_display_transfer_available(scene, False, True)
    assert calls == [("displayTransferLeftAvailable", False), ("displayTransferRightAvailable", True)]


def test_manager_projection_follows_current_owner_and_excludes_retired_units(monkeypatch):
    from engine import display_manager

    published, resolved = [], []
    class Unit:
        is_retired = False
        def __init__(self, name):
            self.runtime = SimpleNamespace(scene_controller=SimpleNamespace(
                set_visualizer_display_transfer_available=lambda *options: published.append((name, options))))
    monkeypatch.setattr(display_manager, "QuickDisplayUnit", Unit)
    source, target, retired = Unit("source"), Unit("target"), Unit("retired")
    retired.is_retired = True
    # Unit stays a local class on purpose: the test patches it in as display_manager.QuickDisplayUnit so the
    # isinstance filter admits it, and it records what each unit is told.
    manager = bare_display_manager(displays=[source, target, retired], _quick_visualizer_unit=source,
                                   _quick_custom_layout_owner=SimpleNamespace(
                                       visualizer_display_transfer_options=lambda unit: resolved.append(unit) or (False, True)))
    DisplayManager._refresh_quick_visualizer_transfer_glyphs(manager)
    assert published == [("source", (False, True)), ("target", (False, False))]
    manager._quick_visualizer_unit = target
    published.clear()
    DisplayManager._refresh_quick_visualizer_transfer_glyphs(manager)
    assert published == [("source", (False, False)), ("target", (False, True))]
    assert resolved == [source, target]
    manager._quick_visualizer_unit = retired
    published.clear()
    DisplayManager._refresh_quick_visualizer_transfer_glyphs(manager)
    assert published == [("source", (False, False)), ("target", (False, False))]
    assert resolved == [source, target]
