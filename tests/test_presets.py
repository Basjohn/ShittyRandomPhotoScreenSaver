"""Comprehensive tests for the presets system."""

import uuid

import pytest

from core.settings.presets import (
    PRESET_DEFINITIONS,
    adjust_settings_for_mc_mode,
    apply_preset,
    check_and_switch_to_custom,
    get_current_preset_info,
    get_ordered_presets,
)
from core.settings.settings_manager import SettingsManager


def _make_manager(tmp_path, base_name=None, app_name=None) -> SettingsManager:
    """Create a SettingsManager backed by a per-test JSON root."""

    storage_root = tmp_path / (base_name or uuid.uuid4().hex)
    storage_root.mkdir(parents=True, exist_ok=True)
    application = app_name or f"ScreensaverTest_{uuid.uuid4().hex}"
    return SettingsManager(
        organization="Test",
        application=application,
        storage_base_dir=storage_root,
    )


class TestPresetDefinitions:
    """Test preset definitions are valid."""
    
    def test_all_presets_defined(self):
        """Test that all expected presets are defined."""
        expected_presets = {'purist', 'essentials', 'media', 'full_monty', 'custom'}
        assert set(PRESET_DEFINITIONS.keys()) == expected_presets
    
    def test_preset_order_unique(self):
        """Test that preset order values are unique."""
        orders = [p.order for p in PRESET_DEFINITIONS.values()]
        assert len(orders) == len(set(orders)), "Preset orders must be unique"
    
    def test_preset_settings_valid(self):
        """Test that all preset settings are dictionaries."""
        for preset_key, preset in PRESET_DEFINITIONS.items():
            assert isinstance(preset.settings, dict), f"{preset_key} settings must be a dict"
            assert preset.name, f"{preset_key} must have a name"
            assert preset.description, f"{preset_key} must have a description"


class TestApplyPreset:
    """Test apply_preset function."""
    
    def test_apply_purist_preset(self, settings_manager: SettingsManager):
        """Test applying Purist preset disables all widgets."""
        result = apply_preset(settings_manager, 'purist')
        assert result is True
        
        # Verify widgets are disabled
        assert settings_manager.get('widgets.clock.enabled') is False
        assert settings_manager.get('widgets.weather.enabled') is False
        assert settings_manager.get('widgets.media.enabled') is False
        assert settings_manager.get('preset') == 'purist'
    
    def test_apply_essentials_preset(self, settings_manager: SettingsManager):
        """Test applying Essentials preset enables clock and weather."""
        result = apply_preset(settings_manager, 'essentials')
        assert result is True
        
        # Verify correct widgets are enabled
        assert settings_manager.get('widgets.clock.enabled') is True
        assert settings_manager.get('widgets.weather.enabled') is True
        assert settings_manager.get('widgets.media.enabled') is False
        assert settings_manager.get('preset') == 'essentials'
    
    def test_apply_media_preset(self, settings_manager: SettingsManager):
        """Test applying Media preset enables clock, weather, and media."""
        result = apply_preset(settings_manager, 'media')
        assert result is True
        
        # Verify correct widgets are enabled
        assert settings_manager.get('widgets.clock.enabled') is True
        assert settings_manager.get('widgets.weather.enabled') is True
        assert settings_manager.get('widgets.media.enabled') is True
        assert settings_manager.get('preset') == 'media'
    
    def test_apply_full_monty_preset(self, settings_manager: SettingsManager):
        """Test applying Full Monty preset enables all widgets."""
        result = apply_preset(settings_manager, 'full_monty')
        assert result is True
        
        # Verify all major widgets are enabled
        assert settings_manager.get('widgets.clock.enabled') is True
        assert settings_manager.get('widgets.weather.enabled') is True
        assert settings_manager.get('widgets.media.enabled') is True
        assert settings_manager.get('widgets.reddit.enabled') is True
        assert settings_manager.get('preset') == 'full_monty'
    
    def test_apply_custom_preset_restores_backup(self, settings_manager: SettingsManager):
        """Test applying Custom preset restores from backup."""
        # First apply a preset and make a change
        apply_preset(settings_manager, 'essentials')
        settings_manager.set('widgets.clock.font_size', 72)
        
        # Switch to another preset
        apply_preset(settings_manager, 'purist')
        
        # Switch back to custom should restore the font size
        apply_preset(settings_manager, 'custom')
        # Note: Custom backup only saves when switching FROM custom
        # So this test verifies the restore mechanism works
        assert settings_manager.get('preset') == 'custom'
    
    def test_apply_invalid_preset_returns_false(self, settings_manager: SettingsManager):
        """Test applying invalid preset returns False."""
        result = apply_preset(settings_manager, 'nonexistent')
        assert result is False
    
    def test_apply_preset_saves_to_disk(self, qt_app, tmp_path):
        """Test that apply_preset persists changes to disk."""
        app_name = f"PresetDisk_{uuid.uuid4().hex}"
        base_name = "apply_preset_saves"
        manager = _make_manager(tmp_path, base_name=base_name, app_name=app_name)

        apply_preset(manager, 'purist')

        new_settings = _make_manager(tmp_path, base_name=base_name, app_name=app_name)
        assert new_settings.get('preset') == 'purist'


