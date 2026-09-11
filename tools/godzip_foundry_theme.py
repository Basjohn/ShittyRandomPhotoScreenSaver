"""Settings-theme bridge for the standalone SRPSS Foundry tools.

Foundries are tools, not SettingsDialog children. They therefore never read or
write product Settings state merely to look like Settings. This module reuses
the validated Settings theme catalogue + ThemeSpec semantics while each tool
keeps its own appearance preference.

Theme files are a deliberate frozen snapshot under ``tools/godzip_themes``.
They do not follow the application's live ``themes`` directory automatically:
repair tools must stay visually usable while the product tree is being changed.
The requested default is Default Dark Glass. If that snapshot is unavailable,
a Glass-backed fallback is derived from compiled Default Dark rather than from a
second hand-written palette.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from ui.settings_theme_catalog import (
    SettingsThemeCatalog,
    build_settings_theme_catalog,
    resolve_theme_selection,
)
from ui.settings_theme_qss import render_qss_color, render_qss_rgba255
from ui.settings_theme_spec import (
    DEFAULT_DARK_SETTINGS_THEME,
    NativeBackdropStyle,
    Rgba,
    SettingsThemeSpec,
)


FOUNDRY_DEFAULT_THEME_ID = "file:Default Dark [Single] [Glass].srtheme"
FOUNDRY_THEME_DIRECTORY = Path(__file__).resolve().parent / "godzip_themes"


@dataclass(frozen=True, slots=True)
class FoundryThemeResolution:
    """One resolved Foundry theme selection plus discovery diagnostics."""

    theme_id: str
    theme: SettingsThemeSpec
    catalog: SettingsThemeCatalog
    used_fallback: bool
    warning: str | None = None


def _glass_fallback_theme() -> SettingsThemeSpec:
    """Return compiled Default Dark visuals with the requested Glass material."""

    return replace(
        DEFAULT_DARK_SETTINGS_THEME,
        name="Default Dark [Foundry Glass Fallback]",
        backdrop=NativeBackdropStyle(
            mode="glass",
            tint=Rgba(24, 24, 24, 0),
        ),
    )


def resolve_foundry_theme(
    requested_theme_id: str | None,
) -> FoundryThemeResolution:
    """Resolve Foundry's bundled theme without touching product Settings."""

    catalog = build_settings_theme_catalog(FOUNDRY_THEME_DIRECTORY)
    requested = str(requested_theme_id or FOUNDRY_DEFAULT_THEME_ID).strip()
    if not requested:
        requested = FOUNDRY_DEFAULT_THEME_ID

    direct = catalog.entry_by_id(requested)
    if direct is not None:
        return FoundryThemeResolution(
            theme_id=direct.theme_id,
            theme=direct.theme,
            catalog=catalog,
            used_fallback=False,
        )

    # A missing user-selected theme falls back to the explicit Foundry default
    # before considering the compiled catalogue fallback.  This keeps the tool
    # visually stable even if a user removes a custom theme file.
    preferred = catalog.entry_by_id(FOUNDRY_DEFAULT_THEME_ID)
    if preferred is not None:
        warning = f"Theme {requested!r} is unavailable; using {preferred.name}."
        return FoundryThemeResolution(
            theme_id=preferred.theme_id,
            theme=preferred.theme,
            catalog=catalog,
            used_fallback=True,
            warning=warning,
        )

    resolution = resolve_theme_selection(catalog, requested)
    warning = resolution.error or (
        "Default Dark Glass theme file is unavailable; using the compiled "
        "Default Dark palette with Glass backdrop."
    )
    return FoundryThemeResolution(
        theme_id=FOUNDRY_DEFAULT_THEME_ID,
        theme=_glass_fallback_theme(),
        catalog=catalog,
        used_fallback=True,
        warning=warning,
    )


def theme_choices(catalog: SettingsThemeCatalog) -> tuple[tuple[str, str], ...]:
    """Return selectable ``(theme_id, name)`` pairs in catalogue order."""

    return tuple((entry.theme_id, entry.name) for entry in catalog.entries)


def _rgba(theme: SettingsThemeSpec, token: str) -> str:
    return render_qss_rgba255(theme.color(token))


def _color(theme: SettingsThemeSpec, token: str) -> str:
    return render_qss_color(theme.color(token))


