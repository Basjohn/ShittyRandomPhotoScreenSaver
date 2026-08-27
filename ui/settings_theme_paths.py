"""Temporary packaged-theme directory resolution.

This module is intentionally disposable. It lets source/dev builds exercise
file-backed Settings themes before frozen-build scripts own the real packaged
resource path.

Build/release authority must replace ``THEMES_DIRECTORY_BUILD_REPLACE_BLANK``
or pass an explicit directory, then retire this stub/dev fallback once the
packaged-resource contract is durable. External theme failure can never remove
compiled ``DEFAULT_DARK_SETTINGS_THEME``.
"""

from __future__ import annotations

from os import PathLike, fspath
from pathlib import Path


# BUILD/RELEASE WIRING: replace this blank with the packaged themes-directory
# authority, or keep passing an explicit directory into SettingsDialog.
# The grotesque name is deliberate so nobody mistakes this for final policy.
THEMES_DIRECTORY_BUILD_REPLACE_BLANK: str = ""


def resolve_settings_themes_directory(
    explicit_directory: str | PathLike[str] | None = None,
) -> Path:
    """Resolve explicit -> build stub -> repository-local ``themes/``."""

    if explicit_directory is not None:
        explicit = str(fspath(explicit_directory)).strip()
        if explicit:
            return Path(explicit)

    build_value = str(THEMES_DIRECTORY_BUILD_REPLACE_BLANK).strip()
    if build_value:
        return Path(build_value)

    # ui/settings_theme_paths.py -> project root -> themes/
    # Missing directories remain safe because the catalogue always has the
    # compiled Default Dark entry.
    return Path(__file__).resolve().parent.parent / "themes"


__all__ = [
    "THEMES_DIRECTORY_BUILD_REPLACE_BLANK",
    "resolve_settings_themes_directory",
]
