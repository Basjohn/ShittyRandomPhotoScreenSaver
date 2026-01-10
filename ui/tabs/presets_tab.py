"""
Presets tab for settings dialog.

Provides a slider-based interface for switching between predefined widget configurations.
The "Custom" preset preserves user's manual settings.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QFrame, QSizePolicy, QScrollArea, QPushButton,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.logging.logger import get_logger
from core.presets import (
    PRESET_DEFINITIONS,
    get_ordered_presets,
    get_preset_by_index,
    apply_preset,
    get_current_preset_info,
    reset_non_custom_presets,
)

if TYPE_CHECKING:
    from core.settings.settings_manager import SettingsManager

logger = get_logger(__name__)


class PresetSlider(QSlider):
    """Custom slider with discrete notches for presets."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setObjectName("presetSlider")
        self._setup_style()
    
    def _setup_style(self) -> None:
        """Apply custom styling for the preset slider to match app theme."""
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 2px solid rgba(68, 68, 68, 1.0);
                height: 8px;
                background: rgba(35, 35, 35, 1.0);
                margin: 2px 0;
                border-radius: 4px;
            }
            
            QSlider::handle:horizontal {
                background: rgba(255, 255, 255, 0.95);
                border: 2px solid rgba(255, 255, 255, 1.0);
                width: 20px;
                margin: -6px 0;
                border-radius: 10px;
            }
            
            QSlider::handle:horizontal:hover {
                background: rgba(255, 255, 255, 1.0);
                border: 2px solid rgba(153, 153, 153, 1.0);
            }
            
            QSlider::sub-page:horizontal {
                background: rgba(58, 58, 58, 1.0);
                border: 2px solid rgba(102, 102, 102, 1.0);
                height: 8px;
                border-radius: 4px;
            }
        """)


class PresetDescriptionBox(QFrame):
    """Description box showing preset details."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("presetDescriptionBox")
        self._setup_ui()
        self._setup_style()
    
    def _setup_ui(self) -> None:
        """Setup the description box UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        # Preset name label
        self._name_label = QLabel()
        self._name_label.setObjectName("presetNameLabel")
        
        # Preset description label
        self._description_label = QLabel()
        self._description_label.setObjectName("presetDescriptionLabel")
        self._description_label.setWordWrap(True)
        
        layout.addWidget(self._name_label)
        layout.addWidget(self._description_label)
        layout.addStretch()
    
    def set_font_family(self, font_family: str) -> None:
        """Update font family for labels."""
        name_font = QFont(font_family, 14, QFont.Weight.Bold)
        self._name_label.setFont(name_font)
        
        desc_font = QFont(font_family, 11, QFont.Weight.Normal)
        self._description_label.setFont(desc_font)
    
    def _setup_style(self) -> None:
        """Apply custom styling."""
        self.setStyleSheet("""
            #presetDescriptionBox {
                background-color: rgba(40, 40, 40, 0.9);
                border: 1px solid rgba(90, 90, 90, 0.8);
                border-radius: 8px;
            }
            
            #presetNameLabel {
                color: #ffffff;
            }
            
            #presetDescriptionLabel {
                color: #cccccc;
            }
        """)
    
    def set_preset(self, name: str, description: str) -> None:
        """Update the displayed preset information."""
        self._name_label.setText(name)
        self._description_label.setText(description)


class PresetsTab(QScrollArea):
    """Presets configuration tab."""
    
    # Signal emitted when preset changes (for live preview)
    preset_changed = Signal(str)  # preset_key
    # Signal emitted when settings need to be reloaded in all tabs
    settings_reloaded = Signal()
    
    def __init__(self, settings_manager: "SettingsManager", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._settings = settings_manager
        self._updating_slider = False  # Prevent recursive updates
        
        self._setup_ui()
        self._load_current_preset()
        
        logger.debug("[PRESETS_TAB] Initialized")
    
    def _setup_ui(self) -> None:
        """Setup the tab UI."""
        # Scroll area setup
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Main content widget
        content = QWidget()
        content.setObjectName("presetsTabContent")
        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Get font from widget settings
        font_family = self._settings.get("widgets.clock.font_family", "Segoe UI")
        
        # Header
        header = QLabel("Presets")
        header.setObjectName("presetsHeader")
        header_font = QFont(font_family, 18, QFont.Weight.Bold)
        header.setFont(header_font)
        header.setStyleSheet("color: #ffffff;")
        main_layout.addWidget(header)
        
        # Subtitle
        subtitle = QLabel(
            "Choose a preset configuration or use Custom to keep your own settings."
        )
        subtitle.setWordWrap(True)
        subtitle_font = QFont(font_family, 12, QFont.Weight.Normal)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: #aaaaaa;")
        main_layout.addWidget(subtitle)
        
        # Spacer
        main_layout.addSpacing(10)
        
        # Slider section
        slider_section = QWidget()
        slider_layout = QVBoxLayout(slider_section)
        slider_layout.setContentsMargins(0, 0, 0, 0)
        slider_layout.setSpacing(10)
        
        # Slider labels row
        labels_layout = QHBoxLayout()
        labels_layout.setContentsMargins(0, 0, 0, 0)
        
        # Get ordered presets for labels
        ordered = get_ordered_presets()
        preset_count = len(ordered)
        
        # Create labels for all presets with proper spacing
        # We'll use a grid-like approach with stretch factors
        for i, preset_key in enumerate(ordered):
            preset = PRESET_DEFINITIONS.get(preset_key)
            if not preset:
                continue
            
            label = QLabel(preset.name)
            label_font = QFont(font_family, 11, QFont.Weight.Normal)
            label.setFont(label_font)
            label.setStyleSheet("color: #ffffff;")
            
            # Alignment based on position
            if i == 0:
                label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            elif i == len(ordered) - 1:
                label.setAlignment(Qt.AlignmentFlag.AlignRight)
            else:
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Add label with stretch before it (except first)
            if i > 0:
                labels_layout.addStretch(1)
            labels_layout.addWidget(label)
        
        # Final stretch after last label is not needed since it's right-aligned
        
        slider_layout.addLayout(labels_layout)
        
        # The slider
        self._slider = PresetSlider()
        self._slider.setMinimum(0)
        self._slider.setMaximum(preset_count - 1)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.setTickInterval(1)
        self._slider.setPageStep(1)
        self._slider.setSingleStep(1)
        self._slider.setMinimumHeight(40)
        self._slider.valueChanged.connect(self._on_slider_changed)
        
        slider_layout.addWidget(self._slider)
        
        main_layout.addWidget(slider_section)
        
        # Spacer
        main_layout.addSpacing(10)
        
        # Description box
        self._description_box = PresetDescriptionBox()
        self._description_box.set_font_family(font_family)
        self._description_box.setMinimumHeight(100)
        self._description_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, 
            QSizePolicy.Policy.Minimum
        )
        main_layout.addWidget(self._description_box)
        
        # Stretch to push everything up
        main_layout.addStretch()
        
        # Bottom right button row
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 10, 0, 0)
        button_row.addStretch()
        
        self._reset_presets_btn = QPushButton("Reset Non-Custom Presets")
        self._reset_presets_btn.setFixedHeight(24)
        self._reset_presets_btn.setStyleSheet("font-size: 11px; padding: 4px 10px;")
        self._reset_presets_btn.setToolTip("Reset all preset definitions to defaults (preserves Custom preset)")
        self._reset_presets_btn.clicked.connect(self._on_reset_presets_clicked)
        button_row.addWidget(self._reset_presets_btn)
        
        main_layout.addLayout(button_row)
        
        self.setWidget(content)
    
    def _load_current_preset(self) -> None:
        """Load and display the current preset from settings."""
        info = get_current_preset_info(self._settings)
        
        self._updating_slider = True
        self._slider.setValue(info["index"])
        self._updating_slider = False
        
        self._description_box.set_preset(info["name"], info["description"])
        
        logger.debug("[PRESETS_TAB] Loaded preset: %s (index %d)", info["key"], info["index"])
    
    def _on_slider_changed(self, value: int) -> None:
        """Handle slider value change."""
        if self._updating_slider:
            return
        
        preset_key = get_preset_by_index(value)
        if preset_key is None:
            return
        
        preset = PRESET_DEFINITIONS.get(preset_key)
        if preset is None:
            return
        
        # Update description box
        self._description_box.set_preset(preset.name, preset.description)
        
        # Apply the preset
        if apply_preset(self._settings, preset_key):
            self.preset_changed.emit(preset_key)
            self.settings_reloaded.emit()
            logger.info("[PRESETS_TAB] Applied preset: %s", preset.name)
    
    def refresh(self) -> None:
        """Refresh the tab to reflect current settings."""
        self._load_current_preset()
    
    def _on_reset_presets_clicked(self) -> None:
        """Reset all non-custom preset definitions to defaults."""
        try:
            reset_non_custom_presets(self._settings)
            
            # Reload current preset to reflect any changes
            self._load_current_preset()
            
            logger.info("[PRESETS_TAB] Non-custom presets reset by user")
            
        except Exception as exc:
            logger.exception("Failed to reset presets: %s", exc)