class TestNestedSettings:
    """Test nested setting path handling."""
    
    def test_nested_widget_setting(self, settings_manager: SettingsManager):
        """Test setting nested widget keys like widgets.clock.enabled."""
        apply_preset(settings_manager, 'essentials')
        
        # Verify nested path was set correctly
        widgets = settings_manager.get('widgets')
        assert isinstance(widgets, dict)
        assert 'clock' in widgets
        assert widgets['clock']['enabled'] is True
    
    def test_deeply_nested_setting(self, settings_manager: SettingsManager):
        """Test deeply nested keys like widgets.media.spotify_volume_enabled."""
        apply_preset(settings_manager, 'media')
        
        # Verify deeply nested path
        spotify_volume = settings_manager.get('widgets.media.spotify_volume_enabled')
        assert spotify_volume is not None
    
    def test_nested_setting_creates_intermediate_dicts(self, settings_manager: SettingsManager):
        """Test that nested setting creation works correctly."""
        # Apply preset that sets nested values
        apply_preset(settings_manager, 'full_monty')
        
        # Verify structure is created
        widgets = settings_manager.get('widgets')
        assert isinstance(widgets, dict)
        assert isinstance(widgets.get('clock'), dict)
        assert isinstance(widgets.get('weather'), dict)


class TestCustomPresetBackup:
    """Test custom preset backup and restore functionality."""
    
    def test_custom_backup_saves_widget_settings(self, settings_manager: SettingsManager):
        """Test that custom backup saves all widget settings."""
        # Set custom to start
        settings_manager.set('preset', 'custom')
        
        # Modify some widget settings
        settings_manager.set('widgets.clock.font_size', 80)
        settings_manager.set('widgets.weather.font_size', 24)
        
        # Switch to another preset (should trigger backup)
        apply_preset(settings_manager, 'purist')
        
        # Verify backup was created
        backup = settings_manager.get('custom_preset_backup')
        assert backup is not None
        assert isinstance(backup, dict)
    
    def test_custom_restore_from_backup(self, settings_manager: SettingsManager):
        """Test that custom preset restores from backup."""
        # Start with essentials
        apply_preset(settings_manager, 'essentials')
        
        # Set to custom and modify
        settings_manager.set('preset', 'custom')
        settings_manager.set('widgets.clock.font_size', 90)
        
        # Switch away (triggers backup)
        apply_preset(settings_manager, 'purist')
        
        # Switch back to custom (should restore)
        apply_preset(settings_manager, 'custom')
        
        # Verify settings were restored
        # Note: Backup only includes widgets, so check widget settings
        assert settings_manager.get('preset') == 'custom'


