"""Edit edits the display it was entered on, with an Expanded Visualizer on another display (plan 1B.1).

Operator, 11 Nov: "When 2+ displays are active and visualizer is fullscreen on (for example) D1, activating edit mode
on D0 or D1 only activates D1's edit mode for the fullscreen visualizer. D0 becomes impossible to edit."

Ordinary Edit is one global session: entered from any display it binds every display. With the Visualizer resting
expanded on one display, Edit entered on that display is Fullscreen Edit (its overlays, M3c) and Edit entered on
another display is an ordinary Edit of every display but the expanded one, which stays expanded and running, outside
the session (no Edit chrome, nothing captured there, no transfer into it).

The bars run the display manager's real Edit entry, Save, Cancel, Settings and context-menu routes (bound onto a
stand-in host, as ``test_visualizer_expansion_fullscreen_edit`` does), the real takeover coordinator, the real
``QuickCustomLayoutOwner`` with its one session, and a real ``SettingsManager`` in ``tmp_path``. The other display is
a real Quick display unit with a real clock family (an unshown runtime, never shown); the expanded display is the
production scene in the hidden ``QQuickRenderControl`` host with the display-wide card drawn. Two logical screens
side by side give the two displays their identities. Every value a test writes is test-owned.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

from tests.test_visualizer_expansion_overlays import _Media, _draw, _open, _run

WIDTH, HEIGHT = 1280, 720


@pytest.fixture
def display(qt_app):
    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production scene needs the Windows QPA GL")
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    host = HiddenDisplayHost(WIDTH, HEIGHT, dpr=1.0)
    try:
        yield host
    finally:
        host.close()


def _settings(root):
    from core.settings.settings_manager import SettingsManager

    settings = SettingsManager(organization="TestOrg", application=f"TestApp_{uuid.uuid4().hex}",
                               storage_base_dir=root)
    widgets = settings.get_widgets_map()
    # A test-owned shared clock (on every display) and nothing else of its family.
    clock = widgets.setdefault("clock", {})
    clock.update(enabled=True, display_mode="digital", font_size=48, position="Top Left", monitor="ALL")
    for other in ("clock2", "clock3"):
        widgets.setdefault(other, {})["enabled"] = False
    settings.set_widgets_map(widgets)
    settings.save()
    return settings


def _screen(name: str, x: int):
    return SimpleNamespace(geometry=lambda rect=QRect(x, 0, WIDTH, HEIGHT): QRect(rect), name=lambda: name,
                           serialNumber=lambda: name, manufacturer=lambda: "", model=lambda: "")


class _HeldPresenter:
    """The covered display's presenter as Edit reads it: its own copy of the shared clock (hidden under the card)."""

    bound_widget_ids = ("clock",)

    @staticmethod
    def geometry_for(_widget_id):
        return SimpleNamespace(x=40.0, y=40.0, width=220.0, height=90.0)

    @staticmethod
    def presentation_for_widget_id(_widget_id):
        return object()


class _View:
    """The Visualizer owner as the takeover coordinator and Fullscreen Edit drive it (records every viewport change)."""

    def __init__(self) -> None:
        from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy

        self.controller = SimpleNamespace(mode_id="sphere", presentation_policy=get_visualizer_presentation_policy(
            "sphere"), engine=SimpleNamespace(get_activation_id=lambda: 1))
        self.is_retired = False
        self.is_started = False
        self.expanded_display = False
        self.expanded_display_transition_active = False
        self.expanded_display_fade_half_s = 0.25
        self._mode_transition_phase = "idle"
        self.calls: list[tuple[bool, bool]] = []

    def set_expanded_display(self, expanded, *, animate=False, on_complete=None):
        self.calls.append((bool(expanded), bool(animate)))
        self.expanded_display = bool(expanded)
        if on_complete is not None:
            on_complete()
        return True


