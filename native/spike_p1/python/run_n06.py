"""N0.6 driver (D6's proof, Current_Plan.md item 8b): the module owns the Vulkan instance and device.

Harness only, nothing ships. Facts and build order: Docs/Future_Work/Native_Core_N06_N07_Qt_Facts.md (section H).
Never shows a window and never sets an environment variable: the variables Qt and the Vulkan loader read are
recorded (they must be unset), and validation is enabled in code by the module when the layer is installed.

Rounds (one per GitHub build of the module):
  facts   round 1: the loader, instance layers and extensions, per GPU the queue families, Win32 present support,
          device extensions, supported features by name, the driver; Qt's own device at API 1.2 (the family and
          queue it chose, its QRhi feature flags, the features Qt enables by its rule).
  device  round 2: our VkInstance at API 1.2 (validation and synchronisation validation in code when the layer is
          installed, else "validation owed"), adopted by a QVulkanInstance; our VkDevice with Qt's feature set and
          one graphics+present queue; the spike scene (the C++ QuadField) in a hidden Qt Quick host
          (QQuickRenderControl, never shown) on Qt's own device and then on ours, pixel-compared; teardown windows
          first, then the device, then the instance.
  lifecycle  rounds 3 and 4: --cycles create/use/destroy cycles of our context with the second queue (D9's
          rule: the graphics family first; proved by an empty submit and a fence); in each, the hidden host on our
          device renders, its target is resized and it renders again; the first cycle also runs Qt's own device
          and is pixel-compared before and after the resize. Handles, threads, GDI/USER objects, private bytes and
          the GPU heap usage are read after every teardown and must return to the first cycle's values; a last
          cycle forces the second queue's absence (negative control; --force-no-second-queue forces it always).
  owners  round 5: whose growth. Seven cycle kinds, each adding one owner to the one before (our raw
          VkInstance; Qt's adoption; our device; the reference instance; Qt's own device under the host; our host
          without readback; the full cycle), --cycles each (the full kind --long-cycles, for plateau versus linear
          growth). After every teardown: gc, then handles, threads, private bytes, GPU heaps and the Python gc
          object count; the handle count after every create, host and teardown step attributes the growth.

Usage (repository venv, the module built on GitHub):
  python native/spike_p1/python/run_n06.py --module-dir release/native_module --round facts --label n06_facts
  python native/spike_p1/python/run_n06.py --module-dir release/native_module --round device --label n06_device
  python native/spike_p1/python/run_n06.py --module-dir release/native_module --round lifecycle --label n06_lifecycle
  python native/spike_p1/python/run_n06.py --module-dir release/native_module --round owners --cycles 12 --label n06_owners
Evidence: .artifacts/evidence/native_core/n06/<date>_<label>/summary.json. Exit 0 whenever the probe ran; the
verdict is in the JSON and the last printed lines ("N06 VERDICT ...").
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from run_spike import HEIGHT, NATIVE_QML, WIDTH, _import_native, _frame_summary, _ptr  # noqa: E402

# Environment variables that change what Qt or the Vulkan loader does with layers, extensions, the GPU choice or
# Qt Quick's backend. The harness never sets them; any one set in the shell would contaminate the run.
CONTAMINATING_PREFIXES = ("QT_VULKAN", "QT_VK_", "QSG_", "QT_QUICK_BACKEND", "QT_RHI", "VK_")
RECORDED_PREFIXES = CONTAMINATING_PREFIXES + ("QT_QPA", "QT_OPENGL", "QT_D3D", "QT_QUICK", "VULKAN_SDK")

VALIDATION_LAYER = "VK_LAYER_KHRONOS_validation"


def _evidence_dir(label: str) -> Path:
    sys.path.insert(0, str(REPO_ROOT))
    from tools import artifact_paths

    folder = artifact_paths.evidence_dir("native_core", "n06", label)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def environment_record() -> dict:
    found = {k: v for k, v in sorted(os.environ.items()) if k.upper().startswith(RECORDED_PREFIXES)}
    contaminating = sorted(k for k in found if k.upper().startswith(CONTAMINATING_PREFIXES))
    return {"recorded": found, "contaminating_set": contaminating, "clean": not contaminating}


def decode_driver_version(vendor_id: int, raw: int) -> str:
    if vendor_id == 0x10DE:  # NVIDIA: 10.8.8.6 bits
        return f"{(raw >> 22) & 0x3FF}.{(raw >> 14) & 0xFF}.{(raw >> 6) & 0xFF}.{raw & 0x3F}"
    if vendor_id == 0x8086 and sys.platform == "win32":  # Intel on Windows: 18.14 bits
        return f"{raw >> 14}.{raw & 0x3FFF}"
    return f"{(raw >> 22) & 0x7F}.{(raw >> 12) & 0x3FF}.{raw & 0xFFF}"


def _rhi_feature_names(flags: dict) -> dict:
    from PySide6.QtGui import QRhi

    named = {}
    for key, supported in flags.items():
        try:
            name = QRhi.Feature(int(key)).name
        except ValueError:
            name = f"feature_{key}"
        named[name] = supported
    return named


def _api_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in text.split(".")[:2])


def qt_enabled_features(device: dict, instance_api: str) -> dict:
    """The features Qt's own device enables, by its rule (facts A6): every supported member of each structure
    its API version chains, except robustBufferAccess and robustImageAccess."""
    api = _api_tuple(instance_api)
    structures = ["vulkan10"]
    if api >= (1, 2):
        structures += ["vulkan11", "vulkan12"]
    if api >= (1, 3):
        structures.append("vulkan13")
    if api >= (1, 4):
        structures.append("vulkan14")
    excluded = {"robustBufferAccess", "robustImageAccess"}
    enabled, left_out = {}, []
    supported = device.get("supported_features", {})
    for name in structures:
        values = supported.get(name, {}).get("values", {})
        enabled[name] = sorted(k for k, v in values.items() if v and k not in excluded)
        left_out += sorted(k for k, v in values.items() if v and k in excluded)
    return {"structures": structures, "enabled": enabled,
            "enabled_count": sum(len(v) for v in enabled.values()),
            "supported_but_left_out": left_out}


def analyse_facts(facts: dict) -> dict:
    inst = facts.get("instance", {})
    qt = facts.get("qt_own_device", {})
    devices = inst.get("physical_devices", [])
    for dev in devices:
        dev["driver_version"] = decode_driver_version(dev.get("vendor_id", 0), dev.get("driver_version_raw", 0))
    if "rhi_feature_flags" in qt:
        qt["rhi_feature_flags"] = _rhi_feature_names(qt["rhi_feature_flags"])

    qt_dev = next((d for d in devices if d.get("vendor_id") == qt.get("vendor_id")
                   and d.get("device_id") == qt.get("device_id")), None)
    analysis: dict = {"qt_device_matched": qt_dev is not None}
    if qt_dev is not None:
        families = qt_dev.get("queue_families", [])
        idx = qt.get("queue_family_index", -1)
        fam = families[idx] if 0 <= idx < len(families) else {}
        analysis["qt_family"] = fam
        analysis["qt_family_graphics_and_present"] = ("graphics" in fam.get("flags", [])
                                                      and fam.get("win32_present") is True)
        analysis["second_queue_same_family"] = fam.get("queue_count", 0) >= 2
        analysis["other_compute_families"] = [f["index"] for f in families
                                              if f["index"] != idx and "compute" in f["flags"]]
        analysis["compute_only_families"] = [f["index"] for f in families
                                             if "compute" in f["flags"] and "graphics" not in f["flags"]]
        analysis["transfer_only_families"] = [f["index"] for f in families
                                              if "transfer" in f["flags"] and "graphics" not in f["flags"]
                                              and "compute" not in f["flags"]]
        exts = set(qt_dev.get("extensions", []))
        wanted = qt.get("preferred_extensions_for_imported_device", [])
        analysis["preferred_device_extensions_available"] = {e: e in exts for e in wanted}
        analysis["qt_enabled_features"] = qt_enabled_features(qt_dev, qt.get("instance_api_version", "1.0"))
        tables = {name: rec.get("table_complete") for name, rec in qt_dev.get("supported_features", {}).items()}
        analysis["feature_tables_complete"] = tables
    layers = {layer["name"]: layer for layer in inst.get("layers", [])}
    validation = layers.get(VALIDATION_LAYER)
    analysis["validation_layer"] = (
        {"present": True, "spec_version": validation["spec_version"], "extensions": validation["extensions"]}
        if validation else {"present": False, "status": "validation owed (layer not installed)"})
    return analysis


def round_facts(native, out: Path) -> dict:
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication([sys.argv[0]])  # no window is created
    facts = json.loads(native.n06_facts())
    loaded = native.runtime_info()["loaded_modules"]
    del app
    analysis = analyse_facts(facts) if facts.get("ok") else {}
    env = environment_record()
    checks = {
        "module_ok": bool(facts.get("ok")),
        "loader_api_at_least_1_2": _api_tuple(facts.get("instance", {}).get("loader_api_version", "0.0")) >= (1, 2),
        "physical_device_found": bool(facts.get("instance", {}).get("physical_devices")),
        "qt_own_device_created": "error" not in facts.get("qt_own_device", {"error": "missing"}),
        "qt_instance_api_1_2": facts.get("qt_own_device", {}).get("instance_api_version") == "1.2",
        "qt_device_matched": analysis.get("qt_device_matched", False),
        "qt_family_graphics_and_present": analysis.get("qt_family_graphics_and_present", False),
        "feature_tables_complete": bool(analysis.get("feature_tables_complete"))
        and all(analysis["feature_tables_complete"].values()),
        "environment_clean": env["clean"],
    }
    return {
        "round": "facts",
        "checks": checks,
        "pass": all(checks.values()),
        "validation": analysis.get("validation_layer", {}),
        "second_queue_same_family": analysis.get("second_queue_same_family"),
        "analysis": analysis,
        "environment": env,
        "vulkan_loader_dll": loaded.get("vulkan-1.dll"),
        "facts": facts,
    }


# --------------------------------------------------------------------- round 2: our instance and device

FRAMES = 120  # the spike's frame count; the last frame is read back (time = 119 / 60 s in both hosts)


def compare_pngs(a: Path, b: Path) -> dict:
    import numpy as np
    from PySide6.QtGui import QImage

    def load(path: Path):
        img = QImage(str(path)).convertToFormat(QImage.Format.Format_RGBA8888)
        if img.isNull():
            return None
        return np.frombuffer(img.constBits(), dtype=np.uint8).reshape(
            img.height(), img.bytesPerLine())[:, : img.width() * 4].astype(np.int16).copy()

    x, y = load(a), load(b)
    if x is None or y is None or x.shape != y.shape:
        return {"comparable": False}
    diff = np.abs(x - y)
    return {"comparable": True, "max_abs": int(diff.max()), "mean_abs": round(float(diff.mean()), 6),
            "differing_pixels": int((diff.reshape(diff.shape[0], -1, 4).max(axis=2) > 0).sum())}


def _quick_host(native, ours: bool, png: Path | None, next_frame_png: Path | None, *, frames_count: int = FRAMES,
                resize_to: tuple[int, int] | None = None, resized_png: Path | None = None,
                steps: list | None = None) -> dict:
    """The spike scene in a hidden Qt Quick host (QQuickRenderControl, never shown), on our device (ours) or on
    the device Qt creates (the reference instance); with resize_to, the target is then replaced at that size and
    the scene rendered again. png None: no readback at all. Everything is destroyed before returning: the render
    control (and with it Qt's QRhi), the scene, the window, the engine. steps, when given, receives the process
    handle count after each step (round 5's attribution)."""
    import gc

    import shiboken6
    from PySide6.QtCore import QCoreApplication, QEvent, QSizeF, QUrl
    from PySide6.QtGui import QImage, QRhi
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickRenderControl, QQuickWindow

    def mark(name: str) -> None:
        if steps is not None and hasattr(native, "n06_handle_count"):
            steps.append([name, native.n06_handle_count()])

    mark("host start")
    result: dict = {"host": "our_device" if ours else "qt_own_device", "ok": False}
    control = QQuickRenderControl()
    window = QQuickWindow(control)  # never shown
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    mark("control, window, engine created")
    root = None
    handle = None
    try:
        native.n06_attach_window(_ptr(window), ours)
        component.setData(NATIVE_QML, QUrl())
        root = component.create()
        if root is None:
            result["error"] = component.errorString()
            return result
        root.setParentItem(window.contentItem())
        window.setGeometry(0, 0, WIDTH, HEIGHT)
        window.contentItem().setSize(QSizeF(WIDTH, HEIGHT))
        root.setSize(QSizeF(WIDTH, HEIGHT))
        mark("scene created")
        try:
            session = native.quick_session_begin(_ptr(control), _ptr(window), WIDTH, HEIGHT, True)
        except RuntimeError as exc:
            result["error"] = f"quick_session_begin: {exc}"
            return result
        mark("session begun (render thread, QRhi, target)")
        handle = session["handle"]
        result.update(backend=session["backend"], device=session["device"], vk_device=session.get("vk_device", 0),
                      vk_queue_family=session.get("vk_queue_family", -1),
                      vk_queue_index=session.get("vk_queue_index", -1))
        frames = native.quick_session_frames(handle, _ptr(root), frames_count, str(png) if png else "")
        mark("frames rendered" + (" with readback" if png else ""))
        result.update(frames_ok=frames["ok"], frames_error=frames["error"], lit_pixels=frames["lit_pixels"],
                      pixel_checksum=frames["pixel_checksum"], timing=_frame_summary(frames["frame_ms"]),
                      png=str(png) if (frames["ok"] and png) else None)
        rhi = control.rhi()
        result["rhi_feature_flags"] = {f.name: bool(rhi.isFeatureSupported(f)) for f in QRhi.Feature} if rhi else {}
        del rhi
        if next_frame_png is not None:
            nxt = native.quick_session_frames(handle, _ptr(root), 1, str(next_frame_png))
            result["next_frame_png"] = str(next_frame_png) if nxt["ok"] else None
        result["ok"] = bool(frames["ok"]) and (frames["lit_pixels"] > 0 or not png)
        if resize_to is not None and resized_png is not None:
            w2, h2 = resize_to
            resize: dict = {"size": [w2, h2], "ok": False}
            try:
                native.quick_session_resize(handle, w2, h2)
                window.setGeometry(0, 0, w2, h2)
                window.contentItem().setSize(QSizeF(w2, h2))
                root.setSize(QSizeF(w2, h2))
                again = native.quick_session_frames(handle, _ptr(root), frames_count, str(resized_png))
                read = QImage(str(resized_png)) if again["ok"] else QImage()
                resize.update(frames_ok=again["ok"], frames_error=again["error"], lit_pixels=again["lit_pixels"],
                              read_size=[read.width(), read.height()], png=str(resized_png) if again["ok"] else None)
                del read
                resize["ok"] = bool(again["ok"]) and again["lit_pixels"] > 0 and resize["read_size"] == [w2, h2]
            except RuntimeError as exc:
                resize["error"] = str(exc)
            mark("resized and rendered with readback")
            result["resize"] = resize
            result["ok"] = result["ok"] and resize["ok"]
        return result
    finally:
        if handle is not None:
            native.quick_session_end(handle)  # invalidates the scene graph on the render thread, which then quits
            mark("session ended (render thread quit)")
        shiboken6.delete(control)  # Qt's QRhi on this window goes with it (Qt's render-control examples' order)
        mark("render control deleted (Qt's QRhi)")
        if root is not None:
            root.setParentItem(None)
            root.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            root = None
        shiboken6.delete(window)
        mark("scene and window deleted")
        del component
        del engine
        gc.collect()
        mark("engine deleted, gc")


def round_device(native, out: Path) -> dict:
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Vulkan)  # in the process, before the app
    app = QGuiApplication([sys.argv[0]])  # no window is ever shown
    facts = json.loads(native.n06_facts())
    facts_analysis = analyse_facts(facts) if facts.get("ok") else {}
    ctx = json.loads(native.n06_context_create(True))
    hosts: dict = {}
    if ctx.get("ok"):
        native.n06_set_phase("render_qt_own_device")
        hosts["qt"] = _quick_host(native, False, out / "n06_quick_qt_own_device.png", None)
        native.n06_set_phase("render_our_device")
        hosts["ours"] = _quick_host(native, True, out / "n06_quick_our_device.png",
                                    out / "n06_quick_our_device_next_frame.png")
    teardown = json.loads(native.n06_context_destroy())  # windows are gone: device, then instances
    del app

    inst = ctx.get("instance", {})
    dev = ctx.get("device", {})
    adopted = inst.get("adopted", {})
    qt_host, our_host = hosts.get("qt", {}), hosts.get("ours", {})
    comparisons = {}
    if qt_host.get("png") and our_host.get("png"):
        comparisons["qt_own_device_vs_our_device"] = compare_pngs(Path(qt_host["png"]), Path(our_host["png"]))
    if our_host.get("png") and our_host.get("next_frame_png"):
        comparisons["negative_control_next_frame"] = compare_pngs(Path(our_host["png"]),
                                                                  Path(our_host["next_frame_png"]))
    identical = comparisons.get("qt_own_device_vs_our_device", {})
    negative = comparisons.get("negative_control_next_frame", {})

    rule = facts_analysis.get("qt_enabled_features", {}).get("enabled", {})
    ours_enabled = {name: sorted(k for k, v in rec.get("values", {}).items() if v)
                    for name, rec in dev.get("enabled_features", {}).items()}
    feature_diff = {name: {"only_ours": sorted(set(ours_enabled.get(name, [])) - set(rule.get(name, []))),
                           "only_qt_rule": sorted(set(rule.get(name, [])) - set(ours_enabled.get(name, [])))}
                    for name in sorted(set(rule) | set(ours_enabled))}
    preferred = facts.get("qt_own_device", {}).get("preferred_extensions_for_imported_device", [])
    messages = teardown.get("messages", {})
    layer_loaded = bool(inst.get("validation_layer_loaded"))

    checks = {
        "context_created": bool(ctx.get("ok")),
        "instance_adopted_api_1_2": adopted.get("same_vk_instance") is True and adopted.get("api_version") == "1.2",
        "adopted_lists_match": set(adopted.get("extensions", [])) == set(inst.get("extensions", []))
        and set(adopted.get("layers", [])) == set(inst.get("layers", [])),
        "graphics_present_family": "graphics" in dev.get("queue_family_flags", []),
        "preferred_device_extensions_enabled": bool(preferred)
        and all(e in dev.get("extensions", []) for e in preferred),
        "feature_tables_complete": bool(dev.get("enabled_features"))
        and all(rec.get("table_complete") for rec in dev.get("enabled_features", {}).values()),
        "feature_set_equals_qt_rule": bool(rule) and all(not d["only_ours"] and not d["only_qt_rule"]
                                                         for d in feature_diff.values()),
        "qt_host_rendered": bool(qt_host.get("ok")),
        "our_host_rendered": bool(our_host.get("ok")),
        "our_host_on_our_device": bool(our_host.get("vk_device")) and our_host.get("vk_device") == dev.get("vk_device")
        and our_host.get("vk_queue_family") == dev.get("queue_family_index") and our_host.get("vk_queue_index") == 0,
        "qt_host_on_its_own_device": bool(qt_host.get("vk_device"))
        and qt_host.get("vk_device") != dev.get("vk_device"),
        "rhi_feature_flags_equal": bool(qt_host.get("rhi_feature_flags"))
        and qt_host.get("rhi_feature_flags") == our_host.get("rhi_feature_flags"),
        "pixel_identical": identical.get("comparable") is True and identical.get("max_abs") == 0,
        "negative_control_detects_change": negative.get("comparable") is True and negative.get("max_abs", 0) > 0,
        "teardown_ok": bool(teardown.get("ok")) and teardown.get("device_wait_idle_ok") is True,
        "environment_clean": environment_record()["clean"],
    }
    owed = []
    if layer_loaded:
        checks["synchronisation_validation_on"] = bool(inst.get("synchronisation_validation"))
        checks["validation_clean"] = messages.get("errors", -1) == 0 and messages.get("warnings", -1) == 0
    else:
        owed.append(inst.get("validation", "validation owed"))
    return {
        "round": "device",
        "checks": checks,
        "pass": all(checks.values()),
        "owed": owed,
        "validation": {"status": inst.get("validation"), "messages": messages},
        "comparisons": comparisons,
        "feature_set_vs_qt_rule": feature_diff,
        "context": ctx,
        "hosts": hosts,
        "teardown": teardown,
        "environment": environment_record(),
    }


# --------------------------------------------------------------------- rounds 3 and 4: lifecycle and the second queue

CYCLE_FRAMES = 30
RESIZED = (1280, 720)
EXPECTED_TEARDOWN = ["vkDeviceWaitIdle: VK_SUCCESS", "vkDestroyDevice", "resetDeviceFunctions",
                     "reference QVulkanInstance destroyed", "adopting QVulkanInstance destroyed",
                     "vkDestroyDebugUtilsMessengerEXT", "vkDestroyInstance"]
# Bounds for "back to baseline" after the warm-up cycle (first run of the round sets them; any change is the lead's).
HANDLE_TOLERANCE = 8
THREAD_TOLERANCE = 1
GPU_HEAP_TOLERANCE_MIB = 2.0
PRIVATE_GROWTH_PER_CYCLE_MIB = 1.0


def _counters(native) -> dict:
    import gc

    gc.collect()
    return json.loads(native.n06_process_counters())


def _cycle(native, out: Path, index: int, queue_mode: str, with_reference: bool) -> dict:
    """One create/use/destroy cycle: our context, the hidden host on our device (render, resize, render), and,
    when asked, the same host on Qt's own device first; then the teardown (windows, device, instances)."""
    record: dict = {"cycle": index, "queue_mode": queue_mode}
    ctx = json.loads(native.n06_context_create(True, queue_mode))
    record["context_ok"] = bool(ctx.get("ok"))
    record["second_queue"] = ctx.get("device", {}).get("second_queue", {})
    record["queues_created"] = ctx.get("device", {}).get("queues_created")
    record["vk_device"] = ctx.get("device", {}).get("vk_device")
    record["queue_family_index"] = ctx.get("device", {}).get("queue_family_index")
    if index == 1:
        record["context"] = ctx
    tag = f"cycle{index:02d}_{queue_mode}"
    if ctx.get("ok"):
        if with_reference:
            native.n06_set_phase(f"{tag}_render_qt_own_device")
            record["qt_host"] = _quick_host(native, False, out / "n06_lifecycle_qt_own_device.png", None,
                                            frames_count=CYCLE_FRAMES, resize_to=RESIZED,
                                            resized_png=out / "n06_lifecycle_qt_own_device_resized.png")
        native.n06_set_phase(f"{tag}_render_our_device")
        keep = with_reference or queue_mode == "force_absent"
        png = out / (f"n06_lifecycle_our_device_{queue_mode}.png" if keep else "n06_cycle_scratch.png")
        resized = out / (f"n06_lifecycle_our_device_{queue_mode}_resized.png" if keep
                         else "n06_cycle_scratch_resized.png")
        record["our_host"] = _quick_host(native, True, png, None, frames_count=CYCLE_FRAMES, resize_to=RESIZED,
                                         resized_png=resized)
        for host in ("qt_host", "our_host"):
            record.get(host, {}).pop("rhi_feature_flags", None)
    teardown = json.loads(native.n06_context_destroy())
    record["teardown_steps"] = teardown.get("steps", [])
    record["teardown_ok"] = bool(teardown.get("ok")) and teardown.get("device_wait_idle_ok") is True
    record["messages"] = teardown.get("messages", {})
    record["validation"] = ctx.get("instance", {}).get("validation")
    record["validation_layer_loaded"] = bool(ctx.get("instance", {}).get("validation_layer_loaded"))
    record["counters_after"] = _counters(native)
    return record


def _delta(series: list[dict], key: str) -> float | None:
    if len(series) < 2 or key not in series[0] or key not in series[-1]:
        return None
    return round(series[-1][key] - series[0][key], 3)


def round_lifecycle(native, out: Path, cycles: int = 10, force_absent_all: bool = False) -> dict:
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Vulkan)
    app = QGuiApplication([sys.argv[0]])  # no window is ever shown
    facts = json.loads(native.n06_facts())
    facts_analysis = analyse_facts(facts) if facts.get("ok") else {}
    start = _counters(native)
    mode = "force_absent" if force_absent_all else "second"
    records = [_cycle(native, out, i, mode, with_reference=(i == 1)) for i in range(1, cycles + 1)]
    negative = _cycle(native, out, cycles + 1, "force_absent", with_reference=False)
    del app
    for scratch in ("n06_cycle_scratch.png", "n06_cycle_scratch_resized.png"):
        (out / scratch).unlink(missing_ok=True)

    first = records[0]
    after = [r["counters_after"] for r in records]  # after[0] is the baseline (after the warm-up cycle)
    baseline, last = after[0], after[-1]
    heap_deltas = [round(b.get("usage_mib", 0.0) - a.get("usage_mib", 0.0), 3)
                   for a, b in zip(baseline.get("gpu_heaps", []), last.get("gpu_heaps", []))]
    measured = max(1, len(after) - 1)
    private_growth = (_delta(after, "private_mib") or 0.0) / measured
    comparisons = {}
    qt_host, our_host = first.get("qt_host", {}), first.get("our_host", {})
    if qt_host.get("png") and our_host.get("png"):
        comparisons["before_resize_qt_vs_ours"] = compare_pngs(Path(qt_host["png"]), Path(our_host["png"]))
    if qt_host.get("resize", {}).get("png") and our_host.get("resize", {}).get("png"):
        comparisons["after_resize_qt_vs_ours"] = compare_pngs(Path(qt_host["resize"]["png"]),
                                                              Path(our_host["resize"]["png"]))
    family_facts = facts_analysis.get("qt_family", {})
    expect_same_family = family_facts.get("queue_count", 0) >= 2
    all_messages = [r["messages"] for r in records + [negative]]
    layer_loaded = all(r["validation_layer_loaded"] for r in records + [negative])

    def cycle_ok(r: dict) -> bool:
        host = r.get("our_host", {})
        return (r["context_ok"] and r["teardown_ok"] and bool(host.get("ok"))
                and host.get("vk_device") == r.get("vk_device") and host.get("vk_queue_index") == 0
                and host.get("vk_queue_family") == r.get("queue_family_index"))

    sq = [r["second_queue"] for r in records]
    checks = {
        "every_cycle_created_rendered_resized_and_tore_down": all(cycle_ok(r) for r in records),
        "teardown_order": all(r["teardown_steps"] == EXPECTED_TEARDOWN for r in records + [negative]),
        "qt_reference_host_ok": bool(qt_host.get("ok")),
        "pixel_identical_before_resize": comparisons.get("before_resize_qt_vs_ours", {}).get("max_abs") == 0,
        "pixel_identical_after_resize": comparisons.get("after_resize_qt_vs_ours", {}).get("max_abs") == 0,
        "handles_back_to_baseline": abs(_delta(after, "handles") or 0) <= HANDLE_TOLERANCE,
        "threads_back_to_baseline": abs(_delta(after, "threads") or 0) <= THREAD_TOLERANCE,
        "gpu_heaps_back_to_baseline": bool(baseline.get("gpu_budget_supported"))
        and all(abs(d) <= GPU_HEAP_TOLERANCE_MIB for d in heap_deltas),
        "private_bytes_flat": private_growth <= PRIVATE_GROWTH_PER_CYCLE_MIB,
        "no_messenger_errors": all(m.get("errors", -1) == 0 for m in all_messages),
        "environment_clean": environment_record()["clean"],
        "negative_control_cycle_ok": cycle_ok(negative),
        "negative_control_second_queue_absent": negative["second_queue"].get("found") is False,
    }
    if not force_absent_all:
        checks["second_queue_found_every_cycle"] = all(s.get("found") is True for s in sq)
        checks["second_queue_in_graphics_family_index_1"] = (not expect_same_family) or all(
            s.get("same_family_as_graphics") is True and s.get("index") == 1 for s in sq)
        checks["second_queue_executes"] = all(s.get("proof", {}).get("submit_ok") is True
                                              and s.get("proof", {}).get("handle_distinct") is True for s in sq)
    owed = []
    if layer_loaded:
        checks["validation_clean"] = all(m.get("errors", -1) == 0 and m.get("warnings", -1) == 0
                                         for m in all_messages)
    else:
        owed.append(first.get("validation") or "validation owed")
    warnings = sorted({s for m in all_messages for s in m.get("samples", [])})
    return {
        "round": "lifecycle",
        "checks": checks,
        "pass": all(checks.values()),
        "owed": owed,
        "cycles": cycles,
        "second_queue": {"expected_same_family": expect_same_family, "first_cycle": sq[0] if sq else {},
                         "negative_control": negative["second_queue"]},
        "counters": {"start": start, "after_each_cycle": after, "after_negative_control": negative["counters_after"],
                     "deltas_last_vs_baseline": {"handles": _delta(after, "handles"),
                                                 "threads": _delta(after, "threads"),
                                                 "gdi_objects": _delta(after, "gdi_objects"),
                                                 "user_objects": _delta(after, "user_objects"),
                                                 "private_mib": _delta(after, "private_mib"),
                                                 "gpu_heap_usage_mib": heap_deltas},
                     "private_growth_per_cycle_mib": round(private_growth, 3),
                     "tolerances": {"handles": HANDLE_TOLERANCE, "threads": THREAD_TOLERANCE,
                                    "gpu_heap_mib": GPU_HEAP_TOLERANCE_MIB,
                                    "private_growth_per_cycle_mib": PRIVATE_GROWTH_PER_CYCLE_MIB}},
        "comparisons": comparisons,
        "validation": {"status": first.get("validation"), "messenger_warning_texts": warnings},
        "records": records,
        "negative_control": negative,
        "environment": environment_record(),
    }


