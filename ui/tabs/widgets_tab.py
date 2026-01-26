"""
Widgets configuration tab for settings dialog.

Allows users to configure overlay widgets:
- Clock widget (enable, position, format, size, font, style)
- Weather widget (enable, position, location, API key, size, font, style)
"""
from typing import Optional, Dict, Any, Mapping
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QGroupBox, QCheckBox, QLineEdit, QPushButton,
    QScrollArea, QSlider, QCompleter, QFontComboBox, QButtonGroup
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QFont

from core.settings.settings_manager import SettingsManager
from core.logging.logger import get_logger
from core.settings.defaults import get_default_settings
from ui.styled_popup import StyledColorPicker
from ui.widget_stack_predictor import WidgetType, get_position_status_for_widget
from widgets.timezone_utils import get_local_timezone, get_common_timezones

logger = get_logger(__name__)


class NoWheelSlider(QSlider):
    def wheelEvent(self, event):  # type: ignore[override]
        event.ignore()


class WidgetsTab(QWidget):
    """Widgets configuration tab."""
    
    # Signals
    widgets_changed = Signal()
    
    def __init__(self, settings: SettingsManager, parent: Optional[QWidget] = None):
        """
        Initialize widgets tab.
        
        Args:
            settings: Settings manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._settings = settings
        self._widget_defaults = self._load_widget_defaults()
        self._current_subtab = 0
        self._scroll_area: Optional[QScrollArea] = None
        self._clock_color = self._color_from_default('clock', 'color', [255, 255, 255, 230])
        self._weather_color = self._color_from_default('weather', 'color', [255, 255, 255, 230])
        self._clock_border_color = self._color_from_default('clock', 'border_color', [128, 128, 128, 255])
        self._clock_bg_color = self._color_from_default('clock', 'bg_color', [64, 64, 64, 255])
        # Weather widget frame defaults mirror WeatherWidget internals
        self._weather_bg_color = self._color_from_default('weather', 'bg_color', [64, 64, 64, 255])
        self._weather_border_color = self._color_from_default('weather', 'border_color', [128, 128, 128, 255])
        # Media widget frame defaults mirror other overlay widgets
        self._media_color = self._color_from_default('media', 'color', [255, 255, 255, 230])
        self._media_bg_color = self._color_from_default('media', 'bg_color', [64, 64, 64, 255])
        self._media_border_color = self._color_from_default('media', 'border_color', [128, 128, 128, 255])
        # Spotify Beat Visualizer frame defaults inherit Spotify/media styling
        self._spotify_vis_fill_color = self._color_from_default(
            'spotify_visualizer', 'bar_fill_color', [255, 255, 255, 230]
        )
        self._spotify_vis_border_color = self._color_from_default(
            'spotify_visualizer', 'bar_border_color', [255, 255, 255, 230]
        )
        # Reddit widget frame defaults mirror Spotify/media widget styling
        self._reddit_color = self._color_from_default('reddit', 'color', [255, 255, 255, 230])
        self._reddit_bg_color = self._color_from_default('reddit', 'bg_color', [64, 64, 64, 255])
        self._reddit_border_color = self._color_from_default('reddit', 'border_color', [128, 128, 128, 255])
        self._media_artwork_size = int(self._widget_default('media', 'artwork_size', 200))
        self._loading = True
        self._setup_ui()
        self._load_settings()
        self._loading = False
        
        logger.debug("WidgetsTab created")
    
    def load_from_settings(self) -> None:
        """Reload all UI controls from settings manager (called after preset change)."""
        self._loading = True
        try:
            self._load_settings()
        finally:
            self._loading = False
        logger.debug("[WIDGETS_TAB] Reloaded from settings")
    
    def _load_widget_defaults(self) -> Dict[str, Dict[str, Any]]:
        """Load canonical widget defaults once for reuse."""
        try:
            defaults = get_default_settings()
            widgets_defaults = defaults.get('widgets', {})
            return widgets_defaults if isinstance(widgets_defaults, dict) else {}
        except Exception:
            logger.debug("[WIDGETS_TAB] Failed to load widget defaults", exc_info=True)
            return {}
    
    def _widget_default(self, section: str, key: str, fallback: Any) -> Any:
        """Fetch a default value for a widget section/key combo."""
        section_defaults = self._widget_defaults.get(section, {})
        if isinstance(section_defaults, dict) and key in section_defaults:
            return section_defaults[key]
        return fallback
    
    def _color_from_default(self, section: str, key: str, fallback: list[int]) -> QColor:
        """Return a QColor built from canonical defaults with fallback."""
        value = self._widget_default(section, key, fallback)
        try:
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                return QColor(*value)
        except Exception:
            logger.debug("[WIDGETS_TAB] Invalid color default for %s.%s", section, key, exc_info=True)
        return QColor(*fallback)
    
    def _default_int(self, section: str, key: str, fallback: int) -> int:
        """Return widget default coerced to int."""
        value = self._widget_default(section, key, fallback)
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(fallback)
    
    def _default_float(self, section: str, key: str, fallback: float) -> float:
        """Return widget default coerced to float."""
        value = self._widget_default(section, key, fallback)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(fallback)
    
    def _default_bool(self, section: str, key: str, fallback: bool) -> bool:
        """Return widget default coerced to bool via SettingsManager helper."""
        value = self._widget_default(section, key, fallback)
        return SettingsManager.to_bool(value, fallback)
    
    def _default_str(self, section: str, key: str, fallback: str) -> str:
        """Return widget default coerced to string."""
        value = self._widget_default(section, key, fallback)
        if value is None:
            return fallback
        return str(value)
    
    def _config_bool(self, section: str, config: Mapping[str, Any], key: str, fallback: bool) -> bool:
        default = self._default_bool(section, key, fallback)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        return SettingsManager.to_bool(raw, default)
    
    def _config_int(self, section: str, config: Mapping[str, Any], key: str, fallback: int) -> int:
        default = self._default_int(section, key, fallback)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
    
    def _config_float(self, section: str, config: Mapping[str, Any], key: str, fallback: float) -> float:
        default = self._default_float(section, key, fallback)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default
    
    def _config_str(self, section: str, config: Mapping[str, Any], key: str, fallback: str) -> str:
        default = self._default_str(section, key, fallback)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        if raw is None:
            return default
        return str(raw)
    
    @staticmethod
    def _set_combo_text(combo: QComboBox, text: str) -> None:
        """Select combo entry by visible text if present."""
        if text is None:
            return
        idx = combo.findText(text, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    
    @staticmethod
    def _set_combo_data(combo: QComboBox, data: Any) -> None:
        """Select combo entry by user data if present."""
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    
    def _setup_ui(self) -> None:
        """Setup tab UI with scroll area."""
        # Create scroll area
        scroll = QScrollArea(self)
        self._scroll_area = scroll
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.NoFrame)
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
        title = QLabel("Overlay Widgets")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        # Global widget options
        global_row = QHBoxLayout()
        self.widget_shadows_enabled = QCheckBox("Enable Widget Drop Shadows")
        self.widget_shadows_enabled.setChecked(self._default_bool('shadows', 'enabled', True))
        self.widget_shadows_enabled.setToolTip(
            "Applies a subtle bottom-right drop shadow to overlay widgets (clocks, "
            "weather, media) when enabled."
        )
        self.widget_shadows_enabled.stateChanged.connect(self._save_settings)
        global_row.addWidget(self.widget_shadows_enabled)
        global_row.addStretch()
        layout.addLayout(global_row)

        # Subtab-style toggle buttons (Clocks / Weather / Media / Reddit)
        subtab_row = QHBoxLayout()
        self._subtab_group = QButtonGroup(self)
        self._subtab_group.setExclusive(True)

        self._btn_clocks = QPushButton("Clocks")
        self._btn_weather = QPushButton("Weather")
        self._btn_media = QPushButton("Media")
        self._btn_reddit = QPushButton("Reddit")

        button_style = (
            "QPushButton {"
            " background-color: #2a2a2a;"
            " color: #ffffff;"
            " border-radius: 4px;"
            " padding: 4px 12px;"
            " border-top: 1px solid rgba(110, 110, 110, 0.8);"
            " border-left: 1px solid rgba(110, 110, 110, 0.8);"
            " border-right: 2px solid rgba(0, 0, 0, 0.75);"
            " border-bottom: 2px solid rgba(0, 0, 0, 0.8);"
            " }"
            "QPushButton:checked {"
            " background-color: #3a3a3a;"
            " font-weight: bold;"
            " border-top: 2px solid rgba(0, 0, 0, 0.75);"
            " border-left: 2px solid rgba(0, 0, 0, 0.75);"
            " border-right: 1px solid rgba(140, 140, 140, 0.85);"
            " border-bottom: 1px solid rgba(140, 140, 140, 0.85);"
            " }"
        )

        for idx, btn in enumerate((self._btn_clocks, self._btn_weather, self._btn_media, self._btn_reddit)):
            btn.setCheckable(True)
            btn.setStyleSheet(button_style)
            self._subtab_group.addButton(btn, idx)
            subtab_row.addWidget(btn)

        subtab_row.addStretch()
        layout.addLayout(subtab_row)

        self._subtab_group.idClicked.connect(self._on_subtab_changed)
        self._btn_clocks.setChecked(True)

        # Clock widget group
        clock_group = QGroupBox("Clock Widget")
        clock_layout = QVBoxLayout(clock_group)
        
        # Enable clock
        self.clock_enabled = QCheckBox("Enable Clock")
        self.clock_enabled.setChecked(self._default_bool('clock', 'enabled', True))
        self.clock_enabled.stateChanged.connect(self._save_settings)
        self.clock_enabled.stateChanged.connect(self._update_stack_status)
        clock_layout.addWidget(self.clock_enabled)
        
        # Time format
        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Format:"))
        self.clock_format = QComboBox()
        self.clock_format.addItems(["12 Hour", "24 Hour"])
        self.clock_format.currentTextChanged.connect(self._save_settings)
        default_format = self._default_str('clock', 'format', '24h').lower()
        format_map = {'12h': "12 Hour", '24h': "24 Hour"}
        self._set_combo_text(self.clock_format, format_map.get(default_format, "24 Hour"))
        format_row.addWidget(self.clock_format)
        format_row.addStretch()
        clock_layout.addLayout(format_row)
        
        # Show seconds
        self.clock_seconds = QCheckBox("Show Seconds")
        self.clock_seconds.setChecked(self._default_bool('clock', 'show_seconds', True))
        self.clock_seconds.stateChanged.connect(self._save_settings)
        self.clock_seconds.stateChanged.connect(self._update_stack_status)
        clock_layout.addWidget(self.clock_seconds)
        
        # Timezone
        tz_row = QHBoxLayout()
        tz_row.addWidget(QLabel("Timezone:"))
        self.clock_timezone = QComboBox()
        self.clock_timezone.setMinimumWidth(200)
        
        # Populate timezone dropdown
        self._populate_timezones()
        default_timezone = self._default_str('clock', 'timezone', 'local')
        self._set_combo_data(self.clock_timezone, default_timezone)
        
        self.clock_timezone.currentTextChanged.connect(self._save_settings)
        tz_row.addWidget(self.clock_timezone)
        
        # Auto-detect button
        self.tz_auto_btn = QPushButton("Auto-Detect")
        self.tz_auto_btn.clicked.connect(self._auto_detect_timezone)
        tz_row.addWidget(self.tz_auto_btn)
        tz_row.addStretch()
        clock_layout.addLayout(tz_row)
        
        # Show timezone abbreviation
        self.clock_show_tz = QCheckBox("Show Timezone Abbreviation")
        self.clock_show_tz.setChecked(self._default_bool('clock', 'show_timezone', True))
        self.clock_show_tz.stateChanged.connect(self._save_settings)
        self.clock_show_tz.stateChanged.connect(self._update_stack_status)
        clock_layout.addWidget(self.clock_show_tz)

        # Analogue mode options
        self.clock_analog_mode = QCheckBox("Use Analogue Clock")
        default_display_mode = self._default_str('clock', 'display_mode', 'analog').lower()
        self.clock_analog_mode.setChecked(default_display_mode == 'analog')
        self.clock_analog_mode.setToolTip(
            "Render the main clock as an analogue clock face with hour/minute/second hands."
        )
        self.clock_analog_mode.stateChanged.connect(self._save_settings)
        self.clock_analog_mode.stateChanged.connect(self._update_stack_status)
        clock_layout.addWidget(self.clock_analog_mode)

        self.clock_analog_shadow = QCheckBox("Analogue Face Shadow")
        self.clock_analog_shadow.setChecked(self._default_bool('clock', 'analog_face_shadow', True))
        self.clock_analog_shadow.setToolTip(
            "Enable a subtle drop shadow under the analogue clock face and hands."
        )
        self.clock_analog_shadow.stateChanged.connect(self._save_settings)
        clock_layout.addWidget(self.clock_analog_shadow)

        self.clock_analog_shadow_intense = QCheckBox("Intense Analogue Shadows")
        self.clock_analog_shadow_intense.setChecked(self._default_bool('clock', 'analog_shadow_intense', False))
        self.clock_analog_shadow_intense.setToolTip(
            "Doubles analogue shadow opacity and enlarges the drop shadow by ~50% for dramatic lighting."
        )
        self.clock_analog_shadow_intense.stateChanged.connect(self._save_settings)
        clock_layout.addWidget(self.clock_analog_shadow_intense)

        self.clock_digital_shadow_intense = QCheckBox("Intense Digital Shadows")
        self.clock_digital_shadow_intense.setChecked(self._default_bool('clock', 'digital_shadow_intense', False))
        self.clock_digital_shadow_intense.setToolTip(
            "Doubles digital clock shadow blur, opacity, and offset for dramatic effect on large displays."
        )
        self.clock_digital_shadow_intense.stateChanged.connect(self._save_settings)
        clock_layout.addWidget(self.clock_digital_shadow_intense)

        self.clock_show_numerals = QCheckBox("Show Hour Numerals (Analogue)")
        self.clock_show_numerals.setChecked(self._default_bool('clock', 'show_numerals', True))
        self.clock_show_numerals.stateChanged.connect(self._save_settings)
        clock_layout.addWidget(self.clock_show_numerals)
        
        # Position
        position_row = QHBoxLayout()
        position_row.addWidget(QLabel("Position:"))
        self.clock_position = QComboBox()
        self.clock_position.addItems([
            "Top Left", "Top Center", "Top Right",
            "Middle Left", "Center", "Middle Right",
            "Bottom Left", "Bottom Center", "Bottom Right"
        ])
        self.clock_position.currentTextChanged.connect(self._save_settings)
        self.clock_position.currentTextChanged.connect(self._update_stack_status)
        position_row.addWidget(self.clock_position)
        self._set_combo_text(self.clock_position, self._default_str('clock', 'position', 'Top Right'))
        self.clock_stack_status = QLabel("")
        self.clock_stack_status.setMinimumWidth(100)
        position_row.addWidget(self.clock_stack_status)
        position_row.addStretch()
        clock_layout.addLayout(position_row)

        # Display (monitor selection)
        clock_disp_row = QHBoxLayout()
        clock_disp_row.addWidget(QLabel("Display:"))
        self.clock_monitor_combo = QComboBox()
        self.clock_monitor_combo.addItems(["ALL", "1", "2", "3"])  # monitor indices are 1-based
        self.clock_monitor_combo.currentTextChanged.connect(self._save_settings)
        self.clock_monitor_combo.currentTextChanged.connect(self._update_stack_status)
        clock_disp_row.addWidget(self.clock_monitor_combo)
        clock_monitor_default = self._widget_default('clock', 'monitor', 'ALL')
        self._set_combo_text(self.clock_monitor_combo, str(clock_monitor_default))
        clock_disp_row.addStretch()
        clock_layout.addLayout(clock_disp_row)
        
        # Font family
        font_family_row = QHBoxLayout()
        font_family_row.addWidget(QLabel("Font:"))
        self.clock_font_combo = QFontComboBox()
        default_clock_font = self._default_str('clock', 'font_family', 'Segoe UI')
        self.clock_font_combo.setCurrentFont(QFont(default_clock_font))
        self.clock_font_combo.setMinimumWidth(220)
        self.clock_font_combo.currentFontChanged.connect(self._save_settings)
        font_family_row.addWidget(self.clock_font_combo)
        font_family_row.addStretch()
        clock_layout.addLayout(font_family_row)
        
        # Font size
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Font Size:"))
        self.clock_font_size = QSpinBox()
        self.clock_font_size.setRange(12, 144)
        self.clock_font_size.setValue(self._default_int('clock', 'font_size', 48))
        self.clock_font_size.setAccelerated(True)
        self.clock_font_size.valueChanged.connect(self._save_settings)
        self.clock_font_size.valueChanged.connect(self._update_stack_status)
        font_row.addWidget(self.clock_font_size)
        font_row.addWidget(QLabel("px"))
        font_row.addStretch()
        clock_layout.addLayout(font_row)
        
        # Text color
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Text Color:"))
        self.clock_color_btn = QPushButton("Choose Color...")
        self.clock_color_btn.clicked.connect(self._choose_clock_color)
        color_row.addWidget(self.clock_color_btn)
        color_row.addStretch()
        clock_layout.addLayout(color_row)
        
        # Margin
        margin_row = QHBoxLayout()
        margin_row.addWidget(QLabel("Margin:"))
        self.clock_margin = QSpinBox()
        self.clock_margin.setRange(0, 100)
        self.clock_margin.setValue(self._default_int('clock', 'margin', 30))
        self.clock_margin.setAccelerated(True)
        self.clock_margin.valueChanged.connect(self._save_settings)
        margin_row.addWidget(self.clock_margin)
        margin_row.addWidget(QLabel("px"))
        margin_row.addStretch()
        clock_layout.addLayout(margin_row)
        
        # Background frame
        self.clock_show_background = QCheckBox("Show Background Frame")
        self.clock_show_background.setChecked(self._default_bool('clock', 'show_background', True))
        self.clock_show_background.stateChanged.connect(self._save_settings)
        clock_layout.addWidget(self.clock_show_background)
        
        # Background opacity
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Background Opacity:"))
        self.clock_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.clock_bg_opacity.setMinimum(0)
        self.clock_bg_opacity.setMaximum(100)
        clock_bg_opacity_pct = int(self._default_float('clock', 'bg_opacity', 0.6) * 100)
        self.clock_bg_opacity.setValue(clock_bg_opacity_pct)
        self.clock_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.clock_bg_opacity.setTickInterval(10)
        self.clock_bg_opacity.valueChanged.connect(self._save_settings)
        opacity_row.addWidget(self.clock_bg_opacity)
        self.clock_opacity_label = QLabel(f"{clock_bg_opacity_pct}%")
        self.clock_bg_opacity.valueChanged.connect(lambda v: self.clock_opacity_label.setText(f"{v}%"))
        opacity_row.addWidget(self.clock_opacity_label)
        clock_layout.addLayout(opacity_row)

        # Background color
        clock_bg_color_row = QHBoxLayout()
        clock_bg_color_row.addWidget(QLabel("Background Color:"))
        self.clock_bg_color_btn = QPushButton("Choose Color...")
        self.clock_bg_color_btn.clicked.connect(self._choose_clock_bg_color)
        clock_bg_color_row.addWidget(self.clock_bg_color_btn)
        clock_bg_color_row.addStretch()
        clock_layout.addLayout(clock_bg_color_row)

        # Background border color
        clock_border_color_row = QHBoxLayout()
        clock_border_color_row.addWidget(QLabel("Border Color:"))
        self.clock_border_color_btn = QPushButton("Choose Color...")
        self.clock_border_color_btn.clicked.connect(self._choose_clock_border_color)
        clock_border_color_row.addWidget(self.clock_border_color_btn)
        clock_border_color_row.addStretch()
        clock_layout.addLayout(clock_border_color_row)

        # Background border opacity
        clock_border_opacity_row = QHBoxLayout()
        clock_border_opacity_row.addWidget(QLabel("Border Opacity:"))
        self.clock_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.clock_border_opacity.setMinimum(0)
        self.clock_border_opacity.setMaximum(100)
        clock_border_opacity_pct = int(self._default_float('clock', 'border_opacity', 0.8) * 100)
        self.clock_border_opacity.setValue(clock_border_opacity_pct)
        self.clock_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.clock_border_opacity.setTickInterval(10)
        self.clock_border_opacity.valueChanged.connect(self._save_settings)
        clock_border_opacity_row.addWidget(self.clock_border_opacity)
        self.clock_border_opacity_label = QLabel(f"{clock_border_opacity_pct}%")
        self.clock_border_opacity.valueChanged.connect(
            lambda v: self.clock_border_opacity_label.setText(f"{v}%")
        )
        clock_border_opacity_row.addWidget(self.clock_border_opacity_label)
        clock_layout.addLayout(clock_border_opacity_row)

        extra_label = QLabel("Additional clocks (optional, share style with main clock)")
        extra_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        clock_layout.addWidget(extra_label)

        clock2_row = QHBoxLayout()
        self.clock2_enabled = QCheckBox("Enable Clock 2")
        self.clock2_enabled.stateChanged.connect(self._save_settings)
        self.clock2_enabled.stateChanged.connect(self._update_stack_status)
        clock2_row.addWidget(self.clock2_enabled)
        clock2_row.addWidget(QLabel("Display:"))
        self.clock2_monitor_combo = QComboBox()
        self.clock2_monitor_combo.addItems(["ALL", "1", "2", "3"])
        self.clock2_monitor_combo.currentTextChanged.connect(self._save_settings)
        clock2_row.addWidget(self.clock2_monitor_combo)
        clock2_row.addWidget(QLabel("Timezone:"))
        self.clock2_timezone = QComboBox()
        self.clock2_timezone.setMinimumWidth(160)
        self._populate_timezones_for_combo(self.clock2_timezone)
        self.clock2_timezone.currentTextChanged.connect(self._save_settings)
        clock2_row.addWidget(self.clock2_timezone)
        clock2_row.addStretch()
        clock_layout.addLayout(clock2_row)

        clock3_row = QHBoxLayout()
        self.clock3_enabled = QCheckBox("Enable Clock 3")
        self.clock3_enabled.stateChanged.connect(self._save_settings)
        self.clock3_enabled.stateChanged.connect(self._update_stack_status)
        clock3_row.addWidget(self.clock3_enabled)
        clock3_row.addWidget(QLabel("Display:"))
        self.clock3_monitor_combo = QComboBox()
        self.clock3_monitor_combo.addItems(["ALL", "1", "2", "3"])
        self.clock3_monitor_combo.currentTextChanged.connect(self._save_settings)
        clock3_row.addWidget(self.clock3_monitor_combo)
        clock3_row.addWidget(QLabel("Timezone:"))
        self.clock3_timezone = QComboBox()
        self.clock3_timezone.setMinimumWidth(160)
        self._populate_timezones_for_combo(self.clock3_timezone)
        self.clock3_timezone.currentTextChanged.connect(self._save_settings)
        clock3_row.addWidget(self.clock3_timezone)
        clock3_row.addStretch()
        clock_layout.addLayout(clock3_row)

        self._clocks_container = QWidget()
        clocks_container_layout = QVBoxLayout(self._clocks_container)
        clocks_container_layout.setContentsMargins(0, 10, 0, 0)
        clocks_container_layout.addWidget(clock_group)
        layout.addWidget(self._clocks_container)
        
        # Weather widget group
        weather_group = QGroupBox("Weather Widget")
        weather_layout = QVBoxLayout(weather_group)
        
        # Enable weather
        self.weather_enabled = QCheckBox("Enable Weather Widget")
        self.weather_enabled.setChecked(self._default_bool('weather', 'enabled', True))
        self.weather_enabled.stateChanged.connect(self._save_settings)
        self.weather_enabled.stateChanged.connect(self._update_stack_status)
        weather_layout.addWidget(self.weather_enabled)
        
        # Info label - no API key needed!
        info_label = QLabel("✓ Uses Open-Meteo API (free, no API key required)")
        info_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        weather_layout.addWidget(info_label)
        
        # Location with autocomplete
        location_row = QHBoxLayout()
        location_row.addWidget(QLabel("Location:"))
        self.weather_location = QLineEdit()
        default_city = self._default_str('weather', 'location', '')
        self.weather_location.setText(default_city)
        self.weather_location.setPlaceholderText("City name...")
        self.weather_location.textChanged.connect(self._save_settings)
        
        # Add autocomplete with common world cities
        common_cities = [
            "London", "New York", "Tokyo", "Paris", "Berlin", "Sydney", "Toronto",
            "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
            "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville",
            "Fort Worth", "Columbus", "Charlotte", "San Francisco", "Indianapolis",
            "Seattle", "Denver", "Washington", "Boston", "El Paso", "Nashville",
            "Detroit", "Portland", "Las Vegas", "Memphis", "Louisville", "Baltimore",
            "Milwaukee", "Albuquerque", "Tucson", "Fresno", "Mesa", "Sacramento",
            "Atlanta", "Kansas City", "Colorado Springs", "Omaha", "Raleigh", "Miami",
            "Long Beach", "Virginia Beach", "Oakland", "Minneapolis", "Tulsa",
            "Arlington", "Tampa", "New Orleans", "Wichita", "Cleveland", "Bakersfield",
            "Munich", "Madrid", "Rome", "Amsterdam", "Barcelona", "Vienna",
            "Hamburg", "Warsaw", "Budapest", "Prague", "Copenhagen", "Stockholm",
            "Brussels", "Dublin", "Lisbon", "Athens", "Helsinki", "Oslo",
            "Shanghai", "Beijing", "Hong Kong", "Singapore", "Seoul", "Bangkok",
            "Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata", "Hyderabad",
            "Melbourne", "Brisbane", "Perth", "Auckland", "Wellington",
            "Cape Town", "Johannesburg", "Durban", "Cairo", "Lagos", "Nairobi",
            "Buenos Aires", "Rio de Janeiro", "São Paulo", "Lima", "Bogotá",
            "Santiago", "Mexico City", "Guadalajara", "Monterrey", "Havana",
            "Tel Aviv", "Jerusalem", "Dubai", "Abu Dhabi", "Doha", "Istanbul",
            "Moscow", "St Petersburg", "Kyiv", "Minsk", "Bucharest", "Sofia"
        ]
        completer = QCompleter(sorted(common_cities))
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.weather_location.setCompleter(completer)
        
        location_row.addWidget(self.weather_location)
        weather_layout.addLayout(location_row)
        
        # Position
        weather_pos_row = QHBoxLayout()
        weather_pos_row.addWidget(QLabel("Position:"))
        self.weather_position = QComboBox()
        self.weather_position.addItems([
            "Top Left", "Top Center", "Top Right",
            "Middle Left", "Center", "Middle Right",
            "Bottom Left", "Bottom Center", "Bottom Right"
        ])
        self.weather_position.currentTextChanged.connect(self._save_settings)
        self.weather_position.currentTextChanged.connect(self._update_stack_status)
        weather_pos_row.addWidget(self.weather_position)
        self._set_combo_text(self.weather_position, self._default_str('weather', 'position', 'Top Left'))
        self.weather_stack_status = QLabel("")
        self.weather_stack_status.setMinimumWidth(100)
        weather_pos_row.addWidget(self.weather_stack_status)
        weather_pos_row.addStretch()
        weather_layout.addLayout(weather_pos_row)

        # Display (monitor selection)
        weather_disp_row = QHBoxLayout()
        weather_disp_row.addWidget(QLabel("Display:"))
        self.weather_monitor_combo = QComboBox()
        self.weather_monitor_combo.addItems(["ALL", "1", "2", "3"])  # monitor indices are 1-based
        self.weather_monitor_combo.currentTextChanged.connect(self._save_settings)
        self.weather_monitor_combo.currentTextChanged.connect(self._update_stack_status)
        weather_disp_row.addWidget(self.weather_monitor_combo)
        monitor_default = self._widget_default('weather', 'monitor', 'ALL')
        self._set_combo_text(self.weather_monitor_combo, str(monitor_default))
        weather_disp_row.addStretch()
        weather_layout.addLayout(weather_disp_row)
        
        # Font family
        weather_font_family_row = QHBoxLayout()
        weather_font_family_row.addWidget(QLabel("Font:"))
        self.weather_font_combo = QFontComboBox()
        default_weather_font = self._default_str('weather', 'font_family', 'Segoe UI')
        self.weather_font_combo.setCurrentFont(QFont(default_weather_font))
        self.weather_font_combo.setMinimumWidth(220)
        self.weather_font_combo.currentFontChanged.connect(self._save_settings)
        weather_font_family_row.addWidget(self.weather_font_combo)
        weather_font_family_row.addStretch()
        weather_layout.addLayout(weather_font_family_row)
        
        # Font size
        weather_font_row = QHBoxLayout()
        weather_font_row.addWidget(QLabel("Font Size:"))
        self.weather_font_size = QSpinBox()
        self.weather_font_size.setRange(12, 72)
        self.weather_font_size.setValue(self._default_int('weather', 'font_size', 24))
        self.weather_font_size.setAccelerated(True)
        self.weather_font_size.valueChanged.connect(self._save_settings)
        self.weather_font_size.valueChanged.connect(self._update_stack_status)
        weather_font_row.addWidget(self.weather_font_size)
        weather_font_row.addWidget(QLabel("px"))
        weather_font_row.addStretch()
        weather_layout.addLayout(weather_font_row)
        
        # Text color
        weather_color_row = QHBoxLayout()
        weather_color_row.addWidget(QLabel("Text Color:"))
        self.weather_color_btn = QPushButton("Choose Color...")
        self.weather_color_btn.clicked.connect(self._choose_weather_color)
        weather_color_row.addWidget(self.weather_color_btn)
        weather_color_row.addStretch()
        weather_layout.addLayout(weather_color_row)
        
        # Show forecast line
        self.weather_show_forecast = QCheckBox("Show Forecast Line")
        self.weather_show_forecast.setChecked(self._default_bool('weather', 'show_forecast', True))
        self.weather_show_forecast.setToolTip("Display tomorrow's forecast below current weather")
        self.weather_show_forecast.stateChanged.connect(self._save_settings)
        self.weather_show_forecast.stateChanged.connect(self._update_stack_status)
        weather_layout.addWidget(self.weather_show_forecast)

        # Detail row toggle
        self.weather_show_details_row = QCheckBox("Show Detail Row (Humidity/Rain/Wind)")
        self.weather_show_details_row.setChecked(self._default_bool('weather', 'show_details_row', False))
        self.weather_show_details_row.setToolTip(
            "Display a compact row of monochrome humidity, rain chance, and wind icons between the main block and forecast."
        )
        self.weather_show_details_row.stateChanged.connect(self._save_settings)
        self.weather_show_details_row.stateChanged.connect(self._update_stack_status)
        weather_layout.addWidget(self.weather_show_details_row)

        icon_row = QHBoxLayout()
        icon_row.addWidget(QLabel("Weather Icon Alignment:"))
        self.weather_icon_alignment = QComboBox()
        self.weather_icon_alignment.addItem("None", "NONE")
        self.weather_icon_alignment.addItem("Left aligned", "LEFT")
        self.weather_icon_alignment.addItem("Right aligned", "RIGHT")
        self.weather_icon_alignment.currentTextChanged.connect(self._save_settings)
        icon_row.addWidget(self.weather_icon_alignment)
        icon_row.addStretch()
        weather_layout.addLayout(icon_row)
        default_icon_alignment = self._default_str('weather', 'animated_icon_alignment', 'NONE')
        self._set_combo_data(self.weather_icon_alignment, (default_icon_alignment or 'NONE').upper())

        self.weather_icon_animated = QCheckBox("Animate weather icon")
        self.weather_icon_animated.setToolTip("Disable animation to reduce CPU/GPU cost while keeping the icon visible.")
        self.weather_icon_animated.setChecked(self._default_bool('weather', 'animated_icon_enabled', True))
        self.weather_icon_animated.stateChanged.connect(self._save_settings)
        weather_layout.addWidget(self.weather_icon_animated)

        self.weather_desaturate_icon = QCheckBox("Desaturate Animated Icon")
        self.weather_desaturate_icon.setToolTip("Render the animated SVG with a grayscale tint to blend with monochrome themes.")
        self.weather_desaturate_icon.setChecked(self._default_bool('weather', 'desaturate_animated_icon', False))
        self.weather_desaturate_icon.stateChanged.connect(self._save_settings)
        weather_layout.addWidget(self.weather_desaturate_icon)

        # Intense shadow
        self.weather_intense_shadow = QCheckBox("Intense Shadows")
        self.weather_intense_shadow.setChecked(self._default_bool('weather', 'intense_shadow', True))
        self.weather_intense_shadow.setToolTip(
            "Doubles shadow blur, opacity, and offset for dramatic effect on large displays."
        )
        self.weather_intense_shadow.stateChanged.connect(self._save_settings)
        weather_layout.addWidget(self.weather_intense_shadow)
        
        # Background frame
        self.weather_show_background = QCheckBox("Show Background Frame")
        self.weather_show_background.setChecked(self._default_bool('weather', 'show_background', True))
        self.weather_show_background.stateChanged.connect(self._save_settings)
        weather_layout.addWidget(self.weather_show_background)
        
        # Background opacity
        weather_opacity_row = QHBoxLayout()
        weather_opacity_row.addWidget(QLabel("Background Opacity:"))
        self.weather_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.weather_bg_opacity.setMinimum(0)
        self.weather_bg_opacity.setMaximum(100)
        weather_bg_opacity_pct = int(self._default_float('weather', 'bg_opacity', 0.6) * 100)
        self.weather_bg_opacity.setValue(weather_bg_opacity_pct)
        self.weather_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.weather_bg_opacity.setTickInterval(10)
        self.weather_bg_opacity.valueChanged.connect(self._save_settings)
        weather_opacity_row.addWidget(self.weather_bg_opacity)
        self.weather_opacity_label = QLabel(f"{weather_bg_opacity_pct}%")
        self.weather_bg_opacity.valueChanged.connect(lambda v: self.weather_opacity_label.setText(f"{v}%"))
        weather_opacity_row.addWidget(self.weather_opacity_label)
        weather_layout.addLayout(weather_opacity_row)

        # Background color
        weather_bg_color_row = QHBoxLayout()
        weather_bg_color_row.addWidget(QLabel("Background Color:"))
        self.weather_bg_color_btn = QPushButton("Choose Color...")
        self.weather_bg_color_btn.clicked.connect(self._choose_weather_bg_color)
        weather_bg_color_row.addWidget(self.weather_bg_color_btn)
        weather_bg_color_row.addStretch()
        weather_layout.addLayout(weather_bg_color_row)

        # Border color
        weather_border_color_row = QHBoxLayout()
        weather_border_color_row.addWidget(QLabel("Border Color:"))
        self.weather_border_color_btn = QPushButton("Choose Color...")
        self.weather_border_color_btn.clicked.connect(self._choose_weather_border_color)
        weather_border_color_row.addWidget(self.weather_border_color_btn)
        weather_border_color_row.addStretch()
        weather_layout.addLayout(weather_border_color_row)

        # Border opacity (independent from background opacity)
        weather_border_opacity_row = QHBoxLayout()
        weather_border_opacity_row.addWidget(QLabel("Border Opacity:"))
        self.weather_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.weather_border_opacity.setMinimum(0)
        self.weather_border_opacity.setMaximum(100)
        weather_border_opacity_pct = int(self._default_float('weather', 'border_opacity', 1.0) * 100)
        self.weather_border_opacity.setValue(weather_border_opacity_pct)
        self.weather_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.weather_border_opacity.setTickInterval(10)
        self.weather_border_opacity.valueChanged.connect(self._save_settings)
        weather_border_opacity_row.addWidget(self.weather_border_opacity)
        self.weather_border_opacity_label = QLabel(f"{weather_border_opacity_pct}%")
        self.weather_border_opacity.valueChanged.connect(
            lambda v: self.weather_border_opacity_label.setText(f"{v}%")
        )
        weather_border_opacity_row.addWidget(self.weather_border_opacity_label)
        weather_layout.addLayout(weather_border_opacity_row)

        # Margin from screen edge
        weather_margin_row = QHBoxLayout()
        weather_margin_row.addWidget(QLabel("Margin:"))
        self.weather_margin = QSpinBox()
        self.weather_margin.setRange(0, 200)
        self.weather_margin.setValue(self._default_int('weather', 'margin', 30))
        self.weather_margin.setSuffix(" px")
        self.weather_margin.setToolTip("Distance from screen edge in pixels")
        self.weather_margin.valueChanged.connect(self._save_settings)
        weather_margin_row.addWidget(self.weather_margin)
        weather_margin_row.addStretch()
        weather_layout.addLayout(weather_margin_row)
        
        self._weather_container = QWidget()
        weather_container_layout = QVBoxLayout(self._weather_container)
        weather_container_layout.setContentsMargins(0, 10, 0, 0)
        weather_container_layout.addWidget(weather_group)
        layout.addWidget(self._weather_container)

        # Media widget group (Spotify-specific overlay)
        media_group = QGroupBox("Spotify Widget")
        media_layout = QVBoxLayout(media_group)

        self.media_enabled = QCheckBox("Enable Spotify Widget")
        self.media_enabled.setToolTip(
            "Shows current Spotify playback using Windows media controls when available."
        )
        self.media_enabled.stateChanged.connect(self._save_settings)
        self.media_enabled.stateChanged.connect(self._update_stack_status)
        media_layout.addWidget(self.media_enabled)

        media_info = QLabel(
            "This widget is display-only and non-interactive. Transport controls will "
            "only be active when explicitly enabled via input settings (hard-exit / Ctrl mode)."
        )
        media_info.setWordWrap(True)
        media_info.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        media_layout.addWidget(media_info)

        media_pos_row = QHBoxLayout()
        media_pos_row.addWidget(QLabel("Position:"))
        self.media_position = QComboBox()
        self.media_position.addItems([
            "Top Left", "Top Center", "Top Right",
            "Middle Left", "Center", "Middle Right",
            "Bottom Left", "Bottom Center", "Bottom Right",
        ])
        self.media_position.currentTextChanged.connect(self._save_settings)
        self.media_position.currentTextChanged.connect(self._update_stack_status)
        media_pos_row.addWidget(self.media_position)
        self._set_combo_text(self.media_position, self._default_str('media', 'position', 'Bottom Left'))
        self.media_stack_status = QLabel("")
        self.media_stack_status.setMinimumWidth(100)
        media_pos_row.addWidget(self.media_stack_status)
        media_pos_row.addStretch()
        media_layout.addLayout(media_pos_row)

        media_disp_row = QHBoxLayout()
        media_disp_row.addWidget(QLabel("Display:"))
        self.media_monitor_combo = QComboBox()
        self.media_monitor_combo.addItems(["ALL", "1", "2", "3"])
        self.media_monitor_combo.currentTextChanged.connect(self._save_settings)
        self.media_monitor_combo.currentTextChanged.connect(self._update_stack_status)
        media_disp_row.addWidget(self.media_monitor_combo)
        media_monitor_default = self._widget_default('media', 'monitor', 'ALL')
        self._set_combo_text(self.media_monitor_combo, str(media_monitor_default))
        media_disp_row.addStretch()
        media_layout.addLayout(media_disp_row)

        media_font_family_row = QHBoxLayout()
        media_font_family_row.addWidget(QLabel("Font:"))
        self.media_font_combo = QFontComboBox()
        default_media_font = self._default_str('media', 'font_family', 'Segoe UI')
        self.media_font_combo.setCurrentFont(QFont(default_media_font))
        self.media_font_combo.setMinimumWidth(220)
        self.media_font_combo.currentFontChanged.connect(self._save_settings)
        media_font_family_row.addWidget(self.media_font_combo)
        media_font_family_row.addStretch()
        media_layout.addLayout(media_font_family_row)

        media_font_row = QHBoxLayout()
        media_font_row.addWidget(QLabel("Font Size:"))
        self.media_font_size = QSpinBox()
        self.media_font_size.setRange(10, 72)
        self.media_font_size.setValue(self._default_int('media', 'font_size', 20))
        self.media_font_size.setAccelerated(True)
        self.media_font_size.valueChanged.connect(self._save_settings)
        self.media_font_size.valueChanged.connect(self._update_stack_status)
        media_font_row.addWidget(self.media_font_size)
        media_font_row.addWidget(QLabel("px"))
        media_font_row.addStretch()
        media_layout.addLayout(media_font_row)

        media_margin_row = QHBoxLayout()
        media_margin_row.addWidget(QLabel("Margin:"))
        self.media_margin = QSpinBox()
        self.media_margin.setRange(0, 100)
        self.media_margin.setValue(self._default_int('media', 'margin', 30))
        self.media_margin.setAccelerated(True)
        self.media_margin.valueChanged.connect(self._save_settings)
        media_margin_row.addWidget(self.media_margin)
        media_margin_row.addWidget(QLabel("px"))
        media_margin_row.addStretch()
        media_layout.addLayout(media_margin_row)

        media_color_row = QHBoxLayout()
        media_color_row.addWidget(QLabel("Text Color:"))
        self.media_color_btn = QPushButton("Choose Color...")
        self.media_color_btn.clicked.connect(self._choose_media_color)
        media_color_row.addWidget(self.media_color_btn)
        media_color_row.addStretch()
        media_layout.addLayout(media_color_row)

        self.media_show_background = QCheckBox("Show Background Frame")
        self.media_show_background.setChecked(self._default_bool('media', 'show_background', True))
        self.media_show_background.stateChanged.connect(self._save_settings)
        media_layout.addWidget(self.media_show_background)

        # Intense shadow
        self.media_intense_shadow = QCheckBox("Intense Shadows")
        self.media_intense_shadow.setChecked(self._default_bool('media', 'intense_shadow', True))
        self.media_intense_shadow.setToolTip(
            "Doubles shadow blur, opacity, and offset for dramatic effect on large displays."
        )
        self.media_intense_shadow.stateChanged.connect(self._save_settings)
        media_layout.addWidget(self.media_intense_shadow)

        media_opacity_row = QHBoxLayout()
        media_opacity_row.addWidget(QLabel("Background Opacity:"))
        self.media_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.media_bg_opacity.setMinimum(0)
        self.media_bg_opacity.setMaximum(100)
        media_bg_opacity_pct = int(self._default_float('media', 'bg_opacity', 0.6) * 100)
        self.media_bg_opacity.setValue(media_bg_opacity_pct)
        self.media_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.media_bg_opacity.setTickInterval(10)
        self.media_bg_opacity.valueChanged.connect(self._save_settings)
        media_opacity_row.addWidget(self.media_bg_opacity)
        self.media_bg_opacity_label = QLabel(f"{media_bg_opacity_pct}%")
        self.media_bg_opacity.valueChanged.connect(
            lambda v: self.media_bg_opacity_label.setText(f"{v}%")
        )
        media_opacity_row.addWidget(self.media_bg_opacity_label)
        media_layout.addLayout(media_opacity_row)

        media_bg_color_row = QHBoxLayout()
        media_bg_color_row.addWidget(QLabel("Background Color:"))
        self.media_bg_color_btn = QPushButton("Choose Color...")
        self.media_bg_color_btn.clicked.connect(self._choose_media_bg_color)
        media_bg_color_row.addWidget(self.media_bg_color_btn)
        media_bg_color_row.addStretch()
        media_layout.addLayout(media_bg_color_row)

        media_border_color_row = QHBoxLayout()
        media_border_color_row.addWidget(QLabel("Border Color:"))
        self.media_border_color_btn = QPushButton("Choose Color...")
        self.media_border_color_btn.clicked.connect(self._choose_media_border_color)
        media_border_color_row.addWidget(self.media_border_color_btn)
        media_border_color_row.addStretch()
        media_layout.addLayout(media_border_color_row)

        media_border_opacity_row = QHBoxLayout()
        media_border_opacity_row.addWidget(QLabel("Border Opacity:"))
        self.media_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.media_border_opacity.setMinimum(0)
        self.media_border_opacity.setMaximum(100)
        media_border_opacity_pct = int(self._default_float('media', 'border_opacity', 1.0) * 100)
        self.media_border_opacity.setValue(media_border_opacity_pct)
        self.media_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.media_border_opacity.setTickInterval(10)
        self.media_border_opacity.valueChanged.connect(self._save_settings)
        media_border_opacity_row.addWidget(self.media_border_opacity)
        self.media_border_opacity_label = QLabel(f"{media_border_opacity_pct}%")
        self.media_border_opacity.valueChanged.connect(
            lambda v: self.media_border_opacity_label.setText(f"{v}%")
        )
        media_border_opacity_row.addWidget(self.media_border_opacity_label)
        media_layout.addLayout(media_border_opacity_row)

        media_volume_fill_row = QHBoxLayout()
        media_volume_fill_row.addWidget(QLabel("Volume Fill Color:"))
        self.media_volume_fill_color_btn = QPushButton("Choose Color...")
        self.media_volume_fill_color_btn.clicked.connect(self._choose_media_volume_fill_color)
        media_volume_fill_row.addWidget(self.media_volume_fill_color_btn)
        media_volume_fill_row.addStretch()
        media_layout.addLayout(media_volume_fill_row)

        # Artwork size
        media_artwork_row = QHBoxLayout()
        media_artwork_row.addWidget(QLabel("Artwork Size:"))
        self.media_artwork_size = QSpinBox()
        # Artwork size is in logical pixels; allow a comfortable range while
        # preventing values that would likely clip inside the widget.
        self.media_artwork_size.setRange(100, 300)
        self.media_artwork_size.setValue(self._default_int('media', 'artwork_size', 200))
        self.media_artwork_size.setAccelerated(True)
        self.media_artwork_size.valueChanged.connect(self._save_settings)
        self.media_artwork_size.valueChanged.connect(self._update_stack_status)
        media_artwork_row.addWidget(self.media_artwork_size)
        media_artwork_row.addWidget(QLabel("px"))
        media_artwork_row.addStretch()
        media_layout.addLayout(media_artwork_row)

        # Artwork border style
        self.media_rounded_artwork = QCheckBox("Rounded Artwork Border")
        self.media_rounded_artwork.setChecked(
            self._default_bool('media', 'rounded_artwork_border', True)
        )
        self.media_rounded_artwork.stateChanged.connect(self._save_settings)
        media_layout.addWidget(self.media_rounded_artwork)

        # Header frame around logo + title
        self.media_show_header_frame = QCheckBox("Header Border Around Logo + Title")
        self.media_show_header_frame.setChecked(
            self._default_bool('media', 'show_header_frame', True)
        )
        self.media_show_header_frame.stateChanged.connect(self._save_settings)
        media_layout.addWidget(self.media_show_header_frame)

        # Controls visibility
        self.media_show_controls = QCheckBox("Show Transport Controls")
        self.media_show_controls.setChecked(
            self._default_bool('media', 'show_controls', True)
        )
        self.media_show_controls.stateChanged.connect(self._save_settings)
        media_layout.addWidget(self.media_show_controls)

        # Spotify-only vertical volume slider (paired with the Spotify card).
        self.media_spotify_volume_enabled = QCheckBox("Enable Spotify Volume Slider")
        self.media_spotify_volume_enabled.setToolTip(
            "Show a slim vertical volume slider next to the Spotify card when Core Audio/pycaw is available. "
            "The slider only affects the Spotify session volume and is gated by hard-exit / Ctrl interaction modes."
        )
        self.media_spotify_volume_enabled.setChecked(
            self._default_bool('media', 'spotify_volume_enabled', True)
        )
        self.media_spotify_volume_enabled.stateChanged.connect(self._save_settings)
        media_layout.addWidget(self.media_spotify_volume_enabled)

        # Spotify Beat Visualizer group (Spotify-only beat bars tied to
        # the Spotify/Media widget).
        spotify_vis_group = QGroupBox("Spotify Beat Visualizer")
        spotify_vis_layout = QVBoxLayout(spotify_vis_group)

        # Enable/disable row with FORCE Software Visualizer on the same line.
        spotify_vis_enable_row = QHBoxLayout()
        self.spotify_vis_enabled = QCheckBox("Enable Spotify Beat Visualizer")
        self.spotify_vis_enabled.setChecked(self._default_bool('spotify_visualizer', 'enabled', True))
        self.spotify_vis_enabled.setToolTip(
            "Shows a thin bar visualizer tied to Spotify playback, positioned just above the Spotify widget."
        )
        self.spotify_vis_enabled.stateChanged.connect(self._save_settings)
        spotify_vis_enable_row.addWidget(self.spotify_vis_enabled)

        # Optional software visualiser fallback. When enabled, the legacy
        # QWidget-based bar renderer is allowed to draw when OpenGL is
        # unavailable or when the renderer backend is set to Software.
        self.spotify_vis_software_enabled = QCheckBox("FORCE Software Visualizer")
        self.spotify_vis_software_enabled.setChecked(
            self._default_bool('spotify_visualizer', 'software_visualizer_enabled', False)
        )
        self.spotify_vis_software_enabled.setToolTip(
            "Force the legacy CPU bar visualizer even when the renderer backend is set to Software or when OpenGL is unavailable."
        )
        self.spotify_vis_software_enabled.stateChanged.connect(self._save_settings)
        spotify_vis_enable_row.addStretch()
        spotify_vis_enable_row.addWidget(self.spotify_vis_software_enabled)
        spotify_vis_layout.addLayout(spotify_vis_enable_row)

        # Visualization Mode dropdown - only Spectrum is functional, others greyed out
        spotify_vis_mode_row = QHBoxLayout()
        spotify_vis_mode_row.addWidget(QLabel("Mode:"))
        self.spotify_vis_mode = QComboBox()
        self.spotify_vis_mode.setMinimumWidth(180)
        # Add all modes - only Spectrum is enabled, others are greyed out (future implementation)
        vis_modes = [
            ("Spectrum", True),           # Classic bar spectrum analyzer - FUNCTIONAL
            ("Waveform Ribbon", False),   # Morphing waveform ribbon - NOT IMPLEMENTED
            ("DNA Helix", False),         # Dual helices with amplitude - NOT IMPLEMENTED
            ("Radial Bloom", False),      # Polar coordinate FFT display - NOT IMPLEMENTED
            ("Spectrogram", False),       # Scrolling history ribbon - NOT IMPLEMENTED
            ("Phasor Swarm", False),      # Particle emitters on bar positions - NOT IMPLEMENTED
        ]
        for mode_name, is_enabled in vis_modes:
            self.spotify_vis_mode.addItem(mode_name)
            idx = self.spotify_vis_mode.count() - 1
            if not is_enabled:
                # Grey out non-functional modes
                self.spotify_vis_mode.setItemData(
                    idx,
                    0,  # Disable the item
                    Qt.ItemDataRole.UserRole - 1
                )
        self.spotify_vis_mode.setCurrentIndex(0)  # Default to Spectrum
        self.spotify_vis_mode.setToolTip(
            "Visualization mode. Only Spectrum is currently functional; other modes are planned for future releases."
        )
        self.spotify_vis_mode.currentIndexChanged.connect(self._save_settings)
        spotify_vis_mode_row.addWidget(self.spotify_vis_mode)
        spotify_vis_mode_row.addStretch()
        spotify_vis_layout.addLayout(spotify_vis_mode_row)

        spotify_vis_bar_row = QHBoxLayout()
        spotify_vis_bar_row.addWidget(QLabel("Bar Count:"))
        self.spotify_vis_bar_count = QSpinBox()
        self.spotify_vis_bar_count.setRange(8, 96)
        self.spotify_vis_bar_count.setValue(self._default_int('spotify_visualizer', 'bar_count', 32))
        self.spotify_vis_bar_count.setAccelerated(True)
        self.spotify_vis_bar_count.setToolTip("Number of frequency bars to display (8-96)")
        self.spotify_vis_bar_count.valueChanged.connect(self._save_settings)
        spotify_vis_bar_row.addWidget(self.spotify_vis_bar_count)
        spotify_vis_bar_row.addWidget(QLabel("bars"))
        spotify_vis_bar_row.addStretch()
        spotify_vis_layout.addLayout(spotify_vis_bar_row)

        spotify_vis_block_row = QHBoxLayout()
        spotify_vis_block_row.addWidget(QLabel("Audio Block Size:"))
        self.spotify_vis_block_size = QComboBox()
        self.spotify_vis_block_size.setMinimumWidth(140)
        self.spotify_vis_block_size.addItem("Auto (Driver)", 0)
        self.spotify_vis_block_size.addItem("256 samples", 256)
        self.spotify_vis_block_size.addItem("512 samples", 512)
        self.spotify_vis_block_size.addItem("1024 samples", 1024)
        self.spotify_vis_block_size.currentIndexChanged.connect(self._save_settings)
        spotify_vis_block_row.addWidget(self.spotify_vis_block_size)
        default_block = self._default_int('spotify_visualizer', 'audio_block_size', 512)
        block_idx = self.spotify_vis_block_size.findData(default_block)
        if block_idx >= 0:
            self.spotify_vis_block_size.setCurrentIndex(block_idx)
        spotify_vis_block_row.addStretch()
        spotify_vis_layout.addLayout(spotify_vis_block_row)

        spotify_vis_fill_row = QHBoxLayout()
        spotify_vis_fill_row.addWidget(QLabel("Bar Fill Color:"))
        self.spotify_vis_fill_color_btn = QPushButton("Choose Color...")
        self.spotify_vis_fill_color_btn.clicked.connect(self._choose_spotify_vis_fill_color)
        spotify_vis_fill_row.addWidget(self.spotify_vis_fill_color_btn)
        spotify_vis_fill_row.addStretch()
        spotify_vis_layout.addLayout(spotify_vis_fill_row)

        spotify_vis_border_color_row = QHBoxLayout()
        spotify_vis_border_color_row.addWidget(QLabel("Bar Border Color:"))
        self.spotify_vis_border_color_btn = QPushButton("Choose Color...")
        self.spotify_vis_border_color_btn.clicked.connect(self._choose_spotify_vis_border_color)
        spotify_vis_border_color_row.addWidget(self.spotify_vis_border_color_btn)
        spotify_vis_border_color_row.addStretch()
        spotify_vis_layout.addLayout(spotify_vis_border_color_row)

        spotify_vis_border_opacity_row = QHBoxLayout()
        spotify_vis_border_opacity_row.addWidget(QLabel("Bar Border Opacity:"))
        self.spotify_vis_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.spotify_vis_border_opacity.setMinimum(0)
        self.spotify_vis_border_opacity.setMaximum(100)
        spotify_vis_border_opacity_pct = int(
            self._default_float('spotify_visualizer', 'bar_border_opacity', 0.85) * 100
        )
        self.spotify_vis_border_opacity.setValue(spotify_vis_border_opacity_pct)
        self.spotify_vis_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.spotify_vis_border_opacity.setTickInterval(5)
        self.spotify_vis_border_opacity.valueChanged.connect(self._save_settings)
        spotify_vis_border_opacity_row.addWidget(self.spotify_vis_border_opacity)
        self.spotify_vis_border_opacity_label = QLabel(f"{spotify_vis_border_opacity_pct}%")
        self.spotify_vis_border_opacity.valueChanged.connect(
            lambda v: self.spotify_vis_border_opacity_label.setText(f"{v}%")
        )
        spotify_vis_border_opacity_row.addWidget(self.spotify_vis_border_opacity_label)
        spotify_vis_layout.addLayout(spotify_vis_border_opacity_row)

        spotify_vis_sensitivity_row = QHBoxLayout()
        self.spotify_vis_recommended = QCheckBox("Adaptive")
        self.spotify_vis_recommended.setChecked(
            self._default_bool('spotify_visualizer', 'adaptive_sensitivity', True)
        )
        self.spotify_vis_recommended.setToolTip(
            "When enabled, the visualizer uses the adaptive (v1.4) sensitivity baseline. Disable to adjust manually."
        )
        self.spotify_vis_recommended.stateChanged.connect(self._save_settings)
        self.spotify_vis_recommended.stateChanged.connect(lambda _: self._update_spotify_vis_sensitivity_enabled_state())
        spotify_vis_sensitivity_row.addWidget(self.spotify_vis_recommended)
        spotify_vis_sensitivity_row.addStretch()
        spotify_vis_layout.addLayout(spotify_vis_sensitivity_row)

        spotify_vis_sensitivity_slider_row = QHBoxLayout()
        spotify_vis_sensitivity_slider_row.addWidget(QLabel("Sensitivity:"))
        self.spotify_vis_sensitivity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.spotify_vis_sensitivity.setMinimum(25)
        self.spotify_vis_sensitivity.setMaximum(250)
        spotify_sens_slider = int(max(0.25, min(2.5, self._default_float('spotify_visualizer', 'sensitivity', 1.0))) * 100)
        self.spotify_vis_sensitivity.setValue(spotify_sens_slider)
        self.spotify_vis_sensitivity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.spotify_vis_sensitivity.setTickInterval(25)
        self.spotify_vis_sensitivity.valueChanged.connect(self._save_settings)
        spotify_vis_sensitivity_slider_row.addWidget(self.spotify_vis_sensitivity)
        self.spotify_vis_sensitivity_label = QLabel(f"{spotify_sens_slider / 100.0:.2f}x")
        self.spotify_vis_sensitivity.valueChanged.connect(
            lambda v: self.spotify_vis_sensitivity_label.setText(f"{v / 100.0:.2f}x")
        )
        spotify_vis_sensitivity_slider_row.addWidget(self.spotify_vis_sensitivity_label)
        spotify_vis_layout.addLayout(spotify_vis_sensitivity_slider_row)

        spotify_vis_floor_row = QHBoxLayout()
        self.spotify_vis_dynamic_floor = QCheckBox("Dynamic Noise Floor")
        self.spotify_vis_dynamic_floor.setChecked(
            self._default_bool('spotify_visualizer', 'dynamic_range_enabled', True)
        )
        self.spotify_vis_dynamic_floor.setToolTip(
            "Automatically adjust the noise floor based on recent Spotify loopback energy."
        )
        self.spotify_vis_dynamic_floor.setChecked(True)
        self.spotify_vis_dynamic_floor.stateChanged.connect(self._save_settings)
        self.spotify_vis_dynamic_floor.stateChanged.connect(
            lambda _: self._update_spotify_vis_floor_enabled_state()
        )
        spotify_vis_floor_row.addWidget(self.spotify_vis_dynamic_floor)
        spotify_vis_floor_row.addStretch()
        spotify_vis_layout.addLayout(spotify_vis_floor_row)

        spotify_vis_manual_floor_row = QHBoxLayout()
        spotify_vis_manual_floor_row.addWidget(QLabel("Manual Floor:"))
        self.spotify_vis_manual_floor = NoWheelSlider(Qt.Orientation.Horizontal)
        self.spotify_vis_manual_floor.setMinimum(12)   # 0.12
        self.spotify_vis_manual_floor.setMaximum(400)  # 4.00
        manual_floor_default = self._default_float('spotify_visualizer', 'manual_floor', 2.1)
        self.spotify_vis_manual_floor.setValue(int(max(0.12, min(4.0, manual_floor_default)) * 100))
        self.spotify_vis_manual_floor.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.spotify_vis_manual_floor.setTickInterval(10)
        self.spotify_vis_manual_floor.valueChanged.connect(self._save_settings)
        spotify_vis_manual_floor_row.addWidget(self.spotify_vis_manual_floor)
        self.spotify_vis_manual_floor_label = QLabel(f"{manual_floor_default:.2f}")
        self.spotify_vis_manual_floor.valueChanged.connect(
            lambda v: self.spotify_vis_manual_floor_label.setText(f"{v / 100.0:.2f}")
        )
        spotify_vis_manual_floor_row.addWidget(self.spotify_vis_manual_floor_label)
        spotify_vis_layout.addLayout(spotify_vis_manual_floor_row)

        # Ghosting controls: global enable, opacity and decay speed.
        spotify_vis_ghost_enable_row = QHBoxLayout()
        self.spotify_vis_ghost_enabled = QCheckBox("Enable Ghosting")
        self.spotify_vis_ghost_enabled.setChecked(
            self._default_bool('spotify_visualizer', 'ghosting_enabled', True)
        )
        self.spotify_vis_ghost_enabled.setToolTip(
            "When enabled, the visualizer draws trailing ghost bars above the current height."
        )
        self.spotify_vis_ghost_enabled.stateChanged.connect(self._save_settings)
        spotify_vis_ghost_enable_row.addWidget(self.spotify_vis_ghost_enabled)
        spotify_vis_ghost_enable_row.addStretch()
        spotify_vis_layout.addLayout(spotify_vis_ghost_enable_row)

        spotify_vis_ghost_opacity_row = QHBoxLayout()
        spotify_vis_ghost_opacity_row.addWidget(QLabel("Ghost Opacity:"))
        self.spotify_vis_ghost_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.spotify_vis_ghost_opacity.setMinimum(0)
        self.spotify_vis_ghost_opacity.setMaximum(100)
        ghost_alpha_pct = int(self._default_float('spotify_visualizer', 'ghost_alpha', 0.4) * 100)
        self.spotify_vis_ghost_opacity.setValue(ghost_alpha_pct)
        self.spotify_vis_ghost_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.spotify_vis_ghost_opacity.setTickInterval(5)
        self.spotify_vis_ghost_opacity.valueChanged.connect(self._save_settings)
        spotify_vis_ghost_opacity_row.addWidget(self.spotify_vis_ghost_opacity)
        self.spotify_vis_ghost_opacity_label = QLabel(f"{ghost_alpha_pct}%")
        self.spotify_vis_ghost_opacity.valueChanged.connect(
            lambda v: self.spotify_vis_ghost_opacity_label.setText(f"{v}%")
        )
        spotify_vis_ghost_opacity_row.addWidget(self.spotify_vis_ghost_opacity_label)
        spotify_vis_layout.addLayout(spotify_vis_ghost_opacity_row)

        spotify_vis_ghost_decay_row = QHBoxLayout()
        spotify_vis_ghost_decay_row.addWidget(QLabel("Ghost Decay Speed:"))
        self.spotify_vis_ghost_decay = NoWheelSlider(Qt.Orientation.Horizontal)
        self.spotify_vis_ghost_decay.setMinimum(10)   # 0.10x
        self.spotify_vis_ghost_decay.setMaximum(100)  # 1.00x
        ghost_decay_slider = int(self._default_float('spotify_visualizer', 'ghost_decay', 0.4) * 100)
        self.spotify_vis_ghost_decay.setValue(max(10, min(100, ghost_decay_slider)))
        self.spotify_vis_ghost_decay.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.spotify_vis_ghost_decay.setTickInterval(5)
        self.spotify_vis_ghost_decay.valueChanged.connect(self._save_settings)
        spotify_vis_ghost_decay_row.addWidget(self.spotify_vis_ghost_decay)
        self.spotify_vis_ghost_decay_label = QLabel(f"{self.spotify_vis_ghost_decay.value() / 100.0:.2f}x")
        self.spotify_vis_ghost_decay.valueChanged.connect(
            lambda v: self.spotify_vis_ghost_decay_label.setText(f"{v / 100.0:.2f}x")
        )
        spotify_vis_ghost_decay_row.addWidget(self.spotify_vis_ghost_decay_label)
        spotify_vis_layout.addLayout(spotify_vis_ghost_decay_row)

        self._media_container = QWidget()
        media_container_layout = QVBoxLayout(self._media_container)
        media_container_layout.setContentsMargins(0, 20, 0, 0)
        media_container_layout.addWidget(media_group)
        media_container_layout.addWidget(spotify_vis_group)
        layout.addWidget(self._media_container)

        # Reddit widget group
        reddit_group = QGroupBox("Reddit Widget")
        reddit_layout = QVBoxLayout(reddit_group)

        self.reddit_enabled = QCheckBox("Enable Reddit Widget")
        self.reddit_enabled.setToolTip(
            "Shows a small list of posts from a subreddit using Reddit's public JSON feed."
        )
        self.reddit_enabled.setChecked(self._default_bool('reddit', 'enabled', True))
        self.reddit_enabled.stateChanged.connect(self._save_settings)
        self.reddit_enabled.stateChanged.connect(self._update_stack_status)
        reddit_layout.addWidget(self.reddit_enabled)

        reddit_info = QLabel(
            "Links open in your browser and only respond while Ctrl-held or hard-exit "
            "interaction modes are active."
        )
        reddit_info.setWordWrap(True)
        reddit_info.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        reddit_layout.addWidget(reddit_info)

        self.reddit_exit_on_click = QCheckBox("Exit screensaver when Reddit links are opened")
        self.reddit_exit_on_click.setToolTip(
            "When enabled, clicking a Reddit link will exit the screensaver and open the link in your browser."
        )
        self.reddit_exit_on_click.setChecked(self._default_bool('reddit', 'exit_on_click', True))
        self.reddit_exit_on_click.stateChanged.connect(self._save_settings)
        reddit_layout.addWidget(self.reddit_exit_on_click)

        # Subreddit name
        reddit_sub_row = QHBoxLayout()
        reddit_sub_row.addWidget(QLabel("Subreddit:"))
        self.reddit_subreddit = QLineEdit()
        default_subreddit = self._default_str('reddit', 'subreddit', 'wallpapers')
        self.reddit_subreddit.setText(default_subreddit)
        self.reddit_subreddit.setPlaceholderText("e.g. wallpapers")
        self.reddit_subreddit.setToolTip("Enter the subreddit name (without r/ prefix)")
        self.reddit_subreddit.textChanged.connect(self._save_settings)
        reddit_sub_row.addWidget(self.reddit_subreddit)
        reddit_layout.addLayout(reddit_sub_row)

        # Item count
        reddit_items_row = QHBoxLayout()
        reddit_items_row.addWidget(QLabel("Items:"))
        self.reddit_items = QComboBox()
        # Expose 4/10/20 item modes (legacy configs <=5 map to the 4-item option).
        self.reddit_items.addItems(["4", "10", "20"])
        self.reddit_items.setToolTip("Number of Reddit posts to display in the widget")
        self.reddit_items.currentTextChanged.connect(self._save_settings)
        self.reddit_items.currentTextChanged.connect(self._update_stack_status)
        reddit_items_row.addWidget(self.reddit_items)
        reddit_limit_default = self._default_int('reddit', 'limit', 10)
        if reddit_limit_default <= 5:
            default_items_text = "4"
        elif reddit_limit_default >= 20:
            default_items_text = "20"
        else:
            default_items_text = "10"
        self._set_combo_text(self.reddit_items, default_items_text)
        reddit_items_row.addStretch()
        reddit_layout.addLayout(reddit_items_row)

        # Position
        reddit_pos_row = QHBoxLayout()
        reddit_pos_row.addWidget(QLabel("Position:"))
        self.reddit_position = QComboBox()
        self.reddit_position.addItems([
            "Top Left", "Top Center", "Top Right",
            "Middle Left", "Center", "Middle Right",
            "Bottom Left", "Bottom Center", "Bottom Right",
        ])
        self.reddit_position.setToolTip("Screen position for the Reddit widget (9-grid layout)")
        self.reddit_position.currentTextChanged.connect(self._save_settings)
        self.reddit_position.currentTextChanged.connect(self._update_stack_status)
        reddit_pos_row.addWidget(self.reddit_position)
        self._set_combo_text(self.reddit_position, self._default_str('reddit', 'position', 'Bottom Right'))
        self.reddit_stack_status = QLabel("")
        self.reddit_stack_status.setMinimumWidth(100)
        reddit_pos_row.addWidget(self.reddit_stack_status)
        reddit_pos_row.addStretch()
        reddit_layout.addLayout(reddit_pos_row)

        # Display (monitor selection)
        reddit_disp_row = QHBoxLayout()
        reddit_disp_row.addWidget(QLabel("Display:"))
        self.reddit_monitor_combo = QComboBox()
        self.reddit_monitor_combo.addItems(["ALL", "1", "2", "3"])
        self.reddit_monitor_combo.setToolTip("Which monitor(s) to show the Reddit widget on")
        self.reddit_monitor_combo.currentTextChanged.connect(self._save_settings)
        self.reddit_monitor_combo.currentTextChanged.connect(self._update_stack_status)
        reddit_disp_row.addWidget(self.reddit_monitor_combo)
        reddit_monitor_default = self._widget_default('reddit', 'monitor', 'ALL')
        self._set_combo_text(self.reddit_monitor_combo, str(reddit_monitor_default))
        reddit_disp_row.addStretch()
        reddit_layout.addLayout(reddit_disp_row)

        # Font family
        reddit_font_family_row = QHBoxLayout()
        reddit_font_family_row.addWidget(QLabel("Font:"))
        self.reddit_font_combo = QFontComboBox()
        default_reddit_font = self._default_str('reddit', 'font_family', 'Segoe UI')
        self.reddit_font_combo.setCurrentFont(QFont(default_reddit_font))
        self.reddit_font_combo.setMinimumWidth(220)
        self.reddit_font_combo.setToolTip("Font family for Reddit post titles")
        self.reddit_font_combo.currentFontChanged.connect(self._save_settings)
        reddit_font_family_row.addWidget(self.reddit_font_combo)
        reddit_font_family_row.addStretch()
        reddit_layout.addLayout(reddit_font_family_row)

        # Font size
        reddit_font_row = QHBoxLayout()
        reddit_font_row.addWidget(QLabel("Font Size:"))
        self.reddit_font_size = QSpinBox()
        self.reddit_font_size.setRange(10, 72)
        self.reddit_font_size.setValue(self._default_int('reddit', 'font_size', 18))
        self.reddit_font_size.setAccelerated(True)
        self.reddit_font_size.setToolTip("Font size for Reddit post titles (10-72px)")
        self.reddit_font_size.valueChanged.connect(self._save_settings)
        self.reddit_font_size.valueChanged.connect(self._update_stack_status)
        reddit_font_row.addWidget(self.reddit_font_size)
        reddit_font_row.addWidget(QLabel("px"))
        reddit_font_row.addStretch()
        reddit_layout.addLayout(reddit_font_row)

        # Margin
        reddit_margin_row = QHBoxLayout()
        reddit_margin_row.addWidget(QLabel("Margin:"))
        self.reddit_margin = QSpinBox()
        self.reddit_margin.setRange(0, 100)
        self.reddit_margin.setValue(self._default_int('reddit', 'margin', 30))
        self.reddit_margin.setAccelerated(True)
        self.reddit_margin.valueChanged.connect(self._save_settings)
        reddit_margin_row.addWidget(self.reddit_margin)
        reddit_margin_row.addWidget(QLabel("px"))
        reddit_margin_row.addStretch()
        reddit_layout.addLayout(reddit_margin_row)

        # Text color
        reddit_color_row = QHBoxLayout()
        reddit_color_row.addWidget(QLabel("Text Color:"))
        self.reddit_color_btn = QPushButton("Choose Color...")
        self.reddit_color_btn.clicked.connect(self._choose_reddit_color)
        reddit_color_row.addWidget(self.reddit_color_btn)
        reddit_color_row.addStretch()
        reddit_layout.addLayout(reddit_color_row)

        # Background frame
        self.reddit_show_background = QCheckBox("Show Background Frame")
        self.reddit_show_background.setChecked(self._default_bool('reddit', 'show_background', True))
        self.reddit_show_background.stateChanged.connect(self._save_settings)
        reddit_layout.addWidget(self.reddit_show_background)

        # Intense shadow
        self.reddit_intense_shadow = QCheckBox("Intense Shadows")
        self.reddit_intense_shadow.setChecked(self._default_bool('reddit', 'intense_shadow', True))
        self.reddit_intense_shadow.setToolTip(
            "Doubles shadow blur, opacity, and offset for dramatic effect on large displays."
        )
        self.reddit_intense_shadow.stateChanged.connect(self._save_settings)
        reddit_layout.addWidget(self.reddit_intense_shadow)

        self.reddit_show_separators = QCheckBox("Show separator lines between posts")
        self.reddit_show_separators.setChecked(self._default_bool('reddit', 'show_separators', True))
        self.reddit_show_separators.stateChanged.connect(self._save_settings)
        reddit_layout.addWidget(self.reddit_show_separators)

        # Background opacity
        reddit_opacity_row = QHBoxLayout()
        reddit_opacity_row.addWidget(QLabel("Background Opacity:"))
        self.reddit_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.reddit_bg_opacity.setMinimum(0)
        self.reddit_bg_opacity.setMaximum(100)
        reddit_bg_opacity_pct = int(self._default_float('reddit', 'bg_opacity', 0.6) * 100)
        self.reddit_bg_opacity.setValue(reddit_bg_opacity_pct)
        self.reddit_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.reddit_bg_opacity.setTickInterval(10)
        self.reddit_bg_opacity.valueChanged.connect(self._save_settings)
        reddit_opacity_row.addWidget(self.reddit_bg_opacity)
        self.reddit_bg_opacity_label = QLabel(f"{reddit_bg_opacity_pct}%")
        self.reddit_bg_opacity.valueChanged.connect(
            lambda v: self.reddit_bg_opacity_label.setText(f"{v}%")
        )
        reddit_opacity_row.addWidget(self.reddit_bg_opacity_label)
        reddit_layout.addLayout(reddit_opacity_row)

        # Background color
        reddit_bg_color_row = QHBoxLayout()
        reddit_bg_color_row.addWidget(QLabel("Background Color:"))
        self.reddit_bg_color_btn = QPushButton("Choose Color...")
        self.reddit_bg_color_btn.clicked.connect(self._choose_reddit_bg_color)
        reddit_bg_color_row.addWidget(self.reddit_bg_color_btn)
        reddit_bg_color_row.addStretch()
        reddit_layout.addLayout(reddit_bg_color_row)

        # Border color
        reddit_border_color_row = QHBoxLayout()
        reddit_border_color_row.addWidget(QLabel("Border Color:"))
        self.reddit_border_color_btn = QPushButton("Choose Color...")
        self.reddit_border_color_btn.clicked.connect(self._choose_reddit_border_color)
        reddit_border_color_row.addWidget(self.reddit_border_color_btn)
        reddit_border_color_row.addStretch()
        reddit_layout.addLayout(reddit_border_color_row)

        # Border opacity
        reddit_border_opacity_row = QHBoxLayout()
        reddit_border_opacity_row.addWidget(QLabel("Border Opacity:"))
        self.reddit_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.reddit_border_opacity.setMinimum(0)
        self.reddit_border_opacity.setMaximum(100)
        reddit_border_opacity_pct = int(self._default_float('reddit', 'border_opacity', 1.0) * 100)
        self.reddit_border_opacity.setValue(reddit_border_opacity_pct)
        self.reddit_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.reddit_border_opacity.setTickInterval(10)
        self.reddit_border_opacity.valueChanged.connect(self._save_settings)
        reddit_border_opacity_row.addWidget(self.reddit_border_opacity)
        self.reddit_border_opacity_label = QLabel(f"{reddit_border_opacity_pct}%")
        self.reddit_border_opacity.valueChanged.connect(
            lambda v: self.reddit_border_opacity_label.setText(f"{v}%")
        )
        reddit_border_opacity_row.addWidget(self.reddit_border_opacity_label)
        reddit_layout.addLayout(reddit_border_opacity_row)

        # Reddit 2 - simplified second widget (subreddit + items only, inherits rest)
        reddit2_label = QLabel("Reddit 2 (inherits styling from Reddit 1):")
        reddit2_label.setStyleSheet("color: #aaaaaa; font-size: 11px; margin-top: 8px;")
        reddit_layout.addWidget(reddit2_label)
        
        reddit2_row = QHBoxLayout()
        self.reddit2_enabled = QCheckBox("Enable Reddit 2")
        self.reddit2_enabled.stateChanged.connect(self._save_settings)
        self.reddit2_enabled.stateChanged.connect(self._update_stack_status)
        reddit2_row.addWidget(self.reddit2_enabled)
        reddit2_row.addWidget(QLabel("Subreddit:"))
        self.reddit2_subreddit = QLineEdit()
        self.reddit2_subreddit.setPlaceholderText("e.g. earthporn")
        self.reddit2_subreddit.textChanged.connect(self._save_settings)
        self.reddit2_subreddit.setMaximumWidth(150)
        reddit2_row.addWidget(self.reddit2_subreddit)
        reddit2_row.addWidget(QLabel("Items:"))
        self.reddit2_items = QComboBox()
        self.reddit2_items.addItems(["4", "10", "20"])
        self.reddit2_items.setMaximumWidth(60)
        self.reddit2_items.currentTextChanged.connect(self._save_settings)
        self.reddit2_items.currentTextChanged.connect(self._update_stack_status)
        reddit2_row.addWidget(self.reddit2_items)
        reddit2_row.addWidget(QLabel("Position:"))
        self.reddit2_position = QComboBox()
        self.reddit2_position.addItems(["Top Left", "Top Center", "Top Right", "Middle Left", "Center", "Middle Right", "Bottom Left", "Bottom Center", "Bottom Right"])
        self.reddit2_position.setMaximumWidth(120)
        self.reddit2_position.currentTextChanged.connect(self._save_settings)
        self.reddit2_position.currentTextChanged.connect(self._update_stack_status)
        reddit2_row.addWidget(self.reddit2_position)
        self.reddit2_stack_status = QLabel("")
        self.reddit2_stack_status.setMinimumWidth(80)
        reddit2_row.addWidget(self.reddit2_stack_status)
        reddit2_row.addWidget(QLabel("Display:"))
        self.reddit2_monitor_combo = QComboBox()
        self.reddit2_monitor_combo.addItems(["ALL", "1", "2", "3"])
        self.reddit2_monitor_combo.setMaximumWidth(60)
        self.reddit2_monitor_combo.currentTextChanged.connect(self._save_settings)
        self.reddit2_monitor_combo.currentTextChanged.connect(self._update_stack_status)
        reddit2_row.addWidget(self.reddit2_monitor_combo)
        reddit2_row.addStretch()
        reddit_layout.addLayout(reddit2_row)

        self._reddit_container = QWidget()
        reddit_container_layout = QVBoxLayout(self._reddit_container)
        reddit_container_layout.setContentsMargins(0, 20, 0, 0)
        reddit_container_layout.addWidget(reddit_group)
        layout.addWidget(self._reddit_container)

        # NOTE: Gmail widget removed - archived in archive/gmail_feature/
        # Google OAuth verification requirements block unverified apps from using
        # sensitive Gmail scopes. See archive/gmail_feature/RESTORE_GMAIL.md

        layout.addStretch()

        # Set scroll area widget and add to main layout
        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        # Unified styling for +/- spin controls so font size, padding and
        # arrow alignment match the Display and Transitions tabs.
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
            QToolTip {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #ffffff;
                padding: 6px;
                font-size: 12px;
            }
            """
        )

        # Default to "Clocks" subtab
        self._on_subtab_changed(0)

    def _on_subtab_changed(self, subtab_id: int) -> None:
        """Show/hide widget sections based on selected subtab."""
        self._current_subtab = int(subtab_id)
        try:
            self._clocks_container.setVisible(subtab_id == 0)
            self._weather_container.setVisible(subtab_id == 1)
            self._media_container.setVisible(subtab_id == 2)
            self._reddit_container.setVisible(subtab_id == 3)
        except Exception:
            # If containers are not yet initialized, ignore
            pass

    def get_view_state(self) -> Dict[str, Any]:
        state: Dict[str, Any] = {"subtab": int(getattr(self, "_current_subtab", 0))}
        scroll = getattr(self, "_scroll_area", None)
        if scroll is not None:
            try:
                state["scroll"] = int(scroll.verticalScrollBar().value())
            except Exception as e:
                logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
        return state

    def restore_view_state(self, state: Dict[str, Any]) -> None:
        if not isinstance(state, dict):
            return
        subtab = state.get("subtab")
        try:
            subtab_id = int(subtab)
        except (TypeError, ValueError):
            subtab_id = 0
        button = self._subtab_group.button(subtab_id)
        if button is not None:
            button.setChecked(True)
            self._on_subtab_changed(subtab_id)
        scroll_value = state.get("scroll")
        if scroll_value is not None:
            scroll = getattr(self, "_scroll_area", None)
            if scroll is not None:
                try:
                    scroll.verticalScrollBar().setValue(int(scroll_value))
                except Exception as e:
                    logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
    
    def _load_settings(self) -> None:
        """Load settings from settings manager."""
        # Block all signals during load to prevent unintended saves from valueChanged/stateChanged
        blockers = []
        try:
            widgets_value = self._settings.get('widgets', {})
            if isinstance(widgets_value, dict):
                widgets = dict(widgets_value)
            else:
                widgets = {}

            for w in [
                getattr(self, 'widget_shadows_enabled', None),
                getattr(self, 'clock_enabled', None),
                getattr(self, 'clock_format', None),
                getattr(self, 'clock_seconds', None),
                getattr(self, 'clock_timezone', None),
                getattr(self, 'clock_show_tz', None),
                getattr(self, 'clock_position', None),
                getattr(self, 'clock_font_combo', None),
                getattr(self, 'clock_font_size', None),
                getattr(self, 'clock_margin', None),
                getattr(self, 'clock_show_background', None),
                getattr(self, 'clock_bg_opacity', None),
                getattr(self, 'clock_border_opacity', None),
                getattr(self, 'clock_bg_color_btn', None),
                getattr(self, 'clock_border_color_btn', None),
                getattr(self, 'clock2_enabled', None),
                getattr(self, 'clock2_timezone', None),
                getattr(self, 'clock2_monitor_combo', None),
                getattr(self, 'clock3_enabled', None),
                getattr(self, 'clock3_timezone', None),
                getattr(self, 'clock3_monitor_combo', None),
                getattr(self, 'weather_enabled', None),
                getattr(self, 'weather_location', None),
                getattr(self, 'weather_position', None),
                getattr(self, 'weather_font_combo', None),
                getattr(self, 'weather_font_size', None),
                getattr(self, 'weather_show_forecast', None),
                getattr(self, 'weather_show_background', None),
                getattr(self, 'weather_bg_opacity', None),
                getattr(self, 'weather_bg_color_btn', None),
                getattr(self, 'weather_border_color_btn', None),
                getattr(self, 'weather_border_opacity', None),
                getattr(self, 'weather_margin', None),
                getattr(self, 'media_enabled', None),
                getattr(self, 'media_position', None),
                getattr(self, 'media_monitor_combo', None),
                getattr(self, 'media_font_combo', None),
                getattr(self, 'media_font_size', None),
                getattr(self, 'media_margin', None),
                getattr(self, 'media_show_background', None),
                getattr(self, 'media_bg_opacity', None),
                getattr(self, 'media_bg_color_btn', None),
                getattr(self, 'media_border_color_btn', None),
                getattr(self, 'media_border_opacity', None),
                getattr(self, 'media_artwork_size', None),
                getattr(self, 'media_rounded_artwork', None),
                getattr(self, 'media_show_header_frame', None),
                getattr(self, 'media_show_controls', None),
                getattr(self, 'media_spotify_volume_enabled', None),
                getattr(self, 'spotify_vis_enabled', None),
                getattr(self, 'spotify_vis_bar_count', None),
                getattr(self, 'spotify_vis_border_opacity', None),
                getattr(self, 'spotify_vis_ghost_enabled', None),
                getattr(self, 'spotify_vis_ghost_opacity', None),
                getattr(self, 'spotify_vis_ghost_decay', None),
                getattr(self, 'reddit_enabled', None),
                getattr(self, 'reddit_subreddit', None),
                getattr(self, 'reddit_items', None),
                getattr(self, 'reddit_position', None),
                getattr(self, 'reddit_monitor_combo', None),
                getattr(self, 'reddit_font_combo', None),
                getattr(self, 'reddit_font_size', None),
                getattr(self, 'reddit_margin', None),
                getattr(self, 'reddit_show_background', None),
                getattr(self, 'reddit_show_separators', None),
                getattr(self, 'reddit_bg_opacity', None),
                getattr(self, 'reddit_bg_color_btn', None),
                getattr(self, 'reddit_color_btn', None),
                getattr(self, 'reddit_border_color_btn', None),
                getattr(self, 'reddit_border_opacity', None),
                getattr(self, 'reddit2_enabled', None),
                getattr(self, 'reddit2_subreddit', None),
                getattr(self, 'reddit2_items', None),
                getattr(self, 'reddit2_position', None),
                getattr(self, 'reddit2_monitor_combo', None),
                getattr(self, 'reddit_exit_on_click', None),
            ]:
                if w is not None and hasattr(w, 'blockSignals'):
                    w.blockSignals(True)
                    blockers.append(w)

            # Global widget shadow settings
            shadows_config = widgets.get('shadows', {}) if isinstance(widgets, dict) else {}
            if isinstance(shadows_config, dict):
                shadows_enabled_raw = shadows_config.get('enabled', True)
                enabled = SettingsManager.to_bool(shadows_enabled_raw, True)
                self.widget_shadows_enabled.setChecked(enabled)
            else:
                self.widget_shadows_enabled.setChecked(True)

            # Load clock settings
            clock_config = widgets.get('clock', {})
            self.clock_enabled.setChecked(self._config_bool('clock', clock_config, 'enabled', True))
            
            format_raw = self._config_str('clock', clock_config, 'format', '24h').lower()
            format_text = "12 Hour" if format_raw == '12h' else "24 Hour"
            index = self.clock_format.findText(format_text)
            if index >= 0:
                self.clock_format.setCurrentIndex(index)
            
            self.clock_seconds.setChecked(self._config_bool('clock', clock_config, 'show_seconds', True))
            
            # Load timezone settings
            timezone_str = self._config_str('clock', clock_config, 'timezone', 'local')
            tz_index = self.clock_timezone.findData(timezone_str)
            if tz_index >= 0:
                self.clock_timezone.setCurrentIndex(tz_index)
            
            self.clock_show_tz.setChecked(self._config_bool('clock', clock_config, 'show_timezone', True))

            # Analogue mode configuration (main clock only). Secondary clocks
            # inherit style from Clock 1 in DisplayWidget._setup_widgets().
            display_mode = self._config_str('clock', clock_config, 'display_mode', 'analog').lower()
            self.clock_analog_mode.setChecked(display_mode == 'analog')

            self.clock_show_numerals.setChecked(self._config_bool('clock', clock_config, 'show_numerals', True))
            self.clock_analog_shadow.setChecked(self._config_bool('clock', clock_config, 'analog_face_shadow', True))
            self.clock_analog_shadow_intense.setChecked(
                self._config_bool('clock', clock_config, 'analog_shadow_intense', False)
            )
            self.clock_digital_shadow_intense.setChecked(
                self._config_bool('clock', clock_config, 'digital_shadow_intense', False)
            )
            
            position = self._config_str('clock', clock_config, 'position', 'Top Right')
            index = self.clock_position.findText(position)
            if index >= 0:
                self.clock_position.setCurrentIndex(index)
            
            self.clock_font_combo.setCurrentFont(QFont(self._config_str('clock', clock_config, 'font_family', 'Segoe UI')))
            self.clock_font_size.setValue(self._config_int('clock', clock_config, 'font_size', 48))
            self.clock_margin.setValue(self._config_int('clock', clock_config, 'margin', 30))
            self.clock_show_background.setChecked(self._config_bool('clock', clock_config, 'show_background', True))
            opacity_pct = int(self._config_float('clock', clock_config, 'bg_opacity', 0.6) * 100)
            self.clock_bg_opacity.setValue(opacity_pct)
            self.clock_opacity_label.setText(f"{opacity_pct}%")
            # Monitor selection
            monitor_sel = clock_config.get('monitor', self._widget_default('clock', 'monitor', 'ALL'))
            mon_text = str(monitor_sel) if isinstance(monitor_sel, (int, str)) else 'ALL'
            idx = self.clock_monitor_combo.findText(mon_text)
            if idx >= 0:
                self.clock_monitor_combo.setCurrentIndex(idx)
            
            # Load clock color
            color_data = clock_config.get('color', self._widget_default('clock', 'color', [255, 255, 255, 230]))
            self._clock_color = QColor(*color_data)
            bg_color_data = clock_config.get('bg_color', self._widget_default('clock', 'bg_color', [64, 64, 64, 255]))
            try:
                self._clock_bg_color = QColor(*bg_color_data)
            except Exception as e:
                logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
                self._clock_bg_color = QColor(64, 64, 64, 255)
            border_color_data = clock_config.get('border_color', self._widget_default('clock', 'border_color', [128, 128, 128, 255]))
            try:
                self._clock_border_color = QColor(*border_color_data)
            except Exception as e:
                logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
                self._clock_border_color = QColor(128, 128, 128, 255)
            border_opacity_pct = int(clock_config.get('border_opacity', self._default_float('clock', 'border_opacity', 0.8)) * 100)
            self.clock_border_opacity.setValue(border_opacity_pct)
            self.clock_border_opacity_label.setText(f"{border_opacity_pct}%")

            clock2_config = widgets.get('clock2', {})
            self.clock2_enabled.setChecked(clock2_config.get('enabled', False))
            monitor2 = clock2_config.get('monitor', 'ALL')
            mon2_text = str(monitor2) if isinstance(monitor2, (int, str)) else 'ALL'
            idx2 = self.clock2_monitor_combo.findText(mon2_text)
            if idx2 >= 0:
                self.clock2_monitor_combo.setCurrentIndex(idx2)
            timezone2 = clock2_config.get('timezone', 'UTC')
            tz2_index = self.clock2_timezone.findData(timezone2)
            if tz2_index >= 0:
                self.clock2_timezone.setCurrentIndex(tz2_index)

            clock3_config = widgets.get('clock3', {})
            self.clock3_enabled.setChecked(clock3_config.get('enabled', False))
            monitor3 = clock3_config.get('monitor', 'ALL')
            mon3_text = str(monitor3) if isinstance(monitor3, (int, str)) else 'ALL'
            idx3 = self.clock3_monitor_combo.findText(mon3_text)
            if idx3 >= 0:
                self.clock3_monitor_combo.setCurrentIndex(idx3)
            timezone3 = clock3_config.get('timezone', 'UTC+01:00')
            tz3_index = self.clock3_timezone.findData(timezone3)
            if tz3_index >= 0:
                self.clock3_timezone.setCurrentIndex(tz3_index)

            # Load weather settings
            weather_config = widgets.get('weather', {})

            # If the location is still the canonical placeholder ("New York"),
            # try to derive a closer default from the local timezone. This is
            # a one-shot override on load; once a user has picked a specific
            # city it will be preserved.
            try:
                raw_loc = str(weather_config.get('location', 'New York') or 'New York')
                if raw_loc == 'New York':
                    tz = get_local_timezone()
                    derived_city = None
                    if isinstance(tz, str) and '/' in tz:
                        # Use the last component of Region/City as a best-effort
                        # city name (e.g. "Africa/Johannesburg" -> "Johannesburg").
                        candidate = tz.split('/')[-1].strip()
                        candidate = candidate.replace('_', ' ')
                        if candidate and candidate.lower() not in {"local", "utc"}:
                            derived_city = candidate

                    if derived_city:
                        weather_config['location'] = derived_city
                        widgets['weather'] = weather_config
                        self._settings.set('widgets', widgets)
                        self._settings.save()
            except Exception:
                logger.debug("Failed to auto-derive weather location from timezone", exc_info=True)

            self.weather_enabled.setChecked(self._config_bool('weather', weather_config, 'enabled', True))
            self.weather_location.setText(self._config_str('weather', weather_config, 'location', ''))
            
            weather_pos = self._config_str('weather', weather_config, 'position', 'Top Left')
            index = self.weather_position.findText(weather_pos)
            if index >= 0:
                self.weather_position.setCurrentIndex(index)
            
            self.weather_font_combo.setCurrentFont(QFont(self._config_str('weather', weather_config, 'font_family', 'Segoe UI')))
            self.weather_font_size.setValue(self._config_int('weather', weather_config, 'font_size', 24))
            self.weather_show_forecast.setChecked(self._config_bool('weather', weather_config, 'show_forecast', True))
            self.weather_show_details_row.setChecked(self._config_bool('weather', weather_config, 'show_details_row', False))
            icon_alignment_value = (self._config_str('weather', weather_config, 'animated_icon_alignment', 'NONE') or 'NONE').upper()
            self._set_combo_data(self.weather_icon_alignment, icon_alignment_value)
            self.weather_icon_animated.setChecked(
                self._config_bool('weather', weather_config, 'animated_icon_enabled', True)
            )
            self.weather_desaturate_icon.setChecked(
                self._config_bool('weather', weather_config, 'desaturate_animated_icon', False)
            )
            self.weather_intense_shadow.setChecked(
                self._config_bool('weather', weather_config, 'intense_shadow', True)
            )
            self.weather_show_background.setChecked(self._config_bool('weather', weather_config, 'show_background', True))
            weather_opacity_pct = int(self._config_float('weather', weather_config, 'bg_opacity', 0.6) * 100)
            self.weather_bg_opacity.setValue(weather_opacity_pct)
            self.weather_opacity_label.setText(f"{weather_opacity_pct}%")
            
            # Load weather color
            weather_color_data = weather_config.get('color', self._widget_default('weather', 'color', [255, 255, 255, 230]))
            self._weather_color = QColor(*weather_color_data)
            # Load weather background and border colors
            bg_color_data = weather_config.get('bg_color', self._widget_default('weather', 'bg_color', [64, 64, 64, 255]))
            try:
                self._weather_bg_color = QColor(*bg_color_data)
            except Exception:
                logger.debug("[WIDGETS_TAB] Exception suppressed: invalid weather bg color", exc_info=True)
                self._weather_bg_color = QColor(64, 64, 64, 255)
            border_color_data = weather_config.get('border_color', self._widget_default('weather', 'border_color', [128, 128, 128, 255]))
            try:
                self._weather_border_color = QColor(*border_color_data)
            except Exception:
                logger.debug("[WIDGETS_TAB] Exception suppressed: invalid weather border color", exc_info=True)
                self._weather_border_color = QColor(128, 128, 128, 255)
            border_opacity_pct = int(self._config_float('weather', weather_config, 'border_opacity', 1.0) * 100)
            self.weather_border_opacity.setValue(border_opacity_pct)
            self.weather_border_opacity_label.setText(f"{border_opacity_pct}%")
            # Margin
            self.weather_margin.setValue(self._config_int('weather', weather_config, 'margin', 30))
            # Monitor selection
            w_monitor_sel = weather_config.get('monitor', self._widget_default('weather', 'monitor', 'ALL'))
            w_mon_text = str(w_monitor_sel) if isinstance(w_monitor_sel, (int, str)) else 'ALL'
            idx = self.weather_monitor_combo.findText(w_mon_text)
            if idx >= 0:
                self.weather_monitor_combo.setCurrentIndex(idx)
            
            # Load media settings
            media_config = widgets.get('media', {})
            self.media_enabled.setChecked(self._config_bool('media', media_config, 'enabled', True))

            media_pos = self._config_str('media', media_config, 'position', 'Bottom Left')
            index = self.media_position.findText(media_pos)
            if index >= 0:
                self.media_position.setCurrentIndex(index)

            self.media_font_combo.setCurrentFont(QFont(self._config_str('media', media_config, 'font_family', 'Segoe UI')))
            self.media_font_size.setValue(self._config_int('media', media_config, 'font_size', 20))
            self.media_margin.setValue(self._config_int('media', media_config, 'margin', 30))
            self.media_show_background.setChecked(self._config_bool('media', media_config, 'show_background', True))
            self.media_intense_shadow.setChecked(self._config_bool('media', media_config, 'intense_shadow', True))
            media_opacity_pct = int(self._config_float('media', media_config, 'bg_opacity', 0.6) * 100)
            self.media_bg_opacity.setValue(media_opacity_pct)
            self.media_bg_opacity_label.setText(f"{media_opacity_pct}%")

            # Artwork size and controls visibility
            self._media_artwork_size = self._config_int('media', media_config, 'artwork_size', 200)
            self.media_artwork_size.setValue(self._media_artwork_size)

            self.media_rounded_artwork.setChecked(
                self._config_bool('media', media_config, 'rounded_artwork_border', True)
            )

            self.media_show_header_frame.setChecked(
                self._config_bool('media', media_config, 'show_header_frame', True)
            )

            self.media_show_controls.setChecked(self._config_bool('media', media_config, 'show_controls', True))

            self.media_spotify_volume_enabled.setChecked(
                self._config_bool('media', media_config, 'spotify_volume_enabled', True)
            )

            # Load media colors
            media_color_data = media_config.get('color', self._widget_default('media', 'color', [255, 255, 255, 230]))
            self._media_color = QColor(*media_color_data)
            media_bg_color_data = media_config.get('bg_color', self._widget_default('media', 'bg_color', [35, 35, 35, 255]))
            try:
                self._media_bg_color = QColor(*media_bg_color_data)
            except Exception:
                logger.debug("[WIDGETS_TAB] Exception suppressed: invalid media bg color", exc_info=True)
                self._media_bg_color = QColor(35, 35, 35, 255)
            media_border_color_data = media_config.get('border_color', self._widget_default('media', 'border_color', [255, 255, 255, 255]))
            try:
                self._media_border_color = QColor(*media_border_color_data)
            except Exception:
                logger.debug("[WIDGETS_TAB] Exception suppressed: invalid media border color", exc_info=True)
                self._media_border_color = QColor(255, 255, 255, 255)
            media_border_opacity_pct = int(self._config_float('media', media_config, 'border_opacity', 1.0) * 100)
            self.media_border_opacity.setValue(media_border_opacity_pct)
            self.media_border_opacity_label.setText(f"{media_border_opacity_pct}%")

            volume_fill_data = media_config.get('spotify_volume_fill_color', self._widget_default('media', 'spotify_volume_fill_color', [255, 255, 255, 230]))
            try:
                self._media_volume_fill_color = QColor(*volume_fill_data)
            except Exception:
                logger.debug("[WIDGETS_TAB] Exception suppressed: invalid media volume fill color", exc_info=True)
                self._media_volume_fill_color = QColor(255, 255, 255, 230)

            m_monitor_sel = media_config.get('monitor', self._widget_default('media', 'monitor', 'ALL'))
            m_mon_text = str(m_monitor_sel) if isinstance(m_monitor_sel, (int, str)) else 'ALL'
            midx = self.media_monitor_combo.findText(m_mon_text)
            if midx >= 0:
                self.media_monitor_combo.setCurrentIndex(midx)

            # Load Spotify Beat Visualizer settings
            spotify_vis_config = widgets.get('spotify_visualizer', {})
            self.spotify_vis_enabled.setChecked(
                self._config_bool('spotify_visualizer', spotify_vis_config, 'enabled', True)
            )
            
            # Mode selection removed - only spectrum mode supported
            
            bar_count = self._config_int('spotify_visualizer', spotify_vis_config, 'bar_count', 32)
            self.spotify_vis_bar_count.setValue(bar_count)

            block_size_val = self._config_int('spotify_visualizer', spotify_vis_config, 'audio_block_size', 0)
            block_idx = self.spotify_vis_block_size.findData(block_size_val)
            if block_idx < 0:
                block_idx = 0
            self.spotify_vis_block_size.setCurrentIndex(block_idx)

            self.spotify_vis_recommended.setChecked(
                self._config_bool('spotify_visualizer', spotify_vis_config, 'adaptive_sensitivity', True)
            )

            sens_f = self._config_float('spotify_visualizer', spotify_vis_config, 'sensitivity', 1.0)
            sens_slider = int(max(0.25, min(2.5, sens_f)) * 100)
            self.spotify_vis_sensitivity.setValue(sens_slider)
            self.spotify_vis_sensitivity_label.setText(f"{sens_slider / 100.0:.2f}x")
            self._update_spotify_vis_sensitivity_enabled_state()

            dynamic_floor = self._config_bool('spotify_visualizer', spotify_vis_config, 'dynamic_range_enabled', True)
            self.spotify_vis_dynamic_floor.setChecked(dynamic_floor)
            manual_floor_f = self._config_float('spotify_visualizer', spotify_vis_config, 'manual_floor', 2.1)
            manual_slider = int(max(0.12, min(4.0, manual_floor_f)) * 100)
            self.spotify_vis_manual_floor.setValue(manual_slider)
            self.spotify_vis_manual_floor_label.setText(f"{manual_slider / 100.0:.2f}")
            self._update_spotify_vis_floor_enabled_state()

            self.spotify_vis_software_enabled.setChecked(
                self._config_bool('spotify_visualizer', spotify_vis_config, 'software_visualizer_enabled', False)
            )

            fill_color_data = spotify_vis_config.get('bar_fill_color', self._widget_default('spotify_visualizer', 'bar_fill_color', [0, 255, 128, 230]))
            try:
                self._spotify_vis_fill_color = QColor(*fill_color_data)
            except Exception:
                logger.debug("[WIDGETS_TAB] Exception suppressed: invalid spotify fill color", exc_info=True)
                self._spotify_vis_fill_color = QColor(0, 255, 128, 230)

            border_color_data = spotify_vis_config.get('bar_border_color', self._widget_default('spotify_visualizer', 'bar_border_color', [255, 255, 255, 230]))
            try:
                self._spotify_vis_border_color = QColor(*border_color_data)
            except Exception:
                logger.debug("[WIDGETS_TAB] Exception suppressed: invalid spotify border color", exc_info=True)
                self._spotify_vis_border_color = QColor(255, 255, 255, 230)

            border_opacity_pct = int(self._config_float('spotify_visualizer', spotify_vis_config, 'bar_border_opacity', 0.85) * 100)
            self.spotify_vis_border_opacity.setValue(border_opacity_pct)
            self.spotify_vis_border_opacity_label.setText(f"{border_opacity_pct}%")

            # Ghosting settings
            self.spotify_vis_ghost_enabled.setChecked(
                self._config_bool('spotify_visualizer', spotify_vis_config, 'ghosting_enabled', True)
            )

            ghost_alpha_pct = int(self._config_float('spotify_visualizer', spotify_vis_config, 'ghost_alpha', 0.4) * 100)
            if ghost_alpha_pct < 0:
                ghost_alpha_pct = 0
            if ghost_alpha_pct > 100:
                ghost_alpha_pct = 100
            self.spotify_vis_ghost_opacity.setValue(ghost_alpha_pct)
            self.spotify_vis_ghost_opacity_label.setText(f"{ghost_alpha_pct}%")

            ghost_decay_f = self._config_float('spotify_visualizer', spotify_vis_config, 'ghost_decay', 0.4)
            ghost_decay_slider = int(ghost_decay_f * 100.0)
            if ghost_decay_slider < 10:
                ghost_decay_slider = 10
            if ghost_decay_slider > 100:
                ghost_decay_slider = 100
            self.spotify_vis_ghost_decay.setValue(ghost_decay_slider)
            self.spotify_vis_ghost_decay_label.setText(f"{ghost_decay_slider / 100.0:.2f}x")

            # Load reddit settings. If the reddit section is missing or empty
            # (older configs), fall back to the canonical defaults from
            # SettingsManager so Reset to Defaults produces the expected
            # bottom-right, compact card with an "all" feed.
            reddit_config = widgets.get('reddit', {})
            if not isinstance(reddit_config, dict) or not reddit_config:
                try:
                    # Prefer the canonical defaults exposed by the active
                    # SettingsManager instance so UI stays in sync with
                    # SettingsManager._set_defaults.
                    getter = getattr(self._settings, 'get_widget_defaults', None)
                    if callable(getter):
                        section = getter('reddit')
                        if isinstance(section, dict) and section:
                            reddit_config = section
                except Exception:
                    # Fall back to an empty dict – subsequent UI code will
                    # still apply reasonable hard-coded defaults.
                    reddit_config = {}

            self.reddit_enabled.setChecked(self._config_bool('reddit', reddit_config, 'enabled', True))

            self.reddit_exit_on_click.setChecked(self._config_bool('reddit', reddit_config, 'exit_on_click', True))

            subreddit = self._config_str('reddit', reddit_config, 'subreddit', 'All')
            self.reddit_subreddit.setText(subreddit)

            limit_val = self._config_int('reddit', reddit_config, 'limit', 10)
            if limit_val <= 5:
                items_text = "4"
            elif limit_val >= 20:
                items_text = "20"
            else:
                items_text = "10"
            idx_items = self.reddit_items.findText(items_text)
            if idx_items >= 0:
                self.reddit_items.setCurrentIndex(idx_items)

            reddit_pos = self._config_str('reddit', reddit_config, 'position', 'Bottom Right')
            idx_pos = self.reddit_position.findText(reddit_pos)
            if idx_pos >= 0:
                self.reddit_position.setCurrentIndex(idx_pos)

            r_monitor_sel = reddit_config.get('monitor', self._widget_default('reddit', 'monitor', 'ALL'))
            r_mon_text = str(r_monitor_sel) if isinstance(r_monitor_sel, (int, str)) else 'ALL'
            r_idx = self.reddit_monitor_combo.findText(r_mon_text)
            if r_idx >= 0:
                self.reddit_monitor_combo.setCurrentIndex(r_idx)

            self.reddit_font_combo.setCurrentFont(QFont(self._config_str('reddit', reddit_config, 'font_family', 'Segoe UI')))
            self.reddit_font_size.setValue(self._config_int('reddit', reddit_config, 'font_size', 18))
            self.reddit_margin.setValue(self._config_int('reddit', reddit_config, 'margin', 30))

            self.reddit_show_background.setChecked(self._config_bool('reddit', reddit_config, 'show_background', True))
            self.reddit_intense_shadow.setChecked(
                self._config_bool('reddit', reddit_config, 'intense_shadow', True)
            )
            self.reddit_show_separators.setChecked(
                self._config_bool('reddit', reddit_config, 'show_separators', True)
            )
            reddit_opacity_pct = int(self._config_float('reddit', reddit_config, 'bg_opacity', 0.6) * 100)
            self.reddit_bg_opacity.setValue(reddit_opacity_pct)
            self.reddit_bg_opacity_label.setText(f"{reddit_opacity_pct}%")

            reddit_border_opacity_pct = int(self._config_float('reddit', reddit_config, 'border_opacity', 1.0) * 100)
            self.reddit_border_opacity.setValue(reddit_border_opacity_pct)
            self.reddit_border_opacity_label.setText(f"{reddit_border_opacity_pct}%")

            reddit_color_data = reddit_config.get('color', self._widget_default('reddit', 'color', [255, 255, 255, 230]))
            self._reddit_color = QColor(*reddit_color_data)
            reddit_bg_color_data = reddit_config.get('bg_color', self._widget_default('reddit', 'bg_color', [35, 35, 35, 255]))
            try:
                self._reddit_bg_color = QColor(*reddit_bg_color_data)
            except Exception:
                logger.debug("[WIDGETS_TAB] Exception suppressed: invalid reddit bg color", exc_info=True)
                self._reddit_bg_color = QColor(35, 35, 35, 255)
            reddit_border_color_data = reddit_config.get('border_color', self._widget_default('reddit', 'border_color', [255, 255, 255, 255]))
            try:
                self._reddit_border_color = QColor(*reddit_border_color_data)
            except Exception:
                logger.debug("[WIDGETS_TAB] Exception suppressed: invalid reddit border color", exc_info=True)
                self._reddit_border_color = QColor(255, 255, 255, 255)
            
            # Reddit 2 settings
            reddit2_config = widgets.get('reddit2', {})
            self.reddit2_enabled.setChecked(self._config_bool('reddit2', reddit2_config, 'enabled', False))
            self.reddit2_subreddit.setText(self._config_str('reddit2', reddit2_config, 'subreddit', ''))
            reddit2_limit = self._config_int('reddit2', reddit2_config, 'limit', 4)
            if reddit2_limit <= 5:
                reddit2_limit_text = "4"
            elif reddit2_limit >= 20:
                reddit2_limit_text = "20"
            else:
                reddit2_limit_text = "10"
            reddit2_items_idx = self.reddit2_items.findText(reddit2_limit_text)
            if reddit2_items_idx >= 0:
                self.reddit2_items.setCurrentIndex(reddit2_items_idx)
            reddit2_pos = self._config_str('reddit2', reddit2_config, 'position', 'Top Left')
            reddit2_pos_idx = self.reddit2_position.findText(reddit2_pos)
            if reddit2_pos_idx >= 0:
                self.reddit2_position.setCurrentIndex(reddit2_pos_idx)
            reddit2_monitor = reddit2_config.get('monitor', self._widget_default('reddit2', 'monitor', 'ALL'))
            reddit2_mon_text = str(reddit2_monitor) if isinstance(reddit2_monitor, (int, str)) else 'ALL'
            reddit2_mon_idx = self.reddit2_monitor_combo.findText(reddit2_mon_text)
            if reddit2_mon_idx >= 0:
                self.reddit2_monitor_combo.setCurrentIndex(reddit2_mon_idx)

            # Gmail settings - archived, see archive/gmail_feature/
        finally:
            for w in blockers:
                try:
                    w.blockSignals(False)
                except Exception as e:
                    logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
        
        # Update stack status labels after loading settings
        try:
            self._update_stack_status()
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)

    def _choose_clock_color(self) -> None:
        """Choose clock text color."""
        color = StyledColorPicker.get_color(self._clock_color, self, "Choose Clock Color")
        if color is not None:
            self._clock_color = color
            self._save_settings()
    
    def _choose_clock_bg_color(self) -> None:
        """Choose clock background color."""
        color = StyledColorPicker.get_color(self._clock_bg_color, self, "Choose Clock Background Color")
        if color is not None:
            self._clock_bg_color = color
            self._save_settings()
    
    def _choose_clock_border_color(self) -> None:
        """Choose clock border color."""
        color = StyledColorPicker.get_color(self._clock_border_color, self, "Choose Clock Border Color")
        if color is not None:
            self._clock_border_color = color
            self._save_settings()
    
    def _choose_weather_color(self) -> None:
        """Choose weather text color."""
        color = StyledColorPicker.get_color(self._weather_color, self, "Choose Weather Color")
        if color is not None:
            self._weather_color = color
            self._save_settings()
    
    def _choose_weather_bg_color(self) -> None:
        """Choose weather background color."""
        color = StyledColorPicker.get_color(self._weather_bg_color, self, "Choose Weather Background Color")
        if color is not None:
            self._weather_bg_color = color
            self._save_settings()

    def _choose_weather_border_color(self) -> None:
        """Choose weather border color."""
        color = StyledColorPicker.get_color(self._weather_border_color, self, "Choose Weather Border Color")
        if color is not None:
            self._weather_border_color = color
            self._save_settings()
    
    def _choose_media_color(self) -> None:
        """Choose media text color."""
        color = StyledColorPicker.get_color(self._media_color, self, "Choose Spotify Color")
        if color is not None:
            self._media_color = color
            self._save_settings()

    def _choose_media_bg_color(self) -> None:
        """Choose media background color."""
        color = StyledColorPicker.get_color(self._media_bg_color, self, "Choose Spotify Background Color")
        if color is not None:
            self._media_bg_color = color
            self._save_settings()

    def _choose_media_border_color(self) -> None:
        """Choose media border color."""
        color = StyledColorPicker.get_color(self._media_border_color, self, "Choose Spotify Border Color")
        if color is not None:
            self._media_border_color = color
            self._save_settings()

    def _choose_media_volume_fill_color(self) -> None:
        """Choose Spotify volume slider fill color."""
        color = StyledColorPicker.get_color(
            getattr(self, "_media_volume_fill_color", self._media_color),
            self,
            "Choose Spotify Volume Fill Color",
        )
        if color is not None:
            self._media_volume_fill_color = color
            self._save_settings()

    def _choose_spotify_vis_fill_color(self) -> None:
        """Choose Spotify Beat Visualizer bar fill color."""
        color = StyledColorPicker.get_color(
            self._spotify_vis_fill_color,
            self,
            "Choose Beat Bar Fill Color",
        )
        if color is not None:
            self._spotify_vis_fill_color = color
            self._save_settings()

    def _choose_spotify_vis_border_color(self) -> None:
        """Choose Spotify Beat Visualizer bar border color."""
        color = StyledColorPicker.get_color(
            self._spotify_vis_border_color,
            self,
            "Choose Beat Bar Border Color",
        )
        if color is not None:
            self._spotify_vis_border_color = color
            self._save_settings()

    def _choose_reddit_color(self) -> None:
        """Choose Reddit text color."""
        color = StyledColorPicker.get_color(self._reddit_color, self, "Choose Reddit Color")
        if color is not None:
            self._reddit_color = color
            self._save_settings()

    def _choose_reddit_bg_color(self) -> None:
        """Choose Reddit background color."""
        color = StyledColorPicker.get_color(self._reddit_bg_color, self, "Choose Reddit Background Color")
        if color is not None:
            self._reddit_bg_color = color
            self._save_settings()

    def _choose_reddit_border_color(self) -> None:
        """Choose Reddit border color."""
        color = StyledColorPicker.get_color(self._reddit_border_color, self, "Choose Reddit Border Color")
        if color is not None:
            self._reddit_border_color = color
            self._save_settings()

    # Gmail methods removed - archived in archive/gmail_feature/
    
    def _save_settings(self) -> None:
        """Save current settings."""
        if getattr(self, "_loading", False):
            return

        try:
            logger.debug("[WIDGETS_TAB] _save_settings start")
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
        # Get timezone from current selection
        tz_data = self.clock_timezone.currentData()
        timezone_str = tz_data if tz_data else 'local'
        
        format_text = ""
        try:
            format_text = (self.clock_format.currentText() or "").strip().lower()
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
            format_text = ""
        clock_format_value = '12h' if format_text.startswith('12') else '24h'

        clock_config = {
            'enabled': self.clock_enabled.isChecked(),
            'format': clock_format_value,
            'show_seconds': self.clock_seconds.isChecked(),
            'timezone': timezone_str,
            'show_timezone': self.clock_show_tz.isChecked(),
            'position': self.clock_position.currentText(),
            'font_family': self.clock_font_combo.currentFont().family(),
            'font_size': self.clock_font_size.value(),
            'margin': self.clock_margin.value(),
            'show_background': self.clock_show_background.isChecked(),
            'bg_opacity': self.clock_bg_opacity.value() / 100.0,
            'bg_color': [self._clock_bg_color.red(), self._clock_bg_color.green(),
                        self._clock_bg_color.blue(), self._clock_bg_color.alpha()],
            'color': [self._clock_color.red(), self._clock_color.green(), 
                     self._clock_color.blue(), self._clock_color.alpha()],
            'border_color': [self._clock_border_color.red(), self._clock_border_color.green(),
                             self._clock_border_color.blue(), self._clock_border_color.alpha()],
            'border_opacity': self.clock_border_opacity.value() / 100.0,
            'display_mode': 'analog' if self.clock_analog_mode.isChecked() else 'digital',
            'show_numerals': self.clock_show_numerals.isChecked(),
            'analog_face_shadow': self.clock_analog_shadow.isChecked(),
            'analog_shadow_intense': self.clock_analog_shadow_intense.isChecked(),
            'digital_shadow_intense': self.clock_digital_shadow_intense.isChecked(),
        }
        # Monitor selection save: 'ALL' or int
        cmon_text = self.clock_monitor_combo.currentText()
        clock_config['monitor'] = cmon_text if cmon_text == 'ALL' else int(cmon_text)
        
        weather_config = {
            'enabled': self.weather_enabled.isChecked(),
            # No api_key needed with Open-Meteo!
            'location': self.weather_location.text(),
            'position': self.weather_position.currentText(),
            'font_family': self.weather_font_combo.currentFont().family(),
            'font_size': self.weather_font_size.value(),
            'margin': self.weather_margin.value(),
            'show_forecast': self.weather_show_forecast.isChecked(),
            'show_details_row': self.weather_show_details_row.isChecked(),
            'animated_icon_alignment': (self.weather_icon_alignment.currentData() or self.weather_icon_alignment.currentText() or "NONE"),
            'animated_icon_enabled': self.weather_icon_animated.isChecked(),
            'desaturate_animated_icon': self.weather_desaturate_icon.isChecked(),
            'intense_shadow': self.weather_intense_shadow.isChecked(),
            'show_background': self.weather_show_background.isChecked(),
            'bg_opacity': self.weather_bg_opacity.value() / 100.0,
            'color': [self._weather_color.red(), self._weather_color.green(), 
                     self._weather_color.blue(), self._weather_color.alpha()],
            'bg_color': [self._weather_bg_color.red(), self._weather_bg_color.green(),
                        self._weather_bg_color.blue(), self._weather_bg_color.alpha()],
            'border_color': [self._weather_border_color.red(), self._weather_border_color.green(),
                             self._weather_border_color.blue(), self._weather_border_color.alpha()],
            'border_opacity': self.weather_border_opacity.value() / 100.0,
        }
        wmon_text = self.weather_monitor_combo.currentText()
        weather_config['monitor'] = wmon_text if wmon_text == 'ALL' else int(wmon_text)

        media_config = {
            'enabled': self.media_enabled.isChecked(),
            'position': self.media_position.currentText(),
            'font_family': self.media_font_combo.currentFont().family(),
            'font_size': self.media_font_size.value(),
            'margin': self.media_margin.value(),
            'show_background': self.media_show_background.isChecked(),
            'intense_shadow': self.media_intense_shadow.isChecked(),
            'bg_opacity': self.media_bg_opacity.value() / 100.0,
            'color': [self._media_color.red(), self._media_color.green(),
                      self._media_color.blue(), self._media_color.alpha()],
            'bg_color': [self._media_bg_color.red(), self._media_bg_color.green(),
                         self._media_bg_color.blue(), self._media_bg_color.alpha()],
            'border_color': [self._media_border_color.red(), self._media_border_color.green(),
                             self._media_border_color.blue(), self._media_border_color.alpha()],
            'border_opacity': self.media_border_opacity.value() / 100.0,
            'spotify_volume_fill_color': [
                self._media_volume_fill_color.red(),
                self._media_volume_fill_color.green(),
                self._media_volume_fill_color.blue(),
                self._media_volume_fill_color.alpha(),
            ],
            'artwork_size': self.media_artwork_size.value(),
            'rounded_artwork_border': self.media_rounded_artwork.isChecked(),
            'show_header_frame': self.media_show_header_frame.isChecked(),
            'show_controls': self.media_show_controls.isChecked(),
            'spotify_volume_enabled': self.media_spotify_volume_enabled.isChecked(),
        }
        mmon_text = self.media_monitor_combo.currentText()
        media_config['monitor'] = mmon_text if mmon_text == 'ALL' else int(mmon_text)

        spotify_vis_config = {
            'enabled': self.spotify_vis_enabled.isChecked(),
            'mode': 'spectrum',  # Only spectrum mode supported
            'bar_count': self.spotify_vis_bar_count.value(),
            'software_visualizer_enabled': self.spotify_vis_software_enabled.isChecked(),
            'adaptive_sensitivity': self.spotify_vis_recommended.isChecked(),
            'audio_block_size': int(self.spotify_vis_block_size.currentData() or 0),
            'sensitivity': max(0.25, min(2.5, self.spotify_vis_sensitivity.value() / 100.0)),
            'bar_fill_color': [
                self._spotify_vis_fill_color.red(),
                self._spotify_vis_fill_color.green(),
                self._spotify_vis_fill_color.blue(),
                self._spotify_vis_fill_color.alpha(),
            ],
            'bar_border_color': [
                self._spotify_vis_border_color.red(),
                self._spotify_vis_border_color.green(),
                self._spotify_vis_border_color.blue(),
                self._spotify_vis_border_color.alpha(),
            ],
            'bar_border_opacity': self.spotify_vis_border_opacity.value() / 100.0,
            'ghosting_enabled': self.spotify_vis_ghost_enabled.isChecked(),
            'ghost_alpha': self.spotify_vis_ghost_opacity.value() / 100.0,
            'ghost_decay': max(0.1, self.spotify_vis_ghost_decay.value() / 100.0),
            'dynamic_floor': self.spotify_vis_dynamic_floor.isChecked(),
            'dynamic_range_enabled': self.spotify_vis_dynamic_floor.isChecked(),
            'manual_floor': max(0.12, min(4.0, self.spotify_vis_manual_floor.value() / 100.0)),
        }

        self._update_spotify_vis_sensitivity_enabled_state()
        self._update_spotify_vis_floor_enabled_state()

        reddit_limit_text = self.reddit_items.currentText().strip()
        try:
            reddit_limit = int(reddit_limit_text)
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
            reddit_limit = 10

        reddit_config = {
            'enabled': self.reddit_enabled.isChecked(),
            'exit_on_click': self.reddit_exit_on_click.isChecked(),
            'subreddit': self.reddit_subreddit.text().strip() or 'wallpapers',
            'limit': reddit_limit,
            'position': self.reddit_position.currentText(),
            'font_family': self.reddit_font_combo.currentFont().family(),
            'font_size': self.reddit_font_size.value(),
            'margin': self.reddit_margin.value(),
            'show_background': self.reddit_show_background.isChecked(),
            'intense_shadow': self.reddit_intense_shadow.isChecked(),
            'show_separators': self.reddit_show_separators.isChecked(),
            'bg_opacity': self.reddit_bg_opacity.value() / 100.0,
            'color': [
                self._reddit_color.red(),
                self._reddit_color.green(),
                self._reddit_color.blue(),
                self._reddit_color.alpha(),
            ],
            'bg_color': [
                self._reddit_bg_color.red(),
                self._reddit_bg_color.green(),
                self._reddit_bg_color.blue(),
                self._reddit_bg_color.alpha(),
            ],
            'border_color': [
                self._reddit_border_color.red(),
                self._reddit_border_color.green(),
                self._reddit_border_color.blue(),
                self._reddit_border_color.alpha(),
            ],
            'border_opacity': self.reddit_border_opacity.value() / 100.0,
        }

        # Monitor selection save: 'ALL' or int, mirroring clock/weather/media.
        rmon_text = self.reddit_monitor_combo.currentText()
        reddit_config['monitor'] = rmon_text if rmon_text == 'ALL' else int(rmon_text)

        clock2_tz_data = self.clock2_timezone.currentData()
        clock2_timezone = clock2_tz_data if clock2_tz_data else 'UTC'
        clock2_config = {
            'enabled': self.clock2_enabled.isChecked(),
            'timezone': clock2_timezone,
        }
        c2mon_text = self.clock2_monitor_combo.currentText()
        clock2_config['monitor'] = c2mon_text if c2mon_text == 'ALL' else int(c2mon_text)

        clock3_tz_data = self.clock3_timezone.currentData()
        clock3_timezone = clock3_tz_data if clock3_tz_data else 'UTC+01:00'
        clock3_config = {
            'enabled': self.clock3_enabled.isChecked(),
            'timezone': clock3_timezone,
        }
        c3mon_text = self.clock3_monitor_combo.currentText()
        clock3_config['monitor'] = c3mon_text if c3mon_text == 'ALL' else int(c3mon_text)

        # Reddit 2 config (inherits styling from Reddit 1)
        try:
            reddit2_limit = int(self.reddit2_items.currentText())
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
            reddit2_limit = 4
        reddit2_config = {
            'enabled': self.reddit2_enabled.isChecked(),
            'subreddit': self.reddit2_subreddit.text().strip(),
            'limit': reddit2_limit,
            'position': self.reddit2_position.currentText(),
        }
        r2mon_text = self.reddit2_monitor_combo.currentText()
        reddit2_config['monitor'] = r2mon_text if r2mon_text == 'ALL' else int(r2mon_text)

        existing_widgets = self._settings.get('widgets', {})
        if not isinstance(existing_widgets, dict):
            existing_widgets = {}

        # Global widget shadow configuration: only the enabled flag is
        # user-editable at present; other parameters remain driven by
        # SettingsManager defaults.
        shadows_config = existing_widgets.get('shadows', {})
        if not isinstance(shadows_config, dict):
            shadows_config = {}
        shadows_config['enabled'] = self.widget_shadows_enabled.isChecked()
        existing_widgets['shadows'] = shadows_config
        existing_widgets['clock'] = clock_config
        existing_widgets['clock2'] = clock2_config
        existing_widgets['clock3'] = clock3_config
        existing_widgets['weather'] = weather_config
        existing_widgets['media'] = media_config
        existing_widgets['spotify_visualizer'] = spotify_vis_config
        existing_widgets['reddit'] = reddit_config
        existing_widgets['reddit2'] = reddit2_config

        # Gmail config - archived, see archive/gmail_feature/

        try:
            logger.debug(
                "[WIDGETS_TAB] Saving widgets config: "
                "clock.enabled=%s, clock.analog_shadow_intense=%s, "
                "reddit.limit=%s, reddit.enabled=%s",
                clock_config.get('enabled'),
                clock_config.get('analog_shadow_intense'),
                reddit_config.get('limit'),
                reddit_config.get('enabled'),
            )
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)

        self._settings.set('widgets', existing_widgets)
        self._settings.save()

    def _update_spotify_vis_sensitivity_enabled_state(self) -> None:
        try:
            recommended = self.spotify_vis_recommended.isChecked()
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
            recommended = True
        try:
            self.spotify_vis_sensitivity.setEnabled(not recommended)
            self.spotify_vis_sensitivity_label.setEnabled(not recommended)
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)

    def _update_spotify_vis_floor_enabled_state(self) -> None:
        try:
            dynamic = self.spotify_vis_dynamic_floor.isChecked()
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
            dynamic = True

        try:
            self.spotify_vis_manual_floor.setEnabled(not dynamic)
            self.spotify_vis_manual_floor_label.setEnabled(not dynamic)
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
    
    def _populate_timezones_for_combo(self, combo) -> None:
        timezones = get_common_timezones()
        for display_name, tz_str in timezones:
            combo.addItem(display_name, tz_str)

    def _populate_timezones(self) -> None:
        """Populate timezone dropdown with common timezones and UTC offsets."""
        # Get common timezones
        self._populate_timezones_for_combo(self.clock_timezone)
    
    def _auto_detect_timezone(self) -> None:
        """Auto-detect user's local timezone."""
        detected_tz = get_local_timezone()
        
        # Find the timezone in the dropdown
        tz_index = self.clock_timezone.findData(detected_tz)
        if tz_index >= 0:
            self.clock_timezone.setCurrentIndex(tz_index)
            logger.info(f"Auto-detected timezone: {detected_tz}")
        else:
            # Try to add it if not found
            self.clock_timezone.addItem(f"Detected: {detected_tz}", detected_tz)
            self.clock_timezone.setCurrentIndex(self.clock_timezone.count() - 1)
            logger.info(f"Added detected timezone: {detected_tz}")
        
        # Save settings with new timezone
        self._save_settings()
    
    def _update_stack_status(self) -> None:
        """Update all widget stack status labels based on current settings.
        
        This is called when any position combo changes. It recalculates
        stacking predictions for all widgets and updates their status labels.
        """
        try:
            # Build current settings from UI state (not saved yet)
            widgets_config = self._build_current_widgets_config()
            
            # Define widget status label mappings
            status_mappings = [
                (WidgetType.CLOCK, 'clock_stack_status', 'clock_position', 'clock_monitor_combo'),
                (WidgetType.WEATHER, 'weather_stack_status', 'weather_position', 'weather_monitor_combo'),
                (WidgetType.MEDIA, 'media_stack_status', 'media_position', 'media_monitor_combo'),
                (WidgetType.REDDIT, 'reddit_stack_status', 'reddit_position', 'reddit_monitor_combo'),
                (WidgetType.REDDIT2, 'reddit2_stack_status', 'reddit2_position', 'reddit2_monitor_combo'),
            ]
            
            for widget_type, status_attr, pos_attr, mon_attr in status_mappings:
                status_label = getattr(self, status_attr, None)
                pos_combo = getattr(self, pos_attr, None)
                mon_combo = getattr(self, mon_attr, None)
                
                if status_label is None or pos_combo is None or mon_combo is None:
                    continue
                
                position = pos_combo.currentText()
                monitor = mon_combo.currentText()
                
                can_stack, message = get_position_status_for_widget(
                    widgets_config, widget_type, position, monitor
                )
                
                if message:
                    if can_stack:
                        status_label.setText(message)
                        status_label.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold;")
                    else:
                        status_label.setText(message)
                        status_label.setStyleSheet("color: #FF9800; font-size: 11px; font-weight: bold;")
                else:
                    status_label.setText("")
                    status_label.setStyleSheet("")
        except Exception as e:
            # Log errors instead of silently swallowing them
            import logging
            logging.getLogger(__name__).debug("Stack status update failed: %s", e, exc_info=True)
    
    def _build_current_widgets_config(self) -> dict:
        """Build widgets config dict from current UI state.
        
        This creates a config dict that mirrors what would be saved,
        but from current UI values (before save).
        """
        config = {}
        
        # Clock
        config['clock'] = {
            'enabled': getattr(self, 'clock_enabled', None) and self.clock_enabled.isChecked(),
            'mode': getattr(self, 'clock_mode_combo', None) and self.clock_mode_combo.currentText() or 'Digital',
            'position': getattr(self, 'clock_position', None) and self.clock_position.currentText() or 'Top Right',
            'monitor': getattr(self, 'clock_monitor_combo', None) and self.clock_monitor_combo.currentText() or 'ALL',
            'font_size': getattr(self, 'clock_font_size', None) and self.clock_font_size.value() or 48,
            'show_seconds': getattr(self, 'clock_seconds', None) and self.clock_seconds.isChecked(),
            'show_timezone_label': getattr(self, 'clock_show_tz_label', None) and self.clock_show_tz_label.isChecked(),
        }
        
        # Clock 2
        config['clock2'] = {
            'enabled': getattr(self, 'clock2_enabled', None) and self.clock2_enabled.isChecked(),
            'monitor': getattr(self, 'clock2_monitor_combo', None) and self.clock2_monitor_combo.currentText() or 'ALL',
        }
        
        # Clock 3
        config['clock3'] = {
            'enabled': getattr(self, 'clock3_enabled', None) and self.clock3_enabled.isChecked(),
            'monitor': getattr(self, 'clock3_monitor_combo', None) and self.clock3_monitor_combo.currentText() or 'ALL',
        }
        
        # Weather
        config['weather'] = {
            'enabled': getattr(self, 'weather_enabled', None) and self.weather_enabled.isChecked(),
            'position': getattr(self, 'weather_position', None) and self.weather_position.currentText() or 'Top Left',
            'monitor': getattr(self, 'weather_monitor_combo', None) and self.weather_monitor_combo.currentText() or 'ALL',
            'font_size': getattr(self, 'weather_font_size', None) and self.weather_font_size.value() or 18,
            'show_forecast': getattr(self, 'weather_show_forecast', None) and self.weather_show_forecast.isChecked(),
        }
        
        # Media
        config['media'] = {
            'enabled': getattr(self, 'media_enabled', None) and self.media_enabled.isChecked(),
            'position': getattr(self, 'media_position', None) and self.media_position.currentText() or 'Bottom Right',
            'monitor': getattr(self, 'media_monitor_combo', None) and self.media_monitor_combo.currentText() or 'ALL',
            'font_size': getattr(self, 'media_font_size', None) and self.media_font_size.value() or 14,
            'artwork_size': getattr(self, 'media_artwork_size', None) and self.media_artwork_size.value() or 80,
        }
        
        # Reddit
        reddit_limit = 10
        reddit_items_combo = getattr(self, 'reddit_items', None)
        if reddit_items_combo is not None:
            try:
                reddit_limit = int(reddit_items_combo.currentText())
            except Exception as e:
                logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
                reddit_limit = 10
        config['reddit'] = {
            'enabled': getattr(self, 'reddit_enabled', None) and self.reddit_enabled.isChecked(),
            'position': getattr(self, 'reddit_position', None) and self.reddit_position.currentText() or 'Bottom Right',
            'monitor': getattr(self, 'reddit_monitor_combo', None) and self.reddit_monitor_combo.currentText() or 'ALL',
            'font_size': getattr(self, 'reddit_font_size', None) and self.reddit_font_size.value() or 18,
            'limit': reddit_limit,
        }
        
        # Reddit 2
        config['reddit2'] = {
            'enabled': getattr(self, 'reddit2_enabled', None) and self.reddit2_enabled.isChecked(),
            'position': getattr(self, 'reddit2_position', None) and self.reddit2_position.currentText() or 'Top Left',
            'monitor': getattr(self, 'reddit2_monitor_combo', None) and self.reddit2_monitor_combo.currentText() or 'ALL',
            'limit': 4,
        }
        try:
            config['reddit2']['limit'] = int(self.reddit2_items.currentText())
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
        
        # Spotify Visualizer
        config['spotify_visualizer'] = {
            'enabled': getattr(self, 'spotify_vis_enabled', None) and self.spotify_vis_enabled.isChecked(),
            'monitor': getattr(self, 'spotify_vis_monitor_combo', None) and self.spotify_vis_monitor_combo.currentText() or 'ALL',
            'bar_count': getattr(self, 'spotify_vis_bar_count', None) and self.spotify_vis_bar_count.value() or 16,
        }
        
        return config
