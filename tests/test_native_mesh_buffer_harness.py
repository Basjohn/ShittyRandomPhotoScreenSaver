"""GPU-free verdict and measurement contracts of the mesh-buffer proof harness."""
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native/core/python"))
harness = importlib.import_module("mesh_buffer_check")


@pytest.mark.parametrize("target", ("opengl", "reference"))
@pytest.mark.parametrize("failure", ("timeout", "exit"))
def test_failed_child_never_reuses_success(target, failure, monkeypatch, tmp_path):
    from tools import artifact_paths

    monkeypatch.setattr(artifact_paths, "evidence_dir", lambda *_: tmp_path)
    monkeypatch.setattr(harness, "_gpu_conditions", lambda: {})
    monkeypatch.setattr(harness, "bake_packs", lambda *_: {})
    monkeypatch.setattr(harness, "cross_compare", lambda *_: {
        key: {"pass": True} for key in ("rule_a", "rule_b", "control_offset_stream_differs")})
    good = {"module_loaded": True, "rounds": [], "reference": {"pass": True}}
    path = tmp_path / f"child_{target}.json"
    path.write_text(json.dumps(good), encoding="utf-8")

    def run(command, **kwargs):
        api = command[command.index("--api") + 1]
        child_path = Path(command[command.index("--child-json") + 1])
        if api == target:
            assert not child_path.exists(), "stale success survived until launch"
        child_path.write_text(json.dumps(good), encoding="utf-8")
        if api == target and failure == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 9 if api == target else 0, "", "crash")

    monkeypatch.setattr(harness.subprocess, "run", run)
    harness.main(["--apis", "opengl", "--rounds", "parity", "--label", "r226_mesh"])
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert not summary["pass"]
    assert not summary["verdicts"][target]["pass"]
    assert "child process failed" in " ".join(summary["verdicts"][target]["failed"])


@pytest.mark.parametrize("exit_code", ("timeout", 9))
def test_reference_result_cannot_overrule_failed_exit(exit_code):
    ok, failed = harness.api_verdict("reference", {"reference": {"pass": True}, "exit_code": exit_code}, False)
    assert not ok and "child process failed" in " ".join(failed)
