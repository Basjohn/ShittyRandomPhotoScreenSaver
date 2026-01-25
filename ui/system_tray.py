"""System tray integration for ShittyRandomPhotoScreenSaver.

Provides a small, themed tray icon with a context menu for
opening Settings and exiting the screensaver when hard-exit
mode is enabled. Tooltip shows GPU usage (if available) on hover.
"""
from __future__ import annotations

from typing import Optional
from pathlib import Path

from PySide6.QtCore import Signal, QTimer
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core.logging.logger import get_logger
from core.resources.manager import ResourceManager
from core.resources.types import ResourceType


logger = get_logger(__name__)

# Lazy imports for performance monitoring (only loaded when needed)
_pynvml_initialized = False
_nvml_handle = None


def _get_gpu_usage() -> Optional[float]:
    """Get GPU usage percentage using pynvml (NVIDIA) or fallback.
    
    Returns None if GPU monitoring is unavailable.
    Uses lazy initialization to avoid startup penalty.
    """
    global _pynvml_initialized, _nvml_handle
    
    if not _pynvml_initialized:
        _pynvml_initialized = True
        try:
            import pynvml
            pynvml.nvmlInit()
            _nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception as e:
            logger.debug("[SYSTEM_TRAY] Exception suppressed: %s", e)
            _nvml_handle = None
    
    if _nvml_handle is None:
        return None
    
    try:
        import pynvml
        util = pynvml.nvmlDeviceGetUtilizationRates(_nvml_handle)
        return float(util.gpu)
    except Exception as e:
        logger.debug("[SYSTEM_TRAY] Exception suppressed: %s", e)
        return None


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
    
    Tooltip displays CPU/GPU usage when hovered (updated lazily).
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

        # Initial tooltip update
        QTimer.singleShot(1000, self._update_tooltip)
        
        # Periodic tooltip refresh timer (every 5 seconds)
        self._tooltip_timer = QTimer(self)
        self._tooltip_timer.timeout.connect(self._update_tooltip)
        self._tooltip_timer.start(5000)  # 5 second refresh

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
        
        # Connect double-click to disable eco mode and enable on-top
        self.activated.connect(self._on_tray_activated)
        
        # Store reference to eco mode callback for double-click handling
        self._eco_mode_callback = None
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

    def _on_tray_activated(self, reason):
        """Handle tray icon activation (clicks).
        
        Double-click disables eco mode and enables always-on-top to bring
        the screensaver back to the foreground smoothly without flashing.
        
        Args:
            reason: QSystemTrayIcon.ActivationReason
        """
        logger.info("[SYSTEM_TRAY] Tray activated: reason=%s", reason)
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            logger.info("[SYSTEM_TRAY] Double-click detected on systray icon")
            # Disable eco mode and enable always-on-top via proper methods
            # This avoids the flashing caused by raw raise_() calls
            if not self._display_widgets:
                logger.warning("[SYSTEM_TRAY] No display widgets registered for double-click handling")
            
            try:
                for widget in self._display_widgets:
                    if hasattr(widget, '_on_context_always_on_top_toggled'):
                        # Enable always-on-top which will:
                        # 1. Disable eco mode
                        # 2. Set window flags properly
                        # 3. Avoid flashing by using proper Qt flag updates
                        widget._on_context_always_on_top_toggled(True)
                        logger.info("[SYSTEM_TRAY] Double-click: enabled always-on-top for display widget")
                    else:
                        logger.warning("[SYSTEM_TRAY] Display widget missing _on_context_always_on_top_toggled method")
            except Exception as e:
                logger.warning("[SYSTEM_TRAY] Failed to enable always-on-top on double-click: %s", e)
                # Fallback to simple raise if proper method fails
                app = QApplication.instance()
                if app:
                    for widget in app.topLevelWidgets():
                        if widget.isVisible() and hasattr(widget, 'raise_'):
                            widget.raise_()
                            widget.activateWindow()
                            logger.info("[SYSTEM_TRAY] Fallback: raised widget to foreground")
    
    def set_eco_mode_callback(self, callback) -> None:
        """Set callback to check Eco Mode status.
        
        Args:
            callback: Function that returns True if Eco Mode is active
        """
        self._eco_mode_callback = callback
    
    def set_display_widgets(self, widgets: list) -> None:
        """Set display widgets for on-top control.
        
        Args:
            widgets: List of DisplayWidget instances
        """
        self._display_widgets = widgets
    
    def _update_tooltip(self) -> None:
        """Update tooltip with current CPU/GPU usage and Eco Mode status.
        
        Called on init and can be called periodically if needed.
        Uses lazy-loaded monitoring to avoid startup penalty.
        """
        try:
            gpu = _get_gpu_usage()
            
            parts = ["SRPSS"]
            if gpu is not None:
                parts.append(f"GPU: {gpu:.0f}%")
            
            # Add Eco Mode indicator if active
            eco_callback = getattr(self, '_eco_mode_callback', None)
            if eco_callback is not None:
                try:
                    if eco_callback():
                        parts.append("ECO MODE ON")
                except Exception as e:
                    logger.debug("[SYSTEM_TRAY] Exception suppressed: %s", e)
            
            tooltip = " | ".join(parts) if len(parts) > 1 else parts[0]
            self.setToolTip(tooltip)
        except Exception as e:
            logger.debug("[SYSTEM_TRAY] Exception suppressed: %s", e)
            self.setToolTip("SRPSS")

    def refresh_tooltip(self) -> None:
        """Public method to refresh the tooltip with current usage stats.
        
        Can be called from a timer or event handler to keep tooltip current.
        """
        self._update_tooltip()
