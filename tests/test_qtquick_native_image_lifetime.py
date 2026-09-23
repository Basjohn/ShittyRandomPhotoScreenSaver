"""PR-04 Stage B: when does Qt read a no-copy native image QImage, and who keeps it?

The retained native background builds ``QImage(PresentationImage.rgba8, ...)``
inside ``updatePaintNode``; Stage B dropped the former ``.copy()``. The probes run
in a subprocess so the app's own Quick graphics bootstrap applies (OpenGL,
threaded render loop) and pin, on a real QQuickWindow:

1. Qt reads the pixels *after* ``updatePaintNode`` returns (render thread,
   during that frame's texture upload): bytes overwritten in
   ``afterSynchronizing`` are the ones that reach the texture.
2. Once uploaded, later frames never read the buffer again.
3. PySide 6.9.1 keeps the Python buffer alive while any C++ QImage copy of it
   exists (the texture's / upload batch's), not only while the wrapper lives.
4. End to end, the production native node renders correct pixels when the
   GUI-side reference is dropped right after sync and freed memory is churned.

The node additionally owns the PresentationImage for as long as its texture
exists, so correctness does not depend on (3) alone.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]

_PROBE = r'''
import json, sys, threading
from rendering.quick.bootstrap import configure_quick_graphics
configure_quick_graphics(reason="native-image-lifetime-probe")
from OpenGL import GL as gl
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtQuick import QQuickItem, QQuickWindow

W, H = 64, 48
ORIGINAL, MUTATED, LATER = (200, 40, 30, 255), (20, 60, 220, 255), (30, 200, 60, 255)

app = QGuiApplication(sys.argv)
buffer = bytearray(bytes(ORIGINAL) * (W * H))


def fill(rgba):
    buffer[:] = bytes(rgba) * (W * H)


class NoCopyItem(QQuickItem):
    def __init__(self):
        super().__init__()
        self.setFlag(QQuickItem.ItemHasContents, True)
        self.created = False
        self.paint_calls = 0

    def updatePaintNode(self, node, _data):
        self.paint_calls += 1
        if node is None:
            window = self.window()
            node = window.createImageNode()
            node.setOwnsTexture(True)
            image = QImage(buffer, W, H, W * 4, QImage.Format.Format_RGBA8888_Premultiplied)
            node.setTexture(window.createTextureFromImage(
                image, QQuickWindow.CreateTextureOption.TextureIsOpaque))
            self.created = True
        node.setRect(0.0, 0.0, float(W), float(H))
        return node


window = QQuickWindow()
window.resize(QSize(W, H))
window.setColor(QColor(0, 0, 0))
item = NoCopyItem()
item.setParentItem(window.contentItem())
item.setWidth(W)
item.setHeight(H)
state = {"mutated": False, "frames": [], "render_thread": None}
lock = threading.Lock()


def after_sync():
    # Render thread, after updatePaintNode returned, before the render pass.
    if item.created and not state["mutated"]:
        fill(MUTATED)
        state["mutated"] = True


def after_rendering():
    # Render thread, default framebuffer still bound: read the centre pixel.
    state["render_thread"] = threading.get_ident() != threading.main_thread().ident
    if not item.created:
        return
    data = gl.glReadPixels(W // 2, H // 2, 1, 1, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    with lock:
        state["frames"].append(list(bytes(data)[:4]))


window.afterSynchronizing.connect(after_sync, Qt.ConnectionType.DirectConnection)
window.afterRendering.connect(after_rendering, Qt.ConnectionType.DirectConnection)


def step(tick=[0]):
    tick[0] += 1
    with lock:
        count = len(state["frames"])
    if count == 1 and tick[0] < 50:
        fill(LATER)  # after the upload frame: must never reach the texture
    if count < 5 and tick[0] < 50:
        item.update()
        return
    api = window.rendererInterface().graphicsApi()
    with lock:
        result = {
            "graphics_api": getattr(api, "name", str(api)),
            "threaded_render_thread": state["render_thread"],
            "mutated_after_sync": state["mutated"],
            "frames": list(state["frames"]),
            "paint_calls": item.paint_calls,
        }
    print("PROBE " + json.dumps(result), flush=True)
    app.quit()


timer = QTimer()
timer.timeout.connect(step)
timer.start(100)
QTimer.singleShot(10000, app.quit)
window.show()
app.exec()
'''


_NODE_PROBE = r'''
import gc, json, sys, threading
from rendering.quick.bootstrap import configure_quick_graphics
configure_quick_graphics(reason="native-image-retention-probe")
from OpenGL import GL as gl
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtQuick import QQuickItem, QQuickWindow
from rendering.quick.image_state import PresentationImage
from rendering.quick.render.background_image_node import RetainedBackgroundSceneNode
from rendering.quick.render.telemetry import RenderNodeTelemetry

W, H = 64, 48
ORIGINAL, FILLER = (200, 40, 30, 255), (30, 200, 60, 255)
app = QGuiApplication(sys.argv)
holder = {"image": PresentationImage(
    identity="retention-probe", source_path="", logical_size=(float(W), float(H)),
    device_pixel_ratio=1.0, pixel_size=(W, H), row_stride=W * 4,
    rgba8=bytes(ORIGINAL) * (W * H))}
filler = []


class ProductionNativeItem(QQuickItem):
    def __init__(self):
        super().__init__()
        self.setFlag(QQuickItem.ItemHasContents, True)
        self.synced = False

    def updatePaintNode(self, node, _data):
        if node is None:
            node = RetainedBackgroundSceneNode(
                window=self.window(), telemetry=RenderNodeTelemetry(gui_thread_id=1),
                screen_index=0, frame_trace=None)
        image = holder["image"]
        if image is not None:
            node._synchronize_native_image(image, logical_size=(float(W), float(H)))
            node._set_native_visible(True)
            self.synced = True
        return node


window = QQuickWindow()
window.resize(QSize(W, H))
window.setColor(QColor(0, 0, 0))
item = ProductionNativeItem()
item.setParentItem(window.contentItem())
item.setWidth(W)
item.setHeight(H)
state = {"dropped": False, "frames": []}
lock = threading.Lock()


def after_sync():
    # After updatePaintNode, before this frame's upload: drop the GUI-side
    # reference and churn same-sized allocations so freed bytes get reused.
    if item.synced and not state["dropped"]:
        holder["image"] = None
        gc.collect()
        filler.extend(bytes(FILLER) * (W * H) for _ in range(256))
        state["dropped"] = True


def after_rendering():
    if not state["dropped"]:
        return
    data = gl.glReadPixels(W // 2, H // 2, 1, 1, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    with lock:
        state["frames"].append(list(bytes(data)[:4]))


window.afterSynchronizing.connect(after_sync, Qt.ConnectionType.DirectConnection)
window.afterRendering.connect(after_rendering, Qt.ConnectionType.DirectConnection)


def step(tick=[0]):
    tick[0] += 1
    with lock:
        count = len([f for f in state["frames"] if f[3] > 0])
    if count < 3 and tick[0] < 60:
        item.update()
        return
    with lock:
        print("PROBE " + json.dumps({"dropped": state["dropped"], "frames": list(state["frames"])}), flush=True)
    app.quit()


timer = QTimer()
timer.timeout.connect(step)
timer.start(100)
QTimer.singleShot(10000, app.quit)
window.show()
app.exec()
'''


def _close(actual, expected, tolerance=3) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(actual, expected))


def _run(script: str) -> dict:
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    lines = [line for line in completed.stdout.splitlines() if line.startswith("PROBE ")]
    assert lines, completed.stdout + completed.stderr
    return json.loads(lines[-1][len("PROBE "):])


@pytest.fixture(scope="module")
def probe() -> dict:
    return _run(_PROBE)


def test_production_native_node_keeps_the_image_bytes_through_the_upload() -> None:
    """Stage B guard: the node, not the GUI-side item, keeps the uploaded bytes.

    The item's reference is dropped right after sync and freed memory is churned
    with other-coloured allocations before the render thread uploads; only the
    node's retention of the PresentationImage keeps the pixels correct.
    """

    result = _run(_NODE_PROBE)
    drawn = [pixel for pixel in result["frames"] if pixel[3] > 0]
    assert result["dropped"] is True and drawn, result
    assert all(_close(pixel, (200, 40, 30, 255)) for pixel in drawn), result


def _drawn(probe) -> list:
    # Readbacks before the window's first composed frame are empty (alpha 0).
    return [pixel for pixel in probe["frames"] if pixel[3] > 0]


def test_probe_runs_the_production_graphics_api(probe) -> None:
    assert probe["graphics_api"] == "OpenGL"
    assert probe["threaded_render_thread"] is True
    assert probe["mutated_after_sync"] is True


def test_qt_reads_the_native_image_after_update_paint_node_returns(probe) -> None:
    # Only the bytes written on the render thread *after* updatePaintNode
    # returned ever reach the texture; the bytes present during sync never do.
    drawn = _drawn(probe)
    assert drawn, probe
    assert not any(_close(pixel, (200, 40, 30, 255)) for pixel in drawn), probe
    assert _close(drawn[0], (20, 60, 220, 255)), probe


def test_steady_frames_do_not_read_the_native_image_again(probe) -> None:
    # The buffer changed again after the upload frame; later frames still show
    # the uploaded texture, so the upload is the only read.
    drawn = _drawn(probe)
    assert len(drawn) >= 3, probe
    assert all(_close(pixel, (20, 60, 220, 255)) for pixel in drawn), probe


def test_pyside_ties_the_bytes_to_the_cxx_image_data_not_the_wrapper(qt_app) -> None:
    """PySide 6.9.1 keeps the Python buffer alive while any C++ QImage copy of it
    exists (texture, upload batch), not just while the Python wrapper lives."""

    import gc

    from PySide6.QtGui import QImage

    width, height = 16, 8
    data = bytes(range(256)) * (width * height * 4 // 256)
    base = sys.getrefcount(data)
    image = QImage(data, width, height, width * 4, QImage.Format.Format_RGBA8888_Premultiplied)
    shared_copy = QImage(image)  # stands in for the copy Qt keeps internally
    del image
    gc.collect()
    assert sys.getrefcount(data) - base == 1, "a C++ copy must keep the bytes alive"
    del shared_copy
    gc.collect()
    assert sys.getrefcount(data) - base == 0


def test_native_node_wraps_the_presentation_bytes_and_owns_them_with_the_texture(qt_app) -> None:
    import numpy as np
    from PySide6.QtGui import QImage
    from PySide6.QtQuick import QSGNode

    from rendering.quick.image_state import PresentationImage
    from rendering.quick.render.background_image_node import RetainedBackgroundSceneNode
    from rendering.quick.render.telemetry import RenderNodeTelemetry

    class _FakeImageNode(QSGNode):
        def __init__(self) -> None:
            super().__init__()
            self.texture = None

        def setOwnsTexture(self, _owns) -> None:  # noqa: N802
            pass

        def setFiltering(self, _filtering) -> None:  # noqa: N802
            pass

        def setTexture(self, texture) -> None:  # noqa: N802
            self.texture = texture

        def setSourceRect(self, _rect) -> None:  # noqa: N802
            pass

        def setRect(self, _rect) -> None:  # noqa: N802
            pass

    class _Window:
        def __init__(self) -> None:
            self.images: list[QImage] = []

        def createImageNode(self):  # noqa: N802
            return _FakeImageNode()

        def createTextureFromImage(self, image, _options):  # noqa: N802
            self.images.append(QImage(image))
            return object()

    def _image(identity: str, value: int) -> PresentationImage:
        return PresentationImage(
            identity=identity, source_path="", logical_size=(8.0, 4.0),
            device_pixel_ratio=1.0, pixel_size=(8, 4), row_stride=32,
            rgba8=bytes((value, value, value, 255)) * 32,
        )

    def _address(buffer) -> int:
        return np.frombuffer(buffer, dtype=np.uint8, count=8 * 4 * 4).__array_interface__["data"][0]

    window = _Window()
    node = RetainedBackgroundSceneNode(
        window=window, telemetry=RenderNodeTelemetry(gui_thread_id=1),
        screen_index=0, frame_trace=None,
    )
    first, second = _image("first", 40), _image("second", 90)

    node._synchronize_native_image(first, logical_size=(8.0, 4.0))
    assert _address(window.images[0].constBits()) == _address(first.rgba8), "no deep copy"
    assert node._native_image_source is first

    node._synchronize_native_image(second, logical_size=(8.0, 4.0))
    assert node._native_image_source is second  # the replaced texture's bytes go with it

    node.release_resources()
    assert node._native_image_source is None
