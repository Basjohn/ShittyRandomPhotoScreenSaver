"""Unrelated hydrated-page edits preserve supported, unexposed authored styling."""
import pytest

from core.dev_gates import force_gate, is_steam_enabled
from ui.tabs.widgets_tab import WidgetsTab


@pytest.mark.parametrize("page,section,field,value", [
    ("feeds", "feeds_custom_1", "feeds_custom1_item_limit", 9),
    ("steam", "steam_progress", "steam_progress_font_size", 19),
    ("system_stats", "system_stats", "system_stats_sample_interval_seconds", 25),
])
def test_page_save_preserves_hidden_style_until_explicit_theme_reset(qt_app, settings_manager, page, section, field, value):
    from ui.tabs.widgets_tab_defaults import _reset_family_color_overrides_to_theme

    prior = is_steam_enabled()
    force_gate(steam=True)
    authored = {"color": [23, 45, 67, 210], "bg_color": [67, 45, 23, 170], "border_color": [90, 80, 70, 220]}
    defaults = settings_manager.get_widget_defaults(section)
    assert authored.keys() <= defaults.keys()
    settings_manager.set(f"widgets.{section}", {**defaults, **authored, "retired_probe_field": "discard"})
    settings_manager.set(f"widgets.family_activation.{page}", True)
    tab = None
    try:
        tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": page})
        getattr(tab, field).setValue(value)
        tab._save_settings_now()
        saved = settings_manager.get(f"widgets.{section}")
        assert {key: saved[key] for key in authored} == authored
        assert "retired_probe_field" not in saved
        # The explicit reset remains authoritative; later saves cannot resurrect
        # the former local colours from cached/unexposed state.
        _reset_family_color_overrides_to_theme(tab)
        tab._save_settings_now()
        saved = settings_manager.get(f"widgets.{section}")
        assert {key: saved[key] for key in authored} == {key: defaults[key] for key in authored}
    finally:
        if tab is not None:
            tab.deleteLater()
            qt_app.processEvents()
        force_gate(steam=prior)
