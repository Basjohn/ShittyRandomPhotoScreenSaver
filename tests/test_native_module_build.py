"""The native module's GitHub build (.github/workflows/native-module.yml, native/spike_p1/build.cmd, both sides of
tools/github_remote_build.py's ``native_module`` target, its Build Runner job, native/spike_p1/python/import_check.py).

Nothing here compiles, dispatches or contacts GitHub: the workflow and build script are read as text, the runner's
build tree is a temporary folder with stand-in files, git runs on a throwaway repository, the GitHub CLI is a recorded
fake, and the module under import check is a stand-in Python module. The contracts proven: the workflow builds exactly
the requested commit, only on dispatch or a call, with read-only permissions and no input interpolated into a script;
the SDK comes from the checked fetch, the compile from build.cmd's one CMake invocation with vcvars found by vswhere;
the runner's manifest records the Qt, PySide6 and MSVC a module was built with and refuses a module built for another
Qt or not checked; locally a download is published into release/native_module only when it is the requested commit's
whole, unaltered module for the pinned Qt; an unpushed commit is never built; the Build Runner job is never
pre-selected and no installer depends on it."""
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


# ------------------------------------------------------------------------------- the download, validated (local)


def _artifact(root: Path, into: Path, *, pyside6: str = sdk.QT_VERSION) -> Path:
    """The runner side end to end (stage, manifest), then the upload layout the workflow produces."""
    remote.stage_native_module(root, runner_build(root))
    manifest = remote.build_manifest(root, "native_module", _git(root, "rev-parse", "HEAD"), TOKEN,
                                     run_id="7", run_attempt="1", pyside6_version=pyside6)
    into.mkdir(parents=True)
    (into / remote.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    shutil.copytree(root / "release", into / "release")
    shutil.copytree(root / "logs", into / "logs")
    return into


def _validate(staging: Path, root: Path, **overrides):
    expected = {"commit": _git(root, "rev-parse", "HEAD"), "version": "9.8.7", "token": TOKEN, **overrides}
    return remote.validate_staging(staging, "native_module", **expected)


def test_a_whole_module_build_of_the_requested_commit_validates(tmp_path):
    root = _repo(tmp_path)
    staging = _artifact(root, tmp_path / "staging")
    manifest = _validate(staging, root)
    assert f"release/{NATIVE.primary}" in manifest["files"] and manifest["qt_version"] == NATIVE.module_qt


def _edit_manifest(staging: Path, change) -> None:
    path = staging / remote.MANIFEST_NAME
    manifest = json.loads(path.read_text(encoding="utf-8"))
    change(manifest)
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _tamper(staging: Path, case: str) -> None:
    payload = staging / "release" / NATIVE.payload_dirs[0]
    module = staging / "release" / NATIVE.primary
    if case == "pyd-bytes":
        module.write_bytes(b"MZ modulf")                                       # same size, other bytes
    elif case == "missing-pyd":
        module.unlink()
    elif case == "unlisted-pyd":                                             # removed from the manifest as well
        module.unlink()
        _edit_manifest(staging, lambda m: m["files"].pop(f"release/{NATIVE.primary}"))
    elif case == "no-shaders":
        shutil.rmtree(payload / remote.SHADERS_DIR)
        _edit_manifest(staging, lambda m: [m["files"].pop(name) for name in list(m["files"]) if name.endswith(".qsb")])
    elif case == "planted-dll":
        (payload / "Qt6Gui.dll").write_bytes(b"x")
    elif case == "qt-version":
        _edit_manifest(staging, lambda m: m.update(qt_version="6.11.1"))
    elif case == "pyside6-version":
        _edit_manifest(staging, lambda m: m.update(pyside6_version="6.12.0"))
    elif case == "no-msvc":
        _edit_manifest(staging, lambda m: m.pop("msvc_version"))
    elif case == "escape":
        _edit_manifest(staging, lambda m: m["files"].update(
            {"release/native_module/../screensaver/SRPSS.scr": {"bytes": 1, "sha256": "0"}}))


@pytest.mark.parametrize("case", ["pyd-bytes", "missing-pyd", "unlisted-pyd", "no-shaders", "planted-dll",
                                  "qt-version", "pyside6-version", "no-msvc", "escape"])
def test_an_altered_or_incomplete_module_download_is_refused(tmp_path, case):
    root = _repo(tmp_path)
    staging = _artifact(root, tmp_path / "staging")
    _tamper(staging, case)
    with pytest.raises(remote.RemoteBuildError):
        _validate(staging, root)


@pytest.mark.parametrize("field,value", [("commit", "f" * 40), ("version", "9.8.8"),
                                         ("token", "20261112_120000_000002")])
def test_a_module_of_another_commit_version_or_run_is_refused(tmp_path, field, value):
    root = _repo(tmp_path)
    staging = _artifact(root, tmp_path / "staging")
    with pytest.raises(remote.RemoteBuildError, match=field):
        _validate(staging, root, **{field: value})


# ---------------------------------------------------------------------------- dispatch, follow, publish (local)


def test_the_module_dispatches_its_own_workflow_with_only_its_inputs():
    calls = []

    def run(args, _timeout):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0, "[]", "")

    cli = remote.GitHubCli(run=run)
    sha = "c" * 40
    cli.dispatch("native_module", "work/branch", sha, TOKEN)
    cli.dispatch("standard", "main", sha, TOKEN)
    assert calls[0] == ["gh", "workflow", "run", remote.NATIVE_WORKFLOW_FILE, "--ref", "work/branch",
                        "-f", f"commit={sha}", "-f", f"token={TOKEN}"]
    assert calls[1] == ["gh", "workflow", "run", remote.WORKFLOW_FILE, "--ref", "main",
                        "-f", "target=standard", "-f", f"commit={sha}", "-f", f"token={TOKEN}"]
    cli.find_run(f"native_module-{TOKEN}", workflow=NATIVE.workflow)
    cli.startup_failure(remote.datetime.now(remote.timezone.utc), sha, workflow=NATIVE.workflow)
    assert all(call[call.index("--workflow") + 1] == remote.NATIVE_WORKFLOW_FILE for call in calls[2:])


