"""Display widget for OpenGL/software rendered screensaver overlays."""
from collections import defaultdict
from typing import Optional, Iterable, Tuple, Callable, Dict, Any, List
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
from PySide6.QtWidgets import QWidget, QApplication, QGraphicsDropShadowEffect, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QEvent, QPoint
from PySide6.QtGui import (
    QPixmap,
    QPainter,
    QKeyEvent,
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
from widgets.clock_widget import ClockWidget, TimeFormat, ClockPosition
from widgets.weather_widget import WeatherWidget, WeatherPosition
from widgets.media_widget import MediaWidget, MediaPosition
from widgets.reddit_widget import RedditWidget, RedditPosition
from widgets.pixel_shift_manager import PixelShiftManager
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
from widgets.spotify_volume_widget import SpotifyVolumeWidget
from widgets.shadow_utils import apply_widget_shadow
from widgets.context_menu import ScreensaverContextMenu
from widgets.cursor_halo import CursorHaloWidget
from rendering.widget_setup import parse_color_to_qcolor
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


TRANSITION_WATCHDOG_DEFAULT_SEC = 6.0
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
    
    # Global Ctrl-held interaction mode flag shared across all display instances.
    # This ensures that holding Ctrl on any screen suppresses mouse-based exit
    # (movement/click) on all displays simultaneously.
    _global_ctrl_held: bool = False
    _halo_owner: Optional["DisplayWidget"] = None
    
    # PERF: Single eventFilter for all DisplayWidgets to avoid redundant processing
    _event_filter_installed: bool = False
    _event_filter_owner: Optional["DisplayWidget"] = None
    
    # PERF: Cache of DisplayWidget instances by screen to avoid iterating topLevelWidgets
    _instances_by_screen: Dict[Any, "DisplayWidget"] = {}

    # On Windows, switching activation between multiple full-screen top-level
    # windows can change the compositor/backing-store path for the *inactive*
    # window. That can make semi-transparent overlay backgrounds appear much
    # more opaque because they end up blending against a stale/darker buffer.
    # To avoid this, only one DisplayWidget is permitted to accept focus.
    _focus_owner: Optional["DisplayWidget"] = None
    
    @classmethod
    def get_all_instances(cls) -> List["DisplayWidget"]:
        """Get all DisplayWidget instances from the cache.
        
        PERF: Uses cached instances instead of iterating QApplication.topLevelWidgets().
        Returns a copy of the values to avoid modification during iteration.
        """
        return list(cls._instances_by_screen.values())

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
        self._pending_reddit_url: Optional[str] = None  # URL to open when exiting (hard-exit mode)
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

        # Setup widget: frameless, always-on-top display window. For the MC
        # build (SRPSS_MC), also mark the window as a tool window so it does
        # not appear in the taskbar or standard Alt+Tab.
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        try:
            exe0 = str(getattr(sys, "argv", [""])[0]).lower()
            if "srpss_mc" in exe0 or "srpss mc" in exe0 or "main_mc.py" in exe0:
                flags |= Qt.WindowType.Tool
        except Exception:
            pass

        self.setWindowFlags(flags)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setMouseTracking(True)
        try:
            if DisplayWidget._focus_owner is None:
                DisplayWidget._focus_owner = self

            if DisplayWidget._focus_owner is self:
                self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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
        try:
            app = QGuiApplication.instance()
            if app is not None and not DisplayWidget._event_filter_installed:
                app.installEventFilter(self)
                DisplayWidget._event_filter_installed = True
                DisplayWidget._event_filter_owner = self
        except Exception:
            pass
        
        # Set black background
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.GlobalColor.black)
        self.setPalette(palette)
        
        # PERF: Register in class-level cache for fast screen-based lookup
        if self._screen is not None:
            DisplayWidget._instances_by_screen[self._screen] = self
        
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
            self.activateWindow()
            try:
                self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
            except Exception:
                try:
                    self.setFocus()
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
        """Setup overlay widgets (clock, weather) based on settings."""
        if not self.settings_manager:
            logger.warning("No settings_manager provided - widgets will not be created")
            return
        
        logger.debug(f"Setting up overlay widgets for screen {self.screen_index}")
        
        widgets = self.settings_manager.get('widgets', {})
        base_clock_settings = widgets.get('clock', {}) if isinstance(widgets, dict) else {}

        # Global widget shadow configuration shared by all overlay widgets.
        shadows_config = widgets.get('shadows', {}) if isinstance(widgets, dict) else {}

        # Reset per-display overlay fade coordination. This is only used for
        # the initial widget fade-ins so that overlays like weather, media
        # and Reddit can appear together. We also precompute which overlays
        # are expected on this display *before* any of them start so that the
        # coordinator never starts early with only the first widget.
        self._overlay_fade_expected = set()
        self._overlay_fade_pending = {}
        self._overlay_fade_started = False
        if self._overlay_fade_timeout is not None:
            try:
                self._overlay_fade_timeout.stop()
                self._overlay_fade_timeout.deleteLater()
            except Exception:
                pass
            self._overlay_fade_timeout = None

        # Secondary fade starters for Spotify widgets (volume slider and
        # visualiser card). These are kicked off shortly after the primary
        # overlay fades begin so they never block the main group but still
        # feel temporally connected.
        self._spotify_secondary_fade_starters = []

        widgets_map = widgets if isinstance(widgets, dict) else {}

        # Background Dimming - now handled by GL compositor for proper compositing.
        # The widget-based DimmingOverlay is kept for fallback but not used when
        # the GL compositor is active.
        # Settings are stored with dot notation (accessibility.dimming.enabled)
        dimming_enabled = SettingsManager.to_bool(
            self.settings_manager.get('accessibility.dimming.enabled', False), False
        )
        try:
            dimming_opacity = int(self.settings_manager.get('accessibility.dimming.opacity', 30))
            dimming_opacity = max(10, min(90, dimming_opacity))
        except (ValueError, TypeError):
            dimming_opacity = 30
        
        # Store dimming state for use by GL compositor
        self._dimming_enabled = dimming_enabled
        self._dimming_opacity = dimming_opacity / 100.0  # Convert to 0.0-1.0
        
        # Configure GL compositor dimming if available
        comp = getattr(self, "_gl_compositor", None)
        if comp is not None and hasattr(comp, "set_dimming"):
            comp.set_dimming(dimming_enabled, self._dimming_opacity)
            logger.debug("GL compositor dimming: enabled=%s, opacity=%d%%", dimming_enabled, dimming_opacity)
        
        # NOTE: Widget-based DimmingOverlay removed - GL compositor handles dimming now

        # Spotify visualizer configuration is used later when wiring the
        # widget. When enabled for this display, the visualiser card
        # participates in the primary overlay fade under the
        # "spotify_visualizer" overlay name so its card/shadow enter with
        # the main group.
        spotify_vis_settings = widgets_map.get('spotify_visualizer', {}) if isinstance(widgets_map, dict) else {}
        spotify_vis_enabled = SettingsManager.to_bool(spotify_vis_settings.get('enabled', False), False)

        weather_settings = widgets_map.get('weather', {}) if isinstance(widgets_map, dict) else {}
        weather_enabled = SettingsManager.to_bool(weather_settings.get('enabled', False), False)
        weather_monitor_sel = weather_settings.get('monitor', 'ALL')
        try:
            weather_show_on_this = (weather_monitor_sel == 'ALL') or (
                int(weather_monitor_sel) == (self.screen_index + 1)
            )
        except Exception:
            weather_show_on_this = False
            logger.debug(
                "Weather widget monitor setting invalid for screen %s: %r (gated off for fade sync)",
                self.screen_index,
                weather_monitor_sel,
            )

        reddit_settings = widgets_map.get('reddit', {}) if isinstance(widgets_map, dict) else {}
        reddit_enabled = SettingsManager.to_bool(reddit_settings.get('enabled', False), False)
        reddit_monitor_sel = reddit_settings.get('monitor', 'ALL')
        try:
            reddit_show_on_this = (reddit_monitor_sel == 'ALL') or (
                int(reddit_monitor_sel) == (self.screen_index + 1)
            )
        except Exception:
            reddit_show_on_this = False
            logger.debug(
                "Reddit widget monitor setting invalid for screen %s: %r (gated off for fade sync)",
                self.screen_index,
                reddit_monitor_sel,
            )

        media_settings = widgets_map.get('media', {}) if isinstance(widgets_map, dict) else {}
        media_enabled = SettingsManager.to_bool(media_settings.get('enabled', False), False)
        media_monitor_sel = media_settings.get('monitor', 'ALL')
        try:
            media_show_on_this = (media_monitor_sel == 'ALL') or (
                int(media_monitor_sel) == (self.screen_index + 1)
            )
        except Exception:
            media_show_on_this = False
            logger.debug(
                "Media widget monitor setting invalid for screen %s: %r (gated off for fade sync)",
                self.screen_index,
                media_monitor_sel,
            )

        self._overlay_fade_expected = set()
        if weather_enabled and weather_show_on_this:
            self._overlay_fade_expected.add("weather")
        if reddit_enabled and reddit_show_on_this:
            self._overlay_fade_expected.add("reddit")
        if media_enabled and media_show_on_this:
            self._overlay_fade_expected.add("media")
        # Spotify visualiser card is anchored to the media widget; only
        # participate in the primary fade when both the media widget and
        # Spotify visualiser are enabled on this display.
        if spotify_vis_enabled and media_enabled and media_show_on_this:
            self._overlay_fade_expected.add("spotify_visualizer")

        position_map = {
            'Top Left': ClockPosition.TOP_LEFT,
            'Top Right': ClockPosition.TOP_RIGHT,
            'Top Center': ClockPosition.TOP_CENTER,
            'Center': ClockPosition.CENTER,
            'Bottom Left': ClockPosition.BOTTOM_LEFT,
            'Bottom Right': ClockPosition.BOTTOM_RIGHT,
            'Bottom Center': ClockPosition.BOTTOM_CENTER,
        }

        def _resolve_clock_style(key: str, default, clock_settings: dict, settings_key: str):
            """Resolve a style value for a clock, with forced inheritance for Clock 2/3.

            For the primary clock, values come from its own settings or the provided default.
            For Clock 2/3, style and position always come from the main clock's settings so they
            visually match Clock 1, regardless of any stray per-clock style keys.
            """
            # Primary clock: use its own style value when present.
            if settings_key == 'clock':
                if isinstance(clock_settings, dict) and key in clock_settings:
                    return clock_settings[key]
                return default

            # Secondary clocks (clock2/clock3): force inheritance from main clock style.
            if isinstance(base_clock_settings, dict) and key in base_clock_settings:
                return base_clock_settings[key]
            return default

        def _create_clock_widget(settings_key: str, attr_name: str, default_position: str, default_font_size: int) -> None:
            clock_settings = widgets.get(settings_key, {}) if isinstance(widgets, dict) else {}
            clock_enabled = SettingsManager.to_bool(clock_settings.get('enabled', False), False)
            clock_monitor_sel = clock_settings.get('monitor', 'ALL')
            try:
                show_on_this = (clock_monitor_sel == 'ALL') or (int(clock_monitor_sel) == (self.screen_index + 1))
            except Exception:
                show_on_this = True

            existing = getattr(self, attr_name, None)
            if not (clock_enabled and show_on_this):
                if existing is not None:
                    try:
                        existing.stop()
                        existing.hide()
                    except Exception:
                        pass
                setattr(self, attr_name, None)
                logger.debug("%s widget disabled in settings", settings_key)
                return

            # Clock overlays participate in per-display fade coordination so
            # that even a single clock on a secondary display fades in using
            # the shared overlay mechanism.
            try:
                self._overlay_fade_expected.add(settings_key)
            except Exception:
                self._overlay_fade_expected = {settings_key}

            raw_format = _resolve_clock_style('format', '12h', clock_settings, settings_key)
            time_format = TimeFormat.TWELVE_HOUR if raw_format == '12h' else TimeFormat.TWENTY_FOUR_HOUR

            base_position_default = default_position
            position_str = _resolve_clock_style('position', base_position_default, clock_settings, settings_key)

            show_seconds_val = _resolve_clock_style('show_seconds', False, clock_settings, settings_key)
            show_seconds = SettingsManager.to_bool(show_seconds_val, False)

            # Timezone is independent per clock; do not inherit.
            timezone_str = clock_settings.get('timezone', 'local')

            show_tz_val = _resolve_clock_style('show_timezone', False, clock_settings, settings_key)
            show_timezone = SettingsManager.to_bool(show_tz_val, False)

            font_size = _resolve_clock_style('font_size', default_font_size, clock_settings, settings_key)
            margin = _resolve_clock_style('margin', 20, clock_settings, settings_key)
            color = _resolve_clock_style('color', [255, 255, 255, 230], clock_settings, settings_key)
            bg_color_data = _resolve_clock_style('bg_color', [64, 64, 64, 255], clock_settings, settings_key)
            border_color_data = _resolve_clock_style(
                'border_color', [128, 128, 128, 255], clock_settings, settings_key
            )
            border_opacity_val = _resolve_clock_style(
                'border_opacity', 0.8, clock_settings, settings_key
            )

            position = position_map.get(position_str, position_map.get(default_position, ClockPosition.TOP_RIGHT))

            try:
                clock = ClockWidget(self, time_format, position, show_seconds, timezone_str, show_timezone)

                font_family = _resolve_clock_style('font_family', 'Segoe UI', clock_settings, settings_key)
                if hasattr(clock, 'set_font_family'):
                    clock.set_font_family(font_family)

                clock.set_font_size(font_size)
                clock.set_margin(margin)

                qcolor = parse_color_to_qcolor(color)
                if qcolor:
                    clock.set_text_color(qcolor)

                # Background color (inherits from main clock for clock2/clock3)
                bg_qcolor = parse_color_to_qcolor(bg_color_data)
                if bg_qcolor and hasattr(clock, "set_background_color"):
                    clock.set_background_color(bg_qcolor)

                # Background border customization (inherits from main clock for clock2/clock3)
                try:
                    bo = float(border_opacity_val)
                except Exception:
                    bo = 0.8
                border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=bo)
                if border_qcolor and hasattr(clock, "set_background_border"):
                    clock.set_background_border(2, border_qcolor)

                show_bg_val = _resolve_clock_style('show_background', False, clock_settings, settings_key)
                show_background = SettingsManager.to_bool(show_bg_val, False)
                clock.set_show_background(show_background)

                bg_opacity = _resolve_clock_style('bg_opacity', 0.9, clock_settings, settings_key)
                clock.set_background_opacity(bg_opacity)

                # Analogue/digital display style and numerals configuration.
                try:
                    display_mode_val = _resolve_clock_style('display_mode', 'digital', clock_settings, settings_key)
                    if hasattr(clock, 'set_display_mode'):
                        clock.set_display_mode(display_mode_val)
                except Exception:
                    logger.debug("Failed to apply display_mode for %s", settings_key, exc_info=True)

                try:
                    show_numerals_val = _resolve_clock_style('show_numerals', True, clock_settings, settings_key)
                    show_numerals = SettingsManager.to_bool(show_numerals_val, True)
                    if hasattr(clock, 'set_show_numerals'):
                        clock.set_show_numerals(show_numerals)
                except Exception:
                    logger.debug("Failed to apply show_numerals for %s", settings_key, exc_info=True)

                # Analogue face/hand shadow toggle (main clock style only).
                try:
                    analog_shadow_val = _resolve_clock_style('analog_face_shadow', True, clock_settings, settings_key)
                    analog_shadow = SettingsManager.to_bool(analog_shadow_val, True)
                    if hasattr(clock, 'set_analog_face_shadow'):
                        clock.set_analog_face_shadow(analog_shadow)
                except Exception:
                    logger.debug("Failed to apply analog_face_shadow for %s", settings_key, exc_info=True)

                # Global widget drop shadow (shared config for all clocks). Where
                # the clock supports coordinated fade-in, we hand off the
                # configuration and let the widget attach the shadow once its
                # opacity fade has completed.
                try:
                    if hasattr(clock, "set_shadow_config"):
                        clock.set_shadow_config(shadows_config)
                    else:
                        apply_widget_shadow(clock, shadows_config, has_background_frame=show_background)
                except Exception:
                    logger.debug("Failed to apply widget shadow to %s", settings_key, exc_info=True)

                # Provide a stable overlay name so ClockWidget can register
                # with DisplayWidget.request_overlay_fade_sync using a
                # descriptive identifier ("clock", "clock2", "clock3").
                try:
                    if hasattr(clock, "set_overlay_name"):
                        clock.set_overlay_name(settings_key)
                except Exception:
                    logger.debug("Failed to set overlay name for %s", settings_key, exc_info=True)

                setattr(self, attr_name, clock)

                clock.raise_()
                clock.start()
                logger.info(
                    "✅ %s widget started: %s, %s, font=%spx, seconds=%s",
                    settings_key,
                    position_str,
                    time_format.value,
                    font_size,
                    show_seconds,
                )
            except Exception as e:
                logger.error("Failed to create/configure %s widget: %s", settings_key, e, exc_info=True)

        _create_clock_widget('clock', 'clock_widget', 'Top Right', 48)
        _create_clock_widget('clock2', 'clock2_widget', 'Bottom Right', 32)
        _create_clock_widget('clock3', 'clock3_widget', 'Bottom Left', 32)

        # Weather widget (uses precomputed weather_settings / weather_enabled /
        # weather_show_on_this from the fade coordination setup above).
        if weather_enabled and weather_show_on_this:
            try:
                self._overlay_fade_expected.add("weather")
            except Exception:
                self._overlay_fade_expected = {"weather"}
            # Canonical defaults for missing keys mirror
            # SettingsManager._set_defaults() / get_widget_defaults('weather').
            position_str = weather_settings.get('position', 'Top Left')
            # Placeholder location is "New York"; WidgetsTab will perform a
            # one-shot timezone-based override when appropriate.
            location = weather_settings.get('location', 'New York')
            font_size = weather_settings.get('font_size', 24)
            color = weather_settings.get('color', [255, 255, 255, 230])
            
            # Map position string to enum
            weather_position_map = {
                'Top Left': WeatherPosition.TOP_LEFT,
                'Top Right': WeatherPosition.TOP_RIGHT,
                'Bottom Left': WeatherPosition.BOTTOM_LEFT,
                'Bottom Right': WeatherPosition.BOTTOM_RIGHT,
            }
            position = weather_position_map.get(position_str, WeatherPosition.TOP_LEFT)
            
            try:
                self.weather_widget = WeatherWidget(self, location, position)
                # Inject ThreadManager if available so weather fetches use central IO pool
                if self._thread_manager is not None and hasattr(self.weather_widget, "set_thread_manager"):
                    try:
                        self.weather_widget.set_thread_manager(self._thread_manager)
                    except Exception:
                        pass

                # Set font family if specified
                font_family = weather_settings.get('font_family', 'Segoe UI')
                if hasattr(self.weather_widget, 'set_font_family'):
                    self.weather_widget.set_font_family(font_family)
                
                self.weather_widget.set_font_size(font_size)
                
                # Convert color arrays to QColor
                qcolor = parse_color_to_qcolor(color)
                if qcolor:
                    self.weather_widget.set_text_color(qcolor)

                # Background/frame customization
                show_background = SettingsManager.to_bool(
                    weather_settings.get('show_background', True), True
                )
                self.weather_widget.set_show_background(show_background)

                # Background color (RGB+alpha), default matches WeatherWidget internal default
                bg_color_data = weather_settings.get('bg_color', [35, 35, 35, 255])
                bg_qcolor = parse_color_to_qcolor(bg_color_data)
                if bg_qcolor:
                    self.weather_widget.set_background_color(bg_qcolor)

                # Background opacity (scales alpha regardless of bg_color alpha)
                bg_opacity = weather_settings.get('bg_opacity', 0.7)
                self.weather_widget.set_background_opacity(bg_opacity)

                # Border color and opacity (independent from background opacity)
                border_color_data = weather_settings.get('border_color', [255, 255, 255, 255])
                border_opacity = weather_settings.get('border_opacity', 1.0)
                try:
                    bo = float(border_opacity)
                except Exception:
                    bo = 1.0
                border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=bo)
                if border_qcolor:
                    self.weather_widget.set_background_border(2, border_qcolor)

                # Optional forecast line
                show_forecast = SettingsManager.to_bool(
                    weather_settings.get('show_forecast', False), False
                )
                self.weather_widget.set_show_forecast(show_forecast)

                # Global widget drop shadow (shared config for all widgets).
                #
                # WeatherWidget performs a fade-in using a temporary
                # QGraphicsOpacityEffect, then attaches the drop shadow
                # afterwards using the shared configuration passed in here.
                try:
                    if hasattr(self.weather_widget, "set_shadow_config"):
                        self.weather_widget.set_shadow_config(shadows_config)
                    else:
                        apply_widget_shadow(self.weather_widget, shadows_config, has_background_frame=show_background)
                except Exception:
                    logger.debug("Failed to configure widget shadow for weather widget", exc_info=True)

                self.weather_widget.raise_()
                self.weather_widget.start()
                logger.info(f"✅ Weather widget started: {location}, {position_str}, font={font_size}px")
            except Exception as e:
                logger.error(f"Failed to create/configure weather widget: {e}", exc_info=True)
        else:
            logger.debug("Weather widget disabled in settings")

        # Reddit widget (uses precomputed reddit_settings / reddit_enabled /
        # reddit_show_on_this from the fade coordination setup above).
        try:
            exit_on_click_val = reddit_settings.get('exit_on_click', True)
            self._reddit_exit_on_click = SettingsManager.to_bool(exit_on_click_val, True)
        except Exception:
            self._reddit_exit_on_click = True
        # reddit_monitor_sel/reddit_show_on_this are already computed above

        existing_reddit = getattr(self, 'reddit_widget', None)
        if not (reddit_enabled and reddit_show_on_this):
            if existing_reddit is not None:
                try:
                    existing_reddit.stop()
                    existing_reddit.hide()
                except Exception:
                    pass
            self.reddit_widget = None
            logger.debug(
                "Reddit widget disabled in settings (screen=%s, enabled=%s, show_on_this=%s, monitor_sel=%r)",
                self.screen_index,
                reddit_enabled,
                reddit_show_on_this,
                reddit_monitor_sel,
            )
        else:
            try:
                self._overlay_fade_expected.add("reddit")
            except Exception:
                self._overlay_fade_expected = {"reddit"}
            position_str = reddit_settings.get('position', 'Bottom Right')
            subreddit = reddit_settings.get('subreddit', 'wallpapers') or 'wallpapers'
            font_size = reddit_settings.get('font_size', 14)
            margin = reddit_settings.get('margin', 20)
            color = reddit_settings.get('color', [255, 255, 255, 230])
            bg_color_data = reddit_settings.get('bg_color', [35, 35, 35, 255])
            border_color_data = reddit_settings.get('border_color', [255, 255, 255, 255])
            border_opacity = reddit_settings.get('border_opacity', 1.0)
            show_background = SettingsManager.to_bool(reddit_settings.get('show_background', True), True)
            show_separators_val = reddit_settings.get('show_separators', True)
            show_separators = SettingsManager.to_bool(show_separators_val, True)
            bg_opacity = reddit_settings.get('bg_opacity', 1.0)
            try:
                limit_val = int(reddit_settings.get('limit', 10))
            except Exception:
                limit_val = 10
            # Historical configs used 5 items for the low-count mode; this is
            # now treated as a 4-item layout so that spacing and card height
            # match the visual design.
            if limit_val <= 5:
                limit_val = 4

            reddit_position_map = {
                'Top Left': RedditPosition.TOP_LEFT,
                'Top Right': RedditPosition.TOP_RIGHT,
                'Bottom Left': RedditPosition.BOTTOM_LEFT,
                'Bottom Right': RedditPosition.BOTTOM_RIGHT,
            }
            rpos = reddit_position_map.get(position_str, RedditPosition.TOP_RIGHT)

            try:
                self.reddit_widget = RedditWidget(self, subreddit=subreddit, position=rpos)

                if self._thread_manager is not None and hasattr(self.reddit_widget, 'set_thread_manager'):
                    try:
                        self.reddit_widget.set_thread_manager(self._thread_manager)
                    except Exception:
                        pass

                font_family = reddit_settings.get('font_family', 'Segoe UI')
                if hasattr(self.reddit_widget, 'set_font_family'):
                    self.reddit_widget.set_font_family(font_family)

                try:
                    self.reddit_widget.set_font_size(int(font_size))
                except Exception:
                    self.reddit_widget.set_font_size(18)

                try:
                    margin_val = int(margin)
                except Exception:
                    margin_val = 20
                self.reddit_widget.set_margin(margin_val)

                qcolor = parse_color_to_qcolor(color)
                if qcolor:
                    self.reddit_widget.set_text_color(qcolor)

                self.reddit_widget.set_show_background(show_background)

                try:
                    self.reddit_widget.set_show_separators(show_separators)
                except Exception:
                    pass

                # Background color
                bg_qcolor = parse_color_to_qcolor(bg_color_data)
                if bg_qcolor:
                    self.reddit_widget.set_background_color(bg_qcolor)

                # Background opacity
                try:
                    bg_opacity_f = float(bg_opacity)
                except Exception:
                    bg_opacity_f = 0.9
                self.reddit_widget.set_background_opacity(bg_opacity_f)

                # Border color and opacity
                try:
                    bo = float(border_opacity)
                except Exception:
                    bo = 0.8
                border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=bo)
                if border_qcolor:
                    self.reddit_widget.set_background_border(2, border_qcolor)

                # Item limit and shadow config
                try:
                    self.reddit_widget.set_item_limit(limit_val)
                except Exception:
                    pass

                try:
                    if hasattr(self.reddit_widget, 'set_shadow_config'):
                        self.reddit_widget.set_shadow_config(shadows_config)
                    else:
                        apply_widget_shadow(self.reddit_widget, shadows_config, has_background_frame=show_background)
                except Exception:
                    logger.debug("Failed to configure widget shadow for reddit widget", exc_info=True)

                # Set overlay name for fade coordination
                try:
                    if hasattr(self.reddit_widget, 'set_overlay_name'):
                        self.reddit_widget.set_overlay_name("reddit")
                except Exception:
                    pass

                self.reddit_widget.raise_()
                self.reddit_widget.start()
                logger.info(
                    "✅ Reddit widget started: r/%s, %s, font=%spx, limit=%s",
                    subreddit,
                    position_str,
                    font_size,
                    limit_val,
                )
            except Exception as e:
                logger.error("Failed to create/configure reddit widget: %s", e, exc_info=True)

        # Reddit 2 widget (inherits styling from Reddit 1)
        reddit2_settings = widgets.get('reddit2', {})
        reddit2_enabled = SettingsManager.to_bool(reddit2_settings.get('enabled', False), False)
        reddit2_monitor_sel = reddit2_settings.get('monitor', 'ALL')
        try:
            reddit2_show_on_this = (reddit2_monitor_sel == 'ALL') or (
                int(reddit2_monitor_sel) == (self.screen_index + 1)
            )
        except Exception:
            reddit2_show_on_this = False
        
        existing_reddit2 = getattr(self, 'reddit2_widget', None)
        if not (reddit2_enabled and reddit2_show_on_this):
            if existing_reddit2 is not None:
                try:
                    existing_reddit2.stop()
                    existing_reddit2.hide()
                except Exception:
                    pass
            self.reddit2_widget = None
        else:
            try:
                self._overlay_fade_expected.add("reddit2")
            except Exception:
                pass
            
            # Reddit 2 uses its own subreddit/position/limit but inherits styling from Reddit 1
            r2_position_str = reddit2_settings.get('position', 'Top Left')
            r2_subreddit = reddit2_settings.get('subreddit', '') or 'earthporn'
            try:
                r2_limit = int(reddit2_settings.get('limit', 4))
            except Exception:
                r2_limit = 4
            if r2_limit <= 5:
                r2_limit = 4
            
            r2_pos = reddit_position_map.get(r2_position_str, RedditPosition.TOP_LEFT)
            
            try:
                self.reddit2_widget = RedditWidget(self, subreddit=r2_subreddit, position=r2_pos)
                
                if self._thread_manager is not None and hasattr(self.reddit2_widget, 'set_thread_manager'):
                    try:
                        self.reddit2_widget.set_thread_manager(self._thread_manager)
                    except Exception:
                        pass
                
                # Inherit styling from Reddit 1
                font_family = reddit_settings.get('font_family', 'Segoe UI')
                if hasattr(self.reddit2_widget, 'set_font_family'):
                    self.reddit2_widget.set_font_family(font_family)
                
                try:
                    self.reddit2_widget.set_font_size(int(reddit_settings.get('font_size', 18)))
                except Exception:
                    self.reddit2_widget.set_font_size(18)
                
                self.reddit2_widget.set_margin(int(reddit_settings.get('margin', 20)))
                
                qcolor = parse_color_to_qcolor(reddit_settings.get('color', [255, 255, 255, 230]))
                if qcolor:
                    self.reddit2_widget.set_text_color(qcolor)
                
                self.reddit2_widget.set_show_background(
                    SettingsManager.to_bool(reddit_settings.get('show_background', True), True)
                )
                
                try:
                    self.reddit2_widget.set_show_separators(
                        SettingsManager.to_bool(reddit_settings.get('show_separators', True), True)
                    )
                except Exception:
                    pass
                
                bg_qcolor = parse_color_to_qcolor(reddit_settings.get('bg_color', [35, 35, 35, 255]))
                if bg_qcolor:
                    self.reddit2_widget.set_background_color(bg_qcolor)
                
                try:
                    self.reddit2_widget.set_background_opacity(float(reddit_settings.get('bg_opacity', 0.9)))
                except Exception:
                    self.reddit2_widget.set_background_opacity(0.9)
                
                try:
                    bo = float(reddit_settings.get('border_opacity', 1.0))
                except Exception:
                    bo = 1.0
                border_qcolor = parse_color_to_qcolor(
                    reddit_settings.get('border_color', [255, 255, 255, 255]), opacity_override=bo
                )
                if border_qcolor:
                    self.reddit2_widget.set_background_border(2, border_qcolor)
                
                try:
                    self.reddit2_widget.set_item_limit(r2_limit)
                except Exception:
                    pass
                
                try:
                    if hasattr(self.reddit2_widget, 'set_shadow_config'):
                        self.reddit2_widget.set_shadow_config(shadows_config)
                    else:
                        apply_widget_shadow(self.reddit2_widget, shadows_config, has_background_frame=True)
                except Exception:
                    pass
                
                # Set overlay name for fade coordination (distinct from reddit1)
                try:
                    if hasattr(self.reddit2_widget, 'set_overlay_name'):
                        self.reddit2_widget.set_overlay_name("reddit2")
                except Exception:
                    pass
                
                self.reddit2_widget.raise_()
                self.reddit2_widget.start()
                logger.info(
                    "✅ Reddit 2 widget started: r/%s, %s, limit=%s",
                    r2_subreddit, r2_position_str, r2_limit,
                )
            except Exception as e:
                logger.error("Failed to create/configure reddit2 widget: %s", e, exc_info=True)

        # Media widget (uses precomputed media_settings / media_enabled /
        # media_show_on_this from the fade coordination setup above).

        # Detailed diagnostics so we can see exactly what the runtime settings
        # look like for the media widget on each screen, including the raw
        # enabled value and monitor selection. The full settings map can be
        # large, so only dump it in verbose mode.
        if is_verbose_logging():
            try:
                logger.debug(
                    "[MEDIA_WIDGET] _setup_widgets: screen=%s, raw_settings=%r, "
                    "enabled_raw=%r, enabled_bool=%s, monitor_sel=%r, show_on_this=%s",
                    self.screen_index,
                    media_settings,
                    media_settings.get('enabled', None),
                    media_enabled,
                    media_monitor_sel,
                    media_show_on_this,
                )
            except Exception:
                logger.debug("[MEDIA_WIDGET] Failed to log media widget settings snapshot", exc_info=True)

        existing_media = getattr(self, 'media_widget', None)
        if not (media_enabled and media_show_on_this):
            if existing_media is not None:
                try:
                    existing_media.stop()
                    existing_media.hide()
                except Exception:
                    pass
            self.media_widget = None
            logger.debug(
                "Media widget disabled in settings (screen=%s, enabled=%s, show_on_this=%s, monitor_sel=%r)",
                self.screen_index,
                media_enabled,
                media_show_on_this,
                media_monitor_sel,
            )
            return

        try:
            self._overlay_fade_expected.add("media")
        except Exception:
            self._overlay_fade_expected = {"media"}

        position_str = media_settings.get('position', 'Bottom Left')
        media_position_map = {
            'Top Left': MediaPosition.TOP_LEFT,
            'Top Right': MediaPosition.TOP_RIGHT,
            'Bottom Left': MediaPosition.BOTTOM_LEFT,
            'Bottom Right': MediaPosition.BOTTOM_RIGHT,
        }
        mpos = media_position_map.get(position_str, MediaPosition.BOTTOM_LEFT)

        font_size = media_settings.get('font_size', 20)
        color = media_settings.get('color', [255, 255, 255, 230])
        artwork_size = media_settings.get('artwork_size', 100)
        rounded_artwork = SettingsManager.to_bool(
            media_settings.get('rounded_artwork_border', True), True
        )
        show_controls = SettingsManager.to_bool(media_settings.get('show_controls', True), True)
        show_header_frame = SettingsManager.to_bool(
            media_settings.get('show_header_frame', True), True
        )
        spotify_volume_enabled = SettingsManager.to_bool(
            media_settings.get('spotify_volume_enabled', True), True
        )

        try:
            self.media_widget = MediaWidget(self, position=mpos)

            # Inject ThreadManager so media polling runs on the IO pool
            if self._thread_manager is not None and hasattr(self.media_widget, "set_thread_manager"):
                try:
                    self.media_widget.set_thread_manager(self._thread_manager)
                except Exception:
                    pass

            # Font family
            font_family = media_settings.get('font_family', 'Segoe UI')
            if hasattr(self.media_widget, 'set_font_family'):
                self.media_widget.set_font_family(font_family)

            # Font size and margin
            try:
                self.media_widget.set_font_size(int(font_size))
            except Exception:
                self.media_widget.set_font_size(20)
            try:
                margin_val = int(media_settings.get('margin', 20))
            except Exception:
                margin_val = 20
            self.media_widget.set_margin(margin_val)

            # Artwork size, border shape, and controls visibility
            try:
                if hasattr(self.media_widget, 'set_artwork_size'):
                    self.media_widget.set_artwork_size(int(artwork_size))
            except Exception:
                pass
            try:
                if hasattr(self.media_widget, 'set_rounded_artwork_border'):
                    self.media_widget.set_rounded_artwork_border(rounded_artwork)
            except Exception:
                pass
            try:
                if hasattr(self.media_widget, 'set_show_controls'):
                    self.media_widget.set_show_controls(show_controls)
            except Exception:
                pass
            try:
                if hasattr(self.media_widget, 'set_show_header_frame'):
                    self.media_widget.set_show_header_frame(show_header_frame)
            except Exception:
                pass

            # Colors
            qcolor = parse_color_to_qcolor(color)
            if qcolor:
                self.media_widget.set_text_color(qcolor)

            # Default to a visible background frame for media so the
            # Spotify block stands out even on bright images. Users can
            # still override this via widgets.media.show_background.
            show_background = SettingsManager.to_bool(
                media_settings.get('show_background', True), True
            )
            self.media_widget.set_show_background(show_background)

            # Background color
            bg_color_data = media_settings.get('bg_color', [64, 64, 64, 255])
            bg_qcolor = parse_color_to_qcolor(bg_color_data)
            if bg_qcolor:
                self.media_widget.set_background_color(bg_qcolor)

            # Background opacity
            try:
                bg_opacity = float(media_settings.get('bg_opacity', 0.9))
            except Exception:
                bg_opacity = 0.9
            self.media_widget.set_background_opacity(bg_opacity)

            # Border color and opacity
            border_color_data = media_settings.get('border_color', [128, 128, 128, 255])
            border_opacity = media_settings.get('border_opacity', 0.8)
            try:
                bo = float(border_opacity)
            except Exception:
                bo = 0.8
            border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=bo)
            if border_qcolor:
                self.media_widget.set_background_border(2, border_qcolor)

            # Global widget drop shadow (shared config for all widgets).
            #
            # MediaWidget uses a temporary opacity effect for its own
            # fade-in; once the fade completes it re-attaches the shared
            # drop shadow using this configuration.
            try:
                if hasattr(self.media_widget, "set_shadow_config"):
                    self.media_widget.set_shadow_config(shadows_config)
                else:
                    apply_widget_shadow(self.media_widget, shadows_config, has_background_frame=show_background)
            except Exception:
                logger.debug("Failed to configure widget shadow for media widget", exc_info=True)

            self.media_widget.raise_()
            self.media_widget.start()
            logger.info(
                "✅ Media widget started: %s, font=%spx, margin=%s", position_str, font_size, margin_val
            )

            # Optional Spotify vertical volume widget, paired with the media
            # card. This is Spotify-only and uses Core Audio/pycaw when
            # available; when unavailable the widget remains hidden.
            existing_vol = getattr(self, "spotify_volume_widget", None)
            media_active_on_this = media_enabled and media_show_on_this
            if not (spotify_volume_enabled and media_active_on_this):
                if existing_vol is not None:
                    try:
                        existing_vol.stop()
                        existing_vol.hide()
                    except Exception:
                        pass
                self.spotify_volume_widget = None
            else:
                try:
                    if existing_vol is None:
                        vol = SpotifyVolumeWidget(self)
                        self.spotify_volume_widget = vol
                    else:
                        vol = existing_vol

                    if self._thread_manager is not None and hasattr(vol, "set_thread_manager"):
                        try:
                            vol.set_thread_manager(self._thread_manager)
                        except Exception:
                            pass

                    try:
                        vol.set_shadow_config(shadows_config)
                    except Exception:
                        pass
                    
                    # Set anchor to media widget for visibility gating
                    try:
                        if hasattr(vol, "set_anchor_media_widget"):
                            vol.set_anchor_media_widget(self.media_widget)
                    except Exception:
                        pass

                    # Inherit media card background and border colours for the
                    # track, while using a dedicated (configurable) fill colour
                    # for the volume bar itself.
                    try:
                        from PySide6.QtGui import QColor as _QColor

                        fill_color_data = media_settings.get('spotify_volume_fill_color', [255, 255, 255, 230])
                        try:
                            fr, fg, fb = (
                                fill_color_data[0],
                                fill_color_data[1],
                                fill_color_data[2],
                            )
                            fa = fill_color_data[3] if len(fill_color_data) > 3 else 230
                            fill_color = _QColor(fr, fg, fb, fa)
                        except Exception:
                            fill_color = _QColor(255, 255, 255, 230)

                        if hasattr(vol, "set_colors"):
                            vol.set_colors(track_bg=bg_qcolor, track_border=border_qcolor, fill=fill_color)
                    except Exception:
                        pass

                    try:
                        self._position_spotify_volume()
                    except Exception:
                        pass
                    # Defer startup to the Spotify secondary fade coordinator
                    # so the slider never appears before the main overlay
                    # group but still fades in smoothly as a second wave.
                    try:
                        if hasattr(self, "register_spotify_secondary_fade"):
                            self.register_spotify_secondary_fade(vol.start)
                        else:
                            vol.start()
                    except Exception:
                        logger.debug("[SPOTIFY_VOL] Failed to register/start volume widget", exc_info=True)
                except Exception:
                    logger.debug("[SPOTIFY_VOL] Failed to create/configure Spotify volume widget", exc_info=True)

            # Spotify Beat Visualizer (paired with media widget).
            existing_vis = getattr(self, 'spotify_visualizer_widget', None)
            media_active_on_this = media_enabled and media_show_on_this
            if not (spotify_vis_enabled and media_active_on_this):
                if existing_vis is not None:
                    try:
                        existing_vis.stop()
                        existing_vis.hide()
                    except Exception:
                        pass
                self.spotify_visualizer_widget = None
            else:
                try:
                    if existing_vis is None:
                        vis = SpotifyVisualizerWidget(self, bar_count=int(spotify_vis_settings.get('bar_count', 32)))
                        self.spotify_visualizer_widget = vis
                    else:
                        vis = existing_vis

                    # ThreadManager for animation tick scheduling
                    if self._thread_manager is not None and hasattr(vis, 'set_thread_manager'):
                        try:
                            vis.set_thread_manager(self._thread_manager)
                        except Exception:
                            pass

                    # Anchor geometry to media widget
                    try:
                        vis.set_anchor_media_widget(self.media_widget)
                    except Exception:
                        pass

                    # Card style inheritance from media widget card
                    try:
                        vis.set_bar_style(
                            bg_color=bg_qcolor,
                            bg_opacity=bg_opacity,
                            border_color=border_qcolor,
                            border_width=2,
                            show_background=show_background,
                        )
                    except Exception:
                        pass

                    # Software visualiser toggle: allow explicit user control
                    # plus automatic enablement when the renderer backend is
                    # set to Software. This keeps the GPU overlay as the
                    # primary path in OpenGL mode while still providing a
                    # software-only visualiser when no GL is available.
                    try:
                        allow_software = bool(spotify_vis_settings.get('software_visualizer_enabled', False))
                        backend_mode_raw = None
                        if self.settings_manager is not None:
                            try:
                                backend_mode_raw = self.settings_manager.get('display.render_backend_mode', 'opengl')
                            except Exception:
                                backend_mode_raw = 'opengl'
                        backend_mode = str(backend_mode_raw or 'opengl').lower().strip()
                        if backend_mode == 'software':
                            allow_software = True
                        if hasattr(vis, 'set_software_visualizer_enabled'):
                            vis.set_software_visualizer_enabled(allow_software)
                    except Exception:
                        logger.debug('[SPOTIFY_VIS] Failed to configure software visualiser flag', exc_info=True)

                    # Per-bar colours from spotify_visualizer settings
                    from PySide6.QtGui import QColor as _QColor
                    try:
                        fill_color_data = spotify_vis_settings.get('bar_fill_color', [0, 255, 128, 230])
                        fr, fg, fb = fill_color_data[0], fill_color_data[1], fill_color_data[2]
                        fa = fill_color_data[3] if len(fill_color_data) > 3 else 230
                        bar_fill_qcolor = _QColor(fr, fg, fb, fa)
                    except Exception:
                        bar_fill_qcolor = _QColor(0, 255, 128, 230)

                    try:
                        bar_border_color_data = spotify_vis_settings.get('bar_border_color', [255, 255, 255, 230])
                        br_r, br_g, br_b = (
                            bar_border_color_data[0],
                            bar_border_color_data[1],
                            bar_border_color_data[2],
                        )
                        base_alpha = bar_border_color_data[3] if len(bar_border_color_data) > 3 else 230
                        try:
                            bo = float(spotify_vis_settings.get('bar_border_opacity', 0.85))
                        except Exception:
                            bo = 0.85
                        bo = max(0.0, min(1.0, bo))
                        br_a = int(bo * base_alpha)
                        bar_border_qcolor = _QColor(br_r, br_g, br_b, br_a)
                    except Exception:
                        bar_border_qcolor = _QColor(255, 255, 255, 230)

                    try:
                        vis.set_bar_colors(bar_fill_qcolor, bar_border_qcolor)
                    except Exception:
                        pass

                    # Ghosting configuration: enabled flag, ghost opacity and
                    # decay speed for the GPU overlay. Defaults are driven by
                    # SettingsManager but can be overridden per-user from the
                    # Widgets tab.
                    try:
                        ghost_enabled_raw = spotify_vis_settings.get('ghosting_enabled', True)
                        ghost_enabled = SettingsManager.to_bool(ghost_enabled_raw, True)
                    except Exception:
                        ghost_enabled = True

                    try:
                        ghost_alpha_val = spotify_vis_settings.get('ghost_alpha', 0.4)
                        ghost_alpha = float(ghost_alpha_val)
                    except Exception:
                        ghost_alpha = 0.4

                    try:
                        ghost_decay_val = spotify_vis_settings.get('ghost_decay', 0.4)
                        ghost_decay = float(ghost_decay_val)
                    except Exception:
                        ghost_decay = 0.4

                    ghost_decay = max(0.0, ghost_decay)

                    try:
                        if hasattr(vis, 'set_ghost_config'):
                            vis.set_ghost_config(ghost_enabled, ghost_alpha, ghost_decay)
                    except Exception:
                        logger.debug('[SPOTIFY_VIS] Failed to configure ghosting settings on visualiser', exc_info=True)

                    # Sensitivity: adaptive (default) or manual scalar.
                    try:
                        adaptive_raw = spotify_vis_settings.get('adaptive_sensitivity', True)
                        adaptive = SettingsManager.to_bool(adaptive_raw, True)
                    except Exception:
                        adaptive = True
                    try:
                        sens_val = spotify_vis_settings.get('sensitivity', 1.0)
                        sens = float(sens_val)
                    except Exception:
                        sens = 1.0
                    sens = max(0.25, min(2.5, sens))
                    try:
                        if hasattr(vis, 'set_sensitivity_config'):
                            vis.set_sensitivity_config(adaptive, sens)
                    except Exception:
                        logger.debug('[SPOTIFY_VIS] Failed to configure sensitivity settings on visualiser', exc_info=True)

                    # Global widget drop shadow
                    try:
                        vis.set_shadow_config(shadows_config)
                    except Exception:
                        try:
                            apply_widget_shadow(vis, shadows_config, has_background_frame=show_background)
                        except Exception:
                            pass

                    # Wire Spotify media state into visualizer for behavioural gating.
                    # Guard against duplicate connections across _setup_widgets calls.
                    try:
                        already_connected = getattr(vis, "_srpss_media_connected", False)
                    except Exception:
                        already_connected = False
                    if not already_connected:
                        try:
                            self.media_widget.media_updated.connect(vis.handle_media_update)
                            setattr(vis, "_srpss_media_connected", True)
                        except Exception:
                            pass

                    # Initial positioning + startup
                    self._position_spotify_visualizer()
                    vis.start()
                except Exception:
                    logger.debug("Failed to create/configure Spotify Beat Visualizer widget", exc_info=True)

        except Exception as e:
            logger.error("Failed to create/configure media widget: %s", e, exc_info=True)

        # Widget Pixel Shift for burn-in prevention - set up AFTER all widgets
        # are created so we can register them all.
        # Settings are stored with dot notation (accessibility.pixel_shift.enabled)
        pixel_shift_enabled = SettingsManager.to_bool(
            self.settings_manager.get('accessibility.pixel_shift.enabled', False), False
        )
        try:
            pixel_shift_rate = int(self.settings_manager.get('accessibility.pixel_shift.rate', 1))
            pixel_shift_rate = max(1, min(5, pixel_shift_rate))
        except (ValueError, TypeError):
            pixel_shift_rate = 1
        
        if self._pixel_shift_manager is None:
            self._pixel_shift_manager = PixelShiftManager(resource_manager=self._resource_manager)
            # Set defer check to avoid shifting during transitions
            self._pixel_shift_manager.set_defer_check(lambda: self._current_transition is not None)
        
        self._pixel_shift_manager.set_shifts_per_minute(pixel_shift_rate)
        
        # Register all overlay widgets for pixel shifting (excluding dimming overlay)
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
            logger.debug("Pixel shift disabled")
        
        # Apply widget stacking for overlapping positions
        self._apply_widget_stacking(widgets)

    def _apply_widget_stacking(self, widgets_config: Dict[str, Any]) -> None:
        """Apply vertical stacking offsets to widgets sharing the same position.
        
        This method collects all visible widgets on THIS screen, groups them by
        position, and applies vertical offsets so they stack without overlapping.
        Called at the end of _setup_widgets after all widgets are created.
        
        Stacking is automatic and has no performance impact on fades since
        offsets are applied once during setup, not during animation.
        
        Note: Widget heights at setup time may be estimates. For widgets like
        Reddit that resize after content loads, consider calling
        recalculate_stacking() after content is ready.
        """
        # Map of position -> list of (widget, attr_name, creation_order)
        # Creation order determines stacking priority (earlier = base, later = stacked)
        position_groups: Dict[str, List[Tuple[Any, str, int]]] = {}
        
        # Widget attributes with creation order priority
        # Order matters: widgets listed first are the "base" at each position
        widget_attrs = [
            ('clock_widget', 0),
            ('clock2_widget', 1),
            ('clock3_widget', 2),
            ('weather_widget', 3),
            ('media_widget', 4),
            ('spotify_visualizer_widget', 5),
            ('reddit_widget', 6),
            ('reddit2_widget', 7),
        ]
        
        for attr_name, order in widget_attrs:
            widget = getattr(self, attr_name, None)
            if widget is None:
                continue
            
            # Query position directly from the widget (already set during creation)
            pos_normalized = self._get_widget_position_key(widget)
            if not pos_normalized:
                continue
            
            if pos_normalized not in position_groups:
                position_groups[pos_normalized] = []
            position_groups[pos_normalized].append((widget, attr_name, order))
        
        # Apply stacking offsets for each position group
        spacing = 10  # Gap between stacked widgets
        
        for pos_key, widgets_at_pos in position_groups.items():
            if len(widgets_at_pos) <= 1:
                # Single widget - ensure no stale offset
                if widgets_at_pos and hasattr(widgets_at_pos[0][0], 'set_stack_offset'):
                    widgets_at_pos[0][0].set_stack_offset(QPoint(0, 0))
                continue
            
            # Determine stack direction based on position
            stack_down = 'top' in pos_key  # Top positions stack downward
            
            # Sort by creation order - for bottom positions, reverse so first widget
            # is visually on top (stacked above later widgets)
            widgets_at_pos.sort(key=lambda x: x[2], reverse=not stack_down)
            
            # First widget is the base (no offset)
            cumulative_offset = 0
            
            for i, (widget, attr_name, _) in enumerate(widgets_at_pos):
                if i == 0:
                    # Base widget - reset any previous offset
                    if hasattr(widget, 'set_stack_offset'):
                        widget.set_stack_offset(QPoint(0, 0))
                    continue
                
                # Get height of previous widget
                prev_widget = widgets_at_pos[i - 1][0]
                prev_height = self._get_widget_stack_height(prev_widget)
                
                cumulative_offset += prev_height + spacing
                
                # Apply offset (positive for down, negative for up)
                offset_y = cumulative_offset if stack_down else -cumulative_offset
                
                if hasattr(widget, 'set_stack_offset'):
                    widget.set_stack_offset(QPoint(0, offset_y))
                    logger.debug(
                        "[STACKING] %s offset y=%d (position=%s, stack_down=%s)",
                        attr_name, offset_y, pos_key, stack_down
                    )
    
    def _get_widget_position_key(self, widget: Any) -> Optional[str]:
        """Get normalized position key from a widget's current position setting."""
        try:
            # BaseOverlayWidget stores position as OverlayPosition enum
            if hasattr(widget, '_position'):
                pos = widget._position
                if hasattr(pos, 'name'):
                    return pos.name.lower()
                return str(pos).lower().replace(' ', '_')
            # Fallback: try get_position method
            if hasattr(widget, 'get_position'):
                pos = widget.get_position()
                if hasattr(pos, 'name'):
                    return pos.name.lower()
                return str(pos).lower().replace(' ', '_')
        except Exception:
            pass
        return None
    
    def _get_widget_stack_height(self, widget: Any) -> int:
        """Get widget height for stacking calculations."""
        try:
            # Prefer bounding size if available (accounts for shadows, etc.)
            if hasattr(widget, 'get_bounding_size'):
                return widget.get_bounding_size().height()
            # Use sizeHint for widgets that haven't been shown yet
            hint = widget.sizeHint()
            if hint.isValid() and hint.height() > 0:
                return hint.height()
            # Fallback to actual height
            return widget.height() if widget.height() > 0 else 100
        except Exception:
            return 100  # Safe fallback
    
    def recalculate_stacking(self) -> None:
        """Recalculate widget stacking offsets.
        
        Call this after widget heights change (e.g., after Reddit content loads)
        to update stacking positions. Safe to call at any time.
        """
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

    def set_image(self, pixmap: QPixmap, image_path: str = "") -> None:
        """Display a new image with transition (backward-compatible sync version).
        
        NOTE: This method processes the image synchronously on the UI thread.
        For better performance, use set_processed_image() with pre-processed
        pixmaps from a background thread.
        
        Args:
            pixmap: Image to display (will be processed for screen fit)
            image_path: Path to image (for logging/events)
        """
        if pixmap.isNull():
            logger.warning("[FALLBACK] Received null pixmap in set_image")
            self.error_message = "Failed to load image"
            self.current_pixmap = None
            self.update()
            return

        # Process image for display at physical resolution
        screen_size = self.get_target_size()
        logger.debug(f"[IMAGE QUALITY] Processing image for {screen_size.width()}x{screen_size.height()} (DPR={self._device_pixel_ratio})")
        
        # Get quality settings
        use_lanczos = False
        sharpen = False
        if self.settings_manager:
            sharpen = self.settings_manager.get('display.sharpen_downscale', False)
            if isinstance(sharpen, str):
                sharpen = sharpen.lower() == 'true'
        
        # Process image (this blocks the UI thread - use set_processed_image for async)
        processed_pixmap = ImageProcessor.process_image(
            pixmap,
            screen_size,
            self.display_mode,
            use_lanczos,
            sharpen
        )
        
        # Delegate to the async-friendly method
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
        if getattr(self, "_current_transition", None) is not None and self._current_transition.is_running():
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
        
        # Stop any running transition
        if self._current_transition:
            transition_to_stop = self._current_transition
            self._current_transition = None  # Clear reference first
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
                    self._current_transition = transition

                    # For compositor-backed 3D Block Spins, keep the compositor
                    # base pixmap on the old image while the GLSL spin runs so
                    # we do not briefly jump to the new image before the
                    # transition actually starts.

                    comp = getattr(self, "_gl_compositor", None)
                    if (
                        transition.__class__.__name__ == "GLCompositorBlockSpinTransition"
                        and isinstance(comp, GLCompositorWidget)
                        and previous_pixmap_ref is not None
                        and not previous_pixmap_ref.isNull()
                    ):
                        try:
                            comp.set_base_pixmap(previous_pixmap_ref)
                        except Exception:
                            logger.debug(
                                "[GL COMPOSITOR] Failed to seed base pixmap for block spins",
                                exc_info=True,
                            )

                    if previous_pixmap_ref:
                        self.previous_pixmap = previous_pixmap_ref
                    else:
                        # Safety fallback: reuse the new frame to avoid synthetic black flashes.
                        self.previous_pixmap = processed_pixmap

                    # Connect transition finished signal using weakref to avoid callbacks
                    # after this widget is destroyed.
                    self_ref = weakref.ref(self)

                    self._pending_transition_finish_args = (
                        processed_pixmap,
                        original_pixmap,
                        image_path,
                        False,
                        None,
                    )

                    def _finish_handler(np=processed_pixmap, op=original_pixmap,
                                        ip=image_path, ref=self_ref):
                        widget = ref()
                        if widget is None or not Shiboken.isValid(widget):
                            return
                        try:
                            widget._pending_transition_finish_args = (np, op, ip, False, None)
                            widget._on_transition_finished(np, op, ip, False, None)
                        finally:
                            widget._pending_transition_finish_args = None

                    transition.finished.connect(_finish_handler)
                    overlay_key = self._resolve_overlay_key_for_transition(transition)
                    self._current_transition_overlay_key = overlay_key
                    self._current_transition_started_at = time.monotonic()
                    if overlay_key:
                        self._overlay_timeouts[overlay_key] = self._current_transition_started_at
                    success = transition.start(self.previous_pixmap, new_pixmap, self)
                    if success:
                        self._start_transition_watchdog(overlay_key, transition)
                        # Raise widgets SYNCHRONOUSLY after transition.start() so they
                        # are above the compositor BEFORE the first frame is rendered.
                        # Previously this was deferred via QTimer.singleShot(0, ...) which
                        # allowed the compositor to render 1+ frames with widgets hidden.
                        try:
                            # Raise all widgets above the compositor
                            for attr_name in ("clock_widget", "clock2_widget", "clock3_widget"):
                                clock = getattr(self, attr_name, None)
                                if clock is not None:
                                    try:
                                        clock.raise_()
                                        if hasattr(clock, '_tz_label') and clock._tz_label:
                                            clock._tz_label.raise_()
                                    except Exception:
                                        pass
                            if self.weather_widget:
                                try:
                                    self.weather_widget.raise_()
                                except Exception:
                                    pass
                            mw = getattr(self, "media_widget", None)
                            if mw is not None:
                                try:
                                    mw.raise_()
                                except Exception:
                                    pass
                            rw = getattr(self, "reddit_widget", None)
                            if rw is not None:
                                try:
                                    rw.raise_()
                                except Exception:
                                    pass
                            # Reddit 2 widget
                            rw2 = getattr(self, "reddit2_widget", None)
                            if rw2 is not None:
                                try:
                                    rw2.raise_()
                                except Exception:
                                    pass
                            sv = getattr(self, "spotify_visualizer_widget", None)
                            if sv is not None:
                                try:
                                    sv.raise_()
                                except Exception:
                                    pass
                            # Also raise the bars GL overlay
                            bars_overlay = getattr(self, "_spotify_bars_overlay", None)
                            if bars_overlay is not None:
                                try:
                                    bars_overlay.raise_()
                                except Exception:
                                    pass
                            # Spotify volume widget
                            vw = getattr(self, "spotify_volume_widget", None)
                            if vw is not None:
                                try:
                                    vw.raise_()
                                except Exception:
                                    pass
                            # Ctrl cursor hint
                            hint = getattr(self, "_ctrl_cursor_hint", None)
                            if hint is not None:
                                try:
                                    hint.raise_()
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        logger.debug(f"Transition started: {transition.__class__.__name__}")
                        return
                    else:
                        logger.warning("Transition failed to start, displaying immediately")
                        transition.cleanup()
                        self._current_transition = None
                        self._pending_transition_finish_args = None
                        self._cancel_transition_watchdog()
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
        _finish_start = time.time()

        overlay_key = self._current_transition_overlay_key
        if overlay_key:
            self._overlay_timeouts.pop(overlay_key, None)
        self._current_transition_overlay_key = None
        self._current_transition_started_at = 0.0

        self._cancel_transition_watchdog()

        transition_to_clean = self._current_transition
        self._current_transition = None

        # Use the pan preview frame if provided so the base widget matches
        # the first pan frame until the pan label takes over.
        self.current_pixmap = pan_preview or new_pixmap
        if self.current_pixmap:
            try:
                self.current_pixmap.setDevicePixelRatio(self._device_pixel_ratio)
            except Exception:
                pass
        self._seed_pixmap = self.current_pixmap
        self._last_pixmap_seed_ts = time.monotonic()
        if is_verbose_logging():
            logger.debug(
                "[DIAG] Seed pixmap set (phase=post-transition, pixmap=%s)",
                _describe_pixmap(self.current_pixmap),
            )
        if self._updates_blocked_until_seed:
            try:
                self.setUpdatesEnabled(True)
            except Exception:
                pass
            self._updates_blocked_until_seed = False
        self.previous_pixmap = None

        # Pan & Scan has been removed; simply ensure overlays are correct and
        # the new image is displayed.

        # After the display reflects the new pixmap (and optional pan), clean up
        # PERF: Use update() instead of repaint() - repaint() is synchronous and blocks
        # the UI thread for 50+ms. update() schedules an async repaint.
        try:
            self._ensure_overlay_stack(stage="transition_finish")
        except Exception:
            pass
        try:
            self.update()  # Async repaint - doesn't block
        except Exception:
            pass
        if transition_to_clean:
            try:
                transition_to_clean.cleanup()
            except Exception as exc:
                logger.warning("Error cleaning up transition: %s", exc)

        logger.debug("Transition completed, image displayed: %s", image_path)
        self.image_displayed.emit(image_path)
        self._pending_transition_finish_args = None
        
        # PERF: Log slow transition completions
        _finish_elapsed = (time.time() - _finish_start) * 1000.0
        if _finish_elapsed > 30.0 and is_perf_metrics_enabled():
            logger.warning("[PERF] Slow _on_transition_finished: %.2fms", _finish_elapsed)

    def _start_transition_watchdog(self, overlay_key: Optional[str], transition: BaseTransition) -> None:
        """Start or restart the transition watchdog timer."""
        timeout_sec = TRANSITION_WATCHDOG_DEFAULT_SEC
        if self.settings_manager:
            raw_timeout = self.settings_manager.get('transitions.watchdog_timeout_sec', timeout_sec)
            try:
                if isinstance(raw_timeout, str):
                    raw_timeout = float(raw_timeout)
                timeout_sec = float(raw_timeout)
            except (TypeError, ValueError):
                timeout_sec = TRANSITION_WATCHDOG_DEFAULT_SEC

        # Ensure watchdog timeout is never shorter than the transition
        # duration plus a small safety margin, otherwise long transitions
        # (e.g. 6.375s) will always hit the default 6s watchdog.
        try:
            duration_ms = getattr(transition, "duration_ms", None)
            if duration_ms is not None:
                duration_sec = float(duration_ms) / 1000.0
                timeout_sec = max(timeout_sec, duration_sec + 1.0)
        except Exception:
            # If anything goes wrong, fall back to the configured timeout.
            pass

        if timeout_sec <= 0:
            logger.debug("[WATCHDOG] Disabled (timeout %.2fs)", timeout_sec)
            self._cancel_transition_watchdog()
            return

        if self._transition_watchdog is None:
            self._transition_watchdog = QTimer(self)
            self._transition_watchdog.setSingleShot(True)
            self._transition_watchdog.timeout.connect(self._on_transition_watchdog_timeout)
            if self._resource_manager and not self._transition_watchdog_resource_id:
                try:
                    self._transition_watchdog_resource_id = self._resource_manager.register_qt(
                        self._transition_watchdog,
                        description="DisplayWidget transition watchdog",
                    )
                except Exception:
                    logger.debug("[WATCHDOG] Failed to register watchdog timer with ResourceManager", exc_info=True)

        if self._transition_watchdog is None:
            return

        interval_ms = max(100, int(timeout_sec * 1000))
        self._transition_watchdog_overlay_key = overlay_key
        self._transition_watchdog_transition = transition.__class__.__name__
        self._transition_watchdog_started_at = time.monotonic()

        try:
            self._transition_watchdog.start(interval_ms)
            logger.debug(
                "[WATCHDOG] Started (transition=%s, overlay=%s, timeout=%.2fs)",
                self._transition_watchdog_transition,
                overlay_key,
                timeout_sec,
            )
        except Exception:
            logger.debug("[WATCHDOG] Failed to start watchdog timer", exc_info=True)

    def _cancel_transition_watchdog(self) -> None:
        """Stop the watchdog timer and clear metadata."""
        if self._transition_watchdog and self._transition_watchdog.isActive():
            try:
                self._transition_watchdog.stop()
            except Exception:
                logger.debug("[WATCHDOG] Failed to stop watchdog timer", exc_info=True)
        self._transition_watchdog_overlay_key = None
        self._transition_watchdog_transition = None
        self._transition_watchdog_started_at = 0.0

    def _on_transition_watchdog_timeout(self) -> None:
        """Handle transition watchdog expiry."""
        elapsed = 0.0
        if self._transition_watchdog_started_at:
            elapsed = max(0.0, time.monotonic() - self._transition_watchdog_started_at)

        transition_name = self._transition_watchdog_transition or (
            self._current_transition.__class__.__name__ if self._current_transition else "<unknown>"
        )
        overlay_ready = False
        try:
            overlay_ready = any_overlay_ready_for_display(self)
        except Exception:
            overlay_ready = False

        log_fn = logger.warning
        if overlay_ready:
            log_fn = logger.debug

        log_fn(
            "[WATCHDOG] Transition timeout detected (transition=%s, overlay=%s, elapsed=%.2fs, overlay_ready=%s)",
            transition_name,
            self._transition_watchdog_overlay_key,
            elapsed,
            overlay_ready,
        )

        # Snapshot current transition before cancelling the watchdog, as
        # other paths may clear self._current_transition while we run.
        transition = self._current_transition

        self._cancel_transition_watchdog()

        if transition is not None:
            try:
                transition.stop()
            except Exception:
                logger.debug("[WATCHDOG] Failed to stop transition during timeout", exc_info=True)
            try:
                transition.cleanup()
            except Exception:
                logger.debug("[WATCHDOG] Failed to cleanup transition during timeout", exc_info=True)
            # Only clear the active reference if it still points at the same
            # transition we just operated on.
            if self._current_transition is transition:
                self._current_transition = None

        args = self._pending_transition_finish_args
        if args:
            try:
                self._on_transition_finished(*args)
            except Exception:
                logger.exception("[WATCHDOG] Failed to finalize transition after timeout")
                self._pending_transition_finish_args = None
        else:
            logger.debug("[WATCHDOG] No pending transition args to finalize after timeout")

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
        """Position Spotify Beat Visualizer just above the media widget."""

        vis = getattr(self, "spotify_visualizer_widget", None)
        media = getattr(self, "media_widget", None)
        if vis is None or media is None:
            return
        try:
            media_geom = media.geometry()
        except Exception:
            return
        if media_geom.width() <= 0 or media_geom.height() <= 0:
            return

        gap = 20
        height = max(vis.height(), vis.minimumHeight())
        width = media_geom.width()
        x = media_geom.left()
        try:
            position = getattr(media, "_position", None)
        except Exception:
            position = None

        place_above = True
        try:
            if position in (MediaPosition.TOP_LEFT, MediaPosition.TOP_RIGHT):
                place_above = False
        except Exception:
            place_above = True

        if place_above:
            y = media_geom.top() - gap - height
        else:
            y = media_geom.bottom() + gap

        if y < 0:
            y = 0
        if x < 0:
            x = 0
        max_width = max(10, self.width() - x)
        width = min(width, max_width)

        try:
            vis.setGeometry(x, y, width, height)
            vis.raise_()
            # Update pixel shift manager with new position
            if self._pixel_shift_manager is not None:
                self._pixel_shift_manager.update_original_position(vis)
        except Exception:
            pass

    def _position_spotify_volume(self) -> None:
        """Position Spotify volume slider beside the media widget.

        The slider is placed on the side of the media card that has more
        horizontal space available (left vs right).
        """

        vol = getattr(self, "spotify_volume_widget", None)
        media = getattr(self, "media_widget", None)
        if vol is None or media is None:
            return
        try:
            media_geom = media.geometry()
        except Exception:
            return
        if media_geom.width() <= 0 or media_geom.height() <= 0:
            return

        parent_width = max(1, self.width())
        space_left = max(0, media_geom.left())
        space_right = max(0, parent_width - media_geom.right())
        gap = 16

        width = max(vol.minimumWidth(), 32)

        # Make the slider roughly match the media card height but with a small
        # inset so the rounded ends are visible and do not collide with the
        # card frame.
        card_height = media_geom.height()
        height = max(vol.minimumHeight(), card_height - 8)
        height = min(height, card_height)

        if space_right >= space_left:
            x = media_geom.right() + gap
            if x + width > parent_width:
                x = max(0, parent_width - width)
        else:
            x = media_geom.left() - gap - width
            if x < 0:
                x = 0

        # Vertically centre the slider relative to the media card.
        y = media_geom.top() + max(0, (card_height - height) // 2)
        max_y = max(0, self.height() - height)
        if y > max_y:
            y = max_y
        if y < 0:
            y = 0

        try:
            vol.setGeometry(x, y, width, height)
            if vol.isVisible():
                vol.raise_()
            # Update pixel shift manager with new position
            if self._pixel_shift_manager is not None:
                self._pixel_shift_manager.update_original_position(vol)
        except Exception:
            pass

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
            )
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to push frame to SpotifyBarsGLOverlay", exc_info=True)
            return False

        return True

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
        
        # PERF: Remove from class-level cache, but only if we're still the registered instance
        # (avoids race condition where new widget registers before old widget's __del__ runs)
        if self._screen is not None:
            if DisplayWidget._instances_by_screen.get(self._screen) is self:
                DisplayWidget._instances_by_screen.pop(self._screen, None)
        
        # Reset eventFilter flags if this was the owner
        if DisplayWidget._event_filter_owner is self:
            DisplayWidget._event_filter_installed = False
            DisplayWidget._event_filter_owner = None
        
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
        
        # Stop and clean up any active transition
        try:
            if self._current_transition:
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
        if self._current_transition:
            transition_to_stop = self._current_transition
            self._current_transition = None  # Clear reference first
            try:
                transition_to_stop.stop()
            except Exception as e:
                logger.warning(f"Error stopping transition in clear(): {e}")
        # Ensure overlays are hidden to prevent residual frames during exit
        try:
            hide_all_overlays(self)
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

        Overlays call this when they are ready to start their first fade-in.
        We buffer the starter callbacks until either all expected overlays have
        registered or a short timeout elapses, then run them together.
        """

        try:
            expected = self._overlay_fade_expected
        except Exception:
            expected = set()

        started = getattr(self, "_overlay_fade_started", False)
        if is_verbose_logging():
            logger.debug(
                "[OVERLAY_FADE] request_overlay_fade_sync: screen=%s overlay=%s expected=%s started=%s",
                self.screen_index,
                overlay_name,
                sorted(expected) if expected else [],
                started,
            )

        # If coordination is not active or fades already kicked off, run now.
        if not expected or started:
            if is_verbose_logging():
                logger.debug(
                    "[OVERLAY_FADE] %s running starter immediately (expected=%s, started=%s)",
                    overlay_name,
                    sorted(expected) if expected else [],
                    started,
                )
            try:
                starter()
            except Exception:
                pass
            return

        pending = getattr(self, "_overlay_fade_pending", None)
        if not isinstance(pending, dict):
            pending = {}
            self._overlay_fade_pending = pending

        pending[overlay_name] = starter

        remaining = [name for name in expected if name not in pending]
        if is_verbose_logging():
            logger.debug(
                "[OVERLAY_FADE] %s registered (pending=%s, remaining=%s)",
                overlay_name,
                sorted(pending.keys()),
                sorted(remaining),
            )
        if not remaining:
            try:
                QTimer.singleShot(0, lambda: self._start_overlay_fades(force=False))
            except Exception:
                self._start_overlay_fades(force=False)
            return

        # Arm a timeout so a misbehaving overlay cannot block all fades.
        if self._overlay_fade_timeout is None:
            try:
                timeout = QTimer(self)
                timeout.setSingleShot(True)

                def _on_timeout() -> None:
                    self._start_overlay_fades(force=True)

                timeout.timeout.connect(_on_timeout)
                timeout.start(2500)
                self._overlay_fade_timeout = timeout
            except Exception:
                # If timer setup fails, just run fades immediately.
                self._start_overlay_fades(force=True)

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
            pos: Position to center the halo on
            mode: "none" for reposition only, "fade_in" or "fade_out" for animation
        """
        self._ensure_ctrl_cursor_hint()
        hint = self._ctrl_cursor_hint
        if hint is None:
            return
        
        # Position and show
        size = hint.size()
        hint.move(pos.x() - size.width() // 2, pos.y() - size.height() // 2)
        hint.show()
        hint.raise_()

        # Movement-only updates while Ctrl is held just reposition the halo.
        if mode == "none":
            return

        # Delegate animation to CursorHaloWidget
        if mode == "fade_in":
            hint.fade_in()
        elif mode == "fade_out":
            hint.fade_out()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press - hotkeys and exit."""
        key = event.key()
        key_text = event.text().lower()

        if key == Qt.Key.Key_Control:
            # Summon halo at the current cursor position and fade it in
            # while keeping the system cursor hidden.
            DisplayWidget._global_ctrl_held = True
            try:
                try:
                    global_pos = QCursor.pos()
                except Exception:
                    global_pos = None

                from PySide6.QtGui import QGuiApplication

                cursor_screen = None
                if global_pos is not None:
                    try:
                        cursor_screen = QGuiApplication.screenAt(global_pos)
                    except Exception:
                        cursor_screen = None

                # PERF: Use cached instances instead of iterating topLevelWidgets
                display_widgets = DisplayWidget.get_all_instances()

                # First, reset Ctrl state and any existing halos on all
                # DisplayWidgets so we never end up with multiple visible
                # halos from previous uses.
                for w in display_widgets:
                    try:
                        w._ctrl_held = False
                        hint = getattr(w, "_ctrl_cursor_hint", None)
                        if hint is not None:
                            try:
                                hint.cancel_animation()
                                hint.hide()
                            except Exception:
                                pass
                    except Exception:
                        continue

                target_widget = None
                target_pos = None

                # Prefer the DisplayWidget whose QScreen matches the cursor's
                # screen. This is more robust across mixed-DPI multi-monitor
                # layouts than relying purely on geometry.
                if cursor_screen is not None and global_pos is not None:
                    for w in display_widgets:
                        try:
                            if getattr(w, "_screen", None) is cursor_screen:
                                local_pos = w.mapFromGlobal(global_pos)
                                target_widget = w
                                target_pos = local_pos
                                break
                        except Exception:
                            continue

                # Fallback: pick the first DisplayWidget whose geometry
                # contains the cursor in its local coordinates.
                if target_widget is None and global_pos is not None:
                    for w in display_widgets:
                        try:
                            local_pos = w.mapFromGlobal(global_pos)
                            if w.rect().contains(local_pos):
                                target_widget = w
                                target_pos = local_pos
                                break
                        except Exception:
                            continue

                if target_widget is None:
                    target_widget = self
                    try:
                        if global_pos is not None:
                            target_pos = self.mapFromGlobal(global_pos)
                        else:
                            target_pos = self.rect().center()
                    except Exception:
                        target_pos = self.rect().center()

                DisplayWidget._halo_owner = target_widget
                target_widget._ctrl_held = True
                logger.debug("[CTRL HALO] Ctrl pressed; starting fade-in at %s", target_pos)
                target_widget._show_ctrl_cursor_hint(target_pos, mode="fade_in")
            except Exception:
                pass
            event.accept()
            return
        
        # Global media keys should never be treated as exit keys; they are
        # reserved for controlling media only.
        media_keys = {
            Qt.Key.Key_MediaPlay,
            Qt.Key.Key_MediaPause,
            Qt.Key.Key_MediaTogglePlayPause,
            Qt.Key.Key_MediaNext,
            Qt.Key.Key_MediaPrevious,
            Qt.Key.Key_VolumeUp,
            Qt.Key.Key_VolumeDown,
            Qt.Key.Key_VolumeMute,
        }

        # On Windows, some keyboards map play/pause combos and other media
        # keys in ways that do not always surface as the Qt.Key_Media*
        # enums above. Guard against those by also checking the native
        # virtual-key code range used for media keys.
        native_vk = None
        try:
            if hasattr(event, "nativeVirtualKey"):
                native_vk = int(event.nativeVirtualKey() or 0)
        except Exception:
            native_vk = None

        # Common Windows VK_* codes for media and volume keys.
        media_vk_codes = {
            0xAD,  # VK_VOLUME_MUTE
            0xAE,  # VK_VOLUME_DOWN
            0xAF,  # VK_VOLUME_UP
            0xB0,  # VK_MEDIA_NEXT_TRACK
            0xB1,  # VK_MEDIA_PREV_TRACK
            0xB2,  # VK_MEDIA_STOP
            0xB3,  # VK_MEDIA_PLAY_PAUSE
        }

        if key in media_keys or (native_vk in media_vk_codes):
            logger.debug("Media key pressed - ignoring for exit (key=%s, native_vk=%s)", key, native_vk)
            event.ignore()
            return

        # Determine current interaction/exit mode.
        ctrl_mode_active = self._ctrl_held or DisplayWidget._global_ctrl_held
        hard_exit_enabled = False
        try:
            hard_exit_enabled = self._is_hard_exit_enabled()
        except Exception:
            hard_exit_enabled = False

        # Hotkeys (always available regardless of hard-exit/ctrl state).
        if key_text == 'z':
            logger.info("Z key pressed - previous image requested")
            self.previous_requested.emit()
            event.accept()
            return
        if key_text == 'x':
            logger.info("X key pressed - next image requested")
            self.next_requested.emit()
            event.accept()
            return
        if key_text == 'c':
            logger.info("C key pressed - cycle transition requested")
            self.cycle_transition_requested.emit()
            event.accept()
            return
        if key_text == 's':
            logger.info("S key pressed - settings requested")
            self.settings_requested.emit()
            event.accept()
            return

        # Exit keys (Esc/Q) should always be honoured.
        if key in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            logger.info("Exit key pressed (%s), requesting exit", key)
            self._exiting = True
            # NOTE: Deferred Reddit URL is opened in _on_destroyed AFTER windows are hidden
            # to prevent Firefox from getting stuck behind still-visible screensaver windows
            self.exit_requested.emit()
            event.accept()
            return

        # In hard-exit mode or Ctrl interaction mode, non-hotkey keys are
        # ignored so that only explicit exit keys or hotkeys take effect.
        if hard_exit_enabled or ctrl_mode_active:
            logger.debug("Key %s ignored due to hard-exit/Ctrl interaction mode", key)
            event.ignore()
            return

        # Normal mode (no hard-exit, Ctrl not held): any other key exits.
        logger.info("Non-hotkey key pressed (%s) in normal mode - requesting exit", key)
        self._exiting = True
        # NOTE: Deferred Reddit URL is opened in _on_destroyed AFTER windows are hidden
        self.exit_requested.emit()
        event.accept()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Control:
            # When hard-exit mode is enabled we treat the Ctrl halo as a
            # persistent cursor proxy while the screensaver is active. In
            # that mode releasing Ctrl should simply leave the halo as-is;
            # it will continue to be driven by mouse movement via the
            # global event filter.
            hard_exit = False
            try:
                hard_exit = self._is_hard_exit_enabled()
            except Exception:
                hard_exit = False

            if hard_exit:
                DisplayWidget._global_ctrl_held = False
                # Also clear instance _ctrl_held so click-to-exit works after Ctrl release
                self._ctrl_held = False
                event.accept()
                return

            # Clear global Ctrl-held mode and gracefully fade out the halo
            # owned by the current DisplayWidget, while ensuring any stray
            # halos on other displays are also cleared.
            DisplayWidget._global_ctrl_held = False
            owner = DisplayWidget._halo_owner
            DisplayWidget._halo_owner = None
            
            # CRITICAL: Always clear _ctrl_held on the widget that received the
            # key release, regardless of whether it's the halo owner or in the cache.
            # This fixes the bug where _ctrl_held remained True after Ctrl release.
            self._ctrl_held = False

            try:
                global_pos = QCursor.pos()
            except Exception:
                global_pos = None

            # PERF: Use cached instances instead of iterating topLevelWidgets
            display_widgets = DisplayWidget.get_all_instances()

            # Fade out the halo for the current owner, if any.
            if isinstance(owner, DisplayWidget) and owner in display_widgets:
                try:
                    owner._ctrl_held = False
                except Exception:
                    pass
                try:
                    hint = getattr(owner, "_ctrl_cursor_hint", None)
                except Exception:
                    hint = None
                if hint is not None and hint.isVisible():
                    try:
                        if global_pos is not None:
                            local_pos = owner.mapFromGlobal(global_pos)
                        else:
                            local_pos = hint.pos() + hint.rect().center()
                    except Exception:
                        local_pos = hint.pos() + hint.rect().center()
                    logger.debug("[CTRL HALO] Ctrl released; starting fade-out at %s", local_pos)
                    try:
                        owner._show_ctrl_cursor_hint(local_pos, mode="fade_out")
                    except Exception:
                        pass

            # Ensure all other DisplayWidgets leave Ctrl mode and hide any
            # stray halos without starting additional fade animations.
            for w in display_widgets:
                if w is owner:
                    continue
                try:
                    w._ctrl_held = False
                    hint = getattr(w, "_ctrl_cursor_hint", None)
                    if hint is not None:
                        try:
                            hint.hide()
                        except Exception:
                            pass
                except Exception:
                    continue

            event.accept()
            return
        event.ignore()
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press - exit on any click unless hard exit is enabled."""
        ctrl_mode_active = self._ctrl_held or DisplayWidget._global_ctrl_held
        
        # Right-click context menu handling:
        # - In hard exit mode: right-click shows menu
        # - In normal mode: Ctrl+right-click shows menu (temporarily enables interaction)
        if event.button() == Qt.MouseButton.RightButton:
            if self._is_hard_exit_enabled() or ctrl_mode_active:
                # Show context menu
                self._show_context_menu(event.globalPosition().toPoint())
                event.accept()
                return
            # Normal mode without Ctrl - fall through to exit
        
        if self._is_hard_exit_enabled() or ctrl_mode_active:
            # In hard-exit or Ctrl-held interaction mode, route clicks over
            # interactive widgets (e.g. media / Spotify volume / reddit widget). Media
            # controls keep the screensaver active; Reddit links open the
            # browser and may optionally request a clean exit depending on
            # settings and hard-exit mode.
            handled = False
            reddit_handled = False

            # Spotify volume widget (vertical slider beside media card)
            vw = getattr(self, "spotify_volume_widget", None)
            try:
                if vw is not None and vw.isVisible() and vw.geometry().contains(event.pos()):
                    try:
                        from PySide6.QtCore import QPoint as _QPoint
                    except Exception:  # pragma: no cover - import guard
                        _QPoint = None  # type: ignore[assignment]

                    if _QPoint is not None:
                        geom = vw.geometry()
                        local_pos = _QPoint(event.pos().x() - geom.x(), event.pos().y() - geom.y())
                    else:
                        local_pos = event.pos()

                    try:
                        if vw.handle_press(local_pos, event.button()):
                            handled = True
                    except Exception:
                        logger.debug("[SPOTIFY_VOL] click routing failed", exc_info=True)
            except Exception:
                logger.debug("[SPOTIFY_VOL] Error while routing click to volume widget", exc_info=True)

            # Media widget (Spotify-style transport controls)
            mw = getattr(self, "media_widget", None)
            try:
                if mw is not None and mw.isVisible() and mw.geometry().contains(event.pos()):
                    button = event.button()
                    try:
                        from PySide6.QtCore import Qt as _Qt
                    except Exception:  # pragma: no cover - import guard
                        _Qt = Qt  # type: ignore[assignment]

                    if button == _Qt.MouseButton.LeftButton:
                        # Map left-clicks to previous / play-pause /
                        # next based on horizontal thirds of the Spotify
                        # widget's *text content* area (between
                        # contentsMargins.left/right), so the visual
                        # arrows and centre glyph match their actions
                        # even when there is a large artwork margin on
                        # the right.
                        #
                        # IMPORTANT: Only process clicks in the controls row
                        # area (bottom ~60px of the widget). Clicks in the
                        # upper portion of the widget should not trigger
                        # transport controls.
                        try:
                            geom = mw.geometry()
                            local_x = event.pos().x() - geom.x()
                            local_y = event.pos().y() - geom.y()
                            height = max(1, mw.height())
                            width = max(1, mw.width())
                            
                            # Controls row is in the bottom portion of the widget
                            # Only process clicks in the bottom 60px (controls area)
                            controls_row_height = 60
                            controls_row_top = height - controls_row_height
                            
                            if local_y >= controls_row_top:
                                # Click is in the controls row area
                                margins = mw.contentsMargins()
                                content_left = margins.left()
                                content_right = width - margins.right()
                                content_width = max(1, content_right - content_left)
                                x_in_content = local_x - content_left
                                # Clamp so clicks slightly inside the card
                                # margins map to the nearest control.
                                if x_in_content < 0:
                                    x_in_content = 0
                                elif x_in_content > content_width:
                                    x_in_content = content_width
                                third = content_width / 3.0
                                if x_in_content < third:
                                    logger.debug(
                                        "[MEDIA] click mapped to PREVIOUS: pos=%s geom=%s local_x=%d local_y=%d x_in_content=%d width=%d content_left=%d content_right=%d third=%.2f",
                                        event.pos(),
                                        geom,
                                        local_x,
                                        local_y,
                                        x_in_content,
                                        width,
                                        content_left,
                                        content_right,
                                        third,
                                    )
                                    mw.previous_track()
                                    handled = True
                                elif x_in_content < 2.0 * third:
                                    logger.debug(
                                        "[MEDIA] click mapped to PLAY/PAUSE: pos=%s geom=%s local_x=%d local_y=%d x_in_content=%d width=%d content_left=%d content_right=%d third=%.2f",
                                        event.pos(),
                                        geom,
                                        local_x,
                                        local_y,
                                        x_in_content,
                                        width,
                                        content_left,
                                        content_right,
                                        third,
                                    )
                                    mw.play_pause()
                                    handled = True
                                else:
                                    logger.debug(
                                        "[MEDIA] click mapped to NEXT: pos=%s geom=%s local_x=%d local_y=%d x_in_content=%d width=%d content_left=%d content_right=%d third=%.2f",
                                        event.pos(),
                                        geom,
                                        local_x,
                                        local_y,
                                        x_in_content,
                                        width,
                                        content_left,
                                        content_right,
                                        third,
                                    )
                                    mw.next_track()
                                    handled = True
                            # else: Click is above controls row - don't handle as transport control
                        except Exception:
                            logger.debug("[MEDIA] left-click media routing failed", exc_info=True)
                    elif button == _Qt.MouseButton.RightButton:
                        try:
                            mw.next_track()
                            handled = True
                        except Exception:
                            logger.debug("[MEDIA] next_track handling failed from mousePressEvent", exc_info=True)
                    elif button == _Qt.MouseButton.MiddleButton:
                        try:
                            mw.previous_track()
                            handled = True
                        except Exception:
                            logger.debug("[MEDIA] previous_track handling failed from mousePressEvent", exc_info=True)
            except Exception:
                logger.debug("[MEDIA] Error while routing click to media widget", exc_info=True)

            # Reddit widgets: map clicks to open links in the browser when
            # interaction mode is active. When hard-exit is disabled,
            # Reddit clicks trigger a clean exit (controlled by the per-widget
            # "exit_on_click" setting). In hard-exit mode, we DEFER the browser
            # open until the user actually exits - this avoids the edge case
            # where Firefox gets stuck behind the screensaver.
            # Check BOTH reddit_widget and reddit2_widget.
            for reddit_attr in ("reddit_widget", "reddit2_widget"):
                if handled:
                    break
                rw = getattr(self, reddit_attr, None)
                try:
                    if rw is not None and rw.isVisible() and rw.geometry().contains(event.pos()):
                        try:
                            from PySide6.QtCore import QPoint as _QPoint
                        except Exception:  # pragma: no cover - import guard
                            _QPoint = None  # type: ignore[assignment]

                        geom = rw.geometry()
                        if _QPoint is not None:
                            local_pos = _QPoint(event.pos().x() - geom.x(), event.pos().y() - geom.y())
                        else:
                            local_pos = event.pos()

                        try:
                            hard_exit_enabled = self._is_hard_exit_enabled()
                        except Exception:
                            hard_exit_enabled = False

                        try:
                            if hasattr(rw, "handle_click"):
                                # In hard-exit mode, defer browser open to exit time UNLESS
                                # this is NOT the primary display AND there's a free display available
                                try:
                                    from PySide6.QtGui import QGuiApplication
                                    is_primary_display = (self._screen == QGuiApplication.primaryScreen())
                                    
                                    # Check if all displays are occupied by the screensaver
                                    all_displays_taken = False
                                    total_screens = len(QGuiApplication.screens())
                                    # Simple heuristic: if we have multiple screens and hard-exit is enabled,
                                    # assume all displays might be taken for safety
                                    all_displays_taken = total_screens > 1
                                    logger.debug(f"[REDDIT] Display detection: total_screens={total_screens}, all_taken={all_displays_taken}")
                                except Exception:
                                    # If we can't determine, assume all displays taken for safety
                                    is_primary_display = True  # Conservative fallback
                                    all_displays_taken = True
                                
                                if hard_exit_enabled and not is_primary_display and not all_displays_taken:
                                    # Secondary display in hard-exit mode with free display: open immediately on primary display
                                    result = rw.handle_click(local_pos, deferred=False)
                                    if isinstance(result, bool) and result:
                                        handled = True
                                        reddit_handled = True
                                        logger.info("[REDDIT] Opened URL immediately on primary display")
                                elif hard_exit_enabled:
                                    # Primary display in hard-exit mode OR all displays taken: defer URL
                                    result = rw.handle_click(local_pos, deferred=True)
                                    if isinstance(result, str):
                                        # Store URL to open when user exits
                                        self._pending_reddit_url = result
                                        handled = True
                                        reddit_handled = True
                                        if all_displays_taken:
                                            logger.info("[REDDIT] URL deferred for exit (all displays taken): %s", result)
                                        else:
                                            logger.info("[REDDIT] URL deferred for exit (primary display): %s", result)
                                else:
                                    # Normal mode: open immediately
                                    if rw.handle_click(local_pos):
                                        handled = True
                                        reddit_handled = True
                        except Exception:
                            logger.debug("[REDDIT] click routing failed for %s", reddit_attr, exc_info=True)
                except Exception:
                    logger.debug("[REDDIT] Error while routing click to %s", reddit_attr, exc_info=True)

            if handled:
                # Request a clean exit after Reddit clicks when hard-exit mode
                # is disabled and the widget is configured to exit-on-click.
                should_exit = False
                if reddit_handled and getattr(self, "_reddit_exit_on_click", True):
                    try:
                        hard_exit_enabled = self._is_hard_exit_enabled()
                    except Exception:
                        hard_exit_enabled = False
                    if not hard_exit_enabled:
                        should_exit = True

                if should_exit:
                    logger.info("[REDDIT] Click handled; requesting screensaver exit")
                    try:
                        from PySide6.QtCore import QTimer as _QTimer
                    except Exception:  # pragma: no cover - import guard
                        _QTimer = None  # type: ignore[assignment]

                    def _do_exit_after_reddit() -> None:
                        if not self._exiting:
                            self._exiting = True
                            try:
                                self.hide()
                            except Exception:
                                pass
                            self.exit_requested.emit()

                    if _QTimer is not None:
                        _QTimer.singleShot(400, _do_exit_after_reddit)
                    else:
                        _do_exit_after_reddit()
                event.accept()
                return

            # Even when no widget handled the click, do not exit while in
            # hard-exit / Ctrl-held interaction mode.
            event.accept()
            return

        logger.info(f"Mouse clicked at ({event.pos().x()}, {event.pos().y()}), requesting exit")
        self._exiting = True
        # NOTE: Deferred Reddit URL is opened in _on_destroyed AFTER windows are hidden
        self.exit_requested.emit()
        event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move - exit if moved beyond threshold (unless hard exit)."""
        # Don't exit while context menu is active
        if self._context_menu_active:
            event.accept()
            return
        
        ctrl_mode_active = DisplayWidget._global_ctrl_held
        if self._is_hard_exit_enabled() or ctrl_mode_active:
            # Hard exit or Ctrl-held mode disables mouse-move exit entirely.
            # Halo movement is handled centrally via the global event filter.
            # While in this mode we also allow dragging over the Spotify
            # volume widget so users can scrub volume without exiting.
            vw = getattr(self, "spotify_volume_widget", None)
            if vw is not None and vw.isVisible():
                try:
                    from PySide6.QtCore import QPoint as _QPoint
                except Exception:  # pragma: no cover - import guard
                    _QPoint = None  # type: ignore[assignment]

                try:
                    if _QPoint is not None:
                        geom = vw.geometry()
                        local_pos = _QPoint(event.pos().x() - geom.x(), event.pos().y() - geom.y())
                    else:
                        local_pos = event.pos()
                    vw.handle_drag(local_pos)
                except Exception:
                    logger.debug("[SPOTIFY_VOL] drag routing failed", exc_info=True)
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
            # NOTE: Deferred Reddit URL is opened in _on_destroyed AFTER windows are hidden
            self.exit_requested.emit()
        
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release; end Spotify volume drags in interaction mode."""

        ctrl_mode_active = self._ctrl_held or DisplayWidget._global_ctrl_held
        if self._is_hard_exit_enabled() or ctrl_mode_active:
            vw = getattr(self, "spotify_volume_widget", None)
            if vw is not None:
                try:
                    vw.handle_release()
                except Exception:
                    logger.debug("[SPOTIFY_VOL] release routing failed", exc_info=True)
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Route wheel scrolling to Spotify volume widget in interaction mode.

        When hard-exit / Ctrl mode is active, scrolling over any Spotify-related
        widget (media card, visualiser, or the volume slider itself) adjusts the
        shared Spotify volume level. Outside these regions the wheel event is
        ignored for volume but still prevented from exiting the saver.
        """

        ctrl_mode_active = self._ctrl_held or DisplayWidget._global_ctrl_held
        if self._is_hard_exit_enabled() or ctrl_mode_active:
            vw = getattr(self, "spotify_volume_widget", None)
            mw = getattr(self, "media_widget", None)
            sv = getattr(self, "spotify_visualizer_widget", None)

            if vw is not None and vw.isVisible():
                try:
                    from PySide6.QtCore import QPoint as _QPoint
                except Exception:  # pragma: no cover - import guard
                    _QPoint = None  # type: ignore[assignment]

                try:
                    pos = event.position()
                    pt = pos.toPoint()

                    geom_vol = vw.geometry()
                    over_volume = geom_vol.contains(pt)

                    over_media = False
                    if mw is not None and mw.isVisible():
                        try:
                            over_media = mw.geometry().contains(pt)
                        except Exception:
                            over_media = False

                    over_vis = False
                    if sv is not None and sv.isVisible():
                        try:
                            over_vis = sv.geometry().contains(pt)
                        except Exception:
                            over_vis = False

                    local_pos = None
                    if _QPoint is not None:
                        if over_volume:
                            local_pos = _QPoint(int(pos.x()) - geom_vol.x(), int(pos.y()) - geom_vol.y())
                        elif over_media or over_vis:
                            # Map wheel to the volume slider's centre X while
                            # preserving the pointer's vertical position.
                            center_x = vw.rect().center().x()
                            local_pos = _QPoint(center_x, int(pos.y()) - geom_vol.y())
                    else:
                        if over_volume or over_media or over_vis:
                            local_pos = event.position().toPoint()

                    if local_pos is not None:
                        delta_y = int(event.angleDelta().y())
                        if vw.handle_wheel(local_pos, delta_y):
                            event.accept()
                            return
                except Exception:
                    logger.debug("[SPOTIFY_VOL] wheel routing failed", exc_info=True)

            # Even when not over the Spotify widgets, wheel in interaction mode
            # should never exit the saver.
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
                        try:
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

                    self._context_menu.aboutToHide.connect(_on_menu_hide)
                    setattr(self, "_context_menu_hide_connected", True)
                except Exception:
                    pass

            try:
                self._invalidate_overlay_effects("menu_before_popup")
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
        # NOTE: Deferred Reddit URL is opened in _on_destroyed AFTER windows are hidden
        self.exit_requested.emit()
    
    def _open_pending_reddit_url(self) -> None:
        """Open any pending Reddit URL that was deferred in hard-exit mode.
        
        NOTE: This is a legacy/backup method. The primary URL opening is now
        handled by DisplayManager.cleanup() which opens URLs AFTER all windows
        are hidden but BEFORE QApplication.quit(). This prevents Firefox from
        getting stuck behind still-visible screensaver windows.
        """
        # URL opening is now handled by DisplayManager.cleanup()
        # This method is kept for backwards compatibility but should not
        # normally be called since DisplayManager clears _pending_reddit_url
        pass

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
        if win_diag_logger.isEnabledFor(logging.DEBUG):
            try:
                win_diag_logger.debug(
                    "[EFFECT_INVALIDATE] screen=%s reason=%s",
                    getattr(self, "screen_index", "?"),
                    reason,
                )
            except Exception:
                pass

        try:
            strong = "menu" in str(reason)
        except Exception:
            strong = False

        refresh_effects = False
        if strong:
            # Toggle-based refresh: recreate effects on every other menu
            # invalidation to bust Qt caches without excessive churn.
            try:
                flip = bool(getattr(self, "_effect_refresh_flip", False))
            except Exception:
                flip = False
            flip = not flip
            try:
                setattr(self, "_effect_refresh_flip", flip)
            except Exception:
                pass
            refresh_effects = flip

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
                eff = w.graphicsEffect()
            except Exception:
                eff = None

            if isinstance(eff, (QGraphicsDropShadowEffect, QGraphicsOpacityEffect)):
                if refresh_effects:
                    try:
                        anim = getattr(w, "_shadowfade_anim", None)
                    except Exception:
                        anim = None
                    try:
                        shadow_anim = getattr(w, "_shadowfade_shadow_anim", None)
                    except Exception:
                        shadow_anim = None
                    if anim is None and shadow_anim is None:
                        if isinstance(eff, QGraphicsDropShadowEffect):
                            try:
                                blur = eff.blurRadius()
                            except Exception:
                                blur = None
                            try:
                                offset = eff.offset()
                            except Exception:
                                offset = None
                            try:
                                color = eff.color()
                            except Exception:
                                color = None
                            try:
                                w.setGraphicsEffect(None)
                            except Exception:
                                pass
                            try:
                                new_eff = QGraphicsDropShadowEffect(w)
                                if blur is not None:
                                    new_eff.setBlurRadius(blur)
                                if offset is not None:
                                    new_eff.setOffset(offset)
                                if color is not None:
                                    new_eff.setColor(color)
                                w.setGraphicsEffect(new_eff)
                                eff = new_eff
                            except Exception:
                                try:
                                    eff = w.graphicsEffect()
                                except Exception:
                                    eff = None
                        elif isinstance(eff, QGraphicsOpacityEffect):
                            try:
                                opacity = eff.opacity()
                            except Exception:
                                opacity = None
                            try:
                                w.setGraphicsEffect(None)
                            except Exception:
                                pass
                            try:
                                new_eff = QGraphicsOpacityEffect(w)
                                if opacity is not None:
                                    new_eff.setOpacity(opacity)
                                w.setGraphicsEffect(new_eff)
                                eff = new_eff
                            except Exception:
                                try:
                                    eff = w.graphicsEffect()
                                except Exception:
                                    eff = None
                try:
                    eff.setEnabled(False)
                    eff.setEnabled(True)
                except Exception:
                    pass
                if isinstance(eff, QGraphicsDropShadowEffect):
                    try:
                        eff.setBlurRadius(eff.blurRadius())
                        eff.setOffset(eff.offset())
                        eff.setColor(eff.color())
                    except Exception:
                        pass
            try:
                if w.isVisible():
                    w.update()
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
            if sys.platform != "win32" or not win_diag_logger.isEnabledFor(logging.DEBUG):
                return super().nativeEvent(eventType, message)

            try:
                msg_ptr = int(message)
            except Exception:
                msg_ptr = 0
            if msg_ptr == 0:
                return super().nativeEvent(eventType, message)

            try:
                msg = ctypes.cast(msg_ptr, ctypes.POINTER(wintypes.MSG)).contents
            except Exception:
                return super().nativeEvent(eventType, message)

            mid = int(getattr(msg, "message", 0) or 0)

            names = {
                0x0006: "WM_ACTIVATE",
                0x0086: "WM_NCACTIVATE",
                0x0046: "WM_WINDOWPOSCHANGING",
                0x0047: "WM_WINDOWPOSCHANGED",
                0x007C: "WM_STYLECHANGING",
                0x007D: "WM_STYLECHANGED",
                0x0014: "WM_ERASEBKGND",
                0x000B: "WM_SETREDRAW",
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

    def eventFilter(self, watched, event):  # type: ignore[override]
        """Global event filter to keep the Ctrl halo responsive over children."""
        try:
            if event is not None and event.type() == QEvent.Type.MouseMove:
                hard_exit = False
                try:
                    hard_exit = self._is_hard_exit_enabled()
                except Exception:
                    hard_exit = False

                if DisplayWidget._global_ctrl_held or hard_exit:
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

                    owner = DisplayWidget._halo_owner

                    # If the cursor moved to a different screen, migrate the
                    # halo owner to the DisplayWidget bound to that screen.
                    if cursor_screen is not None:
                        screen_changed = (
                            owner is None
                            or getattr(owner, "_screen", None) is not cursor_screen
                        )
                        if screen_changed:
                            # PERF: Use cached lookup instead of iterating topLevelWidgets
                            new_owner = DisplayWidget._instances_by_screen.get(cursor_screen)
                            
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
                                            # Update cache for future lookups
                                            DisplayWidget._instances_by_screen[cursor_screen] = w
                                            break
                                    except Exception:
                                        continue

                            if new_owner is None:
                                new_owner = owner or self

                            if owner is not None and owner is not new_owner:
                                try:
                                    hint = getattr(owner, "_ctrl_cursor_hint", None)
                                    if hint is not None:
                                        hint.hide()
                                except Exception:
                                    pass
                                owner._ctrl_held = False

                            DisplayWidget._halo_owner = new_owner
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
                            if owner_hard_exit:
                                if DisplayWidget._halo_owner is None or halo_hidden:
                                    # Fade in if halo owner not set OR if halo is hidden
                                    DisplayWidget._halo_owner = owner
                                    owner._show_ctrl_cursor_hint(local_pos, mode="fade_in")
                                else:
                                    # Just reposition
                                    owner._show_ctrl_cursor_hint(local_pos, mode="none")
                            elif DisplayWidget._global_ctrl_held:
                                # Ctrl mode - show/reposition halo
                                # If halo is hidden (e.g., after settings dialog), fade it in
                                if halo_hidden:
                                    DisplayWidget._halo_owner = owner
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
        ct = getattr(self, "_current_transition", None)
        try:
            return bool(ct and ct.is_running())
        except Exception:
            return False
