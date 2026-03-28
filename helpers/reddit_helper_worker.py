"""
User-session Reddit helper worker.

This script runs inside the interactive user session (started via HKCU\Run
registry entry placed by the Inno Setup installer).  It watches the
ProgramData queue populated by the Winlogon screensaver build and opens
each deferred Reddit URL using the user's default browser.

Modes:
- ``--watch``  : Continuous polling loop (default when started at login).
                 Polls every ``--poll-interval`` seconds, opens URLs, then
                 sleeps.  Exits cleanly on SIGINT/SIGTERM.
- One-shot     : Drains queue once and exits (legacy / manual invocation).
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
from ctypes import wintypes
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from core.logging.logger import get_logger
from core.constants.timing import RETRY_BASE_DELAY_MS, RETRY_MAX_ATTEMPTS, RETRY_MAX_DELAY_MS
from core.windows.reddit_helper_runtime import HEARTBEAT_FILE_NAME

logger = get_logger(__name__)

DEFAULT_PROGRAM_DATA = Path(os.getenv("PROGRAMDATA", r"C:\ProgramData"))
DEFAULT_BASE = DEFAULT_PROGRAM_DATA / "SRPSS"
DEFAULT_QUEUE = DEFAULT_BASE / "url_queue"
DEFAULT_LOG_DIR = DEFAULT_BASE / "logs"
DEFAULT_SIGNAL_DIR = DEFAULT_BASE / "helper_signals"
DEFAULT_MAX_BATCH = 50
DEFAULT_POLL_INTERVAL = 2.0
WINDOW_POLL_INTERVAL = 0.25
BROWSER_FOREGROUND_TIMEOUT = 5.0
_NO_WINDOW_FLAG = getattr(subprocess, "CREATE_NO_WINDOW", 0)
OPEN_URL_MAX_AGE_SECONDS = 3600.0
OPEN_SETTINGS_MAX_AGE_SECONDS = 900.0

BROWSER_WINDOW_CLASSES = {
    "chrome_widgetwin_1",
    "chrome_widgetwin_0",
    "applicationframewindow",
    "mozillawindowclass",
    "ieframe",
}


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

    handlers = [
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
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run in continuous watcher mode (poll queue directory)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL,
        help="Seconds between queue polls in watch mode (default: %.1f)" % DEFAULT_POLL_INTERVAL,
    )
    return parser.parse_args()


def iter_queue_files(queue_dir: Path):
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


def _write_heartbeat(signal_dir: Path, queue_dir: Path, poll_interval: float) -> None:
    payload = {
        "updated_at": time.time(),
        "pid": os.getpid(),
        "queue_dir": str(queue_dir),
        "poll_interval": float(poll_interval),
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


def _write_entry_payload(target_path: Path, payload: Dict[str, Any]) -> None:
    tmp_path = target_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload), encoding="utf-8")
    tmp_path.replace(target_path)


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
    try:
        os.startfile(url)  # type: ignore[attr-defined]
        return True
    except OSError:
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
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)


def process_queue(queue_dir: Path, max_batch: int, signal_dir: Path) -> int:
    processed = 0
    for entry_path in iter_queue_files(queue_dir):
        if processed >= max_batch:
            break
        try:
            data = json.loads(entry_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.warning("Failed to parse %s: %s", entry_path.name, exc)
            entry_path.rename(entry_path.with_suffix(".corrupt"))
            continue

        if not _retry_ready(data):
            continue

        data = _clear_retry_metadata(data)
        action = str(data.get("action") or "open_url").strip().lower()
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
        if action == "open_url":
            success = _handle_open_url(data)
        elif action == "open_settings":
            success = _handle_open_settings(data, signal_dir)
        else:
            logging.warning("Unknown helper action '%s' in %s", action, entry_path.name)
            error = f"unknown action: {action}"

        if success:
            entry_path.unlink(missing_ok=True)
        else:
            _schedule_retry(entry_path, data, error=error)
        processed += 1
    return processed


def main() -> int:
    import signal as _signal

    args = parse_args()
    _hide_own_window()
    args.queue.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_dir, args.verbose)

    signal_dir = DEFAULT_SIGNAL_DIR
    try:
        signal_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.debug("[REDDIT] Failed to ensure signal dir %s: %s", signal_dir, exc)
    _write_heartbeat(signal_dir, args.queue, args.poll_interval if args.watch else 0.0)

    if args.watch:
        _signal.signal(_signal.SIGINT, _signal_handler)
        _signal.signal(_signal.SIGTERM, _signal_handler)
        return _run_watcher(args.queue, args.max_batch, signal_dir, args.poll_interval)

    logging.info("Helper started one-shot (queue=%s)", args.queue)
    processed = process_queue(args.queue, args.max_batch, signal_dir)
    logging.info("Helper finished (processed=%d)", processed)
    return 0


def _run_watcher(queue_dir: Path, max_batch: int, signal_dir: Path, poll_interval: float) -> int:
    """Continuous watcher loop — polls queue, opens URLs, sleeps."""
    global _watcher_running
    poll_interval = max(0.5, poll_interval)
    logging.info("Watcher started (queue=%s, poll=%.1fs)", queue_dir, poll_interval)

    while _watcher_running:
        try:
            _write_heartbeat(signal_dir, queue_dir, poll_interval)
            processed = process_queue(queue_dir, max_batch, signal_dir)
            if processed > 0:
                logging.info("Watcher cycle: processed %d entries", processed)
        except Exception:
            logging.error("Watcher cycle error", exc_info=True)

        # Sleep in small increments so we respond to shutdown quickly
        slept = 0.0
        while slept < poll_interval and _watcher_running:
            chunk = min(0.5, poll_interval - slept)
            time.sleep(chunk)
            slept += chunk

    logging.info("Watcher stopped cleanly")
    return 0


def _handle_open_url(data: Dict[str, Any]) -> bool:
    url = data.get("url")
    if not url:
        logging.warning("Queue entry missing URL")
        return False

    logging.info("Launching deferred URL: %s", url)
    start = time.perf_counter()
    launched = open_url(url)
    duration = time.perf_counter() - start
    if launched:
        logging.info("Launch succeeded (%.2f ms): %s", duration * 1000.0, url)
        try:
            if bring_browser_foreground(url):
                logging.info("Browser foregrounded after helper launch: %s", url)
            else:
                logging.debug("Browser foreground attempt skipped/failed: %s", url)
        except Exception as exc:
            logger.debug("[REDDIT] Exception suppressed: %s", exc)
            logging.debug("Browser foreground attempt errored: %s", url, exc_info=True)
        return True

    logging.error("Launch failed: %s", url)
    return False


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
        completion_path.write_text(
            f"completed {time.time():.0f}",
            encoding="utf-8",
        )
        logging.info("Settings completion token written: %s", completion_path)
    except Exception as exc:
        logging.warning("Failed to write completion token %s: %s", completion_path, exc)
    return True



def bring_browser_foreground(url: str) -> bool:
    """Attempt to foreground the Reddit browser window for the launched URL."""
    if sys.platform != "win32":
        return False

    keywords = _build_keyword_list(url)
    deadline = time.perf_counter() + BROWSER_FOREGROUND_TIMEOUT
    success = False

    while time.perf_counter() < deadline:
        success = _foreground_first_matching_window(keywords)
        if success:
            break
        time.sleep(WINDOW_POLL_INTERVAL)

    return success


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
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)

    if "reddit" not in keywords:
        keywords.append("reddit")
    # Deduplicate while preserving order
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
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)
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
        except Exception as e:
            logger.debug("[REDDIT] Exception suppressed: %s", e)
            return True
        return True

    try:
        user32.EnumWindows(_enum_proc, 0)
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)
        return False

    if not candidates:
        return False

    hwnd = candidates[0]
    try:
        if hasattr(user32, "AllowSetForegroundWindow"):
            user32.AllowSetForegroundWindow(0xFFFFFFFF)

        # Only restore minimized windows; keep maximized windows maximized.
        SW_RESTORE = 9
        SW_SHOW = 5
        SW_SHOWMAXIMIZED = 3

        is_iconic = bool(user32.IsIconic(hwnd))
        show_cmd = 0
        try:
            placement = wintypes.WINDOWPLACEMENT()  # type: ignore[attr-defined]
            placement.length = ctypes.sizeof(placement)  # type: ignore[arg-type]
            if user32.GetWindowPlacement(hwnd, ctypes.byref(placement)):
                show_cmd = placement.showCmd
        except AttributeError:
            show_cmd = 0

        if is_iconic:
            user32.ShowWindow(hwnd, SW_RESTORE)
        elif show_cmd == SW_SHOWMAXIMIZED:
            user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)

        return bool(user32.SetForegroundWindow(hwnd))
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)
        return False


if __name__ == "__main__":
    raise SystemExit(main())
