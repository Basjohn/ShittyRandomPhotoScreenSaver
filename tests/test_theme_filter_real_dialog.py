"""1B.11: the Themes tab's type-in filter, driven through the real SettingsDialog (never shown).

The dialog reads a test-owned copy of the shipped theme tree plus one imported Settings and one imported Widget
theme written by the test. Every expectation is derived from the catalog the dialog loaded (``theme_filter_terms``
on each entry), never from pinned theme names, colours or UI wording. A temporary profile is used throughout.
"""
from __future__ import annotations

import colorsys
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

pytestmark = pytest.mark.qt

REPO_THEMES = Path(__file__).resolve().parents[1] / "themes"
PROBE_WORD = "Zephyrprobe"  # test-owned name of the imported themes


def _rgba(hue: float, value: float):
    from ui.settings_theme_spec import Rgba
    r, g, b = colorsys.hsv_to_rgb(hue / 360.0, 0.85, value)
    return Rgba(round(r * 255), round(g * 255), round(b * 255))


def _write_imported_themes(root: Path) -> None:
    """One user Settings theme and one user Widget theme, recoloured from the compiled defaults."""
    from ui.settings_theme_io import save_settings_theme_file
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NativeBackdropStyle, Rgba
    from ui.widget_theme_io import save_widget_theme_file
    from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME

    colors = dict(DEFAULT_DARK_SETTINGS_THEME.colors)
    colors.update({"panel.group.surface": _rgba(130.0, 0.25), "control.list.selected_accent": _rgba(20.0, 0.9)})
    settings = replace(DEFAULT_DARK_SETTINGS_THEME, name=f"{PROBE_WORD} Import", colors=colors,
                       backdrop=NativeBackdropStyle("smoked", Rgba(20, 30, 20, 120)))
    save_settings_theme_file(settings, root / f"{PROBE_WORD} Import.srtheme")
    widget_colors = dict(DEFAULT_DARK_WIDGET_THEME.colors)
    widget_colors.update({"card.background": _rgba(300.0, 0.25), "card.border": _rgba(185.0, 0.9)})
    widget = replace(DEFAULT_DARK_WIDGET_THEME, theme_id="zephyrprobe_import", name=f"{PROBE_WORD} Widget",
                     linked_settings_theme_id=None, colors=widget_colors, surface_material="frosted")
    save_widget_theme_file(widget, root / "widgets" / f"{PROBE_WORD} Widget.srwtheme")


