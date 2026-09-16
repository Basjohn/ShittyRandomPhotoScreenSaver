"""
User-session lifecycle helpers for the Reddit queue worker.

This module keeps the low-suspicion queue-based helper model intact while
making it operationally reliable:

- secure-desktop / SYSTEM runs queue work and request a Windows-scheduled
  interactive helper start
- the helper itself lives only for the active saver session / queued handoff
- helper health is derived from a shared heartbeat file plus a saver-owned
  session ticket in ProgramData
- the canonical root scheduled task is the only packaged startup/launch authority
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import ctypes
from pathlib import Path
from typing import Optional

from core.build_profile import is_diagnostic_build
from core.mc import is_mc_build
from core.logging.logger import get_logger
from core.windows import reddit_helper_bridge
from core.windows.reddit_helper_installer import _log_helper_event, _running_as_system
from core.windows.reddit_helper_storage import read_json_bounded

logger = get_logger(__name__)

HELPER_EXE_NAME = "SRPSS_RedditHelper.exe"
HEARTBEAT_FILE_NAME = "reddit_helper_heartbeat.json"
HELPER_HEARTBEAT_STALE_SECONDS = 10.0
HELPER_LAUNCH_COOLDOWN_SECONDS = 15.0
SESSION_HELPER_IDLE_EXIT_SECONDS = 45.0
SESSION_HELPER_SHUTDOWN_PREFIX = "reddit_helper_shutdown_"
SESSION_TICKET_FILE_NAME = "reddit_helper_session.json"
SCHEDULED_TASK_NAME = r"SRPSS_RedditHelper"
SESSION_TICKET_REFRESH_SECONDS = 10.0
SESSION_TICKET_VALID_FOR_SECONDS = 25.0


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


def session_ticket_path() -> Path:
    return _signal_dir() / SESSION_TICKET_FILE_NAME


def _shutdown_request_path(owner_pid: int) -> Path:
    owner_pid = max(0, int(owner_pid or 0))
    return _signal_dir() / f"{SESSION_HELPER_SHUTDOWN_PREFIX}{owner_pid}.json"


def _queue_has_pending_entries() -> bool:
    """Return True when the ProgramData helper queue still contains work."""
    queue_dir = _queue_dir()
    try:
        if not queue_dir.exists():
            return False
        for pattern in ("*.json", "*.retry"):
            for path in queue_dir.glob(pattern):
                if path.is_file():
                    return True
    except Exception:
        logger.debug("[REDDIT-HELPER] Failed to inspect helper queue for pending entries", exc_info=True)
    return False


def _installed_helper_path() -> Path:
    return _base_dir() / "helper" / HELPER_EXE_NAME


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _repo_helper_candidates() -> list[Path]:
    root = _repo_root()
    return [root / "release" / "reddit_helper" / HELPER_EXE_NAME]


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


def _scoped_watch_args(
    *,
    owner_pid: int | None = None,
    idle_exit_seconds: float | None = None,
) -> list[str]:
    resolved_owner_pid = int(owner_pid or os.getpid())
    resolved_idle_exit = int(
        max(1.0, float(idle_exit_seconds or SESSION_HELPER_IDLE_EXIT_SECONDS))
    )
    return [
        "--watch",
        "--queue",
        str(_queue_dir()),
        "--owner-pid",
        str(resolved_owner_pid),
        "--idle-exit-seconds",
        str(resolved_idle_exit),
    ]


def resolve_helper_command(
    *,
    owner_pid: int | None = None,
    idle_exit_seconds: float | None = None,
) -> Optional[list[str]]:
    installed = _installed_helper_path()
    if installed.exists():
        return [
            str(installed),
            *_scoped_watch_args(
                owner_pid=owner_pid,
                idle_exit_seconds=idle_exit_seconds,
            ),
        ]

    for candidate in _repo_helper_candidates():
        if candidate.exists():
            return [
                str(candidate),
                *_scoped_watch_args(
                    owner_pid=owner_pid,
                    idle_exit_seconds=idle_exit_seconds,
                ),
            ]

    command = _source_helper_command()
    if not command:
        return None
    return [
        *command,
        *_scoped_watch_args(
            owner_pid=owner_pid,
            idle_exit_seconds=idle_exit_seconds,
        ),
        "--log-dir",
        str(_base_dir() / "logs"),
    ]


def _read_json(path: Path) -> Optional[dict]:
    try:
        payload = read_json_bounded(path)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def refresh_session_ticket(
    *,
    source: str,
    valid_for_seconds: float = SESSION_TICKET_VALID_FOR_SECONDS,
) -> bool:
    """Refresh the saver-owned helper session ticket in ProgramData.

    The helper uses this as a benign keepalive signal while the saver is still
    active. Once refreshes stop, the helper is free to self-expire after the
    queue stays idle.
    """
    path = session_ticket_path()
    try:
        now = time.time()
        payload = {
            "updated_at": now,
            "expires_at": now + max(5.0, float(valid_for_seconds)),
            "source": source,
            "pid": os.getpid(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return True
    except Exception as exc:
        logger.warning("[REDDIT-HELPER] Failed to refresh session ticket: %s", exc, exc_info=True)
        return False


def clear_session_ticket(*, source: str = "runtime_cleanup") -> bool:
    path = session_ticket_path()
    try:
        if not path.exists():
            return False
        path.unlink()
        logger.info("[REDDIT-HELPER] Cleared helper session ticket (%s)", source)
        return True
    except Exception as exc:
        logger.warning("[REDDIT-HELPER] Failed to clear session ticket: %s", exc, exc_info=True)
        return False


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


def _heartbeat_pid(data: dict | None) -> int:
    if not isinstance(data, dict):
        return 0
    try:
        return int(data.get("pid") or 0)
    except Exception:
        return 0


def _heartbeat_owner_pid(data: dict | None) -> int:
    if not isinstance(data, dict):
        return 0
    try:
        return int(data.get("owner_pid") or 0)
    except Exception:
        return 0


def _heartbeat_persistent(data: dict | None) -> bool:
    if not isinstance(data, dict):
        return False
    return bool(data.get("persistent"))


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259

        handle = None
        try:
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if not handle:
                return False

            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == STILL_ACTIVE
        except Exception:
            return False
        finally:
            if handle:
                try:
                    ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
                except Exception:
                    pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _terminate_process(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        PROCESS_TERMINATE = 0x0001
        handle = None
        try:
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if not handle:
                raise OSError(f"OpenProcess failed for pid={pid}")
            if not kernel32.TerminateProcess(handle, 1):
                raise OSError(f"TerminateProcess failed for pid={pid}")
            return True
        except Exception as exc:
            logger.warning("[REDDIT-HELPER] Failed to terminate stale helper pid=%s: %s", pid, exc, exc_info=True)
            return False
        finally:
            if handle:
                try:
                    ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
                except Exception:
                    pass
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except Exception as exc:
        logger.warning("[REDDIT-HELPER] Failed to terminate stale helper pid=%s: %s", pid, exc, exc_info=True)
        return False


def reap_stale_helper() -> bool:
    """Terminate a heartbeat-stale helper process when it is clearly unhealthy."""
    data = read_helper_heartbeat()
    if not data or is_helper_healthy():
        return False

    pid = _heartbeat_pid(data)
    if pid <= 0 or not _process_alive(pid):
        return False

    terminated = _terminate_process(pid)
    if terminated:
        logger.warning("[REDDIT-HELPER] Terminated stale helper watcher pid=%s", pid)
    return terminated


def request_session_helper_shutdown(*, source: str = "app_exit", owner_pid: int | None = None) -> bool:
    """Signal a session-scoped helper watcher to exit promptly.

    This is a best-effort fast path for normal graceful shutdown. We still keep
    owner-pid + idle-exit handling in the worker as the hard-kill fallback for
    Winlogon / abrupt process termination.
    """
    if os.name != "nt":
        return False

    heartbeat = read_helper_heartbeat()
    if not heartbeat:
        return False
    if _heartbeat_persistent(heartbeat):
        return False

    expected_owner_pid = int(owner_pid or os.getpid())
    heartbeat_owner_pid = _heartbeat_owner_pid(heartbeat)
    if heartbeat_owner_pid <= 0 or heartbeat_owner_pid != expected_owner_pid:
        return False

    if _queue_has_pending_entries():
        logger.info(
            "[REDDIT-HELPER] Skipping session helper shutdown because queue still has pending entries "
            "(owner_pid=%s, source=%s)",
            expected_owner_pid,
            source,
        )
        return False

    path = _shutdown_request_path(expected_owner_pid)
    payload = {
        "requested_at": time.time(),
        "source": source,
        "owner_pid": expected_owner_pid,
        "request_pid": os.getpid(),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        logger.info("[REDDIT-HELPER] Requested session-scoped helper shutdown (owner_pid=%s, source=%s)", expected_owner_pid, source)
        return True
    except Exception as exc:
        logger.warning("[REDDIT-HELPER] Failed to request helper shutdown: %s", exc, exc_info=True)
        return False


def _run_helper_scheduled_task(*, source: str) -> bool:
    """Ask the canonical Task Scheduler entry to start the helper on demand."""
    if os.name != "nt":
        return False

    task_name = SCHEDULED_TASK_NAME
    schtasks_path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "schtasks.exe"
    command = [str(schtasks_path), "/Run", "/TN", task_name]
    kwargs: dict[str, object] = {
        "capture_output": True,
        "text": True,
        "timeout": 15,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }
    try:
        _log_helper_event(
            f"task run request source={source} task={task_name!r} command={command!r}"
        )
        result = subprocess.run(command, **kwargs)
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if result.returncode == 0:
            logger.info(
                "[REDDIT-HELPER] Scheduled task run accepted (%s via %s)",
                source,
                task_name,
            )
            _log_helper_event(
                f"task run accepted source={source} task={task_name!r} stdout={stdout!r}"
            )
            return True
        logger.warning(
            "[REDDIT-HELPER] Scheduled task run failed (%s via %s) rc=%s stdout=%s stderr=%s",
            source,
            task_name,
            result.returncode,
            stdout,
            stderr,
        )
        _log_helper_event(
            f"task run failed source={source} task={task_name!r} rc={result.returncode} stdout={stdout!r} stderr={stderr!r}"
        )
    except Exception as exc:
        logger.warning(
            "[REDDIT-HELPER] Scheduled task run errored (%s via %s): %s",
            source,
            task_name,
            exc,
            exc_info=True,
        )
        _log_helper_event(
            f"task run exception source={source} task={task_name!r} error={exc!r}"
        )
    return False


def _should_prefer_scheduled_task(*, source: str, running_as_system: bool) -> bool:
    if os.name != "nt":
        return False
    if running_as_system:
        return True
    normalized = str(source or "").strip().lower()
    return normalized.startswith("run_session")


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
        _log_helper_event(f"launch attempt cwd={cwd} command={command!r}")
        kwargs: dict[str, object] = {
            "cwd": cwd,
        }
        if os.name == "nt":
            creationflags = 0
            creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
            creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
            kwargs["creationflags"] = creationflags
            kwargs["close_fds"] = True
        subprocess.Popen(command, **kwargs)
        logger.info("[REDDIT-HELPER] Launched helper watcher: %s", command[0])
        _log_helper_event(f"launch accepted command={command!r}")
        return True
    except Exception as exc:
        logger.warning("[REDDIT-HELPER] Failed to launch helper watcher: %s", exc, exc_info=True)
        _log_helper_event(f"launch failed error={exc!r} command={command!r}")
        return False


def ensure_helper_runtime(
    *,
    source: str = "app_start",
    owner_pid: int | None = None,
    idle_exit_seconds: float | None = None,
    allow_system: bool = False,
) -> bool:
    """
    Best-effort bootstrap for the user-session helper.

    Modern shipped SCR flow should prefer the Windows scheduled-task authority
    from secure-desktop / SYSTEM contexts so the helper starts on the real user
    desktop instead of as a saver-owned child process. Direct process launch is
    retained only for non-SYSTEM/dev contexts.
    """
    if is_diagnostic_build():
        logger.debug(
            "[REDDIT-HELPER] Skipping helper bootstrap in diagnostic build (%s)",
            source,
        )
        return False
    if os.name != "nt":
        _log_helper_event(f"bootstrap skipped non-windows source={source}")
        return False
    running_as_system = _running_as_system()
    if running_as_system and not allow_system:
        logger.debug("[REDDIT-HELPER] Skipping helper bootstrap in SYSTEM context (%s)", source)
        _log_helper_event(f"bootstrap skipped system-disallowed source={source}")
        return False
    if is_mc_build():
        logger.debug("[REDDIT-HELPER] Skipping helper bootstrap in MC build (%s)", source)
        _log_helper_event(f"bootstrap skipped mc-build source={source}")
        return False
    if not reddit_helper_bridge.is_bridge_available():
        logger.warning("[REDDIT-HELPER] Bridge unavailable; helper bootstrap skipped (%s)", source)
        _log_helper_event(f"bootstrap skipped bridge-unavailable source={source}")
        return False

    if is_helper_healthy():
        logger.debug("[REDDIT-HELPER] Existing helper heartbeat is healthy (%s)", source)
        _log_helper_event(f"bootstrap reused healthy-helper source={source}")
        return True

    stale_reaped = reap_stale_helper()

    if _recent_launch_attempt() and not stale_reaped:
        logger.info("[REDDIT-HELPER] Recent helper launch attempt still cooling down (%s)", source)
        _log_helper_event(f"bootstrap cooled-down source={source}")
        return False

    if _should_prefer_scheduled_task(source=source, running_as_system=running_as_system):
        launched = _run_helper_scheduled_task(source=source)
        if launched:
            _record_launch_attempt(
                source=source,
                command=["schtasks.exe", "/Run", "/TN", SCHEDULED_TASK_NAME],
            )
            _log_helper_event(f"bootstrap task-launched source={source}")
        else:
            _log_helper_event(f"bootstrap task-launch-failed source={source}")
        return launched

    command = resolve_helper_command(
        owner_pid=owner_pid,
        idle_exit_seconds=idle_exit_seconds,
    )
    if not command:
        logger.warning("[REDDIT-HELPER] No helper command available for bootstrap (%s)", source)
        _log_helper_event(f"bootstrap failed no-command source={source}")
        return False

    launched = _launch_helper(command)
    if launched:
        _record_launch_attempt(source=source, command=command)
        _log_helper_event(f"bootstrap launched source={source}")
    else:
        _log_helper_event(f"bootstrap launch-failed source={source}")
    return launched
