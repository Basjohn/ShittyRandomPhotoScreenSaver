from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
LAYOUT_SCRIPT = REPO_ROOT / "tools" / "build_layout.ps1"


def _run_layout_command(command: str, **paths: Path) -> subprocess.CompletedProcess[str]:
    pwsh = shutil.which("pwsh")
    if not pwsh:
        pytest.skip("PowerShell 7 is not available")

    env = os.environ.copy()
    env["SRPSS_LAYOUT_SCRIPT"] = str(LAYOUT_SCRIPT)
    for name, path in paths.items():
        env[f"SRPSS_{name.upper()}"] = str(path)
    return subprocess.run(
        [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )


def test_friend_pulse_and_system_stats_assets_are_in_the_product_contract() -> None:
    contract = LAYOUT_SCRIPT.read_text(encoding="utf-8")

    assert "rendering\\quick\\qml\\FriendPulsePresentation.qml" in contract
    assert "rendering\\quick\\qml\\SystemStatsPresentation.qml" in contract
    assert "ui\\resources\\assets.qrc" in contract
    assert "ui\\resources\\onboarding_assets.qrc" in contract
    assert "--include-module=ui.resources.assets_rc" in contract
    assert "--include-module=ui.resources.onboarding_assets_rc" in contract
    assert "--include-data-dir=images=images" not in contract


def test_build_runner_preflight_checks_friend_pulse_and_system_stats_assets() -> None:
    contract = (REPO_ROOT / "tools" / "build_runner.py").read_text(encoding="utf-8")

    assert '"rendering" / "quick" / "qml" / "FriendPulsePresentation.qml"' in contract
    assert '"rendering" / "quick" / "qml" / "SystemStatsPresentation.qml"' in contract
    assert '"ui" / "resources" / "assets.qrc"' in contract
    assert '"ui" / "resources" / "onboarding_assets.qrc"' in contract


def test_every_product_worker_generates_and_retains_the_two_qrc_modules() -> None:
    scripts = (
        REPO_ROOT / "scripts" / "build_nuitka.ps1",
        REPO_ROOT / "scripts" / "build_nuitka_mc_onedir.ps1",
        REPO_ROOT / "scripts" / "venv" / "build_nuitka.ps1",
        REPO_ROOT / "scripts" / "venv" / "build_nuitka_mc_onedir.ps1",
    )
    for script in scripts:
        worker = script.read_text(encoding="utf-8")
        assert "Invoke-SRPSSQrcRegeneration" in worker
        assert "--include-data-dir=images=images" not in worker
        assert "--include-module=ui.resources.assets_rc" in worker
        assert "--include-module=ui.resources.onboarding_assets_rc" in worker


def test_every_product_worker_emits_nuitka_and_footprint_reports_without_dropping_qrc() -> None:
    scripts = (
        REPO_ROOT / "scripts" / "build_nuitka.ps1",
        REPO_ROOT / "scripts" / "build_nuitka_mc_onedir.ps1",
        REPO_ROOT / "scripts" / "venv" / "build_nuitka.ps1",
        REPO_ROOT / "scripts" / "venv" / "build_nuitka_mc_onedir.ps1",
    )
    for script in scripts:
        worker = script.read_text(encoding="utf-8")
        assert "--report=$NuitkaReportFile" in worker
        assert "Write-SRPSSBuildFootprintReport" in worker
        assert "--include-module=ui.resources.onboarding_assets_rc" in worker

    shared = LAYOUT_SCRIPT.read_text(encoding="utf-8")
    assert "function Write-SRPSSBuildFootprintReport" in shared
    assert "function Get-SRPSSQrcSourceMetrics" in shared
    assert "generated_module_bytes" in shared
    assert "not deployed/frozen payload bytes" in shared
    assert "This report describes the current build and current package contents only." in shared


def test_build_footprint_report_records_current_payload_and_qrc_source_reference(tmp_path):
    repo = tmp_path / "repo"
    resources = repo / "ui" / "resources"
    assets = repo / "ui" / "assets"
    resources.mkdir(parents=True)
    assets.mkdir(parents=True)

    ordinary = assets / "ordinary.bin"
    onboarding = assets / "onboarding.bin"
    ordinary.write_bytes(b"ordinary-source")
    onboarding.write_bytes(b"onboarding-source-bytes")
    (resources / "assets.qrc").write_text(
        '<RCC><qresource prefix="/srpss"><file>../assets/ordinary.bin</file></qresource></RCC>',
        encoding="utf-8",
    )
    (resources / "onboarding_assets.qrc").write_text(
        '<RCC><qresource prefix="/srpss/onboarding"><file>../assets/onboarding.bin</file></qresource></RCC>',
        encoding="utf-8",
    )
    (resources / "assets_rc.py").write_bytes(b"x" * 47)
    (resources / "onboarding_assets_rc.py").write_bytes(b"y" * 113)

    published = repo / "release" / "fixture"
    internal = published / "_internal"
    internal.mkdir(parents=True)
    artifact = published / "fixture.exe"
    artifact.write_bytes(b"artifact-bytes")
    (internal / "runtime.dll").write_bytes(b"r" * 31)
    nuitka_report = repo / "logs" / "fixture_report.xml"
    nuitka_report.parent.mkdir()
    nuitka_report.write_text("<nuitka-compilation-report />", encoding="utf-8")
    footprint = repo / "logs" / "fixture_footprint.json"

    result = _run_layout_command(
        """
. $env:SRPSS_LAYOUT_SCRIPT
Write-SRPSSBuildFootprintReport `
    -RepoRoot $env:SRPSS_REPO `
    -ProductName 'fixture' `
    -PublishedRoot $env:SRPSS_PUBLISHED `
    -PrimaryArtifact $env:SRPSS_ARTIFACT `
    -NuitkaReportPath $env:SRPSS_NUITKA_REPORT `
    -OutputPath $env:SRPSS_FOOTPRINT | Out-Null
""",
        repo=repo,
        published=published,
        artifact=artifact,
        nuitka_report=nuitka_report,
        footprint=footprint,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = __import__("json").loads(footprint.read_text(encoding="utf-8-sig"))
    assert payload["product"] == "fixture"
    assert payload["primary_artifact"]["bytes"] == len(b"artifact-bytes")
    assert payload["published_payload"]["file_count"] == 2
    qrc = {row["qrc"]: row for row in payload["qrc_source_reference"]}
    assert qrc[r"ui\resources\assets.qrc"]["source_bytes"] == len(b"ordinary-source")
    assert qrc[r"ui\resources\assets.qrc"]["generated_module_bytes"] == 47
    assert qrc[r"ui\resources\onboarding_assets.qrc"]["source_bytes"] == len(b"onboarding-source-bytes")
    assert qrc[r"ui\resources\onboarding_assets.qrc"]["generated_module_bytes"] == 113
    assert any("current build and current package contents only" in note for note in payload["notes"])


def test_publish_replaces_only_the_canonical_product_directory(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "artifact.exe").write_bytes(b"new")
    (source / "runtime.dll").write_bytes(b"runtime")

    release_root = tmp_path / "release"
    target = release_root / "screensaver"
    target.mkdir(parents=True)
    (target / "obsolete.exe").write_bytes(b"old")
    sibling = release_root / "installers"
    sibling.mkdir()
    (sibling / "keep.exe").write_bytes(b"keep")

    result = _run_layout_command(
        """
. $env:SRPSS_LAYOUT_SCRIPT
Publish-SRPSSDirectory `
    -SourcePath $env:SRPSS_SOURCE `
    -TargetPath $env:SRPSS_TARGET `
    -ReleaseRoot $env:SRPSS_RELEASE_ROOT `
    -RequiredRelativePaths @('artifact.exe') | Out-Null
""",
        source=source,
        target=target,
        release_root=release_root,
    )

    assert result.returncode == 0, result.stderr
    assert (target / "artifact.exe").read_bytes() == b"new"
    assert (target / "runtime.dll").read_bytes() == b"runtime"
    assert not (target / "obsolete.exe").exists()
    assert (sibling / "keep.exe").read_bytes() == b"keep"


def test_publish_rejects_a_target_outside_release(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "artifact.exe").write_bytes(b"new")
    release_root = tmp_path / "release"
    outside = tmp_path / "outside"

    result = _run_layout_command(
        """
. $env:SRPSS_LAYOUT_SCRIPT
Publish-SRPSSDirectory `
    -SourcePath $env:SRPSS_SOURCE `
    -TargetPath $env:SRPSS_TARGET `
    -ReleaseRoot $env:SRPSS_RELEASE_ROOT `
    -RequiredRelativePaths @('artifact.exe') | Out-Null
""",
        source=source,
        target=outside,
        release_root=release_root,
    )

    assert result.returncode != 0
    assert "outside" in (result.stderr + result.stdout).lower()
    assert not outside.exists()


def test_build_scratch_reset_removes_stale_output_and_prunes_empty_parents(tmp_path):
    build_root = tmp_path / "build"
    product = build_root / "venv" / "reddit_helper"
    product.mkdir(parents=True)
    (product / "stale.exe").write_bytes(b"stale")

    reset = _run_layout_command(
        """
. $env:SRPSS_LAYOUT_SCRIPT
Reset-SRPSSBuildDirectory `
    -Path $env:SRPSS_TARGET `
    -BuildRoot $env:SRPSS_BUILD_ROOT | Out-Null
""",
        target=product,
        build_root=build_root,
    )

    assert reset.returncode == 0, reset.stderr
    assert product.is_dir()
    assert not (product / "stale.exe").exists()
    (product / "current.exe").write_bytes(b"current")

    cleanup = _run_layout_command(
        """
. $env:SRPSS_LAYOUT_SCRIPT
Remove-SRPSSBuildDirectory `
    -Path $env:SRPSS_TARGET `
    -BuildRoot $env:SRPSS_BUILD_ROOT
""",
        target=product,
        build_root=build_root,
    )

    assert cleanup.returncode == 0, cleanup.stderr
    assert not build_root.exists()


def test_shader_contract_is_derived_from_live_source_assets(tmp_path):
    repo_root = tmp_path / "repo"
    shader_source = repo_root / "widgets" / "spotify_visualizer" / "shaders"
    shader_source.mkdir(parents=True)
    (shader_source / "spectrum.frag").write_text("spectrum", encoding="utf-8")
    (shader_source / "bubble.frag").write_text("bubble", encoding="utf-8")

    result = _run_layout_command(
        """
. $env:SRPSS_LAYOUT_SCRIPT
@(Get-SRPSSVisualizerShaderNames -RepoRoot $env:SRPSS_REPO_ROOT) -join ','
""",
        repo_root=repo_root,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "bubble.frag,spectrum.frag"
    assert "blob.frag" not in result.stdout


def test_onedir_shader_contract_rejects_a_missing_live_shader(tmp_path):
    repo_root = tmp_path / "repo"
    shader_source = repo_root / "widgets" / "spotify_visualizer" / "shaders"
    shader_source.mkdir(parents=True)
    (shader_source / "spectrum.frag").write_text("spectrum", encoding="utf-8")
    (shader_source / "bubble.frag").write_text("bubble", encoding="utf-8")

    dist_root = tmp_path / "dist"
    shader_dist = dist_root / "widgets" / "spotify_visualizer" / "shaders"
    shader_dist.mkdir(parents=True)
    (shader_dist / "spectrum.frag").write_text("spectrum", encoding="utf-8")

    result = _run_layout_command(
        """
. $env:SRPSS_LAYOUT_SCRIPT
Assert-SRPSSOnedirVisualizerShaders `
    -RepoRoot $env:SRPSS_REPO_ROOT `
    -DistributionRoot $env:SRPSS_DIST_ROOT | Out-Null
""",
        repo_root=repo_root,
        dist_root=dist_root,
    )

    assert result.returncode != 0
    assert "bubble.frag" in (result.stdout + result.stderr)


def test_onefile_shader_contract_requires_embedded_data_declaration(tmp_path):
    repo_root = tmp_path / "repo"
    shader_source = repo_root / "widgets" / "spotify_visualizer" / "shaders"
    shader_source.mkdir(parents=True)
    (shader_source / "spectrum.frag").write_text("spectrum", encoding="utf-8")

    result = _run_layout_command(
        """
. $env:SRPSS_LAYOUT_SCRIPT
Assert-SRPSSOnefileVisualizerShaderContract `
    -RepoRoot $env:SRPSS_REPO_ROOT `
    -NuitkaArguments @('--onefile') | Out-Null
""",
        repo_root=repo_root,
    )

    assert result.returncode != 0
    assert "does not declare" in (result.stdout + result.stderr)
