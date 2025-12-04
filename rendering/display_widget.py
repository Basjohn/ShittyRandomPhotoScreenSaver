"""Display widget for OpenGL/software rendered screensaver overlays."""
from collections import defaultdict
from typing import Optional, Iterable, Tuple, Callable, Dict
import random
import time
import weakref
import sys
try:
    from OpenGL import GL  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    GL = None
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QPropertyAnimation, QVariantAnimation, QEasingCurve, QEvent
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
from transitions import (
    CrossfadeTransition,
    SlideTransition,
    SlideDirection,
    WipeTransition,
    WipeDirection,
    BlockPuzzleFlipTransition,
)
from transitions.gl_compositor_crossfade_transition import GLCompositorCrossfadeTransition
from transitions.gl_compositor_slide_transition import GLCompositorSlideTransition
from transitions.gl_compositor_wipe_transition import GLCompositorWipeTransition
from transitions.gl_compositor_blockflip_transition import GLCompositorBlockFlipTransition
from transitions.gl_compositor_blinds_transition import GLCompositorBlindsTransition
from transitions.gl_compositor_peel_transition import GLCompositorPeelTransition
from transitions.gl_compositor_blockspin_transition import GLCompositorBlockSpinTransition
from transitions.gl_compositor_raindrops_transition import GLCompositorRainDropsTransition
from transitions.gl_compositor_warp_transition import GLCompositorWarpTransition
from transitions.gl_compositor_diffuse_transition import GLCompositorDiffuseTransition
from transitions.diffuse_transition import DiffuseTransition
from widgets.clock_widget import ClockWidget, TimeFormat, ClockPosition
from widgets.weather_widget import WeatherWidget, WeatherPosition
from widgets.media_widget import MediaWidget, MediaPosition
from widgets.reddit_widget import RedditWidget, RedditPosition
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
from widgets.spotify_volume_widget import SpotifyVolumeWidget
from widgets.shadow_utils import apply_widget_shadow
from core.logging.logger import get_logger, is_verbose_logging
from core.logging.overlay_telemetry import record_overlay_ready
from core.resources.manager import ResourceManager
from core.settings.settings_manager import SettingsManager
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
    
    # Global Ctrl-held interaction mode flag shared across all display instances.
    # This ensures that holding Ctrl on any screen suppresses mouse-based exit
    # (movement/click) on all displays simultaneously.
    _global_ctrl_held: bool = False
    _halo_owner: Optional["DisplayWidget"] = None

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
        self._gl_initial_flush_done = False
        self._overlay_stage_counts: defaultdict[str, int] = defaultdict(int)
        self._overlay_timeouts: dict[str, float] = {}
        self._transitions_enabled: bool = True
        self._ctrl_held: bool = False
        self._ctrl_cursor_hint = None
        self._ctrl_cursor_hint_anim: Optional[QPropertyAnimation] = None
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
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        except Exception:
            pass
        # Ensure we can keep the Ctrl halo moving even when the cursor is over
        # child widgets (clocks, weather, etc.) by observing global mouse
        # move events.
        try:
            app = QGuiApplication.instance()
            if app is not None:
                app.installEventFilter(self)
        except Exception:
            pass
        
        # Set black background
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.GlobalColor.black)
        self.setPalette(palette)
        
        logger.info(f"DisplayWidget created for screen {screen_index} ({display_mode})")

        # Initialize renderer backend using new backend factory
        self._renderer_backend: Optional[RendererBackend] = None
        self._render_surface: Optional[RenderSurface] = None
        self._backend_selection: Optional[BackendSelectionResult] = None
        self._backend_fallback_message: Optional[str] = None
        self._has_rendered_first_frame = False
        self._gl_compositor: Optional[GLCompositorWidget] = None
        self._init_renderer_backend()

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
            target = max(10, min(240, detected))
            self._target_fps = target
            logger.info(f"Detected refresh rate: {detected} Hz, target animation FPS: {self._target_fps}")
        
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

        widgets_map = widgets if isinstance(widgets, dict) else {}

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

        spotify_vis_settings = widgets_map.get('spotify_visualizer', {}) if isinstance(widgets_map, dict) else {}
        spotify_vis_enabled = SettingsManager.to_bool(spotify_vis_settings.get('enabled', False), False)

        self._overlay_fade_expected = set()
        if weather_enabled and weather_show_on_this:
            self._overlay_fade_expected.add("weather")
        if reddit_enabled and reddit_show_on_this:
            self._overlay_fade_expected.add("reddit")
        if media_enabled and media_show_on_this:
            self._overlay_fade_expected.add("media")
        if media_enabled and media_show_on_this and spotify_vis_enabled:
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

                from PySide6.QtGui import QColor
                qcolor = QColor(color[0], color[1], color[2], color[3])
                clock.set_text_color(qcolor)

                # Background color (inherits from main clock for clock2/clock3)
                try:
                    bg_r, bg_g, bg_b = bg_color_data[0], bg_color_data[1], bg_color_data[2]
                    bg_a = bg_color_data[3] if len(bg_color_data) > 3 else 255
                    bg_qcolor = QColor(bg_r, bg_g, bg_b, bg_a)
                    if hasattr(clock, "set_background_color"):
                        clock.set_background_color(bg_qcolor)
                except Exception:
                    pass

                # Background border customization (inherits from main clock for clock2/clock3)
                try:
                    br_r, br_g, br_b = border_color_data[0], border_color_data[1], border_color_data[2]
                    base_alpha = border_color_data[3] if len(border_color_data) > 3 else 255
                    try:
                        bo = float(border_opacity_val)
                    except Exception:
                        bo = 0.8
                    bo = max(0.0, min(1.0, bo))
                    br_a = int(bo * base_alpha)
                    border_qcolor = QColor(br_r, br_g, br_b, br_a)
                    if hasattr(clock, "set_background_border"):
                        clock.set_background_border(2, border_qcolor)
                except Exception:
                    pass

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
                from PySide6.QtGui import QColor
                qcolor = QColor(color[0], color[1], color[2], color[3])
                self.weather_widget.set_text_color(qcolor)

                # Background/frame customization
                show_background = SettingsManager.to_bool(
                    weather_settings.get('show_background', True), True
                )
                self.weather_widget.set_show_background(show_background)

                # Background color (RGB+alpha), default matches WeatherWidget internal default
                bg_color_data = weather_settings.get('bg_color', [35, 35, 35, 255])
                try:
                    bg_r, bg_g, bg_b = bg_color_data[0], bg_color_data[1], bg_color_data[2]
                    bg_a = bg_color_data[3] if len(bg_color_data) > 3 else 255
                    bg_qcolor = QColor(bg_r, bg_g, bg_b, bg_a)
                    self.weather_widget.set_background_color(bg_qcolor)
                except Exception:
                    pass

                # Background opacity (scales alpha regardless of bg_color alpha)
                bg_opacity = weather_settings.get('bg_opacity', 0.7)
                self.weather_widget.set_background_opacity(bg_opacity)

                # Border color and opacity (independent from background opacity)
                border_color_data = weather_settings.get('border_color', [255, 255, 255, 255])
                border_opacity = weather_settings.get('border_opacity', 1.0)
                try:
                    br_r, br_g, br_b = (
                        border_color_data[0],
                        border_color_data[1],
                        border_color_data[2],
                    )
                    base_alpha = border_color_data[3] if len(border_color_data) > 3 else 255
                    br_a = int(max(0.0, min(1.0, float(border_opacity))) * base_alpha)
                    border_qcolor = QColor(br_r, br_g, br_b, br_a)
                    # Border width remains driven by WeatherWidget's defaults (2px)
                    self.weather_widget.set_background_border(2, border_qcolor)
                except Exception:
                    pass
                # Show/hide condition icons; default to OFF so the textual
                # summary is the primary signal unless the user explicitly
                # enables icons in the Widgets tab.
                show_icons = SettingsManager.to_bool(weather_settings.get('show_icons', False), False)
                if hasattr(self.weather_widget, 'set_show_icons'):
                    self.weather_widget.set_show_icons(show_icons)

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

                from PySide6.QtGui import QColor

                try:
                    qcolor = QColor(color[0], color[1], color[2], color[3])
                    self.reddit_widget.set_text_color(qcolor)
                except Exception:
                    pass

                self.reddit_widget.set_show_background(show_background)

                try:
                    self.reddit_widget.set_show_separators(show_separators)
                except Exception:
                    pass

                # Background color
                try:
                    bg_r, bg_g, bg_b = bg_color_data[0], bg_color_data[1], bg_color_data[2]
                    bg_a = bg_color_data[3] if len(bg_color_data) > 3 else 255
                    bg_qcolor = QColor(bg_r, bg_g, bg_b, bg_a)
                    self.reddit_widget.set_background_color(bg_qcolor)
                except Exception:
                    pass

                # Background opacity
                try:
                    bg_opacity_f = float(bg_opacity)
                except Exception:
                    bg_opacity_f = 0.9
                self.reddit_widget.set_background_opacity(bg_opacity_f)

                # Border color and opacity
                try:
                    br_r, br_g, br_b = border_color_data[0], border_color_data[1], border_color_data[2]
                    base_alpha = border_color_data[3] if len(border_color_data) > 3 else 255
                    try:
                        bo = float(border_opacity)
                    except Exception:
                        bo = 0.8
                    bo = max(0.0, min(1.0, bo))
                    br_a = int(bo * base_alpha)
                    border_qcolor = QColor(br_r, br_g, br_b, br_a)
                    self.reddit_widget.set_background_border(2, border_qcolor)
                except Exception:
                    pass

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
            from PySide6.QtGui import QColor

            try:
                qcolor = QColor(color[0], color[1], color[2], color[3])
                self.media_widget.set_text_color(qcolor)
            except Exception:
                pass

            # Default to a visible background frame for media so the
            # Spotify block stands out even on bright images. Users can
            # still override this via widgets.media.show_background.
            show_background = SettingsManager.to_bool(
                media_settings.get('show_background', True), True
            )
            self.media_widget.set_show_background(show_background)

            # Background color
            bg_color_data = media_settings.get('bg_color', [64, 64, 64, 255])
            bg_qcolor = QColor(64, 64, 64, 255)
            try:
                bg_r, bg_g, bg_b = bg_color_data[0], bg_color_data[1], bg_color_data[2]
                bg_a = bg_color_data[3] if len(bg_color_data) > 3 else 255
                bg_qcolor = QColor(bg_r, bg_g, bg_b, bg_a)
                self.media_widget.set_background_color(bg_qcolor)
            except Exception:
                try:
                    self.media_widget.set_background_color(bg_qcolor)
                except Exception:
                    pass

            # Background opacity
            try:
                bg_opacity = float(media_settings.get('bg_opacity', 0.9))
            except Exception:
                bg_opacity = 0.9
            self.media_widget.set_background_opacity(bg_opacity)

            # Border color and opacity
            border_color_data = media_settings.get('border_color', [128, 128, 128, 255])
            border_opacity = media_settings.get('border_opacity', 0.8)
            border_qcolor = QColor(128, 128, 128, 255)
            try:
                br_r, br_g, br_b = (
                    border_color_data[0],
                    border_color_data[1],
                    border_color_data[2],
                )
                base_alpha = border_color_data[3] if len(border_color_data) > 3 else 255
                try:
                    bo = float(border_opacity)
                except Exception:
                    bo = 0.8
                bo = max(0.0, min(1.0, bo))
                br_a = int(bo * base_alpha)
                border_qcolor = QColor(br_r, br_g, br_b, br_a)
                self.media_widget.set_background_border(2, border_qcolor)
            except Exception:
                try:
                    self.media_widget.set_background_border(2, border_qcolor)
                except Exception:
                    pass

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

                    # Inherit media card background and border colours for the
                    # track, while using a dedicated (default white) fill
                    # colour for the volume bar itself.
                    try:
                        from PySide6.QtGui import QColor as _QColor

                        fill_color = _QColor(255, 255, 255, 230)
                        if hasattr(vol, "set_colors"):
                            vol.set_colors(track_bg=bg_qcolor, track_border=border_qcolor, fill=fill_color)
                    except Exception:
                        pass

                    try:
                        vol.start()
                    except Exception:
                        logger.debug("[SPOTIFY_VOL] Failed to start volume widget", exc_info=True)

                    try:
                        self._position_spotify_volume()
                    except Exception:
                        pass
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

    def _warm_up_gl_overlay(self, base_pixmap: QPixmap) -> None:
        """Legacy GL overlay warm-up disabled (compositor-only pipeline)."""
        logger.debug("[WARMUP] Skipping legacy GL overlay warm-up (compositor-only pipeline)")
        return

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
        try:
            overlays_to_raise = [
                "media_widget",
                "spotify_visualizer_widget",
                "spotify_volume_widget",
                "weather_widget",
                "reddit_widget",
            ]
            for attr_name in overlays_to_raise:
                try:
                    w = getattr(self, attr_name, None)
                except Exception:
                    w = None
                if w is None:
                    continue
                try:
                    if w.isVisible():
                        w.raise_()
                except Exception:
                    continue
        except Exception:
            pass

    def _prewarm_gl_contexts(self) -> None:
        """
        Legacy GL overlay prewarm disabled now that compositor is the only GL path.
        """
        logger.debug("[PREWARM] Skipping legacy GL overlay prewarm (compositor-only pipeline)")
        return

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

    def _perform_initial_gl_flush(self) -> None:
        """Force a synchronous Present/flush on persistent overlays to avoid black frames."""

        if self._gl_initial_flush_done:
            return

        if GL is None:
            logger.info("[INIT] Skipping low-level GL flush; PyOpenGL not available (using QOpenGLWidget/QSurface flush only)")
            self._gl_initial_flush_done = True
            return

        flushed = 0
        for attr_name in GL_OVERLAY_KEYS:
            overlay = getattr(self, attr_name, None)
            if overlay is None:
                continue
            try:
                if hasattr(overlay, "makeCurrent"):
                    overlay.makeCurrent()
                try:
                    overlay.repaint()
                except Exception:
                    pass
                try:
                    GL.glFinish()
                except Exception:
                    pass
                try:
                    ctx = overlay.context() if hasattr(overlay, "context") else None
                    if ctx is not None:
                        funcs = ctx.functions()
                        if funcs is not None:
                            funcs.glFlush()
                except Exception:
                    pass
                try:
                    if hasattr(overlay, "doneCurrent"):
                        overlay.doneCurrent()
                except Exception:
                    pass
                flushed += 1
            except Exception as exc:
                logger.debug(f"[INIT] Failed to flush overlay '{attr_name}': {exc}")

        self._gl_initial_flush_done = True
        logger.info("[INIT] Initial GL flush complete (flushed %s overlays)", flushed)
    
    def _create_transition(self) -> Optional[BaseTransition]:
        """Create the next transition, honoring live settings overrides."""
        if not self.settings_manager:
            return None

        transitions_settings = self.settings_manager.get('transitions', {})
        if not isinstance(transitions_settings, dict):
            transitions_settings = {}

        # Canonical transition type comes from nested config
        transition_type = transitions_settings.get('type') or 'Crossfade'
        requested_type = transition_type

        try:
            # Random mode configured via nested flag; engine may still publish
            # a per-rotation choice in 'transitions.random_choice'.
            rnd = transitions_settings.get('random_always', False)
            rnd = SettingsManager.to_bool(rnd, False)
            random_mode = bool(rnd)
            random_choice_value = None
            if random_mode:
                chosen = self.settings_manager.get('transitions.random_choice', None)
                if isinstance(chosen, str) and chosen:
                    transition_type = chosen
                    random_choice_value = chosen
        except Exception:
            random_mode = False
            random_choice_value = None

        base_duration_raw = transitions_settings.get('duration_ms', 1300)
        try:
            base_duration_ms = int(base_duration_raw)
        except Exception:
            base_duration_ms = 1300

        duration_ms = base_duration_ms
        try:
            durations_cfg = transitions_settings.get('durations', {})
            if isinstance(durations_cfg, dict):
                per_type_raw = durations_cfg.get(transition_type)
                if per_type_raw is not None:
                    try:
                        duration_ms = int(per_type_raw)
                    except Exception:
                        duration_ms = base_duration_ms
        except Exception:
            duration_ms = base_duration_ms

        try:
            easing_str = transitions_settings.get('easing') or 'Auto'

            try:
                hw_raw = self.settings_manager.get('display.hw_accel', True)
            except Exception:
                hw_raw = True
            hw_accel = SettingsManager.to_bool(hw_raw, True)

            if transition_type == 'Crossfade':
                if hw_accel:
                    try:
                        self._ensure_gl_compositor()
                    except Exception:
                        logger.debug("[GL COMPOSITOR] Failed to ensure compositor during crossfade selection", exc_info=True)
                    use_compositor = isinstance(getattr(self, "_gl_compositor", None), GLCompositorWidget)
                    if use_compositor:
                        transition = GLCompositorCrossfadeTransition(duration_ms, easing_str)
                    else:
                        # If compositor cannot be used, prefer CPU crossfade over
                        # the legacy GL overlay path to avoid reintroducing
                        # overlay-related flicker.
                        transition = CrossfadeTransition(duration_ms, easing_str)
                else:
                    transition = CrossfadeTransition(duration_ms, easing_str)
                transition.set_resource_manager(self._resource_manager)
                self._log_transition_selection(requested_type, 'Crossfade', random_mode, random_choice_value)
                return transition

            if transition_type == 'Slide':
                slide_settings = transitions_settings.get('slide', {}) if isinstance(transitions_settings.get('slide', {}), dict) else {}
                direction_str = slide_settings.get('direction', 'Random') or 'Random'

                direction_map = {
                    'Left to Right': SlideDirection.LEFT,
                    'Right to Left': SlideDirection.RIGHT,
                    'Top to Bottom': SlideDirection.DOWN,
                    'Bottom to Top': SlideDirection.UP,
                }

                rnd_always = SettingsManager.to_bool(transitions_settings.get('random_always', False), False)

                if direction_str == 'Random' and not rnd_always:
                    all_dirs = [SlideDirection.LEFT, SlideDirection.RIGHT, SlideDirection.UP, SlideDirection.DOWN]
                    last_dir = slide_settings.get('last_direction')
                    str_to_enum = {
                        'Left to Right': SlideDirection.LEFT,
                        'Right to Left': SlideDirection.RIGHT,
                        'Top to Bottom': SlideDirection.DOWN,
                        'Bottom to Top': SlideDirection.UP,
                    }
                    last_enum = str_to_enum.get(last_dir) if isinstance(last_dir, str) else None
                    candidates = [d for d in all_dirs if d != last_enum] if last_enum in all_dirs else all_dirs
                    direction = random.choice(candidates) if candidates else random.choice(all_dirs)
                    enum_to_str = {
                        SlideDirection.LEFT: 'Left to Right',
                        SlideDirection.RIGHT: 'Right to Left',
                        SlideDirection.DOWN: 'Top to Bottom',
                        SlideDirection.UP: 'Bottom to Top',
                    }
                    try:
                        slide_settings['last_direction'] = enum_to_str.get(direction, 'Left to Right')
                        transitions_settings['slide'] = slide_settings
                        self.settings_manager.set('transitions', transitions_settings)
                    except Exception:
                        pass
                else:
                    direction = direction_map.get(direction_str, SlideDirection.LEFT)

                if hw_accel:
                    try:
                        self._ensure_gl_compositor()
                    except Exception:
                        logger.debug("[GL COMPOSITOR] Failed to ensure compositor during slide selection", exc_info=True)
                    use_compositor = isinstance(getattr(self, "_gl_compositor", None), GLCompositorWidget)
                    if use_compositor:
                        transition = GLCompositorSlideTransition(duration_ms, direction, easing_str)
                    else:
                        # If compositor cannot be used, prefer CPU slide over
                        # the legacy GL overlay path.
                        transition = SlideTransition(duration_ms, direction, easing_str)
                else:
                    transition = SlideTransition(duration_ms, direction, easing_str)
                transition.set_resource_manager(self._resource_manager)
                self._log_transition_selection(requested_type, 'Slide', random_mode, random_choice_value)
                return transition

            if transition_type == 'Wipe':
                wipe_settings = transitions_settings.get('wipe', {}) if isinstance(transitions_settings.get('wipe', {}), dict) else {}
                wipe_dir_str = wipe_settings.get('direction', 'Random') or 'Random'

                direction_map = {
                    'Left to Right': WipeDirection.LEFT_TO_RIGHT,
                    'Right to Left': WipeDirection.RIGHT_TO_LEFT,
                    'Top to Bottom': WipeDirection.TOP_TO_BOTTOM,
                    'Bottom to Top': WipeDirection.BOTTOM_TO_TOP,
                    'Diagonal TL-BR': WipeDirection.DIAG_TL_BR,
                    'Diagonal TR-BL': WipeDirection.DIAG_TR_BL,
                }

                rnd_always = self.settings_manager.get('transitions.random_always', None)
                if rnd_always is None:
                    rnd_always = transitions_settings.get('random_always', False)
                rnd_always = SettingsManager.to_bool(rnd_always, False)

                if wipe_dir_str and wipe_dir_str in direction_map and not (wipe_dir_str == 'Random' and not rnd_always):
                    direction = direction_map[wipe_dir_str]
                else:
                    all_wipes = list(direction_map.values())
                    last_wipe = wipe_settings.get('last_direction')
                    str_to_enum = {name: enum for name, enum in direction_map.items()}
                    last_enum = str_to_enum.get(last_wipe) if isinstance(last_wipe, str) else None
                    candidates = [d for d in all_wipes if d != last_enum] if last_enum in all_wipes else all_wipes
                    direction = random.choice(candidates) if candidates else random.choice(all_wipes)
                    enum_to_str = {enum: name for name, enum in direction_map.items()}
                    try:
                        wipe_settings['last_direction'] = enum_to_str.get(direction, 'Left to Right')
                        transitions_settings['wipe'] = wipe_settings
                        self.settings_manager.set('transitions', transitions_settings)
                    except Exception:
                        pass

                if hw_accel:
                    try:
                        self._ensure_gl_compositor()
                    except Exception:
                        logger.debug("[GL COMPOSITOR] Failed to ensure compositor during wipe selection", exc_info=True)
                    use_compositor = isinstance(getattr(self, "_gl_compositor", None), GLCompositorWidget)
                    if use_compositor:
                        transition = GLCompositorWipeTransition(duration_ms, direction, easing_str)
                    else:
                        # Prefer CPU wipe over the legacy GL overlay path when the
                        # compositor cannot be used, to avoid reintroducing
                        # overlay-related flicker.
                        transition = WipeTransition(duration_ms, direction, easing_str)
                else:
                    transition = WipeTransition(duration_ms, direction, easing_str)

                transition.set_resource_manager(self._resource_manager)
                self._log_transition_selection(requested_type, 'Wipe', random_mode, random_choice_value)
                return transition

            if transition_type == 'Peel':
                peel_settings = transitions_settings.get('peel', {}) if isinstance(transitions_settings.get('peel', {}), dict) else {}
                peel_dir_str = peel_settings.get('direction', 'Random') or 'Random'

                direction_map = {
                    'Left to Right': SlideDirection.LEFT,
                    'Right to Left': SlideDirection.RIGHT,
                    'Top to Bottom': SlideDirection.DOWN,
                    'Bottom to Top': SlideDirection.UP,
                }

                rnd_always = SettingsManager.to_bool(transitions_settings.get('random_always', False), False)

                if peel_dir_str == 'Random' and not rnd_always:
                    all_dirs = [
                        SlideDirection.LEFT,
                        SlideDirection.RIGHT,
                        SlideDirection.UP,
                        SlideDirection.DOWN,
                    ]
                    last_dir = peel_settings.get('last_direction')
                    str_to_enum = {
                        'Left to Right': SlideDirection.LEFT,
                        'Right to Left': SlideDirection.RIGHT,
                        'Top to Bottom': SlideDirection.DOWN,
                        'Bottom to Top': SlideDirection.UP,
                    }
                    last_enum = str_to_enum.get(last_dir) if isinstance(last_dir, str) else None
                    candidates = [d for d in all_dirs if d != last_enum] if last_enum in all_dirs else all_dirs
                    direction = random.choice(candidates) if candidates else random.choice(all_dirs)
                    enum_to_str = {
                        SlideDirection.LEFT: 'Left to Right',
                        SlideDirection.RIGHT: 'Right to Left',
                        SlideDirection.DOWN: 'Top to Bottom',
                        SlideDirection.UP: 'Bottom to Top',
                    }
                    try:
                        peel_settings['last_direction'] = enum_to_str.get(direction, 'Left to Right')
                        transitions_settings['peel'] = peel_settings
                        self.settings_manager.set('transitions', transitions_settings)
                    except Exception:
                        pass
                else:
                    direction = direction_map.get(peel_dir_str, SlideDirection.LEFT)

                strips = 12  # Moderate default strip count for a smooth peel

                if hw_accel:
                    try:
                        self._ensure_gl_compositor()
                    except Exception:
                        logger.debug("[GL COMPOSITOR] Failed to ensure compositor during peel selection", exc_info=True)
                    use_compositor = isinstance(getattr(self, "_gl_compositor", None), GLCompositorWidget)
                    if use_compositor:
                        transition = GLCompositorPeelTransition(duration_ms, direction, strips, easing_str)
                    else:
                        # When compositor cannot be used, prefer a CPU
                        # Crossfade fallback instead of attempting a partial
                        # peel implementation.
                        transition = CrossfadeTransition(duration_ms, easing_str)
                else:
                    transition = CrossfadeTransition(duration_ms, easing_str)

                transition.set_resource_manager(self._resource_manager)
                label = 'Peel' if hw_accel else 'Crossfade'
                self._log_transition_selection(requested_type, label, random_mode, random_choice_value)
                return transition

            if transition_type == 'Shuffle':
                # Shuffle has been retired for v1.2. Any legacy configurations
                # that still reference this label are mapped to a simple
                # Crossfade so settings remain valid without exposing Shuffle
                # in the active transition set.

                transition = CrossfadeTransition(duration_ms, easing_str)
                transition.set_resource_manager(self._resource_manager)
                label = 'Crossfade'
                self._log_transition_selection(requested_type, label, random_mode, random_choice_value)
                return transition

            if transition_type == 'Warp Dissolve':
                # Warp Dissolve is implemented as a compositor-driven banded
                # warp of the old image over a stable new image. It is GL-only
                # and falls back to a simple crossfade when GPU acceleration
                # or the compositor is unavailable.

                if hw_accel:
                    try:
                        self._ensure_gl_compositor()
                    except Exception:
                        logger.debug("[GL COMPOSITOR] Failed to ensure compositor during warp dissolve selection", exc_info=True)
                    use_compositor = isinstance(getattr(self, "_gl_compositor", None), GLCompositorWidget)
                    if use_compositor:
                        transition = GLCompositorWarpTransition(duration_ms, easing_str)
                    else:
                        transition = CrossfadeTransition(duration_ms, easing_str)
                else:
                    transition = CrossfadeTransition(duration_ms, easing_str)

                transition.set_resource_manager(self._resource_manager)
                label = 'Warp Dissolve' if hw_accel else 'Crossfade'
                self._log_transition_selection(requested_type, label, random_mode, random_choice_value)
                return transition

            if transition_type == 'Diffuse':
                diffuse_settings = transitions_settings.get('diffuse', {}) if isinstance(transitions_settings.get('diffuse', {}), dict) else {}
                block_size_raw = diffuse_settings.get('block_size', 50)
                try:
                    block_size = int(block_size_raw)
                except Exception:
                    block_size = 50
                shape = diffuse_settings.get('shape', 'Rectangle') or 'Rectangle'

                if hw_accel:
                    try:
                        self._ensure_gl_compositor()
                    except Exception:
                        logger.debug("[GL COMPOSITOR] Failed to ensure compositor during diffuse selection", exc_info=True)
                    use_compositor = isinstance(getattr(self, "_gl_compositor", None), GLCompositorWidget)
                    if use_compositor:
                        transition = GLCompositorDiffuseTransition(duration_ms, block_size, shape, easing_str)
                    else:
                        transition = DiffuseTransition(duration_ms, block_size, shape)
                else:
                    transition = DiffuseTransition(duration_ms, block_size, shape)

                transition.set_resource_manager(self._resource_manager)
                self._log_transition_selection(requested_type, 'Diffuse', random_mode, random_choice_value)
                return transition

            if transition_type in ('Rain Drops', 'Ripple'):
                # Ripple is implemented as a compositor-driven variant of
                # the diffuse mask using circular, expanding droplets. It is
                # GL-only and falls back to a simple crossfade when GPU
                # acceleration or the compositor is unavailable.

                if hw_accel:
                    try:
                        self._ensure_gl_compositor()
                    except Exception:
                        logger.debug("[GL COMPOSITOR] Failed to ensure compositor during rain drops selection", exc_info=True)
                    use_compositor = isinstance(getattr(self, "_gl_compositor", None), GLCompositorWidget)
                    if use_compositor:
                        transition = GLCompositorRainDropsTransition(duration_ms, easing_str)
                    else:
                        transition = CrossfadeTransition(duration_ms, easing_str)
                else:
                    transition = CrossfadeTransition(duration_ms, easing_str)

                transition.set_resource_manager(self._resource_manager)
                label = 'Ripple' if hw_accel else 'Crossfade'
                self._log_transition_selection(requested_type, label, random_mode, random_choice_value)
                return transition

            if transition_type == 'Claw Marks':
                # Claw Marks / Shooting Stars has been removed as a transition
                # type. Any legacy requests for this label are now mapped to a
                # safe Crossfade so existing settings do not break.

                transition = CrossfadeTransition(duration_ms, easing_str)
                transition.set_resource_manager(self._resource_manager)
                self._log_transition_selection(requested_type, 'Crossfade', random_mode, random_choice_value)
                return transition

            if transition_type == 'Block Puzzle Flip':
                block_flip_settings = transitions_settings.get('block_flip', {}) if isinstance(transitions_settings.get('block_flip', {}), dict) else {}
                rows_raw = block_flip_settings.get('rows', 4)
                cols_raw = block_flip_settings.get('cols', 6)
                try:
                    rows = int(rows_raw)
                except Exception:
                    rows = 4
                try:
                    cols = int(cols_raw)
                except Exception:
                    cols = 6

                # Direction bias: reuse the Slide cardinal direction model so
                # Block Puzzle Flip can emit a wave that respects the selected
                # edge (Left/Right/Top/Bottom). When no usable direction is
                # configured we fall back to the original fully-random order.
                blockflip_direction: Optional[SlideDirection] = None
                try:
                    slide_cfg = transitions_settings.get('slide', {}) if isinstance(transitions_settings.get('slide', {}), dict) else {}
                    dir_str = slide_cfg.get('direction', 'Random') or 'Random'

                    direction_map = {
                        'Left to Right': SlideDirection.LEFT,
                        'Right to Left': SlideDirection.RIGHT,
                        'Top to Bottom': SlideDirection.DOWN,
                        'Bottom to Top': SlideDirection.UP,
                    }

                    rnd_always = SettingsManager.to_bool(transitions_settings.get('random_always', False), False)

                    if dir_str == 'Random' and not rnd_always:
                        # Mirror the Slide transition's non-repeating random
                        # selection so BlockFlip shares the same edge bias.
                        all_dirs = [
                            SlideDirection.LEFT,
                            SlideDirection.RIGHT,
                            SlideDirection.UP,
                            SlideDirection.DOWN,
                        ]
                        last_dir = slide_cfg.get('last_direction')
                        str_to_enum = {
                            'Left to Right': SlideDirection.LEFT,
                            'Right to Left': SlideDirection.RIGHT,
                            'Top to Bottom': SlideDirection.DOWN,
                            'Bottom to Top': SlideDirection.UP,
                        }
                        last_enum = str_to_enum.get(last_dir) if isinstance(last_dir, str) else None
                        candidates = [d for d in all_dirs if d != last_enum] if last_enum in all_dirs else all_dirs
                        blockflip_direction = random.choice(candidates) if candidates else random.choice(all_dirs)

                        enum_to_str = {
                            SlideDirection.LEFT: 'Left to Right',
                            SlideDirection.RIGHT: 'Right to Left',
                            SlideDirection.DOWN: 'Top to Bottom',
                            SlideDirection.UP: 'Bottom to Top',
                        }
                        try:
                            slide_cfg['last_direction'] = enum_to_str.get(blockflip_direction, 'Left to Right')
                            transitions_settings['slide'] = slide_cfg
                            self.settings_manager.set('transitions', transitions_settings)
                        except Exception:
                            pass
                    else:
                        blockflip_direction = direction_map.get(dir_str, None)
                except Exception:
                    # On any error, keep direction bias disabled for this run.
                    blockflip_direction = None

                if hw_accel:
                    try:
                        self._ensure_gl_compositor()
                    except Exception:
                        logger.debug("[GL COMPOSITOR] Failed to ensure compositor during block flip selection", exc_info=True)
                    use_compositor = isinstance(getattr(self, "_gl_compositor", None), GLCompositorWidget)
                    if use_compositor:
                        transition = GLCompositorBlockFlipTransition(duration_ms, rows, cols, flip_duration_ms=500, direction=blockflip_direction)
                    else:
                        # Prefer CPU BlockPuzzleFlipTransition over the legacy GL
                        # overlay path when the compositor cannot be used.
                        transition = BlockPuzzleFlipTransition(duration_ms, rows, cols, flip_duration_ms=500, direction=blockflip_direction)
                else:
                    transition = BlockPuzzleFlipTransition(duration_ms, rows, cols, flip_duration_ms=500, direction=blockflip_direction)

                transition.set_resource_manager(self._resource_manager)
                self._log_transition_selection(requested_type, 'Block Puzzle Flip', random_mode, random_choice_value)
                return transition

            if transition_type == '3D Block Spins':
                # Direction configuration for the single-slab 3D Block Spins
                # transition. Grid mode has been removed; the shader always
                # renders a single full-frame slab driven by this direction.
                blockspin_settings = transitions_settings.get('blockspin', {}) if isinstance(transitions_settings.get('blockspin', {}), dict) else {}
                dir_str = blockspin_settings.get('direction', 'Random') or 'Random'

                # Map UI string to SlideDirection, with Random choosing a
                # random cardinal direction at selection time.
                if dir_str == 'Random':
                    dir_choice = random.choice([
                        SlideDirection.LEFT,
                        SlideDirection.RIGHT,
                        SlideDirection.UP,
                        SlideDirection.DOWN,
                    ])
                else:
                    direction_map = {
                        'Left to Right': SlideDirection.LEFT,
                        'Right to Left': SlideDirection.RIGHT,
                        'Top to Bottom': SlideDirection.DOWN,
                        'Bottom to Top': SlideDirection.UP,
                    }
                    dir_choice = direction_map.get(dir_str, SlideDirection.LEFT)

                if hw_accel:
                    try:
                        self._ensure_gl_compositor()
                    except Exception:
                        logger.debug("[GL COMPOSITOR] Failed to ensure compositor during block spins selection", exc_info=True)
                    use_compositor = isinstance(getattr(self, "_gl_compositor", None), GLCompositorWidget)
                    if use_compositor:
                        transition = GLCompositorBlockSpinTransition(duration_ms, easing_str, dir_choice)
                    else:
                        # When compositor cannot be used, prefer a CPU Crossfade
                        # fallback instead of attempting a partial block spins
                        # implementation.
                        transition = CrossfadeTransition(duration_ms, easing_str)
                else:
                    transition = CrossfadeTransition(duration_ms, easing_str)

                transition.set_resource_manager(self._resource_manager)
                label = '3D Block Spins' if hw_accel else 'Crossfade'
                self._log_transition_selection(requested_type, label, random_mode, random_choice_value)
                return transition

            if transition_type == 'Blinds':
                if hw_accel:
                    try:
                        self._ensure_gl_compositor()
                    except Exception:
                        logger.debug("[GL COMPOSITOR] Failed to ensure compositor during blinds selection", exc_info=True)
                    use_compositor = isinstance(getattr(self, "_gl_compositor", None), GLCompositorWidget)
                    if use_compositor:
                        transition = GLCompositorBlindsTransition(duration_ms)
                    else:
                        # When compositor cannot be used, prefer a CPU
                        # Crossfade fallback instead of the legacy GL Blinds
                        # overlay path.
                        transition = CrossfadeTransition(duration_ms)
                else:
                    transition = CrossfadeTransition(duration_ms)

                transition.set_resource_manager(self._resource_manager)
                label = 'Blinds' if hw_accel else 'Crossfade'
                self._log_transition_selection(requested_type, label, random_mode, random_choice_value)
                return transition

            logger.warning("Unknown transition type: %s, using Crossfade", transition_type)
            transition = CrossfadeTransition(duration_ms)
            transition.set_resource_manager(self._resource_manager)
            self._log_transition_selection(requested_type, 'Crossfade', random_mode, random_choice_value)
            return transition

        except Exception as exc:
            logger.error("Failed to create transition: %s", exc, exc_info=True)
            return None

    def _log_transition_selection(self, requested: str, actual: str, random_mode: bool, random_choice: Optional[str]) -> None:
        try:
            if requested != actual:
                logger.info(
                    "[TRANSITIONS] Requested '%s' but instantiating '%s' (random_mode=%s, random_choice=%s)",
                    requested,
                    actual,
                    random_mode,
                    random_choice,
                )
            else:
                logger.debug(
                    "[TRANSITIONS] Instantiating '%s' (requested=%s, random_mode=%s, random_choice=%s)",
                    actual,
                    requested,
                    random_mode,
                    random_choice,
                )
        except Exception:
            pass
    
    def set_image(self, pixmap: QPixmap, image_path: str = "") -> None:
        """
        Display a new image with transition.
        
        Args:
            pixmap: Image to display
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

        if pixmap.isNull():
            logger.warning("[FALLBACK] Received null pixmap")
            self.error_message = "Failed to load image"
            self.current_pixmap = None
            self.update()
            return
        
        # Process image for display at physical resolution for quality
        # Use physical pixels (logical size * DPI ratio) to avoid double-scaling quality loss
        logical_size = self.size()
        screen_size = QSize(
            int(logical_size.width() * self._device_pixel_ratio),
            int(logical_size.height() * self._device_pixel_ratio)
        )
        logger.debug(f"[IMAGE QUALITY] Logical: {logical_size.width()}x{logical_size.height()}, "
                    f"Physical: {screen_size.width()}x{screen_size.height()} (DPR={self._device_pixel_ratio})")
        
        # Get quality settings (force-disable Lanczos; keep sharpen)
        use_lanczos = False
        sharpen = False
        if self.settings_manager:
            # Lanczos intentionally ignored due to distortion; keep False
            sharpen = self.settings_manager.get('display.sharpen_downscale', False)
            if isinstance(sharpen, str):
                sharpen = sharpen.lower() == 'true'
        
        # CRITICAL FIX: Transitions ALWAYS use screen-fitted pixmaps
        # Pan & scan scaling happens AFTER transition finishes
        # This fixes block puzzle, wipe, and diffuse distortions
        processed_pixmap = ImageProcessor.process_image(
            pixmap,
            screen_size,
            self.display_mode,
            use_lanczos,
            sharpen
        )

        # Keep original pixmap for any future processing separate from the
        # screen-fitted frame used for transitions.
        original_pixmap = pixmap

        # For both GL and software transitions we now always present the
        # processed, screen-fitted pixmap.
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
                    for attr_name in ("clock_widget", "clock2_widget", "clock3_widget"):
                        clock = getattr(self, attr_name, None)
                        if clock is not None:
                            try:
                                clock.raise_()
                                if hasattr(clock, "_tz_label") and clock._tz_label:
                                    clock._tz_label.raise_()
                            except Exception:
                                pass
                    if getattr(self, "weather_widget", None) is not None:
                        try:
                            self.weather_widget.raise_()
                        except Exception:
                            pass
                    # Keep media widget above compositor as well so the
                    # Spotify overlay never disappears during GL transitions.
                    mw = getattr(self, "media_widget", None)
                    if mw is not None:
                        try:
                            mw.raise_()
                        except Exception:
                            pass
                    # Raise Reddit widget too so it remains above transitions,
                    # but do not force it visible here; first visibility is
                    # owned by the widget's own fade-in path.
                    rw = getattr(self, "reddit_widget", None)
                    if rw is not None:
                        try:
                            rw.raise_()
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
                        try:
                            self._ensure_overlay_stack(stage="transition_start")
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

                logger.debug(f"Image displayed: {image_path} ({pixmap.width()}x{pixmap.height()})")
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
        # Ensure base repaint is flushed before we remove any overlay to avoid flicker
        try:
            self._ensure_overlay_stack(stage="transition_finish")
        except Exception:
            pass
        try:
            self.repaint()
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

    def _on_destroyed(self, *_args) -> None:
        """Ensure active transitions are stopped when the widget is destroyed."""
        self._destroy_render_surface()
        # Ensure compositor is torn down cleanly
        try:
            if self._gl_compositor is not None:
                try:
                    cleanup = getattr(self._gl_compositor, "cleanup", None)
                    if callable(cleanup):
                        cleanup()
                except Exception as e:
                    logger.debug("[GL COMPOSITOR] Cleanup failed in _on_destroyed: %s", e, exc_info=True)
                self._gl_compositor.hide()
                self._gl_compositor.setParent(None)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Failed to tear down compositor in _on_destroyed: %s", e, exc_info=True)
        self._gl_compositor = None
        # Stop Spotify Beat Visualizer if present
        try:
            vis = getattr(self, "spotify_visualizer_widget", None)
            if vis is not None:
                try:
                    vis.stop()
                except Exception:
                    pass
                try:
                    vis.hide()
                except Exception:
                    pass
                self.spotify_visualizer_widget = None
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Failed to stop visualizer in _on_destroyed: %s", e, exc_info=True)
        # Stop Media widget if present
        try:
            mw = getattr(self, "media_widget", None)
            if mw is not None:
                try:
                    cleanup = getattr(mw, "cleanup", None)
                    if callable(cleanup):
                        cleanup()
                except Exception:
                    pass
                try:
                    mw.hide()
                except Exception:
                    pass
                self.media_widget = None
        except Exception as e:
            logger.debug("[MEDIA] Failed to stop media widget in _on_destroyed: %s", e, exc_info=True)
        # Stop Weather widget if present
        try:
            ww = getattr(self, "weather_widget", None)
            if ww is not None:
                try:
                    cleanup = getattr(ww, "cleanup", None)
                    if callable(cleanup):
                        cleanup()
                except Exception:
                    pass
                try:
                    ww.hide()
                except Exception:
                    pass
                self.weather_widget = None
        except Exception as e:
            logger.debug("[WEATHER] Failed to stop weather widget in _on_destroyed: %s", e, exc_info=True)
        # Stop Reddit widget if present
        try:
            rw = getattr(self, "reddit_widget", None)
            if rw is not None:
                try:
                    cleanup = getattr(rw, "cleanup", None)
                    if callable(cleanup):
                        cleanup()
                except Exception:
                    pass
                try:
                    rw.hide()
                except Exception:
                    pass
                self.reddit_widget = None
        except Exception as e:
            logger.debug("[REDDIT] Failed to stop Reddit widget in _on_destroyed: %s", e, exc_info=True)
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
            logger.debug("[TRANSITION] Failed to stop/cleanup current transition in _on_destroyed: %s", e, exc_info=True)
        # Hide overlays and cancel watchdog timer
        try:
            hide_all_overlays(self)
        except Exception as e:
            logger.debug("[OVERLAYS] Failed to hide overlays in _on_destroyed: %s", e, exc_info=True)
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

        for starter in starters:
            try:
                starter()
            except Exception:
                pass

    def get_overlay_stage_counts(self) -> dict[str, int]:
        """Return snapshot of overlay readiness counts (for diagnostics/tests)."""
        return dict(self._overlay_stage_counts)

    def _ensure_ctrl_cursor_hint(self) -> None:
        if self._ctrl_cursor_hint is not None:
            return
        from PySide6.QtWidgets import QWidget as _W
        from PySide6.QtGui import QColor

        class _CtrlCursorHint(_W):
            def __init__(self, parent: _W) -> None:
                super().__init__(parent)
                self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                self.resize(40, 40)
                self._opacity = 1.0

            def setOpacity(self, value: float) -> None:
                try:
                    self._opacity = max(0.0, min(1.0, float(value)))
                except Exception:
                    self._opacity = 1.0
                self.update()

            def opacity(self) -> float:
                return float(self._opacity)

            def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                base_alpha = 200
                alpha = int(max(0.0, min(1.0, self._opacity)) * base_alpha)
                color = QColor(255, 255, 255, alpha)

                # Thicker outer ring
                pen = painter.pen()
                pen.setColor(color)
                pen.setWidth(4)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                r = min(self.width(), self.height()) - 8
                painter.drawEllipse(4, 4, r, r)

                # Inner solid dot to suggest the click position
                inner_radius = max(2, r // 6)
                cx = self.width() // 2
                cy = self.height() // 2
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(cx - inner_radius, cy - inner_radius, inner_radius * 2, inner_radius * 2)
                painter.end()

        self._ctrl_cursor_hint = _CtrlCursorHint(self)

    def _show_ctrl_cursor_hint(self, pos, mode: str = "none") -> None:
        self._ensure_ctrl_cursor_hint()
        hint = self._ctrl_cursor_hint
        if hint is None:
            return
        size = hint.size()
        hint.move(pos.x() - size.width() // 2, pos.y() - size.height() // 2)
        hint.show()
        hint.raise_()

        # Movement-only updates while Ctrl is held just reposition the halo.
        if mode == "none":
            return

        if self._ctrl_cursor_hint_anim is not None:
            try:
                self._ctrl_cursor_hint_anim.stop()
            except Exception:
                pass
            self._ctrl_cursor_hint_anim = None

        fade_in = mode == "fade_in"
        fade_out = mode == "fade_out"
        if not (fade_in or fade_out):
            return

        try:
            if fade_in:
                hint.setOpacity(0.0)
            else:
                hint.setOpacity(1.0)
        except Exception:
            pass

        anim = QVariantAnimation(self)
        if fade_in:
            anim.setDuration(600)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
        else:
            anim.setDuration(1200)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.OutQuad)

        def _on_value_changed(value):
            try:
                hint.setOpacity(float(value))
            except Exception:
                pass

        anim.valueChanged.connect(_on_value_changed)

        def _on_finished() -> None:
            if fade_out:
                try:
                    hint.hide()
                except Exception:
                    pass
            try:
                hint.setWindowOpacity(1.0)
            except Exception:
                pass
            # Allow future fades after this one completes.
            self._ctrl_cursor_hint_anim = None

        anim.finished.connect(_on_finished)
        self._ctrl_cursor_hint_anim = anim
        anim.start()

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

                try:
                    widgets = QApplication.topLevelWidgets()
                except Exception:
                    widgets = []

                display_widgets = []
                for w in widgets:
                    try:
                        if not isinstance(w, DisplayWidget):
                            continue
                        display_widgets.append(w)
                    except Exception:
                        continue

                # First, reset Ctrl state and any existing halos on all
                # DisplayWidgets so we never end up with multiple visible
                # halos from previous uses.
                for w in display_widgets:
                    try:
                        w._ctrl_held = False
                        anim = getattr(w, "_ctrl_cursor_hint_anim", None)
                        if anim is not None:
                            try:
                                anim.stop()
                            except Exception:
                                pass
                            w._ctrl_cursor_hint_anim = None
                        hint = getattr(w, "_ctrl_cursor_hint", None)
                        if hint is not None:
                            try:
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
                event.accept()
                return

            # Clear global Ctrl-held mode and gracefully fade out the halo
            # owned by the current DisplayWidget, while ensuring any stray
            # halos on other displays are also cleared.
            DisplayWidget._global_ctrl_held = False
            owner = DisplayWidget._halo_owner
            DisplayWidget._halo_owner = None

            try:
                widgets = QApplication.topLevelWidgets()
            except Exception:
                widgets = []

            try:
                global_pos = QCursor.pos()
            except Exception:
                global_pos = None

            display_widgets = []
            for w in widgets:
                try:
                    if not isinstance(w, DisplayWidget):
                        continue
                    display_widgets.append(w)
                except Exception:
                    continue

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
                        try:
                            geom = mw.geometry()
                            local_x = event.pos().x() - geom.x()
                            width = max(1, mw.width())
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
                                    "[MEDIA] click mapped to PREVIOUS: pos=%s geom=%s local_x=%d x_in_content=%d width=%d content_left=%d content_right=%d third=%.2f",
                                    event.pos(),
                                    geom,
                                    local_x,
                                    x_in_content,
                                    width,
                                    content_left,
                                    content_right,
                                    third,
                                )
                                mw.previous_track()
                            elif x_in_content < 2.0 * third:
                                logger.debug(
                                    "[MEDIA] click mapped to PLAY/PAUSE: pos=%s geom=%s local_x=%d x_in_content=%d width=%d content_left=%d content_right=%d third=%.2f",
                                    event.pos(),
                                    geom,
                                    local_x,
                                    x_in_content,
                                    width,
                                    content_left,
                                    content_right,
                                    third,
                                )
                                mw.play_pause()
                            else:
                                logger.debug(
                                    "[MEDIA] click mapped to NEXT: pos=%s geom=%s local_x=%d x_in_content=%d width=%d content_left=%d content_right=%d third=%.2f",
                                    event.pos(),
                                    geom,
                                    local_x,
                                    x_in_content,
                                    width,
                                    content_left,
                                    content_right,
                                    third,
                                )
                                mw.next_track()
                            handled = True
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

            # Reddit widget: map clicks to open links in the browser when
            # interaction mode is active. When hard-exit is disabled,
            # Reddit clicks can also trigger a clean exit (controlled by
            # the per-widget "exit_on_click" setting). In hard-exit mode
            # the screensaver always remains active after the click.
            rw = getattr(self, "reddit_widget", None)
            try:
                if (not handled) and rw is not None and rw.isVisible() and rw.geometry().contains(event.pos()):
                    try:
                        from PySide6.QtCore import QPoint as _QPoint
                    except Exception:  # pragma: no cover - import guard
                        _QPoint = None  # type: ignore[assignment]

                    geom = rw.geometry()
                    if _QPoint is not None:
                        local_pos = _QPoint(event.pos().x() - geom.x(), event.pos().y() - geom.y())
                    else:
                        # Fallback: QRect.contains also accepts global-ish coords,
                        # but handle_click expects something QPoint-like; pass
                        # the original pos and let the widget ignore on failure.
                        local_pos = event.pos()

                    try:
                        if hasattr(rw, "handle_click") and rw.handle_click(local_pos):
                            handled = True
                            reddit_handled = True
                    except Exception:
                        logger.debug("[REDDIT] click routing failed", exc_info=True)
            except Exception:
                logger.debug("[REDDIT] Error while routing click to reddit widget", exc_info=True)

            if handled:
                # Optionally request a clean exit after Reddit clicks when
                # hard-exit mode is disabled and the widget is configured
                # to exit-on-click.
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
        self.exit_requested.emit()
        event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move - exit if moved beyond threshold (unless hard exit)."""
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
        """Route wheel scrolling to Spotify volume widget in interaction mode."""

        ctrl_mode_active = self._ctrl_held or DisplayWidget._global_ctrl_held
        if self._is_hard_exit_enabled() or ctrl_mode_active:
            vw = getattr(self, "spotify_volume_widget", None)
            if vw is not None and vw.isVisible():
                try:
                    from PySide6.QtCore import QPoint as _QPoint
                except Exception:  # pragma: no cover - import guard
                    _QPoint = None  # type: ignore[assignment]

                try:
                    if _QPoint is not None:
                        geom = vw.geometry()
                        pos = event.position()
                        local_pos = _QPoint(int(pos.x()) - geom.x(), int(pos.y()) - geom.y())
                    else:
                        local_pos = event.position().toPoint()
                    delta_y = int(event.angleDelta().y())
                    if vw.handle_wheel(local_pos, delta_y):
                        event.accept()
                        return
                except Exception:
                    logger.debug("[SPOTIFY_VOL] wheel routing failed", exc_info=True)

            # Even when not over the volume widget, wheel in interaction mode
            # should never exit the saver.
            event.accept()
            return

        super().wheelEvent(event)

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
                            try:
                                widgets = QApplication.topLevelWidgets()
                            except Exception:
                                widgets = []

                            new_owner = None
                            for w in widgets:
                                try:
                                    if not isinstance(w, DisplayWidget):
                                        continue
                                    if getattr(w, "_screen", None) is cursor_screen:
                                        new_owner = w
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
                            if hard_exit and DisplayWidget._halo_owner is None:
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

    def _preserve_base_before_overlay(self) -> None:
        """Diagnostic: log when an overlay raises while the base pixmap is absent.

        Helps confirm whether the base widget is the source of the black flash.
        Remove once flicker is conclusively solved.
        """
        try:
            if (self.current_pixmap is None or self.current_pixmap.isNull()) and any_gl_overlay_visible(self):
                if not self._pre_raise_log_emitted:
                    logger.debug("[DIAG] Base pixmap absent as overlay raises (leaving untouched)")
                    self._pre_raise_log_emitted = True
        except Exception:
            pass
