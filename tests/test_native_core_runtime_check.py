"""The native core's MSVC runtime origin check (rendering/native/runtime_check.py; P1 risk 4, N2.1).

Read from real images in this venv, no module build needed: CPython's own extension modules import vcruntime140 and
no STL DLL (they pass), PySide6's QtCore imports msvcp140 (the rule's negative control: it fails), and the loaded
vcruntime140 is this process's own copy. Windows only: the module is built for Windows only so far.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from rendering.native import runtime_check as rc

pytestmark = pytest.mark.skipif(os.name != "nt", reason="the native core and its MSVC runtime are Windows-only")


def _cpython_extension() -> Path:
    """One of CPython's own extension modules: it imports vcruntime140 and nothing from msvcp140."""
    for path in sorted((Path(sys.base_prefix) / "DLLs").glob("*.pyd")):
        imports = rc.read_imports(path)
        if "vcruntime140.dll" in imports and not any(dll.startswith(rc.STL_PREFIX) for dll in imports):
            return path
    pytest.fail(f"no CPython extension module in {Path(sys.base_prefix) / 'DLLs'} imports vcruntime140 alone")


def _loaded_vcruntime() -> Path:
    path = rc.loaded_module_path("vcruntime140.dll")
    assert path, "this Python process has no vcruntime140.dll loaded"
    return Path(path)


def _msc_for(version: tuple[int, ...]) -> int:
    """An ``_MSC_FULL_VER`` whose toolset is ``version``'s 14.xx (cl 19.xx)."""
    return 190_000_000 + version[1] * 100_000 + 1


def test_the_pe_reader_reads_imports_and_exports_of_real_images():
    extension = rc.read_imports(_cpython_extension())
    assert "python3.dll" in extension or any(dll.startswith("python3") for dll in extension)
    assert all(isinstance(name, str) and name for names in extension.values() for name in names)
    exports = rc.read_exports(_loaded_vcruntime())
    assert {"memcpy", "memset", "__C_specific_handler"} <= exports
    with pytest.raises(rc.PeFormatError):
        rc.read_imports(Path(__file__))                                       # not an image


def test_a_module_that_imports_only_vcruntime_from_a_loaded_copy_new_enough_passes():
    version = rc.file_version(_loaded_vcruntime())
    assert version is not None and version[0] == 14
    assert rc.check_module(_cpython_extension(), _msc_for(version)) == []


def test_a_module_that_imports_from_msvcp140_is_refused():
    import PySide6

    qtcore = next(Path(PySide6.__file__).parent.glob("QtCore*.pyd"))
    imports = rc.read_imports(qtcore)
    assert any(dll.startswith(rc.STL_PREFIX) for dll in imports), "PySide6's QtCore no longer uses msvcp140"
    version = rc.file_version(_loaded_vcruntime())
    problems = rc.check_module(qtcore, _msc_for(version))
    assert any("msvcp140" in problem and "P1 risk 4" in problem for problem in problems), problems


def test_a_vcruntime_older_than_the_compiler_is_refused():
    version = rc.file_version(_loaded_vcruntime())
    newer = (14, version[1] + 1)
    problems = rc.check_module(_cpython_extension(), _msc_for(newer))
    assert any("older than the module's toolset" in problem for problem in problems), problems


def test_a_symbol_the_loaded_vcruntime_does_not_export_is_refused():
    loaded = _loaded_vcruntime()
    imports = {"vcruntime140.dll": frozenset({"memcpy", "srpss_not_exported_by_any_runtime"})}
    problems = rc.runtime_problems(imports, _msc_for(rc.file_version(loaded)), {"vcruntime140.dll": str(loaded)})
    assert any("srpss_not_exported_by_any_runtime" in problem for problem in problems), problems
    assert rc.runtime_problems({"vcruntime140.dll": frozenset({"memcpy"})}, _msc_for(rc.file_version(loaded)),
                               {"vcruntime140.dll": str(loaded)}) == []


def test_build_round_one_fh4_against_shibokens_older_copy_is_refused_and_vcruntime140_alone_passes():
    """N2.1 build round 1: a cl 19.51 module importing __CxxFrameHandler4 from vcruntime140_1.dll, whose loaded copy
    was shiboken6's 14.44.35211, was refused. Built without FH4 it imports vcruntime140.dll alone (Python's 14.51)
    and passes. The same numbers, with the exports and versions given, so the rule itself is what is tested."""
    msc = 195136231                                                    # cl 19.51: toolset 14.51
    loaded = {"vcruntime140.dll": "C:/python/VCRUNTIME140.dll", "vcruntime140_1.dll": "C:/shiboken6/VCRUNTIME140_1.dll"}
    versions = {"VCRUNTIME140.dll": (14, 51, 36247, 0), "VCRUNTIME140_1.dll": (14, 44, 35211, 0)}
    exports = {"VCRUNTIME140.dll": frozenset({"memcpy", "__CxxFrameHandler3", "__C_specific_handler"}),
               "VCRUNTIME140_1.dll": frozenset({"__CxxFrameHandler4"})}

    def problems(imports):
        return rc.runtime_problems(imports, msc, loaded, exports_of=lambda path: exports[path.name],
                                   version_of=lambda path: versions[path.name])

    with_fh4 = {"vcruntime140.dll": frozenset({"memcpy", "__C_specific_handler"}),
                "vcruntime140_1.dll": frozenset({"__CxxFrameHandler4"})}
    refused = problems(with_fh4)
    assert len(refused) == 1 and "VCRUNTIME140_1.dll is 14.44.35211.0" in refused[0], refused
    assert "older than the module's toolset 14.51" in refused[0]
    without_fh4 = {"vcruntime140.dll": frozenset({"memcpy", "__CxxFrameHandler3", "__C_specific_handler"})}
    assert problems(without_fh4) == []


def test_the_real_shiboken_vcruntime140_1_refuses_a_newer_compilers_fh4_import():
    loaded = rc.loaded_module_path("vcruntime140_1.dll")
    if loaded is None:
        pytest.skip("this process has not loaded vcruntime140_1.dll")
    version = rc.file_version(Path(loaded))
    imports = {"vcruntime140_1.dll": frozenset({"__CxxFrameHandler4"})}
    assert rc.runtime_problems(imports, _msc_for(version), {"vcruntime140_1.dll": loaded}) == []
    newer = rc.runtime_problems(imports, _msc_for((14, version[1] + 1)), {"vcruntime140_1.dll": loaded})
    assert newer and "older than the module's toolset" in newer[0]


def test_a_vcruntime_the_process_has_not_loaded_is_refused():
    problems = rc.runtime_problems({"vcruntime140_1.dll": frozenset({"__CxxFrameHandler4"})}, 194435227,
                                   {"vcruntime140_1.dll": None})
    assert problems and "has not loaded it" in problems[0]


def test_the_toolset_reads_from_msc_full_ver():
    assert rc.toolset_of(194435227) == (14, 44)
    assert rc.toolset_of(195136231) == (14, 51)
    for bad in (1944, 204435227):
        with pytest.raises(ValueError):
            rc.toolset_of(bad)
