"""Bounded Qt Quick render-thread and target-pacing safety spike.

This standalone tool proves only that top-level QQuickWindows can use a render
thread distinct from the GUI thread under finite, target-paced requests. It is
not the common Slide + Bubble architecture benchmark and its animated clear is
not product-performance evidence.

Normal operator shape:

    python tools/qtquick_presentation_spike.py --seconds 15 \
        --target-hz 165,60 --load-label light

The default path is paced from monotonic deadlines and ends automatically. The
old unpaced afterFrameEnd -> update loop exists only behind
``--throughput-probe`` and is always labelled invalid for architecture evidence.
``--basic`` remains an explicit GUI-thread negative control.
"""

from __future__ import annotations

import math
import os
import sys
import threading


# Render-loop and graphics selection must happen before any Qt import.
_args_preview = set(sys.argv[1:])
if "--basic" in _args_preview:
    os.environ["QSG_RENDER_LOOP"] = "basic"
else:
    os.environ.setdefault("QSG_RENDER_LOOP", "threaded")
os.environ.setdefault("QSG_INFO", "1")
_existing_rules = os.environ.get("QT_LOGGING_RULES", "")
os.environ["QT_LOGGING_RULES"] = (
    (_existing_rules + ";" if _existing_rules else "")
    + "qt.scenegraph.general=true;qt.rhi.general=true"
)

from PySide6.QtCore import QElapsedTimer, QObject, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication, QScreen, QSurfaceFormat  # noqa: E402
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface  # noqa: E402

if __package__:
    from .presentation_benchmark_core import (  # noqa: E402
        TargetPacerState,
        parse_spike_args,
        percentile,
        validate_window_screen_count,
    )
else:
    from presentation_benchmark_core import (  # noqa: E402
        TargetPacerState,
        parse_spike_args,
        percentile,
        validate_window_screen_count,
    )

try:
    from OpenGL import GL as gl  # noqa: E402
except Exception:  # pragma: no cover - operator OpenGL capability result
    gl = None


def _gui_thread_id() -> int:
    return int(threading.get_ident())


class TargetFramePacer(QObject):
    """GUI-side finite request pacer; never schedules from render completion."""

    def __init__(self, window: QQuickWindow, target_hz: float):
        super().__init__(window)
        self._window = window
        self.state = TargetPacerState(float(target_hz))
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._service_deadline)

    def start(self) -> None:
        self._clock.start()
        self.state.start(0)
        self._service_deadline()

    def stop(self) -> None:
        self._timer.stop()

    def _service_deadline(self) -> None:
        decision = self.state.consume(self._clock.nsecsElapsed())
        if decision.due_opportunities:
            # QQuickWindow/Qt may coalesce repeated update requests. The pacer
            # records logical opportunities and issues at most one freshest
            # request for all deadlines already missed; it never catches up.
            self._window.update()
        self._timer.start(decision.next_delay_ms)


class RenderProbe(QObject):
    """Native-GL thread-identity/cadence probe for one QQuickWindow."""

    def __init__(
        self,
        window: QQuickWindow,
        name: str,
        gui_thread_id: int,
        *,
        throughput_probe: bool,
    ):
        super().__init__()
        self._window = window
        self._name = name
        self._gui_thread_id = gui_thread_id
        self._throughput_probe = bool(throughput_probe)
        self._frame_count = 0
        self._render_thread_id: int | None = None
        self._render_thread_is_gui: bool | None = None
        self._clock = QElapsedTimer()
        self._clock.start()
        self._last_frame_ns = 0
        self._gaps_ms: list[float] = []

        window.setColor(Qt.GlobalColor.black)
        window.beforeRendering.connect(self._on_before_rendering, Qt.DirectConnection)
        if self._throughput_probe:
            window.afterFrameEnd.connect(self._request_next_throughput_frame, Qt.DirectConnection)

    def _request_next_throughput_frame(self) -> None:
        # Explicit negative/control mode only. Normal benchmark operation never
        # schedules another frame from a render callback.
        self._window.update()

    def _on_before_rendering(self) -> None:
        if self._render_thread_id is None:
            self._render_thread_id = int(threading.get_ident())
            self._render_thread_is_gui = self._render_thread_id == self._gui_thread_id
            print(
                f"[SPIKE][{self._name}] first_render "
                f"render_thread_id={self._render_thread_id} "
                f"gui_thread_id={self._gui_thread_id} "
                f"threaded={'NO' if self._render_thread_is_gui else 'YES'}",
                flush=True,
            )

        now_ns = self._clock.nsecsElapsed()
        if self._last_frame_ns:
            self._gaps_ms.append((now_ns - self._last_frame_ns) / 1e6)
        self._last_frame_ns = now_ns
        self._frame_count += 1

        if gl is None:
            return
        try:
            self._window.beginExternalCommands()
            try:
                dpr = self._window.effectiveDevicePixelRatio()
                width = int(self._window.width() * dpr)
                height = int(self._window.height() * dpr)
                gl.glViewport(0, 0, max(1, width), max(1, height))
                t = now_ns / 1e9
                red = 0.5 + 0.5 * math.sin(t * 2.0)
                green = 0.5 + 0.5 * math.sin(t * 2.0 + 2.094)
                blue = 0.5 + 0.5 * math.sin(t * 2.0 + 4.188)
                gl.glClearColor(red, green, blue, 1.0)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            finally:
                self._window.endExternalCommands()
        except Exception as exc:  # pragma: no cover - operator diagnostics
            print(f"[SPIKE][{self._name}] gl_render_error={exc}", flush=True)

    def report(self, pacing: TargetPacerState | None) -> None:
        gaps = sorted(self._gaps_ms)
        elapsed_seconds = sum(gaps) / 1000.0
        fps = (len(gaps) / elapsed_seconds) if elapsed_seconds > 0.0 else 0.0
        bins = (12.0, 16.0, 25.0, 33.0, 50.0, 100.0)
        bin_text = " ".join(
            f">={int(threshold)}ms={sum(1 for gap in gaps if gap >= threshold)}"
            for threshold in bins
        )
        if pacing is None:
            pace_text = (
                "mode=throughput_probe requested_opportunities=unbounded "
                "paced_requests=unbounded"
            )
        else:
            pacing_acceptance = (
                100.0 * pacing.paced_requests / pacing.requested_opportunities
                if pacing.requested_opportunities
                else 0.0
            )
            pace_text = (
                f"target_hz={pacing.target_hz:g} "
                f"requested_opportunities={pacing.requested_opportunities} "
                f"paced_requests={pacing.paced_requests} "
                f"pacing_acceptance={pacing_acceptance:.2f}% "
                f"skipped_deadlines={pacing.skipped_deadlines}"
            )
        if self._render_thread_is_gui is None:
            thread_text = "no_frame_INVALID"
        elif self._render_thread_is_gui:
            thread_text = "GUI_INVALID"
        else:
            thread_text = "dedicated"
        print(
            f"[SPIKE][{self._name}] {pace_text} render_callbacks={self._frame_count} "
            f"render_callback_fps={fps:.1f} dt_p50={percentile(gaps, 0.50):.2f} "
            f"dt_p90={percentile(gaps, 0.90):.2f} "
            f"dt_p95={percentile(gaps, 0.95):.2f} "
            f"dt_p99={percentile(gaps, 0.99):.2f} "
            f"dt_max={(gaps[-1] if gaps else 0.0):.2f} {bin_text} "
            f"render_thread={thread_text}",
            flush=True,
        )


