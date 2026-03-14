# Transient per-screen shield windows shown during settings dialog startup.

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget


class _Shield(QWidget):
    """Single-screen overlay."""

    def __init__(self, geometry: QRect):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowTitle(" ")
        self.setObjectName("settingsShieldOverlay")
        self.setStyleSheet(
            "#settingsShieldOverlay { background-color: rgba(5, 5, 5, 200); }"
        )
        # Geometry is the screen's geometry in global coordinates.
        self.setGeometry(geometry)

    def closeEvent(self, event):  # type: ignore[override]
        event.accept()


class SettingsShieldManager:
    """Creates shield overlays on every available screen."""

    def __init__(self) -> None:
        self._shields: List[_Shield] = []
        for screen in QGuiApplication.screens():
            geometry = screen.geometry()
            shield = _Shield(geometry)
            self._shields.append(shield)

    def show(self) -> None:
        for shield in self._shields:
            shield.show()

    def hide(self) -> None:
        for shield in self._shields:
            shield.hide()
            shield.deleteLater()
        self._shields.clear()
