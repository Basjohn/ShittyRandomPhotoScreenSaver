from __future__ import annotations

import os
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


def test_older_baseline_with_unrelated_new_commit_is_compatible_and_not_blocked(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "tracked.txt").write_text("archive version\n", encoding="utf-8")
    archive = tmp_path / "GODZIP_test.zip"
    core.create_godzip(repo, ["tracked.txt"], archive)

    # Advance HEAD in an unrelated path. The archive bytes are not made stale by this.
    (repo / "unrelated.txt").write_text("newer commit\n", encoding="utf-8")
    _git(repo, "add", "unrelated.txt")
    _git(repo, "commit", "-m", "unrelated advance")

    inspection = core.inspect_godzip(repo, archive)
    assert inspection.baseline_relation == "older"
    assert inspection.relation == "compatible"
    assert inspection.history_overlap_paths == []
    assert inspection.selection_requires_history_ack(["tracked.txt"]) is False

    (repo / "tracked.txt").write_text("local pre-apply\n", encoding="utf-8")
    result = core.apply_godzip(repo, inspection, ["tracked.txt"])
    assert result.replaced == 1
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "archive version\n"


def test_older_baseline_target_overlap_requires_review_and_preserves_rollback_and_debris(
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
    assert inspection.baseline_relation == "older"
    assert inspection.relation == "conflict"
    assert inspection.history_overlap_paths == ["tracked.txt"]
    assert inspection.selection_requires_history_ack(["tracked.txt"]) is True
    assert inspection.selection_requires_history_ack(["new.txt"]) is False

    with pytest.raises(core.GodzipError, match="explicit review"):
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
        allow_history_conflict=True,
    )

    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "archive version\n"
    assert (repo / "new.txt").read_text(encoding="utf-8") == "new from archive\n"
    assert not (repo / "obsolete.txt").exists()
    assert result.backup_dir is not None
    assert (result.backup_dir / "tracked.txt").read_text(encoding="utf-8") == "newer local version\n"
    assert result.debris_dir is not None
    assert (result.debris_dir / "obsolete.txt").read_text(encoding="utf-8") == "move me\n"


def test_internal_git_subprocesses_are_hidden_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(core.os, "name", "nt")
    kwargs = core._hidden_subprocess_kwargs()
    assert kwargs["creationflags"] & int(getattr(core.subprocess, "CREATE_NO_WINDOW", 0x08000000))


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
    assert "QApplication.processEvents()" not in source