def _window_screen(app: QGuiApplication, index: int) -> QScreen:
    return list(app.screens())[index]


def _make_window(
    app: QGuiApplication,
    index: int,
    gui_thread_id: int,
    *,
    target_hz: float,
    throughput_probe: bool,
) -> tuple[QQuickWindow, RenderProbe, TargetFramePacer | None]:
    screen = _window_screen(app, index)
    window = QQuickWindow()
    window.setScreen(screen)
    window.setTitle(f"QtQuick Presentation Safety Spike {index}")
    available = screen.availableGeometry()
    width = min(960, max(320, available.width() - 80))
    height = min(540, max(240, available.height() - 80))
    window.resize(width, height)
    window.setPosition(
        available.x() + max(0, (available.width() - width) // 2),
        available.y() + max(0, (available.height() - height) // 2),
    )
    screen_name = screen.name() or f"screen{index}"
    name = f"win{index}:{screen_name}"
    probe = RenderProbe(
        window,
        name,
        gui_thread_id,
        throughput_probe=throughput_probe,
    )
    pacer = None if throughput_probe else TargetFramePacer(window, target_hz)
    window.show()
    return window, probe, pacer


def main(argv: list[str] | None = None) -> int:
    args = parse_spike_args(
        sys.argv[1:] if argv is None else argv,
        description=__doc__,
    )

    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
    surface_format = QSurfaceFormat()
    surface_format.setSwapInterval(0)
    QSurfaceFormat.setDefaultFormat(surface_format)

    app = QGuiApplication(sys.argv[:1])
    screens = list(app.screens())
    try:
        validate_window_screen_count(args.windows, len(screens))
    except ValueError as exc:
        print(f"[SPIKE] INVALID screen_topology={exc}", flush=True)
        return 2
    gui_thread_id = _gui_thread_id()
    mode = "throughput_probe_INVALID" if args.throughput_probe else "target_paced"
    print(
        f"[SPIKE] start loop={os.environ.get('QSG_RENDER_LOOP')} "
        f"mode={mode} gui_thread_id={gui_thread_id} windows={args.windows} "
        f"targets={','.join(f'{rate:g}' for rate in args.target_hz)} "
        f"seconds={args.seconds:g} load_label={args.load_label!r}",
        flush=True,
    )
    if args.basic:
        print("[SPIKE] CONTROL_ONLY basic GUI-thread loop is invalid architecture evidence", flush=True)
    if args.throughput_probe:
        print(
            "[SPIKE] CONTROL_ONLY unpaced throughput probe is invalid architecture evidence",
            flush=True,
        )

    pairs = [
        _make_window(
            app,
            index,
            gui_thread_id,
            target_hz=args.target_hz[index],
            throughput_probe=args.throughput_probe,
        )
        for index in range(args.windows)
    ]
    for window, _probe, pacer in pairs:
        if pacer is None:
            window.update()
        else:
            pacer.start()

    def _finish() -> None:
        for _window, _probe, pacer in pairs:
            if pacer is not None:
                pacer.stop()
        for _window, probe, pacer in pairs:
            probe.report(pacer.state if pacer is not None else None)

        threaded = all(probe._render_thread_is_gui is False for _window, probe, _pacer in pairs)
        if args.basic:
            verdict = "CONTROL_ONLY: basic GUI-thread loop"
        elif args.throughput_probe:
            verdict = "CONTROL_ONLY: unpaced throughput probe"
        elif not threaded:
            verdict = "INVALID: dedicated render thread not proven"
        else:
            verdict = "PASS: bounded pacing and dedicated render thread; workload proof still pending"
        print(f"[SPIKE] done verdict={verdict}", flush=True)
        app.quit()

    QTimer.singleShot(int(round(args.seconds * 1000.0)), _finish)
    return int(app.exec())


if __name__ == "__main__":
    sys.exit(main())
