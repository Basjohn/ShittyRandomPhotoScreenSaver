"""
Display widget for showing images fullscreen.

Handles image display, input events, and error messages.
"""
from typing import Optional
from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QPixmap, QPainter, QKeyEvent, QMouseEvent, QPaintEvent, QFont
from rendering.display_modes import DisplayMode
from rendering.image_processor import ImageProcessor
from core.logging.logger import get_logger

logger = get_logger(__name__)


class DisplayWidget(QWidget):
    """
    Fullscreen widget for displaying images.
    
    Features:
    - Fullscreen display
    - Image processing with display modes
    - Input handling (mouse/keyboard exit)
    - Error message display
    - Screen-specific positioning
    
    Signals:
    - exit_requested: Emitted when user wants to exit
    - image_displayed: Emitted when new image is shown
    """
    
    exit_requested = Signal()
    image_displayed = Signal(str)  # image path
    
    def __init__(self, screen_index: int = 0, 
                 display_mode: DisplayMode = DisplayMode.FILL,
                 parent: Optional[QWidget] = None):
        """
        Initialize display widget.
        
        Args:
            screen_index: Index of screen to display on
            display_mode: Image display mode
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.screen_index = screen_index
        self.display_mode = display_mode
        self.current_pixmap: Optional[QPixmap] = None
        self.error_message: Optional[str] = None
        
        # Setup widget
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setMouseTracking(True)
        
        # Set black background
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.GlobalColor.black)
        self.setPalette(palette)
        
        logger.info(f"DisplayWidget created for screen {screen_index} ({display_mode})")
    
    def show_on_screen(self) -> None:
        """Show widget fullscreen on assigned screen."""
        from PySide6.QtGui import QGuiApplication
        
        screens = QGuiApplication.screens()
        
        if self.screen_index >= len(screens):
            logger.warning(f"[FALLBACK] Screen {self.screen_index} not found, using primary")
            screen = QGuiApplication.primaryScreen()
        else:
            screen = screens[self.screen_index]
        
        geometry = screen.geometry()
        logger.info(f"Showing on screen {self.screen_index}: "
                   f"{geometry.width()}x{geometry.height()} at ({geometry.x()}, {geometry.y()})")
        
        # Position and size window
        self.setGeometry(geometry)
        self.showFullScreen()
    
    def set_image(self, pixmap: QPixmap, image_path: str = "") -> None:
        """
        Display a new image.
        
        Args:
            pixmap: Image to display
            image_path: Path to image (for logging/events)
        """
        if pixmap.isNull():
            logger.warning("[FALLBACK] Received null pixmap")
            self.error_message = "Failed to load image"
            self.current_pixmap = None
            self.update()
            return
        
        # Process image for display
        screen_size = self.size()
        
        try:
            self.current_pixmap = ImageProcessor.process_image(
                pixmap,
                screen_size,
                self.display_mode
            )
            
            self.error_message = None
            self.update()
            
            logger.debug(f"Image displayed: {image_path} ({pixmap.width()}x{pixmap.height()})")
            self.image_displayed.emit(image_path)
        
        except Exception as e:
            logger.error(f"Failed to process image: {e}", exc_info=True)
            self.error_message = f"Error processing image: {e}"
            self.current_pixmap = None
            self.update()
    
    def set_display_mode(self, mode: DisplayMode) -> None:
        """
        Change display mode.
        
        Args:
            mode: New display mode
        """
        if mode != self.display_mode:
            self.display_mode = mode
            logger.info(f"Display mode changed to {mode}")
            
            # Reprocess current image if available
            if self.current_pixmap:
                # Note: This reprocesses the already-processed pixmap
                # In production, we'd want to store the original and reprocess from that
                logger.debug("Reprocessing current image with new mode")
                self.update()
    
    def clear(self) -> None:
        """Clear displayed image."""
        self.current_pixmap = None
        self.error_message = None
        self.update()
        logger.debug("Display cleared")
    
    def show_error(self, message: str) -> None:
        """
        Show error message.
        
        Args:
            message: Error message to display
        """
        self.error_message = message
        self.current_pixmap = None
        self.update()
        logger.warning(f"[FALLBACK] Showing error: {message}")
    
    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint event - draw current image or error message."""
        painter = QPainter(self)
        
        # Fill with black background
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        
        # Draw image if available
        if self.current_pixmap and not self.current_pixmap.isNull():
            painter.drawPixmap(0, 0, self.current_pixmap)
        
        # Draw error message if present
        elif self.error_message:
            painter.setPen(Qt.GlobalColor.white)
            font = QFont("Arial", 24)
            painter.setFont(font)
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self.error_message
            )
        
        painter.end()
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press - exit on any key."""
        logger.info(f"Key pressed: {event.key()}, requesting exit")
        self.exit_requested.emit()
        event.accept()
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press - exit on any click."""
        logger.info(f"Mouse clicked at ({event.pos().x()}, {event.pos().y()}), requesting exit")
        self.exit_requested.emit()
        event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move - could trigger exit after threshold."""
        # For now, just track movement
        # In future, could implement "move distance threshold" before exit
        event.accept()
    
    def get_screen_info(self) -> dict:
        """
        Get information about this display.
        
        Returns:
            Dict with display information
        """
        return {
            'screen_index': self.screen_index,
            'display_mode': str(self.display_mode),
            'size': f"{self.width()}x{self.height()}",
            'has_image': self.current_pixmap is not None,
            'has_error': self.error_message is not None
        }
