# Widgets and UI Implementation

## Clock Widget

### Purpose
Display current time as overlay on screensaver.

### Features
- Digital or analog display
- 12h/24h format
- Timezone support
- Multiple clocks for different timezones
- Configurable position and transparency

### Implementation

```python
# widgets/clock_widget.py

from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPainter, QFont, QColor
from datetime import datetime
import pytz
import logging

logger = logging.getLogger("screensaver.widget.clock")

class ClockWidget(QLabel):
    """Clock overlay widget"""
    
    POSITIONS = {
        'top-left': (20, 20),
        'top-right': (-20, 20),
        'bottom-left': (20, -20),
        'bottom-right': (-20, -20),
    }
    
    def __init__(self, parent, position: str = 'top-right', format_24h: bool = True, 
                 timezone: str = 'local', transparency: float = 0.8):
        super().__init__(parent)
        
        self.format_24h = format_24h
        self.timezone = pytz.timezone(timezone) if timezone != 'local' else None
        self.transparency = transparency
        
        # Setup UI
        self._setup_ui()
        
        # Position
        self._set_position(position)
        
        # Update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_time)
        self.timer.start(1000)  # Update every second
        
        # Initial update
        self._update_time()
        
        logger.debug(f"ClockWidget created: {position}, 24h={format_24h}, tz={timezone}")
    
    def _setup_ui(self):
        """Setup UI styling"""
        self.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: 48px;
                font-weight: bold;
                font-family: 'Segoe UI', Arial, sans-serif;
                background: rgba(0, 0, 0, {self.transparency * 0.5});
                border-radius: 10px;
                padding: 15px 25px;
            }}
        """)
        self.setAlignment(Qt.AlignCenter)
    
    def _set_position(self, position: str):
        """Set widget position"""
        if position in self.POSITIONS:
            offset_x, offset_y = self.POSITIONS[position]
            
            # Position relative to parent
            parent_rect = self.parent().rect()
            
            if offset_x < 0:
                # Right align
                self.move(parent_rect.width() + offset_x - self.width(), 
                         offset_y if offset_y > 0 else parent_rect.height() + offset_y - self.height())
            else:
                # Left align
                self.move(offset_x, 
                         offset_y if offset_y > 0 else parent_rect.height() + offset_y - self.height())
    
    def _update_time(self):
        """Update time display"""
        if self.timezone:
            now = datetime.now(self.timezone)
        else:
            now = datetime.now()
        
        if self.format_24h:
            time_str = now.strftime('%H:%M:%S')
        else:
            time_str = now.strftime('%I:%M:%S %p')
        
        self.setText(time_str)
        self.adjustSize()
```

---

## Weather Widget

### Purpose
Display current weather conditions as overlay.

### Features
- Temperature display
- Weather condition icon
- Location name
- Auto-update every 30 minutes
- Configurable position and transparency

### Implementation

```python
# widgets/weather_widget.py

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap, QFont
from widgets.weather_provider import WeatherProvider
import logging

logger = logging.getLogger("screensaver.widget.weather")

class WeatherWidget(QWidget):
    """Weather overlay widget"""
    
    POSITIONS = {
        'top-left': (20, 20),
        'top-right': (-220, 20),
        'bottom-left': (20, -120),
        'bottom-right': (-220, -120),
    }
    
    def __init__(self, parent, position: str, location: str, transparency: float = 0.8):
        super().__init__(parent)
        
        self.location = location
        self.transparency = transparency
        self.weather_provider = WeatherProvider()
        
        # Setup UI
        self._setup_ui()
        
        # Position
        self._set_position(position)
        
        # Update timer (30 minutes)
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_weather)
        self.timer.start(30 * 60 * 1000)
        
        # Initial update
        self._update_weather()
        
        logger.debug(f"WeatherWidget created: {position}, location={location}")
    
    def _setup_ui(self):
        """Setup UI"""
        self.setFixedSize(200, 100)
        self.setStyleSheet(f"""
            QWidget {{
                background: rgba(0, 0, 0, {self.transparency * 0.5});
                border-radius: 10px;
                padding: 10px;
            }}
            QLabel {{
                color: white;
                background: transparent;
            }}
        """)
        
        layout = QVBoxLayout(self)
        
        # Temperature
        self.temp_label = QLabel("--°")
        self.temp_label.setFont(QFont("Segoe UI", 36, QFont.Bold))
        self.temp_label.setAlignment(Qt.AlignCenter)
        
        # Condition
        self.condition_label = QLabel("Loading...")
        self.condition_label.setFont(QFont("Segoe UI", 12))
        self.condition_label.setAlignment(Qt.AlignCenter)
        
        # Location
        self.location_label = QLabel(self.location)
        self.location_label.setFont(QFont("Segoe UI", 10))
        self.location_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.temp_label)
        layout.addWidget(self.condition_label)
        layout.addWidget(self.location_label)
    
    def _set_position(self, position: str):
        """Set widget position"""
        if position in self.POSITIONS:
            offset_x, offset_y = self.POSITIONS[position]
            
            parent_rect = self.parent().rect()
            
            x = offset_x if offset_x > 0 else parent_rect.width() + offset_x
            y = offset_y if offset_y > 0 else parent_rect.height() + offset_y
            
            self.move(x, y)
    
    def _update_weather(self):
        """Update weather data"""
        logger.debug(f"Updating weather for {self.location}")
        
        try:
            data = self.weather_provider.get_weather(self.location)
            
            if data:
                temp = data.get('temp', '--')
                condition = data.get('condition', 'Unknown')
                
                self.temp_label.setText(f"{temp}°")
                self.condition_label.setText(condition)
                
                logger.debug(f"Weather updated: {temp}°, {condition}")
            else:
                logger.warning("Weather data not available")
                
        except Exception as e:
            logger.error(f"Failed to update weather: {e}")
```

