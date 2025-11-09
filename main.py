"""
ShittyRandomPhotoScreenSaver - Main Entry Point

Windows screensaver application that displays photos with transitions.
"""
import sys
import os
import logging
import shutil
from pathlib import Path
from enum import Enum
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QSurfaceFormat, QImageReader
from core.logging.logger import setup_logging, get_logger
from core.settings.settings_manager import SettingsManager
from core.animation import AnimationManager
from engine.screensaver_engine import ScreensaverEngine
from ui.settings_dialog import SettingsDialog

logger = get_logger(__name__)


class ScreensaverMode(Enum):
    """Screensaver execution modes based on Windows arguments."""
    RUN = "run"          # /s - Run screensaver
    CONFIG = "config"    # /c - Configuration dialog
    PREVIEW = "preview"  # /p <hwnd> - Preview in settings window


def parse_screensaver_args() -> tuple[ScreensaverMode, int | None]:
    """
    Parse Windows screensaver command-line arguments.
    
    Windows screensaver arguments:
    - /s - Run the screensaver
    - /c - Show configuration dialog
    - /p <hwnd> - Preview mode (show in window with handle <hwnd>)
    
    Debug flags (ignored here, handled earlier):
    - --debug, -d - Enable debug logging
    
    Returns:
        tuple: (ScreensaverMode, preview_window_handle)
    """
    # Filter out debug flags
    args = [arg for arg in sys.argv if arg not in ('--debug', '-d')]
    
    logger.debug(f"Command-line arguments: {sys.argv}")
    logger.debug(f"Filtered arguments: {args}")
    
    # Default to run mode if no arguments (besides program name)
    if len(args) == 1:
        logger.info("No arguments provided, defaulting to RUN mode")
        return ScreensaverMode.RUN, None
    
    # Get the first argument (after program name)
    arg = args[1].lower()
    
    # Run screensaver (Windows /s only). For convenience, -s/--s open settings.
    if arg == '/s':
        logger.info("RUN mode selected")
        return ScreensaverMode.RUN, None
    
    # Configuration dialog
    elif arg in ('/c', '-c', '-s', '--s'):
        logger.info("CONFIG mode selected")
        return ScreensaverMode.CONFIG, None
    
    # Preview mode
    elif arg == '/p' or arg == '-p':
        if len(args) > 2:
            try:
                hwnd = int(args[2])
                logger.info(f"PREVIEW mode selected with window handle: {hwnd}")
                return ScreensaverMode.PREVIEW, hwnd
            except ValueError:
                logger.error(f"Invalid window handle: {args[2]}")
                return ScreensaverMode.PREVIEW, None
        else:
            logger.warning("PREVIEW mode selected but no window handle provided")
            return ScreensaverMode.PREVIEW, None
    
    # Unknown argument - default to run
    else:
        logger.warning(f"Unknown argument: {arg}, defaulting to RUN mode")
        return ScreensaverMode.RUN, None


def is_script_mode() -> bool:
    """
    Check if running as a script (not compiled executable).
    
    Returns:
        True if running as .py script, False if compiled .exe/.scr
    """
    # Check if running from a .py file or if __file__ exists
    return hasattr(sys, 'ps1') or (
        hasattr(sys.modules['__main__'], '__file__') and
        sys.modules['__main__'].__file__.endswith('.py')
    )


def cleanup_pycache(root_path: Path) -> int:
    """
    Recursively delete all __pycache__ directories.
    
    Args:
        root_path: Root directory to start cleanup from
    
    Returns:
        Number of directories removed
    """
    removed_count = 0
    
    try:
        for dirpath, dirnames, _ in os.walk(root_path):
            # Look for __pycache__ directories
            if '__pycache__' in dirnames:
                pycache_path = Path(dirpath) / '__pycache__'
                try:
                    shutil.rmtree(pycache_path)
                    removed_count += 1
                    logger.debug(f"Removed pycache: {pycache_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove pycache {pycache_path}: {e}")
    except Exception as e:
        logger.warning(f"Error during pycache cleanup: {e}")
    
    return removed_count


def run_screensaver(app: QApplication) -> int:
    """
    Run the screensaver.
    
    Args:
        app: Qt application instance
    
    Returns:
        Exit code
    """
    logger.info("Initializing screensaver engine")
    
    # Create settings manager
    settings = SettingsManager()
    
    # Check if sources are configured (using dot notation)
    folders = settings.get('sources.folders', [])
    rss_feeds = settings.get('sources.rss_feeds', [])
    
    if not folders and not rss_feeds:
        logger.warning("No image sources configured - opening settings dialog")
        QMessageBox.information(
            None,
            "No Sources Configured",
            "No image sources have been configured.\n\n"
            "Please add folders or RSS feeds in the settings dialog."
        )
        return run_config(app)
    
    # Create and start screensaver engine
    try:
        engine = ScreensaverEngine()
        if not engine.initialize():
            logger.error("Failed to initialize screensaver engine")
            logger.warning("Opening settings dialog to configure sources")
            QMessageBox.warning(
                None,
                "Configuration Required",
                "Failed to initialize screensaver.\n\n"
                "Please configure image sources in the settings dialog."
            )
            return run_config(app)
        
        if not engine.start():
            logger.error("Failed to start screensaver engine")
            logger.warning("Opening settings dialog")
            QMessageBox.warning(
                None,
                "Startup Failed",
                "Failed to start screensaver.\n\n"
                "Please check your configuration."
            )
            return run_config(app)
        
        logger.info("Screensaver engine started - entering event loop")
        return app.exec()
        
    except Exception as e:
        logger.exception(f"Failed to start screensaver engine: {e}")
        QMessageBox.critical(
            None,
            "Screensaver Error",
            f"Failed to start screensaver:\n{e}"
        )
        return 1


