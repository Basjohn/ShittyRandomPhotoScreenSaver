#!/usr/bin/env python
"""
Synthetic widget benchmark for Weather + Reddit overlays.

Usage:
    python tools/synthetic_widget_benchmark.py [options]

Key options (documented via --help):
    --weather / --no-weather
        Enable or disable the weather widget entirely.
    --weather-details / --no-weather-details
        Toggle the detail row population for faster runs.
    --weather-forecast / --no-weather-forecast
        Toggle the forecast block.
    --weather-animated-icon {left,right,none}
        Control whether the animated icon is rendered (NONE skips SVG work).
    --reddit / --no-reddit
        Enable or disable the Reddit widget entirely.
    --reddit-separators / --no-reddit-separators
        Toggle row separators (useful when isolating text-only paint paths).
    --reddit-limit N
        Control how many posts are synthesized for the Reddit list.
    --frames N
        How many repaint frames to drive (per widget) before collecting metrics.

The harness forces SRPSS_PERF_METRICS=1 so existing widget-level perf logs
(`[PERF_WIDGET] ...`) are emitted. Those lines are parsed and summarized into a
compact table plus an optional JSONL artefact for CI diffing.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
import copy
import math
import random
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from datetime import timedelta

# Ensure repo root is importable before local dependencies.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from PySide6.QtCore import QObject, QTimer, Qt, Signal, QBuffer, QIODevice, QSize, QRect  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QPainter,
    QImage,
    QFont,
    QFontMetrics,
    QPen,
    QPixmap,
    QPainterPath,
)
from PySide6.QtWidgets import QApplication, QVBoxLayout, QHBoxLayout, QWidget  # noqa: E402

# Ensure perf metrics emit even when run outside the screensaver shell.
if os.getenv("SRPSS_PERF_METRICS", "").strip().lower() not in {"1", "true", "on", "yes"}:
    os.environ["SRPSS_PERF_METRICS"] = "1"

from core.logging.logger import setup_logging, is_perf_metrics_enabled  # noqa: E402
from core.performance import widget_paint_sample, widget_timer_sample  # noqa: E402
from core.performance.widget_profiler import flush_widget_perf_metrics  # noqa: E402
from core.threading.manager import ThreadManager  # noqa: E402
from widgets.weather_widget import WeatherWidget  # noqa: E402
from widgets.reddit_widget import RedditWidget, RedditPost  # noqa: E402
from widgets.clock_widget import ClockWidget  # noqa: E402


logger = logging.getLogger("tools.synthetic_widget_benchmark")

DEFAULT_WEATHER_SAMPLE: Dict[str, Any] = {
    "temperature": 21.4,
    "condition": "Broken Clouds",
    "location": "Helsinki",
    "weather_code": 3,
    "is_day": 1,
    "humidity": 62,
    "windspeed": 12.4,
    "precipitation_probability": 30,
    "forecast": "Clouds rolling in overnight, scattered showers tomorrow.",
    "weather": [
        {
            "main": "Clouds",
            "description": "broken clouds",
            "id": 803,
            "is_day": 1,
        }
    ],
}

DEFAULT_REDDIT_POSTS: List[Dict[str, Any]] = [
    {
        "title": f"Sample Post #{idx} – synthetic benchmark payload",
        "url": f"https://example.com/post/{idx}",
        "score": 1000 - idx * 37,
        "created_utc": 1705948800.0 - idx * 1800,
    }
    for idx in range(1, 21)
]

_STEADY_WEATHER_REFRESH_FRAMES = 120
_STEADY_REDDIT_REFRESH_FRAMES = 40

_WEATHER_CODE_SEQUENCE: List[int] = [200, 211, 301, 502, 602, 741, 800, 801, 803]


def _load_fixture(path: Optional[Path], fallback: Any) -> Any:
    if not path:
        return fallback
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:  # pragma: no cover - harness helper
        logging.getLogger(__name__).warning(
            "[BENCH] Failed to load fixture %s (%s). Using fallback.", path, exc
        )
        return fallback


def _force_engine_running_flag() -> None:
    """Pretend the screensaver engine is running so PERF logs emit.

    widget_profiler suppresses `[PERF_WIDGET]` buckets unless
    `ScreensaverEngine._is_engine_running()` returns True. The synthetic
    harness operates outside the normal engine lifecycle, so we toggle
    the class-level flag manually.
    """
    try:
        from engine.screensaver_engine import ScreensaverEngine
    except Exception:  # pragma: no cover - toolbox helper
        logging.getLogger(__name__).warning(
            "[BENCH] Could not import ScreensaverEngine; PERF metrics may be suppressed."
        )
        return

    try:
        lock = getattr(ScreensaverEngine, "_instance_lock", None)
        if lock is None:
            logging.getLogger(__name__).warning(
                "[BENCH] ScreensaverEngine._instance_lock missing; PERF metrics may be suppressed."
            )
            return
        with lock:
            ScreensaverEngine._instance_running = True  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - toolbox helper
        logging.getLogger(__name__).warning(
            "[BENCH] Failed to toggle engine running flag (%s); PERF metrics may be suppressed.",
            exc,
        )


class PerfLogCollector(logging.Handler):
    """Collect `[PERF_WIDGET]` log lines for summarisation."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: List[Dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:
            message = record.msg  # type: ignore[assignment]

        if "[PERF_WIDGET]" not in str(message):
            return
        parsed = self._parse_perf_message(str(message))
        if parsed:
            self.records.append(parsed)

    @staticmethod
    def _parse_perf_message(message: str) -> Optional[Dict[str, Any]]:
        tokens = message.split()
        data: Dict[str, Any] = {"raw": message}
        for token in tokens:
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            value = value.rstrip(",")
            if key in {"widget", "kind", "metric"}:
                data[key] = value
            else:
                try:
                    if "." in value:
                        data[key] = float(value)
                    else:
                        data[key] = int(value)
                except ValueError:
                    data[key] = value
        return data if "widget" in data and "kind" in data else None


