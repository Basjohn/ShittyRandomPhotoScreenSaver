"""System tray integration for ShittyRandomPhotoScreenSaver.

Provides a small, themed tray icon with a context menu for
opening Settings and exiting the screensaver when hard-exit
mode is enabled.
"""
from __future__ import annotations

from typing import Optional
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core.logging.logger import get_logger
from core.resources.manager import ResourceManager
from core.resources.types import ResourceType


logger = get_logger(__name__)


def _load_tray_menu_stylesheet() -> str | None:
    """Load the dark theme stylesheet for use with the tray menu only.

    This reuses the existing themes/dark.qss file so the tray context
    menu matches other context menus defined in the theme without
    duplicating styles in code.
    """
    try:
        theme_path = Path(__file__).parent.parent / "themes" / "dark.qss"
        if not theme_path.exists():
            return None
        return theme_path.read_text(encoding="utf-8")
    except Exception:
        logger.debug("Failed to load dark.qss for tray menu", exc_info=True)
        return None


class ScreensaverTrayIcon(QSystemTrayIcon):
    """Minimal system tray icon for the screensaver.

    Exposes two high-level signals so the main entry point
    can wire Settings / Exit behaviour without this class
    needing additional dependencies.
    """

    settings_requested = Signal()
    exit_requested = Signal()

    def __init__(self, app: QApplication, icon: Optional[QIcon] = None) -> None:
        # QSystemTrayIcon requires a QApplication to exist first; the
        # caller (main.py) guarantees this.
        super().__init__(parent=app)

        # Use provided icon if non-null; otherwise fall back to the
        # application icon so taskbar/systray stay consistent.
        tray_icon = icon or app.windowIcon()
        if not tray_icon.isNull():
            self.setIcon(tray_icon)

        self.setToolTip("SRPSS")

        # Build a small context menu and apply the dark theme so it
        # matches other context menus styled in dark.qss.
        menu = QMenu()

        try:
            stylesheet = _load_tray_menu_stylesheet()
            if stylesheet:
                menu.setStyleSheet(stylesheet)
        except Exception:
            logger.debug("Failed to apply dark.qss to tray menu", exc_info=True)

        settings_action = QAction("Settings", menu)
        exit_action = QAction("Exit", menu)

        settings_action.triggered.connect(self.settings_requested)
        exit_action.triggered.connect(self.exit_requested)

        menu.addAction(settings_action)
        menu.addSeparator()
        menu.addAction(exit_action)

        self.setContextMenu(menu)

        # Only show the icon if the system tray is available; if not,
        # log and leave the instance inert.
        if QSystemTrayIcon.isSystemTrayAvailable():
            try:
                self.show()
            except Exception:
                logger.debug("Failed to show system tray icon", exc_info=True)
        else:
            logger.info("System tray not available; skipping tray icon")

        # Register with the centralized ResourceManager so the icon
        # is cleaned up on shutdown with other Qt resources.
        try:
            manager = ResourceManager()
            manager.register_qt(
                self,
                resource_type=ResourceType.GUI_COMPONENT,
                description="Screensaver system tray icon",
                group="qt",
            )
        except Exception:
            # Never let tray registration failure affect startup.
            logger.debug("Failed to register tray icon with ResourceManager", exc_info=True)
