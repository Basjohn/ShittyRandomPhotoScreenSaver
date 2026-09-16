from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_render_task_xml_includes_interactive_principal_and_exec_arguments():
    from tools import reddit_helper_task_harness as harness

    rendered = harness.render_task_xml(
        task_name="SRPSS_RedditHelper",
        user_id=r"TESTBOX\Basjohn",
        command=r"C:\ProgramData\SRPSS\helper\SRPSS_RedditHelper.exe",
        arguments='--watch --queue "C:\\ProgramData\\SRPSS\\url_queue"',
    )

    assert "<LogonType>InteractiveToken</LogonType>" in rendered
    assert "<RunLevel>LeastPrivilege</RunLevel>" in rendered
    assert "<Command>C:\\ProgramData\\SRPSS\\helper\\SRPSS_RedditHelper.exe</Command>" in rendered
    assert "&quot;C:\\ProgramData\\SRPSS\\url_queue&quot;" in rendered


def test_build_helper_arguments_matches_expected_shape():
    from tools import reddit_helper_task_harness as harness

    arguments = harness.build_helper_arguments(
        queue_dir=r"C:\ProgramData\SRPSS\url_queue",
        log_dir=r"C:\ProgramData\SRPSS\logs",
        signal_dir=r"C:\ProgramData\SRPSS\helper_signals",
        session_ticket=r"C:\ProgramData\SRPSS\helper_signals\reddit_helper_session.json",
        idle_exit_seconds=20,
    )

    assert '--watch' in arguments
    assert '--queue "C:\\ProgramData\\SRPSS\\url_queue"' in arguments
    assert '--session-ticket "C:\\ProgramData\\SRPSS\\helper_signals\\reddit_helper_session.json"' in arguments
    assert arguments.endswith("--idle-exit-seconds 20")


def test_installer_and_harness_have_no_retired_reddit_startup_artifacts():
    installer = (REPO_ROOT / "scripts" / "SRPSS_Installer.iss").read_text(encoding="utf-8")
    harness_source = (REPO_ROOT / "tools" / "reddit_helper_task_harness.py").read_text(encoding="utf-8")

    assert r"\SRPSS\RedditHelper" not in installer
    assert r"Software\Microsoft\Windows\CurrentVersion\Run" not in installer
    assert "DeleteLegacyHelperTask" not in installer
    assert "LEGACY_TASK_NAMES" not in harness_source
    assert "SRPSS_RedditHelper" in installer


def test_storage_recovery_harness_exercises_bounded_failure_path():
    from tools import reddit_helper_task_harness as harness

    result = harness.storage_recovery_test()

    assert result["success"] is True
    assert result["marker_independent"] is True
    assert result["recovery"]["recovered"] == 1
    assert result["log_failure_survived"] is True
    assert result["processed"] == 2
    assert len(result["receipts"]) == 2
    assert sum(result["log_sizes"].values()) <= result["log_limit_bytes"]


def test_installer_declares_minimal_programdata_permissions_without_acl_reconciler():
    installer = (REPO_ROOT / "scripts" / "SRPSS_Installer.iss").read_text(encoding="utf-8")

    assert 'Name: "{commonappdata}\\SRPSS\\helper"; Permissions: users-readexec' in installer
    assert 'Name: "{commonappdata}\\SRPSS\\url_queue"; Permissions: users-modify' in installer
    assert 'Name: "{commonappdata}\\SRPSS\\logs"; Permissions: users-modify' in installer
    assert 'Name: "{commonappdata}\\SRPSS\\helper_signals"; Permissions: users-modify' in installer
    assert 'Name: "{commonappdata}\\SRPSS\\presets"' in installer
    assert 'Name: "{commonappdata}\\SRPSS\\themes"' in installer
    assert 'Name: "{commonappdata}\\SRPSS\\sounds"' in installer
    assert "ReconcileRedditHelperStorageAcls" not in installer
    assert "ApplyRedditHelperAcl" not in installer
    assert "/C /Q" not in installer


def test_helper_packaging_is_installer_laid_ondir_not_self_extracting_onefile():
    build_script = (REPO_ROOT / "scripts" / "build_reddit_helper.ps1").read_text(encoding="utf-8")
    installer = (REPO_ROOT / "scripts" / "SRPSS_Installer.iss").read_text(encoding="utf-8")

    assert '"--onedir"' in build_script
    assert '"--onefile"' not in build_script
    assert r"release\reddit_helper\*" in installer
    assert "recursesubdirs createallsubdirs" in installer


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only scheduled task smoke test")
def test_scheduled_task_smoke_test_via_harness_when_enabled(tmp_path):
    if os.environ.get("SRPSS_RUN_TASK_SMOKE_TEST") != "1":
        pytest.skip("Set SRPSS_RUN_TASK_SMOKE_TEST=1 to run the real scheduled-task smoke test")

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "reddit_helper_task_harness.py"),
            "--action",
            "smoke-test",
            "--task-name",
            f"SRPSS_TaskHarness_{os.getpid()}",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["stamp_exists"] is True
    assert payload["register"]["returncode"] == 0
    assert payload["query"]["returncode"] == 0
    assert payload["run"]["returncode"] == 0
