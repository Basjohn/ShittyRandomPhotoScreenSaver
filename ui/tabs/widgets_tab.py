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
    QScrollArea, QSlider, QCompleter, QFontComboBox
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
        self._setup_ui()
        self._load_settings()
        
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
        
        # Font family
        font_family_row = QHBoxLayout()
        font_family_row.addWidget(QLabel("Font:"))
        self.clock_font_combo = QFontComboBox()
        self.clock_font_combo.setCurrentFont("Segoe UI")
        self.clock_font_combo.currentFontChanged.connect(self._save_settings)
        font_family_row.addWidget(self.clock_font_combo)
        clock_layout.addLayout(font_family_row)
        
        # Font size
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Font Size:"))
        self.clock_font_size = QSpinBox()
        self.clock_font_size.setRange(12, 144)
        self.clock_font_size.setValue(48)
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
        
        layout.addWidget(clock_group)
        
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
        
        layout.addWidget(weather_group)
        
        layout.addStretch()
        
        # Set scroll area widget and add to main layout
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def _load_settings(self) -> None:
        """Load settings from settings manager."""
        # Block all signals during load to prevent unintended saves from valueChanged/stateChanged
        blockers = []
        try:
            for w in [
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
                getattr(self, 'weather_enabled', None),
                getattr(self, 'weather_location', None),
                getattr(self, 'weather_position', None),
                getattr(self, 'weather_font_combo', None),
                getattr(self, 'weather_font_size', None),
                getattr(self, 'weather_show_background', None),
                getattr(self, 'weather_bg_opacity', None),
            ]:
                if w is not None and hasattr(w, 'blockSignals'):
                    w.blockSignals(True)
                    blockers.append(w)

            # Load clock settings
            clock_config = self._settings.get('widgets', {}).get('clock', {})
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
            
            # Load clock color
            color_data = clock_config.get('color', [255, 255, 255, 230])
            self._clock_color = QColor(*color_data)
            
            # Load weather settings
            weather_config = self._settings.get('widgets', {}).get('weather', {})
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
            weather_opacity_pct = int(weather_config.get('bg_opacity', 0.9) * 100)
            self.weather_bg_opacity.setValue(weather_opacity_pct)
            self.weather_opacity_label.setText(f"{weather_opacity_pct}%")
            
            # Load weather color
            weather_color_data = weather_config.get('color', [255, 255, 255, 230])
            self._weather_color = QColor(*weather_color_data)
            
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
    
    def _choose_weather_color(self) -> None:
        """Choose weather text color."""
        color = QColorDialog.getColor(self._weather_color, self, "Choose Weather Color")
        if color.isValid():
            self._weather_color = color
            self._save_settings()
    
    def _save_settings(self) -> None:
        """Save current settings."""
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
            'color': [self._clock_color.red(), self._clock_color.green(), 
                     self._clock_color.blue(), self._clock_color.alpha()]
        }
        
        weather_config = {
            'enabled': self.weather_enabled.isChecked(),
            # No api_key needed with Open-Meteo!
            'location': self.weather_location.text(),
            'position': self.weather_position.currentText(),
            'font_family': self.weather_font_combo.currentFont().family(),
            'font_size': self.weather_font_size.value(),
            'show_background': self.weather_show_background.isChecked(),
            'bg_opacity': self.weather_bg_opacity.value() / 100.0,
            'color': [self._weather_color.red(), self._weather_color.green(), 
                     self._weather_color.blue(), self._weather_color.alpha()]
        }
        
        widgets_config = {
            'clock': clock_config,
            'weather': weather_config
        }
        
        self._settings.set('widgets', widgets_config)
        self._settings.save()
        self.widgets_changed.emit()
        
        logger.debug("Saved widget settings")
    
    def _populate_timezones(self) -> None:
        """Populate timezone dropdown with common timezones and UTC offsets."""
        # Get common timezones
        timezones = get_common_timezones()
        
        for display_name, tz_str in timezones:
            self.clock_timezone.addItem(display_name, tz_str)
        
        logger.debug(f"Populated {len(timezones)} timezones")
    
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
