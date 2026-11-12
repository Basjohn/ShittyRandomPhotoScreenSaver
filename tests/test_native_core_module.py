"""The built native core, loaded through rendering.native (N2.1). These tests need the compiled module, which only
GitHub builds: where ``release/native_module/_srpss_native_core.pyd`` is not in this checkout they skip and say so.
Hidden only: the host adapter's window is never shown."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from rendering import native
from rendering.native import loader, runtime_check
from tools import native_sdk_fetch as sdk

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()

pytestmark = pytest.mark.skipif(
    not BUILT,
    reason=f"the native core is not built in this checkout: no release/native_module/{loader.MODULE_NAME}.pyd (only "
           "GitHub builds it: tools/build_runner.py --mode github --run --select native_module, by the lead)",
)


@pytest.fixture(scope="module")
def core():
    return native.load(MODULE_DIR)


def test_the_built_module_loads_for_this_processes_qt_and_abi(core):
    from PySide6.QtCore import qVersion

    assert core.qt_version == qVersion() == sdk.pinned_qt_version()
    assert core.abi == loader.EXPECTED_ABI == core.module.ABI
    assert core.module.QT_VERSION == core.qt_version and core.module.__version__ == core.version
    assert core.path.resolve() == (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").resolve()
    loaded = core.info["loaded_modules"]
    import PySide6

    for dll in ("Qt6Core.dll", "Qt6Gui.dll", "Qt6Qml.dll", "Qt6Quick.dll"):
        assert Path(loaded[dll]).resolve().parent == Path(PySide6.__file__).resolve().parent, dll


def test_the_built_module_imports_no_stl_dll_and_a_runtime_new_enough(core):
    imports = runtime_check.read_imports(core.path)
    assert not [dll for dll in imports if dll.startswith(runtime_check.STL_PREFIX)]
    assert runtime_check.check_module(core.path, core.info["msc_full_ver"]) == []
    assert {"qt6core.dll", "qt6quick.dll"} <= set(imports)        # the host entry really binds Qt Quick


def test_the_host_entry_takes_a_quick_window_and_refuses_anything_else(core, qt_app):
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickWindow
    import shiboken6

    window = QQuickWindow()                                       # never shown
    plain = QObject()
    try:
        for kind in native.HOST_KINDS:
            assert core.attach_host(window, kind) is None
        with pytest.raises(TypeError):
            core.attach_host(plain)
        with pytest.raises(TypeError):
            core.module.host_attach("window", shiboken6.getCppPointer(plain)[0])
        with pytest.raises(ValueError):
            core.module.host_attach("swapchain", shiboken6.getCppPointer(window)[0])
        with pytest.raises(ValueError):
            core.module.host_attach("window", 0)
    finally:
        plain.deleteLater()
        window.deleteLater()


def test_the_import_check_passes_the_built_module(core, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "native" / "core" / "python"))
    monkeypatch.delitem(sys.modules, "import_check", raising=False)
    import import_check

    try:
        assert import_check.main(["--module-dir", str(MODULE_DIR), "--expect-qt", core.qt_version,
                                  "--json", str(tmp_path / "report.json")]) == 0
        report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        assert report["ok"] and report["runtime_info"]["abi"] == loader.EXPECTED_ABI
    finally:
        sys.modules.pop("import_check", None)
