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
from PySide6.QtCore import Signal, Qt

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
        self.interval_spin.setAccelerated(True)
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
        self.pan_speed_spin.setAccelerated(True)
        self.pan_speed_spin.setSuffix(" px/s")
        self.pan_speed_spin.setValue(5)
        self.pan_speed_spin.setEnabled(False)  # Disabled by default (auto mode)
        self.pan_speed_spin.valueChanged.connect(self._save_settings)
        manual_speed_row.addWidget(self.pan_speed_spin)
        manual_speed_row.addStretch()
        pan_layout.addLayout(manual_speed_row)
        
        layout.addWidget(pan_group)

        # Renderer backend group
        backend_group = QGroupBox("Renderer Backend")
        backend_layout = QVBoxLayout(backend_group)

        backend_row = QHBoxLayout()
        backend_row.addWidget(QLabel("Preferred backend:"))
        self.backend_combo = QComboBox()
        self.backend_combo.addItem("OpenGL (recommended)", userData="opengl")
        self.backend_combo.addItem("Software (fallback)", userData="software")
        self.backend_combo.currentIndexChanged.connect(self._save_settings)
        backend_row.addWidget(self.backend_combo, 1)
        backend_layout.addLayout(backend_row)

        backend_hint = QLabel(
            "OpenGL is the primary renderer. If it fails during startup, the software fallback engages automatically."
        )
        backend_hint.setWordWrap(True)
        backend_hint.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        backend_layout.addWidget(backend_hint)

        layout.addWidget(backend_group)

        # Performance group
        perf_group = QGroupBox("Performance")
        perf_layout = QVBoxLayout(perf_group)

        self.refresh_sync_check = QCheckBox("Sync animations to display refresh rate")
        self.refresh_sync_check.setChecked(True)
        self.refresh_sync_check.stateChanged.connect(self._save_settings)
        perf_layout.addWidget(self.refresh_sync_check)

        layout.addWidget(perf_group)

        # Input & Exit group
        input_group = QGroupBox("Input && Exit")
        input_layout = QVBoxLayout(input_group)
        self.hard_exit_check = QCheckBox("Hard Exit (ESC only)")
        self.hard_exit_check.setToolTip(
            "Makes the screensaver only close if you press escape and no longer for simple mouse movement"
        )
        self.hard_exit_check.setChecked(False)
        self.hard_exit_check.stateChanged.connect(self._save_settings)
        input_layout.addWidget(self.hard_exit_check)
        layout.addWidget(input_group)
        
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
        self.sharpen_check.blockSignals(True)
        self.pan_check.blockSignals(True)
        self.pan_auto_check.blockSignals(True)
        self.pan_speed_spin.blockSignals(True)
        # Also block performance toggles to avoid saving defaults while loading
        self.refresh_sync_check.blockSignals(True)
        self.backend_combo.blockSignals(True)
        # Block input toggles
        self.hard_exit_check.blockSignals(True)
        
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
            
            shuffle_raw = self._settings.get('queue.shuffle', True)
            shuffle = SettingsManager.to_bool(shuffle_raw, True)
            self.shuffle_check.setChecked(shuffle)
            
            # Quality (Lanczos intentionally hidden/disabled; only sharpen exposed)
            sharpen_raw = self._settings.get('display.sharpen_downscale', False)
            sharpen = SettingsManager.to_bool(sharpen_raw, False)
            self.sharpen_check.setChecked(sharpen)
            
            # Pan and scan
            pan_enabled_raw = self._settings.get('display.pan_and_scan', False)
            pan_enabled = SettingsManager.to_bool(pan_enabled_raw, False)
            self.pan_check.setChecked(pan_enabled)
            
            pan_auto_raw = self._settings.get('display.pan_auto_speed', True)
            pan_auto = SettingsManager.to_bool(pan_auto_raw, True)
            self.pan_auto_check.setChecked(pan_auto)
            
            pan_speed = self._settings.get('display.pan_speed', 3.0)
            self.pan_speed_spin.setValue(int(pan_speed))
            self.pan_speed_spin.setEnabled(not pan_auto)
            
            # Refresh rate sync
            refresh_sync = self._settings.get_bool('display.refresh_sync', True)
            self.refresh_sync_check.setChecked(refresh_sync)

            # Input / Hard Exit
            hard_exit_raw = self._settings.get('input.hard_exit', False)
            hard_exit = SettingsManager.to_bool(hard_exit_raw, False)
            self.hard_exit_check.setChecked(hard_exit)

            # Renderer backend preferences
            backend_mode_raw = self._settings.get('display.render_backend_mode', 'opengl')
            backend_mode = str(backend_mode_raw).lower()
            if backend_mode == 'd3d11':
                logger.info("[DISPLAY] Legacy Direct3D setting detected; normalizing to OpenGL")
                backend_mode = 'opengl'
                self._settings.set('display.render_backend_mode', 'opengl')
            index = self.backend_combo.findData(backend_mode)
            if index == -1:
                index = 0
            self.backend_combo.setCurrentIndex(index)

            logger.debug(f"Loaded display settings: sharpen={sharpen}, pan={pan_enabled}")
        finally:
            # Re-enable signals
            self.monitor_combo.blockSignals(False)
            self.same_image_check.blockSignals(False)
            self.mode_combo.blockSignals(False)
            self.interval_spin.blockSignals(False)
            self.shuffle_check.blockSignals(False)
            self.sharpen_check.blockSignals(False)
            self.pan_check.blockSignals(False)
            self.pan_auto_check.blockSignals(False)
            self.pan_speed_spin.blockSignals(False)
            self.refresh_sync_check.blockSignals(False)
            self.backend_combo.blockSignals(False)
            self.hard_exit_check.blockSignals(False)
    
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
        
        # Quality (only sharpen is user-configurable)
        sharpen = self.sharpen_check.isChecked()
        self._settings.set('display.sharpen_downscale', sharpen)
        
        # Pan and scan
        self._settings.set('display.pan_and_scan', self.pan_check.isChecked())
        self._settings.set('display.pan_auto_speed', self.pan_auto_check.isChecked())
        self._settings.set('display.pan_speed', self.pan_speed_spin.value())
        
        # Performance
        self._settings.set('display.refresh_sync', self.refresh_sync_check.isChecked())

        # Input / Exit
        self._settings.set('input.hard_exit', self.hard_exit_check.isChecked())

        # Renderer backend
        backend_value = self.backend_combo.currentData() or 'opengl'
        self._settings.set('display.render_backend_mode', backend_value)
        self._settings.set('display.hw_accel', backend_value == 'opengl')

        self._settings.save()
        self.display_changed.emit()
        
        logger.info(f"Saved display settings: mode={mode_map.get(mode_index, 'fill')}, "
                   f"sharpen={sharpen}, "
                   f"same_image={self.same_image_check.isChecked()}, "
                   f"pan_and_scan={self.pan_check.isChecked()}")

        # Improve +/- button clarity and feedback on spin boxes (applies to this tab)
        self.setStyleSheet(
            self.styleSheet() + """
            QSpinBox, QDoubleSpinBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding-right: 28px; /* more space for larger buttons */
                min-height: 24px;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 24px;
                height: 12px;
                background: #2a2a2a;
                border-left: 1px solid #3a3a3a;
                border-bottom: 1px solid #3a3a3a;
                margin: 0px;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 24px;
                height: 12px;
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
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 6px solid #ffffff;
                margin-top: 2px;
            }
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #ffffff;
                margin-bottom: 2px;
            }
            """
        )
    
    def _on_pan_auto_changed(self) -> None:
        """Handle pan auto speed checkbox change."""
        is_auto = self.pan_auto_check.isChecked()
        self.pan_speed_spin.setEnabled(not is_auto)
        self._save_settings()
