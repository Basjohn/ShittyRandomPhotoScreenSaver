"""Bounded filesystem primitives shared by the Reddit helper bridge and worker."""

from __future__ import annotations

import json
import logging
import os
from copy import copy
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

HELPER_LOG_MAX_BYTES = 1024 * 1024
HELPER_LOG_SEGMENT_MAX_BYTES = HELPER_LOG_MAX_BYTES // 2
HELPER_LOG_BACKUP_COUNT = 1
HELPER_LOG_RECORD_MAX_BYTES = 16 * 1024

QUEUE_ENTRY_MAX_BYTES = 64 * 1024
QUEUE_MAX_LIVE_ENTRIES = 256
QUEUE_MAX_TOTAL_BYTES = 8 * 1024 * 1024


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def read_json_bounded(path: Path, *, max_bytes: int = QUEUE_ENTRY_MAX_BYTES) -> Any:
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"{path.name} exceeds {max_bytes} bytes")
    with path.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError(f"{path.name} exceeds {max_bytes} bytes")
    return json.loads(raw.decode("utf-8"))


def write_json_atomic_bounded(
    target_path: Path,
    payload: Any,
    *,
    max_bytes: int = QUEUE_ENTRY_MAX_BYTES,
) -> None:
    raw = json_bytes(payload)
    if len(raw) > max_bytes:
        raise ValueError(f"{target_path.name} payload exceeds {max_bytes} bytes")

    tmp_path = target_path.with_name(f".{target_path.name}.{os.getpid()}.tmp")
    try:
        with tmp_path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(target_path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def queue_usage(queue_dir: Path) -> tuple[int, int]:
    live_count = 0
    total_bytes = 0
    for path in queue_dir.iterdir():
        if not path.is_file():
            continue
        try:
            total_bytes += max(0, path.stat().st_size)
        except OSError:
            continue
        if path.suffix.lower() in {".json", ".retry", ".processing", ".tmp"}:
            live_count += 1
    return live_count, total_bytes


class BoundedRotatingFileHandler(RotatingFileHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            rendered = self.format(record)
            raw = rendered.encode("utf-8", errors="replace")
            if len(raw) > HELPER_LOG_RECORD_MAX_BYTES:
                suffix = "...[truncated]"
                clipped = raw[: HELPER_LOG_RECORD_MAX_BYTES - len(suffix)].decode(
                    "utf-8",
                    errors="ignore",
                )
                record = copy(record)
                record.msg = clipped + suffix
                record.args = ()
                record.exc_info = None
                record.exc_text = None
        except Exception:
            pass
        super().emit(record)


def make_rotating_log_handler(log_file: Path) -> RotatingFileHandler:
    return BoundedRotatingFileHandler(
        log_file,
        maxBytes=HELPER_LOG_SEGMENT_MAX_BYTES,
        backupCount=HELPER_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )


def _bounded_record_bytes(message: str) -> bytes:
    one_line = " ".join(str(message).splitlines())
    raw = one_line.encode("utf-8", errors="replace")
    if len(raw) <= HELPER_LOG_RECORD_MAX_BYTES:
        return raw
    suffix = b"...[truncated]"
    return raw[: HELPER_LOG_RECORD_MAX_BYTES - len(suffix)] + suffix


def append_bounded_log(log_file: Path, message: str) -> bool:
    """Append one diagnostic line while keeping active and backup files <= 1 MiB."""
    raw = _bounded_record_bytes(message) + b"\n"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    backup_path = log_file.with_name(f"{log_file.name}.1")

    try:
        current_size = log_file.stat().st_size if log_file.exists() else 0
        if current_size + len(raw) > HELPER_LOG_SEGMENT_MAX_BYTES:
            backup_path.unlink(missing_ok=True)
            log_file.replace(backup_path)

        with log_file.open("ab") as handle:
            handle.write(raw)
        active_size = log_file.stat().st_size
        backup_size = backup_path.stat().st_size if backup_path.exists() else 0
        return (
            active_size <= HELPER_LOG_SEGMENT_MAX_BYTES
            and backup_size <= HELPER_LOG_SEGMENT_MAX_BYTES
            and active_size + backup_size <= HELPER_LOG_MAX_BYTES
        )
    except OSError:
        return False


def install_null_logging(*, verbose: bool = False) -> None:
    handlers: list[logging.Handler] = [logging.NullHandler()]
    if verbose:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [helper] %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )
