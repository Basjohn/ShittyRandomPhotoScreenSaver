"""Weather widget helper components.

Extracted from weather_widget.py to keep the main widget under the 1500-line
monolith threshold. Contains:
- WeatherConditionIcon — main weather condition PNG renderer
- WeatherDetailIcon — small metric icon (rain/humidity/wind)
- WeatherDetailRow — compact row of detail metrics
- WeatherPosition — enum for widget screen position
- WeatherFetcher — background weather data fetcher
"""
from __future__ import annotations

from typing import Optional, Dict, Tuple, List
from pathlib import Path
from enum import Enum

from PySide6.QtWidgets import QWidget, QSizePolicy, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, QObject, QSize
from PySide6.QtGui import QFont, QPainter, QColor, QFontMetrics, QPixmap

from core.logging.logger import get_logger
from weather.open_meteo_provider import OpenMeteoProvider

logger = get_logger(__name__)

_DETAIL_ICON_MIN_PX = 30


class WeatherConditionIcon(QWidget):
    """Widget that renders static PNG weather icons with proper DPR scaling.
    
    Feature #6: Supports optional monochrome (grayscale) rendering.
    Conversion happens once on load (cached), not every paint - zero perf impact.
    """

    def __init__(self, size_px: int = 96, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._icon_path: Optional[Path] = None
        self._size_px = max(48, int(size_px))
        self._padding = 4
        self._monochrome = False  # Feature #6: Monochrome mode
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

    def set_monochrome(self, enabled: bool) -> None:
        """Enable/disable monochrome (grayscale) rendering.
        
        Feature #6: Conversion happens once on load, not every paint.
        """
        if self._monochrome == enabled:
            return
        self._monochrome = enabled
        self._pixmap = None  # Force reload with new mode
        if self._icon_path:
            self._load_pixmap()
        self.update()

    def is_monochrome(self) -> bool:
        """Return current monochrome state."""
        return self._monochrome

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
        """Load pixmap at full native resolution, optionally converting to grayscale.
        
        Feature #6: Grayscale conversion happens here (once), not in paintEvent.
        """
        if self._icon_path is None:
            self._pixmap = None
            return

        # Load pixmap at full native resolution
        source = QPixmap(str(self._icon_path))
        if source.isNull():
            logger.warning(f"[WEATHER] Failed to load icon: {self._icon_path}")
            self._pixmap = None
            return

        # Feature #6: Convert to grayscale if monochrome mode enabled
        if self._monochrome:
            source = self._convert_to_grayscale(source)

        self._pixmap = source

    def _convert_to_grayscale(self, pixmap: QPixmap) -> QPixmap:
        """Convert pixmap to grayscale while preserving alpha channel.
        
        Feature #6: Performance-safe conversion - called once per icon load,
        cached result used for all subsequent paints.
        """
        from PySide6.QtGui import QImage
        
        image = pixmap.toImage()
        if image.isNull():
            return pixmap
        
        # Convert to ARGB32 format if needed to ensure we can manipulate pixels
        if image.format() != QImage.Format.Format_ARGB32:
            image = image.convertToFormat(QImage.Format.Format_ARGB32)
        
        # Convert each pixel to grayscale while preserving alpha
        width = image.width()
        height = image.height()
        for y in range(height):
            for x in range(width):
                pixel = image.pixel(x, y)
                # Extract ARGB components
                alpha = (pixel >> 24) & 0xFF
                red = (pixel >> 16) & 0xFF
                green = (pixel >> 8) & 0xFF
                blue = pixel & 0xFF
                # Calculate grayscale using luminance formula
                gray = int(0.299 * red + 0.587 * green + 0.114 * blue)
                # Reconstruct pixel with original alpha
                new_pixel = (alpha << 24) | (gray << 16) | (gray << 8) | gray
                image.setPixel(x, y, new_pixel)
        
        return QPixmap.fromImage(image)

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
        # Monochrome conversion already applied in _load_pixmap (zero overhead here)
        target = self.rect().adjusted(self._padding, self._padding, -self._padding, -self._padding)
        painter.drawPixmap(target, self._pixmap)
        painter.end()


class WeatherDetailIcon(QWidget):
    """Custom widget to paint detail metric icons (rain/humidity/wind).
    
    Issue #2 Fix: Icons are pre-scaled when set via set_pixmap(), so paintEvent
    draws at 1:1 scale without additional scaling to avoid quality degradation.
    """

    def __init__(self, size_px: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._target_size = max(_DETAIL_ICON_MIN_PX, size_px)
        self._box = QSize(self._target_size + 6, self._target_size + 6)
        self.setFixedSize(self._box)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._vertical_inset = 3
        self._baseline_offset = 0

    def set_pixmap(self, pixmap: Optional[QPixmap]) -> None:
        """Set pixmap - expects pre-scaled pixmap at target size."""
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
        """Draw pre-scaled pixmap at 1:1 scale (no additional scaling)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if self._pixmap is None or self._pixmap.isNull():
            painter.end()
            return
        
        # Calculate centered position within the widget box
        # Pixmap is already pre-scaled, so draw at 1:1 (no scaling here)
        pm_w = self._pixmap.width()
        pm_h = self._pixmap.height()
        x = (self._box.width() - pm_w) // 2
        y = self._vertical_inset + (self._box.height() - self._vertical_inset * 2 - pm_h) // 2
        
        painter.drawPixmap(x, y, self._pixmap)
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
