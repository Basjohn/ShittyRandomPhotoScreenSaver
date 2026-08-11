"""Qt-free Gmail cache preparation and persistence.

The Gmail widget owns visible Qt state. This module owns detached cache file
inspection, JSON conversion, and atomic persistence suitable for shared I/O
workers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Iterable, Optional

from core.gmail.gmail_client import EmailMetadata
from core.logging.logger import get_logger


logger = get_logger(__name__)

_CACHE_LOCKS_GUARD = threading.Lock()
_CACHE_LOCKS: dict[str, threading.RLock] = {}
_CACHE_WRITE_SEQUENCE_GUARD = threading.Lock()
_CACHE_WRITE_SEQUENCE = 0
_LATEST_RESERVED_WRITES: dict[str, int] = {}


def _normalized_path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _cache_lock(path: Path) -> threading.RLock:
    key = _normalized_path_key(path)
    with _CACHE_LOCKS_GUARD:
        lock = _CACHE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _CACHE_LOCKS[key] = lock
        return lock


def reserve_gmail_cache_write(cache_path: Path) -> int:
    """Reserve the newest accepted write identity for one shared cache path."""

    global _CACHE_WRITE_SEQUENCE
    path = Path(cache_path)
    key = _normalized_path_key(path)
    with _cache_lock(path):
        with _CACHE_WRITE_SEQUENCE_GUARD:
            _CACHE_WRITE_SEQUENCE += 1
            write_id = _CACHE_WRITE_SEQUENCE
        _LATEST_RESERVED_WRITES[key] = write_id
        return write_id


@dataclass(frozen=True)
class PreparedGmailStartup:
    """One immutable startup-cache result published by an I/O worker."""

    emails: tuple[EmailMetadata, ...]
    cache_timestamp: datetime | None
    state: str


def _email_to_cache_dict(email: EmailMetadata) -> dict[str, Any]:
    """Serialize metadata-only mail to the stable JSON schema."""

    return {
        "id": email.id,
        "thread_id": email.thread_id,
        "sender": email.sender,
        "subject": email.subject,
        "date_iso": email.date.isoformat() if email.date else None,
        "labels": list(email.labels),
        "is_unread": email.is_unread,
        "provider": email.provider,
        "account_email": email.account_email,
        "imap_uid": email.imap_uid,
        "rfc822_message_id": email.rfc822_message_id,
        "gmail_thread_id": email.gmail_thread_id,
        "gmail_message_id": email.gmail_message_id,
        "open_url": email.open_url,
    }


def _email_from_cache_dict(data: Any) -> Optional[EmailMetadata]:
    """Deserialize one metadata-only cache record, dropping invalid rows."""

    if not isinstance(data, dict):
        logger.warning("[GMAIL] Ignoring non-object cached email record")
        return None
    try:
        date_str = data.get("date_iso")
        date = datetime.fromisoformat(date_str) if date_str else None
        labels = tuple(data.get("labels", []))
        return EmailMetadata(
            id=data["id"],
            thread_id=data["thread_id"],
            sender=data["sender"],
            subject=data["subject"],
            date=date,
            labels=labels,
            is_unread=data["is_unread"],
            provider=data.get("provider", "gmail_api"),
            account_email=data.get("account_email"),
            imap_uid=data.get("imap_uid"),
            rfc822_message_id=data.get("rfc822_message_id"),
            gmail_thread_id=data.get("gmail_thread_id"),
            gmail_message_id=data.get("gmail_message_id"),
            open_url=data.get("open_url"),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("[GMAIL] Failed to deserialize cached email: %s", exc)
        return None


def serialize_email_cache(emails: Iterable[EmailMetadata]) -> str:
    """Serialize metadata-only mail to the stable cache payload."""

    return json.dumps([_email_to_cache_dict(email) for email in emails], indent=2)


def _decode_email_cache(data: str) -> tuple[tuple[EmailMetadata, ...], bool]:
    try:
        items = json.loads(data)
    except json.JSONDecodeError as exc:
        logger.warning("[GMAIL] Failed to deserialize email cache: %s", exc)
        return (), False
    if not isinstance(items, list):
        logger.warning("[GMAIL] Ignoring email cache with non-list root")
        return (), False
    emails = tuple(
        email
        for email in (_email_from_cache_dict(item) for item in items)
        if email is not None
    )
    return emails, True


def deserialize_email_cache(data: str) -> list[EmailMetadata]:
    """Deserialize a cache payload while preserving the legacy list API."""

    emails, _valid = _decode_email_cache(data)
    return list(emails)


def load_gmail_startup_snapshot(
    cache_path: Path,
    *,
    max_age_hours: int,
    now: datetime | None = None,
) -> PreparedGmailStartup:
    """Read and prepare Gmail startup state without touching Qt objects."""

    path = Path(cache_path)
    with _cache_lock(path):
        try:
            stat_result = path.stat()
        except FileNotFoundError:
            return PreparedGmailStartup((), None, "missing")
        except OSError as exc:
            logger.warning("[GMAIL] Failed to inspect cache: %s", exc)
            return PreparedGmailStartup((), None, "error")

        cache_timestamp = datetime.fromtimestamp(stat_result.st_mtime)
        current_time = now or datetime.now()
        if current_time - cache_timestamp > timedelta(hours=max_age_hours):
            return PreparedGmailStartup((), cache_timestamp, "stale")

        try:
            payload = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("[GMAIL] Failed to read cache: %s", exc)
            return PreparedGmailStartup((), None, "error")

        emails, valid = _decode_email_cache(payload)
        if not valid:
            return PreparedGmailStartup((), None, "invalid")
        return PreparedGmailStartup(emails, cache_timestamp, "fresh")


def write_gmail_email_cache(
    cache_path: Path,
    emails: Iterable[EmailMetadata],
    *,
    write_id: int | None = None,
) -> bool:
    """Atomically persist accepted Gmail metadata on an I/O worker."""

    path = Path(cache_path)
    payload = serialize_email_cache(tuple(emails))
    tmp_path: Path | None = None
    with _cache_lock(path):
        try:
            if (
                write_id is not None
                and _LATEST_RESERVED_WRITES.get(_normalized_path_key(path)) != write_id
            ):
                logger.debug("[GMAIL] Skipping superseded cache write id=%s", write_id)
                return False
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=str(path.parent),
            )
            tmp_path = Path(tmp_name)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
            tmp_path = None
            return True
        except Exception as exc:
            logger.warning("[GMAIL] Failed to write cache: %s", exc)
            return False
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass


__all__ = [
    "PreparedGmailStartup",
    "deserialize_email_cache",
    "load_gmail_startup_snapshot",
    "reserve_gmail_cache_write",
    "serialize_email_cache",
    "write_gmail_email_cache",
]
