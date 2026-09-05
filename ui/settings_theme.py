"""Settings Dialog theme loading and QWidget QSS adapter.

The semantic Settings theme owns visual values. This module remains responsible
for translating the relevant values into the existing QWidget stylesheet while
preserving the current selector structure and geometry.
"""

from __future__ import annotations

from pathlib import Path
from weakref import WeakSet

try:
    from shiboken6 import Shiboken
except ImportError:  # pragma: no cover - PySide runtime supplies shiboken6
    Shiboken = None

from core.logging.logger import get_logger
from ui.settings_theme_runtime import (
    get_active_settings_theme,
    subscribe_settings_theme,
)
from ui.settings_theme_spec import SettingsThemeSpec
from ui.settings_theme_qss import render_qss_color, render_qss_rgba255

logger = get_logger(__name__)

_THEMED_WIDGETS: WeakSet = WeakSet()


def _theme_rgba(theme: SettingsThemeSpec, token: str) -> str:
    """Render one semantic Settings colour as Qt's integer-alpha rgba syntax."""

    return render_qss_rgba255(theme.color(token))


def _theme_qss_color(theme: SettingsThemeSpec, token: str) -> str:
    """Render one semantic Settings colour without requiring opacity."""

    return render_qss_color(theme.color(token))


def _theme_scaled_alpha(theme: SettingsThemeSpec, token: str, scale: float) -> str:
    """Render a semantic colour with bounded derived alpha for disabled chrome."""

    color = theme.color(token)
    alpha = max(0, min(255, int(round(color.a * float(scale)))))
    return f"rgba({color.r}, {color.g}, {color.b}, {alpha})"


def _load_base_stylesheet() -> str | None:
    """Read the existing base QSS without owning semantic theme values."""

    theme_path = Path(__file__).parent.parent / "themes" / "dark.qss"
    if not theme_path.exists():
        logger.warning(f"[FALLBACK] Theme file not found: {theme_path}")
        return None
    with open(theme_path, "r", encoding="utf-8") as f:
        return f.read()


