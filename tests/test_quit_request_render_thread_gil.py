"""Quitting never makes Python wait on a Quick render thread that needs the GIL.

``QCoreApplication.quit()`` called from Python on the GUI thread sends
``QEvent::Quit`` synchronously and QGuiApplication closes every open window in
that call. PySide 6.9.1 holds the GIL for the whole call, so a render thread
running Python (updatePaintNode, a DirectConnection render-phase slot, a Python
render node) cannot finish the render stop the close waits for, and the whole
process wedges.

``request_application_quit`` queues the native ``quit()`` slot instead. The
probe renders the production retained background node (Python on the render
thread for sync, upload and teardown) and quits through the helper; it must
exit. The same probe quitting with ``app.quit()`` (``MODE=synchronous``)
wedged 3 runs out of 3 on the 2026-09-25 Linux/Xvfb threaded-GL run.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

_PROBE = r'''
import sys
from rendering.quick.bootstrap import configure_quick_graphics
configure_quick_graphics(reason="quit-render-thread-gil-probe")
from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtQuick import QQuickItem, QQuickWindow
from engine.runtime_destruction import request_application_quit
from rendering.quick.image_state import PresentationImage
from rendering.quick.render.background_image_node import RetainedBackgroundSceneNode
from rendering.quick.render.telemetry import RenderNodeTelemetry

MODE = sys.argv[1] if len(sys.argv) > 1 else "requested"
W, H = 64, 48
app = QGuiApplication(sys.argv)


class ProductionBackgroundItem(QQuickItem):
    # The production retained background: a Python scene-graph node whose
    # render-thread lifetime (sync, upload, teardown) runs Python.
    def __init__(self):
        super().__init__()
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)
        self.index = 0

    def updatePaintNode(self, node, _data):
        if node is None:
            node = RetainedBackgroundSceneNode(
                window=self.window(), telemetry=RenderNodeTelemetry(gui_thread_id=1),
                screen_index=0, frame_trace=None)
        image = PresentationImage(
            identity=f"quit-probe-{self.index}", source_path="",
            logical_size=(float(W), float(H)), device_pixel_ratio=1.0,
            pixel_size=(W, H), row_stride=W * 4,
            rgba8=bytes((20 + self.index % 200, 60, 120, 255)) * (W * H))
        node._synchronize_native_image(image, logical_size=(float(W), float(H)))
        node._set_native_visible(True)
        self.index += 1
        return node


window = QQuickWindow()
window.resize(QSize(W, H))
window.setColor(QColor(0, 0, 0))
item = ProductionBackgroundItem()
item.setParentItem(window.contentItem())
item.setWidth(W)
item.setHeight(H)
window.frameSwapped.connect(item.update)


def request_when_rendering():
    if item.index < 20:
        QTimer.singleShot(10, request_when_rendering)
        return
    if MODE == "synchronous":
        print("REQUESTED True", flush=True)
        app.quit()
    else:
        print("REQUESTED", request_application_quit("probe"), flush=True)


window.show()
QTimer.singleShot(20, request_when_rendering)
app.exec()
print("EXITED", flush=True)
'''


def test_requested_quit_exits_while_the_render_thread_runs_python() -> None:
    for attempt in range(3):
        completed = subprocess.run(
            [sys.executable, "-c", _PROBE],
            cwd=ROOT,
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
        )
        assert "REQUESTED True" in completed.stdout, completed.stdout + completed.stderr
        assert "EXITED" in completed.stdout, (attempt, completed.stdout + completed.stderr)
