"""Resolved Widget Theme catalogue directory.

Widget Themes share the Settings theme root and live in its ``widgets`` child.
Path policy therefore stays with the same startup/build seam instead of being
reimplemented by retained renderers or Settings tabs.
"""
from __future__ import annotations

from os import PathLike
from pathlib import Path

from ui.settings_theme_paths import resolve_settings_themes_directory


def resolve_widget_themes_directory(
    themes_root: str | PathLike[str] | None = None,
) -> Path:
    """Resolve the active theme root, then return its ``widgets`` child."""

    return resolve_settings_themes_directory(themes_root) / "widgets"


__all__ = ["resolve_widget_themes_directory"]
