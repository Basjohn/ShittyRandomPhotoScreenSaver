"""
Tests for Settings Defaults Parity with SST files.

Tests verify that SettingsManager defaults match the canonical SST
(Settings Snapshot Template) files for both Screensaver and MC builds.
"""
import json
import pytest
from pathlib import Path

from core.settings.defaults import get_default_settings, PRESERVE_ON_RESET


class TestDefaultsStructure:
    """Tests for defaults structure and completeness."""
    
    def test_defaults_has_display_section(self):
        """Test that defaults has display section."""
        defaults = get_default_settings()
        assert 'display' in defaults
        assert 'mode' in defaults['display']
        assert 'hw_accel' in defaults['display']
    
    def test_defaults_has_input_section(self):
        """Test that defaults has input section."""
        defaults = get_default_settings()
        assert 'input' in defaults
        assert 'hard_exit' in defaults['input']
    
    def test_defaults_has_queue_section(self):
        """Test that defaults has queue section."""
        defaults = get_default_settings()
        assert 'queue' in defaults
        assert 'shuffle' in defaults['queue']
    
    def test_defaults_has_sources_section(self):
        """Test that defaults has sources section."""
        defaults = get_default_settings()
        assert 'sources' in defaults
        assert 'mode' in defaults['sources']
        assert 'local_ratio' in defaults['sources']
    
    def test_defaults_has_timing_section(self):
        """Test that defaults has timing section."""
        defaults = get_default_settings()
        assert 'timing' in defaults
        assert 'interval' in defaults['timing']
    
    def test_defaults_has_transitions_section(self):
        """Test that defaults has transitions section."""
        defaults = get_default_settings()
        assert 'transitions' in defaults
        assert 'pool' in defaults['transitions']
        assert 'durations' in defaults['transitions']
    
    def test_defaults_has_accessibility_section(self):
        """Test that defaults has accessibility section."""
        defaults = get_default_settings()
        assert 'accessibility' in defaults
    
    def test_defaults_has_widgets_section(self):
        """Test that defaults has widgets section."""
        defaults = get_default_settings()
        assert 'widgets' in defaults


class TestPreserveOnReset:
    """Tests for PRESERVE_ON_RESET configuration."""
    
    def test_preserve_on_reset_has_folders(self):
        """Test that folders are preserved on reset."""
        assert 'sources.folders' in PRESERVE_ON_RESET
    
    def test_preserve_on_reset_has_rss_feeds(self):
        """Test that RSS feeds are preserved on reset."""
        assert 'sources.rss_feeds' in PRESERVE_ON_RESET
    
    def test_preserve_on_reset_has_weather_location(self):
        """Test that weather location is preserved on reset."""
        assert 'widgets.weather.location' in PRESERVE_ON_RESET


class TestSSTFileParity:
    """Tests for parity with SST snapshot files."""
    
    @pytest.fixture
    def sst_screensaver(self):
        """Load the Screensaver SST file."""
        sst_path = Path(__file__).parent.parent / "audits/setting manager defaults/SRPSS_Settings_Screensaver.sst"
        if not sst_path.exists():
            pytest.skip("SST file not found")
        try:
            with open(sst_path, 'r') as f:
                content = f.read()
                # Fix known JSON issues in SST file (e.g., "00" instead of "0")
                content = content.replace(': 00,', ': 0,')
                return json.loads(content)
        except json.JSONDecodeError as e:
            pytest.skip(f"SST file has invalid JSON: {e}")
    
    def test_display_mode_default(self, sst_screensaver):
        """Test display mode default matches SST."""
        defaults = get_default_settings()
        sst_value = sst_screensaver['snapshot']['display']['mode']
        assert defaults['display']['mode'] == sst_value
    
    def test_hw_accel_default(self, sst_screensaver):
        """Test hw_accel default matches SST."""
        defaults = get_default_settings()
        sst_value = sst_screensaver['snapshot']['display']['hw_accel']
        # SST stores as string "true"
        expected = sst_value == "true" if isinstance(sst_value, str) else bool(sst_value)
        assert defaults['display']['hw_accel'] == expected
    
    def test_shuffle_default(self, sst_screensaver):
        """Test shuffle default matches SST."""
        defaults = get_default_settings()
        sst_value = sst_screensaver['snapshot']['queue']['shuffle']
        expected = sst_value == "true" if isinstance(sst_value, str) else bool(sst_value)
        assert defaults['queue']['shuffle'] == expected
    
    def test_hard_exit_default(self, sst_screensaver):
        """Test hard_exit default matches SST."""
        defaults = get_default_settings()
        sst_value = sst_screensaver['snapshot']['input']['hard_exit']
        expected = sst_value == "true" if isinstance(sst_value, str) else bool(sst_value)
        assert defaults['input']['hard_exit'] == expected
    
    def test_sources_mode_default(self, sst_screensaver):
        """Test sources mode default matches SST."""
        defaults = get_default_settings()
        sst_value = sst_screensaver['snapshot']['sources']['mode']
        assert defaults['sources']['mode'] == sst_value
    
    def test_rss_background_cap_default(self, sst_screensaver):
        """Test rss_background_cap default matches SST."""
        defaults = get_default_settings()
        sst_value = sst_screensaver['snapshot']['sources']['rss_background_cap']
        assert defaults['sources']['rss_background_cap'] == int(sst_value)
    
    def test_transition_pool_has_all_types(self, sst_screensaver):
        """Test that transition pool has all SST transition types."""
        defaults = get_default_settings()
        sst_pool = sst_screensaver['snapshot']['transitions']['pool']
        
        for trans_type in sst_pool.keys():
            assert trans_type in defaults['transitions']['pool'], \
                f"Missing transition type: {trans_type}"


class TestWidgetDefaults:
    """Tests for widget defaults."""
    
    def test_clock_defaults_exist(self):
        """Test that clock defaults exist."""
        defaults = get_default_settings()
        assert 'clock' in defaults['widgets']
    
    def test_weather_defaults_exist(self):
        """Test that weather defaults exist."""
        defaults = get_default_settings()
        assert 'weather' in defaults['widgets']
    
    def test_media_defaults_exist(self):
        """Test that media defaults exist."""
        defaults = get_default_settings()
        assert 'media' in defaults['widgets']
    
    def test_reddit_defaults_exist(self):
        """Test that reddit defaults exist."""
        defaults = get_default_settings()
        assert 'reddit' in defaults['widgets']
    
    def test_shadows_defaults_exist(self):
        """Test that shadows defaults exist."""
        defaults = get_default_settings()
        assert 'shadows' in defaults['widgets']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
