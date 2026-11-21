"""agent_handover's worktree removal: paths past 260 characters, junctions never followed (Windows)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools import agent_handover

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="long paths and junctions are a Windows matter")


def _run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def _make_case(tmp_path: Path):
    """A git repo with a worktree holding an untracked folder past 260 characters, and a junction to a folder outside."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run("git", "init", "-q", "-b", "main", cwd=repo)
    (repo / "a.txt").write_text("a")
    (repo / ".gitignore").write_text(".artifacts/\n")
    _run("git", "add", ".gitignore", cwd=repo)
    _run("git", "add", "a.txt", cwd=repo)
    _run("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init", cwd=repo)
    worktree = tmp_path / "wt"
    _run("git", "worktree", "add", "-q", str(worktree), "-b", "agent-branch", cwd=repo)

    _run("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "agent", cwd=worktree)
    _run("git", "-c", "user.name=t", "-c", "user.email=t@t", "merge", "--no-ff", "-q", "-m", "m", "agent-branch", cwd=repo)
    deep = agent_handover._long(str(worktree / ".artifacts" / "evidence"))
    for index in range(12):
        deep = os.path.join(deep, "segment_%02d_of_a_very_long_folder_name" % index)
    os.makedirs(deep)
    assert len(deep) > 400
    with open(os.path.join(deep, "frame.png"), "w") as handle:
        handle.write("x")
    os.makedirs(agent_handover._long(str(worktree / ".artifacts")), exist_ok=True)

    outside = tmp_path / "outside_target"
    outside.mkdir()
    (outside / "precious.txt").write_text("keep me")
    junction = worktree / ".artifacts" / "evidence_link"
    _run("cmd", "/c", "mklink", "/J", str(junction), str(outside), cwd=tmp_path)
    assert junction.exists()
    return repo, worktree, outside


def test_remove_worktree_handles_long_paths_and_spares_junction_target(tmp_path):
    repo, worktree, outside = _make_case(tmp_path)
    error = agent_handover.remove_worktree(repo, worktree)
    assert error == ""
    assert not os.path.lexists(str(worktree))
    assert (outside / "precious.txt").read_text() == "keep me"
    listed = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
    assert str(worktree.name) not in listed


def test_control_plain_git_remove_without_long_path_handling_leaves_the_folder(tmp_path):
    """The pre-change behaviour: a bare `git worktree remove --force` on the same tree."""
    repo, worktree, outside = _make_case(tmp_path)
    subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=repo, capture_output=True)
    assert os.path.lexists(str(worktree)), "git removed the deep tree, so this control proves nothing"


def _retire_in(repo: Path, worktree: Path, monkeypatch) -> int:
    monkeypatch.setattr(agent_handover, "ROOT", repo)
    monkeypatch.setattr(agent_handover, "running_from", lambda _worktree: [])
    return agent_handover.retire(worktree)


def test_retire_copies_evidence_deeper_than_260_characters(tmp_path, monkeypatch):
    repo, worktree, outside = _make_case(tmp_path)
    assert _retire_in(repo, worktree, monkeypatch) == 0
    arrived = [name for _folder, _dirs, names in os.walk(agent_handover._long(str(repo / ".artifacts" / "evidence")))
               for name in names]
    assert arrived == ["frame.png"]
    assert not os.path.lexists(str(worktree))
    assert (outside / "precious.txt").read_text() == "keep me"


def test_retire_refuses_to_remove_when_an_evidence_file_fails_to_copy(tmp_path, monkeypatch, capsys):
    repo, worktree, _outside = _make_case(tmp_path)

    def broken(_path, _destination):
        raise OSError("disk full")

    monkeypatch.setattr(agent_handover, "_copy_file", broken)
    assert _retire_in(repo, worktree, monkeypatch) == 1
    assert os.path.lexists(str(worktree))
    assert "frame.png" in capsys.readouterr().out