def render_foundry_stylesheet(theme: SettingsThemeSpec) -> str:
    """Render Foundry chrome entirely from Settings ``ThemeSpec`` semantics.

    Foundry deliberately owns its QSS structure while consuming the same semantic
    colour/backdrop roles as Settings.  It does not import ``themes/dark.qss`` or
    mutate the product Settings theme selection.
    """

    # Foundry owns its structural QSS.  It consumes Settings ThemeSpec colour
    # semantics but deliberately does not consume themes/dark.qss; that file is
    # itself scheduled for retirement from the product Settings architecture.
    base = ""
    primary = _color(theme, "text.primary")
    secondary = _color(theme, "text.secondary")
    tertiary = _color(theme, "text.tertiary")
    helper = _rgba(theme, "text.helper")
    panel = _rgba(theme, "panel.group.surface")
    subsection = _rgba(theme, "panel.subsection.surface")
    border = _rgba(theme, "panel.border")
    dialog = _rgba(theme, "window.dialog_glass")
    titlebar = _rgba(theme, "window.titlebar.surface")
    title_text = _color(theme, "window.titlebar.text")
    tab_surface = _rgba(theme, "navigation.subtab.surface")
    tab_hover = _rgba(theme, "navigation.subtab.hover_surface")
    tab_selected = _rgba(theme, "navigation.subtab.selected_surface")
    tab_text = _color(theme, "navigation.subtab.text")
    button_surface = _rgba(theme, "control.button.surface")
    button_hover = _rgba(theme, "control.button.hover_surface")
    button_pressed = _rgba(theme, "control.button.pressed_surface")
    button_border = _rgba(theme, "control.button.border")
    button_text = _color(theme, "control.button.text")
    action_surface = _rgba(theme, "control.setup_action.surface")
    action_hover = _rgba(theme, "control.setup_action.hover_surface")
    action_pressed = _rgba(theme, "control.setup_action.pressed_surface")
    action_border = _rgba(theme, "control.setup_action.border")
    action_text = _color(theme, "control.setup_action.text")
    input_surface = _rgba(theme, "control.input.surface")
    input_focus = _rgba(theme, "control.input.focus_surface")
    input_border = _rgba(theme, "control.input.border")
    input_text = _color(theme, "control.input.text")
    list_surface = _rgba(theme, "control.list.surface")
    list_border = _rgba(theme, "control.list.border")
    list_selected = _rgba(theme, "control.list.selected_surface")
    list_hover = _rgba(theme, "control.list.hover_surface")
    list_text = _color(theme, "control.list.text")
    checkbox_text = _color(theme, "control.checkbox.text")
    checkbox_surface = _rgba(theme, "control.checkbox.indicator.surface")
    checkbox_border = _rgba(theme, "control.checkbox.indicator.highlight_border")
    checkbox_checked = _rgba(theme, "control.checkbox.checked.surface")
    checkbox_checked_border = _rgba(theme, "control.checkbox.checked.highlight_border")
    tooltip_surface = _rgba(theme, "tooltip.surface")
    tooltip_text = _color(theme, "tooltip.text")
    tooltip_border = _rgba(theme, "tooltip.border")
    popup_surface = _rgba(theme, "popup.container.surface")
    popup_border = _rgba(theme, "popup.container.border")
    popup_title = _rgba(theme, "popup.title.text")
    popup_message = _rgba(theme, "popup.message.text")
    success = _color(theme, "popup.icon.success")
    warning = _color(theme, "popup.icon.warning")
    error = _color(theme, "popup.icon.error")

    return base + f"""
        QMainWindow {{ background: transparent; }}
        QWidget#root, QWidget#defaultsFoundryRoot, QWidget#themeFoundryRoot {{ background: {dialog}; color: {primary}; border: 1px solid {border}; border-radius: 10px; }}
        QWidget {{ color: {primary}; font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif'; font-size: 10pt; }}

        QFrame#shell {{ background: {subsection}; border: 1px solid {border}; border-radius: 10px; }}
        QFrame#foundryHeader {{ background: {titlebar}; border: none; border-bottom: 1px solid {border}; }}
        QLabel#appTitle, QLabel#defaultsFoundryTitle, QLabel#themeFoundryTitle {{ color: {title_text}; font-size: 19pt; font-weight: 800; letter-spacing: 1px; }}
        QLabel#subtitle, QLabel#muted, QLabel#defaultsFoundrySubtitle, QLabel#themeFoundrySubtitle {{ color: {secondary}; }}
        QLabel#faint {{ color: {tertiary}; }}
        QLabel#repoPath {{ color: {tertiary}; padding: 1px 2px 5px 2px; }}
        QLabel#sectionTitle {{ color: {primary}; font-size: 12pt; font-weight: 750; }}
        QLabel#archiveName {{ color: {primary}; font-size: 11pt; font-weight: 650; }}
        QLabel#status {{ color: {secondary}; padding: 2px 4px; }}
        QLabel#warningText {{ color: {popup_title}; background: {popup_surface}; border: 1px solid {popup_border}; border-radius: 6px; padding: 7px; }}
        QLabel#chip {{ background: {tab_surface}; border: 1px solid {border}; border-radius: 9px; padding: 4px 9px; color: {secondary}; font-weight: 600; }}
        QLabel#chip[dirty="true"] {{ color: {warning}; border-color: {warning}; }}
        QLabel#chip[dirty="false"] {{ color: {success}; }}

        QFrame#panel {{ background: {panel}; border: 1px solid {border}; border-radius: 8px; }}
        QFrame#dropPanel {{ background: {tab_surface}; border: 1px dashed {border}; border-radius: 8px; }}
        QFrame#dropPanel[dragActive="true"] {{ background: {tab_selected}; border-style: solid; }}
        QLabel#dropTitle {{ color: {title_text}; font-size: 16pt; font-weight: 850; letter-spacing: 1px; }}
        QLabel#dropHint {{ color: {secondary}; font-size: 9pt; }}

        QTabWidget::pane {{ border: 1px solid {border}; background: transparent; top: -1px; border-radius: 8px; }}
        QTabBar::tab {{ background: {tab_surface}; color: {secondary}; border: 1px solid {border}; padding: 9px 15px; margin-right: 3px; border-radius: 8px; font-weight: 650; }}
        QTabBar::tab:selected {{ background: {tab_selected}; color: {tab_text}; }}
        QTabBar::tab:hover {{ background: {tab_hover}; color: {tab_text}; }}


        QFrame#toolTitleBar {{ background: {titlebar}; border: none; border-bottom: 1px solid {border}; }}
        QLabel#toolTitleLabel {{ color: {title_text}; font-size: 15pt; font-weight: 800; letter-spacing: 1px; padding-left: 2px; }}
        QPushButton#toolTitleButton, QPushButton#toolTitleSettingsButton, QPushButton#toolTitleCloseButton {{ background: transparent; color: {title_text}; border: none; border-radius: 5px; padding: 0px; font-size: 15px; font-weight: 700; }}
        QPushButton#toolTitleButton:hover, QPushButton#toolTitleSettingsButton:hover {{ background: {tab_hover}; }}
        QPushButton#toolTitleCloseButton:hover {{ background: {error}; }}
        QPushButton#cmdTabButton {{ background: {tab_surface}; color: {secondary}; border: 1px solid {border}; border-radius: 8px; padding: 9px 15px; font-weight: 700; }}
        QPushButton#cmdTabButton:hover {{ background: {tab_hover}; color: {tab_text}; }}
        QPushButton#cmdTabButton:checked {{ background: {tab_selected}; color: {tab_text}; }}

        QWidget#themeFoundryPane, QWidget#themeFoundryEditor, QWidget#backdropBox {{ background: {panel}; border: 1px solid {border}; border-radius: 9px; }}
        QToolButton#collapsibleHeader {{ background: {tab_surface}; color: {primary}; border: 1px solid {border}; border-radius: 7px; padding: 6px 9px; font-weight: 700; text-align: left; }}
        QToolButton#collapsibleHeader:hover {{ background: {tab_hover}; }}
        QLabel#scopeBanner, QLabel#descriptionBox, QLabel#stateBanner {{ background: {subsection}; border: 1px solid {border}; border-radius: 8px; padding: 8px; color: {primary}; }}
        QLabel#stateBanner, QLabel#previewLabel, QLabel#sectionHeading {{ color: {popup_title}; font-weight: 700; }}
        QLabel#defaultsFoundryStatus {{ color: {success}; }}
        QPushButton#defaultsFoundryPrimary, QPushButton#themeFoundryPrimary {{ background: {action_surface}; color: {action_text}; border: 1.25px solid {action_border}; font-weight: 800; }}
        QPushButton#defaultsFoundryPrimary:hover, QPushButton#themeFoundryPrimary:hover {{ background: {action_hover}; }}
        QSlider::groove:horizontal {{ height: 5px; background: {input_surface}; border: 1px solid {border}; border-radius: 2px; }}
        QSlider::handle:horizontal {{ width: 14px; margin: -5px 0; border-radius: 7px; background: {action_surface}; }}
        QStatusBar {{ background: {titlebar}; color: {secondary}; }}

        QPushButton {{ background: {button_surface}; color: {button_text}; border: 1px solid {button_border}; border-radius: 8px; padding: 7px 13px; font-weight: 600; }}
        QPushButton:hover {{ background: {button_hover}; }}
        QPushButton:pressed {{ background: {button_pressed}; }}
        QPushButton:disabled {{ color: {helper}; border-color: {helper}; background: {subsection}; }}
        QPushButton#primaryButton {{ background: {action_surface}; color: {action_text}; border: 1.25px solid {action_border}; font-weight: 800; padding: 9px 16px; }}
        QPushButton#primaryButton:hover {{ background: {action_hover}; }}
        QPushButton#primaryButton:pressed {{ background: {action_pressed}; }}
        QPushButton#dangerButton {{ color: {error}; border-color: {error}; font-weight: 750; }}
        QPushButton#dangerButton:hover {{ background: {popup_surface}; }}
        QPushButton#iconButton {{ padding: 4px; min-width: 31px; min-height: 31px; font-size: 16px; }}
        QPushButton#expandButton {{ background: {tab_surface}; color: {primary}; border: 1px solid {border}; border-radius: 6px; padding: 4px 9px; min-height: 20px; }}
        QPushButton#expandButton:hover {{ background: {tab_hover}; }}

        QCheckBox {{ color: {checkbox_text}; spacing: 7px; }}
        QCheckBox::indicator {{ width: 15px; height: 15px; border-radius: 7px; background: {checkbox_surface}; border: 1px solid {checkbox_border}; }}
        QCheckBox::indicator:checked {{ background: {checkbox_checked}; border: 1px solid {checkbox_checked_border}; }}
        QCheckBox::indicator:disabled {{ background: {subsection}; border-color: {helper}; }}

        QLineEdit, QComboBox, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{ background: {input_surface}; color: {input_text}; border: 1px solid {input_border}; border-radius: 7px; padding: 7px 9px; selection-background-color: {list_selected}; selection-color: {list_text}; }}
        QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ background: {input_focus}; border-color: {input_border}; }}
        QComboBox::drop-down {{ border: none; width: 24px; }}
        QComboBox QAbstractItemView {{ background: {list_surface}; color: {list_text}; border: 1px solid {list_border}; selection-background-color: {list_selected}; }}

        QTreeWidget {{ background: {list_surface}; alternate-background-color: {subsection}; color: {list_text}; border: 1px solid {list_border}; outline: none; border-radius: 6px; }}
        QTreeWidget::item {{ padding: 4px 3px; }}
        QTreeWidget::item:selected {{ background: {list_selected}; color: {list_text}; }}
        QTreeWidget::item:hover {{ background: {list_hover}; }}
        QHeaderView::section {{ background: {titlebar}; color: {title_text}; border: none; border-right: 1px solid {list_border}; border-bottom: 1px solid {border}; padding: 6px; font-weight: 700; }}

        QToolTip {{ color: {tooltip_text}; background: {tooltip_surface}; border: 1px solid {tooltip_border}; padding: 5px; }}
        QScrollBar:vertical {{ background: {input_surface}; width: 11px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {list_border}; min-height: 28px; border-radius: 5px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{ background: {input_surface}; height: 11px; margin: 0; }}
        QScrollBar::handle:horizontal {{ background: {list_border}; min-width: 28px; border-radius: 5px; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

        QProgressBar {{ background: {input_surface}; border: 1px solid {border}; border-radius: 4px; text-align: center; }}
        QProgressBar::chunk {{ background: {action_surface}; }}
        QSplitter#applySplitter::handle {{ background: {list_border}; width: 3px; margin: 2px 3px; }}
        QSplitter#applySplitter::handle:hover {{ background: {border}; }}

        QLabel[relation="same"], QLabel[relation="compatible"] {{ color: {success}; background: {popup_surface}; border: 1px solid {success}; border-radius: 5px; padding: 6px; font-weight: 650; }}
        QLabel[relation="conflict"], QLabel[relation="diverged"] {{ color: {error}; background: {popup_surface}; border: 1px solid {error}; border-radius: 5px; padding: 6px; font-weight: 800; }}
        QLabel[relation="future"], QLabel[relation="unknown"], QLabel[relation="stale"] {{ color: {warning}; background: {popup_surface}; border: 1px solid {warning}; border-radius: 5px; padding: 6px; font-weight: 750; }}
        QLabel[relation="dirty"] {{ color: {warning}; background: {popup_surface}; border: 1px solid {warning}; border-radius: 5px; padding: 6px; font-weight: 700; }}

        QDialog#foundryPopup {{ background: {popup_surface}; color: {primary}; border: 1px solid {popup_border}; }}
        QFrame#foundryPopupPanel {{ background: {popup_surface}; border: 1px solid {popup_border}; border-radius: 10px; }}
        QLabel#popupTitle {{ color: {popup_title}; font-size: 12pt; font-weight: 750; }}
        QLabel#popupTitle[danger="true"] {{ color: {error}; }}
        QLabel#popupMessage {{ color: {popup_message}; }}
    """


__all__ = [
    "FOUNDRY_DEFAULT_THEME_ID",
    "FOUNDRY_THEME_DIRECTORY",
    "FoundryThemeResolution",
    "render_foundry_stylesheet",
    "resolve_foundry_theme",
    "theme_choices",
]
