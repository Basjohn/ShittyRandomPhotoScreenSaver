"""Widgets -> General -> Style Overrides "Borderless": a latch on the real SettingsDialog.

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
    if getattr(tab, "borderless_btn", None) is None:
        tab._btn_defaults.click()
        for _ in range(5):
            QCoreApplication.processEvents()
    assert tab.borderless_btn is not None
    return dialog, tab


def _close(dialog):
    dialog.close()
    QCoreApplication.processEvents()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()


def _stored(manager) -> bool:
    return resolve_widgets_borderless(manager.get("widgets", {}))


def _latch(tab):
    tab.borderless_btn.click()
    tab._save_settings_now()
    assert tab.borderless_btn.isChecked()


def test_latch_persists_and_resolvers_draw_no_border(manager):
    dialog, tab = _open(manager)
    try:
        assert not tab.borderless_btn.isChecked()
        assert tab.borderless_btn.isCheckable()
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
        assert tab.borderless_btn.isChecked()
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
        assert not tab.borderless_btn.isChecked()
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
        assert not tab.borderless_btn.isChecked()
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
        assert not tab.borderless_btn.isChecked()
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
        assert tab.borderless_btn.isChecked()
        assert _stored(manager)
    finally:
        _close(dialog)


def test_border_roles_resolve_invisible_while_latched_even_when_authored():
    from rendering.quick.widgets.theme_projection import is_border_role, resolve_rgba_role
    from ui.widget_theme_active import get_widgets_borderless, set_widgets_borderless

    authored = (10, 20, 30, 200)
    assert not get_widgets_borderless()
    try:
        assert resolve_rgba_role("media.volume.outline", local_roles=None, fallback=authored,
                                 explicit=authored) == authored
        set_widgets_borderless(True)
        assert resolve_rgba_role("media.volume.outline", local_roles=None, fallback=authored,
                                 explicit=authored)[3] == 0
        assert resolve_rgba_role("system_stats.metric.border", local_roles=None, fallback=authored)[3] == 0
        # A non-border role is untouched.
        assert resolve_rgba_role("media.volume.fill", local_roles=None, fallback=authored,
                                 explicit=authored) == authored
        assert is_border_role("gmail.header.border") and not is_border_role("gmail.header.fill")
    finally:
        set_widgets_borderless(False)