# --------------------------------------------------------------------- round 5: whose growth (owners)

# (kind, context parts, queue mode, host): each kind adds one owner to the one before it, so differences attribute
# growth.
OWNER_KINDS = (
    ("raw_instance", "raw_instance", "one", None),            # our VkInstance and messenger (loader and driver)
    ("instance_adopted", "instance", "one", None),            # + Qt's adopting QVulkanInstance
    ("device_one_queue", "device", "one", None),              # + our VkDevice, graphics queue only
    ("device", "device", "second", None),                     # + the second queue and its fence proof
    ("context_no_host", "full", "second", None),              # + the reference QVulkanInstance (Qt's vkCreateInstance)
    ("qt_host_only", "reference", "one", "qt_full"),          # Qt's own device under the same host, readback, resize
    ("our_host_no_readback", "full", "second", "ours_plain"),  # our host, frames only, no readback, no resize
    ("our_host_full", "full", "second", "ours_full"),         # the rounds 3-4 cycle (also the long series)
)
OWNER_WARMUP = 2
FLAT_HANDLES_PER_CYCLE = 0.05


def _slope(values: list[float]) -> float | None:
    n = len(values)
    if n < 2:
        return None
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    num = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values))
    den = sum((i - mean_x) ** 2 for i in range(n))
    return round(num / den, 4) if den else None


