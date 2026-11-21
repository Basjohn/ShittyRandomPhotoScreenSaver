"""Linked worktrees keep their heavy output on the scratch drive; fast-proof data is never pruned.

Owners: ``tools/artifact_paths.py`` (junctions, ``is_protected``, ``prune_scratch``) and
``tools/agent_handover.py`` (``copy_kept`` and ``drive_targets`` behind ``--retire``). Junctions are made with
``mklink /J`` inside a scratch folder; nothing here touches the real scratch drive.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tools import agent_handover, artifact_paths

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="directory junctions")


@pytest.fixture
def tmp_path():
    """A folder under the layout's scratch (on the scratch drive), not pytest's: Windows refuses to create folders
    through a junction that lies under %TEMP% on C: (WinError 183), which the real layout never does."""
    with artifact_paths.scratch("worktree_link_tests") as folder:
        yield folder


def _junction(link: Path, target: Path) -> bool:
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
    return result.returncode == 0 and link.exists()


def _load_owner_from(checkout: Path):
    target = checkout / "tools" / "artifact_paths.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(artifact_paths.__file__), target)
    spec = importlib.util.spec_from_file_location(f"_ap_links_{checkout.name}", target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_worktree(tmp_path: Path):
    main = tmp_path / "main"
    admin = main / ".git" / "worktrees" / "agent"
    admin.mkdir(parents=True)
    (admin / "commondir").write_text("../..\n", encoding="utf-8")
    worktree = main / ".claude" / "worktrees" / "agent"
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
    drive = tmp_path / "drive"
    drive.mkdir()
    return main, worktree, drive


def test_a_worktree_write_lands_on_the_drive_side_target(tmp_path):
    main, worktree, drive = _fake_worktree(tmp_path)
    owner = _load_owner_from(worktree)
    owner.SCRATCH_DRIVE_ROOT = drive
    (worktree / ".artifacts" / "webp").mkdir(parents=True)
    (worktree / ".artifacts" / "webp" / "keep.txt").write_text("real folder stays")

    folder = owner.evidence_dir("tests", "probe", "run", date="20261122")     # first use links the folders
    folder.mkdir(parents=True)
    (folder / "data.json").write_text("{}")
    landed = drive / "worktrees" / "agent" / "evidence" / "tests" / "probe" / "20261122_run" / "data.json"
    assert landed.is_file()
    assert owner.junction_target(worktree / ".artifacts" / "evidence") is not None
    assert owner.junction_target(worktree / ".artifacts" / "scratch") is not None
    owner.checked_output(folder / "data.json")                                 # still inside the layout

    # control: an existing real folder is never moved or replaced
    assert owner.junction_target(worktree / ".artifacts" / "webp") is None
    assert (worktree / ".artifacts" / "webp" / "keep.txt").read_text() == "real folder stays"
    assert not (drive / "worktrees" / "agent" / "webp").exists()
    # control: the main checkout gets no junctions
    assert owner.link_worktree_artifacts(main, drive) == []
    assert not (main / ".artifacts").exists()
    # control: no drive, nothing linked
    assert owner.link_worktree_artifacts(worktree, tmp_path / "absent") == []


def test_a_junction_target_outside_the_scratch_drive_is_refused(tmp_path):
    main, worktree, drive = _fake_worktree(tmp_path)
    owner = _load_owner_from(worktree)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (worktree / ".artifacts").mkdir()
    assert _junction(worktree / ".artifacts" / "evidence", elsewhere)
    with pytest.raises(owner.ArtifactPathError):
        owner.link_worktree_artifacts(worktree, drive)
    # control: a junction inside the drive is accepted
    inside = drive / "ok"
    inside.mkdir()
    (worktree / ".artifacts" / "evidence").rmdir()
    assert _junction(worktree / ".artifacts" / "evidence", inside)
    owner.link_worktree_artifacts(worktree, drive)


def test_retire_copies_the_keep_group_through_junctions_then_the_drive_targets_can_go(tmp_path):
    main, worktree, drive = _fake_worktree(tmp_path)
    owner = _load_owner_from(worktree)
    owner.link_worktree_artifacts(worktree, drive)
    target_root = drive / "worktrees" / "agent"
    (target_root / "evidence" / "tests" / "probe").mkdir(parents=True)
    (target_root / "evidence" / "tests" / "probe" / "a.json").write_text("A")
    (target_root / "webp" / "x").mkdir(parents=True)
    (target_root / "webp" / "x" / "b.webp").write_bytes(b"B")
    outside = tmp_path / "outside_data"
    outside.mkdir()
    (outside / "precious.txt").write_text("never touched")
    assert _junction(target_root / "evidence" / "nested_link", outside)        # a link inside is never entered

    copied, _kept, differing, failed, links = agent_handover.copy_kept(main, worktree)
    assert (copied, failed, differing) == (2, [], [])
    assert (main / ".artifacts" / "evidence" / "tests" / "probe" / "a.json").read_text() == "A"
    assert (main / ".artifacts" / "webp" / "x" / "b.webp").read_bytes() == b"B"
    assert len(links) == 1 and not (main / ".artifacts" / "evidence" / "nested_link").exists()
    keep_only = agent_handover.copy_kept(tmp_path / "main2", worktree, ["evidence/tests/probe/a.json"])
    assert keep_only[0] == 1 and not keep_only[3]

    targets = agent_handover.drive_targets(worktree, drive)
    assert len(targets) == 3
    for target in targets:
        agent_handover.remove_tree(target)
    assert not list(target_root.rglob("a.json"))
    assert (outside / "precious.txt").read_text() == "never touched"            # no other link was followed


def test_retire_names_no_junction_target_outside_the_worktrees_own_drive_folder(tmp_path):
    main, worktree, drive = _fake_worktree(tmp_path)
    foreign = drive / "worktrees" / "other_agent" / "evidence"
    foreign.mkdir(parents=True)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (worktree / ".artifacts").mkdir()
    assert _junction(worktree / ".artifacts" / "evidence", foreign)            # another worktree's folder
    assert _junction(worktree / ".artifacts" / "webp", unrelated)              # outside the drive
    assert agent_handover.drive_targets(worktree, drive) == []


def test_fast_proof_references_and_accepted_hashes_are_protected(tmp_path, monkeypatch):
    drive = artifact_paths.SCRATCH_DRIVE_ROOT
    assert artifact_paths.is_protected(drive / "fast_proof" / "references")
    assert artifact_paths.is_protected(drive / "fast_proof" / "references" / "bubble" / "take.bin")
    assert artifact_paths.is_protected(tmp_path / "anywhere" / "native_render_parity.json")
    # controls: ordinary scratch and a look-alike sibling are not protected
    assert not artifact_paths.is_protected(drive / "scratch" / "o" / "1_run")
    assert not artifact_paths.is_protected(drive / "fast_proof" / "references_old")

    now = time.time()
    with artifact_paths.use_root(tmp_path / ".artifacts") as root:
        run = root / "scratch" / "owner" / "999999_dead"
        run.mkdir(parents=True)
        (run / "x.bin").write_bytes(b"x")
        for item in (run, run / "x.bin"):
            os.utime(item, (now - 48 * 3600, now - 48 * 3600))
        with monkeypatch.context() as patch:
            patch.setattr(artifact_paths, "is_protected", lambda path: True)
            with pytest.raises(artifact_paths.ArtifactPathError):
                artifact_paths.prune_scratch(apply=True, now=now)
        assert run.exists(), "a protected path was deleted"
        artifact_paths.prune_scratch(apply=True, now=now)                      # control: unprotected goes
        assert not run.exists()
