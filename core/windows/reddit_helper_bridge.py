"""
Reddit helper bridge for Winlogon-hosted screensaver builds.

The screensaver process running inside Winlogon (SYSTEM account, secure
desktop) cannot reliably launch browser processes or write to user
directories.  This module provides a very small IPC layer that queues
deferred Reddit URLs into a ProgramData-backed spool so that a
user-session watcher (running on the interactive desktop) can pick them up
and launch them safely.

Current transport: file-based queue under ``%ProgramData%\\SRPSS\\url_queue``.
Each queued URL is written as a JSON file with metadata.  The watcher
process (installed by the Inno Setup installer, started on user login)
monitors the directory, opens URLs on behalf of the user, and deletes the
file once processed.

This module performs **only benign file I/O** — no process launching, no
token manipulation, no scheduled tasks.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.logging.logger import get_logger

logger = get_logger(__name__)

_PROGRAM_DATA = os.getenv("PROGRAMDATA", r"C:\ProgramData")
_BASE_DIR = Path(_PROGRAM_DATA) / "SRPSS"
_QUEUE_DIR = _BASE_DIR / "url_queue"
_SIGNAL_DIR = _BASE_DIR / "helper_signals"
_SPOOL_READY = False

SECURE_DESKTOP_HANDOFF_DELAY_SECONDS = 12.0


def get_queue_dir() -> Path:
    return _QUEUE_DIR


def get_base_dir() -> Path:
    return _BASE_DIR


def get_signal_dir() -> Path:
    return _SIGNAL_DIR


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


def _coerce_command(command: Iterable[str] | str) -> List[str]:
    if isinstance(command, str):
        stripped = command.strip()
        return [part for part in stripped.split() if part]
    coerced: List[str] = []
    for part in command:
        text = str(part).strip()
        if text:
            coerced.append(text)
    return coerced


def _default_not_before_delay_seconds(payload: Dict[str, Any]) -> float:
    action = str(payload.get("action") or "").strip().lower()
    if action not in {"open_url", "open_settings"}:
        return 0.0

    source = str(payload.get("source") or "").strip().lower()
    session = str(payload.get("session") or "").strip().lower()

    if session in {"winlogon", "services"}:
        return SECURE_DESKTOP_HANDOFF_DELAY_SECONDS

    if source in {"screensaver", "scr_click", "flush_safety_net"} or source.startswith("scr_"):
        return SECURE_DESKTOP_HANDOFF_DELAY_SECONDS

    return 0.0


def _write_entry(entry: Dict[str, Any]) -> bool:
    if not is_bridge_available():
        return False

    payload = dict(entry)
    payload.setdefault("timestamp", time.time())
    payload.setdefault("source", "screensaver")
    payload.setdefault("pid", os.getpid())
    payload.setdefault("session", os.getenv("SESSIONNAME"))

    token = payload.get("token")
    if not token:
        token = f"{int(payload['timestamp'] * 1000)}_{payload['pid']}_{uuid.uuid4().hex}"
        payload["token"] = token

    if payload.get("not_before_ts") is None:
        delay_seconds = _default_not_before_delay_seconds(payload)
        if delay_seconds > 0.0:
            payload["not_before_ts"] = float(payload["timestamp"]) + delay_seconds

    tmp_path = _QUEUE_DIR / f"{token}.tmp"
    final_path = _QUEUE_DIR / f"{token}.json"

    try:
        serialized = json.dumps(payload)
        tmp_path.write_text(serialized, encoding="utf-8")
        tmp_path.replace(final_path)
        logger.info(
            "[REDDIT-BRIDGE] Queued helper action '%s' (token=%s)",
            payload.get("action", "open_url"),
            token,
        )
        return True
    except Exception as exc:
        logger.warning("[REDDIT-BRIDGE] Failed to queue helper entry: %s", exc, exc_info=True)
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception as e:
            logger.debug("[MISC] Exception suppressed: %s", e)
        return False


def enqueue_url(url: str, *, source: str = "screensaver") -> bool:
    """
    Queue a Reddit URL for the interactive helper.
    """
    if not url:
        return False
    entry: Dict[str, Any] = {
        "action": "open_url",
        "url": url,
        "source": source,
    }
    return _write_entry(entry)


def enqueue_settings_request(
    command: Iterable[str] | str,
    *,
    completion_token: Path | str,
    working_dir: Optional[Path | str] = None,
    timeout_seconds: float = 900.0,
    source: str = "screensaver",
) -> bool:
    """Queue a request for the helper to launch settings on the user desktop."""
    cmd_parts = _coerce_command(command)
    if not cmd_parts:
        logger.warning("[REDDIT-BRIDGE] Settings request missing command")
        return False

    completion_path = Path(completion_token)
    try:
        completion_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.debug("[REDDIT-BRIDGE] Failed to prep completion path %s: %s", completion_path, exc)

    entry: Dict[str, Any] = {
        "action": "open_settings",
        "command": cmd_parts,
        "working_dir": str(Path(working_dir)) if working_dir else None,
        "completion_token": str(completion_path),
        "timeout_seconds": float(max(30.0, timeout_seconds)),
        "source": source,
    }
    return _write_entry(entry)


