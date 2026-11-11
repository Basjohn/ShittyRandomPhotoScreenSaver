"""1B.11 side defects: the Weather page's location autocomplete uses Settings' one themed completer popup (shared
with the theme filter, never Qt's default list), and its service note draws in the theme's success role instead of
a fixed green. Driven through the real SettingsDialog (never shown) on a temporary profile; no network (the
geocoder's lookups are stubbed). Expectations derive from the active theme's tokens, never pinned colours.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel

pytestmark = pytest.mark.qt

THEMES = sorted((Path(__file__).resolve().parents[1] / "themes").glob("*.srtheme"))


@pytest.fixture
def weather(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from core.animation import AnimationManager
    from core.settings.settings_manager import SettingsManager
    from ui.settings_dialog import SettingsDialog
    from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
    from ui.styled_popup import StyledPopup
    from ui.widgets.geocode_completer import GeocodeCompleter

    monkeypatch.setattr(StyledPopup, "exec", lambda popup: setattr(popup, "_result_value", None))
    lookups = []
    monkeypatch.setattr(GeocodeCompleter, "_fetch_cities",
                        staticmethod(lambda query, should_continue=None: lookups.append(query) or []))
    before = get_active_settings_theme()
    manager = SettingsManager(application="weather_completer", storage_base_dir=tmp_path / "profile")
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    tab = dialog._get_tab_instance("widgets")
    index = next(i for i, d in enumerate(tab._widget_section_descriptors) if d.section_id == "weather")
    if getattr(tab, "_lazy_sections", False):
        tab._build_lazy_subtab_content(index)
    try:
        yield tab
    finally:
        dialog.close()
        QCoreApplication.processEvents()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QCoreApplication.processEvents()
        assert manager.flush(timeout=5.0)
        set_active_settings_theme(before)


def _note(tab) -> QLabel:
    return next(label for label in tab.findChildren(QLabel) if label.objectName() == "weatherServiceNote")


def _qss_color(label: QLabel) -> QColor:
    sheet = label.styleSheet()
    value = sheet.rsplit("color:", 1)[1].split(";", 1)[0].strip()
    return QColor(value)


def test_the_location_completer_uses_the_theme_filters_popup(weather):
    from ui.widgets.theme_filter import ThemedCompleterPopup
    popup = weather._geocode_completer.popup()
    assert type(popup) is ThemedCompleterPopup                     # the shared class, not a copy
    assert popup.property("customComboPopup")


def test_the_service_note_follows_the_themes_success_role(weather):
    from ui.settings_theme_io import load_settings_theme_file
    from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
    note = _note(weather)
    seen = set()
    for path in THEMES:
        theme = load_settings_theme_file(path)
        success = theme.color("popup.icon.success")
        if (success.r, success.g, success.b) in seen:
            continue
        set_active_settings_theme(theme)
        QCoreApplication.processEvents()
        drawn = _qss_color(note)
        assert (drawn.red(), drawn.green(), drawn.blue()) == (success.r, success.g, success.b), path.name
        seen.add((success.r, success.g, success.b))
        if len(seen) == 2:
            break
    assert len(seen) == 2, "needs two themes with different success roles to show the note follows the theme"
    assert get_active_settings_theme() is not None
