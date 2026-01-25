"""
Weather widget for screensaver overlay.

Displays current weather information using Open-Meteo API (no API key needed).
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List, Callable
import html
import math
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
    QGraphicsColorizeEffect,
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
from core.performance import widget_paint_sample, widget_timer_sample

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
_ICON_ALIGNMENT_OPTIONS = {"LEFT", "RIGHT", "NONE"}
_DEFAULT_ICON_ALIGNMENT = "NONE"
_DEFAULT_DESATURATE_ICON = False
_ANIMATED_ICON_SCALE_FACTOR = 1.44

# Weather code groupings from Open-Meteo to our SVG assets
_WEATHER_CODE_ICON_MAP: List[Tuple[set[int], str]] = [
    (set([0]), "clear-day.svg"),
    (set([1, 2]), "partly-cloudy-day.svg"),
    (set([3]), "overcast-day.svg"),
    (set([45, 48]), "fog-day.svg"),
    (set([51, 53, 55, 56, 57]), "drizzle.svg"),
    (set([61, 63, 65, 80, 81, 82]), "rain.svg"),
    (set([66, 67]), "hail.svg"),
    (set([71, 73, 75, 77, 85, 86]), "snow.svg"),
    (set([95, 96, 99]), "thunderstorms-day.svg"),
]

_CONDITION_KEYWORDS_ICON_MAP: List[Tuple[str, str]] = [
    ("clear", "clear-day.svg"),
    ("partly", "partly-cloudy-day.svg"),
    ("overcast", "overcast-day.svg"),
    ("cloud", "partly-cloudy-day.svg"),
    ("fog", "fog-day.svg"),
    ("haze", "haze-day.svg"),
    ("smoke", "smoke.svg"),
    ("drizzle", "drizzle.svg"),
    ("rain", "rain.svg"),
    ("snow", "snow.svg"),
    ("sleet", "partly-cloudy-day-sleet.svg"),
    ("thunder", "thunderstorms-day-rain.svg"),
]


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


@dataclass
class _DetailSegment:
    widget: QWidget
    icon: WeatherDetailIcon
    text: QLabel


class WeatherConditionIcon(QWidget):
    """Widget that renders animated SVG weather icons with Qt's SVG engine."""

    icon_source_changed = Signal(object, object)  # (renderer, icon_path)

    def __init__(self, size_px: int = 96, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._renderer: Optional[QSvgRenderer] = None
        self._icon_path: Optional[Path] = None
        self._size_px = max(48, int(size_px))
        self._frames_per_second = 12
        self._padding = 4
        self._animation_enabled = True
        self._monochrome_base: Optional[QColor] = None
        self._desaturation_enabled = False
        self._static_pixmap: Optional[QPixmap] = None
        self._static_pixmap_dpr: Optional[float] = None
        self._geom_log_signatures: Dict[str, str] = {}
        self._set_fixed_box()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _set_fixed_box(self) -> None:
        box = QSize(self._size_px, self._size_px)
        self.setMinimumSize(box)
        self.setMaximumSize(box)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not self._animation_enabled:
            self._render_static_frame()

    def set_icon_size(self, size_px: int) -> None:
        size_px = max(32, int(size_px))
        if size_px == self._size_px:
            return
        self._size_px = size_px
        self._set_fixed_box()
        self._static_pixmap = None
        self._static_pixmap_dpr = None
        self.update()

    def clear_icon(self) -> None:
        if self._renderer:
            try:
                self._renderer.repaintNeeded.disconnect(self.update)
            except Exception:
                pass
        self._renderer = None
        self._icon_path = None
        self._static_pixmap = None
        self._static_pixmap_dpr = None
        self.update()
        try:
            self.icon_source_changed.emit(None, None)
        except Exception:
            pass

    def set_icon_path(self, icon_path: Optional[Path]) -> None:
        if icon_path is None or not icon_path.exists():
            self.clear_icon()
            return
        if self._icon_path == icon_path and self._renderer is not None:
            return

        renderer = QSvgRenderer(str(icon_path))
        if not renderer.isValid():
            self.clear_icon()
            return

        if self._renderer:
            try:
                self._renderer.repaintNeeded.disconnect(self.update)
            except Exception:
                pass

        self._renderer = renderer
        self._icon_path = icon_path
        self._apply_animation_state()
        self.update()
        try:
            self.icon_source_changed.emit(renderer, icon_path)
        except Exception:
            pass

    def set_renderer_reference(
        self,
        renderer: Optional[QSvgRenderer],
        icon_path: Optional[Path],
    ) -> None:
        """Adopt an external renderer reference (shared animation driver)."""
        self._renderer = renderer
        self._icon_path = icon_path
        self._static_pixmap = None
        self._static_pixmap_dpr = None
        self.update()

    def has_icon(self) -> bool:
        return self._renderer is not None and self._icon_path is not None

    def set_animation_enabled(self, enabled: bool) -> None:
        if self._animation_enabled == enabled:
            return
        self._animation_enabled = enabled
        self._apply_animation_state()

    def _apply_animation_state(self) -> None:
        renderer = self._renderer
        if renderer is None:
            return

        try:
            renderer.repaintNeeded.disconnect(self.update)
        except Exception:
            pass

        renderer.setAnimationEnabled(self._animation_enabled)
        if self._animation_enabled:
            try:
                renderer.repaintNeeded.disconnect(self.update)
            except Exception:
                pass
            renderer.setFramesPerSecond(self._frames_per_second)
            renderer.repaintNeeded.connect(self.update)
            self._static_pixmap = None
        else:
            try:
                renderer.repaintNeeded.disconnect(self.update)
            except Exception:
                pass
            try:
                renderer.setCurrentFrame(0)
            except Exception:
                pass
            self._render_static_frame()
        self.update()

    def set_desaturation_enabled(self, enabled: bool, *, base_color: Optional[QColor] = None) -> None:
        enabled = bool(enabled)
        if enabled == self._desaturation_enabled and base_color is None:
            return
        self._desaturation_enabled = enabled
        if base_color is not None:
            self._monochrome_base = QColor(base_color)
        elif self._monochrome_base is None:
            self._monochrome_base = QColor(220, 220, 220)
        if not self._animation_enabled:
            self._render_static_frame()
        else:
            self.update()

    def _render_static_frame(self) -> None:
        renderer = self._renderer
        if renderer is None or not renderer.isValid():
            self._static_pixmap = None
            self._static_pixmap_dpr = None
            return

        widget_width = max(1, self.width() or self._size_px)
        widget_height = max(1, self.height() or self._size_px)
        target_width = max(1, widget_width - 2 * self._padding)
        target_height = max(1, widget_height - 2 * self._padding)
        dpr = float(max(1.0, self.devicePixelRatioF()))
        render_width = max(1, int(round(target_width * dpr)))
        render_height = max(1, int(round(target_height * dpr)))

        pixmap = QPixmap(render_width, render_height)
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter, QRectF(0, 0, target_width, target_height))
        painter.end()
        image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
        if self._desaturation_enabled:
            image = self._apply_monochrome(image)
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(dpr)
        self._static_pixmap = pixmap
        self._static_pixmap_dpr = dpr
        self._log_geometry(
            mode="static.cache",
            target_rect=QRectF(
                self._padding,
                self._padding,
                widget_width - 2 * self._padding,
                widget_height - 2 * self._padding,
            ),
            pixmap=self._static_pixmap,
        )
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer = self._renderer
        if not renderer or not renderer.isValid():
            painter.end()
            return
        widget_rect = self.rect()
        target = QRectF(
            self._padding,
            self._padding,
            widget_rect.width() - 2 * self._padding,
            widget_rect.height() - 2 * self._padding,
        )
        if not self._animation_enabled:
            dpr = float(max(1.0, self.devicePixelRatioF()))
            if (
                self._static_pixmap is None
                or self._static_pixmap_dpr is None
                or not math.isclose(self._static_pixmap_dpr, dpr, rel_tol=1e-3)
            ):
                self._render_static_frame()
            if self._static_pixmap is not None:
                painter.drawPixmap(target, self._static_pixmap, self._static_pixmap.rect())
                self._log_geometry(mode="static.paint", target_rect=target, pixmap=self._static_pixmap)
            painter.end()
            return
        if self._desaturation_enabled:
            image = QImage(int(target.width()), int(target.height()), QImage.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            temp = QPainter(image)
            temp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            renderer.render(temp, QRectF(0, 0, target.width(), target.height()))
            temp.end()
            image = self._apply_monochrome(image)
            painter.drawImage(target, image)
        else:
            renderer.render(painter, target)
        self._log_geometry(mode="animated.paint", target_rect=target, pixmap=None)
        painter.end()

    def _apply_monochrome(self, image: QImage) -> QImage:
        palette = self._monochrome_palette()
        if not palette:
            return image
        band_count = max(1, len(palette) - 1)
        for y in range(image.height()):
            for x in range(image.width()):
                color = QColor(image.pixel(x, y))
                alpha = color.alpha()
                if alpha == 0:
                    continue
                gray = int(round(0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()))
                factor = gray / 255.0
                scaled = factor * band_count
                index = min(len(palette) - 2, int(math.floor(scaled)))
                t = max(0.0, min(1.0, scaled - index))
                base_color = palette[index]
                next_color = palette[index + 1]
                blended = self._lerp_color(base_color, next_color, t)
                blended.setAlpha(alpha)
                image.setPixelColor(x, y, blended)
        return image

    def _monochrome_palette(self) -> List[QColor]:
        base = self._monochrome_base or QColor(220, 220, 220)
        highlight = QColor(base)
        highlight = highlight.lighter(120)
        mid = QColor(base)
        mid = mid.darker(140)  # at least 30% darker than base
        shadow = QColor(base)
        shadow = shadow.darker(200)
        return [shadow, mid, highlight]

    @staticmethod
    def _lerp_color(a: QColor, b: QColor, t: float) -> QColor:
        t = max(0.0, min(1.0, t))
        def _lerp(ca: int, cb: int) -> int:
            return int(round(ca + (cb - ca) * t))
        return QColor(
            _lerp(a.red(), b.red()),
            _lerp(a.green(), b.green()),
            _lerp(a.blue(), b.blue()),
        )

    def _log_geometry(self, *, mode: str, target_rect: QRectF, pixmap: Optional[QPixmap]) -> None:
        if not is_perf_metrics_enabled():
            return
        widget_w = self.width() or self._size_px
        widget_h = self.height() or self._size_px
        pixmap_size: Optional[Tuple[int, int]] = None
        if pixmap is not None and not pixmap.isNull():
            ratio = float(max(1.0, pixmap.devicePixelRatio()))
            logical_w = int(round(pixmap.width() / ratio))
            logical_h = int(round(pixmap.height() / ratio))
            pixmap_size = (logical_w, logical_h)
        dpr = float(max(1.0, self.devicePixelRatioF()))
        signature = (
            f"{mode}|{widget_w}x{widget_h}|"
            f"{target_rect.x():.2f},{target_rect.y():.2f},"
            f"{target_rect.width():.2f},{target_rect.height():.2f}|"
            f"{pixmap_size}|{dpr:.3f}|pad={self._padding}|desat={self._desaturation_enabled}"
        )
        if self._geom_log_signatures.get(mode) == signature:
            return
        self._geom_log_signatures[mode] = signature
        logger.info(
            "[WEATHER][ICON][GEOM] mode=%s widget=(%s, %s) target=(%.2f, %.2f, %.2f, %.2f) "
            "pixmap=%s dpr=%.3f padding=%s anim=%s desat=%s",
            mode,
            widget_w,
            widget_h,
            target_rect.x(),
            target_rect.y(),
            target_rect.width(),
            target_rect.height(),
            pixmap_size,
            dpr,
            self._padding,
            self._animation_enabled,
            self._desaturation_enabled,
        )


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
        self._segment_pool: Dict[str, _DetailSegment] = {}
        self._segment_values: Dict[str, str] = {}
        self._segment_icon_cache: Dict[str, Tuple[int, Optional[QPixmap]]] = {}
        self._segment_icon_sizes: Dict[str, int] = {}
        self._segment_color_rgba: Dict[str, str] = {}
        self._segment_font_signature: Dict[str, Tuple[str, int, int, bool]] = {}
        self._segment_heights: Dict[str, int] = {}
        self._segment_debug_logged: set[str] = set()
        self._current_color_rgba: str = "rgba(255,255,255,255)"
        self._font_signature: Tuple[str, int, int, bool] = ("", 0, 0, False)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

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
    ) -> None:
        """Refresh metric segments."""
        self._metrics = list(metrics)
        self._font = QFont(font)
        self._font_metrics = QFontMetrics(self._font)
        self._text_color = QColor(color)
        normalized_icon_size = max(18, int(icon_size))
        if normalized_icon_size != self._icon_size:
            self._icon_size = normalized_icon_size
            self._segment_icon_cache.clear()
            self._segment_debug_logged.clear()
            self._segment_icon_sizes.clear()
            self._segment_heights.clear()
        self._rebuild_segments()
        self.setVisible(bool(metrics))

    def _rebuild_segments(self) -> None:
        has_metrics = bool(self._metrics)
        self._segments_layout.setContentsMargins(0, 6 if has_metrics else 0, 0, 4 if has_metrics else 0)
        self._segments_layout.setSpacing(max(12, self._icon_size // 2 + 4) if has_metrics else 0)
        self._segment_widgets.clear()

        active_keys: List[str] = []
        for key, value in self._metrics:
            active_keys.append(key)
            segment = self._segment_pool.get(key)
            if segment is None:
                segment = self._create_segment()
                self._segment_pool[key] = segment
                insert_pos = max(0, self._segments_layout.count() - 1)
                self._segments_layout.insertWidget(insert_pos, segment.widget)
            self._configure_segment(segment, key, value)
            segment.widget.setVisible(True)
            self._segment_widgets.append(segment.widget)

        for key, segment in self._segment_pool.items():
            if key not in active_keys:
                segment.widget.setVisible(False)

    def _create_segment(self) -> _DetailSegment:
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
        text_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)

        layout.addWidget(icon_label)
        layout.addWidget(text_label)

        return _DetailSegment(widget=segment, icon=icon_label, text=text_label)

    def _configure_segment(self, segment: _DetailSegment, key: str, value: str) -> None:
        font_sig = (
            self._font.family(),
            self._font.pointSize(),
            self._font.weight(),
            self._font.italic(),
        )
        self._font_signature = font_sig
        self._current_color_rgba = (
            f"rgba({self._text_color.red()}, {self._text_color.green()}, "
            f"{self._text_color.blue()}, {self._text_color.alpha()})"
        )

        icon_edge = max(10, self._icon_size)
        cache_entry = self._segment_icon_cache.get(key)
        pixmap: Optional[QPixmap]
        if cache_entry and cache_entry[0] == self._icon_size:
            pixmap = cache_entry[1]
        else:
            pixmap = self._icon_fetcher(key, icon_edge)
            self._segment_icon_cache[key] = (self._icon_size, pixmap)

        original_pixmap = pixmap
        segment.icon.set_pixmap(pixmap if pixmap and not pixmap.isNull() else None)
        base_drop = min(
            segment.icon.sizeHint().height() // 3, int(self._icon_size * 0.18) + 2
        )
        soft_drop = max(0, base_drop - 1)
        segment.icon.set_baseline_offset(soft_drop)
        segment.icon.set_debug_background(False)

        log_detail_geometry = False
        if is_perf_metrics_enabled():
            logged_key = f"{key}:{self._icon_size}"
            if logged_key not in self._segment_debug_logged:
                log_detail_geometry = True
                self._segment_debug_logged.add(logged_key)

        if log_detail_geometry:
            label_pixmap = segment.icon.pixmap()
            widget_size = (segment.icon.width(), segment.icon.height())
            state = "none"
            incoming_size: Optional[Tuple[int, int]] = None
            label_size: Optional[Tuple[int, int]] = None
            if original_pixmap is not None:
                state = "null" if original_pixmap.isNull() else "ready"
                incoming_size = (original_pixmap.width(), original_pixmap.height())
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
            size_hint = segment.icon.sizeHint()
            rect = segment.icon.rect()
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
                segment.widget.sizeHint().width(),
                segment.widget.sizeHint().height(),
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
                        (original_pixmap.width(), original_pixmap.height()),
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

        if self._segment_font_signature.get(key) != font_sig:
            segment.text.setFont(self._font)
            self._segment_font_signature[key] = font_sig
        if self._segment_values.get(key) != value:
            segment.text.setText(value)
            self._segment_values[key] = value
        if self._segment_color_rgba.get(key) != self._current_color_rgba:
            segment.text.setStyleSheet(self._current_color_rgba_style())
            self._segment_color_rgba[key] = self._current_color_rgba
        line_height = self._font_metrics.height()
        height = max(self._icon_size + 10, line_height + 6)
        if self._segment_heights.get(key) != height:
            segment.widget.setFixedHeight(height)
            self._segment_heights[key] = height

    def _current_color_rgba_style(self) -> str:
        return (
            f"color: rgba({self._text_color.red()}, {self._text_color.green()}, "
            f"{self._text_color.blue()}, {self._text_color.alpha()});"
        )

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
                 position: WeatherPosition = WeatherPosition.BOTTOM_LEFT,
                 enable_tooltips: bool = False):
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
        self._min_content_width = 420

        # Padding: slightly more at top/bottom, extra slack on the right so the
        # drop shadow doesn't make TOP_RIGHT appear flush with the screen edge.
        self._padding_top = 4
        self._padding_bottom = 4
        self._padding_left = 8
        self._padding_right = 12
        
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
        self._last_detail_values: Dict[str, Optional[float]] = {}
        self._detail_metrics_signature: Optional[Tuple[Tuple[str, str], ...]] = None
        self._detail_metrics_last_refresh: Optional[datetime] = None
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
        self._primary_layout: Optional[QHBoxLayout] = None
        self._text_column: Optional[QWidget] = None
        self._text_layout: Optional[QVBoxLayout] = None
        self._condition_icon_widget: Optional[WeatherConditionIcon] = None
        self._animated_icon_alignment: str = _DEFAULT_ICON_ALIGNMENT
        self._animated_icon_enabled: bool = True
        self._desaturate_condition_icon: bool = _DEFAULT_DESATURATE_ICON
        self._icon_desaturate_effect: Optional[QGraphicsColorizeEffect] = None
        self._shared_animation_driver_enabled: bool = True
        self._shared_animation_sink_mode: bool = False
        self._last_icon_context: Dict[str, Any] = {}
        self._last_icon_refresh: Optional[datetime] = None
        self._primary_spacer: Optional[QWidget] = None
        self._root_layout: Optional[QVBoxLayout] = None
        self._status_label: Optional[QLabel] = None
        self._current_summary: str = ""
        self._tooltips_enabled: bool = enable_tooltips
        self._display_refresh_interval = timedelta(minutes=30)
        self._last_display_refresh: Optional[datetime] = None
        self._display_refresh_deadline: Optional[datetime] = None
        self._force_next_display_refresh: bool = True
        self._last_display_signature: Optional[Tuple[Any, ...]] = None
        self._last_payload_signature: Optional[Tuple[Any, ...]] = None
        self._pending_payload_signature: Optional[Tuple[Any, ...]] = None
        self._pending_payload_data: Optional[Dict[str, Any]] = None
        self._pending_refresh_deadline_token: Optional[object] = None
        self._last_city_html: Optional[str] = None
        self._last_details_html: Optional[str] = None
        self._detail_font_cache_key: Optional[Tuple[str, int]] = None
        self._detail_row_last_signature: Optional[Tuple[Tuple[str, str], ...]] = None
        self._forecast_label_cache: Optional[str] = None
        self._tooltip_cache: Optional[str] = None
        self._detail_placeholder_label: Optional[QLabel] = None
        self._detail_placeholder_label_cache: Optional[str] = None
        
        # Setup UI
        self._setup_ui()
        
        logger.debug(f"WeatherWidget created (location={location}, position={position.value})")
    
    def paintEvent(self, event) -> None:  # type: ignore[override]
        """Wrap base paint so PERF metrics capture weather card costs."""
        with widget_paint_sample(self, "weather.paint"):
            super().paintEvent(event)
    
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
    
    def _update_detail_metrics(self, data: Dict[str, Any], *, force: bool = False) -> None:
        """Compute available detail metrics from provider payload."""
        metrics: List[Tuple[str, str]] = []
        latest_values: Dict[str, Optional[float]] = {}

        precipitation, humidity, windspeed = self._extract_detail_values(data)

        def _append_metric(key: str, value: Optional[float], fmt: Callable[[float], str]) -> None:
            if value is None:
                return
            metrics.append((key, fmt(value)))
            latest_values[key] = value

        _append_metric("rain", precipitation, lambda val: f"{val:.0f}%")
        _append_metric("humidity", humidity, lambda val: f"{val:.0f}%")
        _append_metric("wind", windspeed, lambda val: f"{val:.1f} km/h")

        if not metrics and self._show_details_row:
            # Provider returned no detail metrics; fall back to cached values or zeros
            fallback = dict(self._last_detail_values) if self._last_detail_values else {}
            if "rain" not in fallback:
                fallback["rain"] = 0.0
            if "humidity" not in fallback:
                fallback["humidity"] = 0.0
            if "wind" not in fallback:
                fallback["wind"] = 0.0

            metrics = [
                ("rain", f"{(fallback.get('rain') or 0.0):.0f}%"),
                ("humidity", f"{(fallback.get('humidity') or 0.0):.0f}%"),
                ("wind", f"{(fallback.get('wind') or 0.0):.1f} km/h"),
            ]
            latest_values = {
                "rain": fallback.get("rain", 0.0),
                "humidity": fallback.get("humidity", 0.0),
                "wind": fallback.get("wind", 0.0),
            }

        metrics_signature: Tuple[Tuple[str, str], ...] = tuple(metrics)
        now = datetime.now()
        should_refresh = force or self._detail_metrics_signature is None
        if not should_refresh:
            if metrics_signature != self._detail_metrics_signature:
                should_refresh = True
            elif self._detail_metrics_last_refresh is None:
                should_refresh = True
            else:
                elapsed = (now - self._detail_metrics_last_refresh).total_seconds()
                should_refresh = elapsed >= 30 * 60

        if not should_refresh:
            if is_perf_metrics_enabled():
                logger.info(
                    "[WEATHER][DETAIL] Skipping metrics refresh (unchanged, last=%ss)",
                    None
                    if self._detail_metrics_last_refresh is None
                    else round((now - self._detail_metrics_last_refresh).total_seconds(), 1),
                )
            return

        self._detail_metrics_signature = metrics_signature
        self._detail_metrics_last_refresh = now
        if latest_values:
            self._last_detail_values = {
                "rain": latest_values.get("rain", precipitation),
                "humidity": latest_values.get("humidity", humidity),
                "wind": latest_values.get("wind", windspeed),
            }
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
    
    def _build_tooltip_text(self, base: str) -> str:
        """Return composed tooltip text for current detail metrics."""
        tooltip_lines = [base]
        if self._detail_metrics:
            detail_text = ", ".join(
                f"{self._metric_label(key)} {value}"
                for key, value in self._detail_metrics
            )
            tooltip_lines.append(detail_text)
        if self._show_forecast and self._forecast_data:
            tooltip_lines.append(f"Forecast: {self._forecast_data}")
        return "\n".join(tooltip_lines)

    def _update_detail_tooltip(self, base: str) -> None:
        """Attach detail values to the widget tooltip."""
        self.setToolTip(self._build_tooltip_text(base))

    def _request_display_refresh(self) -> None:
        """Force the next `_update_display` call to bypass cadence throttling."""
        self._force_next_display_refresh = True

    def _schedule_pending_refresh_consumption(self) -> None:
        """Schedule a deadline-bound flush of any pending payload."""
        deadline = self._display_refresh_deadline
        if deadline is None:
            return

        delay_ms = int(max(0, (deadline - datetime.now()).total_seconds() * 1000))
        runner: Optional[Callable[..., None]] = None
        if self._thread_manager is not None:
            runner = self._thread_manager.single_shot  # type: ignore[attr-defined]
        else:
            runner = ThreadManager.single_shot

        token = object()
        self._pending_refresh_deadline_token = token

        try:
            runner(delay_ms, self._consume_pending_payload_at_deadline, token)
        except Exception:
            self._pending_refresh_deadline_token = None
            logger.debug("[WEATHER] Failed to schedule pending payload flush", exc_info=True)

    def _consume_pending_payload_at_deadline(self, token: object) -> None:
        """Consume any queued payload once the cadence deadline elapses."""
        if token is not self._pending_refresh_deadline_token:
            return
        self._pending_refresh_deadline_token = None

        if not Shiboken.isValid(self):
            return

        pending_payload = self._pending_payload_data
        if not pending_payload:
            return

        deadline = self._display_refresh_deadline
        if deadline is not None and datetime.now() < deadline:
            # Deadline shifted (manual refresh); reschedule with new token.
            self._schedule_pending_refresh_consumption()
            return

        self._force_next_display_refresh = True
        self._pending_payload_data = None
        try:
            self._update_display(pending_payload)
        except Exception:
            logger.exception("[WEATHER] Pending payload flush failed")

    def _build_payload_signature(self, data: Dict[str, Any]) -> Tuple[Any, ...]:
        """Return a coarse signature describing the UI-relevant payload fields."""
        weather_entry: Optional[Dict[str, Any]] = None
        if isinstance(data.get("weather"), list) and data["weather"]:
            weather_entry = data["weather"][0] or {}

        temp = data.get("temperature")
        if temp is None and isinstance(data.get("main"), dict):
            temp = data["main"].get("temp")
        if temp is None:
            temp = 0.0

        condition = data.get("condition")
        if condition is None and weather_entry:
            condition = weather_entry.get("main") or weather_entry.get("description") or "Unknown"
        condition_raw = str(condition or "Unknown")
        condition_key = condition_raw.split("·", 1)[0].split("#", 1)[0].strip().lower()

        location = data.get("location") or data.get("name") or self._location
        location_key = str(location).strip().lower()

        weather_code = data.get("weather_code")
        if weather_code is None and weather_entry:
            weather_code = weather_entry.get("id") or weather_entry.get("code")

        is_day_flag = data.get("is_day")
        if is_day_flag is None and weather_entry:
            is_day_flag = weather_entry.get("is_day")
        if is_day_flag is None:
            is_day_flag = 1
        try:
            is_day_norm = bool(int(is_day_flag)) if isinstance(is_day_flag, (int, str)) else bool(is_day_flag)
        except ValueError:
            is_day_norm = True

        precipitation, humidity, windspeed = self._extract_detail_values(data)
        detail_signature = (
            None if precipitation is None else round(precipitation, 1),
            None if humidity is None else round(humidity, 1),
            None if windspeed is None else round(windspeed, 1),
        )

        forecast_text = data.get("forecast") or self._forecast_data or ""
        forecast_key = ""
        if isinstance(forecast_text, str):
            forecast_key = forecast_text.split("(frame", 1)[0].strip().lower()

        return (
            round(float(temp), 1),
            condition_key,
            location_key,
            weather_code,
            is_day_norm,
            detail_signature,
            bool(self._show_details_row),
            bool(self._show_forecast),
            forecast_key,
        )
    
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
        self._primary_row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        primary_layout = QHBoxLayout(self._primary_row)
        primary_layout.setContentsMargins(0, 0, 0, 0)
        primary_layout.setSpacing(8)
        self._primary_layout = primary_layout

        text_column = QWidget(self._primary_row)
        text_column.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        text_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        text_layout = QVBoxLayout(text_column)
        text_layout.setContentsMargins(8, 2, 8, 2)
        text_layout.setSpacing(1)
        self._text_layout = text_layout

        self._city_label = self._create_content_label(word_wrap=False)
        self._city_label.setContentsMargins(0, 0, 0, 0)
        self._conditions_label = self._create_content_label(word_wrap=False)
        self._conditions_label.setContentsMargins(0, 1, 0, 0)
        text_layout.addWidget(self._city_label)
        text_layout.addWidget(self._conditions_label)

        self._text_column = text_column
        primary_layout.addWidget(text_column, 1)

        default_icon_px = int(round(96 * _ANIMATED_ICON_SCALE_FACTOR))
        self._condition_icon_widget = WeatherConditionIcon(size_px=default_icon_px, parent=self._primary_row)
        self._condition_icon_widget.set_animation_enabled(self._animated_icon_enabled)
        self._condition_icon_widget.setVisible(False)
        primary_layout.addWidget(
            self._condition_icon_widget, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        )

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
        placeholder = self._create_content_label(word_wrap=False)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        placeholder.setVisible(False)
        self._detail_placeholder_label = placeholder
        detail_layout.addWidget(placeholder)
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

        self._status_label = self._create_content_label(word_wrap=True)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setVisible(False)
        self._root_layout.addWidget(self._status_label)

        self._apply_icon_alignment()
        self._apply_icon_desaturation()
        self._sync_primary_row_min_height()

    def text(self) -> str:  # noqa: N802
        """Return user-facing summary text even when base QLabel text is blank."""
        summary = getattr(self, "_current_summary", "")
        if summary:
            return summary
        return super().text()

    def _create_content_label(self, *, word_wrap: bool = True) -> QLabel:
        label = QLabel(self)
        label.setObjectName("")
        label.setWordWrap(word_wrap)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
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
        with widget_timer_sample(self, "weather.update_display"):
            if not data:
                message = "Weather: No Data"
                self._detail_metrics.clear()
                self._update_detail_metrics({}, force=True)
                self._show_status_message(message)
                return
        
            try:
                geometry_dirty = False
                now = datetime.now()
                temp = data.get("temperature")
                condition = data.get("condition")
                location = data.get("location")
                weather_entry: Optional[Dict[str, Any]] = None
                if self._status_label:
                    self._status_label.setVisible(False)
                if self._primary_row:
                    self._primary_row.setVisible(True)

                if isinstance(data.get("weather"), list) and data["weather"]:
                    weather_entry = data["weather"][0] or {}

                if temp is None and isinstance(data.get("main"), dict):
                    temp = data["main"].get("temp")
                if condition is None and weather_entry:
                    condition = weather_entry.get("main") or weather_entry.get("description")
                if not location:
                    location = data.get("name") or self._location

                weather_code = data.get("weather_code")
                if weather_code is None and weather_entry:
                    weather_code = weather_entry.get("id") or weather_entry.get("code")

                is_day_flag = data.get("is_day")
                if is_day_flag is None and weather_entry:
                    is_day_flag = weather_entry.get("is_day")
                if is_day_flag is None:
                    is_day_flag = 1
                is_day = bool(int(is_day_flag)) if isinstance(is_day_flag, (int, str)) else bool(is_day_flag)

                temp = 0.0 if temp is None else float(temp)
                condition = "Unknown" if condition is None else str(condition)
                location = location or self._location

                payload_signature = self._build_payload_signature(data)
                signature_changed = payload_signature != self._last_payload_signature
                refresh_due = (
                    self._force_next_display_refresh
                    or self._last_display_refresh is None
                    or self._display_refresh_deadline is None
                    or now >= self._display_refresh_deadline
                )

                if not refresh_due and not self._force_next_display_refresh:
                    if signature_changed:
                        self._pending_payload_signature = payload_signature
                        self._pending_payload_data = data
                        self._schedule_pending_refresh_consumption()
                    if self._tooltips_enabled and self._current_summary:
                        with widget_timer_sample(self, "weather.details.tooltip"):
                            tooltip_text = self._build_tooltip_text(self._current_summary)
                            if tooltip_text != self._tooltip_cache:
                                self.setToolTip(tooltip_text)
                                self._tooltip_cache = tooltip_text
                    return

                self._force_next_display_refresh = False
                self._last_payload_signature = payload_signature
                self._pending_payload_signature = None
                self._pending_payload_data = None

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

                with widget_timer_sample(self, "weather.label.html"):
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

                    if self._city_label and city_html != self._last_city_html:
                        self._city_label.setTextFormat(Qt.TextFormat.RichText)
                        self._city_label.setText(city_html)
                        self._last_city_html = city_html
                        geometry_dirty = True
                    if self._conditions_label and details_html != self._last_details_html:
                        self._conditions_label.setTextFormat(Qt.TextFormat.RichText)
                        self._conditions_label.setText(details_html)
                        self._last_details_html = details_html
                        geometry_dirty = True

                display_summary = f"{location_display}: {temp:.0f}°C - {condition_display}"
                self._current_summary = display_summary

                font_key = (self._font_family, secondary_pt)
                if self._detail_font_cache_key != font_key:
                    with widget_timer_sample(self, "weather.details.font"):
                        self._details_font = QFont(self._font_family, secondary_pt, QFont.Weight.Normal)
                        self._details_font.setItalic(False)
                        self._details_font_metrics = QFontMetrics(self._details_font)
                        metrics_height = self._details_font_metrics.height()
                        self._detail_icon_size = max(
                            _DETAIL_ICON_MIN_PX, int(metrics_height * 1.15) if metrics_height else _DETAIL_ICON_MIN_PX
                        )
                        self._detail_font_cache_key = font_key
                with widget_timer_sample(self, "weather.details.metrics"):
                    self._update_detail_metrics(data)
                    detail_ready = bool(self._detail_metrics)
                if not detail_ready and self._show_details_row and self._enabled:
                    self._fetch_weather()

                detail_placeholder_needed = self._show_details_row and not detail_ready
                show_detail_segment = bool(self._show_details_row and (detail_ready or detail_placeholder_needed))
                show_details = bool(self._show_details_row and detail_ready)
                if self._details_separator and self._details_separator.isVisible() != show_detail_segment:
                    self._details_separator.setVisible(show_detail_segment)
                    geometry_dirty = True
                if self._detail_row_container and self._detail_row_container.isVisible() != show_detail_segment:
                    self._detail_row_container.setVisible(show_detail_segment)
                    geometry_dirty = True
                if self._detail_row_widget:
                    detail_metrics = self._detail_metrics if show_details else []
                    signature = tuple(detail_metrics)
                    if signature != self._detail_row_last_signature or not show_details:
                        with widget_timer_sample(self, "weather.details.row_widget"):
                            self._detail_row_widget.update_metrics(
                                detail_metrics,
                                self._details_font,
                                self._text_color,
                                self._detail_icon_size,
                            )
                        self._detail_row_last_signature = signature if show_details else None
                        geometry_dirty = True
                    self._detail_row_widget.setVisible(show_details)
                if self._detail_placeholder_label:
                    if detail_placeholder_needed:
                        placeholder_html = (
                            f"<span style='font-size:{secondary_pt}pt; font-style:italic; "
                            f"color:rgba({self._text_color.red()}, {self._text_color.green()}, "
                            f"{self._text_color.blue()}, {int(self._text_color.alpha() * 0.9)})'>"
                            "Detailed metrics unavailable</span>"
                        )
                        if placeholder_html != self._detail_placeholder_label_cache:
                            self._detail_placeholder_label.setTextFormat(Qt.TextFormat.RichText)
                            self._detail_placeholder_label.setText(placeholder_html)
                            self._detail_placeholder_label_cache = placeholder_html
                            geometry_dirty = True
                    else:
                        if self._detail_placeholder_label_cache:
                            self._detail_placeholder_label.clear()
                            self._detail_placeholder_label_cache = None
                    self._detail_placeholder_label.setVisible(detail_placeholder_needed)

                show_forecast_line = bool(self._show_forecast and self._forecast_data)
                if self._forecast_separator and self._forecast_separator.isVisible() != show_forecast_line:
                    self._forecast_separator.setVisible(show_forecast_line)
                    geometry_dirty = True
                if self._forecast_container and self._forecast_container.isVisible() != show_forecast_line:
                    self._forecast_container.setVisible(show_forecast_line)
                    geometry_dirty = True
                if self._forecast_label:
                    with widget_timer_sample(self, "weather.forecast.label"):
                        forecast_html = ""
                        if show_forecast_line:
                            forecast_html = (
                                f"<div style='font-size:{secondary_pt}pt; font-style:italic; "
                                f"font-weight:400; color:{color_rgba};'>"
                                f"{html.escape(self._forecast_data)}</div>"
                            )
                        if forecast_html != self._forecast_label_cache:
                            if show_forecast_line:
                                self._forecast_label.setTextFormat(Qt.TextFormat.RichText)
                                self._forecast_label.setText(forecast_html)
                            else:
                                self._forecast_label.clear()
                            self._forecast_label_cache = forecast_html
                            geometry_dirty = True
                        self._forecast_label.setVisible(show_forecast_line)

                forecast_signature = self._forecast_data if show_forecast_line else None

                display_signature = (
                    round(temp, 2),
                    condition,
                    location,
                    show_details,
                    tuple(self._detail_metrics) if show_details else (),
                    show_forecast_line,
                    forecast_signature,
                    weather_code,
                    is_day,
                    city_pt,
                    primary_pt,
                )

                if self._last_display_signature == display_signature:
                    if self._tooltips_enabled:
                        tooltip_text = self._build_tooltip_text(self._current_summary)
                        if tooltip_text != self._tooltip_cache:
                            self.setToolTip(tooltip_text)
                            self._tooltip_cache = tooltip_text
                    return

                base_icon_scale = max(city_pt * 2, 72)
                animated_scale = int(round(base_icon_scale * _ANIMATED_ICON_SCALE_FACTOR))
                icon_context = (
                    weather_code,
                    condition_display,
                    is_day,
                    animated_scale,
                )
                if (
                    self._last_icon_context.get("code"),
                    self._last_icon_context.get("condition"),
                    self._last_icon_context.get("is_day"),
                    self._last_icon_context.get("icon_scale"),
                ) != icon_context:
                    with widget_timer_sample(self, "weather.icon.update"):
                        self._update_condition_icon(
                            weather_code, condition_display, is_day, icon_scale=animated_scale
                        )
                    geometry_dirty = True

                if geometry_dirty:
                    with widget_timer_sample(self, "weather.adjust_size"):
                        self.adjustSize()
                if self._tooltips_enabled:
                    with widget_timer_sample(self, "weather.details.tooltip"):
                        tooltip_text = self._build_tooltip_text(self._current_summary)
                        if tooltip_text != self._tooltip_cache:
                            self.setToolTip(tooltip_text)
                            self._tooltip_cache = tooltip_text
                if geometry_dirty:
                    with widget_timer_sample(self, "weather.sync_primary_row"):
                        self._sync_primary_row_min_height()
                    if self.parent():
                        with widget_timer_sample(self, "weather.position.update"):
                            self._update_position()

                self._last_display_signature = display_signature
                self._last_display_refresh = now
                self._display_refresh_deadline = now + self._display_refresh_interval

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
        self._request_display_refresh()
        
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
            self._request_display_refresh()
            if self._cached_data:
                self._update_display(self._cached_data)
    
    def set_font_size(self, size: int) -> None:
        """Override to ensure display refresh when typography changes."""
        super().set_font_size(size)
        self._request_display_refresh()
        if self._cached_data:
            self._update_display(self._cached_data)
    
    def set_thread_manager(self, thread_manager) -> None:
        self._thread_manager = thread_manager

    def set_show_forecast(self, show: bool) -> None:
        """Enable or disable the optional forecast line.
        
        Args:
            show: True to show forecast line when data is available
        """
        if self._show_forecast == show:
            return
        self._show_forecast = show
        self._request_display_refresh()
        if self._cached_data:
            self._update_display(self._cached_data)

    def set_desaturate_animated_icon(self, desaturate: bool) -> None:
        """Enable or disable desaturation for the animated icon."""
        if self._desaturate_condition_icon == desaturate:
            return
        self._desaturate_condition_icon = desaturate
        self._apply_icon_desaturation()
        self._request_display_refresh()
        if self._cached_data:
            self._update_display(self._cached_data)

    def get_desaturate_animated_icon(self) -> bool:
        return self._desaturate_condition_icon

    def set_shared_animation_driver_enabled(self, enabled: bool) -> None:
        self._shared_animation_driver_enabled = bool(enabled)

    def shared_animation_driver_enabled(self) -> bool:
        return self._shared_animation_driver_enabled

    def shared_animation_sink_mode_enabled(self) -> bool:
        return self._shared_animation_sink_mode

    def enable_shared_animation_sink_mode(self) -> None:
        self._shared_animation_sink_mode = True

    def disable_shared_animation_sink_mode(self) -> None:
        if not self._shared_animation_sink_mode:
            return
        self._shared_animation_sink_mode = False
        self.refresh_condition_icon()

    def get_condition_icon_widget(self) -> Optional[WeatherConditionIcon]:
        return self._condition_icon_widget

    def refresh_condition_icon(self) -> None:
        icon_widget = self._condition_icon_widget
        if icon_widget is None:
            return
        icon_widget.clear_icon()
        icon_widget.set_animation_enabled(self._animated_icon_enabled)
        self._refresh_condition_icon()

    def _apply_icon_desaturation(self) -> None:
        icon_widget = self._condition_icon_widget
        if icon_widget is None:
            return

        if not self._desaturate_condition_icon:
            if self._icon_desaturate_effect is not None and Shiboken.isValid(self._icon_desaturate_effect):
                try:
                    self._icon_desaturate_effect.setEnabled(False)
                except Exception:
                    logger.debug("[WEATHER] Failed to disable desaturation effect", exc_info=True)
            icon_widget.setGraphicsEffect(None)
            return

        effect = self._icon_desaturate_effect
        if effect is None or Shiboken.isValid(effect) is False:
            effect = QGraphicsColorizeEffect(icon_widget)
            self._icon_desaturate_effect = effect

        effect.setColor(QColor(160, 160, 160))
        effect.setStrength(1.0)
        effect.setEnabled(True)
        icon_widget.setGraphicsEffect(effect)

    def set_show_details_row(self, show: bool) -> None:
        """Enable/disable mini detail row with icons."""
        if self._show_details_row == show:
            return
        self._show_details_row = show
        if not show:
            if self._details_separator:
                self._details_separator.setVisible(False)
            if self._detail_row_container:
                self._detail_row_container.setVisible(False)
        self._request_display_refresh()
        if self._cached_data:
            self._update_display(self._cached_data)
        else:
            self.update()

    def set_animated_icon_alignment(self, alignment: str) -> None:
        """Set animated icon alignment ('LEFT', 'RIGHT', 'NONE')."""
        normalized = (alignment or _DEFAULT_ICON_ALIGNMENT).strip().upper()
        if normalized not in _ICON_ALIGNMENT_OPTIONS:
            normalized = _DEFAULT_ICON_ALIGNMENT
        if normalized == self._animated_icon_alignment:
            return
        self._animated_icon_alignment = normalized
        self._apply_icon_alignment()
        self._refresh_condition_icon()
        self._request_display_refresh()
        if self._cached_data:
            self._update_display(self._cached_data)

    def get_animated_icon_alignment(self) -> str:
        return self._animated_icon_alignment

    def set_animated_icon_enabled(self, enabled: bool) -> None:
        """Enable or disable SVG animation playback."""
        enabled = bool(enabled)
        if enabled == self._animated_icon_enabled:
            return
        self._animated_icon_enabled = enabled
        if self._condition_icon_widget is not None:
            self._condition_icon_widget.set_animation_enabled(enabled)
        self._refresh_condition_icon()
        self._request_display_refresh()
        if self._cached_data:
            self._update_display(self._cached_data)

    def _apply_icon_alignment(self) -> None:
        icon_widget = self._condition_icon_widget
        layout = self._primary_layout
        text_column = self._text_column
        if icon_widget is None or layout is None or text_column is None:
            return

        layout.removeWidget(icon_widget)
        icon_widget.setVisible(False)
        layout.setStretchFactor(text_column, 1)

        if self._animated_icon_alignment == "NONE":
            icon_widget.clear_icon()
            return

        if self._animated_icon_alignment == "LEFT":
            layout.insertWidget(0, icon_widget, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        else:
            layout.addWidget(icon_widget, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        if icon_widget.has_icon():
            icon_widget.setVisible(True)

    def _refresh_condition_icon(self) -> None:
        if not self._last_icon_context:
            return
        self._update_condition_icon(
            self._last_icon_context.get("code"),
            self._last_icon_context.get("condition"),
            self._last_icon_context.get("is_day", True),
            icon_scale=self._last_icon_context.get("icon_scale"),
        )

    def _update_condition_icon(
        self,
        weather_code: Optional[int],
        condition_text: Optional[str],
        is_day: bool,
        icon_scale: Optional[int] = None,
    ) -> None:
        icon_widget = self._condition_icon_widget
        if icon_widget is None:
            return

        self._last_icon_context = {
            "code": weather_code,
            "condition": condition_text,
            "is_day": is_day,
            "icon_scale": icon_scale,
        }

        if self._animated_icon_alignment == "NONE":
            icon_widget = self._condition_icon_widget
        if icon_widget is None:
            return

        self._last_icon_context = {
            "code": weather_code,
            "condition": condition_text,
            "is_day": is_day,
            "icon_scale": icon_scale,
        }

        if self._shared_animation_sink_mode:
            return

        icon_widget.clear_icon()

        icon_path = self._resolve_icon_path(weather_code, condition_text, is_day)
        if icon_path is None:
            icon_widget.setVisible(False)
            return

        if icon_scale:
            icon_widget.set_icon_size(icon_scale)

        icon_widget.set_icon_path(icon_path)
        icon_widget.setVisible(True)
        self._sync_primary_row_min_height()

    def _sync_primary_row_min_height(self) -> None:
        """Ensure the text column expands to match the icon height (DPR aware)."""
        primary_row = self._primary_row
        text_column = self._text_column
        if primary_row is None or text_column is None:
            return

        icon_widget = self._condition_icon_widget
        dpr = max(1.0, float(self.devicePixelRatioF()))

        icon_height = 0
        if icon_widget is not None:
            icon_height = icon_widget.height() or icon_widget.sizeHint().height()

        text_layout = self._text_layout
        text_height = 0
        if text_layout is not None:
            label_heights: List[int] = []
            for idx in range(text_layout.count()):
                item = text_layout.itemAt(idx)
                widget = item.widget() if item is not None else None
                if widget is not None:
                    hint = widget.sizeHint().height()
                    label_heights.append(hint if hint > 0 else widget.height())
            spacing_total = max(0, len(label_heights) - 1) * max(0, text_layout.spacing())
            margins = text_layout.contentsMargins()
            text_height = (
                sum(label_heights)
                + spacing_total
                + margins.top()
                + margins.bottom()
            )

        if text_height <= 0:
            text_height = text_column.sizeHint().height() or text_column.height()

        logical_height = max(icon_height, text_height)
        if logical_height <= 0:
            return

        physical_height = math.ceil(logical_height * dpr)
        min_height = int(math.ceil(physical_height / dpr))
        primary_row.setMinimumHeight(min_height)
        text_column.setMinimumHeight(min_height)
        primary_row.updateGeometry()
        text_column.updateGeometry()

    def _resolve_condition_icon_path(
        self, weather_code: Optional[int], condition_text: Optional[str], is_day: bool
    ) -> Optional[Path]:
        icon_name: Optional[str] = None
        if weather_code is not None:
            for codes, candidate in _WEATHER_CODE_ICON_MAP:
                if weather_code in codes:
                    icon_name = candidate
                    break
        if icon_name is None and condition_text:
            lowered = condition_text.lower()
            for keyword, candidate in _CONDITION_KEYWORDS_ICON_MAP:
                if keyword in lowered:
                    icon_name = candidate
                    break
        if icon_name is None:
            return None

        resolved_name = self._resolve_day_night_icon(icon_name, is_day)
        candidate_path = _WEATHER_ICON_DIR / resolved_name
        if candidate_path.exists():
            return candidate_path

        fallback_path = _WEATHER_ICON_DIR / icon_name
        if fallback_path.exists():
            return fallback_path
        return None

    def _resolve_icon_path(
        self, weather_code: Optional[int], condition_text: Optional[str], is_day: bool
    ) -> Optional[Path]:
        """Legacy alias returning the resolved icon path."""
        return self._resolve_condition_icon_path(weather_code, condition_text, is_day)

    @staticmethod
    def _resolve_day_night_icon(icon_name: str, is_day: bool) -> str:
        if is_day:
            return icon_name
        if "-day" in icon_name:
            return icon_name.replace("-day", "-night")
        if icon_name.endswith(".svg"):
            base = icon_name[:-4]
            return f"{base}-night.svg"
        return icon_name

    def _show_status_message(self, message: str) -> None:
        self._current_summary = message
        if self._primary_row:
            self._primary_row.setVisible(False)
        if self._status_label:
            self._status_label.setTextFormat(Qt.TextFormat.PlainText)
            self._status_label.setText(message)
            self._status_label.setVisible(True)
        if self._city_label:
            self._city_label.clear()
        if self._conditions_label:
            self._conditions_label.clear()
        if self._forecast_label:
            self._forecast_label.clear()
            self._forecast_label.setVisible(False)
        if self._detail_row_widget:
            self._detail_row_widget.setVisible(False)
        if self._detail_row_container:
            self._detail_row_container.setVisible(False)
        if self._details_separator:
            self._details_separator.setVisible(False)
        if self._forecast_separator:
            self._forecast_separator.setVisible(False)
        if self._forecast_container:
            self._forecast_container.setVisible(False)
        if self._condition_icon_widget:
            self._condition_icon_widget.clear_icon()
            self._condition_icon_widget.setVisible(False)
        self.setText("")
        self.adjustSize()
    
    def set_text_color(self, color: QColor) -> None:
        """Override to refresh cached monochrome icons when color changes."""
        previous = QColor(self._text_color)
        super().set_text_color(color)
        if previous == self._text_color:
            return
        self._clear_detail_caches()
        self._request_display_refresh()
        if self._cached_data:
            self._update_display(self._cached_data)

    def set_forecast_data(self, forecast: Optional[str]) -> None:
        """Set the forecast text to display.
        
        Args:
            forecast: Forecast text (e.g. "Tomorrow: 18°C, Partly Cloudy")
        """
        self._forecast_data = forecast
        self._request_display_refresh()
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
