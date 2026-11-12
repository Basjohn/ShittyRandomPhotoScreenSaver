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

Usage (repository venv, the module built on GitHub):
  python native/spike_p1/python/run_n06.py --module-dir release/native_module --round facts --label n06_facts
  python native/spike_p1/python/run_n06.py --module-dir release/native_module --round device --label n06_device
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


def _quick_host(native, ours: bool, png: Path, next_frame_png: Path | None) -> dict:
    """The spike scene in a hidden Qt Quick host (QQuickRenderControl, never shown), on our device (ours) or on
    the device Qt creates (the reference instance). Everything is destroyed before returning: the render control
    (and with it Qt's QRhi), the scene, the window, the engine."""
    import shiboken6
    from PySide6.QtCore import QCoreApplication, QEvent, QSizeF, QUrl
    from PySide6.QtGui import QRhi
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickRenderControl, QQuickWindow

    result: dict = {"host": "our_device" if ours else "qt_own_device", "ok": False}
    control = QQuickRenderControl()
    window = QQuickWindow(control)  # never shown
    engine = QQmlEngine()
    component = QQmlComponent(engine)
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
        try:
            session = native.quick_session_begin(_ptr(control), _ptr(window), WIDTH, HEIGHT, True)
        except RuntimeError as exc:
            result["error"] = f"quick_session_begin: {exc}"
            return result
        handle = session["handle"]
        result.update(backend=session["backend"], device=session["device"], vk_device=session.get("vk_device", 0),
                      vk_queue_family=session.get("vk_queue_family", -1),
                      vk_queue_index=session.get("vk_queue_index", -1))
        frames = native.quick_session_frames(handle, _ptr(root), FRAMES, str(png))
        result.update(frames_ok=frames["ok"], frames_error=frames["error"], lit_pixels=frames["lit_pixels"],
                      pixel_checksum=frames["pixel_checksum"], timing=_frame_summary(frames["frame_ms"]),
                      png=str(png) if frames["ok"] else None)
        rhi = control.rhi()
        result["rhi_feature_flags"] = {f.name: bool(rhi.isFeatureSupported(f)) for f in QRhi.Feature} if rhi else {}
        if next_frame_png is not None:
            nxt = native.quick_session_frames(handle, _ptr(root), 1, str(next_frame_png))
            result["next_frame_png"] = str(next_frame_png) if nxt["ok"] else None
        result["ok"] = bool(frames["ok"]) and frames["lit_pixels"] > 0
        return result
    finally:
        if handle is not None:
            native.quick_session_end(handle)  # invalidates the scene graph on the render thread, which then quits
        shiboken6.delete(control)  # Qt's QRhi on this window goes with it (Qt's render-control examples' order)
        if root is not None:
            root.setParentItem(None)
            root.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        shiboken6.delete(window)
        del component, engine


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


ROUNDS = {"facts": round_facts, "device": round_device}
REQUIRED = {"facts": ("n06_facts",), "device": ("n06_facts", "n06_context_create", "n06_attach_window")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", required=True, type=Path)
    parser.add_argument("--round", default="facts", choices=sorted(ROUNDS))
    parser.add_argument("--label", default="n06")
    args = parser.parse_args()

    native = _import_native(args.module_dir.resolve())
    missing = [name for name in REQUIRED[args.round] if not hasattr(native, name)]
    if missing:
        print(f"N06 VERDICT FAIL: the module has no {', '.join(missing)} (an older build in --module-dir)")
        return 0
    out = _evidence_dir(args.label)
    summary = {"runtime": native.runtime_info(), "python": sys.version}
    summary.update(ROUNDS[args.round](native, out))
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    shown = ("round", "checks", "pass", "owed", "validation", "second_queue_same_family", "comparisons")
    print(json.dumps({k: summary[k] for k in shown if k in summary}, indent=2))
    failed = [k for k, v in summary["checks"].items() if not v]
    print(f"\nevidence: {out / 'summary.json'}")
    print("N06 VERDICT " + ("PASS" if summary["pass"] else "FAIL: " + ", ".join(failed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
