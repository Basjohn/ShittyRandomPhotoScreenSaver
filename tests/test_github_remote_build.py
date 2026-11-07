"""Build Runner's GitHub Remote builds (tools/github_remote_build.py, .github/workflows/windows-build.yml).

Nothing here builds, dispatches or contacts GitHub: the GitHub CLI is a recorded fake, git runs on throwaway
repositories, and the release tree is a temporary directory. The contracts proven: the workflow builds exactly the
requested commit with the canonical workers; a download is published only when it is the requested commit's whole,
unaltered build; any failure keeps the previous payload; a stop cancels the real runs; installers package only
validated builds whose repository inputs equal the built commit."""
from __future__ import annotations

import json
import queue
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import build_runner
from tools import github_remote_build as remote

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "20261108_120000_000001"


# ------------------------------------------------------------------------------------------------- the workflow


def _workflow() -> str:
    return (ROOT / remote.WORKFLOW_PATH).read_text(encoding="utf-8")


def test_the_workflow_builds_only_the_requested_commit_with_the_canonical_workers():
    text = _workflow()
    triggers = text.split("\non:", 1)[1].split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in triggers and "push:" not in triggers and "pull_request" not in triggers
    for name in ("target", "commit", "token"):
        assert re.search(rf"^      {name}:\n", triggers, re.MULTILINE), name
    assert "ref: ${{ inputs.commit }}" in text and "git rev-parse HEAD" in text     # checked out, then verified
    for script in ("scripts/venv/build_nuitka.ps1", "scripts/venv/build_nuitka_mc_onedir.ps1"):
        assert script in text and (ROOT / script).is_file()
    assert "tools\\github_remote_build.py manifest" in text and remote.MANIFEST_NAME in text
    assert "name: srpss-${{ inputs.target }}\n" in text
    assert {f"srpss-{key}" for key in remote.TARGETS} == {target.artifact for target in remote.TARGETS.values()}
    assert re.search(r"options:\n((?:\s+- \w+\n)+)", triggers).group(1).split() == ["-", "standard", "-", "media_center"]
    assert "runs-on: windows" in text and "python-version: \"3.14\"" in text
    assert "ISCC" not in text                                                       # installers stay local


def test_the_workflow_never_interpolates_inputs_into_scripts():
    # Inputs reach scripts only through the environment (no script injection through a crafted input).
    blocks = re.findall(r"run: \|\n((?:\s{10,}.*\n)+)", _workflow())
    assert blocks and not any("${{" in block for block in blocks)


# ------------------------------------------------------------------------------------------- git repositories


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def _repo(tmp_path: Path, version: str = "9.8.7") -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "core.autocrlf", "false")
    (root / "versioning.py").write_text(f'APP_VERSION: str = "{version}"\n', encoding="utf-8")
    (root / "scripts").mkdir()
    (root / "scripts" / "SRPSS_MediaCenter_Installer.iss").write_text(
        "[Setup]\nAppVersion=1.0\nVersionInfoVersion=1.0\nAppName=x\n", encoding="utf-8")
    (root / "themes").mkdir()
    (root / "themes" / "a.srtheme").write_text("{}", encoding="utf-8")
    (root / ".gitignore").write_text("release/\nlogs/\nbuild/\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture")
    return root


def _publish_built(root: Path, target_key: str, *, payload: bytes = b"binary") -> None:
    target = remote.TARGETS[target_key]
    for relative in target.artifacts:
        path = root / "release" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    extra = root / "release" / target.payload_dirs[0] / "lib" / "data.bin"
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_bytes(b"payload-data")
    (root / "logs").mkdir(exist_ok=True)
    stem = "build_nuitka" if target_key == "standard" else "build_nuitka_mc_onedir"
    (root / "logs" / f"{stem}_{TOKEN}.log").write_text("built", encoding="utf-8")