@pytest.fixture
def env(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from core.animation import AnimationManager
    from core.settings.settings_manager import SettingsManager
    from ui.settings_dialog import SettingsDialog
    from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
    from ui.styled_popup import StyledPopup
    from ui.widget_theme_active import get_active_widget_theme, set_active_widget_theme

    monkeypatch.setattr(StyledPopup, "exec", lambda popup: setattr(popup, "_result_value", None))
    before = (get_active_settings_theme(), get_active_widget_theme())
    themes = tmp_path / "themes"
    (themes / "widgets").mkdir(parents=True)
    for path in REPO_THEMES.glob("*.srtheme"):
        shutil.copy2(path, themes / path.name)
    for path in (REPO_THEMES / "widgets").glob("*.srwtheme"):
        shutil.copy2(path, themes / "widgets" / path.name)
    _write_imported_themes(themes)
    manager = SettingsManager(application="theme_filter_dialog", storage_base_dir=tmp_path / "profile")
    manager.set("sources.folders", [str(tmp_path)])
    dialog = SettingsDialog(manager, AnimationManager(), themes_directory=themes)
    QCoreApplication.processEvents()
    tab = dialog._get_tab_instance("themes")
    try:
        yield dialog, tab, manager
    finally:
        dialog.close()
        QCoreApplication.processEvents()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QCoreApplication.processEvents()
        assert manager.flush(timeout=5.0)
        set_active_widget_theme(before[1])
        set_active_settings_theme(before[0])


def _pages(tab):
    from ui.settings_theme_catalog import get_current_settings_theme_catalog
    from ui.widget_theme_catalog import get_current_widget_theme_catalog
    return (("settings", tab.settings_theme_filter, tab.theme_list, get_current_settings_theme_catalog()),
            ("widgets", tab.widget_theme_filter, tab.widget_theme_list, get_current_widget_theme_catalog()))


def _rows(view):
    return [view.item(row) for row in range(view.count())]


def _id(item):
    return str(item.data(Qt.ItemDataRole.UserRole))


def _visible_ids(view):
    return {_id(item) for item in _rows(view) if not item.isHidden()}


def _catalog_terms(catalog):
    from ui.theme_semantics import theme_filter_terms
    return {entry.theme_id: theme_filter_terms(entry.theme).terms for entry in catalog.entries}


def _expected(view, catalog, query):
    """Rows the filter must show, derived from the catalog's own terms and the rows' display names."""
    from ui.theme_semantics import filter_words, theme_matches_filter
    terms = _catalog_terms(catalog)
    words = filter_words(query)
    return {_id(item) for item in _rows(view) if _id(item) in terms
            and theme_matches_filter(words, item.text(), terms[_id(item)])}


def test_typing_filters_both_pages_by_catalog_derived_kinds_and_colours(env):
    _dialog, tab, _manager = env
    for _page, field, view, catalog in _pages(tab):
        terms = _catalog_terms(catalog)
        colours = sorted({t for entry_terms in terms.values() for t in entry_terms[2:]})
        assert colours, "the catalog must yield colour families"
        everything = {_id(item) for item in _rows(view)}
        for colour in colours:
            field.clear()
            QTest.keyClicks(field, colour.lower())
            assert _visible_ids(view) == _expected(view, catalog, colour)
            assert _visible_ids(view)
        # Two words narrow together (AND): a tone and a material one real theme has.
        tone, material = next(iter(terms.values()))[:2]
        field.setText(f"{tone.upper()} {material.lower()}")
        both = _visible_ids(view)
        assert both == _expected(view, catalog, f"{tone} {material}")
        field.setText(tone)
        assert both <= _visible_ids(view)
        field.clear()
        assert _visible_ids(view) == everything


def test_filtering_never_deselects_reapplies_or_persists(env, monkeypatch):
    from ui.settings_theme_runtime import get_active_settings_theme
    from ui.theme_semantics import THEME_COLOUR_FAMILIES

    _dialog, tab, manager = env
    writes = []
    original_set = manager.set
    monkeypatch.setattr(manager, "set", lambda key, value, *a, **k: (writes.append(key), original_set(key, value, *a, **k)))
    for page, field, view, catalog in _pages(tab):
        current = view.currentItem()
        assert current is not None
        selected = view.selectedItems()
        active = get_active_settings_theme()
        spies = (QSignalSpy(view.currentItemChanged), QSignalSpy(view.itemSelectionChanged),
                 QSignalSpy(view.currentRowChanged))
        own = set(_catalog_terms(catalog).get(_id(current), ()))
        hiding = next(c for c in THEME_COLOUR_FAMILIES if c not in own and c.casefold() not in current.text().casefold()
                      and _expected(view, catalog, c))
        field.setText(hiding)
        assert current.isHidden(), f"{page}: the query must hide the active row for this test to mean anything"
        assert view.currentItem() is current and view.selectedItems() == selected
        assert get_active_settings_theme() is active
        field.setText("qqzzxx")
        assert view.visible_theme_count() == 0
        field.clear()
        assert not current.isHidden() and view.currentItem() is current
        assert all(spy.count() == 0 for spy in spies)
    assert writes == [], "the filter is view state: nothing may be written to settings"
    # Negative control: the spies do see a real selection change.
    view = tab.widget_theme_list
    spy = QSignalSpy(view.currentItemChanged)
    other = next(item for item in _rows(view) if item is not view.currentItem())
    view.setCurrentItem(other)
    assert spy.count() == 1


def test_favourites_and_linking_behave_as_without_a_filter(env):
    from ui.widgets.theme_list import FAVOURITE_ROLE, FAVOURITES_KEY, _ThemeRowDelegate
    from ui.widget_theme_selection import read_widget_theme_state

    _dialog, tab, manager = env
    _page, field, view, catalog = _pages(tab)[0]
    colour = _catalog_terms(catalog)[_id(_rows(view)[-1])][2]
    field.setText(colour)
    shown = _visible_ids(view)
    hidden = {_id(item) for item in _rows(view)} - shown
    view.resize(600, 300)
    view.doItemsLayout()
    target = next(item for item in reversed(_rows(view)) if not item.isHidden())
    star, _ = _ThemeRowDelegate.decoration_rects(view.visualItemRect(target))
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=star.center())
    assert target.data(FAVOURITE_ROLE)
    assert _id(target) in manager.get(FAVOURITES_KEY)["settings"]
    assert _visible_ids(view) == shown and hidden == {_id(item) for item in _rows(view) if item.isHidden()}
    assert _id(next(item for item in _rows(view) if not item.isHidden())) == _id(target)  # favourites first
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                     pos=_ThemeRowDelegate.decoration_rects(view.visualItemRect(target))[0].center())
    assert not target.data(FAVOURITE_ROLE) and _visible_ids(view) == shown
    # Linking with both lists filtered to nothing still pairs and selects the linked Widget Theme.
    for _p, page_field, _v, _c in _pages(tab):
        page_field.setText("qqzzxx")
    seen = set()
    for _toggle in range(2):
        tab.widget_keep_synced.setChecked(not tab.widget_keep_synced.isChecked())
        state = read_widget_theme_state(manager)
        seen.add(state.keep_synced)
        assert tab.settings_keep_synced.isChecked() == state.keep_synced == tab.widget_keep_synced.isChecked()
        assert _id(tab.widget_theme_list.currentItem()) == state.selected_id
        assert tab.widget_theme_list.visible_theme_count() == 0
    assert seen == {True, False}


