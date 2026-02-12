"""Display widget for OpenGL/software rendered screensaver overlays."""
from collections import defaultdict
from typing import Optional, Iterable, Tuple, Callable, Dict, Any, List, Set
import logging
import time
import weakref
import sys
import ctypes
try:
    from OpenGL import GL  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    GL = None
from PySide6.QtWidgets import QWidget
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
    GL_OVERLAY_KEYS,
)
from core.events import EventSystem
from core.mc import is_mc_build
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
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Failed to describe pixmap: %s", e)
        return "Pixmap(?)"


# Toggle for MC window style experiments. Leave False to use the historical
# Qt.Tool behavior; switch to True when testing the splash-style flag.
MC_USE_SPLASH_FLAGS = True

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
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Failed to load user32: %s", e)
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
        self._transition_fallback_type: str = "Crossfade"
        self._transition_random_enabled: bool = False
        self._settings_listener_connected: bool = False
        self._settings_refresh_handler_ids: set[str] = set()
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
        
        # MC mode state - default to always on top for MC builds
        self._is_mc_build: bool = is_mc_build()
        self._always_on_top: bool = self._is_mc_build  # Default ON for MC builds
        if self._is_mc_build and self.settings_manager:
            try:
                # Load persisted value, defaulting to True for MC builds
                self._always_on_top = SettingsManager.to_bool(
                    self.settings_manager.get("mc.always_on_top", True), True
                )
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Failed to load always_on_top setting: %s", e)
                self._always_on_top = True  # Default ON for MC builds

        # Central ResourceManager wiring
        self._resource_manager: Optional[ResourceManager] = resource_manager
        if self._resource_manager is None:
            try:
                self._resource_manager = ResourceManager()
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Failed to create ResourceManager: %s", e)
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

        self._refresh_transition_state_from_settings()
        if self.settings_manager:
            try:
                self.settings_manager.settings_changed.connect(self._on_settings_value_changed)
                self._settings_listener_connected = True
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Failed to connect settings listener: %s", e)
            self._register_refresh_listeners()
        
        
        # ImagePresenter for centralized pixmap lifecycle (Phase 4 refactor)
        self._image_presenter: Optional[ImagePresenter] = None
        try:
            self._image_presenter = ImagePresenter(self, display_mode, 1.0)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Failed to create ImagePresenter: %s", e, exc_info=True)
        
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
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Failed to bind screen: %s", e)

        # Setup widget: frameless, always-on-top display window.
        # Use SplashScreen flag to ensure WM_APPCOMMAND messages are received
        # for media key passthrough (works for both screensaver and MC builds)
        self._mc_window_flag_mode: Optional[str] = None

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SplashScreen  # Ensures WM_APPCOMMAND reception
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
                self._mc_window_flag_mode = "splash"
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Failed to detect MC build: %s", e)

        self.setWindowFlags(flags)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setMouseTracking(True)
        # Phase 5: Use MultiMonitorCoordinator for focus ownership
        try:
            if self._coordinator.claim_focus(self):
                self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                try:
                    self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, False)
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Failed to set WindowDoesNotAcceptFocus=False: %s", e)
                try:
                    self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Failed to set WA_ShowWithoutActivating=False: %s", e)
            else:
                self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                try:
                    self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Failed to set WindowDoesNotAcceptFocus=True: %s", e)
                try:
                    self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Failed to set WA_ShowWithoutActivating=True: %s", e)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Failed to claim focus: %s", e)
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
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Failed to install event filter: %s", e)
        
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
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    def _resolve_display_target_fps(self, detected_hz: int, *, adaptive: bool = True) -> int:
        """Resolve per-display target FPS with optional adaptive ladder."""

        if detected_hz <= 0:
            detected_hz = 60
        if adaptive:
            if detected_hz <= 60:
                target = detected_hz
            elif detected_hz <= 120:
                target = max(30, detected_hz // 2)
            else:
                target = max(30, detected_hz // 3)
        else:
            target = detected_hz
        return min(240, max(30, target))
    
    def show_on_screen(self) -> None:
        """Delegates to rendering.display_setup."""
        from rendering.display_setup import show_on_screen
        show_on_screen(self)

    def _prewarm_context_menu(self) -> None:
        """Delegates to rendering.display_setup."""
        from rendering.display_setup import prewarm_context_menu
        prewarm_context_menu(self)

    def shutdown_render_pipeline(self, reason: str = "unspecified") -> None:
        """Stop transitions, animations, and render timers for this display."""
        if is_perf_metrics_enabled():
            try:
                logger.info(
                    "[PERF][DISPLAY] shutdown_render_pipeline screen=%s reason=%s state=%s",
                    self.screen_index,
                    reason,
                    self.describe_runtime_state(),
                )
            except Exception as exc:
                logger.debug("[DISPLAY_WIDGET] Failed to describe state during shutdown: %s", exc)

        # Stop transitions via controller or legacy path
        try:
            if self._transition_controller is not None:
                self._transition_controller.stop_current(reason=reason)
            elif self._current_transition:
                transition_to_stop = self._current_transition
                self._current_transition = None
                try:
                    transition_to_stop.stop()
                except Exception as exc:
                    logger.debug("[DISPLAY_WIDGET] Transition stop failed: %s", exc)
                try:
                    transition_to_stop.cleanup()
                except Exception as exc:
                    logger.debug("[DISPLAY_WIDGET] Transition cleanup failed: %s", exc)
        except Exception as exc:
            logger.debug("[DISPLAY_WIDGET] Transition shutdown failed: %s", exc)

        # Stop GL compositor render strategy
        comp = getattr(self, "_gl_compositor", None)
        if comp is not None and hasattr(comp, "stop_rendering"):
            try:
                comp.stop_rendering(reason=f"display:{reason}")
            except Exception as exc:
                logger.debug("[DISPLAY_WIDGET] GL compositor stop failed: %s", exc)

    def describe_runtime_state(self) -> dict:
        """Lightweight snapshot used during shutdown instrumentation."""
        try:
            transition_state = self._transition_controller.describe_state() if self._transition_controller else None
        except Exception as exc:
            logger.debug("[DISPLAY_WIDGET] describe_state transition failed: %s", exc)
            transition_state = None
        try:
            compositor_state = self._gl_compositor.describe_state() if self._gl_compositor else None
        except Exception as exc:
            logger.debug("[DISPLAY_WIDGET] describe_state compositor failed: %s", exc)
            compositor_state = None
        return {
            "screen_index": self.screen_index,
            "has_gl_compositor": bool(self._gl_compositor),
            "transition": transition_state,
            "render_strategy": compositor_state,
        }

    def _refresh_transition_state_from_settings(self) -> tuple[str, bool]:
        """Load transition type/random flag from settings and cache local state."""
        fallback = self._transition_fallback_type or "Crossfade"
        random_enabled = self._transition_random_enabled
        if not self.settings_manager:
            return fallback, random_enabled
        
        try:
            trans_cfg = self.settings_manager.get("transitions", {})
            if not isinstance(trans_cfg, dict):
                trans_cfg = {}
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Failed to read transitions config: %s", e)
            trans_cfg = {}
        
        next_type = trans_cfg.get("type", fallback) or fallback
        if not isinstance(next_type, str):
            next_type = fallback or "Crossfade"
        else:
            next_type = next_type.strip() or "Crossfade"
        
        next_random = SettingsManager.to_bool(trans_cfg.get("random_always", False), False)
        self._transition_fallback_type = next_type
        self._transition_random_enabled = next_random
        return next_type, next_random
    
    def _on_settings_value_changed(self, key: str, value) -> None:
        """Respond to SettingsManager updates."""
        try:
            if key == "transitions":
                menu_name, random_enabled = self._refresh_transition_state_from_settings()
                if self._context_menu is not None:
                    self._context_menu.update_transition_state(menu_name, random_enabled)
                return

            if key in {
                "display.hw_accel",
                "display.render_backend_mode",
            }:
                if is_verbose_logging():
                    logger.debug(
                        "[DISPLAY] Settings change detected key=%s value=%s",
                        key,
                        value,
                    )
                self._ensure_gl_compositor()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Failed to handle settings change: %s", e, exc_info=True)

    def _register_refresh_listeners(self) -> None:
        if not self.settings_manager:
            return
        try:
            handler_ids = {
                "display.hw_accel",
                "display.render_backend_mode",
            }
            for key in handler_ids:
                self.settings_manager.on_changed(key, self._on_specific_setting_changed)
            self._settings_refresh_handler_ids = handler_ids
        except Exception:
            logger.debug("[DISPLAY_WIDGET] Failed to register refresh listeners", exc_info=True)

    def _on_specific_setting_changed(self, new_value, old_value) -> None:
        # Placeholder required by on_changed signature; actual handling occurs via settings_changed signal.
        pass

    def _mark_all_overlays_ready(self, overlays: Iterable[str], stage: str) -> None:
        """Mark overlays as ready when running without GL support."""

        for attr_name in overlays:
            overlay = getattr(self, attr_name, None)
            if overlay is None:
                continue
            try:
                self._force_overlay_ready(overlay, stage=f"{stage}:{attr_name}", gl_available=False)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                name = overlay.objectName() or attr_name
                self.notify_overlay_ready(name, stage, status="software_ready", gl=False)

    def _handle_screen_change(self, screen) -> None:
        """Delegates to rendering.display_setup."""
        from rendering.display_setup import handle_screen_change
        handle_screen_change(self, screen)

    def _detect_refresh_rate(self) -> float:
        """Delegates to rendering.display_setup."""
        from rendering.display_setup import detect_refresh_rate
        return detect_refresh_rate(self)

    def _configure_refresh_rate_sync(self) -> None:
        """Delegates to rendering.display_setup."""
        from rendering.display_setup import configure_refresh_rate_sync
        configure_refresh_rate_sync(self)

    def _setup_dimming(self) -> None:
        """Delegates to rendering.display_setup."""
        from rendering.display_setup import setup_dimming
        setup_dimming(self)

    def _setup_spotify_widgets(self) -> None:
        """Delegates to rendering.display_setup."""
        from rendering.display_setup import setup_spotify_widgets
        setup_spotify_widgets(self)

    def _setup_pixel_shift(self) -> None:
        """Delegates to rendering.display_setup."""
        from rendering.display_setup import setup_pixel_shift
        setup_pixel_shift(self)

    def _is_hard_exit_enabled(self) -> bool:
        """Return True if hard-exit mode is enabled via settings.

        When enabled, mouse movement/clicks should not close the screensaver;
        only keyboard exit keys are honoured.
        """
        if not self.settings_manager:
            return False
        try:
            raw = self.settings_manager.get('input.hard_exit', False)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
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
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            return False
    
    def _setup_widgets(self) -> None:
        """Delegates to rendering.display_setup."""
        from rendering.display_setup import setup_widgets
        setup_widgets(self)

    def set_process_supervisor(self, supervisor) -> None:
        """Set the ProcessSupervisor on the WidgetManager and TransitionFactory.
        
        This enables FFTWorker integration for the Spotify visualizer and
        TransitionWorker integration for transition precomputation.
        """
        if self._widget_manager is not None:
            self._widget_manager.set_process_supervisor(supervisor)
        
        if self._transition_factory is not None:
            self._transition_factory.set_process_supervisor(supervisor)

    def _apply_widget_stacking(self, widgets_config: Dict[str, Any]) -> None:
        """Delegates to rendering.display_setup."""
        from rendering.display_setup import apply_widget_stacking
        apply_widget_stacking(self, widgets_config)

    def recalculate_stacking(self) -> None:
        """Recalculate widget stacking offsets."""
        try:
            widgets = self.settings_manager.get('widgets', {}) if self.settings_manager else {}
            self._apply_widget_stacking(widgets)
        except Exception:
            logger.debug("Failed to recalculate stacking", exc_info=True)

    def _on_animation_manager_ready(self, animation_manager) -> None:
        """Delegates to rendering.display_setup."""
        from rendering.display_setup import on_animation_manager_ready
        on_animation_manager_ready(self, animation_manager)

    def _ensure_overlay_stack(self, stage: str = "runtime") -> None:
        """Delegates to rendering.display_setup."""
        from rendering.display_setup import ensure_overlay_stack
        ensure_overlay_stack(self, stage)

    def _force_overlay_ready(self, overlay: QWidget, stage: str, *, gl_available: Optional[bool] = None) -> None:
        """Delegates to rendering.display_setup."""
        from rendering.display_setup import force_overlay_ready
        force_overlay_ready(self, overlay, stage, gl_available=gl_available)

    def _reuse_persistent_gl_overlays(self) -> None:
        """Delegates to rendering.display_setup."""
        from rendering.display_setup import reuse_persistent_gl_overlays
        reuse_persistent_gl_overlays(self)

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
        """Delegates to rendering.display_image_ops."""
        from rendering.display_image_ops import set_processed_image
        set_processed_image(self, processed_pixmap, original_pixmap, image_path)

    def _on_transition_finished(self, *args, **kwargs) -> None:
        """Delegates to rendering.display_image_ops."""
        from rendering.display_image_ops import _on_transition_finished
        _on_transition_finished(self, *args, **kwargs)

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
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
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

    def _position_mute_button(self) -> None:
        """Position mute button relative to media widget."""
        mute_btn = getattr(self, "mute_button_widget", None)
        if mute_btn is not None and hasattr(mute_btn, 'update_position'):
            try:
                mute_btn.sync_visibility_with_anchor()
                mute_btn.update_position()
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    def push_spotify_visualizer_frame(self, **kwargs):
        """Delegates to rendering.display_image_ops."""
        from rendering.display_image_ops import push_spotify_visualizer_frame
        return push_spotify_visualizer_frame(self, **kwargs)

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
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        try:
            self._position_spotify_visualizer()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        try:
            self._position_spotify_volume()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    def _init_renderer_backend(self) -> None:
        """Delegates to rendering.display_gl_init."""
        from rendering.display_gl_init import init_renderer_backend
        init_renderer_backend(self)

    def _build_surface_descriptor(self) -> Optional[SurfaceDescriptor]:
        """Delegates to rendering.display_gl_init."""
        from rendering.display_gl_init import build_surface_descriptor
        return build_surface_descriptor(self)

    def _ensure_render_surface(self) -> bool:
        """Delegates to rendering.display_gl_init."""
        from rendering.display_gl_init import ensure_render_surface
        return ensure_render_surface(self)

    def _ensure_gl_compositor(self) -> bool:
        """Delegates to rendering.display_gl_init."""
        from rendering.display_gl_init import ensure_gl_compositor
        return ensure_gl_compositor(self)

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

    def _cleanup_widget(self) -> None:
        """Delegates to rendering.display_gl_init."""
        from rendering.display_gl_init import cleanup_widget
        cleanup_widget(self)

    def _on_destroyed(self, *_args) -> None:
        """Ensure active transitions are stopped when the widget is destroyed."""
        # NOTE: Deferred Reddit URL opening is now handled by DisplayManager.cleanup()
        # to ensure it happens AFTER windows are hidden but BEFORE QApplication.quit()
        if self.settings_manager and self._settings_listener_connected:
            try:
                self.settings_manager.settings_changed.disconnect(self._on_settings_value_changed)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            finally:
                self._settings_listener_connected = False
        
        # Phase 5: Unregister from MultiMonitorCoordinator
        if self._screen is not None:
            try:
                self._coordinator.unregister_instance(self, self._screen)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        
        # Phase 5: Release focus and event filter ownership via coordinator
        try:
            self._coordinator.release_focus(self)
            self._coordinator.uninstall_event_filter(self)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        
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
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            self._ctrl_cursor_hint = None
        
        # Stop and clean up any active transition via TransitionController
        try:
            if self._transition_controller is not None:
                self._transition_controller.stop_current()
            elif self._current_transition:
                try:
                    self._current_transition.stop()
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                try:
                    self._current_transition.cleanup()
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
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
        self.shutdown_render_pipeline("clear")
        self.current_pixmap = None
        self.previous_pixmap = None

        # Reset state to defaults
        self._seed_pixmap = None
        self._last_pixmap_seed_ts = None
        self._pre_raise_log_emitted = False
        self._base_fallback_paint_logged = False
        self.error_message = None
        self._current_transition = None

        # Ensure overlays are hidden to prevent residual frames during exit
        try:
            hide_all_overlays(self)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

        # Hide and destroy cursor halo (top-level window that persists independently)
        # Must hide immediately and process events to ensure it's gone before settings dialog
        try:
            if self._ctrl_cursor_hint is not None:
                self._ctrl_cursor_hint.hide()
                self._ctrl_cursor_hint.close()
                self._ctrl_cursor_hint.deleteLater()
                self._ctrl_cursor_hint = None
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            self._ctrl_cursor_hint = None

        # Reset global Ctrl state to prevent halo from reappearing
        try:
            from rendering.multi_monitor_coordinator import get_coordinator
            coordinator = get_coordinator()
            coordinator.set_ctrl_held(False)
            coordinator.clear_halo_owner()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

        self.update()

    def reset_after_settings(self) -> None:
        try:
            self.setUpdatesEnabled(False)
            self._updates_blocked_until_seed = True
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            self._self._updates_blocked_until_seed = False
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
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

        # Thread-safe check: if any legacy overlay is ready (GL initialized +
        # first frame drawn), let it handle painting. This path is only used
        # when the compositor is not active.
        try:
            if any_overlay_ready_for_display(self):
                return
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

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
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
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
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
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
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        
        # Fallback: run starter immediately if no WidgetManager
        try:
            starter()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    def _start_overlay_fades(self) -> None:
        """Delegates to rendering.display_overlays."""
        from rendering.display_overlays import start_overlay_fades
        start_overlay_fades(self)

    def _run_spotify_secondary_fades(self) -> None:
        """Delegates to rendering.display_overlays."""
        from rendering.display_overlays import run_spotify_secondary_fades
        run_spotify_secondary_fades(self)

    def register_spotify_secondary_fade(self, starter) -> None:
        """Delegates to rendering.display_overlays."""
        from rendering.display_overlays import register_spotify_secondary_fade
        register_spotify_secondary_fade(self, starter)

    def get_overlay_stage_counts(self) -> dict[str, int]:
        """Return snapshot of overlay readiness counts (for diagnostics/tests)."""
        return dict(self._overlay_stage_counts)

    def _ensure_ctrl_cursor_hint(self) -> None:
        """Delegates to rendering.display_input."""
        from rendering.display_input import ensure_ctrl_cursor_hint
        ensure_ctrl_cursor_hint(self)

    def _show_ctrl_cursor_hint(self, pos, mode: str = "none") -> None:
        """Delegates to rendering.display_input."""
        from rendering.display_input import show_ctrl_cursor_hint
        show_ctrl_cursor_hint(self, pos, mode)

    def _hide_ctrl_cursor_hint(self, *, immediate: bool = False) -> None:
        """Delegates to rendering.display_input."""
        from rendering.display_input import hide_ctrl_cursor_hint
        hide_ctrl_cursor_hint(self, immediate=immediate)

    def _reset_halo_inactivity_timer(self) -> None:
        """Delegates to rendering.display_input."""
        from rendering.display_input import reset_halo_inactivity_timer
        reset_halo_inactivity_timer(self)

    def _cancel_halo_inactivity_timer(self) -> None:
        """Delegates to rendering.display_input."""
        from rendering.display_input import cancel_halo_inactivity_timer
        cancel_halo_inactivity_timer(self)

    def _on_halo_inactivity_timeout(self) -> None:
        """Delegates to rendering.display_input."""
        from rendering.display_input import on_halo_inactivity_timeout
        on_halo_inactivity_timeout(self)

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self._coordinator.release_focus(self)
            self._coordinator.uninstall_event_filter(self)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        
        
        # Cleanup widgets via lifecycle system (Dec 2025)
        if self._widget_manager is not None:
            try:
                self._widget_manager.cleanup()
                logger.debug("[LIFECYCLE] WidgetManager cleanup complete")
            except Exception:
                logger.debug("[LIFECYCLE] WidgetManager cleanup failed", exc_info=True)
        
        super().closeEvent(event)

    def _on_destroyed(self) -> None:
        """Delegates to rendering.display_gl_init."""
        from rendering.display_gl_init import on_destroyed
        on_destroyed(self)

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
    
    def mousePressEvent(self, event) -> None:
        """Delegates to rendering.display_input."""
        from rendering.display_input import handle_mousePressEvent
        handle_mousePressEvent(self, event)

    def mouseMoveEvent(self, event) -> None:
        """Delegates to rendering.display_input."""
        from rendering.display_input import handle_mouseMoveEvent
        handle_mouseMoveEvent(self, event)

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
        """Delegates to rendering.display_context_menu."""
        from rendering.display_context_menu import show_context_menu
        show_context_menu(self, global_pos)

    def _on_context_transition_selected(self, name: str) -> None:
        """Delegates to rendering.display_context_menu."""
        from rendering.display_context_menu import on_context_transition_selected
        on_context_transition_selected(self, name)

    def _on_context_dimming_toggled(self, enabled: bool) -> None:
        """Delegates to rendering.display_context_menu."""
        from rendering.display_context_menu import on_context_dimming_toggled
        on_context_dimming_toggled(self, enabled)

    def _on_context_hard_exit_toggled(self, enabled: bool) -> None:
        """Delegates to rendering.display_context_menu."""
        from rendering.display_context_menu import on_context_hard_exit_toggled
        on_context_hard_exit_toggled(self, enabled)

    def _on_context_always_on_top_toggled(self, on_top: bool) -> None:
        """Delegates to rendering.display_context_menu."""
        from rendering.display_context_menu import on_context_always_on_top_toggled
        on_context_always_on_top_toggled(self, on_top)

    def _on_context_exit_requested(self) -> None:
        """Delegates to rendering.display_context_menu."""
        from rendering.display_context_menu import on_context_exit_requested
        on_context_exit_requested(self)

    def _on_input_exit_requested(self) -> None:
        """Delegates to rendering.display_context_menu."""
        from rendering.display_context_menu import on_input_exit_requested
        on_input_exit_requested(self)

    def _on_context_menu_requested(self, global_pos: QPoint) -> None:
        """Delegates to rendering.display_context_menu."""
        from rendering.display_context_menu import on_context_menu_requested
        on_context_menu_requested(self, global_pos)

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
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

        super().focusOutEvent(event)

    def _debug_window_state(self, label: str, *, extra: str = "") -> None:
        """Delegates to rendering.display_overlays."""
        from rendering.display_overlays import debug_window_state
        debug_window_state(self, label, extra=extra)

    def _perform_activation_refresh(self, reason: str) -> None:
        """Delegates to rendering.display_overlays."""
        from rendering.display_overlays import perform_activation_refresh
        perform_activation_refresh(self, reason)

    def _schedule_effect_invalidation(self, reason: str) -> None:
        try:
            if getattr(self, "_pending_effect_invalidation", False):
                return
            self._pending_effect_invalidation = True
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            return

        def _run() -> None:
            try:
                self._invalidate_overlay_effects(reason)
            finally:
                try:
                    self._pending_effect_invalidation = False
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

        try:
            tm = getattr(self, "_thread_manager", None)
            if tm is not None:
                tm.single_shot(0, _run)
            else:
                ThreadManager.single_shot(0, _run)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            _run()

    def _invalidate_overlay_effects(self, reason: str) -> None:
        """Delegate effect invalidation to WidgetManager (Phase E refactor)."""
        if self._widget_manager is not None:
            try:
                self._widget_manager.invalidate_overlay_effects(reason)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    def focusInEvent(self, event: QFocusEvent) -> None:  # type: ignore[override]
        try:
            self._debug_window_state("focusInEvent")
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        try:
            self._invalidate_overlay_effects("focus_in")
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        super().focusInEvent(event)

    def changeEvent(self, event: QEvent) -> None:  # type: ignore[override]
        try:
            if event is not None:
                self._debug_window_state(f"changeEvent:{int(event.type())}")
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        super().changeEvent(event)

    def nativeEvent(self, eventType, message):  # type: ignore[override]
        """Delegates to rendering.display_native_events."""
        from rendering.display_native_events import handle_nativeEvent
        return handle_nativeEvent(self, eventType, message)

    def _extract_win_msg(self, raw_message):
        """Delegates to rendering.display_native_events."""
        from rendering.display_native_events import extract_win_msg
        return extract_win_msg(self, raw_message)

    def _handle_win_appcommand(self, msg) -> tuple[bool, int]:
        """Delegates to rendering.display_native_events."""
        from rendering.display_native_events import handle_win_appcommand
        return handle_win_appcommand(self, msg)

    def _dispatch_appcommand_for_feedback(self, msg) -> None:
        """Delegates to rendering.display_native_events."""
        from rendering.display_native_events import dispatch_appcommand_for_feedback
        dispatch_appcommand_for_feedback(self, msg)

    def _dispatch_appcommand(self, command: int, command_name: str) -> bool:
        """Delegates to rendering.display_native_events."""
        from rendering.display_native_events import dispatch_appcommand
        return dispatch_appcommand(self, command, command_name)

    def eventFilter(self, watched, event):  # type: ignore[override]
        """Delegates to rendering.display_native_events."""
        from rendering.display_native_events import handle_eventFilter
        return handle_eventFilter(self, watched, event)

    def _recover_from_event_filter_memory_error(self, coordinator: Optional["MultiMonitorCoordinator"]) -> None:
        """Delegates to rendering.display_native_events."""
        from rendering.display_native_events import recover_from_event_filter_memory_error
        recover_from_event_filter_memory_error(self, coordinator)

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
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
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
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
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
