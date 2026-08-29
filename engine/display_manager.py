"""
Display manager for multi-monitor support.

Manages DisplayWidget instances across multiple screens.
"""
import time
import weakref
from types import MappingProxyType
from typing import Any, List, Dict, Optional, Set
from PySide6.QtCore import QObject, QSize, Signal, QUrl
from PySide6.QtGui import QGuiApplication, QScreen, QPixmap, QDesktopServices

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.resources.manager import ResourceManager
from rendering.display_modes import DisplayMode
from rendering.display_widget import DisplayWidget
from rendering.quick.display_processing import DisplayProcessingDescriptor
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
    authoritative_first_frames_ready = Signal(int)  # runtime generation
    startup_reveal_completed = Signal(int)  # runtime generation
    transition_completed = Signal(int)  # screen index
    previous_requested = Signal()  # Z key - go to previous image
    next_requested = Signal()  # X key - go to next image
    cycle_transition_requested = Signal()  # C key - cycle transition mode
    settings_requested = Signal()  # S key - open settings
    # The exact DisplayManager identity is a pointer-width Python integer.
    custom_layout_reload_requested = Signal(str, int, object)
    
    def __init__(
        self,
        display_mode: DisplayMode = DisplayMode.FILL,
        same_image_mode: bool = True,
        settings_manager=None,
        resource_manager: ResourceManager | None = None,
        thread_manager=None,
        runtime_generation: int | None = None,
        image_accounting_publisher=None,
    ):
        """
        Initialize display manager.
        
        Args:
            display_mode: Display mode for all screens
            same_image_mode: True = same image on all screens, False = different images
            settings_manager: SettingsManager for widget configuration
        """
        super().__init__()

        self._runtime_generation = (
            int(runtime_generation) if runtime_generation is not None else None
        )
        self._retired = False
        
        self.display_mode = display_mode
        self.same_image_mode = same_image_mode
        self.settings_manager = settings_manager
        self._resource_manager: ResourceManager | None = (
            resource_manager or ResourceManager.get_or_create_app_shared()
        )
        self._thread_manager = thread_manager
        self._process_supervisor = None
        self._image_accounting_publisher_ref = None
        if image_accounting_publisher is not None:
            try:
                self._image_accounting_publisher_ref = weakref.WeakMethod(
                    image_accounting_publisher
                )
            except TypeError:
                try:
                    self._image_accounting_publisher_ref = weakref.ref(
                        image_accounting_publisher
                    )
                except TypeError:
                    self._image_accounting_publisher_ref = None
        self._display_image_accounting_by_id: dict[int, Any] = {}
        self._display_image_accounting_snapshot = MappingProxyType(
            {
                "generation": self._runtime_generation,
                "total_tracked_bytes": 0,
                "resource_count": 0,
                "resources": (),
            }
        )
        self._runtime_signal_connections: list[tuple[str, Any]] = []
        self.displays: List[DisplayWidget] = []
        self.current_images: Dict[int, str] = {}  # screen_index -> image_path
        self._deferred_reddit_urls: list[str] = []
        self._display_startup_generation = 0
        self._display_startup_ready_expected: Set[int] = set()
        self._display_startup_ready_seen: Set[int] = set()
        self._display_startup_ready_emitted_generation: int = -1
        self._authoritative_first_frame_screens: Set[int] = set()
        self._authoritative_first_frame_emitted = False
        self._startup_reveal_screens: Set[int] = set()
        self._startup_reveal_emitted = False
        
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

        self._publish_display_image_accounting()

    def _publish_display_image_accounting(self) -> None:
        """Publish one immutable, display-deduplicated GUI capture."""

        from rendering.image_resource_accounting import (
            aggregate_display_image_accounting,
        )

        self._display_image_accounting_snapshot = aggregate_display_image_accounting(
            self._display_image_accounting_by_id.values(),
            generation=self._runtime_generation,
        )
        publisher_ref = self._image_accounting_publisher_ref
        publisher = publisher_ref() if publisher_ref is not None else None
        if publisher is not None:
            publisher(self._display_image_accounting_snapshot)

    def _record_display_image_accounting(self, display: object, snapshot: Any) -> None:
        if self._retired:
            return
        self._display_image_accounting_by_id[id(display)] = snapshot
        self._publish_display_image_accounting()

    def get_image_accounting_snapshot(self):
        """Return the latest GUI-captured aggregate without touching widgets."""

        return self._display_image_accounting_snapshot

    def track_runtime_signal_connection(
        self,
        signal_name: str,
        callback: Any,
    ) -> None:
        """Record one engine-owned outgoing connection for exact retirement."""

        self._runtime_signal_connections.append((str(signal_name), callback))

    def disconnect_runtime_signal_connections(self) -> None:
        """Disconnect each tracked outgoing route exactly once."""

        connections, self._runtime_signal_connections = (
            self._runtime_signal_connections,
            [],
        )
        for signal_name, callback in reversed(connections):
            signal = getattr(self, signal_name, None)
            disconnect = getattr(signal, "disconnect", None)
            if not callable(disconnect):
                continue
            try:
                disconnect(callback)
            except (RuntimeError, TypeError):
                logger.debug(
                    "[DISPLAY_MANAGER] Runtime signal unavailable during retirement signal=%s",
                    signal_name,
                    exc_info=True,
                )
    
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

        manager_ref = weakref.ref(self)

        def _run() -> None:
            manager = manager_ref()
            if manager is None or manager._retired:
                return
            manager._monitor_reconcile_pending = False
            manager._reconcile_monitor_topology(reason)

        _run._srpss_runtime_generation = self._runtime_generation

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

            manager_ref = weakref.ref(self)
            display_ref = weakref.ref(display)

            def _show_if_current(
                generation: int = startup_generation,
            ) -> None:
                manager = manager_ref()
                disp = display_ref()
                if manager is None or disp is None or manager._retired:
                    return
                if generation != manager._display_startup_generation:
                    logger.debug(
                        "[DISPLAY] Suppressed stale staggered show for screen %s",
                        getattr(disp, "screen_index", "?"),
                    )
                    return
                if disp not in manager.displays:
                    logger.debug(
                        "[DISPLAY] Suppressed staggered show for removed screen %s",
                        getattr(disp, "screen_index", "?"),
                    )
                    return
                manager._show_display_widget(disp, startup_generation=generation)

            _show_if_current._srpss_runtime_generation = self._runtime_generation

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
                runtime_generation=self._runtime_generation,
            )
            display._image_resource_owner = f"display:{screen_index}:manager:{id(self)}"
            display._image_resource_generation = id(self)
            display._runtime_manager_identity = id(self)
            manager_ref = weakref.ref(self)

            def _publish_image_accounting(display_obj, snapshot) -> None:
                manager = manager_ref()
                if manager is not None:
                    manager._record_display_image_accounting(display_obj, snapshot)

            display._image_resource_accounting_publisher = _publish_image_accounting
            refresh_accounting = getattr(display, "refresh_image_resource_accounting", None)
            if callable(refresh_accounting):
                refresh_accounting()
            
            # Connect signals
            display.exit_requested.connect(self._on_exit_requested)
            # FIX: Use default args to capture screen_index by value (not by reference)
            display.image_displayed.connect(
                lambda path, idx=screen_index: self._on_image_displayed(idx, path)
            )
            display.startup_reveal_completed.connect(
                lambda idx=screen_index: self._on_startup_reveal_completed(idx)
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
            if isinstance(display, DisplayWidget):
                display.close()
                display.deleteLater()
            else:
                retire = getattr(display, "retire", None)
                if not callable(retire):
                    raise RuntimeError("display unit has no retirement contract")
                retire()
            logger.info("Removed excess display runtime")
    
    def _on_exit_requested(self) -> None:
        """Handle exit request from any display."""
        logger.info("Exit requested from display widget")
        self.exit_requested.emit()
    
    def _on_image_displayed(self, screen_index: int, image_path: str) -> None:
        """Handle image displayed event."""
        self.current_images[screen_index] = image_path
        self._authoritative_first_frame_screens.add(int(screen_index))
        logger.debug(f"Image displayed on screen {screen_index}: {image_path}")
        expected = {
            int(getattr(display, "screen_index", -1))
            for display in self.displays
        }
        if (
            not self._authoritative_first_frame_emitted
            and expected
            and expected.issubset(self._authoritative_first_frame_screens)
        ):
            self._authoritative_first_frame_emitted = True
            self.authoritative_first_frames_ready.emit(
                int(self._runtime_generation or 0)
            )

    def _on_startup_reveal_completed(self, screen_index: int) -> None:
        """Publish once after every display's existing FadeCoordinator completes."""

        self._startup_reveal_screens.add(int(screen_index))
        expected = {
            int(getattr(display, "screen_index", -1))
            for display in self.displays
        }
        if (
            self._startup_reveal_emitted
            or not expected
            or not expected.issubset(self._startup_reveal_screens)
        ):
            return
        self._startup_reveal_emitted = True
        self.startup_reveal_completed.emit(int(self._runtime_generation or 0))
    
    def set_process_supervisor(self, supervisor) -> None:
        """Retain the process owner used by admitted generation services."""

        self._process_supervisor = supervisor
        for display in self.displays:
            if not isinstance(display, DisplayWidget):
                continue
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
            display = self._display_for_screen_index(screen_index)
            if display is None:
                logger.warning(f"[FALLBACK] Invalid screen index: {screen_index}")
            elif isinstance(display, DisplayWidget):
                display.set_image(pixmap, image_path)
            else:
                presenter = getattr(display, "present_image", None)
                if not callable(presenter):
                    raise TypeError("display unit has no image publication contract")
                presenter(pixmap, image_path=image_path)
                self._on_image_displayed(int(screen_index), image_path)
        else:
            # Show on all screens (same image mode)
            if self.same_image_mode:
                for display in self.displays:
                    if isinstance(display, DisplayWidget):
                        display.set_image(pixmap, image_path)
                        continue
                    presenter = getattr(display, "present_image", None)
                    if not callable(presenter):
                        raise TypeError("display unit has no image publication contract")
                    presenter(pixmap, image_path=image_path)
                    self._on_image_displayed(
                        int(getattr(display, "screen_index")),
                        image_path,
                    )
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

    def _display_for_screen_index(self, screen_index: int) -> object | None:
        for position, display in enumerate(self.displays):
            if int(getattr(display, "screen_index", position)) == int(screen_index):
                return display
        return None

    def present_processed_image(
        self,
        screen_index: int,
        processed_pixmap: QPixmap,
        original_pixmap: QPixmap,
        image_path: str,
    ) -> None:
        """Publish one GUI-materialized image through the selected display unit."""

        display = self._display_for_screen_index(screen_index)
        if display is None:
            raise IndexError(f"no selected display for screen index {screen_index}")
        if isinstance(display, DisplayWidget):
            display.set_processed_image(processed_pixmap, original_pixmap, image_path)
            return
        presenter = getattr(display, "present_image", None)
        if not callable(presenter):
            raise TypeError("display unit has no processed-image publication contract")
        presenter(processed_pixmap, image_path=image_path)
        self._on_image_displayed(int(screen_index), image_path)
    
    def show_error(self, message: str, screen_index: Optional[int] = None) -> None:
        """
        Show error message on display(s).
        
        Args:
            message: Error message
            screen_index: Specific screen, or None for all screens
        """
        if screen_index is not None:
            display = self._display_for_screen_index(screen_index)
            if isinstance(display, DisplayWidget):
                display.show_error(message)
            elif display is not None:
                logger.error(
                    "[DISPLAY] Runtime error for screen %s: %s",
                    screen_index,
                    message,
                )
        else:
            for display in self.displays:
                if isinstance(display, DisplayWidget):
                    display.show_error(message)
                    continue
                logger.error(
                    "[DISPLAY] Runtime error for screen %s: %s",
                    getattr(display, "screen_index", "?"),
                    message,
                )
    
    def clear_all(self) -> None:
        """Clear all displays (removes image but keeps windows visible)."""
        for display in self.displays:
            display.clear()
        self.current_images.clear()
        logger.info("All displays cleared")

    def quiesce_all(self) -> None:
        """Suppress late display/widget work before clear/hide/cleanup proceeds."""
        for display in self.displays:
            quiesce = getattr(display, "quiesce", None)
            if callable(quiesce):
                quiesce()
                continue
            legacy_quiesce = getattr(display, "quiesce_for_runtime_pause", None)
            if not callable(legacy_quiesce):
                raise RuntimeError("display collection member has no quiesce contract")
            legacy_quiesce()
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
            display.show_on_screen()
            if isinstance(display, DisplayWidget):
                hide_all_overlays(display)
        logger.info("All displays shown")
    
    def set_display_mode(self, mode: DisplayMode) -> None:
        """
        Change display mode for all screens.
        
        Args:
            mode: New display mode
        """
        self.display_mode = mode
        for display in self.displays:
            if isinstance(display, DisplayWidget):
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
                if not isinstance(display, DisplayWidget):
                    display.runtime.auxiliary_controller.set_dimming(enabled, opacity)
                    continue
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

    def snapshot_processing_descriptors(
        self,
    ) -> tuple[DisplayProcessingDescriptor, ...]:
        """Return immutable per-display inputs without exposing presenter objects.

        During the H conversion the collection still contains ``DisplayWidget``
        instances. The final Quick collection exposes the same semantic snapshot
        directly from ``QuickDisplayUnit``. Engine consumers see only this
        contract; neither presenter is emulated by the other.
        """

        targets: list[DisplayProcessingDescriptor] = []
        for index, display in enumerate(self.displays):
            snapshot = getattr(display, "processing_descriptor", None)
            if callable(snapshot):
                target = snapshot(self.display_mode)
                if not isinstance(target, DisplayProcessingDescriptor):
                    raise TypeError(
                        "display unit returned an invalid processing-target snapshot"
                    )
                targets.append(target)
                continue

            if not isinstance(display, DisplayWidget):
                raise TypeError(
                    "display collection member has no processing-target contract"
                )
            pixel_size = display.get_target_size()
            dpr = float(getattr(display, "_device_pixel_ratio", 1.0))
            if dpr <= 0.0:
                raise ValueError("legacy display reported a non-positive DPR")
            targets.append(
                DisplayProcessingDescriptor(
                    screen_index=int(getattr(display, "screen_index", index)),
                    target_size=QSize(pixel_size),
                    logical_size=QSize(int(display.width()), int(display.height())),
                    display_mode=self.display_mode,
                    device_pixel_ratio=dpr,
                )
            )
        return tuple(targets)

    def has_presented_image(self) -> bool:
        """Return whether any selected display has accepted current image state."""

        if self.current_images:
            return True
        for display in self.displays:
            if isinstance(display, DisplayWidget):
                if bool(getattr(display, "current_image_path", None)):
                    return True
                continue
            runtime = getattr(display, "runtime", None)
            scene = getattr(runtime, "scene_controller", None)
            if scene is not None and getattr(scene, "presentation_image", None) is not None:
                return True
        return False

    def wake_media_runtime(self) -> int:
        """Wake every owned neutral Media runtime service from idle."""

        awakened = 0
        for display in self.displays:
            if isinstance(display, DisplayWidget):
                runtime_manager = getattr(display, "_widget_runtime_manager", None)
            else:
                runtime = getattr(display, "runtime", None)
                runtime_manager = getattr(runtime, "widget_runtime_manager", None)
            service_getter = getattr(runtime_manager, "get_widget_service", None)
            service = service_getter("media") if callable(service_getter) else None
            wake = getattr(service, "wake_from_idle", None)
            if callable(wake):
                wake()
                awakened += 1
        return awakened

    def describe_display_states(self) -> tuple[dict[str, Any], ...]:
        """Return bounded runtime diagnostics without exposing display owners."""

        states: list[dict[str, Any]] = []
        for display in self.displays:
            describe = getattr(display, "describe_runtime_state", None)
            if callable(describe):
                state = describe()
            else:
                runtime = getattr(display, "runtime", None)
                runtime_describe = getattr(runtime, "describe_runtime_state", None)
                state = runtime_describe() if callable(runtime_describe) else None
            if isinstance(state, dict):
                states.append(state)
        return tuple(states)

    def collect_runtime_retirement_roots(
        self,
    ) -> tuple[list[QObject], list[object]]:
        """Collect exact generation roots for the replacement barrier.

        Destination display units publish their own root topology. The
        temporary legacy branch remains centralized here until the QWidget
        presenter is caller-dead and deleted; no engine/lifecycle caller needs
        to know either concrete display shape.
        """

        qobjects: list[QObject] = []
        python_owners: list[object] = []

        def _append_unique(values: list[object], candidate: object | None) -> None:
            if candidate is None:
                return
            candidate_id = id(candidate)
            if any(id(value) == candidate_id for value in values):
                return
            values.append(candidate)

        def _append_qobject_tree(candidate: object | None) -> None:
            if not isinstance(candidate, QObject):
                return
            _append_unique(qobjects, candidate)
            try:
                for child in candidate.findChildren(QObject):
                    _append_unique(qobjects, child)
            except (RuntimeError, TypeError):
                logger.debug(
                    "[LIFECYCLE_BARRIER] Could not enumerate children for %s",
                    type(candidate).__name__,
                    exc_info=True,
                )

        _append_qobject_tree(self)
        for display in self.displays:
            roots = getattr(display, "runtime_retirement_roots", None)
            if callable(roots):
                display_qobjects, display_python_owners = roots()
                for root in display_qobjects:
                    _append_qobject_tree(root)
                for owner in display_python_owners:
                    _append_unique(python_owners, owner)
                continue

            # Current physical-host roots. Delete this branch with the retired
            # QWidget presenter after the Quick production route is proven.
            _append_qobject_tree(display)
            for attr_name in (
                "_gl_compositor",
                "_compositor",
                "_spotify_bars_overlay",
                "spotify_visualizer_widget",
                "media_widget",
                "_ctrl_cursor_hint",
                "_input_handler",
                "_transition_controller",
                "_image_presenter",
            ):
                _append_qobject_tree(getattr(display, attr_name, None))

            for attr_name in (
                "_widget_manager",
                "_custom_layout_manager",
                "_transition_factory",
                "_pixel_shift_manager",
            ):
                _append_unique(python_owners, getattr(display, attr_name, None))

            widget_manager = getattr(display, "_widget_manager", None)
            if widget_manager is not None:
                for attr_name in ("_fade_coordinator", "_factory_registry"):
                    _append_unique(
                        python_owners,
                        getattr(widget_manager, attr_name, None),
                    )

            custom_manager = getattr(display, "_custom_layout_manager", None)
            if custom_manager is not None:
                _append_qobject_tree(getattr(custom_manager, "_grid_overlay", None))
                for state in list(
                    getattr(custom_manager, "_shell_states", {}).values()
                ):
                    _append_qobject_tree(getattr(state, "shell", None))
                    _append_qobject_tree(getattr(state, "widget", None))

            compositor = getattr(display, "_gl_compositor", None)
            if compositor is not None:
                for attr_name in (
                    "_deferred_warmup_context",
                    "_deferred_warmup_surface",
                ):
                    _append_qobject_tree(getattr(compositor, attr_name, None))
                for attr_name in ("_render_strategy_manager", "_transition_renderer"):
                    _append_unique(
                        python_owners,
                        getattr(compositor, attr_name, None),
                    )
                strategy_manager = getattr(
                    compositor,
                    "_render_strategy_manager",
                    None,
                )
                if strategy_manager is not None:
                    _append_unique(
                        python_owners,
                        getattr(strategy_manager, "_timer", None),
                    )

        return qobjects, python_owners
    
    def get_screen_count(self) -> int:
        """Get number of detected screens."""
        return len(QGuiApplication.screens())
    
    def get_display_info(self) -> List[dict]:
        """
        Get information about all displays.
        
        Returns:
            List of display info dicts
        """
        result: list[dict] = []
        for display in self.displays:
            if isinstance(display, DisplayWidget):
                result.append(display.get_screen_info())
                continue
            runtime = getattr(display, "runtime", None)
            identity = getattr(runtime, "display_identity", None)
            as_dict = getattr(identity, "as_dict", None)
            if callable(as_dict):
                result.append(as_dict())
        return result
    
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

    def set_transition_work_pending(
        self,
        pending: bool,
        *,
        screen_index: int | None = None,
    ) -> None:
        """Mark all displays as having accepted image-change work before transition start."""
        self._transition_work_pending = bool(pending)
        displays = (
            self.displays
            if screen_index is None
            else [self._display_for_screen_index(screen_index)]
        )
        for display in displays:
            if not isinstance(display, DisplayWidget):
                continue
            setter = getattr(display, "set_transition_work_pending", None)
            if callable(setter):
                setter(pending)

    def has_transition_work_pending(self) -> bool:
        """Return True if image-change work is pending or any transition is running."""
        if self._transition_work_pending:
            return True
        try:
            for display in self.displays:
                try:
                    has_pending = getattr(display, "has_transition_work_pending", None)
                    if callable(has_pending) and has_pending():
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
                
                # Do not pump arbitrary Qt events here; synchronized transition
                # readiness must not become a UI-pressure escape hatch.
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
            if isinstance(display, DisplayWidget):
                display.set_image(pixmap, image_path)
                continue
            display.present_image(pixmap, image_path=image_path)
            self._on_image_displayed(
                int(getattr(display, "screen_index")),
                image_path,
            )
        
        # Wait for all to be ready (with timeout)
        all_ready = self.wait_for_all_displays_ready(timeout_sec=1.0)
        
        if not all_ready:
            logger.warning("[SYNC] Not all displays ready, transitions may desync")
        else:
            logger.debug("[SYNC] Synchronized transition started successfully")
    
    def cleanup(self) -> None:
        """Synchronously destroy every display runtime and its GL resources."""
        self._display_startup_generation += 1
        self._display_startup_ready_expected = set()
        self._display_startup_ready_seen = set()
        self._display_startup_ready_emitted_generation = -1
        self._authoritative_first_frame_screens.clear()
        self._authoritative_first_frame_emitted = False
        self._startup_reveal_screens.clear()
        self._startup_reveal_emitted = False
        count = len(self.displays)
        logger.info("Cleaning up %d display widgets", count)

        try:
            from rendering.display_widget import DisplayWidget
            from PySide6.QtGui import QGuiApplication

            owner = DisplayWidget._event_filter_owner
            if owner is not None:
                app = QGuiApplication.instance()
                if app is not None:
                    app.removeEventFilter(owner)

            DisplayWidget._global_ctrl_held = False
            DisplayWidget._halo_owner = None
            DisplayWidget._event_filter_installed = False
            DisplayWidget._event_filter_owner = None
            DisplayWidget._focus_owner = None
            DisplayWidget._instances_by_screen.clear()
            logger.debug("[CLEANUP] Reset all DisplayWidget global state")
        except Exception as exc:
            logger.debug("[DISPLAY_MANAGER] Global state reset failed: %s", exc)

        pending_reddit_urls: list[str] = []
        failed_displays = []
        cleanup_errors: list[str] = []

        for idx, display in enumerate(list(self.displays)):
            screen_index = getattr(display, "screen_index", idx)
            logger.debug(
                "Cleaning up display widget (index=%d/%d, screen_index=%s)",
                idx,
                count,
                screen_index,
            )

            url = getattr(display, "_pending_reddit_url", None)
            prequeued = bool(getattr(display, "_pending_reddit_url_prequeued", False))
            if isinstance(url, str) and url and not prequeued:
                pending_reddit_urls.append(url)
            setattr(display, "_pending_reddit_url", None)
            setattr(display, "_pending_reddit_url_prequeued", False)

            try:
                if is_perf_metrics_enabled():
                    logger.info(
                        "[PERF][DISPLAY_MANAGER] cleanup_display screen=%s state=%s",
                        screen_index,
                        display.describe_runtime_state(),
                    )
                display.quiesce_for_runtime_pause()
                display.clear()
                cleanup_runtime = getattr(display, "cleanup_runtime", None)
                if not callable(cleanup_runtime):
                    raise RuntimeError("DisplayWidget has no cleanup_runtime() contract")
                cleanup_runtime("display_manager_cleanup")
                display.close()
                display._image_resource_accounting_publisher = None
                self._display_image_accounting_by_id.pop(id(display), None)
                display.deleteLater()
            except Exception as exc:
                failed_displays.append(display)
                cleanup_errors.append(
                    f"screen={screen_index} type={type(exc).__name__} error={exc}"
                )
                logger.error(
                    "Display runtime cleanup failed (index=%d, screen_index=%s): %s",
                    idx,
                    screen_index,
                    exc,
                    exc_info=True,
                )

        self._deferred_reddit_urls = pending_reddit_urls
        self._publish_display_image_accounting()
        if cleanup_errors:
            # Retain failed objects so a caller can inspect or retry; clearing the
            # list here would falsely declare ownership released.
            self.displays = failed_displays
            raise RuntimeError(
                "Display runtime cleanup incomplete: " + " | ".join(cleanup_errors)
            )

        self.displays.clear()
        self.current_images.clear()
        logger.info("Display manager cleanup complete")

    def retire_runtime(self) -> None:
        """Detach process-level routes and queue this retired manager for deletion.

        ``cleanup()`` remains reusable by ``initialize_displays()``.  This
        terminal method is intentionally separate and is called only when the
        engine is replacing or shutting down the entire runtime generation.
        """

        if self._retired:
            return
        self._retired = True
        self.disconnect_monitor_detection()
        self.disconnect_runtime_signal_connections()
        self._display_startup_generation += 1
        self._display_startup_ready_expected.clear()
        self._display_startup_ready_seen.clear()
        self._monitor_reconcile_pending = False
        self._transition_work_pending = False
        self._transition_ready_queue = None
        self._display_image_accounting_by_id.clear()
        self._publish_display_image_accounting()
        self._image_accounting_publisher_ref = None

        self.settings_manager = None
        self._thread_manager = None
        self._resource_manager = None
        self.deleteLater()

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
            logger.debug("[REDDIT] Deferred flush requested after widget dismissal; no UI event pump required")

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
