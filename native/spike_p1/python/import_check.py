"""The spike module's GPU-free check: it imports into the repository venv's PySide6 and binds to that Qt.

Every part of ``run_spike.py`` renders through a QRhi device (``rhi``/``gil`` a standalone QRhi, ``hybrid`` and
``quick`` Qt Quick on a backend), so GitHub's GPU-less Windows runner runs only this: the import (the module refuses
any Qt but the one it was compiled for), ``runtime_info()`` (the compiled and running Qt, the compiler, whether part
B is in), and where the Qt DLLs were loaded from (PySide6's own folder, one copy). No QGuiApplication, no window.

    python native/spike_p1/python/import_check.py --module-dir <build dir> --expect-qt 6.11.2 --json <file>

Exit 0 when every check passes; 1 otherwise (the JSON says which). The workflow's manifest reads the JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from run_spike import _import_native  # the same import path the spike itself uses (PySide6's DLLs first)


def check(module_dir: Path, expect_qt: str, *, with_quick: bool = True) -> dict:
    report: dict = {"module_dir": str(module_dir), "expect_qt": expect_qt, "python": sys.version, "checks": {}}
    checks = report["checks"]
    try:
        native = _import_native(module_dir)
    except Exception as exc:              # ImportError from the module's own Qt check, a missing DLL, ...
        checks["import"] = f"FAILED: {type(exc).__name__}: {exc}"
        report["ok"] = False
        return report
    checks["import"] = "ok"
    import PySide6

    info = native.runtime_info()
    report["runtime_info"] = info
    pyside_dir = Path(PySide6.__file__).resolve().parent
    checks["qt_compiled"] = info.get("qt_compiled") == expect_qt
    checks["qt_runtime"] = info.get("qt_runtime") == expect_qt
    checks["with_quick"] = bool(info.get("with_quick")) == with_quick
    loaded = info.get("loaded_modules") or {}
    for dll in ("Qt6Core.dll", "Qt6Gui.dll", *(("Qt6Qml.dll", "Qt6Quick.dll") if with_quick else ())):
        path = loaded.get(dll)
        checks[f"{dll} from PySide6"] = bool(path) and Path(path).resolve().parent == pyside_dir
    report["ok"] = all(value is True or value == "ok" for value in checks.values())
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--module-dir", required=True, type=Path)
    parser.add_argument("--expect-qt", required=True)
    parser.add_argument("--without-quick", action="store_true", help="the module was built with SPIKE_WITH_QUICK=OFF")
    parser.add_argument("--json", type=Path, help="also write the report here")
    args = parser.parse_args(argv)
    report = check(args.module_dir.resolve(), args.expect_qt, with_quick=not args.without_quick)
    text = json.dumps(report, indent=2)
    print(text)
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
