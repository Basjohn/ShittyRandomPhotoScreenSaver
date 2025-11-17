"""
Display manager for multi-monitor support.

Manages DisplayWidget instances across multiple screens.
"""
import time
from typing import List, Dict, Optional, Set
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication, QScreen, QPixmap

from core.logging.logger import get_logger
from core.resources.manager import ResourceManager
from rendering.display_modes import DisplayMode
from rendering.display_widget import DisplayWidget
from transitions.overlay_manager import hide_all_overlays
from utils.lockfree.spsc_queue import SPSCQueue

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
    
    def __init__(
        self,
        display_mode: DisplayMode = DisplayMode.FILL,
        same_image_mode: bool = True,
        settings_manager=None,
        resource_manager: ResourceManager | None = None,
        thread_manager=None,
    ):
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
        self._resource_manager: ResourceManager | None = resource_manager or ResourceManager()
        self._thread_manager = thread_manager
        self.displays: List[DisplayWidget] = []
        self.current_images: Dict[int, str] = {}  # screen_index -> image_path
        
        # Phase 3: Multi-display synchronization (lock-free)
        self._transition_ready_queue: Optional[SPSCQueue] = None
        self._sync_enabled = False
        
        # Monitor hotplug detection
        self.screen_count = 0
        self._setup_monitor_detection()
        
        logger.info("DisplayManager initialized (mode=%s, same_image=%s)" % (display_mode, same_image_mode))
    
    def _setup_monitor_detection(self) -> None:
        """Setup monitor hotplug detection."""
        app = QGuiApplication.instance()
        if app:
            # Connect to screen change signals
            app.screenAdded.connect(self._on_screen_added)
            app.screenRemoved.connect(self._on_screen_removed)
            
            # Store initial screen count
            self.screen_count = len(app.screens())
            logger.info("Monitor detection enabled (%d screens)" % self.screen_count)
    
    def _on_screen_added(self, screen: QScreen) -> None:
        """Handle screen added event."""
        logger.info("Screen added: %s (%dx%d)" % (screen.name(), screen.geometry().width(), screen.geometry().height()))
        
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
        logger.info("Screen removed: %s" % screen.name())
        
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
        
        logger.info("Initializing displays for %d screens" % screen_count)
        
        # Clear existing displays
        self.cleanup()
        
        # Create display for each screen
        for i in range(screen_count):
            self._create_display_for_screen(i)
        
        logger.info("Created %d display widgets" % len(self.displays))
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
                settings_manager=self.settings_manager,
                resource_manager=self._resource_manager,
                thread_manager=self._thread_manager,
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
            logger.info("Display widget created for screen %d" % screen_index)
        
        except Exception as e:
            logger.error("Failed to create display for screen %d: %s" % (screen_index, e), exc_info=True)
    
    def _cleanup_excess_displays(self) -> None:
        """Clean up displays for screens that no longer exist."""
        screen_count = len(QGuiApplication.screens())
        
        while len(self.displays) > screen_count:
            display = self.displays.pop()
            display.close()
            display.deleteLater()
            logger.info("Removed excess display widget")
    
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
            try:
                if hasattr(display, "reset_after_settings"):
                    display.reset_after_settings()
            except Exception:
                pass
            display.showFullScreen()
            try:
                hide_all_overlays(display)
            except Exception:
                pass
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
    
    # --- Phase 3: Multi-Display Synchronization (Lock-Free) ---
    
    def enable_transition_sync(self, enabled: bool = True) -> None:
        """
        Enable synchronized transitions across displays using lock-free SPSC queue.
        
        Args:
            enabled: True to enable sync, False to disable
        """
        self._sync_enabled = enabled
        if enabled and len(self.displays) > 1:
            # Create SPSC queue for transition ready signals (capacity 20 pending signals)
            self._transition_ready_queue = SPSCQueue(capacity=20)
            logger.info(f"[SYNC] Multi-display transition synchronization enabled for {len(self.displays)} displays")
        else:
            self._transition_ready_queue = None
            if enabled:
                logger.debug("[SYNC] Sync requested but only 1 display, disabling")
            else:
                logger.debug("[SYNC] Multi-display transition synchronization disabled")
    
    def _on_display_transition_ready(self, display_index: int) -> None:
        """
        Called when a display's transition overlay is ready.
        
        Producer method for SPSC queue (called from display widgets).
        
        Args:
            display_index: Index of display that's ready
        """
        if self._transition_ready_queue is not None:
            success = self._transition_ready_queue.try_push(display_index)
            if success:
                logger.debug(f"[SYNC] Display {display_index} transition ready signal queued")
            else:
                logger.warning(f"[SYNC] Failed to queue ready signal for display {display_index} (queue full)")
    
    def wait_for_all_displays_ready(self, timeout_sec: float = 1.0) -> bool:
        """
        Wait for all displays to signal transition ready (consumer method).
        
        Uses lock-free SPSC queue to collect ready signals from each display.
        Returns early if all displays signal ready before timeout.
        
        Args:
            timeout_sec: Maximum time to wait in seconds
        
        Returns:
            True if all displays ready, False if timeout or sync disabled
        """
        if not self._sync_enabled or self._transition_ready_queue is None:
            return True  # Sync disabled, proceed immediately
        
        if len(self.displays) <= 1:
            return True  # Single display, no sync needed
        
        expected_count = len(self.displays)
        ready_set: Set[int] = set()
        start_time = time.time()
        
        logger.debug(f"[SYNC] Waiting for {expected_count} displays to be ready (timeout={timeout_sec:.2f}s)")
        
        while len(ready_set) < expected_count:
            # Try to pop ready signal from queue
            success, display_idx = self._transition_ready_queue.try_pop()
            
            if success and display_idx is not None:
                ready_set.add(display_idx)
                logger.debug(f"[SYNC] Display {display_idx} ready ({len(ready_set)}/{expected_count})")
            else:
                # Queue empty, check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout_sec:
                    logger.warning(f"[SYNC] Timeout waiting for displays: {len(ready_set)}/{expected_count} ready after {elapsed:.2f}s")
                    return False
                
                # Small sleep to avoid busy-wait
                time.sleep(0.001)
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"[SYNC] All {expected_count} displays ready in {elapsed_ms:.1f}ms")
        return True
    
    def show_image_synchronized(self, pixmap: QPixmap, image_path: str = "") -> None:
        """
        Show image on all displays with synchronized transitions.
        
        If sync is enabled, waits for all displays to signal transition ready
        before starting animations. Uses lock-free SPSC queue.
        
        Args:
            pixmap: Image to display
            image_path: Path to image file
        """
        if not self.displays:
            logger.warning("[FALLBACK] No displays available")
            return
        
        # If sync disabled or single display, use standard method
        if not self._sync_enabled or len(self.displays) <= 1:
            self.show_image(pixmap, image_path)
            return
        
        # Clear ready queue before starting
        if self._transition_ready_queue:
            while self._transition_ready_queue.try_pop()[0]:
                pass
        
        # Start transitions on all displays
        logger.debug(f"[SYNC] Starting synchronized transition on {len(self.displays)} displays")
        for display in self.displays:
            display.set_image(pixmap, image_path)
        
        # Wait for all to be ready (with timeout)
        all_ready = self.wait_for_all_displays_ready(timeout_sec=1.0)
        
        if not all_ready:
            logger.warning("[SYNC] Not all displays ready, transitions may desync")
        else:
            logger.debug("[SYNC] Synchronized transition started successfully")
    
    def cleanup(self) -> None:
        """Clean up all display widgets."""
        logger.info(f"Cleaning up {len(self.displays)} display widgets")
        
        for display in self.displays:
            try:
                # Ensure per-display cleanup (pan & scan, transitions, overlays)
                try:
                    display.clear()
                except Exception:
                    pass
                display.close()
                display.deleteLater()
            except Exception as e:
                logger.warning(f"Error closing display: {e}")
        
        self.displays.clear()
        self.current_images.clear()
        logger.info("Display manager cleanup complete")
