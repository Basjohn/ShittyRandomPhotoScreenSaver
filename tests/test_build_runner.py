from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from tools import build_runner


def _make_helper_inputs(root: Path, mode: str) -> None:
    paths = [
        root / "helpers" / "reddit_helper_worker.py",
        root / "core" / "constants" / "timing.py",
        root / "core" / "logging" / "logger.py",
        root / "core" / "mc.py",
        root / "core" / "windows" / "browser_window_routing.py",
        root / "core" / "windows" / "reddit_helper_runtime.py",
        root / "build_deps" / "requirements_helper.txt",
        root / "tools" / "build_layout.ps1",
        root / "versioning.py",
        root / "SRPSS.ico",
        root
        / "scripts"
        / ("venv" if mode == "venv" else "")
        / "build_reddit_helper.ps1",
    ]
    for index, path in enumerate(paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture-{index}", encoding="utf-8")


def test_job_modes_share_canonical_installers_but_select_distinct_workers(tmp_path):
    normal = build_runner.jobs_for_mode("normal", tmp_path)
    venv = build_runner.jobs_for_mode("venv", tmp_path)

    assert normal[0].script == tmp_path / "scripts" / "build_nuitka.ps1"
    assert venv[0].script == tmp_path / "scripts" / "venv" / "build_nuitka.ps1"
    assert normal[2].script == venv[2].script == tmp_path / "scripts" / "venv" / "build_nuitka_diagnostic.ps1"
    assert normal[2].default_selected is False
    assert normal[3].script == tmp_path / "scripts" / "build_reddit_helper.ps1"
    assert venv[3].script == tmp_path / "scripts" / "venv" / "build_reddit_helper.ps1"
    assert normal[4].script == venv[4].script == tmp_path / "scripts" / "SRPSS_Installer.iss"
    assert normal[5].script == venv[5].script == tmp_path / "scripts" / "SRPSS_MediaCenter_Installer.iss"
    assert normal[6].script == venv[6].script == tmp_path / "scripts" / "SRPSS_Diagnostic_Installer.iss"
    assert normal[6].default_selected is False
    assert [job.output_dir for job in normal] == [
        tmp_path / "release" / "screensaver",
        tmp_path / "release" / "media_center",
        tmp_path / "release" / "diagnostic",
        tmp_path / "release" / "reddit_helper",
        tmp_path / "release" / "installers",
        tmp_path / "release" / "installers",
        tmp_path / "release" / "installers",
    ]


def test_preferences_round_trip_and_corrupt_fallback(tmp_path):
    target = tmp_path / "preferences.json"
    expected = build_runner.Preferences(auto_close=False, mode="normal")

    assert build_runner.save_preferences(expected, target) is True
    assert build_runner.load_preferences(target) == expected

    target.write_text("{broken", encoding="utf-8")
    assert build_runner.load_preferences(target) == build_runner.Preferences()


def test_foundry_uses_large_dpi_aware_vector_checkbox_indicators():
    source = inspect.getsource(build_runner.FoundryCheckbutton)
    signature = inspect.signature(build_runner.FoundryCheckbutton.__init__)

    assert signature.parameters["indicator_size"].default >= 24
    assert "tk.Canvas(" in source
    assert "create_rectangle(" in source
    assert "create_line(" in source


def test_helper_fingerprint_dechecks_only_after_matching_successful_build(tmp_path):
    _make_helper_inputs(tmp_path, "venv")
    artifact = (
        tmp_path
        / "release"
        / "reddit_helper"
        / "SRPSS_RedditHelper.exe"
    )
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"packaged-helper")
    state_path = tmp_path / "runner_state" / "reddit_helper_build_state.json"

    first = build_runner.helper_build_status("venv", tmp_path, state_path=state_path)
    assert first.needs_rebuild is True
    assert "fingerprint" in first.reason.lower()

    assert build_runner.record_helper_build(
        "venv",
        first.fingerprint,
        artifact=artifact,
        state_path=state_path,
    )
    unchanged = build_runner.helper_build_status("venv", tmp_path, state_path=state_path)
    assert unchanged.needs_rebuild is False
    assert "unchanged" in unchanged.reason.lower()

    runtime_file = artifact.parent / "_internal" / "runtime.dll"
    runtime_file.parent.mkdir()
    runtime_file.write_bytes(b"unexpected-payload-change")
    damaged = build_runner.helper_build_status("venv", tmp_path, state_path=state_path)
    assert damaged.needs_rebuild is True
    assert "payload changed" in damaged.reason.lower()

    worker = tmp_path / "helpers" / "reddit_helper_worker.py"
    worker.write_text("fixture-changed", encoding="utf-8")
    changed = build_runner.helper_build_status("venv", tmp_path, state_path=state_path)
    assert changed.needs_rebuild is True
    assert "changed" in changed.reason.lower()


