"""
Tests for MC vs Screensaver profile separation.

Tests cover:
- Application name detection for MC builds
- Settings isolation between profiles
- Profile-specific defaults
"""
import json
import pytest


class TestApplicationNameDetection:
    """Tests for automatic application name detection."""
    
    def test_explicit_storage_root_honors_exact_application_name(self, tmp_path):
        """Test default application name is Screensaver."""
        from core.settings.settings_manager import SettingsManager
        
        # Create with explicit application name
        settings = SettingsManager(application="Screensaver", storage_base_dir=tmp_path)
        app_name = settings.get_application_name()
        
        assert app_name == "Screensaver"
    
    def test_mc_detection_from_argv_without_explicit_storage_root(self, tmp_path, monkeypatch):
        """Test MC detection from sys.argv."""
        import sys
        
        # Mock sys.argv to simulate MC build
        original_argv = sys.argv
        try:
            sys.argv = ["main_mc.py"]
            
            import core.settings.settings_manager as settings_module

            monkeypatch.setattr(
                settings_module,
                "determine_storage_path",
                lambda application, base_dir=None: tmp_path / application / "settings_v2.json",
            )
            settings = settings_module.SettingsManager(application="Screensaver")
            
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
        """Canonical Screensaver and MC profiles must use different JSON stores."""
        from core.settings.settings_manager import SettingsManager

        settings1 = SettingsManager(application="Screensaver", storage_base_dir=tmp_path)
        settings2 = SettingsManager(application="Screensaver_MC", storage_base_dir=tmp_path)

        assert settings1.get_application_name() == "Screensaver"
        assert settings2.get_application_name() == "Screensaver_MC"
        assert settings1.get_storage_path() != settings2.get_storage_path()
        assert settings1.get_storage_path().name == "settings_v2.json"
        assert settings2.get_storage_path().name == "settings_v2.json"
    
    def test_settings_not_shared(self, tmp_path):
        """A write to one isolated profile must be absent from another profile."""
        from core.settings.settings_manager import SettingsManager

        settings1 = SettingsManager(application="TestProfile1", storage_base_dir=tmp_path)
        settings2 = SettingsManager(application="TestProfile2", storage_base_dir=tmp_path)

        test_key = "test.profile_isolation_check"
        settings1.set(test_key, "profile1_value")

        assert settings1.get(test_key) == "profile1_value"
        assert settings2.get(test_key, "default") == "default"
        assert settings1.get_storage_path() != settings2.get_storage_path()


class TestMCDefaults:
    """Tests for MC-specific default values."""
    
    def test_mc_always_on_top_default_is_current_profile_contract(self, tmp_path):
        """The MC profile owns the canonical always-on-top default."""
        from core.settings.settings_manager import SettingsManager

        settings = SettingsManager(application="Screensaver_MC", storage_base_dir=tmp_path)

        assert settings.get_bool("mc.always_on_top", False) is True


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
            
            with open(temp_path, 'r') as f:
                exported = json.load(f)

            assert exported["application"] == "TestExport"
        finally:
            Path(temp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
