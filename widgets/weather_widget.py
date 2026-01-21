"""
Weather widget for screensaver overlay.

Displays current weather information using Open-Meteo API (no API key needed).
"""
from typing import Any, Dict, Optional, Tuple, List, Callable
import html
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import os
import json
import tempfile
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QFrame,
)
from PySide6.QtCore import QTimer, Qt, Signal, QObject, QRectF, QSize
from PySide6.QtGui import (
    QFont,
    QPainter,
    QColor,
    QFontMetrics,
    QPixmap,
    QImage,
)
from PySide6.QtSvg import QSvgRenderer
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.threading.manager import ThreadManager
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
_WEATHER_ICON_DIR = Path(__file__).resolve().parents[1] / "images" / "weather"
_METRIC_ICON_FILES = {
    "rain": "umbrella.svg",
    "humidity": "humidity.svg",
    "wind": "wind.svg",
}
_DETAIL_ICON_MIN_PX = 30


class WeatherDetailIcon(QWidget):
    """Custom widget to paint detail icons without QLabel quirks."""

    def __init__(self, size_px: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._debug_background = False
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

    def set_debug_background(self, enabled: bool) -> None:
        self._debug_background = enabled
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

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt signature
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._debug_background:
            painter.fillRect(
                self.rect(),
                QColor(255, 0, 0, 45),
            )
            pen = painter.pen()
            pen.setColor(QColor(255, 255, 255, 140))
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if self._pixmap is None or self._pixmap.isNull():
            painter.end()
            return
        target = self.rect().adjusted(3, self._vertical_inset, -3, -self._vertical_inset)
        scaled = self._pixmap.scaled(
            target.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = target.x() + (target.width() - scaled.width()) // 2
        y = target.y() + (target.height() - scaled.height()) // 2 + self._baseline_offset
        painter.drawPixmap(x, y, scaled)
        painter.end()


class WeatherDetailRow(QWidget):
    """Dedicated widget that renders the compact humidity/rain/wind row."""

    def __init__(
        self,
        icon_fetcher: Callable[[str, int], Optional[QPixmap]],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._icon_fetcher = icon_fetcher
        self._metrics: List[Tuple[str, str]] = []
        self._font = QFont()
        self._font_metrics = QFontMetrics(self._font)
        self._text_color = QColor(255, 255, 255)
        self._icon_size = 16
        self._segment_widgets: List[QWidget] = []
        self._debug_dumped_icons: set[str] = set()

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._segments_layout = QHBoxLayout()
        self._segments_layout.setContentsMargins(0, 0, 0, 0)
        self._segments_layout.setSpacing(12)
        self._segments_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        outer.addLayout(self._segments_layout, 1)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def update_metrics(
        self,
        metrics: List[Tuple[str, str]],
        font: QFont,
        color: QColor,
        icon_size: int,
    ) -> None:
        """Refresh metric segments."""
        self._metrics = list(metrics)
        self._font = QFont(font)
        self._font_metrics = QFontMetrics(self._font)
        self._text_color = QColor(color)
        self._icon_size = max(18, int(icon_size))
        self._rebuild_segments()
        self.setVisible(bool(metrics))

    def _rebuild_segments(self) -> None:
        while self._segments_layout.count():
            item = self._segments_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self._segment_widgets.clear()

        if not self._metrics:
            return

        self._segments_layout.setContentsMargins(0, 6, 0, 4)
        self._segments_layout.setSpacing(max(12, self._icon_size // 2 + 4))
        line_height = self._font_metrics.height()

        for key, value in self._metrics:
            segment = QWidget(self)
            segment.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            segment.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            segment.setFixedHeight(max(self._icon_size + 10, line_height + 6))
            layout = QHBoxLayout(segment)
            layout.setContentsMargins(0, 1, 0, 1)
            layout.setSpacing(3)
            layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            icon_label = WeatherDetailIcon(self._icon_size, segment)
            icon_edge = max(10, self._icon_size)
            pixmap = self._icon_fetcher(key, icon_edge)
            original_pixmap = pixmap
            if pixmap is not None and not pixmap.isNull():
                icon_label.set_pixmap(pixmap)
            base_drop = min(icon_label.height() // 3, int(self._icon_size * 0.18) + 2)
            soft_drop = max(0, base_drop - 1)
            icon_label.set_baseline_offset(soft_drop)
            icon_label.set_debug_background(is_perf_metrics_enabled())
            if is_perf_metrics_enabled():
                label_pixmap = icon_label.pixmap()
                widget_size = (icon_label.width(), icon_label.height())
                state = "none"
                incoming_size: Optional[Tuple[int, int]] = None
                label_size: Optional[Tuple[int, int]] = None
                if original_pixmap is not None:
                    state = "null" if original_pixmap.isNull() else "ready"
                    incoming_size = (
                        original_pixmap.width(),
                        original_pixmap.height(),
                    )
                if label_pixmap is not None:
                    label_size = (label_pixmap.width(), label_pixmap.height())
                logger.info(
                    "[WEATHER][DETAIL][ICON][UI] key=%s state=%s incoming=%s label=%s widget=%s scaled=%s",
                    key,
                    state,
                    incoming_size,
                    label_size,
                    widget_size,
                    False,
                )
                size_hint = icon_label.sizeHint()
                rect = icon_label.rect()
                logger.info(
                    "[WEATHER][DETAIL][ICON][GEOM] key=%s fixed=%s size_hint=(%s, %s) rect=(%s, %s, %s, %s) "
                    "segment_hint=(%s, %s)",
                    key,
                    widget_size,
                    size_hint.width(),
                    size_hint.height(),
                    rect.x(),
                    rect.y(),
                    rect.width(),
                    rect.height(),
                    segment.sizeHint().width(),
                    segment.sizeHint().height(),
                )
                if (
                    original_pixmap is not None
                    and not original_pixmap.isNull()
                    and key not in self._debug_dumped_icons
                ):
                    dump_dir = Path(tempfile.gettempdir()) / "srpss_weather_icons"
                    dump_dir.mkdir(parents=True, exist_ok=True)
                    dump_path = dump_dir / f"{key}_{self._icon_size}px.png"
                    try:
                        pixmap.save(str(dump_path), "PNG")
                        logger.info(
                            "[WEATHER][DETAIL][ICON][DUMP] key=%s path=%s size=%s",
                            key,
                            dump_path,
                            incoming_size,
                        )
                    except Exception as exc:  # pragma: no cover - best-effort debug
                        logger.warning(
                            "[WEATHER][DETAIL][ICON][DUMP] Failed key=%s path=%s err=%s",
                            key,
                            dump_path,
                            exc,
                        )
                    else:
                        self._debug_dumped_icons.add(key)

            text_label = QLabel(value, segment)
            text_label.setFont(self._font)
            text_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            text_label.setWordWrap(False)
            text_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            text_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
            text_label.setStyleSheet(
                f"color: rgba({self._text_color.red()}, {self._text_color.green()}, "
                f"{self._text_color.blue()}, {self._text_color.alpha()});"
            )

            layout.addWidget(icon_label)
            layout.addWidget(text_label)

            self._segments_layout.addWidget(segment)
            self._segment_widgets.append(segment)

        self._segments_layout.addStretch(1)

    @property
    def metrics(self) -> List[Tuple[str, str]]:
        return list(self._metrics)

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
        self.setObjectName("weatherOverlayCard")
        
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
        
        # Layout sizing
        self._min_content_width = 520

        # Padding: slightly more at top/bottom, extra slack on the right so the
        # drop shadow doesn't make TOP_RIGHT appear flush with the screen edge.
        self._padding_top = 4
        self._padding_bottom = 4
        self._padding_left = 12
        self._padding_right = 16
        
        # Set visual padding for base class positioning (aligns visible content to margins)
        # This replaces the custom horizontal_margin adjustment in _update_position
        self.set_visual_padding(
            top=self._padding_top,
            right=self._padding_right,
            bottom=self._padding_bottom,
            left=self._padding_left,
        )
        self.setMinimumWidth(self._min_content_width + self._padding_left + self._padding_right)
        
        # Optional forecast line
        self._show_forecast = False
        self._forecast_data: Optional[str] = None
        
        # Detail row + layout tracking
        self._show_details_row = False
        self._detail_metrics: List[Tuple[str, str]] = []
        self._detail_icon_size = 14
        self._detail_icon_cache: Dict[Tuple[str, int, int], QPixmap] = {}
        self._detail_renderer_cache: Dict[str, QSvgRenderer] = {}
        self._details_font: Optional[QFont] = None
        self._details_font_metrics: Optional[QFontMetrics] = None
        self._city_label: Optional[QLabel] = None
        self._conditions_label: Optional[QLabel] = None
        self._forecast_label: Optional[QLabel] = None
        self._details_separator: Optional[QFrame] = None
        self._forecast_separator: Optional[QFrame] = None
        self._detail_row_widget: Optional[WeatherDetailRow] = None
        self._detail_row_container: Optional[QWidget] = None
        self._forecast_container: Optional[QWidget] = None
        self._primary_row: Optional[QWidget] = None
        self._primary_spacer: Optional[QWidget] = None
        self._root_layout: Optional[QVBoxLayout] = None
        
        # Setup UI
        self._setup_ui()
        
        logger.debug(f"WeatherWidget created (location={location}, position={position.value})")
    
    # ------------------------------------------------------------------
    # Detail row helpers
    # ------------------------------------------------------------------
    def _clear_detail_caches(self) -> None:
        """Reset icon caches when styling changes."""
        self._detail_icon_cache.clear()
        self._detail_renderer_cache.clear()
    
    def _metric_label(self, key: str) -> str:
        return {
            "rain": "Rain chance",
            "humidity": "Humidity",
            "wind": "Wind",
        }.get(key, key.title())
    
    def _extract_detail_values(
        self, data: Dict[str, Any]
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Return normalized precipitation, humidity, and windspeed values."""

        def _to_float(value) -> Optional[float]:
            try:
                if value is None:
                    return None
                return float(value)
            except (ValueError, TypeError):
                return None

        precipitation_raw = data.get("precipitation_probability")
        if precipitation_raw is None:
            precipitation_raw = data.get("precipitation_chance")
        humidity_raw = data.get("humidity")
        if humidity_raw is None:
            humidity_raw = (data.get("main") or {}).get("humidity")
        windspeed_raw = data.get("windspeed")
        if windspeed_raw is None:
            windspeed_raw = (data.get("wind") or {}).get("speed")

        precipitation = _to_float(precipitation_raw)
        humidity = _to_float(humidity_raw)
        windspeed = _to_float(windspeed_raw)

        return precipitation, humidity, windspeed
    
    def _update_detail_metrics(self, data: Dict[str, Any]) -> None:
        """Compute available detail metrics from provider payload."""
        metrics: List[Tuple[str, str]] = []
        precipitation, humidity, windspeed = self._extract_detail_values(data)
        
        if precipitation is not None:
            metrics.append(("rain", f"{precipitation:.0f}%"))
        if humidity is not None:
            metrics.append(("humidity", f"{humidity:.0f}%"))
        if windspeed is not None:
            metrics.append(("wind", f"{windspeed:.1f} km/h"))
        
        self._detail_metrics = metrics
        if is_perf_metrics_enabled():
            logger.info(
                "[WEATHER][DETAIL] Metrics updated (rain=%s, humidity=%s, wind=%s) -> %s segments",
                precipitation,
                humidity,
                windspeed,
                len(metrics),
            )
            if self._show_details_row and not metrics:
                logger.info(
                    "[WEATHER][DETAIL] Detail row requested but metrics empty. Keys present: rain=%s humidity=%s wind=%s",
                    precipitation,
                    humidity,
                    windspeed,
                )
    
    def _update_detail_tooltip(self, base: str) -> None:
        """Attach detail values to the widget tooltip."""
        tooltip_lines = [base]
        if self._detail_metrics:
            detail_text = ", ".join(
                f"{self._metric_label(key)} {value}"
                for key, value in self._detail_metrics
            )
            tooltip_lines.append(detail_text)
        if self._show_forecast and self._forecast_data:
            tooltip_lines.append(f"Forecast: {self._forecast_data}")
        self.setToolTip("\n".join(tooltip_lines))
    
    def _get_metric_icon_pixmap(self, key: str, size: int) -> Optional[QPixmap]:
        """Return cached monochrome pixmap for requested icon."""
        if key not in _METRIC_ICON_FILES:
            logger.warning("[WEATHER][DETAIL][ICON] No mapping for key=%s", key)
            return None
        icon_file = _WEATHER_ICON_DIR / _METRIC_ICON_FILES[key]
        if not icon_file.exists():
            logger.warning(
                "[WEATHER][DETAIL][ICON] Icon file missing for key=%s path=%s",
                key,
                icon_file,
            )
            return None

        dpr = max(1.0, self.devicePixelRatioF())
        base_size = max(6, int(size))
        cache_key = (key, int(round(dpr * 100)), base_size)
        cached = self._detail_icon_cache.get(cache_key)
        if cached is not None:
            return cached
        
        renderer = self._detail_renderer_cache.get(key)
        if renderer is not None and not renderer.isValid():
            logger.warning(
                "[WEATHER][DETAIL][ICON] Cached renderer invalidated key=%s path=%s",
                key,
                icon_file,
            )
            self._detail_renderer_cache.pop(key, None)
            renderer = None

        if renderer is None:
            renderer = QSvgRenderer(str(icon_file))
            if not renderer.isValid():
                logger.warning(
                    "[WEATHER][DETAIL][ICON] Renderer invalid for key=%s path=%s",
                    key,
                    icon_file,
                )
                return None
            self._detail_renderer_cache[key] = renderer

        target_px = int(round(base_size * dpr))
        image = QImage(target_px, target_px, QImage.Format.Format_ARGB32_Premultiplied)
        if image.isNull():
            logger.warning(
                "[WEATHER][DETAIL][ICON] Failed to allocate QImage key=%s size=%s",
                key,
                target_px,
            )
            return None
        image.fill(Qt.GlobalColor.transparent)

        try:
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            renderer.render(painter, QRectF(0, 0, target_px, target_px))
            painter.end()
        except Exception as exc:  # pragma: no cover - Qt failures are rare
            logger.warning(
                "[WEATHER][DETAIL][ICON] Render failure key=%s size=%s err=%s",
                key,
                target_px,
                exc,
            )
            return None

        def _crop_alpha(image_obj: QImage) -> Optional[QImage]:
            width = image_obj.width()
            height = image_obj.height()
            left, right = width, -1
            top, bottom = height, -1
            for y in range(height):
                for x in range(width):
                    if QColor(image_obj.pixel(x, y)).alpha() > 0:
                        if x < left:
                            left = x
                        if x > right:
                            right = x
                        if y < top:
                            top = y
                        if y > bottom:
                            bottom = y
            if left >= right or top >= bottom:
                return None
            return image_obj.copy(left, top, right - left + 1, bottom - top + 1)

        cropped_image = _crop_alpha(image)
        if cropped_image is not None:
            image = cropped_image.scaled(
                target_px,
                target_px,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        pixmap = QPixmap.fromImage(image)
        if pixmap.isNull():
            logger.warning(
                "[WEATHER][DETAIL][ICON] Null pixmap after render key=%s size=%s",
                key,
                target_px,
            )
            return None

        # Apply monochrome tint to keep icons desaturated.
        tint_alpha = int(self._text_color.alpha() * 0.9)
        tint = QColor(
            self._text_color.red(),
            self._text_color.green(),
            self._text_color.blue(),
            tint_alpha,
        )
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), tint)
        painter.end()

        pixmap.setDevicePixelRatio(dpr)
        self._detail_icon_cache[cache_key] = pixmap
        return pixmap

    def _fetch_detail_icon(self, key: str, size: int) -> Optional[QPixmap]:
        pixmap = self._get_metric_icon_pixmap(key, size)
        if pixmap is None:
            logger.warning(
                "[WEATHER][DETAIL][ICON] Failed to provide pixmap key=%s size=%s show=%s",
                key,
                size,
                self._show_details_row,
            )
            return None
        # Ensure returned pixmap respects current DPR
        pixmap.setDevicePixelRatio(max(1.0, self.devicePixelRatioF()))
        return pixmap
    
    def _setup_ui(self) -> None:
        """Setup widget UI."""
        self._apply_base_styling()
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception as e:
            logger.debug("[WEATHER] Exception suppressed: %s", e)

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(
            self._padding_left,
            self._padding_top,
            self._padding_right,
            self._padding_bottom,
        )
        self._root_layout.setSpacing(4)

        self._primary_row = QWidget(self)
        self._primary_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._primary_row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        primary_layout = QHBoxLayout(self._primary_row)
        primary_layout.setContentsMargins(0, 0, 0, 0)
        primary_layout.setSpacing(8)

        text_column = QWidget(self._primary_row)
        text_column.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        text_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        text_layout = QVBoxLayout(text_column)
        text_layout.setContentsMargins(8, 2, 8, 2)
        text_layout.setSpacing(1)

        self._city_label = self._create_content_label(word_wrap=False)
        self._city_label.setContentsMargins(0, 0, 0, 0)
        self._conditions_label = self._create_content_label(word_wrap=False)
        self._conditions_label.setContentsMargins(0, 1, 0, 0)
        text_layout.addWidget(self._city_label)
        text_layout.addWidget(self._conditions_label)

        primary_layout.addWidget(text_column, 1)

        self._root_layout.addWidget(self._primary_row)

        self._details_separator = self._create_separator(top_padding=4, bottom_padding=4)
        self._root_layout.addWidget(self._details_separator)

        self._detail_row_container = QWidget(self)
        self._detail_row_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._detail_row_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._detail_row_container.setMinimumWidth(self._min_content_width)
        detail_layout = QVBoxLayout(self._detail_row_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(0)

        self._detail_row_widget = WeatherDetailRow(self._fetch_detail_icon, self)
        self._detail_row_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._detail_row_widget.setVisible(False)
        detail_layout.addWidget(self._detail_row_widget)
        self._detail_row_container.setVisible(False)
        self._root_layout.addWidget(self._detail_row_container)

        self._forecast_separator = self._create_separator(top_padding=4, bottom_padding=4)
        self._root_layout.addWidget(self._forecast_separator)

        self._forecast_container = QWidget(self)
        self._forecast_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._forecast_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._forecast_container.setMinimumWidth(self._min_content_width)
        forecast_layout = QVBoxLayout(self._forecast_container)
        forecast_layout.setContentsMargins(0, 2, 0, 0)
        forecast_layout.setSpacing(0)

        self._forecast_label = self._create_content_label(word_wrap=True)
        self._forecast_label.setVisible(False)
        forecast_layout.addWidget(self._forecast_label)
        self._forecast_container.setVisible(False)
        self._root_layout.addWidget(self._forecast_container)

    def _create_content_label(self, *, word_wrap: bool = True) -> QLabel:
        label = QLabel(self)
        label.setObjectName("")
        label.setWordWrap(word_wrap)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        label.setFrameShape(QFrame.Shape.NoFrame)
        label.setFrameShadow(QFrame.Shadow.Plain)
        label.setMargin(0)
        label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        label.setMinimumWidth(self._min_content_width)
        return label

    def sizeHint(self) -> QSize:
        """Ensure size hints include child layout content."""
        layout = self._root_layout
        if not layout:
            return super().sizeHint()
        layout_hint = layout.sizeHint()
        if not layout_hint.isValid():
            return super().sizeHint()
        base_hint = super().sizeHint()
        return QSize(
            max(layout_hint.width(), base_hint.width()),
            max(layout_hint.height(), base_hint.height()),
        )

    def minimumSizeHint(self) -> QSize:
        layout = self._root_layout
        if not layout:
            return super().minimumSizeHint()
        layout_min = layout.minimumSize()
        if not layout_min.isValid():
            return super().minimumSizeHint()
        base_min = super().minimumSizeHint()
        return QSize(
            max(layout_min.width(), base_min.width()),
            max(layout_min.height(), base_min.height()),
        )

    def _create_separator(self, *, top_padding: int = 8, bottom_padding: int = 8) -> QWidget:
        container = QWidget(self)
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, top_padding, 0, bottom_padding)
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
        
        # Start periodic updates
        self._fetch_weather()
        interval_ms = 30 * 60 * 1000
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

        cached: Dict[str, Any] = {
            "temperature": temp,
            "condition": condition,
            "location": loc,
        }
        humidity = payload.get("humidity")
        if humidity is not None:
            cached["humidity"] = humidity
        precipitation = payload.get("precipitation_probability")
        if precipitation is not None:
            cached["precipitation_probability"] = precipitation
        wind = payload.get("windspeed")
        if wind is not None:
            cached["windspeed"] = wind
        forecast = payload.get("forecast")
        if forecast:
            cached["forecast"] = forecast
        where = payload.get("detail_source", "unknown")
        cached["_detail_source"] = where

        self._cached_data = cached
        self._cache_time = dt
        if is_perf_metrics_enabled():
            logger.debug(
                "[WEATHER][CACHE] Loaded persisted cache with details: humidity=%s wind=%s rain=%s forecast=%s",
                humidity,
                wind,
                precipitation,
                bool(forecast),
            )

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

            precipitation, humidity, windspeed = self._extract_detail_values(data)
            forecast = data.get("forecast") or self._forecast_data

            payload: Dict[str, Any] = {
                "location": location,
                "temperature": float(temp),
                "condition": str(condition),
                "timestamp": datetime.now().isoformat(),
            }
            if humidity is not None:
                payload["humidity"] = float(humidity)
            if precipitation is not None:
                payload["precipitation_probability"] = float(precipitation)
            if windspeed is not None:
                payload["windspeed"] = float(windspeed)
            if forecast:
                payload["forecast"] = str(forecast)

            if is_perf_metrics_enabled():
                logger.debug(
                    "[WEATHER][CACHE] Persisting cache w/ detail metrics (rain=%s humidity=%s wind=%s forecast=%s)",
                    precipitation,
                    humidity,
                    windspeed,
                    bool(forecast),
                )

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
            self._show_status_message("Weather: No Data")
            return
        
        try:
            temp = data.get("temperature")
            condition = data.get("condition")
            location = data.get("location")

            if temp is None and isinstance(data.get("main"), dict):
                temp = data["main"].get("temp")
            if condition is None and isinstance(data.get("weather"), list) and data["weather"]:
                weather_entry = data["weather"][0]
                condition = weather_entry.get("main") or weather_entry.get("description")
            if not location:
                location = data.get("name") or self._location

            temp = 0.0 if temp is None else float(temp)
            condition = "Unknown" if condition is None else str(condition)
            location = location or self._location

            forecast = data.get("forecast")
            if forecast:
                self._forecast_data = forecast

            location_display = html.escape(str(location).title())
            condition_display = html.escape(str(condition).title())

            city_pt = max(6, self._font_size + 2)
            primary_pt = max(6, self._font_size - 2)
            secondary_pt = max(6, self._font_size - 12)

            color_rgba = (
                f"rgba({self._text_color.red()}, {self._text_color.green()}, "
                f"{self._text_color.blue()}, {self._text_color.alpha()})"
            )

            city_html = (
                f"<div style='font-size:{city_pt}pt; font-weight:700; color:{color_rgba};'>"
                f"{location_display}</div>"
            )
            temp_html = (
                f"<span style='font-weight:700; color:{color_rgba};'>{temp:.0f}°C</span>"
            )
            condition_html = (
                f"<span style='font-weight:600; color:{color_rgba};'>{condition_display}</span>"
            )
            details_html = (
                f"<div style='font-size:{primary_pt}pt; color:{color_rgba};'>"
                f"{temp_html} - {condition_html}</div>"
            )

            if self._city_label:
                self._city_label.setTextFormat(Qt.TextFormat.RichText)
                self._city_label.setText(city_html)
            if self._conditions_label:
                self._conditions_label.setTextFormat(Qt.TextFormat.RichText)
                self._conditions_label.setText(details_html)

            self._details_font = QFont(self._font_family, secondary_pt, QFont.Weight.Normal)
            self._details_font.setItalic(False)
            self._details_font_metrics = QFontMetrics(self._details_font)
            metrics_height = self._details_font_metrics.height()
            self._detail_icon_size = max(
                _DETAIL_ICON_MIN_PX, int(metrics_height * 1.15) if metrics_height else _DETAIL_ICON_MIN_PX
            )
            self._update_detail_metrics(data)
            detail_ready = len(self._detail_metrics) >= 2
            if not detail_ready and self._show_details_row and self._enabled:
                self._fetch_weather()

            show_details = bool(self._show_details_row and detail_ready)
            if self._details_separator:
                self._details_separator.setVisible(show_details)
            if self._detail_row_container:
                self._detail_row_container.setVisible(show_details)
            if self._detail_row_widget:
                detail_metrics = self._detail_metrics if show_details else []
                self._detail_row_widget.update_metrics(
                    detail_metrics,
                    self._details_font,
                    self._text_color,
                    self._detail_icon_size,
                )
                self._detail_row_widget.setVisible(show_details)

            show_forecast_line = bool(self._show_forecast and self._forecast_data)
            if self._forecast_separator:
                self._forecast_separator.setVisible(show_forecast_line)
            if self._forecast_container:
                self._forecast_container.setVisible(show_forecast_line)
            if self._forecast_label:
                if show_forecast_line:
                    forecast_html = (
                        f"<div style='font-size:{secondary_pt}pt; font-style:italic; "
                        f"font-weight:400; color:{color_rgba};'>"
                        f"{html.escape(self._forecast_data)}</div>"
                    )
                    self._forecast_label.setTextFormat(Qt.TextFormat.RichText)
                    self._forecast_label.setText(forecast_html)
                self._forecast_label.setVisible(show_forecast_line)

            self.clear()
            self.adjustSize()

            self._update_detail_tooltip(f"{location_display}: {temp:.0f}°C - {condition_display}")

            if self.parent():
                self._update_position()

        except Exception as e:
            logger.exception(f"Error updating weather display: {e}")
            self._show_status_message("Weather: Error")

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

    def set_show_details_row(self, show: bool) -> None:
        """Enable/disable mini detail row with icons."""
        if self._show_details_row == show:
            return
        self._show_details_row = show
        if self._cached_data:
            self._update_display(self._cached_data)
        else:
            self.update()

    def _show_status_message(self, message: str) -> None:
        if self._city_label:
            self._city_label.setText(message)
            self._city_label.setTextFormat(Qt.TextFormat.PlainText)
        if self._conditions_label:
            self._conditions_label.clear()
        if self._forecast_label:
            self._forecast_label.clear()
            self._forecast_label.setVisible(False)
        if self._detail_row_widget:
            self._detail_row_widget.update_metrics([], QFont(self._font_family, 10), self._text_color, self._detail_icon_size)
            self._detail_row_widget.setVisible(False)
        if self._detail_row_container:
            self._detail_row_container.setVisible(False)
        if self._details_separator:
            self._details_separator.setVisible(False)
        if self._forecast_separator:
            self._forecast_separator.setVisible(False)
        if self._forecast_container:
            self._forecast_container.setVisible(False)
        self.clear()
        self.adjustSize()
    
    def set_text_color(self, color: QColor) -> None:
        """Override to refresh cached monochrome icons when color changes."""
        previous = QColor(self._text_color)
        super().set_text_color(color)
        if previous == self._text_color:
            return
        self._clear_detail_caches()
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
