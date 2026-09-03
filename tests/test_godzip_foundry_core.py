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