def _artifact(root: Path, target_key: str, into: Path) -> Path:
    """The runner side: manifest + upload layout, as the workflow produces them."""
    commit = _git(root, "rev-parse", "HEAD")
    manifest = remote.build_manifest(root, target_key, commit, TOKEN, run_id="1", run_attempt="1")
    into.mkdir(parents=True)
    (into / remote.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    shutil.copytree(root / "release", into / "release")
    shutil.copytree(root / "logs", into / "logs")
    return into


# ------------------------------------------------------------------------------------------ manifest + validation


@pytest.mark.parametrize("target_key", sorted(remote.TARGETS))
def test_a_whole_unaltered_build_of_the_requested_commit_validates(tmp_path, target_key):
    root = _repo(tmp_path)
    _publish_built(root, target_key)
    staging = _artifact(root, target_key, tmp_path / "staging")
    commit = _git(root, "rev-parse", "HEAD")
    manifest = remote.validate_staging(staging, target_key, commit=commit, version="9.8.7", token=TOKEN)
    assert any(name.startswith("logs/") for name in manifest["files"])          # reports travel with the payload
    assert all(f"release/{relative}" in manifest["files"] for relative in remote.TARGETS[target_key].artifacts)


def _tamper(staging: Path, case: str) -> dict:
    manifest_path = staging / remote.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if case == "byte":
        (staging / "release" / "screensaver" / "lib" / "data.bin").write_bytes(b"payload-dat4")
    elif case == "missing":
        (staging / "release" / "screensaver" / "lib" / "data.bin").unlink()
    elif case == "extra":
        (staging / "release" / "screensaver" / "planted.dll").write_bytes(b"x")
    elif case == "escape":
        manifest["files"]["release/screensaver/../../outside.txt"] = {"bytes": 1, "sha256": "0"}
    elif case == "diagnostic":
        (staging / "release" / "diagnostic" / "SRPSS_Diagnostic.scr").write_bytes(b"other!")
        entry = manifest["files"]["release/diagnostic/SRPSS_Diagnostic.scr"]
        entry["sha256"] = remote.sha256_file(staging / "release" / "diagnostic" / "SRPSS_Diagnostic.scr")
    elif case == "no-manifest":
        manifest_path.unlink()
        return {}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


@pytest.mark.parametrize("case", ["byte", "missing", "extra", "escape", "diagnostic", "no-manifest"])
def test_an_altered_or_incomplete_download_is_refused(tmp_path, case):
    root = _repo(tmp_path)
    _publish_built(root, "standard")
    staging = _artifact(root, "standard", tmp_path / "staging")
    _tamper(staging, case)
    with pytest.raises(remote.RemoteBuildError):
        remote.validate_staging(staging, "standard", commit=_git(root, "rev-parse", "HEAD"), version="9.8.7",
                                token=TOKEN)


@pytest.mark.parametrize("field,value", [("commit", "f" * 40), ("version", "9.8.8"), ("token", "20261108_120000_000002")])
def test_a_build_of_another_commit_version_or_run_is_refused(tmp_path, field, value):
    root = _repo(tmp_path)
    _publish_built(root, "standard")
    staging = _artifact(root, "standard", tmp_path / "staging")
    expected = {"commit": _git(root, "rev-parse", "HEAD"), "version": "9.8.7", "token": TOKEN, field: value}
    with pytest.raises(remote.RemoteBuildError, match=field):
        remote.validate_staging(staging, "standard", **expected)


def test_the_runner_refuses_to_describe_a_commit_it_did_not_build(tmp_path):
    root = _repo(tmp_path)
    _publish_built(root, "standard")
    with pytest.raises(remote.RemoteBuildError, match="requested"):
        remote.build_manifest(root, "standard", "a" * 40, TOKEN)


def test_version_comes_from_the_built_commit_not_the_working_tree(tmp_path):
    root = _repo(tmp_path, version="1.2.3")
    sha = _git(root, "rev-parse", "HEAD")
    (root / "versioning.py").write_text('APP_VERSION: str = "4.5.6"\n', encoding="utf-8")
    assert remote.version_at_commit(root, sha) == "1.2.3"
    assert remote._same_version("1.2.3.0", "1.2.3") and not remote._same_version("1.2.4.0", "1.2.3")


# --------------------------------------------------------------------------------------------------- publishing


def _release_with_previous(tmp_path: Path) -> Path:
    release = tmp_path / "release"
    for directory in ("screensaver", "diagnostic"):
        (release / directory).mkdir(parents=True)
        (release / directory / "previous.txt").write_text(directory, encoding="utf-8")
    return release


def test_publishing_swaps_in_the_validated_payload(tmp_path):
    root = _repo(tmp_path)
    _publish_built(root, "standard", payload=b"new")
    staging = _artifact(root, "standard", tmp_path / "staging")
    release = _release_with_previous(tmp_path)
    remote.publish_payload(staging, release, "standard")
    assert (release / "screensaver" / "SRPSS.scr").read_bytes() == b"new"
    assert not (release / "screensaver" / "previous.txt").exists()
    assert not list(release.glob(".remote_previous_*"))


def test_a_failed_swap_restores_the_previous_payload(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    _publish_built(root, "standard", payload=b"new")
    staging = _artifact(root, "standard", tmp_path / "staging")
    release = _release_with_previous(tmp_path)
    real_move = shutil.move

    def move(source, destination):
        if Path(destination).name == "diagnostic":
            raise PermissionError("SRPSS_Diagnostic.scr is in use")
        return real_move(source, destination)

    monkeypatch.setattr(remote.shutil, "move", move)
    with pytest.raises(remote.RemoteBuildError, match="previous payload was kept"):
        remote.publish_payload(staging, release, "standard")
    monkeypatch.setattr(remote.shutil, "move", real_move)
    for directory in ("screensaver", "diagnostic"):
        assert sorted(path.name for path in (release / directory).iterdir()) == ["previous.txt"]
    assert not list(release.glob(".remote_previous_*"))


# --------------------------------------------------------------------------------------- installer input checks


def test_installer_inputs_must_equal_the_built_commit(tmp_path):
    root = _repo(tmp_path)
    sha = _git(root, "rev-parse", "HEAD")
    inputs = ("scripts/SRPSS_MediaCenter_Installer.iss", "themes", "versioning.py")
    assert remote.installer_input_mismatches(root, sha, inputs) == ()
    iss = root / "scripts" / "SRPSS_MediaCenter_Installer.iss"
    iss.write_text(iss.read_text(encoding="utf-8").replace("=1.0", "=9.8.7"), encoding="utf-8")
    assert remote.installer_input_mismatches(root, sha, inputs) == ()           # Build Runner's version stamp only
    (root / "themes" / "a.srtheme").write_text('{"changed": 1}', encoding="utf-8")
    (root / "themes" / "new.srtheme").write_text("{}", encoding="utf-8")
    iss.write_text(iss.read_text(encoding="utf-8") + "OutputDir=x\n", encoding="utf-8")
    assert remote.installer_input_mismatches(root, sha, inputs) == (
        "scripts/SRPSS_MediaCenter_Installer.iss", "themes/a.srtheme", "themes/new.srtheme",
    )


# ----------------------------------------------------------------------------------------- remote orchestration


class FakeCli:
    """The GitHub CLI, recorded: each product's run reports the given states, then its artifact downloads."""

    def __init__(self, artifacts: dict[str, Path], states: dict[str, list[remote.RunState]], *, appear=True,
                 refused=None):
        self.artifacts, self.states, self.appear, self.refused = artifacts, states, appear, refused
        self.dispatched, self.cancelled, self.downloads = [], [], []
        self.ids = {}

    def dispatch(self, key, branch, sha, token):
        self.dispatched.append((key, branch, sha, token))
        self.ids[f"{key}-{token}"] = 100 + len(self.ids)

    def find_run(self, request_id, *, after_stop=False):
        if not self.appear and not after_stop:
            return None
        run_id = self.ids.get(request_id)
        return None if run_id is None else (run_id, f"https://github.invalid/runs/{run_id}")

    def startup_failure(self, since, sha):
        return self.refused

    def _key(self, run_id):
        return next(request.split("-")[0] for request, value in self.ids.items() if value == run_id)

    def run_state(self, run_id):
        states = self.states[self._key(run_id)]
        return states.pop(0) if len(states) > 1 else states[0]

    def failed_log(self, run_id):
        return "error C2065: undeclared identifier"

    def download(self, run_id, artifact, destination):
        key = self._key(run_id)
        self.downloads.append(key)
        shutil.copytree(self.artifacts[key], destination, dirs_exist_ok=True)

    def cancel(self, run_id):
        self.cancelled.append(run_id)
        return True


RUNNING = remote.RunState("in_progress", "", "u", "Build with the canonical worker")
SUCCESS = remote.RunState("completed", "success", "u")
FAILURE = remote.RunState("completed", "failure", "u")


def _orchestrate(tmp_path, monkeypatch, cli, keys, *, cancelled=lambda: False, moved=False, between=None):
    root = tmp_path / "repo"
    sha = _git(root, "rev-parse", "HEAD")
    commit = remote.PushedCommit("main", sha, "fixture", sha)
    monkeypatch.setattr(remote, "resolve_pushed_commit", lambda *_a, **_k: remote.PushedCommit(
        "main", "e" * 40 if moved else sha, "x", sha))
    events = []
    release = _release_with_previous(tmp_path)
    results = remote.run_remote_builds(
        root, cli, keys, commit, TOKEN, log_dir=tmp_path / "logs", release_dir=release, cancelled=cancelled,
        emit=lambda kind, key, payload: events.append((kind, key, payload)), between=between,
        poll_seconds=0.0, sleep=lambda _s: None,
    )
    return results, events, release


def _artifacts(tmp_path: Path) -> dict[str, Path]:
    root = _repo(tmp_path)
    artifacts = {}
    for key in remote.TARGETS:
        _publish_built(root, key, payload=f"{key}-new".encode())
        artifacts[key] = _artifact(root, key, tmp_path / f"artifact_{key}")
    return artifacts


def test_both_products_build_in_parallel_and_publish_after_validation(tmp_path, monkeypatch):
    artifacts = _artifacts(tmp_path)
    cli = FakeCli(artifacts, {"standard": [RUNNING, SUCCESS], "media_center": [RUNNING, RUNNING, SUCCESS]})
    order = []
    results, events, release = _orchestrate(
        tmp_path, monkeypatch, cli, ["standard", "media_center"],
        between=lambda: order.append(("between", list(cli.downloads))),
    )
    assert [key for key, *_ in cli.dispatched] == ["standard", "media_center"]       # both dispatched up front
    assert {sha for *_, sha, _token in cli.dispatched} == {_git(tmp_path / "repo", "rev-parse", "HEAD")}
    assert order == [("between", [])]                     # local work runs while GitHub builds, before downloads
    assert all(result.ok for result in results.values())
    assert (release / "screensaver" / "SRPSS.scr").read_bytes() == b"standard-new"
    assert (release / "media_center" / "SRPSS_Media_Center.exe").read_bytes() == b"media_center-new"
    assert all(results[key].evidence_path is not None for key in results)
    assert ("link", "standard", "https://github.invalid/runs/100") in events
    assert any(kind == "status" and payload.startswith("Building") for kind, _key, payload in events)
    assert not (tmp_path / "repo" / remote.STAGING_DIR / TOKEN).exists()             # staging cleaned up


def test_a_failed_run_keeps_the_previous_payload_and_logs_the_failure(tmp_path, monkeypatch):
    artifacts = _artifacts(tmp_path)
    cli = FakeCli(artifacts, {"standard": [RUNNING, FAILURE]})
    results, _events, release = _orchestrate(tmp_path, monkeypatch, cli, ["standard"])
    assert not results["standard"].ok and cli.downloads == []
    assert (release / "screensaver" / "previous.txt").is_file()
    assert "C2065" in results["standard"].log_path.read_text(encoding="utf-8")


def test_an_invalid_download_keeps_the_previous_payload(tmp_path, monkeypatch):
    artifacts = _artifacts(tmp_path)
    _tamper(artifacts["standard"], "byte")
    cli = FakeCli(artifacts, {"standard": [SUCCESS]})
    results, _events, release = _orchestrate(tmp_path, monkeypatch, cli, ["standard"])
    assert not results["standard"].ok and "integrity" in results["standard"].detail
    assert sorted(path.name for path in (release / "screensaver").iterdir()) == ["previous.txt"]


def test_a_stop_cancels_the_real_runs_on_github(tmp_path, monkeypatch):
    artifacts = _artifacts(tmp_path)
    cli = FakeCli(artifacts, {"standard": [RUNNING], "media_center": [RUNNING]})
    polls = {"count": 0}

    def cancelled():
        polls["count"] += 1
        return polls["count"] > 6

    results, _events, release = _orchestrate(tmp_path, monkeypatch, cli, ["standard", "media_center"],
                                              cancelled=cancelled)
    assert sorted(cli.cancelled) == [100, 101]
    assert all(result.aborted and result.returncode == 130 for result in results.values())
    assert (release / "screensaver" / "previous.txt").is_file()


def test_a_run_seen_only_after_the_stop_is_still_cancelled(tmp_path, monkeypatch):
    artifacts = _artifacts(tmp_path)
    cli = FakeCli(artifacts, {"standard": [RUNNING]}, appear=False)
    flag = {"stop": False}

    def cancelled():
        if cli.dispatched:
            flag["stop"] = True
        return flag["stop"]

    results, _events, _release = _orchestrate(tmp_path, monkeypatch, cli, ["standard"], cancelled=cancelled)
    assert cli.cancelled == [100] and results["standard"].aborted


def test_a_run_github_refuses_to_start_is_reported_not_waited_for(tmp_path, monkeypatch):
    # A refused run never gets its custom name (8 Nov: the repository allowed only local actions).
    artifacts = _artifacts(tmp_path)
    cli = FakeCli(artifacts, {"standard": [RUNNING]}, appear=False, refused="https://github.invalid/runs/9")
    results, _events, release = _orchestrate(tmp_path, monkeypatch, cli, ["standard"])
    assert not results["standard"].ok and "could not start the workflow" in results["standard"].detail
    assert results["standard"].run_url == "https://github.invalid/runs/9"
    assert (release / "screensaver" / "previous.txt").is_file()


def test_a_branch_that_moved_since_pre_flight_is_never_built(tmp_path, monkeypatch):
    artifacts = _artifacts(tmp_path)
    cli = FakeCli(artifacts, {"standard": [SUCCESS]})
    results, _events, _release = _orchestrate(tmp_path, monkeypatch, cli, ["standard"], moved=True)
    assert cli.dispatched == [] and "moved since pre-flight" in results["standard"].detail


# ------------------------------------------------------------------------------------------- Build Runner tab


def test_the_github_tab_offers_the_remote_products_and_local_steps(tmp_path):
    github = {job.key: job for job in build_runner.jobs_for_mode("github", tmp_path)}
    venv = {job.key: job for job in build_runner.jobs_for_mode("venv", tmp_path)}
    assert list(github) == ["standard", "media_center", "reddit_helper", "standard_installer", "media_center_installer"]
    for key in ("standard", "media_center"):
        assert github[key].kind == "github" and github[key].script == tmp_path / remote.WORKFLOW_PATH
        assert github[key].artifacts == venv[key].artifacts and github[key].output_dir == venv[key].output_dir
        assert remote.TARGETS[key].artifacts == tuple(
            path.relative_to(tmp_path / "release").as_posix() for path in github[key].artifacts)
    assert github["reddit_helper"].script == venv["reddit_helper"].script          # built locally, venv worker
    assert not github["standard_installer"].default_selected and not github["media_center_installer"].default_selected
    assert build_runner.normalize_mode("GitHub") == "github" and build_runner.normalize_mode("x") == "normal"
    assert build_runner.parse_args(["--mode", "github"]).mode == "github"
    # The other tabs are untouched.
    assert [job.kind for job in venv.values()] == ["powershell", "powershell", "powershell", "inno", "inno", "powershell"]


def test_the_github_tab_shares_the_venv_helper_record(tmp_path):
    from tests.test_build_runner import _make_helper_inputs
    _make_helper_inputs(tmp_path, "venv")
    assert build_runner.helper_fingerprint("github", tmp_path) == build_runner.helper_fingerprint("venv", tmp_path)


def _ok(key):
    return remote.RemoteResult(key, 0, "Completed", Path("log"), Path("out"))


def test_installers_package_only_validated_builds_of_matching_inputs(monkeypatch):
    commit = remote.PushedCommit("main", "c" * 40, "x", "c" * 40)
    mismatches = {"value": ()}
    monkeypatch.setattr(remote, "installer_input_mismatches", lambda *_a: mismatches["value"])
    helper = {"stale": False}
    monkeypatch.setattr(build_runner, "helper_build_status", lambda *_a, **_k: SimpleNamespace(
        needs_rebuild=helper["stale"], reason="Helper inputs changed"))
    refusal = build_runner.github_installer_refusal
    assert "not part of this run" in refusal("standard_installer", {}, commit)
    failed = remote.RemoteResult("standard", 1, "x", Path("l"), Path("o"))
    assert "did not complete" in refusal("standard_installer", {"standard": failed}, commit)
    assert refusal("media_center_installer", {"media_center": _ok("media_center")}, commit) is None
    mismatches["value"] = ("themes/a.srtheme",)
    assert "themes/a.srtheme" in refusal("media_center_installer", {"media_center": _ok("media_center")}, commit)
    mismatches["value"] = ()
    helper["stale"] = True
    assert "Reddit Helper" in refusal("standard_installer", {"standard": _ok("standard")}, commit)
    assert refusal("media_center_installer", {"media_center": _ok("media_center")}, commit) is None


def test_the_pipeline_runs_the_helper_while_github_builds_and_installers_after(monkeypatch, tmp_path):
    jobs = build_runner.jobs_for_mode("github", tmp_path)
    selected = {"standard", "media_center", "reddit_helper", "media_center_installer"}
    order = []

    def run_remote(_root, _cli, keys, _commit, _token, *, emit, between, **_kwargs):
        order.append(("dispatch", tuple(keys)))
        between()
        results = {"standard": remote.RemoteResult("standard", 1, "failed", Path("l"), Path("o")),
                   "media_center": _ok("media_center")}
        for key in keys:
            emit("done", key, results[key])
        return results

    def run_job(job, _preflight, *, process_owner):
        order.append(("local", job.key))
        return build_runner.JobResult(0, "Completed", Path("log"), job.output_dir)

    monkeypatch.setattr(remote, "run_remote_builds", run_remote)
    monkeypatch.setattr(build_runner, "run_job", run_job)
    monkeypatch.setattr(build_runner, "record_helper_build", lambda *_a, **_k: True)
    monkeypatch.setattr(build_runner, "helper_build_status", lambda *_a, **_k: SimpleNamespace(
        needs_rebuild=False, reason="ok", fingerprint="f"))
    monkeypatch.setattr(build_runner, "github_installer_refusal", lambda key, results, _c, *_a: (
        None if results[{"standard_installer": "standard", "media_center_installer": "media_center"}[key]].ok
        else "not validated"))
    app = SimpleNamespace(_events=queue.Queue())
    owner = build_runner.BuildProcessOwner()
    preflight = build_runner.PreflightResult(remote_commit=remote.PushedCommit("main", "c" * 40, "x", "c" * 40))
    build_runner.BuildRunnerApp._github_pipeline_worker(app, jobs, selected, preflight, owner)
    events = []
    while not app._events.empty():
        events.append(app._events.get())
    assert order == [("dispatch", ("standard", "media_center")), ("local", "reddit_helper"),
                     ("local", "media_center_installer")]
    assert ("job_skipped", "standard_installer") in events
    done = {event[1]: event[2] for event in events if event[0] == "job_done"}
    assert set(done) == {"standard", "media_center", "reddit_helper", "media_center_installer"}
    assert events[-1][0] == "pipeline_done" and events[-1][1] is False               # the Standard build failed


def test_preflight_names_the_pushed_commit_and_warns_about_local_differences(monkeypatch):
    commit = remote.PushedCommit("main", "d" * 40, "subject", "a" * 40, (" M themes/x.srtheme",))
    monkeypatch.setattr(remote, "resolve_pushed_commit", lambda *_a, **_k: commit)
    monkeypatch.setattr(build_runner.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    monkeypatch.setattr(remote.GitHubCli, "signed_in", lambda self: False)
    result = build_runner.PreflightResult()
    jobs = build_runner.jobs_for_mode("github")
    build_runner._github_preflight(result, jobs, build_runner.REPO_ROOT)
    assert result.remote_commit is commit and result.notes == [f"GitHub builds {commit.describe()}"]
    assert any("gh auth login" in error for error in result.errors)
    assert {"standard", "media_center"} <= result.unavailable_jobs
    assert any("not origin/main" in warning for warning in result.warnings)
    assert any("uncommitted" in warning for warning in result.warnings)


@pytest.mark.parametrize("policy,selected,refused", [
    ({"enabled": True, "allowed_actions": "local_only"}, None, True),
    ({"enabled": True, "allowed_actions": "selected"}, {"github_owned_allowed": False}, True),
    ({"enabled": True, "allowed_actions": "selected"}, {"github_owned_allowed": True}, False),
    ({"enabled": True, "allowed_actions": "all"}, None, False),
    ({"enabled": False}, None, True),
])
def test_an_actions_policy_that_would_refuse_the_workflow_is_caught_before_dispatch(policy, selected, refused):
    def run(args, _timeout):
        body = selected if args[-1].endswith("selected-actions") else policy
        return subprocess.CompletedProcess(args, 0, json.dumps(body), "")

    problem = remote.GitHubCli(run=run).actions_policy_problem()
    assert (problem is not None) is refused


def test_preflight_reports_the_actions_policy(monkeypatch):
    monkeypatch.setattr(remote, "resolve_pushed_commit", lambda *_a, **_k: remote.PushedCommit(
        "main", "d" * 40, "s", "d" * 40))
    monkeypatch.setattr(build_runner.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    monkeypatch.setattr(remote.GitHubCli, "signed_in", lambda self: True)
    monkeypatch.setattr(remote.GitHubCli, "workflow_registered", lambda self: True)
    monkeypatch.setattr(remote.GitHubCli, "actions_policy_problem", lambda self: "only its own actions")
    result = build_runner.PreflightResult()
    build_runner._github_preflight(result, build_runner.jobs_for_mode("github"), build_runner.REPO_ROOT)
    assert any("only its own actions" in error for error in result.errors)
    assert {"standard", "media_center"} <= result.unavailable_jobs


def test_gh_calls_run_inside_the_cancellable_process_owner():
    owner = build_runner.BuildProcessOwner()
    owner.cancel()
    with pytest.raises(remote.RemoteCancelled):
        build_runner._owner_gh_runner(owner)(["gh", "--version"], 5.0)
