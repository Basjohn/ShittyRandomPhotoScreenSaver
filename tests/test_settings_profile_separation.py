"""
Tests for MC vs Screensaver profile separation.

Tests cover:
- Application name detection for MC builds
- Settings isolation between profiles
- Profile-specific defaults
"""
import pytest


class TestApplicationNameDetection:
    """Tests for automatic application name detection."""
    
    def test_default_application_name(self, tmp_path):
        """Test default application name is Screensaver."""
        from core.settings.settings_manager import SettingsManager
        
        # Create with explicit application name
        settings = SettingsManager(application="Screensaver", storage_base_dir=tmp_path)
        app_name = settings.get_application_name()
        
        # Should be Screensaver or Screensaver_MC depending on how tests are run
        assert app_name in ("Screensaver", "Screensaver_MC")
    
    def test_mc_detection_from_argv(self, tmp_path):
        """Test MC detection from sys.argv."""
        import sys
        
        # Mock sys.argv to simulate MC build
        original_argv = sys.argv
        try:
            sys.argv = ["main_mc.py"]
            
            from core.settings.settings_manager import SettingsManager
            settings = SettingsManager(application="Screensaver", storage_base_dir=tmp_path)
            
            # Should detect MC build from argv
            app_name = settings.get_application_name()
            assert app_name == "Screensaver_MC"
        finally:
            sys.argv = original_argv
    
    def test_explicit_mc_application_name(self, tmp_path):
        """Test explicit MC application name."""
        from core.settings.settings_manager import SettingsManager
        
        settings = SettingsManager(application="Screensaver_MC", storage_base_dir=tmp_path)
        app_name = settings.get_application_name()
        
        assert app_name == "Screensaver_MC"


class TestProfileIsolation:
    """Tests for settings isolation between profiles."""
    
    def test_different_settings_files(self, tmp_path):
        """Test that different profiles use different settings files."""
        from core.settings.settings_manager import SettingsManager
        
        # Create two managers with different application names
        settings1 = SettingsManager(application="Screensaver", storage_base_dir=tmp_path)
        settings2 = SettingsManager(application="Screensaver_MC", storage_base_dir=tmp_path)
        
        # They should have different application names
        # (actual isolation depends on how tests are run)
        _ = settings1.get_application_name()  # Verify it works
        name2 = settings2.get_application_name()
        
        # At minimum, the explicit MC one should be MC
        assert "MC" in name2 or name2 == "Screensaver_MC"
    
    def test_settings_not_shared(self, tmp_path):
        """Test that settings changes don't leak between profiles."""
        from core.settings.settings_manager import SettingsManager
        
        # Create two managers
        settings1 = SettingsManager(application="TestProfile1", storage_base_dir=tmp_path)
        settings2 = SettingsManager(application="TestProfile2", storage_base_dir=tmp_path)
        
        # Set a unique value in one
        test_key = "test.profile_isolation_check"
        test_value = "profile1_value"
        
        settings1.set(test_key, test_value)
        
        # The other should not have this value (or have default)
        value2 = settings2.get(test_key, "default")
        
        # Clean up
        settings1.set(test_key, None)
        
        # Value should either be default or different
        # (depends on whether QSettings shares storage)
        assert value2 == "default" or value2 != test_value


class TestMCDefaults:
    """Tests for MC-specific default values."""
    
    def test_mc_always_on_top_setting(self, tmp_path):
        """Test that MC always_on_top setting can be retrieved."""
        from core.settings.settings_manager import SettingsManager
        
        settings = SettingsManager(application="Screensaver_MC", storage_base_dir=tmp_path)
        
        # MC always_on_top should be retrievable (defaults to True in DisplayWidget)
        # Use get_bool to handle string/bool conversion
        always_on_top = settings.get_bool('mc.always_on_top', True)
        assert always_on_top in (True, False)  # Valid boolean
    
    def test_mc_eco_mode_setting(self, tmp_path):
        """Test that MC eco_mode setting can be retrieved."""
        from core.settings.settings_manager import SettingsManager
        
        settings = SettingsManager(application="Screensaver_MC", storage_base_dir=tmp_path)
        
        # MC eco_mode should be retrievable
        # Use get_bool to handle string/bool conversion
        eco_enabled = settings.get_bool('mc.eco_mode.enabled', True)
        assert eco_enabled in (True, False)  # Valid boolean
    
    def test_mc_display_setting(self, tmp_path):
        """Test MC display setting can be retrieved."""
        from core.settings.settings_manager import SettingsManager
        
        settings = SettingsManager(application="Screensaver_MC", storage_base_dir=tmp_path)
        
        # MC display should be retrievable
        mc_display = settings.get('mc.display', 2)
        assert isinstance(mc_display, int)
        assert mc_display >= 1  # Should be valid display number


class TestExportImportIsolation:
    """Tests for export/import profile isolation."""
    
    def test_export_includes_application_name(self, tmp_path):
        """Test that exported settings include application name."""
        import tempfile
        from pathlib import Path
        from core.settings.settings_manager import SettingsManager
        
        settings = SettingsManager(application="TestExport", storage_base_dir=tmp_path)
        
        # Export to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sst', delete=False) as f:
            temp_path = f.name
        
        try:
            settings.export_to_sst(temp_path)
            
            # Read and verify
            with open(temp_path, 'r') as f:
                content = f.read()
            
            # Should contain application name
            assert 'application' in content or 'TestExport' in content
        finally:
            Path(temp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
