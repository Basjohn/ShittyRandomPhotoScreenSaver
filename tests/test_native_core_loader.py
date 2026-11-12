"""rendering.native, the native core's only importer (D5.7, N2.1): every check after the import lives in one place
and fails with one reason. Stand-in modules (plain Python objects with the module's ``runtime_info()`` shape) take the
compiled module's place, so nothing here needs a build; tests/test_native_core_module.py runs the real module."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from rendering import native
from rendering.native import loader, runtime_check

QT = "6.12.0"


def _module(**overrides):
    info = {"module": loader.MODULE_NAME, "version": "0.1.0", "abi": loader.EXPECTED_ABI, "qt_compiled": QT,
            "qt_runtime": QT, "msc_full_ver": 194435227, "py_limited_api": 0x030A0000, "with_quick": True,
            "module_path": "C:/x/_srpss_native_core.pyd", "loaded_modules": {}}
    info.update(overrides)
    return SimpleNamespace(runtime_info=lambda: dict(info))


def _checked(module, *, problems=(), qt=QT, hexversion=None):
    return loader.checked(module, qt, hexversion=hexversion, runtime_problems=lambda _path, _msc: list(problems))


def test_a_module_that_matches_this_process_is_accepted():
    core = _checked(_module())
    assert (core.abi, core.qt_version, core.version) == (loader.EXPECTED_ABI, QT, "0.1.0")
    assert core.path == Path("C:/x/_srpss_native_core.pyd")


@pytest.mark.parametrize("case,overrides,fragment", [
    ("other-abi", {"abi": loader.EXPECTED_ABI + 1}, "ABI"),
    ("no-abi", {"abi": None}, "ABI"),
    ("compiled-for-other-qt", {"qt_compiled": "6.11.2"}, "built for Qt 6.11.2"),
    ("running-other-qt", {"qt_runtime": "6.11.2"}, "runs on Qt 6.11.2"),
    ("newer-stable-abi", {"py_limited_api": 0x7F000000}, "stable ABI"),
])
def test_a_module_that_does_not_match_fails_with_its_one_reason(case, overrides, fragment):
    with pytest.raises(native.NativeCoreUnavailable) as raised:
        _checked(_module(**overrides))
    assert fragment in raised.value.reason and str(raised.value) == raised.value.reason


def test_pysides_qt_is_the_one_the_module_must_match():
    with pytest.raises(native.NativeCoreUnavailable, match="PySide6 ships Qt 6.13.0"):
        _checked(_module(), qt="6.13.0")


def test_the_msvc_runtime_check_is_part_of_the_load():
    with pytest.raises(native.NativeCoreUnavailable, match="MSVC runtime: imports from msvcp140"):
        _checked(_module(), problems=["imports from msvcp140", "second"])


def test_a_module_that_reports_nothing_is_refused():
    def broken():
        raise RuntimeError("no")

    with pytest.raises(native.NativeCoreUnavailable, match="reports nothing"):
        _checked(SimpleNamespace(runtime_info=broken))


@pytest.mark.skipif(sys.platform != "win32", reason="the native core is built for Windows only so far")
def test_a_missing_module_fails_in_load_with_its_reason(tmp_path, monkeypatch):
    # A built module the module tests loaded earlier in this process is set aside (and restored afterwards).
    monkeypatch.delitem(sys.modules, loader.MODULE_NAME, raising=False)
    monkeypatch.delitem(sys.modules, loader.PACKAGE_MODULE, raising=False)
    with pytest.raises(native.NativeCoreUnavailable, match="not built: no _srpss_native_core.pyd"):
        native.load(tmp_path)
    with pytest.raises(native.NativeCoreUnavailable, match="cannot be imported"):
        native.load()                         # the package location: nothing is placed there in a source tree
    assert loader.MODULE_NAME not in sys.modules


@pytest.mark.skipif(sys.platform != "win32", reason="the native core is built for Windows only so far")
def test_a_module_whose_import_refuses_becomes_the_reason(tmp_path, monkeypatch):
    monkeypatch.delitem(sys.modules, loader.MODULE_NAME, raising=False)
    (tmp_path / f"{loader.MODULE_NAME}.pyd").write_bytes(b"MZ not really a module")
    with pytest.raises(native.NativeCoreUnavailable, match="cannot be imported"):
        native.load(tmp_path)
    assert loader.MODULE_NAME not in sys.modules


@pytest.mark.skipif(sys.platform != "win32", reason="the native core is built for Windows only so far")
def test_the_core_import_check_reports_a_missing_module_as_its_failure(tmp_path, monkeypatch):
    monkeypatch.delitem(sys.modules, loader.MODULE_NAME, raising=False)
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "native" / "core" / "python"))
    monkeypatch.delitem(sys.modules, "import_check", raising=False)
    import import_check

    try:
        report = import_check.check(tmp_path, QT)
        assert report["ok"] is False and report["checks"]["import"].startswith("FAILED: the native core is not built")
        assert import_check.main(["--module-dir", str(tmp_path), "--expect-qt", QT]) == 1
    finally:
        sys.modules.pop("import_check", None)


def _cpython_extension() -> Path:
    """One of CPython's own extension modules: it imports vcruntime140 and nothing from msvcp140."""
    for path in sorted((Path(sys.base_prefix) / "DLLs").glob("*.pyd")):
        imports = runtime_check.read_imports(path)
        if "vcruntime140.dll" in imports and not any(dll.startswith(runtime_check.STL_PREFIX) for dll in imports):
            return path
    pytest.fail(f"no CPython extension module in {Path(sys.base_prefix) / 'DLLs'} imports vcruntime140 alone")