class FrameDriver(QObject):
    """Drive widget repaints for a fixed number of frames."""

    finished = Signal()

    def __init__(
        self,
        widgets: Sequence[QWidget],
        frames: int,
        interval_ms: int,
        tick_callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        super().__init__()
        self._widgets = [w for w in widgets if w is not None]
        self._frames = max(1, frames)
        self._interval = max(1, interval_ms)
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_tick)
        self._current = 0
        self._tick_callback = tick_callback
        self._last_tick_monotonic: Optional[float] = None
        self._interval_samples: List[float] = []
        self._late_tick_frames = 0
        self._max_tick_ms = 0.0
        self._tick_warn_threshold_ms = max(100.0, float(self._interval) * 1.5)

    def start(self) -> None:
        if not self._widgets:
            QTimer.singleShot(0, self.finished.emit)
            return
        self._timer.start(self._interval)

    def _on_tick(self) -> None:
        now = time.perf_counter()
        if self._last_tick_monotonic is not None:
            delta_ms = (now - self._last_tick_monotonic) * 1000.0
            self._interval_samples.append(delta_ms)
            self._max_tick_ms = max(self._max_tick_ms, delta_ms)
            if delta_ms > self._tick_warn_threshold_ms:
                self._late_tick_frames += 1
                if is_perf_metrics_enabled():
                    logger.warning(
                        "[PERF_TIMER] frame_driver.tick frame=%d interval_ms=%d actual_ms=%.2f",
                        self._current,
                        self._interval,
                        delta_ms,
                    )
        self._last_tick_monotonic = now
        if self._tick_callback:
            try:
                self._tick_callback(self._current)
            except Exception as exc:  # pragma: no cover - bench safety
                logging.getLogger(__name__).warning("[BENCH] Tick callback failed: %s", exc)
        for widget in self._widgets:
            widget.update()
        self._current += 1
        if self._current >= self._frames:
            self._timer.stop()
            self.finished.emit()

    @property
    def interval_stats(self) -> Dict[str, Any]:
        samples = len(self._interval_samples)
        if samples == 0:
            return {
                "samples": 0,
                "avg_ms": 0.0,
                "max_ms": 0.0,
                "min_ms": 0.0,
                "late_frames": self._late_tick_frames,
            }
        avg_ms = sum(self._interval_samples) / samples
        min_ms = min(self._interval_samples)
        return {
            "samples": samples,
            "avg_ms": round(avg_ms, 3),
            "max_ms": round(self._max_tick_ms, 3),
            "min_ms": round(min_ms, 3),
            "late_frames": self._late_tick_frames,
            "warn_threshold_ms": round(self._tick_warn_threshold_ms, 3),
        }


@dataclass
class BenchmarkArgs:
    frames: int
    interval_ms: int
    display_count: int
    weather_enabled: bool
    weather_details: bool
    weather_forecast: bool
    weather_icon_alignment: str
    weather_icon_animated: bool
    weather_icon_desaturate: bool
    weather_fixture: Optional[Path]
    weather_width: int
    weather_height: int
    weather_updates_per_frame: int
    weather_per_display: int
    reddit_enabled: bool
    reddit_separators: bool
    reddit_limit: int
    reddit_fixture: Optional[Path]
    reddit_per_display: int
    clock_enabled: bool
    clock_per_display: int
    transitions_enabled: bool
    transition_speed_scale: float
    transition_width: int
    transition_height: int
    media_enabled: bool
    media_per_display: int
    media_track_interval: int
    media_artwork_latency_min_ms: int
    media_artwork_latency_max_ms: int
    media_feed_mode: str
    cadence_mode: str
    json_output: Optional[Path]
    show_window: bool


@dataclass
class WidgetVariant:
    display_index: int
    instance_index: int
    widget_kind: str


@dataclass
class DisplayStack:
    container: QWidget
    weather_widgets: List[WeatherWidget]
    reddit_widgets: List[RedditWidget]
    clock_widgets: List[ClockWidget]
    media_widgets: List["BenchmarkMediaWidget"]
    transition_widget: Optional["TransitionStub"]


@dataclass
class SyntheticMediaTrack:
    track_id: str
    title: str
    artist: str
    album: str
    state: str
    has_artwork: bool


