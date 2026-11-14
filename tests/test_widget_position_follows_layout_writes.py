"""A Widgets page built before a Layout write follows it (plan 1D.12 A).

Now Playing moved in Arrange (Layout tab) while its Widgets page was already built kept
showing its old named position, and the page's next save wrote that stale position back
over the CUSTOM route. Reset Widget Layouts had the mirror defect. The real SettingsDialog
is used, never shown: popups take a scripted answer through a patched exec.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QRect

from rendering.widget_descriptors import (
    CUSTOM_POSITION_OPTION_LABEL,
    get_widget_position_option_labels,
    has_saved_custom_layout_for_widget,
)
from ui.styled_popup import StyledPopup

pytestmark = pytest.mark.usefixtures("qt_app")


def _always(monkeypatch, answer):
    def fake_exec(popup):
        popup._result_value = answer
        return 1
    monkeypatch.setattr(StyledPopup, "exec", fake_exec)


@pytest.fixture
def dialog(tmp_path):
    from core.animation.animator import AnimationManager
    from core.settings.settings_manager import SettingsManager
    from ui.settings_dialog import SettingsDialog

    settings = SettingsManager(organization="SRPSS_Test", application=f"layout_write_{tmp_path.name}",
                               storage_base_dir=tmp_path)
    settings.set("sources.folders", [str(tmp_path)])
    widgets = settings.get("widgets")
    widgets["family_activation"]["media"] = True
    widgets["family_activation"]["clocks"] = True
    widgets["media"].update(enabled=True, monitor="ALL")
    widgets["clock"].update(enabled=True, monitor="ALL")
    # Weather's page is built but the widget is off: Arrange never places it.
    widgets["family_activation"]["weather"] = True
    widgets["weather"]["enabled"] = False
    settings.set("widgets", widgets)
    animations = AnimationManager()
    result = SettingsDialog(settings, animations)
    yield result
    result.deleteLater()
    animations.cleanup()


def _widget_page(dialog, section):
    dialog._switch_tab(dialog._tab_index_for_key("widgets"), animate=False)
    tab = dialog.widgets_tab
    index = tab._widget_section_index(section)
    tab._subtab_group.button(index).setChecked(True)
    tab._on_subtab_clicked(index)
    assert tab._current_subtab == index
    return tab


def _arrange_move_and_apply(dialog, widget_id):
    dialog._switch_tab(dialog._tab_index_for_key("layout"), animate=False)
    layout = dialog.layout_tab
    layout.arrange_toggle.setChecked(True)
    arrange = layout.arrange
    items = [item for item in arrange.model.session.items() if item.model_identity == widget_id]
    assert items, f"{widget_id} is not arrangeable with this activation"
    item = items[0]
    arrange.model.move(item.source_key, QRect(item.current_global_rect).translated(40, 20), snap=False)
    arrange._pending_changed()
    assert arrange.apply() is True


def _custom_index(combo):
    return combo.findText(CUSTOM_POSITION_OPTION_LABEL)


def _is_custom(text: str) -> bool:
    return text.strip().lower() == CUSTOM_POSITION_OPTION_LABEL.lower()


def test_now_playing_moved_in_arrange_reads_custom_on_its_built_page(dialog):
    tab = _widget_page(dialog, "media")
    combo = tab.media_position
    assert not _is_custom(combo.currentText())
    assert not combo.model().item(_custom_index(combo)).isEnabled()

    _arrange_move_and_apply(dialog, "media")
    widgets = dialog._settings.get("widgets")
    assert _is_custom(widgets["media"]["position"])
    assert has_saved_custom_layout_for_widget("media", widgets)

    _widget_page(dialog, "media")
    assert _is_custom(combo.currentText())
    assert combo.model().item(_custom_index(combo)).isEnabled()

    # An unrelated edit on that page never writes a stale named position back.
    tab.media_font_size.setValue(tab.media_font_size.value() + 1)
    tab.flush_pending_changes()
    assert _is_custom(dialog._settings.get("widgets.media.position"))


def test_a_named_position_afterwards_keeps_the_saved_custom_geometry(dialog):
    tab = _widget_page(dialog, "media")
    _arrange_move_and_apply(dialog, "media")
    _widget_page(dialog, "media")
    named = next(label for label in get_widget_position_option_labels("media") if not _is_custom(label))
    tab.media_position.setCurrentText(named)
    tab.flush_pending_changes()
    widgets = dialog._settings.get("widgets")
    assert widgets["media"]["position"] == named
    assert has_saved_custom_layout_for_widget("media", widgets)
    assert tab.media_position.model().item(_custom_index(tab.media_position)).isEnabled()


def test_reset_widget_layouts_leaves_custom_on_the_built_page(dialog, monkeypatch):
    tab = _widget_page(dialog, "media")
    _arrange_move_and_apply(dialog, "media")
    _widget_page(dialog, "media")
    assert _is_custom(tab.media_position.currentText())

    _always(monkeypatch, "yes")
    dialog._switch_tab(dialog._tab_index_for_key("layout"), animate=False)
    dialog.layout_tab.reset_layouts()
    widgets = dialog._settings.get("widgets")
    assert not _is_custom(widgets["media"]["position"])

    _widget_page(dialog, "media")
    assert tab.media_position.currentText() == widgets["media"]["position"]
    tab.media_font_size.setValue(tab.media_font_size.value() + 1)
    tab.flush_pending_changes()
    assert not _is_custom(dialog._settings.get("widgets.media.position"))


def test_a_widget_with_no_saved_custom_layout_never_offers_custom(dialog):
    """Negative control: the reload enables CUSTOM only where geometry was saved.

    CUSTOM is global, so Apply also places every other box on the canvas; a widget that is
    off is never placed and its page must not offer CUSTOM.
    """
    tab = _widget_page(dialog, "weather")
    _widget_page(dialog, "media")
    _arrange_move_and_apply(dialog, "media")
    assert not has_saved_custom_layout_for_widget("weather", dialog._settings.get("widgets"))
    _widget_page(dialog, "weather")
    combo = tab.weather_position
    assert not _is_custom(combo.currentText())
    assert not combo.model().item(_custom_index(combo)).isEnabled()


def test_a_fresh_dialog_reads_custom_from_saved_geometry(dialog, tmp_path):
    from core.animation.animator import AnimationManager
    from ui.settings_dialog import SettingsDialog

    _arrange_move_and_apply(dialog, "media")
    animations = AnimationManager()
    fresh = SettingsDialog(dialog._settings, animations)
    try:
        tab = _widget_page(fresh, "media")
        assert _is_custom(tab.media_position.currentText())
    finally:
        fresh.deleteLater()
        animations.cleanup()
