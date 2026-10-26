"""Theme-row previews and favourites cross the real selection/persistence seam."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QListWidgetItem

from core.settings import SettingsManager
from ui.settings_theme_catalog import SettingsThemeCatalog, SettingsThemeCatalogEntry, BUILTIN_DEFAULT_THEME_ID
from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, Rgba
from ui.widget_theme_catalog import WidgetThemeCatalog, WidgetThemeCatalogEntry
from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME
from ui.widgets.theme_list import (ThemeListWidget, PALETTE_ROLE, FAVOURITE_ROLE, FAVOURITES_KEY,
                                   _ThemeRowDelegate, dominant_theme_colours)
from ui.tabs.themes_tab import ThemesTab


def test_preview_uses_prevalent_authored_colours_and_groups_near_shades():
    red, green, blue, gold = (180, 20, 20), (20, 180, 20), (20, 20, 180), (180, 150, 20)
    colours = {str(index): Rgba(*rgb) for index, rgb in enumerate((red, red, red, green, green, blue, gold))}
    colours.update(shadow=Rgba(0, 0, 0), invisible=Rgba(1, 2, 3, 0), nearby=Rgba(181, 21, 21))
    preview = dominant_theme_colours(SimpleNamespace(colors=colours))
    assert preview == (red, green, blue, gold)
    assert dominant_theme_colours(SimpleNamespace(colors={"one": Rgba(*red)})) == (red,) * 4
    assert dominant_theme_colours(SimpleNamespace(colors={"one": Rgba(*red, 0)})) == (red,) * 4


@pytest.fixture
def themed_page(qt_app, tmp_path, monkeypatch):
    settings_catalog = SettingsThemeCatalog(tuple(
        SettingsThemeCatalogEntry(identity, label, replace(DEFAULT_DARK_SETTINGS_THEME, name=label), None,
                                  is_builtin=number == 0)
        for number, (identity, label) in enumerate(((BUILTIN_DEFAULT_THEME_ID, "Default"),
                                                    ("file:alpha.srtheme", "Alpha"),
                                                    ("file:beta.srtheme", "Beta")))), ())
    widget_catalog = WidgetThemeCatalog(tuple(
        WidgetThemeCatalogEntry(identity, label, replace(DEFAULT_DARK_WIDGET_THEME, theme_id=identity, name=label), None,
                                is_builtin=number == 0)
        for number, (identity, label) in enumerate(((DEFAULT_DARK_WIDGET_THEME.theme_id, "Default"),
                                                    ("alpha", "Alpha"), ("beta", "Beta")))), ())
    monkeypatch.setattr("ui.tabs.themes_tab.get_current_widget_theme_catalog", lambda: widget_catalog)
    manager = SettingsManager(application="ThemeListPreviewTest", storage_base_dir=tmp_path / "profile")
    manager.set("ui.settings_theme_selection", BUILTIN_DEFAULT_THEME_ID)
    page = ThemesTab(manager, catalog=settings_catalog)
    yield page, manager, settings_catalog
    page.deleteLater()
    assert manager.flush(timeout=5)


def _ids(view):
    return [view.item(row).data(Qt.ItemDataRole.UserRole) for row in range(view.count())]


def test_star_click_sorts_and_persists_without_activating_a_theme(themed_page, qt_app, tmp_path):
    page, manager, catalog = themed_page
    view = page.theme_list
    view.resize(550, 240)
    view.doItemsLayout()
    current = view.currentItem()
    selected = manager.get("ui.settings_theme_selection")
    widget_state = manager.get("widget_theme")
    signals = QSignalSpy(view.currentItemChanged)
    target = view.item(2)
    star, _ = _ThemeRowDelegate.decoration_rects(view.visualItemRect(target))
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=star.center())
    assert _ids(view) == ["file:beta.srtheme", BUILTIN_DEFAULT_THEME_ID, "file:alpha.srtheme"]
    assert target.data(FAVOURITE_ROLE) and view.currentItem() is current
    assert signals.count() == 0
    assert manager.get("ui.settings_theme_selection") == selected
    assert manager.get("widget_theme") == widget_state
    assert manager.get(FAVOURITES_KEY) == {"settings": ["file:beta.srtheme"], "widgets": []}
    assert manager.flush(timeout=5)
    reopened = SettingsManager(application="ThemeListPreviewTest", storage_base_dir=tmp_path / "profile")
    second = ThemesTab(reopened, catalog=catalog)
    try:
        assert _ids(second.theme_list)[0] == "file:beta.srtheme"
    finally:
        second.deleteLater()
    # Removing the same favourite restores catalogue order, still without selection edges.
    star, _ = _ThemeRowDelegate.decoration_rects(view.visualItemRect(target))
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=star.center())
    assert _ids(view) == [entry.theme_id for entry in catalog.entries]
    assert not target.data(FAVOURITE_ROLE) and signals.count() == 0


def test_favourites_keep_catalogue_order_and_namespaces_and_custom_refresh(themed_page):
    from ui.widget_theme_io import widget_theme_to_payload

    page, manager, catalog = themed_page
    page._toggle_theme_favourite("settings", "file:beta.srtheme")
    page._toggle_theme_favourite("settings", "file:alpha.srtheme")
    assert _ids(page.theme_list)[:2] == ["file:alpha.srtheme", "file:beta.srtheme"]
    page._toggle_theme_favourite("widgets", "beta")
    assert _ids(page.widget_theme_list)[0] == "beta"
    assert manager.get(FAVOURITES_KEY)["settings"] == ["file:alpha.srtheme", "file:beta.srtheme"]
    manager.set("widget_theme.custom", widget_theme_to_payload(DEFAULT_DARK_WIDGET_THEME))
    page._refresh_widget_theme_page_from_state()
    custom = next(page.widget_theme_list.item(row) for row in range(page.widget_theme_list.count())
                  if page.widget_theme_list.item(row).text() == "Custom")
    assert len(custom.data(PALETTE_ROLE)) == 4
    edited = replace(DEFAULT_DARK_WIDGET_THEME, colors={role: Rgba(33, 110, 177)
                                                      for role in DEFAULT_DARK_WIDGET_THEME.colors})
    manager.set("widget_theme.custom", widget_theme_to_payload(edited))
    page._refresh_widget_theme_page_from_state()
    assert tuple(map(tuple, custom.data(PALETTE_ROLE))) == ((33, 110, 177),) * 4
    page._toggle_theme_favourite("widgets", custom.data(Qt.ItemDataRole.UserRole))
    page._refresh_widget_theme_page_from_state()
    assert custom.data(FAVOURITE_ROLE)
    manager.set("widget_theme.custom", None)
    page._refresh_widget_theme_page_from_state()
    assert "Custom" not in [page.widget_theme_list.item(row).text() for row in range(page.widget_theme_list.count())]


def test_long_rows_render_separate_stars_and_four_colour_squares(qt_app, tmp_path):
    view = ThemeListWidget()
    view.resize(640, 160)
    item = QListWidgetItem("A very long theme name " * 12)
    item.setData(Qt.ItemDataRole.UserRole, "fixture")
    view.add_theme_item(item, DEFAULT_DARK_SETTINGS_THEME)
    view.set_favourites({"fixture"})
    view.setCurrentItem(item)
    view.ensurePolished()
    view.doItemsLayout()
    image = QImage(view.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    view.render(image)
    assert image.save(str(tmp_path / "theme_row.png"))
    star, square = _ThemeRowDelegate.decoration_rects(view.visualItemRect(item))
    assert star.right() < square.left() and square.right() < view.viewport().width()
    signals = QSignalSpy(view.favouriteToggled)
    QTest.keyClick(view, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
    assert signals.count() == 1 and signals.at(0) == ["fixture"]
