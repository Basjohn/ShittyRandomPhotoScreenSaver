"""
ShittyRandomPhotoScreenSaver - Main Entry Point

Windows screensaver application that displays photos with transitions.
"""
import sys
import os
import shutil
from pathlib import Path
from enum import Enum
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QSurfaceFormat, QImageReader, QIcon
from core.logging.logger import setup_logging, get_logger
from core.settings.settings_manager import SettingsManager
from core.animation import AnimationManager
from engine.screensaver_engine import ScreensaverEngine
from ui.settings_dialog import SettingsDialog
from rendering.gl_format import build_surface_format
from ui.system_tray import ScreensaverTrayIcon
from versioning import APP_VERSION, APP_EXE_NAME

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

    # Detect whether we are running as a frozen executable (.exe/.scr)
    # or as a plain Python script.
    is_frozen = bool(getattr(sys, 'frozen', False))

    # Default mode depends on environment:
    #  - Script runs (python main.py) default to RUN for convenience.
    #  - Frozen builds (SRPSS.exe/SRPSS.scr) default to CONFIG to avoid
    #    surprising full-screen runs when selected in the Windows dialog
    #    or double-clicked.
    if len(args) == 1:
        if is_frozen:
            logger.info("No arguments provided in frozen build, defaulting to CONFIG mode")
            return ScreensaverMode.CONFIG, None
        logger.info("No arguments provided in script mode, defaulting to RUN mode")
        return ScreensaverMode.RUN, None
    
    # Get the first argument (after program name)
    raw_arg = args[1]
    arg = raw_arg.lower().strip()

    # Run screensaver (Windows /s only). For convenience, -s/--s open settings.
    if arg == '/s':
        logger.info("RUN mode selected")
        return ScreensaverMode.RUN, None
    
    # Configuration dialog. Windows may pass "/c" or "/c:####" (with a
    # parent window handle); treat any "/c*" pattern as CONFIG mode so the
    # Screen Saver Settings "Settings" button never accidentally runs the
    # saver full-screen.
    elif arg.startswith('/c') or arg in ('-c', '-s', '--s'):
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
    
    # Unknown argument – default mode depends on environment so we never
    # "surprise run" a frozen build while keeping script usage simple.
    else:
        if is_frozen:
            logger.warning(f"Unknown argument: {arg}, defaulting to CONFIG mode (frozen)")
            return ScreensaverMode.CONFIG, None
        logger.warning(f"Unknown argument: {arg}, defaulting to RUN mode (script)")
        return ScreensaverMode.RUN, None


def is_script_mode() -> bool:
    """
    Check if running as a script (not compiled executable).
    
    Returns:
        True if running as .py script, False if compiled .exe/.scr
    """
    # PyInstaller and similar bundlers set sys.frozen on the runtime
    # executable; treat any such environment as non-script.
    if bool(getattr(sys, 'frozen', False)):
        return False

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

    # Determine whether hard-exit mode is enabled so we can optionally
    # expose a small system tray for Settings/Exit while the saver runs.
    hard_exit_enabled = False
    try:
        raw_hard_exit = settings.get('input.hard_exit', False)
        if hasattr(SettingsManager, "to_bool"):
            hard_exit_enabled = SettingsManager.to_bool(raw_hard_exit, False)
        else:
            hard_exit_enabled = bool(raw_hard_exit)
    except Exception:
        hard_exit_enabled = False
    
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
        
        # Optional system tray presence in hard-exit mode.
        tray_icon = None
        if hard_exit_enabled:
            try:
                tray_icon = ScreensaverTrayIcon(app, app.windowIcon())
            except Exception:
                logger.debug("Failed to create system tray icon", exc_info=True)

            if tray_icon is not None:
                # Delegate to the engine's existing S-key workflow so tray
                # Settings behaves identically to pressing S.
                def _on_tray_settings() -> None:
                    try:
                        # _on_settings_requested performs a full stop →
                        # settings dialog → restart cycle.
                        engine._on_settings_requested()  # type: ignore[attr-defined]
                    except Exception:
                        logger.exception("Failed to open settings from system tray")

                def _on_tray_exit() -> None:
                    try:
                        engine.stop()
                    except Exception:
                        logger.exception("Failed to stop engine from system tray")
                    app.quit()

                tray_icon.settings_requested.connect(_on_tray_settings)
                tray_icon.exit_requested.connect(_on_tray_exit)

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
    verbose_mode = '--verbose' in sys.argv or '-v' in sys.argv
    setup_logging(debug=debug_mode, verbose=verbose_mode)
    
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

        fmt, prefs = build_surface_format(reason="startup")
        QSurfaceFormat.setDefaultFormat(fmt)
        logger.info(
            "Global QSurfaceFormat configured (swap=%s, interval=%s, depth=%s, stencil=%s)",
            fmt.swapBehavior(),
            fmt.swapInterval(),
            fmt.depthBufferSize(),
            fmt.stencilBufferSize(),
        )
    except Exception as e:
        logger.warning(f"Failed to configure global OpenGL format: {e}")
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName(APP_EXE_NAME)
    app.setOrganizationName("ShittyRandomPhotoScreenSaver")
    try:
        app.setApplicationVersion(APP_VERSION)
    except Exception:
        pass

    # Apply application icon from SRPSS.ico when available so the
    # taskbar/systray and dialogs share a consistent identity.
    icon_path = Path(__file__).with_name("SRPSS.ico")
    if icon_path.exists():
        try:
            app.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            logger.debug("Failed to set application icon from SRPSS.ico", exc_info=True)
    
    # Increase Qt image allocation limit from 256MB to 1GB for high-res images
    # This is per-image when loaded, not total memory for all images
    # Images are loaded on-demand, not all at startup (ImageQueue stores metadata only)
    QImageReader.setAllocationLimit(1024)  # 1GB in MB
    logger.info("Qt image allocation limit: 1GB (supports 8K+ images, per-image on-demand)")
    
    logger.info("Qt Application created: %s", app.applicationName())
    logger.debug("High DPI scaling enabled")
    
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
            # TODO: Embed preview into the host window. For now we do not
            # start a full-screen run here to avoid surprising the user when
            # the Screen Saver dialog requests a small thumbnail preview.
            logger.warning("PREVIEW mode not yet implemented (no window shown)")
        
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