def _step_deltas(steps: list) -> list:
    """[[name, handles], ...] -> [[name, delta from the previous step], ...]"""
    return [[steps[i][0], steps[i][1] - steps[i - 1][1]] for i in range(1, len(steps))]


def _owner_cycle(native, out: Path, kind: str, parts: str, queue_mode: str, host: str | None) -> str:
    """One cycle of a kind; returned as a JSON string, so the kept records add no gc-tracked object and the
    Python gc object count measures what the cycle itself leaves behind."""
    import gc

    record: dict = {"kind": kind}
    ctx = json.loads(native.n06_context_create(True, queue_mode, parts))
    record["context_ok"] = bool(ctx.get("ok"))
    record["create_steps"] = _step_deltas([[s["step"], s["handles"]] for s in ctx.get("create_handles", [])])
    if host and ctx.get("ok"):
        steps: list = []
        scratch, scratch_resized = out / "n06_owner_scratch.png", out / "n06_owner_scratch_resized.png"
        if host == "qt_full":
            r = _quick_host(native, False, scratch, None, frames_count=CYCLE_FRAMES, resize_to=RESIZED,
                            resized_png=scratch_resized, steps=steps)
        elif host == "ours_plain":
            r = _quick_host(native, True, None, None, frames_count=CYCLE_FRAMES, steps=steps)
        else:
            r = _quick_host(native, True, scratch, None, frames_count=CYCLE_FRAMES, resize_to=RESIZED,
                            resized_png=scratch_resized, steps=steps)
        record["host_ok"] = bool(r.get("ok"))
        record["host_on_expected_device"] = (r.get("vk_device") == ctx.get("device", {}).get("vk_device")
                                             if host != "qt_full" else bool(r.get("vk_device")))
        record["host_steps"] = _step_deltas(steps)
        del r
    teardown = json.loads(native.n06_context_destroy())
    record["teardown_ok"] = bool(teardown.get("ok")) and teardown.get("device_wait_idle_ok", True) is True
    record["teardown_steps"] = _step_deltas([[s["step"], s["handles"]] for s in teardown.get("teardown_handles", [])])
    record["messenger_errors"] = teardown.get("messages", {}).get("errors", -1)
    record["validation_layer_loaded"] = bool(ctx.get("instance", {}).get("validation_layer_loaded"))
    del ctx, teardown
    gc.collect()
    record["counters_after"] = json.loads(native.n06_process_counters())
    record["python_gc_objects"] = len(gc.get_objects())
    return json.dumps(record)


