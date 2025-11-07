"""
Display manager for multi-monitor support.

Manages DisplayWidget instances across multiple screens.
"""
from typing import List, Dict, Optional
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QGuiApplication, QScreen, QPixmap
from rendering.display_widget import DisplayWidget
from rendering.display_modes import DisplayMode
from core.logging.logger import get_logger

logger = get_logger(__name__)


class DisplayManager(QObject):
    """
    Manage display widgets across multiple monitors.
    
    Features:
    - Multi-monitor detection
    - DisplayWidget creation per monitor
    - Monitor hotplug handling
    - Same/different image modes
    - Coordinated exit
    
    Signals:
    - exit_requested: Emitted when any display requests exit
    - monitors_changed: Emitted when monitor configuration changes
    """
    
    exit_requested = Signal()
    monitors_changed = Signal(int)  # new monitor count
    previous_requested = Signal()  # Z key - go to previous image
    next_requested = Signal()  # X key - go to next image
    cycle_transition_requested = Signal()  # C key - cycle transition mode
    settings_requested = Signal()  # S key - open settings
    
    def __init__(self, display_mode: DisplayMode = DisplayMode.FILL,
                 same_image_mode: bool = True,
                 settings_manager=None):
        """
        Initialize display manager.
        
        Args:
            display_mode: Display mode for all screens
            same_image_mode: True = same image on all screens, False = different images
            settings_manager: SettingsManager for widget configuration
        """
        super().__init__()
        
        self.display_mode = display_mode
        self.same_image_mode = same_image_mode
        self.settings_manager = settings_manager
        self.displays: List[DisplayWidget] = []
        self.current_images: Dict[int, str] = {}  # screen_index -> image_path
        
        # Monitor hotplug detection
        self.screen_count = 0
        self._setup_monitor_detection()
        
        logger.info(f"DisplayManager initialized (mode={display_mode}, same_image={same_image_mode})")
    
    def _setup_monitor_detection(self) -> None:
        """Setup monitor hotplug detection."""
        app = QGuiApplication.instance()
        if app:
            # Connect to screen change signals
            app.screenAdded.connect(self._on_screen_added)
            app.screenRemoved.connect(self._on_screen_removed)
            
            # Store initial screen count
            self.screen_count = len(app.screens())
            logger.info(f"Monitor detection enabled ({self.screen_count} screens)")
    
    def _on_screen_added(self, screen: QScreen) -> None:
        """Handle screen added event."""
        logger.info(f"Screen added: {screen.name()} ({screen.geometry().width()}x{screen.geometry().height()})")
        
        new_count = len(QGuiApplication.screens())
        
        if new_count > self.screen_count:
            self.screen_count = new_count
            self.monitors_changed.emit(new_count)
            
            # Create new display for added screen
            if self.displays:  # Only if already initialized
                screen_index = new_count - 1
                self._create_display_for_screen(screen_index)
    
    def _on_screen_removed(self, screen: QScreen) -> None:
        """Handle screen removed event."""
        logger.info(f"Screen removed: {screen.name()}")
        
        new_count = len(QGuiApplication.screens())
        
        if new_count < self.screen_count:
            self.screen_count = new_count
            self.monitors_changed.emit(new_count)
            
            # Clean up excess displays
            self._cleanup_excess_displays()
    
    def initialize_displays(self) -> int:
        """
        Create and show display widgets for all monitors.
        
        Returns:
            Number of displays created
        """
        screens = QGuiApplication.screens()
        screen_count = len(screens)
        
        logger.info(f"Initializing displays for {screen_count} screens")
        
        # Clear existing displays
        self.cleanup()
        
        # Create display for each screen
        for i in range(screen_count):
            self._create_display_for_screen(i)
        
        logger.info(f"Created {len(self.displays)} display widgets")
        return len(self.displays)
    
    def _create_display_for_screen(self, screen_index: int) -> None:
        """
        Create display widget for a specific screen.
        
        Args:
            screen_index: Screen index
        """
        try:
            display = DisplayWidget(
                screen_index=screen_index,
                display_mode=self.display_mode,
                settings_manager=self.settings_manager
            )
            
            # Connect signals
            display.exit_requested.connect(self._on_exit_requested)
            # FIX: Use default args to capture screen_index by value (not by reference)
            display.image_displayed.connect(
                lambda path, idx=screen_index: self._on_image_displayed(idx, path)
            )
            
            # Connect hotkey signals
            display.previous_requested.connect(self.previous_requested.emit)
            display.next_requested.connect(self.next_requested.emit)
            display.cycle_transition_requested.connect(self.cycle_transition_requested.emit)
            display.settings_requested.connect(self.settings_requested.emit)
            
            # Show fullscreen
            display.show_on_screen()
            
            self.displays.append(display)
            logger.info(f"Display widget created for screen {screen_index}")
        
        except Exception as e:
            logger.error(f"Failed to create display for screen {screen_index}: {e}", exc_info=True)
    
    def _cleanup_excess_displays(self) -> None:
        """Clean up displays for screens that no longer exist."""
        screen_count = len(QGuiApplication.screens())
        
        while len(self.displays) > screen_count:
            display = self.displays.pop()
            display.close()
            display.deleteLater()
            logger.info(f"Removed excess display widget")
    
    def _on_exit_requested(self) -> None:
        """Handle exit request from any display."""
        logger.info("Exit requested from display widget")
        self.exit_requested.emit()
    
    def _on_image_displayed(self, screen_index: int, image_path: str) -> None:
        """Handle image displayed event."""
        self.current_images[screen_index] = image_path
        logger.debug(f"Image displayed on screen {screen_index}: {image_path}")
    
    def show_image(self, pixmap: QPixmap, image_path: str = "", 
                   screen_index: Optional[int] = None) -> None:
        """
        Show image on display(s).
        
        Args:
            pixmap: Image to display
            image_path: Path to image (for logging)
            screen_index: Specific screen index, or None for all screens (same_image_mode)
        """
        if not self.displays:
            logger.warning("[FALLBACK] No displays available")
            return
        
        if screen_index is not None:
            # Show on specific screen
            if 0 <= screen_index < len(self.displays):
                self.displays[screen_index].set_image(pixmap, image_path)
            else:
                logger.warning(f"[FALLBACK] Invalid screen index: {screen_index}")
        else:
            # Show on all screens (same image mode)
            if self.same_image_mode:
                for display in self.displays:
                    display.set_image(pixmap, image_path)
                logger.debug(f"Image shown on all {len(self.displays)} displays")
    
    def show_image_on_screen(self, screen_index: int, pixmap: QPixmap, image_path: str = "") -> None:
        """
        Show image on specific screen.
        
        Args:
            screen_index: Screen index
            pixmap: Image to display
            image_path: Path to image
        """
        self.show_image(pixmap, image_path, screen_index)
    
    def show_error(self, message: str, screen_index: Optional[int] = None) -> None:
        """
        Show error message on display(s).
        
        Args:
            message: Error message
            screen_index: Specific screen, or None for all screens
        """
        if screen_index is not None:
            if 0 <= screen_index < len(self.displays):
                self.displays[screen_index].show_error(message)
        else:
            for display in self.displays:
                display.show_error(message)
            logger.warning(f"[FALLBACK] Error shown on all displays: {message}")
    
    def clear_all(self) -> None:
        """Clear all displays (removes image but keeps windows visible)."""
        for display in self.displays:
            display.clear()
        self.current_images.clear()
        logger.info("All displays cleared")
    
    def hide_all(self) -> None:
        """Hide all display widgets (for showing dialogs on top)."""
        for display in self.displays:
            display.hide()
        logger.info("All displays hidden")
    
    def show_all(self) -> None:
        """Show all display widgets (after dialogs close)."""
        for display in self.displays:
            display.showFullScreen()
        logger.info("All displays shown")
    
    def set_display_mode(self, mode: DisplayMode) -> None:
        """
        Change display mode for all screens.
        
        Args:
            mode: New display mode
        """
        self.display_mode = mode
        for display in self.displays:
            display.set_display_mode(mode)
        logger.info(f"Display mode changed to {mode} for all screens")
    
    def set_same_image_mode(self, enabled: bool) -> None:
        """
        Enable/disable same image mode.
        
        Args:
            enabled: True = same image on all screens, False = different images
        """
        self.same_image_mode = enabled
        logger.info(f"Same image mode: {enabled}")
    
    def get_display_count(self) -> int:
        """Get number of active displays."""
        return len(self.displays)
    
    def get_screen_count(self) -> int:
        """Get number of detected screens."""
        return len(QGuiApplication.screens())
    
    def get_display_info(self) -> List[dict]:
        """
        Get information about all displays.
        
        Returns:
            List of display info dicts
        """
        return [display.get_screen_info() for display in self.displays]
    
    def cleanup(self) -> None:
        """Clean up all display widgets."""
        logger.info(f"Cleaning up {len(self.displays)} display widgets")
        
        for display in self.displays:
            try:
                display.close()
                display.deleteLater()
            except Exception as e:
                logger.warning(f"Error closing display: {e}")
        
        self.displays.clear()
        self.current_images.clear()
        logger.info("Display manager cleanup complete")