def run_config(app: QApplication) -> int:
    """
    Run configuration dialog.
    
    Args:
        app: Qt application instance
    
    Returns:
        Exit code
    """
    logger.info("Opening configuration dialog")
    
    # Create settings manager
    settings = SettingsManager()
    
    # Create animation manager
    animations = AnimationManager()
    
    # Create and show settings dialog
    try:
        dialog = SettingsDialog(settings, animations)
        dialog.show()
        
        logger.info("Configuration dialog opened - entering event loop")
        return app.exec()
        
    except Exception as e:
        logger.exception(f"Failed to open configuration dialog: {e}")
        QMessageBox.critical(
            None,
            "Configuration Error",
            f"Failed to open settings:\n{e}"
        )
        return 1


def main():
    """Main entry point for the screensaver application."""
    # Setup logging first
    debug_mode = '--debug' in sys.argv or '-d' in sys.argv
    setup_logging(debug=debug_mode)
    
    logger.info("=" * 60)
    logger.info("ShittyRandomPhotoScreenSaver Starting")
    logger.info("=" * 60)
    
    # Cleanup pycache on startup (script mode only)
    if is_script_mode():
        logger.info("Running in script mode - cleaning pycache on startup")
        project_root = Path(__file__).parent
        removed = cleanup_pycache(project_root)
        if removed > 0:
            logger.info(f"Removed {removed} __pycache__ directories")
        else:
            logger.debug("No __pycache__ directories found")
    
    # Parse command-line arguments
    mode, preview_hwnd = parse_screensaver_args()
    
    # Enable High DPI scaling BEFORE creating QApplication
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Configure OpenGL globally BEFORE creating QApplication
    try:
        # Prefer desktop OpenGL and share contexts across widgets
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL, True)
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

        fmt = QSurfaceFormat()
        fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
        fmt.setSwapInterval(1)  # vsync
        fmt.setDepthBufferSize(24)
        fmt.setStencilBufferSize(8)
        QSurfaceFormat.setDefaultFormat(fmt)
        logger.debug("Global QSurfaceFormat configured (double buffer, vsync, depth=24, stencil=8)")
    except Exception as e:
        logger.warning(f"Failed to configure global OpenGL format: {e}")
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("ShittyRandomPhotoScreenSaver")
    app.setOrganizationName("ShittyRandomPhotoScreenSaver")
    
    # Increase Qt image allocation limit from 256MB to 1GB for high-res images
    # This is per-image when loaded, not total memory for all images
    # Images are loaded on-demand, not all at startup (ImageQueue stores metadata only)
    QImageReader.setAllocationLimit(1024)  # 1GB in MB
    logger.info("Qt image allocation limit: 1GB (supports 8K+ images, per-image on-demand)")
    
    logger.info(f"Qt Application created: {app.applicationName()}")
    logger.debug(f"High DPI scaling enabled")
    
    # Route to appropriate mode
    exit_code = 0
    
    try:
        if mode == ScreensaverMode.RUN:
            logger.info("Starting screensaver in RUN mode")
            exit_code = run_screensaver(app)
            
        elif mode == ScreensaverMode.CONFIG:
            logger.info("Starting configuration dialog")
            exit_code = run_config(app)
            
        elif mode == ScreensaverMode.PREVIEW:
            logger.info(f"Starting preview mode (hwnd={preview_hwnd})")
            # TODO: Show preview in parent window
            logger.warning("PREVIEW mode not yet implemented")
            logger.info("Exiting (preview not yet implemented)")
        
    except Exception as e:
        logger.exception(f"Fatal error in main: {e}")
        exit_code = 1
    
    # Cleanup pycache on exit (script mode only)
    if is_script_mode():
        logger.info("Cleaning pycache on exit")
        project_root = Path(__file__).parent
        removed = cleanup_pycache(project_root)
        if removed > 0:
            logger.info(f"Removed {removed} __pycache__ directories")
    
    logger.info("=" * 60)
    logger.info(f"ShittyRandomPhotoScreenSaver Exiting (code={exit_code})")
    logger.info("=" * 60)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