def _mean_steps(records: list, key: str) -> list:
    """The mean handle delta of each named step over the measured (post warm-up) cycles."""
    totals: dict = {}
    order: list = []
    for r in records:
        for name, delta in r.get(key, []):
            if name not in totals:
                totals[name] = []
                order.append(name)
            totals[name].append(delta)
    return [[name, round(sum(totals[name]) / len(totals[name]), 3)] for name in order]


def _owner_summary(records: list) -> dict:
    measured = records[OWNER_WARMUP - 1:]  # the warm-up's last cycle is the baseline
    handles = [r["counters_after"]["handles"] for r in measured]
    private = [r["counters_after"].get("private_mib", 0.0) for r in measured]
    threads = [r["counters_after"]["threads"] for r in measured]
    gc_objects = [r["python_gc_objects"] for r in measured]
    heaps = [[h.get("usage_mib", 0.0) for h in r["counters_after"].get("gpu_heaps", [])] for r in measured]
    cycles = max(1, len(measured) - 1)
    return {
        "cycles": len(records),
        "handles_per_cycle": round((handles[-1] - handles[0]) / cycles, 3),
        "handles_series": [r["counters_after"]["handles"] for r in records],
        "private_mib_slope_per_cycle": _slope(private),
        "private_mib_series": [round(r["counters_after"].get("private_mib", 0.0), 1) for r in records],
        "threads_delta": threads[-1] - threads[0],
        "python_gc_objects_per_cycle": round((gc_objects[-1] - gc_objects[0]) / cycles, 2),
        "gpu_heap_delta_mib": [round(b - a, 3) for a, b in zip(heaps[0], heaps[-1])] if heaps else [],
        "mean_create_step_deltas": _mean_steps(measured[1:], "create_steps"),
        "mean_host_step_deltas": _mean_steps(measured[1:], "host_steps"),
        "mean_teardown_step_deltas": _mean_steps(measured[1:], "teardown_steps"),
    }


