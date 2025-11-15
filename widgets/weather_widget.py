"""
Weather widget for screensaver overlay.

Displays current weather information using Open-Meteo API (no API key needed).
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
from PySide6.QtWidgets import QLabel, QWidget, QGraphicsOpacityEffect
from PySide6.QtCore import QTimer, Qt, Signal, QThread, QObject, QPropertyAnimation
from PySide6.QtGui import QFont, QColor

from core.logging.logger import get_logger
from weather.open_meteo_provider import OpenMeteoProvider

logger = get_logger(__name__)


class WeatherPosition(Enum):
    """Weather widget position on screen."""
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class WeatherFetcher(QObject):
    """Worker for fetching weather data in background thread using Open-Meteo API."""
    
    # Signals
    data_fetched = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, location: str):
        """
        Initialize weather fetcher.
        
        Args:
            location: City name
        """
        super().__init__()
        self._location = location
        self._provider = OpenMeteoProvider(timeout=10)
    
    def fetch(self) -> None:
        """Fetch weather data from Open-Meteo API."""
        try:
            logger.debug(f"Fetching weather for {self._location}")
            
            # Fetch weather using Open-Meteo (no API key needed!)
            data = self._provider.get_current_weather(self._location)
            
            if data:
                self.data_fetched.emit(data)
                logger.info(f"Weather data fetched successfully for {self._location}")
            else:
                error_msg = f"No weather data returned for {self._location}"
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
    - No API key required (uses Open-Meteo)
    - Error handling
    """
    
    # Signals
    weather_updated = Signal(dict)  # Emits weather data
    error_occurred = Signal(str)
    
    def __init__(self, parent: Optional[QWidget] = None,
                 location: str = "London",
                 position: WeatherPosition = WeatherPosition.BOTTOM_LEFT):
        """
        Initialize weather widget.
        
        Args:
            parent: Parent widget
            location: City name
            position: Screen position
        """
        super().__init__(parent)
        
        self._location = location
        self._position = position
        self._update_timer: Optional[QTimer] = None
        self._enabled = False
        
        # Caching
        self._cached_data: Optional[Dict[str, Any]] = None
        self._cache_time: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=30)
        self._has_displayed_valid_data = False
        self._pending_first_show = False
        
        # Background thread
        self._fetch_thread: Optional[QThread] = None
        self._fetcher: Optional[WeatherFetcher] = None
        
        # Styling defaults
        self._font_family = "Segoe UI"
        self._font_size = 24
        self._text_color = QColor(255, 255, 255, 230)
        self._margin = 20
        
        # Background frame settings
        self._show_background = False
        self._bg_opacity = 0.9  # 90% opacity default
        self._bg_color = QColor(64, 64, 64, int(255 * self._bg_opacity))  # Dark grey
        self._bg_border_width = 2
        self._bg_border_color = QColor(128, 128, 128, 200)  # Light grey border
        self._fade_effect: Optional[QGraphicsOpacityEffect] = None
        self._fade_anim: Optional[QPropertyAnimation] = None
        
        # Setup UI
        self._setup_ui()
        
        logger.debug(f"WeatherWidget created (location={location}, position={position.value})")
    
    def _setup_ui(self) -> None:
        """Setup widget UI."""
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception:
            pass
        self._update_stylesheet()
        
        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)  # Lighter weight than clock
        self.setFont(font)
        
        # Initially hidden
        self.hide()
    
    def start(self) -> None:
        """Start weather updates."""
        if self._enabled:
            logger.warning("[FALLBACK] Weather widget already running")
            return
        
        if not self._location:
            error_msg = "No location configured for weather widget"
            logger.error(error_msg)
            self.setText("Weather: No Location")
            try:
                self.adjustSize()
                if self.parent():
                    self._update_position()
            except Exception:
                pass
            self.show()
            self.error_occurred.emit(error_msg)
            return

        if self._is_cache_valid():
            self._update_display(self._cached_data)
            self._has_displayed_valid_data = True
            self._enabled = True
            self.show()

            self._fetch_weather()
            self._update_timer = QTimer(self)
            self._update_timer.timeout.connect(self._fetch_weather)
            self._update_timer.start(30 * 60 * 1000)

            logger.info("Weather widget started (using cached data)")
            return

        self.hide()
        self._pending_first_show = True

        self._fetch_weather()
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._fetch_weather)
        self._update_timer.start(30 * 60 * 1000)

        self._enabled = True

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
        self._pending_first_show = False
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
        self._fetcher = WeatherFetcher(self._location)
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
        
        if self._pending_first_show and not self._has_displayed_valid_data:
            self._pending_first_show = False
            self._has_displayed_valid_data = True
            self._fade_in()
        else:
            self.show()

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
            # Try modern provider format first (Open-Meteo)
            temp = data.get('temperature')
            condition = data.get('condition')
            location = data.get('location')

            # Back-compat: OpenWeather-style nested JSON (used in tests/mock data)
            if temp is None and isinstance(data.get('main'), dict):
                temp = data['main'].get('temp')
            if condition is None and isinstance(data.get('weather'), list) and data['weather']:
                weather_entry = data['weather'][0]
                condition = weather_entry.get('main') or weather_entry.get('description')
            if not location:
                location = data.get('name') or self._location

            # Normalize extracted values
            if temp is None:
                temp = 0.0
            if condition is None:
                condition = 'Unknown'
            if not location:
                location = self._location
            
            # Relative sizing
            city_pt = max(6, self._font_size + 2)
            details_pt = max(6, self._font_size - 2)
            city_html = f"<div style='font-size:{city_pt}pt; font-weight:700;'>{location}</div>"
            details_text = f"{temp:.0f}°C - {condition}"
            details_html = f"<div style='font-size:{details_pt}pt; font-weight:500;'>{details_text}</div>"
            html = f"<div style='line-height:1.0'>{city_html}{details_html}</div>"
            self.setTextFormat(Qt.TextFormat.RichText)
            self.setText(html)
            
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
        
        # Calculate position with 20px minimum margin from all edges
        edge_margin = 20
        if self._position == WeatherPosition.TOP_LEFT:
            x = edge_margin
            y = edge_margin
        elif self._position == WeatherPosition.TOP_RIGHT:
            x = parent_width - widget_width - edge_margin
            y = edge_margin
        elif self._position == WeatherPosition.BOTTOM_LEFT:
            x = edge_margin
            y = parent_height - widget_height - edge_margin
        elif self._position == WeatherPosition.BOTTOM_RIGHT:
            x = parent_width - widget_width - edge_margin
            y = parent_height - widget_height - edge_margin
        else:
            x = edge_margin
            y = parent_height - widget_height - edge_margin
        
        self.move(x, y)
    
    def set_location(self, location: str) -> None:
        """
        Set location.
        
        Args:
            location: City name or coordinates
        """
        self._location = location
        
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
        
        # Update position immediately if running
        if self._enabled:
            self._update_position()
    
    def set_font_family(self, family: str) -> None:
        """
        Set font family.
        
        Args:
            family: Font family name
        """
        self._font_family = family
        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)
    
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
        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)
    
    def set_text_color(self, color: QColor) -> None:
        """
        Set text color.
        
        Args:
            color: Text color
        """
        self._text_color = color
        self._update_stylesheet()
    
    def set_show_background(self, show: bool) -> None:
        """
        Set whether to show background frame.
        
        Args:
            show: True to show background frame
        """
        self._show_background = show
        self._update_stylesheet()
    
    def set_background_color(self, color: QColor) -> None:
        """
        Set background frame color.
        
        Args:
            color: Background color (with alpha for opacity)
        """
        self._bg_color = color
        if self._show_background:
            self._update_stylesheet()
    
    def set_background_opacity(self, opacity: float) -> None:
        """
        Set background frame opacity (0.0 to 1.0).
        
        Args:
            opacity: Opacity value from 0.0 (transparent) to 1.0 (opaque)
        """
        self._bg_opacity = max(0.0, min(1.0, opacity))
        # Update background color with new opacity
        self._bg_color.setAlpha(int(255 * self._bg_opacity))
        if self._show_background:
            self._update_stylesheet()
    
    def set_background_border(self, width: int, color: QColor) -> None:
        """
        Set background frame border.
        
        Args:
            width: Border width in pixels
            color: Border color
        """
        self._bg_border_width = width
        self._bg_border_color = color
        if self._show_background:
            self._update_stylesheet()
    
    def _update_stylesheet(self) -> None:
        """Update widget stylesheet based on current settings."""
        if self._show_background:
            # With background frame
            self.setStyleSheet(f"""
                QLabel {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: rgba({self._bg_color.red()}, {self._bg_color.green()}, 
                                          {self._bg_color.blue()}, {self._bg_color.alpha()});
                    border: {self._bg_border_width}px solid rgba({self._bg_border_color.red()}, 
                                                                 {self._bg_border_color.green()}, 
                                                                 {self._bg_border_color.blue()}, 
                                                                 {self._bg_border_color.alpha()});
                    border-radius: 8px;
                    padding: 6px 12px 6px 16px;
                }}
            """)
        else:
            # Transparent background (default)
            self.setStyleSheet(f"""
                QLabel {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: transparent;
                    padding: 6px 12px 6px 16px;
                }}
            """)
    
    def cleanup(self) -> None:
        """Clean up resources."""
        logger.debug("Cleaning up weather widget")
        self.stop()

    def _fade_in(self) -> None:
        try:
            if self._fade_effect is None:
                self._fade_effect = QGraphicsOpacityEffect(self)
                self.setGraphicsEffect(self._fade_effect)
            if self._fade_anim is not None:
                try:
                    self._fade_anim.stop()
                except Exception:
                    pass
            self._fade_effect.setOpacity(0.0)
            self.show()
            anim = QPropertyAnimation(self._fade_effect, b"opacity", self)
            anim.setDuration(250)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            self._fade_anim = anim
            self._fade_anim.start()
        except Exception:
            self.show()
