"""The one-off legacy evidence move: copy, verify, then delete; resumable; held folders untouched; references
rewritten to repo-relative layout paths (a converted PNG or frame folder to its WebP); dead ones reported."""
from __future__ import annotations

import os

from tools import artifact_migration as migration
from tools import artifact_paths


def _legacy_tree(root):
    legacy = root / "evidence_legacy"
    (legacy / "studio_drag").mkdir(parents=True)
    (legacy / "studio_drag" / "before.json").write_text("{}")
    (legacy / "spectrum" / "jerkiness_20261105" / "motion").mkdir(parents=True)
    (legacy / "spectrum" / "jerkiness_20261105" / "summary.json").write_text('{"a": 1}')
    (legacy / "spectrum" / "jerkiness_20261105" / "motion.webp").write_bytes(b"RIFFwebp")
    (legacy / "spectrum" / "jerkiness_20261105" / "motion" / "notes.txt").write_text("frames were here")
    (legacy / "quiet_session_20261107").mkdir()
    (legacy / "quiet_session_20261107" / "run.json").write_text("{}")
    return legacy


def test_the_move_copies_verifies_then_deletes_and_leaves_held_folders(tmp_path):
    with artifact_paths.use_root(tmp_path / ".artifacts") as root:
        legacy = _legacy_tree(root)
        units = migration.plan(legacy, None)
        by_name = {unit.legacy: unit for unit in units}
        jerk = by_name[".artifacts/evidence/spectrum/jerkiness_20261105"]
        assert jerk.dest == root / "evidence" / "visualizers" / "spectrum" / "jerkiness" / "20261105_jerkiness"
        assert jerk.webps[0][1] == (root / "webp" / "visualizers" / "spectrum" / "jerkiness"
                                    / "20261105_jerkiness_motion.webp")

        # An interrupted earlier run already copied one file: the rerun resumes past it.
        (jerk.dest).mkdir(parents=True)
        (jerk.dest / "summary.json").write_text('{"a": 1}')
        migration.apply(units)

        assert (jerk.dest / "summary.json").read_text() == '{"a": 1}'
        assert jerk.webps[0][1].read_bytes() == b"RIFFwebp"
        assert not (legacy / "spectrum" / "jerkiness_20261105").exists(), "verified sources are deleted"
        assert (legacy / "quiet_session_20261107" / "run.json").exists(), "a held folder was moved"


def test_a_failed_verify_keeps_the_source(tmp_path, monkeypatch):
    with artifact_paths.use_root(tmp_path / ".artifacts") as root:
        legacy = _legacy_tree(root)
        units = [unit for unit in migration.plan(legacy, None) if unit.legacy.endswith("studio_drag")]
        real_replace = os.replace
        monkeypatch.setattr(migration.os, "replace",
                            lambda src, dst: (real_replace(src, dst), open(dst, "ab").write(b"x")))
        try:
            migration.apply(units)
        except RuntimeError as exc:
            assert "verify failed" in str(exc)
        else:
            raise AssertionError("a size mismatch was not caught")
        assert (legacy / "studio_drag" / "before.json").exists()


def test_references_become_layout_paths_and_dead_ones_are_reported(tmp_path):
    with artifact_paths.use_root(tmp_path / ".artifacts"):
        legacy = _legacy_tree(tmp_path / ".artifacts")
        units = migration.plan(legacy, None)
        repo = tmp_path / "repo"
        (repo / "Docs").mkdir(parents=True)
        doc = repo / "Docs" / "note.md"
        doc.write_text(
            "see `.artifacts/evidence/spectrum/jerkiness_20261105/summary.json`, the frames "
            "`.artifacts/evidence/spectrum/jerkiness_20261105/motion/` and "
            "`.artifacts/evidence/gone_folder/x.png` and `.artifacts/evidence/settings/probe/20261107_a/r.json`\n")
        changed, rewritten, report = migration.rewrite_references(repo, units, write=True)
        text = doc.read_text()
        assert "`.artifacts/evidence/visualizers/spectrum/jerkiness/20261105_jerkiness/summary.json`" in text
        assert "`.artifacts/webp/visualizers/spectrum/jerkiness/20261105_jerkiness_motion.webp`" in text
        assert "`.artifacts/evidence/settings/probe/20261107_a/r.json`" in text      # already a layout path
        assert "`.artifacts/evidence/gone_folder/x.png`" in text
        assert any("DEAD" in line and "gone_folder" in line for line in report)
        assert changed == 1 and rewritten == 2