def round_owners(native, out: Path, cycles: int = 12, long_cycles: int = 40) -> dict:
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Vulkan)
    app = QGuiApplication([sys.argv[0]])  # no window is ever shown
    start = json.loads(native.n06_process_counters())
    kept: dict = {}
    for kind, parts, queue_mode, host in OWNER_KINDS:
        count = long_cycles if kind == "our_host_full" else cycles
        kept[kind] = [_owner_cycle(native, out, kind, parts, queue_mode, host) for _ in range(count)]
    del app
    kinds = {kind: [json.loads(text) for text in texts] for kind, texts in kept.items()}
    for scratch in ("n06_owner_scratch.png", "n06_owner_scratch_resized.png"):
        (out / scratch).unlink(missing_ok=True)

    summaries = {kind: _owner_summary(records) for kind, records in kinds.items()}
    per = {kind: s["handles_per_cycle"] for kind, s in summaries.items()}
    attribution = {
        "vkCreateInstance_and_destroy (loader, driver; ours)": per["raw_instance"],
        "Qt adopting QVulkanInstance": round(per["instance_adopted"] - per["raw_instance"], 3),
        "our VkDevice (graphics queue only)": round(per["device_one_queue"] - per["instance_adopted"], 3),
        "second queue and its fence proof": round(per["device"] - per["device_one_queue"], 3),
        "reference QVulkanInstance (Qt's own vkCreateInstance)": round(per["context_no_host"] - per["device"], 3),
        "our hidden host (Quick, render thread, Qt's QRhi on our device)":
            round(per["our_host_no_readback"] - per["context_no_host"], 3),
        "readback and resize": round(per["our_host_full"] - per["our_host_no_readback"], 3),
        "Qt's own device under the same host (with its instance)": per["qt_host_only"],
    }
    long_series = summaries["our_host_full"]["handles_series"][OWNER_WARMUP - 1:]
    half = len(long_series) // 2
    second_half_rate = round((long_series[-1] - long_series[half]) / max(1, len(long_series) - 1 - half), 3)
    private_long = summaries["our_host_full"]["private_mib_series"][OWNER_WARMUP - 1:]
    third = max(1, len(private_long) // 3)
    private_plateau = {"min_first_third": min(private_long[:third]), "min_last_third": min(private_long[-third:])}
    all_records = [r for records in kinds.values() for r in records]
    checks = {
        "every_cycle_created_and_tore_down": all(r["context_ok"] and r["teardown_ok"] for r in all_records),
        "every_host_rendered_on_its_device": all(r.get("host_ok", True) and r.get("host_on_expected_device", True)
                                                 for r in all_records),
        "no_messenger_errors": all(r["messenger_errors"] == 0 for r in all_records),
        "environment_clean": environment_record()["clean"],
        "our_host_adds_no_handles": abs(attribution["our hidden host (Quick, render thread, Qt's QRhi on our device)"])
        <= FLAT_HANDLES_PER_CYCLE and abs(attribution["readback and resize"]) <= FLAT_HANDLES_PER_CYCLE,
        "our_host_full_handles_flat_in_second_half": second_half_rate <= FLAT_HANDLES_PER_CYCLE,
        "our_host_full_private_bytes_plateau": private_plateau["min_last_third"]
        <= private_plateau["min_first_third"] + 16.0,
    }
    owed = [] if all(r["validation_layer_loaded"] for r in all_records) else ["validation owed (layer not installed)"]
    return {
        "round": "owners",
        "checks": checks,
        "pass": all(checks.values()),
        "owed": owed,
        "handles_per_cycle_by_kind": per,
        "attribution_handles_per_cycle": attribution,
        "long_series": {"second_half_handles_per_cycle": second_half_rate, "private_mib": private_plateau},
        "summaries": summaries,
        "start_counters": start,
        "records": kinds,
        "environment": environment_record(),
    }


ROUNDS = {"facts": round_facts, "device": round_device, "lifecycle": round_lifecycle, "owners": round_owners}
REQUIRED = {"facts": ("n06_facts",), "device": ("n06_facts", "n06_context_create", "n06_attach_window"),
            "lifecycle": ("n06_facts", "n06_context_create", "n06_attach_window", "n06_process_counters",
                          "quick_session_resize"),
            "owners": ("n06_context_create", "n06_attach_window", "n06_process_counters", "quick_session_resize",
                       "n06_handle_count")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", required=True, type=Path)
    parser.add_argument("--round", default="facts", choices=sorted(ROUNDS))
    parser.add_argument("--label", default="n06")
    parser.add_argument("--cycles", type=int, default=10, help="lifecycle: create/destroy cycles (the first is the "
                        "warm-up and the baseline; one forced-absence cycle always follows)")
    parser.add_argument("--long-cycles", type=int, default=40,
                        help="owners: cycles of the full kind (plateau or linear growth)")
    parser.add_argument("--force-no-second-queue", action="store_true",
                        help="lifecycle: force the second queue's absence in every cycle (the negative control as "
                             "a switch; never an environment variable)")
    args = parser.parse_args()

    native = _import_native(args.module_dir.resolve())
    missing = [name for name in REQUIRED[args.round] if not hasattr(native, name)]
    if missing:
        print(f"N06 VERDICT FAIL: the module has no {', '.join(missing)} (an older build in --module-dir)")
        return 0
    out = _evidence_dir(args.label)
    summary = {"runtime": native.runtime_info(), "python": sys.version}
    if args.round == "lifecycle":
        summary.update(round_lifecycle(native, out, max(2, args.cycles), args.force_no_second_queue))
    elif args.round == "owners":
        summary.update(round_owners(native, out, max(4, args.cycles), max(4, args.long_cycles)))
        print(json.dumps({k: summary[k] for k in ("handles_per_cycle_by_kind", "attribution_handles_per_cycle",
                                                   "long_series")}, indent=2))
        print(json.dumps({kind: {k: s[k] for k in ("private_mib_slope_per_cycle", "threads_delta",
                                                   "python_gc_objects_per_cycle", "gpu_heap_delta_mib")}
                          for kind, s in summary["summaries"].items()}, indent=2))
    else:
        summary.update(ROUNDS[args.round](native, out))
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    shown = ("round", "checks", "pass", "owed", "validation", "second_queue_same_family", "comparisons")
    if args.round == "lifecycle":
        shown += ("second_queue",)
        print(json.dumps({"counter_deltas": summary["counters"]["deltas_last_vs_baseline"],
                          "private_growth_per_cycle_mib": summary["counters"]["private_growth_per_cycle_mib"]},
                         indent=2))
    print(json.dumps({k: summary[k] for k in shown if k in summary}, indent=2))
    failed = [k for k, v in summary["checks"].items() if not v]
    print(f"\nevidence: {out / 'summary.json'}")
    print("N06 VERDICT " + ("PASS" if summary["pass"] else "FAIL: " + ", ".join(failed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
