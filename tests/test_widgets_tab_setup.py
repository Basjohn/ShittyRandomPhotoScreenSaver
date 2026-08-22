"""Widgets SETUP subtab: application-level family capability activation (Phase E2).

Proves the SETUP page lists families, toggles application-level *activation*
(distinct from per-instance ``enabled``), persists it, hides/shows the family's
settings pill live, and preserves stored configuration across deactivation.
"""
from __future__ import annotations

import pytest

from core.settings.capability_activation import is_widget_family_activated
from rendering.widget_descriptors import (
    get_widget_family_descriptors,
    get_widget_settings_section_descriptor,
    get_widget_settings_section_descriptors,
)
from ui.tabs.widgets_tab import WidgetsTab


def _make_tab(settings_manager, **kw):
    return WidgetsTab(settings_manager, lazy_sections=True, **kw)


def _family_pill(tab, family):
    descriptor = get_widget_settings_section_descriptor(
        family.settings_section_id, get_widget_settings_section_descriptors()
    )
    return getattr(tab, descriptor.button_attr_name, None)


def test_setup_is_default_landing_and_lists_families(qt_app, settings_manager):
    tab = _make_tab(settings_manager)
    try:
        # SETUP is the default landing page and is built.
        assert tab._widget_section_index("setup") == 0
        assert hasattr(tab, "_setup_container")
        # One activation checkbox per available family, with tooltips.
        families = get_widget_family_descriptors()
        assert set(tab._family_activation_checkboxes) == {f.family_id for f in families}
        for family in families:
            cb = tab._family_activation_checkboxes[family.family_id]
            assert cb.isChecked() is True  # default: all activated
            if family.description:
                assert cb.toolTip() == family.description
    finally:
        tab.deleteLater()


def test_deactivating_family_persists_and_hides_pill(qt_app, settings_manager):
    tab = _make_tab(settings_manager)
    try:
        clocks = next(f for f in get_widget_family_descriptors() if f.family_id == "clocks")
        pill = _family_pill(tab, clocks)
        assert pill is not None
        assert pill.isHidden() is False  # shown while activated

        tab._family_activation_checkboxes["clocks"].setChecked(False)
        tab._save_settings_now()

        widgets_cfg = settings_manager.get("widgets", {})
        assert is_widget_family_activated(widgets_cfg, "clocks") is False
        # Pill hidden live; other families unaffected.
        assert pill.isHidden() is True
        weather_pill = _family_pill(
            tab, next(f for f in get_widget_family_descriptors() if f.family_id == "weather")
        )
        assert weather_pill.isHidden() is False
    finally:
        tab.deleteLater()


def test_deactivating_current_family_returns_to_setup(qt_app, settings_manager):
    tab = _make_tab(settings_manager, initial_view_state={"subtab_id": "weather"})
    try:
        assert tab._current_subtab == tab._widget_section_index("weather")
        tab._family_activation_checkboxes["weather"].setChecked(False)
        # Selection fell back to SETUP rather than a hidden dead page.
        assert tab._current_subtab == tab._widget_section_index("setup")
    finally:
        tab.deleteLater()


def test_disable_all_then_enable_all_affects_activation_only(qt_app, settings_manager):
    settings_manager.set("widgets", {
        "clock": {"enabled": True, "position": "Top Right"},
        "weather": {"enabled": True, "location": "Berlin"},
    })
    tab = _make_tab(settings_manager)
    try:
        tab._set_all_family_activation(False)
        tab._save_settings_now()
        widgets_cfg = settings_manager.get("widgets", {})
        for family in get_widget_family_descriptors():
            assert is_widget_family_activated(widgets_cfg, family.family_id) is False
        # Per-instance enabled values are NOT touched by activation.
        assert widgets_cfg.get("clock", {}).get("enabled") is True
        assert widgets_cfg.get("weather", {}).get("enabled") is True

        tab._set_all_family_activation(True)
        tab._save_settings_now()
        widgets_cfg = settings_manager.get("widgets", {})
        for family in get_widget_family_descriptors():
            assert is_widget_family_activated(widgets_cfg, family.family_id) is True
        # Stored per-instance config survived the activation round-trip.
        assert widgets_cfg.get("clock", {}).get("enabled") is True
        assert widgets_cfg.get("weather", {}).get("location") == "Berlin"
    finally:
        tab.deleteLater()


def test_deactivated_family_is_not_lazily_built_or_hydrated(qt_app, settings_manager):
    # Persist Weather deactivated with a saved config, then restore navigation
    # onto the weather subtab. Admission must land on SETUP and never build or
    # hydrate the deactivated Weather page.
    settings_manager.set("widgets", {
        "weather": {"enabled": True, "location": "Testville", "font_size": 22},
        "shadows": {"enabled": True, "text_enabled": True, "header_enabled": True},
        "global": {"card_border_width_px": 3},
        "family_activation": {"weather": False},
    })
    tab = _make_tab(settings_manager, initial_view_state={"subtab_id": "weather"})
    try:
        setup_idx = tab._widget_section_index("setup")
        weather_idx = tab._widget_section_index("weather")
        weather = next(f for f in get_widget_family_descriptors() if f.family_id == "weather")

        # Landed on SETUP, not the hidden Weather page.
        assert tab._current_subtab == setup_idx
        assert _family_pill(tab, weather).isHidden() is True

        # Weather page was never built or hydrated, and its controls do not exist.
        assert weather_idx not in tab._subtab_content_built
        assert "weather" not in tab._hydrated_widget_sections
        assert not hasattr(tab, "weather_enabled")

        # Saved Weather config is untouched.
        cfg = settings_manager.get("widgets", {})
        assert cfg["weather"]["location"] == "Testville"
        assert cfg["weather"]["font_size"] == 22

        # Reactivate and select Weather -> it now builds AND hydrates preserved config.
        tab._family_activation_checkboxes["weather"].setChecked(True)
        tab._on_subtab_changed(weather_idx)
        qt_app.processEvents()

        assert tab._current_subtab == weather_idx
        assert weather_idx in tab._subtab_content_built
        assert "weather" in tab._hydrated_widget_sections
        assert hasattr(tab, "weather_enabled")
        assert tab.weather_enabled.isChecked() is True
    finally:
        tab.deleteLater()


def test_reactivation_restores_pill_and_reads_persisted_state(qt_app, settings_manager):
    # A previously deactivated family reads back deactivated, then reactivates.
    settings_manager.set("widgets", {"family_activation": {"gmail": False}})
    tab = _make_tab(settings_manager)
    try:
        gmail = next(f for f in get_widget_family_descriptors() if f.family_id == "gmail")
        assert tab._family_activation_checkboxes["gmail"].isChecked() is False
        assert _family_pill(tab, gmail).isHidden() is True

        tab._family_activation_checkboxes["gmail"].setChecked(True)
        tab._save_settings_now()
        assert _family_pill(tab, gmail).isHidden() is False
        widgets_cfg = settings_manager.get("widgets", {})
        assert is_widget_family_activated(widgets_cfg, "gmail") is True
    finally:
        tab.deleteLater()