class TransitionStub(QWidget):
    """Lightweight widget that simulates a visual transition paint path."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        logical_size: tuple[int, int] = (320, 180),
        *,
        speed_scale: float = 1.0,
    ) -> None:
        super().__init__(parent)
        self._progress = 0.0
        self._direction = 1.0
        self._logical_size = logical_size
        self._speed_scale = max(0.1, min(5.0, speed_scale))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(*logical_size)

    def advance(self) -> None:
        step = 0.05 * self._speed_scale
        self._progress += step * self._direction
        if self._progress >= 1.0:
            self._progress = 1.0
            self._direction = -1.0
        elif self._progress <= 0.0:
            self._progress = 0.0
            self._direction = 1.0
        self.update()

    def set_speed_scale(self, scale: float) -> None:
        self._speed_scale = max(0.1, min(5.0, scale))

    def paintEvent(self, event) -> None:  # noqa: N802
        with widget_paint_sample(self, "transition.stub.paint"):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            base_color = QColor(80, 120, 255, 60)
            fade = int(60 + 120 * self._progress)
            base_color.setAlpha(fade)
            painter.fillRect(self.rect(), base_color)
            painter.end()


class SyntheticMediaFeed:
    """Generates synthetic media metadata + artwork shared across widgets."""

    def __init__(self, thread_manager: ThreadManager, args: BenchmarkArgs) -> None:
        self._thread_manager = thread_manager
        self._track_interval_ms = max(400, int(args.media_track_interval))
        self._artwork_latency_min_ms = max(50, int(args.media_artwork_latency_min_ms))
        self._artwork_latency_max_ms = max(self._artwork_latency_min_ms, int(args.media_artwork_latency_max_ms))
        self._listeners: List["BenchmarkMediaWidget"] = []
        self._catalog: List[SyntheticMediaTrack] = self._build_catalog()
        self._catalog_index = 0
        self._rng = random.Random(0x5EEDC0DE)
        self._ms_since_change = 0
        self._current_track: Optional[SyntheticMediaTrack] = None
        self._artwork_cache: Dict[str, QPixmap] = {}
        self._pending_artwork_requests: Set[str] = set()

    def register_widget(self, widget: "BenchmarkMediaWidget") -> None:
        if widget not in self._listeners:
            self._listeners.append(widget)

    def unregister_widget(self, widget: "BenchmarkMediaWidget") -> None:
        try:
            self._listeners.remove(widget)
        except ValueError:
            pass

    def tick(self, delta_ms: int) -> None:
        self._ms_since_change += delta_ms
        if self._current_track is None or self._ms_since_change >= self._track_interval_ms:
            self._ms_since_change = 0
            self._current_track = self._next_track()
            cached_pm = self._artwork_cache.get(self._current_track.track_id or "")
            if cached_pm is not None and not cached_pm.isNull():
                self._broadcast_track(self._current_track, artwork=cached_pm)
            else:
                self._broadcast_track(self._current_track, artwork=None)
                if self._current_track.has_artwork:
                    self._request_artwork(self._current_track)

    # Internal helpers -------------------------------------------------

    def _next_track(self) -> SyntheticMediaTrack:
        track = self._catalog[self._catalog_index]
        self._catalog_index = (self._catalog_index + 1) % len(self._catalog)
        return track

    def _broadcast_track(
        self,
        track: SyntheticMediaTrack,
        artwork: Optional[QPixmap],
    ) -> None:
        for widget in list(self._listeners):
            widget.set_track(track, artwork)

    def _request_artwork(self, track: SyntheticMediaTrack) -> None:
        track_id = track.track_id
        if not track_id:
            return
        cached_pm = self._artwork_cache.get(track_id)
        if cached_pm is not None and not cached_pm.isNull():
            self._broadcast_track(track, cached_pm)
            return
        if track_id in self._pending_artwork_requests:
            return
        self._pending_artwork_requests.add(track_id)
        latency_ms = self._rng.randint(self._artwork_latency_min_ms, self._artwork_latency_max_ms)

        def _generate_artwork() -> bytes:
            time.sleep(latency_ms / 1000.0)
            return self._build_artwork_bytes(track)

        def _on_result(task_result) -> None:
            self._pending_artwork_requests.discard(track_id)
            if not getattr(task_result, "success", False):
                return
            data = getattr(task_result, "result", None)
            if not isinstance(data, (bytes, bytearray)):
                return

            def _deliver() -> None:
                if self._current_track is None or self._current_track.track_id != track.track_id:
                    return
                pm = QPixmap()
                if not pm.loadFromData(bytes(data)):
                    return
                self._artwork_cache[track_id] = pm
                self._broadcast_track(track, pm)

            ThreadManager.run_on_ui_thread(_deliver)

        self._thread_manager.submit_io_task(_generate_artwork, callback=_on_result)

    def _build_catalog(self) -> List[SyntheticMediaTrack]:
        seeds = [
            ("Night Drive", "Heliosphere", "Roads", True),
            ("Lofi Study", "Forrest Kid", "Sunday Loops", True),
            ("Podcast · Release Radar", "SRPSS FM", "Ep. 492", False),
            ("Coding Focus", "Neon Minds", "Compiler Dreams", True),
            ("Weather Break", "Cloud Sculptors", "Cirrus", True),
            ("Daily Brief", "City Desk", "Morning Edition", False),
        ]
        catalog: List[SyntheticMediaTrack] = []
        for idx, (title, artist, album, art) in enumerate(seeds):
            state = "PLAYING" if idx % 3 != 0 else "PAUSED"
            catalog.append(
                SyntheticMediaTrack(
                    track_id=f"synthetic-track-{idx}",
                    title=title,
                    artist=artist,
                    album=album,
                    state=state,
                    has_artwork=art,
                )
            )
        return catalog

    def _build_artwork_bytes(self, track: SyntheticMediaTrack) -> bytes:
        size = 420
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        bg_color = QColor.fromHsv(self._rng.randint(0, 359), 60 + self._rng.randint(0, 80), 200)
        image.fill(bg_color)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        accent = QColor.fromHsv((bg_color.hue() + 45) % 360, 140, 255)
        pen = QPen(accent, 6)
        painter.setPen(pen)
        painter.drawRoundedRect(image.rect().adjusted(12, 12, -12, -12), 32, 32)

        font = QFont("Segoe UI", 64, QFont.Weight.Black)
        painter.setFont(font)
        painter.setPen(QColor(20, 20, 28))
        text = (track.title[:1] or "?").upper()
        painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()

        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        return bytes(buffer.data())


class BenchmarkMediaWidget(QWidget):
    """Minimalistic media card used by the benchmark."""

    def __init__(
        self,
        parent: Optional[QWidget],
        *,
        variant: WidgetVariant,
        feed: SyntheticMediaFeed,
    ) -> None:
        super().__init__(parent)
        self._variant = variant
        self._feed = feed
        self._current_track: Optional[SyntheticMediaTrack] = None
        self._artwork_pixmap: Optional[QPixmap] = None
        self._pending_artwork_track_id: Optional[str] = None
        self._accent_colors: Tuple[QColor, QColor] = (
            QColor(130 + variant.display_index * 20, 180, 255, 180),
            QColor(80, 100, 255, 160),
        )
        self.setMinimumSize(360, 160)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._feed.register_widget(self)
        self.destroyed.connect(self._on_destroyed)
        self._scaled_artwork_cache: Optional[QPixmap] = None
        self._scaled_artwork_cache_key: Optional[Tuple[int, int, int, float]] = None

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(380, 180)

    def _on_destroyed(self) -> None:
        self._feed.unregister_widget(self)

    def set_track(self, track: SyntheticMediaTrack, artwork: Optional[QPixmap]) -> None:
        track_changed = (self._current_track is None) or (track.track_id != self._current_track.track_id)
        self._current_track = track
        if artwork is not None:
            self._artwork_pixmap = artwork
            self._pending_artwork_track_id = None
            self._invalidate_scaled_artwork_cache()
        elif track_changed:
            if track.has_artwork:
                self._pending_artwork_track_id = track.track_id
            else:
                self._artwork_pixmap = None
                self._pending_artwork_track_id = None
            self._invalidate_scaled_artwork_cache()
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._invalidate_scaled_artwork_cache()

    def paintEvent(self, event) -> None:  # noqa: N802
        with widget_paint_sample(self, "media.synthetic.paint"):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            full_rect = self.rect().adjusted(6, 6, -6, -6)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(12, 12, 20, 240))
            painter.drawRoundedRect(full_rect, 16, 16)

            content_rect = full_rect.adjusted(16, 16, -16, -16)
            artwork_width = min(160, max(96, full_rect.height() - 32))
            artwork_rect = QRect(
                content_rect.right() - artwork_width,
                content_rect.top(),
                artwork_width,
                artwork_width,
            )

            painter.save()
            painter.setBrush(self._accent_colors[0])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(artwork_rect, 14, 14)
            if self._artwork_pixmap is not None and not self._artwork_pixmap.isNull():
                try:
                    dpr = float(self.devicePixelRatioF())
                except Exception:
                    dpr = 1.0
                cache_key = (
                    self._artwork_pixmap.cacheKey(),
                    artwork_rect.width(),
                    artwork_rect.height(),
                    round(dpr, 3),
                )
                if (
                    self._scaled_artwork_cache is not None
                    and self._scaled_artwork_cache_key == cache_key
                    and not self._scaled_artwork_cache.isNull()
                ):
                    scaled = self._scaled_artwork_cache
                else:
                    scaled = self._artwork_pixmap.scaled(
                        int(artwork_rect.width() * dpr),
                        int(artwork_rect.height() * dpr),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    try:
                        scaled.setDevicePixelRatio(max(1.0, dpr))
                    except Exception:
                        pass
                    self._scaled_artwork_cache = scaled
                    self._scaled_artwork_cache_key = cache_key
                painter.setClipPath(QPainterPath())
                clip_path = QPainterPath()
                clip_path.addRoundedRect(artwork_rect, 14, 14)
                painter.setClipPath(clip_path)
                painter.drawPixmap(artwork_rect, scaled)
            painter.restore()

            header_font = QFont("Segoe UI", 11, QFont.Weight.Bold)
            painter.setFont(header_font)
            header_text = f"Display {self._variant.display_index + 1} · Media #{self._variant.instance_index + 1}"
            painter.setPen(QColor(210, 215, 225))
            painter.drawText(
                content_rect.adjusted(0, 0, -artwork_width - 16, -content_rect.height() + 24),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                header_text,
            )

            track = self._current_track
            body_rect = QRect(
                content_rect.left(),
                content_rect.top() + 28,
                content_rect.width() - artwork_width - 20,
                content_rect.height() - 28,
            )
            painter.setClipRect(body_rect)
            if track is None:
                painter.setPen(QColor(150, 150, 160))
                painter.setFont(QFont("Segoe UI", 10))
                painter.drawText(body_rect, Qt.AlignmentFlag.AlignVCenter, "Waiting for media data…")
                painter.setClipping(False)
                painter.restore()
                return

            title_font = QFont("Segoe UI", 16, QFont.Weight.DemiBold)
            painter.setFont(title_font)
            painter.setPen(QColor(245, 245, 250))
            painter.drawText(body_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, track.title)

            artist_font = QFont("Segoe UI", 12, QFont.Weight.Medium)
            painter.setFont(artist_font)
            painter.setPen(QColor(200, 200, 210))
            metrics = QFontMetrics(artist_font)
            title_height = QFontMetrics(title_font).height()
            artist_y = body_rect.top() + title_height + 6
            painter.drawText(
                QRect(body_rect.left(), artist_y, body_rect.width(), metrics.height()),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                f"{track.artist} — {track.album}",
            )

            status_font = QFont("Segoe UI", 10, QFont.Weight.Medium)
            painter.setFont(status_font)
            painter.setPen(self._accent_colors[1])
            status_lines = [f"State: {track.state.title()}"]
            if self._pending_artwork_track_id == track.track_id:
                status_lines.append("Artwork: loading…")
            elif not track.has_artwork:
                status_lines.append("Artwork: unavailable")
            elif self._artwork_pixmap is not None:
                status_lines.append("Artwork: ready")
            else:
                status_lines.append("Artwork: waiting")
            painter.drawText(
                QRect(body_rect.left(), artist_y + metrics.height() + 6, body_rect.width(), 60),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                " · ".join(status_lines),
            )

    def _invalidate_scaled_artwork_cache(self) -> None:
        self._scaled_artwork_cache = None
        self._scaled_artwork_cache_key = None

class BenchmarkWindow(QWidget):
    """Container widget that hosts whichever overlays are enabled."""

    def __init__(
        self,
        args: BenchmarkArgs,
        thread_manager: ThreadManager,
        weather_payload: Optional[Dict[str, Any]],
        reddit_posts: List[Dict[str, Any]],
    ) -> None:
        super().__init__()
        self._args = args
        self._thread_manager = thread_manager
        self._cadence_mode = args.cadence_mode
        self._weather_payload_seed = copy.deepcopy(weather_payload) if weather_payload else None
        self._reddit_payload_seed = copy.deepcopy(reddit_posts) if reddit_posts else None
        self.setWindowTitle("Synthetic Widget Benchmark Harness")

        self._display_stacks: List[DisplayStack] = []
        self._weather_widgets: List[WeatherWidget] = []
        self._reddit_widgets: List[RedditWidget] = []
        self._clock_widgets: List[ClockWidget] = []
        self._media_widgets: List["BenchmarkMediaWidget"] = []
        self._transition_widgets: List["TransitionStub"] = []
        self._media_feeds: List[SyntheticMediaFeed] = []
        self._thread_pool_stats: Dict[str, Dict[str, Any]] = {}
        self._thread_pool_last_warn: Dict[str, int] = {}
        if args.media_enabled:
            if args.media_feed_mode == "shared":
                self._media_feeds.append(SyntheticMediaFeed(self._thread_manager, args))
            else:
                self._media_feeds = [
                    SyntheticMediaFeed(self._thread_manager, args) for _ in range(self._args.display_count)
                ]

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(16)

        for display_index in range(self._args.display_count):
            column = QWidget(self)
            column_layout = QVBoxLayout(column)
            column_layout.setContentsMargins(8, 8, 8, 8)
            column_layout.setSpacing(10)

            stack = DisplayStack(
                container=column,
                weather_widgets=[],
                reddit_widgets=[],
                clock_widgets=[],
                media_widgets=[],
                transition_widget=None,
            )

            if self._args.weather_enabled:
                for weather_idx in range(self._args.weather_per_display):
                    widget = self._build_weather_widget(
                        weather_payload,
                        parent=column,
                        instance_index=weather_idx,
                    )
                    if widget is not None:
                        stack.weather_widgets.append(widget)
                        self._weather_widgets.append(widget)
                        column_layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignTop)

            if self._args.reddit_enabled:
                for reddit_idx in range(self._args.reddit_per_display):
                    widget = self._build_reddit_widget(
                        reddit_posts,
                        parent=column,
                    )
                    if widget is not None:
                        stack.reddit_widgets.append(widget)
                        self._reddit_widgets.append(widget)
                        column_layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignTop)

            if self._args.clock_enabled:
                for clock_idx in range(self._args.clock_per_display):
                    widget = self._build_clock_widget(parent=column)
                    if widget is not None:
                        stack.clock_widgets.append(widget)
                        self._clock_widgets.append(widget)
                        column_layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignTop)

            feed = self._get_media_feed(display_index)
            if feed is not None:
                for media_idx in range(self._args.media_per_display):
                    widget = self._build_media_widget(
                        parent=column,
                        variant=WidgetVariant(
                            display_index=display_index,
                            instance_index=media_idx,
                            widget_kind="media",
                        ),
                        feed=feed,
                    )
                    if widget is not None:
                        stack.media_widgets.append(widget)
                        self._media_widgets.append(widget)
                        column_layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignTop)

            if self._args.transitions_enabled:
                transition = TransitionStub(
                    parent=column,
                    logical_size=(self._args.transition_width, self._args.transition_height),
                    speed_scale=self._args.transition_speed_scale,
                )
                stack.transition_widget = transition
                self._transition_widgets.append(transition)
                column_layout.addWidget(transition, 0, Qt.AlignmentFlag.AlignTop)

            column.setLayout(column_layout)
            root_layout.addWidget(column)
            self._display_stacks.append(stack)

        self._configure_widget_cadence()

        if not args.show_window:
            # Keep the QWidget visible for Qt so paint events fire, but avoid presenting UI.
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.show()

        self._all_widgets: List[QWidget] = self._gather_all_widgets()

    @property
    def all_widgets(self) -> List[QWidget]:
        return self._all_widgets

    @property
    def thread_pool_stats(self) -> List[Dict[str, Any]]:
        stats: List[Dict[str, Any]] = []
        for pool_name, data in self._thread_pool_stats.items():
            stats.append(
                {
                    "pool": pool_name,
                    "max_workers": data.get("max_workers", 0),
                    "max_active": data.get("max_active", 0),
                    "max_active_frame": data.get("max_active_frame", 0),
                    "max_active_ratio": round(float(data.get("max_active_ratio", 0.0)), 3),
                    "saturated_frames": data.get("saturated_frames", 0),
                    "submitted": data.get("submitted", 0),
                    "completed": data.get("completed", 0),
                    "failed": data.get("failed", 0),
                }
            )
        stats.sort(key=lambda entry: entry["pool"])
        return stats

    def handle_frame_tick(self, frame_index: int) -> None:
        if self._weather_widgets and self._weather_payload_seed:
            if self._should_drive_weather_update(frame_index):
                updates = (
                    max(1, self._args.weather_updates_per_frame)
                    if self._cadence_mode == "stress"
                    else 1
                )
                for update_idx in range(updates):
                    payload = self._jitter_weather_payload(
                        self._weather_payload_seed,
                        frame_index,
                        update_index=update_idx,
                        updates_per_frame=max(1, updates),
                    )
                    for widget in self._weather_widgets:
                        widget_payload = copy.deepcopy(payload)
                        with widget_timer_sample(
                            widget,
                            "weather.widget.update",
                            interval_ms=self._args.interval_ms,
                        ):
                            widget._cached_data = widget_payload
                            widget._update_display(widget_payload)

        if self._reddit_widgets and self._reddit_payload_seed:
            if self._should_drive_reddit_update(frame_index):
                posts = self._synthesise_reddit_posts(frame_index)
                for widget in self._reddit_widgets:
                    try:
                        widget._cache_invalidated = True
                    except Exception:
                        pass
                    with widget_timer_sample(
                        widget,
                        "reddit.widget.prepare_posts",
                        interval_ms=self._args.interval_ms,
                    ):
                        widget._prepare_posts_for_display(
                            copy.deepcopy(posts),
                            force_refresh=(self._cadence_mode == "stress"),
                        )

        for clock_widget in self._clock_widgets:
            try:
                with widget_timer_sample(
                    clock_widget,
                    "clock.widget.tick",
                    interval_ms=self._args.interval_ms,
                ):
                    clock_widget._update_time()
            except Exception:
                pass

        if self._media_widgets:
            for feed in self._media_feeds:
                with widget_timer_sample(
                    feed,
                    "media.feed.tick",
                    interval_ms=self._args.interval_ms,
                ):
                    feed.tick(self._args.interval_ms)

        for transition in self._transition_widgets:
            with widget_timer_sample(transition, "transition.stub.advance", interval_ms=self._args.interval_ms):
                transition.advance()
        self._record_thread_pool_stats(frame_index)

    def _gather_all_widgets(self) -> List[QWidget]:
        widgets: List[QWidget] = []
        for stack in self._display_stacks:
            widgets.extend(stack.weather_widgets)
            widgets.extend(stack.reddit_widgets)
            widgets.extend(stack.clock_widgets)
            widgets.extend(stack.media_widgets)
            if stack.transition_widget is not None:
                widgets.append(stack.transition_widget)
        return [widget for widget in widgets if widget is not None]

    def _record_thread_pool_stats(self, frame_index: int) -> None:
        if not self._thread_manager:
            return
        snapshot = self._thread_manager.get_stats_snapshot()
        if not snapshot:
            return
        for pool_name, payload in snapshot.items():
            counts = dict(payload.get("stats") or {})
            submitted = int(counts.get("submitted", 0))
            completed = int(counts.get("completed", 0))
            failed = int(counts.get("failed", 0))
            active = max(0, submitted - completed - failed)
            max_workers = int(payload.get("max_workers", 0) or 0)
            entry = self._thread_pool_stats.setdefault(
                pool_name,
                {
                    "max_workers": max_workers,
                    "max_active": 0,
                    "max_active_frame": 0,
                    "max_active_ratio": 0.0,
                    "saturated_frames": 0,
                    "submitted": 0,
                    "completed": 0,
                    "failed": 0,
                },
            )
            entry["max_workers"] = max_workers
            entry["submitted"] = submitted
            entry["completed"] = completed
            entry["failed"] = failed
            if active > entry.get("max_active", 0):
                entry["max_active"] = active
                entry["max_active_frame"] = frame_index
                entry["max_active_ratio"] = (active / max_workers) if max_workers else 0.0
            if max_workers and active >= max_workers:
                entry["saturated_frames"] = entry.get("saturated_frames", 0) + 1
                last_warn = self._thread_pool_last_warn.get(pool_name, -10_000)
                if is_perf_metrics_enabled() and frame_index - last_warn >= 30:
                    logger.warning(
                        "[PERF_THREAD] pool=%s frame=%d active=%d capacity=%d submitted=%d completed=%d failed=%d",
                        pool_name,
                        frame_index,
                        active,
                        max_workers,
                        submitted,
                        completed,
                        failed,
                    )
                    self._thread_pool_last_warn[pool_name] = frame_index


    def _should_drive_weather_update(self, frame_index: int) -> bool:
        if self._cadence_mode == "stress":
            return True
        if frame_index == 0:
            return True
        return frame_index % _STEADY_WEATHER_REFRESH_FRAMES == 0

    def _should_drive_reddit_update(self, frame_index: int) -> bool:
        if self._cadence_mode == "stress":
            return True
        if frame_index == 0:
            return True
        return frame_index % _STEADY_REDDIT_REFRESH_FRAMES == 0

    def _configure_widget_cadence(self) -> None:
        mode = self._cadence_mode
        if mode == "stress":
            fast_interval = timedelta(milliseconds=max(1, self._args.interval_ms))
            for widget in self._weather_widgets:
                widget._display_refresh_interval = fast_interval
                widget._display_refresh_deadline = None
                widget._force_next_display_refresh = True
            for widget in self._reddit_widgets:
                widget._display_refresh_interval = fast_interval
                widget._display_refresh_deadline = None
                widget._force_next_display_refresh = True
        else:
            for widget in self._weather_widgets:
                widget._display_refresh_deadline = None
                widget._force_next_display_refresh = True
            for widget in self._reddit_widgets:
                widget._display_refresh_deadline = None
                widget._force_next_display_refresh = True

    def _jitter_weather_payload(
        self,
        seed: Dict[str, Any],
        frame_index: int,
        update_index: int = 0,
        updates_per_frame: int = 1,
    ) -> Dict[str, Any]:
        payload = copy.deepcopy(seed)
        wobble = math.sin((frame_index * updates_per_frame + update_index) / 4.0)
        payload["temperature"] = float(payload.get("temperature", 0.0)) + wobble * 0.6
        payload["humidity"] = int(min(100, max(0, payload.get("humidity", 50) + wobble * 5)))
        payload["precipitation_probability"] = int(
            min(100, max(0, payload.get("precipitation_probability", 30) + wobble * 7))
        )
        condition = payload.get("condition", "Clouds")
        payload["condition"] = f"{condition} · jitter {frame_index % 3}"
        if payload.get("forecast"):
            payload["forecast"] = f"{payload['forecast']} (frame {frame_index % 5})"
        weather_arr = payload.get("weather")
        if isinstance(weather_arr, list) and weather_arr:
            weather_arr = copy.deepcopy(weather_arr)
            weather_arr[0]["description"] = f"{weather_arr[0].get('description', '')} #{frame_index % 4}"
            payload["weather"] = weather_arr
        seq_index = frame_index * updates_per_frame + update_index
        payload["weather_code"] = _WEATHER_CODE_SEQUENCE[seq_index % len(_WEATHER_CODE_SEQUENCE)]
        payload["is_day"] = 1 if (seq_index % 6) < 3 else 0
        if isinstance(payload.get("weather"), list) and payload["weather"]:
            payload["weather"][0]["id"] = payload["weather_code"]
        return payload

    def _synthesise_reddit_posts(self, frame_index: int) -> List[RedditPost]:
        if not self._reddit_payload_seed:
            return []
        spread = max(1, self._args.reddit_limit)
        posts: List[RedditPost] = []
        for idx, item in enumerate(self._reddit_payload_seed[:spread]):
            jitter = ((frame_index + idx) % 11) - 5
            title = f"{item.get('title', 'Post')} · tick {frame_index % 7}"
            score = int(item.get("score", 0)) + jitter * 3
            created = float(item.get("created_utc", 0.0)) + frame_index * 15.0
            posts.append(
                RedditPost(
                    title=title,
                    url=str(item.get("url", "")),
                    score=score,
                    created_utc=created,
                )
            )
        return posts

    def _get_media_feed(self, display_index: int) -> Optional[SyntheticMediaFeed]:
        if not self._media_feeds:
            return None
        if len(self._media_feeds) == 1:
            return self._media_feeds[0]
        if 0 <= display_index < len(self._media_feeds):
            return self._media_feeds[display_index]
        return self._media_feeds[display_index % len(self._media_feeds)]

    def _build_weather_widget(
        self,
        payload: Optional[Dict[str, Any]],
        *,
        parent: Optional[QWidget] = None,
        instance_index: int = 0,
    ) -> Optional[WeatherWidget]:
        if payload is None:
            payload = DEFAULT_WEATHER_SAMPLE

        widget_parent = parent or self
        widget = WeatherWidget(parent=widget_parent, location=payload.get("location", "Nowhere"))
        widget.set_thread_manager(self._thread_manager)
        widget._enabled = True
        widget.set_show_details_row(self._args.weather_details)
        widget.set_show_forecast(self._args.weather_forecast)
        widget.set_animated_icon_alignment(self._args.weather_icon_alignment.upper())
        widget.set_animated_icon_enabled(self._args.weather_icon_animated)
        widget.set_desaturate_animated_icon(self._args.weather_icon_desaturate)

        # Ensure DPR aware layout before painting.
        widget.resize(widget.minimumSizeHint())
        widget.show()

        widget._cached_data = copy.deepcopy(payload)
        widget._has_displayed_valid_data = True
        widget._pending_first_show = False
        widget._show_details_row = self._args.weather_details
        widget._show_forecast = self._args.weather_forecast
        widget._update_display(widget._cached_data)
        width = max(widget.minimumWidth(), self._args.weather_width)
        height = max(widget.minimumHeight(), self._args.weather_height)
        widget.resize(width, height)
        widget.setMinimumSize(width, height)
        return widget

    def _build_reddit_widget(
        self,
        posts_data: List[Dict[str, Any]],
        *,
        parent: Optional[QWidget] = None,
    ) -> Optional[RedditWidget]:
        widget_parent = parent or self
        widget = RedditWidget(parent=widget_parent, subreddit="synthetic_bench")
        widget.set_thread_manager(self._thread_manager)
        widget._enabled = True
        widget._target_limit = max(1, self._args.reddit_limit)
        widget._limit = widget._target_limit
        widget.set_show_separators(self._args.reddit_separators)
        widget._setup_progressive_stages()

        posts = [
            RedditPost(
                title=str(item.get("title", "")),
                url=str(item.get("url", "")),
                score=int(item.get("score", 0)),
                created_utc=float(item.get("created_utc", 0.0)),
            )
            for item in posts_data[: widget._target_limit]
        ]
        widget._prepare_posts_for_display(posts)
        widget.show()
        return widget

    def _build_clock_widget(
        self,
        *,
        parent: Optional[QWidget] = None,
    ) -> Optional[ClockWidget]:
        widget_parent = parent or self
        widget = ClockWidget(parent=widget_parent)
        widget.set_thread_manager(self._thread_manager)
        widget._enabled = True
        hint = widget.sizeHint()
        if hint.isValid():
            widget.resize(hint)
            widget.setMinimumSize(hint)
        widget.show()
        return widget

    def _build_media_widget(
        self,
        *,
        parent: Optional[QWidget],
        variant: WidgetVariant,
        feed: SyntheticMediaFeed,
    ) -> Optional["BenchmarkMediaWidget"]:
        widget_parent = parent or self
        widget = BenchmarkMediaWidget(parent=widget_parent, variant=variant, feed=feed)
        widget.show()
        return widget


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark harness that exercises multiple overlay widgets with synthetic data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=240,
        help="Number of paint frames to drive before collecting metrics.",
    )
    parser.add_argument(
        "--interval-ms",
        type=int,
        default=16,
        help="Interval between frames in milliseconds.",
    )
    parser.add_argument(
        "--display-count",
        type=int,
        default=1,
        help="Number of simulated displays (each gets its own widget stack).",
    )
    parser.add_argument(
        "--weather",
        dest="weather_enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable or disable the weather widget entirely.",
    )
    parser.add_argument(
        "--weather-details",
        dest="weather_details",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Toggle the weather detail row icons/labels.",
    )
    parser.add_argument(
        "--weather-forecast",
        dest="weather_forecast",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Toggle the optional weather forecast paragraph.",
    )
    parser.add_argument(
        "--weather-width",
        type=int,
        default=620,
        help="Logical width to resize the weather widget to for paint stress.",
    )
    parser.add_argument(
        "--weather-height",
        type=int,
        default=320,
        help="Logical height to resize the weather widget to for paint stress.",
    )
    parser.add_argument(
        "--weather-updates-per-frame",
        type=int,
        default=3,
        help="Number of synthetic weather updates to inject per frame (simulates timers/animations).",
    )
    parser.add_argument(
        "--weather-per-display",
        type=int,
        default=1,
        help="How many weather widgets to instantiate per simulated display.",
    )
    parser.add_argument(
        "--weather-animated-icon",
        choices=["left", "right", "none"],
        default="right",
        help="Control animated icon alignment (NONE disables SVG rendering).",
    )
    parser.add_argument(
        "--weather-animate",
        dest="weather_icon_animated",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable or disable the weather condition icon animation while keeping the art visible.",
    )
    parser.add_argument(
        "--weather-desaturate-icon",
        dest="weather_icon_desaturate",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Render the weather condition icon in grayscale to match monochrome themes.",
    )
    parser.add_argument(
        "--weather-fixture",
        type=Path,
        default=None,
        help="Path to a weather JSON payload fixture.",
    )
    parser.add_argument(
        "--reddit",
        dest="reddit_enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable or disable the Reddit widget entirely.",
    )
    parser.add_argument(
        "--reddit-separators",
        dest="reddit_separators",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Toggle row separators in the Reddit list.",
    )
    parser.add_argument(
        "--reddit-limit",
        type=int,
        default=10,
        help="Number of Reddit posts to synthesize.",
    )
    parser.add_argument(
        "--reddit-per-display",
        type=int,
        default=1,
        help="How many Reddit widgets to instantiate per simulated display.",
    )
    parser.add_argument(
        "--clock",
        dest="clock_enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable or disable the clock widget in the synthetic stack.",
    )
    parser.add_argument(
        "--clock-per-display",
        type=int,
        default=1,
        help="How many clock widgets to instantiate per simulated display (when enabled).",
    )
    parser.add_argument(
        "--transitions",
        dest="transitions_enabled",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Simulate lightweight transition repaint/load per display.",
    )
    parser.add_argument(
        "--transition-speed-scale",
        type=float,
        default=1.0,
        help="Scale factor for transition animation speed (0.1 - 5.0).",
    )
    parser.add_argument(
        "--transition-width",
        type=int,
        default=320,
        help="Logical width of the synthetic transition widget.",
    )
    parser.add_argument(
        "--transition-height",
        type=int,
        default=180,
        help="Logical height of the synthetic transition widget.",
    )
    parser.add_argument(
        "--media",
        dest="media_enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable or disable the synthetic media card simulation.",
    )
    parser.add_argument(
        "--media-per-display",
        type=int,
        default=1,
        help="How many synthetic media widgets to instantiate per display.",
    )
    parser.add_argument(
        "--media-track-interval",
        type=int,
        default=1800,
        help="Approximate interval (ms) between simulated track changes.",
    )
    parser.add_argument(
        "--media-artwork-latency-min-ms",
        type=int,
        default=200,
        help="Minimum latency (ms) for synthetic artwork fetches.",
    )
    parser.add_argument(
        "--media-artwork-latency-max-ms",
        type=int,
        default=1200,
        help="Maximum latency (ms) for synthetic artwork fetches.",
    )
    parser.add_argument(
        "--media-feed-mode",
        choices=["shared", "per-display"],
        default="shared",
        help="Choose whether media widgets share a single feed or get per-display feeds.",
    )
    parser.add_argument(
        "--reddit-fixture",
        type=Path,
        default=None,
        help="Path to a Reddit posts JSON array fixture.",
    )
    parser.add_argument(
        "--cadence-mode",
        choices=["steady", "stress"],
        default="steady",
        help=(
            "Select the cadence model: 'steady' mimics real-world minute-scale refreshes "
            "while 'stress' forces every payload to render immediately."
        ),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Optional output path for JSONL metrics.",
    )
    parser.add_argument(
        "--show-window",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Show the benchmark window (useful when tweaking layout).",
    )
    return parser


def _collect_summary(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    grouped: Dict[tuple[str, str], Dict[str, Any]] = {}
    for record in records:
        widget = str(record.get("widget") or "").strip()
        kind = str(record.get("kind") or "").strip()
        if not widget or not kind:
            continue
        key = (widget, kind)
        entry = grouped.setdefault(
            key,
            {
                "widget": widget,
                "kind": kind,
                "calls": 0,
                "total_ms": 0.0,
                "max_ms": 0.0,
                "area_px": 0,
            },
        )
        calls = max(0, _safe_int(record.get("calls", 0)))
        avg_ms = max(0.0, _safe_float(record.get("avg_ms", 0.0)))
        max_ms = max(0.0, _safe_float(record.get("max_ms", 0.0)))
        area_px = max(entry["area_px"], _safe_int(record.get("area_px", 0)))
        if calls <= 0 and avg_ms > 0:
            # Some widgets log avg/max without call counts; assume single call.
            calls = 1
        entry["calls"] += calls
        entry["total_ms"] += avg_ms * max(1, calls)
        entry["max_ms"] = max(entry["max_ms"], max_ms)
        entry["area_px"] = area_px

    summary_rows: List[Dict[str, Any]] = []
    for entry in grouped.values():
        calls = max(1, entry["calls"])
        avg_ms = entry["total_ms"] / calls
        summary_rows.append(
            {
                "widget": entry["widget"],
                "kind": entry["kind"],
                "calls": entry["calls"],
                "avg_ms": round(avg_ms, 3),
                "max_ms": round(entry["max_ms"], 3),
                "area_px": entry["area_px"],
            }
        )

    summary_rows.sort(key=lambda row: (row["widget"], row["kind"]))
    return summary_rows


def _render_table(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return "No PERF_WIDGET metrics captured."
    headers = ["Widget", "Kind", "Calls", "Avg(ms)", "Max(ms)", "Area(px)"]
    table = [headers]
    for row in rows:
        table.append(
            [
                str(row.get("widget", "")),
                str(row.get("kind", "")),
                str(row.get("calls", "")),
                f"{row.get('avg_ms', '')}",
                f"{row.get('max_ms', '')}",
                str(row.get("area_px", "")),
            ]
        )
    widths = [max(len(line[idx]) for line in table) for idx in range(len(headers))]
    lines = []
    for line in table:
        padded = "  ".join(col.ljust(width) for col, width in zip(line, widths))
        lines.append(padded.rstrip())
    return "\n".join(lines)


def _render_thread_pool_table(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return "No thread pool stats captured."
    headers = [
        "Pool",
        "Max Workers",
        "Max Active",
        "Active Ratio",
        "Frame",
        "Saturated Frames",
        "Submitted",
        "Completed",
        "Failed",
    ]
    table = [headers]
    for row in rows:
        table.append(
            [
                str(row.get("pool", "")),
                str(row.get("max_workers", "")),
                str(row.get("max_active", "")),
                f"{row.get('max_active_ratio', 0.0):.2f}",
                str(row.get("max_active_frame", "")),
                str(row.get("saturated_frames", "")),
                str(row.get("submitted", "")),
                str(row.get("completed", "")),
                str(row.get("failed", "")),
            ]
        )
    widths = [max(len(line[idx]) for line in table) for idx in range(len(headers))]
    return "\n".join("  ".join(col.ljust(width) for col, width in zip(line, widths)).rstrip() for line in table)


def _write_jsonl(
    path: Path,
    *,
    raw_records: Sequence[Dict[str, Any]],
    summary_rows: Sequence[Dict[str, Any]],
    args: BenchmarkArgs,
    thread_pool_stats: Optional[Sequence[Dict[str, Any]]] = None,
    timer_stats: Optional[Dict[str, Any]] = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "type": "run",
                    "frames": args.frames,
                    "interval_ms": args.interval_ms,
                    "display_count": args.display_count,
                    "cadence_mode": args.cadence_mode,
                    "weather_enabled": args.weather_enabled,
                    "weather_details": args.weather_details,
                    "weather_forecast": args.weather_forecast,
                    "weather_width": args.weather_width,
                    "weather_height": args.weather_height,
                    "weather_updates_per_frame": args.weather_updates_per_frame,
                    "reddit_enabled": args.reddit_enabled,
                    "reddit_limit": args.reddit_limit,
                    "reddit_separators": args.reddit_separators,
                    "clock_enabled": args.clock_enabled,
                    "media_enabled": args.media_enabled,
                    "transitions_enabled": args.transitions_enabled,
                    "media_per_display": args.media_per_display,
                    "media_feed_mode": args.media_feed_mode,
                    "transition_speed_scale": args.transition_speed_scale,
                    "transition_width": args.transition_width,
                    "transition_height": args.transition_height,
                    "media_track_interval": args.media_track_interval,
                    "media_artwork_latency_min_ms": args.media_artwork_latency_min_ms,
                    "media_artwork_latency_max_ms": args.media_artwork_latency_max_ms,
                    "weather_per_display": args.weather_per_display,
                    "reddit_per_display": args.reddit_per_display,
                    "clock_per_display": args.clock_per_display,
                    "thread_pool_stats": list(thread_pool_stats or []),
                    "frame_driver_timer": timer_stats or {},
                }
            )
            + "\n"
        )
        for row in summary_rows:
            entry = {"type": "summary", **row}
            fh.write(json.dumps(entry) + "\n")
        for record in raw_records:
            fh.write(json.dumps({"type": "raw", **record}) + "\n")


def _parse_args() -> BenchmarkArgs:
    parser = _build_arg_parser()
    ns = parser.parse_args()
    return BenchmarkArgs(
        frames=ns.frames,
        interval_ms=ns.interval_ms,
        display_count=max(1, ns.display_count),
        weather_enabled=ns.weather_enabled,
        weather_details=ns.weather_details,
        weather_forecast=ns.weather_forecast,
        weather_icon_alignment=ns.weather_animated_icon,
        weather_icon_animated=ns.weather_icon_animated,
        weather_icon_desaturate=ns.weather_icon_desaturate,
        weather_fixture=ns.weather_fixture,
        weather_width=ns.weather_width,
        weather_height=ns.weather_height,
        weather_updates_per_frame=max(1, ns.weather_updates_per_frame),
        weather_per_display=max(0, ns.weather_per_display),
        reddit_enabled=ns.reddit_enabled,
        reddit_separators=ns.reddit_separators,
        reddit_limit=ns.reddit_limit,
        reddit_fixture=ns.reddit_fixture,
        reddit_per_display=max(0, ns.reddit_per_display),
        clock_enabled=ns.clock_enabled,
        clock_per_display=max(0, ns.clock_per_display),
        transitions_enabled=ns.transitions_enabled,
        transition_speed_scale=max(0.1, min(5.0, float(ns.transition_speed_scale))),
        transition_width=max(1, ns.transition_width),
        transition_height=max(1, ns.transition_height),
        media_enabled=ns.media_enabled,
        media_per_display=max(0, ns.media_per_display),
        media_track_interval=max(1, ns.media_track_interval),
        media_artwork_latency_min_ms=ns.media_artwork_latency_min_ms,
        media_artwork_latency_max_ms=ns.media_artwork_latency_max_ms,
        media_feed_mode=ns.media_feed_mode,
        cadence_mode=ns.cadence_mode,
        json_output=ns.json_output,
        show_window=ns.show_window,
    )


def main() -> int:
    args = _parse_args()
    _force_engine_running_flag()
    setup_logging(debug=False, verbose=False)
    collector = PerfLogCollector()
    root_logger = logging.getLogger()
    root_logger.addHandler(collector)

    weather_payload = (
        _load_fixture(args.weather_fixture, DEFAULT_WEATHER_SAMPLE)
        if args.weather_enabled
        else None
    )
    reddit_payload = (
        _load_fixture(args.reddit_fixture, DEFAULT_REDDIT_POSTS)
        if args.reddit_enabled
        else []
    )

    app = QApplication(sys.argv)
    thread_manager = ThreadManager()
    window = BenchmarkWindow(args, thread_manager, weather_payload, reddit_payload)
    if args.show_window:
        window.show()

    driver = FrameDriver(
        window.all_widgets,
        frames=args.frames,
        interval_ms=args.interval_ms,
        tick_callback=window.handle_frame_tick,
    )
    driver.finished.connect(app.quit)
    QTimer.singleShot(0, driver.start)
    app.exec()

    # Ensure perf buckets flush while our handler is still attached.
    flush_widget_perf_metrics(force=True)

    thread_manager.shutdown()
    root_logger.removeHandler(collector)

    summary_rows = _collect_summary(collector.records)
    thread_pool_rows = window.thread_pool_stats
    timer_stats = driver.interval_stats
    print(
        textwrap.dedent(
            """
            ================= Synthetic Widget Benchmark =================
            """
        ).strip()
    )
    print(_render_table(summary_rows))
    print()
    print("Thread Pool Saturation Summary")
    print(_render_thread_pool_table(thread_pool_rows))
    print()
    print("Frame Driver Timer Stats")
    print(
        textwrap.dedent(
            f"""
            Requested interval: {args.interval_ms}ms
            Samples: {timer_stats.get('samples', 0)}
            Avg: {timer_stats.get('avg_ms', 0.0)}ms, Min: {timer_stats.get('min_ms', 0.0)}ms, Max: {timer_stats.get('max_ms', 0.0)}ms
            Late frames (>{timer_stats.get('warn_threshold_ms', 0.0)}ms): {timer_stats.get('late_frames', 0)}
            """
        ).strip()
    )

    if args.json_output:
        _write_jsonl(
            args.json_output,
            raw_records=collector.records,
            summary_rows=summary_rows,
            args=args,
            thread_pool_stats=thread_pool_rows,
            timer_stats=timer_stats,
        )
        print(f"[BENCH] Raw perf metrics written to {args.json_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
