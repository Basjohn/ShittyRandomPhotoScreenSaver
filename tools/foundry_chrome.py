"""Shared frameless chrome + appearance picker for SRPSS Qt Foundries.

Standalone Foundries deliberately keep their appearance preference tool-local.
They consume the frozen ``tools/godzip_themes`` ThemeSpec snapshot rather than
mutating product Settings state or depending on the live theme catalogue.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tools.godzip_foundry_theme import (
    FOUNDRY_DEFAULT_THEME_ID,
    FoundryThemeResolution,
    resolve_foundry_theme,
    theme_choices,
)


def tool_data_dir(tool_key: str) -> Path:
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / "SRPSS" / "Foundries" / str(tool_key)


def tool_appearance_path(tool_key: str) -> Path:
    return tool_data_dir(tool_key) / "appearance.json"


def load_tool_theme_id(tool_key: str) -> str:
    try:
        payload = json.loads(tool_appearance_path(tool_key).read_text(encoding="utf-8"))
        value = payload.get("theme_id") if isinstance(payload, dict) else None
        if isinstance(value, str) and value.strip():
            return value.strip()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return FOUNDRY_DEFAULT_THEME_ID


def save_tool_theme_id(tool_key: str, theme_id: str) -> None:
    path = tool_appearance_path(tool_key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(
            json.dumps({"theme_id": str(theme_id)}, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except OSError:
        pass


def configure_frameless_window(window: QWidget) -> None:
    """Give a Qt Foundry Settings-style custom chrome."""

    window.setWindowFlags(
        Qt.WindowType.Window
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowSystemMenuHint
        | Qt.WindowType.WindowMinMaxButtonsHint
    )
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    # Keep the rounded central-widget border off the native window edge.  On
    # fractional DPI a border painted flush to a translucent HWND is clipped at
    # the corner arc before Qt can antialias it.
    window.setContentsMargins(2, 2, 2, 2)


class FoundryTitleBar(QFrame):
    """Settings-like title bar for standalone Qt Foundries."""

    def __init__(
        self,
        title: str,
        parent: QWidget,
        *,
        settings_callback: Callable[[], None] | None = None,
        compact: bool = False,
        allow_maximize: bool = True,
    ) -> None:
        super().__init__(parent)
        self._drag_offset = QPoint()
        self._allow_maximize = bool(allow_maximize and not compact)
        self.setObjectName("toolTitleBar")
        self.setFixedHeight(48 if not compact else 44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(7)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("toolTitleLabel")
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.title_label)
        layout.addStretch(1)

        if not compact and settings_callback is not None:
            settings = QPushButton("⚙")
            settings.setObjectName("toolTitleSettingsButton")
            settings.setFixedSize(38, 30)
            settings.setToolTip("Foundry appearance")
            settings.clicked.connect(settings_callback)
            layout.addWidget(settings)

        self.minimize_button: QPushButton | None = None
        self.maximize_button: QPushButton | None = None
        if not compact:
            self.minimize_button = QPushButton("−")
            self.minimize_button.setObjectName("toolTitleButton")
            self.minimize_button.setFixedSize(40, 30)
            self.minimize_button.clicked.connect(parent.showMinimized)
            layout.addWidget(self.minimize_button)

            self.maximize_button = QPushButton("□")
            self.maximize_button.setObjectName("toolTitleButton")
            self.maximize_button.setFixedSize(40, 30)
            self.maximize_button.clicked.connect(self.toggle_maximized)
            layout.addWidget(self.maximize_button)

        self.close_button = QPushButton("×")
        self.close_button.setObjectName("toolTitleCloseButton")
        self.close_button.setFixedSize(40, 30)
        self.close_button.clicked.connect(parent.close)
        layout.addWidget(self.close_button)

    def toggle_maximized(self) -> None:
        if not self._allow_maximize:
            return
        window = self.window()
        if window.isMaximized():
            window.showNormal()
            if self.maximize_button is not None:
                self.maximize_button.setText("□")
        else:
            window.showMaximized()
            if self.maximize_button is not None:
                self.maximize_button.setText("❐")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                try:
                    if handle.startSystemMove():
                        event.accept()
                        return
                except (AttributeError, RuntimeError):
                    pass
            self._drag_offset = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.buttons() & Qt.MouseButton.LeftButton and not self._drag_offset.isNull():
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if self._allow_maximize and event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class FoundryAppearanceDialog(QDialog):
    """Small tool-local ThemeSpec selector shared by Qt Foundries."""

    def __init__(
        self,
        owner: QWidget,
        *,
        title: str,
        resolution: FoundryThemeResolution,
        apply_theme: Callable[[str], None],
    ) -> None:
        super().__init__(owner)
        self._apply_theme = apply_theme
        self.setWindowTitle(f"{title} Appearance")
        self.setObjectName("foundryPopup")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(560, 210)
        self.setStyleSheet(owner.styleSheet())

        outer = QVBoxLayout(self)
        # Leave two physical pixels around the rounded shell.  Qt stylesheets do
        # not clip child painting to a parent's border-radius, so flush children
        # are the source of the chopped-corner artefacts the Foundries used to show.
        outer.setContentsMargins(2, 2, 2, 2)
        outer.setSpacing(0)
        shell = QFrame(self)
        shell.setObjectName("foundryPopupShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(2, 2, 2, 2)
        shell_layout.setSpacing(8)

        title_bar = FoundryTitleBar(
            "FOUNDRY APPEARANCE",
            self,
            compact=True,
            allow_maximize=False,
        )
        shell_layout.addWidget(title_bar)

        panel = QFrame(shell)
        panel.setObjectName("foundryPopupPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(10)

        note = QLabel(
            "Tool-local theme only. It uses the frozen Foundry theme catalogue and never changes SRPSS Settings."
        )
        note.setObjectName("popupMessage")
        note.setWordWrap(True)
        layout.addWidget(note)

        row = QHBoxLayout()
        row.addWidget(QLabel("Theme"))
        self.combo = QComboBox()
        selected = -1
        for index, (theme_id, name) in enumerate(theme_choices(resolution.catalog)):
            self.combo.addItem(name, theme_id)
            if theme_id == resolution.theme_id:
                selected = index
        if selected >= 0:
            self.combo.setCurrentIndex(selected)
        row.addWidget(self.combo, 1)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = QPushButton("CLOSE")
        close.clicked.connect(self.close)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        shell_layout.addWidget(panel)
        outer.addWidget(shell)

        self.combo.currentIndexChanged.connect(self._selection_changed)

    def _selection_changed(self, _index: int) -> None:
        theme_id = self.combo.currentData()
        if isinstance(theme_id, str) and theme_id:
            self._apply_theme(theme_id)


def choose_foundry_qcolor(
    owner: QWidget,
    initial: QColor,
    title: str,
    *,
    show_alpha: bool = True,
) -> QColor | None:
    """Show QColorDialog inside Foundry chrome instead of an unthemed native popup.

    The picker is embedded as a widget in our own rounded shell.  Besides keeping
    Widget/Theme Foundry popups on-theme, this avoids native child windows painting
    across translucent rounded corners.
    """

    dialog = QDialog(owner)
    dialog.setWindowTitle(title)
    dialog.setObjectName("foundryPopup")
    dialog.setWindowFlags(
        Qt.WindowType.Tool
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
    )
    dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    dialog.resize(720, 560)
    dialog.setStyleSheet(owner.styleSheet())

    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(2, 2, 2, 2)
    outer.setSpacing(0)
    shell = QFrame(dialog)
    shell.setObjectName("foundryPopupShell")
    shell_layout = QVBoxLayout(shell)
    shell_layout.setContentsMargins(2, 2, 2, 2)
    shell_layout.setSpacing(8)

    title_bar = FoundryTitleBar(
        title.upper(),
        dialog,
        compact=True,
        allow_maximize=False,
    )
    shell_layout.addWidget(title_bar)

    panel = QFrame(shell)
    panel.setObjectName("foundryPopupPanel")
    panel_layout = QVBoxLayout(panel)
    panel_layout.setContentsMargins(12, 10, 12, 12)
    panel_layout.setSpacing(10)

    picker = QColorDialog(initial, dialog)
    picker.setObjectName("foundryColorPicker")
    picker.setWindowFlags(Qt.WindowType.Widget)
    picker.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
    picker.setOption(QColorDialog.ColorDialogOption.NoButtons, True)
    picker.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, bool(show_alpha))
    panel_layout.addWidget(picker, 1)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    panel_layout.addWidget(buttons)
    shell_layout.addWidget(panel, 1)
    outer.addWidget(shell, 1)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    chosen = picker.currentColor()
    return chosen if chosen.isValid() else None


def apply_native_backdrop(window: QWidget, resolution: FoundryThemeResolution) -> bool:
    """Apply the same Windows AccentPolicy semantics used by Settings."""

    if os.name != "nt":
        return False
    try:
        backdrop = resolution.theme.backdrop
        hwnd = int(window.winId())
        if backdrop.mode == "acrylic":
            from core.windows.dwm_blur import enable_acrylic_blur

            return bool(
                enable_acrylic_blur(
                    hwnd,
                    tint_r=backdrop.tint.r,
                    tint_g=backdrop.tint.g,
                    tint_b=backdrop.tint.b,
                    tint_alpha=backdrop.tint.a,
                )
            )
        if backdrop.mode == "glass":
            from core.windows.dwm_blur import enable_glass_blur

            return bool(enable_glass_blur(hwnd))
        from core.windows.dwm_blur import disable_blur

        disable_blur(hwnd)
        return False
    except Exception:
        return False


def resolve_tool_theme(tool_key: str) -> FoundryThemeResolution:
    return resolve_foundry_theme(load_tool_theme_id(tool_key))


__all__ = [
    "FoundryAppearanceDialog",
    "FoundryTitleBar",
    "apply_native_backdrop",
    "choose_foundry_qcolor",
    "configure_frameless_window",
    "load_tool_theme_id",
    "resolve_tool_theme",
    "save_tool_theme_id",
    "tool_data_dir",
]
