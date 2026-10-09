from __future__ import annotations

from pathlib import Path


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
    # The top-level script delegates; installer layout is controlled by venv worker.
    build_script = (REPO_ROOT / "scripts" / "venv" / "build_reddit_helper.ps1").read_text(encoding="utf-8")
    wrapper = (REPO_ROOT / "scripts" / "build_reddit_helper.ps1").read_text(encoding="utf-8")
    installer = (REPO_ROOT / "scripts" / "SRPSS_Installer.iss").read_text(encoding="utf-8")

    assert "venv\\build_reddit_helper.ps1" in wrapper
    assert "& $worker" in wrapper
    assert '"--onedir"' in build_script
    assert '"--onefile"' not in build_script
    assert r"release\reddit_helper\*" in installer
    assert "recursesubdirs createallsubdirs" in installer