---

## Weather Provider

### Purpose
Fetch weather data from API.

### Implementation

```python
# widgets/weather_provider.py

import requests
import logging

logger = logging.getLogger("screensaver.weather")

class WeatherProvider:
    """Weather data provider using wttr.in API"""
    
    def __init__(self):
        self.base_url = "https://wttr.in"
        self.cache = {}
    
    def get_weather(self, location: str) -> dict:
        """
        Get weather for location.
        
        Args:
            location: Location name or coordinates
            
        Returns:
            Dict with temp, condition, etc.
        """
        # Check cache
        if location in self.cache:
            logger.debug(f"Using cached weather for {location}")
            return self.cache[location]
        
        try:
            # Fetch from API
            url = f"{self.base_url}/{location}?format=j1"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Parse current conditions
            current = data.get('current_condition', [{}])[0]
            
            weather_data = {
                'temp': current.get('temp_C', '--'),
                'condition': current.get('weatherDesc', [{}])[0].get('value', 'Unknown'),
                'humidity': current.get('humidity', '--'),
                'wind_speed': current.get('windspeedKmph', '--'),
            }
            
            # Cache
            self.cache[location] = weather_data
            
            logger.info(f"Weather fetched for {location}: {weather_data['temp']}°C")
            
            return weather_data
            
        except Exception as e:
            logger.error(f"Failed to fetch weather for {location}: {e}")
            return None
```

---

## Spotify Media Widget (Spotify)

### Purpose
Provide a Spotify-specific "Now Playing" overlay that surfaces track metadata and optional artwork from the Windows 10/11 media controls layer, using the centralized media controller abstraction.

### Behaviour
- **Spotify-only**: The underlying `WindowsGlobalMediaController` queries GSMTC sessions and picks only those whose `source_app_user_model_id` contains `spotify`. Other players (VLC, browser audio, etc.) are ignored for this widget.
- **Hide-on-no-media**: When there is no active Spotify session or the controller cannot retrieve media properties, the widget hides itself entirely (no placeholder text is rendered).
- **Display when active**:
  - Header line: `SPOTIFY` label.
  - State line: `▶ Playing`, `⏸ Paused`, `■ Stopped`, or `Now Playing`.
  - Metadata line: `title · artist · album`, or `(no metadata)` when all three fields are empty.
  - Optional album artwork drawn on the left when `MediaTrackInfo.artwork` is populated.
  - Optional Spotify logo drawn on the left (from `/images/spotify_logo.png` or variants) when artwork is not available.
- **Artwork fade-in**: The first time artwork becomes available for a track, the widget runs a short `QVariantAnimation` to fade the artwork from 0 → 1 opacity while keeping the text stable.

### Integration & Settings
- Implemented as `MediaWidget` in `widgets/media_widget.py`.
- Created from `rendering/display_widget.DisplayWidget._setup_widgets()` when `widgets.media.enabled` is `True` and the per-monitor filter matches the current display.
- Uses the `widgets.media` settings block from Spec/SettingsManager:
  - `enabled`, `monitor`, `position` (corner), `font_family`, `font_size`, `margin`
  - `show_background`, `bg_color`, `bg_opacity`, `border_color`, `border_opacity`
- Polling is timer-based (~1.5s interval) and calls `BaseMediaController.get_current_track()` to refresh the label contents.

### Interaction Gating
- `MediaWidget` itself is marked `WA_TransparentForMouseEvents` and is non-interactive by default.
- `DisplayWidget.mousePressEvent()` owns input and decides whether clicks should:
  - Exit the screensaver (normal mode), or
  - Be treated as Spotify transport controls during **Ctrl-held** or **hard-exit** interaction modes.
