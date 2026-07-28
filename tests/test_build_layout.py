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
        [pwsh, "-NoProfile", "-Command", command],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )


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
