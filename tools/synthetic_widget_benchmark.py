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
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence
from datetime import timedelta

# Ensure repo root is importable before local dependencies.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from PySide6.QtCore import QObject, QTimer, Qt, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget  # noqa: E402

# Ensure perf metrics emit even when run outside the screensaver shell.
if os.getenv("SRPSS_PERF_METRICS", "").strip().lower() not in {"1", "true", "on", "yes"}:
    os.environ["SRPSS_PERF_METRICS"] = "1"

from core.logging.logger import setup_logging  # noqa: E402
from core.performance.widget_profiler import flush_widget_perf_metrics  # noqa: E402
from core.threading.manager import ThreadManager  # noqa: E402
from widgets.weather_widget import WeatherWidget  # noqa: E402
from widgets.reddit_widget import RedditWidget, RedditPost  # noqa: E402


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

    def start(self) -> None:
        if not self._widgets:
            QTimer.singleShot(0, self.finished.emit)
            return
        self._timer.start(self._interval)

    def _on_tick(self) -> None:
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


@dataclass
class BenchmarkArgs:
    frames: int
    interval_ms: int
    weather_enabled: bool
    weather_details: bool
    weather_forecast: bool
    weather_icon_alignment: str
    weather_fixture: Optional[Path]
    weather_width: int
    weather_height: int
    weather_updates_per_frame: int
    reddit_enabled: bool
    reddit_separators: bool
    reddit_limit: int
    reddit_fixture: Optional[Path]
    cadence_mode: str
    json_output: Optional[Path]
    show_window: bool


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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.weather_widget: Optional[WeatherWidget] = None
        self.reddit_widget: Optional[RedditWidget] = None

        if args.weather_enabled:
            self.weather_widget = self._build_weather_widget(weather_payload)
            if self.weather_widget:
                layout.addWidget(self.weather_widget, 0, Qt.AlignmentFlag.AlignTop)

        if args.reddit_enabled:
            self.reddit_widget = self._build_reddit_widget(reddit_posts)
            if self.reddit_widget:
                layout.addWidget(self.reddit_widget, 0, Qt.AlignmentFlag.AlignTop)

        self._configure_widget_cadence()

        if not args.show_window:
            # Keep the QWidget visible for Qt so paint events fire, but avoid presenting UI.
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.show()

    def handle_frame_tick(self, frame_index: int) -> None:
        if self.weather_widget and self._weather_payload_seed:
            if self._should_drive_weather_update(frame_index):
                updates = (
                    max(1, self._args.weather_updates_per_frame)
                    if self._cadence_mode == "stress"
                    else 1
                )
                base_payload = self._jitter_weather_payload(
                    self._weather_payload_seed,
                    frame_index,
                    0,
                    max(1, updates),
                )
                for update_idx in range(updates):
                    payload = base_payload
                    self.weather_widget._cached_data = payload
                    self.weather_widget._update_display(payload)
        if self.reddit_widget and self._reddit_payload_seed:
            if self._should_drive_reddit_update(frame_index):
                posts = self._synthesise_reddit_posts(frame_index)
                try:
                    self.reddit_widget._cache_invalidated = True
                except Exception:
                    pass
                self.reddit_widget._prepare_posts_for_display(
                    posts, force_refresh=(self._cadence_mode == "stress")
                )

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
            if self.weather_widget:
                self.weather_widget._display_refresh_interval = fast_interval
                self.weather_widget._display_refresh_deadline = None
                self.weather_widget._force_next_display_refresh = True
            if self.reddit_widget:
                self.reddit_widget._display_refresh_interval = fast_interval
                self.reddit_widget._display_refresh_deadline = None
                self.reddit_widget._force_next_display_refresh = True
        else:
            if self.weather_widget:
                self.weather_widget._display_refresh_deadline = None
                self.weather_widget._force_next_display_refresh = True
            if self.reddit_widget:
                self.reddit_widget._display_refresh_deadline = None
                self.reddit_widget._force_next_display_refresh = True

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

    def _build_weather_widget(
        self, payload: Optional[Dict[str, Any]]
    ) -> Optional[WeatherWidget]:
        if payload is None:
            payload = DEFAULT_WEATHER_SAMPLE

        widget = WeatherWidget(parent=self, location=payload.get("location", "Nowhere"))
        widget.set_thread_manager(self._thread_manager)
        widget._enabled = True
        widget.set_show_details_row(self._args.weather_details)
        widget.set_show_forecast(self._args.weather_forecast)
        widget.set_animated_icon_alignment(self._args.weather_icon_alignment.upper())

        # Ensure DPR aware layout before painting.
        widget.resize(widget.minimumSizeHint())
        widget.show()

        widget._cached_data = payload
        widget._has_displayed_valid_data = True
        widget._pending_first_show = False
        widget._show_details_row = self._args.weather_details
        widget._show_forecast = self._args.weather_forecast
        widget._update_display(payload)
        width = max(widget.minimumWidth(), self._args.weather_width)
        height = max(widget.minimumHeight(), self._args.weather_height)
        widget.resize(width, height)
        widget.setMinimumSize(width, height)
        return widget

    def _build_reddit_widget(
        self, posts_data: List[Dict[str, Any]]
    ) -> Optional[RedditWidget]:
        widget = RedditWidget(parent=self, subreddit="synthetic_bench")
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


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synthetic benchmark harness for weather + reddit widgets.",
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
        "--weather-animated-icon",
        choices=["left", "right", "none"],
        default="right",
        help="Control animated icon alignment (NONE disables SVG rendering).",
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
    summary: Dict[tuple[str, str], Dict[str, Any]] = {}
    for record in records:
        key = (str(record.get("widget")), str(record.get("kind")))
        summary[key] = record
    return list(summary.values())


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


def _write_jsonl(path: Path, records: Sequence[Dict[str, Any]]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")


def _parse_args() -> BenchmarkArgs:
    parser = _build_arg_parser()
    ns = parser.parse_args()
    return BenchmarkArgs(
        frames=ns.frames,
        interval_ms=ns.interval_ms,
        weather_enabled=ns.weather_enabled,
        weather_details=ns.weather_details,
        weather_forecast=ns.weather_forecast,
        weather_icon_alignment=ns.weather_animated_icon,
        weather_fixture=ns.weather_fixture,
        weather_width=ns.weather_width,
        weather_height=ns.weather_height,
        weather_updates_per_frame=max(1, ns.weather_updates_per_frame),
        reddit_enabled=ns.reddit_enabled,
        reddit_separators=ns.reddit_separators,
        reddit_limit=ns.reddit_limit,
        reddit_fixture=ns.reddit_fixture,
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
        [widget for widget in (window.weather_widget, window.reddit_widget) if widget],
        frames=args.frames,
        interval_ms=args.interval_ms,
    )
    driver.finished.connect(app.quit)
    QTimer.singleShot(0, driver.start)
    app.exec()

    # Ensure perf buckets flush while our handler is still attached.
    flush_widget_perf_metrics(force=True)

    thread_manager.shutdown()
    root_logger.removeHandler(collector)

    summary_rows = _collect_summary(collector.records)
    print(
        textwrap.dedent(
            """
            ================= Synthetic Widget Benchmark =================
            """
        ).strip()
    )
    print(_render_table(summary_rows))

    if args.json_output:
        _write_jsonl(args.json_output, collector.records)
        print(f"[BENCH] Raw perf metrics written to {args.json_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
