"""Offline recovery controls: late visibility never dispatches twice or bypasses publication validation."""
import json
import subprocess
from types import SimpleNamespace

import pytest

from tools import github_remote_build as remote
from tests.test_github_remote_build import (FakeCli, RUNNING, SUCCESS, TOKEN, _artifacts, _git,
                                          _release_with_previous)


class RecoveryCli(FakeCli):
    recover_run = remote.GitHubCli.recover_run

    def __init__(self, artifacts, sha, *, visible=True):
        super().__init__(artifacts, {"standard": [RUNNING, SUCCESS]})
        self.ids = {f"standard-{TOKEN}": 142}
        self.visible, self.lookups = visible, []
        self.identity = dict(id=142, path=f".github/workflows/{remote.WORKFLOW_FILE}", event="workflow_dispatch",
                             head_sha=sha, display_title=f"SRPSS standard (standard-{TOKEN})", html_url="url")

    def dispatch(self, *_):
        raise AssertionError("recovery must never dispatch")

    def find_run(self, *_a, **_k):
        raise AssertionError("recovery must not enter normal dispatch discovery")

    def _call(self, *args):
        self.lookups.append(args)
        if args[:2] == ("run", "list"):
            return json.dumps([dict(databaseId=142, displayTitle=self.identity["display_title"])] if self.visible else [])
        assert args[0] == "api"
        return json.dumps(self.identity)


def recover(tmp_path, monkeypatch, cli, release, *, run_id=None):
    root = tmp_path / "repo"
    sha = _git(root, "rev-parse", "HEAD")
    def no_preflight(*_a, **_k):
        raise AssertionError("explicit recovery must not fetch or resolve today's pushed tip")
    monkeypatch.setattr(remote, "resolve_pushed_commit", no_preflight)
    return remote.run_remote_builds(root, cli, ("standard",), remote.PushedCommit("", sha, "recover", "f" * 40),
                                    TOKEN, log_dir=tmp_path / "logs", release_dir=release, cancelled=lambda: False,
                                    emit=lambda *_: None, recover=True, recovery_run_id=run_id,
                                    poll_seconds=0, sleep=lambda _: None)


def test_late_visibility_reuses_original_run_and_appends_log(tmp_path, monkeypatch):
    artifacts = _artifacts(tmp_path)
    sha = _git(tmp_path / "repo", "rev-parse", "HEAD")
    cli = RecoveryCli(artifacts, sha, visible=False)
    release = _release_with_previous(tmp_path)
    logs = tmp_path / "logs"
    logs.mkdir()
    log = logs / f"build_runner_standard_{TOKEN}.log"
    log.write_text("original dispatch receipt\n", encoding="utf-8")
    pending = recover(tmp_path, monkeypatch, cli, release)["standard"]
    assert not pending.ok and "visibility pending" in pending.detail.lower()
    assert f"--commit {sha} --token {TOKEN}" in pending.detail
    assert len(cli.lookups) == 1 and not cli.downloads
    cli.visible = True
    completed = recover(tmp_path, monkeypatch, cli, release)["standard"]
    assert completed.ok and cli.downloads == ["standard"]
    assert log.read_text(encoding="utf-8").startswith("original dispatch receipt\n")
    assert (release / "screensaver/SRPSS.scr").read_bytes() == b"standard-new"
    assert not cli.dispatched


@pytest.mark.parametrize("field,value", (("id", 143), ("path", ".github/workflows/other.yml"),
                                        ("event", "push"), ("head_sha", "e" * 40),
                                        ("display_title", "different-target-token")))
def test_known_run_must_match_exact_identity_before_monitor_or_download(tmp_path, monkeypatch, field, value):
    artifacts = _artifacts(tmp_path)
    cli = RecoveryCli(artifacts, _git(tmp_path / "repo", "rev-parse", "HEAD"))
    cli.identity[field] = value
    result = recover(tmp_path, monkeypatch, cli, _release_with_previous(tmp_path), run_id=142)["standard"]
    assert not result.ok and "identity mismatch" in result.detail
    assert not cli.downloads and not cli.dispatched
    assert all(call[0] == "api" for call in cli.lookups)