def test_completer_offers_catalog_kinds_colours_and_names_and_is_themed(env):
    from ui.settings_theme_runtime import get_active_settings_theme

    _dialog, tab, _manager = env
    for _page, field, view, catalog in _pages(tab):
        model = field.completion_model().stringList()
        present = {term for entry_terms in _catalog_terms(catalog).values() for term in entry_terms}
        names = [item.text() for item in _rows(view)]
        assert set(model) == present | set(names)
        assert len(model) == len(set(word.casefold() for word in model))
        assert model.index(next(iter(names))) > max(model.index(term) for term in present)  # kinds first
        assert field.completer().completionMode().name == "PopupCompletion"
    popup = tab.settings_theme_filter.completer_popup()
    assert popup.property("customComboPopup") and popup.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    tab.settings_theme_filter.completer().setCompletionPrefix("qqzzxx")  # no rows: the body alone
    popup.resize(240, 120)
    image = popup.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)
    surface = get_active_settings_theme().color("combo.popup.surface")
    centre = image.pixelColor(image.width() // 2, image.height() // 2)
    assert abs(centre.alpha() - surface.a) <= 2
    assert max(abs(a - b) for a, b in zip(centre.getRgb()[:3], (surface.r, surface.g, surface.b))) <= 3
    corner = image.pixelColor(0, 0)
    assert corner.alpha() == 0, "rounded popup corners must be see-through, not a native square"


def test_imported_user_themes_are_filterable_and_offered(env):
    from ui.theme_semantics import theme_filter_terms

    _dialog, tab, _manager = env
    for _page, field, view, catalog in _pages(tab):
        imported = next(entry for entry in catalog.entries if PROBE_WORD in entry.name)
        terms = theme_filter_terms(imported.theme)
        field.setText(" ".join(terms.terms).lower())
        assert imported.theme_id in _visible_ids(view)
        assert _visible_ids(view) == _expected(view, catalog, " ".join(terms.terms))
        field.setText(PROBE_WORD.upper())
        assert _visible_ids(view) == {imported.theme_id}
        assert any(PROBE_WORD in word for word in field.completion_model().stringList())


def test_no_match_paints_an_empty_state_line(env):
    _dialog, tab, _manager = env
    _page, field, view, _catalog = _pages(tab)[0]
    view.resize(600, 300)
    field.setText("qqzzxx")
    assert view.visible_theme_count() == 0 and view.count() > 0
    image = view.grab().toImage()
    middle = image.height() // 2
    background = image.pixelColor(image.width() // 2, 12)
    assert any(image.pixelColor(x, y) != background
               for x in range(0, image.width(), 2) for y in range(middle - 8, middle + 8)), "empty-state text"
    field.clear()
    assert view.visible_theme_count() == view.count()
