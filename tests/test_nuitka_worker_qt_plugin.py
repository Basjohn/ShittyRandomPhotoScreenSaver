"""R-176 (frozen half, 8 Nov 2026): a compiled process that imports only ``PySide6.QtCore`` loads no Qt GUI module.

The first frozen check (``SRPSS_Diagnostic.scr --viz-engine-worker``, built from 5fb8dab7) found ``Qt6Gui.dll`` and
``Qt6Widgets.dll`` mapped in the engine worker (QtCore only from source) and in both image workers (QtCore and QtGui from
source). The cause is Nuitka's PySide6 plugin, not SRPSS code: with an executable icon it attaches
``import PySide6.QtWidgets`` and ``from PySide6.QtGui import ...`` to the ``PySide6`` package's post-load trigger, which
runs on the first ``import PySide6`` of every compiled process. ``tools/nuitka_worker_qt_plugin.py`` (a Nuitka user
plugin both Windows build workers pass with the icon) removes that code; the frozen audit refuses a report whose
QtCore-import triggers still import a GUI module (``tests/test_frozen_build_audit.py``).

These tests drive the installed Nuitka's own PySide6 plugin class (its source is what the build compiles with, pinned in
``requirements.txt``), never a compile: the hook is there with an icon (the negative control), and gone once this plugin
is active. The build itself is the lead's check (the next frozen build's report and worker DLL maps).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

qt_plugin_module = pytest.importorskip("nuitka.plugins.standard.PySidePyQtPlugin")

from nuitka.plugins import Plugins  # noqa: E402

from tools import nuitka_worker_qt_plugin as worker_qt  # noqa: E402


class _Module:
    """What Nuitka hands a plugin's load-code hook: a module answering ``getFullName``."""

    def __init__(self, name: str) -> None:
        self._name = name

    def getFullName(self) -> str:  # noqa: N802 (Nuitka's API)
        return self._name


def _pyside6_plugin(monkeypatch, *, icon: bool):
    # ``--windows-icon-from-ico`` as the build workers pass it (the plugin reads it through this function).
    monkeypatch.setattr(qt_plugin_module, "getWindowsIconPaths", lambda: ("SRPSS.ico",) if icon else ())
    monkeypatch.setattr(qt_plugin_module, "getWindowsIconExecutablePath", lambda: None)
    return qt_plugin_module.NuitkaPluginPySide6Plugins(
        include_qt_plugins=[], noinclude_qt_plugins=[], no_qt_translations=False, qt_debug_plugins=False)


def _package_post_load(plugin) -> tuple:
    return worker_qt._descriptions(plugin.createPostModuleLoadCode(_Module("PySide6")))


def test_with_an_icon_nuitkas_pyside6_plugin_imports_qt_gui_on_every_pyside6_import(monkeypatch):
    # The defect's mechanism, on the installed Nuitka (negative control for the test below): the package trigger's code
    # imports QtWidgets and QtGui, and only because the executable has an icon.
    with_icon = _package_post_load(_pyside6_plugin(monkeypatch, icon=True))
    assert any(worker_qt.imports_qt_gui(code) for code, *_ in with_icon), with_icon
    joined = "\n".join(code for code, *_ in with_icon)
    assert "import PySide6.QtWidgets" in joined and "from PySide6.QtGui import" in joined
    assert _package_post_load(_pyside6_plugin(monkeypatch, icon=False)) == ()


def test_the_user_plugin_removes_every_qt_gui_import_from_the_pyside6_package_trigger(monkeypatch):
    qt_plugin = _pyside6_plugin(monkeypatch, icon=True)
    monkeypatch.setitem(Plugins.active_plugins, worker_qt.QT_PLUGIN_NAME, qt_plugin)
    plugin = worker_qt.NuitkaPluginSrpssWorkerQt()
    assert _package_post_load(qt_plugin) == ()
    assert plugin.removed == ["Loading Qt application icon from Windows resources."]
    # QtCore's own trigger (the standalone Qt library path) is not the package's and stays as Nuitka writes it.
    monkeypatch.setattr(qt_plugin_module, "isStandaloneMode", lambda: True)
    monkeypatch.setattr(qt_plugin, "isDefaultQtPluginTargetPath", lambda: True)
    qtcore = worker_qt._descriptions(qt_plugin.createPostModuleLoadCode(_Module("PySide6.QtCore")))
    assert len(qtcore) == 1 and "QCoreApplication" in qtcore[0][0] and not worker_qt.imports_qt_gui(qtcore[0][0])


def test_the_user_plugin_refuses_a_build_without_the_pyside6_plugin(monkeypatch):
    monkeypatch.setattr(Plugins, "active_plugins", type(Plugins.active_plugins)())
    with pytest.raises(SystemExit):
        worker_qt.NuitkaPluginSrpssWorkerQt()


def test_the_gui_import_detector_reads_every_import_form():
    for code in ("import PySide6.QtWidgets", "  from PySide6.QtGui import QIcon", "from PySide6 import QtCore, QtGui",
                 "from PySide6 import (QtQuick)"):
        assert worker_qt.imports_qt_gui(code), code
    for code in ("import PySide6.QtCore", "from PySide6.QtCore import QCoreApplication", "from PySide6 import QtCore",
                 "import PySide6", "# import PySide6.QtWidgets is what the hook did"):
        assert not worker_qt.imports_qt_gui(code), code


@pytest.mark.parametrize("worker", ("build_nuitka.ps1", "build_nuitka_mc_onedir.ps1"))
def test_every_windows_build_worker_passes_the_user_plugin_with_the_icon(worker):
    # Without it a build compiles the hook back in (the audit would then refuse publication).
    text = (ROOT / "scripts" / "venv" / worker).read_text(encoding="utf-8")
    block = re.search(r"^if \(\$Icon\) \{\r?\n(.*?)^\}", text, re.MULTILINE | re.DOTALL)
    assert block is not None, worker
    assert '"--windows-icon-from-ico=$($Icon.FullName)"' in block.group(1)
    assert "\"--user-plugin=$(Join-Path $Root 'tools\\nuitka_worker_qt_plugin.py')\"" in block.group(1)
    assert (ROOT / "tools" / "nuitka_worker_qt_plugin.py").is_file()
