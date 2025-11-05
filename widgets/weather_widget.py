"""
Weather widget for screensaver overlay.

Displays current weather information with API integration and caching.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtCore import QTimer, Qt, Signal, QThread, QObject
from PySide6.QtGui import QFont, QColor
import requests
import json

from core.logging.logger import get_logger

logger = get_logger(__name__)


class WeatherPosition(Enum):
    """Weather widget position on screen."""
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class WeatherFetcher(QObject):
    """Worker for fetching weather data in background thread."""
    
    # Signals
    data_fetched = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, api_key: str, location: str):
        """
        Initialize weather fetcher.
        
        Args:
            api_key: OpenWeatherMap API key
            location: City name or coordinates
        """
        super().__init__()
        self._api_key = api_key
        self._location = location
    
    def fetch(self) -> None:
        """Fetch weather data from API."""
        try:
            # OpenWeatherMap API endpoint
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                'q': self._location,
                'appid': self._api_key,
                'units': 'metric'  # Celsius
            }
            
            logger.debug(f"Fetching weather for {self._location}")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            self.data_fetched.emit(data)
            logger.info(f"Weather data fetched successfully for {self._location}")
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch weather: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error fetching weather: {e}"
            logger.exception(error_msg)
            self.error_occurred.emit(error_msg)


class WeatherWidget(QLabel):
    """
    Weather widget for displaying weather information.
    
    Features:
    - Current temperature and condition
    - Location display
    - Auto-update every 30 minutes
    - Caching to reduce API calls
    - Background fetching
    - Error handling
    """
    
    # Signals
    weather_updated = Signal(dict)  # Emits weather data
    error_occurred = Signal(str)
    
    def __init__(self, parent: Optional[QWidget] = None,
                 api_key: str = "",
                 location: str = "London",
                 position: WeatherPosition = WeatherPosition.BOTTOM_LEFT):
        """
        Initialize weather widget.
        
        Args:
            parent: Parent widget
            api_key: OpenWeatherMap API key
            location: City name or coordinates
            position: Screen position
        """
        super().__init__(parent)
        
        self._api_key = api_key
        self._location = location
        self._position = position
        self._update_timer: Optional[QTimer] = None
        self._enabled = False
        
        # Caching
        self._cached_data: Optional[Dict[str, Any]] = None
        self._cache_time: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=30)
        
        # Background thread
        self._fetch_thread: Optional[QThread] = None
        self._fetcher: Optional[WeatherFetcher] = None
        
        # Styling defaults
        self._font_family = "Segoe UI"
        self._font_size = 24
        self._text_color = QColor(255, 255, 255, 230)
        self._margin = 20
        
        # Setup UI
        self._setup_ui()
        
        logger.debug(f"WeatherWidget created (location={location}, position={position.value})")
    
    def _setup_ui(self) -> None:
        """Setup widget UI."""
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setStyleSheet(f"""
            QLabel {{
                color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                           {self._text_color.blue()}, {self._text_color.alpha()});
                background-color: transparent;
                padding: 10px 15px;
            }}
        """)
        
        font = QFont(self._font_family, self._font_size)
        self.setFont(font)
        
        # Initially hidden
        self.hide()
    
    def start(self) -> None:
        """Start weather updates."""
        if self._enabled:
            logger.warning("[FALLBACK] Weather widget already running")
            return
        
        if not self._api_key:
            error_msg = "No API key configured for weather widget"
            logger.error(error_msg)
            self.setText("Weather: No API Key")
            self.error_occurred.emit(error_msg)
            return
        
        # Fetch immediately
        self._fetch_weather()
        
        # Start update timer (30 minutes)
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._fetch_weather)
        self._update_timer.start(30 * 60 * 1000)  # 30 minutes
        
        self._enabled = True
        self.show()
        
        logger.info("Weather widget started")
    
    def stop(self) -> None:
        """Stop weather updates."""
        if not self._enabled:
            return
        
        if self._update_timer:
            try:
                self._update_timer.stop()
                self._update_timer.deleteLater()
            except RuntimeError:
                pass
            self._update_timer = None
        
        # Stop fetch thread if running
        if self._fetch_thread and self._fetch_thread.isRunning():
            self._fetch_thread.quit()
            self._fetch_thread.wait()
        
        self._enabled = False
        self.hide()
        
        logger.debug("Weather widget stopped")
    
    def is_running(self) -> bool:
        """Check if weather widget is running."""
        return self._enabled
    
    def _fetch_weather(self) -> None:
        """Fetch weather data (uses cache if valid)."""
        # Check cache
        if self._is_cache_valid():
            logger.debug("Using cached weather data")
            self._update_display(self._cached_data)
            return
        
        # Fetch from API in background
        logger.debug("Fetching fresh weather data")
        
        # Create worker thread
        self._fetch_thread = QThread()
        self._fetcher = WeatherFetcher(self._api_key, self._location)
        self._fetcher.moveToThread(self._fetch_thread)
        
        # Connect signals
        self._fetch_thread.started.connect(self._fetcher.fetch)
        self._fetcher.data_fetched.connect(self._on_weather_fetched)
        self._fetcher.error_occurred.connect(self._on_fetch_error)
        self._fetcher.data_fetched.connect(self._fetch_thread.quit)
        self._fetcher.error_occurred.connect(self._fetch_thread.quit)
        
        # Start thread
        self._fetch_thread.start()
    
    def _on_weather_fetched(self, data: Dict[str, Any]) -> None:
        """
        Handle fetched weather data.
        
        Args:
            data: Weather data from API
        """
        # Cache data
        self._cached_data = data
        self._cache_time = datetime.now()
        
        # Update display
        self._update_display(data)
        
        # Emit signal
        self.weather_updated.emit(data)
    
    def _on_fetch_error(self, error: str) -> None:
        """
        Handle fetch error.
        
        Args:
            error: Error message
        """
        # Try to use cached data if available
        if self._cached_data:
            logger.warning(f"Fetch failed, using cached data: {error}")
            self._update_display(self._cached_data)
        else:
            logger.error(f"Fetch failed with no cache: {error}")
            self.setText("Weather: Error")
        
        self.error_occurred.emit(error)
    
    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        if not self._cached_data or not self._cache_time:
            return False
        
        age = datetime.now() - self._cache_time
        return age < self._cache_duration
    
    def _update_display(self, data: Optional[Dict[str, Any]]) -> None:
        """
        Update widget display with weather data.
        
        Args:
            data: Weather data
        """
        if not data:
            self.setText("Weather: No Data")
            return
        
        try:
            # Extract data
            temp = data.get('main', {}).get('temp', 0)
            condition = data.get('weather', [{}])[0].get('main', 'Unknown')
            location = data.get('name', self._location)
            
            # Format display
            text = f"{location}\n{temp:.0f}°C - {condition}"
            self.setText(text)
            
            # Adjust size
            self.adjustSize()
            
            # Update position
            if self.parent():
                self._update_position()
            
        except Exception as e:
            logger.exception(f"Error updating weather display: {e}")
            self.setText("Weather: Error")
    
    def _update_position(self) -> None:
        """Update widget position based on settings."""
        if not self.parent():
            return
        
        parent_width = self.parent().width()
        parent_height = self.parent().height()
        widget_width = self.width()
        widget_height = self.height()
        
        # Calculate position
        if self._position == WeatherPosition.TOP_LEFT:
            x = self._margin
            y = self._margin
        elif self._position == WeatherPosition.TOP_RIGHT:
            x = parent_width - widget_width - self._margin
            y = self._margin
        elif self._position == WeatherPosition.BOTTOM_LEFT:
            x = self._margin
            y = parent_height - widget_height - self._margin
        elif self._position == WeatherPosition.BOTTOM_RIGHT:
            x = parent_width - widget_width - self._margin
            y = parent_height - widget_height - self._margin
        else:
            x = self._margin
            y = parent_height - widget_height - self._margin
        
        self.move(x, y)
    
    def set_api_key(self, api_key: str) -> None:
        """
        Set API key.
        
        Args:
            api_key: OpenWeatherMap API key
        """
        self._api_key = api_key
        logger.debug("API key updated")
        
        # Clear cache
        self._cached_data = None
        self._cache_time = None
    
    def set_location(self, location: str) -> None:
        """
        Set location.
        
        Args:
            location: City name or coordinates
        """
        self._location = location
        logger.debug(f"Location set to {location}")
        
        # Clear cache
        self._cached_data = None
        self._cache_time = None
        
        # Fetch new data if running
        if self._enabled:
            self._fetch_weather()
    
    def set_position(self, position: WeatherPosition) -> None:
        """
        Set widget position.
        
        Args:
            position: Screen position
        """
        self._position = position
        logger.debug(f"Position set to {position.value}")
        
        # Update position immediately if running
        if self._enabled:
            self._update_position()
    
    def set_font_size(self, size: int) -> None:
        """
        Set font size.
        
        Args:
            size: Font size in points
        """
        if size <= 0:
            logger.warning(f"[FALLBACK] Invalid font size {size}, using 24")
            size = 24
        
        self._font_size = size
        font = QFont(self._font_family, self._font_size)
        self.setFont(font)
        
        logger.debug(f"Font size set to {size}")
    
    def set_text_color(self, color: QColor) -> None:
        """
        Set text color.
        
        Args:
            color: Text color
        """
        self._text_color = color
        self.setStyleSheet(f"""
            QLabel {{
                color: rgba({color.red()}, {color.green()}, 
                           {color.blue()}, {color.alpha()});
                background-color: transparent;
                padding: 10px 15px;
            }}
        """)
        logger.debug(f"Text color set")
    
    def cleanup(self) -> None:
        """Clean up resources."""
        logger.debug("Cleaning up weather widget")
        self.stop()
