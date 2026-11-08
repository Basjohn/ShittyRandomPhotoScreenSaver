"""Nuitka user plugin for the Windows builds: importing PySide6 loads no Qt GUI module in a compiled process.

Nuitka's PySide6 plugin (``nuitka/plugins/standard/PySidePyQtPlugin.py``, ``createPostModuleLoadCode``), whenever the
build gives the executable an icon (``--windows-icon-from-ico``, as every SRPSS Windows build does), attaches code to
the ``PySide6`` package's post-load trigger that runs ``import PySide6.QtWidgets`` and
``from PySide6.QtGui import QIcon, QPixmap, QImage`` and wraps ``QApplication`` so a new application loads the
executable's icons. That trigger runs on the first ``import PySide6`` of any kind, so in a compiled build every process
that imports only ``PySide6.QtCore`` also maps ``Qt6Gui.dll`` and ``Qt6Widgets.dll``: the Visualizer's engine worker
(QtCore only by contract) and the image workers (QtCore and QtGui) carried them in the first frozen check (8 Nov 2026,
``Docs/Historical_Bugs/R-176_*``). Nuitka 4.2 has no option to turn it off. SRPSS does not need it: ``main.py`` sets the
application icon from ``SRPSS.ico`` right after constructing ``QApplication``, before any window exists, and the
executable's own icon resource (the ``.scr`` in Explorer) is written by Nuitka's post-processing, which this plugin
does not touch.

This plugin removes, from what the PySide6 plugin attaches to the ``PySide6`` package, every piece of code that imports
a Qt module other than QtCore, and logs what it removed. Everything else, the other plugins' post-load code included
(Nuitka's compiled-method protection for ``Signal.connect``, from its package configuration), stays. The build's frozen
audit (``tools/frozen_build_audit.py``) checks the result in Nuitka's report and refuses publication when a trigger
that runs on a QtCore import still imports a GUI module, so a Nuitka upgrade that reshapes the hook fails the build
instead of shipping it.

Passed by ``scripts/venv/build_nuitka.ps1`` and ``scripts/venv/build_nuitka_mc_onedir.ps1`` together with the icon
(``--user-plugin=tools/nuitka_worker_qt_plugin.py``). Runs only inside the Nuitka compiler; never imported by the
application.
"""
from __future__ import annotations

import inspect
import re

from nuitka.plugins.PluginBase import NuitkaPluginBase

#: The binding whose package trigger this plugin edits, and the Nuitka plugin that writes it.
BINDING = "PySide6"
QT_PLUGIN_NAME = "pyside6"

#: An import of a PySide6 Qt module other than QtCore (``import PySide6.QtWidgets``, ``from PySide6.QtGui import``,
#: ``from PySide6 import QtGui``).
_GUI_IMPORT = re.compile(
    r"^\s*(?:import\s+PySide6\.Qt(?!Core\b)\w+|from\s+PySide6\.Qt(?!Core\b)\w+\s+import\b"
    r"|from\s+PySide6\s+import\s+(?:\(?\s*)?(?:\w+\s*,\s*)*Qt(?!Core\b)\w+)",
    re.MULTILINE,
)


def imports_qt_gui(code: str) -> bool:
    """Whether ``code`` imports a PySide6 Qt module other than QtCore."""
    return bool(_GUI_IMPORT.search(code or ""))


def _descriptions(value) -> tuple:
    """A plugin's load-code answer as a tuple of ``(code, reason[, flags])`` tuples (Nuitka accepts None, one
    description, several, or a generator of them)."""
    if value is None:
        return ()
    if inspect.isgenerator(value):
        value = tuple(value)
    if not value:
        return ()
    if type(value[0]) not in (tuple, list):
        value = (value,)
    return tuple(description for description in value if description is not None)


class NuitkaPluginSrpssWorkerQt(NuitkaPluginBase):
    """Keeps the Qt GUI stack out of ``import PySide6`` (see the module docstring)."""

    plugin_name = "srpss-worker-qt"
    plugin_desc = "Importing PySide6 loads no Qt GUI module (removes the PySide6 plugin's application-icon hook)."

    def __init__(self) -> None:
        from nuitka.plugins.Plugins import getActivePlugins

        qt_plugin = next((plugin for plugin in getActivePlugins() if plugin.plugin_name == QT_PLUGIN_NAME), None)
        if qt_plugin is None:
            self.sysexit(f"needs Nuitka's '{QT_PLUGIN_NAME}' plugin enabled (--enable-plugin={QT_PLUGIN_NAME})")
        self.removed: list[str] = []
        original = qt_plugin.createPostModuleLoadCode

        def post_load_code_without_gui(module):
            descriptions = _descriptions(original(module))
            if module.getFullName() != BINDING:
                return descriptions
            kept = []
            for description in descriptions:
                if imports_qt_gui(description[0]):
                    reason = str(description[1]).strip()
                    self.removed.append(reason)
                    self.info(f"Removed from '{BINDING}' post-load (it imported a Qt GUI module): {reason}")
                else:
                    kept.append(description)
            return tuple(kept)

        # The PySide6 plugin's own instance answers through this wrapper from now on (Nuitka asks every active plugin
        # instance for its load code when it discovers a module).
        qt_plugin.createPostModuleLoadCode = post_load_code_without_gui

    def onModuleCompleteSet(self, module_set) -> None:
        if any(module.getFullName() == BINDING for module in module_set) and not self.removed:
            self.warning(f"nothing imported a Qt GUI module on '{BINDING}' import: the PySide6 plugin's icon hook "
                         "changed or is gone (the frozen audit checks the report)")


__all__ = ["BINDING", "NuitkaPluginSrpssWorkerQt", "QT_PLUGIN_NAME", "imports_qt_gui"]
