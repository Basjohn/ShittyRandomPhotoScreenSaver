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
from ui.tabs.shared_styles import SPINBOX_STYLE

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
        
        # Shared alignment helper (fixed-width label column)
        LABEL_WIDTH = 150

        def _aligned_row(parent_layout: QVBoxLayout, label_text: str) -> QHBoxLayout:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            label = QLabel(label_text)
            label.setFixedWidth(LABEL_WIDTH)
            row.addWidget(label)
            content = QHBoxLayout()
            content.setContentsMargins(0, 0, 0, 0)
            content.setSpacing(8)
            row.addLayout(content, 1)
            parent_layout.addLayout(row)
            return content

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
        monitor_layout.setSpacing(6)

        # Show On section (per-monitor checkboxes)
        show_row = _aligned_row(monitor_layout, "Show screensaver on:")
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

        # Same image toggle
        same_image_row = _aligned_row(monitor_layout, "")
        self.same_image_check = QCheckBox("Show same image on all monitors")
        self.same_image_check.setChecked(True)
        self.same_image_check.stateChanged.connect(self._save_settings)
        same_image_row.addWidget(self.same_image_check)
        same_image_row.addStretch()
        
        layout.addWidget(monitor_group)
        
        # Display mode group
        mode_group = QGroupBox("Display Mode")
        mode_layout = QVBoxLayout(mode_group)
        
        mode_row = _aligned_row(mode_layout, "Mode:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Fill - Scale to fill screen (crop if needed)",
            "Fit - Scale to fit screen (show all, may have bars)",
            "Shrink - Only shrink large images (never enlarge)"
        ])
        self.mode_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.mode_combo.currentIndexChanged.connect(self._save_settings)
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch()
        
        layout.addWidget(mode_group)
        
        # Timing group
        timing_group = QGroupBox("Image Timing")
        timing_layout = QVBoxLayout(timing_group)
        
        # Rotation interval
        interval_row = _aligned_row(timing_layout, "Change image every:")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 3600)
        self.interval_spin.setSingleStep(1)
        self.interval_spin.setAccelerated(True)
        self.interval_spin.setSuffix(" seconds")
        self.interval_spin.setValue(10)
        self.interval_spin.valueChanged.connect(self._save_settings)
        self.interval_spin.setFixedWidth(140)
        interval_row.addWidget(self.interval_spin)
        interval_row.addStretch()
        
        # Shuffle toggle
        shuffle_row = _aligned_row(timing_layout, "")
        self.shuffle_check = QCheckBox("Shuffle images (random order)")
        self.shuffle_check.setChecked(True)
        self.shuffle_check.stateChanged.connect(self._save_settings)
        shuffle_row.addWidget(self.shuffle_check)
        shuffle_row.addStretch()
        
        layout.addWidget(timing_group)
        
        # Image quality group
        quality_group = QGroupBox("Image Quality")
        quality_layout = QVBoxLayout(quality_group)
        
        lanczos_row = _aligned_row(quality_layout, "")
        self.lanczos_check = QCheckBox("Use Lanczos scaling (higher quality, more CPU)")
        self.lanczos_check.setChecked(True)
        self.lanczos_check.setToolTip(
            "Lanczos provides better image quality when scaling, especially for downscaling. "
            "Disable if experiencing performance issues during transitions."
        )
        self.lanczos_check.stateChanged.connect(self._save_settings)
        lanczos_row.addWidget(self.lanczos_check)
        lanczos_row.addStretch()
        
        sharpen_row = _aligned_row(quality_layout, "")
        self.sharpen_check = QCheckBox("Apply sharpening filter when downscaling")
        self.sharpen_check.setChecked(False)
        self.sharpen_check.stateChanged.connect(self._save_settings)
        sharpen_row.addWidget(self.sharpen_check)
        sharpen_row.addStretch()
        
        layout.addWidget(quality_group)
        
        # Pan and Scan has been removed in v1.2; no dedicated UI group remains.

        # Renderer backend group
        backend_group = QGroupBox("Renderer Backend")
        backend_layout = QVBoxLayout(backend_group)

        backend_row = _aligned_row(backend_layout, "Preferred backend:")
        self.backend_combo = QComboBox()
        self.backend_combo.addItem("OpenGL (recommended)", userData="opengl")
        self.backend_combo.addItem("Software (fallback)", userData="software")
        self.backend_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.backend_combo.currentIndexChanged.connect(self._save_settings)
        backend_row.addWidget(self.backend_combo)
        backend_row.addStretch()

        backend_hint = QLabel(
            "OpenGL is the primary renderer. If it fails during startup, the software fallback engages automatically."
        )
        backend_hint.setWordWrap(True)
        backend_hint.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        backend_layout.addWidget(backend_hint)

        layout.addWidget(backend_group)
        # Input & Exit group
        input_group = QGroupBox("Input && Exit")
        input_layout = QVBoxLayout(input_group)
        hard_exit_row = _aligned_row(input_layout, "")
        self.hard_exit_check = QCheckBox("Hard Exit (ESC only)")
        self.hard_exit_check.setToolTip(
            "Makes the screensaver only close if you press escape and no longer for simple mouse movement"
        )
        self.hard_exit_check.setChecked(False)
        self.hard_exit_check.stateChanged.connect(self._save_settings)
        hard_exit_row.addWidget(self.hard_exit_check)
        hard_exit_row.addStretch()

        # Cursor Halo Shape
        halo_row = _aligned_row(input_layout, "Cursor Halo Shape:")
        self.halo_shape_combo = QComboBox()
        self.halo_shape_combo.addItems(
            [
                "Circle",
                "Ring",
                "Crosshair",
                "Diamond",
                "Dot",
                "Cursor Pointer (Light)",
                "Cursor Pointer (Dark)",
            ]
        )
        self.halo_shape_combo.setToolTip("Visual shape of the cursor halo in Hard Exit / Ctrl-click mode.")
        self.halo_shape_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.halo_shape_combo.currentIndexChanged.connect(self._save_settings)
        halo_row.addWidget(self.halo_shape_combo)
        halo_row.addStretch()
        
        layout.addWidget(input_group)
        
        # Add stretch at bottom
        layout.addStretch()
        
        # Set scroll area widget and add to main layout
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        self.setStyleSheet(self.styleSheet() + SPINBOX_STYLE)
    
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
        self.lanczos_check.blockSignals(True)
        self.sharpen_check.blockSignals(True)
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
            
            # Quality (Lanczos and sharpen)
            lanczos_raw = self._settings.get('display.use_lanczos', True)
            lanczos = SettingsManager.to_bool(lanczos_raw, True)
            self.lanczos_check.setChecked(lanczos)
            
            sharpen_raw = self._settings.get('display.sharpen_downscale', False)
            sharpen = SettingsManager.to_bool(sharpen_raw, False)
            self.sharpen_check.setChecked(sharpen)

            # Input / Hard Exit
            hard_exit_raw = self._settings.get('input.hard_exit', False)
            hard_exit = SettingsManager.to_bool(hard_exit_raw, False)
            self.hard_exit_check.setChecked(hard_exit)

            # Cursor Halo Shape
            halo_shape = str(self._settings.get('input.halo_shape', 'circle')).lower()
            shape_map = {
                'circle': 0,
                'ring': 1,
                'crosshair': 2,
                'diamond': 3,
                'dot': 4,
                'cursor_light': 5,
                'cursor_dark': 6,
            }
            self.halo_shape_combo.blockSignals(True)
            self.halo_shape_combo.setCurrentIndex(shape_map.get(halo_shape, 0))
            self.halo_shape_combo.blockSignals(False)

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

            logger.debug(f"Loaded display settings: lanczos={lanczos}, sharpen={sharpen}")
        finally:
            # Re-enable signals
            self.same_image_check.blockSignals(False)
            self.mode_combo.blockSignals(False)
            self.interval_spin.blockSignals(False)
            self.shuffle_check.blockSignals(False)
            self.lanczos_check.blockSignals(False)
            self.sharpen_check.blockSignals(False)
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
        
        # Quality (Lanczos and sharpen)
        lanczos = self.lanczos_check.isChecked()
        self._settings.set('display.use_lanczos', lanczos)
        
        sharpen = self.sharpen_check.isChecked()
        self._settings.set('display.sharpen_downscale', sharpen)

        # Input / Exit
        self._settings.set('input.hard_exit', self.hard_exit_check.isChecked())

        # Cursor Halo Shape
        shape_names = [
            'circle',
            'ring',
            'crosshair',
            'diamond',
            'dot',
            'cursor_light',
            'cursor_dark',
        ]
        halo_idx = self.halo_shape_combo.currentIndex()
        self._settings.set('input.halo_shape', shape_names[halo_idx] if 0 <= halo_idx < len(shape_names) else 'circle')

        # Renderer backend
        backend_value = self.backend_combo.currentData() or 'opengl'
        self._settings.set('display.render_backend_mode', backend_value)
        self._settings.set('display.hw_accel', backend_value == 'opengl')

        self._settings.save()
        self.display_changed.emit()

        logger.info(
            f"Saved display settings: mode={mode_map.get(mode_index, 'fill')}, "
            f"lanczos={lanczos}, sharpen={sharpen}, "
            f"same_image={self.same_image_check.isChecked()}"
        )

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
