"""System tray integration for ShittyRandomPhotoScreenSaver.

Provides a small, themed tray icon with a context menu for
opening Settings and exiting the screensaver when hard-exit
mode is enabled. Tooltip shows CPU/GPU usage on hover.
"""
from __future__ import annotations

import os
from typing import Optional
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core.logging.logger import get_logger
from core.resources.manager import ResourceManager
from core.resources.types import ResourceType


logger = get_logger(__name__)

# Lazy imports for performance monitoring (only loaded when needed)
_psutil = None
_pynvml_initialized = False
_nvml_handle = None


def _get_psutil():
    """Lazy load psutil to avoid startup penalty."""
    global _psutil
    if _psutil is None:
        try:
            import psutil
            _psutil = psutil
        except ImportError:
            _psutil = False
    return _psutil if _psutil else None


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
        except Exception:
            _nvml_handle = None
    
    if _nvml_handle is None:
        return None
    
    try:
        import pynvml
        util = pynvml.nvmlDeviceGetUtilizationRates(_nvml_handle)
        return float(util.gpu)
    except Exception:
        return None


def _get_cpu_usage() -> Optional[float]:
    """Get CPU usage percentage for this process.
    
    Returns None if psutil is unavailable.
    """
    psutil = _get_psutil()
    if psutil is None:
        return None
    
    try:
        proc = psutil.Process(os.getpid())
        return proc.cpu_percent(interval=None)
    except Exception:
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

        # Initialize CPU baseline for accurate readings
        _get_cpu_usage()  # Prime psutil's cpu_percent
        
        self._update_tooltip()

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

    def _update_tooltip(self) -> None:
        """Update tooltip with current CPU/GPU usage.
        
        Called on init and can be called periodically if needed.
        Uses lazy-loaded monitoring to avoid startup penalty.
        """
        try:
            cpu = _get_cpu_usage()
            gpu = _get_gpu_usage()
            
            parts = ["SRPSS"]
            if cpu is not None:
                parts.append(f"CPU: {cpu:.0f}%")
            if gpu is not None:
                parts.append(f"GPU: {gpu:.0f}%")
            
            tooltip = " | ".join(parts) if len(parts) > 1 else parts[0]
            self.setToolTip(tooltip)
        except Exception:
            self.setToolTip("SRPSS")

    def refresh_tooltip(self) -> None:
        """Public method to refresh the tooltip with current usage stats.
        
        Can be called from a timer or event handler to keep tooltip current.
        """
        self._update_tooltip()
