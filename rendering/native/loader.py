"""Loading the native core module, ``_srpss_native_core`` (D5.7): the only code that imports it.

A missing or wrong module fails here, in one place, with one reason (``NativeCoreUnavailable.reason``):

- the module file is not there, or Windows cannot load it (a DLL it needs);
- its own exact-Qt guard refuses the process's Qt (``PyInit__srpss_native_core``: ImportError);
- the Qt it was compiled for, the Qt it runs on and PySide6's Qt are not one version;
- its ABI is not the one this package speaks (``EXPECTED_ABI``; ``native/core/src/abi.h``);
- the CPython stable ABI it was built for is newer than this interpreter;
- its MSVC runtime arrangement is unsupported (``runtime_check``): read from the file before the import, so such a
  module never runs code here, and checked again after it with the compiler version the module reports.

Where it is loaded from: by default the package itself (``rendering/native/_srpss_native_core.pyd``, where the product
build places it and where a frozen build carries it); tools and tests name a folder instead (``module_dir``, for
example ``release/native_module`` after a GitHub build). Nothing in the product loads it yet (N2.7 adds the backend
owner); the host adapter's Python face is ``rendering.native.hosts`` (N2.2).
"""
from __future__ import annotations

import importlib
import importlib.machinery
import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping

from rendering.native import runtime_check
from rendering.native.hosts import HiddenHost, WindowHost

MODULE_NAME = "_srpss_native_core"
PACKAGE_MODULE = f"{__package__}.{MODULE_NAME}"
#: The ABI this package speaks; ``SRPSS_NATIVE_CORE_ABI`` in ``native/core/src/abi.h`` (a test holds them equal).
EXPECTED_ABI = 2
HOST_KINDS = ("window", "hidden")


