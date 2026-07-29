"""Small bounded filesystem helpers for the Reddit helper queue and logs."""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
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
    return json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def read_json_bounded(
    path: Path,
    *,
    max_bytes: int = QUEUE_ENTRY_MAX_BYTES,
) -> Any:
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

    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_name(
        f".{target_path.name}.{os.getpid()}.tmp"
    )

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
    """Return live queue-entry count and total queue-directory bytes."""
    live_count = 0
    total_bytes = 0

    try:
        paths = tuple(queue_dir.iterdir())
    except OSError:
        return 0, 0

    for path in paths:
        if not path.is_file():
            continue

        try:
            total_bytes += max(0, path.stat().st_size)
        except OSError:
            continue

        if path.suffix.lower() in {
            ".json",
            ".retry",
            ".processing",
            ".tmp",
        }:
            live_count += 1

    return live_count, total_bytes


class BoundedRotatingFileHandler(RotatingFileHandler):
    """Rotating handler that also clips pathological single records."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            rendered = self.format(record)
            raw = rendered.encode("utf-8", errors="replace")

            if len(raw) > HELPER_LOG_RECORD_MAX_BYTES:
                suffix = "...[truncated]"
                clipped = raw[
                    : HELPER_LOG_RECORD_MAX_BYTES - len(
                        suffix.encode("utf-8")
                    )
                ].decode("utf-8", errors="ignore")

                record = copy(record)
                record.msg = clipped + suffix
                record.args = ()
                record.exc_info = None
                record.exc_text = None
        except Exception:
            # Logging must never break helper execution.
            pass

        super().emit(record)


def make_rotating_log_handler(
    log_file: Path,
) -> RotatingFileHandler:
    log_file.parent.mkdir(parents=True, exist_ok=True)
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
    return raw[
        : HELPER_LOG_RECORD_MAX_BYTES - len(suffix)
    ] + suffix


def append_bounded_log(log_file: Path, message: str) -> bool:
    """Append one line while keeping active plus backup at or below 1 MiB."""
    raw = _bounded_record_bytes(message) + b"\n"
    backup_path = log_file.with_name(f"{log_file.name}.1")

    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)

        current_size = (
            log_file.stat().st_size
            if log_file.exists()
            else 0
        )
        if current_size + len(raw) > HELPER_LOG_SEGMENT_MAX_BYTES:
            backup_path.unlink(missing_ok=True)
            log_file.replace(backup_path)

        with log_file.open("ab") as handle:
            handle.write(raw)
            handle.flush()

        active_size = log_file.stat().st_size
        backup_size = (
            backup_path.stat().st_size
            if backup_path.exists()
            else 0
        )

        return (
            active_size <= HELPER_LOG_SEGMENT_MAX_BYTES
            and backup_size <= HELPER_LOG_SEGMENT_MAX_BYTES
            and active_size + backup_size <= HELPER_LOG_MAX_BYTES
        )
    except OSError:
        return False


def install_emergency_logging(*, verbose: bool = False) -> Path | None:
    """Install a real bounded fallback logger when ProgramData logging fails.

    The fallback is written to the interactive user's temporary directory so an
    ACL problem under ProgramData cannot also erase the explanation.
    """
    handlers: list[logging.Handler] = []
    emergency_path: Path | None = None

    try:
        emergency_dir = Path(tempfile.gettempdir()) / "SRPSS"
        emergency_path = emergency_dir / "reddit_helper_emergency.log"
        handlers.append(make_rotating_log_handler(emergency_path))
    except Exception:
        emergency_path = None

    if verbose or not handlers:
        handlers.append(logging.StreamHandler(sys.stderr))

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [helper-emergency] %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )

    logging.error(
        "Primary Reddit helper log could not be opened; emergency diagnostics "
        "are active%s",
        f" at {emergency_path}" if emergency_path else "",
    )
    return emergency_path


def install_null_logging(*, verbose: bool = False) -> None:
    """Backward-compatible name retained for the existing worker.

    This intentionally does *not* install a NullHandler. Older worker builds
    import this name, so changing its behaviour fixes silent startup failures
    without rewriting the worker.
    """
    install_emergency_logging(verbose=verbose)
