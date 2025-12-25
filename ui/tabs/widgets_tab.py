"""
Widgets configuration tab for settings dialog.

Allows users to configure overlay widgets:
- Clock widget (enable, position, format, size, font, style)
- Weather widget (enable, position, location, API key, size, font, style)
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QGroupBox, QCheckBox, QLineEdit, QPushButton,
    QScrollArea, QSlider, QCompleter, QFontComboBox, QButtonGroup
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QFont

from core.settings.settings_manager import SettingsManager
from core.logging.logger import get_logger
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
        self._clock_color = QColor(255, 255, 255, 230)
        self._weather_color = QColor(255, 255, 255, 230)
        self._clock_border_color = QColor(128, 128, 128, 255)
        self._clock_bg_color = QColor(64, 64, 64, 255)
        # Weather widget frame defaults mirror WeatherWidget internals
        self._weather_bg_color = QColor(64, 64, 64, 255)
        self._weather_border_color = QColor(128, 128, 128, 255)
        # Media widget frame defaults mirror other overlay widgets
        self._media_color = QColor(255, 255, 255, 230)
        self._media_bg_color = QColor(64, 64, 64, 255)
        self._media_border_color = QColor(128, 128, 128, 255)
        # Spotify Beat Visualizer frame defaults inherit Spotify/media styling
        self._spotify_vis_fill_color = QColor(0, 255, 128, 230)
        self._spotify_vis_border_color = QColor(255, 255, 255, 230)
        # Reddit widget frame defaults mirror Spotify/media widget styling
        self._reddit_color = QColor(255, 255, 255, 230)
        self._reddit_bg_color = QColor(64, 64, 64, 255)
        self._reddit_border_color = QColor(128, 128, 128, 255)
        self._media_artwork_size = 100
        self._loading = True
        self._setup_ui()
        self._load_settings()
        self._loading = False
        
        logger.debug("WidgetsTab created")
    
    def _setup_ui(self) -> None:
        """Setup tab UI with scroll area."""
        # Create scroll area
        scroll = QScrollArea(self)
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
        self.clock_enabled.stateChanged.connect(self._save_settings)
        self.clock_enabled.stateChanged.connect(self._update_stack_status)
        clock_layout.addWidget(self.clock_enabled)
        
        # Time format
        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Format:"))
        self.clock_format = QComboBox()
        self.clock_format.addItems(["12 Hour", "24 Hour"])
        self.clock_format.currentTextChanged.connect(self._save_settings)
        format_row.addWidget(self.clock_format)
        format_row.addStretch()
        clock_layout.addLayout(format_row)
        
        # Show seconds
        self.clock_seconds = QCheckBox("Show Seconds")
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
        self.clock_show_tz.stateChanged.connect(self._save_settings)
        self.clock_show_tz.stateChanged.connect(self._update_stack_status)
        clock_layout.addWidget(self.clock_show_tz)

        # Analogue mode options
        self.clock_analog_mode = QCheckBox("Use Analogue Clock")
        self.clock_analog_mode.setToolTip(
            "Render the main clock as an analogue clock face with hour/minute/second hands."
        )
        self.clock_analog_mode.stateChanged.connect(self._save_settings)
        self.clock_analog_mode.stateChanged.connect(self._update_stack_status)
        clock_layout.addWidget(self.clock_analog_mode)

        self.clock_analog_shadow = QCheckBox("Analogue Face Shadow")
        self.clock_analog_shadow.setToolTip(
            "Enable a subtle drop shadow under the analogue clock face and hands."
        )
        self.clock_analog_shadow.stateChanged.connect(self._save_settings)
        clock_layout.addWidget(self.clock_analog_shadow)

        self.clock_analog_shadow_intense = QCheckBox("Intense Analogue Shadows")
        self.clock_analog_shadow_intense.setToolTip(
            "Doubles analogue shadow opacity and enlarges the drop shadow by ~50% for dramatic lighting."
        )
        self.clock_analog_shadow_intense.stateChanged.connect(self._save_settings)
        clock_layout.addWidget(self.clock_analog_shadow_intense)

        self.clock_show_numerals = QCheckBox("Show Hour Numerals (Analogue)")
        self.clock_show_numerals.stateChanged.connect(self._save_settings)
        clock_layout.addWidget(self.clock_show_numerals)
        
        # Position
        position_row = QHBoxLayout()
        position_row.addWidget(QLabel("Position:"))
        self.clock_position = QComboBox()
        self.clock_position.addItems([
            "Top Left", "Top Center", "Top Right",
            "Center",
            "Bottom Left", "Bottom Center", "Bottom Right"
        ])
        self.clock_position.currentTextChanged.connect(self._save_settings)
        self.clock_position.currentTextChanged.connect(self._update_stack_status)
        position_row.addWidget(self.clock_position)
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
        clock_disp_row.addStretch()
        clock_layout.addLayout(clock_disp_row)
        
        # Font family
        font_family_row = QHBoxLayout()
        font_family_row.addWidget(QLabel("Font:"))
        self.clock_font_combo = QFontComboBox()
        self.clock_font_combo.setCurrentFont("Segoe UI")
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
        self.clock_font_size.setValue(48)
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
        self.clock_margin.setValue(20)
        self.clock_margin.setAccelerated(True)
        self.clock_margin.valueChanged.connect(self._save_settings)
        margin_row.addWidget(self.clock_margin)
        margin_row.addWidget(QLabel("px"))
        margin_row.addStretch()
        clock_layout.addLayout(margin_row)
        
        # Background frame
        self.clock_show_background = QCheckBox("Show Background Frame")
        self.clock_show_background.stateChanged.connect(self._save_settings)
        clock_layout.addWidget(self.clock_show_background)
        
        # Background opacity
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Background Opacity:"))
        self.clock_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.clock_bg_opacity.setMinimum(0)
        self.clock_bg_opacity.setMaximum(100)
        self.clock_bg_opacity.setValue(90)
        self.clock_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.clock_bg_opacity.setTickInterval(10)
        self.clock_bg_opacity.valueChanged.connect(self._save_settings)
        opacity_row.addWidget(self.clock_bg_opacity)
        self.clock_opacity_label = QLabel("90%")
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
        self.clock_border_opacity.setValue(80)
        self.clock_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.clock_border_opacity.setTickInterval(10)
        self.clock_border_opacity.valueChanged.connect(self._save_settings)
        clock_border_opacity_row.addWidget(self.clock_border_opacity)
        self.clock_border_opacity_label = QLabel("80%")
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
            "Top Left", "Top Right",
            "Bottom Left", "Bottom Right"
        ])
        self.weather_position.currentTextChanged.connect(self._save_settings)
        self.weather_position.currentTextChanged.connect(self._update_stack_status)
        weather_pos_row.addWidget(self.weather_position)
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
        weather_disp_row.addStretch()
        weather_layout.addLayout(weather_disp_row)
        
        # Font family
        weather_font_family_row = QHBoxLayout()
        weather_font_family_row.addWidget(QLabel("Font:"))
        self.weather_font_combo = QFontComboBox()
        self.weather_font_combo.setCurrentFont("Segoe UI")
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
        self.weather_font_size.setValue(24)
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
        self.weather_show_forecast.setToolTip("Display tomorrow's forecast below current weather")
        self.weather_show_forecast.stateChanged.connect(self._save_settings)
        self.weather_show_forecast.stateChanged.connect(self._update_stack_status)
        weather_layout.addWidget(self.weather_show_forecast)
        
        # Background frame
        self.weather_show_background = QCheckBox("Show Background Frame")
        self.weather_show_background.stateChanged.connect(self._save_settings)
        weather_layout.addWidget(self.weather_show_background)
        
        # Background opacity
        weather_opacity_row = QHBoxLayout()
        weather_opacity_row.addWidget(QLabel("Background Opacity:"))
        self.weather_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.weather_bg_opacity.setMinimum(0)
        self.weather_bg_opacity.setMaximum(100)
        self.weather_bg_opacity.setValue(90)
        self.weather_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.weather_bg_opacity.setTickInterval(10)
        self.weather_bg_opacity.valueChanged.connect(self._save_settings)
        weather_opacity_row.addWidget(self.weather_bg_opacity)
        self.weather_opacity_label = QLabel("90%")
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
        self.weather_border_opacity.setValue(80)
        self.weather_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.weather_border_opacity.setTickInterval(10)
        self.weather_border_opacity.valueChanged.connect(self._save_settings)
        weather_border_opacity_row.addWidget(self.weather_border_opacity)
        self.weather_border_opacity_label = QLabel("80%")
        self.weather_border_opacity.valueChanged.connect(
            lambda v: self.weather_border_opacity_label.setText(f"{v}%")
        )
        weather_border_opacity_row.addWidget(self.weather_border_opacity_label)
        weather_layout.addLayout(weather_border_opacity_row)
        
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
            "Top Left", "Top Right",
            "Bottom Left", "Bottom Right",
        ])
        self.media_position.currentTextChanged.connect(self._save_settings)
        self.media_position.currentTextChanged.connect(self._update_stack_status)
        media_pos_row.addWidget(self.media_position)
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
        media_disp_row.addStretch()
        media_layout.addLayout(media_disp_row)

        media_font_family_row = QHBoxLayout()
        media_font_family_row.addWidget(QLabel("Font:"))
        self.media_font_combo = QFontComboBox()
        self.media_font_combo.setCurrentFont("Segoe UI")
        self.media_font_combo.setMinimumWidth(220)
        self.media_font_combo.currentFontChanged.connect(self._save_settings)
        media_font_family_row.addWidget(self.media_font_combo)
        media_font_family_row.addStretch()
        media_layout.addLayout(media_font_family_row)

        media_font_row = QHBoxLayout()
        media_font_row.addWidget(QLabel("Font Size:"))
        self.media_font_size = QSpinBox()
        self.media_font_size.setRange(10, 72)
        self.media_font_size.setValue(20)
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
        self.media_margin.setValue(20)
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
        self.media_show_background.stateChanged.connect(self._save_settings)
        media_layout.addWidget(self.media_show_background)

        media_opacity_row = QHBoxLayout()
        media_opacity_row.addWidget(QLabel("Background Opacity:"))
        self.media_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.media_bg_opacity.setMinimum(0)
        self.media_bg_opacity.setMaximum(100)
        self.media_bg_opacity.setValue(90)
        self.media_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.media_bg_opacity.setTickInterval(10)
        self.media_bg_opacity.valueChanged.connect(self._save_settings)
        media_opacity_row.addWidget(self.media_bg_opacity)
        self.media_bg_opacity_label = QLabel("90%")
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
        self.media_border_opacity.setValue(80)
        self.media_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.media_border_opacity.setTickInterval(10)
        self.media_border_opacity.valueChanged.connect(self._save_settings)
        media_border_opacity_row.addWidget(self.media_border_opacity)
        self.media_border_opacity_label = QLabel("80%")
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
        self.media_artwork_size.setValue(200)
        self.media_artwork_size.setAccelerated(True)
        self.media_artwork_size.valueChanged.connect(self._save_settings)
        self.media_artwork_size.valueChanged.connect(self._update_stack_status)
        media_artwork_row.addWidget(self.media_artwork_size)
        media_artwork_row.addWidget(QLabel("px"))
        media_artwork_row.addStretch()
        media_layout.addLayout(media_artwork_row)

        # Artwork border style
        self.media_rounded_artwork = QCheckBox("Rounded Artwork Border")
        self.media_rounded_artwork.setChecked(True)
        self.media_rounded_artwork.stateChanged.connect(self._save_settings)
        media_layout.addWidget(self.media_rounded_artwork)

        # Header frame around logo + title
        self.media_show_header_frame = QCheckBox("Header Border Around Logo + Title")
        self.media_show_header_frame.setChecked(True)
        self.media_show_header_frame.stateChanged.connect(self._save_settings)
        media_layout.addWidget(self.media_show_header_frame)

        # Controls visibility
        self.media_show_controls = QCheckBox("Show Transport Controls")
        self.media_show_controls.setChecked(True)
        self.media_show_controls.stateChanged.connect(self._save_settings)
        media_layout.addWidget(self.media_show_controls)

        # Spotify-only vertical volume slider (paired with the Spotify card).
        self.media_spotify_volume_enabled = QCheckBox("Enable Spotify Volume Slider")
        self.media_spotify_volume_enabled.setToolTip(
            "Show a slim vertical volume slider next to the Spotify card when Core Audio/pycaw is available. "
            "The slider only affects the Spotify session volume and is gated by hard-exit / Ctrl interaction modes."
        )
        self.media_spotify_volume_enabled.setChecked(True)
        self.media_spotify_volume_enabled.stateChanged.connect(self._save_settings)
        media_layout.addWidget(self.media_spotify_volume_enabled)

        # Spotify Beat Visualizer group (Spotify-only beat bars tied to
        # the Spotify/Media widget).
        spotify_vis_group = QGroupBox("Spotify Beat Visualizer")
        spotify_vis_layout = QVBoxLayout(spotify_vis_group)

        # Enable/disable row with FORCE Software Visualizer on the same line.
        spotify_vis_enable_row = QHBoxLayout()
        self.spotify_vis_enabled = QCheckBox("Enable Spotify Beat Visualizer")
        self.spotify_vis_enabled.setToolTip(
            "Shows a thin bar visualizer tied to Spotify playback, positioned just above the Spotify widget."
        )
        self.spotify_vis_enabled.stateChanged.connect(self._save_settings)
        spotify_vis_enable_row.addWidget(self.spotify_vis_enabled)

        # Optional software visualiser fallback. When enabled, the legacy
        # QWidget-based bar renderer is allowed to draw when OpenGL is
        # unavailable or when the renderer backend is set to Software.
        self.spotify_vis_software_enabled = QCheckBox("FORCE Software Visualizer")
        self.spotify_vis_software_enabled.setToolTip(
            "Force the legacy CPU bar visualizer even when the renderer backend is set to Software or when OpenGL is unavailable."
        )
        self.spotify_vis_software_enabled.stateChanged.connect(self._save_settings)
        spotify_vis_enable_row.addStretch()
        spotify_vis_enable_row.addWidget(self.spotify_vis_software_enabled)
        spotify_vis_layout.addLayout(spotify_vis_enable_row)

        spotify_vis_bar_row = QHBoxLayout()
        spotify_vis_bar_row.addWidget(QLabel("Bar Count:"))
        self.spotify_vis_bar_count = QSpinBox()
        self.spotify_vis_bar_count.setRange(8, 96)
        self.spotify_vis_bar_count.setValue(32)
        self.spotify_vis_bar_count.setAccelerated(True)
        self.spotify_vis_bar_count.valueChanged.connect(self._save_settings)
        spotify_vis_bar_row.addWidget(self.spotify_vis_bar_count)
        spotify_vis_bar_row.addWidget(QLabel("bars"))
        spotify_vis_bar_row.addStretch()
        spotify_vis_layout.addLayout(spotify_vis_bar_row)

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
        self.spotify_vis_border_opacity.setValue(85)
        self.spotify_vis_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.spotify_vis_border_opacity.setTickInterval(5)
        self.spotify_vis_border_opacity.valueChanged.connect(self._save_settings)
        spotify_vis_border_opacity_row.addWidget(self.spotify_vis_border_opacity)
        self.spotify_vis_border_opacity_label = QLabel("85%")
        self.spotify_vis_border_opacity.valueChanged.connect(
            lambda v: self.spotify_vis_border_opacity_label.setText(f"{v}%")
        )
        spotify_vis_border_opacity_row.addWidget(self.spotify_vis_border_opacity_label)
        spotify_vis_layout.addLayout(spotify_vis_border_opacity_row)

        spotify_vis_sensitivity_row = QHBoxLayout()
        self.spotify_vis_recommended = QCheckBox("Recommended")
        self.spotify_vis_recommended.setToolTip(
            "When enabled, the visualizer uses the recommended (v1.4) sensitivity baseline. Disable to adjust manually."
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
        self.spotify_vis_sensitivity.setValue(100)
        self.spotify_vis_sensitivity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.spotify_vis_sensitivity.setTickInterval(25)
        self.spotify_vis_sensitivity.valueChanged.connect(self._save_settings)
        spotify_vis_sensitivity_slider_row.addWidget(self.spotify_vis_sensitivity)
        self.spotify_vis_sensitivity_label = QLabel("1.00x")
        self.spotify_vis_sensitivity.valueChanged.connect(
            lambda v: self.spotify_vis_sensitivity_label.setText(f"{v / 100.0:.2f}x")
        )
        spotify_vis_sensitivity_slider_row.addWidget(self.spotify_vis_sensitivity_label)
        spotify_vis_layout.addLayout(spotify_vis_sensitivity_slider_row)

        # Ghosting controls: global enable, opacity and decay speed.
        spotify_vis_ghost_enable_row = QHBoxLayout()
        self.spotify_vis_ghost_enabled = QCheckBox("Enable Ghosting")
        self.spotify_vis_ghost_enabled.setChecked(True)
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
        self.spotify_vis_ghost_opacity.setValue(40)
        self.spotify_vis_ghost_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.spotify_vis_ghost_opacity.setTickInterval(5)
        self.spotify_vis_ghost_opacity.valueChanged.connect(self._save_settings)
        spotify_vis_ghost_opacity_row.addWidget(self.spotify_vis_ghost_opacity)
        self.spotify_vis_ghost_opacity_label = QLabel("40%")
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
        self.spotify_vis_ghost_decay.setValue(40)     # 0.40x default
        self.spotify_vis_ghost_decay.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.spotify_vis_ghost_decay.setTickInterval(5)
        self.spotify_vis_ghost_decay.valueChanged.connect(self._save_settings)
        spotify_vis_ghost_decay_row.addWidget(self.spotify_vis_ghost_decay)
        self.spotify_vis_ghost_decay_label = QLabel("0.40x")
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
        self.reddit_exit_on_click.stateChanged.connect(self._save_settings)
        reddit_layout.addWidget(self.reddit_exit_on_click)

        # Subreddit name
        reddit_sub_row = QHBoxLayout()
        reddit_sub_row.addWidget(QLabel("Subreddit:"))
        self.reddit_subreddit = QLineEdit()
        self.reddit_subreddit.setPlaceholderText("e.g. wallpapers")
        self.reddit_subreddit.textChanged.connect(self._save_settings)
        reddit_sub_row.addWidget(self.reddit_subreddit)
        reddit_layout.addLayout(reddit_sub_row)

        # Item count
        reddit_items_row = QHBoxLayout()
        reddit_items_row.addWidget(QLabel("Items:"))
        self.reddit_items = QComboBox()
        # Expose 4/10/20 item modes (legacy configs <=5 map to the 4-item option).
        self.reddit_items.addItems(["4", "10", "20"])
        self.reddit_items.currentTextChanged.connect(self._save_settings)
        self.reddit_items.currentTextChanged.connect(self._update_stack_status)
        reddit_items_row.addWidget(self.reddit_items)
        reddit_items_row.addStretch()
        reddit_layout.addLayout(reddit_items_row)

        # Position
        reddit_pos_row = QHBoxLayout()
        reddit_pos_row.addWidget(QLabel("Position:"))
        self.reddit_position = QComboBox()
        self.reddit_position.addItems([
            "Top Left", "Top Right",
            "Bottom Left", "Bottom Right",
        ])
        self.reddit_position.currentTextChanged.connect(self._save_settings)
        self.reddit_position.currentTextChanged.connect(self._update_stack_status)
        reddit_pos_row.addWidget(self.reddit_position)
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
        self.reddit_monitor_combo.currentTextChanged.connect(self._save_settings)
        self.reddit_monitor_combo.currentTextChanged.connect(self._update_stack_status)
        reddit_disp_row.addWidget(self.reddit_monitor_combo)
        reddit_disp_row.addStretch()
        reddit_layout.addLayout(reddit_disp_row)

        # Font family
        reddit_font_family_row = QHBoxLayout()
        reddit_font_family_row.addWidget(QLabel("Font:"))
        self.reddit_font_combo = QFontComboBox()
        self.reddit_font_combo.setCurrentFont("Segoe UI")
        self.reddit_font_combo.setMinimumWidth(220)
        self.reddit_font_combo.currentFontChanged.connect(self._save_settings)
        reddit_font_family_row.addWidget(self.reddit_font_combo)
        reddit_font_family_row.addStretch()
        reddit_layout.addLayout(reddit_font_family_row)

        # Font size
        reddit_font_row = QHBoxLayout()
        reddit_font_row.addWidget(QLabel("Font Size:"))
        self.reddit_font_size = QSpinBox()
        self.reddit_font_size.setRange(10, 72)
        self.reddit_font_size.setValue(18)
        self.reddit_font_size.setAccelerated(True)
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
        self.reddit_margin.setValue(20)
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
        self.reddit_show_background.stateChanged.connect(self._save_settings)
        reddit_layout.addWidget(self.reddit_show_background)

        self.reddit_show_separators = QCheckBox("Show separator lines between posts")
        self.reddit_show_separators.stateChanged.connect(self._save_settings)
        reddit_layout.addWidget(self.reddit_show_separators)

        # Background opacity
        reddit_opacity_row = QHBoxLayout()
        reddit_opacity_row.addWidget(QLabel("Background Opacity:"))
        self.reddit_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.reddit_bg_opacity.setMinimum(0)
        self.reddit_bg_opacity.setMaximum(100)
        self.reddit_bg_opacity.setValue(90)
        self.reddit_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.reddit_bg_opacity.setTickInterval(10)
        self.reddit_bg_opacity.valueChanged.connect(self._save_settings)
        reddit_opacity_row.addWidget(self.reddit_bg_opacity)
        self.reddit_bg_opacity_label = QLabel("90%")
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
        # Canonical default is 100% (1.0) to match SettingsManager
        # defaults; this will be overridden on load when a saved value
        # exists.
        self.reddit_border_opacity.setValue(100)
        self.reddit_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.reddit_border_opacity.setTickInterval(10)
        self.reddit_border_opacity.valueChanged.connect(self._save_settings)
        reddit_border_opacity_row.addWidget(self.reddit_border_opacity)
        self.reddit_border_opacity_label = QLabel("100%")
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
        self.reddit2_position.addItems(["Top Left", "Top Right", "Bottom Left", "Bottom Right"])
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
            """
        )

        # Default to "Clocks" subtab
        self._on_subtab_changed(0)

    def _on_subtab_changed(self, subtab_id: int) -> None:
        """Show/hide widget sections based on selected subtab."""
        try:
            self._clocks_container.setVisible(subtab_id == 0)
            self._weather_container.setVisible(subtab_id == 1)
            self._media_container.setVisible(subtab_id == 2)
            self._reddit_container.setVisible(subtab_id == 3)
        except Exception:
            # If containers are not yet initialized, ignore
            pass
    
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
            self.clock_enabled.setChecked(clock_config.get('enabled', False))
            
            format_text = "12 Hour" if clock_config.get('format', '12h') == '12h' else "24 Hour"
            index = self.clock_format.findText(format_text)
            if index >= 0:
                self.clock_format.setCurrentIndex(index)
            
            self.clock_seconds.setChecked(clock_config.get('show_seconds', True))
            
            # Load timezone settings
            timezone_str = clock_config.get('timezone', 'local')
            tz_index = self.clock_timezone.findData(timezone_str)
            if tz_index >= 0:
                self.clock_timezone.setCurrentIndex(tz_index)
            
            self.clock_show_tz.setChecked(clock_config.get('show_timezone', False))

            # Analogue mode configuration (main clock only). Secondary clocks
            # inherit style from Clock 1 in DisplayWidget._setup_widgets().
            display_mode = str(clock_config.get('display_mode', 'digital')).lower()
            self.clock_analog_mode.setChecked(display_mode == 'analog')

            show_numerals_val = clock_config.get('show_numerals', True)
            show_numerals = SettingsManager.to_bool(show_numerals_val, True)
            self.clock_show_numerals.setChecked(show_numerals)

            analog_shadow_val = clock_config.get('analog_face_shadow', True)
            analog_shadow = SettingsManager.to_bool(analog_shadow_val, True)
            self.clock_analog_shadow.setChecked(analog_shadow)

            intense_shadow_val = clock_config.get('analog_shadow_intense', False)
            intense_shadow = SettingsManager.to_bool(intense_shadow_val, False)
            self.clock_analog_shadow_intense.setChecked(intense_shadow)
            
            position = clock_config.get('position', 'Top Right')
            index = self.clock_position.findText(position)
            if index >= 0:
                self.clock_position.setCurrentIndex(index)
            
            self.clock_font_combo.setCurrentFont(QFont(clock_config.get('font_family', 'Segoe UI')))
            self.clock_font_size.setValue(clock_config.get('font_size', 48))
            self.clock_margin.setValue(clock_config.get('margin', 20))
            self.clock_show_background.setChecked(clock_config.get('show_background', False))
            opacity_pct = int(clock_config.get('bg_opacity', 0.9) * 100)
            self.clock_bg_opacity.setValue(opacity_pct)
            self.clock_opacity_label.setText(f"{opacity_pct}%")
            # Monitor selection
            monitor_sel = clock_config.get('monitor', 'ALL')
            mon_text = str(monitor_sel) if isinstance(monitor_sel, (int, str)) else 'ALL'
            idx = self.clock_monitor_combo.findText(mon_text)
            if idx >= 0:
                self.clock_monitor_combo.setCurrentIndex(idx)
            
            # Load clock color
            color_data = clock_config.get('color', [255, 255, 255, 230])
            self._clock_color = QColor(*color_data)
            bg_color_data = clock_config.get('bg_color', [64, 64, 64, 255])
            try:
                self._clock_bg_color = QColor(*bg_color_data)
            except Exception:
                self._clock_bg_color = QColor(64, 64, 64, 255)
            border_color_data = clock_config.get('border_color', [128, 128, 128, 255])
            try:
                self._clock_border_color = QColor(*border_color_data)
            except Exception:
                self._clock_border_color = QColor(128, 128, 128, 255)
            border_opacity_pct = int(clock_config.get('border_opacity', 0.8) * 100)
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

            self.weather_enabled.setChecked(weather_config.get('enabled', False))
            # No API key needed with Open-Meteo!
            self.weather_location.setText(weather_config.get('location', 'New York'))
            
            weather_pos = weather_config.get('position', 'Bottom Left')
            index = self.weather_position.findText(weather_pos)
            if index >= 0:
                self.weather_position.setCurrentIndex(index)
            
            self.weather_font_combo.setCurrentFont(QFont(weather_config.get('font_family', 'Segoe UI')))
            self.weather_font_size.setValue(weather_config.get('font_size', 24))
            self.weather_show_forecast.setChecked(weather_config.get('show_forecast', False))
            self.weather_show_background.setChecked(weather_config.get('show_background', False))
            weather_opacity_pct = int(weather_config.get('bg_opacity', 0.9) * 100)
            self.weather_bg_opacity.setValue(weather_opacity_pct)
            self.weather_opacity_label.setText(f"{weather_opacity_pct}%")
            
            # Load weather color
            weather_color_data = weather_config.get('color', [255, 255, 255, 230])
            self._weather_color = QColor(*weather_color_data)
            # Load weather background and border colors
            bg_color_data = weather_config.get('bg_color', [64, 64, 64, 255])
            try:
                self._weather_bg_color = QColor(*bg_color_data)
            except Exception:
                self._weather_bg_color = QColor(64, 64, 64, 255)
            border_color_data = weather_config.get('border_color', [128, 128, 128, 255])
            try:
                self._weather_border_color = QColor(*border_color_data)
            except Exception:
                self._weather_border_color = QColor(128, 128, 128, 255)
            border_opacity_pct = int(weather_config.get('border_opacity', 0.8) * 100)
            self.weather_border_opacity.setValue(border_opacity_pct)
            self.weather_border_opacity_label.setText(f"{border_opacity_pct}%")
            # Monitor selection
            w_monitor_sel = weather_config.get('monitor', 'ALL')
            w_mon_text = str(w_monitor_sel) if isinstance(w_monitor_sel, (int, str)) else 'ALL'
            idx = self.weather_monitor_combo.findText(w_mon_text)
            if idx >= 0:
                self.weather_monitor_combo.setCurrentIndex(idx)
            
            # Load media settings
            media_config = widgets.get('media', {})
            self.media_enabled.setChecked(media_config.get('enabled', False))

            media_pos = media_config.get('position', 'Bottom Left')
            index = self.media_position.findText(media_pos)
            if index >= 0:
                self.media_position.setCurrentIndex(index)

            self.media_font_combo.setCurrentFont(QFont(media_config.get('font_family', 'Segoe UI')))
            self.media_font_size.setValue(media_config.get('font_size', 20))
            self.media_margin.setValue(media_config.get('margin', 20))
            self.media_show_background.setChecked(media_config.get('show_background', False))
            media_opacity_pct = int(media_config.get('bg_opacity', 0.9) * 100)
            self.media_bg_opacity.setValue(media_opacity_pct)
            self.media_bg_opacity_label.setText(f"{media_opacity_pct}%")

            # Artwork size and controls visibility
            artwork_size = media_config.get('artwork_size', 100)
            try:
                self._media_artwork_size = int(artwork_size)
            except Exception:
                self._media_artwork_size = 100
            self.media_artwork_size.setValue(self._media_artwork_size)

            rounded_art = SettingsManager.to_bool(
                media_config.get('rounded_artwork_border', True), True
            )
            self.media_rounded_artwork.setChecked(rounded_art)

            show_header_frame = SettingsManager.to_bool(
                media_config.get('show_header_frame', True), True
            )
            self.media_show_header_frame.setChecked(show_header_frame)

            show_controls = SettingsManager.to_bool(media_config.get('show_controls', True), True)
            self.media_show_controls.setChecked(show_controls)

            spotify_volume_enabled = SettingsManager.to_bool(
                media_config.get('spotify_volume_enabled', True), True
            )
            self.media_spotify_volume_enabled.setChecked(spotify_volume_enabled)

            # Load media colors
            media_color_data = media_config.get('color', [255, 255, 255, 230])
            self._media_color = QColor(*media_color_data)
            media_bg_color_data = media_config.get('bg_color', [64, 64, 64, 255])
            try:
                self._media_bg_color = QColor(*media_bg_color_data)
            except Exception:
                self._media_bg_color = QColor(64, 64, 64, 255)
            media_border_color_data = media_config.get('border_color', [128, 128, 128, 255])
            try:
                self._media_border_color = QColor(*media_border_color_data)
            except Exception:
                self._media_border_color = QColor(128, 128, 128, 255)
            media_border_opacity_pct = int(media_config.get('border_opacity', 0.8) * 100)
            self.media_border_opacity.setValue(media_border_opacity_pct)
            self.media_border_opacity_label.setText(f"{media_border_opacity_pct}%")

            volume_fill_data = media_config.get('spotify_volume_fill_color', [255, 255, 255, 230])
            try:
                self._media_volume_fill_color = QColor(*volume_fill_data)
            except Exception:
                self._media_volume_fill_color = QColor(255, 255, 255, 230)

            m_monitor_sel = media_config.get('monitor', 'ALL')
            m_mon_text = str(m_monitor_sel) if isinstance(m_monitor_sel, (int, str)) else 'ALL'
            midx = self.media_monitor_combo.findText(m_mon_text)
            if midx >= 0:
                self.media_monitor_combo.setCurrentIndex(midx)

            # Load Spotify Beat Visualizer settings
            spotify_vis_config = widgets.get('spotify_visualizer', {})
            self.spotify_vis_enabled.setChecked(spotify_vis_config.get('enabled', False))
            bar_count = int(spotify_vis_config.get('bar_count', 32))
            self.spotify_vis_bar_count.setValue(bar_count)

            recommended_raw = spotify_vis_config.get('adaptive_sensitivity', True)
            recommended = SettingsManager.to_bool(recommended_raw, True)
            self.spotify_vis_recommended.setChecked(recommended)

            sens_val = spotify_vis_config.get('sensitivity', 1.0)
            try:
                sens_f = float(sens_val)
            except Exception:
                sens_f = 1.0
            sens_slider = int(max(0.25, min(2.5, sens_f)) * 100)
            self.spotify_vis_sensitivity.setValue(sens_slider)
            self.spotify_vis_sensitivity_label.setText(f"{sens_slider / 100.0:.2f}x")
            self._update_spotify_vis_sensitivity_enabled_state()

            software_enabled = bool(spotify_vis_config.get('software_visualizer_enabled', False))
            self.spotify_vis_software_enabled.setChecked(software_enabled)

            fill_color_data = spotify_vis_config.get('bar_fill_color', [0, 255, 128, 230])
            try:
                self._spotify_vis_fill_color = QColor(*fill_color_data)
            except Exception:
                self._spotify_vis_fill_color = QColor(0, 255, 128, 230)

            border_color_data = spotify_vis_config.get('bar_border_color', [255, 255, 255, 230])
            try:
                self._spotify_vis_border_color = QColor(*border_color_data)
            except Exception:
                self._spotify_vis_border_color = QColor(255, 255, 255, 230)

            border_opacity_pct = int(spotify_vis_config.get('bar_border_opacity', 0.85) * 100)
            self.spotify_vis_border_opacity.setValue(border_opacity_pct)
            self.spotify_vis_border_opacity_label.setText(f"{border_opacity_pct}%")

            # Ghosting settings
            ghost_enabled_raw = spotify_vis_config.get('ghosting_enabled', True)
            ghost_enabled = SettingsManager.to_bool(ghost_enabled_raw, True)
            self.spotify_vis_ghost_enabled.setChecked(ghost_enabled)

            ghost_alpha_val = spotify_vis_config.get('ghost_alpha', 0.4)
            try:
                ghost_alpha_pct = int(float(ghost_alpha_val) * 100)
            except Exception:
                ghost_alpha_pct = 40
            if ghost_alpha_pct < 0:
                ghost_alpha_pct = 0
            if ghost_alpha_pct > 100:
                ghost_alpha_pct = 100
            self.spotify_vis_ghost_opacity.setValue(ghost_alpha_pct)
            self.spotify_vis_ghost_opacity_label.setText(f"{ghost_alpha_pct}%")

            ghost_decay_val = spotify_vis_config.get('ghost_decay', 0.4)
            try:
                ghost_decay_f = float(ghost_decay_val)
            except Exception:
                ghost_decay_f = 0.4
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

            # Widget defaults to disabled even if config is present
            self.reddit_enabled.setChecked(SettingsManager.to_bool(reddit_config.get('enabled', False), False))

            exit_on_click_val = reddit_config.get('exit_on_click', True)
            exit_on_click = SettingsManager.to_bool(exit_on_click_val, True)
            self.reddit_exit_on_click.setChecked(exit_on_click)

            subreddit = str(reddit_config.get('subreddit', '') or '')
            if not subreddit:
                subreddit = 'wallpapers'
            self.reddit_subreddit.setText(subreddit)

            limit_val = int(reddit_config.get('limit', 10))
            if limit_val <= 5:
                items_text = "4"
            elif limit_val >= 20:
                items_text = "20"
            else:
                items_text = "10"
            idx_items = self.reddit_items.findText(items_text)
            if idx_items >= 0:
                self.reddit_items.setCurrentIndex(idx_items)

            reddit_pos = reddit_config.get('position', 'Bottom Right')
            idx_pos = self.reddit_position.findText(reddit_pos)
            if idx_pos >= 0:
                self.reddit_position.setCurrentIndex(idx_pos)

            r_monitor_sel = reddit_config.get('monitor', 1)
            r_mon_text = str(r_monitor_sel) if isinstance(r_monitor_sel, (int, str)) else '1'
            r_idx = self.reddit_monitor_combo.findText(r_mon_text)
            if r_idx >= 0:
                self.reddit_monitor_combo.setCurrentIndex(r_idx)

            reddit_font_size_data = reddit_config.get('font_size', 14)
            self.reddit_font_size.setValue(reddit_font_size_data)
            self.reddit_margin.setValue(reddit_config.get('margin', 20))

            show_bg_reddit = SettingsManager.to_bool(reddit_config.get('show_background', True), True)
            self.reddit_show_background.setChecked(show_bg_reddit)
            show_separators_val = reddit_config.get('show_separators', True)
            show_separators = SettingsManager.to_bool(show_separators_val, True)
            self.reddit_show_separators.setChecked(show_separators)
            reddit_opacity_pct = int(reddit_config.get('bg_opacity', 1.0) * 100)
            self.reddit_bg_opacity.setValue(reddit_opacity_pct)
            self.reddit_bg_opacity_label.setText(f"{reddit_opacity_pct}%")

            reddit_border_opacity_pct = int(reddit_config.get('border_opacity', 1.0) * 100)
            self.reddit_border_opacity.setValue(reddit_border_opacity_pct)
            self.reddit_border_opacity_label.setText(f"{reddit_border_opacity_pct}%")

            reddit_color_data = reddit_config.get('color', [255, 255, 255, 230])
            self._reddit_color = QColor(*reddit_color_data)
            reddit_bg_color_data = reddit_config.get('bg_color', [35, 35, 35, 255])
            try:
                self._reddit_bg_color = QColor(*reddit_bg_color_data)
            except Exception:
                self._reddit_bg_color = QColor(35, 35, 35, 255)
            reddit_border_color_data = reddit_config.get('border_color', [255, 255, 255, 255])
            try:
                self._reddit_border_color = QColor(*reddit_border_color_data)
            except Exception:
                self._reddit_border_color = QColor(255, 255, 255, 255)
            
            # Reddit 2 settings
            reddit2_config = widgets.get('reddit2', {})
            self.reddit2_enabled.setChecked(SettingsManager.to_bool(reddit2_config.get('enabled', False), False))
            self.reddit2_subreddit.setText(reddit2_config.get('subreddit', ''))
            reddit2_limit = int(reddit2_config.get('limit', 4))
            if reddit2_limit <= 5:
                reddit2_limit_text = "4"
            elif reddit2_limit >= 20:
                reddit2_limit_text = "20"
            else:
                reddit2_limit_text = "10"
            reddit2_items_idx = self.reddit2_items.findText(reddit2_limit_text)
            if reddit2_items_idx >= 0:
                self.reddit2_items.setCurrentIndex(reddit2_items_idx)
            reddit2_pos = reddit2_config.get('position', 'Top Left')
            reddit2_pos_idx = self.reddit2_position.findText(reddit2_pos)
            if reddit2_pos_idx >= 0:
                self.reddit2_position.setCurrentIndex(reddit2_pos_idx)
            reddit2_monitor = reddit2_config.get('monitor', 'ALL')
            reddit2_mon_text = str(reddit2_monitor) if isinstance(reddit2_monitor, (int, str)) else 'ALL'
            reddit2_mon_idx = self.reddit2_monitor_combo.findText(reddit2_mon_text)
            if reddit2_mon_idx >= 0:
                self.reddit2_monitor_combo.setCurrentIndex(reddit2_mon_idx)

            # Gmail settings - archived, see archive/gmail_feature/
        finally:
            for w in blockers:
                try:
                    w.blockSignals(False)
                except Exception:
                    pass
        
        # Update stack status labels after loading settings
        try:
            self._update_stack_status()
        except Exception:
            pass

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
        except Exception:
            pass
        # Get timezone from current selection
        tz_data = self.clock_timezone.currentData()
        timezone_str = tz_data if tz_data else 'local'
        
        format_text = ""
        try:
            format_text = (self.clock_format.currentText() or "").strip().lower()
        except Exception:
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
            'show_forecast': self.weather_show_forecast.isChecked(),
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
            'bar_count': self.spotify_vis_bar_count.value(),
            'software_visualizer_enabled': self.spotify_vis_software_enabled.isChecked(),
            'adaptive_sensitivity': self.spotify_vis_recommended.isChecked(),
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
        }

        self._update_spotify_vis_sensitivity_enabled_state()

        reddit_limit_text = self.reddit_items.currentText().strip()
        try:
            reddit_limit = int(reddit_limit_text)
        except Exception:
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
        except Exception:
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
        except Exception:
            pass

        self._settings.set('widgets', existing_widgets)
        self._settings.save()

    def _update_spotify_vis_sensitivity_enabled_state(self) -> None:
        try:
            recommended = self.spotify_vis_recommended.isChecked()
        except Exception:
            recommended = True
        try:
            self.spotify_vis_sensitivity.setEnabled(not recommended)
            self.spotify_vis_sensitivity_label.setEnabled(not recommended)
        except Exception:
            pass
    
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
            except Exception:
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
        except Exception:
            pass
        
        # Spotify Visualizer
        config['spotify_visualizer'] = {
            'enabled': getattr(self, 'spotify_vis_enabled', None) and self.spotify_vis_enabled.isChecked(),
            'monitor': getattr(self, 'spotify_vis_monitor_combo', None) and self.spotify_vis_monitor_combo.currentText() or 'ALL',
            'bar_count': getattr(self, 'spotify_vis_bar_count', None) and self.spotify_vis_bar_count.value() or 16,
        }
        
        return config
