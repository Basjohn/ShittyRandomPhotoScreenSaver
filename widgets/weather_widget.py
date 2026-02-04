"""
Weather widget for screensaver overlay.

Displays current weather information using Open-Meteo API (no API key needed).
"""
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import os
import json
import random
from PySide6.QtWidgets import QWidget, QSizePolicy, QHBoxLayout, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, QObject, QSize, QTimer
from PySide6.QtGui import QFont, QPainter, QPen, QColor, QFontMetrics, QPixmap
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


class WeatherConditionIcon(QWidget):
    """Widget that renders static PNG weather icons with proper DPR scaling."""

    def __init__(self, size_px: int = 96, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._icon_path: Optional[Path] = None
        self._size_px = max(48, int(size_px))
        self._padding = 4
        self._set_fixed_box()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _set_fixed_box(self) -> None:
        box = QSize(self._size_px, self._size_px)
        self.setMinimumSize(box)
        self.setMaximumSize(box)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def set_icon_size(self, size_px: int) -> None:
        size_px = max(32, int(size_px))
        if size_px == self._size_px:
            return
        self._size_px = size_px
        self._set_fixed_box()
        self._pixmap = None  # Force reload at new size
        self.update()

    def clear_icon(self) -> None:
        self._pixmap = None
        self._icon_path = None
        self.update()

    def set_icon_path(self, icon_path: Optional[Path]) -> None:
        if icon_path is None or not icon_path.exists():
            self.clear_icon()
            return
        if self._icon_path == icon_path and self._pixmap is not None:
            return

        self._icon_path = icon_path
        self._load_pixmap()
        self.update()

    def _load_pixmap(self) -> None:
        """Load pixmap at full native resolution without scaling."""
        if self._icon_path is None:
            self._pixmap = None
            return

        # Load pixmap at full native resolution
        source = QPixmap(str(self._icon_path))
        if source.isNull():
            logger.warning(f"[WEATHER] Failed to load icon: {self._icon_path}")
            self._pixmap = None
            return

        self._pixmap = source

    def has_icon(self) -> bool:
        return self._pixmap is not None and not self._pixmap.isNull()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if not self.has_icon():
            painter.end()
            return

        # Draw pixmap scaled to target with smooth transformation
        target = self.rect().adjusted(self._padding, self._padding, -self._padding, -self._padding)
        painter.drawPixmap(target, self._pixmap)
        painter.end()


class WeatherDetailIcon(QWidget):
    """Custom widget to paint detail metric icons (rain/humidity/wind)."""

    def __init__(self, size_px: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._size_px = max(_DETAIL_ICON_MIN_PX, size_px)
        self._box = QSize(self._size_px + 6, self._size_px + 6)
        self.setFixedSize(self._box)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._vertical_inset = 3
        self._baseline_offset = 0

    def set_pixmap(self, pixmap: Optional[QPixmap]) -> None:
        self._pixmap = pixmap
        self.update()

    def set_baseline_offset(self, pixels: int) -> None:
        max_drop = max(0, (self._box.height() // 2) - 2)
        self._baseline_offset = max(0, min(pixels, max_drop))
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._box)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._box)

    def pixmap(self) -> Optional[QPixmap]:
        return self._pixmap

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._pixmap is None or self._pixmap.isNull():
            painter.end()
            return
        target = self.rect().adjusted(3, self._vertical_inset, -3, -self._vertical_inset)
        # Scale pixmap to target size with smooth transformation and center it
        scaled = self._pixmap.scaled(
            target.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = target.x() + (target.width() - scaled.width()) // 2
        y = target.y() + (target.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()


class WeatherDetailRow(QWidget):
    """Dedicated widget that renders the compact humidity/rain/wind row."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._metrics: List[Tuple[str, str]] = []
        self._font = QFont()
        self._font_metrics = QFontMetrics(self._font)
        self._text_color = QColor(255, 255, 255)
        self._icon_size = 16
        self._segment_widgets: List[QWidget] = []
        self._segment_pool: Dict[str, QWidget] = {}
        self._segment_icon_labels: Dict[str, WeatherDetailIcon] = {}
        self._segment_text_labels: Dict[str, QLabel] = {}

        # Outer layout
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Segments layout with stretch like old code
        self._segments_layout = QHBoxLayout()
        self._segments_layout.setContentsMargins(0, 0, 0, 0)
        self._segments_layout.setSpacing(12)
        self._segments_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._segments_layout.addStretch(1)

        outer.addLayout(self._segments_layout, 1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def update_metrics(
        self,
        metrics: List[Tuple[str, str]],
        font: QFont,
        color: QColor,
        icon_size: int,
        icon_fetcher: callable,
    ) -> None:
        """Refresh metric segments with icons."""
        self._metrics = list(metrics)
        self._font = QFont(font)
        self._font_metrics = QFontMetrics(self._font)
        self._text_color = QColor(color)
        self._icon_size = max(18, int(icon_size))
        self._icon_fetcher = icon_fetcher

        self._rebuild_segments()
        self.setVisible(bool(metrics))

    def _rebuild_segments(self) -> None:
        """Rebuild segments with pooling like old code."""
        has_metrics = bool(self._metrics)
        self._segments_layout.setContentsMargins(
            0, 6 if has_metrics else 0, 0, 4 if has_metrics else 0
        )
        self._segments_layout.setSpacing(
            max(12, self._icon_size // 2 + 4) if has_metrics else 0
        )

        active_keys: List[str] = []
        for key, value in self._metrics:
            active_keys.append(key)
            segment = self._segment_pool.get(key)
            if segment is None:
                segment = self._create_segment(key)
                self._segment_pool[key] = segment
                # Insert before stretch like old code
                insert_pos = max(0, self._segments_layout.count() - 1)
                self._segments_layout.insertWidget(insert_pos, segment)
            self._configure_segment(key, value)
            segment.setVisible(True)

        # Hide inactive segments
        for key, segment in self._segment_pool.items():
            if key not in active_keys:
                segment.setVisible(False)

    def _create_segment(self, key: str) -> QWidget:
        """Create a segment widget like old code."""
        segment = QWidget(self)
        segment.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        segment.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout = QHBoxLayout(segment)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        icon_label = WeatherDetailIcon(self._icon_size, segment)
        text_label = QLabel(segment)
        text_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        text_label.setWordWrap(False)
        text_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        # MinimumExpanding like old code
        text_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)

        layout.addWidget(icon_label)
        layout.addWidget(text_label)

        self._segment_icon_labels[key] = icon_label
        self._segment_text_labels[key] = text_label

        return segment

    def _configure_segment(self, key: str, value: str) -> None:
        """Configure segment like old code."""
        text_label = self._segment_text_labels[key]
        icon_label = self._segment_icon_labels[key]

        text_label.setFont(self._font)
        text_label.setText(value)
        text_label.setStyleSheet(
            f"color: rgba({self._text_color.red()}, {self._text_color.green()}, "
            f"{self._text_color.blue()}, {self._text_color.alpha()});"
        )

        # Get and set icon
        pixmap = self._icon_fetcher(key, self._icon_size)
        icon_label.set_pixmap(pixmap if pixmap and not pixmap.isNull() else None)

        # Fixed height like old code
        line_height = self._font_metrics.height()
        height = max(self._icon_size + 10, line_height + 6)
        icon_label.parentWidget().setFixedHeight(height)


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
        
        # Layout sizing - minimum width like old code
        self._min_content_width = 420
        
        # Padding: reasonable defaults
        self._padding_top = 6
        self._padding_bottom = 6
        self._padding_left = 12
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
        self._show_details_row = True
        self._detail_icon_size = _DEFAULT_DETAIL_ICON_SIZE
        self._last_is_day = True
        self._last_weather_code: Optional[int] = None

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
        
        logger.debug(f"WeatherWidget created (location={location}, position={position.value})")
    
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
        self._primary_row.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
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

        self._city_label = QLabel(self._text_column)
        self._city_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._city_label.setWordWrap(False)
        self._city_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._city_label.setTextFormat(Qt.TextFormat.PlainText)
        self._city_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self._city_label.setMinimumWidth(self._min_content_width)

        self._conditions_label = QLabel(self._text_column)
        self._conditions_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._conditions_label.setWordWrap(False)
        self._conditions_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._conditions_label.setTextFormat(Qt.TextFormat.PlainText)
        self._conditions_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self._conditions_label.setMinimumWidth(self._min_content_width)

        text_layout.addWidget(self._city_label)
        text_layout.addWidget(self._conditions_label)

        # Build primary layout based on icon alignment
        if self._icon_alignment == "LEFT":
            # Icon on left, text on right
            self._condition_icon_widget = WeatherConditionIcon(
                size_px=self._icon_size,
                parent=self._primary_row
            )
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
            self._condition_icon_widget.setVisible(False)
            primary_layout.addWidget(
                self._condition_icon_widget, 0,
                Qt.AlignmentFlag.AlignVCenter
            )

        self._root_layout.addWidget(self._primary_row)

        # Details separator line
        self._details_separator = self._create_separator()
        self._root_layout.addWidget(self._details_separator)

        # Detail row container - expanding width with minimum like old code
        self._detail_row_container = QWidget(self)
        self._detail_row_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._detail_row_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._detail_row_container.setMinimumWidth(self._min_content_width)
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
        self._forecast_label = QLabel(self)
        self._forecast_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._forecast_label.setWordWrap(True)
        self._forecast_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._forecast_label.setTextFormat(Qt.TextFormat.RichText)
        self._forecast_label.setVisible(False)
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
                    x1 = self._padding_left
                    x2 = self.width() - self._padding_right
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
            return icon_name
        if "-day" in icon_name:
            return icon_name.replace("-day", "-night")
        if icon_name.endswith(".png"):
            base = icon_name[:-4]
            return f"{base}-night.png"
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

        # Scale to requested size - use FastTransformation for sharper icons
        scaled = pixmap.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation
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

        # Rain chance fix: try to get from hourly forecast if not in current
        if precipitation is None:
            hourly = data.get("hourly", {})
            if isinstance(hourly, dict):
                precip_data = hourly.get("precipitation_probability", [])
                if isinstance(precip_data, list) and precip_data:
                    # Get current hour index
                    current_hour = datetime.now().hour
                    if current_hour < len(precip_data):
                        precipitation = _to_float(precip_data[current_hour])

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

            # Extract detail metrics for persistence
            precipitation, humidity, windspeed = self._extract_detail_values(data)

            payload = {
                "location": location,
                "temperature": float(temp),
                "condition": str(condition),
                "timestamp": datetime.now().isoformat(),
            }

            # Include detail metrics if available
            if humidity is not None:
                payload["humidity"] = float(humidity)
            if precipitation is not None:
                payload["precipitation_probability"] = float(precipitation)
            if windspeed is not None:
                payload["windspeed"] = float(windspeed)

            _CACHE_FILE.write_text(json.dumps(payload), encoding="utf-8")
        except Exception:
            logger.debug("Failed to persist weather cache", exc_info=True)
    
    def _update_display(self, data: Optional[Dict[str, Any]]) -> None:
        """Update widget display with weather data using new layout."""
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

            city_pt = max(6, int(self._font_size * 0.9))  # Location: 10% smaller
            details_pt = max(6, self._font_size - 2)

            # Set font sizes via stylesheet on labels
            color = self._text_color
            color_rgba = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"

            self._city_label.setStyleSheet(f"font-size: {city_pt}pt; font-weight: 700; color: {color_rgba};")
            self._city_label.setText(location_display)
            
            # Force city label to size properly
            city_font = QFont(self._font_family, city_pt, QFont.Weight.Bold)
            city_fm = QFontMetrics(city_font)
            city_width = city_fm.horizontalAdvance(location_display)
            self._city_label.setMinimumWidth(city_width + 10)

            # Build condition line: "22°C - Partly Cloudy"
            condition_text = f"{temp:.0f}°C - {condition_display}"
            self._conditions_label.setStyleSheet(f"font-size: {details_pt}pt; font-weight: 700; color: {color_rgba};")
            self._conditions_label.setText(condition_text)
            
            # Force label to size properly to fit text
            details_font = QFont(self._font_family, details_pt, QFont.Weight.Bold)
            fm = QFontMetrics(details_font)
            text_width = fm.horizontalAdvance(condition_text)
            self._conditions_label.setMinimumWidth(text_width + 10)

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
                    # Calculate detail font size
                    detail_pt = max(6, self._font_size - 12)
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
                forecast_pt = max(6, self._font_size - 12)
                forecast_html = f"<span style='font-size:{forecast_pt}pt; font-style:italic; font-weight:400; color:{color_rgba};'>{self._forecast_data}</span>"
                self._forecast_label.setText(forecast_html)
                self._forecast_label.setVisible(True)
                self._forecast_separator.setVisible(True)
            else:
                self._forecast_label.setVisible(False)
                self._forecast_separator.setVisible(False)

            # Adjust layout
            self.adjustSize()
            if self.parent():
                self._update_position()

        except Exception as e:
            logger.exception(f"Error updating weather display: {e}")
            self._city_label.setText("Weather: Error")
            self._conditions_label.setText("")

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

    def set_show_condition_icon(self, show: bool) -> None:
        """Enable or disable the condition icon display."""
        self._show_condition_icon = show
        if self._cached_data:
            self._update_display(self._cached_data)

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
        
        if self._cached_data:
            self._update_display(self._cached_data)

    def _rebuild_primary_layout(self) -> None:
        """Rebuild the primary row layout based on current icon alignment."""
        if not hasattr(self, '_primary_row') or not self._primary_row:
            return
        
        # Get the layout
        primary_layout = self._primary_row.layout()
        if not primary_layout:
            return
        
        # Remove existing widgets from layout (but keep them as children)
        while primary_layout.count():
            item = primary_layout.takeAt(0)
            if item.widget():
                # Just remove from layout, don't delete
                pass
        
        # Re-add widgets in correct order
        if self._icon_alignment == "LEFT":
            # Icon on left, text on right
            if self._condition_icon_widget:
                primary_layout.addWidget(self._condition_icon_widget, 0, Qt.AlignmentFlag.AlignVCenter)
            primary_layout.addWidget(self._text_column, 1)
        else:
            # Text on left, icon on right (default)
            primary_layout.addWidget(self._text_column, 1)
            if self._condition_icon_widget:
                primary_layout.addWidget(self._condition_icon_widget, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_icon_size(self, size: int) -> None:
        """Set the condition icon size in pixels."""
        self._icon_size = max(32, int(size))
        if self._condition_icon_widget:
            self._condition_icon_widget.set_icon_size(self._icon_size)
        if self._cached_data:
            self._update_display(self._cached_data)

    def set_show_details_row(self, show: bool) -> None:
        """Enable or disable the detail metrics row."""
        self._show_details_row = show
        if self._cached_data:
            self._update_display(self._cached_data)

    def set_detail_icon_size(self, size: int) -> None:
        """Set the detail row icon size in pixels."""
        self._detail_icon_size = max(16, int(size))
        if self._cached_data:
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
