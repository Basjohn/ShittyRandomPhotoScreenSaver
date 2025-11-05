"""Manual test for display widget and display manager."""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QTimer
from engine.display_manager import DisplayManager
from rendering.display_modes import DisplayMode
from core.logging.logger import setup_logging, get_logger

setup_logging(debug=True)
logger = get_logger(__name__)


def test_display_manager():
    """Test display manager with sample images."""
    logger.info("=" * 60)
    logger.info("Testing Display Manager")
    logger.info("=" * 60)
    
    app = QApplication(sys.argv)
    
    # Create display manager
    manager = DisplayManager(
        display_mode=DisplayMode.FILL,
        same_image_mode=True
    )
    
    # Initialize displays
    display_count = manager.initialize_displays()
    logger.info(f"Initialized {display_count} displays")
    
    # Get screen info
    screens_info = manager.get_display_info()
    for info in screens_info:
        logger.info(f"Screen {info['screen_index']}: {info['size']} ({info['display_mode']})")
    
    # Try to load a test image
    test_images = Path("test_images")
    if test_images.exists():
        images = list(test_images.glob("*.jpg")) + list(test_images.glob("*.png"))
        if images:
            logger.info(f"Found {len(images)} test images")
            
            # Show first image
            test_image = images[0]
            logger.info(f"Loading: {test_image}")
            
            pixmap = QPixmap(str(test_image))
            if not pixmap.isNull():
                logger.info(f"Image loaded: {pixmap.width()}x{pixmap.height()}")
                manager.show_image(pixmap, str(test_image))
            else:
                logger.warning("Failed to load test image")
                manager.show_error("Failed to load image")
        else:
            logger.warning("No test images found")
            manager.show_error("No test images available")
    else:
        logger.warning("test_images directory not found")
        manager.show_error("Press any key or click to exit\n\ntest_images/ directory not found")
    
    # Connect exit signal
    def on_exit():
        logger.info("Exit requested")
        manager.cleanup()
        app.quit()
    
    manager.exit_requested.connect(on_exit)
    
    # Auto-exit after 5 seconds for testing
    def auto_exit():
        logger.info("Auto-exit triggered (5 second timeout)")
        on_exit()
    
    QTimer.singleShot(5000, auto_exit)
    
    logger.info("\nPress any key or click mouse to exit")
    logger.info("(Auto-exit in 5 seconds)")
    
    # Run
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        test_display_manager()
    except KeyboardInterrupt:
        logger.info("\nTest interrupted")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Test failed: {e}")
        sys.exit(1)