def _build_custom_styles(theme: SettingsThemeSpec) -> str:
    """Render the Settings-specific QSS for one resolved ThemeSpec."""

    # Preserve the existing QSS selector/geometry architecture. Semantic
    # visual values come from SettingsThemeSpec; selector, typography, spacing,
    # radii and control dimensions remain renderer-owned here.
    return """
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

                #tabButton:disabled {
                    background-color: %(tab_disabled_surface)s;
                    color: %(tab_disabled_text)s;
                    border: 1.5px solid %(tab_disabled_border)s;
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
                    color: %(list_text)s;
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

                /* Collapsible Settings buckets. Geometry and arrow behavior
                   remain in dark.qss / Qt; ThemeSpec owns the palette. */
                QToolButton[autoRaise="true"] {
                    background-color: %(bucket_closed_surface)s;
                    color: %(bucket_closed_text)s;
                    border: 1px solid %(bucket_closed_border)s;
                    border-radius: 3px;
                    padding: 3px 8px;
                    font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
                    font-size: 11px;
                    font-weight: 500;
                }
                QToolButton[autoRaise="true"]:hover {
                    background-color: %(bucket_closed_hover_surface)s;
                    border-color: %(bucket_closed_hover_border)s;
                }
                QToolButton[autoRaise="true"]:checked {
                    background-color: %(bucket_open_surface)s;
                    color: %(bucket_open_text)s;
                    border-color: %(bucket_open_border)s;
                }
                QToolButton[autoRaise="true"]:checked:hover {
                    background-color: %(bucket_open_hover_surface)s;
                }

                /* dark.qss still supplies base geometry; this later rule makes
                   tooltip colours belong to the selected Settings theme. */
                QToolTip {
                    background-color: %(tooltip_surface)s;
                    color: %(tooltip_text)s;
                    border: 1px solid %(tooltip_border)s;
                    border-radius: 4px;
                    padding: 5px 10px;
                    font-size: 12px;
                }

                QLabel {
                    color: %(label_text)s;
                    background-color: rgba(0, 0, 0, 0);
                }
    """ % {
        "dialog_glass": _theme_rgba(theme, "window.dialog_glass"),
        "titlebar_surface": _theme_rgba(theme, "window.titlebar.surface"),
        "titlebar_text": _theme_rgba(theme, "window.titlebar.text"),
        "titlebar_button_surface": _theme_rgba(
            theme,
            "window.titlebar.button.surface",
        ),
        "titlebar_button_hover": _theme_rgba(
            theme,
            "window.titlebar.button.hover",
        ),
        "titlebar_button_pressed": _theme_rgba(
            theme,
            "window.titlebar.button.pressed",
        ),
        "titlebar_close_hover": _theme_rgba(
            theme,
            "window.titlebar.close.hover",
        ),
        "sidebar_surface": _theme_rgba(theme, "navigation.sidebar.surface"),
        "tab_surface": _theme_rgba(theme, "navigation.tab.surface"),
        "tab_text": _theme_rgba(theme, "navigation.tab.text"),
        "tab_hover_surface": _theme_rgba(
            theme,
            "navigation.tab.hover_surface",
        ),
        "tab_hover_text": _theme_rgba(theme, "navigation.tab.hover_text"),
        "tab_selected_surface": _theme_rgba(
            theme,
            "navigation.tab.selected_surface",
        ),
        "tab_selected_text": _theme_rgba(
            theme,
            "navigation.tab.selected_text",
        ),
        "tab_disabled_surface": _theme_scaled_alpha(
            theme, "navigation.tab.surface", 0.45
        ),
        "tab_disabled_text": _theme_rgba(theme, "text.disabled"),
        "tab_disabled_border": _theme_scaled_alpha(theme, "panel.border", 0.55),
        "content_surface": _theme_rgba(theme, "content.surface"),
        "group_surface": _theme_rgba(theme, "panel.group.surface"),
        "panel_border": _theme_rgba(theme, "panel.border"),
        "group_text": _theme_qss_color(theme, "panel.group.text"),
        "group_title_text": _theme_qss_color(theme, "panel.group.title_text"),
        "list_surface": _theme_rgba(theme, "control.list.surface"),
        "list_text": _theme_qss_color(theme, "control.list.text"),
        "list_border": _theme_rgba(theme, "control.list.border"),
        "list_selected_surface": _theme_rgba(
            theme,
            "control.list.selected_surface",
        ),
        "list_selected_accent": _theme_rgba(
            theme,
            "control.list.selected_accent",
        ),
        "list_hover_surface": _theme_rgba(
            theme,
            "control.list.hover_surface",
        ),
        "button_surface": _theme_rgba(theme, "control.button.surface"),
        "button_text": _theme_qss_color(theme, "control.button.text"),
        "button_border": _theme_qss_color(theme, "control.button.border"),
        "button_hover_surface": _theme_rgba(
            theme,
            "control.button.hover_surface",
        ),
        "button_pressed_surface": _theme_rgba(
            theme,
            "control.button.pressed_surface",
        ),
        "button_pressed_border": _theme_rgba(
            theme,
            "control.button.pressed_border",
        ),
        "checkbox_text": _theme_qss_color(theme, "control.checkbox.text"),
        "checkbox_surface": _theme_rgba(
            theme,
            "control.checkbox.indicator.surface",
        ),
        "checkbox_highlight_border": _theme_rgba(
            theme,
            "control.checkbox.indicator.highlight_border",
        ),
        "checkbox_right_shadow_border": _theme_rgba(
            theme,
            "control.checkbox.indicator.right_shadow_border",
        ),
        "checkbox_bottom_shadow_border": _theme_rgba(
            theme,
            "control.checkbox.indicator.bottom_shadow_border",
        ),
        "checkbox_checked_surface": _theme_rgba(
            theme,
            "control.checkbox.checked.surface",
        ),
        "checkbox_checked_highlight_border": _theme_rgba(
            theme,
            "control.checkbox.checked.highlight_border",
        ),
        "checkbox_checked_right_shadow_border": _theme_rgba(
            theme,
            "control.checkbox.checked.right_shadow_border",
        ),
        "checkbox_checked_bottom_shadow_border": _theme_rgba(
            theme,
            "control.checkbox.checked.bottom_shadow_border",
        ),
        "bucket_closed_surface": _theme_rgba(theme, "bucket.closed.surface"),
        "bucket_closed_text": _theme_rgba(theme, "bucket.closed.text"),
        "bucket_closed_border": _theme_rgba(theme, "bucket.closed.border"),
        "bucket_closed_hover_surface": _theme_rgba(
            theme, "bucket.closed.hover_surface"
        ),
        "bucket_closed_hover_border": _theme_rgba(
            theme, "bucket.closed.hover_border"
        ),
        "bucket_open_surface": _theme_rgba(theme, "bucket.open.surface"),
        "bucket_open_text": _theme_rgba(theme, "bucket.open.text"),
        "bucket_open_border": _theme_rgba(theme, "bucket.open.border"),
        "bucket_open_hover_surface": _theme_rgba(
            theme, "bucket.open.hover_surface"
        ),
        "tooltip_surface": _theme_rgba(theme, "tooltip.surface"),
        "tooltip_text": _theme_rgba(theme, "tooltip.text"),
        "tooltip_border": _theme_rgba(theme, "tooltip.border"),
        "label_text": _theme_qss_color(theme, "text.primary"),
    }


