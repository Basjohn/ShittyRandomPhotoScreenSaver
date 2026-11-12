"""rendering.native, the native core's only importer (D5.7, N2.1): every check after the import lives in one place
and fails with one reason. Stand-in modules (plain Python objects with the module's ``runtime_info()`` shape) take the
compiled module's place, so nothing here needs a build; tests/test_native_core_module.py runs the real module."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from rendering import native
from rendering.native import loader

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


def test_the_host_entry_takes_only_a_quick_window():
    calls = []
    core = loader.NativeCore(SimpleNamespace(host_attach=lambda kind, address: calls.append((kind, address))),
                             {"abi": loader.EXPECTED_ABI})
    with pytest.raises(ValueError, match="unknown host kind"):
        core.attach_host(object(), kind="swapchain")
    with pytest.raises(TypeError, match="QQuickWindow"):
        core.attach_host(object())
    assert calls == []
