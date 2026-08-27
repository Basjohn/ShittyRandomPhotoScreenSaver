"""Settings Dialog theme loading and QWidget QSS adapter.

The semantic Settings theme owns visual values. This module remains responsible
for translating the relevant values into the existing QWidget stylesheet while
preserving the current selector structure and geometry.
"""

from __future__ import annotations

from pathlib import Path

from core.logging.logger import get_logger
from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME

logger = get_logger(__name__)

_SETTINGS_THEME = DEFAULT_DARK_SETTINGS_THEME


def _theme_rgba(token: str) -> str:
    """Render one semantic Settings colour as Qt's integer-alpha rgba syntax."""

    value = _SETTINGS_THEME.color(token)
    return f"rgba({value.r}, {value.g}, {value.b}, {value.a})"


def load_theme(widget) -> None:
    """Load the base dark QSS plus Settings-specific semantic theme values."""
    try:
        theme_path = Path(__file__).parent.parent / "themes" / "dark.qss"
        if theme_path.exists():
            with open(theme_path, "r", encoding="utf-8") as f:
                stylesheet = f.read()

                # Preserve the existing QSS selector/geometry architecture.
                # Only visual values already owned by SettingsThemeSpec are
                # substituted here; the remaining control palette migrates
                # with its owning component modules later.
                custom_styles = """
                /* Settings Dialog Custom Styles
                   NOTE: Qt QSS rgba() alpha MUST be integer 0-255.
                   Float values (e.g. 0.8) are truncated to 0! */
                QDialog {
                    background-color: transparent;
                    border: none;
                }

                #dialogContainer {
                    background-color: %(dialog_glass)s;
                    border: none;
                }

                #customTitleBar {
                    background-color: %(titlebar_surface)s;
                }

                #titleBarLabel {
                    color: %(titlebar_text)s;
                    padding-left: 10px;
                    padding-top: 3px;
                }

                #titleBarButton {
                    background-color: %(titlebar_button_surface)s;
                    color: %(titlebar_text)s;
                    border: none;
                    border-radius: 4px;
                    padding: 0px;
                    margin: 0px;
                    font-size: 16px;
                    font-weight: bold;
                }

                #titleBarButton:hover {
                    background-color: %(titlebar_button_hover)s;
                }

                #titleBarButton:pressed {
                    background-color: %(titlebar_button_pressed)s;
                    margin-top: 0px;
                    margin-left: 0px;
                }

                #titleBarCloseButton {
                    background-color: %(titlebar_button_surface)s;
                    color: %(titlebar_text)s;
                    border: none;
                    border-radius: 4px;
                    padding: 0px;
                    margin: 0px;
                    font-size: 18px;
                    font-weight: bold;
                }

                #titleBarCloseButton:hover {
                    background-color: %(titlebar_close_hover)s;
                }

                #titleBarCloseButton:pressed {
                    margin-top: 0px;
                    margin-left: 0px;
                }

                #sidebar {
                    background-color: %(sidebar_surface)s;
                    border: 1.75px solid %(panel_border)s;
                    border-radius: 8px;
                }

                #tabButton {
                    background-color: %(tab_surface)s;
                    color: %(tab_text)s;
                    text-align: left;
                    padding: 10px 20px;
                    margin: 3px 5px 5px 3px;
                    border-radius: 6px;
                    border: 1.5px solid %(panel_border)s;
                    font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
                    font-weight: 600;
                    font-size: 15px;
                }

                #tabButton:hover {
                    background-color: %(tab_hover_surface)s;
                    color: %(tab_hover_text)s;
                    border: 1.5px solid %(panel_border)s;
                }

                #tabButton:checked {
                    background-color: %(tab_selected_surface)s;
                    color: %(tab_selected_text)s;
                    font-weight: 700;
                    border: 1.5px solid %(panel_border)s;
                }

                #contentArea {
                    background-color: %(content_surface)s;
                    border: 1.75px solid %(panel_border)s;
                    border-radius: 8px;
                    padding: 20px;
                }

                #contentArea > QWidget {
                    background: transparent;
                }

                QListWidget {
                    background-color: rgba(30, 30, 30, 215);
                    color: #ffffff;
                    border: 1px solid rgba(80, 80, 80, 153);
                    border-radius: 8px;
                    padding: 4px;
                }

                QListWidget::item:selected {
                    background-color: rgba(70, 70, 70, 204);
                    border-left: 3px solid rgba(255, 255, 255, 180);
                }

                QListWidget::item:hover {
                    background-color: rgba(55, 55, 55, 204);
                }

                QPushButton {
                    background-color: rgba(45, 45, 45, 215);
                    color: #ffffff;
                    border-radius: 8px;
                    padding: 7px 18px;
                    font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
                    font-weight: 500;
                    font-size: 14px;
                    border: 1.25px solid #ffffff;
                }

                QPushButton:hover {
                    background-color: rgba(60, 60, 60, 220);
                    border: 1.25px solid #ffffff;
                }

                QPushButton:pressed {
                    background-color: rgba(35, 35, 35, 220);
                    border: 1.25px solid rgba(200, 200, 200, 200);
                }

                QGroupBox {
                    background-color: %(group_surface)s;
                    border: 1px solid %(panel_border)s;
                    border-radius: 18px;
                    margin-top: 20px;
                    margin-bottom: 12px;
                    padding: 18px 24px 18px 24px;
                    color: #ffffff;
                }

                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 2px 10px;
                    margin-top: 5px;
                    color: #ffffff;
                    font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
                    font-weight: 800;
                    font-size: 15px;
                    letter-spacing: 0.5px;
                }

                QCheckBox {
                    color: #ffffff;
                    spacing: 8px;
                }

                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    background-color: rgba(45, 45, 45, 204);
                    border-radius: 3px;
                    border-top: 1px solid rgba(90, 90, 90, 191);
                    border-left: 1px solid rgba(90, 90, 90, 191);
                    border-right: 2px solid rgba(0, 0, 0, 179);
                    border-bottom: 2px solid rgba(0, 0, 0, 191);
                }

                QCheckBox::indicator:checked {
                    background-color: rgba(210, 210, 210, 217);
                    border-top: 1px solid rgba(200, 200, 200, 204);
                    border-left: 1px solid rgba(200, 200, 200, 204);
                    border-right: 2px solid rgba(60, 60, 60, 179);
                    border-bottom: 2px solid rgba(60, 60, 60, 191);
                }

                QLabel {
                    color: #ffffff;
                    background-color: rgba(0, 0, 0, 0);
                }
                """ % {
                    "dialog_glass": _theme_rgba("window.dialog_glass"),
                    "titlebar_surface": _theme_rgba("window.titlebar.surface"),
                    "titlebar_text": _theme_rgba("window.titlebar.text"),
                    "titlebar_button_surface": _theme_rgba(
                        "window.titlebar.button.surface"
                    ),
                    "titlebar_button_hover": _theme_rgba(
                        "window.titlebar.button.hover"
                    ),
                    "titlebar_button_pressed": _theme_rgba(
                        "window.titlebar.button.pressed"
                    ),
                    "titlebar_close_hover": _theme_rgba(
                        "window.titlebar.close.hover"
                    ),
                    "sidebar_surface": _theme_rgba("navigation.sidebar.surface"),
                    "tab_surface": _theme_rgba("navigation.tab.surface"),
                    "tab_text": _theme_rgba("navigation.tab.text"),
                    "tab_hover_surface": _theme_rgba(
                        "navigation.tab.hover_surface"
                    ),
                    "tab_hover_text": _theme_rgba("navigation.tab.hover_text"),
                    "tab_selected_surface": _theme_rgba(
                        "navigation.tab.selected_surface"
                    ),
                    "tab_selected_text": _theme_rgba(
                        "navigation.tab.selected_text"
                    ),
                    "content_surface": _theme_rgba("content.surface"),
                    "group_surface": _theme_rgba("panel.group.surface"),
                    "panel_border": _theme_rgba("panel.border"),
                }

                widget.setStyleSheet(stylesheet + custom_styles)
                logger.debug("Theme loaded successfully")
        else:
            logger.warning(f"[FALLBACK] Theme file not found: {theme_path}")
    except Exception as e:
        logger.exception(f"Failed to load theme: {e}")
