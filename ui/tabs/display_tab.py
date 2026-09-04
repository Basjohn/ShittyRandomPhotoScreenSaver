"""
Display configuration tab for settings dialog.

Allows users to configure display settings:
- Monitor selection (primary, all, specific)
- Display mode (Fill, Fit, Shrink)
- Same image on all monitors
- Image rotation interval
- Shuffle mode
"""
import weakref
from typing import Optional, List

import shiboken6
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QSpinBox, QGroupBox, QCheckBox, QScrollArea, QComboBox,
    QButtonGroup, QPushButton,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor

from core.settings.settings_manager import SettingsManager
from core.settings.models import InputSettings
from core.logging.logger import get_logger
from ui.tabs import shared_styles
from ui.tabs.shared_styles import (
    create_inline_label,
    add_aligned_row,
    style_group_box,
)
from ui.flow_layout import FlowContainer
from ui.widgets import StyledComboBox
from ui.styled_popup import ColorSwatchButton
from ui.widget_glow_style import resolve_widget_glow_color
from ui.widget_theme_active import get_active_widget_theme, subscribe_widget_theme
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
        self._is_mc_profile = settings.get_application_name() == "Screensaver_MC"
        self._loading: bool = False
        self._widget_glow_color_override: Optional[List[int]] = None
        self._setup_ui()
        self._load_settings()
        self._bind_widget_glow_theme()

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
        """Build the Display tab and its pill-section navigation.

        ``SettingsDialog`` already owns DisplayTab construction at the
        top-level tab lifecycle (selected immediately when needed, otherwise
        eligible for the existing background hydration queue). The five Display
        sections below are deliberately built together once DisplayTab itself
        is constructed: they are all cheap QWidget controls, have no independent
        workers/timers, and the existing load/save contract is intentionally
        whole-tab atomic. Making these individual pages lazy would add
        partial-hydration/save hazards for no meaningful benefit.
        """
        scroll = QScrollArea(self)
        self._scroll_area = scroll
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet(shared_styles.SCROLL_AREA_STYLE)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Display Settings")
        shared_styles.apply_shared_label_style(title, "PAGE_TITLE_STYLE")
        layout.addWidget(title)

        # Reuse the existing semantic Settings sub-navigation tokens rather
        # than creating Display-specific theme roles. Current .srtheme files
        # therefore style these pills without a schema migration.
        nav = FlowContainer(h_spacing=8, v_spacing=8)
        self._section_group = QButtonGroup(self)
        self._section_group.setExclusive(True)
        self._section_buttons: list[QPushButton] = []

        section_specs = (
            ("monitors", "Monitors", self._build_monitor_section),
            ("display_mode", "Display Mode", self._build_display_mode_section),
            ("timing", "Timing", self._build_timing_section),
            ("quality", "Quality", self._build_quality_section),
            ("interaction", "Interaction", self._build_interaction_section),
        )
        self._section_keys = tuple(key for key, _label, _builder in section_specs)

        self._section_pages: list[QWidget] = []
        for index, (_key, label, builder) in enumerate(section_specs):
            button = QPushButton(label)
            button.setCheckable(True)
            shared_styles.bind_shared_styles(
                button,
                "WIDGET_NAV_PILL_STYLE",
                base_style="",
            )
            self._section_group.addButton(button, index)
            self._section_buttons.append(button)
            nav.addWidget(button)

            page = builder()
            self._section_pages.append(page)

        layout.addWidget(nav)
        for page in self._section_pages:
            layout.addWidget(page)
        layout.addStretch()

        self._section_group.idClicked.connect(self._on_section_changed)
        self._section_buttons[0].setChecked(True)
        self._on_section_changed(0, reset_scroll=False)

        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        shared_styles.bind_shared_styles(
            self,
            "SPINBOX_STYLE",
            "CIRCLE_CHECKBOX_STYLE",
            "COMBOBOX_STYLE",
        )

    def _on_section_changed(self, index: int, *, reset_scroll: bool = True) -> None:
        """Show exactly one Display section without rebuilding its controls."""

        if not 0 <= index < len(self._section_pages):
            return
        for page_index, page in enumerate(self._section_pages):
            page.setVisible(page_index == index)
        self._active_section_index = index
        if reset_scroll and hasattr(self, "_scroll_area"):
            self._scroll_area.verticalScrollBar().setValue(0)

    def get_view_state(self) -> dict[str, str]:
        """Return the selected Display subsection for dialog-level state caching."""

        index = getattr(self, "_active_section_index", 0)
        if 0 <= index < len(getattr(self, "_section_keys", ())):
            return {"section": self._section_keys[index]}
        return {"section": "monitors"}

    def restore_view_state(self, state: dict) -> None:
        """Restore a previously selected Display subsection when available."""

        if not isinstance(state, dict):
            return
        key = state.get("section")
        if not isinstance(key, str):
            return
        try:
            index = self._section_keys.index(key)
        except (AttributeError, ValueError):
            return
        button = self._section_group.button(index)
        if button is not None:
            button.setChecked(True)
        self._on_section_changed(index, reset_scroll=False)

    @staticmethod
    def _new_section_group(title: str) -> tuple[QGroupBox, QVBoxLayout]:
        """Create one existing-style Display section group."""

        group = QGroupBox(title)
        style_group_box(group)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)
        return group, layout

    def _build_monitor_section(self) -> QWidget:
        group, layout = self._new_section_group("Monitor Configuration")

        show_row, _ = add_aligned_row(
            layout,
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

        same_image_row, _ = add_aligned_row(
            layout,
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

        return group

    def _build_display_mode_section(self) -> QWidget:
        group, layout = self._new_section_group("Display Mode")

        mode_row, _ = add_aligned_row(
            layout,
            "Mode:",
            label_width=self._LABEL_WIDTH,
        )
        self.mode_combo = StyledComboBox(size_variant="hero")
        self.mode_combo.addItems([
            "Fill — Crop to fill",
            "Fit — Show all (may letterbox)",
            "Shrink — Never enlarge",
        ])
        self.mode_combo.currentIndexChanged.connect(self._save_settings)
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch()

        return group

    def _build_timing_section(self) -> QWidget:
        group, layout = self._new_section_group("Image Timing")

        interval_row, _ = add_aligned_row(
            layout,
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

        shuffle_row, _ = add_aligned_row(
            layout,
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

        return group

    def _build_quality_section(self) -> QWidget:
        group, layout = self._new_section_group("Image Quality")

        lanczos_row, _ = add_aligned_row(
            layout,
            "",
            label_width=self._LABEL_WIDTH,
            wrap=False,
        )
        self.lanczos_check = QCheckBox(
            "Use Lanczos Scaling (Higher Quality, More CPU)"
        )
        self.lanczos_check.setProperty("circleIndicator", True)
        self.lanczos_check.setChecked(True)
        self.lanczos_check.setToolTip(
            "Lanczos provides better image quality when scaling, especially for "
            "downscaling. Disable if experiencing performance issues during transitions."
        )
        self.lanczos_check.stateChanged.connect(self._save_settings)
        lanczos_row.addWidget(self.lanczos_check)
        lanczos_row.addStretch()

        sharpen_row, _ = add_aligned_row(
            layout,
            "",
            label_width=self._LABEL_WIDTH,
            wrap=False,
        )
        self.sharpen_check = QCheckBox(
            "Apply Sharpening Filter When Downscaling"
        )
        self.sharpen_check.setProperty("circleIndicator", True)
        self.sharpen_check.setChecked(False)
        self.sharpen_check.stateChanged.connect(self._save_settings)
        sharpen_row.addWidget(self.sharpen_check)
        sharpen_row.addStretch()

        return group

    def _build_interaction_section(self) -> QWidget:
        group, layout = self._new_section_group("Interaction")

        interaction_mode_row, _ = add_aligned_row(
            layout,
            "",
            label_width=self._LABEL_WIDTH,
            wrap=False,
        )
        self.interaction_mode_check = QCheckBox("Interaction Mode (ESC Only)")
        self.interaction_mode_check.setProperty("circleIndicator", True)
        self.interaction_mode_check.setToolTip(
            "Keeps the screensaver active during simple mouse movement or clicks "
            "so you can interact with widgets until you press Escape."
        )
        self.interaction_mode_check.setChecked(False)
        if self._is_mc_profile:
            self.interaction_mode_check.setEnabled(False)
            self.interaction_mode_check.setToolTip(
                "Media Center builds keep Interaction Mode always enabled."
            )
        self.interaction_mode_check.stateChanged.connect(self._save_settings)
        interaction_mode_row.addWidget(self.interaction_mode_check)
        interaction_mode_row.addStretch()

        halo_row, _ = add_aligned_row(
            layout,
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
        self.halo_shape_combo.setToolTip(
            "Visual shape of the cursor halo in Interaction / Ctrl-Held Mode."
        )
        self.halo_shape_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self.halo_shape_combo.currentIndexChanged.connect(self._save_settings)
        halo_row.addWidget(self.halo_shape_combo)
        halo_row.addStretch()

        widget_glow_hover_row, _ = add_aligned_row(
            layout,
            "",
            label_width=self._LABEL_WIDTH,
            wrap=False,
        )
        self.widget_glow_on_hover_check = QCheckBox("Widget Glow on Hover")
        self.widget_glow_on_hover_check.setProperty("circleIndicator", True)
        self.widget_glow_on_hover_check.setToolTip(
            "Show a subtle glow while the pointer is over an ordinary widget."
        )
        self.widget_glow_on_hover_check.stateChanged.connect(self._save_settings)
        widget_glow_hover_row.addWidget(self.widget_glow_on_hover_check)
        widget_glow_hover_row.addStretch()

        widget_glow_click_row, _ = add_aligned_row(
            layout,
            "",
            label_width=self._LABEL_WIDTH,
            wrap=False,
        )
        self.widget_glow_on_click_check = QCheckBox("Widget Glow on Click")
        self.widget_glow_on_click_check.setProperty("circleIndicator", True)
        self.widget_glow_on_click_check.setToolTip(
            "Pulse a subtle glow when an ordinary widget receives a click."
        )
        self.widget_glow_on_click_check.stateChanged.connect(self._save_settings)
        widget_glow_click_row.addWidget(self.widget_glow_on_click_check)
        widget_glow_click_row.addStretch()

        widget_glow_color_row, _ = add_aligned_row(
            layout,
            "Widget Glow Color:",
            label_width=self._LABEL_WIDTH,
            wrap=False,
        )
        self.widget_glow_color_btn = ColorSwatchButton(
            title="Choose Widget Glow Color",
            show_alpha=True,
        )
        self.widget_glow_color_btn.setToolTip(
            "Shared RGBA colour used by hover and click widget glow feedback. "
            "Use Theme follows the active Widget Theme card border."
        )
        self.widget_glow_color_btn.color_changed.connect(
            self._on_widget_glow_color_changed
        )
        widget_glow_color_row.addWidget(self.widget_glow_color_btn)
        self.widget_glow_use_theme_btn = QPushButton("Use Theme")
        self.widget_glow_use_theme_btn.setFixedHeight(30)
        self.widget_glow_use_theme_btn.setToolTip(
            "Clear the explicit glow colour and inherit the active Widget Theme card border."
        )
        shared_styles.bind_shared_styles(
            self.widget_glow_use_theme_btn,
            "GHOST_ACTION_BUTTON_STYLE",
            base_style="",
        )
        self.widget_glow_use_theme_btn.clicked.connect(
            self._use_widget_theme_glow_color
        )
        widget_glow_color_row.addWidget(self.widget_glow_use_theme_btn)
        widget_glow_color_row.addStretch()

        return group

    def _refresh_widget_glow_swatch(self, theme=None) -> None:
        """Show the resolved glow colour without changing persistence."""

        color = resolve_widget_glow_color(
            self._widget_glow_color_override,
            theme if theme is not None else get_active_widget_theme(),
        )
        self.widget_glow_color_btn.set_color(QColor(*color))

    def _on_widget_glow_color_changed(self, color: QColor) -> None:
        """Capture a swatch edit as an explicit persisted RGBA override."""

        if getattr(self, "_loading", False):
            return
        self._widget_glow_color_override = list(color.getRgb())
        self._save_settings()

    def _use_widget_theme_glow_color(self) -> None:
        """Clear the explicit override and persist the Use Theme choice."""

        if getattr(self, "_loading", False):
            return
        self._widget_glow_color_override = None
        self._refresh_widget_glow_swatch()
        self._save_settings()

    def _bind_widget_glow_theme(self) -> None:
        """Refresh this Settings swatch from Widget Theme publishes."""

        if getattr(self, "_widget_glow_theme_unsubscribe", None) is not None:
            return
        tab_ref = weakref.ref(self)

        def _theme_changed(theme) -> None:
            owner = tab_ref()
            if owner is None or not shiboken6.isValid(owner):
                return
            owner._refresh_widget_glow_swatch(theme)

        unsubscribe = subscribe_widget_theme(
            _theme_changed,
            call_immediately=True,
        )
        self._widget_glow_theme_unsubscribe = unsubscribe

        # Capture only the subscription callback. The listener itself retains
        # the tab weakly, so theme lifetime cannot retain this Settings page.
        def _unsubscribe(_obj=None, callback=unsubscribe) -> None:
            callback()

        self.destroyed.connect(_unsubscribe)

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
        self.widget_glow_on_hover_check.blockSignals(True)
        self.widget_glow_on_click_check.blockSignals(True)
        
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
            interaction_mode = True if self._is_mc_profile else SettingsManager.to_bool(interaction_mode_raw, False)
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

            # Widget interaction glow
            input_options = InputSettings.from_settings(self._settings)
            self.widget_glow_on_hover_check.setChecked(
                input_options.widget_glow_on_hover
            )
            self.widget_glow_on_click_check.setChecked(
                input_options.widget_glow_on_click
            )
            self._widget_glow_color_override = (
                None
                if input_options.widget_glow_color is None
                else list(input_options.widget_glow_color)
            )
            self._refresh_widget_glow_swatch()

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
            self.widget_glow_on_hover_check.blockSignals(False)
            self.widget_glow_on_click_check.blockSignals(False)
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
        self._settings.set(
            'input.interaction_mode',
            True if self._is_mc_profile else self.interaction_mode_check.isChecked(),
        )

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

        # Widget interaction glow
        self._settings.set(
            'input.widget_glow_on_hover',
            self.widget_glow_on_hover_check.isChecked(),
        )
        self._settings.set(
            'input.widget_glow_on_click',
            self.widget_glow_on_click_check.isChecked(),
        )
        self._settings.set(
            'input.widget_glow_color',
            None
            if self._widget_glow_color_override is None
            else list(self._widget_glow_color_override),
        )

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
