r"""
User-session Reddit helper worker.

This script runs inside the interactive user session (started on demand via a
registered Windows scheduled task). It watches the ProgramData queue populated
by the Winlogon screensaver build and opens each deferred Reddit URL using the
user's default browser.

Modes:
- Default       : Continuous polling loop (watcher mode).
                  Polls every ``--poll-interval`` seconds, opens URLs, then
                  sleeps. Exits cleanly on SIGINT/SIGTERM.
- ``--one-shot``: Drains queue once and exits.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import logging
import os
import subprocess
import sys
import time
import webbrowser
from ctypes import wintypes
from pathlib import Path
from typing import Any, Dict, Iterator
from urllib.parse import urlparse

from core.logging.logger import get_logger
from core.constants.timing import (
    RETRY_BASE_DELAY_MS,
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_DELAY_MS,
)
from core.windows.reddit_helper_runtime import (
    HEARTBEAT_FILE_NAME,
    SESSION_HELPER_SHUTDOWN_PREFIX,
    remove_helper_run_entry,
)

logger = get_logger(__name__)

DEFAULT_PROGRAM_DATA = Path(os.getenv("PROGRAMDATA", r"C:\ProgramData"))
DEFAULT_BASE = DEFAULT_PROGRAM_DATA / "SRPSS"
DEFAULT_QUEUE = DEFAULT_BASE / "url_queue"
DEFAULT_LOG_DIR = DEFAULT_BASE / "logs"
DEFAULT_SIGNAL_DIR = DEFAULT_BASE / "helper_signals"

DEFAULT_MAX_BATCH = 50
DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_IDLE_EXIT_SECONDS = 45.0

WINDOW_POLL_INTERVAL = 0.25
BROWSER_FOREGROUND_TIMEOUT = 5.0
SHELL_READY_TIMEOUT = 12.0
SHELL_READY_SETTLE_SECONDS = 0.75
SHELL_NOT_READY_DEFER_SECONDS = 2.0
SESSION_ACTIVE_DEFER_SECONDS = 1.0
DEFAULT_SESSION_TICKET = DEFAULT_SIGNAL_DIR / "reddit_helper_session.json"

_NO_WINDOW_FLAG = getattr(subprocess, "CREATE_NO_WINDOW", 0)

OPEN_URL_MAX_AGE_SECONDS = 3600.0
OPEN_SETTINGS_MAX_AGE_SECONDS = 900.0

WATCHER_MUTEX_NAME = r"Local\SRPSS_RedditHelper_Watcher"
_ERROR_ALREADY_EXISTS = 183

BROWSER_WINDOW_CLASSES = {
    "chrome_widgetwin_1",
    "chrome_widgetwin_0",
    "applicationframewindow",
    "mozillawindowclass",
    "ieframe",
}


class ShellNotReadyError(RuntimeError):
    """Raised when the helper is alive but the interactive shell is not ready yet."""


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]


def configure_logging(log_dir: Path, verbose: bool) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "reddit_helper.log"

    handlers: list[logging.Handler] = [
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    if verbose:
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [helper] %(levelname)s - %(message)s",
        handlers=handlers,
    )


_watcher_running = True


def _signal_handler(signum, frame):  # noqa: ARG001
    global _watcher_running
    _watcher_running = False
    logging.info("Shutdown signal received (sig=%s)", signum)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SRPSS Reddit helper worker")

    parser.add_argument(
        "--queue",
        type=Path,
        default=DEFAULT_QUEUE,
        help="Queue directory containing deferred URL JSON files",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Directory for helper logs",
    )
    parser.add_argument(
        "--signal-dir",
        type=Path,
        default=DEFAULT_SIGNAL_DIR,
        help="Directory for helper heartbeat/session signal files",
    )
    parser.add_argument(
        "--max-batch",
        type=int,
        default=DEFAULT_MAX_BATCH,
        help="Maximum number of URLs to process per run",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose console logging",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--watch",
        action="store_true",
        help="Run in continuous watcher mode (default)",
    )
    mode_group.add_argument(
        "--one-shot",
        action="store_true",
        help="Drain queue once and exit",
    )

    parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Seconds between queue polls in watch mode (default: {DEFAULT_POLL_INTERVAL:.1f})",
    )
    parser.add_argument(
        "--persistent",
        action="store_true",
        help="Keep the watcher alive independently of the launching app/session owner",
    )
    parser.add_argument(
        "--owner-pid",
        type=int,
        default=0,
        help="Owner process id for session-scoped watcher shutdown",
    )
    parser.add_argument(
        "--idle-exit-seconds",
        type=float,
        default=DEFAULT_IDLE_EXIT_SECONDS,
        help="Seconds to stay alive after owner exit once the queue is idle",
    )
    parser.add_argument(
        "--session-ticket",
        type=Path,
        default=DEFAULT_SESSION_TICKET,
        help="ProgramData session ticket file refreshed by the saver while active",
    )

    args = parser.parse_args()

    # Default mode is watcher mode unless --one-shot was explicitly requested.
    if not args.watch and not args.one_shot:
        args.watch = True

    return args


def iter_queue_files(queue_dir: Path) -> Iterator[Path]:
    paths = {
        path.name.lower(): path
        for pattern in ("*.json", "*.retry")
        for path in queue_dir.glob(pattern)
        if path.is_file()
    }
    for path in sorted(paths.values(), key=lambda item: item.name.lower()):
        if path.is_file():
            yield path


def _canonical_json_path(entry_path: Path) -> Path:
    return entry_path.with_suffix(".json")


def _heartbeat_path(signal_dir: Path) -> Path:
    return signal_dir / HEARTBEAT_FILE_NAME


def _shutdown_request_path(signal_dir: Path, owner_pid: int) -> Path:
    owner_pid = max(0, int(owner_pid or 0))
    return signal_dir / f"{SESSION_HELPER_SHUTDOWN_PREFIX}{owner_pid}.json"


def _write_heartbeat(signal_dir: Path, queue_dir: Path, poll_interval: float) -> None:
    _write_heartbeat_with_lifecycle(
        signal_dir,
        queue_dir,
        poll_interval=poll_interval,
        persistent=False,
        owner_pid=0,
    )


def _write_heartbeat_with_lifecycle(
    signal_dir: Path,
    queue_dir: Path,
    *,
    poll_interval: float,
    persistent: bool,
    owner_pid: int,
) -> None:
    payload = {
        "updated_at": time.time(),
        "pid": os.getpid(),
        "queue_dir": str(queue_dir),
        "poll_interval": float(poll_interval),
        "persistent": bool(persistent),
        "owner_pid": int(owner_pid or 0),
    }
    path = _heartbeat_path(signal_dir)
    tmp_path = path.with_suffix(".tmp")
    try:
        signal_dir.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(payload), encoding="utf-8")
        tmp_path.replace(path)
    except Exception as exc:
        logging.debug("Failed to write helper heartbeat: %s", exc)
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


def _read_session_ticket(path: Path) -> Dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _session_ticket_active(path: Path | None, *, now: float | None = None) -> bool:
    if path is None or not path.exists():
        return False
    payload = _read_session_ticket(path)
    if not isinstance(payload, dict):
        return False
    try:
        expires_at = float(payload.get("expires_at") or 0.0)
    except Exception:
        return False
    if expires_at <= 0.0:
        return False
    return expires_at > (time.time() if now is None else float(now))


def _write_entry_payload(target_path: Path, payload: Dict[str, Any]) -> None:
    tmp_path = target_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload), encoding="utf-8")
    tmp_path.replace(target_path)


def _acquire_watcher_singleton(name: str = WATCHER_MUTEX_NAME) -> tuple[object | None, bool]:
    """Acquire the watcher singleton for this user session.

    Returns ``(handle, acquired)``. If singleton acquisition fails unexpectedly,
    we allow the watcher to continue rather than breaking URL handling.
    """
    if os.name != "nt":
        return None, True

    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.CreateMutexW(None, False, name)
        if not handle:
            logging.warning("Watcher singleton creation failed; continuing without mutex")
            return None, True

        already_exists = kernel32.GetLastError() == _ERROR_ALREADY_EXISTS
        if already_exists:
            kernel32.CloseHandle(handle)
            return None, False

        return handle, True
    except Exception:
        logging.warning("Watcher singleton acquisition failed; continuing without mutex", exc_info=True)
        return None, True


def _release_watcher_singleton(handle: object | None) -> None:
    if handle is None or os.name != "nt":
        return
    try:
        ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
    except Exception:
        logging.debug("Watcher singleton release failed", exc_info=True)


def _schedule_retry(entry_path: Path, data: Dict[str, Any], *, error: str) -> None:
    payload = dict(data)
    retry_count = int(payload.get("retry_count") or 0) + 1
    payload["retry_count"] = retry_count
    payload["last_error"] = error
    delay_ms = min(RETRY_BASE_DELAY_MS * (2 ** max(0, retry_count - 1)), RETRY_MAX_DELAY_MS)
    payload["next_attempt_ts"] = time.time() + (delay_ms / 1000.0)

    if retry_count >= RETRY_MAX_ATTEMPTS:
        failed_path = entry_path.with_suffix(".failed")
        _write_entry_payload(failed_path, payload)
        if failed_path != entry_path:
            entry_path.unlink(missing_ok=True)
        logging.error(
            "Queue entry exceeded max retry attempts (%d): %s",
            retry_count,
            failed_path.name,
        )
        return

    retry_path = _canonical_json_path(entry_path)
    _write_entry_payload(retry_path, payload)
    if retry_path != entry_path:
        entry_path.unlink(missing_ok=True)

    logging.info(
        "Retry scheduled for %s in %.1fs (attempt=%d)",
        retry_path.name,
        delay_ms / 1000.0,
        retry_count,
    )


def _retry_ready(data: Dict[str, Any]) -> bool:
    try:
        next_attempt_ts = float(data.get("next_attempt_ts") or 0.0)
    except Exception:
        return True
    if next_attempt_ts <= 0.0:
        return True
    return time.time() >= next_attempt_ts


def _clear_retry_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(data)
    payload.pop("retry_count", None)
    payload.pop("last_error", None)
    payload.pop("next_attempt_ts", None)
    return payload


def _entry_not_before_ready(data: Dict[str, Any]) -> bool:
    try:
        not_before_ts = float(data.get("not_before_ts") or 0.0)
    except Exception:
        return True
    if not_before_ts <= 0.0:
        return True
    return time.time() >= not_before_ts


def _defer_entry(entry_path: Path, data: Dict[str, Any], *, delay_seconds: float, reason: str) -> None:
    payload = dict(data)
    payload["not_before_ts"] = max(
        float(payload.get("not_before_ts") or 0.0),
        time.time() + max(0.5, float(delay_seconds or 0.0)),
    )
    payload["defer_reason"] = reason or "deferred"
    payload["deferred_at"] = time.time()

    deferred_path = _canonical_json_path(entry_path)
    _write_entry_payload(deferred_path, payload)
    if deferred_path != entry_path:
        entry_path.unlink(missing_ok=True)

    logging.info(
        "Deferred %s for %.1fs (%s)",
        deferred_path.name,
        max(0.5, float(delay_seconds or 0.0)),
        reason or "deferred",
    )


def _is_process_alive(pid: int) -> bool:
    """Windows-safe process existence check.

    Avoids os.kill(pid, 0) on Windows because that can raise WinError 6 /
    SystemError in packaged/background contexts.
    """
    if pid <= 0:
        return False

    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return True
        return True

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259

    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return False

        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass
    except Exception:
        return False


def _queue_has_pending_entries(queue_dir: Path) -> bool:
    return any(iter_queue_files(queue_dir))


def _evaluate_owner_idle_exit(
    queue_dir: Path,
    *,
    owner_pid: int,
    idle_exit_seconds: float,
    idle_since: float | None,
    persistent: bool,
    session_ticket_path: Path | None = None,
    now: float | None = None,
) -> tuple[bool, float | None]:
    if persistent or idle_exit_seconds <= 0.0:
        return False, None

    now = time.time() if now is None else now

    if _session_ticket_active(session_ticket_path, now=now):
        return False, None

    owner_alive = False
    try:
        if owner_pid > 0:
            owner_alive = _is_process_alive(owner_pid)
    except Exception:
        owner_alive = False

    if owner_alive:
        return False, None

    if _queue_has_pending_entries(queue_dir):
        return False, None

    idle_since = idle_since or now
    return (now - idle_since) >= idle_exit_seconds, idle_since


def _consume_shutdown_request(signal_dir: Path, *, owner_pid: int, persistent: bool) -> bool:
    if persistent or owner_pid <= 0:
        return False

    request_path = _shutdown_request_path(signal_dir, owner_pid)
    if not request_path.exists():
        return False

    try:
        request_path.unlink(missing_ok=True)
    except Exception:
        logging.debug("Failed to clear helper shutdown request: %s", request_path, exc_info=True)

    logging.info("Watcher received explicit session shutdown request (owner_pid=%s)", owner_pid)
    return True


def _action_error(action: str) -> str:
    return f"{action or 'unknown'} failed"


def _entry_is_expired(data: Dict[str, Any], *, action: str) -> bool:
    try:
        timestamp = float(data.get("timestamp") or 0.0)
    except Exception:
        return False
    if timestamp <= 0.0:
        return False

    max_age = OPEN_URL_MAX_AGE_SECONDS if action == "open_url" else OPEN_SETTINGS_MAX_AGE_SECONDS
    return (time.time() - timestamp) > max_age


def open_url(url: str) -> bool:
    if not url:
        return False

    if not _wait_for_user_shell_ready():
        raise ShellNotReadyError("user shell not ready")

    # Prefer the native Windows shell association path in the helper.
    # The packaged helper intentionally avoids Qt runtime baggage, while MC
    # already has its own direct QDesktopServices path inside the main app.
    try:
        os.startfile(url)  # type: ignore[attr-defined]
        logging.info("Shell launch request accepted via os.startfile: %s", url)
        return True
    except Exception as exc:
        logging.debug("os.startfile failed (%s), trying QDesktopServices fallback: %s", exc, url)

    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices, QGuiApplication

        app = QGuiApplication.instance()
        created_app = False
        if app is None:
            app = QGuiApplication([sys.argv[0]])
            created_app = True
        opened = bool(QDesktopServices.openUrl(QUrl(url)))
        if opened:
            logging.info("Shell launch request accepted via QDesktopServices: %s", url)
            return True
        logging.debug("QDesktopServices.openUrl returned False for URL: %s", url)
    except Exception as exc:
        logging.debug("QDesktopServices fallback failed for %s: %s", url, exc)
    finally:
        try:
            if created_app and app is not None:
                app.quit()
        except Exception:
            pass

    # Keep webbrowser as the last-resort fallback only.
    try:
        result = webbrowser.open(url)
        if result:
            logging.info("Shell launch request accepted via webbrowser.open: %s", url)
            return True
        logging.warning("webbrowser.open returned False for URL: %s", url)
        return False
    except Exception as exc:
        logging.error("open_url failed for %s: %s", url, exc)
        return False


def _shell_window_present() -> bool:
    if os.name != "nt":
        return True
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        shell_hwnd = user32.GetShellWindow()
        shell_tray = user32.FindWindowW("Shell_TrayWnd", None)
        progman = user32.FindWindowW("Progman", None)
        worker_tray = user32.FindWindowW("WorkerW", None)
        return bool(shell_hwnd or shell_tray or progman or worker_tray)
    except Exception:
        return False


def _wait_for_user_shell_ready(
    timeout_seconds: float = SHELL_READY_TIMEOUT,
    *,
    settle_seconds: float = SHELL_READY_SETTLE_SECONDS,
) -> bool:
    """Best-effort wait for Explorer/user shell readiness after secure-desktop exit."""
    if os.name != "nt":
        return True

    deadline = time.time() + max(1.0, float(timeout_seconds))
    stable_since: float | None = None
    while time.time() < deadline:
        if _shell_window_present():
            stable_since = stable_since or time.time()
            if (time.time() - stable_since) >= max(0.0, float(settle_seconds)):
                return True
        else:
            stable_since = None
        time.sleep(0.5)
    return False


def _hide_own_window() -> None:
    """Hide the helper process window if any transient console is created."""
    if sys.platform != "win32":
        return
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception as exc:
        logger.debug("[REDDIT] Exception suppressed while hiding helper window: %s", exc)


def process_queue(
    queue_dir: Path,
    max_batch: int,
    signal_dir: Path,
    session_ticket_path: Path | None = None,
) -> tuple[int, bool]:
    processed = 0
    opened_url = False
    seen_tokens: set[str] = set()
    seen_urls: set[str] = set()

    for entry_path in iter_queue_files(queue_dir):
        if processed >= max_batch:
            break

        try:
            data = json.loads(entry_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.warning("Failed to parse %s: %s", entry_path.name, exc)
            try:
                entry_path.rename(entry_path.with_suffix(".corrupt"))
            except Exception:
                logging.debug("Failed to rename corrupt queue entry: %s", entry_path, exc_info=True)
            continue

        if not _retry_ready(data):
            continue

        if not _entry_not_before_ready(data):
            continue

        data = _clear_retry_metadata(data)

        token = str(data.get("token") or "").strip()
        url = str(data.get("url") or "").strip()

        # Suppress duplicates within the same processing batch. Prefer token-based
        # dedupe, then fall back to URL dedupe when token is missing.
        if token:
            if token in seen_tokens:
                logging.info("Skipping duplicate queue token in batch: %s (%s)", token, entry_path.name)
                entry_path.unlink(missing_ok=True)
                processed += 1
                continue
            seen_tokens.add(token)
        elif url:
            if url in seen_urls:
                logging.info("Skipping duplicate queue URL in batch: %s (%s)", url, entry_path.name)
                entry_path.unlink(missing_ok=True)
                processed += 1
                continue
            seen_urls.add(url)

        action = str(data.get("action") or "open_url").strip().lower()

        if action == "open_url" and _session_ticket_active(session_ticket_path):
            _defer_entry(
                entry_path,
                data,
                delay_seconds=SESSION_ACTIVE_DEFER_SECONDS,
                reason="session_active",
            )
            logging.info(
                "Deferring URL launch while saver session ticket is still active: %s",
                data.get("url") or "",
            )
            processed += 1
            continue

        if _entry_is_expired(data, action=action):
            expired_path = entry_path.with_suffix(".expired")
            _write_entry_payload(expired_path, data)
            if expired_path != entry_path:
                entry_path.unlink(missing_ok=True)
            logging.warning("Queue entry expired without being handled: %s", expired_path.name)
            processed += 1
            continue

        success = False
        error = _action_error(action)
        defer_seconds: float | None = None

        if action == "open_url":
            success, error, defer_seconds = _handle_open_url(data)
            if success:
                opened_url = True
        elif action == "open_settings":
            success = _handle_open_settings(data, signal_dir)
        else:
            logging.warning("Unknown helper action '%s' in %s", action, entry_path.name)
            error = f"unknown action: {action}"

        if success:
            entry_path.unlink(missing_ok=True)
        elif defer_seconds is not None:
            _defer_entry(entry_path, data, delay_seconds=defer_seconds, reason=error)
        else:
            _schedule_retry(entry_path, data, error=error)

        processed += 1

    return processed, opened_url


def main() -> int:
    import signal as _signal

    args = parse_args()
    _hide_own_window()

    args.queue.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_dir, args.verbose)

    if args.watch and not args.persistent and args.owner_pid <= 0:
        try:
            if remove_helper_run_entry(source="legacy_startup_watcher"):
                logging.info("Removed legacy login-start helper registration")
        except Exception:
            logging.debug("Legacy HKCU Run cleanup failed inside helper", exc_info=True)

    signal_dir = args.signal_dir
    try:
        signal_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.debug("[REDDIT] Failed to ensure signal dir %s: %s", signal_dir, exc)

    _write_heartbeat_with_lifecycle(
        signal_dir,
        args.queue,
        poll_interval=args.poll_interval if args.watch else 0.0,
        persistent=args.persistent,
        owner_pid=args.owner_pid,
    )

    if args.watch:
        _signal.signal(_signal.SIGINT, _signal_handler)
        _signal.signal(_signal.SIGTERM, _signal_handler)
        return _run_watcher(
            args.queue,
            max_batch=args.max_batch,
            signal_dir=signal_dir,
            poll_interval=args.poll_interval,
            persistent=args.persistent,
            owner_pid=args.owner_pid,
            idle_exit_seconds=args.idle_exit_seconds,
            session_ticket_path=args.session_ticket,
        )

    logging.info("Helper started one-shot (queue=%s)", args.queue)
    processed, _opened_url = process_queue(args.queue, args.max_batch, signal_dir)
    logging.info("Helper finished (processed=%d)", processed)
    return 0


def _run_watcher(
    queue_dir: Path,
    max_batch: int,
    signal_dir: Path,
    poll_interval: float,
    *,
    persistent: bool = False,
    owner_pid: int = 0,
    idle_exit_seconds: float = 0.0,
    session_ticket_path: Path | None = None,
) -> int:
    """Continuous watcher loop — polls queue, opens URLs, sleeps."""
    global _watcher_running

    poll_interval = max(0.5, float(poll_interval or DEFAULT_POLL_INTERVAL))
    idle_exit_seconds = max(0.0, float(idle_exit_seconds or 0.0))

    singleton_handle, acquired = _acquire_watcher_singleton()
    if not acquired:
        logging.info("Watcher singleton already active; exiting duplicate watcher")
        return 0

    logging.info(
        "Watcher started (queue=%s, poll=%.1fs, persistent=%s, owner_pid=%s, idle_exit=%.1fs, session_ticket=%s)",
        queue_dir,
        poll_interval,
        persistent,
        owner_pid or 0,
        idle_exit_seconds,
        session_ticket_path,
    )

    owner_idle_since: float | None = None

    try:
        while _watcher_running:
            try:
                _write_heartbeat_with_lifecycle(
                    signal_dir,
                    queue_dir,
                    poll_interval=poll_interval,
                    persistent=persistent,
                    owner_pid=owner_pid,
                )

                processed, opened_url = process_queue(
                    queue_dir,
                    max_batch,
                    signal_dir,
                    session_ticket_path=session_ticket_path,
                )
                if processed > 0:
                    logging.info("Watcher cycle: processed %d entries", processed)

                if (
                    not persistent
                    and owner_pid <= 0
                    and session_ticket_path is None
                    and not _queue_has_pending_entries(queue_dir)
                ):
                    if processed > 0:
                        logging.info("Legacy ownerless watcher exiting after queue drained")
                    else:
                        logging.info("Legacy ownerless watcher exiting because queue is empty")
                    break

                if (
                    opened_url
                    and not persistent
                    and not _queue_has_pending_entries(queue_dir)
                ):
                    if owner_pid > 0:
                        if not _is_process_alive(owner_pid):
                            logging.info(
                                "Watcher exiting immediately after successful deferred URL handoff "
                                "(owner_pid=%s)",
                                owner_pid,
                            )
                            break
                    else:
                        logging.info("Watcher exiting immediately after successful deferred URL handoff")
                        break

                if _consume_shutdown_request(signal_dir, owner_pid=owner_pid, persistent=persistent):
                    break

                should_exit, owner_idle_since = _evaluate_owner_idle_exit(
                    queue_dir,
                    owner_pid=owner_pid,
                    idle_exit_seconds=idle_exit_seconds,
                    idle_since=owner_idle_since,
                    persistent=persistent,
                    session_ticket_path=session_ticket_path,
                )
                if should_exit:
                    logging.info(
                        "Watcher exiting after owner %s disappeared and queue stayed idle for %.1fs",
                        owner_pid,
                        idle_exit_seconds,
                    )
                    break

            except Exception:
                logging.error("Watcher cycle error", exc_info=True)

            slept = 0.0
            while slept < poll_interval and _watcher_running:
                chunk = min(0.5, poll_interval - slept)
                time.sleep(chunk)
                slept += chunk

    finally:
        _release_watcher_singleton(singleton_handle)

    logging.info("Watcher stopped cleanly")
    return 0


def _handle_open_url(data: Dict[str, Any]) -> tuple[bool, str, float | None]:
    url = data.get("url")
    if not url:
        logging.warning("Queue entry missing URL")
        return False, "missing url", None

    logging.info("Launching deferred URL: %s", url)
    start = time.perf_counter()
    try:
        launched = open_url(url)
    except ShellNotReadyError:
        logging.info("Deferring URL launch until the interactive shell is ready: %s", url)
        return False, "shell_not_ready", SHELL_NOT_READY_DEFER_SECONDS
    duration = time.perf_counter() - start

    if launched:
        logging.info("Launch request completed (%.2f ms): %s", duration * 1000.0, url)

        # Best-effort only. A foreground failure must not turn a successful
        # browser launch into a helper failure.
        try:
            if bring_browser_foreground(url):
                logging.info("Browser foregrounded after helper launch: %s", url)
            else:
                logging.warning("Browser foreground not confirmed after launch request: %s", url)
        except Exception as exc:
            logger.debug("[REDDIT] Exception suppressed during foreground attempt: %s", exc)
            logging.debug("Browser foreground attempt errored: %s", url, exc_info=True)

        return True, "", None

    logging.error("Launch failed: %s", url)
    return False, "open_url failed", None


def _handle_open_settings(data: Dict[str, Any], signal_dir: Path) -> bool:
    command = data.get("command")
    if isinstance(command, str):
        command = [part for part in command.strip().split() if part]
    if not command:
        logging.warning("Settings action missing command: %s", data)
        return False

    working_dir = data.get("working_dir") or ""
    completion_token = data.get("completion_token")
    timeout_seconds = float(data.get("timeout_seconds") or 900.0)
    timeout_seconds = max(30.0, min(timeout_seconds, 3600.0))

    completion_path = Path(completion_token) if completion_token else None
    if completion_path is None:
        completion_path = signal_dir / f"settings_complete_{int(time.time())}.ok"

    try:
        completion_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.debug("[REDDIT] Failed to prepare completion path %s: %s", completion_path, exc)

    logging.info("Launching settings helper command: %s", command)
    try:
        proc = subprocess.Popen(
            command,
            cwd=working_dir or None,
            creationflags=_NO_WINDOW_FLAG if os.name == "nt" and _NO_WINDOW_FLAG else 0,
        )
    except Exception as exc:
        logging.error("Failed to start settings helper process: %s", exc)
        return False

    try:
        proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        logging.error("Settings helper command timed out after %.0fs", timeout_seconds)
        try:
            proc.kill()
        except Exception:
            pass
        return False
    except Exception as exc:
        logging.error("Settings helper wait failed: %s", exc)
        return False

    if proc.returncode != 0:
        logging.error("Settings helper exited with code %s", proc.returncode)
        return False

    try:
        completion_path.write_text(f"completed {time.time():.0f}", encoding="utf-8")
        logging.info("Settings completion token written: %s", completion_path)
    except Exception as exc:
        logging.warning("Failed to write completion token %s: %s", completion_path, exc)

    return True


def bring_browser_foreground(url: str) -> bool:
    """Attempt to foreground the browser window for the launched URL."""
    if sys.platform != "win32":
        return False

    keywords = _build_keyword_list(url)
    deadline = time.perf_counter() + BROWSER_FOREGROUND_TIMEOUT

    while time.perf_counter() < deadline:
        if _foreground_first_matching_window(keywords):
            return True
        time.sleep(WINDOW_POLL_INTERVAL)

    return False


def _build_keyword_list(url: str) -> list[str]:
    keywords: list[str] = []
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if host:
            host = host.split("@")[-1]
            host = host.split(":")[0]
            tokens = [part for part in host.replace("-", ".").split(".") if part]
            keywords.extend(token for token in tokens if token not in ("www", "m"))
    except Exception as exc:
        logger.debug("[REDDIT] Exception suppressed while building keywords: %s", exc)

    if "reddit" not in keywords:
        keywords.append("reddit")

    seen = set()
    deduped: list[str] = []
    for kw in keywords:
        if kw and kw not in seen:
            deduped.append(kw)
            seen.add(kw)

    return deduped or ["reddit"]


def _foreground_first_matching_window(keywords: list[str]) -> bool:
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    except Exception as exc:
        logger.debug("[REDDIT] Exception suppressed while acquiring user32: %s", exc)
        return False

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    candidates: list[wintypes.HWND] = []

    @EnumWindowsProc
    def _enum_proc(hwnd: wintypes.HWND, lparam: wintypes.LPARAM) -> bool:  # noqa: ARG001
        try:
            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = (buf.value or "").lower()

            if any(kw in title for kw in keywords):
                candidates.append(hwnd)
                return False
        except Exception as exc:
            logger.debug("[REDDIT] Exception suppressed while enumerating windows: %s", exc)
            return True

        return True

    try:
        user32.EnumWindows(_enum_proc, 0)
    except Exception as exc:
        logger.debug("[REDDIT] Exception suppressed during EnumWindows: %s", exc)
        return False

    if not candidates:
        return False

    hwnd = candidates[0]

    try:
        if hasattr(user32, "AllowSetForegroundWindow"):
            user32.AllowSetForegroundWindow(0xFFFFFFFF)

        SW_RESTORE = 9
        SW_SHOW = 5
        SW_SHOWMAXIMIZED = 3

        is_iconic = bool(user32.IsIconic(hwnd))
        show_cmd = 0

        try:
            placement = WINDOWPLACEMENT()
            placement.length = ctypes.sizeof(placement)
            if user32.GetWindowPlacement(hwnd, ctypes.byref(placement)):
                show_cmd = placement.showCmd
        except Exception:
            show_cmd = 0

        if is_iconic:
            user32.ShowWindow(hwnd, SW_RESTORE)
        elif show_cmd == SW_SHOWMAXIMIZED:
            user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)

        return bool(user32.SetForegroundWindow(hwnd))
    except Exception as exc:
        logger.debug("[REDDIT] Exception suppressed while foregrounding window: %s", exc)
        return False


if __name__ == "__main__":
    raise SystemExit(main())
