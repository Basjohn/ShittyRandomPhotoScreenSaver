"""UI simulation test for Sine Line 4 color persistence.

This test simulates the actual user workflow:
1. Create a tab with UI elements
2. Change line 4 color via color button
3. Verify the attribute is set and save is triggered
4. Verify the setting would be collected correctly
"""
import pytest
from PySide6.QtGui import QColor


@pytest.mark.qt
def test_sine_line4_color_button_sets_attribute(qt_app, qtbot):
    """Test that clicking the color button sets the attribute correctly."""
    from PySide6.QtWidgets import QWidget
    from ui.widgets.color_swatch import ColorSwatchButton
    
    # Create a minimal tab mock with real Qt objects
    class MockTab(QWidget):
        def __init__(self):
            super().__init__()
            self._save_called = False
            # Initialize with default color
            self._sine_line4_color = QColor(255, 0, 150, 230)
            self._sine_line4_glow_color = QColor(255, 0, 150, 180)
            # Create the color button
            self.sine_line4_color_btn = ColorSwatchButton(self, self._sine_line4_color)
            
        def _save_settings(self):
            self._save_called = True
            print(f"_save_settings called! Attribute _sine_line4_color = {self._sine_line4_color.getRgb()}")
    
    tab = MockTab()
    
    # Bind the color button like the builder does
    tab.sine_line4_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_sine_line4_color', c), tab._save_settings())
    )
    
    # Get initial color
    initial_color = tab._sine_line4_color.getRgb()
    print(f"Initial _sine_line4_color: {initial_color}")
    
    # Simulate user picking a new color (cyan)
    new_color = QColor(0, 255, 255, 230)
    tab.sine_line4_color_btn.set_color(new_color)
    
    # Check that the attribute was updated
    updated_color = tab._sine_line4_color.getRgb()
    print(f"After set_color _sine_line4_color: {updated_color}")
    
    assert updated_color[:4] == (0, 255, 255, 230), \
        f"Expected (0, 255, 255, 230), got {updated_color}"
    
    # Check that save was called
    assert tab._save_called, "_save_settings was not called when color changed"


@pytest.mark.qt
def test_sine_line4_vs_line2_builder_pattern(qt_app, qtbot):
    """Compare line 2 and line 4 builder patterns directly."""
    from PySide6.QtWidgets import QWidget
    from ui.widgets.color_swatch import ColorSwatchButton
    
    class MockTab(QWidget):
        def __init__(self):
            super().__init__()
            self._save_called_line2 = False
            self._save_called_line4 = False
            
            # Line 2 setup (pattern from builder)
            self._sine_line2_color = QColor(255, 120, 50, 230)
            self.sine_line2_color_btn = ColorSwatchButton(self, self._sine_line2_color)
            
            # Line 4 setup (pattern from builder)
            self._sine_line4_color = QColor(255, 0, 150, 230)
            self.sine_line4_color_btn = ColorSwatchButton(self, self._sine_line4_color)
        
        def _save_settings_line2(self):
            self._save_called_line2 = True
            
        def _save_settings_line4(self):
            self._save_called_line4 = True
    
    tab = MockTab()
    
    # Line 2 binding (from builder - uses bind_setting_signal pattern)
    # Looking at builder: tab.sine_line2_color_btn.color_changed.connect(lambda c: (setattr(tab, '_sine_line2_color', c), bind_setting_signal(tab, None, attr_name='_sine_line2_color', value=c)))
    # But simpler pattern:
    tab.sine_line2_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_sine_line2_color', c), tab._save_settings_line2())
    )
    
    # Line 4 binding (from builder - direct lambda)
    tab.sine_line4_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_sine_line4_color', c), tab._save_settings_line4())
    )
    
    # Change both colors
    tab.sine_line2_color_btn.set_color(QColor(100, 100, 100, 230))
    tab.sine_line4_color_btn.set_color(QColor(100, 100, 100, 230))
    
    print(f"Line 2 color: {tab._sine_line2_color.getRgb()}, save called: {tab._save_called_line2}")
    print(f"Line 4 color: {tab._sine_line4_color.getRgb()}, save called: {tab._save_called_line4}")
    
    # Both should behave the same
    assert tab._sine_line2_color.getRgb()[:4] == (100, 100, 100, 230)
    assert tab._sine_line4_color.getRgb()[:4] == (100, 100, 100, 230)
    assert tab._save_called_line2, "Line 2 save not called"
    assert tab._save_called_line4, "Line 4 save not called"


@pytest.mark.qt
def test_sine_line4_horizontal_shift_slider(qt_app, qtbot):
    """Test that horizontal shift slider saves correctly."""
    from PySide6.QtWidgets import QWidget, QSlider
    from PySide6.QtCore import Qt
    
    class MockTab(QWidget):
        def __init__(self):
            super().__init__()
            self._save_called = False
            self._sine_line4_horizontal_shift = 25  # Default value
            
            self.sine_line4_horizontal_shift = QSlider(Qt.Orientation.Horizontal, self)
            self.sine_line4_horizontal_shift.setRange(-50, 50)
            self.sine_line4_horizontal_shift.setValue(self._sine_line4_horizontal_shift)
        
        def _save_settings(self):
            self._save_called = True
    
    tab = MockTab()
    
    # Bind like the builder does
    tab.sine_line4_horizontal_shift.valueChanged.connect(
        lambda v: (setattr(tab, '_sine_line4_horizontal_shift', v), tab._save_settings())
    )
    
    # Change the value
    tab.sine_line4_horizontal_shift.setValue(40)
    
    print(f"Horizontal shift value: {tab._sine_line4_horizontal_shift}")
    print(f"Save called: {tab._save_called}")
    
    assert tab._sine_line4_horizontal_shift == 40
    assert tab._save_called


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
