"""
User-session lifecycle helpers for the Reddit queue worker.

This module keeps the low-suspicion queue-based helper model intact while
making it operationally reliable:

- secure-desktop / SYSTEM runs only queue work
- normal user-session runs self-heal the helper watcher when needed
- helper health is derived from a shared heartbeat file
- installed helpers are registered through a standard HKCU Run entry
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from core.logging.logger import get_logger
from core.windows import reddit_helper_bridge
from core.windows.reddit_helper_installer import _running_as_system

logger = get_logger(__name__)

HELPER_EXE_NAME = "SRPSS_RedditHelper.exe"
HEARTBEAT_FILE_NAME = "reddit_helper_heartbeat.json"
RUN_VALUE_NAME = "SRPSS_RedditHelper"
HELPER_HEARTBEAT_STALE_SECONDS = 10.0
HELPER_LAUNCH_COOLDOWN_SECONDS = 15.0
SESSION_HELPER_IDLE_EXIT_SECONDS = 45.0


def _signal_dir() -> Path:
    return reddit_helper_bridge.get_signal_dir()


def _queue_dir() -> Path:
    return reddit_helper_bridge.get_queue_dir()


def _base_dir() -> Path:
    return reddit_helper_bridge.get_base_dir()


def heartbeat_path() -> Path:
    return _signal_dir() / HEARTBEAT_FILE_NAME


def _launch_stamp_path() -> Path:
    return _signal_dir() / "reddit_helper_launch.json"


def _installed_helper_path() -> Path:
    return _base_dir() / "helper" / HELPER_EXE_NAME


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _repo_helper_candidates() -> list[Path]:
    root = _repo_root()
    return [
        root / "release" / "helpers" / HELPER_EXE_NAME,
        root / "release_helpers" / HELPER_EXE_NAME,
    ]


def _source_helper_command() -> Optional[list[str]]:
    if getattr(sys, "frozen", False):
        return None

    script_path = _repo_root() / "helpers" / "reddit_helper_worker.py"
    if not script_path.exists():
        return None

    python_exe = Path(sys.executable)
    if python_exe.name.lower() == "python.exe":
        pythonw = python_exe.with_name("pythonw.exe")
        if pythonw.exists():
            python_exe = pythonw

    return [
        str(python_exe),
        str(script_path),
    ]


def _scoped_watch_args(*, persistent: bool) -> list[str]:
    args = [
        "--watch",
        "--queue",
        str(_queue_dir()),
    ]
    if persistent:
        args.append("--persistent")
    else:
        args.extend(
            [
                "--owner-pid",
                str(os.getpid()),
                "--idle-exit-seconds",
                str(int(SESSION_HELPER_IDLE_EXIT_SECONDS)),
            ]
        )
    return args


def resolve_helper_command(*, persistent: bool = False) -> Optional[list[str]]:
    installed = _installed_helper_path()
    if installed.exists():
        return [str(installed), *_scoped_watch_args(persistent=True)]

    for candidate in _repo_helper_candidates():
        if candidate.exists():
            return [str(candidate), *_scoped_watch_args(persistent=persistent)]

    command = _source_helper_command()
    if not command:
        return None
    return [
        *command,
        *_scoped_watch_args(persistent=persistent),
        "--log-dir",
        str(_base_dir() / "logs"),
    ]


def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_helper_heartbeat() -> Optional[dict]:
    path = heartbeat_path()
    if not path.exists():
        return None
    data = _read_json(path)
    return data if isinstance(data, dict) else None


def is_helper_healthy(*, max_age_seconds: float = HELPER_HEARTBEAT_STALE_SECONDS) -> bool:
    data = read_helper_heartbeat()
    if not data:
        return False
    try:
        updated_at = float(data.get("updated_at") or 0.0)
    except Exception:
        return False
    if updated_at <= 0.0:
        return False
    return (time.time() - updated_at) <= max(1.0, max_age_seconds)


def _format_run_value(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def _ensure_run_entry(command: list[str]) -> bool:
    if os.name != "nt":
        return False
    if not command:
        return False
    exe_path = command[0]
    if not exe_path.lower().endswith(".exe"):
        return False

    try:
        import winreg

        desired = _format_run_value(command)
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run")
        try:
            current, _ = winreg.QueryValueEx(key, RUN_VALUE_NAME)
        except FileNotFoundError:
            current = None

        if current != desired:
            winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, desired)
            logger.info("[REDDIT-HELPER] Ensured HKCU Run entry for helper watcher")
        return True
    except Exception as exc:
        logger.warning("[REDDIT-HELPER] Failed to ensure HKCU Run entry: %s", exc, exc_info=True)
        return False


def _recent_launch_attempt() -> bool:
    stamp = _read_json(_launch_stamp_path())
    if not stamp:
        return False
    try:
        launched_at = float(stamp.get("launched_at") or 0.0)
    except Exception:
        return False
    return (time.time() - launched_at) < HELPER_LAUNCH_COOLDOWN_SECONDS


def _record_launch_attempt(*, source: str, command: list[str]) -> None:
    path = _launch_stamp_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "launched_at": time.time(),
            "source": source,
            "pid": os.getpid(),
            "command": command,
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
    except Exception as exc:
        logger.debug("[REDDIT-HELPER] Failed to record helper launch attempt: %s", exc)


def _launch_helper(command: list[str]) -> bool:
    if not command:
        return False
    try:
        cwd = str(_repo_root()) if not command[0].lower().endswith(".exe") else str(Path(command[0]).parent)
        subprocess.Popen(command, cwd=cwd)
        logger.info("[REDDIT-HELPER] Launched helper watcher: %s", command[0])
        return True
    except Exception as exc:
        logger.warning("[REDDIT-HELPER] Failed to launch helper watcher: %s", exc, exc_info=True)
        return False


def ensure_helper_runtime(*, source: str = "app_start") -> bool:
    """
    Best-effort self-healing bootstrap for the user-session helper.

    SYSTEM / Winlogon runs intentionally do nothing here. They should only
    queue work and rely on an already-running user-session helper.
    """
    if os.name != "nt":
        return False
    if _running_as_system():
        logger.debug("[REDDIT-HELPER] Skipping helper bootstrap in SYSTEM context (%s)", source)
        return False
    if not reddit_helper_bridge.is_bridge_available():
        logger.warning("[REDDIT-HELPER] Bridge unavailable; helper bootstrap skipped (%s)", source)
        return False

    command = resolve_helper_command(persistent=False)
    if not command:
        logger.warning("[REDDIT-HELPER] No helper command available for bootstrap (%s)", source)
        return False

    try:
        command_path = Path(command[0]).resolve()
        installed_path = _installed_helper_path().resolve()
    except Exception:
        command_path = Path(command[0])
        installed_path = _installed_helper_path()

    if command_path == installed_path:
        _ensure_run_entry(command)

    if is_helper_healthy():
        logger.debug("[REDDIT-HELPER] Existing helper heartbeat is healthy (%s)", source)
        return True

    if _recent_launch_attempt():
        logger.info("[REDDIT-HELPER] Recent helper launch attempt still cooling down (%s)", source)
        return False

    launched = _launch_helper(command)
    if launched:
        _record_launch_attempt(source=source, command=command)
    return launched
