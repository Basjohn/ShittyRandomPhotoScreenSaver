"""Display widget for OpenGL/software rendered screensaver overlays."""
from collections import defaultdict
from typing import Optional, Iterable, Tuple
import random
import time
import weakref
try:
    from OpenGL import GL  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    GL = None
from PySide6.QtWidgets import QWidget, QLabel, QApplication
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
)
from shiboken6 import Shiboken
from rendering.display_modes import DisplayMode
from rendering.image_processor import ImageProcessor
from rendering.pan_and_scan import PanAndScan
from rendering.gl_compositor import GLCompositorWidget
from transitions.base_transition import BaseTransition
from transitions import (
    CrossfadeTransition,
    DiffuseTransition,
    SlideDirection,
    SlideTransition,
    WipeDirection,
    WipeTransition,
    BlockPuzzleFlipTransition,
)
from transitions.gl_compositor_crossfade_transition import GLCompositorCrossfadeTransition
from transitions.gl_compositor_slide_transition import GLCompositorSlideTransition
from transitions.gl_compositor_wipe_transition import GLCompositorWipeTransition
from transitions.gl_compositor_blockflip_transition import GLCompositorBlockFlipTransition
from transitions.gl_compositor_blinds_transition import GLCompositorBlindsTransition
from widgets.clock_widget import ClockWidget, TimeFormat, ClockPosition
from widgets.weather_widget import WeatherWidget, WeatherPosition
from widgets.media_widget import MediaWidget, MediaPosition
from core.logging.logger import get_logger
from core.logging.overlay_telemetry import record_overlay_ready
from core.resources.manager import ResourceManager
from core.settings.settings_manager import SettingsManager
from transitions.overlay_manager import (
    hide_all_overlays,
    any_overlay_ready_for_display,
    any_gl_overlay_visible,
    show_backend_fallback_overlay,
    hide_backend_fallback_overlay,
    get_or_create_overlay,
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
        self._current_transition: Optional[BaseTransition] = None
        self._current_transition_overlay_key: Optional[str] = None
        self._current_transition_started_at: float = 0.0
        self._image_label: Optional[QLabel] = None  # For pan and scan
        self._pan_and_scan = PanAndScan(self)
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

        # Central ResourceManager wiring
        self._resource_manager: Optional[ResourceManager] = resource_manager
        if self._resource_manager is None:
            try:
                self._resource_manager = ResourceManager()
            except Exception:
                self._resource_manager = None
        # Central ThreadManager wiring (optional, provided by engine)
        self._thread_manager = thread_manager
        
        # Setup widget
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setMouseTracking(True)
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
            pan_cap = 0
            if self.settings_manager:
                try:
                    pan_cap = int(self.settings_manager.get('pan_and_scan.max_fps', 0))
                except Exception:
                    pan_cap = 0
            eff_pan_fps = min(self._target_fps, pan_cap) if pan_cap > 0 else self._target_fps
            self._pan_and_scan.set_target_fps(eff_pan_fps)
        except Exception:
            pass
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

        # Weather widget
        weather_settings = widgets.get('weather', {}) if isinstance(widgets, dict) else {}
        weather_enabled = SettingsManager.to_bool(weather_settings.get('enabled', False), False)
        # Monitor selection for weather
        weather_monitor_sel = weather_settings.get('monitor', 'ALL')
        try:
            weather_show_on_this = (weather_monitor_sel == 'ALL') or (int(weather_monitor_sel) == (self.screen_index + 1))
        except Exception:
            weather_show_on_this = False
            logger.debug(
                "Weather widget monitor setting invalid for screen %s: %r (gated off)",
                self.screen_index,
                weather_monitor_sel,
            )
        if weather_enabled and weather_show_on_this:
            position_str = weather_settings.get('position', 'Bottom Left')
            location = weather_settings.get('location', 'London')
            font_size = weather_settings.get('font_size', 24)
            color = weather_settings.get('color', [255, 255, 255, 230])
            
            # Map position string to enum
            weather_position_map = {
                'Top Left': WeatherPosition.TOP_LEFT,
                'Top Right': WeatherPosition.TOP_RIGHT,
                'Bottom Left': WeatherPosition.BOTTOM_LEFT,
                'Bottom Right': WeatherPosition.BOTTOM_RIGHT,
            }
            position = weather_position_map.get(position_str, WeatherPosition.BOTTOM_LEFT)
            
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
                    weather_settings.get('show_background', False), False
                )
                self.weather_widget.set_show_background(show_background)

                # Background color (RGB+alpha), default matches WeatherWidget internal default
                bg_color_data = weather_settings.get('bg_color', [64, 64, 64, 255])
                try:
                    bg_r, bg_g, bg_b = bg_color_data[0], bg_color_data[1], bg_color_data[2]
                    bg_a = bg_color_data[3] if len(bg_color_data) > 3 else 255
                    bg_qcolor = QColor(bg_r, bg_g, bg_b, bg_a)
                    self.weather_widget.set_background_color(bg_qcolor)
                except Exception:
                    pass

                # Background opacity (scales alpha regardless of bg_color alpha)
                bg_opacity = weather_settings.get('bg_opacity', 0.9)
                self.weather_widget.set_background_opacity(bg_opacity)

                # Border color and opacity (independent from background opacity)
                border_color_data = weather_settings.get('border_color', [128, 128, 128, 255])
                border_opacity = weather_settings.get('border_opacity', 0.8)
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
                # Show/hide condition icons
                show_icons = SettingsManager.to_bool(weather_settings.get('show_icons', True), True)
                if hasattr(self.weather_widget, 'set_show_icons'):
                    self.weather_widget.set_show_icons(show_icons)
                
                self.weather_widget.raise_()
                self.weather_widget.start()
                logger.info(f"✅ Weather widget started: {location}, {position_str}, font={font_size}px")
            except Exception as e:
                logger.error(f"Failed to create/configure weather widget: {e}", exc_info=True)
        else:
            logger.debug("Weather widget disabled in settings")

        # Media widget
        media_settings = widgets.get('media', {}) if isinstance(widgets, dict) else {}
        media_enabled = SettingsManager.to_bool(media_settings.get('enabled', False), False)
        media_monitor_sel = media_settings.get('monitor', 'ALL')
        try:
            media_show_on_this = (media_monitor_sel == 'ALL') or (int(media_monitor_sel) == (self.screen_index + 1))
        except Exception:
            media_show_on_this = False
            logger.debug(
                "Media widget monitor setting invalid for screen %s: %r (gated off)",
                self.screen_index,
                media_monitor_sel,
            )

        # Detailed diagnostics so we can see exactly what the runtime settings
        # look like for the media widget on each screen, including the raw
        # enabled value and monitor selection.
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
            try:
                bg_r, bg_g, bg_b = bg_color_data[0], bg_color_data[1], bg_color_data[2]
                bg_a = bg_color_data[3] if len(bg_color_data) > 3 else 255
                bg_qcolor = QColor(bg_r, bg_g, bg_b, bg_a)
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
                pass

            self.media_widget.raise_()
            self.media_widget.start()
            logger.info(
                "✅ Media widget started: %s, font=%spx, margin=%s", position_str, font_size, margin_val
            )
        except Exception as e:
            logger.error("Failed to create/configure media widget: %s", e, exc_info=True)

    def _warm_up_gl_overlay(self, base_pixmap: QPixmap) -> None:
        """Legacy GL overlay warm-up disabled (compositor-only pipeline)."""
        logger.debug("[WARMUP] Skipping legacy GL overlay warm-up (compositor-only pipeline)")
        return

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

    def _prewarm_gl_contexts(self) -> None:
        """
        Legacy GL overlay prewarm disabled now that compositor is the only GL path.
        """
        logger.debug("[PREWARM] Skipping legacy GL overlay prewarm (compositor-only pipeline)")
        return

        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt

        start_time = time.time()
        logger.debug(f"[PREWARM] Starting GL context pre-warming for screen {self.screen_index}")

        # Create full-screen dummy pixmap to allocate FBOs at final size.
        # Prefer the currently seeded pixmap (wallpaper snapshot or last image)
        # so overlays do not flash pure black during startup.
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            w, h = 10, 10

        base_pm: Optional[QPixmap] = None
        try:
            if self._seed_pixmap is not None and not self._seed_pixmap.isNull():
                base_pm = self._seed_pixmap
            elif self.current_pixmap is not None and not self.current_pixmap.isNull():
                base_pm = self.current_pixmap
            elif self.previous_pixmap is not None and not self.previous_pixmap.isNull():
                base_pm = self.previous_pixmap
        except Exception:
            base_pm = None

        if base_pm is None or base_pm.isNull():
            logger.debug("[PREWARM] Skipping GL prewarm - no seed pixmap available")
            return

        dummy = QPixmap(w, h)
        dummy.fill(Qt.GlobalColor.black)
        try:
            from PySide6.QtGui import QPainter
            p = QPainter(dummy)
            try:
                p.drawPixmap(dummy.rect(), base_pm)
            finally:
                p.end()
        except Exception:
            pass
        dummy.setDevicePixelRatio(self._device_pixel_ratio)

        # Import GL overlay widget classes
        try:
            from transitions.gl_crossfade_transition import _GLFadeWidget
            from transitions.gl_slide_transition import _GLSlideWidget
            from transitions.slide_transition import SlideDirection
            from transitions.gl_wipe_transition import _GLWipeWidget
            from transitions.wipe_transition import WipeDirection
            from transitions.gl_diffuse_transition import _GLDiffuseWidget, _Cell
            from transitions.gl_block_puzzle_flip_transition import _GLBlockFlipWidget, _GLFlipBlock
            from transitions.gl_blinds import _GLBlindsOverlay, _GLBlindSlat
            from PySide6.QtCore import QRect
        except ImportError as exc:
            logger.warning(f"[PREWARM] Failed to import GL overlay classes: {exc}")
            return

        overlays_to_prewarm = [
            ("Crossfade", "_srpss_gl_xfade_overlay", _GLFadeWidget, lambda: _GLFadeWidget(self, dummy, dummy)),
            ("Slide", "_srpss_gl_slide_overlay", _GLSlideWidget, lambda: _GLSlideWidget(self, dummy, dummy, SlideDirection.LEFT)),
            ("Wipe", "_srpss_gl_wipe_overlay", _GLWipeWidget, lambda: _GLWipeWidget(self, dummy, dummy, WipeDirection.LEFT_TO_RIGHT)),
            ("Diffuse", "_srpss_gl_diffuse_overlay", _GLDiffuseWidget, lambda: _GLDiffuseWidget(self, dummy, dummy, [_Cell(QRect(0, 0, w, h))])),
            ("Block", "_srpss_gl_blockflip_overlay", _GLBlockFlipWidget, lambda: _GLBlockFlipWidget(self, dummy, dummy, [_GLFlipBlock(QRect(0, 0, w, h))])),
            ("Blinds", "_srpss_gl_blinds_overlay", _GLBlindsOverlay, lambda: _GLBlindsOverlay(self, dummy, dummy, [_GLBlindSlat(QRect(0, 0, w, h))])),
        ]

        prewarmed_count = 0
        for name, attr_name, overlay_type, factory in overlays_to_prewarm:
            try:
                per_overlay_start = time.time()
                existing = getattr(self, attr_name, None)
                overlay = get_or_create_overlay(self, attr_name, overlay_type, factory)
                reuse_existing = overlay is existing

                set_overlay_geometry(self, overlay)
                overlay.show()
                raise_overlay(self, overlay)

                # Force GL initialization
                try:
                    overlay.makeCurrent()
                except Exception:
                    pass
                try:
                    overlay.repaint()
                except Exception:
                    pass

                timeout_ms = 150
                start_wait = time.time()
                while hasattr(overlay, "is_ready_for_display") and not overlay.is_ready_for_display():
                    QApplication.processEvents()
                    if (time.time() - start_wait) * 1000 > timeout_ms:
                        logger.debug(f"[PREWARM] {name} timeout, continuing")
                        break
                    time.sleep(0.001)

                try:
                    if hasattr(overlay, "doneCurrent"):
                        overlay.doneCurrent()
                except Exception:
                    pass

                overlay.hide()
                if hasattr(overlay, "set_alpha"):
                    try:
                        overlay.set_alpha(0.0)
                    except Exception:
                        pass

                if hasattr(overlay, "is_ready_for_display") and not overlay.is_ready_for_display():
                    self._force_overlay_ready(overlay, stage=f"prewarm_{name}")

                prewarmed_count += 1
                elapsed = (time.time() - per_overlay_start) * 1000
                log_msg = (
                    f"[PREWARM] {'Reused' if reuse_existing else 'Created'} {name} overlay initialization "
                    f"{elapsed:.1f}ms"
                )
                # Treat typical 175–300ms overlay init as expected; only flag unusually slow cases.
                if elapsed > 500:
                    logger.warning(log_msg)
                elif elapsed > 250:
                    logger.info(log_msg)
                else:
                    logger.debug(log_msg)

            except Exception as exc:
                logger.warning(f"[PREWARM] Failed to pre-warm {name}: {exc}")
                continue

        total_ms = (time.time() - start_time) * 1000
        logger.info(
            "[PREWARM] GL context pre-warming complete for screen %s: %s/%s overlays in %.1fms",
            self.screen_index,
            prewarmed_count,
            len(overlays_to_prewarm),
            total_ms,
        )

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

        duration_ms_raw = transitions_settings.get('duration_ms', 1300)
        try:
            duration_ms = int(duration_ms_raw)
        except Exception:
            duration_ms = 1300

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

            if transition_type == 'Diffuse':
                diffuse_settings = transitions_settings.get('diffuse', {}) if isinstance(transitions_settings.get('diffuse', {}), dict) else {}
                block_size_raw = diffuse_settings.get('block_size', 50)
                try:
                    block_size = int(block_size_raw)
                except Exception:
                    block_size = 50
                shape = diffuse_settings.get('shape', 'Rectangle') or 'Rectangle'

                transition = DiffuseTransition(duration_ms, block_size, shape)

                transition.set_resource_manager(self._resource_manager)
                self._log_transition_selection(requested_type, 'Diffuse', random_mode, random_choice_value)
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

                if hw_accel:
                    try:
                        self._ensure_gl_compositor()
                    except Exception:
                        logger.debug("[GL COMPOSITOR] Failed to ensure compositor during block flip selection", exc_info=True)
                    use_compositor = isinstance(getattr(self, "_gl_compositor", None), GLCompositorWidget)
                    if use_compositor:
                        transition = GLCompositorBlockFlipTransition(duration_ms, rows, cols)
                    else:
                        # Prefer CPU BlockPuzzleFlipTransition over the legacy GL
                        # overlay path when the compositor cannot be used.
                        transition = BlockPuzzleFlipTransition(duration_ms, rows, cols)
                else:
                    transition = BlockPuzzleFlipTransition(duration_ms, rows, cols)

                transition.set_resource_manager(self._resource_manager)
                self._log_transition_selection(requested_type, 'Block Puzzle Flip', random_mode, random_choice_value)
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
        pan_and_scan_enabled = False
        if self.settings_manager:
            # Lanczos intentionally ignored due to distortion; keep False
            sharpen = self.settings_manager.get('display.sharpen_downscale', False)
            if isinstance(sharpen, str):
                sharpen = sharpen.lower() == 'true'
            pan_and_scan_enabled = self.settings_manager.get('display.pan_and_scan', False)
            if isinstance(pan_and_scan_enabled, str):
                pan_and_scan_enabled = pan_and_scan_enabled.lower() == 'true'
        
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

        # Keep original pixmap for pan & scan (will be used after transition)
        original_pixmap = pixmap

        # Optionally build a pan-aware preview so transition matches pan start frame
        pan_transition_frame = None
        if pan_and_scan_enabled:
            try:
                pan_transition_frame = self._pan_and_scan.build_transition_frame(
                    original_pixmap,
                    self.size(),
                    self._device_pixel_ratio
                )
            except Exception:
                pan_transition_frame = None

        # Choose pixmap presented to transition
        new_pixmap = pan_transition_frame or processed_pixmap
        
        self._animation_manager = None
        self._overlay_timeouts: dict[str, float] = {}
        self._pre_raise_log_emitted = False
        self._base_fallback_paint_logged = False
        
        # Set DPR on the processed pixmap for proper display scaling
        new_pixmap.setDevicePixelRatio(self._device_pixel_ratio)
        if pan_transition_frame is not None and pan_transition_frame is not new_pixmap:
            try:
                pan_transition_frame.setDevicePixelRatio(self._device_pixel_ratio)
            except Exception:
                pass
        processed_pixmap.setDevicePixelRatio(self._device_pixel_ratio)
        
        # Stop any running transition
        if self._current_transition:
            transition_to_stop = self._current_transition
            self._current_transition = None  # Clear reference first
            try:
                transition_to_stop.stop()
                transition_to_stop.cleanup()
            except Exception as e:
                logger.warning(f"Error stopping transition: {e}")
        
        # CRITICAL: ALWAYS stop pan & scan and hide label before ANY transition
        # This prevents visual artifacts from previous image's pan & scan overlapping new transition
        self._pan_and_scan.stop()
        if self._image_label:
            self._image_label.hide()
            logger.debug("[BUG FIX #2] Pan & scan label hidden before transition")
        
        # Cache previous pixmap reference before we mutate current_pixmap
        previous_pixmap_ref = self.current_pixmap

        # Seed base widget with the new frame before starting transitions.
        # This prevents fallback paints (black bands) while overlays warm up.
        self.current_pixmap = pan_transition_frame or processed_pixmap
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
                        pan_and_scan_enabled,
                        pan_transition_frame,
                    )

                    def _finish_handler(np=processed_pixmap, op=original_pixmap,
                                        ip=image_path, pse=pan_and_scan_enabled,
                                        preview=pan_transition_frame, ref=self_ref):
                        widget = ref()
                        if widget is None or not Shiboken.isValid(widget):
                            return
                        try:
                            widget._pending_transition_finish_args = (np, op, ip, pse, preview)
                            widget._on_transition_finished(np, op, ip, pse, preview)
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

                if pan_and_scan_enabled:
                    if not self._image_label:
                        self._image_label = QLabel(self)
                        self._image_label.setScaledContents(False)
                    self._pan_and_scan.enable(True)

                    transition_interval = self.settings_manager.get('timing.interval', 10)
                    auto_speed = self.settings_manager.get('display.pan_auto_speed', True)
                    manual_speed = self.settings_manager.get('display.pan_speed', 3.0)

                    if isinstance(auto_speed, str):
                        auto_speed = auto_speed.lower() == 'true'

                    self._pan_and_scan.set_auto_speed(auto_speed, float(transition_interval))
                    if not auto_speed:
                        self._pan_and_scan.set_speed(float(manual_speed))

                    try:
                        init_off = self._pan_and_scan.preview_offset(original_pixmap, self.size())
                        self._pan_and_scan.set_initial_offset(init_off)
                    except Exception:
                        pass
                    self._pan_and_scan.set_image(original_pixmap, self._image_label, self.size())

                    self._image_label.show()
                    self._image_label.raise_()

                    for attr_name in ("clock_widget", "clock2_widget", "clock3_widget"):
                        clock = getattr(self, attr_name, None)
                        if clock is not None:
                            try:
                                clock.raise_()
                            except Exception:
                                pass

                    mw = getattr(self, "media_widget", None)
                    if mw is not None:
                        try:
                            mw.raise_()
                        except Exception:
                            pass

                    self._pan_and_scan.start()
                else:
                    self._pan_and_scan.enable(False)
                    if self._image_label:
                        self._image_label.hide()
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

        # Start pan and scan if enabled (use original uncropped pixmap)
        if pan_enabled:
            if not self._image_label:
                self._image_label = QLabel(self)
                self._image_label.setScaledContents(False)
            self._pan_and_scan.enable(True)

            # Get pan and scan settings
            transition_interval = self.settings_manager.get('timing.interval', 10)
            auto_speed = self.settings_manager.get('display.pan_auto_speed', True)
            manual_speed = self.settings_manager.get('display.pan_speed', 3.0)

            if isinstance(auto_speed, str):
                auto_speed = auto_speed.lower() == 'true'

            self._pan_and_scan.set_auto_speed(auto_speed, float(transition_interval))
            if not auto_speed:
                self._pan_and_scan.set_speed(float(manual_speed))

            # CRITICAL: Use original_pixmap for pan & scan, not the processed one
            # This prevents the zoom effect where the image suddenly changes size
            try:
                init_off = self._pan_and_scan.preview_offset(original_pixmap, self.size())
                self._pan_and_scan.set_initial_offset(init_off)
            except Exception:
                pass
            self._pan_and_scan.set_image(original_pixmap, self._image_label, self.size())

            # Ensure label is visible and on top
            self._image_label.show()
            self._image_label.raise_()

            # Keep widgets above pan & scan
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

            self._pan_and_scan.start()
        else:
            self._pan_and_scan.enable(False)
            if self._image_label:
                self._image_label.hide()
            # Ensure widgets stay visible after transition
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
            self.update()

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
        if pan_enabled and self._image_label:
            try:
                self._image_label.show()
                self._image_label.raise_()
            except Exception:
                pass
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
                self._gl_compositor.hide()
                self._gl_compositor.setParent(None)
        except Exception:
            pass
        self._gl_compositor = None
        # Stop pan & scan if still active
        try:
            if hasattr(self, "_pan_and_scan") and self._pan_and_scan is not None:
                self._pan_and_scan.stop()
        except Exception:
            pass
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
        except Exception:
            pass
        # Hide overlays and cancel watchdog timer
        try:
            hide_all_overlays(self)
        except Exception:
            pass
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
        # Stop pan and scan
        self._pan_and_scan.stop()
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
        
        # Hotkeys
        if key_text == 'z':
            logger.info("Z key pressed - previous image requested")
            self.previous_requested.emit()
            event.accept()
        elif key_text == 'x':
            logger.info("X key pressed - next image requested")
            self.next_requested.emit()
            event.accept()
        elif key_text == 'c':
            logger.info("C key pressed - cycle transition requested")
            self.cycle_transition_requested.emit()
            event.accept()
        elif key_text == 's':
            logger.info("S key pressed - settings requested")
            self.settings_requested.emit()
            event.accept()
        # Exit keys
        elif key == Qt.Key.Key_Escape or key == Qt.Key.Key_Q:
            logger.info(f"Exit key pressed: {key}, requesting exit")
            self._exiting = True
            self.exit_requested.emit()
            event.accept()
        # FIX: Don't exit on any key - only specific hotkeys and exit keys
        else:
            logger.debug(f"Unknown key pressed: {key} - ignoring")
            event.ignore()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Control:
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
            # interactive widgets (e.g. media widget) to their handlers while
            # still suppressing screensaver exit.
            handled = False
            mw = getattr(self, "media_widget", None)
            try:
                if mw is not None and mw.isVisible():
                    if mw.geometry().contains(event.pos()):
                        button = event.button()
                        try:
                            from PySide6.QtCore import Qt as _Qt
                        except Exception:  # pragma: no cover - import guard
                            _Qt = Qt  # type: ignore[assignment]

                        if button == _Qt.MouseButton.LeftButton:
                            try:
                                mw.play_pause()
                                handled = True
                            except Exception:
                                logger.debug("[MEDIA] play_pause handling failed from mousePressEvent", exc_info=True)
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

            if handled:
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
                if DisplayWidget._global_ctrl_held:
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
                        owner._show_ctrl_cursor_hint(local_pos, mode="none")
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