def _linker_minor_at(data: bytes) -> int:
    pe = int.from_bytes(data[0x3C:0x40], "little")
    return pe + 24 + 3                                  # MinorLinkerVersion in the optional header


@pytest.fixture
def import_hook(monkeypatch):
    """Records every load of an extension module through Python's import machinery (``create_module`` is where the
    DLL is loaded and its ``PyInit`` runs); ``refuse`` makes any such load fail the test."""
    from importlib.machinery import ExtensionFileLoader

    calls: list[str] = []
    original = ExtensionFileLoader.create_module
    state = {"refuse": False}

    def create_module(self, spec):
        calls.append(spec.name)
        if state["refuse"]:
            pytest.fail(f"{spec.name} was imported ({spec.origin}) before the MSVC runtime check refused it")
        return original(self, spec)

    monkeypatch.setattr(ExtensionFileLoader, "create_module", create_module)
    monkeypatch.delitem(sys.modules, loader.MODULE_NAME, raising=False)
    monkeypatch.delitem(sys.modules, loader.PACKAGE_MODULE, raising=False)
    return SimpleNamespace(calls=calls, refuse=lambda: state.update(refuse=True))


@pytest.mark.skipif(sys.platform != "win32", reason="the native core is built for Windows only so far")
def test_a_module_that_imports_the_stl_dll_is_refused_before_it_is_imported(tmp_path, import_hook):
    import PySide6

    stand_in = next(Path(PySide6.__file__).parent.glob("QtCore*.pyd"))          # imports msvcp140
    (tmp_path / f"{loader.MODULE_NAME}.pyd").write_bytes(stand_in.read_bytes())
    import_hook.refuse()
    with pytest.raises(native.NativeCoreUnavailable, match="MSVC runtime: .*msvcp140") as raised:
        native.load(tmp_path)
    assert "P1 risk 4" in raised.value.reason and str(raised.value) == raised.value.reason
    assert import_hook.calls == [] and loader.MODULE_NAME not in sys.modules


@pytest.mark.skipif(sys.platform != "win32", reason="the native core is built for Windows only so far")
def test_a_module_linked_by_a_toolset_newer_than_the_loaded_runtime_is_refused_before_import(tmp_path, import_hook):
    loaded = runtime_check.file_version(Path(runtime_check.loaded_module_path("vcruntime140.dll")))
    data = bytearray(_cpython_extension().read_bytes())
    data[_linker_minor_at(data)] = loaded[1] + 1                 # linked by toolset 14.(loaded + 1)
    (tmp_path / f"{loader.MODULE_NAME}.pyd").write_bytes(bytes(data))
    import_hook.refuse()
    with pytest.raises(native.NativeCoreUnavailable, match="older than the module's toolset"):
        native.load(tmp_path)
    assert import_hook.calls == [] and loader.MODULE_NAME not in sys.modules


