"""Integration test that uses the actual builder code."""
import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget


@pytest.mark.qt
def test_sine_builder_line4_color_connections(qt_app, qtbot):
    """Test that the builder actually connects line 4 color buttons correctly."""
    # Import the builder function
    from ui.tabs.media.sine_wave_builder import build_sine_wave_tab
    
    # Create a real tab with all necessary attributes
    class TestTab(QWidget):
        def __init__(self):
            super().__init__()
            self._save_called_count = 0
            self._saved_settings = None
            
        def _save_settings(self):
            self._save_called_count += 1
            print(f"_save_settings called #{self._save_called_count}")
    
    tab = TestTab()
    
    # Build the sine wave UI
    build_sine_wave_tab(tab)
    
    # Check that the color buttons exist
    assert hasattr(tab, 'sine_line4_color_btn'), "sine_line4_color_btn not created"
    assert hasattr(tab, 'sine_line4_glow_btn'), "sine_line4_glow_btn not created"
    
    # Check initial colors
    initial_color = tab.sine_line4_color_btn.get_color()
    print(f"Initial button color: {initial_color.getRgb()}")
    
    # Change the color via the button (simulating user picking a color)
    new_color = QColor(0, 255, 255, 230)
    tab.sine_line4_color_btn.set_color(new_color)
    
    # Check that _save_settings was called
    print(f"Save called count: {tab._save_called_count}")
    
    # The attribute should have been updated
    if hasattr(tab, '_sine_line4_color'):
        print(f"_sine_line4_color: {tab._sine_line4_color.getRgb()}")
    else:
        print("_sine_line4_color attribute does not exist!")
        
    # Verify save was called at least once
    assert tab._save_called_count > 0, "_save_settings was never called"


@pytest.mark.qt
def test_actual_save_media_settings_includes_line4(qt_app, qtbot):
    """Test that save_media_settings actually includes line 4 values."""
    from ui.tabs.widgets_tab_media import save_media_settings, load_media_settings
    from ui.tabs.media.sine_wave_settings_binding import load_sine_wave_mode_settings
    
    # Create a tab with sine mode set
    class TestTab(QWidget):
        def __init__(self):
            super().__init__()
            self._current_visualizer_mode = 'sine_wave'
            # Set up line 4 with a custom color
            self._sine_line4_color = QColor(0, 255, 255, 230)  # Cyan
            self._sine_line4_glow_color = QColor(0, 255, 255, 180)
            self._sine_line4_horizontal_shift = 40
            
            # Set up line 2 for comparison (this should work)
            self._sine_line2_color = QColor(100, 100, 100, 230)
            self._sine_line2_glow_color = QColor(100, 100, 100, 180)
            self._sine_line2_horizontal_shift = 35
            
    tab = TestTab()
    
    # Mock the settings manager
    saved_settings = {}
    
    class MockSM:
        def set_many(self, settings_dict):
            saved_settings.update(settings_dict)
            print(f"Saved settings: {settings_dict}")
    
    # Save the settings
    media_config, spotify_vis_config = save_media_settings(tab)
    
    print(f"spotify_vis_config: {spotify_vis_config}")
    
    # Check that line 2 and line 4 settings are both present
    assert 'sine_line2_color' in spotify_vis_config, "sine_line2_color not in config"
    assert 'sine_line4_color' in spotify_vis_config, "sine_line4_color not in config"
    
    print(f"sine_line2_color: {spotify_vis_config['sine_line2_color']}")
    print(f"sine_line4_color: {spotify_vis_config['sine_line4_color']}")
    
    # Verify values are correct
    assert spotify_vis_config['sine_line4_color'] == [0, 255, 255, 230], \
        f"Expected [0, 255, 255, 230], got {spotify_vis_config['sine_line4_color']}"
    
    # Test loading back
    def mock_config_get(key, default=None):
        return spotify_vis_config.get(key, default)
    
    # Create a fresh tab
    tab2 = TestTab()
    # Reset to defaults
    tab2._sine_line4_color = QColor(255, 0, 150, 230)
    
    # Load the settings
    load_sine_wave_mode_settings(tab2, mock_config_get)
    
    print(f"After load, line4 color: {tab2._sine_line4_color.getRgb()}")
    
    assert tab2._sine_line4_color.getRgb()[:4] == (0, 255, 255, 230), \
        f"Expected (0, 255, 255, 230), got {tab2._sine_line4_color.getRgb()}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
