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


def test_the_placement_control_needs_real_oracle_edge_disagreement(tmp_path):
    import numpy as np

    reference = {}
    for name, _card, _dpr, _glow in check.PARITY_CASES:
        pixels = np.zeros((8, 8, 4), dtype=np.float16)
        pixels[2:, :6] = 0.75
        reference[name] = {"scene.colour": {"array": pixels, "content": (6, 6), "size": (8, 8),
                                             "samples": 1, "format": "rgba16f"}}
    check._save(tmp_path, "parity_reference", reference)
    check._save(tmp_path, "placement_control", reference)
    # Merely running the control is insufficient: unchanged pixels must fail its expected rejection verdict.
    assert not check.placement_control_verdict(tmp_path)["pass"]
    broken = {name: {"scene.colour": {**textures["scene.colour"],
                                     "array": np.roll(textures["scene.colour"]["array"], -2, axis=0)}}
              for name, textures in reference.items()}
    check._save(tmp_path, "placement_control", broken)
    judged = check.placement_control_verdict(tmp_path)
    assert judged["pass"] and judged["edge_reads_rejected_by_rule_a"]


@pytest.mark.parametrize("key", ["scene_targets", "scene_target_textures", "scene_target_bytes",
                                  "scene_target_readbacks", "mode_resources"])
def test_the_retirement_predicate_rejects_each_held_resource(key):
    zero = dict.fromkeys(("scene_targets", "scene_target_textures", "scene_target_bytes",
                         "scene_target_readbacks", "mode_resources"), 0)
    assert check._targets_retired(zero)
    assert not check._targets_retired({**zero, key: 1})
    assert not check._targets_retired({})
