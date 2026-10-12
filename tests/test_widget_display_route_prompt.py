"""Leaving a widget's Settings page while one of its widgets shows only on a display that is not
enabled asks Switch For Me / Trust Me Bro, on every way out (Widgets page, another tab, Guided
Setup, closing Settings), as Arrange does; closing the popup stays.

No window is shown: the popup's exec is replaced by the operator's choice, the dialog reports
itself visible so its leave checks run, and the display count is patched.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.display_selection import (
    describe_monitors,
    enabled_monitor_numbers,
    selected_monitor_numbers,
)
from rendering.widget_descriptors import route_widgets_to_single_monitor, widgets_routed_off_monitors
from ui.styled_popup import StyledPopup

pytestmark = pytest.mark.usefixtures("qt_app")


def test_the_display_selection_parser():
    assert selected_monitor_numbers("ALL", 3) == {1, 2, 3}
    assert selected_monitor_numbers("all", 2) == {1, 2}
    assert selected_monitor_numbers("NONE", 2) == frozenset()
    assert selected_monitor_numbers([2, 5], 3) == {2}                 # absent displays are ignored
    assert selected_monitor_numbers("[1, 3]", 3) == {1, 3}             # historical string form
    for broken in ([4], [], "garbage", 7, ["x"]):
        assert selected_monitor_numbers(broken, 3) is None             # repaired by the caller
    canonical = enabled_monitor_numbers(DEFAULT_SETTINGS["display"]["show_on_monitors"], 2)
    assert enabled_monitor_numbers([9], 2) == canonical and enabled_monitor_numbers([2], 2) == {2}
    assert describe_monitors({2}) == "Display 2" and describe_monitors({3, 2}) == "Displays 2 and 3"


def _widgets(**routes):
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    for widget_id, route in routes.items():
        widgets[widget_id].update(enabled=True, monitor=route)
    return widgets


def test_only_widgets_that_are_on_and_routed_off_every_enabled_display_count():
    widgets = _widgets(clock="2", clock2="ALL", clock3="1")
    assert widgets_routed_off_monitors(widgets, ("clock", "clock2", "clock3"), {1}) == ("clock",)
    assert widgets_routed_off_monitors(widgets, ("clock",), {1, 2}) == ()
    widgets["clock"]["enabled"] = False
    assert widgets_routed_off_monitors(widgets, ("clock",), {1}) == ()
    widgets["clock"]["enabled"] = True
    widgets["family_activation"]["clocks"] = False
    assert widgets_routed_off_monitors(widgets, ("clock",), {1}) == ()
    # Ids without a monitor route (a family key) are skipped, never an error.
    assert widgets_routed_off_monitors(widgets, ("feeds", "defaults"), {1}) == ()


def test_switching_moves_only_the_named_widgets():
    widgets = _widgets(clock="2", weather="2")
    assert route_widgets_to_single_monitor(widgets, 1, ("clock",)) == ("clock",)
    assert widgets["clock"]["monitor"] == "1" and widgets["weather"]["monitor"] == "2"


def test_physical_routes_follow_their_display_after_indices_shift():
    widgets = _widgets(clock="1", weather="2")
    widgets["monitor_bindings"] = {
        "clock": {"monitor": "1", "screen": "serial:MSI"},
        "weather": {"monitor": "2", "screen": "serial:LG"},
    }
    assert widgets_routed_off_monitors(
        widgets, ("clock", "weather"), {1}, screen_identities=("serial:LG",)
    ) == ("clock",)


def test_explicit_switch_rebinds_same_number_and_keeps_other_assignments():
    widgets = _widgets(clock="1", weather="2", clock2="ALL")
    widgets["monitor_bindings"] = {
        "clock": {"monitor": "1", "screen": "serial:MSI"},
        "weather": {"monitor": "2", "screen": "serial:LG"},
    }
    changed = route_widgets_to_single_monitor(
        widgets, 1, ("clock", "clock2"), screen_identities=("serial:LG",)
    )
    assert changed == ("clock",)
    assert widgets["clock"]["monitor"] == "1"
    assert widgets["monitor_bindings"]["clock"] == {"monitor": "1", "screen": "serial:LG"}
    assert widgets["monitor_bindings"]["weather"] == {"monitor": "2", "screen": "serial:LG"}
    assert widgets["clock2"]["monitor"] == "ALL"
    assert route_widgets_to_single_monitor(
        widgets, 1, ("clock",), screen_identities=("serial:LG",)
    ) == ()


def test_explicit_switch_captures_a_numbered_route_without_metadata():
    widgets = _widgets(clock="1")
    assert route_widgets_to_single_monitor(
        widgets, 1, ("clock",), screen_identities=("serial:LG",)
    ) == ("clock",)
    assert widgets["monitor_bindings"]["clock"] == {"monitor": "1", "screen": "serial:LG"}


def test_explicit_switch_updates_authored_restore_identity_even_when_number_matches():
    from rendering.custom_layout_contract import (
        load_custom_layout_restore_map, get_custom_layout_restore_entry,
        set_custom_layout_restore_entry, write_custom_layout_restore_map,
    )

    widgets = _widgets(clock="1")
    widgets["monitor_bindings"] = {"clock": {"monitor": "1", "screen": "serial:MSI"}}
    restore = load_custom_layout_restore_map(widgets)
    set_custom_layout_restore_entry(
        restore, "clock", position="Top Right", monitor="1", screen="serial:MSI",
    )
    write_custom_layout_restore_map(widgets, restore)
    route_widgets_to_single_monitor(widgets, 1, ("clock",), screen_identities=("serial:LG",))
    assert get_custom_layout_restore_entry(load_custom_layout_restore_map(widgets), "clock") == {
        "position": "Top Right", "monitor": "1", "screen": "serial:LG",
    }


class _Settings:
    def __init__(self, show_on, **routes):
        self.values = {"widgets": _widgets(**routes), "display": {"show_on_monitors": show_on}}
        self.writes = []

    def get(self, key, default=None):
        value = self.values
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return deepcopy(default)
            value = value[part]
        return deepcopy(value)

    def set(self, key, value):
        self.writes.append(key)
        self.values[key] = deepcopy(value)


def _answer(monkeypatch, answers, asked):
    """Each popup takes the next answer (None = closed without choosing)."""
    def fake_exec(popup):
        asked.append(popup)
        popup._result_value = answers.pop(0)
        return 1
    monkeypatch.setattr(StyledPopup, "exec", fake_exec)


@pytest.fixture
def two_displays(monkeypatch):
    import ui.widget_display_routes as routes

    monkeypatch.setattr(routes.QGuiApplication, "screens", staticmethod(lambda: [object(), object()]))


def test_the_guard_switches_trusts_or_stays(monkeypatch, two_displays):
    from ui.widget_display_routes import DisplayRouteLeaveGuard

    asked, switched = [], []
    settings = _Settings([1], clock="2")
    guard = DisplayRouteLeaveGuard(settings)

    _answer(monkeypatch, [None], asked)
    assert guard.resolve(None, ("clock", "clock2")) is False and settings.writes == []
    assert "Clock" in asked[-1]._message and "Display 2" in asked[-1]._message

    _answer(monkeypatch, ["trust"], asked)
    assert guard.resolve(None, ("clock",)) is True and settings.writes == []
    assert guard.resolve(None, ("clock",)) is True and len(asked) == 2      # trusted: not asked again
    settings.values["widgets"]["clock"]["monitor"] = "3"                    # a different arrangement
    _answer(monkeypatch, ["switch"], asked)
    assert guard.resolve(None, ("clock",), on_switched=lambda: switched.append(1)) is True
    assert len(asked) == 3 and switched == [1]
    assert settings.values["widgets"]["clock"]["monitor"] == "1"


def test_nothing_is_asked_when_every_widget_can_show(monkeypatch, two_displays):
    from ui.widget_display_routes import DisplayRouteLeaveGuard

    asked = []
    _answer(monkeypatch, ["switch"], asked)
    for settings in (_Settings("ALL", clock="2"), _Settings([1, 2], clock="2"), _Settings([2], clock="ALL")):
        assert DisplayRouteLeaveGuard(settings).resolve(None, ("clock", "clock2", "clock3")) is True
    assert asked == []


def test_guard_switches_absent_physical_assignment_even_with_same_display_number(monkeypatch):
    import ui.widget_display_routes as routes

    monkeypatch.setattr(routes.QGuiApplication, "screens", staticmethod(lambda: [object()]))
    monkeypatch.setattr(routes, "current_screen_identities", lambda: ("serial:LG",))
    settings = _Settings([1], clock="1", weather="2")
    settings.values["widgets"]["monitor_bindings"] = {
        "clock": {"monitor": "1", "screen": "serial:MSI"},
        "weather": {"monitor": "2", "screen": "serial:LG"},
    }
    asked = []
    _answer(monkeypatch, ["switch"], asked)
    guard = routes.DisplayRouteLeaveGuard(settings)
    # The surviving LG widget is already visible despite retaining its old number.
    assert guard.resolve(None, ("weather",)) is True and asked == []
    assert guard.resolve(None, ("clock",)) is True and len(asked) == 1
    assert settings.values["widgets"]["monitor_bindings"]["clock"] == {
        "monitor": "1", "screen": "serial:LG",
    }
    assert guard.resolve(None, ("clock",)) is True and len(asked) == 1


@pytest.fixture
def dialog(tmp_path, monkeypatch, two_displays):
    from core.animation.animator import AnimationManager
    from core.settings.settings_manager import SettingsManager
    from ui.settings_dialog import SettingsDialog

    settings = SettingsManager(organization="SRPSS_Test", application=f"display_route_{tmp_path.name}",
                               storage_base_dir=tmp_path)
    settings.set("sources.folders", [str(tmp_path)])   # an image source: close reaches the leave checks
    settings.set("display.show_on_monitors", [1])
    widgets = settings.get("widgets")
    widgets["family_activation"]["clocks"] = True
    widgets["clock"].update(enabled=True, monitor="2")
    settings.set("widgets", widgets)
    animations = AnimationManager()
    result = SettingsDialog(settings, animations)
    result.isVisible = lambda: True   # never shown; its leave checks apply as if it were
    yield result
    result.deleteLater()
    animations.cleanup()


def _clock_page(dialog):
    index = dialog._tab_index_for_key("widgets")
    dialog._switch_tab(index, animate=False)
    tab = dialog.widgets_tab
    clock = tab._widget_section_index("clock")
    tab._subtab_group.button(clock).setChecked(True)
    tab._on_subtab_clicked(clock)
    assert tab._current_subtab == clock
    return index, tab, clock


def test_every_way_out_of_the_page_asks_and_stays_when_the_popup_is_closed(dialog, monkeypatch):
    index, tab, clock = _clock_page(dialog)
    asked = []
    _answer(monkeypatch, [None, None, None, None], asked)

    dialog._switch_tab(0, animate=False)
    assert len(asked) == 1 and dialog.content_stack.currentIndex() == index
    assert dialog.tab_buttons[index].isChecked()

    weather = tab._widget_section_index("weather")
    tab._subtab_group.button(weather).setChecked(True)
    tab._on_subtab_clicked(weather)
    assert len(asked) == 2 and tab._current_subtab == clock
    assert tab._subtab_group.button(clock).isChecked()

    assert dialog.close() is False
    assert len(asked) == 3

    dialog.run_guided_setup()
    assert len(asked) == 4 and dialog._guided_setup_panel is None


def test_switch_for_me_moves_the_widget_and_the_page_follows(dialog, monkeypatch):
    index, tab, _clock = _clock_page(dialog)
    asked = []
    _answer(monkeypatch, ["switch"], asked)
    dialog._switch_tab(0, animate=False)
    assert len(asked) == 1 and dialog.content_stack.currentIndex() == 0
    assert dialog._settings.get("widgets.clock.monitor") == "1"
    assert tab.clock_monitor_combo.currentText() == "1"      # the page reloaded: no stale save back
    tab.flush_pending_changes()
    assert dialog._settings.get("widgets.clock.monitor") == "1"


def test_trust_me_bro_leaves_without_changing_anything(dialog, monkeypatch):
    _index, tab, _clock = _clock_page(dialog)
    asked = []
    _answer(monkeypatch, ["trust"], asked)
    weather = tab._widget_section_index("weather")
    tab._subtab_group.button(weather).setChecked(True)
    tab._on_subtab_clicked(weather)
    assert len(asked) == 1 and tab._current_subtab == weather
    assert dialog._settings.get("widgets.clock.monitor") == "2"


def test_leaving_visualizers_asks_about_a_visualizer_on_a_disabled_display(dialog, monkeypatch):
    widgets = dialog._settings.get("widgets")
    for key in ("media", "spotify_visualizer"):      # wherever its effective route lives
        widgets[key].update(enabled=True, monitor="2")
    widgets["clock"]["monitor"] = "1"
    dialog._settings.set("widgets", widgets)
    index = dialog._tab_index_for_key("visualizers")
    dialog._switch_tab(index, animate=False)
    if dialog.content_stack.currentIndex() != index:
        pytest.skip("Visualizers is not admitted with the default family activation")
    asked = []
    _answer(monkeypatch, [None, "trust"], asked)
    dialog._switch_tab(0, animate=False)
    assert len(asked) == 1 and dialog.content_stack.currentIndex() == index
    dialog._switch_tab(0, animate=False)
    assert len(asked) == 2 and dialog.content_stack.currentIndex() == 0


def test_the_saver_selects_displays_through_the_same_parser():
    from types import SimpleNamespace

    from engine.display_manager import DisplayManager

    def allowed(raw, count):
        owner = SimpleNamespace(settings_manager=SimpleNamespace(get=lambda _key: raw))
        return DisplayManager._get_allowed_screen_indices(owner, count)

    assert allowed("ALL", 3) == {0, 1, 2} and allowed([2, 3], 3) == {1, 2} and allowed("NONE", 2) == set()
    assert allowed([7], 2) == {n - 1 for n in enabled_monitor_numbers([7], 2)}     # canonical repair
