"""
Transitions configuration tab for settings dialog.

Allows users to configure transition settings:
- Transition type selection
- Duration
- Direction (for directional transitions)
- Easing curves
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QGroupBox, QScrollArea, QSlider
)
from PySide6.QtCore import Signal, Qt

from core.settings.settings_manager import SettingsManager
from core.logging.logger import get_logger

logger = get_logger(__name__)


class TransitionsTab(QWidget):
    """Transitions configuration tab."""
    
    # Signals
    transitions_changed = Signal()
    
    def __init__(self, settings: SettingsManager, parent: Optional[QWidget] = None):
        """
        Initialize transitions tab.
        
        Args:
            settings: Settings manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._settings = settings
        self._setup_ui()
        self._load_settings()
        
        logger.debug("TransitionsTab created")
    
    def _setup_ui(self) -> None:
        """Setup tab UI with scroll area."""
        # Create scroll area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollArea QWidget { background: transparent; }
        """)
        
        # Create content widget
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Transition Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)
        
        # Transition type group
        type_group = QGroupBox("Transition Type")
        type_layout = QVBoxLayout(type_group)
        
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Transition:"))
        self.transition_combo = QComboBox()
        self.transition_combo.addItems([
            "Crossfade",
            "Slide",
            "Wipe",
            "Diffuse",
            "Block Puzzle Flip"
        ])
        self.transition_combo.currentTextChanged.connect(self._on_transition_changed)
        type_row.addWidget(self.transition_combo)
        type_row.addStretch()
        type_layout.addLayout(type_row)
        
        layout.addWidget(type_group)
        
        # Duration group (slider: short → long)
        duration_group = QGroupBox("Timing")
        duration_layout = QVBoxLayout(duration_group)
        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("Duration (short → long):"))
        self.duration_slider = QSlider(Qt.Orientation.Horizontal)
        self.duration_slider.setRange(100, 10000)  # store milliseconds directly
        self.duration_slider.setSingleStep(100)
        self.duration_slider.setPageStep(500)
        self.duration_slider.setValue(1300)  # BUG FIX #5: Increased from 1000ms (30% slower)
        self.duration_slider.valueChanged.connect(self._on_duration_changed)
        duration_row.addWidget(self.duration_slider, 1)
        self.duration_value_label = QLabel("1300 ms")
        duration_row.addWidget(self.duration_value_label)
        duration_row.addStretch()
        duration_layout.addLayout(duration_row)
        layout.addWidget(duration_group)
        
        # Direction group (for directional transitions)
        self.direction_group = QGroupBox("Direction")
        direction_layout = QVBoxLayout(self.direction_group)
        
        direction_row = QHBoxLayout()
        direction_row.addWidget(QLabel("Direction:"))
        self.direction_combo = QComboBox()
        self.direction_combo.addItems([
            "Left to Right",
            "Right to Left",
            "Top to Bottom",
            "Bottom to Top",
            "Random"
        ])
        self.direction_combo.currentTextChanged.connect(self._save_settings)
        direction_row.addWidget(self.direction_combo)
        direction_row.addStretch()
        direction_layout.addLayout(direction_row)
        
        layout.addWidget(self.direction_group)
        
        # Easing group
        easing_group = QGroupBox("Easing Curve")
        easing_layout = QVBoxLayout(easing_group)
        
        easing_row = QHBoxLayout()
        easing_row.addWidget(QLabel("Easing:"))
        self.easing_combo = QComboBox()
        self.easing_combo.addItems([
            "Auto",
            "Linear",
            "InQuad", "OutQuad", "InOutQuad",
            "InCubic", "OutCubic", "InOutCubic",
            "InQuart", "OutQuart", "InOutQuart",
            "InExpo", "OutExpo", "InOutExpo",
            "InSine", "OutSine", "InOutSine",
            "InCirc", "OutCirc", "InOutCirc",
            "InBack", "OutBack", "InOutBack"
        ])
        self.easing_combo.currentTextChanged.connect(self._save_settings)
        easing_row.addWidget(self.easing_combo)
        easing_row.addStretch()
        easing_layout.addLayout(easing_row)
        
        layout.addWidget(easing_group)
        
        # Block flip specific settings
        self.flip_group = QGroupBox("Block Flip Settings")
        flip_layout = QVBoxLayout(self.flip_group)
        
        grid_row = QHBoxLayout()
        grid_row.addWidget(QLabel("Grid Size:"))
        self.grid_rows_spin = QSpinBox()
        self.grid_rows_spin.setRange(2, 10)
        self.grid_rows_spin.setValue(4)
        self.grid_rows_spin.valueChanged.connect(self._save_settings)
        grid_row.addWidget(QLabel("Rows:"))
        grid_row.addWidget(self.grid_rows_spin)
        self.grid_cols_spin = QSpinBox()
        self.grid_cols_spin.setRange(2, 10)
        self.grid_cols_spin.setValue(6)
        self.grid_cols_spin.valueChanged.connect(self._save_settings)
        grid_row.addWidget(QLabel("Cols:"))
        grid_row.addWidget(self.grid_cols_spin)
        grid_row.addStretch()
        flip_layout.addLayout(grid_row)
        
        layout.addWidget(self.flip_group)
        
        # Diffuse specific settings
        self.diffuse_group = QGroupBox("Diffuse Settings")
        diffuse_layout = QVBoxLayout(self.diffuse_group)
        
        block_size_row = QHBoxLayout()
        block_size_row.addWidget(QLabel("Block Size (px):"))
        self.block_size_spin = QSpinBox()
        self.block_size_spin.setRange(10, 200)
        self.block_size_spin.setValue(50)
        self.block_size_spin.valueChanged.connect(self._save_settings)
        block_size_row.addWidget(self.block_size_spin)
        block_size_row.addStretch()
        diffuse_layout.addLayout(block_size_row)
        
        shape_row = QHBoxLayout()
        shape_row.addWidget(QLabel("Shape:"))
        self.diffuse_shape_combo = QComboBox()
        self.diffuse_shape_combo.addItems(["Rectangle", "Circle", "Triangle"])
        self.diffuse_shape_combo.currentTextChanged.connect(self._save_settings)
        shape_row.addWidget(self.diffuse_shape_combo)
        shape_row.addStretch()
        diffuse_layout.addLayout(shape_row)
        
        layout.addWidget(self.diffuse_group)
        
        layout.addStretch()
        
        # Set scroll area widget and add to main layout
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        # Update visibility based on default transition
        self._update_specific_settings()
        
        # Improve +/- button clarity and feedback on spin boxes
        self.setStyleSheet(
            self.styleSheet() + """
            QSpinBox, QDoubleSpinBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding-right: 24px; /* space for buttons */
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                width: 18px;
                background: #2a2a2a;
                border-left: 1px solid #3a3a3a;
                margin: 0px;
            }
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
                background: #3a3a3a;
            }
            QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
            QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
                background: #505050;
            }
            """
        )
    
    def _load_settings(self) -> None:
        """Load settings from settings manager."""
        transitions_config = self._settings.get('transitions', {})
        
        # Load transition type
        transition_type = transitions_config.get('type', 'Crossfade')
        index = self.transition_combo.findText(transition_type)
        if index >= 0:
            self.transition_combo.setCurrentIndex(index)
        
        # Load duration (default 1300ms - Bug Fix #5)
        duration = transitions_config.get('duration_ms', 1300)
        self.duration_slider.setValue(duration)
        self.duration_value_label.setText(f"{duration} ms")
        
        # Load direction
        direction = transitions_config.get('direction', 'Left to Right')
        index = self.direction_combo.findText(direction)
        if index >= 0:
            self.direction_combo.setCurrentIndex(index)
        
        # Load easing
        easing = transitions_config.get('easing', 'Auto')
        index = self.easing_combo.findText(easing)
        if index >= 0:
            self.easing_combo.setCurrentIndex(index)

        # Note: GPU acceleration is controlled globally in Display tab
        
        # Load block flip settings
        block_flip = transitions_config.get('block_flip', {})
        self.grid_rows_spin.setValue(block_flip.get('rows', 4))
        self.grid_cols_spin.setValue(block_flip.get('cols', 6))
        
        # Load diffuse settings
        diffuse = transitions_config.get('diffuse', {})
        self.block_size_spin.setValue(diffuse.get('block_size', 50))
        shape = diffuse.get('shape', 'Rectangle')
        index = self.diffuse_shape_combo.findText(shape)
        if index >= 0:
            self.diffuse_shape_combo.setCurrentIndex(index)
        
        logger.debug("Loaded transition settings")
    
    def _on_transition_changed(self, transition: str) -> None:
        """Handle transition type change."""
        self._update_specific_settings()
        self._save_settings()
    
    def _update_specific_settings(self) -> None:
        """Update visibility of transition-specific settings."""
        transition = self.transition_combo.currentText()
        
        # Show/hide direction for directional transitions
        show_direction = transition in ["Slide", "Wipe", "Diffuse"]
        self.direction_group.setVisible(show_direction)
        
        # Show/hide block flip settings
        self.flip_group.setVisible(transition == "Block Puzzle Flip")
        
        # Show/hide diffuse settings
        self.diffuse_group.setVisible(transition == "Diffuse")
    
    def _save_settings(self) -> None:
        """Save current settings."""
        config = {
            'type': self.transition_combo.currentText(),
            'duration_ms': self.duration_slider.value(),
            'direction': self.direction_combo.currentText(),
            'easing': self.easing_combo.currentText(),
            'block_flip': {
                'rows': self.grid_rows_spin.value(),
                'cols': self.grid_cols_spin.value()
            },
            'diffuse': {
                'block_size': self.block_size_spin.value(),
                'shape': self.diffuse_shape_combo.currentText()
            }
        }
        
        self._settings.set('transitions', config)
        self._settings.save()
        self.transitions_changed.emit()
        
        logger.debug(f"Saved transition settings: {config['type']}")

    def _on_duration_changed(self, value: int) -> None:
        """Update label and persist duration to settings."""
        self.duration_value_label.setText(f"{value} ms")
        self._save_settings()
