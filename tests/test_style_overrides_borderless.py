"""Themes -> Widget Themes "Borderless": a latch on the real SettingsDialog.

The control lives on the Themes tab and writes ``widgets.global.borderless``; the Widgets tab (General -> Style
Overrides) only releases it.

Latch, every un-latch path (Reset Colours, the border width, each surface choice), persistence across a reload,
and what the latch does to the resolvers every card reads. No preset or default value is pinned: widths and
materials are derived from the combos' own items and the canonical contract.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from core.animation import AnimationManager
from core.settings.default_contract import (
    resolve_card_border_width_px,
    resolve_card_border_width_setting_px,
    resolve_widgets_borderless,
)
from core.settings.settings_manager import SettingsManager
from ui.settings_dialog import SettingsDialog
from ui.styled_popup import StyledPopup


@pytest.fixture
def manager(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    # The Reset confirmation answers yes; nothing else in these tests opens a popup.
    monkeypatch.setattr(StyledPopup, "question", staticmethod(lambda *a, **k: True))
    manager = SettingsManager(application="borderless_latch", storage_base_dir=tmp_path)
    yield manager
    assert manager.flush(timeout=5.0)


def _open(manager):
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    dialog._switch_tab(dialog._tab_index_for_key("widgets"), animate=False)
    for _ in range(5):
        QCoreApplication.processEvents()
    tab = dialog.widgets_tab
    if getattr(tab, "card_border_width_spin", None) is None:
        tab._btn_defaults.click()
        for _ in range(5):
            QCoreApplication.processEvents()
    assert tab.card_border_width_spin is not None
    dialog._switch_tab(dialog._tab_index_for_key("themes"), animate=False)
    for _ in range(5):
        QCoreApplication.processEvents()
    return dialog, tab


def _close(dialog):
    dialog.close()
    QCoreApplication.processEvents()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()


def _btn(tab):
    return tab.window().themes_tab.borderless_btn


def _stored(manager) -> bool:
    return resolve_widgets_borderless(manager.get("widgets", {}))


def _latch(tab):
    _btn(tab).click()
    tab._save_settings_now()
    assert _btn(tab).isChecked()
    assert _stored_from(tab)


def _stored_from(tab):
    return resolve_widgets_borderless(tab._settings.get("widgets", {}))


def test_the_control_lives_on_themes_and_not_on_widgets(manager):
    dialog, tab = _open(manager)
    try:
        themes = dialog.themes_tab
        assert themes.borderless_btn.isCheckable()
        assert themes.widget_themes_pill is not None
        assert themes._page_stack.widget(1).isAncestorOf(themes.borderless_btn)
        assert getattr(tab, "borderless_btn", None) is None
        assert not [b for b in tab.findChildren(type(themes.borderless_btn)) if b.text() == "Borderless"]
        assert getattr(tab, "borderless_btn", None) is None
    finally:
        _close(dialog)


def test_toggling_saves_the_key_without_the_widgets_tab(manager):
    dialog, tab = _open(manager)
    try:
        dialog.themes_tab.borderless_btn.click()
        assert _stored(manager)
        dialog.themes_tab.borderless_btn.click()
        assert not _stored(manager)
    finally:
        _close(dialog)


def test_latch_persists_and_resolvers_draw_no_border(manager):
    dialog, tab = _open(manager)
    try:
        assert not _btn(tab).isChecked()
        assert _btn(tab).isCheckable()
        _latch(tab)
        widgets = manager.get("widgets", {})
        assert resolve_widgets_borderless(widgets)
        assert resolve_card_border_width_px(widgets) == 0.0
        # The stored width stays what the spin shows, so un-latching restores it.
        assert resolve_card_border_width_setting_px(widgets) == tab.card_border_width_spin.value()
    finally:
        _close(dialog)


def test_latch_survives_a_reload(manager):
    dialog, tab = _open(manager)
    try:
        _latch(tab)
    finally:
        _close(dialog)
    dialog, tab = _open(manager)
    try:
        assert _btn(tab).isChecked()
        assert _stored(manager)
    finally:
        _close(dialog)


def test_reset_colours_unlatches(manager):
    from ui.tabs.widgets_tab_defaults import _on_reset_family_colors_to_theme
    dialog, tab = _open(manager)
    try:
        _latch(tab)
        _on_reset_family_colors_to_theme(tab)
        for _ in range(3):
            QCoreApplication.processEvents()
        assert not _btn(tab).isChecked()
        assert not _stored(manager)
    finally:
        _close(dialog)


def test_editing_the_border_width_unlatches(manager):
    dialog, tab = _open(manager)
    try:
        _latch(tab)
        spin = tab.card_border_width_spin
        spin.setValue(spin.value() + 1 if spin.value() < spin.maximum() else spin.value() - 1)
        tab._save_settings_now()
        assert not _btn(tab).isChecked()
        assert not _stored(manager)
    finally:
        _close(dialog)


@pytest.mark.parametrize("combo_attr", ["surface_material_combo", "border_surface_mode_combo",
                                        "header_surface_mode_combo"])
def test_each_surface_choice_unlatches(manager, combo_attr):
    dialog, tab = _open(manager)
    try:
        _latch(tab)
        combo = getattr(tab, combo_attr)
        combo.setCurrentIndex((combo.currentIndex() + 1) % combo.count())
        tab._save_settings_now()
        assert not _btn(tab).isChecked()
        assert not _stored(manager)
    finally:
        _close(dialog)


def test_a_reload_does_not_unlatch_through_the_controls_it_refills(manager):
    """Loading refills the width and surface controls programmatically; that is not an edit."""
    dialog, tab = _open(manager)
    try:
        _latch(tab)
        tab.load_from_settings()
        for _ in range(3):
            QCoreApplication.processEvents()
        assert _btn(tab).isChecked()
        assert _stored(manager)
    finally:
        _close(dialog)


def test_a_latched_button_reads_clearly_inset(manager):
    """Checked is a darker fill than resting, by a margin visible at a glance, plus an inner shadow."""
    from ui.widgets.outlined_button import OutlinedButton

    button = OutlinedButton("Borderless", role="secondary")
    button.setCheckable(True)
    button.resize(110, 32)

    def luma(point):
        c = button.grab().toImage().pixelColor(*point)
        return 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()

    fill_point, shadow_point = (8, 16), (10, 6)  # beside the label; just inside the top-left rim
    resting = luma(fill_point)
    button.setChecked(True)
    assert luma(fill_point) <= resting * 0.7  # the earlier pressed-token fill was 0.78 of resting
    assert luma(shadow_point) < luma(fill_point) - 5  # the shadow lies on the top-left inner edge


def _family_models(widgets):
    """Every ordinary family's presentation model built from ``widgets`` by the real adapters."""
    from rendering.quick.widgets import family_binder
    from core.settings.default_contract import require_canonical_default

    shadows = require_canonical_default("widgets.shadows")
    models = {}
    for adapter_cls, widget_id in (
            (family_binder.ClockFamilyAdapter, "clock"), (family_binder.WeatherFamilyAdapter, "weather"),
            (family_binder.RedditFamilyAdapter, "reddit"), (family_binder.FeedFamilyAdapter, "feeds_custom_1"),
            (family_binder.GmailFamilyAdapter, "gmail"),
            (family_binder.AchievementPulseFamilyAdapter, "achievement_pulse"),
            (family_binder.AbandonmentIssuesFamilyAdapter, "abandonment_issues"),
            (family_binder.FriendPulseFamilyAdapter, "friend_pulse"),
            (family_binder.SystemStatsFamilyAdapter, "system_stats"),
            (family_binder.MediaFamilyAdapter, "media")):
        adapter = adapter_cls.__new__(adapter_cls)
        models[widget_id] = adapter.presentation_model(
            widget_id=widget_id, widgets_config=widgets, shadow_values=shadows)
    return models


