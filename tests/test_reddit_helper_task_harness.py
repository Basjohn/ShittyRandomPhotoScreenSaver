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