def test_reserved_godzip_metadata_can_be_moved_as_debris_but_not_replaced(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    metadata = repo / ".godzip" / "manifest.json"
    metadata.parent.mkdir()
    metadata.write_text("{}\n", encoding="utf-8")

    with pytest.raises(core.GodzipError, match="Reserved path"):
        core.validate_repo_relpath(".godzip/manifest.json")

    assert core.validate_debris_relpath(".godzip/manifest.json") == ".godzip/manifest.json"
    moved_root, count = core.move_paths_to_deleteme(repo, [".godzip/manifest.json"], label="metadata")
    assert count == 1
    assert not metadata.exists()
    assert (moved_root / ".godzip" / "manifest.json").is_file()


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


def test_zip_candidate_discovery_filters_noise_is_shallow_and_sorts_by_mtime(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    nested = first / "nested"
    first.mkdir()
    second.mkdir()
    nested.mkdir()

    old = first / "GODZIP_old.zip"
    manifested = second / "opaque-name.zip"
    unrelated = second / "movie-release.zip"
    ignored_nested = nested / "GODZIP_nested.zip"
    with zipfile.ZipFile(old, "w") as archive:
        archive.writestr("tracked.txt", "legacy")
    with zipfile.ZipFile(manifested, "w") as archive:
        archive.writestr(
            core.MANIFEST_MEMBER,
            '{"format":"srpss-godzip","version":1,"files":[],"debris":[]}',
        )
    with zipfile.ZipFile(unrelated, "w") as archive:
        archive.writestr("episode.mkv.txt", "not this project")
    with zipfile.ZipFile(ignored_nested, "w") as archive:
        archive.writestr("tracked.txt", "nested")
    os.utime(old, (10, 10))
    os.utime(manifested, (30, 30))
    os.utime(unrelated, (40, 40))

    found = core.discover_zip_candidates(
        [first, second, tmp_path / "does-not-exist", first],
        limit=10,
    )
    assert found == [manifested.resolve(), old.resolve()]
    assert unrelated.resolve() not in found
    assert ignored_nested.resolve() not in found

    all_zips = core.discover_zip_candidates([first, second], limit=10, project_only=False)
    assert all_zips == [unrelated.resolve(), manifested.resolve(), old.resolve()]


def test_logzip_can_share_last_godzip_output_directory(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    logs = repo / "logs"
    logs.mkdir()
    (logs / "run.log").write_text("hello\n", encoding="utf-8")
    out = tmp_path / "handoff"

    first = core.create_logzip(repo, output_dir=out)
    second = core.create_logzip(repo, output_dir=out)

    short = core.git_head(repo)[:10]
    assert first.zip_path == out / f"logs{short}.zip"
    assert second.zip_path == out / f"logs{short}2.zip"
    assert not (logs / first.zip_path.name).exists()


def test_godzip_diff_uses_archived_dirty_bytes_and_finds_later_git_and_worktree_changes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    source_head = core.git_head(repo)
    (repo / "tracked.txt").write_text("baseline dirty\n", encoding="utf-8")
    archive = tmp_path / "GODZIP_baseline.zip"
    core.create_godzip(repo, ["tracked.txt"], archive)

    (repo / "tracked.txt").write_text("after claude\n", encoding="utf-8")
    (repo / "new_committed.py").write_text("print('new')\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt", "new_committed.py")
    _git(repo, "commit", "-m", "claude work")
    (repo / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
    state = repo / ".godzip_foundry" / "settings.json"
    state.parent.mkdir(exist_ok=True)
    state.write_text("{}\n", encoding="utf-8")

    result = core.generate_godzip_diff(repo, archive)

    assert result.baseline_head == source_head
    assert result.current_head == core.git_head(repo)
    assert result.changed_files == 3
    assert result.added == 2
    assert result.modified == 1
    assert result.deleted == 0
    assert "-baseline dirty" in result.text
    assert "+after claude" in result.text
    assert "new_committed.py" in result.text
    assert "scratch.txt" in result.text
    assert ".godzip_foundry/settings.json" not in result.text


def _add_runtime_surface(repo: Path, *, windows_venv: bool = False) -> None:
    flags = [
        "--debug", "-d", "--verbose", "-v", "--perf", "--gpu-timing",
        "--usage", "--viz", "--geo", "--set", "--life", "--cache",
        "--steam", "--noupdates", "--viz-diagnostics", "--viz-diag",
        "--fresh", "--devcurve", "--devsteam", "--diag-pair-warm-finish",
        "--diag-p4-stages", "--diag-p4-no-perf-hud",
    ]
    (repo / "main.py").write_text(
        "def parse_screensaver_args():\n"
        f"    _filtered = {set(flags)!r}\n"
        "    return _filtered\n",
        encoding="utf-8",
    )
    (repo / "main_mc.py").write_text("from main import parse_screensaver_args\n", encoding="utf-8")
    python_exe = (
        repo / ".venv" / "Scripts" / "python.exe"
        if windows_venv
        else core.repo_venv_python(repo)
    )
    python_exe.parent.mkdir(parents=True, exist_ok=True)
    python_exe.write_bytes(b"fixture-python")


def test_run_flag_discovery_uses_current_main_cli_surface_and_collapses_aliases(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _add_runtime_surface(repo)

    flags = core.discover_run_flags(repo)

    assert "--debug" in flags
    assert "--verbose" in flags
    assert "--viz-diagnostics" in flags
    assert "-d" not in flags
    assert "-v" not in flags
    assert "--viz-diag" not in flags
    assert set(core.RUN_DEFAULT_FLAGS).issubset(set(flags))


def test_run_command_defaults_to_repo_venv_and_rejects_unknown_flags(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _add_runtime_surface(repo)

    command = core.build_run_command(repo, "main.py", core.RUN_DEFAULT_FLAGS)

    assert Path(command[0]) == core.repo_venv_python(repo)
    assert Path(command[1]) == repo / "main.py"
    assert tuple(command[2:]) == core.RUN_DEFAULT_FLAGS
    with pytest.raises(core.GodzipError, match="not accepted"):
        core.build_run_command(repo, "main.py", ["--made-up-goblin-flag"])


def test_windows_run_console_auto_closes_unless_keep_open_is_explicit(monkeypatch, tmp_path: Path) -> None:
    from types import SimpleNamespace

    repo = _repo(tmp_path)
    # Build the Windows-shaped fixture before substituting the core's os facade.
    (repo / "main.py").write_text(
        "def parse_screensaver_args():\n"
        "    _filtered = {'--debug', '--fresh'}\n"
        "    return _filtered\n",
        encoding="utf-8",
    )
    (repo / "main_mc.py").write_text("from main import parse_screensaver_args\n", encoding="utf-8")
    python_exe = repo / ".venv" / "Scripts" / "python.exe"
    python_exe.parent.mkdir(parents=True)
    python_exe.write_bytes(b"fixture-python")

    calls: list[tuple[list[str], dict]] = []

    class FakeProcess:
        pid = 4242

    def fake_popen(command, **kwargs):
        calls.append((list(command), dict(kwargs)))
        return FakeProcess()

    monkeypatch.setattr(core, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(core.subprocess, "Popen", fake_popen)

    direct = core.launch_run_command(repo, "main.py", ["--debug"], keep_console_open=False)
    assert direct.pid == 4242
    direct_cmd, direct_kwargs = calls[-1]
    assert Path(direct_cmd[0]).as_posix().endswith(".venv/Scripts/python.exe")
    assert direct_cmd[1].endswith("main.py")
    assert direct_cmd[2:] == ["--debug"]
    assert direct_kwargs["creationflags"] == int(getattr(core.subprocess, "CREATE_NEW_CONSOLE", 0x00000010))
    assert direct_cmd[0].lower() != "cmd.exe"

    kept = core.launch_run_command(repo, "main.py", ["--fresh"], keep_console_open=True)
    assert kept.pid == 4242
    kept_cmd, kept_kwargs = calls[-1]
    assert kept_cmd[:3] == ["cmd.exe", "/d", "/k"]
    assert "--fresh" in kept_cmd[3]
    assert kept_kwargs["creationflags"] == direct_kwargs["creationflags"]


def test_run_tab_is_last_and_remains_repo_local() -> None:
    source = (TOOLS_DIR / "godzip_foundry.py").read_text(encoding="utf-8")
    assert "class RunTab" in source
    assert "class DiffTab" in source
    assert 'self.tabs.addTab(self.diff_tab, "DIFF")' in source
    assert 'self.tabs.addTab(self.run_tab, "RUN")' in source
    assert source.index('self.tabs.addTab(self.debris_tab, "DEBRIS")') < source.index('self.tabs.addTab(self.run_tab, "RUN")')
    assert '"run_flags"' in source
    assert '"run_entrypoint"' in source
    assert "COPY TO CLIPBOARD" in source
    assert "refresh_native_taskbar_icon" in source
    assert "WM_SETICON" not in source  # numeric native message kept implementation-local, no shell command fallback
    assert "LOCALAPPDATA" not in source
    assert "AppData" not in source


def test_run_auto_logzip_waits_for_process_exit_without_polling_and_is_repo_local() -> None:
    source = (TOOLS_DIR / "godzip_foundry.py").read_text(encoding="utf-8")

    assert 'QCheckBox("LogZIP after run automatically")' in source
    assert '"run_auto_logzip_after_exit"' in source
    assert "process.wait()" in source
    assert "process.poll()" not in source
    assert 'name="GodzipFoundryRunWait"' in source
    assert "create_logzip(" in source
    assert "if checked and self.keep_console.isChecked():" in source
    assert "if checked and self.auto_logzip.isChecked():" in source


def test_create_and_logzip_expose_shell_open_for_remembered_output_without_console_spawn() -> None:
    source = (TOOLS_DIR / "godzip_foundry.py").read_text(encoding="utf-8")

    assert source.count('QPushButton("Open Saved Folder")') >= 2
    assert "QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))" in source
    assert "def open_saved_folder" in source
    assert "explorer.exe" not in source
