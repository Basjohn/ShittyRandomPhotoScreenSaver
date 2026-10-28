"""Atomic file replacement for data shared by concurrently running builds.

The normal saver and MC share one data root (``core.settings.storage_paths``),
and per-path locks are in-process only. A reader in either process must see
the old file or the new one, never a partial write.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _atomic_write(path: Path, payload: str | bytes, *, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        options = {"encoding": encoding} if isinstance(payload, str) else {}
        with os.fdopen(fd, "w" if isinstance(payload, str) else "wb", **options) as handle:
            handle.write(payload)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write text to a sibling temp file, then atomically replace the target."""
    _atomic_write(path, text, encoding=encoding)


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Atomically replace a file without changing backup bytes or line endings."""
    _atomic_write(path, payload)
