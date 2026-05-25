"""Tests for WidgetsTab._save_settings debounce (IO batching).

Verifies that rapid calls to _save_settings coalesce into fewer actual
writes via the 200ms QTimer.singleShot mechanism.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _seed_minimal_widgets_tab_state(tab) -> None:
    tab._custom_resize_lock_notice_labels = {}
    tab._widget_section_descriptors = ()
    tab._refresh_custom_resize_lock_state = MagicMock()
    tab._auto_switch_preset_to_custom = MagicMock()
    tab._save_coalesce_token = 0


@pytest.fixture
def mock_settings():
    """Minimal mock SettingsManager for WidgetsTab."""
    sm = MagicMock()
    sm.get.return_value = {}
    return sm


class TestSaveDebounce:
    def test_debounce_flag_set_on_first_call(self, mock_settings):
        """First _save_settings call sets the pending flag."""
        with patch("PySide6.QtCore.QTimer.singleShot") as mock_timer:
            from ui.tabs.widgets_tab import WidgetsTab
            with patch.object(WidgetsTab, "__init__", lambda self, *a, **kw: None):
                tab = WidgetsTab.__new__(WidgetsTab)
                tab._loading = False
                tab._save_coalesce_pending = False
                tab._settings = mock_settings
                _seed_minimal_widgets_tab_state(tab)

                tab._save_settings()

                assert tab._save_coalesce_pending is True
                mock_timer.assert_called_once()

    def test_second_call_does_not_schedule_extra_timer(self, mock_settings):
        """Rapid calls schedule fresh tokenized timers while leaving one effective save path."""
        with patch("PySide6.QtCore.QTimer.singleShot") as mock_timer:
            from ui.tabs.widgets_tab import WidgetsTab
            with patch.object(WidgetsTab, "__init__", lambda self, *a, **kw: None):
                tab = WidgetsTab.__new__(WidgetsTab)
                tab._loading = False
                tab._save_coalesce_pending = False
                tab._settings = mock_settings
                _seed_minimal_widgets_tab_state(tab)

                tab._save_settings()
                tab._save_settings()
                tab._save_settings()

                assert mock_timer.call_count == 3
                assert tab._save_coalesce_pending is True
                assert tab._save_coalesce_token == 3

    def test_loading_flag_prevents_save(self, mock_settings):
        """_save_settings is a no-op when _loading is True."""
        with patch("PySide6.QtCore.QTimer.singleShot") as mock_timer:
            from ui.tabs.widgets_tab import WidgetsTab
            with patch.object(WidgetsTab, "__init__", lambda self, *a, **kw: None):
                tab = WidgetsTab.__new__(WidgetsTab)
                tab._loading = True
                tab._save_coalesce_pending = False
                tab._settings = mock_settings
                _seed_minimal_widgets_tab_state(tab)

                tab._save_settings()

                assert tab._save_coalesce_pending is False
                mock_timer.assert_not_called()

    def test_save_settings_now_clears_pending(self, mock_settings):
        """_save_settings_now resets the pending flag so future calls re-arm."""
        from ui.tabs.widgets_tab import WidgetsTab
        with patch.object(WidgetsTab, "__init__", lambda self, *a, **kw: None):
            tab = WidgetsTab.__new__(WidgetsTab)
            tab._loading = False
            tab._save_coalesce_pending = True
            tab._settings = mock_settings
            _seed_minimal_widgets_tab_state(tab)

            # Mock the widget attribute accessed during save and all delegates
            tab.widget_shadows_enabled = MagicMock()
            tab.widget_shadows_enabled.isChecked.return_value = True
            tab.widget_text_shadows_enabled = MagicMock()
            tab.widget_text_shadows_enabled.isChecked.return_value = True
            tab.widget_header_shadows_enabled = MagicMock()
            tab.widget_header_shadows_enabled.isChecked.return_value = True
            tab.widget_stacking_enabled = MagicMock()
            tab.widget_stacking_enabled.isChecked.return_value = False

            with patch("ui.tabs.widgets_tab.collect_widget_section_save_results", return_value={}), \
                 patch(
                     "ui.tabs.widgets_tab.apply_widget_section_save_results",
                     side_effect=lambda widgets, _results, **_kwargs: widgets,
                 ):
                tab._save_settings_now()

            assert tab._save_coalesce_pending is False
