"""The built native core, loaded through rendering.native (N2.1, N2.2). These tests need the compiled module, which only
GitHub builds: where ``release/native_module/_srpss_native_core.pyd`` is not in this checkout they skip and say so.
Hidden only: no window is ever shown (the hidden host renders through a render control)."""
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
    # The check before the import reads the linker's toolset from the file: the compiler's, for the built module.
    assert runtime_check.linker_toolset(core.path) == runtime_check.toolset_of(core.info["msc_full_ver"])
    assert runtime_check.check_file(core.path) == []
    assert {"qt6core.dll", "qt6quick.dll"} <= set(imports)        # the host entry really binds Qt Quick


def test_the_window_host_takes_a_quick_window_and_refuses_anything_else(core, qt_app):
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickWindow
    import shiboken6

    window = QQuickWindow()                                       # never shown: no frame, no device
    plain = QObject()
    try:
        host = core.attach_host(window)
        assert isinstance(host, native.WindowHost)
        state = host.state()
        assert state["kind"] == "window" and state["attached"] and state["driver"]["edges"] == 0
        host.detach()
        assert not host.state()["attached"] and host.state()["previous_driver"]["detach_requested"]
        host.attach()
        assert host.state()["attachments"] == 2
        host.close()
        with pytest.raises(RuntimeError, match="closed"):
            host.state()
        with pytest.raises(ValueError):
            core.attach_host(window, "hidden")
        with pytest.raises(TypeError):
            core.attach_host(plain)
        with pytest.raises(TypeError):
            core.module.host_attach("window", shiboken6.getCppPointer(plain)[0])
        with pytest.raises(ValueError):
            core.module.host_attach("swapchain", shiboken6.getCppPointer(window)[0])
        with pytest.raises(ValueError):
            core.module.host_attach("window", 0)
        with pytest.raises(ValueError):
            core.module.host_attach("hidden", shiboken6.getCppPointer(window)[0], 64, 64)
        assert core.live_hosts() == 0
    finally:
        plain.deleteLater()
        window.deleteLater()


def test_the_hidden_host_round_passes_on_opengl(tmp_path):
    """The harness's hidden round in its own process (Qt Quick's graphics API is process-wide): the frame edge on the
    render thread with no Python thread state, the probe against the conventions with its negative controls, detach,
    re-attach, close, and the GUI-thread negative control of the thread probe."""
    import subprocess

    record_path = tmp_path / "child.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "native" / "core" / "python" / "host_check.py"), "--child", "--api", "opengl",
         "--rounds", "hidden", "--repo", str(ROOT), "--module-dir", str(MODULE_DIR), "--out-dir", str(tmp_path),
         "--child-json", str(record_path)],
        capture_output=True, text=True, timeout=600, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr[-2000:]
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert not record.get("error"), record.get("error")
    hidden = record["hidden"]
    assert hidden["pass"], {k: v for k, v in hidden.get("checks", {}).items() if not v} or hidden.get("error")
    assert record["live_hosts_at_end"] == 0


def test_the_composite_rounds_pass_on_opengl(tmp_path):
    """N2.4's harness, its hidden rounds in their own process: texels one to one under pixel shift, CUSTOM scale and
    quarter turns, plan 1C.4's clip contract on the native item in every display style, overflow held to the display
    rect, each with its negative controls; nothing of the core's left at the end."""
    import subprocess

    record_path = tmp_path / "child.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "native" / "core" / "python" / "composite_check.py"), "--child", "--api", "opengl",
         "--rounds", "texels", "contract", "overflow", "--repo", str(ROOT), "--module-dir", str(MODULE_DIR),
         "--out-dir", str(tmp_path), "--child-json", str(record_path)],
        capture_output=True, text=True, timeout=900, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr[-2000:]
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert not record.get("error"), record.get("error")
    for name in ("texels", "contract", "overflow"):
        entry = record[name]
        assert entry["pass"], {k: v for k, v in entry.get("checks", {}).items() if not v} or entry.get("error")
    assert record["live_hosts_at_end"] == 0
    assert record["composites_at_end"] == {"items": 0, "surfaces": 0, "surface_resources": 0, "handles": 0}


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