class _Rig:
    """Two displays: ``self.view`` (the hidden production scene, where the Visualizer is) and ``self.other`` (a real
    clock display); ``view_index`` says which one is display 0."""

    MANAGER_ROUTES = (
        "_start_quick_custom_layout_session", "_start_quick_custom_layout_from_shortcut",
        "_start_fullscreen_overlay_edit", "_save_quick_custom_layout", "cancel_custom_layout_session",
        "_fullscreen_edit_holds_draft", "_handle_quick_context_action", "_refresh_quick_context_menu",
        "_quick_context_transition_state", "_interaction_mode_enabled", "_route_hover_edit_glyph",
    )

    def __init__(self, qt_app, display, settings, *, view_index: int = 1, plain: bool = False) -> None:
        """``plain``: the Visualizer's display is a second real clock display too (no expanded card drawn), for the
        global ordinary Edit both displays join."""
        from engine.display_manager import DisplayManager
        from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
        from tests.test_qtquick_custom_layout_owner import _clock_unit
        from widgets.spotify_visualizer.expanded_display_coordinator import (
            ExpandedDisplayCoordinator,
            ExpandedDisplayServices,
        )

        self.display = display
        self.settings = settings
        other_index = 1 - view_index
        self.clock_unit, self.factory = _clock_unit(qt_app, settings.get_widgets_map(), generation=1101,
                                                    screen_index=other_index)
        assert self.clock_unit.presenter.bound_widget_ids == ("clock",)
        self.menus: dict[int, tuple] = {}
        screens = {index: _screen(f"logical-{index}", index * WIDTH) for index in (0, 1)}

        def route(index, presenter, scene):
            return SimpleNamespace(
                screen_index=index, is_retired=False, presenter=presenter,
                configure_context_menu=lambda entries, action_handler, index=index: self.menus.__setitem__(
                    index, tuple(entry.action_id for entry in entries if entry.action_id)),
                runtime=SimpleNamespace(
                    scene_controller=scene, window=SimpleNamespace(screen=lambda screen=screens[index]: screen),
                    context_menu_model=SimpleNamespace(dismiss=lambda: None),
                    display_identity=SimpleNamespace(screen_key=f"logical-{index}",
                                                     geometry=(index * WIDTH, 0, WIDTH, HEIGHT))))

        self.other = route(other_index, self.clock_unit.presenter, self.clock_unit.runtime.scene_controller)
        self.view_unit = None
        if plain:
            self.view_unit, _factory = _clock_unit(qt_app, settings.get_widgets_map(), generation=1101,
                                                   screen_index=view_index, factory=self.factory)
            self.view = route(view_index, self.view_unit.presenter, self.view_unit.runtime.scene_controller)
        else:
            self.view = route(view_index, _HeldPresenter(), display.scene)
        self.units = tuple(sorted((self.other, self.view), key=lambda unit: unit.screen_index))
        self.visualizer = _View()
        self.reloads: list[str] = []
        self.owner = QuickCustomLayoutOwner(
            settings_manager=settings, participants_provider=lambda: self.units,
            visualizer_provider=lambda: (None, None) if plain else (self.visualizer, self.view),
            reload_request=self.reloads.append,
            live_config_commit=lambda _widgets: None)
        host = SimpleNamespace(
            _quick_custom_layout_owner=self.owner, _quick_visualizer_unit=self.view,
            _quick_visualizer_owner=self.visualizer, settings_manager=settings, displays=list(self.units),
            _retired=False, authored_calls=[], published=[], settings_emits=[])
        host._visualizer_section = lambda: settings.get("widgets.spotify_visualizer")
        host._set_quick_authored_layout_enabled = lambda *a, **k: host.authored_calls.append((a, k))
        host._authored_layout_allowed_by_settings = lambda: True
        host._refresh_all_quick_context_menus = lambda: [host._refresh_quick_context_menu(unit)
                                                         for unit in self.units]
        host._refresh_quick_visualizer_edit_content_envelope = lambda *a, **k: None
        host._publish_expanded_overlays = lambda: host.published.append(1)
        host.settings_requested = SimpleNamespace(emit=lambda: host.settings_emits.append(1))
        for name in self.MANAGER_ROUTES:
            setattr(host, name, getattr(DisplayManager, name).__get__(host))
        self.coordinator = ExpandedDisplayCoordinator(ExpandedDisplayServices(
            admitted_owner=lambda: self.visualizer,
            admitted_unit=lambda: self.view,
            requested=lambda: False,
            persist_requested=lambda _value: None,
            mode_capable=lambda mode: mode != "incapable",
            edit_active=lambda: self.owner.is_active,
            publish_glyph=lambda *_args: None,
        ))
        host._expanded_display_coordinator = self.coordinator
        self.host = host

    # ---------------------------------------------------------------------------------------------- facts

    def expand(self) -> None:
        from core.expanded_visualizer_takeover import Phase

        self.coordinator.generation_ready()
        assert self.coordinator.glyph_pressed(self.view, True)
        assert self.coordinator.phase is Phase.EXPANDED and self.visualizer.calls == [(True, True)]

    def enter(self, unit, route: str) -> bool:
        """Edit entered on ``unit`` by one of the product's entries (the menu, the double-right shortcut)."""
        if route == "menu":
            return self.host._handle_quick_context_action(unit, "edit_layout", "")
        return self.host._start_quick_custom_layout_from_shortcut(unit)

    @staticmethod
    def bound(unit) -> bool:
        """The display's scene holds an Edit session (its Edit layer is drawn)."""
        try:
            unit.runtime.scene_controller.custom_layout_overlay.model
        except RuntimeError:
            return False
        return True

    def rows(self, unit) -> tuple[str, ...]:
        model = unit.runtime.scene_controller.custom_layout_overlay.model
        return tuple(item.model_identity for item in model._items)

    def still_expanded(self) -> None:
        """The view kept running display-wide: no collapse reached the Visualizer owner, the card is still drawn."""
        from core.expanded_visualizer_takeover import Phase

        assert self.coordinator.phase is Phase.EXPANDED
        assert self.visualizer.calls == [(True, True)] and self.visualizer.expanded_display
        _run(self.display, 60)
        root = self.display.scene._visualizer_root
        assert root is not None and root.isVisible()
        assert not self.display.scene.custom_layout_fullscreen

    def menu(self, unit) -> tuple[str, ...]:
        self.host._refresh_quick_context_menu(unit)
        return self.menus[unit.screen_index]

    def close(self, qt_app) -> None:
        if self.owner.is_active:
            self.owner.cancel()
        self.owner.retire()
        self.clock_unit.retire()
        if self.view_unit is not None:
            self.view_unit.retire()
        self.factory.deleteLater()
        qt_app.processEvents()


