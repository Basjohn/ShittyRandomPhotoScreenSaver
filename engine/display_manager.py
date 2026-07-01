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
MONITOR_RECONCILE_DELAY_MS = 250

try:  # Windows-only bridge for ProgramData queue
    from core.windows import reddit_helper_bridge
except Exception:  # pragma: no cover - non-Windows or optional import failure
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
    displays_ready = Signal(int)  # startup generation ready for image replay
    transition_completed = Signal(int)  # screen index
    previous_requested = Signal()  # Z key - go to previous image
    next_requested = Signal()  # X key - go to next image
    cycle_transition_requested = Signal()  # C key - cycle transition mode
    settings_requested = Signal()  # S key - open settings
    custom_layout_reload_requested = Signal()
    
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
        self._resource_manager: ResourceManager | None = (
            resource_manager or ResourceManager.get_or_create_app_shared()
        )
        self._thread_manager = thread_manager
        self.displays: List[DisplayWidget] = []
        self.current_images: Dict[int, str] = {}  # screen_index -> image_path
        self._deferred_reddit_urls: list[str] = []
        self._display_startup_generation = 0
        self._display_startup_ready_expected: Set[int] = set()
        self._display_startup_ready_seen: Set[int] = set()
        self._display_startup_ready_emitted_generation: int = -1
        
        # Phase 3: Multi-display synchronization (lock-free)
        self._transition_ready_queue: Optional[SPSCQueue] = None
        self._sync_enabled = False
        self._transition_work_pending = False
        self._monitor_detection_app = None
        self._monitor_detection_connected = False
        self._monitor_reconcile_pending = False
        self._screen_signature: tuple[tuple[object, ...], ...] = ()
        
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
            self._monitor_detection_app = app
            self._monitor_detection_connected = True
            
            # Store initial screen count
            self._screen_signature = self._current_screen_signature()
            self.screen_count = len(self._screen_signature)
            logger.info("Monitor detection enabled (%d screens)" % self.screen_count)

    def disconnect_monitor_detection(self) -> None:
        """Detach this manager from application monitor signals before replacement."""
        app = self._monitor_detection_app
        if app is None or not self._monitor_detection_connected:
            return
        try:
            app.screenAdded.disconnect(self._on_screen_added)
        except Exception:
            logger.debug("[DISPLAY_MANAGER] screenAdded disconnect skipped", exc_info=True)
        try:
            app.screenRemoved.disconnect(self._on_screen_removed)
        except Exception:
            logger.debug("[DISPLAY_MANAGER] screenRemoved disconnect skipped", exc_info=True)
        self._monitor_detection_connected = False
        self._monitor_detection_app = None

    @staticmethod
    def _call_screen_attr(obj: object, name: str, default: object = None) -> object:
        try:
            attr = getattr(obj, name)
        except Exception:
            return default
        try:
            return attr() if callable(attr) else attr
        except Exception:
            return default

    def _screen_signature_part(self, index: int, screen: QScreen) -> tuple[object, ...]:
        geometry = self._call_screen_attr(screen, "geometry")
        available = self._call_screen_attr(screen, "availableGeometry")

        def _geom_part(rect: object) -> tuple[int, int, int, int]:
            if rect is None:
                return (0, 0, 0, 0)
            return (
                int(self._call_screen_attr(rect, "x", 0) or 0),
                int(self._call_screen_attr(rect, "y", 0) or 0),
                int(self._call_screen_attr(rect, "width", 0) or 0),
                int(self._call_screen_attr(rect, "height", 0) or 0),
            )

        dpr = self._call_screen_attr(screen, "devicePixelRatio", 1.0)
        try:
            dpr = round(float(dpr), 3)
        except Exception:
            dpr = 1.0
        return (
            index,
            str(self._call_screen_attr(screen, "name", "")),
            str(self._call_screen_attr(screen, "manufacturer", "")),
            str(self._call_screen_attr(screen, "model", "")),
            str(self._call_screen_attr(screen, "serialNumber", "")),
            _geom_part(geometry),
            _geom_part(available),
            dpr,
        )

    def _current_screen_signature(self) -> tuple[tuple[object, ...], ...]:
        try:
            screens = QGuiApplication.screens()
        except Exception:
            logger.debug("[DISPLAY_MANAGER] Failed to read screen signature", exc_info=True)
            return ()
        return tuple(self._screen_signature_part(index, screen) for index, screen in enumerate(screens))

    def _schedule_monitor_reconcile(self, reason: str) -> None:
        """Coalesce Qt screen churn into one settled topology reconcile.

        Windows display wake can emit screenAdded/screenRemoved while
        QGuiApplication.screens() still reports a stale count.  Rechecking a
        short moment later by full screen signature avoids both missed rebuilds
        and per-event rebuild storms.
        """

        if not self._monitor_detection_connected:
            return
        if self._monitor_reconcile_pending:
            logger.debug("[DISPLAY_MANAGER] Monitor reconcile already pending reason=%s", reason)
            return
        self._monitor_reconcile_pending = True

        def _run() -> None:
            self._monitor_reconcile_pending = False
            self._reconcile_monitor_topology(reason)

        if self._thread_manager is None or not hasattr(self._thread_manager, "single_shot"):
            self._monitor_reconcile_pending = False
            logger.warning(
                "[DISPLAY_MANAGER][FALLBACK] Monitor topology reconcile skipped: "
                "ThreadManager single_shot unavailable"
            )
            return

        try:
            self._thread_manager.single_shot(MONITOR_RECONCILE_DELAY_MS, _run)
        except Exception:
            self._monitor_reconcile_pending = False
            logger.warning(
                "[DISPLAY_MANAGER][FALLBACK] Monitor topology reconcile scheduling failed; "
                "ThreadManager single_shot rejected the request",
                exc_info=True,
            )

    def _reconcile_monitor_topology(self, reason: str) -> None:
        if not self._monitor_detection_connected:
            logger.debug("[DISPLAY_MANAGER] Ignoring monitor reconcile after manager disconnect reason=%s", reason)
            return

        old_count = self.screen_count
        old_signature = self._screen_signature
        new_signature = self._current_screen_signature()
        new_count = len(new_signature)
        if new_count == old_count and new_signature == old_signature:
            logger.debug("[DISPLAY_MANAGER] Monitor reconcile no-op reason=%s count=%d", reason, new_count)
            return

        self.screen_count = new_count
        self._screen_signature = new_signature
        logger.info(
            "[DISPLAY_MANAGER] Monitor topology reconciled reason=%s old_count=%d new_count=%d old_signature=%s new_signature=%s",
            reason,
            old_count,
            new_count,
            old_signature,
            new_signature,
        )
        self.monitors_changed.emit(new_count)

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
            if raw.upper() == 'NONE':
                return set()
            # Attempt to parse a stringified list such as "[1, 2]"
            try:
                import ast
                parsed = ast.literal_eval(raw)
                if not isinstance(parsed, (list, tuple, set)):
                    return indices
                values = {int(x) for x in parsed}
            except Exception:
                logger.debug("[DISPLAY] Failed to parse show_on_monitors=%r; defaulting to ALL", raw)
                return indices
        elif isinstance(raw, (list, tuple, set)):
            try:
                values = {int(x) for x in raw}
            except Exception:
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
        self._schedule_monitor_reconcile("screenAdded")
    
    def _on_screen_removed(self, screen: QScreen) -> None:
        """Handle screen removed event."""
        logger.info("Screen removed: %s" % screen.name())
        self._schedule_monitor_reconcile("screenRemoved")
    
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
        self._display_startup_generation += 1
        startup_generation = self._display_startup_generation

        # Resolve which screens should actually create DisplayWidgets
        allowed_indices = self._get_allowed_screen_indices(screen_count)
        
        # Instantiate the full active display set before the first display runs
        # widget setup. Visualizer CUSTOM owner selection is participation-based,
        # so screen 0 must be able to see later requested displays as pending
        # startup instead of misclassifying them as absent.
        pending_displays: List[DisplayWidget] = []
        for i in range(screen_count):
            if i in allowed_indices:
                display = self._create_display_for_screen(i, show_immediately=False)
                if display is not None:
                    pending_displays.append(display)
            else:
                logger.info(
                    "[DISPLAY] Skipping display for screen %d due to show_on_monitors",
                    i,
                )

        self._display_startup_ready_expected = {id(display) for display in pending_displays}
        self._display_startup_ready_seen = set()
        self._display_startup_ready_emitted_generation = -1

        # Preserve staggered show behavior without processEvents() re-entry.
        # Display registration happens before this loop, so visualizer owner
        # selection sees the full active set while the expensive show/GL startup
        # work is still spread across UI turns. The generation guard prevents a
        # delayed show from firing after settings/edit cleanup has replaced the
        # display set.
        stagger_ms = 100
        for idx, display in enumerate(pending_displays):
            delay_ms = idx * stagger_ms
            if delay_ms <= 0:
                self._show_display_widget(display, startup_generation=startup_generation)
                continue

            def _show_if_current(
                disp: DisplayWidget = display,
                generation: int = startup_generation,
            ) -> None:
                if generation != self._display_startup_generation:
                    logger.debug(
                        "[DISPLAY] Suppressed stale staggered show for screen %s",
                        getattr(disp, "screen_index", "?"),
                    )
                    return
                if disp not in self.displays:
                    logger.debug(
                        "[DISPLAY] Suppressed staggered show for removed screen %s",
                        getattr(disp, "screen_index", "?"),
                    )
                    return
                self._show_display_widget(disp, startup_generation=generation)

            try:
                from core.threading.manager import ThreadManager

                scheduler = self._thread_manager or ThreadManager
                scheduler.single_shot(delay_ms, _show_if_current)
            except Exception:
                logger.warning(
                    "[DISPLAY][FALLBACK] Stagger scheduler unavailable; showing screen %s immediately",
                    getattr(display, "screen_index", "?"),
                    exc_info=True,
                )
                self._show_display_widget(display, startup_generation=startup_generation)
        
        logger.info("Created %d display widgets" % len(self.displays))
        return len(self.displays)
    
    def _create_display_for_screen(
        self,
        screen_index: int,
        *,
        show_immediately: bool = True,
    ) -> Optional[DisplayWidget]:
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
            display.transition_completed.connect(
                lambda idx=screen_index: self.transition_completed.emit(idx)
            )
            
            # Connect hotkey signals
            display.previous_requested.connect(self.previous_requested.emit)
            display.next_requested.connect(self.next_requested.emit)
            display.cycle_transition_requested.connect(self.cycle_transition_requested.emit)
            display.settings_requested.connect(self.settings_requested.emit)
            display.custom_layout_reload_requested.connect(self.custom_layout_reload_requested.emit)
            
            # Connect dimming sync signal - when one display changes dimming, update all
            display.dimming_changed.connect(self.set_dimming_all_displays)
            
            self.displays.append(display)
            logger.info("Display widget created for screen %d" % screen_index)
            if show_immediately:
                self._show_display_widget(display)
            return display
        except Exception as e:
            logger.error("Failed to create display for screen %d: %s" % (screen_index, e), exc_info=True)
            return None

    def _show_display_widget(self, display: DisplayWidget, *, startup_generation: int | None = None) -> bool:
        """Show a previously-instantiated display widget."""
        try:
            display.show_on_screen()
            if startup_generation is not None:
                self._mark_display_startup_ready(display, startup_generation)
            return True
        except Exception as e:
            screen_index = getattr(display, "screen_index", "?")
            logger.error(
                "Failed to show display for screen %s: %s",
                screen_index,
                e,
                exc_info=True,
            )
            try:
                if display in self.displays:
                    self.displays.remove(display)
            except Exception:
                logger.debug("[DISPLAY_MANAGER] Failed to remove display after show failure", exc_info=True)
            try:
                display.close()
            except Exception:
                logger.debug("[DISPLAY_MANAGER] Failed to close display after show failure", exc_info=True)
            try:
                display.deleteLater()
            except Exception:
                logger.debug("[DISPLAY_MANAGER] Failed to delete display after show failure", exc_info=True)
            if startup_generation is not None and startup_generation == self._display_startup_generation:
                self._display_startup_ready_expected.discard(id(display))
                self._emit_display_startup_ready_if_complete(startup_generation)
            return False

    def _mark_display_startup_ready(self, display: DisplayWidget, generation: int) -> None:
        """Record that one display finished generation-scoped startup setup."""

        if generation != self._display_startup_generation:
            logger.debug(
                "[DISPLAY] Ignoring stale startup-ready signal screen=%s generation=%s current=%s",
                getattr(display, "screen_index", "?"),
                generation,
                self._display_startup_generation,
            )
            return
        if display not in self.displays:
            logger.debug(
                "[DISPLAY] Ignoring startup-ready for removed display screen=%s generation=%s",
                getattr(display, "screen_index", "?"),
                generation,
            )
            return

        key = id(display)
        self._display_startup_ready_seen.add(key)
        expected = self._display_startup_ready_expected
        surface_ready = getattr(display, "_render_surface", None) is not None
        compositor_ready = getattr(display, "_gl_compositor", None) is not None
        logger.info(
            "[DISPLAY] Startup display ready screen=%s generation=%s surface_ready=%s compositor_ready=%s ready=%d/%d",
            getattr(display, "screen_index", "?"),
            generation,
            surface_ready,
            compositor_ready,
            len(self._display_startup_ready_seen.intersection(expected)),
            len(expected),
        )

        self._emit_display_startup_ready_if_complete(generation)

    def _emit_display_startup_ready_if_complete(self, generation: int) -> None:
        expected = self._display_startup_ready_expected
        if not expected:
            return
        if self._display_startup_ready_emitted_generation == generation:
            return
        if not expected.issubset(self._display_startup_ready_seen):
            return

        self._display_startup_ready_emitted_generation = generation
        logger.info("[DISPLAY] Startup generation ready for image replay generation=%s", generation)
        self.displays_ready.emit(generation)

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
        
        This enables worker integration for widgets that need process supervision.
        """
        for display in self.displays:
            try:
                display.set_process_supervisor(supervisor)
            except Exception:
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

    def quiesce_all(self) -> None:
        """Suppress late display/widget work before clear/hide/cleanup proceeds."""
        for display in self.displays:
            try:
                display.quiesce_for_runtime_pause()
            except Exception:
                logger.debug("[DISPLAY_MANAGER] Failed to quiesce display before runtime pause", exc_info=True)
        logger.info("All displays quiesced")
    
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

    def set_transition_work_pending(self, pending: bool) -> None:
        """Mark all displays as having accepted image-change work before transition start."""
        self._transition_work_pending = bool(pending)
        try:
            for display in self.displays:
                setter = getattr(display, "set_transition_work_pending", None)
                if callable(setter):
                    setter(pending)
        except Exception as e:
            logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)

    def has_transition_work_pending(self) -> bool:
        """Return True if image-change work is pending or any transition is running."""
        any_display_pending = False
        try:
            for display in self.displays:
                try:
                    has_pending = getattr(display, "has_transition_work_pending", None)
                    if callable(has_pending) and has_pending():
                        any_display_pending = True
                        return True
                except Exception as e:
                    logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
                    continue
        except Exception as e:
            logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
            return False
        if not any_display_pending:
            self._transition_work_pending = False
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
                
                # Pump UI events while waiting (keeps UI responsive)
                from PySide6.QtCore import QCoreApplication
                QCoreApplication.processEvents()
        
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
        self._display_startup_generation += 1
        self._display_startup_ready_expected = set()
        self._display_startup_ready_seen = set()
        self._display_startup_ready_emitted_generation = -1
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
                prequeued = bool(getattr(display, "_pending_reddit_url_prequeued", False))
                if isinstance(url, str) and url and not prequeued:
                    pending_reddit_urls.append(url)
                try:
                    setattr(display, "_pending_reddit_url", None)
                    setattr(display, "_pending_reddit_url_prequeued", False)
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
        """Open any deferred Reddit URLs collected during the last cleanup.

        Build-aware behaviour:
        - **MC builds**: open directly via ``QDesktopServices.openUrl()``.
        - **SCR builds**: URLs were pre-queued to ProgramData at click time.
          This flush acts as a safety-net for any URLs collected during
          cleanup that weren't pre-queued (e.g. edge-case race).
        """
        urls = self.take_deferred_reddit_urls()
        if not urls:
            return

        if ensure_widgets_dismissed:
            try:
                app = QGuiApplication.instance()
                if app is not None:
                    app.processEvents()
            except Exception:
                logger.debug("[REDDIT] processEvents failed before flush", exc_info=True)

        logger.info("[REDDIT] Deferred URL flush started (count=%d)", len(urls))

        from core.mc import is_mc_build
        if is_mc_build():
            for url in urls:
                try:
                    opened = QDesktopServices.openUrl(QUrl(url))
                    if opened:
                        logger.info("[REDDIT] MC flush opened: %s", url)
                        try:
                            from core.windows.browser_window_routing import try_bring_browser_window_to_front
                            if self._thread_manager is None or not hasattr(self._thread_manager, "single_shot"):
                                logger.warning(
                                    "[REDDIT][FALLBACK] MC flush foreground preference skipped: "
                                    "ThreadManager single_shot unavailable"
                                )
                            else:
                                self._thread_manager.single_shot(
                                    800,
                                    lambda target=url: try_bring_browser_window_to_front(
                                        target,
                                        preferred_display_index=0,
                                        fallback_keywords=("reddit",),
                                    ),
                                )
                        except Exception:
                            logger.warning(
                                "[REDDIT][FALLBACK] MC flush foreground preference setup failed",
                                exc_info=True,
                            )
                    else:
                        logger.warning("[REDDIT] MC flush rejected: %s", url)
                except Exception:
                    logger.warning("[REDDIT] MC flush failed: %s", url, exc_info=True)
        else:
            # SCR build: URLs should have been pre-queued at click time.
            # Safety-net: queue any that weren't (collected during cleanup).
            helper_bridge = reddit_helper_bridge
            if helper_bridge is not None and helper_bridge.is_bridge_available():
                for url in urls:
                    try:
                        helper_bridge.enqueue_url(url, source="flush_safety_net")
                        logger.info("[REDDIT] Safety-net queued: %s", url)
                    except Exception:
                        logger.warning("[REDDIT] Safety-net queue failed: %s", url, exc_info=True)
            else:
                logger.warning("[REDDIT] Bridge unavailable; %d URLs will be lost", len(urls))
