"""
Weather widget for screensaver overlay.

Displays current weather information using Open-Meteo API (no API key needed).
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import os
import json
import random
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Qt, Signal, QObject
from PySide6.QtGui import QFont, QPainter, QPen, QColor, QFontMetrics
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.threading.manager import ThreadManager
from core.performance import widget_paint_sample
from weather.open_meteo_provider import OpenMeteoProvider
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.shadow_utils import apply_widget_shadow, ShadowFadeProfile
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle

logger = get_logger(__name__)
# Store the weather cache in the user's home directory so it is stable
# across script, PyInstaller, and Nuitka onefile runs. Writing next to the
# module (e.g. in a onefile temp extraction directory) can fail or be
# ephemeral; the home directory is always present and writable.
_CACHE_FILE = Path(os.path.expanduser("~")) / ".srpss_last_weather.json"


class WeatherPosition(Enum):
    """Weather widget position on screen."""
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
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


class WeatherWidget(BaseOverlayWidget):
    """
    Weather widget for displaying weather information.
    
    Extends BaseOverlayWidget for common styling/positioning functionality.
    
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
    
    # Override defaults for weather widget
    DEFAULT_FONT_SIZE = 24
    
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
        # Convert WeatherPosition to OverlayPosition for base class
        overlay_pos = OverlayPosition(position.value)
        super().__init__(parent, position=overlay_pos, overlay_name="weather")
        
        # Defer visibility until fade sync triggers
        self._defer_visibility_for_fade_sync = True
        
        self._location = location
        self._weather_position = position  # Keep original enum for compatibility
        self._position = OverlayPosition(position.value)
        self._update_timer: Optional[QTimer] = None
        self._retry_timer: Optional[QTimer] = None
        self._update_timer_handle: Optional[OverlayTimerHandle] = None
        self._icon_timer_handle: Optional[OverlayTimerHandle] = None
        
        # Caching
        self._cached_data: Optional[Dict[str, Any]] = None
        self._cache_time: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=30)
        self._has_displayed_valid_data = False
        self._pending_first_show = False
        self._load_persisted_cache()
        
        # Background thread
        # Override base class font size default
        self._font_size = 24
        
        # Padding: slightly more at top/bottom, extra slack on the right so the
        # drop shadow doesn't make TOP_RIGHT appear flush with the screen edge.
        self._padding_top = 8
        self._padding_bottom = 8
        self._padding_left = 21  # +5 to align with overlay cards
        self._padding_right = 28  # wider to match visual spacing on right-anchored layouts
        
        # Set visual padding for base class positioning (aligns visible content to margins)
        # This replaces the custom horizontal_margin adjustment in _update_position
        self.set_visual_padding(
            top=self._padding_top,
            right=self._padding_right,
            bottom=self._padding_bottom,
            left=self._padding_left,
        )
        
        # Optional forecast line
        self._show_forecast = False
        self._forecast_data: Optional[str] = None
        
        # Separator line position (set during _update_display)
        self._separator_y: Optional[int] = None
        
        # Setup UI
        self._setup_ui()
        
        logger.debug(f"WeatherWidget created (location={location}, position={position.value})")
    
    def _setup_ui(self) -> None:
        """Setup widget UI."""
        # Use base class styling setup
        self._apply_base_styling()
        
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception as e:
            logger.debug("[WEATHER] Exception suppressed: %s", e)
        
        # Weather uses normal weight font
        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)
    
    def paintEvent(self, event) -> None:
        """Override to draw separator line between weather and forecast."""
        with widget_paint_sample(self, "weather.paint"):
            # Let base class draw the text
            super().paintEvent(event)
            
            # Draw separator line if forecast is shown
            if self._separator_y is not None and self._show_forecast and self._forecast_data:
                painter = QPainter(self)
                try:
                    pen = QPen(QColor(255, 255, 255, 153))  # 60% opacity white
                    pen.setWidth(1)
                    painter.setPen(pen)
                    # Draw horizontal line from left padding to right edge minus padding
                    x1 = self._padding_left
                    x2 = self.width() - self._padding_right
                    painter.drawLine(x1, self._separator_y, x2, self._separator_y)
                finally:
                    painter.end()
    
    def _update_content(self) -> None:
        """Required by BaseOverlayWidget - update weather display."""
        if self._cached_data:
            self._update_display(self._cached_data)
    
    # -------------------------------------------------------------------------
    # Lifecycle Implementation Hooks
    # -------------------------------------------------------------------------
    
    def _initialize_impl(self) -> None:
        """Initialize weather resources (lifecycle hook)."""
        # Load any persisted cache
        self._load_persisted_cache()
        logger.debug("[LIFECYCLE] WeatherWidget initialized")
    
    def _activate_impl(self) -> None:
        """Activate weather widget - start updates (lifecycle hook)."""
        if not self._ensure_thread_manager("WeatherWidget._activate_impl"):
            raise RuntimeError("ThreadManager not available")
        
        if not self._location:
            raise ValueError("No location configured for weather widget")
        
        # Display cached data if available
        if self._is_cache_valid():
            self._update_display(self._cached_data)
            self._has_displayed_valid_data = True
        
        # Start periodic updates with desync jitter to prevent alignment with other widgets
        self._fetch_weather()
        base_interval_ms = 30 * 60 * 1000  # 30 minutes
        # Add ±2 minute jitter to desync from other widgets and transitions
        jitter_ms = random.randint(-2 * 60 * 1000, 2 * 60 * 1000)
        interval_ms = base_interval_ms + jitter_ms
        if is_perf_metrics_enabled():
            logger.debug("[PERF] WeatherWidget: refresh interval %.1f min (jitter: %+.1f min)",
                        interval_ms / 60000, jitter_ms / 60000)
        handle = create_overlay_timer(self, interval_ms, self._fetch_weather, description="WeatherWidget refresh")
        self._update_timer_handle = handle
        self._update_timer = getattr(handle, "_timer", None)
        
        # Fade in
        parent = self.parent()
        if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
            try:
                parent.request_overlay_fade_sync("weather", lambda: self._fade_in())
            except Exception as e:
                logger.debug("[WEATHER] Exception suppressed: %s", e)
                self._fade_in()
        else:
            self._fade_in()
        
        logger.debug("[LIFECYCLE] WeatherWidget activated")
    
    def _deactivate_impl(self) -> None:
        """Deactivate weather widget - stop updates (lifecycle hook)."""
        # Stop timers
        if self._update_timer_handle is not None:
            try:
                self._update_timer_handle.stop()
            except Exception as e:
                logger.debug("[WEATHER] Exception suppressed: %s", e)
            self._update_timer_handle = None
        
        if self._update_timer is not None:
            try:
                self._update_timer.stop()
                self._update_timer.deleteLater()
            except RuntimeError:
                pass
            self._update_timer = None
        
        if self._retry_timer:
            try:
                self._retry_timer.stop()
                self._retry_timer.deleteLater()
            except RuntimeError:
                pass
            self._retry_timer = None
        
        if self._icon_timer_handle is not None:
            try:
                self._icon_timer_handle.stop()
            except Exception as e:
                logger.debug("[WEATHER] Exception suppressed: %s", e)
            self._icon_timer_handle = None
        
        logger.debug("[LIFECYCLE] WeatherWidget deactivated")
    
    def _cleanup_impl(self) -> None:
        """Clean up weather resources (lifecycle hook)."""
        self._deactivate_impl()
        self._cached_data = None
        self._cache_time = None
        logger.debug("[LIFECYCLE] WeatherWidget cleaned up")
    
    # -------------------------------------------------------------------------
    # Legacy Start/Stop Methods (for backward compatibility)
    # -------------------------------------------------------------------------
    
    def start(self) -> None:
        """Start weather updates."""
        if self._enabled:
            logger.warning("[FALLBACK] Weather widget already running")
            return
        if not self._ensure_thread_manager("WeatherWidget.start"):
            return
        
        if not self._location:
            error_msg = "No location configured for weather widget"
            logger.error(error_msg)
            self.setText("Weather: No Location")
            try:
                self.adjustSize()
                if self.parent():
                    self._update_position()
            except Exception as e:
                logger.debug("[WEATHER] Exception suppressed: %s", e)
            self.show()
            self.error_occurred.emit(error_msg)
            return

        if self._is_cache_valid():
            self._update_display(self._cached_data)
            self._has_displayed_valid_data = True
            self._enabled = True

            def _starter() -> None:
                # Guard against widget being deleted before deferred callback runs
                if not Shiboken.isValid(self):
                    return
                self._fade_in()

            parent = self.parent()
            if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
                try:
                    parent.request_overlay_fade_sync("weather", _starter)
                except Exception as e:
                    logger.debug("[WEATHER] Exception suppressed: %s", e)
                    _starter()
            else:
                _starter()

            self._fetch_weather()
            interval_ms = 30 * 60 * 1000
            handle = create_overlay_timer(self, interval_ms, self._fetch_weather, description="WeatherWidget refresh")
            self._update_timer_handle = handle
            try:
                self._update_timer = getattr(handle, "_timer", None)
            except Exception as e:
                logger.debug("[WEATHER] Exception suppressed: %s", e)
                self._update_timer = None

            logger.info("Weather widget started (using cached data)")
            return

        self.hide()
        self._pending_first_show = True

        self._fetch_weather()
        interval_ms = 30 * 60 * 1000
        handle = create_overlay_timer(self, interval_ms, self._fetch_weather, description="WeatherWidget refresh")
        self._update_timer_handle = handle
        try:
            self._update_timer = getattr(handle, "_timer", None)
        except Exception as e:
            logger.debug("[WEATHER] Exception suppressed: %s", e)
            self._update_timer = None

        self._enabled = True

        logger.info("Weather widget started")
    
    def stop(self) -> None:
        """Stop weather updates."""
        if not self._enabled:
            return
        
        if self._update_timer_handle is not None:
            try:
                self._update_timer_handle.stop()
            except Exception as e:
                logger.debug("[WEATHER] Exception suppressed: %s", e)
            self._update_timer_handle = None

        if self._update_timer is not None:
            try:
                self._update_timer.stop()
                self._update_timer.deleteLater()
            except RuntimeError:
                pass
            self._update_timer = None
        if self._retry_timer:
            try:
                self._retry_timer.stop()
                self._retry_timer.deleteLater()
            except RuntimeError:
                pass
            self._retry_timer = None

        if self._icon_timer_handle is not None:
            try:
                self._icon_timer_handle.stop()
            except Exception as e:
                logger.debug("[WEATHER] Exception suppressed: %s", e)
            self._icon_timer_handle = None
        
        self._enabled = False
        self._pending_first_show = False
        self.hide()
        
        logger.debug("Weather widget stopped")
    
    def is_running(self) -> bool:
        """Check if weather widget is running."""
        return self._enabled
    
    def _fetch_weather(self) -> None:
        """Fetch weather data (always attempts a refresh in the background)."""

        # Always try to refresh from the provider; any existing cached data
        # remains available for display if the fetch fails.
        if is_perf_metrics_enabled():
            logger.debug("[PERF] Weather fetch initiated for %s", self._location)
        else:
            logger.debug("Fetching fresh weather data")

        if self._thread_manager is not None:
            self._fetch_via_thread_manager()
        else:
            logger.error("[THREAD_MANAGER] Weather fetch aborted: no ThreadManager available")

    def _fetch_via_thread_manager(self) -> None:
        tm = self._thread_manager
        def _do_fetch(location: str) -> Dict[str, Any]:
            import time
            start_time = time.perf_counter()
            if is_perf_metrics_enabled():
                logger.debug("[PERF] Weather API call starting for %s", location)
            else:
                logger.debug("[ThreadManager] Fetching weather for %s", location)
            provider = OpenMeteoProvider(timeout=10)
            result = provider.get_current_weather(location)
            if is_perf_metrics_enabled():
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.debug("[PERF] Weather API call completed in %.2fms for %s", elapsed_ms, location)
            return result

        def _on_result(result) -> None:
            try:
                if getattr(result, "success", False) and isinstance(getattr(result, "result", None), dict):
                    data = result.result
                    ThreadManager.run_on_ui_thread(self._on_weather_fetched, data)
                else:
                    err = getattr(result, "error", None)
                    if err is None:
                        err = "No weather data returned"
                    ThreadManager.run_on_ui_thread(self._on_fetch_error, str(err))
            except Exception as e:
                ThreadManager.run_on_ui_thread(self._on_fetch_error, f"Weather fetch failed: {e}")

        try:
            tm.submit_io_task(_do_fetch, self._location, callback=_on_result)
        except Exception as e:
            logger.exception("ThreadManager IO task submission failed for weather fetch: %s", e)
    
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
        self._persist_cache(data)
        
        if self._pending_first_show and not self._has_displayed_valid_data:
            self._pending_first_show = False
            self._has_displayed_valid_data = True

            def _starter() -> None:
                # Guard against widget being deleted before deferred callback runs
                if not Shiboken.isValid(self):
                    return
                self._fade_in()

            parent = self.parent()
            if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
                try:
                    parent.request_overlay_fade_sync("weather", _starter)
                except Exception as e:
                    logger.debug("[WEATHER] Exception suppressed: %s", e)
                    _starter()
            else:
                _starter()
        else:
            # For subsequent updates, keep using the current visibility state;
            # the initial fade-in (if any) owns showing the widget.
            pass

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
        
        if not self._cached_data and self._enabled:
            self._schedule_retry()

        self.error_occurred.emit(error)
    
    def _is_cache_valid(self) -> bool:
        """Return True if any cached data exists.

        Age is intentionally ignored for display purposes so that the last
        successfully fetched sample can be shown instantly on startup,
        even if it is older than the 30 minute refresh cadence. Periodic
        refresh attempts are still driven by the update timer.
        """

        return bool(self._cached_data)

    def _load_persisted_cache(self) -> None:
        try:
            if not _CACHE_FILE.exists():
                return
            raw = _CACHE_FILE.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except Exception:
            logger.debug("Failed to load persisted weather cache", exc_info=True)
            return

        loc = payload.get("location")
        ts = payload.get("timestamp")
        if not loc or not ts:
            return
        try:
            dt = datetime.fromisoformat(ts)
        except Exception as e:
            logger.debug("[WEATHER] Exception suppressed: %s", e)
            return
        if loc.lower() != self._location.lower():
            return

        temp = payload.get("temperature")
        condition = payload.get("condition")
        if temp is None or condition is None:
            return

        self._cached_data = {
            "temperature": temp,
            "condition": condition,
            "location": loc,
        }
        self._cache_time = dt

    def _schedule_retry(self, delay_ms: int = 5 * 60 * 1000) -> None:
        if self._retry_timer is not None:
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._on_retry_timeout)
        timer.start(delay_ms)
        self._retry_timer = timer

    def _on_retry_timeout(self) -> None:
        self._retry_timer = None
        if self._enabled:
            self._fetch_weather()
    
    def _persist_cache(self, data: Dict[str, Any]) -> None:
        try:
            temp = data.get("temperature")
            condition = data.get("condition")
            location = data.get("location") or self._location

            if temp is None:
                main = data.get("main")
                if isinstance(main, dict):
                    temp = main.get("temp")
            if condition is None:
                weather_list = data.get("weather")
                if isinstance(weather_list, list) and weather_list:
                    entry = weather_list[0]
                    condition = entry.get("main") or entry.get("description")

            if temp is None or condition is None:
                return

            payload = {
                "location": location,
                "temperature": float(temp),
                "condition": str(condition),
                "timestamp": datetime.now().isoformat(),
            }
            _CACHE_FILE.write_text(json.dumps(payload), encoding="utf-8")
        except Exception:
            logger.debug("Failed to persist weather cache", exc_info=True)
    
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

            # Extract forecast data if present in the response
            forecast = data.get('forecast')
            if forecast:
                self._forecast_data = forecast

            # Title Case presentation for readability
            location_display = str(location).title()
            condition_display = str(condition).title()
            
            # Relative sizing (forecast is 12pt smaller than base font)
            city_pt = max(6, self._font_size + 2)
            details_pt = max(6, self._font_size - 2)
            forecast_pt = max(6, self._font_size - 12)
            city_html = f"<div style='font-size:{city_pt}pt; font-weight:700;'>{location_display}</div>"

            # Temperature is bold (700), condition is semi-bold (600)
            temp_html = f"<span style='font-weight:700;'>{temp:.0f}°C</span>"
            details_text = f"{temp_html} - <span style='font-weight:600;'>{condition_display}</span>"
            details_html = f"<div style='font-size:{details_pt}pt;'>{details_text}</div>"

            # Optional forecast line (italic, smaller)
            forecast_html = ""
            self._separator_y = None  # Reset separator position
            if self._show_forecast and self._forecast_data:
                # Calculate separator Y position based on city + details height
                city_fm = QFontMetrics(QFont(self._font_family, city_pt, QFont.Weight.Bold))
                details_fm = QFontMetrics(QFont(self._font_family, details_pt, QFont.Weight.Normal))
                # Separator with minimal padding - middle ground
                self._separator_y = self._padding_top + city_fm.height() + details_fm.height() + 6
                # Top margin on forecast to maintain spacing
                forecast_html = f"<div style='margin-top: 6px; font-size:{forecast_pt}pt; font-style:italic; font-weight:400;'>{self._forecast_data}</div>"

            html = (
                f"<div style='line-height:1.0'>"
                f"{city_html}{details_html}{forecast_html}</div>"
            )
            self.setTextFormat(Qt.TextFormat.RichText)
            self.setText(html)
            self.adjustSize()
            
            # Update position
            if self.parent():
                self._update_position()
            
        except Exception as e:
            logger.exception(f"Error updating weather display: {e}")
            self.setText("Weather: Error")

    def _update_position(self) -> None:
        """Update widget position using base class visual padding helpers.
        
        The base class _update_position() now handles visual padding offsets,
        so we just need to sync our position enum and delegate to the base class.
        """
        # Sync WeatherPosition to OverlayPosition for base class
        from widgets.base_overlay_widget import OverlayPosition
        
        position_map = {
            WeatherPosition.TOP_LEFT: OverlayPosition.TOP_LEFT,
            WeatherPosition.TOP_CENTER: OverlayPosition.TOP_CENTER,
            WeatherPosition.TOP_RIGHT: OverlayPosition.TOP_RIGHT,
            WeatherPosition.MIDDLE_LEFT: OverlayPosition.MIDDLE_LEFT,
            WeatherPosition.CENTER: OverlayPosition.CENTER,
            WeatherPosition.MIDDLE_RIGHT: OverlayPosition.MIDDLE_RIGHT,
            WeatherPosition.BOTTOM_LEFT: OverlayPosition.BOTTOM_LEFT,
            WeatherPosition.BOTTOM_CENTER: OverlayPosition.BOTTOM_CENTER,
            WeatherPosition.BOTTOM_RIGHT: OverlayPosition.BOTTOM_RIGHT,
        }
        
        # Update base class position and let it handle visual padding
        self._position = position_map.get(self._weather_position, OverlayPosition.TOP_LEFT)
        
        # Delegate to base class which handles visual padding, pixel shift, and stack offset
        super()._update_position()

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
        self._weather_position = position
        # Also update base class position for consistency
        self._position = OverlayPosition(position.value)
        
        # Update position immediately if running
        if self._enabled:
            self._update_position()
    
    def set_thread_manager(self, thread_manager) -> None:
        self._thread_manager = thread_manager

    def set_show_forecast(self, show: bool) -> None:
        """Enable or disable the optional forecast line.
        
        Args:
            show: True to show forecast line when data is available
        """
        self._show_forecast = show
        if self._cached_data:
            self._update_display(self._cached_data)

    def set_forecast_data(self, forecast: Optional[str]) -> None:
        """Set the forecast text to display.
        
        Args:
            forecast: Forecast text (e.g. "Tomorrow: 18°C, Partly Cloudy")
        """
        self._forecast_data = forecast
        if self._show_forecast and self._cached_data:
            self._update_display(self._cached_data)
    
    def _update_stylesheet(self) -> None:
        """Update widget stylesheet based on current settings."""
        # Padding: top right bottom left
        padding = f"{self._padding_top}px {self._padding_right}px {self._padding_bottom}px {self._padding_left}px"
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
                    padding: {padding};
                }}
            """)
        else:
            # Transparent background (default)
            self.setStyleSheet(f"""
                QLabel {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: transparent;
                    padding: {padding};
                }}
            """)
    
    def cleanup(self) -> None:
        """Clean up resources."""
        logger.debug("Cleaning up weather widget")
        self.stop()

    def _fade_in(self) -> None:
        """Fade the widget in via ShadowFadeProfile, then attach the shared drop shadow.

        The ShadowFadeProfile helper drives the opacity/shadow staging for the
        card. On failure we fall back to an immediate show and, if configured,
        a direct call to apply_widget_shadow.
        """

        try:
            ShadowFadeProfile.start_fade_in(
                self,
                self._shadow_config,
                has_background_frame=self._show_background,
            )
        except Exception:
            # Fallback: just show and, if available, apply the shared shadow.
            logger.debug("[WEATHER] _fade_in fallback path triggered", exc_info=True)
            try:
                self.show()
            except Exception as e:
                logger.debug("[WEATHER] Exception suppressed: %s", e)
            if self._shadow_config is not None:
                try:
                    apply_widget_shadow(
                        self,
                        self._shadow_config,
                        has_background_frame=self._show_background,
                    )
                except Exception:
                    logger.debug(
                        "[WEATHER] Failed to apply widget shadow in fallback path",
                        exc_info=True,
                    )
