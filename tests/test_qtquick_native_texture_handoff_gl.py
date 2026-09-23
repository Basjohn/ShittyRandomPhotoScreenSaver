"""PR-04 native texture handoff on a real threaded OpenGL QQuickWindow.

Drives the production ``BackgroundRenderItem`` exactly as runtime does -- a
steady image, a transition, its end, a second transition, its end, then a
retirement -- in a subprocess with the app's own Quick graphics bootstrap, and
checks on the render thread:

* the finished transition's destination is adopted, not uploaded again, and the
  next transition reuses it as its source (only the new destination uploads);
* adopted frames are byte-identical to the Stage-B upload of the same pixels
  (orientation, channel order, filtering, DPR scaling);
* the previous adopted texture is deleted once replaced, the shown one stays
  alive, and retirement deletes every GL texture (no leak, no double delete);
* the adopting sync leaves the inherited GL state untouched.
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
import json, sys, threading, time
from rendering.quick.bootstrap import configure_quick_graphics
configure_quick_graphics(reason="native-texture-handoff-probe")
from OpenGL import GL as gl
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtQuick import QQuickWindow
from rendering.quick.image_state import PresentationImage
from rendering.quick.render.background_item import BackgroundRenderItem
from rendering.quick.render.telemetry import RenderNodeTelemetry
from rendering.quick.transitions import TransitionRequest, TransitionRun
from rendering.quick.render import image_textures as _image_textures
# Every image identity whose texture the host deletes, in order. GL names are
# reused, so liveness is judged by identity from the host's own deletions.
deleted = []
_real_drain = _image_textures.PresentationTextureHost._drain_pending_deletions


def _recording_drain(self):
    deleted.extend(record.identity for record in self._pending_deletions.values())
    return _real_drain(self)


_image_textures.PresentationTextureHost._drain_pending_deletions = _recording_drain
# FAULT-INJECTION-POINT

W, H = 96, 64
app = QGuiApplication(sys.argv)


def quadrant_image(identity, colors):
    rows = []
    for y in range(H):
        row = bytearray()
        for x in range(W):
            row += bytes(colors[(y >= H // 2) * 2 + (x >= W // 2)])
        rows.append(bytes(row))
    return PresentationImage(identity=identity, source_path="", logical_size=(float(W), float(H)),
                             device_pixel_ratio=1.0, pixel_size=(W, H), row_stride=W * 4,
                             rgba8=b"".join(rows))


A = quadrant_image("a", [(200, 30, 30, 255), (30, 200, 30, 255), (30, 30, 200, 255), (230, 230, 230, 255)])
B = quadrant_image("b", [(10, 120, 240, 255), (240, 200, 10, 255), (120, 10, 160, 255), (20, 20, 20, 255)])
C = quadrant_image("c", [(250, 90, 20, 255), (20, 250, 200, 255), (90, 90, 90, 255), (160, 220, 60, 255)])
B_COPY = PresentationImage(identity="b-copy", source_path="", logical_size=B.logical_size,
                           device_pixel_ratio=1.0, pixel_size=B.pixel_size, row_stride=B.row_stride,
                           rgba8=bytes(B.rgba8))
run_ids = iter(range(1, 100))


def run(source, destination):
    request = TransitionRequest(runtime_generation=1, transition_id="crossfade", requested_name="Crossfade",
                                selected_from_random=False, duration_ms=200, direction=None, parameters={},
                                source_image=source, destination_image=destination)
    return TransitionRun.start(run_id=next(run_ids), request=request, start_ns=time.monotonic_ns())


telemetry = RenderNodeTelemetry(gui_thread_id=threading.get_ident())
window = QQuickWindow()
window.resize(QSize(W, H))
window.setColor(QColor(255, 0, 255))
item = BackgroundRenderItem(telemetry=telemetry, screen_index=0)
item.setParentItem(window.contentItem())
item.setWidth(W)
item.setHeight(H)

STATES = (GL_TB := gl.GL_TEXTURE_BINDING_2D, gl.GL_ACTIVE_TEXTURE, gl.GL_UNPACK_ALIGNMENT,
          gl.GL_ARRAY_BUFFER_BINDING, gl.GL_CURRENT_PROGRAM)
state = {"step": 0, "frames": {}, "records": {}, "gl_before": None, "gl_after": None,
         "capture": None, "error": None}
lock = threading.Lock()


def host():
    node = item._retirement._node
    return None if node is None else node._custom_node._image_textures


def gl_state():
    return [int(gl.glGetIntegerv(name)) for name in STATES] + [bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST)),
                                                                bool(gl.glIsEnabled(gl.GL_STENCIL_TEST))]


def before_sync():
    if state["capture"] == "adopt-c":
        state["gl_before"] = gl_state()


def after_sync():
    try:
        textures = host()
        if textures is not None:
            with lock:
                state["records"] = {k: r.texture_id for k, r in textures._records.items()}
        if state["capture"] == "adopt-c" and state["gl_before"] is not None and state["gl_after"] is None:
            state["gl_after"] = gl_state()
    except Exception as exc:  # noqa: BLE001
        state["error"] = repr(exc)


def after_rendering():
    label = state["capture"]
    if label is None:
        return
    if label == "retired" and item._retirement._node is not None:
        return  # a frame still in flight from before the retiring sync
    fb_w = int(round(window.width() * window.effectiveDevicePixelRatio()))
    fb_h = int(round(window.height() * window.effectiveDevicePixelRatio()))
    data = bytes(gl.glReadPixels(0, 0, fb_w, fb_h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE))
    if not any(data[3::4]):
        return
    with lock:
        state["frames"].setdefault(label, []).append((fb_w, fb_h, data))


window.beforeSynchronizing.connect(before_sync, Qt.ConnectionType.DirectConnection)
window.afterSynchronizing.connect(after_sync, Qt.ConnectionType.DirectConnection)
window.afterRendering.connect(after_rendering, Qt.ConnectionType.DirectConnection)


def frames(label):
    with lock:
        return len(state["frames"].get(label, ()))


def counters():
    s = telemetry.snapshot()
    return {"host_and_native_uploads": s.image_upload_count, "adopted": s.native_background_adopt_count,
            "native_uploads": s.native_background_upload_count, "route": s.native_background_last_route,
            "reason": s.native_background_fallback_reason}


log = {}
ids = {}


def step():
    s = state["step"]
    if s == 0:
        # Stage-B reference first: B's pixels under another identity (not resident).
        item.set_presentation_image(B_COPY); state["capture"] = "stage-b-reference"; state["step"] = 1
    elif s == 1 and frames("stage-b-reference") >= 3:
        log["after_reference"] = counters()
        item.set_presentation_image(A); state["capture"] = "steady-a"; state["step"] = 2
    elif s == 2 and frames("steady-a") >= 2:
        log["after_a"] = counters()
        item.set_transition_run(run(A, B)); state["capture"] = "transition-ab"; state["step"] = 3
    elif s == 3 and frames("transition-ab") >= 3:
        with lock:
            ids.update(state["records"])
        item.set_presentation_image(B); item.set_transition_run(None)
        state["capture"] = "adopt-b"; state["step"] = 4
    elif s == 4 and frames("adopt-b") >= 3:
        log["after_b"] = counters()
        log["deleted_after_b"] = list(deleted)
        log["uploads_before_bc"] = counters()["host_and_native_uploads"]
        item.set_transition_run(run(B, C)); state["capture"] = "transition-bc"; state["step"] = 5
    elif s == 5 and frames("transition-bc") >= 3:
        log["during_bc"] = counters()
        with lock:
            ids.update(state["records"])
        item.set_presentation_image(C); item.set_transition_run(None)
        state["capture"] = "adopt-c"; state["step"] = 6
    elif s == 6 and frames("adopt-c") >= 3:
        log["after_c"] = counters()
        log["deleted_after_c"] = list(deleted)
        item.set_presentation_image(None)              # retirement while C is adopted
        state["capture"] = "retired"; state["step"] = 7
    elif s == 7 and frames("retired") >= 1:
        log["deleted_after_retirement"] = list(deleted)
        state["capture"] = None
        finish()
        return
    item.update()


def finish():
    def last(label):
        return state["frames"][label][-1]

    result = {"log": log, "ids": ids, "gl_before": state["gl_before"],
              "gl_after": state["gl_after"], "error": state["error"],
              "graphics_api": str(window.rendererInterface().graphicsApi())}
    try:
        adopted_b = last("adopt-b")[2]
        # B was adopted; C then took the screen; B_COPY re-shows B's pixels via Stage B.
        result["adopted_equals_stage_b"] = adopted_b == last("stage-b-reference")[2]
        fb_w, fb_h, data = last("adopt-b")
        def px(x, y):
            i = ((fb_h - 1 - y) * fb_w + x) * 4
            return list(data[i:i + 4])
        result["adopted_quadrants"] = [px(fb_w // 4, fb_h // 4), px(3 * fb_w // 4, fb_h // 4),
                                       px(fb_w // 4, 3 * fb_h // 4), px(3 * fb_w // 4, 3 * fb_h // 4)]
    except Exception as exc:  # noqa: BLE001
        result["error"] = repr(exc)
    print("PROBE " + json.dumps(result), flush=True)
    app.quit()


timer = QTimer()
timer.timeout.connect(step)
timer.start(60)
QTimer.singleShot(20000, app.quit)
window.show()
app.exec()
'''


def _run_probe(script: str, fault: str = "") -> dict:
    script = script.replace("# FAULT-INJECTION-POINT", fault)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT, env=os.environ.copy(), text=True, capture_output=True, timeout=60, check=False,
    )
    lines = [line for line in completed.stdout.splitlines() if line.startswith("PROBE ")]
    assert lines, completed.stdout[-2000:] + completed.stderr[-4000:]
    return json.loads(lines[-1][len("PROBE "):])


@pytest.fixture(scope="module")
def probe() -> dict:
    result = _run_probe(_PROBE)
    assert result["error"] is None, result
    return result


def test_runs_on_the_production_graphics_api(probe) -> None:
    assert probe["graphics_api"].endswith("OpenGL")


def test_the_finished_destination_is_adopted_not_uploaded_again(probe) -> None:
    log = probe["log"]
    assert log["after_a"]["route"] == "uploaded" and log["after_a"]["reason"] == "not_resident"
    uploads = log["after_a"]["native_uploads"]              # the two images shown without a transition
    assert log["after_b"]["adopted"] == 1 and log["after_b"]["route"] == "adopted"
    assert log["after_b"]["native_uploads"] == uploads      # no upload at the end of A -> B
    assert log["after_c"]["adopted"] == 2 and log["after_c"]["native_uploads"] == uploads


def test_the_next_transition_reuses_the_adopted_texture_as_its_source(probe) -> None:
    log = probe["log"]
    # B -> C uploads only C: B is still resident (lent) from the previous run.
    assert log["during_bc"]["host_and_native_uploads"] == log["uploads_before_bc"] + 1


def test_adopted_pixels_match_the_stage_b_upload_exactly(probe) -> None:
    assert probe["adopted_equals_stage_b"] is True
    assert probe["adopted_quadrants"] == [[10, 120, 240, 255], [240, 200, 10, 255],
                                          [120, 10, 160, 255], [20, 20, 20, 255]]
    assert probe["log"]["after_reference"]["route"] == "uploaded"  # the reference really was Stage B


def test_replaced_textures_are_deleted_and_shown_ones_kept(probe) -> None:
    log = probe["log"]
    assert "a" in log["deleted_after_b"] and "b" not in log["deleted_after_b"]
    assert "b" in log["deleted_after_c"] and "c" not in log["deleted_after_c"]


def test_retirement_deletes_the_adopted_texture_exactly_once(probe) -> None:
    final = probe["log"]["deleted_after_retirement"]
    assert "c" in final
    assert all(final.count(identity) == 1 for identity in ("a", "b", "c")), final


def test_the_adopting_sync_leaves_inherited_gl_state_untouched(probe) -> None:
    assert probe["gl_before"] is not None and probe["gl_before"] == probe["gl_after"]