@pytest.mark.skipif(sys.platform != "win32", reason="the native core is built for Windows only so far")
def test_a_module_that_passes_the_runtime_check_is_then_imported(tmp_path, import_hook):
    # A CPython extension module passes the runtime rule; imported under the core's name it has no
    # PyInit__srpss_native_core, so the import itself refuses: the import was reached, after the check.
    (tmp_path / f"{loader.MODULE_NAME}.pyd").write_bytes(_cpython_extension().read_bytes())
    assert runtime_check.check_file(tmp_path / f"{loader.MODULE_NAME}.pyd") == []
    with pytest.raises(native.NativeCoreUnavailable, match="cannot be imported") as raised:
        native.load(tmp_path)
    assert "MSVC runtime" not in raised.value.reason
    assert import_hook.calls == [loader.MODULE_NAME] and loader.MODULE_NAME not in sys.modules


@pytest.mark.skipif(sys.platform != "win32", reason="the native core is built for Windows only so far")
def test_the_hook_sees_an_import_first_order(tmp_path, import_hook):
    """Negative control: the order the loader had before (import, then the runtime check on the loaded module) is
    caught by the same hook, so the hook really watches the loader's imports."""
    import PySide6

    stand_in = next(Path(PySide6.__file__).parent.glob("QtCore*.pyd"))
    (tmp_path / f"{loader.MODULE_NAME}.pyd").write_bytes(stand_in.read_bytes())
    with pytest.raises(ImportError):
        loader._import_module(tmp_path)                 # the old first step: import before any check
    assert import_hook.calls == [loader.MODULE_NAME]


@pytest.mark.skipif(sys.platform != "win32", reason="the native core is built for Windows only so far")
def test_a_package_located_module_is_checked_before_it_is_imported(import_hook, monkeypatch):
    import PySide6

    stand_in = next(Path(PySide6.__file__).parent.glob("QtCore*.pyd"))
    checked_paths = []
    original_check = getattr(runtime_check, "check_file", None)

    def find_spec(name, package=None):
        assert name == loader.PACKAGE_MODULE
        return SimpleNamespace(name=name, origin=str(stand_in))

    def check_file(path, loaded=None):
        checked_paths.append(Path(path))
        return original_check(path, loaded)

    monkeypatch.setattr(loader.importlib.util, "find_spec", find_spec)
    monkeypatch.setattr(runtime_check, "check_file", check_file, raising=False)
    import_hook.refuse()
    with pytest.raises(native.NativeCoreUnavailable, match="MSVC runtime: .*msvcp140"):
        native.load()
    assert checked_paths == [stand_in] and import_hook.calls == []


@pytest.mark.skipif(sys.platform != "win32", reason="the native core is built for Windows only so far")
def test_the_import_check_and_the_frozen_probe_refuse_before_the_import(tmp_path, import_hook, monkeypatch):
    """The workflow's import check (a module folder) and the frozen probe (the package location) both go through
    ``load``, so a module the runtime rule refuses is not imported by either."""
    import PySide6

    stand_in = next(Path(PySide6.__file__).parent.glob("QtCore*.pyd"))                # imports msvcp140
    (tmp_path / f"{loader.MODULE_NAME}.pyd").write_bytes(stand_in.read_bytes())
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "native" / "core" / "python"))
    for name in ("import_check", "frozen_probe"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    import frozen_probe
    import import_check

    import_hook.refuse()
    try:
        report = import_check.check(tmp_path, QT)
        assert report["ok"] is False and "MSVC runtime" in report["checks"]["import"], report
        monkeypatch.setattr(loader.importlib.util, "find_spec",
                            lambda name, package=None: SimpleNamespace(name=name, origin=str(stand_in)))
        report = frozen_probe.probe()
        assert report["ok"] is False and "MSVC runtime" in report["checks"]["load"], report
    finally:
        sys.modules.pop("import_check", None)
        sys.modules.pop("frozen_probe", None)
    assert import_hook.calls == []


def test_the_host_entry_takes_only_a_quick_window():
    calls = []
    core = loader.NativeCore(SimpleNamespace(host_attach=lambda kind, address: calls.append((kind, address))),
                             {"abi": loader.EXPECTED_ABI})
    with pytest.raises(ValueError, match="unknown host kind"):
        core.attach_host(object(), kind="swapchain")
    with pytest.raises(TypeError, match="QQuickWindow"):
        core.attach_host(object())
    assert calls == []
