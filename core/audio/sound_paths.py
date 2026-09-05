"""Default notification sound path helpers."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

DEFAULT_NOTIFICATION_SOUND_NAME = "tutuogg.ogg"
DEFAULT_NOTIFICATION_SOUND_RELATIVE = f"resources/{DEFAULT_NOTIFICATION_SOUND_NAME}"
JEDI_MODE_SOUND_NAME = "jedimodeyall.mp3"
JEDI_MODE_SOUND_RELATIVE = f"resources/{JEDI_MODE_SOUND_NAME}"


def programdata_sound_dir() -> Path:
    base = os.environ.get("PROGRAMDATA") or r"C:\ProgramData"
    return Path(base) / "SRPSS" / "sounds"


def bundled_resource_root() -> Path:
    """Return the source/onefile extraction root containing ``resources``."""

    return Path(__file__).resolve().parents[2]


def programdata_notification_sound_path() -> Path:
    return programdata_sound_dir() / DEFAULT_NOTIFICATION_SOUND_NAME


def repo_notification_sound_path(root: Optional[Path] = None) -> Path:
    base = root if root is not None else Path.cwd()
    return base / "resources" / DEFAULT_NOTIFICATION_SOUND_NAME


def programdata_jedi_mode_sound_path() -> Path:
    return programdata_sound_dir() / JEDI_MODE_SOUND_NAME


def repo_jedi_mode_sound_path(root: Optional[Path] = None) -> Path:
    base = root if root is not None else Path.cwd()
    return base / "resources" / JEDI_MODE_SOUND_NAME


def default_jedi_mode_sound_path(root: Optional[Path] = None) -> str:
    installed = programdata_jedi_mode_sound_path()
    if installed.exists():
        return str(installed)
    bundled = bundled_resource_root() / "resources" / JEDI_MODE_SOUND_NAME
    if bundled.exists():
        return str(bundled)
    repo_path = repo_jedi_mode_sound_path(root)
    if repo_path.exists():
        return str(repo_path)
    return JEDI_MODE_SOUND_RELATIVE


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

    bundled_candidate = bundled_resource_root() / expanded
    if bundled_candidate.exists():
        return bundled_candidate

    base = root if root is not None else Path.cwd()
    candidate = base / expanded
    if candidate.exists():
        return candidate

    if normalized == DEFAULT_NOTIFICATION_SOUND_NAME:
        repo_path = repo_notification_sound_path(base)
        if repo_path.exists():
            return repo_path

    return None


def resolve_jedi_mode_sound_path(
    path: str, root: Optional[Path] = None
) -> Optional[Path]:
    raw = str(path or "").strip()
    if not raw:
        return None
    expanded = Path(os.path.expandvars(os.path.expanduser(raw)))
    if expanded.is_absolute():
        return expanded if expanded.exists() else None
    normalized = raw.replace("\\", "/").lower()
    if normalized in {
        JEDI_MODE_SOUND_RELATIVE,
        JEDI_MODE_SOUND_NAME,
        f"./{JEDI_MODE_SOUND_RELATIVE}",
    }:
        installed = programdata_jedi_mode_sound_path()
        if installed.exists():
            return installed
        bundled = bundled_resource_root() / "resources" / JEDI_MODE_SOUND_NAME
        if bundled.exists():
            return bundled
    base = root if root is not None else Path.cwd()
    candidate = base / expanded
    if candidate.exists():
        return candidate
    if normalized == JEDI_MODE_SOUND_NAME:
        repo_path = repo_jedi_mode_sound_path(base)
        if repo_path.exists():
            return repo_path
    return None
