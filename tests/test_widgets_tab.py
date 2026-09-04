"""Tests for Widgets tab UI.

Verifies that WidgetsTab integrates correctly with the canonical nested
`widgets` settings structure (clock + weather) and that defaults and
roundtrips behave as expected.
"""
from copy import deepcopy
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
# Some CI environments install the wheel without sip stubs; guard the import.
try:  # pragma: no cover - only for environments with sip installed separately
    import sip  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    sip = None  # WidgetsTab tests do not use sip directly
import uuid

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QToolButton

from ui.tabs.widgets_tab import WidgetsTab
from ui.tabs.shared_styles import SPINBOX_STYLE
from core.settings import SettingsManager
from core.settings.defaults import get_default_settings
from core.settings.visualizer_mode_registry import (
    get_default_visualizer_mode_id,
    get_preset_slider_attr,
    iter_visualizer_mode_descriptors,
)
from core.settings.visualizer_presets import MODE_KEY_PREFIXES
from rendering.widget_descriptors import get_widget_settings_section_descriptors
from rendering.widget_descriptors import get_widgets_tab_settings_section_descriptors
from rendering.widget_descriptors import get_widget_position_option_labels


def _find_toggle(container, text: str) -> QToolButton | None:
    for toggle in container.findChildren(QToolButton):
        if toggle.text() == text:
            return toggle
    return None


@pytest.fixture
def widgets_tab(qt_app, settings_manager):
    """Create WidgetsTab for testing."""
    tab = WidgetsTab(settings_manager)
    yield tab
    tab.deleteLater()