- When interaction mode is active and the click is inside the media widget geometry:
  - Left click → `MediaWidget.play_pause()`
  - Right click → `MediaWidget.next_track()`
  - Middle click → `MediaWidget.previous_track()`
- This preserves the global "click to exit" behaviour unless the user is clearly signalling intent (Ctrl halo or hard-exit).

---

## Settings Dialog

### Purpose
Main configuration GUI for the screensaver.

### Features
- Dark themed using dark.qss
- Side-tab navigation
- Four tabs: Sources, Transitions, Widgets, About
- Instant save and apply
- 16:9 aspect ratio (1080x720 minimum)

### Implementation

```python
# ui/settings_dialog.py

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QStackedWidget, QWidget, QLabel)
from PySide6.QtCore import Qt, QSize
from ui.sources_tab import SourcesTab
from ui.transitions_tab import TransitionsTab
from ui.widgets_tab import WidgetsTab
from ui.about_tab import AboutTab
import logging

logger = logging.getLogger("screensaver.ui.settings")

class SettingsDialog(QDialog):
    """Main settings dialog"""
    
    def __init__(self, settings_manager):
        super().__init__()
        
        self.settings_manager = settings_manager
        
        # Setup window
        self.setWindowTitle("Screensaver Settings")
        self.setMinimumSize(1080, 720)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        
        # Setup UI
        self._setup_ui()
        
        # Load settings
        self._load_settings()
        
        logger.info("SettingsDialog opened")
    
    def _setup_ui(self):
        """Setup UI"""
        main_layout = QHBoxLayout(self)
        
        # Side tab bar
        self.tab_bar = self._create_tab_bar()
        main_layout.addWidget(self.tab_bar)
        
        # Content area
        self.content_stack = QStackedWidget()
        
        # Create tabs
        self.sources_tab = SourcesTab(self.settings_manager)
        self.transitions_tab = TransitionsTab(self.settings_manager)
        self.widgets_tab = WidgetsTab(self.settings_manager)
        self.about_tab = AboutTab()
        
        self.content_stack.addWidget(self.sources_tab)
        self.content_stack.addWidget(self.transitions_tab)
        self.content_stack.addWidget(self.widgets_tab)
        self.content_stack.addWidget(self.about_tab)
        
        main_layout.addWidget(self.content_stack, 1)
        
        # Connect tab buttons
        self.sources_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))
        self.transitions_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(1))
        self.widgets_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(2))
        self.about_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(3))
    
    def _create_tab_bar(self) -> QWidget:
        """Create side tab bar"""
        tab_widget = QWidget()
        tab_widget.setFixedWidth(200)
        tab_widget.setObjectName("settingsDialogBorder")
        
        layout = QVBoxLayout(tab_widget)
        
        # Title
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; padding: 10px;")
        layout.addWidget(title)
        
        # Tab buttons
        self.sources_btn = self._create_tab_button("Sources")
        self.transitions_btn = self._create_tab_button("Transitions")
        self.widgets_btn = self._create_tab_button("Widgets")
        self.about_btn = self._create_tab_button("About")
        
        layout.addWidget(self.sources_btn)
        layout.addWidget(self.transitions_btn)
        layout.addWidget(self.widgets_btn)
        layout.addSpacing(20)
        layout.addWidget(self.about_btn)
        layout.addStretch()
        
        return tab_widget
    
    def _create_tab_button(self, text: str) -> QPushButton:
        """Create tab button"""
        btn = QPushButton(text)
        btn.setObjectName("selectButton")
        btn.setMinimumHeight(50)
        btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 20px;
                font-size: 16px;
            }
        """)
        return btn
    
    def _load_settings(self):
        """Load current settings"""
        self.settings_manager.load()
    
    def closeEvent(self, event):
        """Handle dialog close"""
        # Settings are saved instantly, so nothing to do
        logger.info("SettingsDialog closed")
        event.accept()
```

---

## Sources Tab

### Implementation

