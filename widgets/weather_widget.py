"""
Weather widget for screensaver overlay.

Displays current weather information using Open-Meteo API (no API key needed).
"""
from typing import Optional, Dict, Any, Tuple, List
from pathlib import Path
from PySide6.QtWidgets import QWidget, QSizePolicy, QHBoxLayout, QVBoxLayout, QLabel
from PySide6.QtCore import QPoint, QRect, Qt, Signal, QSize
from PySide6.QtGui import QFont, QPainter, QPen, QColor, QFontMetrics, QPixmap
from shiboken6 import Shiboken

from core.logging.logger import get_logger
from core.performance import widget_paint_sample
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.shadow_utils import PaintedShadowLabel, ShadowFadeProfile
from widgets.weather_runtime import WeatherRuntimeService
from widgets.weather_components import (  # noqa: F401 (re-exports for tests/external)
    WeatherConditionIcon,
    WeatherDetailRow,
    WeatherPosition,
    WeatherFetcher,
)

logger = get_logger(__name__)

# Weather icon directory (PNG files)
_WEATHER_ICON_DIR = Path(__file__).resolve().parents[1] / "images" / "weather"

# Detail metric icon files
_DETAIL_ICON_FILES = {
    "rain": "umbrella.png",
    "humidity": "humidity.png",
    "wind": "wind.png",
}
_DETAIL_ICON_MIN_PX = 30
_DETAIL_METRICS_TTL_SECONDS = 30 * 60

# Weather code groupings from Open-Meteo to our PNG assets
_WEATHER_CODE_ICON_MAP: List[Tuple[set[int], str]] = [
    (set([0]), "clear-day.png"),
    (set([1, 2]), "partly-cloudy-day.png"),
    (set([3]), "overcast-day.png"),
    (set([45, 48]), "fog-day.png"),
    (set([51, 53, 55, 56, 57]), "drizzle.png"),
    (set([61, 63, 65, 80, 81, 82]), "rain.png"),
    (set([66, 67]), "hail.png"),
    (set([71, 73, 75, 77, 85, 86]), "snow.png"),
    (set([95, 96, 99]), "thunderstorms-day.png"),
]

# Condition keyword fallback mapping
_CONDITION_KEYWORDS_ICON_MAP: List[Tuple[str, str]] = [
    ("clear", "clear-day.png"),
    ("partly", "partly-cloudy-day.png"),
    ("overcast", "overcast-day.png"),
    ("cloud", "partly-cloudy-day.png"),
    ("fog", "fog-day.png"),
    ("haze", "haze-day.png"),
    ("smoke", "smoke.png"),
    ("drizzle", "drizzle.png"),
    ("rain", "rain.png"),
    ("snow", "snow.png"),
    ("sleet", "partly-cloudy-day-sleet.png"),
    ("thunder", "thunderstorms-day-rain.png"),
]

