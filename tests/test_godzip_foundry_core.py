from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import godzip_foundry_core as core  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "godzip-foundry@example.invalid")
    _git(repo, "config", "user.name", "GODZIP Foundry Tests")
    (repo / ".gitignore").write_text(
        "/.godzip_foundry/\n/deleteme/\n*.zip\n",
        encoding="utf-8",
    )
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    return repo


def test_repo_local_foundry_state_is_never_archive_payload(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    state = repo / ".godzip_foundry" / "settings.json"
    state.parent.mkdir()
    state.write_text('{"output_dir": "C:/example"}\n', encoding="utf-8")

    listed = {entry.path for entry in core.collect_repo_files(repo)}

    assert ".godzip_foundry/settings.json" not in listed
    with pytest.raises(core.GodzipError, match="Reserved path"):
        core.validate_repo_relpath(".godzip_foundry/settings.json")


def test_manifest_archive_records_dirty_source_and_never_implies_deletion(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    source_head = core.git_head(repo)
    (repo / "tracked.txt").write_text("archive version\n", encoding="utf-8")
    (repo / "new.txt").write_text("new file\n", encoding="utf-8")
    archive = tmp_path / "GODZIP_test.zip"

    manifest = core.create_godzip(repo, ["tracked.txt", "new.txt"], archive)
    inspection = core.inspect_godzip(repo, archive)

    assert manifest["source_head"] == source_head
    assert manifest["dirty_worktree"] is True
    assert manifest["omission_means_delete"] is False
    assert inspection.relation == "same"
    assert {entry.target_path for entry in inspection.files} == {"tracked.txt", "new.txt"}
    assert all(entry.sha256 for entry in inspection.files)


def test_proven_older_archive_requires_override_and_preserves_rollback_and_debris(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    (repo / "tracked.txt").write_text("archive version\n", encoding="utf-8")
    (repo / "new.txt").write_text("new from archive\n", encoding="utf-8")
    (repo / "obsolete.txt").write_text("move me\n", encoding="utf-8")
    archive = tmp_path / "GODZIP_test.zip"
    core.create_godzip(
        repo,
        ["tracked.txt", "new.txt"],
        archive,
        debris_entries=[{"path": "obsolete.txt", "reason": "obsolete fixture"}],
    )

    (repo / "tracked.txt").write_text("newer local version\n", encoding="utf-8")
    (repo / "advance.txt").write_text("advance HEAD\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt", "advance.txt")
    _git(repo, "commit", "-m", "advance")

    inspection = core.inspect_godzip(repo, archive)
    assert inspection.proven_older is True

    with pytest.raises(core.GodzipError, match="proven older"):
        core.apply_godzip(
            repo,
            inspection,
            ["tracked.txt", "new.txt"],
            selected_debris=["obsolete.txt"],
        )

    result = core.apply_godzip(
        repo,
        inspection,
        ["tracked.txt", "new.txt"],
        selected_debris=["obsolete.txt"],
        allow_proven_older=True,
    )

    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "archive version\n"
    assert (repo / "new.txt").read_text(encoding="utf-8") == "new from archive\n"
    assert not (repo / "obsolete.txt").exists()
    assert result.backup_dir is not None
    assert (result.backup_dir / "tracked.txt").read_text(encoding="utf-8") == "newer local version\n"
    assert result.debris_dir is not None
    assert (result.debris_dir / "obsolete.txt").read_text(encoding="utf-8") == "move me\n"


def test_legacy_zip_is_unknown_age_and_has_no_implicit_debris(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    archive = tmp_path / "legacy.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("tracked.txt", "legacy payload\n")

    inspection = core.inspect_godzip(repo, archive)

    assert inspection.legacy is True
    assert inspection.relation == "unknown"
    assert inspection.debris == []
    assert any("never infer deletion" in warning for warning in inspection.warnings)


def test_ui_persists_preferences_repo_locally_not_in_global_appdata() -> None:
    source = (TOOLS_DIR / "godzip_foundry.py").read_text(encoding="utf-8")

    assert '".godzip_foundry"' in source
    assert "QSettings" not in source
    assert "LOCALAPPDATA" not in source
    assert "AppData" not in source
    assert "SRPSSGodZIP.ico" in source
    assert "QTimer.singleShot(0, self.refresh)" not in source


def test_workflow_defaults_keep_docs_and_direct_tests_but_not_payload_trees() -> None:
    assert core.workflow_default_selected("Docs/Current_Plan.md") is True
    assert core.workflow_default_selected("docs/architecture.md") is True
    assert core.workflow_default_selected("tests/test_visualizer.py") is True
    assert core.workflow_default_selected("tests/fixtures/huge.bin") is False
    assert core.workflow_default_selected("tests/goldens/frame.png") is False
    assert core.workflow_default_selected("themes/settings/Dark.json") is False
    assert core.workflow_default_selected("images/wallpaper.jpg") is False
    assert core.workflow_default_selected("core/runtime.py") is True


def test_logzip_uses_direct_loose_logs_only_and_suffixes_duplicates(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    logs = repo / "logs"
    logs.mkdir()
    (logs / "one.log").write_text("one\n", encoding="utf-8")
    (logs / "two.txt").write_text("two\n", encoding="utf-8")
    (logs / "old.zip").write_bytes(b"existing")
    nested = logs / "tests"
    nested.mkdir()
    (nested / "ignored.log").write_text("nested\n", encoding="utf-8")

    first = core.create_logzip(repo)
    second = core.create_logzip(repo)

    short = core.git_head(repo)[:10]
    assert first.zip_path.name == f"logs{short}.zip"
    assert second.zip_path.name == f"logs{short}2.zip"
    assert set(first.files) == {"one.log", "two.txt"}
    with zipfile.ZipFile(first.zip_path) as archive:
        assert set(archive.namelist()) == {"one.log", "two.txt"}
    assert (logs / "one.log").exists()  # LOGZIP is non-destructive.


def _remote_pair(tmp_path: Path) -> tuple[Path, Path, Path]:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init")
    _git(seed, "config", "user.email", "godzip-foundry@example.invalid")
    _git(seed, "config", "user.name", "GODZIP Foundry Tests")
    (seed / "keep.txt").write_text("base\n", encoding="utf-8")
    (seed / "change.txt").write_text("base\n", encoding="utf-8")
    _git(seed, "add", ".")
    _git(seed, "commit", "-m", "base")
    _git(seed, "branch", "-M", "main")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-u", "origin", "main")
    subprocess.run(["git", "--git-dir", str(remote), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
    local = tmp_path / "local"
    subprocess.run(["git", "clone", str(remote), str(local)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _git(local, "config", "user.email", "godzip-foundry@example.invalid")
    _git(local, "config", "user.name", "GODZIP Foundry Tests")
    return remote, seed, local


def test_pull_inspection_full_ff_and_selective_sync_are_truthful(tmp_path: Path) -> None:
    _remote, seed, local = _remote_pair(tmp_path)
    (seed / "change.txt").write_text("remote one\n", encoding="utf-8")
    (seed / "new.txt").write_text("remote new\n", encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-m", "remote change")
    _git(seed, "push")

    inspection = core.inspect_pull(local, fetch=True)
    assert inspection.relation == "behind"
    assert {item.path for item in inspection.files} == {"change.txt", "new.txt"}
    assert inspection.fast_forward_possible is True

    # Dirty worktree blocks coherent full PULL, but selective sync remains available.
    (local / "keep.txt").write_text("local dirty\n", encoding="utf-8")
    dirty_inspection = core.inspect_pull(local, fetch=False)
    with pytest.raises(core.GodzipError, match="clean worktree"):
        core.git_pull_ff_only(local, dirty_inspection)

    result = core.selective_sync_from_remote(local, dirty_inspection, ["change.txt"])
    assert result.written == 1
    assert core.git_head(local) == dirty_inspection.local_head
    assert (local / "change.txt").read_text(encoding="utf-8") == "remote one\n"
    assert (local / "keep.txt").read_text(encoding="utf-8") == "local dirty\n"

    # Restore to a clean local clone and prove full ff-only advances HEAD.
    subprocess.run(["git", "-C", str(local), "reset", "--hard", "HEAD"], check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "-C", str(local), "clean", "-fd"], check=True, stdout=subprocess.PIPE)
    clean = core.inspect_pull(local, fetch=False)
    old = core.git_head(local)
    core.git_pull_ff_only(local, clean)
    assert core.git_head(local) != old
    assert core.git_head(local) == clean.remote_head
    assert (local / "new.txt").read_text(encoding="utf-8") == "remote new\n"


def test_selective_sync_backs_up_overwritten_local_target(tmp_path: Path) -> None:
    _remote, seed, local = _remote_pair(tmp_path)
    (seed / "change.txt").write_text("remote value\n", encoding="utf-8")
    _git(seed, "add", "change.txt")
    _git(seed, "commit", "-m", "remote value")
    _git(seed, "push")
    inspection = core.inspect_pull(local, fetch=True)

    (local / "change.txt").write_text("precious local edit\n", encoding="utf-8")
    inspection = core.inspect_pull(local, fetch=False)
    selected = next(item for item in inspection.files if item.path == "change.txt")
    assert selected.local_dirty is True

    result = core.selective_sync_from_remote(local, inspection, ["change.txt"])
    assert result.backup_dir is not None
    assert (result.backup_dir / "change.txt").read_text(encoding="utf-8") == "precious local edit\n"
    assert (local / "change.txt").read_text(encoding="utf-8") == "remote value\n"


def test_commit_all_stages_untracked_modified_and_deleted(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "tracked.txt").write_text("modified\n", encoding="utf-8")
    (repo / "new.txt").write_text("new\n", encoding="utf-8")
    head = core.git_commit_all(repo, "foundry commit")
    assert head == core.git_head(repo)
    assert core.git_changes(repo) == []
    assert _git(repo, "log", "-1", "--pretty=%s") == "foundry commit"


def test_selective_sync_handles_remote_delete_reversibly(tmp_path: Path) -> None:
    _remote, seed, local = _remote_pair(tmp_path)
    (seed / "change.txt").unlink()
    _git(seed, "add", "-A")
    _git(seed, "commit", "-m", "remote delete")
    _git(seed, "push")
    inspection = core.inspect_pull(local, fetch=True)
    deleted = next(item for item in inspection.files if item.path == "change.txt")
    assert deleted.status.startswith("D")

    result = core.selective_sync_from_remote(local, inspection, ["change.txt"])
    assert not (local / "change.txt").exists()
    assert result.backup_dir is not None
    assert (result.backup_dir / "change.txt").read_text(encoding="utf-8") == "base\n"


def test_commit_then_push_updates_upstream_without_force(tmp_path: Path) -> None:
    _remote, _seed, local = _remote_pair(tmp_path)
    before = _git(local, "rev-parse", "origin/main")
    (local / "local.txt").write_text("from local\n", encoding="utf-8")
    committed = core.git_commit_all(local, "local push")
    assert committed != before
    core.git_push_current(local)
    _git(local, "fetch", "origin")
    assert _git(local, "rev-parse", "origin/main") == committed
