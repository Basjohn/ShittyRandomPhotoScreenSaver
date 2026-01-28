"""
Display configuration tab for settings dialog.

Allows users to configure display settings:
- Monitor selection (primary, all, specific)
- Display mode (Fill, Fit, Shrink)
- Same image on all monitors
- Image rotation interval
- Shuffle mode
"""
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QGroupBox, QCheckBox, QScrollArea
)
from PySide6.QtCore import Signal, Qt

from core.settings.settings_manager import SettingsManager
from utils.monitors import get_screen_count
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
        self._loading: bool = False
        self._setup_ui()
        self._load_settings()
        
        logger.debug("DisplayTab created")
    
    def load_from_settings(self) -> None:
        """Reload all UI controls from settings manager (called after preset change)."""
        self._loading = True
        try:
            self._load_settings()
        finally:
            self._loading = False
        logger.debug("[DISPLAY_TAB] Reloaded from settings")
    
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

        # Show On section (per-monitor checkboxes)
        monitor_layout.addWidget(QLabel("Show screensaver on:"))

        show_row = QHBoxLayout()
        self.show_all_check = QCheckBox("All")
        self.monitor_checks: List[QCheckBox] = [
            QCheckBox("Monitor 1"),
            QCheckBox("Monitor 2"),
            QCheckBox("Monitor 3"),
            QCheckBox("Monitor 4"),
        ]
        self.show_all_check.stateChanged.connect(self._on_show_on_changed)
        show_row.addWidget(self.show_all_check)
        for cb in self.monitor_checks:
            cb.stateChanged.connect(self._on_show_on_changed)
            show_row.addWidget(cb)
        show_row.addStretch()
        monitor_layout.addLayout(show_row)

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
        
        # Pan and Scan has been removed in v1.2; no dedicated UI group remains.

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
        self.refresh_sync_check.stateChanged.connect(self._on_refresh_sync_toggled)
        perf_layout.addWidget(self.refresh_sync_check)

        self.refresh_adaptive_check = QCheckBox("Adaptive ratios (1× / 1⁄2 / 1⁄3)")
        self.refresh_adaptive_check.setChecked(True)
        self.refresh_adaptive_check.stateChanged.connect(self._save_settings)
        perf_layout.addWidget(self.refresh_adaptive_check)

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

        # Unified styling for +/- spin controls in this tab. This improves the
        # visual hit area of the buttons and keeps arrow glyphs aligned.
        self.setStyleSheet(
            self.styleSheet()
            + """
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
                border-top: 1px solid #3a3a3a;
                border-right: 1px solid #3a3a3a;
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
                border-right: 1px solid #3a3a3a;
                border-bottom: 1px solid #3a3a3a;
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
    
    def _load_settings(self) -> None:
        """Load settings from settings manager."""
        # Block signals during load to prevent triggering saves
        # Guard against re-entrant saves while loading
        self._loading = True

        # Block signals during load to prevent triggering saves
        self.same_image_check.blockSignals(True)
        self.mode_combo.blockSignals(True)
        self.interval_spin.blockSignals(True)
        self.shuffle_check.blockSignals(True)
        self.sharpen_check.blockSignals(True)
        # Also block performance toggles to avoid saving defaults while loading
        self.refresh_sync_check.blockSignals(True)
        self.refresh_adaptive_check.blockSignals(True)
        self.backend_combo.blockSignals(True)
        # Block input toggles
        self.hard_exit_check.blockSignals(True)
        
        try:
            # Monitor selection (new canonical: display.show_on_monitors)
            raw_show_on = self._settings.get('display.show_on_monitors', 'ALL')

            show_all = False
            selected_monitors: set[int] = set()
            if isinstance(raw_show_on, str):
                if raw_show_on.upper() == 'ALL':
                    show_all = True
                else:
                    # Attempt to parse stringified list, fall back to legacy setting
                    try:
                        import ast
                        parsed = ast.literal_eval(raw_show_on)
                        if isinstance(parsed, (list, tuple, set)):
                            selected_monitors = {int(x) for x in parsed}
                    except Exception as e:
                        logger.debug("[MISC] Exception suppressed: %s", e)
                        selected_monitors = set()
            elif isinstance(raw_show_on, (list, tuple, set)):
                try:
                    selected_monitors = {int(x) for x in raw_show_on}
                except Exception as e:
                    logger.debug("[MISC] Exception suppressed: %s", e)
                    selected_monitors = set()

            self.show_all_check.setChecked(show_all)

            # Apply selection to per-monitor checkboxes, respecting available screens
            screen_count = max(1, get_screen_count())
            for idx, cb in enumerate(self.monitor_checks, start=1):
                enabled = idx <= screen_count
                cb.setEnabled(enabled)
                if not enabled:
                    cb.setChecked(False)
                else:
                    if show_all or not selected_monitors:
                        cb.setChecked(True)
                    else:
                        cb.setChecked(idx in selected_monitors)
            
            # Same image toggle
            same_image = self._settings.get('display.same_image_all_monitors', False)
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
            
            # Timing – use canonical default (45s) when key is missing.
            interval = self._settings.get('timing.interval', 45)
            self.interval_spin.setValue(int(interval))
            
            shuffle_raw = self._settings.get('queue.shuffle', True)
            shuffle = SettingsManager.to_bool(shuffle_raw, True)
            self.shuffle_check.setChecked(shuffle)
            
            # Quality (Lanczos intentionally hidden/disabled; only sharpen exposed)
            sharpen_raw = self._settings.get('display.sharpen_downscale', False)
            sharpen = SettingsManager.to_bool(sharpen_raw, False)
            self.sharpen_check.setChecked(sharpen)
            
            # Refresh rate sync
            refresh_sync = self._settings.get_bool('display.refresh_sync', True)
            self.refresh_sync_check.setChecked(refresh_sync)

            refresh_adaptive = self._settings.get_bool('display.refresh_adaptive', True)
            self.refresh_adaptive_check.setChecked(refresh_adaptive)
            self._update_adaptive_checkbox_state()

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

            logger.debug(f"Loaded display settings: sharpen={sharpen}")
        finally:
            # Re-enable signals
            self.same_image_check.blockSignals(False)
            self.mode_combo.blockSignals(False)
            self.interval_spin.blockSignals(False)
            self.shuffle_check.blockSignals(False)
            self.sharpen_check.blockSignals(False)
            self.refresh_sync_check.blockSignals(False)
            self.refresh_adaptive_check.blockSignals(False)
            self.backend_combo.blockSignals(False)
            self.hard_exit_check.blockSignals(False)
            self._loading = False
    
    def _save_settings(self) -> None:
        """Save current settings to settings manager."""
        if getattr(self, "_loading", False):
            return
        # Monitor selection (canonical show_on_monitors + legacy shim)
        screen_count = max(1, get_screen_count())
        show_all = self.show_all_check.isChecked()

        selected: list[int] = []
        for idx, cb in enumerate(self.monitor_checks, start=1):
            if idx <= screen_count and cb.isEnabled() and cb.isChecked():
                selected.append(idx)

        if show_all or not selected:
            show_value = 'ALL'
        else:
            show_value = selected

        self._settings.set('display.show_on_monitors', show_value)
        
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
        
        # Performance
        self._settings.set('display.refresh_sync', self.refresh_sync_check.isChecked())
        self._settings.set('display.refresh_adaptive', self.refresh_adaptive_check.isChecked())

        # Input / Exit
        self._settings.set('input.hard_exit', self.hard_exit_check.isChecked())

        # Renderer backend
        backend_value = self.backend_combo.currentData() or 'opengl'
        self._settings.set('display.render_backend_mode', backend_value)
        self._settings.set('display.hw_accel', backend_value == 'opengl')

        self._settings.save()
        self.display_changed.emit()
        
        logger.info(
            f"Saved display settings: mode={mode_map.get(mode_index, 'fill')}, "
            f"sharpen={sharpen}, "
            f"same_image={self.same_image_check.isChecked()}"
        )

    def _on_refresh_sync_toggled(self) -> None:
        self._update_adaptive_checkbox_state()
        self._save_settings()

    def _update_adaptive_checkbox_state(self) -> None:
        enabled = self.refresh_sync_check.isChecked()
        self.refresh_adaptive_check.setEnabled(enabled)

    def _on_show_on_changed(self) -> None:
        """Handle changes to the monitor "Show On" checkboxes."""

        if getattr(self, "_loading", False):
            return

        sender = self.sender()

        # Update dependent checkboxes without triggering recursive saves.
        screen_count = max(1, get_screen_count())

        if sender is self.show_all_check:
            checked = self.show_all_check.isChecked()
            for idx, cb in enumerate(self.monitor_checks, start=1):
                if idx <= screen_count and cb.isEnabled():
                    cb.blockSignals(True)
                    cb.setChecked(checked)
                    cb.blockSignals(False)
        else:
            # A specific monitor checkbox changed; update the "All" checkbox
            # to reflect whether every enabled monitor is selected.
            all_enabled_checked = True
            for idx, cb in enumerate(self.monitor_checks, start=1):
                if idx <= screen_count and cb.isEnabled():
                    if not cb.isChecked():
                        all_enabled_checked = False
                        break

            self.show_all_check.blockSignals(True)
            self.show_all_check.setChecked(all_enabled_checked)
            self.show_all_check.blockSignals(False)

        self._save_settings()
