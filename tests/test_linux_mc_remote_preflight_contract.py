"""The PowerShell launcher must validate the pinned *pushed* revision before running MC."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_remote_mc_capability_is_checked_before_dispatch_or_tag():
    source = (ROOT / "scripts/linux/build_from_windows.ps1").read_text(encoding="utf-8")
    preflight = source.index("# GitHub Actions builds the pushed commit")
    selection = source.index("if ($Mode -eq 'Auto')", preflight)
    dispatch = source.index("Invoke-Checked gh $dispatchArgs", selection)
    tagging = source.index("Invoke-Checked git @('push'", selection)
    assert preflight < selection < dispatch < tagging or preflight < selection < tagging < dispatch
    assert 'git show "$($remoteSha):.github/workflows/linux-build.yml"' in source
    assert 'git show "$($remoteSha):tools/linux_build.py"' in source
    assert "$Profile -eq 'mc'" in source
    assert '$hasMcWorkflow' in source and '$hasMcBuilder' in source
    assert "MC unavailable at pushed commit" in source
    assert "A temporary tag cannot turn the old screensaver workflow into an MC build" in source


def test_new_workflow_matches_mc_preflight_contract():
    workflow = (ROOT / ".github/workflows/linux-build.yml").read_text(encoding="utf-8")
    builder = (ROOT / "tools/linux_build.py").read_text(encoding="utf-8")
    for marker in ('refs/tags/linux-build/mc-', '--profile "$BUILD_PROFILE"', 'srpss-linux-mc'):
        assert marker in workflow
    for marker in ('main_mc.py', '--profile', 'PROFILES'):
        assert marker in builder
