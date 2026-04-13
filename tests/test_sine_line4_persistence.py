"""Test that reproduces the sine line 4-6 color persistence issue.

Simulates the exact workflow:
1. Change Sine Line 4 color swatches (both color and glow)
2. Save settings via _save_settings()
3. Load settings
4. Check if the colors persisted
"""
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtGui import QColor


def create_mock_tab():
    """Create a mock tab with all necessary attributes."""
    tab = MagicMock()
    # Initialize color attributes to defaults
    tab._sine_line_color = QColor(255, 255, 255, 255)
    tab._sine_glow_color = QColor(0, 200, 255, 230)
    tab._sine_line2_color = QColor(255, 120, 50, 230)
    tab._sine_line2_glow_color = QColor(255, 120, 50, 180)
    tab._sine_line3_color = QColor(50, 255, 120, 230)
    tab._sine_line3_glow_color = QColor(50, 255, 120, 180)
    tab._sine_line4_color = QColor(255, 0, 150, 230)
    tab._sine_line4_glow_color = QColor(255, 0, 150, 180)
    tab._sine_line5_color = QColor(0, 255, 200, 230)
    tab._sine_line5_glow_color = QColor(0, 255, 200, 180)
    tab._sine_line6_color = QColor(200, 100, 255, 230)
    tab._sine_line6_glow_color = QColor(200, 100, 255, 180)
    return tab


def create_mock_config():
    """Create a mock config with get method."""
    config = MagicMock()
    config.get = MagicMock(return_value=None)
    return config


@pytest.mark.qt
def test_sine_line4_color_persistence_workflow(qt_app):
    """Test the exact user workflow that fails.
    
    Workflow:
    1. User changes line 4 color to match other lines (e.g., cyan [0, 255, 255, 230])
    2. User changes line 4 glow to match (e.g., cyan [0, 255, 255, 180])
    3. Settings are saved
    4. Settings are loaded
    5. Colors should be the new values, not defaults
    """
    # Import here to avoid import issues
    from ui.tabs.media.sine_wave_settings_binding import (
        collect_sine_wave_mode_settings,
        load_sine_wave_mode_settings,
        _SINE_COLOR_DEFAULTS
    )
    
    # Step 1: Create a fresh tab with default colors
    tab = create_mock_tab()
    config = create_mock_config()
    
    # Verify initial defaults
    print(f"Initial line4 color: {tab._sine_line4_color.getRgb()}")
    print(f"Initial line4 glow: {tab._sine_line4_glow_color.getRgb()}")
    
    # Step 2: Simulate user changing colors (like in the builder)
    # User sets line 4 to cyan to match the theme
    new_color = QColor(0, 255, 255, 230)
    new_glow = QColor(0, 255, 255, 180)
    
    tab._sine_line4_color = new_color
    tab._sine_line4_glow_color = new_glow
    
    print(f"After change line4 color: {tab._sine_line4_color.getRgb()}")
    print(f"After change line4 glow: {tab._sine_line4_glow_color.getRgb()}")
    
    # Step 3: Collect settings (this is what _save_settings triggers)
    collected = collect_sine_wave_mode_settings(tab)
    
    print(f"Collected sine_line4_color: {collected.get('sine_line4_color')}")
    print(f"Collected sine_line4_glow_color: {collected.get('sine_line4_glow_color')}")
    
    # Verify collected values are the NEW values
    assert collected['sine_line4_color'] == [0, 255, 255, 230], \
        f"Expected [0, 255, 255, 230], got {collected['sine_line4_color']}"
    assert collected['sine_line4_glow_color'] == [0, 255, 255, 180], \
        f"Expected [0, 255, 255, 180], got {collected['sine_line4_glow_color']}"
    
    # Step 4: Simulate loading settings back
    # Create a fresh tab
    tab2 = create_mock_tab()
    
    # Mock config to return the collected values
    def mock_get(key, default=None):
        return collected.get(key, default)
    
    config2 = MagicMock()
    config2.get = mock_get
    
    # Load settings
    load_sine_wave_mode_settings(tab2, config2)
    
    print(f"After load line4 color: {tab2._sine_line4_color.getRgb()}")
    print(f"After load line4 glow: {tab2._sine_line4_glow_color.getRgb()}")
    
    # Step 5: Verify loaded colors match what was saved
    assert tab2._sine_line4_color.getRgb()[:4] == (0, 255, 255, 230), \
        f"Expected (0, 255, 255, 230), got {tab2._sine_line4_color.getRgb()}"
    assert tab2._sine_line4_glow_color.getRgb()[:4] == (0, 255, 255, 180), \
        f"Expected (0, 255, 255, 180), got {tab2._sine_line4_glow_color.getRgb()}"


