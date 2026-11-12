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
  translucent  round 6: real Qt Quick windows kept invisible by tests/_invisible_windows.py's pattern (opacity 0,
          transparent for input, a tool window; frameless like the Studio): on our device translucent and opaque
          (the negative control), translucent with the DWM system backdrop and with the project's AccentPolicy
          glass, and translucent on Qt's own device; an OpenGL child process for comparison (D7 point 8's route 3).
          Records supportedCompositeAlpha, Qt's swapchain flags and the compositeAlpha its rule picks, the
          extended style, the backdrop HRESULTs, and the alpha in Qt's grabWindow and in PrintWindow
          (PW_RENDERFULLCONTENT, DWM's copy of the window). See-through to the desktop is the lead's visible run.

Usage (repository venv, the module built on GitHub):
  python native/spike_p1/python/run_n06.py --module-dir release/native_module --round facts --label n06_facts
  python native/spike_p1/python/run_n06.py --module-dir release/native_module --round device --label n06_device
  python native/spike_p1/python/run_n06.py --module-dir release/native_module --round lifecycle --label n06_lifecycle
  python native/spike_p1/python/run_n06.py --module-dir release/native_module --round owners --cycles 12 --label n06_owners
  python native/spike_p1/python/run_n06.py --module-dir release/native_module --round translucent --label n06_translucent
With the Khronos validation layer installed outside the registry, add --layer-path <folder with
VkLayer_khronos_validation.json>: VK_ADD_LAYER_PATH is set for this process only and reported as allowed. With the
layer the reference instance is validated too, Qt's QRhi names its objects (debug markers), every error is kept
with its phase, instance, thread and caller stack, and the summary groups them ("attribution").
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
# The one variable a harness may set, for its own process (and its child) only, when the lead passes --layer-path:
# the Vulkan loader finds the Khronos validation layer through it (the layer is installed without registry entries).
LAYER_PATH_VARIABLE = "VK_ADD_LAYER_PATH"
_ALLOWED_ENV: set[str] = set()


def use_layer_path(path: Path | None) -> None:
    """--layer-path: VK_ADD_LAYER_PATH for this process (and the children it starts), set before the module or Qt
    touches the Vulkan loader; reported by environment_record() as allowed, never hidden."""
    if path is None:
        return
    os.environ[LAYER_PATH_VARIABLE] = str(path)
    _ALLOWED_ENV.add(LAYER_PATH_VARIABLE)


def _evidence_dir(label: str) -> Path:
    sys.path.insert(0, str(REPO_ROOT))
    from tools import artifact_paths

    folder = artifact_paths.evidence_dir("native_core", "n06", label)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def environment_record() -> dict:
    found = {k: v for k, v in sorted(os.environ.items()) if k.upper().startswith(RECORDED_PREFIXES)}
    contaminating = sorted(k for k in found if k.upper().startswith(CONTAMINATING_PREFIXES)
                           and k.upper() not in _ALLOWED_ENV)
    allowed = sorted(k for k in found if k.upper() in _ALLOWED_ENV)
    return {"recorded": found, "contaminating_set": contaminating, "allowed_set_by_argument": allowed,
            "clean": not contaminating}


# Frames of the layer, the loader and our messenger callback sit on top of the caller's stack in a message entry.
_NOT_CALLER = ("VkLayer_", "vulkan-1.dll")


def validation_warnings(messages: dict) -> int:
    """Warnings that are validation findings: the loader's own general messages (for example "Registry lookup
    failed to get layer manifest files" when the layer is found through VK_ADD_LAYER_PATH, not the registry) are
    reported in the record and not counted. Errors are always counted."""
    loader = sum(1 for e in messages.get("entries", []) if e.get("severity") == "warning"
                 and e.get("id") == "Loader Message")
    return messages.get("warnings", 0) - loader


def message_groups(messages: dict) -> list:
    """Validation errors and warnings grouped by (id, phase, source instance): count, the thread, the objects (with
    their debug names) and the caller chain (the modules below the layer and the loader, consecutive repeats
    collapsed), which says whose call the layer reported on."""
    groups: dict = {}
    for e in messages.get("entries", []):
        stack = e.get("stack", [])
        last_layer = max((i for i, f in enumerate(stack) if f.startswith(_NOT_CALLER)), default=-1)
        chain: list = []
        for frame in stack[last_layer + 1:]:
            module = frame.split("+0x")[0]
            if not chain or chain[-1] != module:
                chain.append(module)
        key = (e.get("id"), e.get("phase"), e.get("source"))
        g = groups.setdefault(key, {"id": e.get("id"), "phase": e.get("phase"), "source": e.get("source"),
                                    "severity": e.get("severity"), "count": 0, "threads": [], "caller_modules": chain,
                                    "caller_frames": stack[last_layer + 1:last_layer + 13],
                                    "objects": e.get("objects", []), "message": e.get("message", "")[:1500]})
        g["count"] += 1
        if e.get("thread") not in g["threads"]:
            g["threads"].append(e.get("thread"))
    return sorted(groups.values(), key=lambda g: (g["phase"] or "", g["id"] or ""))


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
                steps: list | None = None, preserve_color: bool = False) -> dict:
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
            session = (native.quick_session_begin(_ptr(control), _ptr(window), WIDTH, HEIGHT, True, True)
                       if preserve_color else
                       native.quick_session_begin(_ptr(control), _ptr(window), WIDTH, HEIGHT, True))
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
        if ctx.get("instance", {}).get("validation_layer_loaded"):
            # N0.7 attribution: the same host whose offscreen target keeps its contents between frames
            # (PreserveColorContents; gui_helpers.h says why), on our device and on Qt's own.
            native.n06_set_phase("render_qt_own_device_preserve")
            hosts["qt_preserve"] = _quick_host(native, False, out / "n06_quick_qt_own_device_preserve.png", None,
                                               preserve_color=True)
            native.n06_set_phase("render_our_device_preserve")
            hosts["ours_preserve"] = _quick_host(native, True, out / "n06_quick_our_device_preserve.png", None,
                                                 preserve_color=True)
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
    for name in ("qt_preserve", "ours_preserve"):
        if our_host.get("png") and hosts.get(name, {}).get("png"):
            comparisons[f"our_device_vs_{name}"] = compare_pngs(Path(our_host["png"]), Path(hosts[name]["png"]))
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
        checks["reference_instance_validated"] = "validated" in ctx.get("reference_instance", {}).get("route", "")
        checks["preserve_hosts_pixel_identical"] = all(
            comparisons.get(f"our_device_vs_{n}", {}).get("max_abs") == 0 for n in ("qt_preserve", "ours_preserve"))
        per_phase = messages.get("per_phase", {})
        checks["preserve_hosts_validation_clean"] = all(
            per_phase.get(p, {}).get("errors", 0) == 0 and per_phase.get(p, {}).get("warnings", 0) == 0
            for p in ("render_qt_own_device_preserve", "render_our_device_preserve"))
        checks["validation_clean"] = messages.get("errors", -1) == 0 and validation_warnings(messages) == 0
    else:
        owed.append(inst.get("validation", "validation owed"))
    return {
        "round": "device",
        "checks": checks,
        "pass": all(checks.values()),
        "owed": owed,
        "validation": {"status": inst.get("validation"), "messages": messages,
                       "attribution": message_groups(messages)},
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
# Bounds for "back to baseline" after the warm-up cycle.
# The driver's own cost, measured by round 5 (owners, 94426903; NVIDIA 617.42): every VkDevice create and destroy
# leaves 3 process handles, whoever creates it (ours and Qt's alike; instance, adoption, second queue, reference
# instance, host, readback and resize add none). The handle check is therefore the baseline plus this cost times
# the devices the run created after the baseline, counted from the run itself.
DRIVER_HANDLES_PER_DEVICE = 3
HANDLE_TOLERANCE = 2
THREAD_TOLERANCE = 1
GPU_HEAP_TOLERANCE_MIB = 2.0
# Private bytes swing by about 100 MiB between cycles with no trend (rounds 3 to 5): the check is a plateau, the
# lowest reading of the last third against the lowest of the first third.
PRIVATE_PLATEAU_TOLERANCE_MIB = 16.0


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
    # Devices this cycle created: ours, and Qt's own when the reference host got as far as its QRhi.
    record["devices_created"] = int(bool(ctx.get("device", {}).get("vk_device"))) + int(
        bool(record.get("qt_host", {}).get("vk_device")))
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
    # Devices created after the baseline: ours in every cycle, plus Qt's own in a cycle with the reference host.
    devices_after_baseline = sum(r["devices_created"] for r in records[1:])
    expected_handle_delta = DRIVER_HANDLES_PER_DEVICE * devices_after_baseline
    handle_delta = _delta(after, "handles")  # None (a missing reading) fails the check below
    measured_private = [a.get("private_mib", 0.0) for a in after]
    third = max(1, len(measured_private) // 3)
    private_plateau = {"min_first_third": round(min(measured_private[:third]), 1),
                       "min_last_third": round(min(measured_private[-third:]), 1),
                       "slope_per_cycle": _slope(measured_private)}
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
        "handles_baseline_plus_driver_cost": handle_delta is not None
        and abs(handle_delta - expected_handle_delta) <= HANDLE_TOLERANCE,
        "threads_back_to_baseline": _delta(after, "threads") is not None
        and abs(_delta(after, "threads")) <= THREAD_TOLERANCE,
        "gpu_heaps_back_to_baseline": bool(baseline.get("gpu_budget_supported"))
        and all(abs(d) <= GPU_HEAP_TOLERANCE_MIB for d in heap_deltas),
        "private_bytes_plateau": private_plateau["min_last_third"]
        <= private_plateau["min_first_third"] + PRIVATE_PLATEAU_TOLERANCE_MIB,
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
        checks["validation_clean"] = all(m.get("errors", -1) == 0 and validation_warnings(m) == 0
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
                     "handles_expected_delta": {"devices_after_baseline": devices_after_baseline,
                                                "driver_handles_per_device": DRIVER_HANDLES_PER_DEVICE,
                                                "expected": expected_handle_delta, "measured": handle_delta},
                     "private_plateau_mib": private_plateau,
                     "tolerances": {"handles_around_expected": HANDLE_TOLERANCE, "threads": THREAD_TOLERANCE,
                                    "gpu_heap_mib": GPU_HEAP_TOLERANCE_MIB,
                                    "private_plateau_mib": PRIVATE_PLATEAU_TOLERANCE_MIB}},
        "comparisons": comparisons,
        "validation": {"status": first.get("validation"), "messenger_warning_texts": warnings,
                       "attribution": [dict(g, cycle=r["cycle"]) for r in records + [negative]
                                       for g in message_groups(r["messages"])]},
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
        # One device per full cycle: the driver's measured cost and nothing more (round 5's verdict).
        "our_host_full_handles_only_driver_cost": abs(second_half_rate - DRIVER_HANDLES_PER_DEVICE)
        <= FLAT_HANDLES_PER_CYCLE,
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


# --------------------------------------------------------------------- round 6: a translucent Vulkan window

WINDOW_SIZE = (640, 360)


def _frame_counter():
    from PySide6.QtCore import QObject, Slot

    class FrameCounter(QObject):
        """Counts frameSwapped on the GUI thread (queued from the render thread; no Python on Qt's thread)."""

        def __init__(self):
            super().__init__()
            self.count = 0

        @Slot()
        def on_frame(self):
            self.count += 1

    return FrameCounter()


def qt_composite_alpha(supported: list, flags: list) -> str:
    """The compositeAlpha QRhiVulkan::recreateSwapChain picks (facts D1, read from the 6.12 source; derived here
    because the swapchain's create info is not readable back)."""
    chosen = "INHERIT" if "INHERIT" in supported else "OPAQUE"
    if "SurfaceHasPreMulAlpha" in flags:
        if "PRE_MULTIPLIED" in supported:
            return "PRE_MULTIPLIED"
        if "POST_MULTIPLIED" in supported:
            return "POST_MULTIPLIED"
    elif "SurfaceHasNonPreMulAlpha" in flags:
        if "POST_MULTIPLIED" in supported:
            return "POST_MULTIPLIED"
    return chosen


def _window_readings(window, hwnd: int, out: Path, tag: str) -> dict:
    import n06_windows as nw

    readings: dict = {}
    grab = window.grabWindow()  # Qt renders the scene into an image: not the screen, so opacity does not matter
    readings["grabwindow"] = {"size": [grab.width(), grab.height()],
                              "regions": {k: nw.sample_qimage(grab, fx, fy) for k, (fx, fy) in nw.REGIONS.items()}}
    grab.save(str(out / f"n06_window_{tag}_grabwindow.png"), "PNG")
    del grab
    pw = nw.print_window(hwnd)  # DWM's composed content of this window, not the screen
    if pw.get("ok"):
        readings["printwindow"] = {"ok": True, "size": [pw["width"], pw["height"]],
                                   "regions": {k: nw.sample_bgra(pw["bgra"], pw["width"], pw["height"], fx, fy)
                                               for k, (fx, fy) in nw.REGIONS.items()}}
        nw.save_bgra_png(pw["bgra"], pw["width"], pw["height"], out / f"n06_window_{tag}_printwindow.png")
    else:
        readings["printwindow"] = {k: v for k, v in pw.items() if k != "bgra"}
    return readings


def _window_variant(native, out: Path, name: str, *, api: str, ours: bool | None, alpha: bool,
                    backdrop: str | None = None) -> dict:
    """One real QQuickWindow, shown but invisible (tests/_invisible_windows.py's pattern: opacity 0, transparent
    for input, a tool window; frameless like the Studio), on our device, Qt's own device, or OpenGL."""
    import shiboken6
    from PySide6.QtCore import QCoreApplication, QEvent, QSizeF, Qt, QUrl
    from PySide6.QtGui import QRhiSwapChain
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickWindow

    import n06_windows as nw

    w, h = WINDOW_SIZE
    result: dict = {"variant": name, "api": api, "alpha_requested": alpha, "ok": False}
    window = QQuickWindow()
    window.setFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                    | Qt.WindowType.WindowTransparentForInput)
    window.setOpacity(0.0)
    fmt = window.requestedFormat()
    if alpha:
        fmt.setAlphaBufferSize(8)
    window.setFormat(fmt)
    window.setColor(Qt.GlobalColor.transparent if alpha else Qt.GlobalColor.black)
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    counter = _frame_counter()
    root = None
    try:
        if api == "vulkan":
            native.n06_attach_window(_ptr(window), bool(ours))
        component.setData(nw.SCENE_QML, QUrl())
        root = component.create()
        if root is None:
            result["error"] = component.errorString()
            return result
        root.setParentItem(window.contentItem())
        window.setGeometry(120, 120, w, h)
        window.contentItem().setSize(QSizeF(w, h))
        root.setSize(QSizeF(w, h))
        window.frameSwapped.connect(counter.on_frame, Qt.ConnectionType.QueuedConnection)
        native.n06_set_phase(f"{name}_show_and_present")  # N0.7: per-step phases attribute validation messages
        window.show()
        nw.pump(lambda: counter.count >= 30, 10.0)
        result["frames_after_show"] = counter.count
        hwnd = int(window.winId())
        result["format"] = {"requested_alpha": window.requestedFormat().alphaBufferSize(),
                            "actual_alpha": window.format().alphaBufferSize()}
        result["opacity"] = window.opacity()
        result["exstyle"] = nw.extended_style(hwnd)
        rhi = window.rhi()
        result["backend"] = rhi.backendName() if rhi else None
        del rhi
        sc = window.swapChain()
        flags = [f.name for f in QRhiSwapChain.Flag if sc is not None and bool(sc.flags() & f)]
        result["swapchain"] = ({"flags": flags, "format": sc.format().name,
                                "pixel_size": [sc.currentPixelSize().width(), sc.currentPixelSize().height()]}
                               if sc is not None else None)
        del sc
        if api == "vulkan":
            surface = json.loads(native.n06_window_surface(_ptr(window)))
            result["surface"] = surface
            result["qt_composite_alpha_derived"] = qt_composite_alpha(surface.get("supported_composite_alpha", []),
                                                                      flags)
        native.n06_set_phase(f"{name}_grab_and_printwindow")
        result["readings"] = {"shown": _window_readings(window, hwnd, out, name)}
        native.n06_set_phase(f"{name}_present_after_grab")
        after_grab = counter.count
        nw.pump(lambda: counter.count >= after_grab + 10, 3.0)
        result["frames_after_grab"] = counter.count - after_grab
        if backdrop:
            before = counter.count
            result["backdrop"] = {"kind": backdrop, **(nw.dwm_system_backdrop(hwnd) if backdrop == "dwm_system"
                                                       else nw.accent_glass(hwnd, REPO_ROOT))}
            nw.pump(lambda: counter.count >= before + 30, 5.0)
            result["frames_after_backdrop"] = counter.count - before
            result["exstyle_after_backdrop"] = nw.extended_style(hwnd)
            native.n06_set_phase(f"{name}_grab_after_backdrop")
            result["readings"]["after_backdrop"] = _window_readings(window, hwnd, out, name + "_after_backdrop")
        result["ok"] = result["frames_after_show"] >= 10  # a real swapchain presenting continuously
        return result
    finally:
        native.n06_set_phase(f"{name}_hide_and_teardown")
        window.hide()
        nw.pump(lambda: False, 0.2)
        if root is not None:
            root.setParentItem(None)
            root.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            root = None
        shiboken6.delete(window)  # its scene graph, swapchain and QRhi go before our device (facts A7)
        del component
        del engine
        shiboken6.delete(counter)
        nw.pump(lambda: False, 0.2)


def _region_alpha(variant: dict, source: str, region: str, stage: str = "shown") -> float | None:
    return (variant.get("readings", {}).get(stage, {}).get(source, {}).get("regions", {})
            .get(region, {}).get("rgba", [None] * 4)[3])


def _at_most(value: float | None, bound: float) -> bool:
    return value is not None and value <= bound


def _at_least(value: float | None, bound: float) -> bool:
    return value is not None and value >= bound


def translucent_child(native, out: Path, api: str) -> dict:
    """The OpenGL comparison (route 3 of D7 point 8), in a child process because the graphics API is process-wide."""
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
    app = QGuiApplication([sys.argv[0]])
    variants = {"opengl_translucent": _window_variant(native, out, "opengl_translucent", api=api, ours=None,
                                                      alpha=True),
                "opengl_opaque": _window_variant(native, out, "opengl_opaque", api=api, ours=None, alpha=False)}
    del app
    return variants


def round_translucent(native, out: Path, module_dir: Path, label: str) -> dict:
    import subprocess

    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Vulkan)
    app = QGuiApplication([sys.argv[0]])
    ctx = json.loads(native.n06_context_create(True, "one", "full"))
    variants: dict = {}
    if ctx.get("ok"):
        native.n06_set_phase("windows")
        plan = (("ours_translucent", True, True, None), ("ours_opaque", True, False, None),
                ("ours_translucent_dwm_system_backdrop", True, True, "dwm_system"),
                ("ours_translucent_accent_glass", True, True, "accent_glass"),
                ("qt_own_device_translucent", False, True, None))
        for name, ours, alpha, backdrop in plan:
            variants[name] = _window_variant(native, out, name, api="vulkan", ours=ours, alpha=alpha,
                                             backdrop=backdrop)
    teardown = json.loads(native.n06_context_destroy())
    del app

    child_json = out / "child_translucent_opengl.json"
    proc = subprocess.run([sys.executable, __file__, "--module-dir", str(module_dir), "--round", "translucent",
                           "--label", label, "--child-api", "opengl", "--child-json", str(child_json)],
                          capture_output=True, text=True, timeout=300)
    opengl = json.loads(child_json.read_text(encoding="utf-8")) if child_json.exists() else {}
    child_json.unlink(missing_ok=True)
    if proc.returncode != 0 or not opengl:
        opengl["stderr_tail"] = proc.stderr[-2000:]
        opengl["exit_code"] = proc.returncode

    dev = ctx.get("device", {}).get("vk_device")
    ours_names = [n for n in variants if n.startswith("ours_")]
    translucent_names = [n for n in variants if "translucent" in n]
    findings = {
        name: {"supported_composite_alpha": v.get("surface", {}).get("supported_composite_alpha"),
               "qt_composite_alpha_derived": v.get("qt_composite_alpha_derived"),
               "swapchain_flags": (v.get("swapchain") or {}).get("flags"),
               "exstyle_layered": v.get("exstyle", {}).get("WS_EX_LAYERED"),
               "exstyle_noredirectionbitmap": v.get("exstyle", {}).get("WS_EX_NOREDIRECTIONBITMAP"),
               "printwindow_alpha_empty_region": _region_alpha(v, "printwindow", "empty_top_left"),
               "printwindow_alpha_half_red": _region_alpha(v, "printwindow", "half_red_right"),
               "printwindow_alpha_empty_after_backdrop": _region_alpha(v, "printwindow", "empty_top_left",
                                                                       "after_backdrop"),
               "backdrop": v.get("backdrop"), "frames_after_backdrop": v.get("frames_after_backdrop")}
        for name, v in {**variants, **{k: v for k, v in opengl.items() if isinstance(v, dict)}}.items()}

    def distinguishes(translucent: str, opaque: str, source: str) -> bool | None:
        a = _region_alpha(variants.get(translucent) or opengl.get(translucent, {}), source, "empty_top_left")
        b = _region_alpha(variants.get(opaque) or opengl.get(opaque, {}), source, "empty_top_left")
        return None if a is None or b is None else bool(b - a >= 64)

    findings["alpha_reaches_printwindow"] = {
        "vulkan_our_device": distinguishes("ours_translucent", "ours_opaque", "printwindow"),
        "opengl": distinguishes("opengl_translucent", "opengl_opaque", "printwindow"),
    }
    checks = {
        "context_created": bool(ctx.get("ok")),
        "vulkan_windows_presented": bool(variants) and all(v.get("ok") for v in variants.values()),
        "our_windows_on_our_device": all(variants[n].get("surface", {}).get("vk_device") == dev
                                         and variants[n].get("surface", {}).get("instance_is_ours") is True
                                         for n in ours_names),
        "qt_window_on_its_own_device": bool(variants.get("qt_own_device_translucent", {}).get("surface", {})
                                            .get("vk_device")) and variants["qt_own_device_translucent"]["surface"]
        ["vk_device"] != dev,
        "surface_capabilities_read": all(v.get("surface", {}).get("capabilities_result") == 0
                                         and v.get("surface", {}).get("supported_composite_alpha")
                                         for v in variants.values()),
        "premultiplied_flag_follows_alpha": all(
            ("SurfaceHasPreMulAlpha" in ((variants[n].get("swapchain") or {}).get("flags") or []))
            == ("translucent" in n) for n in variants),
        # A missing reading fails; an alpha of 0.0 is the pass value (round 6's first run read `0.0 or 255`).
        "qt_scene_alpha_translucent": bool(translucent_names) and all(
            _at_most(_region_alpha(variants[n], "grabwindow", "empty_top_left"), 2) for n in translucent_names),
        "qt_scene_alpha_opaque_negative_control": _at_least(
            _region_alpha(variants.get("ours_opaque", {}), "grabwindow", "empty_top_left"), 253),
        "teardown_ok": bool(teardown.get("ok")) and teardown.get("device_wait_idle_ok") is True,
        "no_messenger_errors": teardown.get("messages", {}).get("errors", -1) == 0,
        "opengl_comparison_ran": bool(opengl.get("opengl_translucent", {}).get("ok"))
        and bool(opengl.get("opengl_opaque", {}).get("ok")),
        "environment_clean": environment_record()["clean"],
    }
    layer = bool(ctx.get("instance", {}).get("validation_layer_loaded"))
    return {
        "round": "translucent",
        "checks": checks,
        "pass": all(checks.values()),
        "owed": [] if layer else ["validation owed (layer not installed)",
                                  "see-through to the desktop: the lead's visible run on Display 1"],
        "findings": findings,
        "hidden_window_caveat": "the invisible pattern's opacity 0 makes the window layered (WS_EX_LAYERED, "
                                "alpha 0), which changes DWM's composition path; PrintWindow reads DWM's copy of "
                                "the window, not the desktop behind it",
        "variants": variants,
        "opengl": opengl,
        "context": {"device": ctx.get("device", {}).get("vk_device"), "ok": ctx.get("ok")},
        "teardown": teardown,
        "validation": {"status": ctx.get("instance", {}).get("validation"),
                       "messages": teardown.get("messages", {}),
                       "attribution": message_groups(teardown.get("messages", {}))},
        "environment": environment_record(),
    }


