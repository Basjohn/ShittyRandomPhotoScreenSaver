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
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
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


class FoundryTitleBar(QFrame):
    """Settings-like title bar for standalone Qt Foundries."""

    def __init__(
        self,
        title: str,
        parent: QWidget,
        *,
        settings_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._drag_offset = QPoint()
        self.setObjectName("toolTitleBar")
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(7)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("toolTitleLabel")
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.title_label)
        layout.addStretch(1)

        if settings_callback is not None:
            settings = QPushButton("⚙")
            settings.setObjectName("toolTitleSettingsButton")
            settings.setFixedSize(38, 30)
            settings.setToolTip("Foundry appearance")
            settings.clicked.connect(settings_callback)
            layout.addWidget(settings)

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
        window = self.window()
        if window.isMaximized():
            window.showNormal()
            self.maximize_button.setText("□")
        else:
            window.showMaximized()
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
        if event.button() == Qt.MouseButton.LeftButton:
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
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.resize(520, 170)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        panel.setObjectName("foundryPopupPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        heading = QLabel("FOUNDRY APPEARANCE")
        heading.setObjectName("popupTitle")
        layout.addWidget(heading)
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
        outer.addWidget(panel)

        self.combo.currentIndexChanged.connect(self._selection_changed)

    def _selection_changed(self, _index: int) -> None:
        theme_id = self.combo.currentData()
        if isinstance(theme_id, str) and theme_id:
            self._apply_theme(theme_id)


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
    "configure_frameless_window",
    "load_tool_theme_id",
    "resolve_tool_theme",
    "save_tool_theme_id",
    "tool_data_dir",
]