class TestWidgetsTab:
    """Tests for Widgets tab UI component."""

    def test_widgets_tab_creation(self, qt_app, settings_manager):
        """WidgetsTab can be created and wired to SettingsManager."""
        tab = WidgetsTab(settings_manager)
        assert tab is not None
        assert tab._settings is settings_manager
        tab.deleteLater()

    def test_widgets_tab_subtab_labels_follow_descriptor_order(self, qt_app, settings_manager):
        # V7 moved Visualizers to its own top-level tab, so WidgetsTab subtabs now
        # follow the WidgetsTab-scoped descriptor list (which excludes visualizers).
        tab = WidgetsTab(settings_manager)
        try:
            descriptors = get_widgets_tab_settings_section_descriptors()
            labels = [
                tab._subtab_group.button(idx).text()
                for idx in range(len(descriptors))
            ]
            assert labels == [descriptor.button_label for descriptor in descriptors]
            assert tab._subtab_group.checkedId() == 0
        finally:
            tab.deleteLater()

    def test_lazy_widgets_tab_builds_persisted_subtab_first(self, qt_app, settings_manager):
        """Lazy settings-dialog mode should build only the requested subtab first."""
        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "weather"},
        )
        try:
            assert hasattr(tab, "weather_enabled")
            assert hasattr(tab, "widget_shadows_enabled")
            assert not hasattr(tab, "clock_enabled")

            tab._on_subtab_changed(tab._widget_section_index("clock"))
            qt_app.processEvents()

            assert hasattr(tab, "clock_enabled")
        finally:
            tab.deleteLater()

    def test_lazy_widgets_tab_accepts_descriptor_owned_subtab_id_restore(self, qt_app, settings_manager):
        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "reddit"},
        )
        try:
            assert hasattr(tab, "reddit_enabled")
            assert hasattr(tab, "widget_shadows_enabled")
            assert not hasattr(tab, "clock_enabled")

            view_state = tab.get_view_state()
            assert view_state["subtab_id"] == "reddit"
        finally:
            tab.deleteLater()

    def test_lazy_widgets_tab_media_restore_hydrates_media_only(self, qt_app, settings_manager):
        settings_manager.set("widgets", {
            "media": {"enabled": True, "position": "Bottom Left", "monitor": "ALL"},
            "spotify_visualizer": {"enabled": True, "mode": "bubble"},
            "shadows": {"enabled": True, "text_enabled": True, "header_enabled": True},
            "global": {"card_border_width_px": 3},
        })

        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "media"},
        )
        try:
            assert hasattr(tab, "media_enabled")
            assert not hasattr(tab, "vis_enabled_checkbox")
            assert tab.media_enabled.isChecked() is True
            assert tab.media_position.currentText() == "Bottom Left"
            assert tab.media_monitor_combo.currentText() == "ALL"
        finally:
            tab.deleteLater()

    def test_media_spotify_browser_choice_enables_exact_host_volume_fallback(
        self,
        qt_app,
        settings_manager,
    ):
        settings_manager.set("widgets", {
            "media": {
                "enabled": True,
                "provider": "spotify_browser",
                "position": "Bottom Left",
                "monitor": "ALL",
                "spotify_volume_enabled": True,
            },
            "shadows": {"enabled": True, "text_enabled": True, "header_enabled": True},
            "global": {"card_border_width_px": 3},
        })

        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "media"},
        )
        try:
            assert tab.media_provider_combo.currentData() == "spotify_browser"
            assert tab.media_spotify_volume_enabled.isChecked() is True
            assert tab.media_spotify_volume_enabled.isEnabled() is True
            assert tab._spotify_browser_provider_note.isHidden() is False
            assert "whole audio session" in tab.media_spotify_volume_enabled.toolTip()

            tab.media_provider_combo.setCurrentIndex(
                tab.media_provider_combo.findData("spotify")
            )
            assert tab.media_spotify_volume_enabled.isEnabled() is True
            assert tab._spotify_browser_provider_note.isHidden() is True
        finally:
            tab.deleteLater()

    def test_media_progress_settings_roundtrip_and_transport_gate(
        self,
        qt_app,
        settings_manager,
    ):
        from ui.tabs.widgets_tab_media import save_media_settings

        settings_manager.set("widgets", {
            "media": {
                "enabled": True,
                "show_controls": True,
                "playback_progress_enabled": True,
                "playback_progress_height": 11,
                "playback_progress_fill_color": [15, 125, 235, 210],
                "playback_progress_shadow_enabled": True,
                "playback_progress_glow_enabled": True,
                "playback_progress_glow_color": [45, 180, 255, 160],
            },
            "shadows": {"enabled": True},
            "global": {"card_border_width_px": 3},
        })
        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "media"},
        )
        try:
            assert tab.media_playback_progress_enabled.isChecked() is True
            assert tab.media_playback_progress_height.value() == 11
            assert tab._media_progress_fill_color.getRgb() == (15, 125, 235, 210)
            assert tab.media_playback_progress_shadow_enabled.isChecked() is True
            assert tab.media_playback_progress_glow_enabled.isChecked() is True
            assert tab._media_progress_glow_color.getRgb() == (45, 180, 255, 160)
            assert tab._media_progress_options_container.isEnabled() is True
            assert tab.media_playback_progress_glow_color_btn.isEnabled() is True

            saved = save_media_settings(tab)
            assert saved["playback_progress_enabled"] is True
            assert saved["playback_progress_height"] == 11
            assert saved["playback_progress_fill_color"] == [15, 125, 235, 210]
            assert saved["playback_progress_shadow_enabled"] is True
            assert saved["playback_progress_glow_enabled"] is True
            assert saved["playback_progress_glow_color"] == [45, 180, 255, 160]

            tab.media_show_controls.setChecked(False)
            assert tab.media_playback_progress_enabled.isEnabled() is False
            assert tab._media_progress_options_container.isEnabled() is False
        finally:
            tab.deleteLater()

    def test_invalid_media_provider_is_visible_and_not_coerced_to_spotify(
        self,
        qt_app,
        settings_manager,
    ):
        settings_manager.set("widgets", {
            "media": {
                "enabled": True,
                "provider": "retired_alias",
                "position": "Bottom Left",
                "monitor": "ALL",
                "spotify_volume_enabled": True,
            },
            "shadows": {"enabled": True, "text_enabled": True, "header_enabled": True},
            "global": {"card_border_width_px": 3},
        })

        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "media"},
        )
        try:
            assert tab.media_provider_combo.currentData() == "retired_alias"
            assert tab._unsupported_media_provider_note.isHidden() is False
            assert tab.media_spotify_volume_enabled.isEnabled() is False
            assert settings_manager.get("widgets")["media"]["provider"] == "retired_alias"
        finally:
            tab.deleteLater()


    def test_lazy_widgets_tab_save_preserves_unbuilt_section_config(self, qt_app, settings_manager):
        """Saving a built lazy section must not clobber config for sections never constructed."""
        settings_manager.set("widgets", {
            "clock": {"enabled": True, "position": "Top Right"},
            "weather": {"enabled": True, "location": "Johannesburg", "position": "Top Left"},
            "shadows": {"enabled": True, "text_enabled": True, "header_enabled": True},
            "global": {"card_border_width_px": 3},
        })

        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "clock"},
        )
        try:
            assert hasattr(tab, "clock_enabled")
            assert not hasattr(tab, "weather_enabled")

            tab.clock_enabled.setChecked(False)
            tab._save_settings_now()

            widgets_cfg = settings_manager.get("widgets", {})
            assert widgets_cfg.get("clock", {}).get("enabled") is False
            assert widgets_cfg.get("weather", {}).get("location") == "Johannesburg"
            assert widgets_cfg.get("weather", {}).get("position") == "Top Left"
        finally:
            tab.deleteLater()

    def test_lazy_save_omits_expected_unhydrated_sections_without_guard_warning(
        self,
        qt_app,
        settings_manager,
        caplog,
    ):
        visualizer = {
            "enabled": True,
            "mode": "bubble",
            "preset_bubble": 3,
            "future_unknown_value": {"keep": [1, 2, 3]},
        }
        settings_manager.set("widgets", {
            "clock": {"enabled": True, "position": "Top Right"},
            "weather": {"enabled": True, "location": "Johannesburg"},
            "spotify_visualizer": visualizer,
            "shadows": {"enabled": True, "text_enabled": True, "header_enabled": True},
            "global": {"card_border_width_px": 3},
        })

        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "clock"},
        )
        try:
            visualizer_before_save = deepcopy(
                settings_manager.get("widgets.spotify_visualizer")
            )
            with caplog.at_level(logging.WARNING, logger="ui.tabs.widgets_tab"):
                tab.clock_enabled.setChecked(False)
                tab._save_settings_now()

            assert "blocked_save_from_unhydrated_section" not in caplog.text
            assert settings_manager.get("widgets.spotify_visualizer") == visualizer_before_save
        finally:
            tab.deleteLater()

    def test_lazy_widgets_tab_subtab_build_uses_section_scoped_loader(self, qt_app, settings_manager, monkeypatch):
        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "clock"},
        )
        try:
            descriptors = get_widget_settings_section_descriptors()
            weather_index = next(
                idx for idx, descriptor in enumerate(descriptors)
                if descriptor.section_id == "weather"
            )
            broad_calls: list[dict] = []
            scoped_calls: list[str] = []

            def _fake_load_sections(owner, widgets_config, descriptors=None):
                broad_calls.append(
                    {
                        "owner": owner,
                        "widgets_config": dict(widgets_config),
                        "descriptors": descriptors,
                    }
                )

            def _fake_load_section(owner, section_id, widgets_config, descriptors=None):
                assert owner is tab
                assert isinstance(widgets_config, dict)
                scoped_calls.append(section_id)
                return True

            monkeypatch.setattr("ui.tabs.widgets_tab.load_widget_sections", _fake_load_sections)
            monkeypatch.setattr("ui.tabs.widgets_tab.load_widget_section", _fake_load_section)

            tab._on_subtab_changed(weather_index)
            qt_app.processEvents()

            assert broad_calls == []
            assert scoped_calls == ["weather"]
        finally:
            tab.deleteLater()

    def test_lazy_widgets_tab_media_build_uses_dependency_scoped_loaders(self, qt_app, settings_manager, monkeypatch):
        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "clock"},
        )
        try:
            descriptors = get_widget_settings_section_descriptors()
            media_index = next(
                idx for idx, descriptor in enumerate(descriptors)
                if descriptor.section_id == "media"
            )
            broad_calls: list[dict] = []
            scoped_calls: list[str] = []

            def _fake_load_sections(owner, widgets_config, descriptors=None):
                broad_calls.append(
                    {
                        "owner": owner,
                        "widgets_config": dict(widgets_config),
                        "descriptors": descriptors,
                    }
                )

            def _fake_load_section(owner, section_id, widgets_config, descriptors=None):
                assert owner is tab
                assert isinstance(widgets_config, dict)
                scoped_calls.append(section_id)
                return True

            monkeypatch.setattr("ui.tabs.widgets_tab.load_widget_sections", _fake_load_sections)
            monkeypatch.setattr("ui.tabs.widgets_tab.load_widget_section", _fake_load_section)

            tab._on_subtab_changed(media_index)
            qt_app.processEvents()

            assert broad_calls == []
            assert scoped_calls == ["media"]
        finally:
            tab.deleteLater()


    def test_lazy_widgets_tab_media_first_save_preserves_visualizer_config(
        self,
        qt_app,
        settings_manager,
    ):
        settings_manager.set("widgets", {
            "media": {
                "enabled": True,
                "position": "Bottom Left",
                "monitor": "ALL",
            },
            "spotify_visualizer": {
                "enabled": True,
                "visualizers_enabled": True,
                "mode": "bubble",
                "preset_bubble": 3,
                "bubble_big_count": 7,
                "bubble_small_count": 38,
            },
            "shadows": {"enabled": True, "text_enabled": True, "header_enabled": True},
            "global": {"card_border_width_px": 3},
        })

        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "media"},
        )
        try:
            assert hasattr(tab, "media_enabled")
            assert not hasattr(tab, "vis_enabled_checkbox")
            tab.media_enabled.setChecked(False)
            tab._save_settings_now()

            widgets_cfg = settings_manager.get("widgets", {})
            assert widgets_cfg.get("media", {}).get("enabled") is False
            vis_cfg = widgets_cfg.get("spotify_visualizer", {})
            assert vis_cfg.get("enabled") is True
            assert vis_cfg.get("mode") == "bubble"
            assert vis_cfg.get("preset_bubble") == 3
            assert vis_cfg.get("bubble_big_count") == 7
            assert vis_cfg.get("bubble_small_count") == 38
        finally:
            tab.deleteLater()

    def test_lazy_widgets_tab_media_hydration_does_not_trigger_save_while_building(
        self,
        qt_app,
        settings_manager,
        monkeypatch,
    ):
        settings_manager.set("widgets", {
            "media": {"enabled": True, "position": "Bottom Right", "monitor": "ALL"},
            "spotify_visualizer": {
                "enabled": True,
                "visualizers_enabled": True,
                "mode": "bubble",
            },
            "shadows": {"enabled": True, "text_enabled": True, "header_enabled": True},
            "global": {"card_border_width_px": 3},
        })

        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "clock"},
        )
        try:
            descriptors = get_widget_settings_section_descriptors()
            media_index = next(
                idx for idx, descriptor in enumerate(descriptors)
                if descriptor.section_id == "media"
            )
            save_calls: list[str] = []
            original_save = tab._save_settings

            def _record_save():
                if not tab._loading:
                    save_calls.append("save")
                return original_save()

            monkeypatch.setattr(tab, "_save_settings", _record_save)

            tab._on_subtab_changed(media_index)
            qt_app.processEvents()

            assert save_calls == []
            widgets_cfg = settings_manager.get("widgets", {})
            assert widgets_cfg.get("media", {}).get("enabled") is True
        finally:
            tab.deleteLater()

    def test_widgets_tab_custom_position_slot_tracks_saved_custom_layout_state(self, qt_app, settings_manager):
        settings_manager.set("widgets", {
            "clock": {"enabled": True, "position": "Custom"},
            "media": {"enabled": True, "position": "Bottom Left", "monitor": "ALL"},
            "custom_layout": {
                "version": 2,
                "displays": {
                    "screen:test": {
                        "clock": {"digital": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.2, "height": 0.1},
                            "size_payload": {"font_size": 64},
                            "resize_mode": "clock_font",
                        }}
                    }
                },
            },
        })

        tab = WidgetsTab(settings_manager)
        try:
            clock_idx = tab.clock_position.findText("Custom")
            media_idx = tab.media_position.findText("Custom")
            assert clock_idx >= 0
            assert media_idx >= 0
            assert tab.clock_position.currentText() == "Custom"
            assert tab.clock_position.model().item(clock_idx).isEnabled() is True
            assert tab.media_position.model().item(media_idx).isEnabled() is False
        finally:
            tab.deleteLater()

    def test_widgets_tab_disables_media_size_controls_when_custom_is_active(self, qt_app, settings_manager):
        settings_manager.set("widgets", {
            "media": {
                "enabled": True,
                "provider": "spotify",
                "position": "Custom",
                "monitor": "1",
                "show_controls": True,
                "playback_progress_enabled": True,
                "playback_progress_glow_enabled": True,
                "spotify_volume_enabled": True,
                "mute_button_enabled": True,
            },
            "custom_layout": {
                "version": 2,
                "displays": {
                    "screen:test": {
                        "media": {"default": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                            "size_payload": {"font_size": 22, "artwork_size": 220},
                            "resize_mode": "media_scale",
                        }}
                    }
                },
            },
        })

        tab = WidgetsTab(settings_manager)
        try:
            assert tab.media_font_size.isEnabled() is False
            assert tab.media_artwork_size.isEnabled() is False
            notice = tab._custom_resize_lock_notice_labels["media"]
            assert notice.isHidden() is False
            assert "Disable Custom Mode" in notice.text()
            assert tab.media_font_combo.isEnabled() is True
            assert tab.media_show_controls.isEnabled() is True
            assert tab.media_playback_progress_enabled.isEnabled() is True
            assert tab.media_playback_progress_height.isEnabled() is True
            assert tab.media_playback_progress_shadow_enabled.isEnabled() is True
            assert tab.media_playback_progress_glow_enabled.isEnabled() is True
            assert tab.media_playback_progress_glow_color_btn.isEnabled() is True
            assert tab.media_spotify_volume_enabled.isEnabled() is True
            assert tab.media_mute_button_enabled.isEnabled() is True
        finally:
            tab.deleteLater()

    def test_widgets_tab_locks_both_clock_font_sizes_when_custom_is_active(
        self,
        qt_app,
        settings_manager,
    ):
        settings_manager.set("widgets", {
            "clock": {
                "enabled": True,
                "position": "Custom",
                "show_day_of_week": True,
                "show_date": True,
                "show_separator": True,
                "calendar_font_size": 28,
            },
            "custom_layout": {
                "version": 2,
                "displays": {
                    "screen:test": {
                        "clock": {"digital": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                            "size_payload": {"font_size": 64},
                            "resize_mode": "clock_font",
                        }}
                    }
                },
            },
        })

        tab = WidgetsTab(settings_manager)
        try:
            assert tab.clock_font_size.isEnabled() is False
            assert tab.clock_calendar_font_size.isEnabled() is False
            assert tab.clock_show_separator.isChecked() is True
            assert tab.clock_font_combo.isEnabled() is True
            assert tab._custom_resize_lock_notice_labels["clock"].isHidden() is False
        finally:
            tab.deleteLater()

    def test_widgets_tab_disable_custom_mode_link_restores_authored_layout(self, qt_app, settings_manager, monkeypatch):
        settings_manager.set("widgets", {
            "media": {"enabled": True, "position": "Custom", "monitor": "1"},
            "spotify_visualizer": {"position": "Custom", "monitor": "2"},
            "custom_layout": {
                "version": 2,
                "displays": {
                    "screen:test": {
                        "media": {"default": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                            "size_payload": {"font_size": 22, "artwork_size": 220},
                            "resize_mode": "media_scale",
                        }},
                        "spotify_volume": {"default": {
                            "rect": {"x": 0.4, "y": 0.2, "width": 0.05, "height": 0.3},
                            "size_payload": {"width": 32, "height": 180},
                            "resize_mode": "volume_scale",
                        }},
                        "spotify_visualizer": {"default": {
                            "rect": {"x": 0.55, "y": 0.2, "width": 0.18, "height": 0.22},
                            "size_payload": {"width_scale": 1.2, "height_scale": 1.1},
                            "resize_mode": "visualizer_rect",
                        }},
                    }
                },
            },
            "custom_layout_restore": {
                "version": 1,
                "widgets": {
                    "media": {"position": "Bottom Left", "monitor": "ALL"},
                    "spotify_visualizer": {"position": "Bottom Left", "monitor": "ALL"},
                },
            },
        })

        monkeypatch.setattr("ui.tabs.widgets_tab.StyledPopup.question", lambda *args, **kwargs: True)

        tab = WidgetsTab(settings_manager)
        try:
            tab._on_custom_resize_lock_link_activated("media")
            widgets_cfg = settings_manager.get("widgets", {})
            assert widgets_cfg["media"]["position"] == "Bottom Left"
            assert widgets_cfg["media"]["monitor"] == "ALL"
            assert widgets_cfg["spotify_visualizer"]["position"] == "Bottom Left"
            assert widgets_cfg["spotify_visualizer"]["monitor"] == "ALL"
            displays = widgets_cfg["custom_layout"]["displays"]
            layouts = displays.get("screen:test", {})
            assert "media" not in layouts
            assert "spotify_volume" not in layouts
            assert "spotify_visualizer" not in layouts
            assert tab.media_font_size.isEnabled() is True
            assert tab.media_artwork_size.isEnabled() is True
            assert tab._custom_resize_lock_notice_labels["media"].isHidden() is True
        finally:
            tab.deleteLater()

    def test_widgets_tab_disable_custom_mode_link_cancel_keeps_state(self, qt_app, settings_manager, monkeypatch):
        settings_manager.set("widgets", {
            "media": {"enabled": True, "position": "Custom", "monitor": "1"},
            "custom_layout": {
                "version": 2,
                "displays": {
                    "screen:test": {
                        "media": {"default": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                            "size_payload": {"font_size": 22, "artwork_size": 220},
                            "resize_mode": "media_scale",
                        }}
                    }
                },
            },
            "custom_layout_restore": {
                "version": 1,
                "widgets": {
                    "media": {"position": "Bottom Left", "monitor": "ALL"},
                },
            },
        })

        monkeypatch.setattr("ui.tabs.widgets_tab.StyledPopup.question", lambda *args, **kwargs: False)

        tab = WidgetsTab(settings_manager)
        try:
            tab._on_custom_resize_lock_link_activated("media")
            widgets_cfg = settings_manager.get("widgets", {})
            assert widgets_cfg["media"]["position"] == "Custom"
            assert "media" in widgets_cfg["custom_layout"]["displays"]["screen:test"]
            assert tab.media_font_size.isEnabled() is False
        finally:
            tab.deleteLater()

    def test_widgets_tab_disable_custom_mode_revert_invalidates_pending_stale_save(self, qt_app, settings_manager, monkeypatch):
        settings_manager.set("widgets", {
            "media": {"enabled": True, "position": "Custom", "monitor": "1"},
            "spotify_visualizer": {"position": "Custom", "monitor": "2"},
            "custom_layout": {
                "version": 2,
                "displays": {
                    "screen:test": {
                        "media": {"default": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                            "size_payload": {"font_size": 22, "artwork_size": 220},
                            "resize_mode": "media_scale",
                        }},
                        "spotify_visualizer": {"default": {
                            "rect": {"x": 0.55, "y": 0.2, "width": 0.18, "height": 0.22},
                            "size_payload": {"width_scale": 1.2, "height_scale": 1.1},
                            "resize_mode": "visualizer_rect",
                        }},
                    }
                },
            },
            "custom_layout_restore": {
                "version": 1,
                "widgets": {
                    "media": {"position": "Bottom Left", "monitor": "ALL"},
                    "spotify_visualizer": {"position": "Bottom Left", "monitor": "ALL"},
                },
            },
        })

        monkeypatch.setattr("ui.tabs.widgets_tab.StyledPopup.question", lambda *args, **kwargs: True)

        tab = WidgetsTab(settings_manager)
        try:
            tab._save_coalesce_pending = True
            tab._save_coalesce_token = 5
            tab._on_custom_resize_lock_link_activated("media")

            widgets_cfg = settings_manager.get("widgets", {})
            assert widgets_cfg["media"]["position"] == "Bottom Left"
            assert widgets_cfg["spotify_visualizer"]["position"] == "Bottom Left"

            tab._save_settings_now(5)

            widgets_cfg = settings_manager.get("widgets", {})
            assert widgets_cfg["media"]["position"] == "Bottom Left"
            assert widgets_cfg["spotify_visualizer"]["position"] == "Bottom Left"
        finally:
            tab.deleteLater()

    def test_widgets_tab_disable_custom_mode_revert_is_silent_widgets_update(self, qt_app, settings_manager, monkeypatch):
        settings_manager.set("widgets", {
            "media": {"enabled": True, "position": "Custom", "monitor": "1"},
            "gmail": {"enabled": True, "position": "Custom", "monitor": "2"},
            "custom_layout": {
                "version": 2,
                "displays": {
                    "screen:test": {
                        "media": {"default": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                            "size_payload": {"font_size": 22, "artwork_size": 220},
                            "resize_mode": "media_scale",
                        }},
                        "gmail": {"default": {
                            "rect": {"x": 0.5, "y": 0.1, "width": 0.2, "height": 0.2},
                            "size_payload": {"font_size": 15},
                            "resize_mode": "gmail_font",
                        }}
                    }
                },
            },
            "custom_layout_restore": {
                "version": 1,
                "widgets": {
                    "media": {"position": "Bottom Left", "monitor": "ALL"},
                    "gmail": {"position": "Top Left", "monitor": "2"},
                },
            },
        })

        monkeypatch.setattr("ui.tabs.widgets_tab.StyledPopup.question", lambda *args, **kwargs: True)
        received: list[tuple[str, object]] = []
        settings_manager.settings_changed.connect(lambda key, value: received.append((key, value)))

        tab = WidgetsTab(settings_manager)
        try:
            received.clear()
            tab._on_custom_resize_lock_link_activated("media")
            assert all(key != "widgets" for key, _value in received)
            widgets_cfg = settings_manager.get("widgets", {})
            assert widgets_cfg["media"]["position"] == "Bottom Left"
            assert widgets_cfg["gmail"]["position"] == "Top Left"
        finally:
            tab.deleteLater()

    def test_widgets_tab_default_values(self, qt_app, tmp_path):
        """Default widget settings match canonical SettingsManager defaults."""
        mgr = SettingsManager(organization="Test", application=f"WidgetsTabTest_{uuid.uuid4().hex}", storage_base_dir=tmp_path)
        # Ensure a clean slate and then re-apply canonical defaults so the
        # nested `widgets` map reflects SettingsManager._set_defaults().
        mgr.reset_to_defaults()

        tab = WidgetsTab(mgr)
        try:
            defaults = get_default_settings()["widgets"]
            clock_defaults = defaults["clock"]
            weather_defaults = defaults["weather"]
            shadow_defaults = defaults["shadows"]

            assert tab.clock_enabled.isChecked() is bool(clock_defaults["enabled"])
            assert tab.clock_position.currentText() == str(clock_defaults["position"])
            expected_format = "24 Hour" if clock_defaults["format"] == "24h" else "12 Hour"
            assert tab.clock_format.currentText() == expected_format
            assert tab.clock_seconds.isChecked() is bool(clock_defaults["show_seconds"])
            assert tab.clock_show_background.isChecked() is bool(clock_defaults["show_background"])
            assert tab.clock_bg_opacity.value() == round(float(clock_defaults["bg_opacity"]) * 100)
            assert tab.clock_monitor_combo.currentText() == str(clock_defaults["monitor"])

            assert tab.weather_enabled.isChecked() is bool(weather_defaults["enabled"])
            assert tab.weather_position.currentText() == str(weather_defaults["position"])
            assert tab.weather_location.text() == str(weather_defaults["location"])
            assert tab.weather_show_forecast.isChecked() is bool(weather_defaults["show_forecast"])
            assert tab.weather_show_background.isChecked() is bool(weather_defaults["show_background"])
            assert tab.weather_bg_opacity.value() == round(float(weather_defaults["bg_opacity"]) * 100)
            assert tab.widget_shadows_enabled.isChecked() is bool(shadow_defaults["enabled"])
            assert tab.widget_text_shadows_enabled.isChecked() is bool(shadow_defaults["text_enabled"])
            assert tab.widget_header_shadows_enabled.isChecked() is bool(shadow_defaults["header_enabled"])
        finally:
            tab.deleteLater()

    def test_weather_empty_location_stays_explicit(self, qt_app, settings_manager, monkeypatch):
        import ui.tabs.widgets_tab_weather as weather_tab_module

        monkeypatch.setattr(
            weather_tab_module,
            "get_local_timezone",
            lambda: "Africa/Blantyre",
            raising=False,
        )
        settings_manager.set("widgets.weather.location", "")

        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "weather"},
        )
        try:
            assert tab.weather_location.text() == ""
            assert settings_manager.get("widgets.weather.location", "missing") == ""
        finally:
            tab.deleteLater()

    def test_widgets_tab_position_combos_follow_descriptor_position_options(self, qt_app, settings_manager):
        tab = WidgetsTab(settings_manager)
        try:
            def _combo_items(combo):
                return [combo.itemText(i) for i in range(combo.count())]

            assert _combo_items(tab.clock_position) == list(get_widget_position_option_labels("clock"))
            assert _combo_items(tab.weather_position) == list(get_widget_position_option_labels("weather"))
            assert _combo_items(tab.media_position) == list(get_widget_position_option_labels("media"))
            assert _combo_items(tab.reddit_position) == list(get_widget_position_option_labels("reddit"))
            assert _combo_items(tab.reddit2_position) == list(get_widget_position_option_labels("reddit2"))
            assert _combo_items(tab.gmail_position) == list(get_widget_position_option_labels("gmail"))
        finally:
            tab.deleteLater()


    def test_widgets_tab_saves_and_roundtrips(self, qt_app, widgets_tab):
        """Changing widget controls and saving updates nested `widgets` config."""
        tab = widgets_tab

        # Mutate some clock settings through the UI
        tab.clock_enabled.setChecked(True)
        tab.clock_position.setCurrentText("Bottom Left")
        tab.clock_show_background.setChecked(True)
        tab.clock_bg_opacity.setValue(75)  # 75%
        tab.clock_monitor_combo.setCurrentText("ALL")

        # Mutate some weather settings
        tab.weather_enabled.setChecked(True)
        tab.weather_location.setText("Johannesburg")
        tab.weather_position.setCurrentText("Bottom Left")
        tab.weather_monitor_combo.setCurrentText("ALL")
        tab.weather_show_forecast.setChecked(True)
        tab.weather_show_background.setChecked(True)
        tab.weather_bg_opacity.setValue(80)  # 80%
        tab.widget_shadows_enabled.setChecked(False)
        tab.widget_text_shadows_enabled.setChecked(False)
        tab.widget_header_shadows_enabled.setChecked(True)

        # Persist settings (call _now directly; _save_settings is debounced)
        tab._save_settings_now()

        widgets_cfg = tab._settings.get("widgets", {})
        assert isinstance(widgets_cfg, dict)

        clock_cfg = widgets_cfg.get("clock", {})
        assert clock_cfg.get("enabled") is True
        assert clock_cfg.get("position") == "Bottom Left"
        assert clock_cfg.get("show_background") is True
        assert pytest.approx(clock_cfg.get("bg_opacity", 0.0)) == 0.75
        # Monitor stored as "ALL" string when combo shows ALL
        assert clock_cfg.get("monitor") == "ALL"

        weather_cfg = widgets_cfg.get("weather", {})
        assert weather_cfg.get("enabled") is True
        assert weather_cfg.get("location") == "Johannesburg"
        assert weather_cfg.get("position") == "Bottom Left"
        assert weather_cfg.get("show_forecast") is True
        assert weather_cfg.get("show_background") is True
        assert pytest.approx(weather_cfg.get("bg_opacity", 0.0)) == 0.80
        assert weather_cfg.get("monitor") == "ALL"

        shadows_cfg = widgets_cfg.get("shadows", {})
        assert shadows_cfg.get("enabled") is False
        assert shadows_cfg.get("text_enabled") is False
        assert shadows_cfg.get("header_enabled") is True

    def test_widgets_tab_master_reddit_toggle_disables_reddit2_persistence(self, qt_app, widgets_tab):
        tab = widgets_tab

        tab.reddit_enabled.setChecked(True)
        tab.reddit2_enabled.setChecked(True)
        tab._save_settings_now()

        widgets_cfg = tab._settings.get("widgets", {})
        assert widgets_cfg.get("reddit2", {}).get("enabled") is True

        tab.reddit_enabled.setChecked(False)
        tab._save_settings_now()

        widgets_cfg = tab._settings.get("widgets", {})
        assert widgets_cfg.get("reddit", {}).get("enabled") is False
        assert widgets_cfg.get("reddit2", {}).get("enabled") is False

    def test_widgets_tab_load_settings_uses_descriptor_loader_routing(self, qt_app, settings_manager):
        tab = WidgetsTab(settings_manager)
        try:
            calls: list[str] = []

            def _loader_a(owner, widgets):
                assert owner is tab
                assert isinstance(widgets, dict)
                calls.append("a")

            def _loader_b(owner, widgets):
                assert owner is tab
                assert isinstance(widgets, dict)
                calls.append("b")

            tab._widget_section_descriptors = (
                SimpleNamespace(
                    can_load_for_owner=lambda owner: True,
                    resolve_loader=lambda: _loader_a,
                ),
                SimpleNamespace(
                    can_load_for_owner=lambda owner: False,
                    resolve_loader=lambda: _loader_b,
                ),
                SimpleNamespace(
                    can_load_for_owner=lambda owner: True,
                    resolve_loader=lambda: None,
                ),
            )

            tab._load_settings()

            assert calls == ["a"]
        finally:
            tab.deleteLater()

    def test_widgets_tab_load_settings_uses_descriptor_signal_block_helper(self, qt_app, settings_manager, monkeypatch):
        tab = WidgetsTab(settings_manager)
        try:
            calls: list[tuple[object, tuple[str, ...]]] = []

            def _fake_collect(owner, *, extra_attr_names=()):
                calls.append((owner, tuple(extra_attr_names)))
                return ()

            monkeypatch.setattr(
                "ui.tabs.widgets_tab.collect_widget_section_signal_block_targets",
                _fake_collect,
            )

            tab._load_settings()

            assert len(calls) == 1
            owner, extra_attr_names = calls[0]
            assert owner is tab
            assert extra_attr_names == ()
        finally:
            tab.deleteLater()

    def test_widgets_tab_save_settings_uses_descriptor_saver_routing(self, qt_app, settings_manager):
        tab = WidgetsTab(settings_manager)
        try:
            settings_manager.set("widgets", {
                "clock": {"enabled": True},
                "clock2": {"enabled": False},
                "clock3": {"enabled": False},
            })
            calls: list[str] = []

            def _clock_saver(owner):
                assert owner is tab
                calls.append("clock")
                return (
                    {"enabled": False},
                    {"enabled": True},
                    {"enabled": True},
                )

            tab._widget_section_descriptors = (
                SimpleNamespace(
                    section_id="clock",
                    persisted_widget_keys=("clock", "clock2", "clock3"),
                    can_save_for_owner=lambda owner: True,
                    resolve_saver=lambda: _clock_saver,
                ),
                SimpleNamespace(
                    section_id="defaults",
                    persisted_widget_keys=(),
                    can_save_for_owner=lambda owner: False,
                    resolve_saver=lambda: None,
                ),
            )

            tab._save_settings_now()

            widgets_cfg = settings_manager.get("widgets", {})
            assert calls == ["clock"]
            assert widgets_cfg["clock"]["enabled"] is False
            assert widgets_cfg["clock2"]["enabled"] is True
            assert widgets_cfg["clock3"]["enabled"] is True
        finally:
            tab.deleteLater()

    def test_widgets_tab_save_settings_uses_descriptor_apply_helper(self, qt_app, settings_manager, monkeypatch):
        tab = WidgetsTab(settings_manager)
        try:
            calls: list[tuple[object, object, tuple[str, ...]]] = []

            def _fake_apply(widgets_config, section_results, *, exclude_keys=(), descriptors=None):
                calls.append((widgets_config, section_results, tuple(exclude_keys)))
                return widgets_config

            monkeypatch.setattr(
                "ui.tabs.widgets_tab.apply_widget_section_save_results",
                _fake_apply,
            )

            tab._save_settings_now()

            assert len(calls) == 1
            widgets_config, section_results, exclude_keys = calls[0]
            assert isinstance(widgets_config, dict)
            assert isinstance(section_results, dict)
            assert exclude_keys == ("spotify_visualizer",)
        finally:
            tab.deleteLater()

    def test_widgets_tab_defaults_section_uses_descriptor_load_and_save_paths(self, qt_app, settings_manager):
        tab = WidgetsTab(settings_manager)
        try:
            settings_manager.set("widgets", {
                "shadows": {
                    "enabled": False,
                    "text_enabled": False,
                    "header_enabled": True,
                },
                "global": {
                    "card_border_width_px": 6,
                    "stacking_enabled": False,
                },
            })

            tab._load_settings()

            assert tab.widget_shadows_enabled.isChecked() is False
            assert tab.widget_text_shadows_enabled.isChecked() is False
            assert tab.widget_header_shadows_enabled.isChecked() is True
            assert tab.widget_stacking_enabled.isChecked() is False
            assert tab.card_border_width_spin.value() == 6

            tab.widget_shadows_enabled.setChecked(True)
            tab.widget_text_shadows_enabled.setChecked(True)
            tab.widget_header_shadows_enabled.setChecked(False)
            tab.widget_stacking_enabled.setChecked(True)
            tab.card_border_width_spin.setValue(4)
            tab._save_settings_now()

            widgets_cfg = settings_manager.get("widgets", {})
            saved_shadows = widgets_cfg["shadows"]
            # Edited enable toggles land.
            assert saved_shadows["enabled"] is True
            assert saved_shadows["text_enabled"] is True
            assert saved_shadows["header_enabled"] is False
            # F0.5: the General save now writes the full canonical shadow mapping
            # (direction + darkness/blur/extra-offset) instead of a 3-key partial
            # map that erased direction/opacity/blur, and never re-persists the
            # retired ``offset`` pair.
            assert saved_shadows["direction"] == "SE"
            assert saved_shadows["frame_opacity"] == pytest.approx(0.77)
            assert saved_shadows["blur_radius"] == 18
            assert saved_shadows["frame_extra_offset"] == 0
            assert saved_shadows["text_opacity"] == pytest.approx(0.33)
            assert saved_shadows["text_extra_offset"] == 0
            assert "offset" not in saved_shadows
            assert widgets_cfg["global"]["card_border_width_px"] == 4
            assert widgets_cfg["global"]["stacking_enabled"] is True
        finally:
            tab.deleteLater()

    def test_widgets_tab_defaults_reset_positions_button_restores_application_defaults(self, qt_app, settings_manager, monkeypatch):
        settings_manager.set("widgets", {
            "media": {"enabled": True, "position": "Custom", "monitor": "2"},
            "spotify_visualizer": {"position": "Custom", "monitor": "2"},
            "gmail": {"enabled": True, "position": "Custom", "monitor": "1"},
            "custom_layout": {
                "version": 2,
                "displays": {
                    "screen:test": {
                        "media": {"default": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                            "size_payload": {"font_size": 22, "artwork_size": 220},
                            "resize_mode": "media_scale",
                        }},
                        "spotify_visualizer": {"default": {
                            "rect": {"x": 0.55, "y": 0.2, "width": 0.18, "height": 0.22},
                            "size_payload": {"width_scale": 1.2, "height_scale": 1.1},
                            "resize_mode": "visualizer_rect",
                        }},
                        "gmail": {"default": {
                            "rect": {"x": 0.5, "y": 0.1, "width": 0.2, "height": 0.2},
                            "size_payload": {"font_size": 15},
                            "resize_mode": "gmail_font",
                        }},
                    }
                },
            },
        })

        monkeypatch.setattr("ui.tabs.widgets_tab.StyledPopup.question", lambda *args, **kwargs: True)

        tab = WidgetsTab(settings_manager)
        try:
            tab._on_reset_widget_positions_to_defaults_clicked()
            widgets_cfg = settings_manager.get("widgets", {})
            defaults = get_default_settings()["widgets"]

            assert widgets_cfg["media"]["position"] == defaults["media"]["position"]
            assert str(widgets_cfg["media"]["monitor"]) == str(defaults["media"]["monitor"])
            assert widgets_cfg["spotify_visualizer"]["position"] == defaults["spotify_visualizer"]["position"]
            assert str(widgets_cfg["spotify_visualizer"]["monitor"]) == str(defaults["spotify_visualizer"]["monitor"])
            assert widgets_cfg["gmail"]["position"] == defaults["gmail"]["position"]
            assert str(widgets_cfg["gmail"]["monitor"]) == str(defaults["gmail"]["monitor"])
            assert widgets_cfg["custom_layout"]["displays"].get("screen:test", {}) == {}
        finally:
            tab.deleteLater()

    def test_widgets_tab_update_stack_status_uses_descriptor_status_targets(self, qt_app, settings_manager, monkeypatch):
        tab = WidgetsTab(settings_manager)
        try:
            calls: list[object] = []

            def _fake_collect(owner):
                calls.append(owner)
                return ()

            monkeypatch.setattr(
                "ui.tabs.widgets_tab.collect_widget_stack_status_targets",
                _fake_collect,
            )

            tab._update_stack_status()

            assert calls == [tab]
        finally:
            tab.deleteLater()

    def test_widgets_tab_initializes_standard_default_attrs_from_descriptor_metadata(self, qt_app, settings_manager):
        tab = WidgetsTab(settings_manager)
        try:
            assert isinstance(tab._global_card_border_width, int)
            assert isinstance(tab._clock_color, QColor)
            assert isinstance(tab._weather_color, QColor)
            assert isinstance(tab._media_color, QColor)
            assert isinstance(tab._reddit_color, QColor)
            assert isinstance(tab._gmail_color, QColor)
        finally:
            tab.deleteLater()







