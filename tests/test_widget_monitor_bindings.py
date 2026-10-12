"""Hotplug cannot turn another physical display into a widget's assignment."""
from copy import deepcopy

import pytest

from core.settings import monitor_routes as routes
from core.settings.settings_manager import SettingsManager
from engine.display_manager import DisplayManager
from rendering.widget_descriptors import widget_route_admits_screen


MSI = "serial:MSI|model:Panel|name:MSI"
LG = "serial:LG|model:TV|name:LG"


def _widgets():
    return {
        "clock": {"enabled": True, "monitor": "1", "position": "Custom"},
        "clock2": {"enabled": True, "monitor": "2", "position": "Custom"},
        "media": {"monitor": "2", "position": "Custom"},
        "spotify_visualizer": {"monitor": "1", "position": "Custom"},
    }


def test_remove_first_screen_preserves_both_physical_assignments_and_restore():
    widgets = _widgets()
    widgets[routes.BINDINGS_KEY] = routes.reconcile_monitor_bindings(widgets, {}, (MSI, LG))
    original = deepcopy(widgets)
    # LG becomes index zero, but neither gains Clock 1 nor loses its own Clock 2.
    assert not widget_route_admits_screen("clock", widgets, 0, display_identity=LG)
    assert widget_route_admits_screen("clock2", widgets, 0, display_identity=LG)
    assert routes.reconcile_monitor_bindings(widgets, widgets, (LG,)) == widgets[routes.BINDINGS_KEY]
    # Return in a different enumeration order: the same identities own each card.
    assert widget_route_admits_screen("clock", widgets, 1, display_identity=MSI)
    assert widget_route_admits_screen("clock2", widgets, 0, display_identity=LG)
    assert widgets == original


@pytest.mark.parametrize("position,expected", [("Custom", MSI), ("Center", LG)])
def test_visualizer_effective_route_follows_physical_identity(monkeypatch, position, expected):
    widgets = _widgets()
    widgets["spotify_visualizer"]["position"] = position
    widgets[routes.BINDINGS_KEY] = routes.reconcile_monitor_bindings(widgets, {}, (MSI, LG))
    monkeypatch.setattr(routes, "current_screen_identities", lambda: (LG,))
    index = DisplayManager._resolve_visualizer_requested_screen_index(widgets)
    assert index == (0 if expected == LG else 1)  # absent is out of range, never ALL


def test_settings_replacement_and_restart_keep_assignment_until_route_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "current_screen_identities", lambda: (MSI, LG))
    manager = SettingsManager(application="MonitorBindingTest", storage_base_dir=tmp_path)
    manager.set_widgets_map(_widgets())
    manager.ensure_widget_monitor_bindings()
    before = manager.get_widgets_map()[routes.BINDINGS_KEY]
    monkeypatch.setattr(routes, "current_screen_identities", lambda: (LG,))
    manager.set("widgets.clock.font_size", 47)
    manager.ensure_widget_monitor_bindings()
    assert manager.get_widgets_map()[routes.BINDINGS_KEY] == before
    manager.save()
    reopened = SettingsManager(application="MonitorBindingTest", storage_base_dir=tmp_path)
    assert reopened.get_widgets_map()[routes.BINDINGS_KEY] == before
    # Explicit numeric change binds to the current physical display.
    reopened.set("widgets.clock2.monitor", "1")
    assert reopened.get_widgets_map()[routes.BINDINGS_KEY]["clock2"] == {"monitor": "1", "screen": LG}
    reopened.set("widgets.clock.monitor", "ALL")
    assert "clock" not in reopened.get_widgets_map()[routes.BINDINGS_KEY]
    assert widget_route_admits_screen("clock", reopened.get_widgets_map(), 0, display_identity=LG)


def test_first_upgrade_uses_unique_saved_custom_home_even_when_already_absent():
    widgets = _widgets()
    widgets["custom_layout"] = {"version": 2, "displays": {MSI: {"clock": {"default": {"rect": [0, 0, .2, .2]}}}}}
    bindings = routes.reconcile_monitor_bindings(widgets, widgets, (LG,))
    assert bindings["clock"]["screen"] == MSI


@pytest.mark.parametrize("malformed", [None, [], "bad"])
def test_malformed_binding_metadata_is_repaired(malformed):
    widgets = _widgets()
    widgets[routes.BINDINGS_KEY] = malformed
    assert routes.reconcile_monitor_bindings(widgets, {}, (MSI, LG))["clock"]["screen"] == MSI


def test_layout_slot_keeps_physical_assignments():
    from core.settings.layout_slots import save_layout_slot, apply_layout_slot
    widgets = _widgets()
    widgets[routes.BINDINGS_KEY] = routes.reconcile_monitor_bindings(widgets, {}, (MSI, LG))
    before = deepcopy(widgets[routes.BINDINGS_KEY])
    assert save_layout_slot(widgets, "1")
    widgets[routes.BINDINGS_KEY] = {}
    assert apply_layout_slot(widgets, "1")
    assert widgets[routes.BINDINGS_KEY] == before


@pytest.mark.parametrize("widget_id", ["clock", "system_audio_osd", "feeds_custom_1"])
def test_settings_combo_explicit_same_number_selection_reassigns(qt_app, tmp_path, monkeypatch, widget_id):
    from PySide6.QtWidgets import QWidget, QComboBox
    from ui.tabs.widgets_tab import WidgetsTab
    from rendering.widget_descriptors import feed_settings_attr_stem
    from core.feeds.config import FEED_WIDGET_IDS

    class Page(QWidget):
        _wire_monitor_assignment_controls = WidgetsTab._wire_monitor_assignment_controls
        _assign_widget_monitor = WidgetsTab._assign_widget_monitor

    monkeypatch.setattr(routes, "current_screen_identities", lambda: (MSI, LG))
    page = Page()
    page._settings = SettingsManager(application="MonitorComboTest", storage_base_dir=tmp_path)
    widgets = _widgets()
    widgets[widget_id] = {"monitor": "1", "enabled": True}
    page._settings.set_widgets_map(widgets)
    combo = QComboBox(page)
    combo.addItems(["1", "2", "ALL"])
    stem = feed_settings_attr_stem(widget_id) if widget_id in FEED_WIDGET_IDS else widget_id
    setattr(page, f"{stem}_monitor_combo", combo)
    page._wire_monitor_assignment_controls()
    page._wire_monitor_assignment_controls()  # lazy revisits must not duplicate connections
    monkeypatch.setattr(routes, "current_screen_identities", lambda: (LG,))
    assert page._settings.get_widgets_map()[routes.BINDINGS_KEY][widget_id]["screen"] == MSI
    combo.activated.emit(0)  # same text, explicit user choice of today's 1
    assert page._settings.get_widgets_map()[routes.BINDINGS_KEY][widget_id]["screen"] == LG
    page.deleteLater()
