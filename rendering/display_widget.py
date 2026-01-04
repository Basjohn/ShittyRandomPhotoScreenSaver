"""Display widget for OpenGL/software rendered screensaver overlays."""
from collections import defaultdict
from typing import Optional, Iterable, Tuple, Callable, Dict, Any, List, Set
import logging
import time
import weakref
import sys
import ctypes
from ctypes import wintypes
try:
    from OpenGL import GL  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    GL = None
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import (
    QPoint,
    QTimer,
    Qt,
    Signal,
    QSize,
    QEvent,
)
from PySide6.QtGui import (
    QPixmap,
    QPainter,
    QKeyEvent,
    QCloseEvent,
    QMouseEvent,
    QPaintEvent,
    QFont,
    QResizeEvent,
    QCursor,
    QFocusEvent,
    QGuiApplication,
    QWheelEvent,
)
from shiboken6 import Shiboken
from rendering.display_modes import DisplayMode
from rendering.image_processor import ImageProcessor
from rendering.gl_compositor import GLCompositorWidget
from transitions.base_transition import BaseTransition
from rendering.transition_factory import TransitionFactory
from widgets.clock_widget import ClockWidget
from widgets.weather_widget import WeatherWidget
from widgets.media_widget import MediaWidget
from widgets.reddit_widget import RedditWidget
from widgets.pixel_shift_manager import PixelShiftManager
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
from widgets.spotify_volume_widget import SpotifyVolumeWidget
from widgets.context_menu import ScreensaverContextMenu
from widgets.cursor_halo import CursorHaloWidget
from rendering.widget_manager import WidgetManager
from rendering.input_handler import InputHandler
from rendering.transition_controller import TransitionController
from rendering.image_presenter import ImagePresenter
from rendering.multi_monitor_coordinator import get_coordinator, MultiMonitorCoordinator
from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from core.logging.overlay_telemetry import record_overlay_ready
from core.resources.manager import ResourceManager
from core.settings.settings_manager import SettingsManager
from core.threading.manager import ThreadManager
from transitions.overlay_manager import (
    hide_all_overlays,
    any_overlay_ready_for_display,
    any_gl_overlay_visible,
    show_backend_fallback_overlay,
    hide_backend_fallback_overlay,
    set_overlay_geometry,
    raise_overlay,
    schedule_raise_when_ready,
    GL_OVERLAY_KEYS,
    SW_OVERLAY_KEYS,
)
from core.events import EventSystem
from rendering.backends import BackendSelectionResult, create_backend_from_settings
from rendering.backends.base import RendererBackend, RenderSurface, SurfaceDescriptor

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


TRANSITION_WATCHDOG_DEFAULT_SEC = 18.0
_FULLSCREEN_COMPAT_WORKAROUND = True


def _describe_pixmap(pm: Optional[QPixmap]) -> str:
    if pm is None:
        return "None"
    try:
        if pm.isNull():
            return "NullPixmap"
        size = pm.size()
        return (
            f"Pixmap(id={id(pm):#x}, cacheKey={pm.cacheKey():#x}, "
            f"size={size.width()}x{size.height()}, dpr={pm.devicePixelRatio():.2f}, depth={pm.depth()})"
        )
    except Exception:
        return "Pixmap(?)"


# Toggle for MC window style experiments. Leave False to use the historical
# Qt.Tool behavior; switch to True when testing the splash-style flag.
MC_USE_SPLASH_FLAGS = False

# Windows-specific constants for diagnostics and input handling
WM_APPCOMMAND = 0x0319

_APPCOMMAND_NAMES = {
    0x0005: "APPCOMMAND_MEDIA_NEXTTRACK",
    0x0006: "APPCOMMAND_MEDIA_PREVIOUSTRACK",
    0x0007: "APPCOMMAND_MEDIA_STOP",
    0x000E: "APPCOMMAND_MEDIA_PLAY_PAUSE",
    0x0008: "APPCOMMAND_MEDIA_PLAY",
    0x0009: "APPCOMMAND_MEDIA_PAUSE",
    0x000A: "APPCOMMAND_MEDIA_RECORD",
    0x000B: "APPCOMMAND_MEDIA_FAST_FORWARD",
    0x000C: "APPCOMMAND_MEDIA_REWIND",
    0x000D: "APPCOMMAND_MEDIA_CHANNEL_UP",
    0x0011: "APPCOMMAND_VOLUME_MUTE",
    0x0000: "APPCOMMAND_BROWSER_BACKWARD",  # included for completeness
    0x0001: "APPCOMMAND_BROWSER_FORWARD",
    0x0002: "APPCOMMAND_BROWSER_REFRESH",
    0x0003: "APPCOMMAND_BROWSER_STOP",
    0x0004: "APPCOMMAND_BROWSER_SEARCH",
    0x000F: "APPCOMMAND_MEDIA_CHANNEL_DOWN",
    0x0010: "APPCOMMAND_VOLUME_DOWN",
    0x0012: "APPCOMMAND_VOLUME_UP",
}

if sys.platform == "win32":
    try:
        _USER32 = ctypes.windll.user32
    except Exception:
        _USER32 = None
