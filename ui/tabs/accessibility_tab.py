"""
Accessibility configuration tab for settings dialog.

Provides accessibility-focused features:
- Background Dimming: Adds a semi-transparent black overlay behind widgets
- Widget Pixel Shift: Subtle periodic movement to prevent burn-in on older displays
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QCheckBox, QSlider, QScrollArea,
)
from PySide6.QtCore import Signal, Qt

from core.settings.settings_manager import SettingsManager
from core.logging.logger import get_logger

logger = get_logger(__name__)


class NoWheelSlider(QSlider):
    """Slider that ignores mouse wheel events to prevent accidental changes."""
    def wheelEvent(self, event):  # type: ignore[override]
        event.ignore()


class AccessibilityTab(QWidget):
    """Accessibility configuration tab."""
    
    # Signals
    accessibility_changed = Signal()
    
    def __init__(self, settings: SettingsManager, parent: Optional[QWidget] = None):
        """
        Initialize accessibility tab.
        
        Args:
            settings: Settings manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._settings = settings
        self._loading = True
        self._setup_ui()
        self._load_settings()
        self._loading = False
        
        logger.debug("AccessibilityTab created")
    
    def load_from_settings(self) -> None:
        """Reload all UI controls from settings manager (called after preset change)."""
        self._loading = True
        try:
            self._load_settings()
        finally:
            self._loading = False
        logger.debug("[ACCESSIBILITY_TAB] Reloaded from settings")
    
    def _setup_ui(self) -> None:
        """Setup tab UI with scroll area."""
        # Create scroll area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { 
                border: none; 
                background: transparent; 
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollArea QWidget {
                background: transparent;
            }
        """)
        
        # Create content widget
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Accessibility")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "These features help reduce eye strain and prevent screen burn-in on older displays."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaaaaa; font-size: 11px; margin-bottom: 10px;")
        layout.addWidget(desc)
        
        # Background Dimming group
        dimming_group = self._create_dimming_group()
        layout.addWidget(dimming_group)
        
        # Widget Pixel Shift group
        shift_group = self._create_pixel_shift_group()
        layout.addWidget(shift_group)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def _create_dimming_group(self) -> QGroupBox:
        """Create the Background Dimming settings group."""
        group = QGroupBox("Background Dimming")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        
        # Enable checkbox
        self.dimming_enabled = QCheckBox("Enable Background Dimming")
        self.dimming_enabled.setToolTip(
            "Adds a semi-transparent black overlay behind all widgets to reduce "
            "brightness and improve widget readability on bright images.\n\n"
            "⚠️ Medium Performance Penalty"
        )
        self.dimming_enabled.stateChanged.connect(self._on_dimming_enabled_changed)
        layout.addWidget(self.dimming_enabled)
        
        # Opacity slider row
        opacity_row = QHBoxLayout()
        opacity_label = QLabel("Dimming Opacity:")
        opacity_label.setMinimumWidth(120)
        opacity_row.addWidget(opacity_label)
        
        self.dimming_opacity_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.dimming_opacity_slider.setRange(10, 90)  # 10% to 90%
        self.dimming_opacity_slider.setValue(30)  # Default 30%
        self.dimming_opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.dimming_opacity_slider.setTickInterval(10)
        self.dimming_opacity_slider.valueChanged.connect(self._on_dimming_opacity_changed)
        opacity_row.addWidget(self.dimming_opacity_slider, 1)
        
        self.dimming_opacity_value = QLabel("30%")
        self.dimming_opacity_value.setMinimumWidth(40)
        self.dimming_opacity_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        opacity_row.addWidget(self.dimming_opacity_value)
        
        layout.addLayout(opacity_row)
        
        # Description
        dim_desc = QLabel(
            "The dimming overlay appears above the wallpaper/transitions but below all widgets, "
            "reducing overall screen brightness without affecting widget visibility."
        )
        dim_desc.setWordWrap(True)
        dim_desc.setStyleSheet("color: #888888; font-size: 10px; margin-top: 5px;")
        layout.addWidget(dim_desc)
        
        return group
    
    def _create_pixel_shift_group(self) -> QGroupBox:
        """Create the Widget Pixel Shift settings group."""
        group = QGroupBox("Widget Pixel Shift (Burn-in Prevention)")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        
        # Enable checkbox
        self.pixel_shift_enabled = QCheckBox("Enable Widget Pixel Shift")
        self.pixel_shift_enabled.setToolTip(
            "Periodically shifts all overlay widgets by 1 pixel in a random direction "
            "to prevent static elements from causing burn-in on older LCD displays."
        )
        self.pixel_shift_enabled.stateChanged.connect(self._on_pixel_shift_enabled_changed)
        layout.addWidget(self.pixel_shift_enabled)
        
        # Shifts per minute slider row
        shift_row = QHBoxLayout()
        shift_label = QLabel("Shifts Per Minute:")
        shift_label.setMinimumWidth(120)
        shift_row.addWidget(shift_label)
        
        self.pixel_shift_rate_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.pixel_shift_rate_slider.setRange(1, 5)
        self.pixel_shift_rate_slider.setValue(1)  # Default 1 shift per minute
        self.pixel_shift_rate_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.pixel_shift_rate_slider.setTickInterval(1)
        self.pixel_shift_rate_slider.valueChanged.connect(self._on_pixel_shift_rate_changed)
        shift_row.addWidget(self.pixel_shift_rate_slider, 1)
        
        self.pixel_shift_rate_value = QLabel("1")
        self.pixel_shift_rate_value.setMinimumWidth(30)
        self.pixel_shift_rate_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        shift_row.addWidget(self.pixel_shift_rate_value)
        
        layout.addLayout(shift_row)
        
        # Description
        shift_desc = QLabel(
            "Widgets will drift up to 4 pixels in any direction, then drift back. "
            "This subtle movement is designed to be imperceptible while preventing "
            "static burn-in on susceptible displays. Not effective for OLED burn-in."
        )
        shift_desc.setWordWrap(True)
        shift_desc.setStyleSheet("color: #888888; font-size: 10px; margin-top: 5px;")
        layout.addWidget(shift_desc)
        
        return group
    
    def _load_settings(self) -> None:
        """Load settings from settings manager."""
        try:
            # Background Dimming
            dimming_enabled = self._settings.get("accessibility.dimming.enabled", False)
            self.dimming_enabled.setChecked(SettingsManager.to_bool(dimming_enabled, False))
            
            dimming_opacity = self._settings.get("accessibility.dimming.opacity", 30)
            try:
                opacity_val = int(dimming_opacity)
                opacity_val = max(10, min(90, opacity_val))
            except (ValueError, TypeError):
                opacity_val = 30
            self.dimming_opacity_slider.setValue(opacity_val)
            self.dimming_opacity_value.setText(f"{opacity_val}%")
            
            # Widget Pixel Shift
            shift_enabled = self._settings.get("accessibility.pixel_shift.enabled", False)
            self.pixel_shift_enabled.setChecked(SettingsManager.to_bool(shift_enabled, False))
            
            shift_rate = self._settings.get("accessibility.pixel_shift.rate", 1)
            try:
                rate_val = int(shift_rate)
                rate_val = max(1, min(5, rate_val))
            except (ValueError, TypeError):
                rate_val = 1
            self.pixel_shift_rate_slider.setValue(rate_val)
            self.pixel_shift_rate_value.setText(str(rate_val))
            
            # Update enabled states
            self._update_dimming_controls_state()
            self._update_pixel_shift_controls_state()
            
            logger.debug("Accessibility settings loaded")
        except Exception as e:
            logger.warning("Failed to load accessibility settings: %s", e, exc_info=True)
    
    def _save_settings(self) -> None:
        """Save settings to settings manager."""
        if self._loading:
            return
        
        try:
            # Background Dimming
            self._settings.set("accessibility.dimming.enabled", self.dimming_enabled.isChecked())
            self._settings.set("accessibility.dimming.opacity", self.dimming_opacity_slider.value())
            
            # Widget Pixel Shift
            self._settings.set("accessibility.pixel_shift.enabled", self.pixel_shift_enabled.isChecked())
            self._settings.set("accessibility.pixel_shift.rate", self.pixel_shift_rate_slider.value())
            
            self.accessibility_changed.emit()
            logger.debug("Accessibility settings saved")
        except Exception as e:
            logger.warning("Failed to save accessibility settings: %s", e, exc_info=True)
    
    def _on_dimming_enabled_changed(self, state: int) -> None:
        """Handle dimming enabled checkbox change."""
        self._update_dimming_controls_state()
        self._save_settings()
    
    def _on_dimming_opacity_changed(self, value: int) -> None:
        """Handle dimming opacity slider change."""
        self.dimming_opacity_value.setText(f"{value}%")
        self._save_settings()
    
    def _on_pixel_shift_enabled_changed(self, state: int) -> None:
        """Handle pixel shift enabled checkbox change."""
        self._update_pixel_shift_controls_state()
        self._save_settings()
    
    def _on_pixel_shift_rate_changed(self, value: int) -> None:
        """Handle pixel shift rate slider change."""
        self.pixel_shift_rate_value.setText(str(value))
        self._save_settings()
    
    def _update_dimming_controls_state(self) -> None:
        """Update enabled state of dimming controls based on checkbox."""
        enabled = self.dimming_enabled.isChecked()
        self.dimming_opacity_slider.setEnabled(enabled)
    
    def _update_pixel_shift_controls_state(self) -> None:
        """Update enabled state of pixel shift controls based on checkbox."""
        enabled = self.pixel_shift_enabled.isChecked()
        self.pixel_shift_rate_slider.setEnabled(enabled)
