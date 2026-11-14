"""The native core's build guards (native/core, Current_Plan.md item 8b N2.1, decision D5.7).

Nothing here compiles: the module is built only on GitHub. The CMake file, the module's C++ and the build script are
read as text, and each guard is checked twice: the real source has it, and the same reading of the source with the
guard taken out reports it missing (the negative control lives in the test, so a reading that cannot fail fails here).
"""
from __future__ import annotations

import re
from pathlib import Path

from rendering.native import loader
from tools import native_sdk_fetch as sdk

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native" / "core"


# ------------------------------------------------------------------------------- CMake's Qt guard (the PySide6 pin)


def _cmake_pin_regex(text: str) -> str:
    """The pin regex CMake applies, as Python reads it (CMake's ``\\\\.`` is the regex ``\\.``)."""
    match = re.search(r'string\(REGEX MATCH "([^"]+)" _pyside6_match "\$\{_pyside6_pin\}"\)', text)
    assert match, "CMakeLists.txt reads no PySide6 pin"
    return match.group(1).replace("\\\\", "\\")


def cmake_guard_problems(text: str) -> list[str]:
    problems = []
    if 'set(_requirements "${CMAKE_CURRENT_SOURCE_DIR}/../../requirements.txt")' not in text:
        problems.append("the pin is not read from the repository's requirements.txt")
    if 'file(STRINGS "${_requirements}" _pyside6_pin REGEX "^PySide6==")' not in text:
        problems.append("requirements.txt's PySide6 line is not read")
    if not re.search(r'if\(NOT CMAKE_MATCH_1\)\s*\n\s*message\(FATAL_ERROR', text):
        problems.append("a requirements.txt without a pin does not stop the configure")
    if 'set(CORE_QT_VERSION "${CMAKE_MATCH_1}")' not in text:
        problems.append("the pinned version is not the one compared")
    if not re.search(r'if\(NOT Qt6_VERSION VERSION_EQUAL CORE_QT_VERSION\)\s*\n\s*message\(FATAL_ERROR', text):
        problems.append("a Qt SDK other than the pin does not stop the configure")
    find = text.find("find_package(Qt6 REQUIRED")
    if find < 0 or text.find("VERSION_EQUAL CORE_QT_VERSION") < find:
        problems.append("the version is compared before Qt is found")
    return problems


def test_cmake_refuses_a_qt_sdk_other_than_pyside6s_pin():
    text = (CORE / "CMakeLists.txt").read_text(encoding="utf-8")
    assert cmake_guard_problems(text) == []
    assert (CORE / "../../requirements.txt").resolve() == (ROOT / "requirements.txt").resolve()
    # Negative control: the same reading of the file without the version comparison.
    unguarded = re.sub(r"if\(NOT Qt6_VERSION VERSION_EQUAL CORE_QT_VERSION\).*?endif\(\)", "", text, flags=re.S)
    assert unguarded != text and cmake_guard_problems(unguarded)


def test_cmakes_pin_regex_reads_the_same_version_the_sdk_fetch_and_the_manifest_read():
    regex = re.compile(_cmake_pin_regex((CORE / "CMakeLists.txt").read_text(encoding="utf-8")))
    lines = [line for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
             if line.startswith("PySide6==")]
    assert lines, "requirements.txt pins no PySide6"
    assert regex.match(lines[0]).group(1) == sdk.pinned_qt_version()
    for unpinned in ("PySide6>=6.12.0", "PySide6==6.12", "PySide6"):         # what CMake's FATAL_ERROR branch sees
        assert regex.match(unpinned) is None, unpinned


# ------------------------------------------------------------------------------------- the exact-Qt import guard


def pyinit_guard_problems(text: str) -> list[str]:
    match = re.search(r"PyMODINIT_FUNC PyInit__srpss_native_core\(void\)\s*\{(.*)\}\s*$", text, re.S)
    if match is None:
        return ["no PyInit__srpss_native_core"]
    body = match.group(1)
    guard = re.search(r"if \(std::strcmp\(qVersion\(\), QT_VERSION_STR\) != 0\) \{\s*PyErr_Format\(PyExc_ImportError,"
                      r".*?return nullptr;\s*\}", body, re.S)
    create = body.find("PyModule_Create(")
    if guard is None:
        return ["the module does not compare the running Qt with the Qt it was compiled for"]
    if create < 0 or guard.start() > create:
        return ["the module is created before the Qt comparison"]
    return []


