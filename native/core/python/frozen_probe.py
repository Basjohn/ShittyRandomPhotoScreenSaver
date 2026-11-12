"""The native core's frozen probe (N2.1): the entry point of a separate Nuitka build made with the product's Qt
includes and QML prune (scripts/venv/build_native_core_probe.ps1), never the product itself (nothing in the product
imports the module yet).

Frozen, it loads the module the way the product will: ``rendering.native.load()`` from the package location, where the
probe build placed it, with every check the importer makes (the MSVC runtime origin check against the runtime DLLs the
frozen build actually carries, read from the module file before the import; exact Qt; ABI). On top it records where Qt and the module were loaded from (inside
the frozen build's own folder, one copy each), and hands an unshown QQuickWindow to the host adapter's entry. No
window is ever shown; no GPU device is opened.

    SRPSS_NativeCoreProbe.exe --out <report.json>

Exit 0 when every check passes, 1 otherwise (the JSON says which). Also runs unfrozen from the repository root, where
it reports ``frozen: false``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if "__compiled__" not in globals():                    # unfrozen: the repository root on the path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

QT_DLLS = ("Qt6Core.dll", "Qt6Gui.dll", "Qt6Qml.dll", "Qt6Quick.dll")


def probe() -> dict:
    import PySide6.QtQuick  # noqa: F401  Qt's DLLs load before the module binds to them

    from rendering.native import NativeCoreUnavailable, load

    frozen = "__compiled__" in globals()
    report: dict = {"frozen": frozen, "executable": sys.executable, "python": sys.version, "checks": {}}
    checks = report["checks"]
    try:
        core = load()
    except NativeCoreUnavailable as exc:
        checks["load"] = f"FAILED: {exc.reason}"
        report["ok"] = False
        return report
    checks["load"] = "ok"
    info = dict(core.info)
    report["runtime_info"] = info
    home = Path(sys.executable).resolve().parent
    if frozen:                                         # everything from the frozen build's own folder
        checks["module inside the build"] = home in core.path.resolve().parents
        loaded = info.get("loaded_modules") or {}
        for dll in QT_DLLS:
            path = loaded.get(dll)
            checks[f"{dll} inside the build"] = bool(path) and home in Path(path).resolve().parents
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickWindow

    app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    window = QQuickWindow()                            # never shown
    try:
        core.attach_host(window)
        checks["host entry"] = "ok"
    except (TypeError, ValueError) as exc:
        checks["host entry"] = f"FAILED: {exc}"
    finally:
        window.deleteLater()
        del app
    report["ok"] = all(value is True or value == "ok" for value in checks.values())
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = probe()
    except Exception as exc:                           # the probe itself broke: say so in the report
        report = {"frozen": "__compiled__" in globals(), "ok": False,
                  "checks": {"probe": f"FAILED: {type(exc).__name__}: {exc}"}}
    text = json.dumps(report, indent=2)
    print(text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text + "\n", encoding="utf-8")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
