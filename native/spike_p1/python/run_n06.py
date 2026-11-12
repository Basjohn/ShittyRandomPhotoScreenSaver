"""N0.6 driver (D6's proof, Current_Plan.md item 8b): the module owns the Vulkan instance and device.

Harness only, nothing ships. Facts and build order: Docs/Future_Work/Native_Core_N06_N07_Qt_Facts.md (section H).
Never shows a window and never sets an environment variable: the variables Qt and the Vulkan loader read are
recorded (they must be unset), and validation is enabled in code by the module when the layer is installed.

Rounds (one per GitHub build of the module):
  facts   round 1: the loader, instance layers and extensions, per GPU the queue families, Win32 present support,
          device extensions, supported features by name, the driver; Qt's own device at API 1.2 (the family and
          queue it chose, its QRhi feature flags, the features Qt enables by its rule).

Usage (repository venv, the module built on GitHub):
  python native/spike_p1/python/run_n06.py --module-dir release/native_module --round facts --label n06_facts
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

from run_spike import _import_native  # noqa: E402  (PySide6's Qt DLLs first, then the module)

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


ROUNDS = {"facts": round_facts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", required=True, type=Path)
    parser.add_argument("--round", default="facts", choices=sorted(ROUNDS))
    parser.add_argument("--label", default="n06")
    args = parser.parse_args()

    native = _import_native(args.module_dir.resolve())
    if not hasattr(native, "n06_facts"):
        print("N06 VERDICT FAIL: the module has no n06_facts (an older build in --module-dir)")
        return 0
    out = _evidence_dir(args.label)
    summary = {"runtime": native.runtime_info(), "python": sys.version}
    summary.update(ROUNDS[args.round](native, out))
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("round", "checks", "pass", "validation", "second_queue_same_family")},
                     indent=2))
    failed = [k for k, v in summary["checks"].items() if not v]
    print(f"\nevidence: {out / 'summary.json'}")
    print("N06 VERDICT " + ("PASS" if summary["pass"] else "FAIL: " + ", ".join(failed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
