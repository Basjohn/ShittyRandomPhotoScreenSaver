"""
Tests for SettingsManager critical settings sync mechanism.

Verifies that critical settings (transitions, widgets, sources, display)
are immediately synced to persistent storage to prevent data loss.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestSettingsCriticalSync:
    """Test that critical settings trigger immediate sync."""

    def test_transitions_key_triggers_sync(self):
        """Verify 'transitions' key triggers immediate sync."""
        with patch('core.settings.settings_manager.QSettings') as mock_qsettings:
            mock_instance = MagicMock()
            mock_qsettings.return_value = mock_instance
            
            from core.settings.settings_manager import SettingsManager
            manager = SettingsManager(organization="TestOrg", application="TestApp")
            
            # Reset mock to clear init calls
            mock_instance.reset_mock()
            
            # Set a transitions value
            manager.set('transitions', {'type': 'Particle', 'duration_ms': 5000})
            
            # Verify sync was called
            assert mock_instance.sync.called, "sync() should be called for 'transitions' key"

    def test_widgets_key_triggers_sync(self):
        """Verify 'widgets' key triggers immediate sync."""
        with patch('core.settings.settings_manager.QSettings') as mock_qsettings:
            mock_instance = MagicMock()
            mock_qsettings.return_value = mock_instance
            
            from core.settings.settings_manager import SettingsManager
            manager = SettingsManager(organization="TestOrg", application="TestApp")
            
            mock_instance.reset_mock()
            
            manager.set('widgets', {'clock': {'enabled': True}})
            
            assert mock_instance.sync.called, "sync() should be called for 'widgets' key"

    def test_sources_folders_triggers_sync(self):
        """Verify 'sources.folders' key triggers immediate sync."""
        with patch('core.settings.settings_manager.QSettings') as mock_qsettings:
            mock_instance = MagicMock()
            mock_qsettings.return_value = mock_instance
            
            from core.settings.settings_manager import SettingsManager
            manager = SettingsManager(organization="TestOrg", application="TestApp")
            
            mock_instance.reset_mock()
            
            manager.set('sources.folders', ['/path/to/images'])
            
            assert mock_instance.sync.called, "sync() should be called for 'sources.folders' key"

    def test_display_key_triggers_sync(self):
        """Verify 'display' key triggers immediate sync."""
        with patch('core.settings.settings_manager.QSettings') as mock_qsettings:
            mock_instance = MagicMock()
            mock_qsettings.return_value = mock_instance
            
            from core.settings.settings_manager import SettingsManager
            manager = SettingsManager(organization="TestOrg", application="TestApp")
            
            mock_instance.reset_mock()
            
            manager.set('display', {'mode': 'fill'})
            
            assert mock_instance.sync.called, "sync() should be called for 'display' key"

    def test_non_critical_key_no_sync(self):
        """Verify non-critical keys do NOT trigger immediate sync."""
        with patch('core.settings.settings_manager.QSettings') as mock_qsettings:
            mock_instance = MagicMock()
            mock_qsettings.return_value = mock_instance
            
            from core.settings.settings_manager import SettingsManager
            manager = SettingsManager(organization="TestOrg", application="TestApp")
            
            mock_instance.reset_mock()
            
            # Set a non-critical value
            manager.set('ui.dialog_geometry', {'x': 100, 'y': 100})
            
            # Verify sync was NOT called (setValue should be called, but not sync)
            assert mock_instance.setValue.called, "setValue should be called"
            assert not mock_instance.sync.called, "sync() should NOT be called for non-critical keys"

    def test_critical_keys_list_complete(self):
        """Verify all expected critical keys are in the set."""
        from core.settings.settings_manager import SettingsManager
        
        expected_critical = {'transitions', 'widgets', 'sources.folders', 'sources.rss_feeds', 'display'}
        assert SettingsManager._CRITICAL_KEYS == expected_critical, \
            f"Critical keys mismatch. Expected {expected_critical}, got {SettingsManager._CRITICAL_KEYS}"

    def test_nested_critical_key_triggers_sync(self):
        """Verify nested keys under critical roots trigger sync."""
        with patch('core.settings.settings_manager.QSettings') as mock_qsettings:
            mock_instance = MagicMock()
            mock_qsettings.return_value = mock_instance
            
            from core.settings.settings_manager import SettingsManager
            manager = SettingsManager(organization="TestOrg", application="TestApp")
            
            mock_instance.reset_mock()
            
            # Set a nested key under 'display'
            manager.set('display.hw_accel', True)
            
            assert mock_instance.sync.called, "sync() should be called for nested critical keys"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
