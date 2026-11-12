"""The native modules' GitHub build (.github/workflows/native-module.yml, its two sources native/core and
native/spike_p1, both sides of tools/github_remote_build.py's module targets, their Build Runner jobs,
native/spike_p1/python/import_check.py).

Nothing here compiles, dispatches or contacts GitHub: the workflow and build scripts are read as text, the runner's
build tree is a temporary folder with stand-in files, git runs on a throwaway repository, the GitHub CLI is a recorded
fake, and the spike module under import check is a stand-in Python module. The contracts proven: one workflow builds
every native source (its ``source`` input, by default the product's native core), exactly the requested commit, only
on dispatch or a call, with read-only permissions and no input interpolated into a script, and names its run for the
target that source builds; the SDK comes from the checked fetch, the compile from the source's build.cmd; staging
refuses a build without its module or without a shader its source has; the runner's manifest records the source, Qt,
PySide6 and MSVC a module was built with and refuses a module built for another Qt or not checked; locally a download
is published into release/<target> only when it is the requested commit's whole, unaltered module for the pinned Qt
with exactly its sources' shaders; an unpushed commit is never built; the Build Runner jobs are never pre-selected and
no installer depends on them."""
from __future__ import annotations

import json
import queue
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_github_remote_build import RUNNING, SUCCESS, FakeCli
from tools import build_runner
from tools import github_remote_build as remote
from tools import native_sdk_fetch as sdk

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "20261112_120000_000001"
NATIVE = remote.MODULE_TARGETS["native_module"]           # the product's native core
SPIKE = remote.MODULE_TARGETS["native_spike"]             # the P1 harness
QT = sdk.pinned_qt_version()          # the repository's pin (the import check's stand-ins)
FIXTURE_QT = "7.8.9"                  # the fixture repository's pin: the value flows from requirements.txt
# The fixture repository's shader sources per target (anything else in shaders/ is not a shader source).
FIXTURE_SHADERS = {"native_module": ("field.comp", ".gitkeep", "notes.md"),
                   "native_spike": ("quadfield.vert", "quadfield.frag")}


def _baked(key: str) -> list[str]:
    return sorted(f"{name}.qsb" for name in FIXTURE_SHADERS[key] if not name.startswith(".") and
                  not name.endswith(".md"))


# ------------------------------------------------------------------------------------------------- the workflow


def _workflow() -> str:
    return (ROOT / remote.NATIVE_WORKFLOW_PATH).read_text(encoding="utf-8")


def test_the_workflow_builds_only_the_requested_commit_on_dispatch_or_a_call():
    text = _workflow()
    triggers = text.split("\non:", 1)[1].split("\npermissions:", 1)[0]
    assert re.findall(r"^  (\w+):", triggers, re.MULTILINE) == ["workflow_dispatch", "workflow_call"]
    for trigger in triggers.split("\n  workflow_call:"):
        assert re.findall(r"^      (\w+):\n", trigger, re.MULTILINE) == ["commit", "token", "source"]
        source = trigger.split("      source:\n", 1)[1]
        assert re.search(r"^        default: (\S+)$", source, re.MULTILINE).group(1) == NATIVE.source
    assert "ref: ${{ inputs.commit }}" in text and "git rev-parse HEAD" in text     # checked out, then verified
    assert "permissions:\n  contents: read\n" in text and "secrets." not in text
    assert "runs-on: windows" in text and 'python-version: "3.14"' in text
    assert "name: srpss-${{ steps.target.outputs.key }}\n" in text
    assert remote.DEFAULT_NATIVE_TARGET == NATIVE.key and NATIVE.workflow == SPIKE.workflow == remote.NATIVE_WORKFLOW_FILE


def test_the_run_is_named_for_the_target_its_source_builds():
    """find_run matches ``<target>-<token>`` in the run's name; the workflow derives the target from the source with
    an expression (a run name cannot use a step's output), checked against MODULE_TARGETS here and on the runner."""
    text = _workflow()
    run_name = text.split("run-name:", 1)[1].splitlines()[0]
    mapping = re.search(r"inputs\.source == '([^']+)' && '(\w+)' \|\| '(\w+)'", run_name)
    assert mapping and f"-${{{{ inputs.token }}}}" in run_name
    source, named, otherwise = mapping.groups()
    assert remote.module_target_for_source(source).key == named
    assert remote.MODULE_TARGETS[otherwise].source == NATIVE.source and {named, otherwise} == set(remote.MODULE_TARGETS)
    assert run_name.split("SRPSS native", 1)[1].count(mapping.group(0)) == 1
    assert mapping.group(0) in text.split("RUN_NAME_TARGET:", 1)[1].splitlines()[0]       # the runner's own check
    assert "native-target --source $env:NATIVE_SOURCE" in text and "$key -ne $env:RUN_NAME_TARGET" in text


def test_the_workflow_never_interpolates_inputs_into_scripts():
    blocks = re.findall(r"run: \|\n((?:\s{10,}.*\n)+)", _workflow())
    assert len(blocks) >= 9 and not any("${{" in block for block in blocks)


