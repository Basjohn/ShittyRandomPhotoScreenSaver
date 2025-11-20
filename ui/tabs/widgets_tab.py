"""
Widgets configuration tab for settings dialog.

Allows users to configure overlay widgets:
- Clock widget (enable, position, format, size, font, style)
- Weather widget (enable, position, location, API key, size, font, style)
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QGroupBox, QCheckBox, QLineEdit, QColorDialog, QPushButton,
    QScrollArea, QSlider, QCompleter, QFontComboBox, QButtonGroup
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QFont

from core.settings.settings_manager import SettingsManager
from core.logging.logger import get_logger
from widgets.timezone_utils import get_local_timezone, get_common_timezones

logger = get_logger(__name__)


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

        # Subtab-style toggle buttons (Clocks / Weather / Media)
        subtab_row = QHBoxLayout()
        self._subtab_group = QButtonGroup(self)
        self._subtab_group.setExclusive(True)

        self._btn_clocks = QPushButton("Clocks")
        self._btn_weather = QPushButton("Weather")
        self._btn_media = QPushButton("Media")

        button_style = (
            "QPushButton {"
            " background-color: #2a2a2a;"
            " color: #ffffff;"
            " border: 1px solid #3a3a3a;"
            " border-radius: 4px;"
            " padding: 4px 12px;"
            " }"
            "QPushButton:checked {"
            " background-color: #3a3a3a;"
            " border-color: #5c5c5c;"
            " font-weight: bold;"
            " }"
        )

        for idx, btn in enumerate((self._btn_clocks, self._btn_weather, self._btn_media)):
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
        clock_layout.addWidget(self.clock_show_tz)

        # Analogue mode options
        self.clock_analog_mode = QCheckBox("Use Analogue Clock")
        self.clock_analog_mode.setToolTip(
            "Render the main clock as an analogue clock face with hour/minute/second hands."
        )
        self.clock_analog_mode.stateChanged.connect(self._save_settings)
        clock_layout.addWidget(self.clock_analog_mode)

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
        position_row.addWidget(self.clock_position)
        position_row.addStretch()
        clock_layout.addLayout(position_row)

        # Display (monitor selection)
        clock_disp_row = QHBoxLayout()
        clock_disp_row.addWidget(QLabel("Display:"))
        self.clock_monitor_combo = QComboBox()
        self.clock_monitor_combo.addItems(["ALL", "1", "2", "3"])  # monitor indices are 1-based
        self.clock_monitor_combo.currentTextChanged.connect(self._save_settings)
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
        self.clock_bg_opacity = QSlider(Qt.Orientation.Horizontal)
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
        self.clock_border_opacity = QSlider(Qt.Orientation.Horizontal)
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
        self.weather_enabled = QCheckBox("Enable Weather")
        self.weather_enabled.stateChanged.connect(self._save_settings)
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
        weather_pos_row.addWidget(self.weather_position)
        weather_pos_row.addStretch()
        weather_layout.addLayout(weather_pos_row)

        # Display (monitor selection)
        weather_disp_row = QHBoxLayout()
        weather_disp_row.addWidget(QLabel("Display:"))
        self.weather_monitor_combo = QComboBox()
        self.weather_monitor_combo.addItems(["ALL", "1", "2", "3"])  # monitor indices are 1-based
        self.weather_monitor_combo.currentTextChanged.connect(self._save_settings)
        weather_disp_row.addWidget(self.weather_monitor_combo)
        weather_disp_row.addStretch()
        weather_layout.addLayout(weather_disp_row)
        
        # Font family
        weather_font_family_row = QHBoxLayout()
        weather_font_family_row.addWidget(QLabel("Font:"))
        self.weather_font_combo = QFontComboBox()
        self.weather_font_combo.setCurrentFont("Segoe UI")
        self.weather_font_combo.currentFontChanged.connect(self._save_settings)
        weather_font_family_row.addWidget(self.weather_font_combo)
        weather_layout.addLayout(weather_font_family_row)
        
        # Font size
        weather_font_row = QHBoxLayout()
        weather_font_row.addWidget(QLabel("Font Size:"))
        self.weather_font_size = QSpinBox()
        self.weather_font_size.setRange(12, 72)
        self.weather_font_size.setValue(24)
        self.weather_font_size.setAccelerated(True)
        self.weather_font_size.valueChanged.connect(self._save_settings)
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
        
        # Background frame
        self.weather_show_background = QCheckBox("Show Background Frame")
        self.weather_show_background.stateChanged.connect(self._save_settings)
        weather_layout.addWidget(self.weather_show_background)
        
        # Background opacity
        weather_opacity_row = QHBoxLayout()
        weather_opacity_row.addWidget(QLabel("Background Opacity:"))
        self.weather_bg_opacity = QSlider(Qt.Orientation.Horizontal)
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
        self.weather_border_opacity = QSlider(Qt.Orientation.Horizontal)
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

        # Condition icons toggle
        self.weather_show_icons = QCheckBox("Show Condition Icons")
        self.weather_show_icons.stateChanged.connect(self._save_settings)
        weather_layout.addWidget(self.weather_show_icons)
        
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
        media_pos_row.addWidget(self.media_position)
        media_pos_row.addStretch()
        media_layout.addLayout(media_pos_row)

        media_disp_row = QHBoxLayout()
        media_disp_row.addWidget(QLabel("Display:"))
        self.media_monitor_combo = QComboBox()
        self.media_monitor_combo.addItems(["ALL", "1", "2", "3"])
        self.media_monitor_combo.currentTextChanged.connect(self._save_settings)
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
        self.media_bg_opacity = QSlider(Qt.Orientation.Horizontal)
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
        self.media_border_opacity = QSlider(Qt.Orientation.Horizontal)
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

        self._media_container = QWidget()
        media_container_layout = QVBoxLayout(self._media_container)
        media_container_layout.setContentsMargins(0, 20, 0, 0)
        media_container_layout.addWidget(media_group)
        layout.addWidget(self._media_container)
        
        layout.addStretch()
        
        # Set scroll area widget and add to main layout
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        # Default to "Clocks" subtab
        self._on_subtab_changed(0)

    def _on_subtab_changed(self, subtab_id: int) -> None:
        """Show/hide widget sections based on selected subtab."""
        try:
            self._clocks_container.setVisible(subtab_id == 0)
            self._weather_container.setVisible(subtab_id == 1)
            self._media_container.setVisible(subtab_id == 2)
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
            migrated = False

            if 'clock' not in widgets or not isinstance(widgets.get('clock'), dict) or not widgets.get('clock'):
                legacy_clock = {}
                if self._settings.contains('widgets.clock_enabled'):
                    legacy_clock['enabled'] = self._settings.get_bool('widgets.clock_enabled', False)
                legacy_format = self._settings.get('widgets.clock_format', None)
                if legacy_format:
                    legacy_clock['format'] = str(legacy_format).lower()
                legacy_tz = self._settings.get('widgets.clock_timezone', None)
                if legacy_tz:
                    legacy_clock['timezone'] = legacy_tz
                legacy_pos = self._settings.get('widgets.clock_position', None)
                if legacy_pos:
                    try:
                        pos_str = str(legacy_pos).replace('-', ' ')
                        pos_str = pos_str.title()
                        legacy_clock['position'] = pos_str
                    except Exception:
                        pass
                legacy_transparency = self._settings.get('widgets.clock_transparency', None)
                if legacy_transparency is not None:
                    try:
                        alpha = float(legacy_transparency)
                    except Exception:
                        alpha = 0.8
                    legacy_clock['bg_opacity'] = alpha
                    legacy_clock['show_background'] = alpha > 0.0
                if legacy_clock:
                    existing_clock = widgets.get('clock')
                    if isinstance(existing_clock, dict):
                        for k, v in legacy_clock.items():
                            if k not in existing_clock:
                                existing_clock[k] = v
                        widgets['clock'] = existing_clock
                    else:
                        widgets['clock'] = legacy_clock
                    migrated = True

            if 'weather' not in widgets or not isinstance(widgets.get('weather'), dict) or not widgets.get('weather'):
                legacy_weather = {}
                if self._settings.contains('widgets.weather_enabled'):
                    legacy_weather['enabled'] = self._settings.get_bool('widgets.weather_enabled', False)
                legacy_loc = self._settings.get('widgets.weather_location', None)
                if legacy_loc:
                    legacy_weather['location'] = legacy_loc
                legacy_wpos = self._settings.get('widgets.weather_position', None)
                if legacy_wpos:
                    try:
                        wpos_str = str(legacy_wpos).replace('-', ' ')
                        wpos_str = wpos_str.title()
                        legacy_weather['position'] = wpos_str
                    except Exception:
                        pass
                legacy_wtrans = self._settings.get('widgets.weather_transparency', None)
                if legacy_wtrans is not None:
                    try:
                        walpha = float(legacy_wtrans)
                    except Exception:
                        walpha = 0.8
                    legacy_weather['bg_opacity'] = walpha
                    legacy_weather['show_background'] = walpha > 0.0
                if legacy_weather:
                    existing_weather = widgets.get('weather')
                    if isinstance(existing_weather, dict):
                        for k, v in legacy_weather.items():
                            if k not in existing_weather:
                                existing_weather[k] = v
                        widgets['weather'] = existing_weather
                    else:
                        widgets['weather'] = legacy_weather
                    migrated = True

            if migrated:
                self._settings.set('widgets', widgets)
                self._settings.save()

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
                getattr(self, 'weather_show_background', None),
                getattr(self, 'weather_show_icons', None),
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
            self.weather_enabled.setChecked(weather_config.get('enabled', False))
            # No API key needed with Open-Meteo!
            self.weather_location.setText(weather_config.get('location', 'London'))
            
            weather_pos = weather_config.get('position', 'Bottom Left')
            index = self.weather_position.findText(weather_pos)
            if index >= 0:
                self.weather_position.setCurrentIndex(index)
            
            self.weather_font_combo.setCurrentFont(QFont(weather_config.get('font_family', 'Segoe UI')))
            self.weather_font_size.setValue(weather_config.get('font_size', 24))
            self.weather_show_background.setChecked(weather_config.get('show_background', False))
            show_icons = SettingsManager.to_bool(weather_config.get('show_icons', True), True)
            self.weather_show_icons.setChecked(show_icons)
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

            m_monitor_sel = media_config.get('monitor', 'ALL')
            m_mon_text = str(m_monitor_sel) if isinstance(m_monitor_sel, (int, str)) else 'ALL'
            midx = self.media_monitor_combo.findText(m_mon_text)
            if midx >= 0:
                self.media_monitor_combo.setCurrentIndex(midx)

            logger.debug("Loaded widget settings")
        finally:
            for w in blockers:
                try:
                    w.blockSignals(False)
                except Exception:
                    pass
    
    def _choose_clock_color(self) -> None:
        """Choose clock text color."""
        color = QColorDialog.getColor(self._clock_color, self, "Choose Clock Color")
        if color.isValid():
            self._clock_color = color
            self._save_settings()
    
    def _choose_clock_bg_color(self) -> None:
        """Choose clock background color."""
        color = QColorDialog.getColor(self._clock_bg_color, self, "Choose Clock Background Color")
        if color.isValid():
            self._clock_bg_color = color
            self._save_settings()
    
    def _choose_clock_border_color(self) -> None:
        """Choose clock border color."""
        color = QColorDialog.getColor(self._clock_border_color, self, "Choose Clock Border Color")
        if color.isValid():
            self._clock_border_color = color
            self._save_settings()
    
    def _choose_weather_color(self) -> None:
        """Choose weather text color."""
        color = QColorDialog.getColor(self._weather_color, self, "Choose Weather Color")
        if color.isValid():
            self._weather_color = color
            self._save_settings()
    
    def _choose_weather_bg_color(self) -> None:
        """Choose weather background color."""
        color = QColorDialog.getColor(self._weather_bg_color, self, "Choose Weather Background Color")
        if color.isValid():
            self._weather_bg_color = color
            self._save_settings()

    def _choose_weather_border_color(self) -> None:
        """Choose weather border color."""
        color = QColorDialog.getColor(self._weather_border_color, self, "Choose Weather Border Color")
        if color.isValid():
            self._weather_border_color = color
            self._save_settings()
    
    def _choose_media_color(self) -> None:
        """Choose media text color."""
        color = QColorDialog.getColor(self._media_color, self, "Choose Spotify Color")
        if color.isValid():
            self._media_color = color
            self._save_settings()

    def _choose_media_bg_color(self) -> None:
        """Choose media background color."""
        color = QColorDialog.getColor(self._media_bg_color, self, "Choose Spotify Background Color")
        if color.isValid():
            self._media_bg_color = color
            self._save_settings()

    def _choose_media_border_color(self) -> None:
        """Choose media border color."""
        color = QColorDialog.getColor(self._media_border_color, self, "Choose Spotify Border Color")
        if color.isValid():
            self._media_border_color = color
            self._save_settings()
    
    def _save_settings(self) -> None:
        """Save current settings."""
        if getattr(self, "_loading", False):
            return
        # Get timezone from current selection
        tz_data = self.clock_timezone.currentData()
        timezone_str = tz_data if tz_data else 'local'
        
        clock_config = {
            'enabled': self.clock_enabled.isChecked(),
            'format': '12h' if self.clock_format.currentText() == "12 Hour" else '24h',
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
            'show_background': self.weather_show_background.isChecked(),
            'show_icons': self.weather_show_icons.isChecked(),
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
            'artwork_size': self.media_artwork_size.value(),
            'rounded_artwork_border': self.media_rounded_artwork.isChecked(),
            'show_header_frame': self.media_show_header_frame.isChecked(),
            'show_controls': self.media_show_controls.isChecked(),
        }
        mmon_text = self.media_monitor_combo.currentText()
        media_config['monitor'] = mmon_text if mmon_text == 'ALL' else int(mmon_text)

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

        self._settings.set('widgets', existing_widgets)
        self._settings.save()
        self.widgets_changed.emit()
        
        logger.debug("Saved widget settings")
    
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