@pytest.fixture
def rig_factory(qt_app, display, tmp_path):
    rigs: list[_Rig] = []

    def make(*, view_index: int = 1, plain: bool = False) -> _Rig:
        settings = _settings(tmp_path)
        if not plain:
            _draw(display, media=_Media())
            _open(display)
        rig = _Rig(qt_app, display, settings, view_index=view_index, plain=plain)
        rigs.append(rig)
        return rig

    yield make
    for rig in rigs:
        rig.close(qt_app)


# ------------------------------------------------------------------------------ the operator's report (1B.1)


@pytest.mark.qt
@pytest.mark.parametrize("view_index", [1, 0])
@pytest.mark.parametrize("route", ["menu", "shortcut"])
def test_edit_from_the_other_display_edits_it_while_the_expanded_view_keeps_running(rig_factory, view_index, route):
    rig = rig_factory(view_index=view_index)
    rig.expand()

    assert rig.enter(rig.other, route)
    # The other display entered Edit: an ordinary Edit of its widgets ...
    assert rig.owner.is_editing and not rig.owner.is_fullscreen
    assert rig.bound(rig.other) and rig.rows(rig.other) == ("clock",)
    assert rig.coordinator.edit_elsewhere and not rig.coordinator.fullscreen_edit
    # ... and only there: the expanded display has no Edit chrome, nothing of it is in the session.
    assert not rig.bound(rig.view)
    assert [binding.unit for binding in rig.owner._bindings.values()] == [rig.other]
    assert {item.current_display_identity for item in rig.owner.session.items()} == set(rig.owner._bindings)
    rig.still_expanded()
    # Its menu offers Save/Cancel; the expanded display's offers Edit Layout (entering Edit there edits it).
    assert {"save_layout", "cancel_layout"} <= set(rig.menu(rig.other))
    assert "edit_layout" in rig.menu(rig.view) and "save_layout" not in rig.menu(rig.view)


# --------------------------------------------------------------------- ordinary Edit with no expanded view


@pytest.mark.qt
def test_ordinary_edit_without_an_expanded_view_edits_every_display_from_either(rig_factory):
    rig = rig_factory(plain=True)
    rig.coordinator.generation_ready()            # capable, not expanded
    for entry in (rig.view, rig.other):
        assert rig.enter(entry, "menu")
        assert rig.owner.is_editing and not rig.owner.is_fullscreen
        assert rig.bound(rig.view) and rig.bound(rig.other)
        assert sorted(binding.unit.screen_index for binding in rig.owner._bindings.values()) == [0, 1]
        assert all({"save_layout", "cancel_layout"} <= set(rig.menu(unit)) for unit in rig.units)
        assert not rig.coordinator.edit_elsewhere and not rig.coordinator.fullscreen_edit
        # Entering again from the other display is the same session (nothing restarts).
        session = rig.owner.session
        assert rig.enter(rig.other if entry is rig.view else rig.view, "shortcut")
        assert rig.owner.session is session
        assert rig.host.cancel_custom_layout_session() and not rig.owner.is_active
    assert rig.visualizer.calls == []


