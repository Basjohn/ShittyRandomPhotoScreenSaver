"""
Simple ProgramData queue bridge for the Reddit helper.

The secure-desktop screensaver writes queue entries. The interactive scheduled
helper reads them and opens links. This module performs file I/O only.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.logging.logger import get_logger
from core.windows.reddit_helper_storage import (
    QUEUE_ENTRY_MAX_BYTES,
    QUEUE_MAX_LIVE_ENTRIES,
    QUEUE_MAX_TOTAL_BYTES,
    json_bytes,
    queue_usage,
    write_json_atomic_bounded,
)

logger = get_logger(__name__)

_PROGRAM_DATA = os.getenv("PROGRAMDATA", r"C:\ProgramData")
_BASE_DIR = Path(_PROGRAM_DATA) / "SRPSS"
_QUEUE_DIR = _BASE_DIR / "url_queue"
_SIGNAL_DIR = _BASE_DIR / "helper_signals"
_SPOOL_READY = False

SECURE_DESKTOP_HANDOFF_DELAY_SECONDS = 3.0


def get_queue_dir() -> Path:
    return _QUEUE_DIR


def get_base_dir() -> Path:
    return _BASE_DIR


def get_signal_dir() -> Path:
    return _SIGNAL_DIR


def _ensure_queue_dir() -> bool:
    """Ensure the queue exists without custom ACL probing or retry machinery."""
    global _SPOOL_READY

    if _SPOOL_READY and _QUEUE_DIR.is_dir():
        return True

    try:
        _QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        _SPOOL_READY = _QUEUE_DIR.is_dir()
        return _SPOOL_READY
    except Exception as exc:
        _SPOOL_READY = False
        logger.warning(
            "[REDDIT-BRIDGE] ProgramData queue is unavailable: %s",
            exc,
            exc_info=True,
        )
        return False


def is_bridge_available() -> bool:
    if os.getenv("SRPSS_DISABLE_REDDIT_HELPER_BRIDGE"):
        return False
    return _ensure_queue_dir()


def _coerce_command(command: Iterable[str] | str) -> List[str]:
    if isinstance(command, str):
        stripped = command.strip()
        return [part for part in stripped.split() if part]

    parts: List[str] = []
    for part in command:
        text = str(part).strip()
        if text:
            parts.append(text)
    return parts


def _default_not_before_delay_seconds(
    payload: Dict[str, Any],
) -> float:
    action = str(payload.get("action") or "").strip().lower()
    if action not in {"open_url", "open_settings"}:
        return 0.0

    source = str(payload.get("source") or "").strip().lower()
    session = str(payload.get("session") or "").strip().lower()

    if session in {"winlogon", "services"}:
        return SECURE_DESKTOP_HANDOFF_DELAY_SECONDS

    if (
        source in {"screensaver", "scr_click", "flush_safety_net"}
        or source.startswith("scr_")
    ):
        return SECURE_DESKTOP_HANDOFF_DELAY_SECONDS

    return 0.0


def _write_entry(entry: Dict[str, Any]) -> bool:
    global _SPOOL_READY

    if not is_bridge_available():
        return False

    payload = dict(entry)
    payload.setdefault("schema_version", 1)
    payload.setdefault("timestamp", time.time())
    payload.setdefault("source", "screensaver")
    payload.setdefault("pid", os.getpid())
    payload.setdefault("session", os.getenv("SESSIONNAME"))

    token = str(payload.get("token") or "").strip()
    if not token:
        token = (
            f"{int(float(payload['timestamp']) * 1000)}_"
            f"{payload['pid']}_{uuid.uuid4().hex}"
        )
        payload["token"] = token

    if payload.get("not_before_ts") is None:
        delay = _default_not_before_delay_seconds(payload)
        if delay > 0.0:
            payload["not_before_ts"] = (
                float(payload["timestamp"]) + delay
            )

    final_path = _QUEUE_DIR / f"{token}.json"

    try:
        serialized = json_bytes(payload)
        if len(serialized) > QUEUE_ENTRY_MAX_BYTES:
            raise ValueError(
                f"queue entry exceeds {QUEUE_ENTRY_MAX_BYTES} bytes"
            )

        live_count, total_bytes = queue_usage(_QUEUE_DIR)
        if live_count >= QUEUE_MAX_LIVE_ENTRIES:
            raise OSError(
                f"queue entry limit reached "
                f"({QUEUE_MAX_LIVE_ENTRIES})"
            )
        if total_bytes + len(serialized) > QUEUE_MAX_TOTAL_BYTES:
            raise OSError(
                f"queue byte limit reached "
                f"({QUEUE_MAX_TOTAL_BYTES})"
            )

        write_json_atomic_bounded(final_path, payload)
        logger.info(
            "[REDDIT-BRIDGE] Queued helper action '%s' (token=%s)",
            payload.get("action", "open_url"),
            token,
        )
        return True
    except Exception as exc:
        _SPOOL_READY = False
        logger.warning(
            "[REDDIT-BRIDGE] Failed to queue helper entry: %s",
            exc,
            exc_info=True,
        )
        return False


def enqueue_url(
    url: str,
    *,
    source: str = "screensaver",
) -> bool:
    if not url:
        return False

    return _write_entry(
        {
            "action": "open_url",
            "url": url,
            "source": source,
        }
    )


def enqueue_settings_request(
    command: Iterable[str] | str,
    *,
    completion_token: Path | str,
    working_dir: Optional[Path | str] = None,
    timeout_seconds: float = 900.0,
    source: str = "screensaver",
) -> bool:
    cmd_parts = _coerce_command(command)
    if not cmd_parts:
        logger.warning(
            "[REDDIT-BRIDGE] Settings request missing command"
        )
        return False

    completion_path = Path(completion_token)
    try:
        completion_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.debug(
            "[REDDIT-BRIDGE] Failed to prepare completion path %s: %s",
            completion_path,
            exc,
        )

    return _write_entry(
        {
            "action": "open_settings",
            "command": cmd_parts,
            "working_dir": (
                str(Path(working_dir))
                if working_dir
                else None
            ),
            "completion_token": str(completion_path),
            "timeout_seconds": float(
                max(30.0, timeout_seconds)
            ),
            "source": source,
        }
    )
