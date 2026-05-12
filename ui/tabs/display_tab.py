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
    QWidget, QVBoxLayout, QLabel,
    QSpinBox, QGroupBox, QCheckBox, QScrollArea, QComboBox
)
from PySide6.QtCore import Signal, Qt

from core.settings.settings_manager import SettingsManager
from core.logging.logger import get_logger
from ui.tabs.shared_styles import (
    SPINBOX_STYLE,
    CIRCLE_CHECKBOX_STYLE,
    COMBOBOX_STYLE,
    PAGE_TITLE_STYLE,
    create_inline_label,
    add_aligned_row,
    style_group_box,
)
from ui.widgets import StyledComboBox
from utils.monitors import get_screen_count

logger = get_logger(__name__)


class DisplayTab(QWidget):
    """Display configuration tab."""
    
    # Signals
    display_changed = Signal()
    _LABEL_WIDTH = 160
    
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
        from ui.tabs.shared_styles import SCROLL_AREA_STYLE
        scroll.setStyleSheet(SCROLL_AREA_STYLE)

        # Create content widget
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("Display Settings")
        title.setStyleSheet(PAGE_TITLE_STYLE)
        layout.addWidget(title)
        
        # Monitor selection group
        monitor_group = QGroupBox("Monitor Configuration")
        style_group_box(monitor_group)
        monitor_layout = QVBoxLayout(monitor_group)
        monitor_layout.setContentsMargins(0, 12, 0, 0)
        monitor_layout.setSpacing(12)

        # Show On section (per-monitor checkboxes)
        show_row, _ = add_aligned_row(
            monitor_layout,
            "Show screensaver on:",
            label_width=self._LABEL_WIDTH,
        )
        self.show_all_check = QCheckBox("All")
        self.show_all_check.setProperty("circleIndicator", True)
        self.monitor_checks: List[QCheckBox] = [
            QCheckBox("Monitor 1"),
            QCheckBox("Monitor 2"),
            QCheckBox("Monitor 3"),
            QCheckBox("Monitor 4"),
        ]
        self.show_all_check.stateChanged.connect(self._on_show_on_changed)
        show_row.addWidget(self.show_all_check)
        for cb in self.monitor_checks:
            cb.setProperty("circleIndicator", True)
            cb.stateChanged.connect(self._on_show_on_changed)
            show_row.addWidget(cb)
        show_row.addSpacing(12)
        show_row.addStretch()

        # Same image toggle
        same_image_row, _ = add_aligned_row(
            monitor_layout,
            "",
            label_width=self._LABEL_WIDTH,
            wrap=False,
        )
        self.same_image_check = QCheckBox("Show Same Image on All Monitors")
        self.same_image_check.setProperty("circleIndicator", True)
        self.same_image_check.setChecked(True)
        self.same_image_check.stateChanged.connect(self._save_settings)
        same_image_row.addWidget(self.same_image_check)
        same_image_row.addStretch()
        
        layout.addWidget(monitor_group)
        
        # Display mode group
        mode_group = QGroupBox("Display Mode")
        style_group_box(mode_group)
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setContentsMargins(0, 12, 0, 0)
        mode_layout.setSpacing(12)
        
        mode_row, _ = add_aligned_row(
            mode_layout,
            "Mode:",
            label_width=self._LABEL_WIDTH,
        )
        self.mode_combo = StyledComboBox(size_variant="hero")
        self.mode_combo.addItems([
            "Fill — Crop to fill",
            "Fit — Show all (may letterbox)",
            "Shrink — Never enlarge"
        ])
        self.mode_combo.currentIndexChanged.connect(self._save_settings)
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch()
        
        layout.addWidget(mode_group)
        
        # Timing group
        timing_group = QGroupBox("Image Timing")
        style_group_box(timing_group)
        timing_layout = QVBoxLayout(timing_group)
        timing_layout.setContentsMargins(0, 12, 0, 0)
        timing_layout.setSpacing(12)
        
        # Rotation interval
        interval_row, _ = add_aligned_row(
            timing_layout,
            "Change image every:",
            label_width=self._LABEL_WIDTH,
        )
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 3600)
        self.interval_spin.setSingleStep(1)
        self.interval_spin.setAccelerated(True)
        self.interval_spin.setSuffix("")
        self.interval_spin.setValue(10)
        self.interval_spin.valueChanged.connect(self._save_settings)
        self.interval_spin.setFixedWidth(140)
        interval_row.addWidget(self.interval_spin)
        interval_row.addWidget(create_inline_label("seconds"))
        interval_row.addStretch()
        
        # Shuffle toggle
        shuffle_row, _ = add_aligned_row(
            timing_layout,
            "",
            label_width=self._LABEL_WIDTH,
            wrap=False,
        )
        self.shuffle_check = QCheckBox("Shuffle Images (Random Order)")
        self.shuffle_check.setProperty("circleIndicator", True)
        self.shuffle_check.setChecked(True)
        self.shuffle_check.stateChanged.connect(self._save_settings)
        shuffle_row.addWidget(self.shuffle_check)
        shuffle_row.addStretch()
        
        layout.addWidget(timing_group)
        
        # Image quality group
        quality_group = QGroupBox("Image Quality")
        style_group_box(quality_group)
        quality_layout = QVBoxLayout(quality_group)
        quality_layout.setContentsMargins(0, 12, 0, 0)
        quality_layout.setSpacing(12)
        
        lanczos_row, _ = add_aligned_row(
            quality_layout,
            "",
            label_width=self._LABEL_WIDTH,
            wrap=False,
        )
        self.lanczos_check = QCheckBox("Use Lanczos Scaling (Higher Quality, More CPU)")
        self.lanczos_check.setProperty("circleIndicator", True)
        self.lanczos_check.setChecked(True)
        self.lanczos_check.setToolTip(
            "Lanczos provides better image quality when scaling, especially for downscaling. "
            "Disable if experiencing performance issues during transitions."
        )
        self.lanczos_check.stateChanged.connect(self._save_settings)
        lanczos_row.addWidget(self.lanczos_check)
        lanczos_row.addStretch()
        
        sharpen_row, _ = add_aligned_row(
            quality_layout,
            "",
            label_width=self._LABEL_WIDTH,
            wrap=False,
        )
        self.sharpen_check = QCheckBox("Apply Sharpening Filter When Downscaling")
        self.sharpen_check.setProperty("circleIndicator", True)
        self.sharpen_check.setChecked(False)
        self.sharpen_check.stateChanged.connect(self._save_settings)
        sharpen_row.addWidget(self.sharpen_check)
        sharpen_row.addStretch()
        
        layout.addWidget(quality_group)
        
        # Pan and Scan has been removed in v1.2; no dedicated UI group remains.

        # Interaction group
        input_group = QGroupBox("Interaction")
        style_group_box(input_group)
        input_layout = QVBoxLayout(input_group)
        input_layout.setContentsMargins(0, 12, 0, 0)
        input_layout.setSpacing(12)
        interaction_mode_row, _ = add_aligned_row(
            input_layout,
            "",
            label_width=self._LABEL_WIDTH,
            wrap=False,
        )
        self.interaction_mode_check = QCheckBox("Interaction Mode (ESC Only)")
        self.interaction_mode_check.setProperty("circleIndicator", True)
        self.interaction_mode_check.setToolTip(
            "Keeps the screensaver active during simple mouse movement or clicks so you can interact with widgets until you press Escape."
        )
        self.interaction_mode_check.setChecked(False)
        self.interaction_mode_check.stateChanged.connect(self._save_settings)
        interaction_mode_row.addWidget(self.interaction_mode_check)
        interaction_mode_row.addStretch()

        # Cursor Halo Shape
        halo_row, _ = add_aligned_row(
            input_layout,
            "Cursor Halo Shape:",
            label_width=self._LABEL_WIDTH,
        )
        self.halo_shape_combo = StyledComboBox()
        self.halo_shape_combo.setFixedWidth(192)
        self.halo_shape_combo.setFixedHeight(42)
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
        self.halo_shape_combo.setToolTip("Visual shape of the cursor halo in Interaction / Ctrl-Held Mode.")
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

        self.setStyleSheet(
            self.styleSheet()
            + SPINBOX_STYLE
            + CIRCLE_CHECKBOX_STYLE
            + COMBOBOX_STYLE
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
        self.lanczos_check.blockSignals(True)
        self.sharpen_check.blockSignals(True)
        # Block input toggles
        self.interaction_mode_check.blockSignals(True)
        
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

            # Interaction Mode
            interaction_mode_raw = self._settings.get('input.interaction_mode', False)
            interaction_mode = SettingsManager.to_bool(interaction_mode_raw, False)
            self.interaction_mode_check.setChecked(interaction_mode)

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

            # Renderer backend — always OpenGL, normalize legacy values
            backend_mode_raw = self._settings.get('display.render_backend_mode', 'opengl')
            backend_mode = str(backend_mode_raw).lower()
            if backend_mode != 'opengl':
                logger.info("[DISPLAY] Legacy backend '%s' detected; normalizing to OpenGL", backend_mode)
                self._settings.set('display.render_backend_mode', 'opengl')
                self._settings.set('display.hw_accel', True)

            logger.debug(f"Loaded display settings: lanczos={lanczos}, sharpen={sharpen}")
        finally:
            # Re-enable signals
            self.same_image_check.blockSignals(False)
            self.mode_combo.blockSignals(False)
            self.interval_spin.blockSignals(False)
            self.shuffle_check.blockSignals(False)
            self.lanczos_check.blockSignals(False)
            self.sharpen_check.blockSignals(False)
            self.interaction_mode_check.blockSignals(False)
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

        # Interaction
        self._settings.set('input.interaction_mode', self.interaction_mode_check.isChecked())

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

        # Renderer backend — always OpenGL
        self._settings.set('display.render_backend_mode', 'opengl')
        self._settings.set('display.hw_accel', True)

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
