"""System tray integration for ShittyRandomPhotoScreenSaver.

Provides a small, themed tray icon with a context menu for
opening Settings and exiting the screensaver when Interaction Mode
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
    
    The tooltip is intentionally static; diagnostics belong to opt-in sidecars.
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
        
        # Connect double-click to bring screensaver to foreground
        self.activated.connect(self._on_tray_activated)
        
        self._display_widgets = []  # Store display widgets for on-top control

        # Only show the icon if the system tray is available; if not,
        # log and leave the instance inert.
        if QSystemTrayIcon.isSystemTrayAvailable():
            try:
                self.show()
            except Exception:
                logger.debug("Failed to show system tray icon", exc_info=True)
        else:
            logger.info("System tray not available; skipping tray icon")

        # Register with the centralized ResourceManager so the icon is cleaned
        # up on shutdown with other Qt resources.
        try:
            manager = ResourceManager.get_or_create_app_shared()
            manager.register_qt(
                self,
                resource_type=ResourceType.GUI_COMPONENT,
                description="Screensaver system tray icon",
                group="qt",
            )
        except Exception:
            # Never let tray registration failure affect startup.
            logger.debug("Failed to register tray icon with ResourceManager", exc_info=True)

    def _on_tray_activated(self, reason):
        """Handle tray icon activation (clicks).
        
        Double-click enables always-on-top to bring the screensaver
        back to the foreground smoothly without flashing.
        
        Args:
            reason: QSystemTrayIcon.ActivationReason
        """
        logger.info("[SYSTEM_TRAY] Tray activated: reason=%s", reason)
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            logger.info("[SYSTEM_TRAY] Double-click detected on systray icon")
            if not self._display_widgets:
                logger.warning("[SYSTEM_TRAY] No display widgets registered for double-click handling")
            
            try:
                for widget in self._display_widgets:
                    if hasattr(widget, '_on_context_always_on_top_toggled'):
                        widget._on_context_always_on_top_toggled(True)
                        logger.info("[SYSTEM_TRAY] Double-click: enabled always-on-top for display widget")
                    else:
                        logger.warning("[SYSTEM_TRAY] Display widget missing _on_context_always_on_top_toggled method")
            except Exception as e:
                logger.warning("[SYSTEM_TRAY] Failed to enable always-on-top on double-click: %s", e)
                app = QApplication.instance()
                if app:
                    for widget in app.topLevelWidgets():
                        if widget.isVisible() and hasattr(widget, 'raise_'):
                            widget.raise_()
                            widget.activateWindow()
                            logger.info("[SYSTEM_TRAY] Fallback: raised widget to foreground")
    
    def set_display_widgets(self, widgets: list) -> None:
        """Set display widgets for on-top control.
        
        Args:
            widgets: List of DisplayWidget instances
        """
        self._display_widgets = widgets