def _border_values(obj):
    import dataclasses
    found = {}
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for field in dataclasses.fields(obj):
            value = getattr(obj, field.name)
            if ("border" in field.name or "outline" in field.name) and isinstance(value, tuple) and len(value) == 4:
                found[field.name] = value
            elif dataclasses.is_dataclass(value):
                found.update({f"{field.name}.{k}": v for k, v in _border_values(value).items()})
    return found


def test_the_built_family_configs_carry_invisible_borders_and_nothing_else_changes():
    from copy import deepcopy
    import dataclasses

    from core.settings.default_contract import require_canonical_default

    widgets = deepcopy(require_canonical_default("widgets"))
    # An authored border colour must not survive the latch.
    for section in ("clock", "media", "gmail"):
        if isinstance(widgets.get(section), dict) and "border_color" in widgets[section]:
            widgets[section]["border_color"] = [10, 20, 30, 200]
    open_models = _family_models(widgets)
    latched = deepcopy(widgets)
    latched["global"]["borderless"] = True
    shut_models = _family_models(latched)
    assert open_models and open_models.keys() == shut_models.keys()
    seen = 0
    for widget_id, shut in shut_models.items():
        open_cfg, shut_cfg = open_models[widget_id].config, shut.config
        assert shut.style.card_style.border_width == 0.0
        shut_borders = _border_values(shut_cfg)
        for name, value in _border_values(open_cfg).items():
            assert shut_borders[name][3] == 0, (widget_id, name)
            assert shut_borders[name][:3] == value[:3], (widget_id, name)
            seen += 1
        # Everything that is not a border field is identical.
        for field in dataclasses.fields(open_cfg):
            if "border" in field.name or "outline" in field.name or dataclasses.is_dataclass(getattr(open_cfg, field.name)):
                continue
            assert getattr(shut_cfg, field.name) == getattr(open_cfg, field.name), (widget_id, field.name)
    assert seen


def test_hide_borders_touches_only_border_colour_tuples():
    import dataclasses
    from rendering.quick.widgets.theme_projection import hide_borders

    @dataclasses.dataclass(frozen=True)
    class Inner:
        outline_color: tuple = (1, 2, 3, 4)

    @dataclasses.dataclass(frozen=True)
    class Config:
        border_color: tuple = (10, 20, 30, 200)
        header_border_color: tuple = (5, 6, 7, 255)
        border_opacity: float = 0.5
        show_header_border: bool = True
        text_color: tuple = (9, 9, 9, 255)
        inner: Inner = Inner()

    out = hide_borders(Config())
    assert out.border_color == (10, 20, 30, 0) and out.header_border_color == (5, 6, 7, 0)
    assert out.inner.outline_color == (1, 2, 3, 0)
    assert (out.border_opacity, out.show_header_border, out.text_color) == (0.5, True, (9, 9, 9, 255))