# ------------------------------------------------------------------------------- Save and Cancel on each


@pytest.mark.qt
@pytest.mark.parametrize("ending", ["save", "cancel"])
def test_save_and_cancel_of_an_edit_beside_the_view_keep_it_expanded(rig_factory, ending):
    from rendering.custom_layout_contract import get_screen_layout_entries_for_screen, load_custom_layout_map

    rig = rig_factory()
    rig.expand()
    before = rig.settings.get_widgets_map()
    assert rig.enter(rig.other, "menu")
    model = rig.other.runtime.scene_controller.custom_layout_overlay.model
    start = rig.owner.session.items()[0].current_global_rect
    model.moveItem(0, start.x() - rig.other.screen_index * WIDTH + 60, start.y() + 40,
                   start.x() - rig.other.screen_index * WIDTH + 70, start.y() + 50)
    model.finishMove()
    assert rig.owner.unsaved_changes

    action = "save_layout" if ending == "save" else "cancel_layout"
    assert rig.host._handle_quick_context_action(rig.other, action, "")
    assert not rig.owner.is_active and not rig.bound(rig.other)
    assert not rig.coordinator.edit_elsewhere
    rig.still_expanded()
    after = rig.settings.get_widgets_map()
    view_screen, other_screen = rig.view.runtime.window.screen(), rig.other.runtime.window.screen()

    def entries(widgets, screen):
        return get_screen_layout_entries_for_screen(load_custom_layout_map(widgets), screen)[1]

    # The expanded display's layout is never touched; the shared clock keeps its route.
    assert entries(after, view_screen) == entries(before, view_screen) == {}
    assert after["clock"]["monitor"] == "ALL" and after["clock"]["enabled"] is True
    if ending == "save":
        assert "clock" in entries(after, other_screen)
    else:
        assert after == before
    assert rig.reloads == []


@pytest.mark.qt
@pytest.mark.parametrize("ending", ["save", "cancel"])
def test_edit_from_the_expanded_display_is_fullscreen_edit_there_only(rig_factory, ending):
    rig = rig_factory()
    rig.expand()
    assert rig.enter(rig.view, "shortcut")
    assert rig.owner.is_fullscreen and rig.coordinator.fullscreen_edit
    assert rig.bound(rig.view) and not rig.bound(rig.other)       # the other display has no Edit chrome
    assert rig.host.authored_calls == []                           # the ordinary layout was never quiesced
    assert "edit_layout" in rig.menu(rig.other) and {"save_layout", "cancel_layout"} <= set(rig.menu(rig.view))
    action = "save_layout" if ending == "save" else "cancel_layout"
    assert rig.host._handle_quick_context_action(rig.view, action, "")
    assert not rig.owner.is_active and not rig.coordinator.fullscreen_edit
    from core.expanded_visualizer_takeover import Phase

    assert rig.coordinator.phase is Phase.EXPANDED and rig.visualizer.calls == [(True, True)]


# --------------------------------------------------------- a request from the display the session does not edit


@pytest.mark.qt
def test_an_unsaved_fullscreen_draft_holds_an_edit_request_and_settings_from_the_other_display(rig_factory):
    rig = rig_factory()
    rig.expand()
    assert rig.enter(rig.view, "menu") and rig.owner.is_fullscreen
    # A clean Fullscreen Edit has nothing to lose: Edit moves to the other display at once.
    assert rig.enter(rig.other, "shortcut")
    assert rig.owner.is_editing and not rig.owner.is_fullscreen and rig.coordinator.edit_elsewhere
    assert rig.bound(rig.other) and not rig.bound(rig.view)
    rig.still_expanded()
    assert rig.host.cancel_custom_layout_session()

    # With an unsaved draft the request waits for the draft's own Save or Cancel (never discarded or saved).
    assert rig.enter(rig.view, "menu") and rig.owner.is_fullscreen
    model = rig.view.runtime.scene_controller.custom_layout_overlay.model
    row = next(index for index, item in enumerate(model._items)
               if item.model_identity == "fullscreen_overlay.preset")
    model.resizeWheel(row, 240)
    assert rig.owner.fullscreen_draft_pending
    value = rig.settings.get("widgets.spotify_visualizer.fullscreen_overlays")
    for route in ("menu", "shortcut"):
        assert rig.enter(rig.other, route) is False
        assert rig.owner.is_fullscreen and rig.owner.fullscreen_draft_pending
        assert not rig.bound(rig.other)
    # The Settings-wait rule holds from either display.
    for unit in (rig.other, rig.view):
        assert rig.host._handle_quick_context_action(unit, "settings", "") is False
    assert rig.host.settings_emits == []
    assert rig.settings.get("widgets.spotify_visualizer.fullscreen_overlays") == value
    assert rig.host.cancel_custom_layout_session()
    assert rig.enter(rig.other, "menu") and rig.coordinator.edit_elsewhere
    rig.still_expanded()


