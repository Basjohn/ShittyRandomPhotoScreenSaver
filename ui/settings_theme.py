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


def _theme_hex(token: str) -> str:
    """Render one opaque semantic Settings colour in legacy QSS hex form."""

    value = _SETTINGS_THEME.color(token)
    if value.a != 255:
        raise ValueError(f"Settings theme colour {token!r} is not opaque")
    return f"#{value.r:02x}{value.g:02x}{value.b:02x}"


def load_theme(widget) -> None:
    """Load the base dark QSS plus Settings-specific semantic theme values."""
    try:
        theme_path = Path(__file__).parent.parent / "themes" / "dark.qss"
        if theme_path.exists():
            with open(theme_path, "r", encoding="utf-8") as f:
                stylesheet = f.read()

                # Preserve the existing QSS selector/geometry architecture.
                # Semantic visual values come from SettingsThemeSpec; selector,
                # typography, spacing, radii and control dimensions remain here.
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
                    background-color: %(list_surface)s;
                    color: %(list_text)s;
                    border: 1px solid %(list_border)s;
                    border-radius: 8px;
                    padding: 4px;
                }

                QListWidget::item:selected {
                    background-color: %(list_selected_surface)s;
                    border-left: 3px solid %(list_selected_accent)s;
                }

                QListWidget::item:hover {
                    background-color: %(list_hover_surface)s;
                }

                QPushButton {
                    background-color: %(button_surface)s;
                    color: %(button_text)s;
                    border-radius: 8px;
                    padding: 7px 18px;
                    font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
                    font-weight: 500;
                    font-size: 14px;
                    border: 1.25px solid %(button_border)s;
                }

                QPushButton:hover {
                    background-color: %(button_hover_surface)s;
                    border: 1.25px solid %(button_border)s;
                }

                QPushButton:pressed {
                    background-color: %(button_pressed_surface)s;
                    border: 1.25px solid %(button_pressed_border)s;
                }

                QGroupBox {
                    background-color: %(group_surface)s;
                    border: 1px solid %(panel_border)s;
                    border-radius: 18px;
                    margin-top: 20px;
                    margin-bottom: 12px;
                    padding: 18px 24px 18px 24px;
                    color: %(group_text)s;
                }

                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 2px 10px;
                    margin-top: 5px;
                    color: %(group_title_text)s;
                    font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
                    font-weight: 800;
                    font-size: 15px;
                    letter-spacing: 0.5px;
                }

                QCheckBox {
                    color: %(checkbox_text)s;
                    spacing: 8px;
                }

                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    background-color: %(checkbox_surface)s;
                    border-radius: 3px;
                    border-top: 1px solid %(checkbox_highlight_border)s;
                    border-left: 1px solid %(checkbox_highlight_border)s;
                    border-right: 2px solid %(checkbox_right_shadow_border)s;
                    border-bottom: 2px solid %(checkbox_bottom_shadow_border)s;
                }

                QCheckBox::indicator:checked {
                    background-color: %(checkbox_checked_surface)s;
                    border-top: 1px solid %(checkbox_checked_highlight_border)s;
                    border-left: 1px solid %(checkbox_checked_highlight_border)s;
                    border-right: 2px solid %(checkbox_checked_right_shadow_border)s;
                    border-bottom: 2px solid %(checkbox_checked_bottom_shadow_border)s;
                }

                QLabel {
                    color: %(label_text)s;
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
                    "group_text": _theme_hex("panel.group.text"),
                    "group_title_text": _theme_hex("panel.group.title_text"),
                    "list_surface": _theme_rgba("control.list.surface"),
                    "list_text": _theme_hex("control.list.text"),
                    "list_border": _theme_rgba("control.list.border"),
                    "list_selected_surface": _theme_rgba(
                        "control.list.selected_surface"
                    ),
                    "list_selected_accent": _theme_rgba(
                        "control.list.selected_accent"
                    ),
                    "list_hover_surface": _theme_rgba(
                        "control.list.hover_surface"
                    ),
                    "button_surface": _theme_rgba("control.button.surface"),
                    "button_text": _theme_hex("control.button.text"),
                    "button_border": _theme_hex("control.button.border"),
                    "button_hover_surface": _theme_rgba(
                        "control.button.hover_surface"
                    ),
                    "button_pressed_surface": _theme_rgba(
                        "control.button.pressed_surface"
                    ),
                    "button_pressed_border": _theme_rgba(
                        "control.button.pressed_border"
                    ),
                    "checkbox_text": _theme_hex("control.checkbox.text"),
                    "checkbox_surface": _theme_rgba(
                        "control.checkbox.indicator.surface"
                    ),
                    "checkbox_highlight_border": _theme_rgba(
                        "control.checkbox.indicator.highlight_border"
                    ),
                    "checkbox_right_shadow_border": _theme_rgba(
                        "control.checkbox.indicator.right_shadow_border"
                    ),
                    "checkbox_bottom_shadow_border": _theme_rgba(
                        "control.checkbox.indicator.bottom_shadow_border"
                    ),
                    "checkbox_checked_surface": _theme_rgba(
                        "control.checkbox.checked.surface"
                    ),
                    "checkbox_checked_highlight_border": _theme_rgba(
                        "control.checkbox.checked.highlight_border"
                    ),
                    "checkbox_checked_right_shadow_border": _theme_rgba(
                        "control.checkbox.checked.right_shadow_border"
                    ),
                    "checkbox_checked_bottom_shadow_border": _theme_rgba(
                        "control.checkbox.checked.bottom_shadow_border"
                    ),
                    "label_text": _theme_hex("text.primary"),
                }

                widget.setStyleSheet(stylesheet + custom_styles)
                logger.debug("Theme loaded successfully")
        else:
            logger.warning(f"[FALLBACK] Theme file not found: {theme_path}")
    except Exception as e:
        logger.exception(f"Failed to load theme: {e}")
