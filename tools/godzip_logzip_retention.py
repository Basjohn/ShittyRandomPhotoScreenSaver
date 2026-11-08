"""Godzip Foundry LOGZIP destination and narrowly scoped archive retention.

Keep GODZIP transfer output preferences entirely separate. Every manual or
post-RUN LOGZIP is written into <repo>/logs/evidence_chest. Only verified LOGZIP
archives matching the newly created archive's ten-hex-character Git HEAD are
subject to five-file rolling retention. Never touch loose logs or other ZIPs.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Sequence

from godzip_foundry_core import GodzipError, LogzipResult, create_logzip

_LOGZIP_NAME = re.compile(r"^logs(?P<head>[0-9a-f]{10})(?P<number>[0-9]*)\.zip$", re.IGNORECASE)


def logzip_chest(repo_root: Path) -> Path:
    """Repository-local location for manual and after-run LOGZIPs."""
    return Path(repo_root).resolve() / "logs" / "evidence_chest"


def prune_logzip_series(chest: Path, just_created: Path, keep: int = 5) -> tuple[Path, ...]:
    """Retain the newest N files for one exact logs<HEAD>[number].zip series.

    Must be invoked *after* create_logzip finished writing and verifying the new
    archive. The completed archive is never removed. Files are enumerated only
    in chest's immediate directory, and symlinks/nonmatching archives are left
    untouched. A filesystem deletion failure propagates as an explicit error.
    """
    if keep < 1:
        raise ValueError("LOGZIP retention must keep at least one archive")
    chest = Path(chest).resolve()
    just_created = Path(just_created)
    if just_created.resolve().parent != chest:
        raise GodzipError("LOGZIP retention refused an archive outside logs/evidence_chest")
    match = _LOGZIP_NAME.fullmatch(just_created.name)
    if match is None:
        raise GodzipError(f"Unexpected LOGZIP filename: {just_created.name}")
    head = match.group("head").casefold()
    candidates: list[tuple[float, int, Path]] = []
    with os.scandir(chest) as iterator:
        for entry in iterator:
            parsed = _LOGZIP_NAME.fullmatch(entry.name)
            if parsed is None or parsed.group("head").casefold() != head:
                continue
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
                stamp = entry.stat(follow_symlinks=False).st_mtime_ns
            except OSError:
                continue
            number = int(parsed.group("number") or "1")
            candidates.append((stamp, number, Path(entry.path)))

    # Even if the archive's recorded timestamp is strange, it must survive.
    chosen = [item for item in candidates if item[2].name == just_created.name]
    if not chosen:
        raise GodzipError("Newly created LOGZIP disappeared before retention")
    other = sorted(
        (item for item in candidates if item[2].name != just_created.name),
        key=lambda item: (item[0], item[1], item[2].name.casefold()), reverse=True,
    )
    victims = other[max(0, keep - 1):]
    removed: list[Path] = []
    for _stamp, _number, path in victims:
        try:
            path.unlink()
        except OSError as exc:
            raise GodzipError(f"LOGZIP created, but retention could not remove {path}: {exc}") from exc
        removed.append(path)
    return tuple(removed)


def create_chest_logzip(repo_root: Path, selected_names: Sequence[str] | None = None) -> LogzipResult:
    """Create and verify an archive, then trim only its matching HEAD series."""
    chest = logzip_chest(repo_root)
    result = create_logzip(repo_root, selected_names, output_dir=chest)
    prune_logzip_series(chest, result.zip_path, keep=5)
    return result
