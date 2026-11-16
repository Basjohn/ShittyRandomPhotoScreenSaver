"""Child records cannot outlive their process or override its failure."""
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native" / "core" / "python"))

TOOLS = ("backdrop_pyramid_check", "background_layer_check", "compute_pass_check", "devcurve_check",
         "fullscreen_pass_check", "generic_mode_check", "job_service_check", "post_stage_check",
         "spectrum_check", "timer_check", "transition_route_check")


@pytest.mark.parametrize("name", TOOLS)
@pytest.mark.parametrize("failure", ("timeout", "exit"))
def test_failed_child_cannot_reuse_success(name, failure, monkeypatch, tmp_path):
    from tools import artifact_paths

    tool = importlib.import_module(name)
    monkeypatch.setattr(artifact_paths, "evidence_dir", lambda *_: tmp_path)
    if name == "compute_pass_check":
        monkeypatch.setattr(tool.mbc, "_gpu_conditions", lambda: {})
        monkeypatch.setattr(tool, "bake_packs", lambda *_: {})
        monkeypatch.setattr(tool, "qualifier_facts", lambda *_: {})
    if name == "post_stage_check":
        monkeypatch.setattr(tool, "_machine_state", lambda: {})
    path = tmp_path / "child_opengl.json"
    good = {"api": "opengl", "module_loaded": True, "rounds": [], "reference": {"pass": True}}
    path.write_text(json.dumps(good), encoding="utf-8")

    def run(command, **kwargs):
        assert not path.exists(), "stale success survived until launch"
        path.write_text(json.dumps(good), encoding="utf-8")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 9, "", "crash")

    monkeypatch.setattr(tool.subprocess, "run", run)
    tool.main(["--apis", "opengl", "--label", "r226_fresh"])
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert not summary["verdicts"]["opengl"]["pass"]
    assert "child process failed" in " ".join(summary["verdicts"]["opengl"]["failed"])


@pytest.mark.parametrize("name", ("compute_pass_check", "post_stage_check"))
@pytest.mark.parametrize("exit_code", ("timeout", 9))
def test_reference_success_cannot_override_failed_process(name, exit_code):
    tool = importlib.import_module(name)
    record = {"reference": {"pass": True}, "exit_code": exit_code}
    args = ("reference", record, False, []) if name == "post_stage_check" else ("reference", record, False)
    ok, failed = tool.api_verdict(*args)
    assert not ok
    assert "child process failed" in " ".join(failed)