else:
    _USER32 = None


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
    - previous_requested: Emitted when user wants to go to previous image
    - next_requested: Emitted when user wants to go to next image
    - cycle_transition_requested: Emitted when user wants to cycle transitions
    - settings_requested: Emitted when user wants to open settings
    """
    
    exit_requested = Signal()
    image_displayed = Signal(str)  # image path
    previous_requested = Signal()  # Z key - go to previous image
    next_requested = Signal()  # X key - go to next image
    cycle_transition_requested = Signal()  # C key - cycle transition mode
    settings_requested = Signal()  # S key - open settings
    dimming_changed = Signal(bool, float)  # enabled, opacity - sync dimming across displays
    
    # Phase 5: Class-level state has been migrated to MultiMonitorCoordinator.
    # The following are kept as deprecated fallbacks for any external code that
    # may still reference them. New code should use get_coordinator() instead.
    # These will be removed in a future version.
    _global_ctrl_held: bool = False  # DEPRECATED: Use get_coordinator().ctrl_held
    _halo_owner: Optional["DisplayWidget"] = None  # DEPRECATED: Use get_coordinator().halo_owner
    _event_filter_installed: bool = False  # DEPRECATED: Use get_coordinator().event_filter_installed
    _event_filter_owner: Optional["DisplayWidget"] = None  # DEPRECATED
    _instances_by_screen: Dict[Any, "DisplayWidget"] = {}  # DEPRECATED: Use get_coordinator().get_all_instances()
    _focus_owner: Optional["DisplayWidget"] = None  # DEPRECATED: Use get_coordinator().focus_owner
    
    @classmethod
    def get_all_instances(cls) -> List["DisplayWidget"]:
        """Get all DisplayWidget instances.
        
        Phase 5: Delegates to MultiMonitorCoordinator for centralized instance tracking.
        Returns a copy of the values to avoid modification during iteration.
        """
        return get_coordinator().get_all_instances()

    def __init__(
        self,
        screen_index: int = 0,
        display_mode: DisplayMode = DisplayMode.FILL,
        settings_manager=None,
        parent: Optional[QWidget] = None,
        resource_manager: Optional[ResourceManager] = None,
        thread_manager=None,
    ):
        """
        Initialize display widget.
        
        Args:
            screen_index: Index of screen to display on
            display_mode: Image display mode
            settings_manager: SettingsManager instance for widget configuration
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.screen_index = screen_index
        self.display_mode = display_mode
        self.settings_manager = settings_manager
        self.current_pixmap: Optional[QPixmap] = None
        self.current_image_path: Optional[str] = None
        self.previous_pixmap: Optional[QPixmap] = None
        self.error_message: Optional[str] = None
        self.clock_widget: Optional[ClockWidget] = None
        self.clock2_widget: Optional[ClockWidget] = None
        self.clock3_widget: Optional[ClockWidget] = None
        self.weather_widget: Optional[WeatherWidget] = None
        self.media_widget: Optional[MediaWidget] = None
        self.spotify_visualizer_widget: Optional[SpotifyVisualizerWidget] = None
        self.spotify_volume_widget: Optional[SpotifyVolumeWidget] = None
        self._spotify_bars_overlay: Optional[SpotifyBarsGLOverlay] = None
        self.reddit_widget: Optional[RedditWidget] = None
        self.reddit2_widget: Optional[RedditWidget] = None
        self._pixel_shift_manager: Optional[PixelShiftManager] = None
        self._current_transition: Optional[BaseTransition] = None
        self._current_transition_overlay_key: Optional[str] = None
        self._current_transition_started_at: float = 0.0
        self._current_transition_name: Optional[str] = None
        self._current_transition_first_run: bool = False
        self._warmed_transition_types: Set[str] = set()
        self._prewarmed_transition_types: Set[str] = set()
        self._last_transition_name: Optional[str] = None
        self._last_transition_finished_wall_ts: float = 0.0
        self._screen = None  # Store screen reference for DPI
        self._device_pixel_ratio = 1.0  # DPI scaling factor
        self._initial_mouse_pos = None  # Track mouse movement for exit
        self._mouse_move_threshold = 10  # Pixels of movement before exit
        self._target_fps = 60  # Target FPS derived from screen refresh rate
        self._pre_raise_log_emitted = False
        self._base_fallback_paint_logged = False
        self._seed_pixmap: Optional[QPixmap] = None
        self._last_pixmap_seed_ts: Optional[float] = None
        self._last_overlay_ready_ts: Optional[float] = None
        self._overlay_swap_warned: set[str] = set()
        self._updates_blocked_until_seed = False
        self._overlay_stage_counts: defaultdict[str, int] = defaultdict(int)
        self._overlay_timeouts: dict[str, float] = {}
        self._transitions_enabled: bool = True
        self._ctrl_held: bool = False
        self._ctrl_cursor_hint: Optional[CursorHaloWidget] = None
        self._last_halo_activity_ts: float = 0.0
        self._halo_last_local_pos: Optional[QPoint] = None
        self._halo_activity_timeout: float = 2.0
        self._exiting: bool = False
        self._focus_loss_logged: bool = False
        self._transition_watchdog: Optional[QTimer] = None
        self._transition_watchdog_resource_id: Optional[str] = None
        self._transition_watchdog_overlay_key: Optional[str] = None
        self._transition_watchdog_transition: Optional[str] = None
        self._transition_watchdog_started_at: float = 0.0
        self._pending_transition_finish_args: Optional[Tuple[QPixmap, QPixmap, str, bool, Optional[QPixmap]]] = None
        self._transition_skip_count: int = 0
        self._overlay_fade_expected: set[str] = set()
        self._overlay_fade_pending: Dict[str, Callable[[], None]] = {}
        self._overlay_fade_started: bool = False
        self._overlay_fade_timeout: Optional[QTimer] = None
        self._reddit_exit_on_click: bool = True
        self._pending_reddit_url: Optional[str] = None  # URL to open once saver exits
        self._pending_activation_refresh: bool = False
        self._last_deactivate_ts: float = 0.0
        
        # Context menu for right-click actions
        self._context_menu: Optional[ScreensaverContextMenu] = None
        self._context_menu_active: bool = False
        self._context_menu_prewarmed: bool = False
        self._pending_effect_invalidation: bool = False

        # Central ResourceManager wiring
        self._resource_manager: Optional[ResourceManager] = resource_manager
        if self._resource_manager is None:
            try:
                self._resource_manager = ResourceManager()
            except Exception:
                self._resource_manager = None
        # Central ThreadManager wiring (optional, provided by engine)
        self._thread_manager = thread_manager
        
        # WidgetManager for centralized overlay widget lifecycle (Phase E refactor)
        self._widget_manager: Optional[WidgetManager] = None
        try:
            self._widget_manager = WidgetManager(self, self._resource_manager)
        except Exception:
            logger.debug("[DISPLAY_WIDGET] Failed to create WidgetManager", exc_info=True)
        
        # InputHandler for centralized input event handling (Phase E refactor)
        self._input_handler: Optional[InputHandler] = None
        try:
            self._input_handler = InputHandler(
                self, self.settings_manager, self._widget_manager
            )
            # Connect InputHandler signals to DisplayWidget signals/handlers
            self._input_handler.exit_requested.connect(self._on_input_exit_requested)
            self._input_handler.settings_requested.connect(self.settings_requested)
            self._input_handler.next_image_requested.connect(self.next_requested)
            self._input_handler.previous_image_requested.connect(self.previous_requested)
            self._input_handler.cycle_transition_requested.connect(self.cycle_transition_requested)
            self._input_handler.context_menu_requested.connect(self._on_context_menu_requested)
        except Exception:
            logger.debug("[DISPLAY_WIDGET] Failed to create InputHandler", exc_info=True)
        
        # TransitionController for centralized transition lifecycle (Phase 3 refactor)
        self._transition_controller: Optional[TransitionController] = None
        try:
            self._transition_controller = TransitionController(
                self, self._resource_manager, self._widget_manager
            )
        except Exception:
            logger.debug("[DISPLAY_WIDGET] Failed to create TransitionController", exc_info=True)
        
        # ImagePresenter for centralized pixmap lifecycle (Phase 4 refactor)
        self._image_presenter: Optional[ImagePresenter] = None
        try:
            self._image_presenter = ImagePresenter(self, display_mode, 1.0)
        except Exception:
            logger.debug("[DISPLAY_WIDGET] Failed to create ImagePresenter", exc_info=True)
        
        # MultiMonitorCoordinator for centralized cross-display state (Phase 5 refactor)
        self._coordinator: MultiMonitorCoordinator = get_coordinator()

        # Best-effort screen binding for tests/dev windows that call `show()`
        # directly instead of `show_on_screen()`. This allows Ctrl-halo logic
        # (and MultiMonitorCoordinator registration) to function in unit tests.
        if self._screen is None:
            try:
                screens = QGuiApplication.screens()
                if 0 <= int(screen_index) < len(screens):
                    self._screen = screens[int(screen_index)]
                elif screens:
                    self._screen = QGuiApplication.primaryScreen()
            except Exception:
                pass

        # Setup widget: frameless, always-on-top display window. For the MC
        # build (SRPSS_MC), also mark the window as a tool window so it does
        # not appear in the taskbar or standard Alt+Tab.
        self._mc_window_flag_mode: Optional[str] = None

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        try:
            exe0 = str(getattr(sys, "argv", [""])[0]).lower()
            if (
                "srpss_mc" in exe0
                or "srpss mc" in exe0
                or "srpss_media_center" in exe0
                or "srpss media center" in exe0
                or "main_mc.py" in exe0
            ):
                if MC_USE_SPLASH_FLAGS:
                    flags |= Qt.WindowType.SplashScreen
                    self._mc_window_flag_mode = "splash"
                else:
                    flags |= Qt.WindowType.Tool
                    self._mc_window_flag_mode = "tool"
        except Exception:
            pass

        self.setWindowFlags(flags)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setMouseTracking(True)
        # Phase 5: Use MultiMonitorCoordinator for focus ownership
        try:
            if self._coordinator.claim_focus(self):
                self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                try:
                    self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, False)
                except Exception:
                    pass
                try:
                    self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
                except Exception:
                    pass
            else:
                self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                try:
                    self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
                except Exception:
                    pass
                try:
                    self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
                except Exception:
                    pass
        except Exception:
            pass
        # Ensure we can keep the Ctrl halo moving even when the cursor is over
        # child widgets (clocks, weather, etc.) by observing global mouse
        # move events.
        # PERF: Only install ONE eventFilter across all DisplayWidgets to avoid
        # redundant processing of every mouse event by multiple filters.
        # Phase 5: Use MultiMonitorCoordinator for event filter management
        try:
            app = QGuiApplication.instance()
            if app is not None and self._coordinator.install_event_filter(self):
                app.installEventFilter(self)
        except Exception:
            pass
        
        # Set black background
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.GlobalColor.black)
        self.setPalette(palette)
        
        # Phase 5: Register with MultiMonitorCoordinator instead of class-level cache
        if self._screen is not None:
            self._coordinator.register_instance(self, self._screen)
        
        logger.info(f"DisplayWidget created for screen {screen_index} ({display_mode})")

        # Initialize renderer backend using new backend factory
        self._renderer_backend: Optional[RendererBackend] = None
        self._render_surface: Optional[RenderSurface] = None
        self._backend_selection: Optional[BackendSelectionResult] = None
        self._backend_fallback_message: Optional[str] = None
        self._has_rendered_first_frame = False
        self._gl_compositor: Optional[GLCompositorWidget] = None
        self._init_renderer_backend()
        
        # Initialize transition factory (delegates transition creation logic)
        self._transition_factory: Optional[TransitionFactory] = None
        if self.settings_manager:
            self._transition_factory = TransitionFactory(
                settings_manager=self.settings_manager,
                resource_manager=self._resource_manager,
                compositor_checker=self._has_gl_compositor,
                compositor_ensurer=self._ensure_gl_compositor,
            )

        # Ensure transitions are cleaned up if the widget is destroyed
        try:
            self.destroyed.connect(self._on_destroyed)
        except Exception:
            pass
    
    def show_on_screen(self) -> None:
        """Show widget fullscreen on assigned screen."""
        screens = QGuiApplication.screens()
        
        if self.screen_index >= len(screens):
            logger.warning(f"[FALLBACK] Screen {self.screen_index} not found, using primary")
            screen = QGuiApplication.primaryScreen()
        else:
            screen = screens[self.screen_index]
        
        # Store screen reference and DPI ratio for high-quality rendering
        self._screen = screen
        self._device_pixel_ratio = screen.devicePixelRatio()
        
        screen_geom = screen.geometry()
        geom = screen_geom
        if _FULLSCREEN_COMPAT_WORKAROUND:
            try:
                if geom.height() > 1:
                    geom.setHeight(geom.height() - 1)
            except Exception:
                pass

        logger.info(
            f"Showing on screen {self.screen_index}: "
            f"{screen_geom.width()}x{screen_geom.height()} at ({screen_geom.x()}, {screen_geom.y()}) "
            f"DPR={self._device_pixel_ratio}"
        )

        # Borderless fullscreen: frameless, always-on-top window sized to the
        # target screen. Avoid exclusive fullscreen mode to reduce compositor
        # and driver-induced flicker on modern Windows.
        self.setGeometry(geom)
        # Seed with a placeholder snapshot of the current screen to avoid a hard
        # wallpaper->black flash while GL prewarm runs. If this fails, fall back
        # to blocking updates until the first real image is seeded.
        placeholder_set = False
        try:
            wallpaper_pm = screen.grabWindow(0)
            if wallpaper_pm is not None and not wallpaper_pm.isNull():
                try:
                    wallpaper_pm.setDevicePixelRatio(self._device_pixel_ratio)
                except Exception:
                    pass
                self.current_pixmap = wallpaper_pm
                self.previous_pixmap = wallpaper_pm
                self._seed_pixmap = wallpaper_pm
                self._last_pixmap_seed_ts = time.monotonic()
                placeholder_set = True
        except Exception:
            placeholder_set = False

        if placeholder_set:
            try:
                self.setUpdatesEnabled(True)
            except Exception:
                pass
            self._updates_blocked_until_seed = False
        else:
            try:
                self.setUpdatesEnabled(False)
                self._updates_blocked_until_seed = True
            except Exception:
                self._updates_blocked_until_seed = False

        # Determine hardware acceleration setting once for startup behaviour.
        # IMPORTANT: We no longer run GL prewarm at startup; GL overlays are
        # initialized lazily by per-transition prepaint. This avoids any
        # startup interaction with GL contexts that could cause black flashes.
        hw_accel = True
        if self.settings_manager is not None:
            try:
                raw = self.settings_manager.get('display.hw_accel', True)
            except Exception:
                raw = True
            hw_accel = SettingsManager.to_bool(raw, True)

        # In pure software environments (no GL support at all), mark overlays
        # as ready so diagnostics remain consistent. When GL is available, we
        # defer all overlay initialization to transition-time prepaint.
        if not hw_accel and GL is None:
            self._mark_all_overlays_ready(GL_OVERLAY_KEYS, stage="software_prewarm")

        # Show as borderless fullscreen instead of exclusive fullscreen.
        self.show()
        try:
            self.raise_()
        except Exception:
            pass
        try:
            focus_policy = self.focusPolicy()
        except Exception:
            focus_policy = Qt.FocusPolicy.StrongFocus

        focusable = focus_policy != Qt.FocusPolicy.NoFocus

        try:
            if focusable:
                self.activateWindow()
                try:
                    handle = self.windowHandle()
                    if handle is not None:
                        handle.requestActivate()
                except Exception:
                    pass
                try:
                    self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
                except Exception:
                    try:
                        self.setFocus()
                    except Exception:
                        pass
            else:
                try:
                    handle = self.windowHandle()
                    if handle is not None:
                        handle.setFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
                except Exception:
                    pass
        except Exception:
            pass
        self._handle_screen_change(screen)
        # Reconfigure when screen changes
        try:
            handle = self.windowHandle()
            if handle is not None:
                handle.screenChanged.connect(self._handle_screen_change)
        except Exception:
            pass

        # Ensure shared GL compositor and reuse any persistent overlays
        try:
            self._ensure_gl_compositor()
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to ensure compositor during show", exc_info=True)

        self._reuse_persistent_gl_overlays()

        # Setup overlay widgets AFTER geometry is set
        if self.settings_manager:
            self._setup_widgets()

        # Prewarm context menu on the UI thread so first right-click does not
        # pay the QMenu construction/polish cost.
        try:
            if self._thread_manager is not None:
                self._thread_manager.single_shot(200, self._prewarm_context_menu)
            else:
                ThreadManager.single_shot(200, self._prewarm_context_menu)
        except Exception:
            pass

    def _prewarm_context_menu(self) -> None:
        try:
            if getattr(self, "_context_menu_prewarmed", False):
                return
            if self._context_menu is not None:
                self._context_menu_prewarmed = True
                return
        except Exception:
            return

        try:
            current_transition = "Crossfade"
            if self.settings_manager:
                trans_cfg = self.settings_manager.get("transitions", {})
                if isinstance(trans_cfg, dict):
                    current_transition = trans_cfg.get("type", "Crossfade")
            hard_exit = self._is_hard_exit_enabled()
            dimming_enabled = False
            if self.settings_manager:
                dimming_enabled = SettingsManager.to_bool(
                    self.settings_manager.get("accessibility.dimming.enabled", False),
                    False,
                )
            self._context_menu = ScreensaverContextMenu(
                parent=self,
                current_transition=current_transition,
                dimming_enabled=dimming_enabled,
                hard_exit_enabled=hard_exit,
            )
            self._context_menu.previous_requested.connect(self.previous_requested.emit)
            self._context_menu.next_requested.connect(self.next_requested.emit)
            self._context_menu.transition_selected.connect(self._on_context_transition_selected)
            self._context_menu.settings_requested.connect(self.settings_requested.emit)
            self._context_menu.dimming_toggled.connect(self._on_context_dimming_toggled)
            self._context_menu.hard_exit_toggled.connect(self._on_context_hard_exit_toggled)
            self._context_menu.exit_requested.connect(self._on_context_exit_requested)

            try:
                self._context_menu.aboutToShow.connect(lambda: self._invalidate_overlay_effects("menu_about_to_show"))
            except Exception:
                pass

            # Force Qt to polish/apply stylesheet now.
            try:
                self._context_menu.ensurePolished()
            except Exception:
                pass
        except Exception:
            logger.debug("Failed to prewarm context menu", exc_info=True)
        finally:
            try:
                self._context_menu_prewarmed = True
            except Exception:
                pass

    def _mark_all_overlays_ready(self, overlays: Iterable[str], stage: str) -> None:
        """Mark overlays as ready when running without GL support."""

        for attr_name in overlays:
            overlay = getattr(self, attr_name, None)
            if overlay is None:
                continue
            try:
                self._force_overlay_ready(overlay, stage=f"{stage}:{attr_name}", gl_available=False)
            except Exception:
                name = overlay.objectName() or attr_name
                self.notify_overlay_ready(name, stage, status="software_ready", gl=False)

    def _handle_screen_change(self, screen) -> None:
        """Apply geometry, DPI, and overlay updates for the active screen."""

        if screen is None:
            return

        self._screen = screen

        try:
            self._device_pixel_ratio = float(screen.devicePixelRatio())
        except Exception:
            logger.debug("[SCREEN] Failed to read devicePixelRatio", exc_info=True)

        try:
            screen_geom = screen.geometry()
            if screen_geom is not None and screen_geom.isValid():
                geom = screen_geom
                if _FULLSCREEN_COMPAT_WORKAROUND:
                    try:
                        if geom.height() > 1:
                            geom.setHeight(geom.height() - 1)
                    except Exception:
                        pass
                self.setGeometry(geom)
        except Exception:
            logger.debug("[SCREEN] Failed to apply screen geometry", exc_info=True)

        try:
            self._configure_refresh_rate_sync()
        except Exception:
            logger.debug("[SCREEN] Refresh rate sync configuration failed", exc_info=True)

        try:
            self._ensure_render_surface()
        except Exception:
            logger.debug("[SCREEN] Render surface update failed", exc_info=True)

        try:
            self._ensure_overlay_stack(stage="screen_change")
        except Exception:
            logger.debug("[SCREEN] Overlay stack update failed", exc_info=True)

        try:
            self._reuse_persistent_gl_overlays()
        except Exception:
            logger.debug("[SCREEN] Persistent overlay reuse failed", exc_info=True)

        try:
            self._ensure_gl_compositor()
        except Exception:
            logger.debug("[SCREEN] GL compositor update failed", exc_info=True)

    def _detect_refresh_rate(self) -> float:
        try:
            screen = self._screen
            if screen is None:
                from PySide6.QtGui import QGuiApplication
                screens = QGuiApplication.screens()
                screen = screens[self.screen_index] if self.screen_index < len(screens) else QGuiApplication.primaryScreen()
            hz_attr = getattr(screen, 'refreshRate', None)
            rate = float(hz_attr()) if callable(hz_attr) else 60.0
            if not (10.0 <= rate <= 240.0):
                return 60.0
            return rate
        except Exception:
            return 60.0

    def _configure_refresh_rate_sync(self) -> None:
        # Check if refresh rate sync is enabled
        refresh_sync_enabled = True
        if self.settings_manager:
            try:
                raw = self.settings_manager.get('display.refresh_sync', True)
            except Exception:
                raw = True
            refresh_sync_enabled = SettingsManager.to_bool(raw, True)
        
        if not refresh_sync_enabled:
            # Use fixed 60 FPS when sync is disabled
            self._target_fps = 60
            logger.info("Refresh rate sync disabled, using fixed 60 FPS")
        else:
            detected = int(round(self._detect_refresh_rate()))
            # Apply adaptive rate selection to prevent judder on high-Hz displays:
            # - 60Hz or below: full refresh rate
            # - 61-120Hz: half refresh rate (e.g., 120Hz → 60Hz)
            # - Above 120Hz: third refresh rate (e.g., 165Hz → 55Hz)
            if detected <= 60:
                target = detected
            elif detected <= 120:
                target = detected // 2
            else:
                target = detected // 3
            target = max(30, min(240, target))  # Clamp to reasonable range
            self._target_fps = target
            logger.info(f"Detected refresh rate: {detected} Hz, adaptive target FPS: {self._target_fps}")
        
        try:
            am = getattr(self, "_animation_manager", None)
            if am is not None and hasattr(am, 'set_target_fps'):
                am.set_target_fps(self._target_fps)
        except Exception:
            pass

    def _setup_dimming(self) -> None:
        """Setup background dimming via GL compositor.
        
        Phase 1b: Extracted from _setup_widgets for cleaner delegation.
        """
        if not self.settings_manager:
            return
        
        dimming_enabled = SettingsManager.to_bool(
            self.settings_manager.get('accessibility.dimming.enabled', False), False
        )
        try:
            dimming_opacity = int(self.settings_manager.get('accessibility.dimming.opacity', 30))
            dimming_opacity = max(10, min(90, dimming_opacity))
        except (ValueError, TypeError):
            dimming_opacity = 30
        
        self._dimming_enabled = dimming_enabled
        self._dimming_opacity = dimming_opacity / 100.0
        
        comp = getattr(self, "_gl_compositor", None)
        if comp is not None and hasattr(comp, "set_dimming"):
            comp.set_dimming(dimming_enabled, self._dimming_opacity)
            logger.debug("GL compositor dimming: enabled=%s, opacity=%d%%", dimming_enabled, dimming_opacity)

    def _setup_spotify_widgets(self) -> None:
        """Position Spotify widgets after WidgetManager creates them.
        
        WidgetManager handles creation; this just handles positioning.
        """
        # Position Spotify visualizer if created
        if self.spotify_visualizer_widget is not None:
            try:
                self._position_spotify_visualizer()
            except Exception:
                pass
        
        # Position Spotify volume if created
        if self.spotify_volume_widget is not None:
            try:
                self._position_spotify_volume()
            except Exception:
                pass

    def _setup_pixel_shift(self) -> None:
        """Setup pixel shift manager for burn-in prevention.
        
        Phase 1b: Extracted from _setup_widgets for cleaner delegation.
        """
        if not self.settings_manager:
            return
        
        pixel_shift_enabled = SettingsManager.to_bool(
            self.settings_manager.get('accessibility.pixel_shift.enabled', False), False
        )
        try:
            pixel_shift_rate = int(self.settings_manager.get('accessibility.pixel_shift.rate', 1))
            pixel_shift_rate = max(1, min(5, pixel_shift_rate))
        except (ValueError, TypeError):
            pixel_shift_rate = 1
        
        if self._pixel_shift_manager is None:
            self._pixel_shift_manager = PixelShiftManager(
                resource_manager=self._resource_manager,
                thread_manager=self._thread_manager,
            )
            if self._thread_manager is not None:
                self._pixel_shift_manager.set_thread_manager(self._thread_manager)
            self._pixel_shift_manager.set_defer_check(lambda: self.has_running_transition())
        
        self._pixel_shift_manager.set_shifts_per_minute(pixel_shift_rate)
        
        # Register all overlay widgets
        for attr_name in (
            "clock_widget", "clock2_widget", "clock3_widget",
            "weather_widget", "media_widget", "spotify_visualizer_widget",
            "spotify_volume_widget", "reddit_widget", "reddit2_widget",
        ):
            widget = getattr(self, attr_name, None)
            if widget is not None:
                self._pixel_shift_manager.register_widget(widget)
        
        if pixel_shift_enabled:
            self._pixel_shift_manager.set_enabled(True)
            logger.debug("Pixel shift enabled (rate=%d/min)", pixel_shift_rate)
        else:
            self._pixel_shift_manager.set_enabled(False)

    def _is_hard_exit_enabled(self) -> bool:
        """Return True if hard-exit mode is enabled via settings.

        When enabled, mouse movement/clicks should not close the screensaver;
        only keyboard exit keys are honoured.
        """
        if not self.settings_manager:
            return False
        try:
            raw = self.settings_manager.get('input.hard_exit', False)
        except Exception:
            return False
        if isinstance(raw, str):
            raw = raw.strip().lower()
            if raw in ("true", "1", "yes", "on"):
                return True
            if raw in ("false", "0", "no", "off"):
                return False
            return False
        try:
            return bool(raw)
        except Exception:
            return False
    
    def _setup_widgets(self) -> None:
        """Setup overlay widgets via WidgetManager delegation.
        
        Milestone 2: Refactored to delegate widget creation to WidgetManager.
        This reduces DisplayWidget from ~1166 lines of widget setup to ~50 lines.
        """
        if not self.settings_manager:
            logger.warning("No settings_manager provided - widgets will not be created")
            return

        try:
            # Explicit dot-notation reads kept here for regression coverage.
            self.settings_manager.get("accessibility.dimming.enabled", False)
            self.settings_manager.get("accessibility.dimming.opacity", 30)
            self.settings_manager.get("accessibility.pixel_shift.enabled", False)
            self.settings_manager.get("accessibility.pixel_shift.rate", 1)
        except Exception:
            pass
        
        logger.debug("Setting up overlay widgets for screen %d", self.screen_index)
        
        # Setup dimming first (GL compositor)
        self._setup_dimming()
        
        # Delegate widget creation to WidgetManager
        if self._widget_manager is not None:
            widgets_config = self.settings_manager.get('widgets', {}) if self.settings_manager else {}
            self._widget_manager.configure_expected_overlays(widgets_config)
            created = self._widget_manager.setup_all_widgets(
                self.settings_manager,
                self.screen_index,
                self._thread_manager,
            )
            # Assign created widgets to DisplayWidget attributes
            for attr_name, widget in created.items():
                setattr(self, attr_name, widget)
            logger.info("WidgetManager created %d widgets", len(created))
            
            # Initialize all widgets via lifecycle system (Dec 2025)
            initialized_count = self._widget_manager.initialize_all_widgets()
            if initialized_count > 0:
                logger.debug("[LIFECYCLE] Initialized %d widgets via lifecycle system", initialized_count)
        else:
            logger.warning("No WidgetManager available - widgets will not be created")
            return
        
        # Setup Spotify widgets (complex wiring with media widget)
        self._setup_spotify_widgets()
        
        # Setup pixel shift manager
        self._setup_pixel_shift()
        
        # Apply widget stacking for overlapping positions
        widgets = self.settings_manager.get('widgets', {})
        self._apply_widget_stacking(widgets if isinstance(widgets, dict) else {})

    def _apply_widget_stacking(self, widgets_config: Dict[str, Any]) -> None:
        """Apply vertical stacking offsets - delegates to WidgetManager."""
        if self._widget_manager is None:
            return
        widget_list = [
            (getattr(self, 'clock_widget', None), 'clock_widget'),
            (getattr(self, 'clock2_widget', None), 'clock2_widget'),
            (getattr(self, 'clock3_widget', None), 'clock3_widget'),
            (getattr(self, 'weather_widget', None), 'weather_widget'),
            (getattr(self, 'media_widget', None), 'media_widget'),
            (getattr(self, 'spotify_visualizer_widget', None), 'spotify_visualizer_widget'),
            (getattr(self, 'reddit_widget', None), 'reddit_widget'),
            (getattr(self, 'reddit2_widget', None), 'reddit2_widget'),
        ]
        self._widget_manager.apply_widget_stacking(widget_list)
    
    def recalculate_stacking(self) -> None:
        """Recalculate widget stacking offsets."""
        try:
            widgets = self.settings_manager.get('widgets', {}) if self.settings_manager else {}
            self._apply_widget_stacking(widgets)
        except Exception:
            logger.debug("Failed to recalculate stacking", exc_info=True)

    def _on_animation_manager_ready(self, animation_manager) -> None:
        """Hook called by BaseTransition when an AnimationManager is available.

        Allows overlays such as the Spotify Beat Visualizer to subscribe to
        the same high-frequency tick that drives transitions so they do not
        pause or desync during animations.
        """

        try:
            vis = getattr(self, "spotify_visualizer_widget", None)
        except Exception:
            vis = None

        if vis is None:
            return

        try:
            if hasattr(vis, "attach_to_animation_manager"):
                vis.attach_to_animation_manager(animation_manager)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to attach visualizer to AnimationManager", exc_info=True)

    def _ensure_overlay_stack(self, stage: str = "runtime") -> None:
        """Refresh overlay geometry and schedule raises to maintain Z-order."""

        overlay_keys = GL_OVERLAY_KEYS + SW_OVERLAY_KEYS
        for attr_name in overlay_keys:
            overlay = getattr(self, attr_name, None)
            if overlay is None:
                continue
            try:
                set_overlay_geometry(self, overlay)
            except Exception:
                pass
            try:
                if overlay.isVisible():
                    schedule_raise_when_ready(
                        self,
                        overlay,
                        stage=f"{stage}_{attr_name}",
                    )
                else:
                    # Keep stacking order deterministic even if hidden for now
                    raise_overlay(self, overlay)
            except Exception:
                continue

        # Ensure primary overlay widgets remain above any GL compositor or
        # legacy transition overlays for the duration of transitions.
        # PERF: Skip if we've already raised overlays this frame (raise_overlay handles this)
        # The raise_overlay function already handles all the necessary raises with
        # frame-rate limiting, so we don't need to duplicate the work here.
        pass

    def _force_overlay_ready(self, overlay: QWidget, stage: str, *, gl_available: Optional[bool] = None) -> None:
        """Fallback: force overlay readiness when GL initialization fails."""

        if gl_available is None:
            gl_available = GL is not None

        try:
            lock = getattr(overlay, "_state_lock", None)
            if lock:
                with lock:  # type: ignore[arg-type]
                    if hasattr(overlay, "_gl_initialized"):
                        overlay._gl_initialized = True  # type: ignore[attr-defined]
                    if hasattr(overlay, "_first_frame_drawn"):
                        overlay._first_frame_drawn = True  # type: ignore[attr-defined]
                    if hasattr(overlay, "_has_drawn"):
                        overlay._has_drawn = True  # type: ignore[attr-defined]
                    if hasattr(overlay, "_initialized"):
                        overlay._initialized = True  # type: ignore[attr-defined]
                    if hasattr(overlay, "_ready"):
                        overlay._ready = True  # type: ignore[attr-defined]
                    if hasattr(overlay, "_is_ready"):
                        overlay._is_ready = True  # type: ignore[attr-defined]
            else:
                if hasattr(overlay, "_gl_initialized"):
                    overlay._gl_initialized = True  # type: ignore[attr-defined]
                if hasattr(overlay, "_first_frame_drawn"):
                    overlay._first_frame_drawn = True  # type: ignore[attr-defined]
                if hasattr(overlay, "_has_drawn"):
                    overlay._has_drawn = True  # type: ignore[attr-defined]
                if hasattr(overlay, "_initialized"):
                    overlay._initialized = True  # type: ignore[attr-defined]
                if hasattr(overlay, "_ready"):
                    overlay._ready = True  # type: ignore[attr-defined]
                if hasattr(overlay, "_is_ready"):
                    overlay._is_ready = True  # type: ignore[attr-defined]
        except Exception:
            pass

        try:
            overlay.update()
        except Exception:
            pass

        try:
            name = overlay.objectName() or overlay.__class__.__name__
            self.notify_overlay_ready(name, stage, status="forced_ready", gl=bool(gl_available))
        except Exception:
            pass

    def _reuse_persistent_gl_overlays(self) -> None:
        """Ensure persistent overlays have correct parent and geometry after show."""

        for attr_name in GL_OVERLAY_KEYS:
            overlay = getattr(self, attr_name, None)
            if overlay is None:
                continue
            try:
                if overlay.parent() is not self:
                    overlay.setParent(self)
                set_overlay_geometry(self, overlay)
                overlay.hide()  # stay hidden until transition starts
            except Exception:
                continue
    
    def _create_transition(self) -> Optional[BaseTransition]:
        """Create the next transition, honoring live settings overrides.
        
        Delegates to TransitionFactory for actual transition instantiation.
        This reduces display_widget.py by ~550 lines while maintaining
        identical behavior.
        """
        if self._transition_factory is None:
            # Fallback if factory wasn't initialized (no settings_manager)
            if not self.settings_manager:
                return None
            # Late initialization
            self._transition_factory = TransitionFactory(
                settings_manager=self.settings_manager,
                resource_manager=self._resource_manager,
                compositor_checker=self._has_gl_compositor,
                compositor_ensurer=self._ensure_gl_compositor,
            )
        
        return self._transition_factory.create_transition()
    
    def get_target_size(self) -> QSize:
        """Get the target physical size for image processing.
        
        Returns the physical pixel size (logical * DPR) that images should be
        processed to for this display. Used by async image processing pipelines.
        """
        logical_size = self.size()
        return QSize(
            int(logical_size.width() * self._device_pixel_ratio),
            int(logical_size.height() * self._device_pixel_ratio)
        )

    def logical_to_physical_size(self) -> QSize:
        """
        Convenience alias for tests/utilities that expect a physical size helper.

        Historically DisplayWidget exposed logical_to_physical_size(); the modern
        pipeline uses get_target_size(). Keep this thin wrapper so geometry/DPI
        regression tests can validate DPR scaling without duplicating logic.
        """
        return self.get_target_size()

    def set_image(self, pixmap: QPixmap, image_path: str = "") -> None:
        """Display a new image with transition (backward-compatible sync version)."""
        if pixmap.isNull():
            logger.warning("[FALLBACK] Received null pixmap in set_image")
            self.error_message = "Failed to load image"
            self.current_pixmap = None
            self.update()
            return

        # Delegate processing to ImagePresenter if available
        screen_size = self.get_target_size()
        if self._image_presenter is not None:
            processed = self._image_presenter.process_image(
                pixmap, (screen_size.width(), screen_size.height()), image_path
            )
            if processed is not None:
                self.set_processed_image(processed, pixmap, image_path)
                return
        
        # Fallback: direct processing
        processed_pixmap = ImageProcessor.process_image(
            pixmap, screen_size, self.display_mode, False, False
        )
        self.set_processed_image(processed_pixmap, pixmap, image_path)

    def set_processed_image(self, processed_pixmap: QPixmap, original_pixmap: QPixmap, 
                           image_path: str = "") -> None:
        """Display an already-processed image with transition.
        
        ARCHITECTURAL NOTE: This method accepts pre-processed pixmaps to avoid
        blocking the UI thread with image scaling. The caller (typically the
        engine) should process images on a background thread and call this
        method on the UI thread with the results.
        
        Args:
            processed_pixmap: Screen-fitted pixmap ready for display
            original_pixmap: Original unprocessed pixmap (for reference)
            image_path: Path to image (for logging/events)
        """
        # If a transition is already running, skip this call (single-skip policy)
        if self.has_running_transition():
            self._transition_skip_count += 1
            logger.debug(
                "Transition in progress - skipping image request (skip_count=%s)",
                self._transition_skip_count,
            )
            return

        if processed_pixmap.isNull():
            logger.warning("[FALLBACK] Received null processed pixmap")
            self.error_message = "Failed to load image"
            self.current_pixmap = None
            self.update()
            return

        # Use the pre-processed pixmap directly - no UI thread blocking
        new_pixmap = processed_pixmap
        
        self._animation_manager = None
        self._overlay_timeouts: dict[str, float] = {}
        self._pre_raise_log_emitted = False
        self._base_fallback_paint_logged = False
        
        # Set DPR on the processed pixmap for proper display scaling
        processed_pixmap.setDevicePixelRatio(self._device_pixel_ratio)
        try:
            new_pixmap.setDevicePixelRatio(self._device_pixel_ratio)
        except Exception:
            pass
        
        # Stop any running transition via TransitionController
        if self._transition_controller is not None:
            self._transition_controller.stop_current()
        elif self._current_transition:
            transition_to_stop = self._current_transition
            self._current_transition = None
            try:
                transition_to_stop.stop()
                transition_to_stop.cleanup()
            except Exception as e:
                logger.warning(f"Error stopping transition: {e}")
        
        # Cache previous pixmap reference before we mutate current_pixmap
        previous_pixmap_ref = self.current_pixmap

        # Seed base widget with the new frame before starting transitions.
        # This prevents fallback paints (black bands) while overlays warm up.
        self.current_pixmap = processed_pixmap
        if self.current_pixmap:
            try:
                self.current_pixmap.setDevicePixelRatio(self._device_pixel_ratio)
            except Exception:
                pass
            self._seed_pixmap = self.current_pixmap
            self._last_pixmap_seed_ts = time.monotonic()
            
            # Phase 4b: Notify ImagePresenter of pixmap change
            if self._image_presenter is not None:
                try:
                    self._image_presenter.set_current(self.current_pixmap, update_seed=True)
                except Exception:
                    pass
            if is_verbose_logging():
                logger.debug(
                    "[DIAG] Seed pixmap set (phase=pre-transition, pixmap=%s)",
                    _describe_pixmap(self.current_pixmap),
                )
            if self._updates_blocked_until_seed:
                try:
                    self.setUpdatesEnabled(True)
                except Exception:
                    pass
                self._updates_blocked_until_seed = False

            # Pre-warm the shared GL compositor with the current frame so that
            # its GL surface is active before any animated transition starts.
            # This reduces first-use flicker, especially on secondary
            # displays, by avoiding late compositor initialization.
            try:
                self._ensure_gl_compositor()
            except Exception:
                pass
            comp = getattr(self, "_gl_compositor", None)
            if isinstance(comp, GLCompositorWidget):
                try:
                    comp.setGeometry(0, 0, self.width(), self.height())
                    comp.set_base_pixmap(self.current_pixmap)
                    comp.show()
                    comp.raise_()
                    # Prewarm shader textures for the upcoming transition so
                    # GLSL paths (Slide, Wipe, Diffuse, etc.) do not pay the
                    # full texture upload cost on their first animated frame.
                    try:
                        comp.warm_shader_textures(previous_pixmap_ref, new_pixmap)
                    except Exception:
                        logger.debug(
                            "[GL COMPOSITOR] warm_shader_textures failed during pre-warm",
                            exc_info=True,
                        )
                    # Raise all overlay widgets above the compositor ONCE here.
                    # The rate-limited raise_overlay() handles ongoing raises.
                    # Raise all widgets above the compositor
                    for attr_name in (
                        "clock_widget", "clock2_widget", "clock3_widget",
                        "weather_widget", "media_widget", "spotify_visualizer_widget",
                        "_spotify_bars_overlay", "spotify_volume_widget", "reddit_widget",
                        "reddit2_widget", "_ctrl_cursor_hint",
                    ):
                        w = getattr(self, attr_name, None)
                        if w is not None:
                            try:
                                w.raise_()
                            except Exception:
                                pass
                except Exception:
                    logger.debug("[GL COMPOSITOR] Failed to pre-warm compositor with base frame", exc_info=True)

            use_transition = bool(self.settings_manager) and self._has_rendered_first_frame
            if self.settings_manager and not self._has_rendered_first_frame:
                logger.debug("[INIT] First frame - presenting without transition to avoid black flicker")

            if not self._transitions_enabled:
                use_transition = False

            if use_transition:
                transition = self._create_transition()
                if transition:
                    # Set previous pixmap for transition
                    self.previous_pixmap = previous_pixmap_ref or processed_pixmap
                    
                    # For compositor-backed 3D Block Spins, seed with old image
                    comp = getattr(self, "_gl_compositor", None)
                    if (transition.__class__.__name__ == "GLCompositorBlockSpinTransition"
                        and isinstance(comp, GLCompositorWidget)
                        and previous_pixmap_ref is not None
                        and not previous_pixmap_ref.isNull()):
                        try:
                            comp.set_base_pixmap(previous_pixmap_ref)
                        except Exception:
                            pass

                    self._warm_transition_if_needed(
                        comp,
                        transition.__class__.__name__,
                        self.previous_pixmap,
                        new_pixmap,
                    )

                    # Store pending finish args
                    self._pending_transition_finish_args = (processed_pixmap, original_pixmap, image_path, False, None)
                    
                    # Create finish handler with weakref
                    self_ref = weakref.ref(self)
                    def _finish_handler(np=processed_pixmap, op=original_pixmap, ip=image_path, ref=self_ref):
                        widget = ref()
                        if widget is None or not Shiboken.isValid(widget):
                            return
                        try:
                            widget._pending_transition_finish_args = (np, op, ip, False, None)
                            widget._on_transition_finished(np, op, ip, False, None)
                        finally:
                            widget._pending_transition_finish_args = None

                    # Delegate transition start to TransitionController
                    overlay_key = self._resolve_overlay_key_for_transition(transition)
                    if self._transition_controller is not None:
                        success = self._transition_controller.start_transition(
                            transition, self.previous_pixmap, new_pixmap,
                            overlay_key=overlay_key, on_finished=_finish_handler
                        )
                    else:
                        # Fallback: direct start
                        transition.finished.connect(_finish_handler)
                        success = transition.start(self.previous_pixmap, new_pixmap, self)
                    
                    if success:
                        self._current_transition = transition
                        self._current_transition_overlay_key = overlay_key
                        self._current_transition_started_at = time.monotonic()
                        self._current_transition_name = transition.__class__.__name__
                        self._current_transition_first_run = (
                            self._current_transition_name not in self._warmed_transition_types
                        )
                        if is_perf_metrics_enabled():
                            logger.info(
                                "[PERF] [TRANSITION] Start name=%s first_run=%s overlay=%s",
                                self._current_transition_name,
                                self._current_transition_first_run,
                                overlay_key or "<none>",
                            )
                        if overlay_key:
                            self._overlay_timeouts[overlay_key] = self._current_transition_started_at
                        # Raise widgets SYNCHRONOUSLY
                        if self._widget_manager is not None:
                            try:
                                self._widget_manager.raise_all_widgets()
                            except Exception:
                                pass
                        for attr in ("_spotify_bars_overlay", "_ctrl_cursor_hint"):
                            w = getattr(self, attr, None)
                            if w is not None:
                                try:
                                    w.raise_()
                                except Exception:
                                    pass
                        logger.debug(f"Transition started: {transition.__class__.__name__}")
                        return
                    else:
                        logger.warning("Transition failed to start, displaying immediately")
                        transition.cleanup()
                        self._current_transition = None
                        self._current_transition_name = None
                        self._current_transition_first_run = False
                        self._pending_transition_finish_args = None
                        use_transition = False
                else:
                    use_transition = False

            if not use_transition:
                self._pending_transition_finish_args = None
                self._cancel_transition_watchdog()
                # No transition - display immediately
                self.previous_pixmap = None
                self.update()
                if GL is None:
                    try:
                        self._mark_all_overlays_ready(GL_OVERLAY_KEYS, stage="software_display")
                    except Exception:
                        pass

                try:
                    self._ensure_overlay_stack(stage="display")
                except Exception:
                    pass

                logger.debug(f"Image displayed: {image_path} ({processed_pixmap.width()}x{processed_pixmap.height()})")
                self.current_image_path = image_path
                self.image_displayed.emit(image_path)
                self._has_rendered_first_frame = True

    def _on_transition_finished(
        self,
        new_pixmap: QPixmap,
        original_pixmap: QPixmap,
        image_path: str,
        pan_enabled: bool,
        pan_preview: Optional[QPixmap] = None,
    ) -> None:
        """Handle transition completion."""
        # Delegate cleanup to TransitionController
        if self._transition_controller is not None:
            try:
                self._transition_controller.on_transition_finished()
            except Exception:
                pass
        
        # Clear local state
        self._current_transition_overlay_key = None
        self._current_transition_started_at = 0.0
        self._current_transition = None
        if self._current_transition_name:
            self._warmed_transition_types.add(self._current_transition_name)
            self._last_transition_name = self._current_transition_name
        self._current_transition_name = None
        self._current_transition_first_run = False
        self._last_transition_finished_wall_ts = time.time()

        # Update pixmap state
        self.current_pixmap = pan_preview or new_pixmap
        if self.current_pixmap:
            try:
                self.current_pixmap.setDevicePixelRatio(self._device_pixel_ratio)
            except Exception:
                pass
        self._seed_pixmap = self.current_pixmap
        self._last_pixmap_seed_ts = time.monotonic()
        
        # Notify ImagePresenter
        if self._image_presenter is not None:
            try:
                self._image_presenter.complete_transition(new_pixmap, pan_preview)
            except Exception:
                pass
        
        if self._updates_blocked_until_seed:
            try:
                self.setUpdatesEnabled(True)
            except Exception:
                pass
            self._updates_blocked_until_seed = False
        self.previous_pixmap = None

        # Ensure overlays and repaint
        try:
            self._ensure_overlay_stack(stage="transition_finish")
        except Exception:
            pass
        self.update()

        try:
            logger.debug("Transition completed, image displayed: %s", image_path)
        except Exception:
            pass
        self.current_image_path = image_path
        self.image_displayed.emit(image_path)
        self._pending_transition_finish_args = None

    def _warm_transition_if_needed(
        self,
        compositor: Optional[GLCompositorWidget],
        transition_name: str,
        old_pixmap: Optional[QPixmap],
        new_pixmap: Optional[QPixmap],
    ) -> None:
        """Warm per-transition GL resources to avoid first-run stalls."""
        if (
            compositor is None
            or transition_name in self._prewarmed_transition_types
            or new_pixmap is None
            or new_pixmap.isNull()
        ):
            return

        warm_old = old_pixmap
        if warm_old is None or warm_old.isNull():
            warm_old = new_pixmap

        try:
            warmed = compositor.warm_transition_resources(transition_name, warm_old, new_pixmap)
            if warmed:
                self._prewarmed_transition_types.add(transition_name)
        except Exception:
            logger.debug(
                "[GL COMPOSITOR] warm_transition_resources failed for %s",
                transition_name,
                exc_info=True,
            )

    def _cancel_transition_watchdog(self) -> None:
        """Cancel transition watchdog."""
        if self._transition_controller is not None:
            try:
                self._transition_controller._cancel_watchdog()
            except Exception:
                pass
        self._transition_watchdog_overlay_key = None
        self._transition_watchdog_transition = None

    def _resolve_overlay_key_for_transition(self, transition: BaseTransition) -> Optional[str]:
        mapping = {
            "GLCrossfadeTransition": "_srpss_gl_xfade_overlay",
            "GLSlideTransition": "_srpss_gl_slide_overlay",
            "GLWipeTransition": "_srpss_gl_wipe_overlay",
            "GLBlindsTransition": "_srpss_gl_blinds_overlay",
            "GLDiffuseTransition": "_srpss_gl_diffuse_overlay",
            "GLBlockPuzzleFlipTransition": "_srpss_gl_blockflip_overlay",
        }
        return mapping.get(transition.__class__.__name__)

    def _position_spotify_visualizer(self) -> None:
        """Position Spotify Beat Visualizer - delegates to WidgetManager."""
        if self._widget_manager is not None:
            self._widget_manager.position_spotify_visualizer(
                getattr(self, "spotify_visualizer_widget", None),
                getattr(self, "media_widget", None),
                self.width(), self.height()
            )

    def _position_spotify_volume(self) -> None:
        """Position Spotify volume slider - delegates to WidgetManager."""
        if self._widget_manager is not None:
            self._widget_manager.position_spotify_volume(
                getattr(self, "spotify_volume_widget", None),
                getattr(self, "media_widget", None),
                self.width(), self.height()
            )

    def push_spotify_visualizer_frame(
        self,
        *,
        bars,
        bar_count,
        segments,
        fill_color,
        border_color,
        fade,
        playing,
        ghosting_enabled=True,
        ghost_alpha=0.4,
        ghost_decay=-1.0,
        vis_mode="spectrum",
    ):
        vis = getattr(self, "spotify_visualizer_widget", None)
        if vis is None:
            return False

        try:
            if not vis.isVisible():
                return False
        except Exception:
            return False

        try:
            geom = vis.geometry()
        except Exception:
            return False

        if geom.width() <= 0 or geom.height() <= 0:
            return False

        # Lazily create a small GL overlay dedicated to Spotify bars. This
        # sits above the card widget in Z-order while the card itself remains
        # a normal QWidget with ShadowFadeProfile-driven opacity.
        overlay = getattr(self, "_spotify_bars_overlay", None)
        if overlay is None or not isinstance(overlay, SpotifyBarsGLOverlay):
            try:
                overlay = SpotifyBarsGLOverlay(self)
                overlay.setObjectName("spotify_bars_gl_overlay")
                self._spotify_bars_overlay = overlay
                if self._resource_manager is not None:
                    try:
                        self._resource_manager.register_qt(
                            overlay,
                            description="Spotify bars GL overlay",
                        )
                    except Exception:
                        logger.debug("[SPOTIFY_VIS] Failed to register SpotifyBarsGLOverlay", exc_info=True)
                pixel_shift_manager = getattr(self, "_pixel_shift_manager", None)
                if pixel_shift_manager is not None:
                    try:
                        pixel_shift_manager.register_widget(overlay)
                    except Exception:
                        logger.debug("[SPOTIFY_VIS] Failed to register GL overlay with PixelShiftManager", exc_info=True)
            except Exception:
                self._spotify_bars_overlay = None
                return False

        if overlay is None:
            return False

        try:
            overlay.set_state(
                geom,
                bars,
                bar_count,
                segments,
                fill_color,
                border_color,
                fade,
                playing,
                visible=True,
                ghosting_enabled=ghosting_enabled,
                ghost_alpha=ghost_alpha,
                ghost_decay=ghost_decay,
                vis_mode=vis_mode,
            )
            pixel_shift_manager = getattr(self, "_pixel_shift_manager", None)
            if pixel_shift_manager is not None and hasattr(pixel_shift_manager, "update_original_position"):
                try:
                    pixel_shift_manager.update_original_position(overlay)
                except Exception:
                    logger.debug("[SPOTIFY_VIS] Failed to sync GL overlay baseline with PixelShiftManager", exc_info=True)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to push frame to SpotifyBarsGLOverlay", exc_info=True)
            return False

        return True

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Handle mouse double click."""
        if self._input_handler is not None:
            self._input_handler.handle_mouse_double_click(event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._device_pixel_ratio = self.windowHandle().devicePixelRatio() if self.windowHandle() else self._device_pixel_ratio
        if self._render_surface is not None:
            try:
                self._render_surface.resize(
                    event.size().width(),
                    event.size().height(),
                    self._device_pixel_ratio,
                )
            except NotImplementedError:
                logger.debug("[RENDER] Render surface resize not implemented yet")
            except Exception as exc:
                logger.warning("[RENDER] Failed to resize render surface: %s", exc)

        # Ensure backend fallback overlay tracks geometry
        if self._backend_fallback_message:
            try:
                self._refresh_backend_fallback_overlay()
            except Exception:
                logger.debug("[RENDER] Failed to refresh backend fallback overlay geometry", exc_info=True)
        try:
            self._ensure_overlay_stack(stage="resize")
        except Exception:
            pass
        try:
            self._position_spotify_visualizer()
        except Exception:
            pass
        try:
            self._position_spotify_volume()
        except Exception:
            pass

    def _init_renderer_backend(self) -> None:
        """Select and initialize the configured renderer backend."""

        if self.settings_manager is None:
            logger.info("[RENDER] No settings manager attached; backend initialization skipped")
            return

        event_system: Optional[EventSystem] = None
        try:
            if hasattr(self.settings_manager, "get_event_system"):
                candidate = self.settings_manager.get_event_system()
                if isinstance(candidate, EventSystem):
                    event_system = candidate
        except Exception:
            event_system = None

        try:
            selection = create_backend_from_settings(
                self.settings_manager,
                event_system=event_system,
            )
            backend = selection.backend
            self._backend_selection = selection
            self._renderer_backend = backend
            caps = backend.get_capabilities()
            logger.info(
                "[RENDER] Backend active (screen=%s, api=%s %s, triple=%s, vsync_toggle=%s)",
                self.screen_index,
                caps.api_name,
                caps.api_version,
                caps.supports_triple_buffer,
                caps.supports_vsync_toggle,
            )
            if selection.fallback_performed:
                logger.warning(
                    "[RENDER] Backend fallback engaged (requested=%s, resolved=%s, reason=%s)",
                    selection.requested_mode,
                    selection.resolved_mode,
                    selection.fallback_reason,
                )
            self._backend_fallback_message = (
                "Renderer backend: "
                f"{selection.resolved_mode.upper()} (requested {selection.requested_mode.upper()})"
            )
            self._update_backend_fallback_overlay()
        except Exception:
            logger.exception("[RENDER] Failed to initialize renderer backend", exc_info=True)
            self._renderer_backend = None
            self._backend_selection = None
            self._backend_fallback_message = None
            hide_backend_fallback_overlay(self)

    def _build_surface_descriptor(self) -> SurfaceDescriptor:
        vsync_enabled = True
        prefer_triple = True
        if self.settings_manager:
            refresh_sync = self.settings_manager.get('display.refresh_sync', True)
            if isinstance(refresh_sync, str):
                refresh_sync = refresh_sync.lower() in ('true', '1', 'yes')
            vsync_enabled = bool(refresh_sync)

            prefer_triple = self.settings_manager.get('display.prefer_triple_buffer', True)
            if isinstance(prefer_triple, str):
                prefer_triple = prefer_triple.lower() in ('true', '1', 'yes')

        width = max(1, self.width())
        height = max(1, self.height())

        return SurfaceDescriptor(
            screen_index=self.screen_index,
            width=width,
            height=height,
            dpi=self._device_pixel_ratio,
            vsync_enabled=vsync_enabled,
            prefer_triple_buffer=prefer_triple,
        )

    def _ensure_render_surface(self) -> None:
        if self._renderer_backend is None:
            return
        if self._render_surface is not None:
            return
        descriptor = self._build_surface_descriptor()
        try:
            surface = self._renderer_backend.create_surface(descriptor)
        except NotImplementedError:
            logger.debug("[RENDER] Backend create_surface not implemented; using widget fallback")
            return
        except Exception as exc:
            logger.exception("[RENDER] Failed to create render surface: %s", exc)
            return

        self._render_surface = surface
        logger.info(
            "[RENDER] Render surface established (screen=%s, %sx%s, vsync=%s, triple_preference=%s)",
            descriptor.screen_index,
            descriptor.width,
            descriptor.height,
            descriptor.vsync_enabled,
            descriptor.prefer_triple_buffer,
        )

    def _ensure_gl_compositor(self) -> None:
        """Create or resize the shared GL compositor widget when appropriate.

        The compositor is only used when hardware acceleration is enabled,
        an OpenGL backend is active, and PyOpenGL/GL are available. This keeps
        software-only environments on the existing CPU path.
        """

        # Guard on hw_accel setting
        hw_accel = True
        if self.settings_manager is not None:
            try:
                raw = self.settings_manager.get("display.hw_accel", True)
            except Exception:
                raw = True
            hw_accel = SettingsManager.to_bool(raw, True)
        if not hw_accel:
            return

        # Require an OpenGL backend selection
        if self._backend_selection and self._backend_selection.resolved_mode != "opengl":
            return

        if self._gl_compositor is None:
            try:
                comp = GLCompositorWidget(self)
                comp.setObjectName("_srpss_gl_compositor")
                comp.setGeometry(0, 0, self.width(), self.height())
                comp.hide()
                if self._resource_manager is not None:
                    try:
                        self._resource_manager.register_qt(
                            comp,
                            description="Shared GL compositor for DisplayWidget",
                        )
                    except Exception:
                        logger.debug("[GL COMPOSITOR] Failed to register compositor with ResourceManager", exc_info=True)
                self._gl_compositor = comp
                logger.info("[GL COMPOSITOR] Created shared compositor for screen %s", self.screen_index)
            except Exception as exc:
                logger.warning("[GL COMPOSITOR] Failed to create compositor: %s", exc)
                self._gl_compositor = None
                return
        else:
            try:
                self._gl_compositor.setGeometry(0, 0, self.width(), self.height())
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to update compositor geometry", exc_info=True)

    def _has_gl_compositor(self) -> bool:
        """Check if the GL compositor is available and ready."""
        return isinstance(self._gl_compositor, GLCompositorWidget)

    def _destroy_render_surface(self) -> None:
        if self._render_surface is None or self._renderer_backend is None:
            self._render_surface = None
            return
        try:
            self._renderer_backend.destroy_surface(self._render_surface)
        except Exception as exc:
            logger.warning("[RENDER] Failed to destroy render surface cleanly: %s", exc)
        finally:
            self._render_surface = None

    def _cleanup_widget(self, attr_name: str, tag: str, stop_method: str = "cleanup") -> None:
        """Helper to safely cleanup a widget attribute.
        
        Args:
            attr_name: Name of the widget attribute (e.g., "media_widget")
            tag: Log tag for debug messages (e.g., "MEDIA")
            stop_method: Method to call for cleanup ("cleanup", "stop", or None)
        """
        try:
            widget = getattr(self, attr_name, None)
            if widget is None:
                return
            if stop_method:
                method = getattr(widget, stop_method, None)
                if callable(method):
                    try:
                        method()
                    except Exception:
                        pass
            try:
                widget.hide()
            except Exception:
                pass
            setattr(self, attr_name, None)
        except Exception as e:
            logger.debug("[%s] Failed to cleanup in _on_destroyed: %s", tag, e, exc_info=True)

    def _on_destroyed(self, *_args) -> None:
        """Ensure active transitions are stopped when the widget is destroyed."""
        # NOTE: Deferred Reddit URL opening is now handled by DisplayManager.cleanup()
        # to ensure it happens AFTER windows are hidden but BEFORE QApplication.quit()
        
        # Phase 5: Unregister from MultiMonitorCoordinator
        if self._screen is not None:
            try:
                self._coordinator.unregister_instance(self, self._screen)
            except Exception:
                pass
        
        # Phase 5: Release focus and event filter ownership via coordinator
        try:
            self._coordinator.release_focus(self)
            self._coordinator.uninstall_event_filter(self)
        except Exception:
            pass
        
        self._destroy_render_surface()
        
        # Ensure compositor is torn down cleanly
        try:
            if self._gl_compositor is not None:
                cleanup = getattr(self._gl_compositor, "cleanup", None)
                if callable(cleanup):
                    try:
                        cleanup()
                    except Exception as e:
                        logger.debug("[GL COMPOSITOR] Cleanup failed: %s", e, exc_info=True)
                self._gl_compositor.hide()
                self._gl_compositor.setParent(None)
                self._gl_compositor = None
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Teardown failed: %s", e, exc_info=True)
            self._gl_compositor = None
        
        # Cleanup all overlay widgets using helper
        self._cleanup_widget("spotify_visualizer_widget", "SPOTIFY_VIS", "stop")
        self._cleanup_widget("media_widget", "MEDIA", "cleanup")
        self._cleanup_widget("weather_widget", "WEATHER", "cleanup")
        self._cleanup_widget("reddit_widget", "REDDIT", "cleanup")
        self._cleanup_widget("reddit2_widget", "REDDIT2", "cleanup")
        self._cleanup_widget("_pixel_shift_manager", "PIXEL_SHIFT", "cleanup")
        
        # Cleanup cursor halo (top-level window, must be explicitly destroyed)
        try:
            if self._ctrl_cursor_hint is not None:
                self._ctrl_cursor_hint.hide()
                self._ctrl_cursor_hint.deleteLater()
                self._ctrl_cursor_hint = None
        except Exception:
            self._ctrl_cursor_hint = None
        
        # Stop and clean up any active transition via TransitionController
        try:
            if self._transition_controller is not None:
                self._transition_controller.stop_current()
            elif self._current_transition:
                try:
                    self._current_transition.stop()
                except Exception:
                    pass
                try:
                    self._current_transition.cleanup()
                except Exception:
                    pass
                self._current_transition = None
        except Exception as e:
            logger.debug("[TRANSITION] Cleanup failed: %s", e, exc_info=True)
        
        # Hide overlays and cancel watchdog timer
        try:
            hide_all_overlays(self)
        except Exception as e:
            logger.debug("[OVERLAYS] Hide failed: %s", e, exc_info=True)
        self._cancel_transition_watchdog()

    def _update_backend_fallback_overlay(self) -> None:
        """Show or hide diagnostic overlay based on backend selection state."""

        if self._backend_selection and self._backend_selection.fallback_performed:
            reason = self._backend_selection.fallback_reason or "Unknown"
            message = (
                "Renderer fallback active\n"
                f"Requested: {self._backend_selection.requested_mode.upper()}\n"
                f"Using: {self._backend_selection.resolved_mode.upper()}\n"
                f"Reason: {reason}"
            )
            self._backend_fallback_message = message
            self._refresh_backend_fallback_overlay()
        else:
            self._backend_fallback_message = None
            hide_backend_fallback_overlay(self)

    def _refresh_backend_fallback_overlay(self) -> None:
        """Ensure backend fallback overlay matches current geometry/message."""

        if not self._backend_fallback_message:
            hide_backend_fallback_overlay(self)
            return

        def _register_overlay(overlay: QWidget) -> None:
            if self._resource_manager:
                try:
                    self._resource_manager.register_qt(
                        overlay,
                        description="Backend fallback diagnostic overlay",
                    )
                except Exception:
                    logger.debug("[RENDER] Failed to register fallback overlay", exc_info=True)

        show_backend_fallback_overlay(
            self,
            self._backend_fallback_message,
            on_create=_register_overlay,
        )
    
    def set_display_mode(self, mode: DisplayMode) -> None:
        """
        Change display mode.
        
        Args:
            mode: New display mode
        """
        if mode != self.display_mode:
            self.display_mode = mode
            logger.info(f"Display mode changed to {mode}")
            
            # FIX: Need to store original pixmap to reprocess properly
            # Reprocess current image if available
            if self.current_pixmap:
                # WARNING: This reprocesses the already-processed pixmap - will degrade quality
                logger.warning("Reprocessing already-processed pixmap - quality may degrade. Store original pixmap for proper reprocessing.")
                # In production, we'd want to store the original and reprocess from that
                logger.debug("Reprocessing current image with new mode")
                self.update()
    
    def clear(self) -> None:
        """Clear displayed image and stop any transitions."""
        # Stop transition via TransitionController
        if self._transition_controller is not None:
            self._transition_controller.stop_current()
        elif self._current_transition:
            transition_to_stop = self._current_transition
            self._current_transition = None
            try:
                transition_to_stop.stop()
            except Exception as e:
                logger.warning(f"Error stopping transition in clear(): {e}")
        # Ensure overlays are hidden to prevent residual frames during exit
        try:
            hide_all_overlays(self)
        except Exception:
            pass
        
        # Hide and destroy cursor halo (top-level window that persists independently)
        # Must hide immediately and process events to ensure it's gone before settings dialog
        try:
            if self._ctrl_cursor_hint is not None:
                self._ctrl_cursor_hint.hide()
                self._ctrl_cursor_hint.close()
                self._ctrl_cursor_hint.deleteLater()
                self._ctrl_cursor_hint = None
        except Exception:
            self._ctrl_cursor_hint = None
        
        # Reset global Ctrl state to prevent halo from reappearing
        try:
            from rendering.multi_monitor_coordinator import get_coordinator
            coordinator = get_coordinator()
            coordinator.set_ctrl_held(False)
            coordinator.clear_halo_owner()
        except Exception:
            pass

        self.previous_pixmap = self.current_pixmap
        self.current_pixmap = None
        self._seed_pixmap = None
        self._last_pixmap_seed_ts = None
        self.error_message = None
        self._pre_raise_log_emitted = False
        self._base_fallback_paint_logged = False
        self.update()

    def reset_after_settings(self) -> None:
        try:
            self.setUpdatesEnabled(False)
            self._updates_blocked_until_seed = True
        except Exception:
            self._updates_blocked_until_seed = False
        self._has_rendered_first_frame = False
        self._seed_pixmap = None
        self._last_pixmap_seed_ts = None
        self._pre_raise_log_emitted = False
        self._base_fallback_paint_logged = False

    def show_error(self, message: str) -> None:
        """Show error message on the display widget."""
        self.error_message = message
        self.previous_pixmap = self.current_pixmap
        self.current_pixmap = None
        self._seed_pixmap = None
        self._last_pixmap_seed_ts = None
        self._pre_raise_log_emitted = False
        self._base_fallback_paint_logged = False
        self.update()
        logger.warning(f"[FALLBACK] Showing error: {message}")

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint event - draw current image or error message."""
        # If the shared GL compositor is present and visible, let it handle
        # all rendering instead of painting the base widget or legacy overlays.
        try:
            comp = getattr(self, "_gl_compositor", None)
            if isinstance(comp, GLCompositorWidget) and comp.isVisible():
                return
        except Exception:
            pass

        # Thread-safe check: if any legacy overlay is ready (GL initialized +
        # first frame drawn), let it handle painting. This path is only used
        # when the compositor is not active.
        try:
            if any_overlay_ready_for_display(self):
                return
        except Exception:
            pass

        pixmap_to_paint = self.current_pixmap
        if (pixmap_to_paint is None or pixmap_to_paint.isNull()) and self._seed_pixmap and not self._seed_pixmap.isNull():
            pixmap_to_paint = self._seed_pixmap
        # As a last resort (no current/seed and no error), reuse the previous pixmap rather than flashing black.
        if (
            (pixmap_to_paint is None or pixmap_to_paint.isNull())
            and self.error_message is None
            and self.previous_pixmap is not None
            and not self.previous_pixmap.isNull()
        ):
            pixmap_to_paint = self.previous_pixmap

        if (pixmap_to_paint is None or pixmap_to_paint.isNull()) and not self._base_fallback_paint_logged:
            try:
                overlay_visible = any_gl_overlay_visible(self)
            except Exception:
                overlay_visible = False
            seed_age_ms = None
            if self._last_pixmap_seed_ts is not None:
                seed_age_ms = (time.monotonic() - self._last_pixmap_seed_ts) * 1000.0
            logger.debug(
                "[DIAG] Base paint fallback executing (screen=%s, overlay_visible=%s, has_error=%s, seed_age_ms=%s, current=%s, seed=%s, updates_blocked=%s)",
                self.screen_index,
                overlay_visible,
                bool(self.error_message),
                f"{seed_age_ms:.2f}" if seed_age_ms is not None else "N/A",
                _describe_pixmap(self.current_pixmap),
                _describe_pixmap(self._seed_pixmap),
                bool(self._updates_blocked_until_seed),
            )
            self._base_fallback_paint_logged = True

        painter = QPainter(self)

        # Draw image if available; only fall back to a black fill when we truly
        # have nothing to show or an error message. This avoids a full-screen
        # black flash during normal first-frame paints.
        if pixmap_to_paint and not pixmap_to_paint.isNull():
            try:
                painter.drawPixmap(self.rect(), pixmap_to_paint)
            except Exception:
                painter.drawPixmap(0, 0, pixmap_to_paint)
        elif self.error_message:
            painter.fillRect(self.rect(), Qt.GlobalColor.black)
            painter.setPen(Qt.GlobalColor.white)
            font = QFont("Arial", 24)
            painter.setFont(font)
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self.error_message
            )
        else:
            painter.fillRect(self.rect(), Qt.GlobalColor.black)

        painter.end()
    
    def notify_overlay_ready(self, overlay_name: str, stage: str, **details) -> None:
        """Diagnostic hook invoked by overlays when they report readiness."""
        self._last_overlay_ready_ts = time.monotonic()
        seed_age_ms = None
        if self._last_pixmap_seed_ts is not None:
            seed_age_ms = (self._last_overlay_ready_ts - self._last_pixmap_seed_ts) * 1000.0
        record_overlay_ready(
            logger,
            self.screen_index,
            overlay_name,
            stage,
            self._overlay_stage_counts,
            self._overlay_swap_warned,
            seed_age_ms,
            details,
        )

    def request_overlay_fade_sync(self, overlay_name: str, starter: Callable[[], None]) -> None:
        """Register an overlay's initial fade so all widgets can fade together.

        Delegates to WidgetManager which has the correct expected overlay set.
        """
        if self._widget_manager is not None:
            try:
                self._widget_manager.request_overlay_fade_sync(overlay_name, starter)
                return
            except Exception:
                pass
        
        # Fallback: run starter immediately if no WidgetManager
        try:
            starter()
        except Exception:
            pass

    def _start_overlay_fades(self, force: bool = False) -> None:
        """Kick off any pending overlay fade callbacks."""

        if getattr(self, "_overlay_fade_started", False):
            return
        self._overlay_fade_started = True

        timeout = getattr(self, "_overlay_fade_timeout", None)
        if timeout is not None:
            try:
                timeout.stop()
                timeout.deleteLater()
            except Exception:
                pass
            self._overlay_fade_timeout = None

        pending = getattr(self, "_overlay_fade_pending", {})
        try:
            starters = list(pending.values())
            names = list(pending.keys())
        except Exception:
            starters = []
            names = []
        logger.debug(
            "[OVERLAY_FADE] starting overlay fades (force=%s, overlays=%s)",
            force,
            sorted(names),
        )
        self._overlay_fade_pending = {}

        # To reduce visible pops on startup when the event loop is still busy
        # with GL/image initialisation, introduce a short warm-up delay for
        # coordinated fades. The force path keeps immediate behaviour so a
        # misbehaving overlay cannot block fades indefinitely.
        warmup_delay_ms = 0 if force else 250

        if warmup_delay_ms <= 0:
            for starter in starters:
                try:
                    starter()
                except Exception:
                    pass
            # When the primary fades fire immediately (force path or no
            # warm-up), still give Spotify widgets a brief second-wave delay
            # so they do not appear before the main group.
            try:
                self._run_spotify_secondary_fades(base_delay_ms=150)
            except Exception:
                pass
            return

        for starter in starters:
            try:
                QTimer.singleShot(warmup_delay_ms, starter)
            except Exception:
                try:
                    starter()
                except Exception:
                    pass

        # Schedule Spotify secondary fades to start a little after the
        # coordinated primary warm-up, so the volume slider and visualiser
        # card feel attached to the wave without blocking it.
        try:
            self._run_spotify_secondary_fades(base_delay_ms=warmup_delay_ms + 150)
        except Exception:
            pass

    def _run_spotify_secondary_fades(self, *, base_delay_ms: int) -> None:
        """Start any queued Spotify second-wave fade callbacks."""

        starters = getattr(self, "_spotify_secondary_fade_starters", None)
        if not starters:
            return
        try:
            queued = list(starters)
        except Exception:
            queued = []
        self._spotify_secondary_fade_starters = []

        delay_ms = max(0, int(base_delay_ms))
        for starter in queued:
            try:
                if delay_ms <= 0:
                    starter()
                else:
                    QTimer.singleShot(delay_ms, starter)
            except Exception:
                try:
                    starter()
                except Exception:
                    pass

    def register_spotify_secondary_fade(self, starter: Callable[[], None]) -> None:
        """Register a Spotify second-wave fade to run after primary overlays.

        When there is no primary overlay coordination active, or when the
        primary group has already started, the starter is run with a small
        delay so it still feels like a secondary pass without popping in
        ahead of other widgets.
        """

        try:
            expected = self._overlay_fade_expected
        except Exception:
            expected = set()

        starters = getattr(self, "_spotify_secondary_fade_starters", None)
        if not isinstance(starters, list):
            starters = []
            self._spotify_secondary_fade_starters = starters

        # If no primary overlays are coordinated for this display, or the
        # primary wave has already started, run this as a tiny second wave
        # instead of waiting for a coordinator that will never fire.
        if not expected or getattr(self, "_overlay_fade_started", False):
            try:
                QTimer.singleShot(150, starter)
            except Exception:
                try:
                    starter()
                except Exception:
                    pass
            return

        starters.append(starter)

    def get_overlay_stage_counts(self) -> dict[str, int]:
        """Return snapshot of overlay readiness counts (for diagnostics/tests)."""
        return dict(self._overlay_stage_counts)

    def _ensure_ctrl_cursor_hint(self) -> None:
        """Create the cursor halo widget if it doesn't exist."""
        if self._ctrl_cursor_hint is not None:
            return
        self._ctrl_cursor_hint = CursorHaloWidget(self)

    def _show_ctrl_cursor_hint(self, pos, mode: str = "none") -> None:
        """Show/animate the cursor halo at the given position.
        
        Args:
            pos: Position to center the halo on (local widget coordinates)
            mode: "none" for reposition only, "fade_in" or "fade_out" for animation
        """
        self._ensure_ctrl_cursor_hint()
        hint = self._ctrl_cursor_hint
        if hint is None:
            return

        # Do not show the halo while the settings dialog is active.
        try:
            from rendering.multi_monitor_coordinator import get_coordinator

            if get_coordinator().settings_dialog_active:
                self._hide_ctrl_cursor_hint(immediate=True)
                return
        except Exception:
            pass

        # Normalize incoming position to QPoint for consistency
        try:
            if isinstance(pos, QPoint):
                local_point = QPoint(pos)
            else:
                local_point = QPoint(int(pos.x()), int(pos.y()))
        except Exception:
            return
        rect = self.rect()
        context_menu_active = bool(getattr(self, "_context_menu_active", False))
        halo_slack = float(max(0.0, getattr(self, "_halo_out_of_bounds_slack", 8.0)))

        if mode != "fade_out":
            if not rect.contains(local_point):
                should_hide = (
                    local_point.x() < rect.left() - halo_slack
                    or local_point.y() < rect.top() - halo_slack
                    or local_point.x() > rect.right() + halo_slack
                    or local_point.y() > rect.bottom() + halo_slack
                )
                if should_hide:
                    self._hide_ctrl_cursor_hint(immediate=True)
                    return
            if context_menu_active:
                self._hide_ctrl_cursor_hint(immediate=True)
                return
            self._halo_last_local_pos = QPoint(local_point)
            self._last_halo_activity_ts = time.monotonic()
            self._reset_halo_inactivity_timer()
            hint.move_to(local_point.x(), local_point.y())
            if not hint.isVisible():
                hint.show()
        else:
            self._cancel_halo_inactivity_timer()

        if mode == "fade_in":
            if not hint.isVisible():
                hint.show()
            hint.fade_in()
        elif mode == "fade_out":
            hint.fade_out()
        elif mode != "fade_out":
            # Already ensured move/show above
            pass

    def _hide_ctrl_cursor_hint(self, *, immediate: bool = False) -> None:
        """Hide the cursor halo widget."""
        hint = self._ctrl_cursor_hint
        if hint is None:
            return
        self._cancel_halo_inactivity_timer()
        try:
            if immediate:
                hint.cancel_animation()
                hint.hide()
            else:
                hint.fade_out()
        except Exception:
            hint.hide()

    def _reset_halo_inactivity_timer(self) -> None:
        """Restart the inactivity timer that hides the halo after inactivity."""
        timeout_sec = float(max(0.5, getattr(self, "_halo_activity_timeout", 2.0)))
        timeout_ms = int(timeout_sec * 1000)

        timer = getattr(self, "_halo_inactivity_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._on_halo_inactivity_timeout)
            self._halo_inactivity_timer = timer

        try:
            timer.start(timeout_ms)
        except Exception:
            pass

    def _cancel_halo_inactivity_timer(self) -> None:
        timer = getattr(self, "_halo_inactivity_timer", None)
        if timer is None:
            return
        try:
            timer.stop()
        except Exception:
            pass

    def _on_halo_inactivity_timeout(self) -> None:
        """Hide the halo if there has been no local movement recently."""
        now = time.monotonic()
        last = float(getattr(self, "_last_halo_activity_ts", 0.0) or 0.0)
        timeout_sec = float(max(0.5, getattr(self, "_halo_activity_timeout", 2.0)))
        if last <= 0.0 or (now - last) >= timeout_sec:
            self._hide_ctrl_cursor_hint(immediate=True)

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self._coordinator.release_focus(self)
            self._coordinator.uninstall_event_filter(self)
        except Exception:
            pass
        
        # Cleanup widgets via lifecycle system (Dec 2025)
        if self._widget_manager is not None:
            try:
                self._widget_manager.cleanup()
                logger.debug("[LIFECYCLE] WidgetManager cleanup complete")
            except Exception:
                logger.debug("[LIFECYCLE] WidgetManager cleanup failed", exc_info=True)
        
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press - delegate to InputHandler."""
        key = event.key()

        # Ctrl key: delegate halo management to InputHandler
        if key == Qt.Key.Key_Control:
            if self._input_handler is not None:
                try:
                    self._input_handler.handle_ctrl_press(self._coordinator)
                    event.accept()
                    return
                except Exception:
                    logger.debug("[KEY] Ctrl press delegation failed", exc_info=True)
            event.accept()
            return
        
        # Delegate all other key handling to InputHandler
        if self._input_handler is not None:
            try:
                if self._input_handler.handle_key_press(event):
                    # InputHandler signals are connected to our signals
                    if self._input_handler.is_exiting():
                        self._exiting = True
                    event.accept()
                    return
            except Exception:
                logger.debug("[KEY] Key press delegation failed", exc_info=True)
        
        event.ignore()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Control:
            # Delegate Ctrl release to InputHandler
            if self._input_handler is not None:
                try:
                    self._input_handler.handle_ctrl_release(self._coordinator)
                    event.accept()
                    return
                except Exception:
                    logger.debug("[KEY] Ctrl release delegation failed", exc_info=True)
            event.accept()
            return
        event.ignore()
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press - exit on any click unless hard exit is enabled."""
        # Phase 5: Use coordinator for global Ctrl state
        ctrl_mode_active = self._ctrl_held or self._coordinator.ctrl_held
        
        # Phase E: Delegate right-click context menu to InputHandler if available
        # This ensures effect invalidation is triggered consistently before menu popup
        if event.button() == Qt.MouseButton.RightButton:
            if self._is_hard_exit_enabled() or ctrl_mode_active:
                if self._input_handler is not None:
                    try:
                        # InputHandler will trigger effect invalidation and emit context_menu_requested
                        if self._input_handler.handle_mouse_press(event, self._coordinator.ctrl_held):
                            event.accept()
                            return
                    except Exception:
                        pass
                # Fallback: direct context menu show
                self._show_context_menu(event.globalPosition().toPoint())
                event.accept()
                return
            # Normal mode without Ctrl - fall through to exit
        
        if self._is_hard_exit_enabled() or ctrl_mode_active:
            # Delegate widget click routing to InputHandler
            handled = False
            reddit_handled = False
            
            reddit_url = None
            if self._input_handler is not None:
                try:
                    handled, reddit_handled, reddit_url = self._input_handler.route_widget_click(
                        event,
                        getattr(self, "spotify_volume_widget", None),
                        getattr(self, "media_widget", None),
                        getattr(self, "reddit_widget", None),
                        getattr(self, "reddit2_widget", None),
                        getattr(self, "gmail_widget", None),
                    )
                    logger.info("[REDDIT] route_widget_click returned: handled=%s reddit_handled=%s screen=%s",
                               handled, reddit_handled, self.screen_index)
                except Exception:
                    logger.debug("[INPUT] Widget click routing failed", exc_info=True)

            if handled:
                # Request exit after Reddit clicks
                reddit_exit_on_click = getattr(self, "_reddit_exit_on_click", True)
                logger.info("[REDDIT] Click routed: handled=%s reddit_handled=%s reddit_exit_on_click=%s screen=%s", 
                            handled, reddit_handled, reddit_exit_on_click, self.screen_index)
                if reddit_handled and reddit_exit_on_click:
                    # Detect display configuration for Reddit link handling:
                    # A) All displays covered + hard_exit: Exit immediately
                    # B) All displays covered + Ctrl held: Exit immediately
                    # C) MC mode (primary NOT covered): Stay open, bring browser to foreground
                    #
                    # System-agnostic: uses QGuiApplication.primaryScreen() which is the
                    # OS-configured primary, not necessarily screen index 0.
                    
                    this_is_primary = False
                    primary_is_covered = False
                    try:
                        from PySide6.QtGui import QGuiApplication
                        primary_screen = QGuiApplication.primaryScreen()
                        
                        # Check if THIS widget is on the primary screen
                        if self._screen is not None and primary_screen is not None:
                            this_is_primary = (self._screen is primary_screen)
                        
                        # If THIS is primary, then primary is definitely covered
                        if this_is_primary:
                            primary_is_covered = True
                        else:
                            # Check if primary screen has a DisplayWidget registered
                            if primary_screen is not None:
                                primary_widget = self._coordinator.get_instance_for_screen(primary_screen)
                                primary_is_covered = (primary_widget is not None)
                    except Exception:
                        # Fallback: assume primary is NOT covered (MC mode behavior)
                        # This is safer than assuming exit - user can always press Esc
                        primary_is_covered = False
                    
                    logger.info("[REDDIT] Exit check: this_is_primary=%s primary_is_covered=%s exiting=%s screen=%s",
                                this_is_primary, primary_is_covered, self._exiting, self.screen_index)
                    
                    if primary_is_covered:
                        # Cases A & B: Primary is covered, user wants to leave screensaver
                        logger.info("[REDDIT] Primary covered; requesting immediate exit")
                        if not self._exiting:
                            self._exiting = True
                            if reddit_url:
                                self._pending_reddit_url = reddit_url
                            # Bring browser to foreground after windows start closing
                            def _bring_browser_foreground():
                                try:
                                    from widgets.reddit_widget import _try_bring_reddit_window_to_front
                                    _try_bring_reddit_window_to_front()
                                except Exception:
                                    pass
                            QTimer.singleShot(300, _bring_browser_foreground)
                            self.exit_requested.emit()
                    else:
                        # Case C: MC mode - primary not covered, stay open
                        # Delay browser foreground to give browser time to open the URL
                        # and create a window with "reddit" in the title
                        logger.info("[REDDIT] MC mode (primary not covered); staying open, will bring browser to foreground after delay")
                        url_to_open = reddit_url
                        if url_to_open:
                            try:
                                from PySide6.QtCore import QUrl
                                from PySide6.QtGui import QDesktopServices
                                if QDesktopServices.openUrl(QUrl(url_to_open)):
                                    logger.info("[REDDIT] MC mode: opened %s immediately", url_to_open)
                                else:
                                    logger.warning("[REDDIT] MC mode: QDesktopServices rejected %s", url_to_open)
                            except Exception:
                                logger.debug("[REDDIT] MC mode immediate open failed; falling back", exc_info=True)
                                url_to_open = None
                        if not url_to_open:
                            logger.info("[REDDIT] MC mode: no URL opened immediately; skipping foreground attempt")
                        else:
                            def _bring_browser_foreground_mc():
                                try:
                                    from widgets.reddit_widget import _try_bring_reddit_window_to_front
                                    _try_bring_reddit_window_to_front()
                                    logger.debug("[REDDIT] MC mode: browser foreground attempted")
                                except Exception:
                                    pass
                            QTimer.singleShot(300, _bring_browser_foreground_mc)
                    
                event.accept()
                return

            # In interaction mode, don't exit on unhandled clicks
            event.accept()
            return

        logger.info(f"Mouse clicked at ({event.pos().x()}, {event.pos().y()}), requesting exit")
        self._exiting = True
        # Deferred Reddit URLs are now flushed centrally by DisplayManager after teardown.
        self.exit_requested.emit()
        event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move - exit if moved beyond threshold (unless hard exit)."""
        # Don't exit while context menu is active
        if self._context_menu_active:
            event.accept()
            return
        
        # Phase 5: Use coordinator for global Ctrl state
        ctrl_mode_active = self._coordinator.ctrl_held
        if self._is_hard_exit_enabled() or ctrl_mode_active:
            # Delegate volume drag to InputHandler
            if self._input_handler is not None:
                try:
                    self._input_handler.route_volume_drag(
                        event.pos(), getattr(self, "spotify_volume_widget", None)
                    )
                except Exception:
                    pass
            event.accept()
            return

        # Store initial position on first move
        if self._initial_mouse_pos is None:
            self._initial_mouse_pos = event.pos()
            event.accept()
            return
        
        # Calculate distance from initial position
        dx = event.pos().x() - self._initial_mouse_pos.x()
        dy = event.pos().y() - self._initial_mouse_pos.y()
        distance = (dx * dx + dy * dy) ** 0.5
        
        # Exit if moved beyond threshold
        if distance > self._mouse_move_threshold:
            logger.info(f"Mouse moved {distance:.1f} pixels, requesting exit")
            self._exiting = True
            self.exit_requested.emit()
        
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release; end Spotify volume drags in interaction mode."""
        ctrl_mode_active = self._ctrl_held or self._coordinator.ctrl_held
        if self._is_hard_exit_enabled() or ctrl_mode_active:
            if self._input_handler is not None:
                self._input_handler.route_volume_release(getattr(self, "spotify_volume_widget", None))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Route wheel scrolling to Spotify volume widget in interaction mode."""
        ctrl_mode_active = self._ctrl_held or self._coordinator.ctrl_held
        if self._is_hard_exit_enabled() or ctrl_mode_active:
            # Delegate to InputHandler
            if self._input_handler is not None:
                try:
                    pos = event.position().toPoint()
                    delta_y = int(event.angleDelta().y())
                    if self._input_handler.route_wheel_event(
                        pos, delta_y,
                        getattr(self, "spotify_volume_widget", None),
                        getattr(self, "media_widget", None),
                        getattr(self, "spotify_visualizer_widget", None),
                    ):
                        event.accept()
                        return
                except Exception:
                    logger.debug("[WHEEL] routing failed", exc_info=True)
            # In interaction mode, wheel should never exit
            event.accept()
            return
        super().wheelEvent(event)

    def _show_context_menu(self, global_pos) -> None:
        """Show the context menu at the given global position."""
        try:
            # Get current transition from settings
            current_transition = "Crossfade"
            if self.settings_manager:
                trans_cfg = self.settings_manager.get("transitions", {})
                if isinstance(trans_cfg, dict):
                    current_transition = trans_cfg.get("type", "Crossfade")
            
            hard_exit = self._is_hard_exit_enabled()
            
            # Get dimming state - use dot notation for settings
            dimming_enabled = False
            if self.settings_manager:
                dimming_enabled = SettingsManager.to_bool(
                    self.settings_manager.get("accessibility.dimming.enabled", False), False
                )
            
            # Create menu if needed (lazy init for performance)
            if self._context_menu is None:
                self._context_menu = ScreensaverContextMenu(
                    parent=self,
                    current_transition=current_transition,
                    dimming_enabled=dimming_enabled,
                    hard_exit_enabled=hard_exit,
                )
                # Connect signals
                self._context_menu.previous_requested.connect(self.previous_requested.emit)
                self._context_menu.next_requested.connect(self.next_requested.emit)
                self._context_menu.transition_selected.connect(self._on_context_transition_selected)
                self._context_menu.settings_requested.connect(self.settings_requested.emit)
                self._context_menu.dimming_toggled.connect(self._on_context_dimming_toggled)
                self._context_menu.hard_exit_toggled.connect(self._on_context_hard_exit_toggled)
                self._context_menu.exit_requested.connect(self._on_context_exit_requested)
                try:
                    self._context_menu.aboutToShow.connect(lambda: self._invalidate_overlay_effects("menu_about_to_show"))
                except Exception:
                    pass
                try:
                    submenu = getattr(self._context_menu, "_transition_menu", None)
                except Exception:
                    submenu = None
                try:
                    connected_sub = bool(getattr(self, "_context_menu_sub_connected", False))
                except Exception:
                    connected_sub = False
                if submenu is not None and not connected_sub:
                    try:
                        submenu.aboutToShow.connect(lambda: self._invalidate_overlay_effects("menu_sub_about_to_show"))
                    except Exception:
                        pass
                    try:
                        submenu.aboutToHide.connect(lambda: self._schedule_effect_invalidation("menu_sub_after_hide"))
                    except Exception:
                        pass
                    try:
                        setattr(self, "_context_menu_sub_connected", True)
                    except Exception:
                        pass
            else:
                # Update state before showing
                self._context_menu.update_current_transition(current_transition)
                self._context_menu.update_dimming_state(dimming_enabled)
                self._context_menu.update_hard_exit_state(hard_exit)
            
            try:
                self._context_menu_active = True
            except Exception:
                pass
            self._hide_ctrl_cursor_hint(immediate=True)

            try:
                t0 = time.monotonic()
                setattr(self, "_menu_open_ts", t0)
                if win_diag_logger.isEnabledFor(logging.DEBUG):
                    win_diag_logger.debug(
                        "[MENU_OPEN] begin t=%.6f screen=%s pos=%s",
                        t0,
                        self.screen_index,
                        global_pos,
                    )
            except Exception:
                setattr(self, "_menu_open_ts", None)

            try:
                connected = getattr(self, "_context_menu_hide_connected", False)
            except Exception:
                connected = False
            if not connected:
                try:
                    def _on_menu_hide() -> None:
                        try:
                            self._context_menu_active = False
                        except Exception:
                            pass
                        # Phase E: Notify InputHandler of menu close for consistent state
                        try:
                            if self._input_handler is not None:
                                self._input_handler.set_context_menu_active(False)
                        except Exception:
                            pass
                        try:
                            self._invalidate_overlay_effects("menu_after_hide")
                            self._schedule_effect_invalidation("menu_after_hide")
                        except Exception:
                            pass
                        try:
                            start = getattr(self, "_menu_open_ts", None)
                            if start is not None and win_diag_logger.isEnabledFor(logging.DEBUG):
                                t1 = time.monotonic()
                                win_diag_logger.debug(
                                    "[MENU_OPEN] end t=%.6f dt=%.3fms screen=%s",
                                    t1,
                                    (t1 - start) * 1000.0,
                                    self.screen_index,
                                )
                        except Exception:
                            pass
                        # Restore halo after menu closes if still in hard_exit or Ctrl mode
                        try:
                            hard_exit = False
                            if self.settings_manager:
                                hard_exit = SettingsManager.to_bool(
                                    self.settings_manager.get("input.hard_exit", False), False
                                )
                            if hard_exit or self._coordinator.ctrl_held:
                                # Re-show halo at current cursor position
                                global_pos = QCursor.pos()
                                local_pos = self.mapFromGlobal(global_pos)
                                if self.rect().contains(local_pos):
                                    self._coordinator.set_halo_owner(self)
                                    self._show_ctrl_cursor_hint(local_pos, mode="fade_in")
                        except Exception:
                            pass

                    self._context_menu.aboutToHide.connect(_on_menu_hide)
                    setattr(self, "_context_menu_hide_connected", True)
                except Exception:
                    pass

            # Phase E: Notify InputHandler of menu open for consistent state
            try:
                if self._input_handler is not None:
                    self._input_handler.set_context_menu_active(True)
            except Exception:
                pass
            try:
                # Phase E: Broadcast effect invalidation to ALL displays
                # Context menu on one display triggers Windows activation cascade
                # that corrupts QGraphicsEffect caches on OTHER displays
                from rendering.multi_monitor_coordinator import get_coordinator
                try:
                    self._invalidate_overlay_effects("menu_before_popup")
                except Exception:
                    pass
                get_coordinator().invalidate_all_effects("menu_before_popup_broadcast")
                self._context_menu.popup(global_pos)
            except Exception:
                try:
                    self._context_menu.popup(QCursor.pos())
                except Exception:
                    pass

        except Exception:
            logger.debug("Failed to show context menu", exc_info=True)
            self._context_menu_active = False
    
    def _on_context_transition_selected(self, name: str) -> None:
        """Handle transition selection from context menu."""
        try:
            if self.settings_manager:
                trans_cfg = self.settings_manager.get("transitions", {})
                if not isinstance(trans_cfg, dict):
                    trans_cfg = {}
                trans_cfg["type"] = name
                trans_cfg["random_always"] = False
                self.settings_manager.set("transitions", trans_cfg)
                self.settings_manager.save()
                logger.info("Context menu: transition changed to %s", name)
        except Exception:
            logger.debug("Failed to set transition from context menu", exc_info=True)
    
    def _on_context_dimming_toggled(self, enabled: bool) -> None:
        """Handle dimming toggle from context menu."""
        try:
            if self.settings_manager:
                self.settings_manager.set("accessibility.dimming.enabled", enabled)
                self.settings_manager.save()
                logger.info("Context menu: dimming set to %s", enabled)
            
            # Update local GL compositor dimming
            self._dimming_enabled = enabled
            comp = getattr(self, "_gl_compositor", None)
            if comp is not None and hasattr(comp, "set_dimming"):
                comp.set_dimming(enabled, self._dimming_opacity)
            
            # Emit signal to sync dimming across ALL displays
            self.dimming_changed.emit(enabled, self._dimming_opacity)
        except Exception:
            logger.debug("Failed to toggle dimming from context menu", exc_info=True)
    
    def _on_context_hard_exit_toggled(self, enabled: bool) -> None:
        """Handle hard exit toggle from context menu."""
        try:
            if self.settings_manager:
                self.settings_manager.set("input.hard_exit", enabled)
                self.settings_manager.save()
                logger.info("Context menu: hard exit mode set to %s", enabled)
        except Exception:
            logger.debug("Failed to toggle hard exit from context menu", exc_info=True)
    
    def _on_context_exit_requested(self) -> None:
        """Handle exit request from context menu."""
        logger.info("Context menu: exit requested")
        self._exiting = True
        self.exit_requested.emit()
    
    def _on_input_exit_requested(self) -> None:
        """Handle exit request from InputHandler (Phase E refactor)."""
        self._exiting = True
        self.exit_requested.emit()
    
    def _on_context_menu_requested(self, global_pos: QPoint) -> None:
        """Handle context menu request from InputHandler (Phase E refactor).
        
        This method centralizes menu popup triggering through InputHandler,
        ensuring consistent effect invalidation ordering.
        """
        try:
            self._show_context_menu(global_pos)
        except Exception:
            logger.debug("[INPUT_HANDLER] Failed to show context menu", exc_info=True)
    
    def focusOutEvent(self, event: QFocusEvent) -> None:  # type: ignore[override]
        """Diagnostic: log once if we lose focus while still visible.

        This helps detect cases where another window occludes the screensaver
        without going through the normal exit paths. Only logs in debug mode
        and only once per widget instance.
        """
        try:
            if self.isVisible() and not self._exiting and not self._focus_loss_logged:
                logger.debug(
                    "[ZORDER] DisplayWidget lost focus while visible; "
                    "screensaver may be occluded (screen_index=%s, window_state=%s)",
                    self.screen_index,
                    int(self.windowState()),
                )
                self._focus_loss_logged = True
        except Exception:
            pass

        super().focusOutEvent(event)

    def _debug_window_state(self, label: str, *, extra: str = "") -> None:
        if not win_diag_logger.isEnabledFor(logging.DEBUG):
            return
        try:
            try:
                hwnd = int(self.winId())
            except Exception:
                hwnd = 0
            try:
                active = bool(self.isActiveWindow())
            except Exception:
                active = False
            try:
                visible = bool(self.isVisible())
            except Exception:
                visible = False
            try:
                ws = int(self.windowState())
            except Exception:
                ws = -1
            try:
                upd = bool(self.updatesEnabled())
            except Exception:
                upd = False

            win_diag_logger.debug(
                "[WIN_STATE] %s screen=%s hwnd=%s visible=%s active=%s windowState=%s updatesEnabled=%s %s",
                label,
                getattr(self, "screen_index", "?"),
                hex(hwnd) if hwnd else "?",
                visible,
                active,
                ws,
                upd,
                extra,
            )
        except Exception:
            pass

    def _perform_activation_refresh(self, reason: str) -> None:
        try:
            self._pending_activation_refresh = False
        except Exception:
            pass

        try:
            self._base_fallback_paint_logged = False
        except Exception:
            pass

        if win_diag_logger.isEnabledFor(logging.DEBUG):
            try:
                win_diag_logger.debug(
                    "[ACTIVATE_REFRESH] screen=%s reason=%s",
                    getattr(self, "screen_index", "?"),
                    reason,
                )
            except Exception:
                pass

        comp = getattr(self, "_gl_compositor", None)
        if comp is not None:
            try:
                comp.update()
            except Exception:
                pass

        try:
            self.update()
        except Exception:
            pass

        try:
            bars_gl = getattr(self, "_spotify_bars_overlay", None)
            if bars_gl is not None:
                try:
                    bars_gl.update()
                except Exception:
                    pass
        except Exception:
            pass

        for name in (
            "clock_widget",
            "clock2_widget",
            "clock3_widget",
            "weather_widget",
            "media_widget",
            "spotify_visualizer_widget",
            "spotify_volume_widget",
            "reddit_widget",
            "reddit2_widget",
        ):
            w = getattr(self, name, None)
            if w is None:
                continue
            try:
                if w.isVisible():
                    w.update()
            except Exception:
                pass

        self._schedule_effect_invalidation(f"activate_refresh:{reason}")

    def _schedule_effect_invalidation(self, reason: str) -> None:
        try:
            if getattr(self, "_pending_effect_invalidation", False):
                return
            self._pending_effect_invalidation = True
        except Exception:
            return

        def _run() -> None:
            try:
                self._invalidate_overlay_effects(reason)
            finally:
                try:
                    self._pending_effect_invalidation = False
                except Exception:
                    pass

        try:
            tm = getattr(self, "_thread_manager", None)
            if tm is not None:
                tm.single_shot(0, _run)
            else:
                ThreadManager.single_shot(0, _run)
        except Exception:
            _run()

    def _invalidate_overlay_effects(self, reason: str) -> None:
        """Delegate effect invalidation to WidgetManager (Phase E refactor)."""
        if self._widget_manager is not None:
            try:
                self._widget_manager.invalidate_overlay_effects(reason)
            except Exception:
                pass

    def focusInEvent(self, event: QFocusEvent) -> None:  # type: ignore[override]
        try:
            self._debug_window_state("focusInEvent")
        except Exception:
            pass
        try:
            self._invalidate_overlay_effects("focus_in")
        except Exception:
            pass
        super().focusInEvent(event)

    def changeEvent(self, event: QEvent) -> None:  # type: ignore[override]
        try:
            if event is not None:
                self._debug_window_state(f"changeEvent:{int(event.type())}")
        except Exception:
            pass
        super().changeEvent(event)

    def nativeEvent(self, eventType, message):  # type: ignore[override]
        try:
            if sys.platform != "win32":
                return super().nativeEvent(eventType, message)

            msg = self._extract_win_msg(message)
            if msg is None:
                return super().nativeEvent(eventType, message)

            mid = int(getattr(msg, "message", 0) or 0)
            if mid == WM_APPCOMMAND:
                handled, result = self._handle_win_appcommand(msg)
                if handled:
                    return True, result

            if not win_diag_logger.isEnabledFor(logging.DEBUG):
                return super().nativeEvent(eventType, message)

            names = {
                0x0006: "WM_ACTIVATE",
                0x0086: "WM_NCACTIVATE",
                0x0046: "WM_WINDOWPOSCHANGING",
                0x0047: "WM_WINDOWPOSCHANGED",
                0x007C: "WM_STYLECHANGING",
                0x007D: "WM_STYLECHANGED",
                0x0014: "WM_ERASEBKGND",
                0x000B: "WM_SETREDRAW",
                WM_APPCOMMAND: "WM_APPCOMMAND",
            }

            name = names.get(mid)
            if name is not None:
                try:
                    hwnd = int(getattr(msg, "hwnd", 0) or 0)
                except Exception:
                    hwnd = 0
                try:
                    wparam = int(getattr(msg, "wParam", 0) or 0)
                except Exception:
                    wparam = 0
                try:
                    lparam = int(getattr(msg, "lParam", 0) or 0)
                except Exception:
                    lparam = 0

                extra = f"msg={name} wParam={wparam} lParam={lparam} hwnd={hex(hwnd) if hwnd else '?'}"
                try:
                    for inst in DisplayWidget.get_all_instances():
                        try:
                            inst._debug_window_state("nativeEvent", extra=extra)
                        except Exception:
                            pass
                except Exception:
                    self._debug_window_state("nativeEvent", extra=extra)

                if name == "WM_ACTIVATE":
                    if wparam == 0:
                        try:
                            for inst in DisplayWidget.get_all_instances():
                                try:
                                    inst._pending_activation_refresh = True
                                    inst._last_deactivate_ts = time.monotonic()
                                except Exception:
                                    pass
                        except Exception:
                            try:
                                self._pending_activation_refresh = True
                                self._last_deactivate_ts = time.monotonic()
                            except Exception:
                                pass
                    elif wparam == 1:
                        now_ts = time.monotonic()
                        try:
                            for inst in DisplayWidget.get_all_instances():
                                try:
                                    if not getattr(inst, "_pending_activation_refresh", False):
                                        continue
                                    dt = now_ts - float(getattr(inst, "_last_deactivate_ts", 0.0) or 0.0)
                                    if dt <= 3.0:
                                        try:
                                            QTimer.singleShot(0, lambda _inst=inst: _inst._perform_activation_refresh("wm_activate"))
                                        except Exception:
                                            inst._perform_activation_refresh("wm_activate")
                                    else:
                                        inst._pending_activation_refresh = False
                                except Exception:
                                    pass
                        except Exception:
                            pass

        except Exception:
            pass

        return super().nativeEvent(eventType, message)

    def _extract_win_msg(self, raw_message):
        try:
            msg_ptr = int(raw_message)
        except Exception:
            return None
        if msg_ptr == 0:
            return None
        try:
            return ctypes.cast(msg_ptr, ctypes.POINTER(wintypes.MSG)).contents
        except Exception:
            return None

    def _handle_win_appcommand(self, msg) -> tuple[bool, int]:
        try:
            hwnd = int(getattr(msg, "hwnd", 0) or 0)
        except Exception:
            hwnd = 0
        try:
            wparam = int(getattr(msg, "wParam", 0) or 0)
        except Exception:
            wparam = 0
        try:
            lparam = int(getattr(msg, "lParam", 0) or 0)
        except Exception:
            lparam = 0

        command = (lparam >> 16) & 0xFFFF
        command_name = _APPCOMMAND_NAMES.get(command, f"APPCOMMAND_{command:04x}")
        device = lparam & 0xFFFF
        window_mode = getattr(self, "_mc_window_flag_mode", None) or "standard"

        target_logger = win_diag_logger if win_diag_logger.isEnabledFor(logging.DEBUG) else logger
        target_logger.debug(
            "[WIN_APPCOMMAND] mode=%s cmd=%s (%#06x) device=%#06x wParam=%s lParam=%#010x",
            window_mode,
            command_name,
            command,
            device,
            wparam,
            lparam,
        )

        if _USER32 is not None and hwnd:
            try:
                result = int(_USER32.DefWindowProcW(hwnd, WM_APPCOMMAND, wparam, lparam))
                return True, result
            except Exception:
                target_logger.debug("[WIN_APPCOMMAND] DefWindowProcW failed", exc_info=True)

        return False, 0

    def eventFilter(self, watched, event):  # type: ignore[override]
        """Global event filter to keep the Ctrl halo responsive over children."""
        try:
            coordinator = self._coordinator
        except Exception:
            coordinator = None

        settings_dialog_active = False
        if coordinator is not None:
            try:
                settings_dialog_active = bool(coordinator.settings_dialog_active)
            except Exception:
                settings_dialog_active = False

        if settings_dialog_active:
            # Settings dialog suppresses halo/activity entirely.
            try:
                owner = coordinator.halo_owner if coordinator is not None else None
                if owner is not None:
                    owner._hide_ctrl_cursor_hint(immediate=True)
            except Exception:
                pass
            return super().eventFilter(watched, event)

        try:
            if event is not None and event.type() == QEvent.Type.KeyPress:
                try:
                    key_event = event  # QKeyEvent
                    target = self._coordinator.focus_owner
                    if target is None or not isinstance(target, DisplayWidget) or not target.isVisible():
                        target = self
                    if isinstance(target, DisplayWidget) and target.isVisible():
                        if key_event.key() == Qt.Key.Key_Control:
                            if target._input_handler is not None:
                                try:
                                    target._input_handler.handle_ctrl_press(self._coordinator)
                                    event.accept()
                                    return True
                                except Exception:
                                    logger.debug("[KEY] Ctrl press delegation failed", exc_info=True)
                            event.accept()
                            return True
                        if target._input_handler is not None:
                            try:
                                if target._input_handler.handle_key_press(key_event):
                                    if target._input_handler.is_exiting():
                                        target._exiting = True
                                    event.accept()
                                    return True
                            except Exception:
                                logger.debug("[KEY] Key press delegation failed", exc_info=True)
                except Exception:
                    pass

            if event is not None and event.type() == QEvent.Type.KeyRelease:
                try:
                    key_event = event  # QKeyEvent
                    if key_event.key() == Qt.Key.Key_Control:
                        target = self._coordinator.focus_owner
                        if target is None or not isinstance(target, DisplayWidget) or not target.isVisible():
                            target = self
                        if isinstance(target, DisplayWidget) and target.isVisible():
                            if target._input_handler is not None:
                                try:
                                    target._input_handler.handle_ctrl_release(self._coordinator)
                                    event.accept()
                                    return True
                                except Exception:
                                    logger.debug("[KEY] Ctrl release delegation failed", exc_info=True)
                            event.accept()
                            return True
                except Exception:
                    pass

            if event is not None and event.type() == QEvent.Type.MouseMove:
                hard_exit = False
                try:
                    hard_exit = self._is_hard_exit_enabled()
                except Exception:
                    hard_exit = False

                # Phase 5: Use coordinator for global Ctrl state and halo ownership
                ctrl_held = bool(self._coordinator.ctrl_held or getattr(DisplayWidget, "_global_ctrl_held", False))
                if ctrl_held or hard_exit:
                    # Use global cursor position so we track even when the
                    # event originates from a child widget. Resolve the
                    # DisplayWidget that owns the halo based on the cursor's
                    # current QScreen to behave correctly across mixed-DPI
                    # multi-monitor layouts.
                    global_pos = QCursor.pos()

                    from PySide6.QtGui import QGuiApplication

                    cursor_screen = None
                    try:
                        cursor_screen = QGuiApplication.screenAt(global_pos)
                    except Exception:
                        cursor_screen = None

                    owner = self._coordinator.halo_owner
                    if owner is None:
                        owner = getattr(DisplayWidget, "_halo_owner", None)

                    # If the cursor moved to a different screen, migrate the
                    # halo owner to the DisplayWidget bound to that screen.
                    if cursor_screen is not None:
                        screen_changed = (
                            owner is None
                            or getattr(owner, "_screen", None) is not cursor_screen
                        )
                        if screen_changed:
                            # Phase 5: Use coordinator for instance lookup
                            new_owner = self._coordinator.get_instance_for_screen(cursor_screen)
                            
                            # Fallback to iteration only if cache miss (shouldn't happen)
                            if new_owner is None:
                                try:
                                    widgets = QApplication.topLevelWidgets()
                                except Exception:
                                    widgets = []

                                for w in widgets:
                                    try:
                                        if not isinstance(w, DisplayWidget):
                                            continue
                                        if getattr(w, "_screen", None) is cursor_screen:
                                            new_owner = w
                                            # Register with coordinator for future lookups
                                            self._coordinator.register_instance(w, cursor_screen)
                                            break
                                    except Exception:
                                        continue

                            if new_owner is None:
                                new_owner = owner or self

                            if owner is not None and owner is not new_owner:
                                try:
                                    hint = getattr(owner, "_ctrl_cursor_hint", None)
                                    if hint is not None:
                                        try:
                                            hint.cancel_animation()
                                        except Exception:
                                            pass
                                        hint.hide()
                                        try:
                                            hint.setOpacity(0.0)
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                                owner._ctrl_held = False

                            # Phase 5: Use coordinator for halo ownership
                            self._coordinator.set_halo_owner(new_owner)
                            try:
                                DisplayWidget._halo_owner = new_owner
                            except Exception:
                                pass
                            owner = new_owner

                    if owner is None:
                        owner = self

                    try:
                        local_pos = owner.mapFromGlobal(global_pos)
                    except Exception:
                        try:
                            local_pos = owner.rect().center()
                        except Exception:
                            local_pos = None

                    if local_pos is not None:
                        try:
                            # In hard-exit mode the halo should always be
                            # visible while the cursor is over an active
                            # DisplayWidget, without requiring Ctrl to be
                            # held. On the first move we trigger a fade-in;
                            # subsequent moves just reposition the halo.
                            #
                            # IMPORTANT: Check hard_exit on the OWNER widget, not self,
                            # because multiple DisplayWidgets install eventFilters and
                            # self might not be the widget under the cursor.
                            owner_hard_exit = False
                            try:
                                owner_hard_exit = owner._is_hard_exit_enabled()
                            except Exception:
                                owner_hard_exit = hard_exit  # fallback to self's value
                            
                            hint = getattr(owner, "_ctrl_cursor_hint", None)
                            halo_hidden = hint is None or not hint.isVisible()
                            
                            # In hard exit mode, always show halo on mouse move
                            # Phase 5: Use coordinator for halo ownership
                            if owner_hard_exit:
                                if self._coordinator.halo_owner is None or halo_hidden:
                                    # Fade in if halo owner not set OR if halo is hidden
                                    self._coordinator.set_halo_owner(owner)
                                    owner._show_ctrl_cursor_hint(local_pos, mode="fade_in")
                                else:
                                    # Just reposition
                                    owner._show_ctrl_cursor_hint(local_pos, mode="none")
                            elif ctrl_held:
                                # Ctrl mode - show/reposition halo
                                # If halo is hidden (e.g., after settings dialog), fade it in
                                if halo_hidden:
                                    self._coordinator.set_halo_owner(owner)
                                    try:
                                        DisplayWidget._halo_owner = owner
                                    except Exception:
                                        pass
                                    owner._show_ctrl_cursor_hint(local_pos, mode="fade_in")
                                else:
                                    owner._show_ctrl_cursor_hint(local_pos, mode="none")

                            # Forward halo hover position to the Reddit
                            # widget (if present) so it can manage its own
                            # delayed tooltips over post titles.
                            try:
                                rw = getattr(owner, "reddit_widget", None)
                                if rw is not None and rw.isVisible() and hasattr(rw, "handle_hover"):
                                    try:
                                        local_rw_pos = rw.mapFromGlobal(global_pos)
                                    except Exception:
                                        local_rw_pos = None
                                    if local_rw_pos is not None:
                                        rw.handle_hover(local_rw_pos, global_pos)
                            except Exception:
                                pass
                        except Exception:
                            pass
        except Exception:
            pass
        return super().eventFilter(watched, event)

    def get_screen_info(self) -> dict:
        """Get information about this display."""
        return {
            'screen_index': self.screen_index,
            'display_mode': str(self.display_mode),
            'size': f"{self.width()}x{self.height()}",
            'has_image': self.current_pixmap is not None,
            'has_error': self.error_message is not None,
            'transition_skip_count': self._transition_skip_count,
        }

    def get_transition_skip_count(self) -> int:
        """Return the number of image requests skipped due to active transitions."""
        return int(self._transition_skip_count)

    def has_running_transition(self) -> bool:
        # Delegate to TransitionController if available
        if self._transition_controller is not None:
            return self._transition_controller.is_running
        # Fallback to local state
        ct = getattr(self, "_current_transition", None)
        try:
            return bool(ct and ct.is_running())
        except Exception:
            return False

    def get_transition_snapshot(self) -> Dict[str, Any]:
        """Return lightweight metrics about the active transition, if any."""
        now_wall = time.time()
        snapshot: Dict[str, Any] = {
            "running": False,
            "name": None,
            "elapsed": None,
            "first_run": False,
            "idle_age": None,
            "last_transition": self._last_transition_name,
        }
        transition = self._current_transition
        if transition is not None:
            try:
                running = transition.is_running()
            except Exception:
                running = False
            if running:
                snapshot["running"] = True
                snapshot["name"] = self._current_transition_name
                snapshot["first_run"] = self._current_transition_first_run
                if self._current_transition_started_at > 0.0:
                    snapshot["elapsed"] = max(0.0, time.monotonic() - self._current_transition_started_at)
        if not snapshot["running"] and self._last_transition_finished_wall_ts > 0.0:
            snapshot["idle_age"] = max(0.0, now_wall - self._last_transition_finished_wall_ts)
        return snapshot