@pytest.mark.qt
def test_sine_line4_vs_line2_behavior_parity(qt_app):
    """Test that line 4 behaves exactly like line 2 for color persistence.
    
    This test verifies that the save/load pipeline works identically for
    line 2 (which works) and line 4 (which doesn't).
    """
    from ui.tabs.media.sine_wave_settings_binding import (
        collect_sine_wave_mode_settings,
        load_sine_wave_mode_settings,
    )
    
    # Test line 2 behavior
    tab_line2 = create_mock_tab()
    tab_line2._sine_line2_color = QColor(100, 100, 100, 230)
    tab_line2._sine_line2_glow_color = QColor(100, 100, 100, 180)
    
    collected_line2 = collect_sine_wave_mode_settings(tab_line2)
    
    # Test line 4 behavior with same values
    tab_line4 = create_mock_tab()
    tab_line4._sine_line4_color = QColor(100, 100, 100, 230)
    tab_line4._sine_line4_glow_color = QColor(100, 100, 100, 180)
    
    collected_line4 = collect_sine_wave_mode_settings(tab_line4)
    
    # Both should behave the same
    print(f"Line 2 collected: {collected_line2.get('sine_line2_color')}")
    print(f"Line 4 collected: {collected_line4.get('sine_line4_color')}")
    
    # If line 2 works and line 4 doesn't, we'll see different behavior here
    assert collected_line2['sine_line2_color'] == [100, 100, 100, 230]
    assert collected_line4['sine_line4_color'] == [100, 100, 100, 230]
    
    # Test loading
    def mock_get_line2(key, default=None):
        return collected_line2.get(key, default)
    
    def mock_get_line4(key, default=None):
        return collected_line4.get(key, default)
    
    config_line2 = MagicMock()
    config_line2.get = mock_get_line2
    
    config_line4 = MagicMock()
    config_line4.get = mock_get_line4
    
    tab2_loaded = create_mock_tab()
    tab4_loaded = create_mock_tab()
    
    load_sine_wave_mode_settings(tab2_loaded, config_line2)
    load_sine_wave_mode_settings(tab4_loaded, config_line4)
    
    print(f"Line 2 loaded: {tab2_loaded._sine_line2_color.getRgb()}")
    print(f"Line 4 loaded: {tab4_loaded._sine_line4_color.getRgb()}")
    
    assert tab2_loaded._sine_line2_color.getRgb()[:4] == (100, 100, 100, 230)
    assert tab4_loaded._sine_line4_color.getRgb()[:4] == (100, 100, 100, 230)


@pytest.mark.qt
def test_sine_line4_horizontal_shift_persistence(qt_app):
    """Test that horizontal shift for line 4 also persists.
    
    The user reported this also doesn't save.
    """
    from ui.tabs.media.sine_wave_settings_binding import (
        collect_sine_wave_mode_settings,
        load_sine_wave_mode_settings,
    )
    
    tab = create_mock_tab()
    
    # Set the horizontal shift value (like the slider would)
    tab._sine_line4_horizontal_shift = 25
    
    collected = collect_sine_wave_mode_settings(tab)
    print(f"Collected sine_line4_shift: {collected.get('sine_line4_shift')}")
    
    assert collected['sine_line4_shift'] == 25, \
        f"Expected 25, got {collected.get('sine_line4_shift')}"
    
    # Test loading
    def mock_get(key, default=None):
        return collected.get(key, default)
    
    config = MagicMock()
    config.get = mock_get
    
    tab2 = create_mock_tab()
    load_sine_wave_mode_settings(tab2, config)
    
    print(f"Loaded _sine_line4_horizontal_shift: {tab2._sine_line4_horizontal_shift}")
    
    assert tab2._sine_line4_horizontal_shift == 25, \
        f"Expected 25, got {tab2._sine_line4_horizontal_shift}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
