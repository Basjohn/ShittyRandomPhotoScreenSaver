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
from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QPixmap, QPainter, QKeyEvent, QMouseEvent, QPaintEvent, QFont, QResizeEvent
from shiboken6 import Shiboken
from rendering.display_modes import DisplayMode
from rendering.image_processor import ImageProcessor
from rendering.pan_and_scan import PanAndScan
from transitions.base_transition import BaseTransition
from transitions import (
    CrossfadeTransition,
    DiffuseTransition,
    GLBlindsTransition,
    GLBlockPuzzleFlipTransition,
    GLCrossfadeTransition,
    GLSlideTransition,
    GLWipeTransition,
    SlideDirection,
    SlideTransition,
    WipeDirection,
    WipeTransition,
    BlockPuzzleFlipTransition,
)
from widgets.clock_widget import ClockWidget, TimeFormat, ClockPosition
from widgets.weather_widget import WeatherWidget, WeatherPosition
from core.logging.logger import get_logger
from core.resources.manager import ResourceManager
from transitions.gl_crossfade_transition import _GLFadeWidget
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
    """
    
    exit_requested = Signal()
    image_displayed = Signal(str)  # image path
    previous_requested = Signal()  # Z key - go to previous image
    next_requested = Signal()  # X key - go to next image
    cycle_transition_requested = Signal()  # C key - cycle transition mode
    settings_requested = Signal()  # S key - open settings
    
    def __init__(
        self,
        screen_index: int = 0,
        display_mode: DisplayMode = DisplayMode.FILL,
        settings_manager=None,
        parent: Optional[QWidget] = None,
        resource_manager: Optional[ResourceManager] = None,
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
        
        # Setup widget
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setMouseTracking(True)
        
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
        self._init_renderer_backend()

        # Ensure transitions are cleaned up if the widget is destroyed
        try:
            self.destroyed.connect(self._on_destroyed)
        except Exception:
            pass
    
    def show_on_screen(self) -> None:
        """Show widget fullscreen on assigned screen."""
        from PySide6.QtGui import QGuiApplication
        
        screens = QGuiApplication.screens()
        
        if self.screen_index >= len(screens):
            logger.warning(f"[FALLBACK] Screen {self.screen_index} not found, using primary")
            screen = QGuiApplication.primaryScreen()
        else:
            screen = screens[self.screen_index]
        
        # Store screen reference and DPI ratio for high-quality rendering
        self._screen = screen
        self._device_pixel_ratio = screen.devicePixelRatio()
        
        geometry = screen.geometry()
        logger.info(f"Showing on screen {self.screen_index}: "
                   f"{geometry.width()}x{geometry.height()} at ({geometry.x()}, {geometry.y()}) "
                   f"DPR={self._device_pixel_ratio}")

        # Position and size window
        self.setGeometry(geometry)
        try:
            self.setUpdatesEnabled(False)
            self._updates_blocked_until_seed = True
        except Exception:
            self._updates_blocked_until_seed = False
        self.showFullScreen()
        self._handle_screen_change(screen)
        # Reconfigure when screen changes
        try:
            handle = self.windowHandle()
            if handle is not None:
                handle.screenChanged.connect(self._handle_screen_change)
        except Exception:
            pass

        # Pre-warm GL contexts if hardware acceleration enabled
        hw_accel = False
        if self.settings_manager:
            hw_accel = self.settings_manager.get('display.hw_accel', False)
            # Handle string boolean values from settings file
            if isinstance(hw_accel, str):
                hw_accel = hw_accel.lower() in ('true', '1', 'yes')
        if hw_accel:
            self._prewarm_gl_contexts()
            self._perform_initial_gl_flush()
        elif GL is None:
            self._mark_all_overlays_ready(GL_OVERLAY_KEYS, stage="software_prewarm")

        # Reuse persistent GL overlays
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
            geometry = screen.geometry()
            if geometry is not None and geometry.isValid():
                self.setGeometry(geometry)
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
            refresh_sync = self.settings_manager.get('display.refresh_sync', True)
            if isinstance(refresh_sync, str):
                refresh_sync_enabled = refresh_sync.lower() in ('true', '1', 'yes')
            else:
                refresh_sync_enabled = bool(refresh_sync)
        
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

        def _to_bool(val, default=False):
            if isinstance(val, str):
                return val.lower() in ('true', '1', 'yes')
            return bool(val) if val is not None else default

        position_map = {
            'Top Left': ClockPosition.TOP_LEFT,
            'Top Right': ClockPosition.TOP_RIGHT,
            'Top Center': ClockPosition.TOP_CENTER,
            'Center': ClockPosition.CENTER,
            'Bottom Left': ClockPosition.BOTTOM_LEFT,
            'Bottom Right': ClockPosition.BOTTOM_RIGHT,
            'Bottom Center': ClockPosition.BOTTOM_CENTER,
        }

        def _create_clock_widget(settings_key: str, attr_name: str, default_position: str, default_font_size: int) -> None:
            clock_settings = widgets.get(settings_key, {}) if isinstance(widgets, dict) else {}
            clock_enabled = _to_bool(clock_settings.get('enabled', False), False)
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

            time_format = TimeFormat.TWELVE_HOUR if clock_settings.get('format', '12h') == '12h' else TimeFormat.TWENTY_FOUR_HOUR
            position_str = clock_settings.get('position', default_position)
            show_seconds = _to_bool(clock_settings.get('show_seconds', False), False)
            timezone_str = clock_settings.get('timezone', 'local')
            show_timezone = _to_bool(clock_settings.get('show_timezone', False), False)
            font_size = clock_settings.get('font_size', default_font_size)
            margin = clock_settings.get('margin', 20)
            color = clock_settings.get('color', [255, 255, 255, 230])

            position = position_map.get(position_str, position_map.get(default_position, ClockPosition.TOP_RIGHT))

            try:
                clock = ClockWidget(self, time_format, position, show_seconds, timezone_str, show_timezone)

                font_family = clock_settings.get('font_family', 'Segoe UI')
                if hasattr(clock, 'set_font_family'):
                    clock.set_font_family(font_family)

                clock.set_font_size(font_size)
                clock.set_margin(margin)

                from PySide6.QtGui import QColor
                qcolor = QColor(color[0], color[1], color[2], color[3])
                clock.set_text_color(qcolor)

                show_background = _to_bool(clock_settings.get('show_background', False), False)
                clock.set_show_background(show_background)

                bg_opacity = clock_settings.get('bg_opacity', 0.9)
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
        weather_enabled = _to_bool(weather_settings.get('enabled', False), False)
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
                
                # Set font family if specified
                font_family = weather_settings.get('font_family', 'Segoe UI')
                if hasattr(self.weather_widget, 'set_font_family'):
                    self.weather_widget.set_font_family(font_family)
                
                self.weather_widget.set_font_size(font_size)
                
                # Convert color array to QColor
                from PySide6.QtGui import QColor
                qcolor = QColor(color[0], color[1], color[2], color[3])
                self.weather_widget.set_text_color(qcolor)
                
                # Set background frame if enabled
                show_background = _to_bool(weather_settings.get('show_background', False), False)
                self.weather_widget.set_show_background(show_background)
                
                # Set background opacity
                bg_opacity = weather_settings.get('bg_opacity', 0.9)
                self.weather_widget.set_background_opacity(bg_opacity)
                
                self.weather_widget.raise_()
                self.weather_widget.start()
                logger.info(f"✅ Weather widget started: {location}, {position_str}, font={font_size}px")
            except Exception as e:
                logger.error(f"Failed to create/configure weather widget: {e}", exc_info=True)
        else:
            logger.debug("Weather widget disabled in settings")

    def _warm_up_gl_overlay(self, base_pixmap: QPixmap) -> None:
        """Warm up the persistent GL overlay once to avoid first-run flicker."""
        if not self.settings_manager:
            return
        hw_accel = self.settings_manager.get('display.hw_accel', False)
        if isinstance(hw_accel, str):
            hw_accel = hw_accel.lower() == 'true'
        existing = getattr(self, "_srpss_gl_xfade_overlay", None)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0 or base_pixmap is None or base_pixmap.isNull():
            return

        overlay = get_or_create_overlay(
            self,
            "_srpss_gl_xfade_overlay",
            _GLFadeWidget,
            lambda: _GLFadeWidget(self, base_pixmap, base_pixmap),
        )
        set_overlay_geometry(self, overlay)
        overlay.set_alpha(1.0)
        overlay.set_images(base_pixmap, base_pixmap)
        if overlay is not existing:
            logger.debug("[WARMUP] Created GL crossfade overlay for warm-up")
        else:
            logger.debug("[WARMUP] Reusing GL crossfade overlay for warm-up")

        # Present once with the current image to ensure context/FBO are ready
        try:
            overlay.setVisible(True)
            raise_overlay(self, overlay)
            try:
                overlay.makeCurrent()
            except Exception:
                pass
            try:
                _ = overlay.grabFramebuffer()
            except Exception:
                pass
            try:
                overlay.repaint()
            except Exception:
                pass
        finally:
            try:
                overlay.hide()
            except Exception:
                pass

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
        Pre-warm GL overlays so they have live contexts and textures before first use.
        """

        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt

        start_time = time.time()
        logger.debug(f"[PREWARM] Starting GL context pre-warming for screen {self.screen_index}")

        # Create full-screen dummy pixmap to allocate FBOs at final size
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            w, h = 10, 10
        dummy = QPixmap(w, h)
        dummy.fill(Qt.GlobalColor.black)
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
            logger.debug("[INIT] Skipping initial GL flush; PyOpenGL not available")
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

        transition_type = self.settings_manager.get('transitions.type', None)
        if not transition_type:
            transition_type = transitions_settings.get('type')
        transition_type = transition_type or 'Crossfade'
        requested_type = transition_type

        try:
            rnd = self.settings_manager.get('transitions.random_always', None)
            if rnd is None:
                rnd = transitions_settings.get('random_always', False)
            if isinstance(rnd, str):
                rnd = rnd.lower() in ('true', '1', 'yes')
            random_mode = bool(rnd)
            random_choice_value = None
            if rnd:
                chosen = self.settings_manager.get('transitions.random_choice', None)
                if chosen:
                    transition_type = chosen
                    random_choice_value = chosen
        except Exception:
            rnd = False
            random_mode = False
            random_choice_value = None

        duration_ms = self.settings_manager.get('transitions.duration_ms', None)
        if duration_ms is None:
            duration_ms = transitions_settings.get('duration_ms')
        duration_ms = int(duration_ms or 1300)

        try:
            easing_str = self.settings_manager.get('transitions.easing', None)
            if not easing_str:
                easing_str = transitions_settings.get('easing')
            easing_str = easing_str or 'Auto'

            hw_accel = self.settings_manager.get('display.hw_accel', False)
            if isinstance(hw_accel, str):
                hw_accel = hw_accel.lower() in ('true', '1', 'yes')

            if transition_type == 'Crossfade':
                transition = GLCrossfadeTransition(duration_ms, easing_str) if hw_accel else CrossfadeTransition(duration_ms, easing_str)
                transition.set_resource_manager(self._resource_manager)
                self._log_transition_selection(requested_type, 'Crossfade', random_mode, random_choice_value)
                return transition

            if transition_type == 'Slide':
                slide_settings = transitions_settings.get('slide', {})
                if not isinstance(slide_settings, dict):
                    slide_settings = {}
                direction_str = self.settings_manager.get('transitions.slide.direction', None)
                if direction_str is None:
                    direction_str = slide_settings.get('direction')
                if direction_str is None:
                    direction_str = self.settings_manager.get('transitions.direction', None)
                if direction_str is None:
                    direction_str = transitions_settings.get('direction')
                direction_str = direction_str or 'Random'

                direction_map = {
                    'Left to Right': SlideDirection.LEFT,
                    'Right to Left': SlideDirection.RIGHT,
                    'Top to Bottom': SlideDirection.DOWN,
                    'Bottom to Top': SlideDirection.UP,
                }

                rnd_always = self.settings_manager.get('transitions.random_always', None)
                if rnd_always is None:
                    rnd_always = transitions_settings.get('random_always', False)
                if isinstance(rnd_always, str):
                    rnd_always = rnd_always.lower() in ('true', '1', 'yes')

                if direction_str == 'Random' and not rnd_always:
                    all_dirs = [SlideDirection.LEFT, SlideDirection.RIGHT, SlideDirection.UP, SlideDirection.DOWN]
                    last_dir = self.settings_manager.get('transitions.last_slide_direction', None)
                    last_dir = slide_settings.get('last_direction', last_dir)
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
                    self.settings_manager.set('transitions.last_slide_direction', enum_to_str.get(direction, 'Left to Right'))
                else:
                    direction = direction_map.get(direction_str, SlideDirection.LEFT)

                transition = GLSlideTransition(duration_ms, direction, easing_str) if hw_accel else SlideTransition(duration_ms, direction, easing_str)
                transition.set_resource_manager(self._resource_manager)
                self._log_transition_selection(requested_type, 'Slide', random_mode, random_choice_value)
                return transition

            if transition_type == 'Wipe':
                wipe_settings = transitions_settings.get('wipe', {})
                if not isinstance(wipe_settings, dict):
                    wipe_settings = {}
                wipe_dir_str = self.settings_manager.get('transitions.wipe.direction', None)
                if wipe_dir_str is None:
                    wipe_dir_str = wipe_settings.get('direction')
                if wipe_dir_str is None:
                    wipe_dir_str = self.settings_manager.get('transitions.direction', None)
                if wipe_dir_str is None:
                    wipe_dir_str = transitions_settings.get('wipe_direction')
                if wipe_dir_str is None:
                    wipe_dir_str = transitions_settings.get('direction')

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
                if isinstance(rnd_always, str):
                    rnd_always = rnd_always.lower() in ('true', '1', 'yes')

                if wipe_dir_str and wipe_dir_str in direction_map and not (wipe_dir_str == 'Random' and not rnd_always):
                    direction = direction_map[wipe_dir_str]
                else:
                    all_wipes = list(direction_map.values())
                    last_wipe = self.settings_manager.get('transitions.last_wipe_direction', None)
                    last_wipe = wipe_settings.get('last_direction', last_wipe)
                    str_to_enum = {name: enum for name, enum in direction_map.items()}
                    last_enum = str_to_enum.get(last_wipe) if isinstance(last_wipe, str) else None
                    candidates = [d for d in all_wipes if d != last_enum] if last_enum in all_wipes else all_wipes
                    direction = random.choice(candidates) if candidates else random.choice(all_wipes)
                    enum_to_str = {enum: name for name, enum in direction_map.items()}
                    self.settings_manager.set('transitions.last_wipe_direction', enum_to_str.get(direction, 'Left to Right'))

                transition = GLWipeTransition(duration_ms, direction, easing_str) if hw_accel else WipeTransition(duration_ms, direction, easing_str)
                transition.set_resource_manager(self._resource_manager)
                self._log_transition_selection(requested_type, 'Wipe', random_mode, random_choice_value)
                return transition

            if transition_type == 'Diffuse':
                diffuse_block = self.settings_manager.get('transitions.diffuse.block_size', None)
                diffuse_shape = self.settings_manager.get('transitions.diffuse.shape', None)
                diffuse_settings = transitions_settings.get('diffuse', {}) if isinstance(transitions_settings.get('diffuse', {}), dict) else {}
                if diffuse_block is None:
                    diffuse_block = diffuse_settings.get('block_size')
                if diffuse_shape is None:
                    diffuse_shape = diffuse_settings.get('shape')
                block_size = int(diffuse_block or 50)
                shape = diffuse_shape or 'Rectangle'
                transition = DiffuseTransition(duration_ms, block_size, shape)
                transition.set_resource_manager(self._resource_manager)
                self._log_transition_selection(requested_type, 'Diffuse', random_mode, random_choice_value)
                return transition

            if transition_type == 'Block Puzzle Flip':
                rows = self.settings_manager.get('transitions.block_flip.rows', None)
                cols = self.settings_manager.get('transitions.block_flip.cols', None)
                block_flip_settings = transitions_settings.get('block_flip', {}) if isinstance(transitions_settings.get('block_flip', {}), dict) else {}
                if rows is None:
                    rows = block_flip_settings.get('rows')
                if cols is None:
                    cols = block_flip_settings.get('cols')
                rows = int(rows or 4)
                cols = int(cols or 6)
                transition = GLBlockPuzzleFlipTransition(duration_ms, rows, cols) if hw_accel else BlockPuzzleFlipTransition(duration_ms, rows, cols)
                transition.set_resource_manager(self._resource_manager)
                self._log_transition_selection(requested_type, 'Block Puzzle Flip', random_mode, random_choice_value)
                return transition

            if transition_type == 'Blinds':
                if hw_accel:
                    try:
                        transition = GLBlindsTransition(duration_ms)
                        transition.set_resource_manager(self._resource_manager)
                        self._log_transition_selection(requested_type, 'Blinds', random_mode, random_choice_value)
                        return transition
                    except Exception as exc:
                        logger.warning("Failed to init GL Blinds, falling back: %s", exc)
                transition = CrossfadeTransition(duration_ms)
                transition.set_resource_manager(self._resource_manager)
                self._log_transition_selection(requested_type, 'Crossfade', random_mode, random_choice_value)
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

                    self._pan_and_scan.start()
                else:
                    self._pan_and_scan.enable(False)
                    if self._image_label:
                        self._image_label.hide()
                    self.update()
                    try:
                        self._warm_up_gl_overlay(self.current_pixmap)
                    except Exception:
                        pass
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

        self._cancel_transition_watchdog()

        if self._current_transition:
            try:
                self._current_transition.stop()
            except Exception:
                logger.debug("[WATCHDOG] Failed to stop transition during timeout", exc_info=True)
            try:
                self._current_transition.cleanup()
            except Exception:
                logger.debug("[WATCHDOG] Failed to cleanup transition during timeout", exc_info=True)
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
        # Thread-safe check: if any overlay is ready (GL initialized + first frame drawn), let it handle painting
        try:
            if any_overlay_ready_for_display(self):
                # Overlay is ready and will handle the paint
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
        # Fill with black background
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        
        # Draw image if available
        if pixmap_to_paint and not pixmap_to_paint.isNull():
            try:
                painter.drawPixmap(self.rect(), pixmap_to_paint)
            except Exception:
                painter.drawPixmap(0, 0, pixmap_to_paint)
        
        # Draw error message if present
        elif self.error_message:
            painter.setPen(Qt.GlobalColor.white)
            font = QFont("Arial", 24)
            painter.setFont(font)
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self.error_message
            )
        
        painter.end()
    
    def notify_overlay_ready(self, overlay_name: str, stage: str, **details) -> None:
        """Diagnostic hook invoked by overlays when they report readiness."""
        self._last_overlay_ready_ts = time.monotonic()
        seed_age_ms = None
        if self._last_pixmap_seed_ts is not None:
            seed_age_ms = (self._last_overlay_ready_ts - self._last_pixmap_seed_ts) * 1000.0
        key = f"{overlay_name}:{stage}"
        self._overlay_stage_counts[key] += 1
        # Avoid logging huge pixmap representations in details
        sanitized_details = dict(details)
        if "base_pixmap" in sanitized_details:
            try:
                bp = sanitized_details["base_pixmap"]
                # Summarize pixmap geometry if possible
                from PySide6.QtGui import QPixmap  # type: ignore
                if isinstance(bp, QPixmap) and not bp.isNull():
                    sanitized_details["base_pixmap"] = f"Pixmap(size={bp.width()}x{bp.height()}, dpr={bp.devicePixelRatioF():.2f})"
                else:
                    sanitized_details["base_pixmap"] = "<pixmap>"
            except Exception:
                sanitized_details["base_pixmap"] = "<pixmap>"
        logger.debug(
            "[DIAG] Overlay readiness (name=%s, stage=%s, seed_age_ms=%s, count=%s, details=%s)",
            overlay_name,
            stage,
            f"{seed_age_ms:.2f}" if seed_age_ms is not None else "N/A",
            self._overlay_stage_counts[key],
            sanitized_details,
        )
        if stage == "gl_initialized":
            try:
                actual_swap = str(details.get("swap", ""))
            except Exception:
                actual_swap = str(details.get("swap", ""))
            if "triple" not in actual_swap.lower():
                if overlay_name not in self._overlay_swap_warned:
                    logger.info(
                        "[DIAG] Overlay swap = %s (screen=%s, name=%s, interval=%s) — driver enforced double buffer",
                        actual_swap or "Unknown",
                        self.screen_index,
                        overlay_name,
                        details.get("interval", "?"),
                    )
                    self._overlay_swap_warned.add(overlay_name)

    def get_overlay_stage_counts(self) -> dict[str, int]:
        """Return snapshot of overlay readiness counts (for diagnostics/tests)."""
        return dict(self._overlay_stage_counts)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press - hotkeys and exit."""
        key = event.key()
        key_text = event.text().lower()
        
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
            self.exit_requested.emit()
            event.accept()
        # FIX: Don't exit on any key - only specific hotkeys and exit keys
        else:
            logger.debug(f"Unknown key pressed: {key} - ignoring")
            event.ignore()
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press - exit on any click unless hard exit is enabled."""
        if self._is_hard_exit_enabled():
            # In hard-exit mode, ignore mouse clicks for exit purposes.
            event.accept()
            return

        logger.info(f"Mouse clicked at ({event.pos().x()}, {event.pos().y()}), requesting exit")
        self.exit_requested.emit()
        event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move - exit if moved beyond threshold (unless hard exit)."""

        if self._is_hard_exit_enabled():
            # Hard exit mode disables mouse-move exit entirely.
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
            self.exit_requested.emit()
        
        event.accept()

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