ROUNDS = {"facts": round_facts, "device": round_device, "lifecycle": round_lifecycle, "owners": round_owners,
          "translucent": round_translucent}
REQUIRED = {"facts": ("n06_facts",), "device": ("n06_facts", "n06_context_create", "n06_attach_window"),
            "lifecycle": ("n06_facts", "n06_context_create", "n06_attach_window", "n06_process_counters",
                          "quick_session_resize"),
            "owners": ("n06_context_create", "n06_attach_window", "n06_process_counters", "quick_session_resize",
                       "n06_handle_count"),
            "translucent": ("n06_context_create", "n06_attach_window", "n06_window_surface")}


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
    parser.add_argument("--layer-path", type=Path, default=None,
                        help="the folder holding VkLayer_khronos_validation.json: sets VK_ADD_LAYER_PATH for this "
                             "process (and the translucent round's child) only; reported, allowed by the "
                             "environment check")
    parser.add_argument("--child-api", choices=("opengl",), help=argparse.SUPPRESS)
    parser.add_argument("--child-json", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    use_layer_path(args.layer_path)  # before the module or Qt loads the Vulkan loader
    native = _import_native(args.module_dir.resolve())
    if args.child_api:  # translucent round's OpenGL comparison, in its own process
        out = _evidence_dir(args.label)
        result = translucent_child(native, out, args.child_api)
        args.child_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 0
    missing = [name for name in REQUIRED[args.round] if not hasattr(native, name)]
    if missing:
        print(f"N06 VERDICT FAIL: the module has no {', '.join(missing)} (an older build in --module-dir)")
        return 0
    out = _evidence_dir(args.label)
    summary = {"runtime": native.runtime_info(), "python": sys.version}
    if args.round == "translucent":
        summary.update(round_translucent(native, out, args.module_dir, args.label))
        print(json.dumps(summary["findings"], indent=2))
    elif args.round == "lifecycle":
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
                          "handles_expected_delta": summary["counters"]["handles_expected_delta"],
                          "private_plateau_mib": summary["counters"]["private_plateau_mib"]}, indent=2))
    print(json.dumps({k: summary[k] for k in shown if k in summary}, indent=2))
    failed = [k for k, v in summary["checks"].items() if not v]
    print(f"\nevidence: {out / 'summary.json'}")
    print("N06 VERDICT " + ("PASS" if summary["pass"] else "FAIL: " + ", ".join(failed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