@pytest.mark.parametrize("field,value", (("commit", "e" * 40), ("token", "20260101_000000_000001")))
def test_recovered_artifact_uses_canonical_commit_and_token_validation(tmp_path, monkeypatch, field, value):
    artifacts = _artifacts(tmp_path)
    path = artifacts["standard"] / remote.MANIFEST_NAME
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest[field] = value
    path.write_text(json.dumps(manifest), encoding="utf-8")
    cli = RecoveryCli(artifacts, _git(tmp_path / "repo", "rev-parse", "HEAD"))
    release = _release_with_previous(tmp_path)
    result = recover(tmp_path, monkeypatch, cli, release, run_id=142)["standard"]
    assert not result.ok and "Retrieval failed" in result.detail
    assert (release / "screensaver/previous.txt").read_text(encoding="utf-8") == "screensaver"
    assert not (release / "screensaver/SRPSS.scr").exists()
    assert cli.downloads == ["standard"] and not cli.dispatched


def test_recovery_does_not_accept_legacy_substring_identity():
    sha = "c" * 40
    listed = [dict(databaseId=142, displayTitle=f"unrelated (standard-{TOKEN}) suffix", url="url")]
    cli = remote.GitHubCli(run=lambda args, timeout: subprocess.CompletedProcess(args, 0, json.dumps(listed), ""))
    assert cli.find_run(f"standard-{TOKEN}") == (142, "url")  # observed legacy discovery accepts the substring
    assert cli.recover_run("standard", sha, TOKEN) is None


def test_recovery_rejects_ambiguous_exact_titles():
    title = f"SRPSS standard (standard-{TOKEN})"
    listed = [dict(databaseId=run_id, displayTitle=title) for run_id in (142, 143)]
    cli = remote.GitHubCli(run=lambda args, timeout: subprocess.CompletedProcess(args, 0, json.dumps(listed), ""))
    with pytest.raises(remote.RemoteBuildError, match="ambiguous"):
        cli.recover_run("standard", "c" * 40, TOKEN)


def test_native_recovery_requires_its_source_workflow_and_exact_title():
    sha, calls = "c" * 40, []
    target = remote.MODULE_TARGETS["native_module"]
    identity = dict(id=142, path=f".github/workflows/{target.workflow}", event="workflow_dispatch", head_sha=sha,
                    display_title=f"SRPSS native {target.source} ({target.key}-{TOKEN})", html_url="url")
    def run(args, timeout):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, json.dumps(identity), "")
    assert remote.GitHubCli(run=run).recover_run(target.key, sha, TOKEN, 142) == (142, "url")
    assert len(calls) == 1 and calls[0][1] == "api"


def test_recovery_cli_preserves_original_identity_without_new_preflight_or_token(monkeypatch, tmp_path):
    sha, calls = "c" * 40, []
    monkeypatch.setattr(remote, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(remote, "GitHubCli", lambda: SimpleNamespace(signed_in=lambda: True))
    monkeypatch.setattr(remote, "_git", lambda *_: "d" * 40)
    monkeypatch.setattr(remote.signal, "signal", lambda *_: None)
    def run(root, cli, keys, commit, token, **kwargs):
        calls.append((keys, commit.sha, token, kwargs["recover"], kwargs["recovery_run_id"]))
        return {"standard": SimpleNamespace(ok=True)}
    monkeypatch.setattr(remote, "run_remote_builds", run)
    assert remote.main(["recover", "--target", "standard", "--commit", sha, "--token", TOKEN, "--run-id", "142"]) == 0
    assert calls == [(("standard",), sha, TOKEN, True, 142)]