def _orchestrate(tmp_path, monkeypatch, cli, *, local_head: str | None = None, release: Path | None = None):
    root = tmp_path / "repo"
    sha = _git(root, "rev-parse", "HEAD")
    monkeypatch.setattr(remote, "resolve_pushed_commit", lambda *_a, **_k: remote.PushedCommit(
        "work", sha, "x", local_head or sha))
    release = release or tmp_path / "release"
    results = remote.run_remote_builds(
        root, cli, ["native_module"], remote.PushedCommit("work", sha, "fixture", sha), TOKEN,
        log_dir=tmp_path / "logs", release_dir=release, cancelled=lambda: False,
        emit=lambda *_event: None, poll_seconds=0.0, sleep=lambda _s: None,
    )
    return results["native_module"], release


def test_a_validated_module_is_published_into_release_with_its_manifest(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    artifact = _artifact(root, tmp_path / "artifact")
    shutil.rmtree(root / "release")                         # the runner's staging; the local tree is separate
    release = tmp_path / "release"
    (release / "native_module").mkdir(parents=True)
    (release / "native_module" / "previous.pyd").write_bytes(b"old")
    (release / "screensaver").mkdir()
    (release / "screensaver" / "SRPSS.scr").write_bytes(b"product")
    cli = FakeCli({"native_module": artifact}, {"native_module": [RUNNING, SUCCESS]})
    result, release = _orchestrate(tmp_path, monkeypatch, cli, release=release)
    assert result.ok, result.detail
    assert [entry[0] for entry in cli.dispatched] == ["native_module"]
    assert {workflow for _request, workflow in cli.lookups} == {remote.NATIVE_WORKFLOW_FILE}
    published = release / "native_module"
    assert (published / Path(NATIVE.primary).name).read_bytes() == b"MZ module"
    assert sorted(path.name for path in (published / remote.SHADERS_DIR).iterdir()) == [
        "quadfield.frag.qsb", "quadfield.vert.qsb"]
    assert not (published / "previous.pyd").exists()
    kept = json.loads((published / remote.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert kept["commit"] == _git(root, "rev-parse", "HEAD") and kept["qt_version"] == NATIVE.module_qt
    assert (release / "screensaver" / "SRPSS.scr").read_bytes() == b"product"     # the products are untouched
    assert result.output_path == published
    for name in NATIVE.report_names(TOKEN):
        assert (tmp_path / "logs" / name).is_file()


def test_an_invalid_module_download_keeps_the_previous_module(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    artifact = _artifact(root, tmp_path / "artifact")
    _tamper(artifact, "qt-version")
    release = tmp_path / "release"
    (release / "native_module").mkdir(parents=True)
    (release / "native_module" / "previous.pyd").write_bytes(b"old")
    cli = FakeCli({"native_module": artifact}, {"native_module": [SUCCESS]})
    result, release = _orchestrate(tmp_path, monkeypatch, cli, release=release)
    assert not result.ok and "qt_version" in result.detail
    assert sorted(path.name for path in (release / "native_module").iterdir()) == ["previous.pyd"]


def test_an_unpushed_commit_is_never_built(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    artifact = _artifact(root, tmp_path / "artifact")
    cli = FakeCli({"native_module": artifact}, {"native_module": [SUCCESS]})
    result, release = _orchestrate(tmp_path, monkeypatch, cli, local_head="a" * 40)
    assert not result.ok and "push it first" in result.detail
    assert cli.dispatched == [] and not (release / "native_module").exists()


# ------------------------------------------------------------------------------------------- Build Runner's tab


def test_the_github_tab_offers_the_module_unselected_and_publishing_into_release(tmp_path):
    github = {job.key: job for job in build_runner.jobs_for_mode("github", tmp_path)}
    venv = {job.key for job in build_runner.jobs_for_mode("venv", tmp_path)}
    job = github["native_module"]
    assert job.kind == "github" and not job.default_selected and "native_module" not in venv
    assert job.script == tmp_path / remote.NATIVE_WORKFLOW_PATH and (ROOT / remote.NATIVE_WORKFLOW_PATH).is_file()
    assert job.output_dir == tmp_path / "release" / NATIVE.payload_dirs[0]
    assert job.artifacts == (tmp_path / "release" / NATIVE.primary,)


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


def test_the_headless_run_selects_the_module_only_when_asked(monkeypatch):
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
    assert "native_module" not in seen[0] and seen[1] == {"native_module"}


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


def test_preflight_makes_only_the_module_unavailable_for_an_unpushed_head_or_an_unlisted_workflow(monkeypatch):
    pushed = remote.PushedCommit("work", "d" * 40, "s", "d" * 40)
    assert "native_module" not in _preflight_with(monkeypatch, pushed).unavailable_jobs
    for result in (_preflight_with(monkeypatch, replace_head(pushed, "a" * 40)),
                   _preflight_with(monkeypatch, pushed, registered=False)):
        assert "native_module" in result.unavailable_jobs and not result.errors
        assert not {"standard", "media_center"} & result.unavailable_jobs
        assert any(warning.startswith("Native Module:") for warning in result.warnings)


def replace_head(commit: remote.PushedCommit, head: str) -> remote.PushedCommit:
    return remote.PushedCommit(commit.branch, commit.sha, commit.subject, head)