def test_visualizer_bucket_toggles_use_standard_circle_checkbox_spacing():
    source_path = Path(__file__).resolve().parents[1] / "ui" / "tabs" / "media" / "technical_controls.py"
    src = source_path.read_text(encoding="utf-8")
    toggle_block_start = src.index("def _build_visibility_toggle(")
    toggle_block_end = src.index("def _aligned_row_widget(", toggle_block_start)
    toggle_block = src[toggle_block_start:toggle_block_end]
    assert 'toggle.setProperty("circleIndicator", True)' in toggle_block
    assert 'toggle.setProperty("tightSpacing", True)' not in toggle_block












































def test_build_visualizer_preset_payload_uses_shared_missing_preset_fallback(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        mode = "bubble"
        widgets_cfg = settings_manager.get("widgets", {}) or {}
        widgets_cfg["spotify_visualizer"] = {
            "mode": mode,
            "bubble_gradient_direction": "right",
            "bubble_growth": 2.8,
        }
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()
        payload = tab.build_visualizer_preset_payload(mode)

        assert payload
        assert payload["preset_index"] == 0
    finally:
        tab.deleteLater()





def test_spinbox_stylesheet_attached(qt_app, settings_manager):
    """WidgetsTab stylesheet must keep the shared QSpinBox skin."""

    tab = WidgetsTab(settings_manager)
    try:
        css = tab.styleSheet()
        assert css, "WidgetsTab stylesheet should not be empty"
        assert "QSpinBox, QDoubleSpinBox, QLineEdit, QAbstractSpinBox" in css
        assert "QSpinBox::up-button" in css
        expected_token = "background-color: #282828"
        assert SPINBOX_STYLE.strip() in css or expected_token in css
    finally:
        tab.deleteLater()




def test_widget_bucket_toggles_default_closed(qt_app, settings_manager):
    """Non-Gmail widget buckets should start collapsed on a fresh profile."""
    tab = WidgetsTab(settings_manager)
    try:
        checks = (
            (tab._clock_controls_container, "Time Content"),
            (tab._weather_controls_container, "Location & Layout"),
            (tab._media_controls_container, "Provider & Layout"),
            (tab._reddit_controls_container, "Reddit 1"),
            (tab._reddit_controls_container, "Link Behavior"),
            (tab._reddit_controls_container, "Shared Layout & Typography"),
            (tab._reddit_controls_container, "Shared Appearance"),
        )
        for container, text in checks:
            toggle = _find_toggle(container, text)
            assert toggle is not None, f"Missing bucket toggle: {text}"
            assert toggle.isChecked() is False
    finally:
        tab.deleteLater()


def test_build_current_widgets_config_uses_live_clock_preview_fields(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        tab.clock_enabled.setChecked(True)
        tab.clock_analog_mode.setChecked(True)
        tab.clock_show_tz.setChecked(True)
        tab.clock_show_day_of_week.setChecked(True)
        tab.clock_show_date.setChecked(True)
        tab.clock_show_separator.setChecked(True)
        tab.clock_separator_thickness.setValue(4)
        tab.clock_calendar_layout.setCurrentIndex(
            tab.clock_calendar_layout.findData("two_lines")
        )
        tab.clock_calendar_font_size.setValue(26)
        tab.clock_position.setCurrentText("Bottom Left")
        tab.clock_monitor_combo.setCurrentText("ALL")
        tab.clock_font_size.setValue(52)

        built = tab._build_current_widgets_config()["clock"]

        assert built["enabled"] is True
        assert built["display_mode"] == "analog"
        assert built["show_timezone_label"] is True
        assert built["show_day_of_week"] is True
        assert built["show_date"] is True
        assert built["show_separator"] is True
        assert built["separator_thickness"] == 4
        assert built["calendar_layout"] == "two_lines"
        assert built["calendar_font_size"] == 26
        assert built["position"] == "Bottom Left"
        assert built["monitor"] == "ALL"
        assert built["font_size"] == 52
    finally:
        tab.deleteLater()


def test_clock_calendar_controls_are_conditioned_and_save_canonical_keys(
    qt_app,
    settings_manager,
):
    from ui.tabs.widgets_tab_clock import save_clock_settings

    tab = WidgetsTab(settings_manager)
    try:
        tab.clock_show_day_of_week.setChecked(False)
        tab.clock_show_date.setChecked(False)
        assert tab._clock_calendar_controls_container.isHidden() is True
        assert tab.clock_show_separator.isEnabled() is False

        tab.clock_show_day_of_week.setChecked(True)
        assert tab._clock_calendar_controls_container.isHidden() is False
        assert tab._clock_calendar_layout_row.isHidden() is True
        assert tab.clock_show_separator.isEnabled() is True

        tab.clock_show_date.setChecked(True)
        assert tab._clock_calendar_layout_row.isHidden() is False
        tab.clock_calendar_layout.setCurrentIndex(
            tab.clock_calendar_layout.findData("two_lines")
        )
        tab.clock_calendar_font_size.setValue(31)
        tab.clock_show_separator.setChecked(True)
        tab.clock_separator_thickness.setValue(5)

        clock, _, _ = save_clock_settings(tab)
        assert clock["show_day_of_week"] is True
        assert clock["show_date"] is True
        assert clock["show_separator"] is True
        assert clock["separator_thickness"] == 5
        assert clock["calendar_layout"] == "two_lines"
        assert clock["calendar_font_size"] == 31
    finally:
        tab.deleteLater()


def test_widget_bucket_state_roundtrip(qt_app, settings_manager):
    """Expanded widget bucket state should persist through WidgetsTab reloads."""
    tab = WidgetsTab(settings_manager)
    try:
        checks = (
            (tab._clock_controls_container, "Time Content", "clock", "time"),
            (tab._media_controls_container, "Transport & Volume", "media", "controls"),
            (tab._reddit_controls_container, "Reddit 1", "reddit", "reddit1"),
            (tab._reddit_controls_container, "Reddit 2", "reddit", "secondary"),
        )
        for container, text, section, bucket in checks:
            toggle = _find_toggle(container, text)
            assert toggle is not None, f"Missing bucket toggle: {text}"
            toggle.click()
            qt_app.processEvents()
            assert tab.get_widget_bucket_state(section, bucket, False) is True
    finally:
        tab.deleteLater()

    reloaded = WidgetsTab(settings_manager)
    try:
        checks = (
            (reloaded._clock_controls_container, "Time Content", "clock", "time"),
            (reloaded._media_controls_container, "Transport & Volume", "media", "controls"),
            (reloaded._reddit_controls_container, "Reddit 1", "reddit", "reddit1"),
            (reloaded._reddit_controls_container, "Reddit 2", "reddit", "secondary"),
        )
        for container, text, section, bucket in checks:
            toggle = _find_toggle(container, text)
            assert toggle is not None, f"Missing bucket toggle after reload: {text}"
            assert reloaded.get_widget_bucket_state(section, bucket, False) is True
            assert toggle.isChecked() is True
    finally:
        reloaded.deleteLater()