def test_the_workflow_fetches_the_checked_sdk_and_compiles_with_the_sources_one_cmake_invocation():
    text = _workflow()
    assert "native_sdk_fetch.py --print-qt-version" in text and "--expect-qt $env:QT_VERSION" in text
    assert "tools\\native_sdk_fetch.py --prefix" in text and "-r native\\tool_requirements.txt" in text
    assert "hashFiles('tools/native_sdk_fetch.py')" in text and "${{ env.QT_VERSION }}" in text
    assert 'call "%NATIVE_DIR%\\build.cmd" "%GITHUB_WORKSPACE%\\%BUILD_DIR%" ON "%GITHUB_WORKSPACE%\\.venv" ' \
           '"%SDK_ROOT%"' in text and "cmake " not in text
    assert '"$env:NATIVE_DIR\\python\\import_check.py" --module-dir $env:BUILD_DIR' in text
    assert "-r requirements.txt" in text                                            # PySide6's qsb and Qt DLLs
    for step in ("stage-native --target $env:NATIVE_KEY", "manifest --target $env:NATIVE_KEY", remote.MANIFEST_NAME,
                 "if: failure()"):
        assert step in text, step
    assert remote.NATIVE_BUILD_LOG.format(key="%NATIVE_KEY%").replace("{token}", "%RUN_TOKEN%") in text
    assert remote.NATIVE_IMPORT_REPORT.format(key="$($env:NATIVE_KEY)").replace(
        "{token}", "$($env:RUN_TOKEN)") in text
    for target in remote.MODULE_TARGETS.values():                       # every source has what the workflow calls
        for part in ("build.cmd", "CMakeLists.txt", "python/import_check.py"):
            assert (ROOT / target.source / part).is_file(), (target.key, part)
        assert target.reports == (target.build_log, target.import_report)


def test_the_spikes_build_cmd_finds_msvc_with_vswhere_and_names_the_sdk_layout():
    text = (ROOT / SPIKE.source / "build.cmd").read_text(encoding="utf-8")
    assert "vswhere.exe" in text and "Microsoft.VisualStudio.Component.VC.Tools.x86.x64" in text
    assert "\\Microsoft Visual Studio\\18\\" not in text and "BuildTools\\VC" not in text   # no fixed install path
    assert "VC\\Auxiliary\\Build\\vcvars64.bat" in text
    assert sdk.VULKAN_INCLUDE_RELATIVE in text and "%SPIKE%\\venv\\Scripts\\ninja.exe" in text
    for variable in ("CMAKE_PREFIX_PATH", "Python_EXECUTABLE", "SPIKE_QSB", "SPIKE_VULKAN_INCLUDE", "SPIKE_WITH_QUICK"):
        assert f"-D{variable}=" in text, variable
    assert len(re.findall(r"^cmake -S ", text, re.MULTILINE)) == 1


def test_a_source_names_its_target_and_an_unknown_source_is_refused(capsys):
    assert remote.module_target_for_source("native/core") is NATIVE
    assert remote.module_target_for_source("native\\spike_p1\\") is SPIKE
    with pytest.raises(remote.RemoteBuildError, match="no native module is built from"):
        remote.module_target_for_source("native/other")
    assert remote.main(["native-target", "--source", "native/spike_p1"]) == 0
    assert capsys.readouterr().out.strip() == SPIKE.key
    assert remote.main(["native-target", "--source", "tools"]) == 1


def test_the_baked_shaders_are_one_per_shader_source():
    assert remote.expected_shaders(["a.vert", "a.frag", "b.comp", ".gitkeep", "README.md", "x.glsl"]) == (
        "a.frag.qsb", "a.vert.qsb", "b.comp.qsb")
    assert remote.expected_shaders([]) == ()
    for target in remote.MODULE_TARGETS.values():           # the real sources: exactly what CMake bakes
        folder = ROOT / target.source / "shaders"
        assert remote.expected_shaders([path.name for path in folder.iterdir()]) == tuple(sorted(
            f"{path.name}.qsb" for path in folder.iterdir() if path.suffix in remote.SHADER_SUFFIXES))


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
    (root / "requirements.txt").write_text(f"PySide6=={FIXTURE_QT}\nshiboken6=={FIXTURE_QT}\n", encoding="utf-8")
    (root / ".gitignore").write_text("release/\nlogs/\nbuild/\n", encoding="utf-8")
    for key, names in FIXTURE_SHADERS.items():
        folder = root / remote.MODULE_TARGETS[key].source / "shaders"
        folder.mkdir(parents=True)
        for name in names:
            (folder / name).write_text("// shader\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture")
    return root


def runtime_info(qt: str = FIXTURE_QT, **overrides) -> dict:
    info = {"qt_compiled": qt, "qt_runtime": qt, "msc_full_ver": 194435227, "with_quick": True,
            "loaded_modules": {}}
    info.update(overrides)
    return info


def runner_build(root: Path, target=NATIVE, *, import_ok: bool = True, info: dict | None = None, pyd: bool = True,
                 shaders: bool = True, log: bool = True) -> Path:
    """What the workflow leaves in the checkout before the manifest step: a build tree, its log and import check."""
    build = root / "build" / "native_module"
    (build / "generated").mkdir(parents=True, exist_ok=True)
    if pyd:
        (build / f"{target.module_name}.pyd").write_bytes(b"MZ module")
    if shaders:
        for name in _baked(target.key):
            (build / "generated" / name).write_bytes(f"qsb {name}".encode())
    (build / "generated" / "stale.vert.qsb").write_bytes(b"not a source of this build")     # never staged
    (root / "logs").mkdir(exist_ok=True)
    if log:
        (root / "logs" / target.build_log.format(token=TOKEN)).write_text("[ok] linked", encoding="utf-8")
    report = {"ok": import_ok, "checks": {"import": "ok"}, "runtime_info": info or runtime_info()}
    (root / "logs" / target.import_report.format(token=TOKEN)).write_text(json.dumps(report), encoding="utf-8")
    return build


