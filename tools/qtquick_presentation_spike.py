"""Qt Quick physical-presentation vertical slice (Current_Plan section 6-8).

The one question this spike answers:

    Does moving physical rendering/present onto Qt Quick's threaded scene-graph
    render loop (one top-level QQuickWindow per display, no QQuickWidget, no
    QWidget embedding) collapse the GUI-dispatch / frame-gap pathology that every
    QWidget/QRhi state shared, while preserving the authored workload?

This is a STANDALONE architecture prototype. It does not import or modify the
product. It renders representative content with native OpenGL on the Quick
render thread via `beforeRendering`, feeds immutable synthetic state, and proves
- via Qt scene-graph logging and live thread-id capture - whether the render
loop is actually threaded and which thread owns rendering for each window.

Run on the operator's real dual-display hardware:

    python tools/qtquick_presentation_spike.py --seconds 20

Flags:
    --seconds N     run duration (default 15)
    --windows N     number of QQuickWindows (default 2)
    --basic         force the basic (GUI-thread) render loop, to contrast

The candidate is INVALID if it silently runs the basic GUI-thread loop; the log
must show `threaded` and a render thread distinct from the GUI thread.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time

# The render-loop and graphics-API selection MUST be set before any Qt import.
_args_preview = set(sys.argv[1:])
if "--basic" in _args_preview:
    os.environ["QSG_RENDER_LOOP"] = "basic"
else:
    os.environ.setdefault("QSG_RENDER_LOOP", "threaded")
# Ask Qt Quick to print the render loop / scene-graph backend it selected.
os.environ.setdefault("QSG_INFO", "1")
# Scene-graph general logging so the selected loop is explicit in the output.
_existing_rules = os.environ.get("QT_LOGGING_RULES", "")
os.environ["QT_LOGGING_RULES"] = (
    (_existing_rules + ";" if _existing_rules else "")
    + "qt.scenegraph.general=true;qt.rhi.general=true"
)

from PySide6.QtCore import QElapsedTimer, QObject, Qt, QThread, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication, QSurfaceFormat  # noqa: E402
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface  # noqa: E402

try:
    from OpenGL import GL as gl  # noqa: E402
except Exception:  # pragma: no cover - spike is OpenGL-only
    gl = None


def _gui_thread_id() -> int:
    return int(threading.get_ident())


class RenderProbe(QObject):
    """Native-GL render-thread renderer for one QQuickWindow.

    Connected to `beforeRendering` (fires on the render thread when threaded).
    It records the render-thread identity, paces frames, and draws a moving
    full-window clear colour from immutable synthetic state so the scene-graph
    keeps producing frames without vsync.
    """

    def __init__(self, window: QQuickWindow, name: str, gui_thread_id: int):
        super().__init__()
        self._window = window
        self._name = name
        self._gui_thread_id = gui_thread_id
        self._frame_count = 0
        self._render_thread_id: int | None = None
        self._render_thread_is_gui: bool | None = None
        self._clock = QElapsedTimer()
        self._clock.start()
        self._last_frame_ns = 0
        self._gaps_ms: list[float] = []

        window.setColor(Qt.GlobalColor.black)
        # `beforeRendering` fires on the scene-graph render thread when the loop
        # is threaded; the scene graph performs its own clear to window.color()
        # afterwards, so this underlay GL is for the thread-ownership/cadence
        # proof. A visible representative underlay (transparent window colour +
        # Blockspin/Bubble/Spectrum shader) is the follow-up once the threaded
        # lever is confirmed.
        window.beforeRendering.connect(self._on_before_rendering, Qt.DirectConnection)
        window.afterFrameEnd.connect(self._request_next_frame, Qt.DirectConnection)

    def _request_next_frame(self) -> None:
        # No-vsync continuous loop: request the next frame as soon as one ends.
        self._window.update()

    def _on_before_rendering(self) -> None:
        # Runs on the scene-graph RENDER thread when the loop is threaded.
        if self._render_thread_id is None:
            self._render_thread_id = int(threading.get_ident())
            self._render_thread_is_gui = self._render_thread_id == self._gui_thread_id
            print(
                f"[SPIKE][{self._name}] first render: render_thread_id={self._render_thread_id} "
                f"gui_thread_id={self._gui_thread_id} "
                f"threaded={'NO (GUI-thread loop!)' if self._render_thread_is_gui else 'YES'}",
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
                w = int(self._window.width() * self._window.effectiveDevicePixelRatio())
                h = int(self._window.height() * self._window.effectiveDevicePixelRatio())
                gl.glViewport(0, 0, max(1, w), max(1, h))
                # Immutable synthetic state -> an animated clear colour. A
                # representative shader port (Blockspin/Bubble/Spectrum) is the
                # next step once the threaded-loop lever is proven.
                t = now_ns / 1e9
                import math
                r = 0.5 + 0.5 * math.sin(t * 2.0)
                g = 0.5 + 0.5 * math.sin(t * 2.0 + 2.094)
                b = 0.5 + 0.5 * math.sin(t * 2.0 + 4.188)
                gl.glClearColor(r, g, b, 1.0)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            finally:
                self._window.endExternalCommands()
        except Exception as exc:  # pragma: no cover - spike diagnostics
            print(f"[SPIKE][{self._name}] GL render error: {exc}", flush=True)

    def report(self) -> None:
        gaps = sorted(self._gaps_ms)
        n = len(gaps)

        def pct(p: float) -> float:
            if not gaps:
                return 0.0
            return gaps[min(n - 1, int(round((n - 1) * p)))]

        fps = (n / (sum(gaps) / 1000.0)) if gaps and sum(gaps) > 0 else 0.0
        over_33 = sum(1 for g in gaps if g >= 33.0)
        over_50 = sum(1 for g in gaps if g >= 50.0)
        print(
            f"[SPIKE][{self._name}] frames={self._frame_count} fps={fps:.1f} "
            f"dt_p50={pct(0.5):.2f} dt_p95={pct(0.95):.2f} dt_p99={pct(0.99):.2f} "
            f"dt_max={(gaps[-1] if gaps else 0.0):.2f} >=33ms={over_33} >=50ms={over_50} "
            f"render_thread={'GUI (INVALID)' if self._render_thread_is_gui else 'dedicated'}",
            flush=True,
        )


def _make_window(index: int, gui_thread_id: int) -> tuple[QQuickWindow, RenderProbe]:
    window = QQuickWindow()
    window.setTitle(f"QtQuick Presentation Spike {index}")
    window.resize(960, 540)
    # Place windows side by side; the operator can drag them onto the 60/165 Hz
    # displays for the real mixed-refresh proof.
    window.setPosition(60 + index * 980, 80)
    probe = RenderProbe(window, f"win{index}", gui_thread_id)
    window.show()
    return window, probe


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=15.0)
    parser.add_argument("--windows", type=int, default=2)
    parser.add_argument("--basic", action="store_true", help="force GUI-thread loop (contrast)")
    parser.add_argument("--heavy", type=int, default=0,
                        help="spawn N CPU-burn threads for the controlled heavy-load pass")
    args = parser.parse_args()

    _stop_load = threading.Event()
    for _ in range(max(0, args.heavy)):
        def _burn() -> None:
            x = 0.0
            while not _stop_load.is_set():
                for i in range(50000):
                    x += i * 1.000001
        threading.Thread(target=_burn, daemon=True).start()
    if args.heavy:
        print(f"[SPIKE] heavy load: {args.heavy} CPU-burn threads", flush=True)

    # OpenGL + no-vsync (swap interval 0), matching the product policy.
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
    fmt = QSurfaceFormat()
    fmt.setSwapInterval(0)  # no vsync
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QGuiApplication(sys.argv)
    gui_thread_id = _gui_thread_id()
    print(f"[SPIKE] QSG_RENDER_LOOP={os.environ.get('QSG_RENDER_LOOP')} "
          f"gui_thread_id={gui_thread_id} windows={args.windows} seconds={args.seconds}", flush=True)

    pairs = [_make_window(i, gui_thread_id) for i in range(max(1, args.windows))]

    def _finish() -> None:
        for _win, probe in pairs:
            probe.report()
        loop_kind = os.environ.get("QSG_RENDER_LOOP")
        any_gui = any(p._render_thread_is_gui for _w, p in pairs)
        print(
            f"[SPIKE] DONE loop={loop_kind} "
            f"verdict={'INVALID: ran on GUI thread' if any_gui else 'render thread is dedicated'}",
            flush=True,
        )
        app.quit()

    QTimer.singleShot(int(args.seconds * 1000), _finish)
    result = app.exec()
    _stop_load.set()
    return result


if __name__ == "__main__":
    sys.exit(main())