def test_the_module_refuses_to_import_under_any_qt_but_its_own():
    text = (CORE / "src" / "module.cpp").read_text(encoding="utf-8")
    assert pyinit_guard_problems(text) == []
    unguarded = text.replace("std::strcmp(qVersion(), QT_VERSION_STR) != 0", "false")
    assert unguarded != text and pyinit_guard_problems(unguarded)


def test_the_module_and_its_importer_speak_one_abi():
    header = (CORE / "src" / "abi.h").read_text(encoding="utf-8")
    defined = re.findall(r"^#define SRPSS_NATIVE_CORE_ABI (\d+)$", header, re.M)
    assert defined == [str(loader.EXPECTED_ABI)]
    module = (CORE / "src" / "module.cpp").read_text(encoding="utf-8")
    assert '"abi", PyLong_FromLong(SRPSS_NATIVE_CORE_ABI)' in module
    assert 'PyModule_AddIntConstant(module, "ABI", SRPSS_NATIVE_CORE_ABI)' in module


def test_the_module_reports_what_its_importer_checks():
    module = (CORE / "src" / "module.cpp").read_text(encoding="utf-8")
    for key in ("version", "abi", "qt_compiled", "qt_runtime", "msc_full_ver", "py_limited_api", "module_path",
                "loaded_modules"):
        assert f'put(d, "{key}",' in module, key
    for dll in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll", "Qt6Core.dll", "Qt6Quick.dll"):
        assert f'L"{dll}"' in module, dll


def fh4_problems(text: str) -> list[str]:
    """The module must not use the FH4 exception handler (vcruntime140_1.dll, whose in-process copy is shiboken6's
    older one): both halves of the switch, the compiler's and the linker's, inside the MSVC branch."""
    branch = re.search(r"^if\(MSVC\)\n(.*?)^endif\(\)", text, re.S | re.M)
    body = branch.group(1) if branch else ""
    problems = []
    if not re.search(r"target_compile_options\(_srpss_native_core PRIVATE[^)]*\s/d2FH4-[\s)]", body):
        problems.append("the compiler still emits FH4 handlers (/d2FH4- missing)")
    if not re.search(r"target_link_options\(_srpss_native_core PRIVATE[^)]*\s/d2:-FH4-[\s)]", body):
        problems.append("the linker still pulls in the FH4 handler (/d2:-FH4- missing)")
    return problems


def test_the_module_is_built_without_the_fh4_exception_handler():
    text = (CORE / "CMakeLists.txt").read_text(encoding="utf-8")
    assert fh4_problems(text) == []
    for flag in ("/d2FH4-", "/d2:-FH4-"):
        removed = text.replace(f" {flag})", ")")
        assert removed != text and fh4_problems(removed), flag


#: CPython's non-limited-API accessor macros (the module builds against the limited API: N2.5 build round 4 failed on
#: PyBytes_AS_STRING / PyBytes_GET_SIZE). Their function forms (PyBytes_AsString, PyBytes_Size, ...) are fine.
_NON_LIMITED_MACRO = re.compile(r"\bPy\w+_(?:AS_[A-Z_]+|GET_[A-Z_]+|SET_[A-Z_]+)\s*\("
                                r"|\bPyUnicode_(?:DATA|KIND|READ|WRITE|READ_CHAR|GET_LENGTH)\s*\("
                                r"|\bPySequence_Fast_GET_\w+\s*\(")


def non_limited_macros(text: str) -> list[str]:
    code = re.sub(r"//[^\n]*", "", text)
    return [match.group(0) for match in _NON_LIMITED_MACRO.finditer(code)]