@pytest.mark.parametrize("target", [NATIVE, SPIKE], ids=lambda target: target.key)
def test_the_runner_stages_the_module_and_records_what_it_was_built_with(tmp_path, target):
    root = _repo(tmp_path)
    build = runner_build(root, target)
    placed = remote.stage_native_module(root, build, target.key)
    payload = f"release/{target.payload_dirs[0]}"
    assert {path.relative_to(root).as_posix() for path in placed} == {
        f"release/{target.primary}", *(f"{payload}/{remote.SHADERS_DIR}/{name}" for name in _baked(target.key))}
    commit = _git(root, "rev-parse", "HEAD")
    manifest = remote.build_manifest(root, target.key, commit, TOKEN, pyside6_version=FIXTURE_QT)
    assert (manifest["target"], manifest["commit"], manifest["token"]) == (target.key, commit, TOKEN)
    assert manifest["native_source"] == target.source
    assert manifest["qt_version"] == FIXTURE_QT and manifest["pyside6_version"] == FIXTURE_QT
    assert manifest["msvc_version"] == "19.44.35227" and manifest["with_quick"] is True
    assert set(manifest["files"]) == {
        *(path.relative_to(root).as_posix() for path in placed),
        *(remote.REPORTS_PREFIX + name for name in target.report_names(TOKEN))}
    entry = manifest["files"][f"release/{target.primary}"]
    assert entry == {"bytes": len(b"MZ module"), "sha256": remote.sha256_file(root / "release" / target.primary)}


def test_a_source_without_shaders_stages_its_module_alone(tmp_path):
    root = _repo(tmp_path)
    for path in (root / NATIVE.source / "shaders").iterdir():
        path.unlink()
    placed = remote.stage_native_module(root, runner_build(root, NATIVE, shaders=False), NATIVE.key)
    assert [path.relative_to(root).as_posix() for path in placed] == [f"release/{NATIVE.primary}"]


@pytest.mark.parametrize("case", ["import-failed", "other-qt-compiled", "other-qt-runtime", "no-log", "no-import"])
def test_the_runner_refuses_to_describe_an_unchecked_or_mismatched_module(tmp_path, case):
    root = _repo(tmp_path)
    info = {"other-qt-compiled": runtime_info(qt_compiled="6.11.1"),
            "other-qt-runtime": runtime_info(qt_runtime="6.12.0")}.get(case)
    build = runner_build(root, import_ok=case != "import-failed", info=info, log=case != "no-log")
    if case == "no-import":
        (root / "logs" / NATIVE.import_report.format(token=TOKEN)).unlink()
    remote.stage_native_module(root, build)
    with pytest.raises(remote.RemoteBuildError):
        remote.build_manifest(root, "native_module", _git(root, "rev-parse", "HEAD"), TOKEN, pyside6_version=FIXTURE_QT)


@pytest.mark.parametrize("target", [NATIVE, SPIKE], ids=lambda target: target.key)
@pytest.mark.parametrize("missing", ["pyd", "shaders"])
def test_staging_refuses_a_build_without_its_module_or_shaders(tmp_path, missing, target):
    root = _repo(tmp_path)
    build = runner_build(root, target, pyd=missing != "pyd", shaders=missing != "shaders")
    with pytest.raises(remote.RemoteBuildError, match="produced no" if missing == "pyd" else "baked no"):
        remote.stage_native_module(root, build, target.key)
    assert not (root / "release").exists()


def test_the_msvc_version_reads_as_cl_prints_it():
    assert remote.msvc_version(195136231) == "19.51.36231"
    with pytest.raises(remote.RemoteBuildError):
        remote.msvc_version(1944)


# ------------------------------------------------------------------------------------- the spike's GPU-free check


@pytest.fixture
def import_check(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / SPIKE.source / "python"))
    monkeypatch.delitem(sys.modules, SPIKE.module_name, raising=False)
    monkeypatch.delitem(sys.modules, "import_check", raising=False)
    import import_check as module

    yield module
    sys.modules.pop(SPIKE.module_name, None)
    sys.modules.pop("import_check", None)


def _stand_in_module(folder: Path, *, qt: str = QT, dll_dir: str | None = None,
                     broken: bool = False) -> Path:
    """A Python stand-in for the compiled spike: the same name and ``runtime_info()`` shape."""
    folder.mkdir(parents=True, exist_ok=True)
    body = "raise ImportError('built for Qt 6.11.1 but the process runs Qt 6.11.2')\n" if broken else (
        "from pathlib import Path\nimport PySide6\n"
        f"_DLLS = Path({dll_dir!r}) if {dll_dir!r} else Path(PySide6.__file__).parent\n"
        "def runtime_info():\n"
        f"    return {{'qt_compiled': {qt!r}, 'qt_runtime': {qt!r}, 'msc_full_ver': 194435227, 'with_quick': True,\n"
        "            'loaded_modules': {name: str(_DLLS / name) for name in\n"
        "                               ('Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Qml.dll', 'Qt6Quick.dll')}}\n")
    (folder / f"{SPIKE.module_name}.py").write_text(body, encoding="utf-8")
    return folder


