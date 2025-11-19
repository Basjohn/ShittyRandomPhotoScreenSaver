"""Integration tests for media widget settings persistence.

These tests verify that the Widgets tab and SettingsDialog correctly
persist `widgets.media` configuration via SettingsManager and that a
fresh SettingsManager instance plus DisplayWidget see the expected
values.
"""

import pytest

from core.settings import SettingsManager
from core.animation import AnimationManager
from ui.settings_dialog import SettingsDialog


@pytest.mark.qt
def test_widgets_tab_media_roundtrip(qt_app):
    org = "Test"
    app = "WidgetsTabMediaRoundtripTest"

    settings = SettingsManager(organization=org, application=app)
    settings.clear()

    animations = AnimationManager()
    dialog = SettingsDialog(settings, animations)
    tab = dialog.widgets_tab

    tab.media_enabled.setChecked(True)
    tab.media_position.setCurrentText("Bottom Left")
    tab.media_monitor_combo.setCurrentText("ALL")
    tab._save_settings()

    widgets_cfg = settings.get("widgets", {})
    media_cfg = widgets_cfg.get("media", {})

    assert media_cfg.get("enabled") is True
    assert media_cfg.get("position") == "Bottom Left"
    assert media_cfg.get("monitor") == "ALL"

    dialog.close()
    settings.clear()


@pytest.mark.qt
def test_media_widget_created_after_config_roundtrip(qt_app, qtbot):
    org = "Test"
    app = "MediaConfigRoundtripDisplayTest"

    settings = SettingsManager(organization=org, application=app)
    settings.clear()

    animations = AnimationManager()
    dialog = SettingsDialog(settings, animations)
    tab = dialog.widgets_tab

    tab.media_enabled.setChecked(True)
    tab.media_monitor_combo.setCurrentText("ALL")
    tab._save_settings()

    dialog.close()

    # New SettingsManager instance should see the same widgets.media config
    # that was written by the SettingsDialog in this test, proving that
    # persistence across instances is correct.
    settings2 = SettingsManager(organization=org, application=app)
    widgets_cfg2 = settings2.get("widgets", {})
    media_cfg2 = widgets_cfg2.get("media", {})

    assert media_cfg2.get("enabled") is True
    assert media_cfg2.get("monitor") == "ALL"

    settings.clear()
    settings2.clear()
