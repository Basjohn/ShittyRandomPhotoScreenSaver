"""Tests for SettingsManager."""
from core.settings import SettingsManager


def test_settings_manager_initialization(qt_app):
    """Test SettingsManager initialization."""
    manager = SettingsManager(organization="Test", application="ScreensaverTest")
    
    assert manager is not None
    
    manager.clear()


def test_get_set_setting(qt_app):
    """Test getting and setting values."""
    manager = SettingsManager(organization="Test", application="ScreensaverTest")
    
    # Set a value
    manager.set("test.key", "test value")
    
    # Get the value
    value = manager.get("test.key")
    assert value == "test value"
    
    manager.clear()


def test_default_values(qt_app):
    """Test default values are set."""
    manager = SettingsManager(organization="Test", application="ScreensaverTest")
    
    # Check some defaults exist
    assert manager.contains("sources.mode")
    assert manager.contains("display.mode")
    assert manager.contains("transitions")
    
    manager.clear()


def test_widget_defaults_helper_matches_schema(qt_app):
    """get_widget_defaults sections should mirror the widgets schema in _set_defaults.

    This is a light invariant test to catch accidental drift between the
    canonical defaults map and the helper used by UI code.
    """
    manager = SettingsManager(organization="Test", application="ScreensaverTest")

    # Force canonical defaults to be present in the underlying QSettings.
    manager.reset_to_defaults()

    widgets_value = manager.get("widgets", {})
    assert isinstance(widgets_value, dict)

    for section in ["clock", "clock2", "clock3", "weather", "media", "spotify_visualizer", "reddit", "shadows"]:
        helper_defaults = manager.get_widget_defaults(section)
        assert isinstance(helper_defaults, dict)

        schema_section = widgets_value.get(section, {})
        assert isinstance(schema_section, dict)

        # Every key exposed by get_widget_defaults must exist in the
        # canonical widgets map (and share the same type of value).
        for key, helper_val in helper_defaults.items():
            assert key in schema_section
            schema_val = schema_section[key]
            assert type(schema_val) is type(helper_val)


def test_on_changed_handler(qt_app):
    """Test change notification handler."""
    manager = SettingsManager(organization="Test", application="ScreensaverTest")
    
    changed_values = []
    
    def handler(new_value, old_value):
        changed_values.append((new_value, old_value))
    
    manager.on_changed("test.key", handler)
    
    # Change the value
    manager.set("test.key", "initial")
    manager.set("test.key", "updated")
    
    assert len(changed_values) >= 1
    
    manager.clear()


def test_reset_to_defaults(qt_app):
    """Test resetting to defaults."""
    manager = SettingsManager(organization="Test", application="ScreensaverTest")
    
    # Change a value
    manager.set("sources.mode", "custom_value")
    assert manager.get("sources.mode") == "custom_value"
    
    # Reset
    manager.reset_to_defaults()
    
    # Should be back to default
    assert manager.get("sources.mode") == "folders"
    
    manager.clear()


def test_get_all_keys(qt_app):
    """Test getting all keys."""
    manager = SettingsManager(organization="Test", application="ScreensaverTest")
    
    keys = manager.get_all_keys()
    
    assert isinstance(keys, list)
    assert len(keys) > 0
    assert "sources.mode" in keys
    
    manager.clear()