class NativeCoreUnavailable(ImportError):
    """The native core cannot be used in this process; ``reason`` says why, in one sentence."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class NativeCore:
    """The loaded, checked module and what it reported about itself."""

    module: ModuleType = field(repr=False)
    info: Mapping[str, Any]

    @property
    def version(self) -> str:
        return str(self.info["version"])

    @property
    def abi(self) -> int:
        return int(self.info["abi"])

    @property
    def qt_version(self) -> str:
        return str(self.info["qt_compiled"])

    @property
    def path(self) -> Path:
        return Path(str(self.info["module_path"]))

    def attach_host(self, window: Any, kind: str = "window") -> WindowHost:
        """The host adapter's entry for a Qt Quick window the product shows (D5.1): the core's frame driver is connected
        to its ``beforeRendering`` in C++ (D5.2). On Vulkan call it before the window is first shown, with the process
        instance created (:meth:`vulkan_instance`). Refuses anything that is not a live ``QQuickWindow``; a hidden host
        owns its window (:meth:`hidden_host`)."""
        from PySide6.QtQuick import QQuickWindow
        import shiboken6

        if kind not in HOST_KINDS:
            raise ValueError(f"unknown host kind {kind!r} (the hosts are {', '.join(HOST_KINDS)})")
        if kind != "window":
            raise ValueError("a hidden host owns its window: NativeCore.hidden_host(width, height)")
        if not isinstance(window, QQuickWindow) or not shiboken6.isValid(window):
            raise TypeError(f"a host hands over a live QQuickWindow, not {type(window).__name__}")
        return WindowHost(self.module, self.module.host_attach(kind, shiboken6.getCppPointer(window)[0]))

    def hidden_host(self, width: int, height: int, *, threaded: bool = True) -> HiddenHost:
        """A hidden host: a Qt Quick window the core drives with a render control on its own render thread
        (``threaded``; False renders on the calling thread, the thread probe's negative control). On Vulkan it runs on
        a device of the module's (create the process instance first)."""
        return HiddenHost(self.module, self.module.host_attach("hidden", 0, int(width), int(height), bool(threaded)))

    def vulkan_instance(self, *, validation: bool = False) -> dict:
        """The process's Vulkan instance (D6 point 1), before any Vulkan host. ``validation`` (harness only) enables the
        Khronos layer and synchronisation validation when installed; the result says whether it loaded."""
        return json.loads(self.module.vulkan_instance_create(bool(validation)))

    def destroy_vulkan_instance(self) -> dict:
        """After every Vulkan host and window: the teardown steps and the validation messages per phase."""
        return json.loads(self.module.vulkan_instance_destroy())

    def set_vulkan_phase(self, phase: str) -> None:
        """The phase the validation messages that follow are counted under."""
        self.module.vulkan_set_phase(str(phase))

    def process_counters(self) -> dict:
        """Handles, GDI and USER objects, threads, private bytes and working set (lifecycle proofs)."""
        return json.loads(self.module.process_counters())

    def live_hosts(self) -> int:
        return int(self.module.live_hosts())


def _bind_pyside6_qt() -> str:
    """Load PySide6's Qt first (the DLLs the module must bind to, by name) and return its version."""
    import PySide6
    from PySide6 import QtCore, QtGui, QtQml, QtQuick  # noqa: F401  Qt6Core/Gui/Qml/Quick, PySide6's copies

    if os.name == "nt":
        package = Path(PySide6.__file__).resolve().parent
        if (package / "Qt6Core.dll").is_file():          # a frozen build keeps Qt beside the executable instead
            os.add_dll_directory(str(package))
    return QtCore.qVersion()


def _module_file(module_dir: Path | None) -> Path | None:
    """The file the import will load, found without importing it; None when the module is already in this process
    (there is nothing left to refuse before its import)."""
    if module_dir is None:
        if PACKAGE_MODULE in sys.modules:
            return None
        try:
            spec = importlib.util.find_spec(PACKAGE_MODULE)
        except (ImportError, ValueError) as exc:
            raise NativeCoreUnavailable(f"{MODULE_NAME} cannot be imported: {exc}") from exc
        if spec is None:
            raise NativeCoreUnavailable(
                f"{MODULE_NAME} cannot be imported: no {MODULE_NAME}.pyd in {Path(__file__).resolve().parent}")
        if not spec.origin or not Path(spec.origin).is_file():
            raise NativeCoreUnavailable(f"{MODULE_NAME} cannot be imported: the import system names no file for it "
                                        f"({spec.origin!r}), so its MSVC runtime cannot be checked first")
        return Path(spec.origin)
    folder = Path(module_dir)
    candidates = sorted(folder.glob(f"{MODULE_NAME}*.pyd")) if folder.is_dir() else []
    if not candidates:
        raise NativeCoreUnavailable(f"the native core is not built: no {MODULE_NAME}.pyd in {folder}")
    return None if MODULE_NAME in sys.modules else candidates[0]


def _refuse_by_runtime(problems_of) -> None:
    """The MSVC runtime refusal, before or after the import: the first problem is the one reason."""
    try:
        problems = problems_of()
    except (OSError, ValueError) as exc:
        problems = [f"its MSVC runtime cannot be checked: {exc}"]
    if problems:
        raise NativeCoreUnavailable(f"{MODULE_NAME}'s MSVC runtime: {problems[0]}")


def _check_before_import(path: Path) -> None:
    """The runtime rule from the file alone (``runtime_check.check_file``), so a module it refuses is never imported:
    importing runs the module's code (its ``DllMain``, its static initialisers, ``PyInit``) in this process."""
    try:
        problems = runtime_check.check_file(path)
    except (OSError, runtime_check.PeFormatError) as exc:   # not a readable image: Windows could not load it either
        raise NativeCoreUnavailable(f"{MODULE_NAME} cannot be imported: {exc}") from exc
    except ValueError as exc:                               # an image, but not linked by an MSVC 14.x toolset
        problems = [f"its MSVC runtime cannot be checked: {exc}"]
    _refuse_by_runtime(lambda: problems)


def _import_module(module_dir: Path | None) -> ModuleType:
    if module_dir is None:
        return importlib.import_module(PACKAGE_MODULE)
    folder = Path(module_dir)
    candidates = sorted(folder.glob(f"{MODULE_NAME}*.pyd")) if folder.is_dir() else []
    if not candidates:
        raise NativeCoreUnavailable(f"the native core is not built: no {MODULE_NAME}.pyd in {folder}")
    if MODULE_NAME in sys.modules:
        loaded = sys.modules[MODULE_NAME]
        if Path(getattr(loaded, "__file__", "")).resolve() != candidates[0].resolve():
            raise NativeCoreUnavailable(
                f"{MODULE_NAME} is already loaded from {loaded.__file__}; a process holds one copy of the module")
        return loaded
    spec = importlib.util.spec_from_file_location(
        MODULE_NAME, candidates[0], loader=importlib.machinery.ExtensionFileLoader(MODULE_NAME, str(candidates[0])))
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(MODULE_NAME, None)
        raise
    return module


def checked(module: ModuleType, running_qt: str, *, hexversion: int | None = None,
            runtime_problems=runtime_check.check_module) -> NativeCore:
    """Check an imported module against this process (PySide6's Qt ``running_qt``, this interpreter); the one place
    every check after the import lives."""
    try:
        info = dict(module.runtime_info())
    except Exception as exc:                            # an older module, or one that is not ours
        raise NativeCoreUnavailable(f"{MODULE_NAME} reports nothing about itself ({type(exc).__name__}: {exc})") from exc
    abi = info.get("abi")
    if abi != EXPECTED_ABI:
        raise NativeCoreUnavailable(
            f"{MODULE_NAME} speaks ABI {abi}, rendering.native speaks ABI {EXPECTED_ABI}: the module was built from "
            "another commit; rebuild it from this one")
    compiled, runtime = info.get("qt_compiled"), info.get("qt_runtime")
    if not (compiled == runtime == running_qt):
        raise NativeCoreUnavailable(
            f"{MODULE_NAME} was built for Qt {compiled} and runs on Qt {runtime}, but PySide6 ships Qt {running_qt}")
    limited = info.get("py_limited_api")
    if not isinstance(limited, int) or limited > (sys.hexversion if hexversion is None else hexversion):
        raise NativeCoreUnavailable(f"{MODULE_NAME} needs the CPython stable ABI 0x{limited or 0:08x}, newer than "
                                    f"this interpreter {sys.version.split()[0]}")
    _refuse_by_runtime(lambda: runtime_problems(Path(str(info.get("module_path"))), int(info.get("msc_full_ver") or 0)))
    return NativeCore(module, info)


def load(module_dir: Path | None = None) -> NativeCore:
    """Check, import and check again the native core; raises ``NativeCoreUnavailable`` with the one reason it cannot be
    used. The MSVC runtime rule runs on the file before the import (PySide6's Qt, and with it shiboken6's runtime
    copies, is loaded first, so the copies the module would bind to are the ones checked)."""
    if os.name != "nt":
        raise NativeCoreUnavailable("the native core is built for Windows only so far")
    running_qt = _bind_pyside6_qt()
    path = _module_file(module_dir)
    if path is not None:
        _check_before_import(path)
    try:
        module = _import_module(module_dir)
    except NativeCoreUnavailable:
        raise
    except ImportError as exc:                          # a DLL that does not load, the exact-Qt guard
        raise NativeCoreUnavailable(f"{MODULE_NAME} cannot be imported: {exc}") from exc
    imported = getattr(module, "__file__", None)
    if path is not None and imported and os.path.normcase(Path(imported).resolve()) != os.path.normcase(path.resolve()):
        raise NativeCoreUnavailable(f"{MODULE_NAME} was imported from {imported}, not from {path}, the file checked "
                                    "before the import")
    return checked(module, running_qt)
