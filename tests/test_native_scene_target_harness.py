"""Scene-target proof controls: verdicts must reject failed children and broken forms."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HARNESS = Path(__file__).resolve().parents[1] / "native" / "core" / "python"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))
import scene_target_check as check


@pytest.mark.parametrize("exit_code", [3, "timeout"])
@pytest.mark.parametrize("api", ["opengl", "reference"])
def test_a_failed_child_cannot_supply_successful_proof(api, exit_code):
    record = {"module_loaded": True, "rounds": ["rest"], "rest": {"pass": True},
              "reference": {"pass": True}, "exit_code": exit_code}
    assert not check.api_verdict(api, record, False)[0]


@pytest.mark.parametrize("outcome", ["timeout", "nonzero"])
def test_the_parent_removes_stale_child_proof_before_launch(tmp_path, monkeypatch, outcome):
    from tools import artifact_paths

    stale = tmp_path / "child_opengl.json"
    stale.write_text(json.dumps({"api": "opengl", "module_loaded": True, "rounds": ["rest"],
                                 "rest": {"pass": True}}), encoding="utf-8")
    removed_at_launch = []

    def run(command, **kwargs):
        removed_at_launch.append(not stale.exists())
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, 1)
        # A failed child may even write a plausible success report before crashing.
        stale.write_text(json.dumps({"api": "opengl", "module_loaded": True, "rounds": ["rest"],
                                     "rest": {"pass": True}}), encoding="utf-8")
        return SimpleNamespace(returncode=7, stderr="controlled child failure")

    monkeypatch.setattr(artifact_paths, "evidence_dir", lambda *args: tmp_path)
    monkeypatch.setattr(check.subprocess, "run", run)
    monkeypatch.setattr(check.vk_validation, "environment_record", lambda *args: {"clean": True})
    assert check.main(["--apis", "opengl", "--rounds", "rest"]) == 0
    result = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert removed_at_launch == [True]
    assert not result["pass"]