@pytest.mark.qt
def test_an_edit_beside_the_view_moves_to_it_only_when_clean(rig_factory):
    rig = rig_factory()
    rig.expand()
    assert rig.enter(rig.other, "menu") and rig.coordinator.edit_elsewhere
    # Clean: Edit on the expanded display becomes its Fullscreen Edit.
    assert rig.enter(rig.view, "shortcut")
    assert rig.owner.is_fullscreen and rig.bound(rig.view) and not rig.bound(rig.other)
    assert rig.host.cancel_custom_layout_session()

    assert rig.enter(rig.other, "menu")
    model = rig.other.runtime.scene_controller.custom_layout_overlay.model
    rect = rig.owner.session.items()[0].current_global_rect
    local_x = rect.x() - rig.other.screen_index * WIDTH
    model.moveItem(0, local_x + 50, rect.y() + 30, local_x + 60, rect.y() + 40)
    model.finishMove()
    assert rig.owner.unsaved_changes
    assert rig.enter(rig.view, "menu") is False
    assert rig.owner.is_editing and not rig.owner.is_fullscreen and rig.bound(rig.other)
    assert rig.owner.session.items()[0].current_global_rect != rect      # the draft is untouched
    # Settings from either display ends an ordinary Edit through its Cancel, as an ordinary Edit always did.
    assert rig.host._handle_quick_context_action(rig.view, "settings", "")
    assert rig.host.settings_emits == [1] and not rig.owner.is_active
    rig.still_expanded()


# ------------------------------------------------------------------- a shared widget beside the expanded view


@pytest.mark.qt
def test_closing_a_shared_widget_beside_the_view_removes_only_that_copy(rig_factory):
    """In a global Edit the X on one copy of a shared (ALL) widget removes that copy; the one left narrows the
    route to its display. The expanded display's copy is outside the session but still counts."""
    rig = rig_factory()
    rig.expand()
    assert rig.enter(rig.other, "menu")
    item = rig.owner.session.items()[0]
    assert item.model_identity == "clock" and item.is_duplicate
    rig.other.runtime.scene_controller.custom_layout_overlay.model.closeItem(0)
    assert item.removed and item.current_enabled
    assert rig.host._save_quick_custom_layout()
    widgets = rig.settings.get_widgets_map()
    assert widgets["clock"]["enabled"] is True
    assert widgets["clock"]["monitor"] == str(rig.view.screen_index + 1)
    rig.still_expanded()


# ------------------------------------------------------------- the view neither collapses nor moves under it


@pytest.mark.qt
def test_the_view_waits_for_the_edit_beside_it_before_collapsing_or_changing_to_an_incapable_mode(rig_factory):
    from core.expanded_visualizer_takeover import Phase

    rig = rig_factory()
    rig.expand()
    assert rig.enter(rig.other, "menu")
    # A (stale) collapse press is answered through the Edit session: declined, the view and Edit stay.
    rig.coordinator._glyph_activation = 1
    rig.coordinator.glyph_pressed(rig.view, False)
    assert rig.coordinator.phase is Phase.EXPANDED and rig.owner.is_editing
    # A mode that cannot expand would collapse the view into a layout the session does not hold: refused until
    # Save or Cancel. A capable one is forwarded and the view stays expanded.
    forwarded: list[str] = []
    assert rig.coordinator.mode_requested("incapable", lambda: forwarded.append("incapable") or True) is False
    assert rig.coordinator.mode_requested("capable", lambda: forwarded.append("capable") or True) is True
    assert forwarded == ["capable"]
    rig.still_expanded()
    assert rig.host.cancel_custom_layout_session()
    rig.still_expanded()
