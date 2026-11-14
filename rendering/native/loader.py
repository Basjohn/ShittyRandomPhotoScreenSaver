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
example ``release/native_module`` after a GitHub build). The product loads it only through the backend owner,
``rendering.quick.bootstrap`` (N2.7; a source checkout without the packaged module uses ``release/native_module``);
the host adapter's Python face is ``rendering.native.hosts`` (N2.2).
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
from rendering.native.composite import CompositeItem
from rendering.native.hosts import HiddenHost, WindowHost
from rendering.native.packet_reader import (
    PacketReader,
    SchemaTableMismatch,
    python_schema_table,
    reader_config,
    schema_table_differences,
)
from rendering.native.mode import NativeMode, mode_blocks, program_json, schema_table_entry
from rendering.native.spectrum import NativeSpectrum, spectrum_block

MODULE_NAME = "_srpss_native_core"
PACKAGE_MODULE = f"{__package__}.{MODULE_NAME}"
#: The ABI this package speaks; ``SRPSS_NATIVE_CORE_ABI`` in ``native/core/src/abi.h`` (a test holds them equal).
EXPECTED_ABI = 12
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

    def hidden_host(self, width: int, height: int, *, threaded: bool = True, dpr: float = 1.0,
                    timestamps: bool = False) -> HiddenHost:
        """A hidden host: a Qt Quick window the core drives with a render control on its own render thread
        (``threaded``; False renders on the calling thread, the thread probe's negative control). ``width`` and
        ``height`` are device pixels, laid out in logical pixels at ``dpr``. On Vulkan it runs on a device of the
        module's (create the process instance first). ``timestamps``: Qt's QRhi times its whole frames (the GPU timer's
        frame figure, the only one QRhi gives on D3D11 and D3D12); off, QRhi creates no query objects of its own."""
        if timestamps:
            return HiddenHost(self.module, self.module.host_attach("hidden", 0, int(width), int(height),
                                                                   bool(threaded), float(dpr), True))
        if dpr == 1.0:
            return HiddenHost(self.module, self.module.host_attach("hidden", 0, int(width), int(height),
                                                                   bool(threaded)))
        return HiddenHost(self.module, self.module.host_attach("hidden", 0, int(width), int(height), bool(threaded),
                                                               float(dpr)))

    def composite(self, parent: Any) -> CompositeItem:
        """A composite item (D5.2, N2.4) in the Qt Quick item ``parent``: a scene-graph texture node carrying the
        card's coverage, its surface drawn by the frame driver of a host attached to the parent's window. Placed with
        :meth:`CompositeItem.place` from ``rendering.native.composite.composite_geometry``."""
        from PySide6.QtQuick import QQuickItem
        import shiboken6

        if not isinstance(parent, QQuickItem) or not shiboken6.isValid(parent):
            raise TypeError(f"a composite is placed in a live QQuickItem, not {type(parent).__name__}")
        return CompositeItem(self.module, self.module.composite_create(shiboken6.getCppPointer(parent)[0]))

    def composite_live(self) -> dict:
        """Composite items, surfaces and their QRhi objects alive in the process, the native Spectrum's and the generic
        modes' sources and QRhi objects, and the items' textures (``mode_textures``, ``mode_texture_bytes``, the core's
        copies not yet uploaded ``mode_texture_images``, ``mode_texture_uploads``; lifecycle proofs)."""
        return json.loads(self.module.composite_live())

    def spectrum(self, parent: Any) -> NativeSpectrum:
        """The native Spectrum (N2.5) on a new composite item in ``parent``; place the composite and bind a stream.
        Refused while the module's compiled-in frame schemas differ from this build's (``SchemaTableMismatch``)."""
        differences = schema_table_differences(self.frame_schemas(), python_schema_table())
        if differences:
            raise SchemaTableMismatch(f"{MODULE_NAME}'s frame schemas are not this build's: {'; '.join(differences)}")
        return NativeSpectrum(self.module, self.composite(parent))

    def spectrum_block(self, record: bytes, card: Mapping[str, Any], pack: bytes | None,
                       settings: Mapping[str, Any]) -> tuple[bytes | None, dict]:
        """The SpectrumDraw block the native Spectrum uploads for ``record`` under ``card``, drawn by ``pack`` (None:
        the compiled-in copy) with ``settings`` by name (GPU-free)."""
        return spectrum_block(self.module, record, card, pack, settings)

    def spectrum_block_layout(self, pack: bytes | None = None) -> dict:
        """SpectrumDraw as ``pack`` (None: the module's compiled-in copy) reflects it (size, binding, members) and
        the members the core fills per frame."""
        return json.loads(self.module.spectrum_block_layout(pack))

    def mode(self, parent: Any) -> NativeMode:
        """A generic mode (N2.9, ``rendering.native.mode``) on a new composite item in ``parent``: place the
        composite, give it its program and settings, bind its stream with its schema. Refused while the module's
        compiled-in frame schemas differ from this build's (``SchemaTableMismatch``)."""
        differences = schema_table_differences(self.frame_schemas(), python_schema_table())
        if differences:
            raise SchemaTableMismatch(f"{MODULE_NAME}'s frame schemas are not this build's: {'; '.join(differences)}")
        return NativeMode(self.module, self.composite(parent))

    def mode_blocks(self, schema: Any, passes: Any, settings: Mapping[str, Any], record: bytes,
                    card: Mapping[str, Any] | None, target: tuple[int, int]) -> tuple[list[bytes], dict]:
        """Each pass's block bytes a generic mode uploads for ``record`` under ``card`` into ``target`` pixels
        (GPU-free)."""
        return mode_blocks(self.module, schema, passes, settings, record, card, target)

    def mode_core_members(self) -> dict:
        """The core's conventions as compiled: name -> (components, read from the card)."""
        rows = json.loads(self.module.mode_core_members())["members"]
        return {str(name): (int(components), bool(from_card)) for name, components, from_card in rows}

    def mode_core_values(self, name: str, card: Mapping[str, Any], target: tuple[int, int]) -> list[float]:
        """One core member's numbers for ``card`` (``mode.mode_card``'s keys) and ``target`` pixels, from its own row
        of the conventions (audit N29 round 2, L6); KeyError for a name the core does not fill (never zeros)."""
        from rendering.native.mode import _card

        return list(self.module.mode_core_values(str(name), _card(card), (int(target[0]), int(target[1]))))

    def mode_program_layout(self, passes: Any) -> dict:
        """The program's passes, blends, uv inputs, samplers and reflected blocks (GPU-free)."""
        declared, packs = program_json(passes)
        return json.loads(self.module.mode_program_layout(declared, packs))

    def program_block_pack(self, pack: bytes, block: str, values: Mapping[str, Any]) -> tuple[bytes, dict]:
        """One reflected block of ``pack`` packed from ``values`` by name, as the core packs every block (GPU-free):
        its bytes and facts (``layout``, ``unfilled``); ValueError when a value is refused."""
        from rendering.native.program_values import settings_json

        data, facts = self.module.program_block_pack(bytes(pack), str(block), settings_json(values))
        return bytes(data), json.loads(facts)

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

    def frame_schemas(self) -> dict:
        """The frame ABI version, mode codes and native schemas compiled into the module (N2.3)."""
        return json.loads(self.module.frame_schemas())

    def packet_reader(self, mapping_name: str, *, expect: Mapping[str, int] | None = None,
                      controls: tuple[str, ...] = (), schema: Any = None) -> PacketReader:
        """The core's reader of a frame stream (N2.3, D1 and D2) on its own view of the named mapping. ``expect``: the
        stream's identity (runtime and engine generation, activation id, mode code; a slot of another is foreign);
        ``controls``: a harness's negative controls (``READER_CONTROLS``); ``schema``: a generic mode's
        ``NativeSchema`` (or its table entry), admitted beside the compiled ones (N2.9). Refused while the module's
        compiled-in schemas differ from this build's (``SchemaTableMismatch``)."""
        differences = schema_table_differences(self.frame_schemas(), python_schema_table())
        if differences:
            raise SchemaTableMismatch(f"{MODULE_NAME}'s frame schemas are not this build's: {'; '.join(differences)}")
        config = reader_config(expect, tuple(controls))
        if schema is None:
            return PacketReader(self.module, self.module.packet_reader_open(str(mapping_name), config))
        table = schema if isinstance(schema, Mapping) else schema_table_entry(schema)
        return PacketReader(self.module, self.module.packet_reader_open(str(mapping_name), config,
                                                                        json.dumps(dict(table))))

    def packet_reader_live(self) -> dict:
        """Packet readers alive, views mapped and handles: all zero once every reader is closed."""
        return json.loads(self.module.packet_reader_live())

    def gpu_timer_live(self) -> dict:
        """GPU timers alive in the process and the query objects they hold (``timers``, ``query_pools``,
        ``queries``): all zero while every timer is off (N2.6)."""
        return json.loads(self.module.gpu_timer_live())


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
