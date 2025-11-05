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
    QSpinBox, QGroupBox, QCheckBox
)
from PySide6.QtCore import Signal

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
        """Setup tab UI."""
        layout = QVBoxLayout(self)
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
            "Diffuse",
            "Block Puzzle Flip"
        ])
        self.transition_combo.currentTextChanged.connect(self._on_transition_changed)
        type_row.addWidget(self.transition_combo)
        type_row.addStretch()
        type_layout.addLayout(type_row)
        
        layout.addWidget(type_group)
        
        # Duration group
        duration_group = QGroupBox("Timing")
        duration_layout = QVBoxLayout(duration_group)
        
        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("Duration (ms):"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(100, 10000)
        self.duration_spin.setSingleStep(100)
        self.duration_spin.setValue(1000)
        self.duration_spin.valueChanged.connect(self._save_settings)
        duration_row.addWidget(self.duration_spin)
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
            "Diagonal TL-BR",
            "Diagonal TR-BL",
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
        
        layout.addWidget(self.diffuse_group)
        
        layout.addStretch()
        
        # Update visibility based on default transition
        self._update_specific_settings()
    
    def _load_settings(self) -> None:
        """Load settings from settings manager."""
        transitions_config = self._settings.get('transitions', {})
        
        # Load transition type
        transition_type = transitions_config.get('type', 'Crossfade')
        index = self.transition_combo.findText(transition_type)
        if index >= 0:
            self.transition_combo.setCurrentIndex(index)
        
        # Load duration
        duration = transitions_config.get('duration_ms', 1000)
        self.duration_spin.setValue(duration)
        
        # Load direction
        direction = transitions_config.get('direction', 'Left to Right')
        index = self.direction_combo.findText(direction)
        if index >= 0:
            self.direction_combo.setCurrentIndex(index)
        
        # Load easing
        easing = transitions_config.get('easing', 'InOutQuad')
        index = self.easing_combo.findText(easing)
        if index >= 0:
            self.easing_combo.setCurrentIndex(index)
        
        # Load block flip settings
        block_flip = transitions_config.get('block_flip', {})
        self.grid_rows_spin.setValue(block_flip.get('rows', 4))
        self.grid_cols_spin.setValue(block_flip.get('cols', 6))
        
        # Load diffuse settings
        diffuse = transitions_config.get('diffuse', {})
        self.block_size_spin.setValue(diffuse.get('block_size', 50))
        
        logger.debug("Loaded transition settings")
    
    def _on_transition_changed(self, transition: str) -> None:
        """Handle transition type change."""
        self._update_specific_settings()
        self._save_settings()
    
    def _update_specific_settings(self) -> None:
        """Update visibility of transition-specific settings."""
        transition = self.transition_combo.currentText()
        
        # Show/hide direction for directional transitions
        show_direction = transition in ["Slide", "Diffuse"]
        self.direction_group.setVisible(show_direction)
        
        # Show/hide block flip settings
        self.flip_group.setVisible(transition == "Block Puzzle Flip")
        
        # Show/hide diffuse settings
        self.diffuse_group.setVisible(transition == "Diffuse")
    
    def _save_settings(self) -> None:
        """Save current settings."""
        config = {
            'type': self.transition_combo.currentText(),
            'duration_ms': self.duration_spin.value(),
            'direction': self.direction_combo.currentText(),
            'easing': self.easing_combo.currentText(),
            'block_flip': {
                'rows': self.grid_rows_spin.value(),
                'cols': self.grid_cols_spin.value()
            },
            'diffuse': {
                'block_size': self.block_size_spin.value()
            }
        }
        
        self._settings.set('transitions', config)
        self._settings.save()
        self.transitions_changed.emit()
        
        logger.debug(f"Saved transition settings: {config['type']}")
