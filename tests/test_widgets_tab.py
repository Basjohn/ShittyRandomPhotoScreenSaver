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
        tab = WidgetsTab(settings_manager)
        try:
            labels = [
                tab._subtab_group.button(idx).text()
                for idx in range(len(get_widget_settings_section_descriptors()))
            ]
            assert labels == [
                descriptor.button_label
                for descriptor in get_widget_settings_section_descriptors()
            ]
            assert tab._subtab_group.checkedId() == 0
        finally:
            tab.deleteLater()

    def test_lazy_widgets_tab_builds_persisted_subtab_first(self, qt_app, settings_manager):
        """Lazy settings-dialog mode should build only the requested subtab first."""
        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab": 1},
        )
        try:
            assert hasattr(tab, "weather_enabled")
            assert hasattr(tab, "widget_shadows_enabled")
            assert not hasattr(tab, "clock_enabled")

            tab._on_subtab_changed(0)
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

    def test_lazy_widgets_tab_visualizers_restore_hydrates_visualizers_only(self, qt_app, settings_manager):
        settings_manager.set("widgets", {
            "media": {"enabled": True, "position": "Bottom Right", "monitor": "ALL"},
            "spotify_visualizer": {
                "enabled": False,
                "visualizers_enabled": True,
                "mode": "devcurve",
            },
            "shadows": {"enabled": True, "text_enabled": True, "header_enabled": True},
            "global": {"card_border_width_px": 3},
        })

        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "visualizers"},
        )
        try:
            assert not hasattr(tab, "media_enabled")
            assert hasattr(tab, "vis_enabled_checkbox")
            assert tab.vis_enabled_checkbox.isChecked() is False
            assert tab.vis_mode_combo.currentData() == "devcurve"
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
            initial_view_state={"subtab": 0},
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

    def test_lazy_widgets_tab_visualizers_first_save_preserves_media_config(
        self,
        qt_app,
        settings_manager,
    ):
        settings_manager.set("widgets", {
            "media": {
                "enabled": True,
                "position": "Bottom Right",
                "monitor": "ALL",
                "font_size": 27,
            },
            "spotify_visualizer": {
                "enabled": True,
                "visualizers_enabled": True,
                "mode": "spectrum",
                "preset_spectrum": 2,
            },
            "shadows": {"enabled": True, "text_enabled": True, "header_enabled": True},
            "global": {"card_border_width_px": 3},
        })

        tab = WidgetsTab(
            settings_manager,
            lazy_sections=True,
            initial_view_state={"subtab_id": "visualizers"},
        )
        try:
            assert hasattr(tab, "vis_enabled_checkbox")
            assert not hasattr(tab, "media_enabled")
            tab.vis_enabled_checkbox.setChecked(False)
            tab._save_settings_now()

            widgets_cfg = settings_manager.get("widgets", {})
            assert widgets_cfg.get("spotify_visualizer", {}).get("enabled") is False
            assert widgets_cfg.get("media", {}).get("enabled") is True
            assert widgets_cfg.get("media", {}).get("position") == "Bottom Right"
            assert widgets_cfg.get("media", {}).get("font_size") == 27
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
                "version": 1,
                "displays": {
                    "screen:test": {
                        "clock": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.2, "height": 0.1},
                            "size_payload": {"font_size": 64},
                            "resize_mode": "clock_font",
                        }
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
            "media": {"enabled": True, "position": "Custom", "monitor": "1"},
            "custom_layout": {
                "version": 1,
                "displays": {
                    "screen:test": {
                        "media": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                            "size_payload": {"font_size": 22, "artwork_size": 220},
                            "resize_mode": "media_scale",
                        }
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
                "show_digital_separator": True,
                "calendar_font_size": 28,
            },
            "custom_layout": {
                "version": 1,
                "displays": {
                    "screen:test": {
                        "clock": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                            "size_payload": {"font_size": 64},
                            "resize_mode": "clock_font",
                        }
                    }
                },
            },
        })

        tab = WidgetsTab(settings_manager)
        try:
            assert tab.clock_font_size.isEnabled() is False
            assert tab.clock_calendar_font_size.isEnabled() is False
            assert tab.clock_show_digital_separator.isChecked() is True
            assert tab.clock_font_combo.isEnabled() is True
            assert tab._custom_resize_lock_notice_labels["clock"].isHidden() is False
        finally:
            tab.deleteLater()

    def test_widgets_tab_disable_custom_mode_link_restores_authored_layout(self, qt_app, settings_manager, monkeypatch):
        settings_manager.set("widgets", {
            "media": {"enabled": True, "position": "Custom", "monitor": "1"},
            "spotify_visualizer": {"position": "Custom", "monitor": "2"},
            "custom_layout": {
                "version": 1,
                "displays": {
                    "screen:test": {
                        "media": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                            "size_payload": {"font_size": 22, "artwork_size": 220},
                            "resize_mode": "media_scale",
                        },
                        "spotify_volume": {
                            "rect": {"x": 0.4, "y": 0.2, "width": 0.05, "height": 0.3},
                            "size_payload": {"width": 32, "height": 180},
                            "resize_mode": "volume_scale",
                        },
                        "spotify_visualizer": {
                            "rect": {"x": 0.55, "y": 0.2, "width": 0.18, "height": 0.22},
                            "size_payload": {"width_scale": 1.2, "height_scale": 1.1},
                            "resize_mode": "visualizer_rect",
                        },
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
                "version": 1,
                "displays": {
                    "screen:test": {
                        "media": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                            "size_payload": {"font_size": 22, "artwork_size": 220},
                            "resize_mode": "media_scale",
                        }
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
                "version": 1,
                "displays": {
                    "screen:test": {
                        "media": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                            "size_payload": {"font_size": 22, "artwork_size": 220},
                            "resize_mode": "media_scale",
                        },
                        "spotify_visualizer": {
                            "rect": {"x": 0.55, "y": 0.2, "width": 0.18, "height": 0.22},
                            "size_payload": {"width_scale": 1.2, "height_scale": 1.1},
                            "resize_mode": "visualizer_rect",
                        },
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
                "version": 1,
                "displays": {
                    "screen:test": {
                        "media": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                            "size_payload": {"font_size": 22, "artwork_size": 220},
                            "resize_mode": "media_scale",
                        },
                        "gmail": {
                            "rect": {"x": 0.5, "y": 0.1, "width": 0.2, "height": 0.2},
                            "size_payload": {"font_size": 15},
                            "resize_mode": "gmail_font",
                        }
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
            assert widgets_cfg["shadows"] == {
                "enabled": True,
                "text_enabled": True,
                "header_enabled": False,
            }
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
                "version": 1,
                "displays": {
                    "screen:test": {
                        "media": {
                            "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                            "size_payload": {"font_size": 22, "artwork_size": 220},
                            "resize_mode": "media_scale",
                        },
                        "spotify_visualizer": {
                            "rect": {"x": 0.55, "y": 0.2, "width": 0.18, "height": 0.22},
                            "size_payload": {"width_scale": 1.2, "height_scale": 1.1},
                            "resize_mode": "visualizer_rect",
                        },
                        "gmail": {
                            "rect": {"x": 0.5, "y": 0.1, "width": 0.2, "height": 0.2},
                            "size_payload": {"font_size": 15},
                            "resize_mode": "gmail_font",
                        },
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
            assert isinstance(tab._imgur_color, QColor)
        finally:
            tab.deleteLater()

    def test_sine_wave_swatch_persistence(self, qt_app, settings_manager):
        """Glow + line swatch selections persist through save/load and update buttons."""

        def _rgba_tuple(color: QColor) -> tuple[int, int, int, int]:
            return color.red(), color.green(), color.blue(), color.alpha()

        first_tab = WidgetsTab(settings_manager)

        # Must set mode to sine_wave before saving sine-specific settings
        # (save_media_settings now only collects current mode's settings)
        first_tab.vis_mode_combo.setCurrentIndex(first_tab.vis_mode_combo.findData("sine_wave"))
        first_tab._sine_preset_slider.set_preset_index(
            first_tab._sine_preset_slider.custom_index()
        )
        qt_app.processEvents()

        custom_glow = QColor(12, 34, 56, 200)
        custom_line = QColor(210, 180, 150, 128)
        first_tab._sine_glow_color = custom_glow
        first_tab._sine_line_color = custom_line
        first_tab._save_settings_now()
        first_tab.deleteLater()

        reloaded_tab = WidgetsTab(settings_manager)
        try:
            assert _rgba_tuple(reloaded_tab._sine_glow_color) == _rgba_tuple(custom_glow)
            assert _rgba_tuple(reloaded_tab._sine_line_color) == _rgba_tuple(custom_line)
            assert _rgba_tuple(reloaded_tab.sine_glow_color_btn.color()) == _rgba_tuple(custom_glow)
            assert _rgba_tuple(reloaded_tab.sine_line_color_btn.color()) == _rgba_tuple(custom_line)
        finally:
            reloaded_tab.deleteLater()

    def test_spectrum_swatch_persistence(self, qt_app, settings_manager):
        """Spectrum bar fill/border swatches persist and hydrate swatch buttons."""

        def _rgba_tuple(color: QColor) -> tuple[int, int, int, int]:
            return color.red(), color.green(), color.blue(), color.alpha()

        first_tab = WidgetsTab(settings_manager)
        first_tab.vis_mode_combo.setCurrentIndex(
            first_tab.vis_mode_combo.findData("spectrum")
        )
        first_tab._spectrum_preset_slider.set_preset_index(
            first_tab._spectrum_preset_slider.custom_index()
        )
        qt_app.processEvents()

        custom_fill = QColor(90, 200, 145, 210)
        custom_border = QColor(30, 60, 90, 255)
        first_tab._spotify_vis_fill_color = custom_fill
        first_tab._spotify_vis_border_color = custom_border
        first_tab._save_settings_now()
        first_tab.deleteLater()

        reloaded_tab = WidgetsTab(settings_manager)
        try:
            assert _rgba_tuple(reloaded_tab._spotify_vis_fill_color) == _rgba_tuple(custom_fill)
            assert _rgba_tuple(reloaded_tab._spotify_vis_border_color) == _rgba_tuple(custom_border)
            assert _rgba_tuple(reloaded_tab.vis_fill_color_btn.color()) == _rgba_tuple(custom_fill)
            assert _rgba_tuple(reloaded_tab.vis_border_color_btn.color()) == _rgba_tuple(custom_border)
        finally:
            reloaded_tab.deleteLater()

    def test_oscilloscope_swatch_persistence(self, qt_app, settings_manager):
        """Oscilloscope glow + line swatches persist through save/load and sync button UI."""

        def _rgba_tuple(color: QColor) -> tuple[int, int, int, int]:
            return color.red(), color.green(), color.blue(), color.alpha()

        first_tab = WidgetsTab(settings_manager)

        # Must set mode to oscilloscope before saving osc-specific settings
        first_tab.vis_mode_combo.setCurrentIndex(first_tab.vis_mode_combo.findData("oscilloscope"))
        first_tab._osc_preset_slider.set_preset_index(
            first_tab._osc_preset_slider.custom_index()
        )
        qt_app.processEvents()

        custom_glow = QColor(33, 77, 190, 210)
        custom_line = QColor(240, 245, 250, 180)
        first_tab._osc_glow_color = custom_glow
        first_tab._osc_line_color = custom_line
        first_tab._save_settings_now()
        first_tab.deleteLater()

        reloaded_tab = WidgetsTab(settings_manager)
        try:
            assert _rgba_tuple(reloaded_tab._osc_glow_color) == _rgba_tuple(custom_glow)
            assert _rgba_tuple(reloaded_tab._osc_line_color) == _rgba_tuple(custom_line)
            assert _rgba_tuple(reloaded_tab.osc_glow_color_btn.color()) == _rgba_tuple(custom_glow)
            assert _rgba_tuple(reloaded_tab.osc_line_color_btn.color()) == _rgba_tuple(custom_line)
        finally:
            reloaded_tab.deleteLater()

    def test_secondary_line_ghost_toggles_persist(self, qt_app, settings_manager):
        """Osc and Sine ghost toggles persist when saved in their respective modes.

        Note: mode-scoped save only saves current mode's settings. This test
        verifies each mode's toggles persist independently when saved in that mode.
        """
        # Test oscilloscope ghost toggles persist
        osc_tab = WidgetsTab(settings_manager)
        osc_tab.vis_mode_combo.setCurrentIndex(osc_tab.vis_mode_combo.findData("oscilloscope"))
        qt_app.processEvents()
        osc_tab.osc_ghost_line2_enabled.setChecked(False)
        osc_tab.osc_ghost_line3_enabled.setChecked(True)
        osc_tab._save_settings_now()
        osc_tab.deleteLater()

        reloaded_osc = WidgetsTab(settings_manager)
        try:
            assert reloaded_osc.osc_ghost_line2_enabled.isChecked() is False
            assert reloaded_osc.osc_ghost_line3_enabled.isChecked() is True
        finally:
            reloaded_osc.deleteLater()

        # Test sine ghost toggles persist
        sine_tab = WidgetsTab(settings_manager)
        sine_tab.vis_mode_combo.setCurrentIndex(sine_tab.vis_mode_combo.findData("sine_wave"))
        qt_app.processEvents()
        sine_tab.sine_ghost_line2_enabled.setChecked(True)
        sine_tab.sine_ghost_line3_enabled.setChecked(False)
        sine_tab._save_settings_now()
        sine_tab.deleteLater()

        reloaded_sine = WidgetsTab(settings_manager)
        try:
            assert reloaded_sine.sine_ghost_line2_enabled.isChecked() is True
            assert reloaded_sine.sine_ghost_line3_enabled.isChecked() is False
        finally:
            reloaded_sine.deleteLater()

    def test_visualizer_advanced_edit_switches_to_custom(self, qt_app, settings_manager):
        tab = WidgetsTab(settings_manager)
        try:
            tab._load_settings()
            tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData("bubble"))
            preset_slider = getattr(tab, "_bubble_preset_slider", None)
            assert preset_slider is not None

            preset_slider.set_preset_index(0)  # curated preset without emitting
            widgets_cfg = tab._settings.get('widgets', {}) or {}
            spotify_vis = widgets_cfg.setdefault('spotify_visualizer', {})
            spotify_vis['preset_bubble'] = 0
            tab._settings.set('widgets', widgets_cfg)
            tab._settings.save()

            pulse_slider = getattr(tab, "bubble_big_bass_pulse", None)
            assert pulse_slider is not None
            pulse_slider.setValue(min(pulse_slider.maximum(), pulse_slider.value() + 5))
            qt_app.processEvents()
            tab._save_settings_now()

            assert preset_slider.preset_index() == preset_slider.custom_index()
            widgets_cfg = tab._settings.get('widgets', {}) or {}
            spotify_vis = widgets_cfg.get('spotify_visualizer', {})
            assert spotify_vis.get('preset_bubble') == preset_slider.custom_index()
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


def test_sine_curated_preset_survives_save_and_reload(qt_app, settings_manager):
    """Selecting a curated Sine preset must not silently fall back to Custom."""

    tab = WidgetsTab(settings_manager)
    try:
        mode = "sine_wave"
        curated_index = 0
        slider = tab._sine_preset_slider
        custom_index = slider.custom_index()

        tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData(mode))
        slider.set_preset_index(custom_index)
        slider._slider.setValue(curated_index)
        qt_app.processEvents()
        tab._save_settings_now()

        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert saved.get("preset_sine_wave") == curated_index
        assert slider.preset_index() == curated_index
        assert slider.preset_index() != custom_index
    finally:
        tab.deleteLater()

    reloaded = WidgetsTab(settings_manager)
    try:
        reloaded._load_settings()
        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert saved.get("preset_sine_wave") == curated_index
        assert reloaded._sine_preset_slider.preset_index() == curated_index
        assert reloaded._sine_preset_slider.preset_index() != reloaded._sine_preset_slider.custom_index()
    finally:
        reloaded.deleteLater()


def test_visualizer_mode_builders_keep_preset_scaffold_wiring(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        for descriptor in iter_visualizer_mode_descriptors():
            slider = getattr(tab, descriptor.preset_slider_attr)
            assert slider._advanced_container is not None, descriptor.mode_id
            assert slider._technical_container is not None, descriptor.mode_id
            assert slider._advanced_container.parent() is not None, descriptor.mode_id
            assert slider._technical_container.parent() is not None, descriptor.mode_id
    finally:
        tab.deleteLater()


def test_visualizer_sparse_mapping_uses_first_preset_fallback(qt_app, settings_manager):
    widgets_cfg = settings_manager.get("widgets", {}) or {}
    widgets_cfg["spotify_visualizer"] = {
        "mode": "sine_wave",
    }
    settings_manager.set("widgets", widgets_cfg)

    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        assert tab._sine_preset_slider.preset_index() == 0
        assert tab._bubble_preset_slider.preset_index() == 0
    finally:
        tab.deleteLater()


def test_visualizer_mode_roundtrip_uses_shared_binding_contract(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData("bubble"))
        qt_app.processEvents()
        tab._save_settings_now()

        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert saved.get("mode") == "bubble"
    finally:
        tab.deleteLater()

    reloaded = WidgetsTab(settings_manager)
    try:
        reloaded._load_settings()
        assert reloaded.vis_mode_combo.currentData() == "bubble"
    finally:
        reloaded.deleteLater()


def test_visualizer_unknown_saved_mode_falls_back_to_registry_default(qt_app, settings_manager):
    widgets_cfg = settings_manager.get("widgets", {}) or {}
    widgets_cfg["spotify_visualizer"] = {
        "mode": "not_a_real_mode",
    }
    settings_manager.set("widgets", widgets_cfg)

    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        assert tab.vis_mode_combo.currentData() == get_default_visualizer_mode_id()
    finally:
        tab.deleteLater()


def test_visualizer_custom_preset_roundtrip(qt_app, settings_manager):
    """Custom visualizer config survives curated preset switches and restores UI state."""

    tab = WidgetsTab(settings_manager)
    try:
        mode = "spectrum"
        tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData(mode))
        slider = getattr(tab, "_spectrum_preset_slider", None)
        assert slider is not None
        custom_index = slider.custom_index()

        custom_snapshot = {
            "mode": mode,
            "preset_spectrum": custom_index,
            "monitor": "PRIMARY",
            "spectrum_growth": 3.7,
            "spectrum_wave_amplitude": 0.82,
            "spectrum_shape_nodes": [[0.0, 0.15], [0.4, 0.85], [1.0, 0.55]],
            "spectrum_profile_floor": 0.08,
        }

        widgets_cfg = settings_manager.get("widgets", {}) or {}
        widgets_cfg["spotify_visualizer"] = custom_snapshot.copy()
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()
        # Save immediately during preset changes to avoid timer-based debounce in tests.
        tab._save_settings = tab._save_settings_now

        # Switch to curated preset slot 0 (should snapshot custom state first).
        slider.set_preset_index(0)
        tab._on_visualizer_preset_changed(mode, 0)

        cache = settings_manager.get("visualizer_custom_presets", {})
        assert isinstance(cache, dict)
        assert mode in cache
        assert cache[mode]["spectrum_growth"] == pytest.approx(3.7)

        # Switch back to Custom and expect the snapshot to restore values.
        slider.set_preset_index(custom_index)
        tab._on_visualizer_preset_changed(mode, custom_index)

        restored = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert restored.get("preset_spectrum") == custom_index
        assert restored.get("spectrum_growth") == pytest.approx(3.7)
        assert restored.get("spectrum_wave_amplitude") == pytest.approx(0.82)
        assert restored.get("spectrum_profile_floor") == pytest.approx(0.08)
    finally:
        tab.deleteLater()

def test_spectrum_custom_roundtrip_preserves_broad_state(qt_app, settings_manager):
    """Spectrum Custom should restore broad advanced + technical state without curated bleed."""
    from ui.tabs.media.technical_controls import get_per_mode_controls_for_mode

    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        tab._save_settings = tab._save_settings_now

        mode = "spectrum"
        tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData(mode))
        slider = tab._spectrum_preset_slider
        custom_index = slider.custom_index()

        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.update({
            "mode": mode,
            "preset_spectrum": custom_index,
            "spectrum_growth": 3.1,
            "spectrum_render_mode": "segment",
            "spectrum_border_radius": 1.0,
            "spectrum_glow_enabled": False,
            "spectrum_glow_intensity": 0.55,
            "spectrum_glow_color": [110, 220, 255, 235],
            "spectrum_mirrored": True,
            "spectrum_bar_count": 33,
            "spectrum_sensitivity": 0.50,
            "spectrum_manual_floor": 0.12,
            "spectrum_agc_strength": 0.50,
            "spectrum_kick_lane_gain": 1.0,
            "spectrum_lane_transient_mix": 0.65,
        })
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()

        tab._spotify_vis_fill_color = QColor(12, 122, 210, 211)
        tab._spotify_vis_border_color = QColor(220, 180, 80, 255)
        tab.vis_border_opacity.setValue(73)
        tab.vis_ghost_enabled.setChecked(False)
        tab.vis_ghost_opacity_slider.setValue(33)
        tab.vis_ghost_decay_slider.setValue(71)
        tab.spectrum_growth.setValue(370)
        tab._set_spectrum_render_mode("bars")
        tab.spectrum_rainbow_per_bar.setChecked(True)
        tab.spectrum_border_radius.setValue(7)
        tab.spectrum_glow_enabled.setChecked(True)
        tab.spectrum_glow_intensity.setValue(94)
        tab._spectrum_glow_color = QColor(15, 230, 255, 210)
        tab.spectrum_mirrored.setChecked(False)
        tab.spectrum_wave_amplitude.setValue(93)
        tab.spectrum_profile_floor.setValue(17)
        tab.spectrum_drop_speed.setValue(241)
        if hasattr(tab, "spectrum_shape_editor"):
            tab.spectrum_shape_editor.set_nodes([[0.0, 0.10], [0.4, 0.85], [1.0, 0.65]])
            tab.spectrum_shape_editor.set_lane_strengths(
                {"Bass": 0.81, "Low-Mid": 0.62, "Vocal": 0.57, "Hi-Mid": 0.78, "Treble": 0.94},
                mirrored=False,
            )

        controls = get_per_mode_controls_for_mode(tab, mode)
        assert controls is not None
        controls["bar_count"].setValue(44)
        controls["sensitivity_slider"].setValue(77)
        controls["manual_floor"].setValue(26)
        controls["agc_strength_slider"].setValue(61)
        controls["kick_gain_slider"].setValue(155)
        controls["mix_slider"].setValue(88)

        slider.set_preset_index(0)
        tab._on_visualizer_preset_changed(mode, 0)

        cache = settings_manager.get("visualizer_custom_presets", {})
        assert isinstance(cache, dict)
        snapshot = cache[mode]
        assert snapshot["spectrum_bar_fill_color"] == [12, 122, 210, 211]
        assert snapshot["spectrum_bar_border_color"] == [220, 180, 80, 255]
        assert snapshot["spectrum_bar_border_opacity"] == pytest.approx(0.73)
        assert snapshot["spectrum_growth"] == pytest.approx(3.7)
        assert snapshot["spectrum_render_mode"] == "bars"
        assert snapshot["spectrum_border_radius"] == pytest.approx(7.0)
        assert snapshot["spectrum_glow_enabled"] is True
        assert snapshot["spectrum_glow_intensity"] == pytest.approx(0.94)
        assert snapshot["spectrum_glow_color"] == [15, 230, 255, 210]
        assert snapshot["spectrum_mirrored"] is False
        assert snapshot["spectrum_shape_nodes"] == [[0.0, 0.10], [0.4, 0.85], [1.0, 0.65]]
        assert snapshot["spectrum_bar_count"] == 44
        assert snapshot["spectrum_sensitivity"] == pytest.approx(0.77)
        assert snapshot["spectrum_manual_floor"] == pytest.approx(0.26)
        assert snapshot["spectrum_agc_strength"] == pytest.approx(0.61)
        assert snapshot["spectrum_kick_lane_gain"] == pytest.approx(1.55)
        assert snapshot["spectrum_lane_transient_mix"] == pytest.approx(0.88)

        slider.set_preset_index(custom_index)
        tab._on_visualizer_preset_changed(mode, custom_index)

        restored = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert restored.get("spectrum_bar_fill_color") == [12, 122, 210, 211]
        assert restored.get("spectrum_bar_border_color") == [220, 180, 80, 255]
        assert restored.get("spectrum_bar_border_opacity") == pytest.approx(0.73)
        assert restored.get("spectrum_growth") == pytest.approx(3.7)
        assert restored.get("spectrum_render_mode") == "bars"
        assert restored.get("spectrum_border_radius") == pytest.approx(7.0)
        assert restored.get("spectrum_glow_enabled") is True
        assert restored.get("spectrum_glow_intensity") == pytest.approx(0.94)
        assert restored.get("spectrum_glow_color") == [15, 230, 255, 210]
        assert restored.get("spectrum_mirrored") is False
        assert restored.get("spectrum_shape_nodes") == [[0.0, 0.10], [0.4, 0.85], [1.0, 0.65]]
        assert restored.get("spectrum_lane_strengths_linear") == {
            "Bass": pytest.approx(0.81),
            "Low-Mid": pytest.approx(0.62),
            "Vocal": pytest.approx(0.57),
            "Hi-Mid": pytest.approx(0.78),
            "Treble": pytest.approx(0.94),
        }
        assert restored.get("spectrum_bar_count") == 44
        assert restored.get("spectrum_sensitivity") == pytest.approx(0.77)
        assert restored.get("spectrum_manual_floor") == pytest.approx(0.26)
        assert restored.get("spectrum_agc_strength") == pytest.approx(0.61)
        assert restored.get("spectrum_kick_lane_gain") == pytest.approx(1.55)
        assert restored.get("spectrum_lane_transient_mix") == pytest.approx(0.88)
        for retired_global in (
            "bar_count",
            "adaptive_sensitivity",
            "sensitivity",
            "dynamic_floor",
            "manual_floor",
            "dynamic_range_enabled",
            "agc_strength",
            "input_gain",
            "kick_lane_gain",
            "transient_pulse_gain",
            "transient_clamp",
            "audio_block_size",
        ):
            assert retired_global not in restored
    finally:
        tab.deleteLater()

def test_bubble_custom_snapshot_uses_live_ui_state_for_colors(qt_app, settings_manager):
    """Leaving Bubble custom snapshots current swatches even before an explicit save."""

    def _rgba_tuple(color: QColor) -> tuple[int, int, int, int]:
        return color.red(), color.green(), color.blue(), color.alpha()

    tab = WidgetsTab(settings_manager)
    try:
        mode = "bubble"
        tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData(mode))
        slider = getattr(tab, "_bubble_preset_slider", None)
        assert slider is not None
        custom_index = slider.custom_index()

        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.update({
            "mode": mode,
            "preset_bubble": custom_index,
            "bubble_gradient_light": [20, 30, 40, 255],
            "bubble_stream_reactivity": 0.2,
        })
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()
        tab._save_settings = tab._save_settings_now

        live_color = QColor(171, 122, 77, 240)
        tab._bubble_gradient_light = live_color

        slider.set_preset_index(0)
        tab._on_visualizer_preset_changed(mode, 0)

        cache = settings_manager.get("visualizer_custom_presets", {})
        assert isinstance(cache, dict)
        assert cache[mode]["bubble_gradient_light"] == list(_rgba_tuple(live_color))
    finally:
        tab.deleteLater()

def test_bubble_custom_snapshot_uses_live_ui_state_for_reactive_speed(qt_app, settings_manager):
    """Leaving Bubble custom snapshots the current reactive-speed slider value."""

    tab = WidgetsTab(settings_manager)
    try:
        mode = "bubble"
        tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData(mode))
        slider = getattr(tab, "_bubble_preset_slider", None)
        assert slider is not None
        custom_index = slider.custom_index()

        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.update({
            "mode": mode,
            "preset_bubble": custom_index,
            "bubble_stream_reactivity": 0.15,
        })
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()
        tab._save_settings = tab._save_settings_now

        tab.bubble_stream_reactivity.setValue(95)

        slider.set_preset_index(0)
        tab._on_visualizer_preset_changed(mode, 0)

        cache = settings_manager.get("visualizer_custom_presets", {})
        assert isinstance(cache, dict)
        assert cache[mode]["bubble_stream_reactivity"] == pytest.approx(0.95)
    finally:
        tab.deleteLater()

def test_bubble_stream_reactivity_load_clamps_to_200(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        custom_index = tab._bubble_preset_slider.custom_index()
        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.update({
            "mode": "bubble",
            "preset_bubble": custom_index,
            "bubble_stream_reactivity": 2.75,
        })
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()

        assert tab.bubble_stream_reactivity.maximum() == 200
        assert tab.bubble_stream_reactivity.value() == 200
        assert tab.bubble_stream_reactivity_label.text() == "200%"
    finally:
        tab.deleteLater()


def test_bubble_legacy_gradient_direction_loads_as_canonical_label_and_saves_version(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        custom_index = tab._bubble_preset_slider.custom_index()
        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.pop("bubble_gradient_semantics_version", None)
        spotify_vis.update({
            "mode": "bubble",
            "preset_bubble": custom_index,
            "bubble_gradient_direction": "left",
        })
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()

        assert tab.bubble_gradient_direction.currentData() == "right"

        tab._save_settings_now()

        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert saved.get("bubble_gradient_direction") == "right"
        assert saved.get("bubble_gradient_semantics_version") == 2
    finally:
        tab.deleteLater()


def test_bubble_center_out_reverse_round_trips_through_widgets_tab(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        custom_index = tab._bubble_preset_slider.custom_index()
        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.update({
            "mode": "bubble",
            "preset_bubble": custom_index,
            "bubble_gradient_direction": "center_out_reverse",
            "bubble_gradient_semantics_version": 2,
        })
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()

        assert tab.bubble_gradient_direction.currentData() == "center_out_reverse"

        tab._save_settings_now()

        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert saved.get("bubble_gradient_direction") == "center_out_reverse"
        assert saved.get("bubble_gradient_semantics_version") == 2
    finally:
        tab.deleteLater()


def test_spectrum_builder_uses_real_bucket_order_and_collapsible_sections(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        normal_layout = tab._spectrum_normal.layout()
        normal_titles = []
        for idx in range(normal_layout.count()):
            widget = normal_layout.itemAt(idx).widget()
            if widget is not None:
                title = widget.property("bucketTitle")
                if title:
                    normal_titles.append(title)
        assert normal_titles == ["Appearance", "Shape"]

        adv_layout = tab._spectrum_advanced.layout()
        adv_titles = []
        for idx in range(adv_layout.count()):
            widget = adv_layout.itemAt(idx).widget()
            if widget is not None:
                title = widget.property("bucketTitle")
                if title:
                    adv_titles.append(title)
        assert adv_titles == ["Render", "Audio", "Ghost"]
    finally:
        tab.deleteLater()


def test_spectrum_builder_uses_explicit_bar_segment_render_mode_buttons(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        assert set(tab.spectrum_render_mode_buttons.keys()) == {"segment", "bars"}
        assert tab.spectrum_render_mode_buttons["bars"].text() == "BAR"
        assert tab.spectrum_render_mode_buttons["segment"].text() == "SEGMENTS"
        assert tab._spectrum_render_mode in {"bars", "segment"}
    finally:
        tab.deleteLater()


def test_widgets_tab_curated_preset_apply_ignores_stale_custom_runtime_values(qt_app, settings_manager):
    """Settings GUI preset apply should commit curated values, not stale custom values."""
    from core.settings.models import SpotifyVisualizerSettings

    tab = WidgetsTab(settings_manager)
    try:
        mode = "bubble"
        tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData(mode))
        slider = getattr(tab, "_bubble_preset_slider", None)
        assert slider is not None
        tab._save_settings = tab._save_settings_now

        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.update(
            {
                "mode": mode,
                "preset_bubble": slider.custom_index(),
                # Deliberately conflicting values.
                "bubble_manual_floor": 0.31,
                "bubble_audio_block_size": 256,
            }
        )
        settings_manager.set("widgets", widgets_cfg)
        tab._load_settings()

        slider.set_preset_index(0)
        tab._on_visualizer_preset_changed(mode, 0)

        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        saved_model = SpotifyVisualizerSettings.from_mapping(saved)
        baseline = SpotifyVisualizerSettings.from_mapping({"mode": mode, "preset_bubble": 0})

        assert saved_model.resolve_manual_floor("bubble") == pytest.approx(
            baseline.resolve_manual_floor("bubble")
        )
        assert saved_model.resolve_audio_block_size("bubble") == baseline.resolve_audio_block_size("bubble")
    finally:
        tab.deleteLater()


def test_move_to_custom_preserves_current_visualizer_colors(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        tab._save_settings = tab._save_settings_now
        mode = "bubble"
        slider = tab._bubble_preset_slider

        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.update({
            "mode": mode,
            "preset_bubble": 0,
            "bubble_gradient_light": [10, 20, 30, 255],
            "bubble_gradient_dark": [40, 50, 60, 255],
            "bubble_outline_color": [70, 80, 90, 255],
        })
        settings_manager.set("widgets", widgets_cfg)
        settings_manager.set("visualizer_custom_presets", {
            mode: {
                "mode": mode,
                "bubble_gradient_light": [200, 1, 2, 255],
                "bubble_gradient_dark": [201, 3, 4, 255],
                "bubble_outline_color": [202, 5, 6, 255],
            }
        })

        tab._load_settings()

        resolved_light = [
            tab._bubble_gradient_light.red(),
            tab._bubble_gradient_light.green(),
            tab._bubble_gradient_light.blue(),
            tab._bubble_gradient_light.alpha(),
        ]
        resolved_dark = [
            tab._bubble_gradient_dark.red(),
            tab._bubble_gradient_dark.green(),
            tab._bubble_gradient_dark.blue(),
            tab._bubble_gradient_dark.alpha(),
        ]
        resolved_outline = [
            tab._bubble_outline_color.red(),
            tab._bubble_outline_color.green(),
            tab._bubble_outline_color.blue(),
            tab._bubble_outline_color.alpha(),
        ]
        assert resolved_light != [10, 20, 30, 255]

        slider.set_preset_index(0)
        slider._move_to_custom()

        cache = settings_manager.get("visualizer_custom_presets", {})
        assert cache[mode]["bubble_gradient_light"] == resolved_light
        assert cache[mode]["bubble_gradient_dark"] == resolved_dark
        assert cache[mode]["bubble_outline_color"] == resolved_outline
        assert [
            tab._bubble_gradient_light.red(),
            tab._bubble_gradient_light.green(),
            tab._bubble_gradient_light.blue(),
            tab._bubble_gradient_light.alpha(),
        ] == resolved_light
    finally:
        tab.deleteLater()


@pytest.mark.parametrize(
    ("mode", "expected_bar_count", "expected_sensitivity", "expected_floor", "expected_block"),
    (
        ("spectrum", 35, 0.97, 0.42, 128),
        ("oscilloscope", 32, 0.40, 0.12, 256),
        ("sine_wave", 40, 1.20, 0.40, 128),
        ("bubble", 48, 0.55, 0.30, 128),
        ("devcurve", 35, 1.35, 0.15, 256),
    ),
)
def test_move_to_custom_uses_runtime_resolved_curated_state_for_every_mode(
    qt_app,
    settings_manager,
    caplog,
    mode,
    expected_bar_count,
    expected_sensitivity,
    expected_floor,
    expected_block,
):
    """Every mode must fork the curated UI state, not stale backing values."""
    from ui.tabs.media.technical_controls import get_per_mode_controls_for_mode

    caplog.set_level(logging.INFO, logger="ui.tabs.media.preset_slider")

    stale = {
        f"{mode}_bar_count": 7,
        f"{mode}_sensitivity": 0.11,
        f"{mode}_manual_floor": 0.07,
        f"{mode}_audio_block_size": 512,
    }
    widgets_cfg = settings_manager.get("widgets", {}) or {}
    spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
    spotify_vis.update(
        {
            "mode": mode,
            f"preset_{mode}": 0,
            **stale,
        }
    )
    settings_manager.set("widgets", widgets_cfg)
    settings_manager.set(
        "visualizer_custom_presets",
        {
            mode: {
                "mode": mode,
                **stale,
            }
        },
    )

    tab = WidgetsTab(settings_manager)
    try:
        tab._save_settings = tab._save_settings_now
        tab._load_settings()
        slider = getattr(tab, get_preset_slider_attr(mode))
        controls = get_per_mode_controls_for_mode(tab, mode)
        assert controls is not None

        assert controls["bar_count"].value() == expected_bar_count
        assert controls["sensitivity_slider"].value() == round(expected_sensitivity * 100)
        assert controls["manual_floor"].value() == round(expected_floor * 100)
        assert controls["block_size"].currentData() == expected_block

        slider._move_to_custom()

        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        custom = settings_manager.get("visualizer_custom_presets", {})[mode]
        assert any(
            "[VIS_PRESETS] Move To Custom" in record.getMessage()
            and f"mode={mode}" in record.getMessage()
            and "source_index=0" in record.getMessage()
            and f"custom_index={slider.custom_index()}" in record.getMessage()
            for record in caplog.records
        )
        assert saved[f"preset_{mode}"] == slider.custom_index()
        assert custom[f"{mode}_bar_count"] == expected_bar_count
        assert custom[f"{mode}_sensitivity"] == pytest.approx(expected_sensitivity)
        assert custom[f"{mode}_manual_floor"] == pytest.approx(expected_floor)
        assert custom[f"{mode}_audio_block_size"] == expected_block
    finally:
        tab.deleteLater()


def test_move_to_custom_spectrum_flushes_custom_state_before_followup_edit(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        mode = "spectrum"
        slider = tab._spectrum_preset_slider
        custom_index = slider.custom_index()

        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.update({
            "mode": mode,
            "preset_spectrum": 0,
            "spectrum_render_mode": "bars",
            "spectrum_unique_colors": True,
            "spectrum_glow_enabled": False,
            "spectrum_glow_color": [110, 220, 255, 235],
        })
        settings_manager.set("widgets", widgets_cfg)
        settings_manager.set("visualizer_custom_presets", {
            mode: {
                "mode": mode,
                "spectrum_render_mode": "segment",
                "spectrum_unique_colors": False,
                "spectrum_glow_enabled": False,
            }
        })

        tab._load_settings()

        slider.set_preset_index(0)
        slider._move_to_custom()
        tab.spectrum_glow_enabled.setChecked(True)
        tab._save_settings_now()

        saved_widgets = settings_manager.get("widgets", {}) or {}
        saved_vis = saved_widgets.get("spotify_visualizer", {})
        custom_cache = settings_manager.get("visualizer_custom_presets", {})

        assert saved_vis.get("preset_spectrum") == custom_index
        assert saved_vis.get("spectrum_glow_enabled") is True
        assert saved_vis.get("spectrum_render_mode") == "bars"
        assert saved_vis.get("spectrum_unique_colors") is True
        assert custom_cache[mode]["spectrum_render_mode"] == "bars"
        assert custom_cache[mode]["spectrum_unique_colors"] is True
    finally:
        tab.deleteLater()


def test_spectrum_smoothing_edit_forks_curated_state_and_survives_recreation(
    qt_app,
    settings_manager,
):
    """A smoothing edit must copy the live preset, never restore stale Custom."""
    from ui.tabs.media.technical_controls import get_per_mode_controls_for_mode

    mode = "spectrum"
    widgets_cfg = settings_manager.get("widgets", {}) or {}
    spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
    spotify_vis.update(
        {
            "mode": mode,
            "preset_spectrum": 0,
            "spectrum_visual_smoothing_enabled": True,
            "spectrum_visual_smoothing": 0.50,
            # Stale underlying values from the live MC settings file. Runtime
            # correctly replaced these with Organs, but Settings previously
            # displayed and copied them into Custom.
            "spectrum_bar_count": 33,
            "spectrum_sensitivity": 0.40,
            "spectrum_manual_floor": 0.12,
            "spectrum_audio_block_size": 512,
        }
    )
    settings_manager.set("widgets", widgets_cfg)
    settings_manager.set(
        "visualizer_custom_presets",
        {
            mode: {
                "mode": mode,
                "spectrum_bar_count": 33,
                "spectrum_sensitivity": 0.40,
                "spectrum_manual_floor": 0.12,
                "spectrum_audio_block_size": 512,
                "spectrum_visual_smoothing_enabled": True,
                "spectrum_visual_smoothing": 0.90,
            }
        },
    )

    tab = WidgetsTab(settings_manager)
    recreated = None
    try:
        tab._load_settings()
        slider = tab._spectrum_preset_slider
        custom_index = slider.custom_index()
        controls = get_per_mode_controls_for_mode(tab, mode)
        assert controls is not None
        curated_state = {
            "bar_count": controls["bar_count"].value(),
            "sensitivity": controls["sensitivity_slider"].value() / 100.0,
            "manual_floor": controls["manual_floor"].value() / 100.0,
            "block_size": controls["block_size"].currentData(),
        }
        assert curated_state == {
            "bar_count": 35,
            "sensitivity": 0.97,
            "manual_floor": 0.42,
            "block_size": 128,
        }
        assert curated_state != {
            "bar_count": 33,
            "sensitivity": 0.40,
            "manual_floor": 0.12,
            "block_size": 512,
        }

        # This is the exact explicit-button route from the live MC evidence
        # (22:25:45): fork first, then tune smoothing while Custom is active.
        slider._move_to_custom()
        tab.spectrum_visual_smoothing.setValue(70)
        tab._save_settings_now()

        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        custom = settings_manager.get("visualizer_custom_presets", {})[mode]
        assert slider.preset_index() == custom_index
        assert saved["preset_spectrum"] == custom_index
        assert saved["spectrum_visual_smoothing_enabled"] is True
        assert saved["spectrum_visual_smoothing"] == pytest.approx(0.70)
        assert custom["spectrum_visual_smoothing"] == pytest.approx(0.70)
        assert custom["spectrum_bar_count"] == curated_state["bar_count"]
        assert custom["spectrum_sensitivity"] == pytest.approx(
            curated_state["sensitivity"]
        )
        assert custom["spectrum_manual_floor"] == pytest.approx(
            curated_state["manual_floor"]
        )
        assert custom["spectrum_audio_block_size"] == curated_state["block_size"]

        # Reconstruct the Settings tab as the runtime Settings-close workflow
        # does, and require the filter controls plus technical state to replay.
        recreated = WidgetsTab(settings_manager)
        recreated._load_settings()
        recreated_controls = get_per_mode_controls_for_mode(recreated, mode)
        assert recreated_controls is not None
        assert recreated._spectrum_preset_slider.preset_index() == custom_index
        assert recreated.spectrum_visual_smoothing_enabled.isChecked() is True
        assert recreated.spectrum_visual_smoothing.value() == 70
        assert recreated_controls["bar_count"].value() == curated_state["bar_count"]
        assert recreated_controls["sensitivity_slider"].value() == round(
            curated_state["sensitivity"] * 100
        )
        assert recreated_controls["manual_floor"].value() == round(
            curated_state["manual_floor"] * 100
        )
        assert recreated_controls["block_size"].currentData() == curated_state["block_size"]
    finally:
        if recreated is not None:
            recreated.deleteLater()
        tab.deleteLater()


def test_build_current_spotify_visualizer_config_uses_descriptor_owned_visualizers_saver(
    qt_app,
    settings_manager,
    monkeypatch,
):
    tab = WidgetsTab(settings_manager)
    try:
        base_config = {
            "mode": "spectrum",
            "spectrum_bar_count": 35,
            "spectrum_glow_enabled": True,
        }
        captured = {}

        def _fake_collect(owner, section_id, descriptors=None):
            captured["owner"] = owner
            captured["section_id"] = section_id
            captured["descriptors"] = descriptors
            return {"mode": "bubble", "bubble_growth": 3.2}

        monkeypatch.setattr("ui.tabs.widgets_tab.collect_widget_section_save_result", _fake_collect)

        result = tab._build_current_spotify_visualizer_config(base_config)

        assert captured["owner"] is tab
        assert captured["section_id"] == "visualizers"
        assert captured["descriptors"] == tab._widget_section_descriptors
        assert result["mode"] == "bubble"
        assert result["bubble_growth"] == pytest.approx(3.2)
        assert result["spectrum_bar_count"] == 35
    finally:
        tab.deleteLater()


def test_visualizer_preset_change_uses_descriptor_owned_visualizers_loader(
    qt_app,
    settings_manager,
    monkeypatch,
):
    tab = WidgetsTab(settings_manager)
    try:
        mode = "bubble"
        tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData(mode))
        slider = getattr(tab, "_bubble_preset_slider", None)
        assert slider is not None
        custom_index = slider.custom_index()

        widgets_cfg = settings_manager.get("widgets", {}) or {}
        widgets_cfg["spotify_visualizer"] = {
            "mode": mode,
            "preset_bubble": custom_index,
            "bubble_growth": 3.7,
        }
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()

        calls = []

        def _fake_load(owner, section_id, widgets_config, descriptors=None):
            calls.append(
                {
                    "owner": owner,
                    "section_id": section_id,
                    "widgets_config": dict(widgets_config),
                    "descriptors": descriptors,
                }
            )
            return True

        monkeypatch.setattr("ui.tabs.widgets_tab.load_widget_section", _fake_load)
        monkeypatch.setattr("ui.tabs.widgets_tab.load_per_mode_technical_controls", lambda *args, **kwargs: None)
        tab._save_settings = lambda: None

        slider.set_preset_index(0)
        tab._on_visualizer_preset_changed(mode, 0)

        assert len(calls) == 1
        assert calls[0]["owner"] is tab
        assert calls[0]["section_id"] == "visualizers"
        assert calls[0]["descriptors"] == tab._widget_section_descriptors
        assert calls[0]["widgets_config"]["spotify_visualizer"]["mode"] == mode
        assert calls[0]["widgets_config"]["spotify_visualizer"]["preset_bubble"] == 0
    finally:
        tab.deleteLater()


def test_save_settings_now_normalizes_sparse_visualizer_payload(qt_app, settings_manager, monkeypatch):
    tab = WidgetsTab(settings_manager)
    try:
        from ui.tabs import widgets_tab_media as media_module

        tab._load_settings()

        def _fake_save_visualizer_settings(_tab):
            return {
                "enabled": True,
                "mode": "spectrum",
                "preset_spectrum": 0,
                "spectrum_glow_enabled": True,
                "spectrum_glow_color": [255, 255, 255, 235],
            }

        monkeypatch.setattr(media_module, "save_visualizer_settings", _fake_save_visualizer_settings)

        tab._save_settings_now()

        saved_widgets = settings_manager.get("widgets", {}) or {}
        saved_vis = saved_widgets.get("spotify_visualizer", {})
        assert saved_vis.get("mode") == "spectrum"
        assert saved_vis.get("preset_spectrum") == 0
        assert saved_vis.get("spectrum_glow_enabled") is True
        assert saved_vis.get("spectrum_render_mode") == "bars"
        assert saved_vis.get("spectrum_unique_colors") is True
    finally:
        tab.deleteLater()


def test_build_visualizer_preset_payload_normalizes_mode_snapshot(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        from tools import visualizer_preset_repair as repair

        mode = "bubble"
        custom_index = tab._bubble_preset_slider.custom_index()
        widgets_cfg = settings_manager.get("widgets", {}) or {}
        widgets_cfg["spotify_visualizer"] = {
            "mode": mode,
            "preset_bubble": custom_index,
            "bubble_manual_floor": 0.28,
            "bubble_input_gain": 0.81,
            "bubble_growth": 3.4,
            "bubble_rainbow_enabled": True,
            "bubble_rainbow_speed": 0.62,
        }
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()
        payload = tab.build_visualizer_preset_payload(mode)
        assert payload

        snapshot = payload["snapshot"]["widgets"]["spotify_visualizer"]
        assert payload["visualizer_preset_override"] is True
        assert payload["visualizer_preset_mode"] == mode
        assert snapshot["bubble_manual_floor"] == pytest.approx(0.28)
        assert snapshot["bubble_input_gain"] == pytest.approx(0.81)
        assert snapshot["bubble_growth"] == pytest.approx(3.4)
        assert snapshot["bubble_rainbow_enabled"] is True
        assert snapshot["bubble_rainbow_speed"] == pytest.approx(0.62)
        assert "manual_floor" not in snapshot
        assert "input_gain" not in snapshot
        assert "ghosting_enabled" not in snapshot
        assert "ghost_alpha" not in snapshot
        assert "ghost_decay" not in snapshot
        assert "settings" not in payload
        assert "custom_preset_backup" not in payload["snapshot"]
        assert "bubble_use_raw_energy" not in snapshot
        assert "bubble_energy_boost" not in snapshot

        report = repair.audit_payload(mode, payload)
        assert report["problem_count"] == 0
    finally:
        tab.deleteLater()


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


@pytest.mark.parametrize(
    ("mode", "slider_attr", "mode_key", "mode_value"),
    [
        ("spectrum", "_spectrum_preset_slider", "spectrum_growth", 2.9),
        ("bubble", "_bubble_preset_slider", "bubble_growth", 3.2),
        ("sine_wave", "_sine_preset_slider", "sine_wave_growth", 1.7),
        ("oscilloscope", "_osc_preset_slider", "osc_growth", 2.4),
    ],
)
def test_build_visualizer_preset_payload_strips_retired_compat_keys_for_all_modes(
    qt_app,
    settings_manager,
    mode,
    slider_attr,
    mode_key,
    mode_value,
):
    tab = WidgetsTab(settings_manager)
    try:
        slider = getattr(tab, slider_attr)
        custom_index = slider.custom_index()
        prefix = MODE_KEY_PREFIXES[mode][0]
        widgets_cfg = settings_manager.get("widgets", {}) or {}
        widgets_cfg["spotify_visualizer"] = {
            "mode": mode,
            f"preset_{mode}": custom_index,
            f"{prefix}energy_boost": 1.33,
            f"{prefix}use_raw_energy": True,
            mode_key: mode_value,
        }
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()
        payload = tab.build_visualizer_preset_payload(mode)

        assert payload
        snapshot = payload["snapshot"]["widgets"]["spotify_visualizer"]
        assert f"{prefix}energy_boost" not in snapshot
        assert f"{prefix}use_raw_energy" not in snapshot
        assert "ghosting_enabled" not in snapshot
        assert "ghost_alpha" not in snapshot
        assert "ghost_decay" not in snapshot
        assert "osc_sensitivity" not in snapshot
        assert snapshot[mode_key] == pytest.approx(mode_value)
    finally:
        tab.deleteLater()


def test_build_current_widgets_config_uses_live_visualizer_builder(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        custom_index = tab._bubble_preset_slider.custom_index()
        widgets_cfg = settings_manager.get("widgets", {}) or {}
        widgets_cfg["spotify_visualizer"] = {
            "mode": "bubble",
            "preset_bubble": custom_index,
            "bubble_gradient_direction": "center_out_reverse",
            "bubble_gradient_semantics_version": 2,
            "bubble_big_bass_pulse": 0.72,
        }
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()

        built = tab._build_current_widgets_config()["spotify_visualizer"]

        assert built["mode"] == "bubble"
        assert built["bubble_gradient_direction"] == "center_out_reverse"
        assert built["bubble_gradient_semantics_version"] == 2
        assert built["bubble_big_bass_pulse"] == pytest.approx(0.72)
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

def test_visualizers_toggle_gates_controls(qt_app, settings_manager):
    """Master + Beat Visualizer toggles should persist state changes in settings."""

    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        tab._save_settings = tab._save_settings_now

        master_initial = tab.visualizers_enabled.isChecked()
        tab.visualizers_enabled.setChecked(not master_initial)
        tab._save_settings_now()
        cfg = tab._settings.get('widgets', {}).get('spotify_visualizer', {})
        assert cfg.get('visualizers_enabled') is (not master_initial)

        beat_initial = tab.vis_enabled_checkbox.isChecked()
        tab.vis_enabled_checkbox.setChecked(not beat_initial)
        tab._save_settings_now()
        cfg = tab._settings.get('widgets', {}).get('spotify_visualizer', {})
        assert cfg.get('enabled') is (not beat_initial)

        # Disable both to verify persisted reload state
        tab.visualizers_enabled.setChecked(False)
        tab.vis_enabled_checkbox.setChecked(False)
        tab._save_settings_now()
        tab.deleteLater()

        reloaded = WidgetsTab(settings_manager)
        try:
            reloaded._load_settings()
            qt_app.processEvents()
            cfg = reloaded._settings.get('widgets', {}).get('spotify_visualizer', {})
            assert cfg.get('visualizers_enabled') is False
            assert cfg.get('enabled') is False
        finally:
            reloaded.deleteLater()
    finally:
        pass

def test_visualizer_technical_bucket_visibility_roundtrip(qt_app, settings_manager):
    """Technical subsection visibility toggles should persist per mode."""
    from ui.tabs.media.technical_controls import get_per_mode_controls_for_mode

    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        controls = get_per_mode_controls_for_mode(tab, "spectrum")
        assert controls is not None

        agc_toggle = controls.get("agc_visibility_toggle")
        transient_toggle = controls.get("transient_visibility_toggle")
        assert agc_toggle is not None
        assert transient_toggle is not None

        agc_toggle.setChecked(True)
        transient_toggle.setChecked(False)
        qt_app.processEvents()

        assert tab.get_visualizer_tech_bucket_state("spectrum", "agc", False) is True
        assert tab.get_visualizer_tech_bucket_state("spectrum", "transient", True) is False

        tab.deleteLater()

        reloaded = WidgetsTab(settings_manager)
        try:
            reloaded._load_settings()
            reloaded_controls = get_per_mode_controls_for_mode(reloaded, "spectrum")
            assert reloaded_controls is not None
            reloaded_agc = reloaded_controls.get("agc_visibility_toggle")
            reloaded_transient = reloaded_controls.get("transient_visibility_toggle")
            assert reloaded_agc is not None
            assert reloaded_transient is not None
            assert reloaded_agc.isChecked() is True
            assert reloaded_transient.isChecked() is False
        finally:
            reloaded.deleteLater()
    finally:
        pass


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
        tab.clock_show_digital_separator.setChecked(True)
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
        assert built["show_digital_separator"] is True
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
        assert tab.clock_show_digital_separator.isEnabled() is False

        tab.clock_show_day_of_week.setChecked(True)
        assert tab._clock_calendar_controls_container.isHidden() is False
        assert tab._clock_calendar_layout_row.isHidden() is True
        assert tab.clock_show_digital_separator.isEnabled() is True

        tab.clock_show_date.setChecked(True)
        assert tab._clock_calendar_layout_row.isHidden() is False
        tab.clock_calendar_layout.setCurrentIndex(
            tab.clock_calendar_layout.findData("two_lines")
        )
        tab.clock_calendar_font_size.setValue(31)
        tab.clock_show_digital_separator.setChecked(True)

        clock, _, _ = save_clock_settings(tab)
        assert clock["show_day_of_week"] is True
        assert clock["show_date"] is True
        assert clock["show_digital_separator"] is True
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


def test_bubble_swirl_toggle_hides_conflicting_direction_rows(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()

        tab.bubble_swirl_enabled.setChecked(True)
        qt_app.processEvents()

        assert tab._bubble_stream_direction_row_widget.isHidden() is True
        assert tab._bubble_drift_direction_row_widget.isHidden() is True
        assert tab._bubble_swirl_direction_row_widget.isHidden() is False

        tab.bubble_swirl_enabled.setChecked(False)
        qt_app.processEvents()

        assert tab._bubble_stream_direction_row_widget.isHidden() is False
        assert tab._bubble_drift_direction_row_widget.isHidden() is False
        assert tab._bubble_swirl_direction_row_widget.isHidden() is True
    finally:
        tab.deleteLater()
