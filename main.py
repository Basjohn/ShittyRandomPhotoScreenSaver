"""
ShittyRandomPhotoScreenSaver - Main Entry Point

Windows screensaver application that displays photos with transitions.
"""
import sys
import logging
from enum import Enum
from PySide6.QtWidgets import QApplication
from core.logging.logger import setup_logging, get_logger

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
    
    Returns:
        tuple: (ScreensaverMode, preview_window_handle)
    """
    args = sys.argv
    
    logger.debug(f"Command-line arguments: {args}")
    
    # Default to run mode if no arguments
    if len(args) == 1:
        logger.info("No arguments provided, defaulting to RUN mode")
        return ScreensaverMode.RUN, None
    
    # Get the first argument (after program name)
    arg = args[1].lower()
    
    # Run screensaver
    if arg == '/s' or arg == '-s':
        logger.info("RUN mode selected")
        return ScreensaverMode.RUN, None
    
    # Configuration dialog
    elif arg == '/c' or arg == '-c':
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


def main():
    """Main entry point for the screensaver application."""
    # Setup logging first
    debug_mode = '--debug' in sys.argv or '-d' in sys.argv
    setup_logging(debug=debug_mode)
    
    logger.info("=" * 60)
    logger.info("ShittyRandomPhotoScreenSaver Starting")
    logger.info("=" * 60)
    
    # Parse command-line arguments
    mode, preview_hwnd = parse_screensaver_args()
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("ShittyRandomPhotoScreenSaver")
    app.setOrganizationName("ShittyRandomPhotoScreenSaver")
    
    logger.info(f"Qt Application created: {app.applicationName()}")
    
    # Route to appropriate mode
    exit_code = 0
    
    try:
        if mode == ScreensaverMode.RUN:
            logger.info("Starting screensaver in RUN mode")
            # TODO: Start screensaver engine
            logger.warning("RUN mode not yet implemented")
            
        elif mode == ScreensaverMode.CONFIG:
            logger.info("Starting configuration dialog")
            # TODO: Show settings dialog
            logger.warning("CONFIG mode not yet implemented")
            
        elif mode == ScreensaverMode.PREVIEW:
            logger.info(f"Starting preview mode (hwnd={preview_hwnd})")
            # TODO: Show preview in parent window
            logger.warning("PREVIEW mode not yet implemented")
        
        # For now, just exit
        logger.info("Exiting (implementation pending)")
        
    except Exception as e:
        logger.exception(f"Fatal error in main: {e}")
        exit_code = 1
    
    logger.info("=" * 60)
    logger.info(f"ShittyRandomPhotoScreenSaver Exiting (code={exit_code})")
    logger.info("=" * 60)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