def test_helper_fingerprint_is_environment_specific(tmp_path):
    _make_helper_inputs(tmp_path, "normal")
    _make_helper_inputs(tmp_path, "venv")

    normal, _ = build_runner.helper_fingerprint("normal", tmp_path)
    venv, _ = build_runner.helper_fingerprint("venv", tmp_path)

    assert normal != venv


def test_run_job_writes_one_clickable_runner_log(monkeypatch, tmp_path):
    script = tmp_path / "scripts" / "build.ps1"
    script.parent.mkdir()
    script.write_text("Write-Host ok", encoding="utf-8")
    output_dir = tmp_path / "release"
    job = build_runner.Job(
        "fixture",
        "Fixture Build",
        "powershell",
        script,
        output_dir,
        output_dir / "artifact.exe",
    )

    def fake_run(command, **kwargs):
        kwargs["stdout"].write(b"fixture output\n")
        job.expected_artifact.parent.mkdir(parents=True, exist_ok=True)
        job.expected_artifact.write_bytes(b"artifact")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(build_runner.subprocess, "run", fake_run)
    monkeypatch.setattr(build_runner, "_windows_subprocess_kwargs", lambda: {})
    preflight = build_runner.PreflightResult(pwsh=Path("pwsh.exe"))

    result = build_runner.run_job(job, preflight, tmp_path / "logs")

    assert result.returncode == 0
    assert result.log_path.is_file()
    text = result.log_path.read_text(encoding="utf-8")
    assert "Fixture Build" in text
    assert "fixture output" in text
    assert "Process exit code: 0" in text
    assert "Runner exit code: 0" in text


def test_run_job_rejects_zero_exit_without_expected_artifact(monkeypatch, tmp_path):
    script = tmp_path / "scripts" / "build.ps1"
    script.parent.mkdir()
    script.write_text("Write-Host ok", encoding="utf-8")
    output_dir = tmp_path / "release" / "fixture"
    job = build_runner.Job(
        "fixture",
        "Fixture Build",
        "powershell",
        script,
        output_dir,
        output_dir / "missing.exe",
    )

    def fake_run(command, **kwargs):
        kwargs["stdout"].write(b"fixture output\n")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(build_runner.subprocess, "run", fake_run)
    monkeypatch.setattr(build_runner, "_windows_subprocess_kwargs", lambda: {})
    preflight = build_runner.PreflightResult(pwsh=Path("pwsh.exe"))

    result = build_runner.run_job(job, preflight, tmp_path / "logs")

    assert result.returncode == 1
    assert "expected artifact is missing" in result.detail.lower()


def test_smoke_payload_uses_only_tools_runner_owner():
    payload = build_runner.smoke_payload("venv")

    assert payload["mode"] == "venv"
    assert len(payload["jobs"]) == 7
    assert Path(payload["jobs"][2]["script"]) == build_runner.REPO_ROOT / "scripts" / "venv" / "build_nuitka_diagnostic.ps1"
    assert payload["jobs"][2]["default_selected"] is False
    assert Path(payload["jobs"][4]["script"]) == build_runner.REPO_ROOT / "scripts" / "SRPSS_Installer.iss"
    assert not (build_runner.REPO_ROOT / "scripts" / "build_runner.py").exists()
    assert not (build_runner.REPO_ROOT / "scripts" / "venv" / "build_runner_venv.py").exists()


def test_preflight_does_not_block_release_jobs_when_optional_diagnostic_is_missing(
    tmp_path,
    monkeypatch,
):
    jobs = build_runner.jobs_for_mode("normal", tmp_path)
    for job in jobs:
        if not job.default_selected:
            continue
        job.script.parent.mkdir(parents=True, exist_ok=True)
        job.script.write_text("fixture", encoding="utf-8")
    for asset in (
        tmp_path / "SRPSS.ico",
        tmp_path / "images" / "LogoBMP.bmp",
        tmp_path / "resources" / "tutuogg.ogg",
    ):
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_bytes(b"fixture")
    monkeypatch.setattr(build_runner, "_find_pwsh", lambda: Path("pwsh.exe"))
    monkeypatch.setattr(build_runner, "_find_iscc", lambda: Path("ISCC.exe"))

    result = build_runner.run_preflight("normal", tmp_path)

    assert result.errors == []
    assert {"diagnostic", "diagnostic_installer"} <= result.unavailable_jobs
    assert any("Diagnostic Runtime" in warning for warning in result.warnings)


