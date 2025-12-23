"""
Reddit helper bridge for Winlogon-hosted screensaver builds.

The screensaver process running inside Winlogon (SYSTEM account, secure
desktop) cannot reliably launch browser processes or write to user
directories.  This module provides a very small IPC layer that queues
deferred Reddit URLs into a ProgramData-backed spool so that a
user-session helper (running on the interactive desktop) can pick them up
and launch them safely.

Current transport: file-based queue under ``%ProgramData%\\SRPSS\\url_queue``.
Each queued URL is written as a JSON file with metadata.  A future helper
process will monitor the directory, launch URLs on behalf of the user, and
delete the file once processed.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict

from core.logging.logger import get_logger

try:
    from core.windows import reddit_helper_installer
except Exception:  # pragma: no cover - import guard for non-Windows
    reddit_helper_installer = None

logger = get_logger(__name__)

_PROGRAM_DATA = os.getenv("PROGRAMDATA", r"C:\ProgramData")
_BASE_DIR = Path(_PROGRAM_DATA) / "SRPSS"
_QUEUE_DIR = _BASE_DIR / "url_queue"
_HELPER_TASK_NAME = os.getenv("SRPSS_REDDIT_HELPER_TASK", r"SRPSS\RedditHelper")
_NO_WINDOW_FLAG = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_SPOOL_READY = False


def get_queue_dir() -> Path:
    return _QUEUE_DIR


def _ensure_queue_dir() -> bool:
    global _SPOOL_READY
    if _SPOOL_READY and _QUEUE_DIR.exists():
        return True
    try:
        _QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        # Touch a sentinel so we know Winlogon had write permission.
        sentinel = _QUEUE_DIR / ".bridge_ready"
        sentinel.write_text("ok", encoding="utf-8")
        _SPOOL_READY = True
        return True
    except Exception as exc:
        logger.debug("[REDDIT-BRIDGE] Failed to prep ProgramData queue: %s", exc, exc_info=True)
        return False


def is_bridge_available() -> bool:
    """
    Check whether the bridge spool is writable in this environment.
    """
    if os.getenv("SRPSS_DISABLE_REDDIT_HELPER_BRIDGE"):
        return False
    return _ensure_queue_dir()


def enqueue_url(url: str, *, source: str = "screensaver") -> bool:
    """
    Queue a Reddit URL for the interactive helper.
    """
    if not url:
        return False
    if not is_bridge_available():
        return False

    entry: Dict[str, Any] = {
        "url": url,
        "source": source,
        "timestamp": time.time(),
        "pid": os.getpid(),
        "session": os.getenv("SESSIONNAME"),
    }
    token = f"{int(entry['timestamp'] * 1000)}_{entry['pid']}_{uuid.uuid4().hex}"
    tmp_path = _QUEUE_DIR / f"{token}.tmp"
    final_path = _QUEUE_DIR / f"{token}.json"

    try:
        tmp_path.write_text(json.dumps(entry), encoding="utf-8")
        tmp_path.replace(final_path)
        logger.info("[REDDIT-BRIDGE] Queued deferred URL via ProgramData bridge: %s", url)
        triggered = _trigger_helper_process()
        if not triggered:
            _kick_helper()
    except Exception as exc:
        logger.warning("[REDDIT-BRIDGE] Failed to queue URL %s: %s", url, exc, exc_info=True)
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        return False
    return True


def _kick_helper() -> None:
    if not _HELPER_TASK_NAME:
        return
    try:
        result = subprocess.run(
            [
                "schtasks",
                "/Run",
                "/TN",
                _HELPER_TASK_NAME,
            ],
            capture_output=True,
            text=True,
            check=False,
            creationflags=_NO_WINDOW_FLAG if _NO_WINDOW_FLAG else 0,
        )
        if result.returncode != 0:
            logger.debug(
                "[REDDIT-BRIDGE] schtasks /Run failed (rc=%s): %s",
                result.returncode,
                (result.stderr or result.stdout).strip(),
            )
    except Exception as exc:
        logger.debug("[REDDIT-BRIDGE] Unable to trigger helper task: %s", exc, exc_info=True)


def _trigger_helper_process() -> bool:
    if reddit_helper_installer is None:
        return False
    try:
        launched = reddit_helper_installer.trigger_helper_run()
        if launched:
            logger.debug("[REDDIT-BRIDGE] Embedded helper triggered directly")
        else:
            logger.debug("[REDDIT-BRIDGE] Embedded helper trigger declined")
        return launched
    except Exception as exc:
        logger.debug("[REDDIT-BRIDGE] Embedded helper trigger failed: %s", exc, exc_info=True)
        return False