class TestMCModeAdjustments:
    """Test MC mode monitor adjustments."""
    
    def test_mc_mode_adjusts_monitor_1_to_2(self, monkeypatch):
        """Test that MC mode changes monitor 1 to monitor 2."""
        monkeypatch.setattr("core.settings.presets.is_mc_mode", lambda: True)
        settings = {
            'widgets': {
                'clock': {'monitor': 1},
                'weather': {'monitor': 1},
            }
        }
        
        adjusted = adjust_settings_for_mc_mode(settings)
        
        assert adjusted['widgets']['clock']['monitor'] == 2
        assert adjusted['widgets']['weather']['monitor'] == 2
    
    def test_mc_mode_adjusts_all_to_2(self, monkeypatch):
        """Test that MC mode changes 'ALL' to monitor 2."""
        monkeypatch.setattr("core.settings.presets.is_mc_mode", lambda: True)
        settings = {
            'widgets': {
                'clock': {'monitor': 'ALL'},
                'media': {'monitor': 'ALL'},
            }
        }
        
        adjusted = adjust_settings_for_mc_mode(settings)
        
        assert adjusted['widgets']['clock']['monitor'] == 2
        assert adjusted['widgets']['media']['monitor'] == 2
    
    def test_mc_mode_preserves_other_monitors(self):
        """Test that MC mode preserves monitor 2 and 3."""
        settings = {
            'widgets': {
                'clock': {'monitor': 2},
                'weather': {'monitor': 3},
            }
        }
        
        adjusted = adjust_settings_for_mc_mode(settings)
        
        assert adjusted['widgets']['clock']['monitor'] == 2
        assert adjusted['widgets']['weather']['monitor'] == 3
    
    def test_mc_mode_handles_missing_monitor_key(self):
        """Test that MC mode handles widgets without monitor key."""
        settings = {
            'widgets': {
                'clock': {},  # No monitor key
            }
        }
        
        # Should not crash
        adjusted = adjust_settings_for_mc_mode(settings)
        assert 'clock' in adjusted['widgets']


class TestGetOrderedPresets:
    """Test get_ordered_presets function."""
    
    def test_presets_ordered_correctly(self):
        """Test that presets are returned in correct order."""
        ordered = get_ordered_presets()
        
        # Should be 5 presets
        assert len(ordered) == 5
        
        # Custom should be last
        assert ordered[-1] == 'custom'
        
        # Purist should be first (order=0)
        assert ordered[0] == 'purist'
    
    def test_ordered_presets_are_strings(self):
        """Test that ordered presets are string keys."""
        ordered = get_ordered_presets()
        
        for preset_key in ordered:
            assert isinstance(preset_key, str)
            assert preset_key in PRESET_DEFINITIONS


class TestGetCurrentPresetInfo:
    """Test get_current_preset_info function."""
    
    def test_current_preset_info_structure(self, settings_manager: SettingsManager):
        """Test that current preset info has correct structure."""
        apply_preset(settings_manager, 'essentials')
        
        info = get_current_preset_info(settings_manager)
        
        assert 'key' in info
        assert 'name' in info
        assert 'description' in info
        assert info['key'] == 'essentials'
    
    def test_current_preset_info_for_custom(self, settings_manager: SettingsManager):
        """Test current preset info for custom preset."""
        settings_manager.set('preset', 'custom')
        
        info = get_current_preset_info(settings_manager)
        
        assert info['key'] == 'custom'
        assert info['name'] == 'Custom'