_ICON_ALIGNMENT_OPTIONS = {"LEFT", "RIGHT", "NONE"}
_DEFAULT_ICON_ALIGNMENT = "RIGHT"
_DEFAULT_ICON_SIZE = 120
_DEFAULT_DETAIL_ICON_SIZE = 16
WEATHER_SETTINGS_TARGET = "weather_location"


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
    settings_requested = Signal(str)
    
    # Override defaults for weather widget
    DEFAULT_FONT_SIZE = 24
    
    def __init__(self, parent: Optional[QWidget] = None,
                 location: str = "London",
                 position: WeatherPosition = WeatherPosition.BOTTOM_LEFT,
                 *,
                 build_default_runtime: bool = True):
        """
        Initialize weather widget.

        Args:
            parent: Parent widget
            location: City name
            position: Screen position
            build_default_runtime: When True (standalone), construct a convenience
                WeatherRuntimeService. Production creation passes False so the
                presentation-neutral runtime-data owner is attached by
                WidgetRuntimeManager instead (no QWidget-owned provider/timer).
        """
        # Convert WeatherPosition to OverlayPosition for base class
        overlay_pos = OverlayPosition(position.value)
        super().__init__(parent, position=overlay_pos, overlay_name="weather")

        # Defer visibility until fade sync triggers
        self._defer_visibility_for_fade_sync = True

        self._location = str(location or "").strip()
        self._weather_position = position  # Keep original enum for compatibility
        self._position = OverlayPosition(position.value)
        # Runtime-data ownership (provider/fetch/cache/refresh/retry/generation)
        # lives in a presentation-neutral WeatherRuntimeService (Phase E1 slice 3).
        # This widget is a presentation consumer of prepared state + events. The
        # service is attached here for standalone use, or by WidgetRuntimeManager
        # in production (build_default_runtime=False).
        self._runtime_service: Optional[WeatherRuntimeService] = None
        self._owns_runtime_service = False

        # Presentation-only display state.
        self._has_displayed_valid_data = False
        self._pending_first_show = False

        # Background thread
        # Override base class font size default
        self._font_size = 24
        
        # Layout sizing - minimum width like old code
        self._min_content_width = BaseOverlayWidget.DEFAULT_CARD_MIN_WIDTH
        
        # Padding: reasonable defaults
        self._padding_top = 6
        self._padding_bottom = 6
        self._padding_left = 20
        self._padding_right = 20
        
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

        # Icon and detail row configuration
        self._show_condition_icon = True
        self._icon_alignment = _DEFAULT_ICON_ALIGNMENT
        self._icon_size = _DEFAULT_ICON_SIZE
        self._icon_monochrome = False  # Feature #6: Monochrome icon mode
        self._show_details_row = True
        self._detail_icon_size = _DEFAULT_DETAIL_ICON_SIZE
        self._last_is_day = True
        self._last_weather_code: Optional[int] = None
        self._missing_location_active = False

        # UI Components (created in _setup_ui)
        self._root_layout: Optional[QVBoxLayout] = None
        self._primary_row: Optional[QWidget] = None
        self._text_column: Optional[QWidget] = None
        self._condition_icon_widget: Optional[WeatherConditionIcon] = None
        self._city_label: Optional[QLabel] = None
        self._conditions_label: Optional[QLabel] = None
        self._details_separator: Optional[QWidget] = None
        self._detail_row_container: Optional[QWidget] = None
        self._detail_row_widget: Optional[WeatherDetailRow] = None
        self._detail_icon_cache: Dict[Tuple[str, int], QPixmap] = {}

        # Setup UI
        self._setup_ui()

        if build_default_runtime:
            # Standalone convenience owner. Production defers to WidgetRuntimeManager.
            self.set_runtime_service(
                WeatherRuntimeService(
                    runtime_generation=getattr(self, "_runtime_generation", None)
                ),
                owns_service=True,
            )

        logger.debug(f"WeatherWidget created (location={location}, position={position.value})")

    # -------------------------------------------------------------------------
    # Runtime-data ownership: attach + presentation consumer read boundary
    # -------------------------------------------------------------------------
    def set_runtime_service(
        self,
        service: Optional[WeatherRuntimeService],
        *,
        owns_service: bool = False,
    ) -> None:
        """Attach the presentation-neutral Weather runtime-data owner.

        Called for standalone construction and by WidgetRuntimeManager in
        production. Syncs current location/thread-manager so the owner can operate
        without the widget owning provider/timer lifetime.
        """
        previous = self._runtime_service
        previous_owned = self._owns_runtime_service
        if previous is service:
            owns_service = previous_owned or owns_service
        if previous is not None and previous is not service:
            if previous_owned:
                previous.retire()
            else:
                previous.detach_consumer(self)

        self._runtime_service = service
        self._owns_runtime_service = bool(service is not None and owns_service)
        if service is None:
            return
        try:
            service.attach_consumer(self)
            service.set_location(self._location)
            tm = getattr(self, "_thread_manager", None)
            if tm is not None:
                service.set_thread_manager(tm)
        except Exception:
            self._runtime_service = None
            self._owns_runtime_service = False
            if owns_service:
                service.retire()
            raise

    def _release_runtime_service(self) -> None:
        service = self._runtime_service
        owns_service = self._owns_runtime_service
        self._runtime_service = None
        self._owns_runtime_service = False
        if service is None:
            return
        if owns_service:
            service.retire()
        else:
            service.detach_consumer(self)

    def _current_weather_data(self) -> Optional[Dict[str, Any]]:
        """Read accepted data through the consumer API for presentation redraws."""

        service = self._runtime_service
        return service.get_cached_data() if service is not None else None

    def _refresh_current_weather_presentation(self) -> None:
        data = self._current_weather_data()
        if data:
            self._update_display(data)

    # -------------------------------------------------------------------------
    # Consumer protocol (WeatherRuntimeService -> presentation)
    # -------------------------------------------------------------------------
    def is_weather_consumer_alive(self) -> bool:
        return bool(Shiboken.isValid(self))

    def weather_pending_first_show(self) -> bool:
        return self._pending_first_show

    def on_weather_state(self, data: Dict[str, Any], *, from_cache: bool) -> None:
        """Apply prepared Weather state to the pixels + coordinate first-show fade."""
        if not Shiboken.isValid(self):
            return
        self._update_display(data)
        if self._pending_first_show and not self._has_displayed_valid_data:
            self._pending_first_show = False
            self._request_fade_in()
        self._has_displayed_valid_data = True
        if not from_cache:
            self.weather_updated.emit(data)

    def apply_weather_data(self, data: Dict[str, Any]) -> None:
        """Re-apply already-prepared Weather state (e.g. cached on fetch error)."""
        if not Shiboken.isValid(self):
            return
        self._update_display(data)

    def on_weather_error(self, error: str) -> None:
        if not Shiboken.isValid(self):
            return
        self.error_occurred.emit(error)
    
    def _setup_ui(self) -> None:
        """Setup widget UI with icon and detail row support."""
        # Use base class styling setup
        self._apply_base_styling()

        # Main container layout
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(
            self._padding_left,
            self._padding_top,
            self._padding_right,
            self._padding_bottom,
        )
        self._root_layout.setSpacing(4)

        # Primary row: icon + text - minimum width to fit content
        self._primary_row = QWidget(self)
        self._primary_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._primary_row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        primary_layout = QHBoxLayout(self._primary_row)
        primary_layout.setContentsMargins(0, 0, 0, 0)
        primary_layout.setSpacing(16)

        # Text column - expanding width
        self._text_column = QWidget(self._primary_row)
        self._text_column.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._text_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        text_layout = QVBoxLayout(self._text_column)
        text_layout.setContentsMargins(6, 2, 6, 2)
        text_layout.setSpacing(2)

        self._city_label = PaintedShadowLabel(self._text_column)
        self._city_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._city_label.setWordWrap(False)
        self._city_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._city_label.setTextFormat(Qt.TextFormat.PlainText)
        self._city_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._city_label.setMinimumWidth(0)

        self._conditions_label = PaintedShadowLabel(self._text_column)
        self._conditions_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._conditions_label.setWordWrap(False)
        self._conditions_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._conditions_label.setTextFormat(Qt.TextFormat.PlainText)
        self._conditions_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._conditions_label.setMinimumWidth(0)

        text_layout.addWidget(self._city_label)
        text_layout.addWidget(self._conditions_label)
        self._apply_text_alignment()

        # Build primary layout based on icon alignment
        if self._icon_alignment == "LEFT":
            # Icon on left, text on right
            self._condition_icon_widget = WeatherConditionIcon(
                size_px=self._icon_size,
                parent=self._primary_row
            )
            self._condition_icon_widget.set_shadow_config(self._shadow_config)
            self._condition_icon_widget.setVisible(False)
            primary_layout.addWidget(
                self._condition_icon_widget, 0,
                Qt.AlignmentFlag.AlignVCenter
            )
            primary_layout.addWidget(self._text_column, 1)
        else:
            # Text on left, icon on right (default)
            primary_layout.addWidget(self._text_column, 1)
            self._condition_icon_widget = WeatherConditionIcon(
                size_px=self._icon_size,
                parent=self._primary_row
            )
            self._condition_icon_widget.set_shadow_config(self._shadow_config)
            self._condition_icon_widget.setVisible(False)
            primary_layout.addWidget(
                self._condition_icon_widget, 0,
                Qt.AlignmentFlag.AlignVCenter
            )

        self._root_layout.addWidget(self._primary_row)
        self.setMinimumWidth(self._min_content_width)

        # Details separator line
        self._details_separator = self._create_separator()
        self._root_layout.addWidget(self._details_separator)

        # Detail row container - expanding width with minimum like old code
        self._detail_row_container = QWidget(self)
        self._detail_row_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._detail_row_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._detail_row_container.setMinimumWidth(0)
        detail_container_layout = QHBoxLayout(self._detail_row_container)
        detail_container_layout.setContentsMargins(0, 4, 0, 4)
        detail_container_layout.setSpacing(0)

        self._detail_row_widget = WeatherDetailRow(self._detail_row_container)
        self._detail_row_widget.setVisible(False)
        detail_container_layout.addWidget(self._detail_row_widget, 1)

        self._detail_row_container.setVisible(False)
        self._root_layout.addWidget(self._detail_row_container)

        # Forecast separator
        self._forecast_separator = self._create_separator()
        self._root_layout.addWidget(self._forecast_separator)

        # Forecast container (reused existing structure)
        self._forecast_label = PaintedShadowLabel(self)
        self._forecast_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._forecast_label.setWordWrap(True)
        self._forecast_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        self._forecast_label.setTextFormat(Qt.TextFormat.PlainText)
        self._forecast_label.setVisible(False)
        self._forecast_label.setContentsMargins(0, 0, 0, 11)
        self._root_layout.addWidget(self._forecast_label)

        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception as e:
            logger.debug("[WEATHER] Exception suppressed: %s", e)
    
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
                    contents = self._root_layout.contentsMargins() if self._root_layout is not None else None
                    left_pad = contents.left() if contents is not None else self._padding_left
                    right_pad = contents.right() if contents is not None else self._padding_right
                    x1 = left_pad
                    x2 = self.width() - right_pad
                    painter.drawLine(x1, self._separator_y, x2, self._separator_y)
                finally:
                    painter.end()
    
    def sizeHint(self) -> QSize:
        """Return the layout's size hint for proper sizing."""
        if self._root_layout is not None:
            return self._root_layout.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        """Return the layout's minimum size hint."""
        if self._root_layout is not None:
            return self._root_layout.minimumSize()
        return super().minimumSizeHint()

    def _refresh_outer_geometry_for_runtime_content(self) -> None:
        """Refresh layout-driven internals without letting runtime content own CUSTOM geometry."""
        if self._active_custom_layout_rect() is not None:
            try:
                self.updateGeometry()
            except Exception as e:
                logger.debug("[WEATHER] Exception suppressed: %s", e)
            self._schedule_custom_layout_geometry_reapply()
            try:
                self.update()
            except Exception as e:
                logger.debug("[WEATHER] Exception suppressed: %s", e)
            return

        self.adjustSize()
        if self.parent():
            self._update_position()

    def _create_separator(self) -> QWidget:
        """Create a horizontal separator line widget."""
        from PySide6.QtWidgets import QFrame
        container = QWidget(self)
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(0)

        line = QFrame(container)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setStyleSheet(
            "QFrame { background-color: rgba(255, 255, 255, 140); border: none; min-height:1px; }"
        )
        line.setFixedHeight(1)
        layout.addWidget(line)

        container.setVisible(False)
        return container

    def _resolve_condition_icon_path(
        self, weather_code: Optional[int], condition_text: Optional[str], is_day: bool
    ) -> Optional[Path]:
        """Resolve the appropriate icon path for weather conditions."""
        icon_name: Optional[str] = None

        # Try weather code mapping first
        if weather_code is not None:
            for codes, candidate in _WEATHER_CODE_ICON_MAP:
                if weather_code in codes:
                    icon_name = candidate
                    break

        # Fallback to condition text keyword matching
        if icon_name is None and condition_text:
            lowered = condition_text.lower()
            for keyword, candidate in _CONDITION_KEYWORDS_ICON_MAP:
                if keyword in lowered:
                    icon_name = candidate
                    break

        if icon_name is None:
            return None

        # Apply day/night variant
        resolved_name = self._resolve_day_night_icon(icon_name, is_day)
        candidate_path = _WEATHER_ICON_DIR / resolved_name
        if candidate_path.exists():
            return candidate_path

        # Fallback to base name
        fallback_path = _WEATHER_ICON_DIR / icon_name
        if fallback_path.exists():
            return fallback_path

        return None

    @staticmethod
    def _resolve_day_night_icon(icon_name: str, is_day: bool) -> str:
        """Convert day icon name to night variant if needed."""
        if is_day:
            logger.debug(f"[WEATHER] Icon resolution: {icon_name} (is_day=True, keeping day icon)")
            return icon_name
        if "-day" in icon_name:
            result = icon_name.replace("-day", "-night")
            logger.debug(f"[WEATHER] Icon resolution: {icon_name} -> {result} (is_day=False)")
            return result
        if icon_name.endswith(".png"):
            base = icon_name[:-4]
            result = f"{base}-night.png"
            logger.debug(f"[WEATHER] Icon resolution: {icon_name} -> {result} (is_day=False, no -day suffix)")
            return result
        logger.debug(f"[WEATHER] Icon resolution: {icon_name} unchanged (is_day=False, no .png)")
        return icon_name

    def _get_detail_icon_pixmap(self, key: str, size: int) -> Optional[QPixmap]:
        """Get cached pixmap for detail metric icon with DPR handling."""
        cache_key = (key, size)
        if cache_key in self._detail_icon_cache:
            return self._detail_icon_cache[cache_key]

        if key not in _DETAIL_ICON_FILES:
            return None

        icon_file = _WEATHER_ICON_DIR / _DETAIL_ICON_FILES[key]
        if not icon_file.exists():
            return None

        pixmap = QPixmap(str(icon_file))
        if pixmap.isNull():
            return None

        # Issue #2 Fix: Single scale operation using SmoothTransformation
        # This is the ONLY scale - paintEvent draws at 1:1
        scaled = pixmap.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # Apply monochrome tint
        tinted = self._apply_monochrome_tint(scaled)
        self._detail_icon_cache[cache_key] = tinted
        return tinted

    def _apply_monochrome_tint(self, pixmap: QPixmap) -> QPixmap:
        """Apply monochrome tint to icon pixmap."""
        # Get tint color from text color (slightly dimmed)
        tint = QColor(
            self._text_color.red(),
            self._text_color.green(),
            self._text_color.blue(),
            int(self._text_color.alpha() * 0.85)
        )

        # Create tinted pixmap
        tinted = QPixmap(pixmap.size())
        tinted.fill(Qt.GlobalColor.transparent)

        painter = QPainter(tinted)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), tint)
        painter.end()

        return tinted

    def _extract_detail_values(
        self, data: Dict[str, Any]
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Extract precipitation, humidity, and wind speed from data."""
        def _to_float(value) -> Optional[float]:
            try:
                if value is None:
                    return None
                return float(value)
            except (ValueError, TypeError):
                return None

        # Try direct fields first
        precipitation = _to_float(data.get("precipitation_probability"))
        humidity = _to_float(data.get("humidity"))
        windspeed = _to_float(data.get("windspeed"))

        # Fallback to nested structures
        if humidity is None:
            main = data.get("main")
            if isinstance(main, dict):
                humidity = _to_float(main.get("humidity"))

        if windspeed is None:
            wind = data.get("wind")
            if isinstance(wind, dict):
                windspeed = _to_float(wind.get("speed"))

        return precipitation, humidity, windspeed

    def _build_detail_metrics(self, data: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Build list of detail metrics to display - always show all 3 with fallback."""
        metrics: List[Tuple[str, str]] = []

        precipitation, humidity, windspeed = self._extract_detail_values(data)
        
        # Debug logging
        logger.debug(f"[WEATHER] Detail values: precip={precipitation}, humidity={humidity}, wind={windspeed}")
        logger.debug(f"[WEATHER] Raw data keys: {list(data.keys())}")

        # Always show all 3 metrics with fallback to 0 like old code
        rain_val = precipitation if precipitation is not None else 0.0
        humidity_val = humidity if humidity is not None else 0.0
        wind_val = windspeed if windspeed is not None else 0.0
        
        metrics.append(("rain", f"{rain_val:.0f}%"))
        metrics.append(("humidity", f"{humidity_val:.0f}%"))
        metrics.append(("wind", f"{wind_val:.1f} km/h"))
        
        logger.debug(f"[WEATHER] Built metrics: {metrics}")

        return metrics

    def _update_content(self) -> None:
        """Required by BaseOverlayWidget - update weather display."""
        if not self._location.strip():
            self._show_missing_location_state()
        else:
            self._refresh_current_weather_presentation()

    def _request_fade_in(self) -> None:
        """Join the normal coordinated fade without duplicating lifecycle branches."""

        def _starter() -> None:
            if Shiboken.isValid(self):
                self._fade_in()

        parent = self.parent()
        if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
            try:
                parent.request_overlay_fade_sync("weather", _starter)
                return
            except Exception as exc:
                logger.debug("[WEATHER] Coordinated fade request failed: %s", exc)
        _starter()

    def _show_missing_location_state(self) -> None:
        """Render a stable, provider-inert settings affordance for blank location."""
        if not Shiboken.isValid(self):
            return
        self._missing_location_active = True
        self.setText("")
        self._city_label.setText("Weather location required")
        self._city_label.setFont(
            QFont(self._font_family, max(12, int(self._font_size * 0.82)), QFont.Weight.Bold)
        )
        self._conditions_label.setText("Open Weather Settings")
        action_font = QFont(
            self._font_family,
            max(11, int(self._font_size * 0.65)),
            QFont.Weight.DemiBold,
        )
        action_font.setUnderline(True)
        self._conditions_label.setFont(action_font)
        self._city_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._conditions_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color = self._text_color
        self._city_label.setStyleSheet(
            f"color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});"
        )
        self._conditions_label.setStyleSheet("color: rgba(103, 193, 245, 235);")
        self._conditions_label.setWordWrap(False)
        if self._condition_icon_widget is not None:
            self._condition_icon_widget.clear_icon()
            self._condition_icon_widget.setVisible(False)
        if self._details_separator is not None:
            self._details_separator.setVisible(False)
        if self._detail_row_widget is not None:
            self._detail_row_widget.setVisible(False)
        if self._detail_row_container is not None:
            self._detail_row_container.setVisible(False)
        if self._forecast_separator is not None:
            self._forecast_separator.setVisible(False)
        if self._forecast_label is not None:
            self._forecast_label.setVisible(False)
        if self._text_column is not None:
            self._text_column.setMinimumHeight(74)
        if self._primary_row is not None:
            self._primary_row.setMinimumHeight(82)
        self._refresh_outer_geometry_for_runtime_content()

    def _restore_location_layout_state(self) -> None:
        if not self._missing_location_active:
            return
        self._missing_location_active = False
        if self._text_column is not None:
            self._text_column.setMinimumHeight(0)
        if self._primary_row is not None:
            self._primary_row.setMinimumHeight(0)
        self._conditions_label.setWordWrap(False)
        self._apply_text_alignment()
    
    # -------------------------------------------------------------------------
    # Lifecycle Implementation Hooks
    # -------------------------------------------------------------------------
    
    def _initialize_impl(self) -> None:
        """Initialize presentation-only Weather resources (lifecycle hook)."""
        if not self._location.strip():
            self._show_missing_location_state()
        logger.debug("[LIFECYCLE] WeatherWidget initialized")

    def _start_runtime_data(self, *, immediate_refresh_on_miss: bool) -> bool:
        """Start the attached neutral data owner and coordinate first-show pixels."""
        service = self._runtime_service
        if service is None:
            logger.error("[WEATHER] Required Weather runtime service is not attached")
            return False

        has_cached_data = service.has_cached_data()
        if has_cached_data:
            self._pending_first_show = False
        else:
            self.hide()
            self._pending_first_show = True

        if not service.start(immediate_refresh_on_miss=immediate_refresh_on_miss):
            self._pending_first_show = False
            return False

        if has_cached_data:
            self._request_fade_in()
        return True

    def _activate_impl(self) -> None:
        """Activate Weather presentation and its attached neutral data owner."""
        if not self._location.strip():
            service = self._runtime_service
            if service is not None:
                service.stop()
            self._show_missing_location_state()
            self._request_fade_in()
            logger.info("[LIFECYCLE] WeatherWidget activated in missing-location state")
            return
        if not self._ensure_thread_manager("WeatherWidget._activate_impl"):
            raise RuntimeError("ThreadManager not available")
        if not self._start_runtime_data(immediate_refresh_on_miss=False):
            raise RuntimeError("Weather runtime service failed to start")
        logger.debug("[LIFECYCLE] WeatherWidget activated")

    def _deactivate_impl(self) -> None:
        """Deactivate Weather presentation and stop its neutral data cadence."""
        service = self._runtime_service
        if service is not None:
            service.stop()
        self._pending_first_show = False
        logger.debug("[LIFECYCLE] WeatherWidget deactivated")

    def _cleanup_impl(self) -> None:
        """Detach presentation and release only a standalone-owned data service."""
        service = self._runtime_service
        if service is not None:
            service.stop()
        self._pending_first_show = False
        self._release_runtime_service()
        logger.debug("[LIFECYCLE] WeatherWidget cleaned up")

    # -------------------------------------------------------------------------
    # Legacy Start/Stop Methods (for backward compatibility)
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Start Weather presentation through the attached neutral data owner."""
        if self._enabled:
            logger.warning("[LIFECYCLE] Weather widget already running")
            return
        if not self._location.strip():
            service = self._runtime_service
            if service is not None:
                service.stop()
            self._show_missing_location_state()
            self._enabled = True
            self._request_fade_in()
            logger.info("Weather widget started in missing-location state")
            return
        if not self._ensure_thread_manager("WeatherWidget.start"):
            return

        self._enabled = True
        if not self._start_runtime_data(immediate_refresh_on_miss=True):
            self._enabled = False
            return
        logger.info("Weather widget started")

    def stop(self) -> None:
        """Stop Weather presentation and the attached neutral data cadence."""
        if not self._enabled:
            return

        service = self._runtime_service
        if service is not None:
            service.stop()

        self._enabled = False
        self._pending_first_show = False
        self.hide()
        logger.debug("Weather widget stopped")

    def is_running(self) -> bool:
        """Check if Weather presentation is running."""
        return self._enabled

    def handle_double_click(self, local_pos) -> bool:
        """Called by WidgetManager dispatch. Triggers a manual Weather refresh."""
        if not self._enabled:
            return False
        service = self._runtime_service
        if service is None:
            logger.error("[WEATHER] Manual refresh rejected: runtime service is not attached")
            return False
        try:
            service.fetch_weather()
            logger.debug("[WEATHER] Double-click triggered weather refresh")
            return True
        except Exception:
            logger.debug("[WEATHER] Double-click refresh failed", exc_info=True)
            return False

    # TRANSITIONAL QWidget/standalone forwarding only; this is not the runtime
    # model API inherited by the future Quick presenter. Runtime-data behavior
    # and state stay owned by WeatherRuntimeService.
    def _fetch_weather(self) -> None:
        service = self._runtime_service
        if service is not None:
            service.fetch_weather()

    def _on_weather_fetched(self, data: Dict[str, Any]) -> None:
        service = self._runtime_service
        if service is not None:
            service.on_weather_fetched(data)

    def _on_fetch_error(self, error: str) -> None:
        service = self._runtime_service
        if service is not None:
            service.on_fetch_error(error)

    def _is_cache_valid(self) -> bool:
        service = self._runtime_service
        return service.is_cache_valid() if service is not None else False

    def _available_primary_text_width(self) -> int:
        """Return a safe text-column width that stays inside the weather card."""
        visible_width = max(self.width() if self.width() > 0 else 0, self._min_content_width)

        icon_space = 0
        if self._show_condition_icon and self._icon_alignment != "NONE":
            icon_space = self._icon_size + 16

        layout_margins = self._padding_left + self._padding_right + 28
        available = visible_width - layout_margins - icon_space
        return max(160, int(available))

    def _fit_weather_font(
        self,
        text: str,
        *,
        point_size: int,
        weight: QFont.Weight,
        max_width: int,
        min_point_size: int,
    ) -> tuple[QFont, str, QFontMetrics]:
        """Fit a single-line weather label to the current card text column."""
        point_size = max(min_point_size, int(point_size))
        while point_size > min_point_size:
            font = QFont(self._font_family, point_size, weight)
            metrics = QFontMetrics(font)
            if metrics.horizontalAdvance(text) <= max_width:
                return font, text, metrics
            point_size -= 1

        font = QFont(self._font_family, min_point_size, weight)
        metrics = QFontMetrics(font)
        fitted = metrics.elidedText(text, Qt.TextElideMode.ElideRight, max_width)
        return font, fitted, metrics
    
    def _update_display(self, data: Optional[Dict[str, Any]]) -> None:
        """Update widget display with weather data using new layout."""
        if not Shiboken.isValid(self):
            return
        if not self._location.strip():
            self._show_missing_location_state()
            return
        self._restore_location_layout_state()
        if not data:
            self._city_label.setText("Weather: No Data")
            self._conditions_label.setText("")
            self._condition_icon_widget.clear_icon()
            self._condition_icon_widget.setVisible(False)
            return

        try:
            # Extract data
            temp = data.get('temperature')
            condition = data.get('condition')
            location = data.get('location')
            weather_code = data.get('weather_code')
            is_day = data.get('is_day', 1)

            # Back-compat
            if temp is None and isinstance(data.get('main'), dict):
                temp = data['main'].get('temp')
            if condition is None and isinstance(data.get('weather'), list) and data['weather']:
                weather_entry = data['weather'][0]
                condition = weather_entry.get('main') or weather_entry.get('description')
                weather_code = weather_entry.get('id') or weather_code
                is_day = weather_entry.get('is_day', is_day)
            if not location:
                location = data.get('name') or self._location

            # Normalize
            temp = 0.0 if temp is None else float(temp)
            condition = 'Unknown' if condition is None else str(condition)
            location = location or self._location
            is_day_bool = bool(int(is_day)) if isinstance(is_day, (int, str)) else bool(is_day)

            # Store for icon refresh
            self._last_is_day = is_day_bool
            self._last_weather_code = weather_code

            # Update forecast
            forecast = data.get('forecast')
            if forecast:
                self._forecast_data = forecast

            # Build plain text (no HTML) to prevent clipping issues
            location_display = str(location).title()
            condition_display = str(condition).title()

            # Feature #5: Font size hierarchy
            # Location = 100% of user setting (largest/base)
            # Condition = 80% of user setting
            # Detail row = 50% of user setting (calculated below)
            location_pt = max(8, int(self._font_size))  # 100% - this is the base
            condition_pt = max(6, int(self._font_size * 0.8))  # 80% of location
            text_width = self._available_primary_text_width()

            # Set font sizes via QFont (not stylesheet) for consistency with shadow rendering
            color = self._text_color
            color_rgba = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"

            city_font, location_display, city_fm = self._fit_weather_font(
                location_display,
                point_size=location_pt,
                weight=QFont.Weight.Bold,
                max_width=text_width,
                min_point_size=12,
            )
            self._city_label.setFont(city_font)
            self._city_label.setStyleSheet(f"color: {color_rgba};")
            self._city_label.setText(location_display)

            # Calculate text metrics for sizing
            city_width = city_fm.horizontalAdvance(location_display)

            # Build condition line: "22°C - Partly Cloudy"
            # Issue #2 Fix: Handle long conditions (3+ words) with smaller font and word wrap
            condition_words = condition_display.split()
            is_long_condition = len(condition_words) >= 3
            
            if is_long_condition:
                # 3+ word conditions: reduce font by 30%, enable word wrap
                condition_pt = max(6, int(self._font_size * 0.8 * 0.7))  # 80% * 70% = 56% of base
                self._conditions_label.setWordWrap(True)
            else:
                # Short conditions (1-2 words): normal size, no word wrap
                self._conditions_label.setWordWrap(False)
            
            condition_text = f"{temp:.0f}°C - {condition_display}"
            condition_font, condition_text, condition_fm = self._fit_weather_font(
                condition_text,
                point_size=condition_pt,
                weight=QFont.Weight.Bold,
                max_width=text_width,
                min_point_size=10,
            )
            self._conditions_label.setFont(condition_font)
            self._conditions_label.setStyleSheet(f"color: {color_rgba};")
            self._conditions_label.setText(condition_text)

            # Calculate text metrics for sizing
            condition_width = condition_fm.horizontalAdvance(condition_text)
            
            self._city_label.setMinimumWidth(0)
            self._conditions_label.setMinimumWidth(0)
            self._city_label.setMaximumWidth(16777215)
            self._conditions_label.setMaximumWidth(16777215)
            
            if self._text_column:
                self._text_column.setMinimumWidth(0)
                self._text_column.setMaximumWidth(16777215)
            
            if self._primary_row:
                self._primary_row.setMinimumWidth(0)
                self._primary_row.setMaximumWidth(16777215)

            # Update condition icon
            if self._show_condition_icon and self._icon_alignment != "NONE":
                icon_path = self._resolve_condition_icon_path(weather_code, condition, is_day_bool)
                if icon_path:
                    self._condition_icon_widget.set_icon_path(icon_path)
                    self._condition_icon_widget.setVisible(True)
                else:
                    self._condition_icon_widget.clear_icon()
                    self._condition_icon_widget.setVisible(False)
            else:
                self._condition_icon_widget.clear_icon()
                self._condition_icon_widget.setVisible(False)

            # Update detail metrics
            if self._show_details_row:
                metrics = self._build_detail_metrics(data)
                if metrics:
                    # Feature #5: Detail font = 50% of location size
                    detail_pt = max(6, int(self._font_size * 0.5))
                    detail_font = QFont(self._font_family, detail_pt, QFont.Weight.Normal)
                    fm = QFontMetrics(detail_font)
                    icon_size = max(_DETAIL_ICON_MIN_PX, int(fm.height() * 1.15))

                    self._detail_row_widget.update_metrics(
                        metrics,
                        detail_font,
                        self._text_color,
                        icon_size,
                        self._get_detail_icon_pixmap
                    )
                    self._detail_row_widget.setVisible(True)
                    self._detail_row_container.setVisible(True)
                    self._details_separator.setVisible(True)
                else:
                    self._detail_row_widget.setVisible(False)
                    self._detail_row_container.setVisible(False)
                    self._details_separator.setVisible(False)
            else:
                self._detail_row_widget.setVisible(False)
                self._detail_row_container.setVisible(False)
                self._details_separator.setVisible(False)

            # Update forecast
            if self._show_forecast and self._forecast_data:
                # Feature #5: Forecast font = 50% of location size (same as detail row)
                forecast_pt = max(6, int(self._font_size * 0.5))
                forecast_font = QFont(self._font_family, forecast_pt, QFont.Weight.Normal)
                forecast_font.setItalic(True)
                self._forecast_label.setFont(forecast_font)
                self._forecast_label.setStyleSheet(f"color: {color_rgba};")
                self._forecast_label.setText(str(self._forecast_data))
                self._forecast_label.setContentsMargins(0, 0, 0, 11)
                self._forecast_label.setVisible(True)
                self._forecast_separator.setVisible(True)
            else:
                self._forecast_label.setVisible(False)
                self._forecast_separator.setVisible(False)

            # Refresh internals while keeping a saved CUSTOM rect authoritative.
            self._refresh_outer_geometry_for_runtime_content()

        except Exception as e:
            logger.exception(f"Error updating weather display: {e}")
            # Check if Qt objects are still valid before accessing them
            try:
                if Shiboken.isValid(self._city_label):
                    self._city_label.setText("Weather: Error")
                if Shiboken.isValid(self._conditions_label):
                    self._conditions_label.setText("")
            except Exception:
                # Widget is being destroyed, ignore
                pass

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
        next_location = str(location or "").strip()
        service = self._runtime_service
        service_was_running = service.is_running() if service is not None else False
        self._location = next_location
        if service is not None:
            service.set_location(next_location)
        
        if not self._location:
            self._show_missing_location_state()
        elif self._enabled:
            self._restore_location_layout_state()
            if service is None:
                logger.error("[WEATHER] Location refresh rejected: runtime service is not attached")
            elif service_was_running and service.is_running():
                service.fetch_weather()
            else:
                self._start_runtime_data(immediate_refresh_on_miss=True)

    def settings_action_at(self, local_pos: QPoint) -> str | None:
        """Return the Weather-settings action only over the inert-state link."""
        if not self._missing_location_active or self._conditions_label is None:
            return None
        top_left = self._conditions_label.mapTo(self, QPoint(0, 0))
        action_rect = QRect(top_left, self._conditions_label.size())
        return WEATHER_SETTINGS_TARGET if action_rect.contains(local_pos) else None

    def handle_click(self, local_pos: QPoint) -> bool:
        target = self.settings_action_at(local_pos)
        if target is None:
            return False
        self.settings_requested.emit(target)
        return True
    
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
        service = self._runtime_service
        if service is not None:
            service.set_thread_manager(thread_manager)

    def set_show_forecast(self, show: bool) -> None:
        """Enable or disable the optional forecast line.
        
        Args:
            show: True to show forecast line when data is available
        """
        self._show_forecast = show
        self._refresh_current_weather_presentation()

    def set_forecast_data(self, forecast: Optional[str]) -> None:
        """Set the forecast text to display.

        Args:
            forecast: Forecast text (e.g. "Tomorrow: 18°C, Partly Cloudy")
        """
        self._forecast_data = forecast
        if self._show_forecast:
            self._refresh_current_weather_presentation()

    def set_show_condition_icon(self, show: bool) -> None:
        """Enable or disable the condition icon display."""
        self._show_condition_icon = show
        self._refresh_current_weather_presentation()

    def set_icon_alignment(self, alignment: str) -> None:
        """Set icon alignment ('LEFT', 'RIGHT', 'NONE')."""
        normalized = (alignment or _DEFAULT_ICON_ALIGNMENT).strip().upper()
        if normalized not in _ICON_ALIGNMENT_OPTIONS:
            normalized = _DEFAULT_ICON_ALIGNMENT
        
        # Only rebuild if alignment actually changed
        if self._icon_alignment != normalized:
            self._icon_alignment = normalized
            # Rebuild the primary row layout
            self._rebuild_primary_layout()
        
        self._refresh_current_weather_presentation()

    def _apply_text_alignment(self) -> None:
        """Right-align city/condition labels when icon is on the left so
        text edges align cleanly; revert to left-align otherwise.
        """
        if not self._city_label or not self._conditions_label:
            return
        if self._icon_alignment == "LEFT":
            self._city_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._conditions_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
        else:
            self._city_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self._conditions_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

    def set_shadow_config(self, config: Optional[Dict[str, Any]]) -> None:
        super().set_shadow_config(config)
        for label in (self._city_label, self._conditions_label, self._forecast_label):
            if hasattr(label, "set_shadow_config"):
                try:
                    label.set_shadow_config(config)  # type: ignore[attr-defined]
                except Exception as e:
                    logger.debug("[WEATHER] Exception suppressed: %s", e)
        if self._detail_row_widget is not None and hasattr(self._detail_row_widget, "set_shadow_config"):
            try:
                self._detail_row_widget.set_shadow_config(config)
            except Exception as e:
                logger.debug("[WEATHER] Exception suppressed: %s", e)
        if self._condition_icon_widget is not None and hasattr(self._condition_icon_widget, "set_shadow_config"):
            try:
                self._condition_icon_widget.set_shadow_config(config)
            except Exception as e:
                logger.debug("[WEATHER] Exception suppressed: %s", e)

    def _rebuild_primary_layout(self) -> None:
        """Rebuild the primary row layout based on current icon alignment.
        
        Issue #4 Fix: Properly remove widgets from layout before re-adding in new order,
        and force layout update to ensure changes take effect immediately.
        """
        if not hasattr(self, '_primary_row') or not self._primary_row:
            return

        self._apply_text_alignment()

        # Get the layout
        primary_layout = self._primary_row.layout()
        if not primary_layout:
            return
        
        logger.debug(f"[WEATHER] Rebuilding primary layout for alignment: {self._icon_alignment}")
        
        # Store references to widgets we need to re-add
        text_col = self._text_column
        icon_widget = self._condition_icon_widget
        
        # Remove all widgets from layout (but keep them as children of parent)
        # We must remove ALL items, not just widgets
        while primary_layout.count() > 0:
            primary_layout.takeAt(0)  # Item is removed from layout but widget remains as child
        
        # Re-add widgets in correct order based on alignment
        if self._icon_alignment == "LEFT":
            # Icon on left, text on right
            logger.debug("[WEATHER] Setting layout: ICON | TEXT")
            if icon_widget:
                primary_layout.addWidget(icon_widget, 0, Qt.AlignmentFlag.AlignVCenter)
            if text_col:
                primary_layout.addWidget(text_col, 1)
        elif self._icon_alignment == "NONE":
            # Text only, no icon
            logger.debug("[WEATHER] Setting layout: TEXT only")
            if text_col:
                primary_layout.addWidget(text_col, 1)
        else:
            # Text on left, icon on right (default: RIGHT)
            logger.debug("[WEATHER] Setting layout: TEXT | ICON")
            if text_col:
                primary_layout.addWidget(text_col, 1)
            if icon_widget:
                primary_layout.addWidget(icon_widget, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # Force layout update to apply changes immediately
        primary_layout.invalidate()
        self._primary_row.updateGeometry()
        self._primary_row.update()

    def set_icon_size(self, size: int) -> None:
        """Set the condition icon size in pixels."""
        self._icon_size = max(32, int(size))
        if self._condition_icon_widget:
            self._condition_icon_widget.set_icon_size(self._icon_size)
        self._refresh_current_weather_presentation()

    def set_show_details_row(self, show: bool) -> None:
        """Enable or disable the detail metrics row."""
        self._show_details_row = show
        self._refresh_current_weather_presentation()

    def set_detail_icon_size(self, size: int) -> None:
        """Set the detail row icon size in pixels."""
        self._detail_icon_size = max(16, int(size))
        self._refresh_current_weather_presentation()

    def set_icon_monochrome(self, enabled: bool) -> None:
        """Enable/disable monochrome (grayscale) weather icon.
        
        Feature #6: Monochrome icon option with zero performance impact.
        Conversion happens once on icon load, not every paint.
        """
        self._icon_monochrome = bool(enabled)
        if self._condition_icon_widget:
            self._condition_icon_widget.set_monochrome(self._icon_monochrome)
        logger.debug(f"[WEATHER] Icon monochrome set to: {self._icon_monochrome}")

    def is_icon_monochrome(self) -> bool:
        """Return current monochrome icon state."""
        return self._icon_monochrome

    def _update_stylesheet(self) -> None:
        """Update widget stylesheet based on current settings."""
        selector = f"#{self.objectName()}" if self.objectName() else "QLabel"
        if self.uses_painted_frame_shadow():
            self.setStyleSheet(f"""
                {selector} {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: transparent;
                    border: {self._bg_border_width}px solid transparent;
                    border-radius: 8px;
                }}
            """)
            return
        if self._show_background:
            # With background frame
            self.setStyleSheet(f"""
                {selector} {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: rgba({self._bg_color.red()}, {self._bg_color.green()}, 
                                          {self._bg_color.blue()}, {self._bg_color.alpha()});
                    border: {self._bg_border_width}px solid rgba({self._bg_border_color.red()}, 
                                                                 {self._bg_border_color.green()}, 
                                                                 {self._bg_border_color.blue()}, 
                                                                 {self._bg_border_color.alpha()});
                    border-radius: 8px;
                }}
            """)
        else:
            # Transparent background (default)
            self.setStyleSheet(f"""
                {selector} {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: transparent;
                }}
            """)
    
    def cleanup(self) -> None:
        """Clean up resources."""
        logger.debug("Cleaning up weather widget")
        super().cleanup()

    def _fade_in(self) -> None:
        """Fade the widget in via ShadowFadeProfile.

        The ShadowFadeProfile helper drives opacity staging; card shadows are
        painter-owned by the widget.
        """

        try:
            ShadowFadeProfile.start_fade_in(
                self,
                self._shadow_config,
                has_background_frame=self._show_background,
            )
        except Exception:
            # Fallback: just show and, if available, apply the shared shadow.
            logger.warning("[LIFECYCLE][FALLBACK] Weather fade-in failed; using direct show", exc_info=True)
            try:
                self.show()
            except Exception as e:
                logger.debug("[WEATHER] Exception suppressed: %s", e)