def test_the_module_sources_use_only_the_limited_apis_function_forms():
    found = {path.name: non_limited_macros(path.read_text(encoding="utf-8"))
             for path in sorted((CORE / "src").glob("*.cpp")) + sorted((CORE / "src").glob("*.h"))}
    assert not {name: hits for name, hits in found.items() if hits}, found
    # Negative control: round 4's failing line is caught.
    assert non_limited_macros("*out = QByteArray(PyBytes_AS_STRING(o), qsizetype(PyBytes_GET_SIZE(o)));") == [
        "PyBytes_AS_STRING(", "PyBytes_GET_SIZE("]


#: The STL containers the core never uses (their growth paths import std::_Xlength_error from msvcp140.dll, whose copy in
#: the process is shiboken6's, older than the compiler: P1 risk 4; N2.5 round 5's module was refused by the import
#: check for program_blocks' std::vector). Qt containers (QList, QByteArray, QHash, QString) instead.
_STL_CONTAINER = re.compile(r"\bstd::(?:vector|string|wstring|map|multimap|set|multiset|deque|list|forward_list|"
                            r"unordered_\w+)\b|#\s*include\s*<(?:vector|string|map|set|deque|list|forward_list|"
                            r"unordered_map|unordered_set)>")


def _code(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", re.sub(r"//[^\n]*", "", text), flags=re.S)


def stl_containers(text: str) -> list[str]:
    return [match.group(0) for match in _STL_CONTAINER.finditer(_code(text))]


def test_the_core_uses_no_stl_container():
    found = {path.name: stl_containers(path.read_text(encoding="utf-8"))
             for path in sorted((CORE / "src").glob("*.cpp")) + sorted((CORE / "src").glob("*.h"))}
    assert not {name: hits for name, hits in found.items() if hits}, found
    # Negative control: round 5's offending lines are caught.
    assert stl_containers("#include <vector>\n    std::vector<bool> m_filled;") == ["#include <vector>", "std::vector"]


#: A header naming a QRhi class's member (``QRhiTexture::Format``, ``QRhiGraphicsPipeline::TargetBlend``) needs the
#: class's definition, so it includes <rhi/qrhi.h> itself (round 5's first compile failed: targets.h and surfaces.h
#: named QRhiTexture::Format with only a forward declaration).
_QRHI_MEMBER = re.compile(r"\bQRhi\w*::\w+")


def qrhi_member_without_include(text: str) -> list[str]:
    code = _code(text)
    if re.search(r"#\s*include\s*<rhi/qrhi\.h>", code):
        return []
    return [match.group(0) for match in _QRHI_MEMBER.finditer(code)]


def test_a_header_naming_a_qrhi_member_includes_qrhi():
    found = {path.name: qrhi_member_without_include(path.read_text(encoding="utf-8"))
             for path in sorted((CORE / "src").glob("*.h"))}
    assert not {name: hits for name, hits in found.items() if hits}, found
    # Negative control: the slip of round 5's first compile.
    assert qrhi_member_without_include("class QRhiTexture;\nbool f(QRhiTexture::Format format = "
                                       "QRhiTexture::RGBA8);") == ["QRhiTexture::Format", "QRhiTexture::RGBA8"]


# ----------------------------------------------------------------------------------------------- the build script


def test_build_cmd_is_the_workflows_one_cmake_call_with_the_spikes_arguments():
    text = (CORE / "build.cmd").read_text(encoding="utf-8")
    assert "vswhere.exe" in text and "Microsoft.VisualStudio.Component.VC.Tools.x86.x64" in text
    assert "VC\\Auxiliary\\Build\\vcvars64.bat" in text and "BuildTools\\VC" not in text
    assert sdk.VULKAN_INCLUDE_RELATIVE in text and "%SDK%\\venv\\Scripts\\ninja.exe" in text
    for variable in ("CMAKE_PREFIX_PATH", "Python_EXECUTABLE", "CORE_QSB", "CORE_VULKAN_INCLUDE"):
        assert f"-D{variable}=" in text, variable
    assert len(re.findall(r"^cmake -S ", text, re.M)) == 1
    # The workflow calls every source's build.cmd with the same four arguments; the core's Quick part is not optional.
    assert 'if /i not "%QUICK%"=="ON"' in text
    cmake = (CORE / "CMakeLists.txt").read_text(encoding="utf-8")
    assert f"Python_add_library({loader.MODULE_NAME} MODULE USE_SABI 3.10" in cmake
