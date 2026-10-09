"""Pure reporting and provenance tests. Absolutely no compilation."""
from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from tools.build_evidence import evidence_files, sha256_file, write_build_evidence
from tools.frozen_build_audit import main


def test_normal_evidence_owns_one_run_and_reports_omissions(tmp_path):
    token = "20261009_060001_123456"
    older = "20261009_055959_123456"
    runner = tmp_path / f"build_runner_standard_{token}.log"
    runner.write_text("Build Runner full preflight + compiler output", encoding="utf-8")
    (tmp_path / f"build_nuitka_{token}.log").write_text("compiler output", encoding="utf-8")
    (tmp_path / f"build_nuitka_report_{older}.xml").write_text("STALE", encoding="utf-8")
    exe = tmp_path / "release" / "SRPSS.scr"
    exe.parent.mkdir()
    exe.write_bytes(b"a new compiled screensaver")

    archive = write_build_evidence(tmp_path, "standard", token, runner, exe, 0)
    with ZipFile(archive) as reader:
        content = set(reader.namelist())
        manifest = json.loads(reader.read("evidence.json"))
        assert runner.name in content
        assert f"build_nuitka_{token}.log" in content
        assert f"build_nuitka_report_{older}.xml" not in content
        assert f"build_nuitka_report_{token}.xml" in manifest["missing_files"]
        assert manifest["published_artifact"]["sha256"] == sha256_file(exe)
        assert manifest["runner_exit_code"] == 0


def test_malformed_token_rejected(tmp_path):
    with pytest.raises(ValueError, match="Invalid build run token"):
        write_build_evidence(tmp_path, "standard", "../../another_build", tmp_path / "log", tmp_path / "a", 1)


def test_failure_bundle_has_only_failure_logs(tmp_path):
    token = "20261009_060003_000001"
    runner = tmp_path / f"build_runner_standard_{token}.log"
    runner.write_text("Nuitka failed", encoding="utf-8")
    archive = write_build_evidence(tmp_path, "standard", token, runner, tmp_path / "missing.scr", 1)
    with ZipFile(archive) as reader:
        manifest = json.loads(reader.read("evidence.json"))
        assert manifest["runner_exit_code"] == 1
        assert not manifest["published_artifact"]["exists"]
        assert len(manifest["missing_files"]) == len(evidence_files("standard", token))


def test_compiled_and_published_identity_matches_receipt(tmp_path):
    token = "20261009_060004_000001"
    runner = tmp_path / f"build_runner_media_center_{token}.log"
    runner.write_text("COMPLETE", encoding="utf-8")
    exe = tmp_path / "SRPSS_Media_Center.exe"
    exe.write_bytes(b"exact frozen bytes")
    receipt = tmp_path / f"build_nuitka_mc_onedir_frozen_audit_{token}.json"
    receipt.write_text(json.dumps({"artifact_sha256": sha256_file(exe)}), encoding="utf-8")
    archive = write_build_evidence(tmp_path, "media_center", token, runner, exe, 0)
    with ZipFile(archive) as reader:
        meta = json.loads(reader.read("evidence.json"))
        assert meta["published_artifact"]["matches_compiled_artifact_sha256"] is True
    assert main(["compare", "--receipt", str(receipt), "--artifact", str(exe)]) == 0
    exe.write_bytes(b"older installed executable")
    assert main(["compare", "--receipt", str(receipt), "--artifact", str(exe)]) == 1


def test_runner_and_workers_share_exact_run_token_without_building():
    root = Path(__file__).resolve().parents[1]
    runner = (root / "tools/build_runner.py").read_text(encoding="utf-8")
    assert '"SRPSS_BUILD_RUN_ID": timestamp' in runner
    assert 'write_build_evidence(' in runner
    for worker in ("build_nuitka.ps1", "build_nuitka_mc_onedir.ps1", "build_reddit_helper.ps1"):
        text = (root / "scripts/venv" / worker).read_text(encoding="utf-8")
        assert "$env:SRPSS_BUILD_RUN_ID" in text
        assert '$Timestamp' in text
