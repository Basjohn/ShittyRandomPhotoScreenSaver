"""Default notification sound path helpers."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

DEFAULT_NOTIFICATION_SOUND_NAME = "tutuogg.ogg"
DEFAULT_NOTIFICATION_SOUND_RELATIVE = f"resources/{DEFAULT_NOTIFICATION_SOUND_NAME}"


def programdata_sound_dir() -> Path:
    base = os.environ.get("PROGRAMDATA") or r"C:\ProgramData"
    return Path(base) / "SRPSS" / "sounds"


def programdata_notification_sound_path() -> Path:
    return programdata_sound_dir() / DEFAULT_NOTIFICATION_SOUND_NAME


def repo_notification_sound_path(root: Optional[Path] = None) -> Path:
    base = root if root is not None else Path.cwd()
    return base / "resources" / DEFAULT_NOTIFICATION_SOUND_NAME


def default_notification_sound_path(root: Optional[Path] = None) -> str:
    installed = programdata_notification_sound_path()
    if installed.exists():
        return str(installed)
    repo_path = repo_notification_sound_path(root)
    if repo_path.exists():
        return str(repo_path)
    return DEFAULT_NOTIFICATION_SOUND_RELATIVE


def resolve_notification_sound_path(path: str, root: Optional[Path] = None) -> Optional[Path]:
    raw = str(path or "").strip()
    if not raw:
        return None

    expanded = Path(os.path.expandvars(os.path.expanduser(raw)))
    if expanded.is_absolute():
        return expanded if expanded.exists() else None

    normalized = raw.replace("\\", "/").lower()
    if normalized in {
        DEFAULT_NOTIFICATION_SOUND_RELATIVE,
        DEFAULT_NOTIFICATION_SOUND_NAME,
        f"./{DEFAULT_NOTIFICATION_SOUND_RELATIVE}",
    }:
        installed = programdata_notification_sound_path()
        if installed.exists():
            return installed

    base = root if root is not None else Path.cwd()
    candidate = base / expanded
    if candidate.exists():
        return candidate

    if normalized == DEFAULT_NOTIFICATION_SOUND_NAME:
        repo_path = repo_notification_sound_path(base)
        if repo_path.exists():
            return repo_path

    return None