def test_the_import_check_passes_a_module_bound_to_pysides_qt(tmp_path, import_check):
    report = import_check.check(_stand_in_module(tmp_path / "ok"), QT)
    assert report["ok"] and report["runtime_info"]["qt_runtime"] == QT


@pytest.mark.parametrize("case", ["refused-import", "other-qt", "foreign-dlls"])
def test_the_import_check_fails_a_module_that_is_not(tmp_path, import_check, case):
    folder = _stand_in_module(tmp_path / case, broken=case == "refused-import",
                              qt="6.11.1" if case == "other-qt" else QT,
                              dll_dir=str(tmp_path / "elsewhere") if case == "foreign-dlls" else None)
    report = import_check.check(folder, QT)
    assert report["ok"] is False
    assert import_check.main(["--module-dir", str(folder), "--expect-qt", QT]) == 1


# ------------------------------------------------------------------------------- the download, validated (local)


def _artifact(root: Path, into: Path, target=NATIVE, *, pyside6: str = FIXTURE_QT) -> Path:
    """The runner side end to end (stage, manifest), then the upload layout the workflow produces."""
    remote.stage_native_module(root, runner_build(root, target), target.key)
    manifest = remote.build_manifest(root, target.key, _git(root, "rev-parse", "HEAD"), TOKEN,
                                     run_id="7", run_attempt="1", pyside6_version=pyside6)
    into.mkdir(parents=True)
    (into / remote.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    shutil.copytree(root / "release", into / "release")
    shutil.copytree(root / "logs", into / "logs")
    return into


def _validate(staging: Path, root: Path, target=NATIVE, **overrides):
    sha = _git(root, "rev-parse", "HEAD")
    expected = {"commit": sha, "version": "9.8.7", "token": TOKEN, "qt_version": FIXTURE_QT,
                "shaders": remote.shaders_at_commit(root, sha, target.source), **overrides}
    return remote.validate_staging(staging, target.key, **expected)


@pytest.mark.parametrize("target", [NATIVE, SPIKE], ids=lambda target: target.key)
def test_a_whole_module_build_of_the_requested_commit_validates(tmp_path, target):
    root = _repo(tmp_path)
    staging = _artifact(root, tmp_path / "staging", target)
    manifest = _validate(staging, root, target)
    assert f"release/{target.primary}" in manifest["files"] and manifest["qt_version"] == FIXTURE_QT
    assert remote.shaders_at_commit(root, _git(root, "rev-parse", "HEAD"), target.source) == tuple(_baked(target.key))
    with pytest.raises(remote.RemoteBuildError, match="pinned Qt"):            # a module needs the commit's pin
        _validate(staging, root, target, qt_version=None)
    with pytest.raises(remote.RemoteBuildError, match="shader sources"):       # and the commit's shader sources
        _validate(staging, root, target, shaders=None)


def _edit_manifest(staging: Path, change) -> None:
    path = staging / remote.MANIFEST_NAME
    manifest = json.loads(path.read_text(encoding="utf-8"))
    change(manifest)
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _tamper(staging: Path, case: str, target=NATIVE) -> None:
    payload = staging / "release" / target.payload_dirs[0]
    module = staging / "release" / target.primary
    if case == "pyd-bytes":
        module.write_bytes(b"MZ modulf")                                       # same size, other bytes
    elif case == "missing-pyd":
        module.unlink()
    elif case == "unlisted-pyd":                                             # removed from the manifest as well
        module.unlink()
        _edit_manifest(staging, lambda m: m["files"].pop(f"release/{target.primary}"))
    elif case == "no-shaders":
        shutil.rmtree(payload / remote.SHADERS_DIR)
        _edit_manifest(staging, lambda m: [m["files"].pop(name) for name in list(m["files"]) if name.endswith(".qsb")])
    elif case == "extra-shader":                                             # listed and hashed, but no source
        extra = payload / remote.SHADERS_DIR / "planted.frag.qsb"
        extra.write_bytes(b"qsb")
        _edit_manifest(staging, lambda m: m["files"].update({
            extra.relative_to(staging).as_posix(): {"bytes": 3, "sha256": remote.sha256_file(extra)}}))
    elif case == "planted-dll":
        (payload / "Qt6Gui.dll").write_bytes(b"x")
    elif case == "qt-version":
        _edit_manifest(staging, lambda m: m.update(qt_version="6.11.1"))
    elif case == "pyside6-version":
        _edit_manifest(staging, lambda m: m.update(pyside6_version="6.12.0"))
    elif case == "no-msvc":
        _edit_manifest(staging, lambda m: m.pop("msvc_version"))
    elif case == "other-source":
        _edit_manifest(staging, lambda m: m.update(native_source=SPIKE.source if target is NATIVE else NATIVE.source))
    elif case == "escape":
        _edit_manifest(staging, lambda m: m["files"].update(
            {f"release/{target.payload_dirs[0]}/../screensaver/SRPSS.scr": {"bytes": 1, "sha256": "0"}}))


@pytest.mark.parametrize("target", [NATIVE, SPIKE], ids=lambda target: target.key)
@pytest.mark.parametrize("case", ["pyd-bytes", "missing-pyd", "unlisted-pyd", "no-shaders", "extra-shader",
                                  "planted-dll", "qt-version", "pyside6-version", "no-msvc", "other-source", "escape"])
def test_an_altered_or_incomplete_module_download_is_refused(tmp_path, case, target):
    root = _repo(tmp_path)
    staging = _artifact(root, tmp_path / "staging", target)
    _tamper(staging, case, target)
    with pytest.raises(remote.RemoteBuildError):
        _validate(staging, root, target)


@pytest.mark.parametrize("field,value", [("commit", "f" * 40), ("version", "9.8.8"),
                                         ("token", "20261112_120000_000002")])
def test_a_module_of_another_commit_version_or_run_is_refused(tmp_path, field, value):
    root = _repo(tmp_path)
    staging = _artifact(root, tmp_path / "staging")
    with pytest.raises(remote.RemoteBuildError, match=field):
        _validate(staging, root, **{field: value})


# --------------------------------------------------------------- the products carry the native core (product job)


def test_every_product_carries_the_native_core_and_requires_its_frozen_probe():
    for target in remote.TARGETS.values():
        assert target.native == remote.CARRIED_NATIVE.key == NATIVE.key
        assert set(NATIVE.payload_dirs) <= set(target.payload_dirs) and NATIVE.primary in target.artifacts
        assert target.payload_dirs[0] != NATIVE.payload_dirs[0]               # the product's own folder comes first
        assert remote.NATIVE_PROBE_REPORT in target.reports


def test_the_product_workflow_calls_the_native_workflow_then_places_and_probes_its_module():
    text = (ROOT / remote.WORKFLOW_PATH).read_text(encoding="utf-8")
    jobs = text.split("\njobs:\n", 1)[1]
    native = jobs.split("\n  build:\n", 1)[0]
    assert f"uses: ./.github/workflows/{remote.NATIVE_WORKFLOW_FILE}" in native
    assert "commit: ${{ inputs.commit }}" in native and "token: ${{ inputs.token }}" in native
    assert f"source: {NATIVE.source}" in native
    build = jobs.split("\n  build:\n", 1)[1]
    assert "needs: native" in build
    steps = [build.index(marker) for marker in (
        "Build with the canonical worker", f"name: {NATIVE.artifact}\n", "place-native --artifact-dir",
        "scripts/venv/build_native_core_probe.ps1", "Record the build manifest")]
    assert steps == sorted(steps)                                            # worker, place, probe, then manifest
    assert remote.NATIVE_PROBE_REPORT.format(token="$($env:SRPSS_BUILD_RUN_ID)") in build
    probe = (ROOT / "scripts" / "venv" / "build_native_core_probe.ps1").read_text(encoding="utf-8")
    for needed in ("Get-SRPSSNuitkaQmlPruneArguments -RepoRoot $Root", "--standalone", "--enable-plugin=pyside6",
                   "--include-qt-plugins=qml", "--include-module=rendering.native.$ModuleName",
                   "native\\core\\python\\frozen_probe.py", "$Result.ok -ne $true", "$Result.frozen -ne $true"):
        assert needed in probe, needed
    assert f"$ModuleName = '{NATIVE.module_name}'" in probe
    assert "main.py" not in probe                                            # the product itself is not frozen here


def _placed(root: Path, tmp_path: Path) -> str:
    """The product job's place-native on this run's native artifact; returns the built commit."""
    sha = _git(root, "rev-parse", "HEAD")
    artifact = _artifact(root, tmp_path / "native_artifact", NATIVE)
    shutil.rmtree(root / "release")                         # the product checkout: no native build of its own
    shutil.rmtree(root / "logs")
    remote.place_native_module(root, artifact, sha, TOKEN)
    return sha


def test_place_native_puts_the_validated_module_in_the_release_tree(tmp_path):
    root = _repo(tmp_path)
    _placed(root, tmp_path)
    payload = root / "release" / NATIVE.payload_dirs[0]
    assert (root / "release" / NATIVE.primary).read_bytes() == b"MZ module"
    assert sorted(path.name for path in (payload / remote.SHADERS_DIR).iterdir()) == _baked(NATIVE.key)
    kept = json.loads((payload / remote.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert (kept["target"], kept["native_source"], kept["token"]) == (NATIVE.key, NATIVE.source, TOKEN)
    for name in NATIVE.reports:
        assert (root / "logs" / name.format(token=TOKEN)).is_file()


@pytest.mark.parametrize("case", ["qt-version", "pyd-bytes", "no-shaders", "other-source"])
def test_place_native_refuses_an_altered_module_and_places_nothing(tmp_path, case):
    root = _repo(tmp_path)
    sha = _git(root, "rev-parse", "HEAD")
    artifact = _artifact(root, tmp_path / "native_artifact", NATIVE)
    shutil.rmtree(root / "release")
    _tamper(artifact, case, NATIVE)
    with pytest.raises(remote.RemoteBuildError):
        remote.place_native_module(root, artifact, sha, TOKEN)
    assert not (root / "release").exists()
    with pytest.raises(remote.RemoteBuildError, match="token"):
        remote.place_native_module(root, _artifact(root, tmp_path / "other_run", NATIVE), sha,
                                   "20261112_120000_000009")


def _product_with_core(root: Path, tmp_path: Path, *, probe: dict | None = None) -> Path:
    """A Standard build of the fixture commit carrying the placed core, uploaded as the product workflow does."""
    sha = _placed(root, tmp_path)
    target = remote.TARGETS["standard"]
    for relative in (target.primary, *target.companions):
        path = root / "release" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"product")
    if probe is not False:
        (root / "logs" / remote.NATIVE_PROBE_REPORT.format(token=TOKEN)).write_text(
            json.dumps(probe or {"ok": True, "frozen": True, "checks": {"load": "ok"}}), encoding="utf-8")
    manifest = remote.build_manifest(root, target.key, sha, TOKEN)
    staging = tmp_path / "product_staging"
    staging.mkdir()
    (staging / remote.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    shutil.copytree(root / "release", staging / "release")
    shutil.copytree(root / "logs", staging / "logs")
    return staging


def _validate_product(staging: Path, root: Path):
    sha = _git(root, "rev-parse", "HEAD")
    return remote.validate_staging(staging, "standard", commit=sha, version="9.8.7", token=TOKEN,
                                   qt_version=remote.qt_version_at_commit(root, sha),
                                   shaders=remote.shaders_at_commit(root, sha, NATIVE.source))


def test_a_product_carrying_the_runs_validated_core_validates(tmp_path):
    root = _repo(tmp_path)
    staging = _product_with_core(root, tmp_path)
    manifest = _validate_product(staging, root)
    assert f"release/{NATIVE.primary}" in manifest["files"]
    assert remote.REPORTS_PREFIX + remote.NATIVE_PROBE_REPORT.format(token=TOKEN) in manifest["files"]


def _rehash(staging: Path, relative: str) -> None:
    path = staging / relative
    _edit_manifest(staging, lambda m: m["files"].update(
        {relative: {"bytes": path.stat().st_size, "sha256": remote.sha256_file(path)}}))


@pytest.mark.parametrize("case", ["swapped-core", "core-of-another-run", "probe-failed", "probe-unfrozen"])
def test_a_product_whose_core_is_not_the_runs_or_failed_its_probe_is_refused(tmp_path, case):
    root = _repo(tmp_path)
    probe = {"probe-failed": {"ok": False, "frozen": True, "checks": {"load": "FAILED: x"}},
             "probe-unfrozen": {"ok": True, "frozen": False, "checks": {}}}.get(case)
    staging = _product_with_core(root, tmp_path, probe=probe)
    folder = f"release/{NATIVE.payload_dirs[0]}/"
    if case == "swapped-core":                     # other bytes, consistently re-listed in the product's manifest
        (staging / "release" / NATIVE.primary).write_bytes(b"MZ other core")
        _rehash(staging, f"release/{NATIVE.primary}")
    elif case == "core-of-another-run":
        carried = staging / folder / remote.MANIFEST_NAME
        data = json.loads(carried.read_text(encoding="utf-8"))
        data["token"] = "20261112_120000_000009"
        carried.write_text(json.dumps(data), encoding="utf-8")
        _rehash(staging, folder + remote.MANIFEST_NAME)
    with pytest.raises(remote.RemoteBuildError):
        _validate_product(staging, root)


def test_a_product_without_its_frozen_probe_report_is_not_described(tmp_path):
    root = _repo(tmp_path)
    with pytest.raises(remote.RemoteBuildError, match=remote.NATIVE_PROBE_REPORT.format(token=TOKEN)):
        _product_with_core(root, tmp_path, probe=False)


@pytest.mark.skipif(sys.platform != "win32", reason="the native core is built for Windows only so far")
def test_the_frozen_probe_reports_a_core_it_cannot_load_as_its_failure(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / NATIVE.source / "python"))
    monkeypatch.delitem(sys.modules, "frozen_probe", raising=False)
    monkeypatch.delitem(sys.modules, NATIVE.module_name, raising=False)
    import frozen_probe

    try:
        out = tmp_path / "probe.json"
        assert frozen_probe.main(["--out", str(out)]) == 1      # unfrozen, nothing at the package location
        report = json.loads(out.read_text(encoding="utf-8"))
        assert report["frozen"] is False and report["ok"] is False
        assert report["checks"]["load"].startswith("FAILED: ") and "cannot be imported" in report["checks"]["load"]
    finally:
        sys.modules.pop("frozen_probe", None)


# ---------------------------------------------------------------------------- dispatch, follow, publish (local)


def test_each_module_dispatches_the_one_native_workflow_with_its_source():
    calls = []

    def run(args, _timeout):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0, "[]", "")

    cli = remote.GitHubCli(run=run)
    sha = "c" * 40
    cli.dispatch("native_module", "work/branch", sha, TOKEN)
    cli.dispatch("native_spike", "work/branch", sha, TOKEN)
    cli.dispatch("standard", "main", sha, TOKEN)
    for call, target in zip(calls, (NATIVE, SPIKE)):
        assert call == ["gh", "workflow", "run", remote.NATIVE_WORKFLOW_FILE, "--ref", "work/branch",
                        "-f", f"commit={sha}", "-f", f"token={TOKEN}", "-f", f"source={target.source}"]
    assert calls[2] == ["gh", "workflow", "run", remote.WORKFLOW_FILE, "--ref", "main",
                        "-f", "target=standard", "-f", f"commit={sha}", "-f", f"token={TOKEN}"]
    cli.find_run(f"native_module-{TOKEN}", workflow=NATIVE.workflow)
    cli.startup_failure(remote.datetime.now(remote.timezone.utc), sha, workflow=NATIVE.workflow)
    assert all(call[call.index("--workflow") + 1] == remote.NATIVE_WORKFLOW_FILE for call in calls[3:])


def _orchestrate(tmp_path, monkeypatch, cli, *, keys=("native_module",), local_head: str | None = None,
                 release: Path | None = None):
    root = tmp_path / "repo"
    sha = _git(root, "rev-parse", "HEAD")
    monkeypatch.setattr(remote, "resolve_pushed_commit", lambda *_a, **_k: remote.PushedCommit(
        "work", sha, "x", local_head or sha))
    release = release or tmp_path / "release"
    results = remote.run_remote_builds(
        root, cli, list(keys), remote.PushedCommit("work", sha, "fixture", sha), TOKEN,
        log_dir=tmp_path / "logs", release_dir=release, cancelled=lambda: False,
        emit=lambda *_event: None, poll_seconds=0.0, sleep=lambda _s: None,
    )
    return results, release


def test_validated_modules_are_published_into_release_with_their_manifests(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    artifacts = {}
    for target in (NATIVE, SPIKE):
        artifacts[target.key] = _artifact(root, tmp_path / f"artifact_{target.key}", target)
        shutil.rmtree(root / "release")                     # the runner's staging; the local tree is separate
        shutil.rmtree(root / "logs")
        shutil.rmtree(root / "build")
    release = tmp_path / "release"
    (release / "native_module").mkdir(parents=True)
    (release / "native_module" / "previous.pyd").write_bytes(b"old")
    (release / "screensaver").mkdir()
    (release / "screensaver" / "SRPSS.scr").write_bytes(b"product")
    cli = FakeCli(artifacts, {"native_module": [RUNNING, SUCCESS], "native_spike": [SUCCESS]})
    results, release = _orchestrate(tmp_path, monkeypatch, cli, keys=("native_module", "native_spike"),
                                    release=release)
    assert all(result.ok for result in results.values()), {key: r.detail for key, r in results.items()}
    assert [entry[0] for entry in cli.dispatched] == ["native_module", "native_spike"]
    assert {workflow for _request, workflow in cli.lookups} == {remote.NATIVE_WORKFLOW_FILE}
    for target in (NATIVE, SPIKE):
        published = release / target.payload_dirs[0]
        assert (published / Path(target.primary).name).read_bytes() == b"MZ module"
        shaders = published / remote.SHADERS_DIR
        assert sorted(path.name for path in shaders.iterdir()) == _baked(target.key)
        kept = json.loads((published / remote.MANIFEST_NAME).read_text(encoding="utf-8"))
        assert kept["native_source"] == target.source and kept["qt_version"] == FIXTURE_QT
        assert results[target.key].output_path == published
        for name in target.report_names(TOKEN):
            assert (tmp_path / "logs" / name).is_file()
    assert not (release / "native_module" / "previous.pyd").exists()
    assert (release / "screensaver" / "SRPSS.scr").read_bytes() == b"product"     # the products are untouched


def test_an_invalid_module_download_keeps_the_previous_module(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    artifact = _artifact(root, tmp_path / "artifact")
    _tamper(artifact, "qt-version")
    release = tmp_path / "release"
    (release / "native_module").mkdir(parents=True)
    (release / "native_module" / "previous.pyd").write_bytes(b"old")
    cli = FakeCli({"native_module": artifact}, {"native_module": [SUCCESS]})
    results, release = _orchestrate(tmp_path, monkeypatch, cli, release=release)
    assert not results["native_module"].ok and "qt_version" in results["native_module"].detail
    assert sorted(path.name for path in (release / "native_module").iterdir()) == ["previous.pyd"]


def test_the_expected_qt_and_shaders_are_the_built_commits_not_the_working_trees(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    artifact = _artifact(root, tmp_path / "artifact")
    built = _git(root, "rev-parse", "HEAD")
    (root / "requirements.txt").write_text("PySide6==9.9.9\n", encoding="utf-8")       # uncommitted edits
    (root / NATIVE.source / "shaders" / "later.frag").write_text("// later\n", encoding="utf-8")
    cli = FakeCli({"native_module": artifact}, {"native_module": [SUCCESS]})
    results, _release = _orchestrate(tmp_path, monkeypatch, cli)
    assert results["native_module"].ok, results["native_module"].detail
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "the Qt bump and a shader")
    head = _git(root, "rev-parse", "HEAD")
    assert remote.qt_version_at_commit(root, built) == FIXTURE_QT
    assert remote.qt_version_at_commit(root, head) == "9.9.9"
    assert remote.shaders_at_commit(root, built, NATIVE.source) == tuple(_baked("native_module"))
    assert "later.frag.qsb" in remote.shaders_at_commit(root, head, NATIVE.source)


def test_an_unpushed_commit_is_never_built(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    artifact = _artifact(root, tmp_path / "artifact")
    cli = FakeCli({"native_module": artifact}, {"native_module": [SUCCESS]})
    results, release = _orchestrate(tmp_path, monkeypatch, cli, local_head="a" * 40)
    assert not results["native_module"].ok and "push it first" in results["native_module"].detail
    assert cli.dispatched == [] and not (release / "native_module").exists()


# ------------------------------------------------------------------------------------------- Build Runner's tab


def test_the_github_tab_offers_both_modules_unselected_and_publishing_into_release(tmp_path):
    github = {job.key: job for job in build_runner.jobs_for_mode("github", tmp_path)}
    venv = {job.key for job in build_runner.jobs_for_mode("venv", tmp_path)}
    for target in (NATIVE, SPIKE):
        job = github[target.key]
        assert job.kind == "github" and not job.default_selected and target.key not in venv
        assert job.script == tmp_path / remote.NATIVE_WORKFLOW_PATH and (ROOT / remote.NATIVE_WORKFLOW_PATH).is_file()
        assert job.output_dir == tmp_path / "release" / target.payload_dirs[0]
        assert job.artifacts == (tmp_path / "release" / target.primary,)
    assert github["native_module"].name != github["native_spike"].name


def test_the_module_alone_dispatches_only_itself_and_runs_no_local_step(monkeypatch, tmp_path):
    jobs = build_runner.jobs_for_mode("github", tmp_path)
    order = []

    def run_remote(_root, _cli, keys, _commit, _token, *, emit, between, **_kwargs):
        order.append(("dispatch", tuple(keys)))
        between()
        result = remote.RemoteResult("native_module", 0, "Completed", Path("l"), Path("o"))
        emit("done", "native_module", result)
        return {"native_module": result}

    def run_job(job, _preflight, *, process_owner):
        order.append(("local", job.key))
        return build_runner.JobResult(0, "Completed", Path("log"), job.output_dir)

    monkeypatch.setattr(remote, "run_remote_builds", run_remote)
    monkeypatch.setattr(build_runner, "run_job", run_job)
    monkeypatch.setattr(build_runner, "helper_build_status", lambda *_a, **_k: SimpleNamespace(
        needs_rebuild=True, reason="stale", fingerprint="f"))
    app = SimpleNamespace(_events=queue.Queue())
    preflight = build_runner.PreflightResult(remote_commit=remote.PushedCommit("work", "c" * 40, "x", "c" * 40))
    build_runner.BuildRunnerApp._github_pipeline_worker(app, jobs, {"native_module"}, preflight,
                                                        build_runner.BuildProcessOwner())
    assert order == [("dispatch", ("native_module",))]          # no helper, no installer
    events = []
    while not app._events.empty():
        events.append(app._events.get())
    assert events[-1][:2] == ("pipeline_done", True)


def test_the_headless_run_selects_a_module_only_when_asked(monkeypatch):
    commit = remote.PushedCommit("work", "c" * 40, "x", "c" * 40)
    monkeypatch.setattr(build_runner, "run_preflight", lambda mode, **_kw: build_runner.PreflightResult(
        remote_commit=commit))
    monkeypatch.setattr(build_runner, "helper_build_status", lambda *_a, **_k: SimpleNamespace(
        needs_rebuild=True, reason="stale", fingerprint="f"))
    seen = []

    def pipeline(host, jobs, selected, preflight, owner):
        seen.append(set(selected))
        host._events.put(("pipeline_done", True, "done", False))

    monkeypatch.setattr(build_runner.BuildRunnerApp, "_github_pipeline_worker", pipeline)
    assert build_runner.run_headless(None, out=lambda _line: None) == 0
    assert build_runner.run_headless(["native_module"], out=lambda _line: None) == 0
    assert build_runner.run_headless(["native_spike"], out=lambda _line: None) == 0
    assert not set(remote.MODULE_TARGETS) & seen[0]
    assert seen[1:] == [{"native_module"}, {"native_spike"}]


def _preflight_with(monkeypatch, commit, *, registered=True):
    monkeypatch.setattr(remote, "resolve_pushed_commit", lambda *_a, **_k: commit)
    monkeypatch.setattr(build_runner.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    monkeypatch.setattr(remote.GitHubCli, "signed_in", lambda self: True)
    monkeypatch.setattr(remote.GitHubCli, "actions_policy_problem", lambda self: None)
    monkeypatch.setattr(remote.GitHubCli, "workflow_registered", lambda self, workflow=remote.WORKFLOW_FILE: (
        registered or workflow != remote.NATIVE_WORKFLOW_FILE))
    result = build_runner.PreflightResult()
    build_runner._github_preflight(result, build_runner.jobs_for_mode("github"), build_runner.REPO_ROOT)
    return result


def test_preflight_makes_only_the_modules_unavailable_for_an_unpushed_head_or_an_unlisted_workflow(monkeypatch):
    pushed = remote.PushedCommit("work", "d" * 40, "s", "d" * 40)
    assert not set(remote.MODULE_TARGETS) & _preflight_with(monkeypatch, pushed).unavailable_jobs
    for result in (_preflight_with(monkeypatch, replace_head(pushed, "a" * 40)),
                   _preflight_with(monkeypatch, pushed, registered=False)):
        assert set(remote.MODULE_TARGETS) <= result.unavailable_jobs and not result.errors
        assert not {"standard", "media_center"} & result.unavailable_jobs
        assert any(warning.startswith("Native Module:") for warning in result.warnings)


def replace_head(commit: remote.PushedCommit, head: str) -> remote.PushedCommit:
    return remote.PushedCommit(commit.branch, commit.sha, commit.subject, head)