def _is_live_qobject(widget) -> bool:
    """Return whether a PySide wrapper still owns a live C++ QObject.

    ``WeakSet`` only tracks Python-wrapper lifetime. PySide can keep that wrapper
    alive briefly after Qt has already deleted the underlying ``SettingsDialog``.
    Theme activation is transactional, so a stale wrapper must be removed before
    it can abort an otherwise-valid live theme change.
    """

    if widget is None:
        return False
    if Shiboken is None:
        return True
    try:
        return bool(Shiboken.isValid(widget))
    except RuntimeError:
        return False


def _apply_theme_to_widget(widget, theme: SettingsThemeSpec) -> bool:
    """Apply one resolved theme to a registered Settings root."""

    if not _is_live_qobject(widget):
        return False

    stylesheet = _load_base_stylesheet()
    if stylesheet is None:
        return False

    widget.setStyleSheet(stylesheet + _build_custom_styles(theme))
    logger.debug("Theme loaded successfully: %s", theme.name)
    return True


def _refresh_registered_widgets(theme: SettingsThemeSpec) -> None:
    """Re-render every live Settings root after an active-theme change.

    Dead PySide wrappers are pruned as an ownership cleanup, not treated as a
    renderer failure. A RuntimeError from a still-valid QWidget remains fatal so
    the runtime transaction can correctly roll the theme back.
    """

    for widget in tuple(_THEMED_WIDGETS):
        if not _is_live_qobject(widget):
            _THEMED_WIDGETS.discard(widget)
            continue
        try:
            _apply_theme_to_widget(widget, theme)
        except RuntimeError:
            if not _is_live_qobject(widget):
                _THEMED_WIDGETS.discard(widget)
                continue
            raise


def load_theme(widget) -> None:
    """Register a Settings root and apply the currently active ThemeSpec."""

    try:
        _THEMED_WIDGETS.add(widget)
        _apply_theme_to_widget(widget, get_active_settings_theme())
    except Exception as e:
        logger.exception(f"Failed to load theme: {e}")


# Keep the subscription module-level and stable; the runtime authority retains
# this renderer callback for the process lifetime.
_THEME_UNSUBSCRIBE = subscribe_settings_theme(_refresh_registered_widgets)
