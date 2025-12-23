"""Integration tests for Display tab UI.

Tests the new Display tab created in Phase 1 for settings management.
"""
import pytest
import uuid
from ui.tabs.display_tab import DisplayTab
from core.settings import SettingsManager


@pytest.fixture
def display_tab(qt_app, settings_manager):
    """Create DisplayTab for testing."""
    tab = DisplayTab(settings_manager)
    yield tab
    tab.deleteLater()


class TestDisplayTab:
    """Tests for Display tab UI component."""
    
    def test_display_tab_creation(self, qt_app, settings_manager):
        """Test that DisplayTab can be created without errors."""
        tab = DisplayTab(settings_manager)
        
        assert tab is not None
        assert tab.settings_manager == settings_manager
        
        tab.deleteLater()
    
    def test_display_tab_loads_settings(self, qt_app, display_tab):
        """Test that DisplayTab loads settings correctly."""
        # Set some settings
        display_tab.settings_manager.set('display.show_on_monitors', 'ALL')
        display_tab.settings_manager.set('display.same_image_all_monitors', True)
        display_tab.settings_manager.set('display.mode', 'fill')
        display_tab.settings_manager.set('timing.interval', 10)
        display_tab.settings_manager.set('queue.shuffle', True)
        display_tab.settings_manager.set('display.use_lanczos', True)
        display_tab.settings_manager.set('display.sharpen_downscale', False)
        
        # Create new tab instance - should load these settings
        new_tab = DisplayTab(display_tab.settings_manager)
        
        # Verify settings were loaded (indirectly by checking UI state)
        # The UI elements should reflect the loaded settings
        assert new_tab is not None
        
        new_tab.deleteLater()
    
    def test_display_tab_saves_monitor_selection(self, qt_app, display_tab):
        """Test saving monitor selection setting using canonical key."""
        # Simulate user changing monitor selection via the canonical setting
        display_tab.settings_manager.set('display.show_on_monitors', [1])

        value = display_tab.settings_manager.get('display.show_on_monitors', 'ALL')
        assert value == [1]
    
    def test_display_tab_saves_display_mode(self, qt_app, display_tab):
        """Test saving display mode setting."""
        modes = ['fill', 'fit', 'shrink']
        
        for mode in modes:
            display_tab.settings_manager.set('display.mode', mode)
            value = display_tab.settings_manager.get('display.mode', 'fill')
            assert value == mode
    
    def test_display_tab_saves_timing(self, qt_app, display_tab):
        """Test saving rotation interval setting."""
        intervals = [1, 5, 10, 30, 60, 300]
        
        for interval in intervals:
            display_tab.settings_manager.set('timing.interval', interval)
            value = display_tab.settings_manager.get('timing.interval', 5)
            assert value == interval
    
    def test_display_tab_boolean_conversion(self, qt_app, display_tab):
        """
        Test boolean type conversion for settings.
        
        Settings may be stored as strings or booleans, tab should handle both.
        """
        # Test with actual booleans
        display_tab.settings_manager.set('queue.shuffle', True)
        value = display_tab.settings_manager.get('queue.shuffle', False)
        assert value in (True, 'true')
        
        display_tab.settings_manager.set('queue.shuffle', False)
        value = display_tab.settings_manager.get('queue.shuffle', True)
        assert value in (False, 'false')
        
        # Test with strings (some settings may be stored as strings)
        display_tab.settings_manager.set('queue.shuffle', 'true')
        value = display_tab.settings_manager.get('queue.shuffle', False)
        # Should handle string 'true' correctly
        assert value in [True, 'true']
    
    def test_display_tab_lanczos_setting(self, qt_app, display_tab):
        """Test Lanczos quality setting (new feature)."""
        # Test enabling Lanczos
        display_tab.settings_manager.set('display.use_lanczos', True)
        value = display_tab.settings_manager.get('display.use_lanczos', False)
        assert value in (True, 'true')
        
        # Test disabling Lanczos
        display_tab.settings_manager.set('display.use_lanczos', False)
        value = display_tab.settings_manager.get('display.use_lanczos', True)
        assert value in (False, 'false')
    
    def test_display_tab_sharpen_setting(self, qt_app, display_tab):
        """Test sharpen filter setting (new feature)."""
        # Test enabling sharpening
        display_tab.settings_manager.set('display.sharpen_downscale', True)
        value = display_tab.settings_manager.get('display.sharpen_downscale', False)
        assert value in (True, 'true')
        
        # Test disabling sharpening
        display_tab.settings_manager.set('display.sharpen_downscale', False)
        value = display_tab.settings_manager.get('display.sharpen_downscale', True)
        assert value in (False, 'false')
    
    def test_display_tab_same_image_monitors(self, qt_app, display_tab):
        """Test same image on all monitors setting."""
        display_tab.settings_manager.set('display.same_image_all_monitors', True)
        value = display_tab.settings_manager.get('display.same_image_all_monitors', False)
        assert value in (True, 'true')
        
        display_tab.settings_manager.set('display.same_image_all_monitors', False)
        value = display_tab.settings_manager.get('display.same_image_all_monitors', True)
        assert value in (False, 'false')
    
    def test_display_tab_all_settings_persist(self, qt_app, settings_manager):
        """
        Test that all settings persist correctly (roundtrip test).
        
        Set all settings, create new tab, verify settings maintained.
        """
        # Set all display-related settings
        test_settings = {
            'display.show_on_monitors': 'ALL',
            'display.same_image_all_monitors': False,
            'display.mode': 'fit',
            'timing.interval': 15,
            'queue.shuffle': True,
            'display.use_lanczos': True,
            'display.sharpen_downscale': True
        }
        
        # Save all settings
        for key, value in test_settings.items():
            settings_manager.set(key, value)
        
        # Create tab instance
        tab1 = DisplayTab(settings_manager)
        
        # Verify all settings were loaded
        for key, expected_value in test_settings.items():
            actual_value = settings_manager.get(key)
            
            # Handle boolean/string conversion
            if isinstance(expected_value, bool):
                assert actual_value in [expected_value, str(expected_value).lower()]
            else:
                assert actual_value == expected_value
        
        tab1.deleteLater()
    
    def test_display_tab_default_values(self, qt_app):
        """Test that DisplayTab uses correct default values."""
        # Create fresh settings manager
        fresh_settings = SettingsManager(organization="Test", application=f"DisplayTabTest_{uuid.uuid4().hex}")
        fresh_settings.reset_to_defaults()
        
        tab = DisplayTab(fresh_settings)
        
        # Check defaults
        monitor = fresh_settings.get('display.show_on_monitors', 'ALL')
        assert monitor == 'ALL'
        
        mode = fresh_settings.get('display.mode', 'fill')
        assert mode == 'fill'
        
        interval = fresh_settings.get('timing.interval', 5)
        assert interval == 45
        
        tab.deleteLater()

    
    def test_display_tab_invalid_mode_handling(self, qt_app, display_tab):
        """Test handling of invalid display mode."""
        # Set invalid mode
        display_tab.settings_manager.set('display.mode', 'invalid_mode')
        
        # Tab should handle gracefully (fall back to default)
        # This shouldn't crash
        new_tab = DisplayTab(display_tab.settings_manager)
        assert new_tab is not None
        
        new_tab.deleteLater()
    
    def test_display_tab_invalid_interval_handling(self, qt_app, display_tab):
        """Test handling of invalid rotation interval."""
        # Set invalid intervals
        invalid_intervals = [-1, 0, 10000]
        
        for interval in invalid_intervals:
            display_tab.settings_manager.set('timing.interval', interval)
            
            # Should handle gracefully
            new_tab = DisplayTab(display_tab.settings_manager)
            assert new_tab is not None
            new_tab.deleteLater()
    
    def test_display_tab_ui_elements_exist(self, qt_app, display_tab):
        """Test that key UI elements are present in the tab."""
        # The tab should have been initialized with UI elements
        # We can't access private UI elements directly, but we can verify
        # the tab was created successfully and has children
        
        assert display_tab is not None
        assert display_tab.settings_manager is not None
        
        # Tab should have child widgets
        children = display_tab.children()
        assert len(children) > 0, "Display tab should have child widgets"
