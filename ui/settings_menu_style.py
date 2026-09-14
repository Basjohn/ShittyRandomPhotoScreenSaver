"""Narrow QWidget menu styles owned by the Settings theme system.

The legacy Settings base-stylesheet monolith used to be loaded by the system tray
solely so one QMenu family inherited its old rules.  Menu structure belongs to
this renderer; colours remain semantic SettingsThemeSpec values.
"""
from __future__ import annotations

from ui.settings_theme_qss import render_qss_rgba255
from ui.settings_theme_runtime import get_active_settings_theme
from ui.settings_theme_spec import SettingsThemeSpec


def _rgba(theme: SettingsThemeSpec, token: str) -> str:
    return render_qss_rgba255(theme.color(token))


def build_tray_menu_stylesheet(
    theme: SettingsThemeSpec | None = None,
) -> str:
    """Render the tray QMenu without a dependency on the legacy base QSS.

    Geometry intentionally preserves the old tray-menu QMenu family.  Visual
    values come from the active Settings theme's existing context-menu roles so
    the tray no longer needs a second dark-only palette authority.
    """

    resolved = theme or get_active_settings_theme()
    return f"""
        QMenu {{
            background-color: {_rgba(resolved, 'context.menu.surface')};
            color: {_rgba(resolved, 'context.menu.text')};
            border: 1px solid {_rgba(resolved, 'context.menu.border')};
            padding: 4px;
            border-radius: 4px;
        }}
        QMenu::item {{
            padding: 6px 25px 6px 20px;
            border-radius: 2px;
        }}
        QMenu::item:selected {{
            background-color: {_rgba(resolved, 'context.menu.selected_surface')};
        }}
        QMenu::item:disabled {{
            color: {_rgba(resolved, 'context.menu.disabled_text')};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {_rgba(resolved, 'context.menu.separator')};
            margin: 4px 0;
        }}
    """


__all__ = ["build_tray_menu_stylesheet"]
