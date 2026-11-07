"""P1 toolchain spike driver: native QRhi rendering inside our PySide6 process.

Runs offscreen only: no window is ever shown. The graphics API is chosen inside
the process (QQuickWindow.setGraphicsApi before QGuiApplication), one backend
per child process because Qt Quick's graphics API is process-global.

Parts:
  rhi     standalone native QRhi on a native QThread, every backend, PNG each
  gil     render-thread GIL independence (native thread vs a GIL-taking control)
  hybrid  Qt Quick hosts a PySide6 QSGRenderNode that delegates to native QRhi
          recording into Quick's own command buffer (ABI/RHI sharing proof)
  quick   part B: C++ QQuickItem + QSGRenderNode registered from the module,
          rendered by QQuickRenderControl on a separate render thread
  all     everything above that the built module supports

Usage (repository venv):
  python native/spike_p1/python/run_spike.py --module-dir <build dir> [--part all]
Evidence goes to .artifacts/evidence/architecture/native_core_p1/<date>_<label>/.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKENDS = ("d3d11", "d3d12", "vulkan", "opengl")
WIDTH, HEIGHT = 960, 540


def _evidence_dir(label: str) -> Path:
    sys.path.insert(0, str(REPO_ROOT))
    from tools import artifact_paths

    folder = artifact_paths.evidence_dir("architecture", "native_core_p1", label)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _import_native(module_dir: Path):
    # PySide6 first: its Qt DLLs are the ones the module must bind to.
    import PySide6

    os.add_dll_directory(str(Path(PySide6.__file__).parent))
    sys.path.insert(0, str(module_dir))
    import _srpss_native_spike as native

    return native


def _ptr(obj) -> int:
    import shiboken6

    return shiboken6.getCppPointer(obj)[0]


def _frame_summary(frame_ms: list[float]) -> dict:
    if not frame_ms:
        return {}
    ordered = sorted(frame_ms)
    return {
        "frames": len(frame_ms),
        "median_ms": round(statistics.median(ordered), 3),
        "p90_ms": round(ordered[int(0.9 * (len(ordered) - 1))], 3),
        "max_ms": round(ordered[-1], 3),
    }


def _graphics_api(backend: str):
    from PySide6.QtQuick import QSGRendererInterface

    api = QSGRendererInterface.GraphicsApi
    return {"d3d11": api.Direct3D11, "d3d12": api.Direct3D12, "vulkan": api.Vulkan,
            "opengl": api.OpenGL}[backend]


# --------------------------------------------------------------------- rhi / gil

def run_rhi(native, out: Path) -> dict:
    results = {}
    for backend in BACKENDS:
        png = out / f"rhi_{backend}.png"
        try:
            handle = native.rhi_offscreen_start(backend, WIDTH, HEIGHT, 120, 4096, str(png))
            r = native.rhi_offscreen_join(handle)
        except RuntimeError as exc:
            r = {"ok": False, "error": str(exc)}
        r["timing"] = _frame_summary(r.pop("frame_ms", []))
        r["png"] = str(png) if r.get("ok") else None
        results[backend] = r
    return results


def _spin_until_done(native, handle) -> int:
    """Pure-Python busy loop that keeps the GIL until the native run ends."""
    n = 0
    while not native.rhi_offscreen_done(handle):
        n += 1
    return n


def run_gil(native, backend: str = "d3d11") -> dict:
    out = {}
    for gil_per_frame in (False, True):
        for python_busy in (False, True):
            handle = native.rhi_offscreen_start(backend, WIDTH, HEIGHT, 240, 4096, "", gil_per_frame)
            spins = _spin_until_done(native, handle) if python_busy else 0
            r = native.rhi_offscreen_join(handle)
            key = ("render_thread_takes_gil" if gil_per_frame else "native_render_thread") + (
                "+python_busy" if python_busy else "+python_idle")
            out[key] = {
                "ok": r["ok"],
                "error": r["error"],
                "timing": _frame_summary(r["frame_ms"]),
                "python_loop_iterations_meanwhile": spins,
                "render_thread_is_caller": r["render_thread_id"] == r["caller_thread_id"],
                "frames_with_python_thread_state": r["frames_with_python_thread_state"],
            }
    return {"backend": backend, "switch_interval_s": sys.getswitchinterval(), "runs": out}


# --------------------------------------------------------------------- Qt Quick children

HYBRID_QML = b"""
import QtQuick
import SpikeHybrid 1.0
Rectangle {
    color: "#10121a"
    property real time: 0
    HybridQuadField { anchors.fill: parent; anchors.margins: 24; time: parent.time }
}
"""

NATIVE_QML = b"""
import QtQuick
import SrpssNativeSpike 1.0
Rectangle {
    color: "#10121a"
    property real time: 0
    QuadField { anchors.fill: parent; anchors.margins: 24; time: parent.time; instances: 4096 }
}
"""


def _make_hybrid_types(native):
    from PySide6.QtCore import Property, QRectF, Signal
    from PySide6.QtGui import QMatrix4x4
    from PySide6.QtQuick import QQuickItem, QSGNode, QSGRenderNode

    class HybridNode(QSGRenderNode):
        def __init__(self, window):
            super().__init__()
            self._window = window
            self._handle = native.hybrid_new(4096)
            self._w = self._h = 1.0
            self._t = 0.0

        def sync(self, w, h, t):
            self._w, self._h, self._t = max(1.0, w), max(1.0, h), t

        def prepare(self):
            m = QMatrix4x4(self.projectionMatrix()) * QMatrix4x4(self.matrix())
            m.scale(self._w, self._h)
            cols = []
            for c in range(4):
                v = m.column(c)
                cols += [v.x(), v.y(), v.z(), v.w()]
            native.hybrid_prepare(self._handle, _ptr(self._window.rhi()), _ptr(self.commandBuffer()),
                                  _ptr(self.renderTarget()), struct.pack("16f", *cols),
                                  self._t, self._w / self._h)

        def render(self, state):
            native.hybrid_render(self._handle, _ptr(self.commandBuffer()), _ptr(self.renderTarget()))

        def releaseResources(self):
            native.hybrid_release(self._handle)

        def changedStates(self):
            return QSGRenderNode.StateFlag.ViewportState

        def flags(self):
            f = QSGRenderNode.RenderingFlag
            return f.BoundedRectRendering | f.NoExternalRendering

        def rect(self):
            return QRectF(0, 0, self._w, self._h)

    class HybridQuadField(QQuickItem):
        timeChanged = Signal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setFlag(QQuickItem.Flag.ItemHasContents, True)
            self._time = 0.0
            self._node = None

        def _get_time(self):
            return self._time

        def _set_time(self, value):
            self._time = float(value)
            self.timeChanged.emit()
            self.update()

        time = Property(float, _get_time, _set_time, notify=timeChanged)

        def updatePaintNode(self, old, data):
            if self._node is None:
                self._node = HybridNode(self.window())  # kept referenced: Python overrides live here
            self._node.sync(self.width(), self.height(), self._time)
            self._node.markDirty(QSGNode.DirtyStateBit.DirtyMaterial)
            return self._node

    return HybridQuadField


def child_quick(native, part: str, backend: str, out: Path) -> dict:
    from PySide6.QtCore import QSizeF, QUrl
    from PySide6.QtGui import QGuiApplication, QRhiTextureRenderTarget
    from PySide6.QtQml import QQmlComponent, QQmlEngine, qmlRegisterType
    from PySide6.QtQuick import QQuickRenderControl, QQuickRenderTarget, QQuickWindow
    import shiboken6

    QQuickWindow.setGraphicsApi(_graphics_api(backend))  # inside the process, before the app
    app = QGuiApplication([sys.argv[0]])
    result: dict = {"part": part, "backend": backend}

    if part == "hybrid":
        qmlRegisterType(_make_hybrid_types(native), "SpikeHybrid", 1, 0, "HybridQuadField")
    control = QQuickRenderControl()
    window = QQuickWindow(control)  # never shown
    if backend == "vulkan":
        native.vulkan_attach(_ptr(window))
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(HYBRID_QML if part == "hybrid" else NATIVE_QML, QUrl())
    root = component.create()
    if root is None:
        result.update(ok=False, error=component.errorString())
        return result
    root.setParentItem(window.contentItem())
    window.setGeometry(0, 0, WIDTH, HEIGHT)
    window.contentItem().setSize(QSizeF(WIDTH, HEIGHT))
    root.setSize(QSizeF(WIDTH, HEIGHT))
    native.probe_reset()

    if part == "hybrid":
        if not control.initialize():
            result.update(ok=False, error="QQuickRenderControl.initialize failed")
            return result
        rhi = control.rhi()
        target, rt_ptr = native.target_new(_ptr(rhi), WIDTH, HEIGHT)
        window.setRenderTarget(QQuickRenderTarget.fromRhiRenderTarget(
            shiboken6.wrapInstance(rt_ptr, QRhiTextureRenderTarget)))

        def frames(count: int, png: str | None) -> list[float]:
            times, readback = [], None
            for i in range(count):
                t0 = time.perf_counter()
                root.setProperty("time", i / 60.0)
                control.polishItems()
                control.beginFrame()
                control.sync()
                control.render()
                if png and i == count - 1:
                    readback = native.readback_enqueue(_ptr(rhi), _ptr(control.commandBuffer()), target)
                control.endFrame()
                times.append((time.perf_counter() - t0) * 1000.0)
            if readback is not None:
                result["image"] = native.readback_save(readback, png, rhi.isYUpInFramebuffer())
            return times

        png = str(out / f"quick_hybrid_{backend}.png")
        result["backend_name"] = rhi.backendName()
        driver_info = rhi.driverInfo()  # keep the value alive: its QByteArray member is borrowed
        result["device"] = bytes(driver_info.deviceName).decode(errors="replace")
        result["timing_python_idle"] = _frame_summary(frames(120, png))
        stop = threading.Event()
        spins = [0]

        def hog():
            while not stop.is_set():
                spins[0] += 1

        thread = threading.Thread(target=hog, daemon=True)
        thread.start()
        result["timing_python_busy"] = _frame_summary(frames(60, None))
        stop.set()
        thread.join()
        result["python_loop_iterations_meanwhile"] = spins[0]
        result["probe"] = native.probe_stats("hybrid")
        result["png"] = png if result.get("image", {}).get("saved") else None
        result["ok"] = bool(result["png"])
        window.setRenderTarget(QQuickRenderTarget())
        native.target_free(target)
    else:
        # Sync and render on a separate render thread; the GUI thread blocks during sync.
        session = native.quick_session_begin(_ptr(control), _ptr(window), WIDTH, HEIGHT, True)
        handle = session["handle"]
        png = str(out / f"quick_native_{backend}.png")
        r = native.quick_session_frames(handle, _ptr(root), 120, png)
        result.update(ok=r["ok"], error=r["error"], backend_name=session["backend"],
                      device=session["device"], timing_python_idle=_frame_summary(r["frame_ms"]),
                      render_thread_is_gui_thread=session["render_thread_id"] == session["gui_thread_id"],
                      lit_pixels=r["lit_pixels"], png=png if r["ok"] else None)
        result["probe_idle"] = native.probe_stats("native")
        # The same scene while a pure-Python thread holds the GIL throughout.
        native.probe_reset()
        stop = threading.Event()
        spins = [0]

        def hog():
            while not stop.is_set():
                spins[0] += 1

        thread = threading.Thread(target=hog, daemon=True)
        thread.start()
        r2 = native.quick_session_frames(handle, _ptr(root), 120)
        stop.set()
        thread.join()
        result["timing_python_busy"] = _frame_summary(r2["frame_ms"])
        result["python_loop_iterations_meanwhile"] = spins[0]
        result["probe_busy"] = native.probe_stats("native")
        native.quick_session_end(handle)
    del app
    return result


# --------------------------------------------------------------------- orchestration

def _compare_pngs(paths: dict[str, str]) -> dict:
    import numpy as np
    from PySide6.QtGui import QImage

    arrays = {}
    for name, path in paths.items():
        img = QImage(path).convertToFormat(QImage.Format.Format_RGBA8888)
        arrays[name] = np.frombuffer(img.constBits(), dtype=np.uint8).reshape(
            img.height(), img.bytesPerLine())[:, : img.width() * 4].astype(np.int16)
    names = sorted(arrays)
    if not names:
        return {}
    ref = names[0]
    return {f"{ref}_vs_{n}": {"mean_abs": round(float(np.abs(arrays[ref] - arrays[n]).mean()), 4),
                              "max_abs": int(np.abs(arrays[ref] - arrays[n]).max())}
            for n in names[1:] if arrays[n].shape == arrays[ref].shape}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", required=True, type=Path)
    parser.add_argument("--part", default="all", choices=("all", "rhi", "gil", "hybrid", "quick"))
    parser.add_argument("--backend", choices=BACKENDS)
    parser.add_argument("--label", default="spike")
    parser.add_argument("--child-json", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    native = _import_native(args.module_dir)
    out = _evidence_dir(args.label)

    if args.child_json:  # one Qt Quick backend in this process
        result = child_quick(native, args.part, args.backend, out)
        args.child_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 0

    from PySide6.QtGui import QGuiApplication

    info = native.runtime_info()
    summary: dict = {"runtime": info, "python": sys.version}
    quick_parts = []
    if args.part in ("all", "rhi", "gil"):
        app = QGuiApplication([sys.argv[0]])  # no window is created
        if args.part in ("all", "rhi"):
            summary["rhi"] = run_rhi(native, out)
            summary["rhi_cross_backend_diff"] = _compare_pngs(
                {b: r["png"] for b, r in summary["rhi"].items() if r.get("png")})
        if args.part in ("all", "gil"):
            summary["gil"] = run_gil(native)
        summary["runtime_after"] = native.runtime_info()["loaded_modules"]
        del app
    if args.part in ("all", "hybrid"):
        quick_parts.append("hybrid")
    if args.part in ("all", "quick") and info["with_quick"]:
        quick_parts.append("quick")

    for part in quick_parts:
        backends = [args.backend] if args.backend else list(BACKENDS)
        part_results = {}
        for backend in backends:
            child_json = out / f"child_{part}_{backend}.json"
            proc = subprocess.run(
                [sys.executable, __file__, "--module-dir", str(args.module_dir), "--part", part,
                 "--backend", backend, "--label", args.label, "--child-json", str(child_json)],
                capture_output=True, text=True, timeout=300)
            entry = json.loads(child_json.read_text(encoding="utf-8")) if child_json.exists() else {}
            entry["exit_code"] = proc.returncode
            if proc.returncode != 0 or not entry.get("ok"):
                entry["stderr_tail"] = proc.stderr[-2000:]
            part_results[backend] = entry
            child_json.unlink(missing_ok=True)
        summary[part] = part_results
        summary[f"{part}_cross_backend_diff"] = _compare_pngs(
            {b: r["png"] for b, r in part_results.items() if r.get("png")})

    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nevidence: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