def test_workers_and_installers_share_the_canonical_output_layout():
    scripts = build_runner.REPO_ROOT / "scripts"
    normal_standard = (scripts / "build_nuitka.ps1").read_text(encoding="utf-8")
    venv_standard = (scripts / "venv" / "build_nuitka.ps1").read_text(encoding="utf-8")
    standard_installer = (scripts / "SRPSS_Installer.iss").read_text(encoding="utf-8")
    media_installer = (scripts / "SRPSS_MediaCenter_Installer.iss").read_text(
        encoding="utf-8"
    )
    diagnostic_worker = (scripts / "venv" / "build_nuitka_diagnostic.ps1").read_text(
        encoding="utf-8"
    )
    diagnostic_entrypoint = (build_runner.REPO_ROOT / "main_diagnostic.py").read_text(
        encoding="utf-8"
    )
    diagnostic_installer = (scripts / "SRPSS_Diagnostic_Installer.iss").read_text(
        encoding="utf-8"
    )

    assert "'normal\\screensaver'" in normal_standard
    assert '[string]$BuildTarget = "screensaver"' in venv_standard
    assert '("venv\\{0}" -f $BuildTarget)' in venv_standard
    assert "--output-dir=$BuildOutputDir" in normal_standard
    assert "--output-dir=$BuildOutputDir" in venv_standard
    assert r"OutputDir=..\release\installers" in standard_installer
    assert r"release\screensaver\SRPSS.scr" in standard_installer
    assert r"release\reddit_helper\*" in standard_installer
    assert r"OutputDir=..\release\installers" in media_installer
    assert r"release\media_center\*" in media_installer
    assert "main_diagnostic.py" in diagnostic_worker
    assert "SRPSS_Diagnostic" in diagnostic_worker
    assert "-DistributionName 'diagnostic'" in diagnostic_worker
    assert "from core.build_profile import activate_diagnostic_build" in diagnostic_entrypoint
    assert "from core.logging import crash_capture" in diagnostic_entrypoint
    assert "from core.logging import ownership_trace" in diagnostic_entrypoint
    assert r"release\diagnostic\SRPSS_Diagnostic.exe" in diagnostic_installer
    assert "Setup_SRPSS_Diagnostic" in diagnostic_installer
    assert "AppId={{9E730AA6-0FF0-4EF5-AE55-7D88956F32DE}" in diagnostic_installer
    assert "SCRNSAVE.EXE" not in diagnostic_installer
    assert r"{sys}\SRPSS.scr" not in diagnostic_installer
    assert r"{localappdata}\SRPSS Diagnostic" in diagnostic_installer
    assert r'Parameters: """{app}\logs"""' in diagnostic_installer
    assert "Full Telemetry" not in diagnostic_installer
    assert "commonappdata" not in diagnostic_installer.lower()
    assert "reddit_helper" not in diagnostic_installer.lower()

    for mode in ("normal", "venv"):
        jobs = {
            job.key: job
            for job in build_runner.jobs_for_mode(mode)
        }
        for key in ("standard", "media_center", "reddit_helper"):
            job = jobs[key]
            worker = job.script.read_text(encoding="utf-8")
            assert "$BuildExit = $LASTEXITCODE" in worker
            assert "if ($BuildExit -ne 0)" in worker


def test_visualizer_shader_validation_tracks_source_assets_without_retired_blob():
    scripts = build_runner.REPO_ROOT / "scripts" / "venv"
    onefile = (scripts / "build_nuitka.ps1").read_text(encoding="utf-8")
    onedir = (scripts / "build_nuitka_mc_onedir.ps1").read_text(encoding="utf-8")
    shared = (build_runner.REPO_ROOT / "tools" / "build_layout.ps1").read_text(
        encoding="utf-8"
    )

    assert "Assert-SRPSSOnefileVisualizerShaderContract" in onefile
    assert "Assert-SRPSSOnedirVisualizerShaders" in onedir
    assert "Get-SRPSSVisualizerShaderNames" in shared
    assert "blob.frag" not in onefile
    assert "blob.frag" not in onedir
    assert "blob.frag" not in shared


def test_helper_state_record_is_bounded_metadata(tmp_path):
    artifact = tmp_path / "helper.exe"
    artifact.write_bytes(b"binary")
    state = tmp_path / "state.json"

    assert build_runner.record_helper_build(
        "normal",
        "a" * 64,
        artifact=artifact,
        state_path=state,
    )
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["mode"] == "normal"
    assert payload["artifact_size"] == 6
    assert payload["bundle_file_count"] == 1
    assert payload["bundle_size"] == 6
    assert state.stat().st_size < 4096
