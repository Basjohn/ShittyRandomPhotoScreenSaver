"""The native core's GPU-free check: it loads through ``rendering.native`` into the repository venv's PySide6.

The same check runs on GitHub's runner after the compile (the workflow's "Import check" step; the runner has no GPU)
and on any machine with a built module. Everything goes through ``rendering.native.load`` (the module's only
importer): the exact-Qt guard, the Qt and ABI checks and the MSVC runtime origin check. On top it records where the
Qt DLLs were loaded from (PySide6's own folder, one copy each). No QGuiApplication, no window.

    python native/core/python/import_check.py --module-dir <build dir> --expect-qt 6.12.0 --json <file>

Exit 0 when every check passes, 1 otherwise (the JSON says which). The workflow's manifest reads the JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
QT_DLLS = ("Qt6Core.dll", "Qt6Gui.dll", "Qt6Qml.dll", "Qt6Quick.dll")


def check(module_dir: Path, expect_qt: str) -> dict:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from rendering.native import NativeCoreUnavailable, load

    report: dict = {"module_dir": str(module_dir), "expect_qt": expect_qt, "python": sys.version, "checks": {}}
    checks = report["checks"]
    try:
        core = load(module_dir)
    except NativeCoreUnavailable as exc:
        checks["import"] = f"FAILED: {exc.reason}"
        report["ok"] = False
        return report
    checks["import"] = "ok"
    import PySide6

    info = dict(core.info)
    report["runtime_info"] = info
    pyside_dir = Path(PySide6.__file__).resolve().parent
    checks["qt_compiled"] = info.get("qt_compiled") == expect_qt
    checks["qt_runtime"] = info.get("qt_runtime") == expect_qt
    checks["with_quick"] = bool(info.get("with_quick"))
    loaded = info.get("loaded_modules") or {}
    for dll in QT_DLLS:
        path = loaded.get(dll)
        checks[f"{dll} from PySide6"] = bool(path) and Path(path).resolve().parent == pyside_dir
    report["ok"] = all(value is True or value == "ok" for value in checks.values())
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--module-dir", required=True, type=Path)
    parser.add_argument("--expect-qt", required=True)
    parser.add_argument("--json", type=Path, help="also write the report here")
    args = parser.parse_args(argv)
    report = check(args.module_dir.resolve(), args.expect_qt)
    text = json.dumps(report, indent=2)
    print(text)
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
