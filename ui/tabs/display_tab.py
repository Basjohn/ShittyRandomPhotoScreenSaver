"""
Display configuration tab for settings dialog.

Allows users to configure display settings:
- Monitor selection (primary, all, specific)
- Display mode (Fill, Fit, Shrink)
- Same image on all monitors
- Image rotation interval
- Shuffle mode
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QGroupBox, QCheckBox, QScrollArea
)
from PySide6.QtCore import Signal

from core.settings.settings_manager import SettingsManager
from core.logging.logger import get_logger

logger = get_logger(__name__)


class DisplayTab(QWidget):
    """Display configuration tab."""
    
    # Signals
    display_changed = Signal()
    
    def __init__(self, settings: SettingsManager, parent: Optional[QWidget] = None):
        """
        Initialize display tab.
        
        Args:
            settings: Settings manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._settings = settings
        self.settings_manager = settings  # Also expose as property for tests
        self._setup_ui()
        self._load_settings()
        
        logger.debug("DisplayTab created")
    
    def _setup_ui(self) -> None:
        """Setup tab UI with scroll area."""
        # Create scroll area
        from PySide6.QtCore import Qt
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
        layout.setSpacing(20)  # Increased from 15 to 20 for better breathing room
        
        # Title
        title = QLabel("Display Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)
        
        # Monitor selection group
        monitor_group = QGroupBox("Monitor Configuration")
        monitor_layout = QVBoxLayout(monitor_group)
        
        # Monitor selection
        monitor_row = QHBoxLayout()
        monitor_row.addWidget(QLabel("Monitors:"))
        self.monitor_combo = QComboBox()
        self.monitor_combo.addItems([
            "All Monitors",
            "Primary Monitor Only",
            "Monitor 1",
            "Monitor 2",
            "Monitor 3",
            "Monitor 4"
        ])
        self.monitor_combo.currentTextChanged.connect(self._save_settings)
        monitor_row.addWidget(self.monitor_combo)
        monitor_row.addStretch()
        monitor_layout.addLayout(monitor_row)
        
        # Same image toggle
        self.same_image_check = QCheckBox("Show same image on all monitors")
        self.same_image_check.setChecked(True)
        self.same_image_check.stateChanged.connect(self._save_settings)
        monitor_layout.addWidget(self.same_image_check)
        
        layout.addWidget(monitor_group)
        
        # Display mode group
        mode_group = QGroupBox("Display Mode")
        mode_layout = QVBoxLayout(mode_group)
        
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Fill - Scale to fill screen (crop if needed)",
            "Fit - Scale to fit screen (show all, may have bars)",
            "Shrink - Only shrink large images (never enlarge)"
        ])
        self.mode_combo.currentIndexChanged.connect(self._save_settings)
        mode_row.addWidget(self.mode_combo, 1)
        mode_layout.addLayout(mode_row)
        
        layout.addWidget(mode_group)
        
        # Timing group
        timing_group = QGroupBox("Image Timing")
        timing_layout = QVBoxLayout(timing_group)
        
        # Rotation interval
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Change image every:"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 3600)
        self.interval_spin.setSingleStep(1)
        self.interval_spin.setSuffix(" seconds")
        self.interval_spin.setValue(10)
        self.interval_spin.valueChanged.connect(self._save_settings)
        interval_row.addWidget(self.interval_spin)
        interval_row.addStretch()
        timing_layout.addLayout(interval_row)
        
        # Shuffle toggle
        self.shuffle_check = QCheckBox("Shuffle images (random order)")
        self.shuffle_check.setChecked(True)
        self.shuffle_check.stateChanged.connect(self._save_settings)
        timing_layout.addWidget(self.shuffle_check)
        
        layout.addWidget(timing_group)
        
        # Image quality group
        quality_group = QGroupBox("Image Quality")
        quality_layout = QVBoxLayout(quality_group)
        
        # Quality explanation
        quality_label = QLabel(
            "High quality scaling uses Lanczos resampling for better image quality,\n"
            "especially when downscaling images. Disable if you experience performance issues."
        )
        quality_label.setWordWrap(True)
        quality_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        quality_layout.addWidget(quality_label)
        
        self.quality_check = QCheckBox("Use high quality image scaling (Lanczos)")
        self.quality_check.setChecked(True)
        self.quality_check.stateChanged.connect(self._save_settings)
        quality_layout.addWidget(self.quality_check)
        
        self.sharpen_check = QCheckBox("Apply sharpening filter when downscaling")
        self.sharpen_check.setChecked(False)
        self.sharpen_check.stateChanged.connect(self._save_settings)
        quality_layout.addWidget(self.sharpen_check)
        
        layout.addWidget(quality_group)
        
        # Pan and scan group
        pan_group = QGroupBox("Pan and Scan")
        pan_layout = QVBoxLayout(pan_group)
        
        # Pan and scan explanation
        pan_label = QLabel(
            "Adds subtle movement to static images. The image will be larger than the display\n"
            "and drift slowly in random directions, creating a dynamic effect."
        )
        pan_label.setWordWrap(True)
        pan_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        pan_layout.addWidget(pan_label)
        
        self.pan_check = QCheckBox("Enable pan and scan effect")
        self.pan_check.setChecked(False)
        self.pan_check.stateChanged.connect(self._save_settings)
        pan_layout.addWidget(self.pan_check)
        
        # Speed settings
        speed_row = QHBoxLayout()
        self.pan_auto_check = QCheckBox("Auto speed (based on transition interval)")
        self.pan_auto_check.setChecked(True)
        self.pan_auto_check.stateChanged.connect(self._on_pan_auto_changed)
        speed_row.addWidget(self.pan_auto_check)
        pan_layout.addLayout(speed_row)
        
        # Manual speed
        manual_speed_row = QHBoxLayout()
        manual_speed_row.addWidget(QLabel("Manual speed:"))
        self.pan_speed_spin = QSpinBox()
        self.pan_speed_spin.setRange(1, 50)
        self.pan_speed_spin.setSingleStep(1)
        self.pan_speed_spin.setSuffix(" px/s")
        self.pan_speed_spin.setValue(5)
        self.pan_speed_spin.setEnabled(False)  # Disabled by default (auto mode)
        self.pan_speed_spin.valueChanged.connect(self._save_settings)
        manual_speed_row.addWidget(self.pan_speed_spin)
        manual_speed_row.addStretch()
        pan_layout.addLayout(manual_speed_row)
        
        layout.addWidget(pan_group)
        
        # Add stretch at bottom
        layout.addStretch()
        
        # Set scroll area widget and add to main layout
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def _load_settings(self) -> None:
        """Load settings from settings manager."""
        # Block signals during load to prevent triggering saves
        self.monitor_combo.blockSignals(True)
        self.same_image_check.blockSignals(True)
        self.mode_combo.blockSignals(True)
        self.interval_spin.blockSignals(True)
        self.shuffle_check.blockSignals(True)
        self.quality_check.blockSignals(True)
        self.sharpen_check.blockSignals(True)
        self.pan_check.blockSignals(True)
        self.pan_auto_check.blockSignals(True)
        self.pan_speed_spin.blockSignals(True)
        
        try:
            # Monitor selection
            monitor_setting = self._settings.get('display.monitor_selection', 'all')
            if monitor_setting == 'all':
                self.monitor_combo.setCurrentText("All Monitors")
            elif monitor_setting == 'primary':
                self.monitor_combo.setCurrentText("Primary Monitor Only")
            elif monitor_setting.startswith('monitor_'):
                monitor_num = monitor_setting.split('_')[1]
                self.monitor_combo.setCurrentText(f"Monitor {monitor_num}")
            
            # Same image toggle
            same_image = self._settings.get('display.same_image_all_monitors', True)
            # Convert to bool (settings may return string "true"/"false")
            if isinstance(same_image, str):
                same_image = same_image.lower() == 'true'
            self.same_image_check.setChecked(same_image)
            
            # Display mode
            mode = self._settings.get('display.mode', 'fill')
            if mode == 'fill':
                self.mode_combo.setCurrentIndex(0)
            elif mode == 'fit':
                self.mode_combo.setCurrentIndex(1)
            elif mode == 'shrink':
                self.mode_combo.setCurrentIndex(2)
            
            # Timing
            interval = self._settings.get('timing.interval', 10)
            self.interval_spin.setValue(int(interval))
            
            shuffle = self._settings.get('queue.shuffle', True)
            if isinstance(shuffle, str):
                shuffle = shuffle.lower() == 'true'
            self.shuffle_check.setChecked(shuffle)
            
            # Quality
            use_lanczos = self._settings.get('display.use_lanczos', True)
            if isinstance(use_lanczos, str):
                use_lanczos = use_lanczos.lower() == 'true'
            self.quality_check.setChecked(use_lanczos)
            
            sharpen = self._settings.get('display.sharpen_downscale', False)
            if isinstance(sharpen, str):
                sharpen = sharpen.lower() == 'true'
            self.sharpen_check.setChecked(sharpen)
            
            # Pan and scan
            pan_enabled = self._settings.get('display.pan_and_scan', False)
            if isinstance(pan_enabled, str):
                pan_enabled = pan_enabled.lower() == 'true'
            self.pan_check.setChecked(pan_enabled)
            
            pan_auto = self._settings.get('display.pan_auto_speed', True)
            if isinstance(pan_auto, str):
                pan_auto = pan_auto.lower() == 'true'
            self.pan_auto_check.setChecked(pan_auto)
            
            pan_speed = self._settings.get('display.pan_speed', 3.0)
            self.pan_speed_spin.setValue(int(pan_speed))
            self.pan_speed_spin.setEnabled(not pan_auto)
            
            logger.debug(f"Loaded display settings: use_lanczos={use_lanczos}, sharpen={sharpen}, pan={pan_enabled}")
        finally:
            # Re-enable signals
            self.monitor_combo.blockSignals(False)
            self.same_image_check.blockSignals(False)
            self.mode_combo.blockSignals(False)
            self.interval_spin.blockSignals(False)
            self.shuffle_check.blockSignals(False)
            self.quality_check.blockSignals(False)
            self.sharpen_check.blockSignals(False)
            self.pan_check.blockSignals(False)
            self.pan_auto_check.blockSignals(False)
            self.pan_speed_spin.blockSignals(False)
    
    def _save_settings(self) -> None:
        """Save current settings to settings manager."""
        # Monitor selection
        monitor_text = self.monitor_combo.currentText()
        if monitor_text == "All Monitors":
            monitor_setting = 'all'
        elif monitor_text == "Primary Monitor Only":
            monitor_setting = 'primary'
        elif monitor_text.startswith("Monitor "):
            monitor_num = monitor_text.split(" ")[1]
            monitor_setting = f'monitor_{monitor_num}'
        else:
            monitor_setting = 'all'
        
        self._settings.set('display.monitor_selection', monitor_setting)
        
        # Same image toggle
        self._settings.set('display.same_image_all_monitors', self.same_image_check.isChecked())
        
        # Display mode
        mode_index = self.mode_combo.currentIndex()
        mode_map = {0: 'fill', 1: 'fit', 2: 'shrink'}
        self._settings.set('display.mode', mode_map.get(mode_index, 'fill'))
        
        # Timing
        self._settings.set('timing.interval', self.interval_spin.value())
        self._settings.set('queue.shuffle', self.shuffle_check.isChecked())
        
        # Quality
        use_lanczos = self.quality_check.isChecked()
        sharpen = self.sharpen_check.isChecked()
        self._settings.set('display.use_lanczos', use_lanczos)
        self._settings.set('display.sharpen_downscale', sharpen)
        
        # Pan and scan
        self._settings.set('display.pan_and_scan', self.pan_check.isChecked())
        self._settings.set('display.pan_auto_speed', self.pan_auto_check.isChecked())
        self._settings.set('display.pan_speed', self.pan_speed_spin.value())
        
        self._settings.save()
        self.display_changed.emit()
        
        logger.info(f"Saved display settings: mode={mode_map.get(mode_index, 'fill')}, "
                   f"use_lanczos={use_lanczos}, sharpen={sharpen}, "
                   f"same_image={self.same_image_check.isChecked()}, "
                   f"pan_and_scan={self.pan_check.isChecked()}")
    
    def _on_pan_auto_changed(self) -> None:
        """Handle pan auto speed checkbox change."""
        is_auto = self.pan_auto_check.isChecked()
        self.pan_speed_spin.setEnabled(not is_auto)
        self._save_settings()