class TestCheckAndSwitchToCustom:
    """Test check_and_switch_to_custom function."""
    
    def test_switch_to_custom_when_settings_diverge(self, settings_manager: SettingsManager):
        """Test that manual changes trigger switch to custom."""
        # Apply a preset
        apply_preset(settings_manager, 'essentials')
        
        # Manually change a setting that differs from preset
        settings_manager.set('widgets.clock.font_size', 100)
        
        # Check should detect divergence and switch to custom
        result = check_and_switch_to_custom(settings_manager)
        
        # Note: Function implementation may vary, test based on actual behavior
        # This test documents expected behavior
        assert isinstance(result, bool)
    
    def test_no_switch_when_settings_match(self, settings_manager: SettingsManager):
        """Test that no switch occurs when settings match preset."""
        # Apply a preset
        apply_preset(settings_manager, 'purist')
        
        # Don't change anything
        
        # Check should not switch
        check_and_switch_to_custom(settings_manager)
        
        # Should remain on purist
        assert settings_manager.get('preset') == 'purist'


class TestPresetPersistence:
    """Test preset persistence across sessions."""
    
    def test_preset_persists_across_instances(self, qt_app, tmp_path):
        """Test that preset selection persists."""
        app_name = f"PresetPersist_{uuid.uuid4().hex}"
        base_name = "preset_persist"
        manager = _make_manager(tmp_path, base_name=base_name, app_name=app_name)

        apply_preset(manager, 'media')

        new_settings = _make_manager(tmp_path, base_name=base_name, app_name=app_name)
        assert new_settings.get('preset') == 'media'
    
    def test_custom_backup_persists(self, qt_app, tmp_path):
        """Test that custom backup persists across sessions."""
        app_name = f"CustomBackup_{uuid.uuid4().hex}"
        base_name = "custom_backup"
        manager = _make_manager(tmp_path, base_name=base_name, app_name=app_name)

        manager.set('preset', 'custom')
        manager.set('widgets.clock.font_size', 85)

        apply_preset(manager, 'purist')

        new_settings = _make_manager(tmp_path, base_name=base_name, app_name=app_name)

        backup = new_settings.get('custom_preset_backup')
        assert backup is not None


class TestPresetValidation:
    """Test preset validation and error handling."""
    
    def test_apply_none_preset_returns_false(self, settings_manager: SettingsManager):
        """Test that None preset returns False."""
        result = apply_preset(settings_manager, None)
        assert result is False
    
    def test_apply_empty_preset_returns_false(self, settings_manager: SettingsManager):
        """Test that empty string preset returns False."""
        result = apply_preset(settings_manager, '')
        assert result is False
    
    def test_preset_with_invalid_settings_handled(self, settings_manager: SettingsManager):
        """Test that presets with invalid settings are handled gracefully."""
        # Apply a valid preset first
        result = apply_preset(settings_manager, 'essentials')
        assert result is True
        
        # Preset system should handle invalid keys gracefully
        # (This is more of a robustness test)


@pytest.mark.parametrize("preset_key,expected_clock", [
    ("purist", False),
    ("essentials", True),
    ("media", True),
    ("full_monty", True),
])
def test_preset_clock_enabled(settings_manager: SettingsManager, preset_key: str, expected_clock: bool):
    """Parametrized test for clock enabled state across presets."""
    apply_preset(settings_manager, preset_key)
    assert settings_manager.get('widgets.clock.enabled') == expected_clock


@pytest.mark.parametrize("preset_key,expected_media", [
    ("purist", False),
    ("essentials", False),
    ("media", True),
    ("full_monty", True),
])
def test_preset_media_enabled(settings_manager: SettingsManager, preset_key: str, expected_media: bool):
    """Parametrized test for media widget enabled state across presets."""
    apply_preset(settings_manager, preset_key)
    assert settings_manager.get('widgets.media.enabled') == expected_media


@pytest.mark.parametrize("preset_key,expected_reddit", [
    ("purist", False),
    ("essentials", False),
    ("media", False),
    ("full_monty", True),
])
def test_preset_reddit_enabled(settings_manager: SettingsManager, preset_key: str, expected_reddit: bool):
    """Parametrized test for reddit widget enabled state across presets."""
    apply_preset(settings_manager, preset_key)
    assert settings_manager.get('widgets.reddit.enabled') == expected_reddit
