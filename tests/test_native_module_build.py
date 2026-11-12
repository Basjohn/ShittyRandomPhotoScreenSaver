"""The native module's GitHub build (.github/workflows/native-module.yml, native/spike_p1/build.cmd, the runner side
of tools/github_remote_build.py, native/spike_p1/python/import_check.py).

Nothing here compiles, dispatches or contacts GitHub: the workflow and build script are read as text, the runner's
build tree is a temporary folder with stand-in files, git runs on a throwaway repository, and the module under import
check is a stand-in Python module. The contracts proven: the workflow builds exactly the requested commit, only on
dispatch or a call, with read-only permissions and no input interpolated into a script; the SDK comes from the
checked fetch, the compile from build.cmd's one CMake invocation with vcvars found by vswhere; the runner's manifest
records the Qt, PySide6 and MSVC a module was built with and refuses a module built for another Qt or not checked."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tools import github_remote_build as remote
from tools import native_sdk_fetch as sdk

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "20261112_120000_000001"
NATIVE = remote.MODULE_TARGETS["native_module"]


# ------------------------------------------------------------------------------------------------- the workflow


def _workflow() -> str:
    return (ROOT / remote.NATIVE_WORKFLOW_PATH).read_text(encoding="utf-8")


def test_the_workflow_builds_only_the_requested_commit_on_dispatch_or_a_call():
    text = _workflow()
    triggers = text.split("\non:", 1)[1].split("\npermissions:", 1)[0]
    assert re.findall(r"^  (\w+):", triggers, re.MULTILINE) == ["workflow_dispatch", "workflow_call"]
    for trigger in triggers.split("\n  workflow_call:"):
        assert re.findall(r"^      (\w+):\n", trigger, re.MULTILINE) == ["commit", "token"]
    assert "ref: ${{ inputs.commit }}" in text and "git rev-parse HEAD" in text     # checked out, then verified
    assert "permissions:\n  contents: read\n" in text and "secrets." not in text
    assert "runs-on: windows" in text and 'python-version: "3.14"' in text
    # find_run matches "<key>-<token>" in the run's name.
    assert f"{NATIVE.key}-${{{{ inputs.token }}}}" in text.split("run-name:", 1)[1].splitlines()[0]
    assert f"name: {NATIVE.artifact}\n" in text and NATIVE.workflow == remote.NATIVE_WORKFLOW_FILE


def test_the_workflow_never_interpolates_inputs_into_scripts():
    blocks = re.findall(r"run: \|\n((?:\s{10,}.*\n)+)", _workflow())
    assert len(blocks) >= 8 and not any("${{" in block for block in blocks)


def test_the_workflow_fetches_the_checked_sdk_and_compiles_with_the_one_cmake_invocation():
    text = _workflow()
    assert re.search(r'QT_VERSION: "([^"]+)"', text).group(1) == sdk.QT_VERSION == NATIVE.module_qt
    assert "tools\\native_sdk_fetch.py --prefix" in text and "-r native\\tool_requirements.txt" in text
    assert "hashFiles('tools/native_sdk_fetch.py')" in text and "${{ env.QT_VERSION }}" in text
    assert f"call {remote.NATIVE_SOURCE.replace('/', chr(92))}\\build.cmd" in text and "cmake " not in text
    assert "-r requirements.txt" in text                                            # PySide6's qsb and Qt DLLs
    for step in ("import_check.py", "stage-native --target native_module", "manifest --target native_module",
                 remote.MANIFEST_NAME, "if: failure()"):
        assert step in text, step
    for report in NATIVE.reports:
        assert report.replace("{token}", "%RUN_TOKEN%") in text or report.replace(
            "{token}", "$env:RUN_TOKEN") in text, report


def test_build_cmd_finds_msvc_with_vswhere_and_names_the_sdk_layout():
    text = (ROOT / remote.NATIVE_SOURCE / "build.cmd").read_text(encoding="utf-8")
    assert "vswhere.exe" in text and "Microsoft.VisualStudio.Component.VC.Tools.x86.x64" in text
    assert "\\Microsoft Visual Studio\\18\\" not in text and "BuildTools\\VC" not in text   # no fixed install path
    assert "VC\\Auxiliary\\Build\\vcvars64.bat" in text
    assert sdk.VULKAN_INCLUDE_RELATIVE in text and "%SPIKE%\\venv\\Scripts\\ninja.exe" in text
    for variable in ("CMAKE_PREFIX_PATH", "Python_EXECUTABLE", "SPIKE_QSB", "SPIKE_VULKAN_INCLUDE", "SPIKE_WITH_QUICK"):
        assert f"-D{variable}=" in text, variable
    assert len(re.findall(r"^cmake -S ", text, re.MULTILINE)) == 1


# ------------------------------------------------------------------------------------------- the runner's manifest


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    (root / "versioning.py").write_text('APP_VERSION: str = "9.8.7"\n', encoding="utf-8")
    (root / ".gitignore").write_text("release/\nlogs/\nbuild/\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture")
    return root


def runtime_info(qt: str = sdk.QT_VERSION, **overrides) -> dict:
    info = {"qt_compiled": qt, "qt_runtime": qt, "msc_full_ver": 194435227, "with_quick": True,
            "loaded_modules": {}}
    info.update(overrides)
    return info


def runner_build(root: Path, *, import_ok: bool = True, info: dict | None = None, pyd: bool = True,
                 shaders: bool = True, log: bool = True) -> Path:
    """What the workflow leaves in the checkout before the manifest step: a build tree, its log and import check."""
    build = root / "build" / "native_module"
    (build / "generated").mkdir(parents=True)
    if pyd:
        (build / f"{remote.NATIVE_MODULE}.pyd").write_bytes(b"MZ module")
    if shaders:
        for stage in ("vert", "frag"):
            (build / "generated" / f"quadfield.{stage}.qsb").write_bytes(f"qsb {stage}".encode())
    (root / "logs").mkdir(exist_ok=True)
    if log:
        (root / "logs" / remote.NATIVE_BUILD_LOG.format(token=TOKEN)).write_text("[ok] linked", encoding="utf-8")
    report = {"ok": import_ok, "checks": {"import": "ok"}, "runtime_info": info or runtime_info()}
    (root / "logs" / remote.NATIVE_IMPORT_REPORT.format(token=TOKEN)).write_text(json.dumps(report), encoding="utf-8")
    return build


def test_the_runner_stages_the_module_and_records_what_it_was_built_with(tmp_path):
    root = _repo(tmp_path)
    build = runner_build(root)
    placed = remote.stage_native_module(root, build)
    payload = f"release/{NATIVE.payload_dirs[0]}"
    assert {path.relative_to(root).as_posix() for path in placed} == {
        f"release/{NATIVE.primary}", f"{payload}/{remote.SHADERS_DIR}/quadfield.vert.qsb",
        f"{payload}/{remote.SHADERS_DIR}/quadfield.frag.qsb"}
    commit = _git(root, "rev-parse", "HEAD")
    manifest = remote.build_manifest(root, "native_module", commit, TOKEN, pyside6_version=sdk.QT_VERSION)
    assert (manifest["target"], manifest["commit"], manifest["token"]) == ("native_module", commit, TOKEN)
    assert manifest["qt_version"] == sdk.QT_VERSION and manifest["pyside6_version"] == sdk.QT_VERSION
    assert manifest["msvc_version"] == "19.44.35227" and manifest["with_quick"] is True
    assert set(manifest["files"]) == {
        *(path.relative_to(root).as_posix() for path in placed),
        *(remote.REPORTS_PREFIX + name for name in NATIVE.report_names(TOKEN))}
    entry = manifest["files"][f"release/{NATIVE.primary}"]
    assert entry == {"bytes": len(b"MZ module"), "sha256": remote.sha256_file(root / "release" / NATIVE.primary)}


@pytest.mark.parametrize("case", ["import-failed", "other-qt-compiled", "other-qt-runtime", "no-log", "no-import"])
def test_the_runner_refuses_to_describe_an_unchecked_or_mismatched_module(tmp_path, case):
    root = _repo(tmp_path)
    info = {"other-qt-compiled": runtime_info(qt_compiled="6.11.1"),
            "other-qt-runtime": runtime_info(qt_runtime="6.12.0")}.get(case)
    build = runner_build(root, import_ok=case != "import-failed", info=info, log=case != "no-log")
    if case == "no-import":
        (root / "logs" / remote.NATIVE_IMPORT_REPORT.format(token=TOKEN)).unlink()
    remote.stage_native_module(root, build)
    with pytest.raises(remote.RemoteBuildError):
        remote.build_manifest(root, "native_module", _git(root, "rev-parse", "HEAD"), TOKEN, pyside6_version="6.11.2")


@pytest.mark.parametrize("missing", ["pyd", "shaders"])
def test_staging_refuses_a_build_without_its_module_or_shaders(tmp_path, missing):
    root = _repo(tmp_path)
    build = runner_build(root, pyd=missing != "pyd", shaders=missing != "shaders")
    with pytest.raises(remote.RemoteBuildError):
        remote.stage_native_module(root, build)
    assert not (root / "release").exists()


def test_the_msvc_version_reads_as_cl_prints_it():
    assert remote.msvc_version(195136231) == "19.51.36231"
    with pytest.raises(remote.RemoteBuildError):
        remote.msvc_version(1944)


# ------------------------------------------------------------------------------------------ the GPU-free check


@pytest.fixture
def import_check(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / remote.NATIVE_SOURCE / "python"))
    monkeypatch.delitem(sys.modules, remote.NATIVE_MODULE, raising=False)
    import import_check as module

    yield module
    sys.modules.pop(remote.NATIVE_MODULE, None)


def _stand_in_module(folder: Path, *, qt: str = sdk.QT_VERSION, dll_dir: str | None = None,
                     broken: bool = False) -> Path:
    """A Python stand-in for the compiled module: the same name and ``runtime_info()`` shape."""
    folder.mkdir(parents=True, exist_ok=True)
    body = "raise ImportError('built for Qt 6.11.1 but the process runs Qt 6.11.2')\n" if broken else (
        "from pathlib import Path\nimport PySide6\n"
        f"_DLLS = Path({dll_dir!r}) if {dll_dir!r} else Path(PySide6.__file__).parent\n"
        "def runtime_info():\n"
        f"    return {{'qt_compiled': {qt!r}, 'qt_runtime': {qt!r}, 'msc_full_ver': 194435227, 'with_quick': True,\n"
        "            'loaded_modules': {name: str(_DLLS / name) for name in\n"
        "                               ('Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Qml.dll', 'Qt6Quick.dll')}}\n")
    (folder / f"{remote.NATIVE_MODULE}.py").write_text(body, encoding="utf-8")
    return folder


def test_the_import_check_passes_a_module_bound_to_pysides_qt(tmp_path, import_check):
    report = import_check.check(_stand_in_module(tmp_path / "ok"), sdk.QT_VERSION)
    assert report["ok"] and report["runtime_info"]["qt_runtime"] == sdk.QT_VERSION


@pytest.mark.parametrize("case", ["refused-import", "other-qt", "foreign-dlls"])
def test_the_import_check_fails_a_module_that_is_not(tmp_path, import_check, case):
    folder = _stand_in_module(tmp_path / case, broken=case == "refused-import",
                              qt="6.11.1" if case == "other-qt" else sdk.QT_VERSION,
                              dll_dir=str(tmp_path / "elsewhere") if case == "foreign-dlls" else None)
    report = import_check.check(folder, sdk.QT_VERSION)
    assert report["ok"] is False
    assert import_check.main(["--module-dir", str(folder), "--expect-qt", sdk.QT_VERSION]) == 1
