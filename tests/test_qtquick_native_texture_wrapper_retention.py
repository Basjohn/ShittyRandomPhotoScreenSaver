"""Uploaded background textures do not leave Python wrappers behind.

PySide parents every ``QQuickWindow.createTextureFromImage()`` result to the
window's Python wrapper. The retained background's ``QSGImageNode`` owns and
deletes each C++ texture when the next image replaces it, so every upload used
to leave one dangling ``QSGTexture`` wrapper alive until the window died (the
2026-09-25 Linux soak counted one per rotation).

The probe drives the production ``RetainedBackgroundSceneNode`` on a real
threaded-OpenGL ``QQuickWindow`` through many distinct images, then proves the
node still shows the latest image (ownership intact, no double delete) and that
no wrapper accumulated.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

_PROBE = r'''
import gc, json, sys, threading
from rendering.quick.bootstrap import configure_quick_graphics
configure_quick_graphics(reason="texture-wrapper-retention-probe")
from OpenGL import GL as gl
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtQuick import QQuickItem, QQuickWindow, QSGTexture
from rendering.quick.image_state import PresentationImage
from rendering.quick.render.background_image_node import RetainedBackgroundSceneNode
from rendering.quick.render.telemetry import RenderNodeTelemetry
from engine.runtime_destruction import request_application_quit

W, H, IMAGES = 64, 48, 40
app = QGuiApplication(sys.argv)


def image(index):
    rgba = (10 + index * 5, 40, 200 - index * 3, 255)
    return PresentationImage(
        identity=f"wrapper-probe-{index}", source_path="", logical_size=(float(W), float(H)),
        device_pixel_ratio=1.0, pixel_size=(W, H), row_stride=W * 4,
        rgba8=bytes(rgba) * (W * H))


class ProductionNativeItem(QQuickItem):
    def __init__(self):
        super().__init__()
        self.setFlag(QQuickItem.ItemHasContents, True)
        self.index = 0
        self.synced = 0

    def updatePaintNode(self, node, _data):
        if node is None:
            node = RetainedBackgroundSceneNode(
                window=self.window(), telemetry=RenderNodeTelemetry(gui_thread_id=1),
                screen_index=0, frame_trace=None)
        node._synchronize_native_image(image(self.index), logical_size=(float(W), float(H)))
        node._set_native_visible(True)
        self.synced = self.index + 1
        return node


window = QQuickWindow()
window.resize(QSize(W, H))
window.setColor(QColor(0, 0, 0))
item = ProductionNativeItem()
item.setParentItem(window.contentItem())
item.setWidth(W)
item.setHeight(H)
state = {"pixel": None}
lock = threading.Lock()


def after_rendering():
    data = gl.glReadPixels(W // 2, H // 2, 1, 1, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    with lock:
        state["pixel"] = list(bytes(data)[:4])
        state["rendered"] = item.synced


window.afterRendering.connect(after_rendering, Qt.ConnectionType.DirectConnection)


def step():
    with lock:
        rendered = state.get("rendered", 0)
    if rendered == item.index + 1 and item.index < IMAGES - 1:
        item.index += 1
    if rendered == IMAGES:
        timer.stop()
        gc.collect()
        wrappers = sum(1 for obj in gc.get_objects() if isinstance(obj, QSGTexture))
        with lock:
            print("PROBE " + json.dumps({"images": rendered, "pixel": state["pixel"], "wrappers": wrappers}), flush=True)
        # A synchronous app.quit() here wedges on the render thread's Python
        # teardown of this very node (see test_quit_request_render_thread_gil).
        request_application_quit("probe")
        return
    item.update()


timer = QTimer()
timer.timeout.connect(step)
timer.start(20)
QTimer.singleShot(20000, lambda: request_application_quit("probe_timeout"))
window.show()
app.exec()
'''


def test_replaced_uploads_leave_no_python_texture_wrappers() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=ROOT,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    lines = [line for line in completed.stdout.splitlines() if line.startswith("PROBE ")]
    assert lines, completed.stdout + completed.stderr
    result = json.loads(lines[-1][len("PROBE "):])

    assert result["images"] == 40, result
    # A current image is still on screen (the readback may trail by one frame):
    # the node's ownership of the C++ texture was not disturbed by releasing
    # the Python side.
    recent = [(10 + index * 5, 40, 200 - index * 3, 255) for index in (38, 39)]
    assert any(
        all(abs(a - b) <= 3 for a, b in zip(result["pixel"], expected))
        for expected in recent
    ), result
    # Before the fix every replaced upload stayed alive on the window wrapper.
    assert result["wrappers"] <= 1, result
