"""Operating-system data roots: the single owner of per-OS base directories.

Every SRPSS path authority (settings store, data/cache root, logs, curated
presets/themes, sounds) derives its folder from one of these roots instead of
reading ``%APPDATA%``/``%PROGRAMDATA%`` itself. Callers append their own
``SRPSS/...`` suffix.

Windows resolution is the historical contract and must not change:

=====================  ==========================================  =========================
root                   Windows                                     Linux (XDG base dirs)
=====================  ==========================================  =========================
user roaming           ``%APPDATA%`` else ``~/AppData/Roaming``    ``$XDG_CONFIG_HOME`` else ``~/.config``
machine shared         ``%PROGRAMDATA%`` else ``C:\\ProgramData``  ``$XDG_DATA_HOME`` else ``~/.local/share``
user local (optional)  ``%LOCALAPPDATA%`` else none                ``$XDG_STATE_HOME`` else ``~/.local/state``
=====================  ==========================================  =========================

Linux installs are per-user, so the "machine shared" curated tree (installed
presets/themes/sounds) is the user's XDG data home. The XDG variables are the
operating system's own location contract (the counterpart of ``%APPDATA%``);
SRPSS configuration never uses environment variables.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")


def _xdg_root(variable: str, default_relative: str) -> Path:
    value = os.environ.get(variable, "").strip()
    # The XDG spec ignores relative paths.
    if value and os.path.isabs(value):
        return Path(value)
    return (Path.home() / default_relative).resolve()


def user_roaming_root() -> Path:
    """Return the per-user settings root (``%APPDATA%`` on Windows)."""

    if IS_WINDOWS:
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata)
        return (Path.home() / "AppData" / "Roaming").resolve()
    return _xdg_root("XDG_CONFIG_HOME", ".config")


def machine_shared_root() -> Path:
    """Return the curated shared-data root (``%PROGRAMDATA%`` on Windows)."""

    if IS_WINDOWS:
        return Path(os.getenv("PROGRAMDATA", r"C:\ProgramData"))
    return _xdg_root("XDG_DATA_HOME", ".local/share")


def configured_machine_shared_root() -> Optional[Path]:
    """Like :func:`machine_shared_root`, but ``None`` when Windows defines no ``%PROGRAMDATA%``."""

    if IS_WINDOWS:
        program_data = os.getenv("PROGRAMDATA")
        return Path(program_data) if program_data else None
    return machine_shared_root()


def user_local_root() -> Optional[Path]:
    """Return the per-user local (non-roaming) root, or ``None`` when Windows defines none."""

    if IS_WINDOWS:
        local_app_data = os.getenv("LOCALAPPDATA")
        return Path(local_app_data) if local_app_data else None
    return _xdg_root("XDG_STATE_HOME", ".local/state")


__all__ = [
    "IS_LINUX",
    "IS_WINDOWS",
    "configured_machine_shared_root",
    "machine_shared_root",
    "user_local_root",
    "user_roaming_root",
]
