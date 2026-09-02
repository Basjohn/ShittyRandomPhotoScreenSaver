"""Canonical Settings/Widget theme-root resolution.

Source/dev builds read the repository ``themes/`` tree directly. Installed or
frozen Windows builds read the curated machine-wide tree seeded by the SRPSS
installers at ``%ProgramData%\\SRPSS\\themes``. Widget Themes derive their
``widgets`` child from this same root; there is no second mutable catalogue.

An explicit directory remains the test/tool injection seam and always wins.
Missing installed theme files are handled by the compiled theme fallback in the
catalogue layer rather than by silently merging another filesystem root.
"""

from __future__ import annotations

import builtins
import os
from os import PathLike, fspath
from pathlib import Path
import sys


def _is_frozen_runtime() -> bool:
    """Return whether this process is an installed/frozen SRPSS runtime."""

    if bool(getattr(sys, "frozen", False)):
        return True
    if globals().get("__compiled__", False):
        return True
    if bool(getattr(builtins, "__compiled__", False)):
        return True
    main_mod = sys.modules.get("__main__")
    if main_mod is not None and bool(getattr(main_mod, "__compiled__", False)):
        return True

    argv0 = Path(str(sys.argv[0]) if sys.argv else "").suffix.lower()
    if argv0 in (".exe", ".scr"):
        return True

    executable = Path(getattr(sys, "executable", "") or "")
    executable_name = executable.name.lower()
    if executable_name and executable_name not in ("python.exe", "pythonw.exe"):
        if executable_name.startswith("srpss") or executable_name.endswith(".scr"):
            return True
    return False


def _installed_themes_directory() -> Path:
    """Return the curated machine-wide theme root used beside preset assets."""

    program_data = os.getenv("PROGRAMDATA", r"C:\ProgramData")
    return Path(program_data) / "SRPSS" / "themes"


def _source_themes_directory() -> Path:
    """Return the repository/bundled source theme root for script/dev mode."""

    return Path(__file__).resolve().parent.parent / "themes"


def resolve_settings_themes_directory(
    explicit_directory: str | PathLike[str] | None = None,
) -> Path:
    """Resolve explicit injection -> installed ProgramData -> source ``themes``.

    Frozen builds deliberately do not merge the packaged extraction tree with
    ProgramData. The installer owns curated deployment; catalogue code retains
    its compiled Default Dark fallback if that external tree is unavailable.
    """

    if explicit_directory is not None:
        explicit = str(fspath(explicit_directory)).strip()
        if explicit:
            return Path(explicit)

    if _is_frozen_runtime():
        return _installed_themes_directory()
    return _source_themes_directory()


__all__ = [
    "resolve_settings_themes_directory",
]
