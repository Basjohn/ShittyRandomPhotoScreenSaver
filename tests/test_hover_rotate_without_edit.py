"""Plan 1D.7: the hover Rotate glyph never drops the user into Edit (operator, 13-14 Nov).

Outside Edit, Rotate is one committed change with no Edit chrome, on every surface that offers it: the ordinary
Visualizer card and the expanded (display-wide) card. It runs through the one CUSTOM owner and Edit's own turn
(``QuickCustomLayoutOwner.rotate_visualizer_content``), Saved at once and promoted live (no rebuild). Inside an open
Edit it stays Edit's undoable draft step. Restore Size and Child Lock still enter Edit (operator rulings, 14 Nov).

The rotate tests drive the real ``DisplayManager`` route (``bare_display_manager``) over a real, never-shown Quick
runtime, the production Visualizer owner, the real ``QuickCustomLayoutOwner``, a real ``SettingsManager`` in
``tmp_path`` and (for the expanded card) the real takeover coordinator. Modes are derived from the registry.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.display_manager import DisplayManager
from tests._display_manager_doubles import bare_display_manager, display_runtime_double, display_unit_double

pytestmark = pytest.mark.qt


def _rotating_mode(*, expanded: bool) -> str:
    from core.settings.visualizer_mode_registry import (
        VISUALIZER_MODE_IDS,
        get_visualizer_mode_descriptor,
        get_visualizer_presentation_policy,
    )

    return next(mode for mode in VISUALIZER_MODE_IDS
                if get_visualizer_presentation_policy(mode).content_rotation_capable
                and (not expanded or get_visualizer_mode_descriptor(mode).supports_expanded_display))


class _Stack:
    """The real route's participants: one unshown runtime, the production Visualizer owner, the CUSTOM owner and the
    display manager that owns the hover route."""

    def __init__(self, qt_app, tmp_path, monkeypatch, *, expanded: bool) -> None:
        from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
        from rendering.quick.runtime import QuickDisplayRuntime
        from rendering.quick.scene_controller import QuickSceneFactory
        from rendering.quick.state import QuickInputState, QuickWindowPolicy
        from tests._visualizer_frozen_settings import frozen_visualizer_settings
        from tests._visualizer_presentation import make_visualizer_owner
        from tests.test_visualizer_expansion_fullscreen_edit import _manager, _seed
        from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs

        self.qt_app = qt_app
        self.mode = _rotating_mode(expanded=expanded)
        self.settings = _manager(tmp_path)
        _seed(self.settings)
        self.saves = 0
        real_save = self.settings.save

        def counted_save(*args, **kwargs):
            self.saves += 1
            return real_save(*args, **kwargs)

        monkeypatch.setattr(self.settings, "save", counted_save)
        self.factory = QuickSceneFactory()
        self.runtime = QuickDisplayRuntime(screen_index=0, runtime_generation=1307, screen=qt_app.primaryScreen(),
                                           scene_factory=self.factory,
                                           window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
        self.owner = make_visualizer_owner(self.runtime, bar_count=32, initial_mode=self.mode)
        apply_presentation_vis_mode_kwargs(self.owner.controller.presentation_state,
                                           frozen_visualizer_settings(self.mode))
        self.unit = display_unit_double(self.runtime, screen_index=0,
                                        presenter=SimpleNamespace(bound_widget_ids=()))
        self.reloads: list[str] = []
        # The authored-layout switch (stacking/adjacency over the ordinary presenters) is recorded, not run: this unit
        # has no ordinary presenter, and the switch is the same edge for every session kind.
        self.authored: list[bool] = []
        self.manager = bare_display_manager(
            _retired=False, displays=[self.unit], settings_manager=self.settings,
            _quick_visualizer_unit=self.unit, _quick_visualizer_owner=self.owner, _widgets_config_snapshot={},
            _set_quick_authored_layout_enabled=lambda enabled, **_kw: self.authored.append(bool(enabled)))
        self.edit = QuickCustomLayoutOwner(
            settings_manager=self.settings, participants_provider=lambda: (self.unit,),
            visualizer_provider=lambda: (self.owner, self.unit), reload_request=self.reloads.append,
            live_config_commit=self.manager._commit_quick_custom_layout_config_snapshot)
        self.manager._quick_custom_layout_owner = self.edit
        self.scene = self.runtime.scene_controller
        self.scene.apply_input_state(QuickInputState(screen_index=0, runtime_generation=1307,
                                                     interaction_mode_enabled=True))
        self.owner.bind(engine_generation=1, activation_id=1)
        self.drawn()
        self.owner._started = True       # the live promotion's liveness gate (no logical runtime runs here)
        self.scene.set_visualizer_startup_reveal_opacity(1.0)
        self.takeover_owner = None
        if expanded:
            self._expand()
        # Edit chrome is bound by exactly these scene calls; record each bind and whether the event loop turned
        # (the only way Qt Quick can sync or render a frame) before the matching clear.
        self.binds: list[str] = []
        self.turned_while_bound: list[bool] = []
        self._turns: list[int] = []
        for name in ("bind_custom_layout_session", "bind_fullscreen_overlay_edit_session"):
            self._spy_bind(monkeypatch, name)
        real_clear = self.scene.clear_custom_layout_session

        def clear(*args, **kwargs):
            if self.binds and len(self.turned_while_bound) < len(self.binds):
                self.turned_while_bound.append(bool(self._turns))
            return real_clear(*args, **kwargs)

        monkeypatch.setattr(self.scene, "clear_custom_layout_session", clear)

    def _spy_bind(self, monkeypatch, name: str) -> None:
        from PySide6.QtCore import QTimer

        real = getattr(self.scene, name)

        def bind(*args, **kwargs):
            self.binds.append(name)
            self._turns.clear()
            QTimer.singleShot(0, lambda: self._turns.append(1))      # fires at the next event-loop turn only
            return real(*args, **kwargs)

        monkeypatch.setattr(self.scene, name, bind)

    def _expand(self) -> None:
        from core.expanded_visualizer_takeover import Phase
        from tests.test_visualizer_expansion_fullscreen_edit import _VisualizerOwner
        from widgets.spotify_visualizer.expanded_display_coordinator import (
            ExpandedDisplayCoordinator,
            ExpandedDisplayServices,
        )

        assert self.owner.set_expanded_display(True)
        self.drawn()
        # The real takeover reducer, resting EXPANDED (its owner side is the route stand-in its own tests use).
        self.takeover_owner = _VisualizerOwner()
        coordinator = ExpandedDisplayCoordinator(ExpandedDisplayServices(
            admitted_owner=lambda: self.takeover_owner, admitted_unit=lambda: self.unit, requested=lambda: False,
            persist_requested=lambda _value: None, mode_capable=lambda _mode: True,
            edit_active=lambda: self.edit.is_active, publish_glyph=lambda *_args: None))
        coordinator.generation_ready()
        assert coordinator.glyph_pressed(self.unit, True) and coordinator.phase is Phase.EXPANDED
        self.manager._expanded_display_coordinator = coordinator

    def drawn(self):
        self.owner._reapply_route()      # one publication edge (no logical runtime runs here)
        self.qt_app.processEvents()
        return self.scene.visualizer_item.presentation

    def committed_rotation(self) -> dict:
        from rendering.quick.custom_layout_hydration import resolve_visualizer_custom_entry
        from widgets.spotify_visualizer.presentation_orientation import normalize_content_rotation_by_mode

        entry = resolve_visualizer_custom_entry(self.settings.get_widgets_map(), self.qt_app.primaryScreen(),
                                                self.mode)
        if entry is None:
            return {}
        return normalize_content_rotation_by_mode(entry.size_payload.get("content_rotation_quarters_by_mode"))

    def rotate(self) -> bool:
        return DisplayManager._route_hover_edit_glyph(self.manager, self.unit, "rotate", "spotify_visualizer")

    def close(self) -> None:
        if self.edit.is_active:
            self.edit.cancel()
        self.owner._started = False
        self.owner.retire()
        self.runtime.close_runtime()
        self.factory.deleteLater()
        self.qt_app.processEvents()


@pytest.fixture
def stack(qt_app, tmp_path, monkeypatch, request):
    built = _Stack(qt_app, tmp_path, monkeypatch, expanded=request.param == "expanded")
    try:
        yield built
    finally:
        built.close()


@pytest.mark.parametrize("stack", ["card", "expanded"], indirect=True)
def test_rotate_outside_edit_commits_once_with_no_edit_session_or_chrome(stack):
    """Outside Edit, one click turns the card and commits that turn once: no Edit session remains, no Edit overlay is
    shown (the card never binds Edit chrome; the expanded card's Fullscreen session opens and closes inside the one
    call, before any event-loop turn, so no frame can show it), and the turn is promoted live (no runtime reload).
    Negative control (old route): the click left Edit open with an unsaved draft and wrote nothing."""
    expanded = stack.takeover_owner is not None
    assert stack.committed_rotation() == {} and stack.drawn().content_rotation_quarters == 0

    assert stack.rotate()

    assert not stack.edit.is_active, "the click left a CUSTOM session open"
    assert stack.scene.custom_layout_overlay._model is None              # no Edit overlay bound
    assert stack.runtime.window._custom_layout_input_blocked is False     # Edit's input block is not held
    assert stack.saves == 1 and stack.committed_rotation() == {stack.mode: 1}
    assert stack.owner.controller.committed_content_rotation_quarters == 1
    assert stack.reloads == []                                           # promoted live, never rebuilt
    assert stack.drawn().content_rotation_quarters == 1
    if expanded:
        assert stack.manager._expanded_display_coordinator.phase.value == "expanded"
        assert not stack.manager._expanded_display_coordinator.fullscreen_edit
        assert stack.binds == ["bind_fullscreen_overlay_edit_session"] and stack.turned_while_bound == [False]
        stack.qt_app.processEvents()
        assert stack._turns == [1]                                       # the probe itself does fire on a turn
    else:
        assert stack.binds == []                                         # Edit chrome was never bound

    # A second click turns once more, again committed once.
    assert stack.rotate()
    assert stack.saves == 2 and stack.committed_rotation() == {stack.mode: 2} and not stack.edit.is_active


@pytest.mark.parametrize("stack", ["card", "expanded"], indirect=True)
def test_rotate_inside_edit_stays_an_undoable_draft_step(stack):
    """Inside an open Edit the same click is Edit's draft step: the session stays, nothing is written, and Undo takes
    the turn back exactly."""
    assert stack.manager._start_quick_custom_layout_session(stack.unit)
    assert stack.edit.is_editing
    assert stack.rotate()
    assert stack.edit.is_editing and stack.saves == 0 and stack.committed_rotation() == {}
    assert stack.edit.unsaved_changes
    assert stack.edit.undo_last_change()
    assert not stack.edit.unsaved_changes
    assert stack.manager.cancel_custom_layout_session() and not stack.edit.is_active
    assert stack.saves == 0 and stack.committed_rotation() == {}


# ------------------------------------------------- Restore Size and Child Lock still enter Edit (operator, 14 Nov)


def _manager_for_edit_entry(widget_id: str):
    """The route's Edit part over a recorded session (the Edit owner's session surface and the overlay model's
    actions): what the route opened, ran and cancelled."""
    calls: list[object] = []
    target = SimpleNamespace(current_display_identity="source", source_key=SimpleNamespace(widget_id=widget_id),
                             current_enabled=True, removed=False, profile_parked=False, size_reset_capable=True,
                             content_rotation_capable=False)
    session = SimpleNamespace(items=lambda: [target], selected_item=lambda: target, select_item=lambda _: None)
    model = SimpleNamespace(
        _items=[target],
        restoreSize=lambda row: calls.append(("restoreSize", row)) or True,
        requestToggleChildEditLockForWidget=lambda widget: calls.append(("lock", widget)))
    roles = SimpleNamespace(toVariant=lambda: [{"roleId": "artwork"}])
    presentation = SimpleNamespace(is_qt_alive=True, item=SimpleNamespace(property=lambda _name: roles))
    state = SimpleNamespace(admission_open=True, exiting=False, context_menu_active=False,
                            interaction_mode_enabled=True, ctrl_held=False, always_show_glyphs=True)
    # The scene stays hand-built on purpose: it carries the scene's private admission state (_input_state), which
    # the route reads and the setter double refuses as an instance-only name.
    source = display_unit_double(display_runtime_double(scene_controller=SimpleNamespace(
        _input_state=state, custom_layout_overlay=SimpleNamespace(model=model),
        ordinary_widget_host=SimpleNamespace(presentation_for_model_identity=lambda _identity: presentation))))
    owner = SimpleNamespace(is_editing=False, is_active=False, session=session,
                            _bindings={"source": SimpleNamespace(identity="source", unit=source)})
    manager = bare_display_manager(_retired=False, displays=[source], _quick_visualizer_unit=source,
                                   _quick_custom_layout_owner=owner,
                                   _start_quick_custom_layout_session=lambda _entry: calls.append("start") or True,
                                   cancel_custom_layout_session=lambda: calls.append("cancel") or True,
                                   _save_quick_custom_layout=lambda: calls.append("save") or True)
    return manager, source, calls


@pytest.mark.parametrize("action,widget_id,expected", [
    ("restore", "spotify_visualizer", ("restoreSize", 0)),
    ("restore", "clock", ("restoreSize", 0)),
    ("lock", "media", ("lock", "media")),
])
def test_restore_size_and_child_lock_still_enter_edit(action, widget_id, expected):
    """Operator, 14 Nov: Restore Size (widgets and the Visualizer) and Child Lock still open Edit and leave it open,
    with their action as its draft; only Rotate commits without Edit. Pinned so a later change cannot take them out
    of Edit by accident."""
    manager, source, calls = _manager_for_edit_entry(widget_id)
    assert DisplayManager._route_hover_edit_glyph(manager, source, action, widget_id)
    assert calls == ["start", expected]               # Edit opened, the action ran, and nothing saved or cancelled
