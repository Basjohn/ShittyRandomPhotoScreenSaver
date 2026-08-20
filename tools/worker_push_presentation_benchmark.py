"""Bounded production-path worker+push Slide + Bubble benchmark.

Runs one 15-second sample on exactly two physical displays. P0 is the common
Slide + deterministic Bubble workload. P1 adds the currently enabled primary
overlay/card widgets in static state; their provider lifecycles are not started.

``QRhiWidget.frameSubmitted`` is only an internal submission proxy. Capture the
process with PresentMon for physical-presentation gap evidence.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import threading
import time
import traceback
from typing import Any, Iterable

from PySide6.QtCore import QCoreApplication, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPixmap, QSurfaceFormat
from PySide6.QtWidgets import QApplication

if __package__:
    from .presentation_benchmark_core import (
        COMMON_BUBBLE_RECT_FRACTIONS,
        COMMON_SLIDE_SOURCE_SPEC,
        COMMON_TIMELINE,
        BenchmarkMetricsRecorder,
        build_common_bubble_feature_clip,
        common_workload_identity,
        parse_candidate_args,
        percentile,
        validate_window_screen_count,
    )
else:
    from presentation_benchmark_core import (
        COMMON_BUBBLE_RECT_FRACTIONS,
        COMMON_SLIDE_SOURCE_SPEC,
        COMMON_TIMELINE,
        BenchmarkMetricsRecorder,
        build_common_bubble_feature_clip,
        common_workload_identity,
        parse_candidate_args,
        percentile,
        validate_window_screen_count,
    )


CANDIDATE = "worker_push"
RUNTIME_GENERATION = 1
SCREEN_COUNT = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def bubble_rect(width: int, height: int) -> QRect:
    x, y, width_fraction, height_fraction = COMMON_BUBBLE_RECT_FRACTIONS
    return QRect(
        round(max(1, width) * x),
        round(max(1, height) * y),
        max(1, round(max(1, width) * width_fraction)),
        max(1, round(max(1, height) * height_fraction)),
    )


def wall_offset_frame(frame: Any, wall_origin_s: float) -> Any:
    return replace(
        frame,
        timestamp_us=max(
            0,
            round(float(wall_origin_s) * 1_000_000) + int(frame.timestamp_us),
        ),
    )


class FeatureCursor:
    def __init__(self, frames: Iterable[Any]) -> None:
        self.frames = tuple(frames)
        if not self.frames:
            raise ValueError("feature cursor requires frames")
        self.deadlines_ns = tuple(int(frame.timestamp_us) * 1_000 for frame in self.frames)

    def latest(self, elapsed_ns: int) -> tuple[int, Any] | None:
        index = bisect_right(self.deadlines_ns, int(elapsed_ns)) - 1
        return None if index < 0 else (index, self.frames[index])


def make_slide_pixmap(width: int, height: int, dpr: float, variant: str) -> QPixmap:
    spec = COMMON_SLIDE_SOURCE_SPEC[variant]
    dpr = max(1.0, float(dpr))
    pixel_width = max(1, round(width * dpr))
    pixel_height = max(1, round(height * dpr))
    image = QImage(pixel_width, pixel_height, QImage.Format.Format_ARGB32)
    image.fill(QColor(spec["background"]))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    band_count = int(COMMON_SLIDE_SOURCE_SPEC["band_count"])
    band_width = max(1, math.ceil(pixel_width / band_count))
    colors = spec["bands"]
    for index in range(band_count):
        painter.fillRect(
            index * band_width,
            0,
            band_width,
            pixel_height,
            QColor(colors[index % len(colors)]),
        )
    accent_width = max(
        2,
        round(pixel_width * COMMON_SLIDE_SOURCE_SPEC["accent_width_fraction"]),
    )
    for x in (pixel_width // 4, pixel_width * 3 // 4):
        painter.fillRect(x, 0, accent_width, pixel_height, QColor(spec["accent"]))
    painter.end()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def numeric_summary(values: Iterable[float], *, gap_counts: bool = False) -> dict[str, Any]:
    ordered = sorted(float(value) for value in values)
    result = {
        "count": len(ordered),
        "p50": percentile(ordered, 0.50),
        "p90": percentile(ordered, 0.90),
        "p95": percentile(ordered, 0.95),
        "p99": percentile(ordered, 0.99),
        "max": ordered[-1] if ordered else 0.0,
    }
    if gap_counts:
        result["counts_gte_ms"] = {
            str(threshold): sum(value >= threshold for value in ordered)
            for threshold in (12, 16, 25, 33, 50, 100)
        }
    return result


class ResourceSampler:
    """Passive one-second process/system/GPU sampling on the real I/O pool."""

    def __init__(self, thread_manager: Any, recorders: Iterable[BenchmarkMetricsRecorder]) -> None:
        from core.performance.usage_sampler import ProcessUsageCollector, WindowsGpuUsageCollector

        self._thread_manager = thread_manager
        self._recorders = tuple(recorders)
        self._process = ProcessUsageCollector()
        self._gpu = WindowsGpuUsageCollector(refresh_seconds=15.0)
        self._stop = threading.Event()
        self._done = threading.Event()
        self._lock = threading.Lock()
        self._samples: dict[str, list[float]] = defaultdict(list)
        self.statuses: list[str] = []

    def start(self) -> None:
        self._thread_manager.submit_io_task(
            self._run,
            task_id="presentation-benchmark-resource-sampler",
            category="benchmark.resource_sampling",
        )

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                process = self._process.collect()
                gpu = self._gpu.collect(process.pids)
                values = {
                    "system_cpu_pct": process.cpu_system_pct,
                    "process_cpu_pct": process.cpu_app_pct,
                    "gpu_busy_pct": gpu.busy_pct,
                    "memory_mb": process.rss_app_mb,
                    "vram_mb": gpu.vram_dedicated_mb,
                }
                with self._lock:
                    self.statuses.append(str(gpu.status))
                    for name, value in values.items():
                        if value is not None:
                            self._samples[name].append(float(value))
                for recorder in self._recorders:
                    recorder.record_resource_sample(**values)
                self._stop.wait(1.0)
        finally:
            self._gpu.close()
            self._done.set()

    def stop(self) -> bool:
        self._stop.set()
        return self._done.wait(3.0)

    def report(self) -> dict[str, Any]:
        with self._lock:
            return {
                "samples": {
                    name: numeric_summary(values)
                    for name, values in sorted(self._samples.items())
                },
                "gpu_statuses": list(self.statuses),
            }


class WorkerPushBenchmark:
    def __init__(self, app: QApplication, args: Any) -> None:
        self.app = app
        self.args = args
        self.gui_thread_id = threading.get_ident()
        self.workload = common_workload_identity()
        self.cursor = FeatureCursor(build_common_bubble_feature_clip().frames)
        self.origin_ns = 0
        self.wall_origin_s = 0.0
        self.started_utc = ""
        self.finished_utc = ""
        self.failure: str | None = None
        self.displays: list[Any] = []
        self.compositors: list[Any] = []
        self.recorders: list[BenchmarkMetricsRecorder] = []
        self.old_pixmaps: list[QPixmap] = []
        self.new_pixmaps: list[QPixmap] = []
        self.submissions_ns: list[list[int]] = [[], []]
        self.submission_thread_ids: list[set[int]] = [set(), set()]
        self.submission_callbacks: list[Any] = []
        self.screen_metadata: list[dict[str, Any]] = []
        self.phases_ns: dict[str, int] = {}
        self.phase_wall_utc: dict[str, str] = {}
        self.phase_lock = threading.Lock()
        self.ui_delivery_baseline = 0
        self.resource_manager: Any = None
        self.thread_manager: Any = None
        self.animation_manager: Any = None
        self.resource_sampler: ResourceSampler | None = None
        self.visualizer: Any = None
        self.engine: Any = None
        self.logical_runtime: Any = None
        self.logical_snapshot: dict[str, Any] = {}
        self.last_feature_index = -1
        self.last_playing: bool | None = None
        self.p1_settings: Any = None
        self.p1_widgets: list[dict[str, Any]] = []
        self._finishing = False

    def elapsed_ns(self) -> int:
        return max(0, time.perf_counter_ns() - self.origin_ns) if self.origin_ns else 0

    def mark(
        self,
        name: str,
        *,
        recorder_phase: str | None = None,
        screens: Iterable[int] = (0, 1),
    ) -> None:
        elapsed = self.elapsed_ns()
        wall = utc_now()
        with self.phase_lock:
            self.phases_ns.setdefault(name, elapsed)
            self.phase_wall_utc.setdefault(name, wall)
        if recorder_phase is not None:
            for index in screens:
                self.recorders[index].mark_phase(recorder_phase, elapsed)
        print(
            "[BENCHMARK][MARKER] "
            + json.dumps(
                {"run_id": self.args.run_id, "name": name, "elapsed_ns": elapsed, "wall_utc": wall},
                sort_keys=True,
            ),
            flush=True,
        )

    def setup(self) -> None:
        from core.animation.animator import AnimationManager
        from core.resources.manager import ResourceManager
        from core.threading.manager import ThreadManager, ThreadPoolType

        screens = list(QGuiApplication.screens())
        validate_window_screen_count(SCREEN_COUNT, len(screens))
        if len(screens) != SCREEN_COUNT:
            raise ValueError(f"benchmark requires exactly two physical screens; Qt reported {len(screens)}")
        source_components = {
            key: value for key, value in self.workload.items() if key != "workload_sha256"
        }
        for index, screen in enumerate(screens):
            geometry = screen.geometry()
            self.recorders.append(
                BenchmarkMetricsRecorder(
                    candidate=CANDIDATE,
                    population=self.args.population,
                    display=(
                        f"screen{index}:{screen.name() or index}:"
                        f"{geometry.width()}x{geometry.height()}"
                    ),
                    target_hz=self.args.target_hz[index],
                    completion_signal="qrhiwidget.frameSubmitted",
                    source_sha256=self.workload["workload_sha256"],
                    source_components=source_components,
                )
            )
        self.resource_manager = ResourceManager()
        self.thread_manager = ThreadManager(
            config={ThreadPoolType.IO: 2, ThreadPoolType.COMPUTE: 4},
            resource_manager=self.resource_manager,
        )
        self.ui_delivery_baseline = int(
            self.thread_manager.get_frame_delivery_snapshot().get("ui_delivered", 0)
        )
        self.animation_manager = AnimationManager(
            fps=max(round(rate) for rate in self.args.target_hz),
            resource_manager=self.resource_manager,
            owner="benchmark:worker_push",
            runtime_generation=RUNTIME_GENERATION,
        )
        for index, screen in enumerate(screens):
            self._create_display(index, screen)
        self._create_visualizer()
        if self.args.population == "P1":
            self._add_static_p1_population()
        self.resource_sampler = ResourceSampler(self.thread_manager, self.recorders)

    def _create_display(self, index: int, screen: Any) -> None:
        from rendering.display_modes import DisplayMode
        from rendering.display_widget import DisplayWidget

        display = DisplayWidget(
            screen_index=index,
            display_mode=DisplayMode.FILL,
            settings_manager=None,
            resource_manager=self.resource_manager,
            thread_manager=self.thread_manager,
            runtime_generation=RUNTIME_GENERATION,
        )
        geometry = QRect(screen.geometry())
        display._screen = screen
        display._device_pixel_ratio = float(screen.devicePixelRatio())
        display._target_fps = round(self.args.target_hz[index])
        display.setGeometry(geometry)
        display.setWindowTitle(
            f"SRPSS Benchmark {CANDIDATE} {self.args.population} {self.args.run_id} screen{index}"
        )
        self.screen_metadata.append(
            {
                "index": index,
                "name": str(screen.name() or index),
                "geometry": list(geometry.getRect()),
                "reported_refresh_hz": float(screen.refreshRate()),
                "target_hz": float(self.args.target_hz[index]),
                "device_pixel_ratio": display._device_pixel_ratio,
                "window_title": display.windowTitle(),
            }
        )
        display._ensure_gl_compositor()
        compositor = display._gl_compositor
        if compositor is None:
            raise RuntimeError(f"screen{index} did not create GLCompositorWidget")
        compositor._desync_delay_ms = 0
        compositor.setGeometry(0, 0, geometry.width(), geometry.height())
        old_pixmap = make_slide_pixmap(
            geometry.width(), geometry.height(), display._device_pixel_ratio, "old"
        )
        new_pixmap = make_slide_pixmap(
            geometry.width(), geometry.height(), display._device_pixel_ratio, "new"
        )
        display.current_pixmap = old_pixmap
        display.previous_pixmap = old_pixmap
        display._seed_pixmap = old_pixmap
        display._updates_blocked_until_seed = False
        compositor.set_base_pixmap(old_pixmap)

        def _submitted(index: int = index) -> None:
            if self.origin_ns:
                elapsed = self.elapsed_ns()
                self.submissions_ns[index].append(elapsed)
                self.submission_thread_ids[index].add(threading.get_ident())
                self.recorders[index].record_completed_frame(
                    consumed_ns=elapsed,
                    completed_ns=elapsed,
                )

        compositor.frameSubmitted.connect(_submitted)
        self.submission_callbacks.append(_submitted)
        self.displays.append(display)
        self.compositors.append(compositor)
        self.old_pixmaps.append(old_pixmap)
        self.new_pixmaps.append(new_pixmap)

    def _create_visualizer(self) -> None:
        from widgets.spotify_visualizer.logical_runtime import LatestStateMailbox, VisualizerLogicalRuntime
        from widgets.spotify_visualizer.replay_runtime import ReplayBeatEngine, _apply_authored_preset_zero
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

        display = self.displays[1]
        widget = SpotifyVisualizerWidget(display, bar_count=32, initial_mode="bubble")
        widget.setGeometry(bubble_rect(display.width(), display.height()))
        engine = ReplayBeatEngine(widget._bar_count)
        engine.set_thread_manager(self.thread_manager)
        widget._engine = engine
        widget._bind_engine_aliases(engine)
        widget._thread_manager = self.thread_manager
        widget._runtime_generation = RUNTIME_GENERATION
        widget._logical_mailbox = LatestStateMailbox()
        widget._logical_present_pending = False
        widget._enabled = True
        widget._spotify_playing = True
        widget._has_seen_media = True
        widget._has_pushed_first_frame = False
        widget._waiting_for_fresh_engine_frame = True
        widget._waiting_for_fresh_frame = True
        widget._startup_reveal_pending = True
        widget._startup_reveal_not_before_ts = 0.0
        widget._startup_require_playing_before_reveal = False
        widget._startup_idle_reveal_requires_authoritative_media = False
        widget._startup_has_authoritative_media_update = True
        widget.presentation_fade().reset()
        widget.hide()
        _apply_authored_preset_zero(widget, "bubble")
        engine.reset_smoothing_state()
        widget._track_engine_generation(engine)
        engine.set_playback_state(True)
        runtime = VisualizerLogicalRuntime(
            step=self._logical_step,
            interval_s=1.0 / COMMON_TIMELINE.logical_hz,
            generation=RUNTIME_GENERATION,
            name="srpss-benchmark-visualizer-logical",
        )
        widget._logical_runtime = runtime
        display.spotify_visualizer_widget = widget
        self.visualizer = widget
        self.engine = engine
        self.logical_runtime = runtime

    def _add_static_p1_population(self) -> None:
        """Create real enabled cards without starting any provider lifecycle."""

        from core.settings.settings_manager import SettingsManager
        from rendering.widget_setup_all import (
            _create_factory_widgets,
            _ensure_factory_registry,
            _resolve_card_border_width,
            _resolve_widgets_config,
        )
        from widgets.base_overlay_widget import BaseOverlayWidget

        settings = SettingsManager()
        widgets_config = _resolve_widgets_config(settings)
        BaseOverlayWidget.set_global_border_width(_resolve_card_border_width(widgets_config))
        shadows = widgets_config.get("shadows", {}) if isinstance(widgets_config, dict) else {}
        self.p1_settings = settings
        for index, display in enumerate(self.displays):
            manager = display._widget_manager
            if manager is None:
                raise RuntimeError(f"screen{index} has no WidgetManager")
            display.settings_manager = settings
            _ensure_factory_registry(manager, settings, self.thread_manager)
            created: dict[str, Any] = {}
            _create_factory_widgets(manager, created, widgets_config, shadows, index)
            for attr_name, widget in created.items():
                initialized = bool(widget.initialize()) if hasattr(widget, "initialize") else True
                if attr_name.startswith("clock") and hasattr(widget, "_update_time"):
                    widget._update_time()
                if hasattr(widget, "_update_position"):
                    widget._update_position()
                widget.show()
                widget.raise_()
                geometry = widget.geometry()
                self.p1_widgets.append(
                    {
                        "screen": index,
                        "attribute": attr_name,
                        "class": type(widget).__name__,
                        "initialized": initialized,
                        "geometry": list(geometry.getRect()),
                        "intended_visible": True,
                        "provider_lifecycle_started": False,
                    }
                )

    def start(self) -> None:
        self.started_utc = utc_now()
        self.wall_origin_s = time.time()
        self.origin_ns = time.perf_counter_ns()
        self.mark(
            "first_intentional_visible_frame",
            recorder_phase="first_intentional_visible_frame",
        )
        for display, compositor in zip(self.displays, self.compositors):
            display.show()
            compositor.show()
            display.raise_()
        self.resource_sampler.start()
        QTimer.singleShot(0, self._validate_topology)
        QTimer.singleShot(1000, self._start_workload)
        QTimer.singleShot(15000, self.finish)
        print(
            "[BENCHMARK] start "
            + json.dumps(
                {
                    "candidate": CANDIDATE,
                    "population": self.args.population,
                    "run_id": self.args.run_id,
                    "pid": os.getpid(),
                    "output": str(self.args.output),
                    "physical_evidence_valid": False,
                },
                sort_keys=True,
            ),
            flush=True,
        )

    def _validate_topology(self) -> None:
        screens = list(QGuiApplication.screens())
        for index, display in enumerate(self.displays):
            handle = display.windowHandle()
            if index >= len(screens) or handle is None or handle.screen() is not screens[index]:
                self.abort(f"screen{index} window is not on its requested physical screen")
                return

    def _start_workload(self) -> None:
        from core.animation.types import EasingCurve

        self.mark("slide_start", recorder_phase="slide_start")
        duration_ms = int(COMMON_SLIDE_SOURCE_SPEC["duration_ms"])
        for index, compositor in enumerate(self.compositors):
            width = max(1, compositor.width())

            def _finished(index: int = index) -> None:
                self.mark(
                    f"slide_end_screen{index}",
                    recorder_phase="slide_end",
                    screens=(index,),
                )
                # Continue the compositor's existing passive paint window for
                # the settled Bubble/idle portion after Slide finalizes it.
                self.compositors[index]._begin_paint_metrics("benchmark_hold")

            started = compositor.start_slide(
                self.old_pixmaps[index],
                self.new_pixmaps[index],
                old_start=QPoint(0, 0),
                old_end=QPoint(-width, 0),
                new_start=QPoint(width, 0),
                new_end=QPoint(0, 0),
                duration_ms=duration_ms,
                easing=EasingCurve.LINEAR,
                animation_manager=self.animation_manager,
                on_finished=_finished,
            )
            if not started:
                self.abort(f"screen{index} production Slide refused to start")
                return
        if not self.logical_runtime.start():
            self.abort("VisualizerLogicalRuntime refused to start")

    def _logical_step(self, _now_s: float) -> None:
        selected = self.cursor.latest(self.elapsed_ns())
        if selected is None:
            return
        index, relative_frame = selected
        if index == self.last_feature_index:
            return
        skipped = max(0, index - self.last_feature_index - 1)
        self.last_feature_index = index
        frame = wall_offset_frame(relative_frame, self.wall_origin_s)
        previous_playing = self.last_playing
        if previous_playing is None or bool(frame.playing) != previous_playing:
            self.last_playing = bool(frame.playing)
            self.visualizer._spotify_playing = self.last_playing
            self.engine.set_playback_state(self.last_playing)
            if previous_playing is not None:
                phase = "synthetic_resume" if self.last_playing else "synthetic_pause"
                self.mark(phase, recorder_phase=phase)
        if self.engine.accept_feature_frame(frame):
            from widgets.spotify_visualizer import tick_pipeline

            payload = tick_pipeline.logical_tick(self.visualizer)
        else:
            payload = None
        completed_ns = self.elapsed_ns()
        self.recorders[1].record_logical_step(
            completed_ns=completed_ns,
            scheduled_ns=int(relative_frame.timestamp_us) * 1_000,
            skipped_deadlines=skipped,
            failed=payload is None,
        )
        with self.phase_lock:
            first_logical_missing = "bubble_first_logical_frame" not in self.phases_ns
        if payload is not None and first_logical_missing:
            self.mark(
                "bubble_first_logical_frame",
                recorder_phase="bubble_first_logical_frame",
                screens=(1,),
            )

    def abort(self, reason: str) -> None:
        if self._finishing:
            return
        self.failure = reason
        print(f"[BENCHMARK] INVALID {reason}", flush=True)
        self.finish()

    def _display_report(self, index: int, compositor: Any) -> dict[str, Any]:
        submission_times = list(self.submissions_ns[index])
        submission_gaps = [
            (right - left) / 1_000_000.0
            for left, right in zip(submission_times, submission_times[1:])
        ]
        paint_metrics = getattr(compositor, "_paint_metrics", None)
        timer_metrics = getattr(compositor, "_render_timer_metrics", None)
        gpu_queries = getattr(compositor, "_gpu_timer_queries", None)
        common_report = self.recorders[index].report(elapsed_ns=self.elapsed_ns())
        history = getattr(compositor, "_gpu_assoc_paint_history", None)
        paint_samples = list(history) if history else (
            list(paint_metrics.samples) if paint_metrics is not None else []
        )
        paint_durations = [sample.paint_duration_ms for sample in paint_samples]
        paint_intervals = [
            sample.paint_interval_ms
            for sample in paint_samples
            if sample.paint_interval_ms is not None
        ]
        request_ages = [
            sample.request_to_paint_age_ms
            for sample in paint_samples
            if sample.request_to_paint_age_ms is not None
        ]
        production_paint = {
            "frames": len(paint_samples),
            "interval_ms": numeric_summary(paint_intervals, gap_counts=True),
            "paint_ms": numeric_summary(paint_durations),
            "request_age_ms": numeric_summary(request_ages),
        }
        if timer_metrics is not None:
            requested = int(timer_metrics.wakeup_count)
            accepted = int(timer_metrics.frame_count)
            common_report["counts"]["requested_opportunities"] = requested
            common_report["counts"]["accepted_requests"] = accepted
            common_report["rates"]["request_acceptance_pct"] = (
                accepted / requested * 100.0 if requested else 0.0
            )
        common_report["timing_ms"]["paint"] = production_paint["paint_ms"]
        common_report["timing_ms"]["request_age"] = production_paint["request_age_ms"]
        return {
            "common_metrics": common_report,
            "screen": index,
            "target_hz": self.args.target_hz[index],
            "frame_submitted": {
                "stage": "graphics_submission",
                "physical_presentation_evidence": False,
                "frames": len(submission_times),
                "gap_ms": numeric_summary(submission_gaps, gap_counts=True),
                "callback_thread_ids": sorted(self.submission_thread_ids[index]),
            },
            "production_paint_metrics": production_paint,
            "production_render_timer": (
                {
                    "wakeup_count": timer_metrics.wakeup_count,
                    "accepted_updates": timer_metrics.frame_count,
                    "pending_skips": timer_metrics.pending_skip_count,
                    "stall_count": timer_metrics.stall_count,
                    "max_dt_ms": timer_metrics.max_dt * 1000.0,
                }
                if timer_metrics is not None
                else None
            ),
            "gpu_timer_window": (
                gpu_queries.consume_window() if gpu_queries is not None else None
            ),
        }

    def finish(self) -> None:
        if self._finishing:
            return
        self._finishing = True
        self.mark("stop_report", recorder_phase="stop_report")
        cleanup_errors: list[str] = []
        try:
            if self.logical_runtime is not None:
                if not self.logical_runtime.stop(timeout_s=2.0):
                    cleanup_errors.append("logical runtime did not join")
                self.logical_snapshot = self.logical_runtime.describe()
                self.recorders[1].set_logical_runtime_totals(
                    steps=int(self.logical_snapshot.get("steps", 0)),
                    skipped_deadlines=int(self.logical_snapshot.get("skipped_deadlines", 0)),
                    slow_steps=int(self.logical_snapshot.get("slow_steps", 0)),
                    failures=int(self.logical_snapshot.get("step_failures", 0)),
                )
        except Exception as exc:
            cleanup_errors.append(f"logical runtime: {exc}")
        try:
            if self.resource_sampler is not None and not self.resource_sampler.stop():
                cleanup_errors.append("resource sampler did not stop")
        except Exception as exc:
            cleanup_errors.append(f"resource sampler: {exc}")
        try:
            ui_delivered = int(
                self.thread_manager.get_frame_delivery_snapshot().get("ui_delivered", 0)
            )
            gui_callbacks = max(0, ui_delivered - self.ui_delivery_baseline)
            for recorder in self.recorders:
                recorder.gui_callback_count = gui_callbacks
        except Exception as exc:
            cleanup_errors.append(f"GUI callback snapshot: {exc}")
        display_reports = [
            self._display_report(index, compositor)
            for index, compositor in enumerate(self.compositors)
        ]
        settings_sha256 = None
        if self.p1_settings is not None:
            path = Path(self.p1_settings.get_storage_path())
            if path.is_file():
                settings_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        for compositor, callback in zip(self.compositors, self.submission_callbacks):
            try:
                compositor.frameSubmitted.disconnect(callback)
                compositor.stop_rendering(reason="benchmark_complete")
            except Exception as exc:
                cleanup_errors.append(f"compositor cleanup: {exc}")
        for display in self.displays:
            try:
                display.cleanup_runtime(reason="benchmark_complete")
                display.hide()
                display.deleteLater()
            except Exception as exc:
                cleanup_errors.append(f"display cleanup: {exc}")
        try:
            if self.animation_manager is not None:
                self.animation_manager.cleanup()
            if self.thread_manager is not None and not self.thread_manager.shutdown(wait=True, timeout=3.0):
                cleanup_errors.append("ThreadManager did not shut down")
            if self.resource_manager is not None:
                self.resource_manager.cleanup_all()
        except Exception as exc:
            cleanup_errors.append(f"manager cleanup: {exc}")

        self.finished_utc = utc_now()
        self.failure = self.failure or (" | ".join(cleanup_errors) if cleanup_errors else None)
        report = {
            "schema_version": 1,
            "candidate": CANDIDATE,
            "population": self.args.population,
            "run_id": self.args.run_id,
            "load_label": self.args.load_label,
            "pid": os.getpid(),
            "started_utc": self.started_utc,
            "finished_utc": self.finished_utc,
            "elapsed_ns": self.elapsed_ns(),
            "valid_internal_run": self.failure is None,
            "invalid_reason": self.failure,
            "cleanup_errors": cleanup_errors,
            "workload": self.workload,
            "phases_ns": dict(self.phases_ns),
            "phase_wall_utc": dict(self.phase_wall_utc),
            "gui_thread_id": self.gui_thread_id,
            "logical_runtime": self.logical_snapshot,
            "resources": self.resource_sampler.report() if self.resource_sampler else {},
            "screens": self.screen_metadata,
            "displays": display_reports,
            "p1_population": {
                "policy": "enabled production factory widgets, initialized/static, providers not activated",
                "settings_sha256": settings_sha256,
                "widgets": self.p1_widgets,
            },
            "external_physical_evidence": {
                "required": True,
                "accepted_signal": "external.presentmon.displayed",
                "internal_frame_submitted_is_physical": False,
                "correlate_by": {
                    "pid": os.getpid(),
                    "run_id": self.args.run_id,
                    "window_titles": [display.windowTitle() for display in self.displays],
                },
            },
        }
        self.args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.args.output.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(report, handle, allow_nan=False, indent=2, sort_keys=True)
                handle.write("\n")
        except Exception as exc:
            self.failure = self.failure or f"report write failed: {exc}"
            print(f"[BENCHMARK] report_error={exc}", flush=True)
        print(
            f"[BENCHMARK] done valid={self.failure is None} output={self.args.output} "
            "physical_evidence_valid=False",
            flush=True,
        )
        self.app.exit(0 if self.failure is None else 1)


def configure_qt() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL, True)
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    from rendering.gl_format import build_surface_format

    surface_format, _ = build_surface_format(reason="worker_push_presentation_benchmark")
    QSurfaceFormat.setDefaultFormat(surface_format)


def main(argv: list[str] | None = None) -> int:
    args = parse_candidate_args(
        sys.argv[1:] if argv is None else argv,
        description=__doc__,
    )
    from core.logging.logger import setup_logging

    setup_logging(perf=True, gpu_timing=True, usage=True)
    configure_qt()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("SRPSSWorkerPushBenchmark")
    benchmark = WorkerPushBenchmark(app, args)
    try:
        benchmark.setup()
        benchmark.start()
    except Exception as exc:
        traceback.print_exc()
        benchmark.failure = f"setup failed: {type(exc).__name__}: {exc}"
        print(f"[BENCHMARK] INVALID {benchmark.failure}", flush=True)
        return 2
    return int(app.exec())


if __name__ == "__main__":
    sys.exit(main())
