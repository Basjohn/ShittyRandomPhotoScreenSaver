"""N2.2's proof (Current_Plan.md item 8b): the host interface and the frame driver, through ``rendering.native``.

The module (``release/native_module``, built on GitHub) is loaded the product's way and driven in one child process per
graphics API (Qt Quick's API is process-wide): OpenGL, Vulkan on the module's own instance and devices (D6), D3D11 and
D3D12. No window is ever visible: the hidden host never shows one, and the window host's windows are kept off screen by
the tests' pattern (``tests/_invisible_windows.py``: zero opacity, transparent for input, a tool window).

Rounds (each per API):
  hidden     the hidden host on the core's render thread: at rest it records nothing (frames without the probe: zero
             passes); the frame edge is on the render thread with no Python thread state (D5.4); the probe pass records
             every frame and its raw readback equals the analytical image (the upload correction, the front-face rule on
             the corrected matrix, the conventions block, the readback orientation; probe_analysis.py); each negative
             control fails exactly where it changes the rasterizer's input; detach releases on the render thread and
             the detached driver gets no more edges; re-attach records again; close tears down in the decided order;
             the same host rendering on the GUI thread (the negative control) reports a Python thread state every edge.
  window     a real Qt Quick window rendered by Qt's render loop, kept off screen: hosted before it is shown, the probe
             on Qt's render thread, detach (released at the next frame edge on the render thread), re-attach, and the
             window destroyed while it animates (mid-frame): released at the scene graph's invalidation on the render
             thread, then (Vulkan) the module's device destroyed after the window.
  lifecycle  create-use-destroy cycles, each kind of ours right after its control (Qt alone doing the same on the
             same API): a window with the core (attach, probe, detach, re-attach, destroyed mid-frame) against a window
             without it; a hidden host (probe, readback, detach, re-attach, close) against Qt's threaded render control
             in the same sequence (on Vulkan against the Qt-only window). After a warm-up, the core may add no handle,
             USER object or private-byte trough growth over its control (the control's own noise is the tolerance),
             and threads stay flat. What the drivers and Qt keep per cycle themselves is recorded in
             Docs/Future_Work/Native_Core_N06_N07_Qt_Facts.md section J.
On Vulkan the instance has the Khronos validation layer with synchronisation validation when --layer-path gives it; every
message is attributed and only Qt 6.12.0's recorded defects are excused, by id (vk_validation.py, the N0.6 rule).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/host_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan d3d11 d3d12] [--rounds hidden window lifecycle] [--cycles 16] [--label n22_hosts]
Evidence: .artifacts/evidence/native_core/n2_2/<date>_<label>/ (summary.json, the probe readbacks as PNG). Exit 0 whenever
the harness ran; the verdict is the last printed line ("N22 VERDICT PASS" or "N22 VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import subprocess
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import vk_validation  # noqa: E402  (native/core/python)

APIS = ("opengl", "vulkan", "d3d11", "d3d12")
ROUNDS = ("hidden", "window", "lifecycle")
HOST_SIZE = (320, 180)
REST_FRAMES = 30
PROBE_FRAMES = 10
WINDOW_FRAMES = 20
WAIT_S = 15.0
CHILD_TIMEOUT_S = 900
LIFECYCLE_WARMUP_CYCLES = 8        # D3D12's own pools grow in 8 MiB steps for about 8 creations, then plateau
LIFECYCLE_CYCLES = 16
HANDLE_SLOPE_TOLERANCE = 0.25      # handles (or USER objects) per cycle the core may add over Qt alone
THREAD_TOLERANCE = 1
PRIVATE_PLATEAU_TOLERANCE_MIB = 16.0   # the floor; the control's own range on that API when larger
DEVICE_TEARDOWN = ["vkDeviceWaitIdle: VK_SUCCESS", "vkDestroyDevice", "resetDeviceFunctions"]
# Negative controls of the probe (probe_pass.h ProbeConfig); the clip-NDC flip's inverse is added per backend.
NEGATIVES = {
    "no_correction": {"correction": "none"},
    "rule_on_the_uncorrected_matrix": {"front_face": "rule_uncorrected"},
    "front_face_fixed_ccw": {"front_face": "ccw"},
    "fragment_flip_inverted": {"fragment_flip": 1},
}
CONTENT_QML = b"""import QtQuick
Rectangle {
    color: "#203040"
    Rectangle {
        x: 40; y: 40; width: 120; height: 60; color: "#c08040"
        RotationAnimation on rotation { from: 0; to: 360; duration: 1500; loops: Animation.Infinite }
    }
}
"""
_ALLOWED_ENV: set[str] = set()


def _root(repo: str) -> Path:
    sys.path.insert(0, os.path.abspath(repo))
    from tools.artifact_paths import repository_root

    return repository_root(repo)


# --------------------------------------------------------------------------------------------------------- helpers

def _pump(app, seconds: float) -> None:
    from PySide6.QtCore import QEventLoop

    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 16)


def _wait_until(app, condition, timeout: float = WAIT_S) -> bool:
    from PySide6.QtCore import QEventLoop

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 16)
    return bool(condition())


def _flush_deletes(app) -> None:
    from PySide6.QtCore import QCoreApplication, QEvent

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    gc.collect()


def _content(engine):
    from PySide6.QtCore import QSizeF, QUrl
    from PySide6.QtQml import QQmlComponent

    component = QQmlComponent(engine)
    component.setData(CONTENT_QML, QUrl())
    item = component.create()
    if item is None:
        raise RuntimeError(f"the content did not load: {component.errorString()}")
    item.setSize(QSizeF(*HOST_SIZE))
    return item, component


def _drop_item(app, item) -> None:
    import shiboken6

    if item is not None and shiboken6.isValid(item):
        item.setParentItem(None)
        shiboken6.delete(item)
    _flush_deletes(app)


def _save_png(readback, path: Path) -> str | None:
    """The raw readback as an opaque PNG (row 0 at the top, as the target's memory holds it; alpha carries ndcToUv's
    v there, so it is set opaque for viewing)."""
    import numpy as np
    from PySide6.QtGui import QImage

    if readback is None:
        return None
    rgba = np.frombuffer(readback.rgba, dtype=np.uint8)[: readback.width * readback.height * 4]
    rgba = rgba.reshape(readback.height, readback.width, 4).copy()
    rgba[..., 3] = 255
    image = QImage(rgba.tobytes(), readback.width, readback.height, readback.width * 4,
                   QImage.Format.Format_RGBA8888).copy()
    return str(path) if image.save(str(path), "PNG") else None


def _readback_dict(readback) -> dict:
    return {"facts": readback.facts, "rgba": readback.rgba, "width": readback.width, "height": readback.height,
            "frame": readback.frame}


def _slope(values: list[float]) -> float | None:
    n = len(values)
    if n < 2:
        return None
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    den = sum((i - mean_x) ** 2 for i in range(n))
    return round(sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values)) / den, 4) if den else None


def _driver(state: dict, which: str = "driver") -> dict:
    return state.get(which) or {}


# --------------------------------------------------------------------------------------------------------- hidden

def _probe_hidden(host, analyse) -> tuple[object, dict]:
    host.request_readback()
    host.frames(1)
    readback = host.probe_result()
    return readback, (analyse(_readback_dict(readback)) if readback is not None else {"pass": False,
                                                                                         "error": "no readback"})


def round_hidden(core, engine, app, api: str, out: Path) -> dict:
    from probe_analysis import analyse, negative_verdict

    record: dict = {}
    checks: dict = {}
    item, _component = _content(engine)
    host = core.hidden_host(*HOST_SIZE)
    try:
        host.set_content(item)
        host.frames(REST_FRAMES)
        state = host.state()
        rest = _driver(state)
        record["at_rest"] = rest
        checks["at_rest_records_nothing"] = rest.get("edges") == REST_FRAMES and rest.get("passes_recorded") == 0
        checks["frame_edge_on_the_render_thread"] = (rest.get("edges_on_gui_thread") == 0
                                                     and state.get("render_thread") != state.get("host_gui_thread"))
        checks["no_python_thread_state_on_the_frame_edge"] = rest.get("edges_with_python_thread_state") == 0

        host.set_probe()
        host.frames(PROBE_FRAMES)
        readback, analysis = _probe_hidden(host, analyse)
        record["probe"] = {k: v for k, v in analysis.items()}
        record["probe_png"] = _save_png(readback, out / f"n22_probe_{api}_hidden.png")
        driver = _driver(host.state())
        record["probe_driver"] = driver
        checks["probe_matches_the_conventions"] = bool(analysis.get("pass"))
        checks["probe_recorded_every_frame"] = driver.get("passes_recorded") == PROBE_FRAMES + 1
        checks["probe_readback_is_its_frames"] = readback is not None and readback.frame == driver.get("edges")
        checks["no_python_thread_state_while_recording"] = driver.get("edges_with_python_thread_state") == 0

        negatives: dict = {}
        if readback is not None:
            default_facts = readback.facts
            decided_ndc = float(default_facts["conventions_block"][1])
            variants = dict(NEGATIVES, clip_ndc_flip_inverted={"ndc_flip": 0 if decided_ndc else 1})
            for name, config in variants.items():
                host.set_probe(**config)
                negative, _analysis = _probe_hidden(host, analyse)
                negatives[name] = (negative_verdict(default_facts, _readback_dict(negative)) if negative is not None
                                   else {"ok": False, "status": "no readback"})
        record["negative_controls"] = negatives
        checks["negative_controls_fail_where_they_change_anything"] = bool(negatives) and all(
            v.get("ok") for v in negatives.values())

        host.set_probe()
        host.frames(2)
        host.detach()
        previous = _driver(host.state(), "previous_driver")
        record["detached"] = previous
        checks["detach_released_on_the_render_thread"] = (
            previous.get("released") is True and previous.get("released_on_gui_thread") is False
            and previous.get("live_resources_before_release") == 10 and previous.get("probe_live_resources") == 0
            and previous.get("disconnected") is True)
        edges_at_detach = previous.get("edges")
        host.frames(5)
        checks["a_detached_driver_gets_no_edges"] = _driver(host.state(), "previous_driver").get("edges") == edges_at_detach

        host.attach()
        host.frames(5)
        again = _driver(host.state())
        checks["reattached_driver_records_from_its_first_edge"] = (again.get("edges") == 5
                                                                   and again.get("passes_recorded") == 0)
        host.set_probe()
        host.frames(2)
        readback2, analysis2 = _probe_hidden(host, analyse)
        record["probe_after_reattach"] = analysis2
        checks["probe_after_reattach_matches"] = bool(analysis2.get("pass"))
    finally:
        closed = host.close()
        record["close"] = closed
        _drop_item(app, item)
    steps = closed.get("steps", [])
    checks["close_releases_then_invalidates_then_deletes"] = (
        steps[-3:-1] == ["render control deleted (Qt's QRhi)", "window deleted"] if api == "vulkan"
        else steps[-2:] == ["render control deleted (Qt's QRhi)", "window deleted"])
    closed_driver = _driver(closed.get("state", {}), "previous_driver")
    checks["close_released_everything"] = closed_driver.get("released") is True and closed_driver.get(
        "probe_live_resources") == 0
    if api == "vulkan":
        checks["device_destroyed_after_the_window"] = (closed.get("device_teardown") == DEVICE_TEARDOWN
                                                       and steps[-1:] == ["device destroyed"])

    # The negative control of the thread probe: the same host rendering on the calling (GUI) thread, which has a Python
    # thread state, reports one on every edge.
    item2, _component2 = _content(engine)
    control = core.hidden_host(*HOST_SIZE, threaded=False)
    try:
        control.set_content(item2)
        control.frames(5)
        edge = _driver(control.state())
        record["thread_probe_negative_control"] = edge
        checks["negative_control_gui_thread_reports_python_thread_state"] = (
            edge.get("edges") == 5 and edge.get("edges_with_python_thread_state") == 5
            and edge.get("edges_on_gui_thread") == 5)
    finally:
        record["negative_control_close"] = control.close()
        _drop_item(app, item2)
    record["checks"] = checks
    record["pass"] = all(checks.values())
    return record


# --------------------------------------------------------------------------------------------------------- window

def _off_screen_window():
    """A real Qt Quick window that is shown but never visible (tests/_invisible_windows.py's keep_off_screen, inline)."""
    from PySide6.QtCore import Qt
    from PySide6.QtQuick import QQuickWindow

    window = QQuickWindow()
    window.setFlag(Qt.WindowType.FramelessWindowHint, True)
    window.setOpacity(0.0)
    window.setFlag(Qt.WindowType.WindowTransparentForInput, True)
    window.setFlag(Qt.WindowType.Tool, True)
    window.resize(*HOST_SIZE)
    return window


def _show(window) -> None:
    window.setOpacity(0.0)   # keep_off_screen's call, repeated where the window is shown
    window.show()


def _window_probe(app, host, analyse) -> tuple[object, dict]:
    host.request_readback()
    holder: list = []

    def ready() -> bool:
        if not holder:
            result = host.probe_result()
            if result is not None:
                holder.append(result)
        return bool(holder)

    _wait_until(app, ready)
    readback = holder[0] if holder else None
    return readback, (analyse(_readback_dict(readback)) if readback is not None else {"pass": False,
                                                                                         "error": "no readback"})


def round_window(core, engine, app, api: str, out: Path) -> dict:
    import shiboken6
    from probe_analysis import analyse

    record: dict = {}
    checks: dict = {}
    item, _component = _content(engine)
    window = _off_screen_window()
    item.setParentItem(window.contentItem())
    host = core.attach_host(window)       # before the window is first shown (D6 on Vulkan)
    try:
        host.set_probe()
        _show(window)
        checks["frames_arrive"] = _wait_until(app, lambda: window.isExposed()
                                              and _driver(host.state()).get("edges", 0) >= WINDOW_FRAMES)
        readback, analysis = _window_probe(app, host, analyse)
        record["probe"] = analysis
        record["probe_png"] = _save_png(readback, out / f"n22_probe_{api}_window.png")
        state = host.state()
        driver = _driver(state)
        record["driver"] = driver
        record["render_loop_renders_on_gui_thread"] = driver.get("edges_on_gui_thread", 0) > 0
        checks["probe_matches_the_conventions"] = bool(analysis.get("pass"))
        checks["frame_edge_on_qts_render_thread"] = driver.get("edges_on_gui_thread") == 0
        checks["no_python_thread_state_on_the_frame_edge"] = driver.get("edges_with_python_thread_state") == 0
        checks["probe_recorded_every_edge"] = driver.get("passes_recorded") == driver.get("edges") - driver.get(
            "edges_without_command_buffer", 0) and driver.get("passes_recorded", 0) >= WINDOW_FRAMES
        if api == "vulkan":
            checks["window_runs_on_the_modules_device"] = state.get("device_alive") is True and bool(
                state.get("device", {}).get("vk_device"))

        host.detach()
        released = _wait_until(app, lambda: _driver(host.state(), "previous_driver").get("released") is True)
        previous = _driver(host.state(), "previous_driver")
        record["detached"] = previous
        checks["detach_released_at_a_frame_edge_on_the_render_thread"] = (
            released and previous.get("released_on_gui_thread") is False
            and previous.get("release_reason") == "detached: released at the frame edge"
            and previous.get("live_resources_before_release") == 10 and previous.get("disconnected") is True)
        edges_at_release = previous.get("edges")
        _pump(app, 0.3)
        checks["a_detached_driver_gets_no_edges"] = _driver(host.state(), "previous_driver").get(
            "edges") == edges_at_release

        host.attach()
        host.set_probe()
        checks["reattached_driver_gets_edges"] = _wait_until(
            app, lambda: _driver(host.state()).get("passes_recorded", 0) >= 5)
        readback2, analysis2 = _window_probe(app, host, analyse)
        record["probe_after_reattach"] = analysis2
        checks["probe_after_reattach_matches"] = bool(analysis2.get("pass"))

        # Destroyed while it animates: Qt's render thread is rendering when the GUI thread deletes the window.
        edges_before = _driver(host.state()).get("edges", 0)
        shiboken6.delete(window)
        window = None
        _flush_deletes(app)
        state = host.state()
        destroyed = _driver(state)
        record["destroyed_mid_frame"] = {"edges_before": edges_before, "state": state}
        checks["window_destroyed_mid_frame_released_on_the_render_thread"] = (
            state.get("window_destroyed") is True and destroyed.get("probe_live_resources") == 0
            and destroyed.get("release_reason") == "scene graph invalidated"
            and destroyed.get("released_on_gui_thread") is False
            and destroyed.get("live_resources_before_release") == 10)
        if api == "vulkan":
            checks["device_destroyed_after_the_window"] = (state.get("device_alive") is False
                                                           and state.get("device_teardown") == DEVICE_TEARDOWN)
    finally:
        if window is not None and shiboken6.isValid(window):
            shiboken6.delete(window)
        record["close"] = host.close()
        _drop_item(app, item)
    record["checks"] = checks
    record["pass"] = all(checks.values())
    return record


# --------------------------------------------------------------------------------------------------------- lifecycle

def _cycle_window(core, engine, app, with_core: bool) -> bool:
    import shiboken6

    item, _component = _content(engine)
    window = _off_screen_window()
    item.setParentItem(window.contentItem())
    host = core.attach_host(window) if with_core else None
    ok = True
    try:
        if host is not None:
            host.set_probe()
        _show(window)
        if host is not None:
            ok = _wait_until(app, lambda: _driver(host.state()).get("passes_recorded", 0) >= 10)
            host.detach()
            ok = ok and _wait_until(app, lambda: _driver(host.state(), "previous_driver").get("released") is True)
            host.attach()
            ok = ok and _wait_until(app, lambda: _driver(host.state()).get("edges", 0) >= 5)
        else:
            ok = _wait_until(app, window.isExposed)
            _pump(app, 0.25)
        shiboken6.delete(window)           # while it animates
        window = None
        _flush_deletes(app)
        if host is not None:
            destroyed = host.state()
            ok = (ok and destroyed.get("window_destroyed") is True
                  and _driver(destroyed).get("release_reason") == "scene graph invalidated"
                  and _driver(destroyed).get("probe_live_resources") == 0)
    finally:
        if window is not None and shiboken6.isValid(window):
            shiboken6.delete(window)
        if host is not None:
            host.close()
        _drop_item(app, item)
    return bool(ok)


def _cycle_hidden(core, engine, app) -> bool:
    from probe_analysis import analyse

    item, _component = _content(engine)
    host = core.hidden_host(*HOST_SIZE)
    try:
        host.set_content(item)
        host.set_probe()
        host.frames(PROBE_FRAMES)
        _readback, analysis = _probe_hidden(host, analyse)
        host.detach()
        host.attach()
        host.frames(3)
        ok = bool(analysis.get("pass")) and _driver(host.state()).get("edges") == 3
    finally:
        host.close()
        _drop_item(app, item)
    return ok


def _cycle_hidden_qt_alone(engine, app) -> bool:
    """The hidden host's control: Qt alone, the same sequence on a QThread (a render control prepared for the thread,
    initialised, a preserving target, 5 frames, invalidated, the OpenGL context handed back, deleted on the GUI thread),
    driven from Python with no native core. Not on Vulkan: PySide6 has no QVulkanInstance to give the window."""
    import queue

    import shiboken6
    from PySide6.QtCore import QSize, QSizeF, QThread
    from PySide6.QtGui import (QOpenGLContext, QRhiColorAttachment, QRhiTexture, QRhiTextureRenderTarget,
                               QRhiTextureRenderTargetDescription)
    from PySide6.QtQuick import QQuickRenderControl, QQuickRenderTarget, QQuickWindow

    class Worker(QThread):
        def __init__(self):
            super().__init__()
            self.jobs, self.done = queue.Queue(), queue.Queue()

        def run(self):
            while True:
                job = self.jobs.get()
                if job is None:
                    return
                try:
                    self.done.put((True, job()))
                except Exception as exc:  # noqa: BLE001  handed back to the GUI thread
                    self.done.put((False, exc))

    worker = Worker()
    worker.start()

    def call(fn):
        worker.jobs.put(fn)
        ok, value = worker.done.get()
        if not ok:
            raise value
        return value

    item, _component = _content(engine)
    control = QQuickRenderControl()
    window = QQuickWindow(control)                # never shown
    window.setGeometry(0, 0, *HOST_SIZE)
    window.contentItem().setSize(QSizeF(*HOST_SIZE))
    item.setParentItem(window.contentItem())
    control.prepareThread(worker)
    held: dict = {}
    gui = app.thread()

    def init():
        if not control.initialize():
            raise RuntimeError("QQuickRenderControl::initialize failed")
        rhi = control.rhi()
        texture = rhi.newTexture(QRhiTexture.Format.RGBA8, QSize(*HOST_SIZE), 1, QRhiTexture.Flag.RenderTarget)
        texture.create()
        target = rhi.newTextureRenderTarget(QRhiTextureRenderTargetDescription(QRhiColorAttachment(texture)),
                                            QRhiTextureRenderTarget.Flag.PreserveColorContents)
        rp = target.newCompatibleRenderPassDescriptor()
        target.setRenderPassDescriptor(rp)
        target.create()
        window.setRenderTarget(QQuickRenderTarget.fromRhiRenderTarget(target))
        held.update(target=target, rp=rp, texture=texture)

    def frame():
        control.beginFrame()
        control.sync()
        control.render()
        control.endFrame()

    def end():
        window.setRenderTarget(QQuickRenderTarget())
        for key in ("target", "rp", "texture"):
            shiboken6.delete(held.pop(key))
        control.invalidate()
        context = QOpenGLContext.currentContext()
        if context is not None:
            context.doneCurrent()
            context.moveToThread(gui)

    try:
        call(init)
        for _ in range(5):
            control.polishItems()
            call(frame)
        call(end)
    finally:
        worker.jobs.put(None)
        worker.wait()
        item.setParentItem(None)
        shiboken6.delete(control)
        shiboken6.delete(window)
        shiboken6.delete(worker)
        _drop_item(app, item)
    return True


def _series(core, app, run, cycles: int) -> dict:
    for _ in range(LIFECYCLE_WARMUP_CYCLES):
        run()
    _flush_deletes(app)
    readings, oks = [], []
    for _ in range(cycles):
        oks.append(run())
        _flush_deletes(app)
        readings.append(core.process_counters())
    handles = [r["handles"] for r in readings]
    users = [r["user_objects"] for r in readings]
    private = [r.get("private_mib", 0.0) for r in readings]
    half = max(1, len(private) // 2)
    return {
        "cycles_ok": oks, "readings": readings,
        "handle_slope_per_cycle": _slope(handles),
        "user_object_slope_per_cycle": _slope(users),
        "threads_last_minus_first": readings[-1]["threads"] - readings[0]["threads"],
        # A leak raises the troughs; a driver's block allocator moves the readings up and down by whole blocks (32 or
        # 64 MiB on Vulkan, measured 13 Nov), so the troughs of the two halves are compared, never single readings.
        "private_trough_growth_mib": round(min(private[half:]) - min(private[:half]), 1),
        "private_range_mib": round(max(private) - min(private), 1),
        "private_slope_mib_per_cycle": _slope(private),
    }


def _against(ours: dict, control: dict) -> dict:
    """Our kind against its control: the core may add nothing Qt alone does not show on this API."""
    tolerance = max(PRIVATE_PLATEAU_TOLERANCE_MIB, control["private_range_mib"])
    return {
        "handles": (ours["handle_slope_per_cycle"] is not None and control["handle_slope_per_cycle"] is not None
                    and ours["handle_slope_per_cycle"] <= max(control["handle_slope_per_cycle"], 0.0)
                    + HANDLE_SLOPE_TOLERANCE),
        "user_objects": (ours["user_object_slope_per_cycle"] is not None
                         and control["user_object_slope_per_cycle"] is not None
                         and ours["user_object_slope_per_cycle"] <= max(control["user_object_slope_per_cycle"], 0.0)
                         + HANDLE_SLOPE_TOLERANCE),
        "private_bytes": ours["private_trough_growth_mib"] <= max(control["private_trough_growth_mib"], 0.0)
        + tolerance,
        "private_tolerance_mib": tolerance,
    }


def round_lifecycle(core, engine, app, api: str, cycles: int) -> dict:
    """Each kind of ours runs right after its control (Qt alone doing the same on the same API, in the same process
    state), after a warm-up long enough for the drivers' own pools (D3D12 grows in 8 MiB steps for about 8 creations).
    The hidden host's control is Qt's threaded render control; on Vulkan, where PySide6 cannot give a render control
    its instance, it is the Qt-only window, which also creates one device per cycle (NVIDIA keeps 3 handles per device
    whoever creates it, N0.6). Findings behind these references: Native_Core_N06_N07_Qt_Facts.md section J."""
    pairs = [("window_qt_alone", "window_with_core"),
             ("window_qt_alone" if api == "vulkan" else "hidden_qt_alone", "hidden_host")]
    runs = {
        "window_qt_alone": lambda: _cycle_window(core, engine, app, with_core=False),
        "window_with_core": lambda: _cycle_window(core, engine, app, with_core=True),
        "hidden_qt_alone": lambda: _cycle_hidden_qt_alone(engine, app),
        "hidden_host": lambda: _cycle_hidden(core, engine, app),
    }
    series: dict = {}
    for control, ours in pairs:
        for kind in (control, ours):
            if kind in series:
                continue
            if api == "vulkan":
                core.set_vulkan_phase(f"lifecycle {kind}")
            series[kind] = _series(core, app, runs[kind], cycles)
    checks: dict = {}
    comparisons: dict = {}
    for kind, s in series.items():
        checks[f"{kind}_every_cycle_ok"] = all(s["cycles_ok"])
        checks[f"{kind}_threads_flat"] = abs(s["threads_last_minus_first"]) <= THREAD_TOLERANCE
    for control, ours in pairs:
        result = _against(series[ours], series[control])
        comparisons[ours] = dict(result, control=control)
        for measure in ("handles", "user_objects", "private_bytes"):
            checks[f"{ours}_{measure}_no_more_than_{control}"] = result[measure]
    return {"cycles": cycles, "warmup": LIFECYCLE_WARMUP_CYCLES, "series": series, "comparisons": comparisons,
            "checks": checks, "pass": all(checks.values()), "live_hosts_after": core.live_hosts()}


# --------------------------------------------------------------------------------------------------------- child

def child(args) -> dict:
    root = _root(args.repo)
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

    api_enum = QSGRendererInterface.GraphicsApi
    QQuickWindow.setGraphicsApi({"opengl": api_enum.OpenGL, "vulkan": api_enum.Vulkan,
                                 "d3d11": api_enum.Direct3D11, "d3d12": api_enum.Direct3D12}[args.api])
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlEngine

    app = QGuiApplication([sys.argv[0]])
    from rendering.native import NativeCoreUnavailable, load

    # module_loaded and instance_created say how far the child got: the verdict judges only what ran.
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
    try:
        core = load((root / args.module_dir) if not Path(args.module_dir).is_absolute() else Path(args.module_dir))
    except NativeCoreUnavailable as exc:
        record["error"] = f"the module did not load: {exc.reason}"
        return record
    record["module_loaded"] = True
    record["runtime"] = dict(core.info)
    out = Path(args.out_dir)
    vulkan = args.api == "vulkan"
    if vulkan:
        instance = core.vulkan_instance(validation=True)
        record["instance"] = instance
        if not instance.get("ok"):
            record["error"] = f"the Vulkan instance failed: {instance.get('instance', {}).get('error')}"
            return record
        record["instance_created"] = True
    engine = QQmlEngine()
    try:
        for name in args.rounds:
            if vulkan:
                core.set_vulkan_phase(name)
            try:
                if name == "hidden":
                    record[name] = round_hidden(core, engine, app, args.api, out)
                elif name == "window":
                    record[name] = round_window(core, engine, app, args.api, out)
                else:
                    record[name] = round_lifecycle(core, engine, app, args.api, args.cycles)
            except Exception:
                record[name] = {"pass": False, "error": traceback.format_exc()}
    finally:
        _flush_deletes(app)
        record["live_hosts_at_end"] = core.live_hosts()
        if vulkan:
            teardown = core.destroy_vulkan_instance()
            messages = teardown.pop("messages", {}) if isinstance(teardown, dict) else {}
            summary = vk_validation.validation_summary(messages)
            layer = bool(record["instance"].get("validation_layer_loaded"))
            record["instance_teardown"] = teardown
            record["validation"] = {"layer_loaded": layer, "per_phase": messages.get("per_phase"),
                                    **{k: v for k, v in summary.items() if k != "groups"},
                                    "attribution": summary["groups"]}
        del engine
    return record


# --------------------------------------------------------------------------------------------------------- verdict

def api_verdict(api: str, record: dict, require_validation: bool) -> tuple[bool, list[str]]:
    """What failed on one API. A child that stopped before the module loaded (or, on Vulkan, before the instance
    existed) reports that one reason alone: nothing after it ran, so no round, validation or teardown is judged."""
    error = (record.get("error") or "").strip()
    if not record.get("module_loaded"):
        return False, [f"{api}: {error.splitlines()[0] if error else 'the module did not load'}"]
    if api == "vulkan" and not record.get("instance_created"):
        return False, [f"{api}: {error.splitlines()[0] if error else 'the Vulkan instance was not created'}"]
    failed: list[str] = []
    if error:
        failed.append(f"{api}: {error.splitlines()[0]}")
    for name in record.get("rounds", []):
        entry = record.get(name, {})
        if not entry.get("pass"):
            bad = [k for k, v in entry.get("checks", {}).items() if not v] or [
                (entry.get("error") or "did not run").strip().splitlines()[-1]]
            failed.append(f"{api} {name}: {', '.join(bad)}")
    if record.get("live_hosts_at_end", 0) != 0:
        failed.append(f"{api}: {record['live_hosts_at_end']} host(s) left open")
    if api == "vulkan":
        v = record.get("validation") or {}
        if not v.get("layer_loaded"):
            if require_validation:
                failed.append("vulkan: the validation layer did not load (--require-validation)")
        elif not v.get("clean"):
            failed.append(f"vulkan: validation not clean ({v.get('unexplained_errors')} errors, "
                          f"{v.get('unexplained_warnings')} warnings unexplained)")
        if (record.get("instance_teardown") or {}).get("ok") is not True:
            failed.append("vulkan: the instance teardown was refused (a device still live)")
    return not failed, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--rounds", nargs="+", default=list(ROUNDS), choices=ROUNDS)
    parser.add_argument("--cycles", type=int, default=LIFECYCLE_CYCLES)
    parser.add_argument("--label", default="n22_hosts")
    parser.add_argument("--layer-path", type=Path, default=None,
                        help="the folder holding VkLayer_khronos_validation.json (VK_ADD_LAYER_PATH for this run only)")
    parser.add_argument("--require-validation", action="store_true",
                        help="a Vulkan run whose validation layer did not load is a FAIL, never a pass")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--api", choices=APIS, help=argparse.SUPPRESS)
    parser.add_argument("--out-dir", help=argparse.SUPPRESS)
    parser.add_argument("--child-json", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.child:
        try:
            record = child(args)
        except Exception:
            text = traceback.format_exc()
            record = {"api": args.api, "error": text.strip().splitlines()[-1], "traceback": text}
        args.child_json.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        return 0

    vk_validation.use_layer_path(args.layer_path, _ALLOWED_ENV)   # inherited by the children
    root = _root(args.repo)
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", "n2_2", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    for api in args.apis:
        child_json = out / f"child_{api}.json"
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--cycles", str(args.cycles), "--rounds", *args.rounds]
        started = time.monotonic()
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S, cwd=str(root))
            exit_code, stderr = proc.returncode, proc.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code, stderr = "timeout", (exc.stderr or b"").decode(errors="replace") if isinstance(
                exc.stderr, bytes) else str(exc.stderr or "")
        record = json.loads(child_json.read_text(encoding="utf-8")) if child_json.exists() else {
            "api": api, "rounds": list(args.rounds), "error": f"the child process ended without a record ({exit_code})"}
        child_json.unlink(missing_ok=True)
        record["exit_code"] = exit_code
        record["seconds"] = round(time.monotonic() - started, 1)
        if exit_code != 0 or record.get("error"):
            record["stderr_tail"] = (stderr or "")[-4000:]
        results[api] = record

    verdicts = {api: api_verdict(api, record, args.require_validation) for api, record in results.items()}
    failed = [reason for _ok, reasons in verdicts.values() for reason in reasons]
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "rounds": args.rounds, "cycles": args.cycles, "environment": environment,
               "require_validation": args.require_validation,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons) + ")"))
        v = results[api].get("validation")
        if v:
            print(f"  validation: layer {'loaded' if v.get('layer_loaded') else 'NOT loaded'}, "
                  f"excused {v.get('recorded_qt_defects_excused')}, unexplained errors {v.get('unexplained_errors')}, "
                  f"warnings {v.get('unexplained_warnings')}")
    print(f"evidence: {out / 'summary.json'}")
    print("N22 VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