```python
# ui/sources_tab.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QListWidget, QFileDialog, QLineEdit, QCheckBox, QGroupBox)
from PySide6.QtCore import Qt
import logging

logger = logging.getLogger("screensaver.ui.sources")

class SourcesTab(QWidget):
    """Sources configuration tab"""
    
    def __init__(self, settings_manager):
        super().__init__()
        
        self.settings_manager = settings_manager
        
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Image Sources")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(title)
        
        # Folders group
        folders_group = QGroupBox("Local Folders")
        folders_layout = QVBoxLayout(folders_group)
        
        # Folder checkbox
        self.folders_check = QCheckBox("Enable local folders")
        self.folders_check.stateChanged.connect(self._on_folders_toggled)
        folders_layout.addWidget(self.folders_check)
        
        # Folder list
        self.folders_list = QListWidget()
        folders_layout.addWidget(self.folders_list)
        
        # Folder buttons
        folder_btns = QHBoxLayout()
        self.add_folder_btn = QPushButton("Add Folder")
        self.add_folder_btn.setObjectName("actionButton")
        self.add_folder_btn.clicked.connect(self._on_add_folder)
        
        self.remove_folder_btn = QPushButton("Remove")
        self.remove_folder_btn.setObjectName("actionButton")
        self.remove_folder_btn.clicked.connect(self._on_remove_folder)
        
        folder_btns.addWidget(self.add_folder_btn)
        folder_btns.addWidget(self.remove_folder_btn)
        folders_layout.addLayout(folder_btns)
        
        layout.addWidget(folders_group)
        
        # RSS group
        rss_group = QGroupBox("RSS Feeds")
        rss_layout = QVBoxLayout(rss_group)
        
        # RSS checkbox
        self.rss_check = QCheckBox("Enable RSS feeds")
        self.rss_check.stateChanged.connect(self._on_rss_toggled)
        rss_layout.addWidget(self.rss_check)
        
        # RSS list
        self.rss_list = QListWidget()
        rss_layout.addWidget(self.rss_list)
        
        # RSS input
        rss_input = QHBoxLayout()
        self.rss_input = QLineEdit()
        self.rss_input.setPlaceholderText("Enter RSS feed URL...")
        
        self.add_rss_btn = QPushButton("Add")
        self.add_rss_btn.setObjectName("actionButton")
        self.add_rss_btn.clicked.connect(self._on_add_rss)
        
        self.remove_rss_btn = QPushButton("Remove")
        self.remove_rss_btn.setObjectName("actionButton")
        self.remove_rss_btn.clicked.connect(self._on_remove_rss)
        
        rss_input.addWidget(self.rss_input)
        rss_input.addWidget(self.add_rss_btn)
        rss_input.addWidget(self.remove_rss_btn)
        rss_layout.addLayout(rss_input)
        
        layout.addWidget(rss_group)
        
        layout.addStretch()
    
    def _load_settings(self):
        """Load current settings"""
        # Load folders
        folders = self.settings_manager.get('sources.folders', [])
        self.folders_list.addItems(folders)
        
        # Load RSS feeds
        feeds = self.settings_manager.get('sources.rss_feeds', [])
        self.rss_list.addItems(feeds)
        
        # Load source mode
        mode = self.settings_manager.get('sources.mode', 'folders')
        self.folders_check.setChecked(mode in ('folders', 'both'))
        self.rss_check.setChecked(mode in ('rss', 'both'))
    
    def _on_add_folder(self):
        """Add folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folders_list.addItem(folder)
            self._save_folders()
    
    def _on_remove_folder(self):
        """Remove selected folder"""
        current = self.folders_list.currentRow()
        if current >= 0:
            self.folders_list.takeItem(current)
            self._save_folders()
    
    def _on_add_rss(self):
        """Add RSS feed"""
        url = self.rss_input.text().strip()
        if url:
            self.rss_list.addItem(url)
            self.rss_input.clear()
            self._save_rss()
    
    def _on_remove_rss(self):
        """Remove selected RSS feed"""
        current = self.rss_list.currentRow()
        if current >= 0:
            self.rss_list.takeItem(current)
            self._save_rss()
    
    def _on_folders_toggled(self):
        """Handle folders checkbox"""
        self._save_mode()
    
    def _on_rss_toggled(self):
        """Handle RSS checkbox"""
        self._save_mode()
    
    def _save_folders(self):
        """Save folders to settings"""
        folders = [self.folders_list.item(i).text() for i in range(self.folders_list.count())]
        self.settings_manager.set('sources.folders', folders)
        self.settings_manager.save()
        logger.debug(f"Folders saved: {len(folders)}")
    
    def _save_rss(self):
        """Save RSS feeds to settings"""
        feeds = [self.rss_list.item(i).text() for i in range(self.rss_list.count())]
        self.settings_manager.set('sources.rss_feeds', feeds)
        self.settings_manager.save()
        logger.debug(f"RSS feeds saved: {len(feeds)}")
    
    def _save_mode(self):
        """Save source mode"""
        folders_enabled = self.folders_check.isChecked()
        rss_enabled = self.rss_check.isChecked()
        
        if folders_enabled and rss_enabled:
            mode = 'both'
        elif rss_enabled:
            mode = 'rss'
        else:
            mode = 'folders'
        
        self.settings_manager.set('sources.mode', mode)
        self.settings_manager.save()
        logger.debug(f"Source mode saved: {mode}")
```

---

**Next Document**: `08_TESTING_AND_DEPLOYMENT.md` - Testing strategy and deployment
