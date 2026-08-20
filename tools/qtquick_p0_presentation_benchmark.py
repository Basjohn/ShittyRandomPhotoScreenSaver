"""Threaded standalone-QQuickWindow implementation of the common P0 workload.

Runs the same bounded 15-second deterministic Slide + Bubble workload as the
worker+push reference.  The only independently presented surfaces are two
top-level QQuickWindows, one per physical display.  PresentMon remains the
display-boundary evidence source.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict, deque
import ctypes
from dataclasses import replace
from datetime import datetime, timezone
import json
import math
import os
import sys
import threading
import time
import traceback
from types import SimpleNamespace
from typing import Any, Iterable


# These must be selected before importing Qt.
os.environ["QSG_RENDER_LOOP"] = "threaded"
os.environ.setdefault("QSG_INFO", "1")
_logging_rules = os.environ.get("QT_LOGGING_RULES", "")
os.environ["QT_LOGGING_RULES"] = (
    (_logging_rules + ";" if _logging_rules else "")
    + "qt.scenegraph.general=true;qt.rhi.general=true"
)

import numpy as np  # noqa: E402
from OpenGL import GL as gl  # noqa: E402
from PySide6.QtCore import QObject, QRect, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QSurfaceFormat  # noqa: E402
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

if __package__:
    from .presentation_benchmark_core import (  # noqa: E402
        COMMON_BUBBLE_RECT_FRACTIONS,
        COMMON_LOGICAL_HZ,
        COMMON_SLIDE_SOURCE_SPEC,
        COMMON_TIMELINE,
        BenchmarkMetricsRecorder,
        TargetPacerState,
        build_common_bubble_feature_clip,
        common_workload_identity,
        parse_candidate_args,
        validate_window_screen_count,
    )
else:
    from presentation_benchmark_core import (  # noqa: E402
        COMMON_BUBBLE_RECT_FRACTIONS,
        COMMON_LOGICAL_HZ,
        COMMON_SLIDE_SOURCE_SPEC,
        COMMON_TIMELINE,
        BenchmarkMetricsRecorder,
        TargetPacerState,
        build_common_bubble_feature_clip,
        common_workload_identity,
        parse_candidate_args,
        validate_window_screen_count,
    )


CANDIDATE = "qtquick_threaded"
SCREEN_COUNT = 2
RUNTIME_GENERATION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def elapsed_ns(origin_ns: int) -> int:
    return max(0, time.perf_counter_ns() - int(origin_ns)) if origin_ns else 0


def bubble_rect(width: int, height: int) -> tuple[int, int, int, int]:
    x, y, width_fraction, height_fraction = COMMON_BUBBLE_RECT_FRACTIONS
    return (
        round(max(1, width) * x),
        round(max(1, height) * y),
        max(1, round(max(1, width) * width_fraction)),
        max(1, round(max(1, height) * height_fraction)),
    )


def wall_offset_frame(frame: Any, wall_origin_s: float) -> Any:
    return replace(
        frame,
        timestamp_us=(
            round(float(wall_origin_s) * 1_000_000) + int(frame.timestamp_us)
        ),
    )


class FeatureCursor:
    def __init__(self, frames: Iterable[Any]) -> None:
        self.frames = tuple(frames)
        self.deadlines_ns = tuple(int(frame.timestamp_us) * 1_000 for frame in self.frames)
        if not self.frames:
            raise ValueError("feature cursor requires frames")

    def latest(self, now_ns: int) -> tuple[int, Any] | None:
        index = bisect_right(self.deadlines_ns, int(now_ns)) - 1
        return None if index < 0 else (index, self.frames[index])


class LatestCaptureSink:
    """One-slot GUI-commit to render-thread handoff; latest state wins."""

    def __init__(self, logical_timestamp: Any) -> None:
        self._logical_timestamp = logical_timestamp
        self._lock = threading.Lock()
        self._latest: tuple[dict[str, Any], int] | None = None

    def append(self, state: dict[str, Any]) -> None:
        with self._lock:
            self._latest = (state, int(self._logical_timestamp()))

    def latest(self) -> tuple[dict[str, Any], int] | None:
        with self._lock:
            return self._latest


class ResourceSampler:
    """Passive one-second process/system/GPU samples."""

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
            task_id="qtquick-p0-resource-sampler",
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
                "sample_counts": {
                    name: len(values) for name, values in sorted(self._samples.items())
                },
                "gpu_statuses": list(self.statuses),
            }


class TargetFramePacer(QObject):
    """GUI-side deadline pacer; never requeues from render completion."""

    def __init__(
        self,
        window: QQuickWindow,
        renderer: "QuickP0Renderer",
        target_hz: float,
        origin: Any,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._renderer = renderer
        self._origin = origin
        self.state = TargetPacerState(float(target_hz))
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._service)

    def start(self) -> None:
        self.state.start(0)
        self._service()

    def stop(self) -> None:
        self._timer.stop()

    def _service(self) -> None:
        now_ns = elapsed_ns(self._origin())
        decision = self.state.consume(now_ns)
        if decision.due_opportunities:
            self._renderer.note_request(now_ns)
            self._window.update()
        self._timer.start(decision.next_delay_ms)


def _compile_program(vertex_source: str, fragment_source: str, label: str) -> int:
    def _shader(source: str, shader_type: int) -> int:
        shader = gl.glCreateShader(shader_type)
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)
        if not gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS):
            info = gl.glGetShaderInfoLog(shader)
            gl.glDeleteShader(shader)
            raise RuntimeError(f"{label} shader compile failed: {info}")
        return int(shader)

    vertex = _shader(vertex_source, gl.GL_VERTEX_SHADER)
    fragment = _shader(fragment_source, gl.GL_FRAGMENT_SHADER)
    program = gl.glCreateProgram()
    gl.glAttachShader(program, vertex)
    gl.glAttachShader(program, fragment)
    gl.glLinkProgram(program)
    gl.glDeleteShader(vertex)
    gl.glDeleteShader(fragment)
    if not gl.glGetProgramiv(program, gl.GL_LINK_STATUS):
        info = gl.glGetProgramInfoLog(program)
        gl.glDeleteProgram(program)
        raise RuntimeError(f"{label} program link failed: {info}")
    return int(program)


def _rgba(text: str) -> tuple[int, int, int, int]:
    return QColor(text).getRgb()


def _slide_pixels(width: int, height: int, variant: str) -> np.ndarray:
    spec = COMMON_SLIDE_SOURCE_SPEC[variant]
    pixels = np.empty((height, width, 4), dtype=np.uint8)
    pixels[:, :] = _rgba(spec["background"])
    count = int(COMMON_SLIDE_SOURCE_SPEC["band_count"])
    band_width = max(1, math.ceil(width / count))
    colors = tuple(spec["bands"])
    for index in range(count):
        left = index * band_width
        right = min(width, left + band_width)
        if left < width:
            pixels[:, left:right] = _rgba(colors[index % len(colors)])
    accent_width = max(
        2,
        round(width * COMMON_SLIDE_SOURCE_SPEC["accent_width_fraction"]),
    )
    for left in (width // 4, width * 3 // 4):
        pixels[:, left : min(width, left + accent_width)] = _rgba(spec["accent"])
    return pixels


class QuickP0Renderer(QObject):
    """Render-thread OpenGL underlay for one standalone QQuickWindow."""

    ready = Signal(int)
    failed = Signal(int, str)
    phaseObserved = Signal(int, str, object)

    def __init__(
        self,
        window: QQuickWindow,
        index: int,
        recorder: BenchmarkMetricsRecorder,
        capture_sink: LatestCaptureSink,
        bubble_style: dict[str, Any],
    ) -> None:
        super().__init__()
        self.window = window
        self.index = int(index)
        self.recorder = recorder
        self.capture_sink = capture_sink
        self.bubble_style = bubble_style
        self.gui_thread_id = threading.get_ident()
        self.render_thread_id: int | None = None
        self.actual_graphics_api: str | None = None
        self.origin_ns = 0
        self.error: str | None = None
        self._ready_emitted = False
        self._slide_end_emitted = False
        self._bubble_physical_emitted = False
        self._request_lock = threading.Lock()
        self._latest_request_ns: int | None = None
        self._pending_frames: deque[tuple[int, float, int | None, int | None]] = deque()
        self._quad_vao = 0
        self._quad_vbo = 0
        self._slide_program = 0
        self._slide_uniforms: dict[str, int] = {}
        self._slide_helper: Any = None
        self._bubble_program = 0
        self._bubble_uniforms: dict[str, int] = {}
        self._old_texture = 0
        self._new_texture = 0
        self._bubble_state = SimpleNamespace()

        # Draw after Qt Quick's own render pass so its clear cannot erase the
        # candidate workload. QQuickWindow still owns the context and swap.
        window.afterRendering.connect(self._render, Qt.ConnectionType.DirectConnection)
        window.frameSwapped.connect(self._frame_swapped, Qt.ConnectionType.DirectConnection)
        window.sceneGraphInvalidated.connect(
            self._cleanup_gl,
            Qt.ConnectionType.DirectConnection,
        )

    def set_origin(self, origin_ns: int) -> None:
        self.origin_ns = int(origin_ns)

    def note_request(self, requested_ns: int) -> None:
        with self._request_lock:
            self._latest_request_ns = int(requested_ns)

    def _take_request(self) -> int | None:
        with self._request_lock:
            requested = self._latest_request_ns
            self._latest_request_ns = None
            return requested

    def _render(self) -> None:
        if self.error is not None:
            return
        try:
            thread_id = threading.get_ident()
            if self.render_thread_id is None:
                self.render_thread_id = thread_id
                self.recorder.set_thread_identity(
                    gui_thread_id=self.gui_thread_id,
                    render_thread_id=thread_id,
                )
                print(
                    f"[QUICK][screen{self.index}] render_thread_id={thread_id} "
                    f"gui_thread_id={self.gui_thread_id} "
                    f"threaded={'YES' if thread_id != self.gui_thread_id else 'NO'}",
                    flush=True,
                )

            self.window.beginExternalCommands()
            paint_started = time.perf_counter_ns()
            try:
                if not self._slide_program:
                    self._initialize_gl()
                requested_ns = self._take_request()
                consumed = elapsed_ns(self.origin_ns)
                captured = self.capture_sink.latest() if self.index == 1 else None
                logical_ns = captured[1] if captured is not None else None
                self._draw(consumed, captured[0] if captured is not None else None)
                paint_ms = (time.perf_counter_ns() - paint_started) / 1_000_000.0
                if self.origin_ns:
                    self._pending_frames.append(
                        (consumed, paint_ms, requested_ns, logical_ns)
                    )
                if not self._ready_emitted:
                    self._ready_emitted = True
                    self.ready.emit(self.index)
            finally:
                self.window.endExternalCommands()
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
            self.failed.emit(self.index, self.error)

    def _frame_swapped(self) -> None:
        if not self.origin_ns or not self._pending_frames:
            return
        consumed, paint_ms, requested_ns, logical_ns = self._pending_frames.popleft()
        completed = elapsed_ns(self.origin_ns)
        self.recorder.record_completed_frame(
            consumed_ns=consumed,
            completed_ns=completed,
            paint_ms=paint_ms,
            requested_ns=requested_ns,
            logical_published_ns=logical_ns,
        )

    def _initialize_gl(self) -> None:
        from rendering.gl_programs.slide_program import SlideProgram
        from widgets.spotify_visualizer.renderers import bubble as bubble_renderer
        from widgets.spotify_visualizer.shaders import (
            SHARED_VERTEX_SHADER,
            load_fragment_shader,
        )

        graphics_api = self.window.rendererInterface().graphicsApi()
        self.actual_graphics_api = getattr(graphics_api, "name", str(graphics_api))
        if graphics_api != QSGRendererInterface.GraphicsApi.OpenGL:
            raise RuntimeError(
                f"Qt Quick selected {self.actual_graphics_api}, expected OpenGL"
            )

        vertices = np.array(
            [
                -1.0,
                -1.0,
                0.0,
                0.0,
                1.0,
                -1.0,
                1.0,
                0.0,
                -1.0,
                1.0,
                0.0,
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
            ],
            dtype=np.float32,
        )
        self._quad_vao = int(gl.glGenVertexArrays(1))
        self._quad_vbo = int(gl.glGenBuffers(1))
        gl.glBindVertexArray(self._quad_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._quad_vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_STATIC_DRAW)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(
            0,
            2,
            gl.GL_FLOAT,
            False,
            16,
            ctypes.c_void_p(0),
        )
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(
            1,
            2,
            gl.GL_FLOAT,
            False,
            16,
            ctypes.c_void_p(8),
        )
        gl.glBindVertexArray(0)

        self._slide_helper = SlideProgram()
        self._slide_program = self._slide_helper.create_program()
        self._slide_uniforms = self._slide_helper.cache_uniforms(self._slide_program)
        bubble_source = load_fragment_shader("bubble")
        if not bubble_source:
            raise RuntimeError("production Bubble shader source is unavailable")
        self._bubble_program = _compile_program(
            SHARED_VERTEX_SHADER,
            bubble_source,
            "Bubble",
        )
        names = {
            "u_resolution",
            "u_dpr",
            "u_viewport_origin_px",
            "u_border_width",
            "u_fade",
            "u_time",
            "u_rainbow_hue_offset",
            *bubble_renderer.get_uniform_names(),
        }
        self._bubble_uniforms = {
            name: int(gl.glGetUniformLocation(self._bubble_program, name))
            for name in names
        }

        dpr = max(1.0, float(self.window.effectiveDevicePixelRatio()))
        width = max(1, round(self.window.width() * dpr))
        height = max(1, round(self.window.height() * dpr))
        self._old_texture = self._upload_texture(_slide_pixels(width, height, "old"))
        self._new_texture = self._upload_texture(_slide_pixels(width, height, "new"))

        self._bubble_state = SimpleNamespace(
            _energy_bands=SimpleNamespace(bass=0.0, mid=0.0, high=0.0, overall=0.0),
            _playing=True,
            _bubble_ghost_alpha=float(self.bubble_style["ghost_alpha"]),
            _bubble_ghosting_enabled=bool(self.bubble_style["ghosting_enabled"]),
            _bubble_count=0,
            _bubble_pos_data=[],
            _bubble_extra_data=[],
            _bubble_trail_data=[],
            _bubble_trail_strength=0.0,
            _bubble_tail_opacity=0.0,
            _bubble_specular_direction=str(self.bubble_style["specular_direction"]),
            _bubble_gradient_direction=str(self.bubble_style["gradient_direction"]),
            _bubble_outline_color=QColor(self.bubble_style["outline_color"]),
            _bubble_specular_color=QColor(self.bubble_style["specular_color"]),
            _bubble_gradient_light=QColor(self.bubble_style["gradient_light"]),
            _bubble_gradient_dark=QColor(self.bubble_style["gradient_dark"]),
            _bubble_pop_color=QColor(self.bubble_style["pop_color"]),
        )

    @staticmethod
    def _upload_texture(pixels: np.ndarray) -> int:
        texture = int(gl.glGenTextures(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        height, width, _channels = pixels.shape
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D,
            0,
            gl.GL_RGBA8,
            width,
            height,
            0,
            gl.GL_RGBA,
            gl.GL_UNSIGNED_BYTE,
            pixels,
        )
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        return texture

    def _draw(self, now_ns: int, bubble_state: dict[str, Any] | None) -> None:
        dpr = max(1.0, float(self.window.effectiveDevicePixelRatio()))
        width = max(1, round(self.window.width() * dpr))
        height = max(1, round(self.window.height() * dpr))
        state = COMMON_TIMELINE.state_at(now_ns)
        progress = float(state.slide_progress)
        slide_state = SimpleNamespace(progress=progress)
        self._slide_helper.render(
            self._slide_program,
            self._slide_uniforms,
            (width, height),
            self._old_texture,
            self._new_texture,
            slide_state,
            self._quad_vao,
            old_rect=(-progress, 0.0, 1.0, 1.0),
            new_rect=(1.0 - progress, 0.0, 1.0, 1.0),
        )

        if not self._slide_end_emitted and now_ns >= COMMON_TIMELINE.marker_ns("slide_end"):
            self._slide_end_emitted = True
            self.phaseObserved.emit(self.index, "slide_end", now_ns)

        if self.index == 1 and state.bubble_active and bubble_state is not None:
            self._draw_bubble(width, height, dpr, now_ns, bubble_state)
            if not self._bubble_physical_emitted:
                self._bubble_physical_emitted = True
                self.phaseObserved.emit(
                    self.index,
                    "bubble_first_physical_frame",
                    now_ns,
                )

    def _draw_bubble(
        self,
        framebuffer_width: int,
        framebuffer_height: int,
        dpr: float,
        now_ns: int,
        captured: dict[str, Any],
    ) -> None:
        from widgets.spotify_visualizer.renderers import bubble as bubble_renderer

        logical_rect = bubble_rect(self.window.width(), self.window.height())
        x, y, width, height = logical_rect
        x_px = round(x * dpr)
        width_px = max(1, round(width * dpr))
        height_px = max(1, round(height * dpr))
        y_px = max(0, framebuffer_height - round((y + height) * dpr))

        gl.glEnable(gl.GL_SCISSOR_TEST)
        gl.glScissor(x_px, y_px, width_px, height_px)
        gl.glClearColor(0.035, 0.055, 0.085, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        gl.glDisable(gl.GL_SCISSOR_TEST)

        energy = captured.get("energy", {})
        bubble = captured.get("bubble", {})
        state = self._bubble_state
        state._energy_bands = SimpleNamespace(
            bass=float(energy.get("bass", 0.0)),
            mid=float(energy.get("mid", 0.0)),
            high=float(energy.get("high", 0.0)),
            overall=float(energy.get("overall", 0.0)),
        )
        state._playing = bool(captured.get("playing", False))
        state._bubble_count = int(bubble.get("count", 0))
        state._bubble_pos_data = bubble.get("positions", [])
        state._bubble_extra_data = bubble.get("extra", [])
        state._bubble_trail_data = bubble.get("trails", [])
        state._bubble_trail_strength = float(bubble.get("trail_strength", 0.0))
        state._bubble_tail_opacity = float(bubble.get("tail_opacity", 0.0))

        gl.glViewport(x_px, y_px, width_px, height_px)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glUseProgram(self._bubble_program)
        uniforms = self._bubble_uniforms
        gl.glUniform2f(uniforms["u_resolution"], float(width), float(height))
        gl.glUniform1f(uniforms["u_dpr"], float(dpr))
        gl.glUniform2f(uniforms["u_viewport_origin_px"], float(x_px), float(y_px))
        gl.glUniform1f(uniforms["u_border_width"], 2.0)
        gl.glUniform1f(uniforms["u_fade"], 1.0)
        gl.glUniform1f(uniforms["u_time"], now_ns / 1_000_000_000.0)
        gl.glUniform1f(uniforms["u_rainbow_hue_offset"], 0.0)
        bubble_renderer.upload_uniforms(gl, uniforms, state)
        gl.glBindVertexArray(self._quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)
        gl.glDisable(gl.GL_BLEND)
        gl.glViewport(0, 0, framebuffer_width, framebuffer_height)

    def _cleanup_gl(self) -> None:
        try:
            if self._old_texture:
                gl.glDeleteTextures([self._old_texture])
                self._old_texture = 0
            if self._new_texture:
                gl.glDeleteTextures([self._new_texture])
                self._new_texture = 0
            if self._slide_program:
                gl.glDeleteProgram(self._slide_program)
                self._slide_program = 0
            if self._bubble_program:
                gl.glDeleteProgram(self._bubble_program)
                self._bubble_program = 0
            if self._quad_vbo:
                gl.glDeleteBuffers(1, [self._quad_vbo])
                self._quad_vbo = 0
            if self._quad_vao:
                gl.glDeleteVertexArrays(1, [self._quad_vao])
                self._quad_vao = 0
        except Exception:
            traceback.print_exc()


class QtQuickP0Benchmark(QObject):
    def __init__(self, app: QApplication, args: Any) -> None:
        super().__init__()
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
        self.phases_ns: dict[str, int] = {}
        self.phase_wall_utc: dict[str, str] = {}
        self.phase_lock = threading.Lock()
        self.recorders: list[BenchmarkMetricsRecorder] = []
        self.windows: list[QQuickWindow] = []
        self.renderers: list[QuickP0Renderer] = []
        self.pacers: list[TargetFramePacer] = []
        self.screen_metadata: list[dict[str, Any]] = []
        self.ready_screens: set[int] = set()
        self.resource_manager: Any = None
        self.thread_manager: Any = None
        self.resource_sampler: ResourceSampler | None = None
        self.replay_display: Any = None
        self.visualizer: Any = None
        self.engine: Any = None
        self.logical_runtime: Any = None
        self.logical_snapshot: dict[str, Any] = {}
        self.capture_sink = LatestCaptureSink(lambda: self.latest_logical_ns)
        self.latest_logical_ns = 0
        self.last_feature_index = -1
        self.last_playing: bool | None = None
        self.ui_delivery_baseline = 0
        self._finishing = False

    def elapsed_ns(self) -> int:
        return elapsed_ns(self.origin_ns)

    def mark(
        self,
        name: str,
        *,
        recorder_phase: str | None = None,
        screens: Iterable[int] = (0, 1),
        observed_ns: int | None = None,
    ) -> None:
        observed = self.elapsed_ns() if observed_ns is None else int(observed_ns)
        wall = utc_now()
        with self.phase_lock:
            if name in self.phases_ns:
                return
            self.phases_ns[name] = observed
            self.phase_wall_utc[name] = wall
        if recorder_phase is not None:
            for index in screens:
                self.recorders[index].mark_phase(recorder_phase, observed)
        print(
            "[QUICK][MARKER] "
            + json.dumps(
                {
                    "run_id": self.args.run_id,
                    "name": name,
                    "elapsed_ns": observed,
                    "wall_utc": wall,
                },
                sort_keys=True,
            ),
            flush=True,
        )

    def setup(self) -> None:
        from core.resources.manager import ResourceManager
        from core.threading.manager import ThreadManager, ThreadPoolType
        from widgets.spotify_visualizer.logical_runtime import (
            LatestStateMailbox,
            VisualizerLogicalRuntime,
        )
        from widgets.spotify_visualizer.replay_runtime import _prepare_widget

        screens = list(QGuiApplication.screens())
        validate_window_screen_count(SCREEN_COUNT, len(screens))
        if len(screens) != SCREEN_COUNT:
            raise ValueError(
                f"benchmark requires exactly two physical screens; Qt reported {len(screens)}"
            )

        source_components = {
            key: value for key, value in self.workload.items() if key != "workload_sha256"
        }
        for index, screen in enumerate(screens):
            geometry = screen.geometry()
            self.recorders.append(
                BenchmarkMetricsRecorder(
                    candidate=CANDIDATE,
                    population="P0",
                    display=(
                        f"screen{index}:{screen.name() or index}:"
                        f"{geometry.width()}x{geometry.height()}"
                    ),
                    target_hz=self.args.target_hz[index],
                    completion_signal="qquickwindow.frameSwapped",
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

        display, widget, engine = _prepare_widget("bubble")
        display.logical_pushes = self.capture_sink
        engine.set_thread_manager(self.thread_manager)
        widget._thread_manager = self.thread_manager
        widget._runtime_generation = RUNTIME_GENERATION
        widget._logical_mailbox = LatestStateMailbox()
        widget._logical_present_pending = False
        runtime = VisualizerLogicalRuntime(
            step=self._logical_step,
            interval_s=1.0 / COMMON_LOGICAL_HZ,
            generation=RUNTIME_GENERATION,
            name="srpss-qtquick-benchmark-logical",
        )
        widget._logical_runtime = runtime
        self.replay_display = display
        self.visualizer = widget
        self.engine = engine
        self.logical_runtime = runtime
        bubble_style = {
            "ghost_alpha": float(getattr(widget, "_bubble_ghost_alpha", 0.0)),
            "ghosting_enabled": bool(
                getattr(widget, "_bubble_ghosting_enabled", False)
            ),
            "specular_direction": str(
                getattr(widget, "_bubble_specular_direction", "top_left")
            ),
            "gradient_direction": str(
                getattr(widget, "_bubble_gradient_direction", "top")
            ),
            "outline_color": QColor(widget._bubble_outline_color),
            "specular_color": QColor(widget._bubble_specular_color),
            "gradient_light": QColor(widget._bubble_gradient_light),
            "gradient_dark": QColor(widget._bubble_gradient_dark),
            "pop_color": QColor(widget._bubble_pop_color),
        }

        self.resource_sampler = ResourceSampler(self.thread_manager, self.recorders)
        for index, screen in enumerate(screens):
            self._create_window(index, screen, bubble_style)

    def _create_window(self, index: int, screen: Any, bubble_style: dict[str, Any]) -> None:
        geometry = QRect(screen.geometry())
        window = QQuickWindow()
        window.setScreen(screen)
        window.setTitle(
            f"SRPSS Benchmark {CANDIDATE} P0 {self.args.run_id} screen{index}"
        )
        window.setFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        window.setGeometry(geometry)
        window.setColor(Qt.GlobalColor.black)
        renderer = QuickP0Renderer(
            window,
            index,
            self.recorders[index],
            self.capture_sink,
            bubble_style,
        )
        renderer.ready.connect(self._renderer_ready, Qt.ConnectionType.QueuedConnection)
        renderer.failed.connect(self._renderer_failed, Qt.ConnectionType.QueuedConnection)
        renderer.phaseObserved.connect(
            self._renderer_phase,
            Qt.ConnectionType.QueuedConnection,
        )
        pacer = TargetFramePacer(
            window,
            renderer,
            self.args.target_hz[index],
            lambda: self.origin_ns,
        )
        self.windows.append(window)
        self.renderers.append(renderer)
        self.pacers.append(pacer)
        self.screen_metadata.append(
            {
                "index": index,
                "name": str(screen.name() or index),
                "geometry": list(geometry.getRect()),
                "reported_refresh_hz": float(screen.refreshRate()),
                "target_hz": float(self.args.target_hz[index]),
                "device_pixel_ratio": float(screen.devicePixelRatio()),
                "window_title": window.title(),
                "surface": "QQuickWindow",
            }
        )
        window.show()
        window.update()

    def _renderer_ready(self, index: int) -> None:
        self.ready_screens.add(int(index))
        if len(self.ready_screens) != SCREEN_COUNT or self.origin_ns:
            return
        if self.replay_display.testAttribute(Qt.WidgetAttribute.WA_WState_Created):
            self.abort("hidden logical QWidget unexpectedly created a native window")
            return
        screens = list(QGuiApplication.screens())
        for screen_index, window in enumerate(self.windows):
            if window.screen() is not screens[screen_index]:
                self.abort(f"screen{screen_index} QQuickWindow is on the wrong physical screen")
                return

        self.started_utc = utc_now()
        self.wall_origin_s = time.time()
        self.origin_ns = time.perf_counter_ns()
        for renderer in self.renderers:
            renderer.set_origin(self.origin_ns)
        self.mark(
            "first_intentional_visible_frame",
            recorder_phase="first_intentional_visible_frame",
        )
        for window in self.windows:
            window.update()
        for pacer in self.pacers:
            pacer.start()
        self.resource_sampler.start()
        QTimer.singleShot(1000, self._start_workload)
        QTimer.singleShot(15000, self.finish)
        print(
            "[QUICK] start "
            + json.dumps(
                {
                    "candidate": CANDIDATE,
                    "population": "P0",
                    "run_id": self.args.run_id,
                    "pid": os.getpid(),
                    "output": str(self.args.output),
                    "render_loop": os.environ.get("QSG_RENDER_LOOP"),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    def _renderer_failed(self, index: int, reason: str) -> None:
        self.abort(f"screen{index} renderer failed: {reason}")

    def _renderer_phase(self, index: int, name: str, observed_ns: object) -> None:
        observed = int(observed_ns)
        if name == "slide_end":
            self.mark(
                f"slide_end_screen{index}",
                recorder_phase="slide_end",
                screens=(index,),
                observed_ns=observed,
            )
        elif name == "bubble_first_physical_frame":
            self.mark(
                name,
                recorder_phase=name,
                screens=(index,),
                observed_ns=observed,
            )

    def _start_workload(self) -> None:
        self.mark("slide_start", recorder_phase="slide_start")
        if not self.logical_runtime.start():
            self.abort("VisualizerLogicalRuntime refused to start")

    def _logical_step(self, _deadline_s: float) -> None:
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

        accepted = self.engine.accept_feature_frame(frame)
        payload = None
        if accepted:
            from widgets.spotify_visualizer import tick_pipeline

            self.latest_logical_ns = self.elapsed_ns()
            payload = tick_pipeline.logical_tick(self.visualizer)
        completed = self.elapsed_ns()
        self.recorders[1].record_logical_step(
            completed_ns=completed,
            scheduled_ns=int(relative_frame.timestamp_us) * 1_000,
            skipped_deadlines=skipped,
            failed=payload is None,
        )
        if payload is not None:
            self.mark(
                "bubble_first_logical_frame",
                recorder_phase="bubble_first_logical_frame",
                screens=(1,),
            )

    def abort(self, reason: str) -> None:
        if self._finishing:
            return
        self.failure = str(reason)
        print(f"[QUICK] INVALID {reason}", flush=True)
        if self.origin_ns:
            self.finish()
        else:
            self.app.exit(2)

    def finish(self) -> None:
        if self._finishing:
            return
        self._finishing = True
        self.mark("stop_report", recorder_phase="stop_report")
        cleanup_errors: list[str] = []
        for pacer in self.pacers:
            pacer.stop()
        try:
            if self.logical_runtime is not None:
                if not self.logical_runtime.stop(timeout_s=2.0):
                    cleanup_errors.append("logical runtime did not join")
                self.logical_snapshot = self.logical_runtime.describe()
                self.recorders[1].set_logical_runtime_totals(
                    steps=int(self.logical_snapshot.get("steps", 0)),
                    skipped_deadlines=int(
                        self.logical_snapshot.get("skipped_deadlines", 0)
                    ),
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

        render_thread_ids = [renderer.render_thread_id for renderer in self.renderers]
        if any(thread_id is None for thread_id in render_thread_ids):
            cleanup_errors.append("render thread identity missing")
        if any(thread_id == self.gui_thread_id for thread_id in render_thread_ids):
            cleanup_errors.append("Qt Quick render loop ran on the GUI thread")
        if os.environ.get("QSG_RENDER_LOOP") != "threaded":
            cleanup_errors.append("QSG_RENDER_LOOP is not threaded")
        for renderer in self.renderers:
            if renderer.error:
                cleanup_errors.append(f"screen{renderer.index}: {renderer.error}")

        reports = []
        for index, recorder in enumerate(self.recorders):
            report = recorder.report(elapsed_ns=self.elapsed_ns())
            report["request_semantics"] = (
                "target opportunities and issued QQuickWindow.update calls; "
                "QQuickWindow exposes no acceptance callback"
            )
            pacing = self.pacers[index].state
            report["counts"]["requested_opportunities"] = (
                pacing.requested_opportunities
            )
            report["counts"]["accepted_requests"] = None
            report["rates"]["request_acceptance_pct"] = None
            report["issued_update_requests"] = pacing.paced_requests
            report["pacing_skipped_deadlines"] = pacing.skipped_deadlines
            report["screen_index"] = index
            reports.append(report)

        try:
            if self.visualizer is not None:
                self.visualizer.cleanup()
            if self.thread_manager is not None and not self.thread_manager.shutdown(
                wait=True,
                timeout=3.0,
            ):
                cleanup_errors.append("ThreadManager did not shut down")
            if self.resource_manager is not None:
                self.resource_manager.cleanup_all()
        except Exception as exc:
            cleanup_errors.append(f"logical owner cleanup: {exc}")

        self.finished_utc = utc_now()
        self.failure = self.failure or (" | ".join(cleanup_errors) if cleanup_errors else None)
        report = {
            "schema_version": 1,
            "candidate": CANDIDATE,
            "population": "P0",
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
            "screens": self.screen_metadata,
            "displays": reports,
            "logical_runtime": self.logical_snapshot,
            "resources": self.resource_sampler.report() if self.resource_sampler else {},
            "quick_scene_graph": {
                "requested_render_loop": os.environ.get("QSG_RENDER_LOOP"),
                "requested_graphics_api": "OpenGL",
                "actual_graphics_apis": [
                    renderer.actual_graphics_api for renderer in self.renderers
                ],
                "gui_thread_id": self.gui_thread_id,
                "render_thread_ids": render_thread_ids,
                "all_render_threads_distinct_from_gui": all(
                    thread_id is not None and thread_id != self.gui_thread_id
                    for thread_id in render_thread_ids
                ),
                "top_level_presented_windows": SCREEN_COUNT,
                "presented_window_type": "QQuickWindow",
                "hidden_logical_widget_native_window_created": bool(
                    self.replay_display.testAttribute(
                        Qt.WidgetAttribute.WA_WState_Created
                    )
                ),
            },
            "external_physical_evidence": {
                "required": True,
                "accepted_signal": "external.presentmon.displayed",
                "frame_swapped_stage": "swap_completed_not_monitor_scanout",
                "correlate_by": {
                    "pid": os.getpid(),
                    "run_id": self.args.run_id,
                    "window_titles": [window.title() for window in self.windows],
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
            print(f"[QUICK] report_error={exc}", flush=True)

        print(
            f"[QUICK] done valid={self.failure is None} output={self.args.output}",
            flush=True,
        )
        for window in self.windows:
            window.close()
        self.app.exit(0 if self.failure is None else 1)


def configure_qt() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
    surface_format = QSurfaceFormat()
    surface_format.setVersion(4, 1)
    surface_format.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    surface_format.setSwapInterval(0)
    QSurfaceFormat.setDefaultFormat(surface_format)


def main(argv: list[str] | None = None) -> int:
    args = parse_candidate_args(
        sys.argv[1:] if argv is None else argv,
        description=__doc__,
    )
    if args.population != "P0":
        print("[QUICK] INVALID only the P0 architecture discriminator is implemented", flush=True)
        return 2

    from core.logging.logger import setup_logging

    setup_logging(perf=True, gpu_timing=False, usage=True)
    configure_qt()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("SRPSSThreadedQuickP0Benchmark")
    benchmark = QtQuickP0Benchmark(app, args)
    try:
        benchmark.setup()
    except Exception as exc:
        traceback.print_exc()
        print(f"[QUICK] INVALID setup failed: {type(exc).__name__}: {exc}", flush=True)
        return 2
    return int(app.exec())


if __name__ == "__main__":
    sys.exit(main())
