"""
Display manager for multi-monitor support.

Manages DisplayWidget instances across multiple screens.
"""
import time
from typing import List, Dict, Optional, Set
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtGui import QGuiApplication, QScreen, QPixmap, QDesktopServices

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.resources.manager import ResourceManager
from rendering.display_modes import DisplayMode
from rendering.display_widget import DisplayWidget
from transitions.overlay_manager import hide_all_overlays
from utils.lockfree.spsc_queue import SPSCQueue

logger = get_logger(__name__)
REDDIT_FLUSH_LOGGING = True  # Set to False to silence deferred Reddit flush diagnostics once stable.

try:  # Windows-only helper to escape Winlogon desktop
    from core.windows import url_launcher as windows_url_launcher
    from core.windows import reddit_helper_bridge
except Exception:  # pragma: no cover - non-Windows or optional import failure
    windows_url_launcher = None
    reddit_helper_bridge = None


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
        self._deferred_reddit_urls: list[str] = []
        
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

    def _get_allowed_screen_indices(self, screen_count: int) -> set[int]:
        """Resolve which screen indices should create DisplayWidgets.

        Uses the canonical display.show_on_monitors setting:
        - 'ALL' (default) means all screens.
        - A list/tuple/set of 1-based monitor indices (e.g. [1, 2]) selects
          specific screens. Values outside the available range are ignored.
        """

        indices: set[int] = set(range(screen_count))
        if self.settings_manager is None:
            return indices

        try:
            raw = self.settings_manager.get('display.show_on_monitors', 'ALL')
        except Exception as e:
            logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
            raw = 'ALL'

        # Default: all screens
        if isinstance(raw, str):
            if raw.upper() == 'ALL':
                return indices
            # Attempt to parse a stringified list such as "[1, 2]"
            try:
                import ast
                parsed = ast.literal_eval(raw)
                if not isinstance(parsed, (list, tuple, set)):
                    return indices
                values = {int(x) for x in parsed}
            except Exception as e:
                logger.debug("[DISPLAY] Failed to parse show_on_monitors=%r; defaulting to ALL", raw)
                return indices
        elif isinstance(raw, (list, tuple, set)):
            try:
                values = {int(x) for x in raw}
            except Exception as e:
                logger.debug("[DISPLAY] Invalid show_on_monitors=%r; defaulting to ALL", raw)
                return indices
        else:
            return indices

        # Convert 1-based monitor numbers to 0-based indices and clamp to range
        allowed = {m - 1 for m in values if 1 <= int(m) <= screen_count}
        if not allowed:
            logger.debug("[DISPLAY] Resolved empty show_on_monitors from %r; defaulting to ALL", raw)
            return indices
        logger.info("[DISPLAY] show_on_monitors=%r → allowed screen indices=%s", raw, sorted(allowed))
        return allowed
    
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
                allowed = self._get_allowed_screen_indices(new_count)
                if screen_index in allowed:
                    self._create_display_for_screen(screen_index)
                else:
                    logger.info(
                        "[DISPLAY] Skipping display for screen %d due to show_on_monitors",
                        screen_index,
                    )
    
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

        # Resolve which screens should actually create DisplayWidgets
        allowed_indices = self._get_allowed_screen_indices(screen_count)
        
        # Create display for each allowed screen with staggered initialization.
        # This prevents simultaneous GL compositor init on multiple displays
        # which can cause 100-200ms UI thread blocks.
        stagger_ms = 100  # 100ms between display creations (increased from 50ms)
        created_count = 0
        for i in range(screen_count):
            if i in allowed_indices:
                # Stagger after first display to spread GL init load
                if created_count > 0 and stagger_ms > 0:
                    from PySide6.QtCore import QCoreApplication
                    # Process events and wait to stagger GL compositor init
                    QCoreApplication.processEvents()
                    time.sleep(stagger_ms / 1000.0)
                self._create_display_for_screen(i)
                created_count += 1
            else:
                logger.info(
                    "[DISPLAY] Skipping display for screen %d due to show_on_monitors",
                    i,
                )
        
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
            
            # Connect dimming sync signal - when one display changes dimming, update all
            display.dimming_changed.connect(self.set_dimming_all_displays)
            
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
    
    def set_process_supervisor(self, supervisor) -> None:
        """Set the ProcessSupervisor on all display widgets.
        
        This enables FFTWorker integration for the Spotify visualizer.
        """
        for display in self.displays:
            try:
                display.set_process_supervisor(supervisor)
            except Exception as e:
                logger.debug("Failed to set ProcessSupervisor on display", exc_info=True)
    
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
            except Exception as e:
                logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
            try:
                display.show_on_screen()
            except Exception as e:
                logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
                display.show()
            try:
                hide_all_overlays(display)
            except Exception as e:
                logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
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
    
    def set_dimming_all_displays(self, enabled: bool, opacity: float) -> None:
        """
        Update dimming on ALL displays.
        
        Called when dimming is toggled via context menu to ensure all displays
        stay synchronized.
        
        Args:
            enabled: True to enable dimming, False to disable
            opacity: Dimming opacity 0.0-1.0
        """
        for display in self.displays:
            try:
                display._dimming_enabled = enabled
                display._dimming_opacity = opacity
                comp = getattr(display, "_gl_compositor", None)
                if comp is not None and hasattr(comp, "set_dimming"):
                    comp.set_dimming(enabled, opacity)
            except Exception as e:
                logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
        logger.debug("Dimming updated on all %d displays: enabled=%s, opacity=%.0f%%",
                     len(self.displays), enabled, opacity * 100)
    
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
    
    def has_running_transition(self) -> bool:
        """Return True if any display currently has a running transition."""
        try:
            for display in self.displays:
                try:
                    if hasattr(display, "has_running_transition") and display.has_running_transition():
                        return True
                except Exception as e:
                    logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
                    continue
        except Exception as e:
            logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
            return False
        return False
    
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
        count = len(self.displays)
        logger.info("Cleaning up %d display widgets", count)

        # Reset global DisplayWidget state to avoid stale references after cleanup
        try:
            from rendering.display_widget import DisplayWidget
            from PySide6.QtGui import QGuiApplication
            
            # Remove event filter from app before destroying the owner widget
            owner = DisplayWidget._event_filter_owner
            if owner is not None:
                try:
                    app = QGuiApplication.instance()
                    if app is not None:
                        app.removeEventFilter(owner)
                except Exception as e:
                    logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
            
            DisplayWidget._global_ctrl_held = False
            DisplayWidget._halo_owner = None
            DisplayWidget._event_filter_installed = False
            DisplayWidget._event_filter_owner = None
            DisplayWidget._focus_owner = None
            # Clear the screen-to-widget cache to avoid stale references
            DisplayWidget._instances_by_screen.clear()
            logger.debug("[CLEANUP] Reset all DisplayWidget global state")
        except Exception as e:
            logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)

        pending_reddit_urls: list[str] = []

        for idx, display in enumerate(self.displays):
            try:
                screen_index = getattr(display, "screen_index", idx)
            except Exception as e:
                logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
                screen_index = idx
            logger.debug(
                "Cleaning up display widget (index=%d/%d, screen_index=%s)",
                idx,
                count,
                screen_index,
            )

            try:
                url = getattr(display, "_pending_reddit_url", None)
                if isinstance(url, str) and url:
                    pending_reddit_urls.append(url)
                    try:
                        setattr(display, "_pending_reddit_url", None)
                    except Exception as e:
                        logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
                # Instrumentation: log state and stop render pipeline before clearing
                if is_perf_metrics_enabled():
                    try:
                        state = display.describe_runtime_state()
                        logger.info("[PERF][DISPLAY_MANAGER] cleanup_display screen=%s state=%s", screen_index, state)
                    except Exception as exc:
                        logger.debug("[DISPLAY_MANAGER] Failed to describe state: %s", exc)
                try:
                    display.shutdown_render_pipeline("cleanup")
                except Exception as exc:
                    logger.debug("[DISPLAY_MANAGER] shutdown_render_pipeline failed: %s", exc)
                # Ensure per-display cleanup (pan & scan, transitions, overlays)
                try:
                    display.clear()
                except Exception as e:
                    logger.debug(
                        "Display.clear() failed during cleanup (index=%d, screen_index=%s): %s",
                        idx,
                        screen_index,
                        e,
                        exc_info=True,
                    )
                display.close()
                display.deleteLater()
            except Exception as e:
                logger.warning(
                    "Error closing display (index=%d, screen_index=%s): %s",
                    idx,
                    screen_index,
                    e,
                    exc_info=True,
                )

        self.displays.clear()
        self.current_images.clear()

        self._deferred_reddit_urls = pending_reddit_urls

        logger.info("Display manager cleanup complete")

    def take_deferred_reddit_urls(self) -> list[str]:
        """Retrieve and clear deferred Reddit URLs collected during cleanup."""
        urls, self._deferred_reddit_urls = self._deferred_reddit_urls, []
        return urls

    def flush_deferred_reddit_urls(self, *, ensure_widgets_dismissed: bool = False) -> None:
        """Open any deferred Reddit URLs collected during the last cleanup."""
        urls = self.take_deferred_reddit_urls()
        if not urls:
            return

        if ensure_widgets_dismissed:
            try:
                app = QGuiApplication.instance()
                if app is not None:
                    app.processEvents()
            except Exception as e:
                logger.debug("[REDDIT] processEvents failed before flush", exc_info=True)

        if REDDIT_FLUSH_LOGGING:
            logger.info("[REDDIT] Deferred URL flush started (count=%d)", len(urls))
        else:
            logger.info("[REDDIT] Opening %d deferred Reddit URLs", len(urls))

        helper_module = windows_url_launcher
        helper_bridge = reddit_helper_bridge
        use_helper = False
        use_bridge = False
        if helper_module is not None:
            try:
                use_helper = helper_module.should_use_session_launcher()
            except Exception as e:
                logger.debug("[REDDIT] Helper capability check failed", exc_info=True)
                use_helper = False
        if helper_bridge is not None and helper_bridge.is_bridge_available():
            use_bridge = True

        for url in urls:
            launched = False

            if use_bridge:
                try:
                    launched = helper_bridge.enqueue_url(url)
                    if launched:
                        logger.info("[REDDIT] Deferred URL queued via ProgramData bridge: %s", url)
                        continue
                except Exception as e:
                    logger.warning("[REDDIT] Bridge enqueue failed; falling back", exc_info=True)
                    launched = False

            if use_helper:
                try:
                    launched = bool(helper_module.launch_url_via_user_desktop(url))
                    if launched:
                        logger.info("[REDDIT] Helper launched deferred URL: %s", url)
                    else:
                        logger.debug("[REDDIT] Helper declined to launch URL; falling back")
                except Exception as e:
                    logger.warning("[REDDIT] Helper launch failed; falling back", exc_info=True)
                    launched = False

            if not launched:
                try:
                    launched = QDesktopServices.openUrl(QUrl(url))
                except Exception as exc:
                    logger.warning("[REDDIT] Failed to open deferred URL: %s", exc, exc_info=True)
                    launched = False

                if launched:
                    logger.info("[REDDIT] Deferred URL opened: %s", url)
                else:
                    logger.warning(
                        "[REDDIT] Failed to open deferred URL (QDesktopServices rejected): %s",
                        url,
                    )
